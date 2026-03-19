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
from ..models.profile import Profile


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


def _get_profile(db: Session) -> Profile:
    profile = db.query(Profile).first()
    if not profile:
        profile = Profile(id=1)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _veta_p(parent: ET.Element, profile: Profile) -> None:
    """Společný element VetaP pro všechny exporty."""
    street_name = profile.street or ""
    ET.SubElement(
        parent,
        "VetaP",
        c_pracufo=profile.fu_pracufo or "",
        c_ufo=profile.fu_ufo or "",
        email=profile.email or "",
        typ_ds="F",
        dic=(profile.dic or "").replace("CZ", ""),
        ulice=street_name,
        c_pop=profile.house_number or "",
        c_orient=profile.orientation_number or "",
        c_telef=profile.phone or "",
        naz_obce=profile.city or "",
        psc=(profile.zip_code or "").replace(" ", ""),
        stat="Česká republika",
        jmeno=profile.first_name or "",
        prijmeni=profile.last_name or "",
        titul="",
    )


def generate_kh1(
    db: Session,
    year: int,
    period: int,
    quarter: bool = False,
    submission_date: date | None = None,
) -> str:
    """Vygeneruje XML Kontrolního hlášení (KH1)."""
    profile = _get_profile(db)

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
    pisemnost = ET.Element("Pisemnost", nazevSW="InvoiCzech", verzeSW="1.0")
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
    _veta_p(dphkh1, profile)

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
    profile = _get_profile(db)

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
    pisemnost = ET.Element("Pisemnost", nazevSW="InvoiCzech", verzeSW="1.0")
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
        c_okec=profile.okec or "",
    )
    _veta_p(dphdp3, profile)

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


def generate_dpfdp7(
    db: Session,
    year: int,
    pausal: int = 60,
    sleva: int = 30840,
    zalohy: int = 0,
    submission_date: date | None = None,
) -> str:
    """Vygeneruje XML Přiznání k dani z příjmů FO (DPFDP7)."""
    profile = _get_profile(db)

    if submission_date is None:
        submission_date = date.today()

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    # Příjmy = uhrazené faktury podle paid_date, bez DPH
    invoices: List[Invoice] = (
        db.query(Invoice)
        .filter(
            Invoice.status == "Uhrazena",
            Invoice.paid_date >= year_start,
            Invoice.paid_date <= year_end,
        )
        .all()
    )

    prijmy = _round_czk(sum(i.subtotal for i in invoices))
    vydaje = _round_czk(Decimal(str(prijmy)) * Decimal(str(pausal)) / Decimal("100"))
    zaklad = max(0, prijmy - vydaje)
    dan_15 = _round_czk(Decimal(str(zaklad)) * Decimal("0.15"))
    dan_po_sleve = max(0, dan_15 - sleva)
    vysledna = dan_po_sleve - zalohy  # kladné = platit, záporné = přeplatek

    # --- XML ---
    pisemnost = ET.Element("Pisemnost", nazevSW="InvoiCzech", verzeSW="1.0")
    dpfdp7 = ET.SubElement(pisemnost, "DPFDP7", verzePis="01.01.02")

    ET.SubElement(
        dpfdp7,
        "VetaD",
        dokument="DPFDP7",
        rok=str(year),
        d_poddp=submission_date.strftime("%Y-%m-%d"),
        k_uladis="DPF",
    )
    _veta_p(dpfdp7, profile)

    # Příloha č. 1 — příjmy §7
    ET.SubElement(
        dpfdp7,
        "PrilohaC1",
        r101=str(prijmy),
        r102=str(vydaje),
        r113=str(zaklad),
    )

    # Výpočet daně
    ET.SubElement(
        dpfdp7,
        "VypocetDane",
        r37=str(zaklad),
        r45=str(zaklad),
        r56=str(dan_15),
        r58=str(sleva),
        r60=str(dan_po_sleve),
        r85=str(zalohy),
        r91=str(vysledna),
    )

    return _prettify(pisemnost)
