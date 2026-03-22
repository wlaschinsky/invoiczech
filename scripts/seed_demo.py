#!/usr/bin/env python3
"""
Generátor demo dat pro InvoiCzech.

Vytvoří smyšlený profil, adresář kontaktů, faktury a náklady
za rok 2025 (leden–prosinec) a 2026 (leden–únor).

Použití:
    ./venv/bin/python3 scripts/seed_demo.py
    ./venv/bin/python3 scripts/seed_demo.py --dry-run
    ./venv/bin/python3 scripts/seed_demo.py --clear   # smaže vše a seeduje znovu
"""

import argparse
import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.contact import Contact
from app.models.expense import Expense, ExpenseItem
from app.models.invoice import Invoice, InvoiceItem
from app.models.profile import Profile

# ── Deterministický seed pro reprodukovatelnost ───────────────────────────────
random.seed(42)


# ── Demo profil ───────────────────────────────────────────────────────────────

PROFILE = dict(
    first_name="Tomáš",
    last_name="Novák",
    email="tomas.novak@demofirma.cz",
    phone="+420 731 123 456",
    company_name="",
    ico="87654321",
    dic="CZ8765432100",
    vat_payer=True,
    street="Korunní",
    house_number="48",
    orientation_number="",
    city="Praha",
    zip_code="120 00",
    country="Česká republika",
    bank_name="Fio banka",
    bank_account="2800123456/2010",
    iban="CZ6520100000002800123456",
    currency="CZK",
    fu_ufo="FU pro Prahu 2",
    fu_pracufo="451",
    okec="6201",
    ds_type="F",
    default_due_days=14,
    default_payment_method="Bankovní převod",
    default_invoice_text="Fakturujeme Vám za poskytnuté služby.",
    default_vat_rate=21,
)


# ── Demo kontakty ─────────────────────────────────────────────────────────────

CONTACTS = [
    # Odběratelé
    dict(
        name="Softex Solutions s.r.o.",
        ico="12345678",
        dic="CZ12345678",
        street="Wenceslas Square 15",
        city="Praha",
        zip_code="110 00",
        email="fakturace@softex.cz",
        phone="+420 222 111 000",
        contact_type="Odběratel",
    ),
    dict(
        name="MediaGroup a.s.",
        ico="22334455",
        dic="CZ22334455",
        street="Náměstí Míru 7",
        city="Praha",
        zip_code="120 00",
        email="billing@mediagroup.cz",
        phone="+420 224 500 600",
        contact_type="Odběratel",
    ),
    dict(
        name="StartupHub Czech s.r.o.",
        ico="33445566",
        dic="CZ33445566",
        street="Technická 12",
        city="Brno",
        zip_code="616 00",
        email="office@startuphub.cz",
        phone="+420 548 100 200",
        contact_type="Odběratel",
    ),
    dict(
        name="DigitalFactory s.r.o.",
        ico="44556677",
        dic="CZ44556677",
        street="Lindnerova 4",
        city="Praha",
        zip_code="180 00",
        email="kontakt@digitalfactory.cz",
        phone="+420 266 300 400",
        contact_type="Odběratel",
    ),
    dict(
        name="Svoboda & Partners v.o.s.",
        ico="55667788",
        dic=None,
        street="Jiráskovo náměstí 2",
        city="České Budějovice",
        zip_code="370 01",
        email="info@svobodapartners.cz",
        phone="+420 387 200 300",
        contact_type="Odběratel",
    ),
    # Dodavatelé
    dict(
        name="O2 Czech Republic a.s.",
        ico="60193336",
        dic="CZ60193336",
        street="Za Brumlovkou 266/2",
        city="Praha",
        zip_code="140 22",
        email="fakturace@o2.cz",
        phone="800 020 202",
        contact_type="Dodavatel",
    ),
    dict(
        name="Microsoft s.r.o.",
        ico="47123737",
        dic="CZ47123737",
        street="BB Centrum, Vyskočilova 1461/2a",
        city="Praha",
        zip_code="140 00",
        email="billing@microsoft.com",
        phone="+420 221 842 200",
        contact_type="Dodavatel",
    ),
    dict(
        name="Hetzner Online GmbH",
        ico=None,
        dic=None,
        street="Industriestr. 25",
        city="Gunzenhausen",
        zip_code="91710",
        email="info@hetzner.com",
        phone="+49 9831 505-0",
        contact_type="Dodavatel",
    ),
    dict(
        name="Adobe Systems Software Ireland",
        ico=None,
        dic=None,
        street="4-6 Riverwalk, Citywest Business Campus",
        city="Dublin",
        zip_code="D24 FK65",
        email="billing@adobe.com",
        phone=None,
        contact_type="Dodavatel",
    ),
    dict(
        name="Účetní kancelář Horáková s.r.o.",
        ico="72345678",
        dic="CZ72345678",
        street="Blanická 8",
        city="Praha",
        zip_code="120 00",
        email="info@horakova-uctarna.cz",
        phone="+420 222 980 100",
        contact_type="Dodavatel",
    ),
    dict(
        name="Datart International a.s.",
        ico="26204676",
        dic="CZ26204676",
        street="Türkova 1001/2",
        city="Praha",
        zip_code="149 00",
        email="eshop@datart.cz",
        phone="840 840 840",
        contact_type="Dodavatel",
    ),
]


# ── Šablony fakturačních položek (odběratel → popis, cena BEZ DPH) ────────────

INVOICE_ITEMS_POOL = [
    ("Vývoj webové aplikace — sprint", Decimal("25000")),
    ("Konzultace IT architektury (4 hod.)", Decimal("6000")),
    ("Správa serverové infrastruktury — měsíční paušál", Decimal("8000")),
    ("SEO analýza a optimalizace", Decimal("12000")),
    ("Tvorba grafického designu — landing page", Decimal("9500")),
    ("Implementace API integrace", Decimal("18000")),
    ("Code review a technický audit", Decimal("7500")),
    ("Vývoj mobilní aplikace — modul platby", Decimal("32000")),
    ("Školení — React & TypeScript (1 den)", Decimal("5000")),
    ("Databázová migrace a optimalizace", Decimal("14000")),
    ("Bezpečnostní audit aplikace", Decimal("11000")),
    ("Technická dokumentace projektu", Decimal("4500")),
    ("UX/UI redesign dashboard", Decimal("22000")),
    ("Integrace CRM systému", Decimal("16500")),
    ("Maintenance & podpora — kvartální paušál", Decimal("15000")),
]

# Šablony nákladových položek (dodavatel → [položky])
EXPENSE_ITEMS_POOL = {
    "O2 Czech Republic a.s.": [
        ("Mobilní tarif — Business L", Decimal("800"), 21),
        ("Datové připojení — Business Fiber", Decimal("990"), 21),
    ],
    "Microsoft s.r.o.": [
        ("Microsoft 365 Business — předplatné", Decimal("380"), 21),
    ],
    "Hetzner Online GmbH": [
        ("VPS server CX21 — měsíční nájem", Decimal("200"), 21),
        ("Object Storage 500 GB", Decimal("95"), 21),
    ],
    "Adobe Systems Software Ireland": [
        ("Adobe Creative Cloud — All Apps", Decimal("1500"), 21),
    ],
    "Účetní kancelář Horáková s.r.o.": [
        ("Vedení účetnictví — měsíční paušál", Decimal("3500"), 21),
        ("Zpracování daňového přiznání", Decimal("4500"), 21),
    ],
    "Datart International a.s.": [
        ("Monitor LG 27\" 4K", Decimal("7900"), 21),
        ("Mechanická klávesnice Logitech MX", Decimal("3200"), 21),
        ("Webkamera Logitech Brio 4K", Decimal("3800"), 21),
    ],
}


# ── Pomocné funkce ────────────────────────────────────────────────────────────

def next_weekday(d: date) -> date:
    """Přesune datum na nejbližší pracovní den (pondělí–pátek)."""
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def make_date(year: int, month: int, day_hint: int) -> date:
    """Vytvoří datum a posunut na pracovní den."""
    import calendar
    max_day = calendar.monthrange(year, month)[1]
    day = min(day_hint, max_day)
    return next_weekday(date(year, month, day))


def paid_or_not(issue: date, chance: float = 0.85) -> date | None:
    """S pravděpodobností chance vrátí datum úhrady 3–10 dní po vystavení."""
    if random.random() < chance:
        return issue + timedelta(days=random.randint(3, 10))
    return None


# ── Seed funkce ───────────────────────────────────────────────────────────────

def seed_profile(db, dry_run: bool):
    profile = db.query(Profile).filter(Profile.id == 1).first()
    if profile:
        for k, v in PROFILE.items():
            setattr(profile, k, v)
    else:
        profile = Profile(id=1, **PROFILE)
        db.add(profile)
    if not dry_run:
        db.commit()
    print("  Profil: nastaven")


def seed_contacts(db, dry_run: bool) -> dict[str, int]:
    """Vrátí mapping name → contact.id."""
    name_map: dict[str, int] = {}
    imported = skipped = 0
    for c in CONTACTS:
        existing = db.query(Contact).filter(Contact.name == c["name"]).first()
        if existing:
            name_map[c["name"]] = existing.id
            skipped += 1
            continue
        contact = Contact(country="Česká republika", **c)
        if not dry_run:
            db.add(contact)
            db.flush()
            name_map[c["name"]] = contact.id
        else:
            name_map[c["name"]] = -(imported + 1)
        imported += 1
    if not dry_run:
        db.commit()
    print(f"  Kontakty: {imported} přidáno, {skipped} přeskočeno")
    return name_map


def seed_invoices(db, name_map: dict[str, int], dry_run: bool):
    """
    Generuje faktury:
    - 2025: ~2 faktury/měsíc (leden–prosinec)
    - 2026: 1–2 faktury/měsíc (leden–únor)
    """
    existing = {r[0] for r in db.query(Invoice.number).all()}
    clients = [c for c in CONTACTS if c["contact_type"] == "Odběratel"]
    imported = skipped = 0
    counter = 1

    periods = (
        [(2025, m) for m in range(1, 13)] +
        [(2026, m) for m in range(1, 3)]
    )

    for year, month in periods:
        count = 1 if (year == 2026) else random.choice([2, 2, 3])
        for _ in range(count):
            number = f"FA {year}{counter:03d}"
            counter += 1
            if number in existing:
                skipped += 1
                continue

            client = random.choice(clients)
            issue = make_date(year, month, random.randint(2, 20))
            due = issue + timedelta(days=14)
            paid = paid_or_not(issue)
            status = "Uhrazena" if paid else "Vystavena"

            items_pool = random.sample(INVOICE_ITEMS_POOL, k=random.randint(1, 3))

            invoice = Invoice(
                number=number,
                contact_id=name_map.get(client["name"]),
                contact_name=client["name"],
                contact_ico=client.get("ico"),
                contact_dic=client.get("dic"),
                contact_street=client.get("street"),
                contact_city=client.get("city"),
                contact_zip=client.get("zip_code"),
                contact_email=client.get("email"),
                issue_date=issue,
                due_date=due,
                duzp=issue,
                payment_method="Bankovní převod",
                variable_symbol=str(number.replace("FA ", "")),
                status=status,
                paid_date=paid,
            )

            if not dry_run:
                db.add(invoice)
                db.flush()
                for i, (desc, price) in enumerate(items_pool):
                    db.add(InvoiceItem(
                        invoice_id=invoice.id,
                        description=desc,
                        quantity=Decimal("1"),
                        unit_price=price,
                        vat_rate=21,
                        position=i,
                    ))

            imported += 1
            existing.add(number)

    if not dry_run:
        db.commit()
    print(f"  Faktury: {imported} přidáno, {skipped} přeskočeno")


def seed_expenses(db, name_map: dict[str, int], dry_run: bool):
    """
    Generuje náklady:
    - Pravidelné měsíční (O2, Microsoft, Hetzner, Adobe)
    - Čtvrtletní (Účetní kancelář)
    - Jednorázové (Datart — 2025 Q2)
    """
    existing = {r[0] for r in db.query(Expense.number).all()}
    imported = skipped = 0

    # (dodavatel, měsíce kdy se fakturuje, rok_start, rok_end)
    schedule = [
        ("O2 Czech Republic a.s.",         list(range(1, 13)), 2025, 2026),
        ("Microsoft s.r.o.",               list(range(1, 13)), 2025, 2026),
        ("Hetzner Online GmbH",            list(range(1, 13)), 2025, 2026),
        ("Adobe Systems Software Ireland", list(range(1, 13)), 2025, 2026),
        ("Účetní kancelář Horáková s.r.o.", [1, 3, 4, 7, 10], 2025, 2026),
        ("Datart International a.s.",      [4],                2025, 2025),
    ]

    counter = 1
    for supplier_name, months, yr_start, yr_end in schedule:
        supplier = next((c for c in CONTACTS if c["name"] == supplier_name), None)
        items_defs = EXPENSE_ITEMS_POOL.get(supplier_name, [])
        if not items_defs or not supplier:
            continue

        for year in range(yr_start, yr_end + 1):
            for month in months:
                if year == 2026 and month > 2:
                    break
                number = f"N{year}{counter:05d}"
                counter += 1
                if number in existing:
                    skipped += 1
                    continue

                issue = make_date(year, month, random.randint(1, 10))
                paid = paid_or_not(issue, chance=0.9)

                # Pro účetní daňové přiznání = jiný typ
                doc_type = "Faktura"
                if supplier_name == "Datart International a.s.":
                    doc_type = "Účtenka"

                first_desc = items_defs[0][0]
                title = first_desc[:80]

                expense = Expense(
                    number=number,
                    title=title,
                    contact_id=name_map.get(supplier_name),
                    contact_name=supplier_name,
                    issue_date=issue,
                    duzp=issue,
                    paid_date=paid,
                    payment_method="Bankovní převod",
                    document_type=doc_type,
                    tax_deductible="Ano",
                    price_includes_vat=False,
                )

                if not dry_run:
                    db.add(expense)
                    db.flush()
                    for i, (desc, price, vat) in enumerate(items_defs):
                        db.add(ExpenseItem(
                            expense_id=expense.id,
                            description=desc,
                            quantity=Decimal("1"),
                            unit="ks",
                            unit_price=price,
                            vat_rate=vat,
                            position=i,
                        ))

                imported += 1
                existing.add(number)

    if not dry_run:
        db.commit()
    print(f"  Náklady: {imported} přidáno, {skipped} přeskočeno")


def clear_data(db):
    """Smaže všechna data (profil, kontakty, faktury, náklady)."""
    from app.models.invoice import InvoiceItem
    from app.models.expense import ExpenseItem, ExpenseAttachment
    db.query(InvoiceItem).delete()
    db.query(Invoice).delete()
    db.query(ExpenseItem).delete()
    db.query(ExpenseAttachment).delete()
    db.query(Expense).delete()
    db.query(Contact).delete()
    db.query(Profile).delete()
    db.commit()
    print("  Data vymazána.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Seed demo dat pro InvoiCzech")
    parser.add_argument("--dry-run", action="store_true", help="Pouze simulace, nezapisuje do DB")
    parser.add_argument("--clear", action="store_true", help="Smaže stávající data a seeduje znovu")
    args = parser.parse_args()

    if args.dry_run:
        print("=== DRY RUN — do DB se nic nezapíše ===\n")

    db = SessionLocal()
    try:
        if args.clear and not args.dry_run:
            print("Mažu stávající data...")
            clear_data(db)

        print("Seeding demo dat...")
        seed_profile(db, args.dry_run)
        name_map = seed_contacts(db, args.dry_run)
        seed_invoices(db, name_map, args.dry_run)
        seed_expenses(db, name_map, args.dry_run)
        print("\nHotovo.")
    except Exception as e:
        db.rollback()
        print(f"\nChyba: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
