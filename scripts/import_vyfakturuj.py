#!/usr/bin/env python3
"""
Import dat z Vyfakturuj.cz do InvoiCzech.

Použití:
    ./venv/bin/python3 scripts/import_vyfakturuj.py \
        --contacts  "Adresář - 21.03.2026.csv" \
        --invoices  "Vyfakturuj.cz export 2021-03-01 - 2026-03-31 samuel-wlaschinsky.csv" \
        --expenses  "Vyfakturuj.cz export samuel-wlaschinsky.csv"

Přidejte --dry-run pro testovací běh bez zápisu do DB.
"""

import argparse
import csv
import sys
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.contact import Contact
from app.models.expense import Expense, ExpenseItem
from app.models.invoice import Invoice, InvoiceItem

ENCODING = "cp1250"


# ── Pomocné funkce ────────────────────────────────────────────────────────────

def read_csv(path: str) -> list[dict]:
    with open(path, encoding=ENCODING, newline="") as f:
        reader = csv.DictReader(f, delimiter=";", quotechar='"')
        return [row for row in reader]


def parse_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%d.%m.%Y").date()
    except ValueError:
        return None


def parse_decimal(s: str) -> Decimal:
    s = (s or "").strip().replace(",", ".")
    if not s:
        return Decimal("0")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")


def split_pipe(s: str) -> list[str]:
    """Rozdělí pipe-separated hodnotu, vrátí seznam."""
    s = (s or "").strip()
    if not s:
        return []
    return [x.strip() for x in s.split("|")]


def price_without_vat(price_with_vat: Decimal, vat_rate: int) -> Decimal:
    """Přepočítá cenu S DPH na cenu BEZ DPH."""
    if vat_rate == 0:
        return price_with_vat
    return (price_with_vat / Decimal(str(1 + vat_rate / 100))).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )


# ── Import kontaktů ───────────────────────────────────────────────────────────

def import_contacts(db, rows: list[dict], dry_run: bool) -> dict[str, int]:
    """
    Importuje kontakty z adresáře. Vrátí mapping {ico: contact_id}.
    Deduplikuje podle IČO — přeskočí kontakty se stejným IČO.
    """
    ico_map: dict[str, int] = {}  # ico → contact.id

    # Načti existující kontakty z DB
    for c in db.query(Contact).all():
        if c.ico:
            ico_map[c.ico] = c.id

    imported = skipped = 0

    for row in rows:
        ico = (row.get("IČO") or row.get("IÈO") or "").strip()
        name = (row.get("Firma/osoba") or row.get("Váš název") or row.get("Vá název") or "").strip()
        if not name:
            continue

        if ico and ico in ico_map:
            skipped += 1
            continue

        contact = Contact(
            name=name,
            ico=ico or None,
            dic=(row.get("DIČ") or row.get("DIÈ") or "").strip() or None,
            street=(row.get("Ulice") or "").strip() or None,
            city=(row.get("Město") or row.get("Mìsto") or "").strip() or None,
            zip_code=(row.get("PSČ") or row.get("PSÈ") or "").strip() or None,
            country=(row.get("Země") or row.get("Zemì") or "Česká republika").strip(),
            email=(row.get("E-mail") or "").strip() or None,
            phone=(row.get("Telefon") or "").strip() or None,
            contact_type="Odběratel",
        )

        if not dry_run:
            db.add(contact)
            db.flush()
            if ico:
                ico_map[ico] = contact.id
        else:
            if ico:
                ico_map[ico] = -1  # placeholder pro dry run

        imported += 1

    if not dry_run:
        db.commit()

    print(f"  Kontakty: {imported} importováno, {skipped} přeskočeno (duplikát IČO)")
    return ico_map


def ensure_supplier_contact(db, ico: str, name: str, dic: str, street: str, city: str,
                             zip_code: str, country: str, ico_map: dict, dry_run: bool) -> int | None:
    """Zajistí existenci dodavatelského kontaktu, vrátí jeho ID."""
    if ico and ico in ico_map:
        return ico_map[ico]

    # Zkusí najít v DB podle IČO
    if ico:
        existing = db.query(Contact).filter(Contact.ico == ico).first()
        if existing:
            ico_map[ico] = existing.id
            return existing.id

    contact = Contact(
        name=name or "Neznámý dodavatel",
        ico=ico or None,
        dic=dic or None,
        street=street or None,
        city=city or None,
        zip_code=zip_code or None,
        country=country or "Česká republika",
        contact_type="Dodavatel",
    )
    if not dry_run:
        db.add(contact)
        db.flush()
        if ico:
            ico_map[ico] = contact.id
        return contact.id
    return None


# ── Import faktur ─────────────────────────────────────────────────────────────

def import_invoices(db, rows: list[dict], ico_map: dict, dry_run: bool):
    imported = skipped = 0

    # Existující čísla faktur
    existing_numbers = {r[0] for r in db.query(Invoice.number).all()}

    for row in rows:
        number = (row.get("Číslo dokladu") or row.get("Èíslo dokladu") or "").strip()
        if not number:
            continue
        if number in existing_numbers:
            skipped += 1
            continue

        issue_date = parse_date(row.get("Datum vystavení") or "")
        due_date = parse_date(row.get("Datum splatnosti") or "")
        duzp = parse_date(row.get("Datum zdanitelného plnění") or row.get("Datum zdanitelného plnìní") or "")
        paid_date = parse_date(row.get("Datum úhrady") or "")

        if not issue_date or not due_date:
            print(f"  ! Faktura {number}: chybí datum, přeskakuji")
            skipped += 1
            continue

        status = "Uhrazena" if paid_date else "Vystavena"

        contact_name = (row.get("Společnost odběratele") or row.get("Spoleènost odbìratele") or "").strip()
        contact_ico = (row.get("IČO odběratele") or row.get("IÈO odbìratele") or "").strip()
        contact_dic = (row.get("DIČ odběratele") or row.get("DIÈ odbìratele") or "").strip()
        contact_street = (row.get("Ulice odběratele") or row.get("Ulice odbìratele") or "").strip()
        contact_city = (row.get("Město odběratele") or row.get("Mìsto odbìratele") or "").strip()
        contact_zip = (row.get("PSČ odběratele") or row.get("PSÈ odbìratele") or "").strip()

        contact_id = ico_map.get(contact_ico) if contact_ico else None
        variable_symbol = (row.get("Variabilní Symbol") or row.get("Variabilní symbol") or "").strip()
        payment_method = (row.get("Platební metoda") or "Bankovní převod").strip() or "Bankovní převod"

        # Parsování položek
        quantities = split_pipe(row.get("Položky počet") or row.get("Poloky poèet") or "")
        descriptions = split_pipe(row.get("Položky text") or row.get("Poloky text") or "")
        prices = split_pipe(row.get("Položky cena") or row.get("Poloky cena") or "")
        vat_rates = split_pipe(row.get("Položky %DPH") or row.get("Poloky %DPH") or "")

        if not descriptions or not prices:
            print(f"  ! Faktura {number}: chybí položky, přeskakuji")
            skipped += 1
            continue

        invoice = Invoice(
            number=number,
            contact_id=contact_id,
            contact_name=contact_name or None,
            contact_ico=contact_ico or None,
            contact_dic=contact_dic or None,
            contact_street=contact_street or None,
            contact_city=contact_city or None,
            contact_zip=contact_zip or None,
            issue_date=issue_date,
            due_date=due_date,
            duzp=duzp or issue_date,
            payment_method=payment_method,
            variable_symbol=variable_symbol or None,
            status=status,
            paid_date=paid_date,
        )

        if not dry_run:
            db.add(invoice)
            db.flush()

        n = max(len(descriptions), len(prices))
        for i in range(n):
            desc = descriptions[i] if i < len(descriptions) else ""
            qty_str = quantities[i] if i < len(quantities) else "1"
            price_str = prices[i] if i < len(prices) else "0"
            vat_str = vat_rates[i] if i < len(vat_rates) else "0"

            try:
                qty = Decimal(qty_str) if qty_str else Decimal("1")
            except Exception:
                qty = Decimal("1")
            price = parse_decimal(price_str)
            try:
                vat = int(vat_str) if vat_str else 0
            except Exception:
                vat = 0

            if not dry_run:
                item = InvoiceItem(
                    invoice_id=invoice.id,
                    description=desc or "—",
                    quantity=qty,
                    unit_price=price,
                    vat_rate=vat,
                    position=i,
                )
                db.add(item)

        imported += 1
        existing_numbers.add(number)

    if not dry_run:
        db.commit()

    print(f"  Faktury: {imported} importováno, {skipped} přeskočeno")


# ── Import nákladů ────────────────────────────────────────────────────────────

def import_expenses(db, rows: list[dict], ico_map: dict, dry_run: bool):
    imported = skipped = 0

    existing_numbers = {r[0] for r in db.query(Expense.number).all()}

    for row in rows:
        number = (row.get("Doklad") or "").strip()
        if not number:
            continue
        if number in existing_numbers:
            skipped += 1
            continue

        issue_date = parse_date(row.get("Datum vystavení") or "")
        paid_date = parse_date(row.get("Datum úhrady") or "")

        if not issue_date:
            print(f"  ! Náklad {number}: chybí datum vystavení, přeskakuji")
            skipped += 1
            continue

        supplier_name = (row.get("Společnost dodavatele") or row.get("Spoleènost dodavatele") or "").strip()
        supplier_ico = (row.get("IČO dodavatele") or row.get("IÈO dodavatele") or "").strip()
        supplier_dic = (row.get("DIČ dodavatele") or row.get("DIÈ dodavatele") or "").strip()
        supplier_street = (row.get("Ulice dodavatele") or "").strip()
        supplier_city = (row.get("Město dodavatele") or row.get("Mìsto dodavatele") or "").strip()
        supplier_zip = (row.get("PSČ dodavatele") or row.get("PSÈ dodavatele") or "").strip()
        supplier_country = (row.get("Země dodavatele") or row.get("Zemì dodavatele") or "Česká republika").strip()

        contact_id = ensure_supplier_contact(
            db, supplier_ico, supplier_name, supplier_dic,
            supplier_street, supplier_city, supplier_zip, supplier_country,
            ico_map, dry_run
        )

        # Parsování položek
        descriptions = split_pipe(row.get("Položky text") or row.get("Poloky text") or "")
        prices_raw = split_pipe(row.get("Položky cena") or row.get("Poloky cena") or "")
        vat_rates = split_pipe(row.get("Položky %DPH") or row.get("Poloky %DPH") or "")
        quantities = split_pipe(row.get("Položky počet") or row.get("Poloky poèet") or "")

        if not prices_raw:
            print(f"  ! Náklad {number}: chybí cena, přeskakuji")
            skipped += 1
            continue

        # Název nákladu
        title_tag = (row.get("Štítek") or row.get("títek") or "").strip()
        first_desc = descriptions[0] if descriptions else ""
        title = title_tag or first_desc or supplier_name or number

        expense = Expense(
            number=number,
            title=title[:200],
            contact_id=contact_id,
            contact_name=supplier_name or None,
            issue_date=issue_date,
            duzp=issue_date,
            paid_date=paid_date,
            payment_method="Bankovní převod",
            document_type="Faktura",
            tax_deductible="Ano",
            price_includes_vat=False,  # ukládáme vždy BEZ DPH
        )

        if not dry_run:
            db.add(expense)
            db.flush()

        n = max(len(descriptions), len(prices_raw))
        for i in range(n):
            desc = descriptions[i] if i < len(descriptions) else ""
            price_str = prices_raw[i] if i < len(prices_raw) else "0"
            vat_str = vat_rates[i] if i < len(vat_rates) else "21"
            qty_str = quantities[i] if i < len(quantities) else "1"

            price_with_vat = parse_decimal(price_str)
            try:
                vat = int(vat_str) if vat_str else 21
            except Exception:
                vat = 21
            try:
                qty = Decimal(qty_str) if qty_str else Decimal("1")
            except Exception:
                qty = Decimal("1")

            # Cena je v CSV S DPH → přepočítáme na bez DPH
            unit_price = price_without_vat(price_with_vat, vat)

            if not dry_run:
                item = ExpenseItem(
                    expense_id=expense.id,
                    description=desc or supplier_name or "—",
                    quantity=qty,
                    unit=("ks"),
                    unit_price=unit_price,
                    vat_rate=vat,
                    position=i,
                )
                db.add(item)

        imported += 1
        existing_numbers.add(number)

    if not dry_run:
        db.commit()

    print(f"  Náklady: {imported} importováno, {skipped} přeskočeno")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Import z Vyfakturuj.cz")
    parser.add_argument("--contacts", required=True, help="CSV adresáře")
    parser.add_argument("--invoices", required=True, help="CSV faktur")
    parser.add_argument("--expenses", required=True, help="CSV nákladů")
    parser.add_argument("--dry-run", action="store_true", help="Pouze simulace, nezapisuje do DB")
    args = parser.parse_args()

    if args.dry_run:
        print("=== DRY RUN — do DB se nic nezapíše ===\n")

    db = SessionLocal()
    try:
        print("Načítám kontakty...")
        contact_rows = read_csv(args.contacts)
        ico_map = import_contacts(db, contact_rows, args.dry_run)

        print("Načítám faktury...")
        invoice_rows = read_csv(args.invoices)
        import_invoices(db, invoice_rows, ico_map, args.dry_run)

        print("Načítám náklady...")
        expense_rows = read_csv(args.expenses)
        import_expenses(db, expense_rows, ico_map, args.dry_run)

        print("\nHotovo.")
    except Exception as e:
        db.rollback()
        print(f"\nChyba: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
