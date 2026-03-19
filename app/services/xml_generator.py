"""Generování XML exportů pro portál Moje Daně (KH1, DP3)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple
from xml.etree import ElementTree as ET
from xml.dom import minidom

from sqlalchemy.orm import Session

from ..models.contact import Contact  # noqa — potřeba pro SQLAlchemy relationship
from ..models.invoice import Invoice
from ..models.expense import Expense


def _next_month_start(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def _period_dates(year: int, month: int, quarter: bool) -> tuple[date, date]:
    """Vrátí (od, do_exclusive) pro dané období."""
    if not quarter:
        return date(year, month, 1), _next_month_start(year, month)
    first_month = ((month - 1) * 3) + 1  # quarter=1→1, 2→4, 3→7, 4→10
    last_month = first_month + 2
    return date(year, first_month, 1), _next_month_start(year, last_month)


def _round_czk(value) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _prettify(root: ET.Element) -> str:
    raw = ET.tostring(root, encoding="unicode")
    parsed = minidom.parseString(raw.encode("utf-8"))
    return parsed.toprettyxml(indent="  ", encoding="UTF-8").decode("utf-8")


def generate_kh1(
    db: Session,
    year: int,
    period: int,
    quarter: bool = False,
    submission_date: date | None = None,
) -> str:
    """Vygeneruje XML Kontrolního hlášení (KH1)."""
    from ..config import get_settings
    settings = get_settings()

    if submission_date is None:
        submission_date = date.today()

    date_from, date_to = _period_dates(year, period, quarter)
    mesic = (period - 1) * 3 + 1 if quarter else period

    invoices: List[Invoice] = (
        db.query(Invoice)
        .filter(
            Invoice.status != "Stornována",
            Invoice.duzp >= date_from,
            Invoice.duzp < date_to,
        )
        .all()
    )

    deductible_expenses: List[Expense] = (
        db.query(Expense)
        .filter(
            Expense.tax_deductible.in_(["Ano", "Nevím"]),
            Expense.duzp >= date_from,
            Expense.duzp < date_to,
        )
        .all()
    )

    # --- XML ---
    pisemnost = ET.Element("Pisemnost", nazevSW="FakturacniApp", verzeSW="1.0")
    dphkh1 = ET.SubElement(pisemnost, "DPHKH1", verzePis="02.01")

    ET.SubElement(
        dphkh1,
        "VetaD",
        mesic=str(mesic),
        rok=str(year),
        dokument="KH1",
        d_poddp=submission_date.strftime("%Y-%m-%d"),
        k_uladis="DPH",
        khdph_forma="B",
    )
    ET.SubElement(
        dphkh1,
        "VetaP",
        c_pracufo=settings.SUPPLIER_FU_PRACUFO,
        c_ufo=settings.SUPPLIER_FU_UFO,
        email=settings.SUPPLIER_EMAIL,
        typ_ds="F",
        dic=settings.SUPPLIER_DIC.replace("CZ", ""),
        ulice=settings.SUPPLIER_STREET.split(" ")[0] if " " in settings.SUPPLIER_STREET else settings.SUPPLIER_STREET,
        c_pop="2284",
        c_orient="21",
        c_telef=settings.SUPPLIER_PHONE,
        naz_obce=settings.SUPPLIER_CITY,
        psc=settings.SUPPLIER_ZIP.replace(" ", ""),
        stat="Česká republika",
        jmeno="Samuel",
        prijmeni="Wlaschinský",
        titul="",
    )

    ET.SubElement(dphkh1, "VetaA1")

    # VetaA4 — vydané faktury B2B, základ > 10 000 Kč
    for inv in invoices:
        base_21 = sum(
            item.subtotal for item in inv.items if item.vat_rate == 21
        )
        vat_21 = sum(
            item.vat_amount for item in inv.items if item.vat_rate == 21
        )
        if base_21 > Decimal("10000"):
            contact_dic = (inv.contact_dic or "").replace("CZ", "")
            ET.SubElement(
                dphkh1,
                "VetaA4",
                c_evid_dd=inv.number,
                dan1=str(_round_czk(vat_21)),
                dic_odb=contact_dic,
                dppd=(inv.duzp or inv.issue_date).strftime("%Y-%m-%d"),
                zakl_dane1=str(_round_czk(base_21)),
                kod_rezim_pl="0",
                zdph_44="N",
            )

    ET.SubElement(dphkh1, "VetaA5")
    ET.SubElement(dphkh1, "VetaB1")
    ET.SubElement(dphkh1, "VetaB2")

    # VetaB3 — souhrnný řádek daňově uznatelných nákladů
    b3_base = sum(
        sum(item.subtotal for item in exp.items if item.vat_rate == 21)
        for exp in deductible_expenses
    )
    b3_vat = sum(
        sum(item.vat_amount for item in exp.items if item.vat_rate == 21)
        for exp in deductible_expenses
    )
    if b3_base > 0:
        ET.SubElement(
            dphkh1,
            "VetaB3",
            dan1=str(_round_czk(b3_vat)),
            zakl_dane1=str(_round_czk(b3_base)),
        )

    # VetaC — celkové obraty
    obrat_21 = sum(
        sum(item.subtotal for item in inv.items if item.vat_rate == 21)
        for inv in invoices
    )
    odpocet_21 = b3_base

    ET.SubElement(
        dphkh1,
        "VetaC",
        obrat23=str(_round_czk(obrat_21)),
        obrat5="0",
        pln23=str(_round_czk(odpocet_21)),
        pln5="0",
    )

    return _prettify(pisemnost)


def generate_dp3(
    db: Session,
    year: int,
    period: int,
    quarter: bool = False,
    submission_date: date | None = None,
) -> str:
    """Vygeneruje XML Přiznání k DPH (DP3)."""
    from ..config import get_settings
    settings = get_settings()

    if submission_date is None:
        submission_date = date.today()

    date_from, date_to = _period_dates(year, period, quarter)
    mesic = (period - 1) * 3 + 1 if quarter else period

    invoices: List[Invoice] = (
        db.query(Invoice)
        .filter(
            Invoice.status != "Stornována",
            Invoice.duzp >= date_from,
            Invoice.duzp < date_to,
        )
        .all()
    )

    deductible_expenses: List[Expense] = (
        db.query(Expense)
        .filter(
            Expense.tax_deductible.in_(["Ano", "Nevím"]),
            Expense.duzp >= date_from,
            Expense.duzp < date_to,
        )
        .all()
    )

    # Výstupy (faktury)
    obrat_21 = sum(
        sum(item.subtotal for item in inv.items if item.vat_rate == 21)
        for inv in invoices
    )
    dan_vystupu = sum(
        sum(item.vat_amount for item in inv.items if item.vat_rate == 21)
        for inv in invoices
    )
    dan_vystupu_zaokr = _round_czk(dan_vystupu)

    # Vstupy (náklady)
    zakl_odpoctu_21 = sum(
        sum(item.subtotal for item in exp.items if item.vat_rate == 21)
        for exp in deductible_expenses
    )
    odpocet_vat = sum(
        sum(item.vat_amount for item in exp.items if item.vat_rate == 21)
        for exp in deductible_expenses
    )
    odpocet_zaokr = _round_czk(odpocet_vat)

    vlastni_dan = max(0, dan_vystupu_zaokr - odpocet_zaokr)
    nadmerny_odpocet = max(0, odpocet_zaokr - dan_vystupu_zaokr)

    # --- XML ---
    pisemnost = ET.Element("Pisemnost", nazevSW="FakturacniApp", verzeSW="1.0")
    dphdp3 = ET.SubElement(pisemnost, "DPHDP3", verzePis="01.02")

    ET.SubElement(
        dphdp3,
        "VetaD",
        dapdph_forma="B",
        mesic=str(mesic),
        rok=str(year),
        dokument="DP3",
        d_poddp=submission_date.strftime("%Y-%m-%d"),
        k_uladis="DPH",
        typ_platce="P",
        c_okec=settings.SUPPLIER_OKEC,
    )
    ET.SubElement(
        dphdp3,
        "VetaP",
        c_pracufo=settings.SUPPLIER_FU_PRACUFO,
        c_ufo=settings.SUPPLIER_FU_UFO,
        email=settings.SUPPLIER_EMAIL,
        typ_ds="F",
        dic=settings.SUPPLIER_DIC.replace("CZ", ""),
        ulice=settings.SUPPLIER_STREET.split(" ")[0] if " " in settings.SUPPLIER_STREET else settings.SUPPLIER_STREET,
        c_pop="2284",
        c_orient="21",
        c_telef=settings.SUPPLIER_PHONE,
        naz_obce=settings.SUPPLIER_CITY,
        psc=settings.SUPPLIER_ZIP.replace(" ", ""),
        stat="Česká republika",
        jmeno="Samuel",
        prijmeni="Wlaschinský",
        titul="",
    )

    ET.SubElement(
        dphdp3,
        "Veta1",
        dan23=str(dan_vystupu_zaokr),
        obrat23=str(_round_czk(obrat_21)),
        dan5="0",
        obrat5="0",
    )
    ET.SubElement(dphdp3, "Veta2")
    ET.SubElement(
        dphdp3,
        "Veta4",
        odp_tuz23_nar=str(odpocet_zaokr),
        pln23=str(_round_czk(zakl_odpoctu_21)),
        odp_tuz5_nar="0",
        pln5="0",
        nar_zdp23="0",
        od_zdp23="0",
        nar_zdp5="0",
        od_zdp5="0",
        odp_sum_nar=str(odpocet_zaokr),
    )
    ET.SubElement(
        dphdp3,
        "Veta6",
        dan_zocelk=str(dan_vystupu_zaokr),
        odp_zocelk=str(odpocet_zaokr),
        dano_da=str(vlastni_dan),
        dano_no=str(nadmerny_odpocet),
        dano="",
    )

    return _prettify(pisemnost)
