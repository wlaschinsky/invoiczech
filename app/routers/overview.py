"""Roční přehled příjmů, nákladů a DPH."""
import csv
import io
import os
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, Response
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session
from weasyprint import HTML

from ..database import get_db
from ..config import get_settings
from ..models.invoice import Invoice
from ..models.expense import Expense
from ..tmpl import templates, _fmt_czk, _fmt_date

router = APIRouter(prefix="/prehled")

settings = get_settings()

_MONTHS_CS = [
    "", "leden", "únor", "březen", "duben",
    "květen", "červen", "červenec", "srpen",
    "září", "říjen", "listopad", "prosinec",
]


_BASIS_LABELS = {
    "duzp": "DUZP",
    "issue_date": "Vystaveno",
    "paid_date": "Uhrazeno",
}


def _inv_date(inv, basis: str):
    if basis == "issue_date":
        return inv.issue_date
    if basis == "paid_date":
        return inv.paid_date
    return inv.duzp


def _exp_date(exp, basis: str):
    if basis == "paid_date":
        return exp.paid_date
    return exp.issue_date


def _compute(db: Session, year: int, basis: str = "duzp") -> dict:
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    invoices = [
        i for i in db.query(Invoice).filter(Invoice.status != "Stornována").all()
        if _inv_date(i, basis) and year_start <= _inv_date(i, basis) <= year_end
    ]
    expenses = [
        e for e in db.query(Expense).all()
        if _exp_date(e, basis) and year_start <= _exp_date(e, basis) <= year_end
        and e.tax_deductible in ("Ano", "Nevím")
    ]

    income_base = sum(i.subtotal for i in invoices)
    income_total = sum(i.total for i in invoices)
    vat_output = sum(i.vat_total for i in invoices)

    costs_base = sum(e.subtotal for e in expenses)
    costs_total = sum(e.total for e in expenses)
    vat_input = sum(e.vat_total for e in expenses)

    vat_liability = vat_output - vat_input

    # Monthly breakdown
    months = []
    for m in range(1, 13):
        m_start = date(year, m, 1)
        m_end = date(year, 12, 31) if m == 12 else date(year, m + 1, 1)

        m_inv = [i for i in invoices if m_start <= _inv_date(i, basis) < m_end] if m < 12 else [i for i in invoices if _inv_date(i, basis) >= m_start]
        m_exp = [e for e in expenses if m_start <= _exp_date(e, basis) < m_end] if m < 12 else [e for e in expenses if _exp_date(e, basis) >= m_start]

        m_vat_out = sum(i.vat_total for i in m_inv)
        m_vat_in = sum(e.vat_total for e in m_exp)

        months.append({
            "name": _MONTHS_CS[m],
            "income_base": sum(i.subtotal for i in m_inv),
            "income_total": sum(i.total for i in m_inv),
            "vat_output": m_vat_out,
            "costs_base": sum(e.subtotal for e in m_exp),
            "costs_total": sum(e.total for e in m_exp),
            "vat_input": m_vat_in,
            "vat_liability": m_vat_out - m_vat_in,
        })

    return {
        "year": year,
        "basis": basis,
        "basis_label": _BASIS_LABELS.get(basis, "DUZP"),
        "income_base": income_base,
        "income_total": income_total,
        "vat_output": vat_output,
        "costs_base": costs_base,
        "costs_total": costs_total,
        "vat_input": vat_input,
        "vat_liability": vat_liability,
        "months": months,
    }


@router.get("/rok", response_class=HTMLResponse)
async def yearly_overview(
    request: Request,
    db: Session = Depends(get_db),
    rok: int = Query(default=None),
    basis: str = Query(default="duzp"),
):
    if basis not in _BASIS_LABELS:
        basis = "duzp"
    year = rok or date.today().year
    data = _compute(db, year, basis)

    all_inv = db.query(Invoice).all()
    all_exp = db.query(Expense).all()
    inv_years = {i.duzp.year for i in all_inv if i.duzp} | \
                {i.issue_date.year for i in all_inv if i.issue_date} | \
                {i.paid_date.year for i in all_inv if i.paid_date}
    exp_years = {e.issue_date.year for e in all_exp if e.issue_date} | \
                {e.paid_date.year for e in all_exp if e.paid_date}
    available_years = sorted(inv_years | exp_years | {year}, reverse=True)

    return templates.TemplateResponse(
        "overview/year.html",
        {"request": request, "available_years": available_years, "basis_options": _BASIS_LABELS, **data},
    )


@router.get("/rok/csv")
async def yearly_csv(
    db: Session = Depends(get_db),
    rok: int = Query(default=None),
    basis: str = Query(default="duzp"),
):
    if basis not in _BASIS_LABELS:
        basis = "duzp"
    year = rok or date.today().year
    data = _compute(db, year, basis)

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")

    writer.writerow(["", "Příjmy bez DPH", "Příjmy s DPH", "DPH výstup",
                      "Náklady bez DPH", "Náklady s DPH", "DPH vstup", "Daň. povinnost"])

    for m in data["months"]:
        writer.writerow([
            m["name"].capitalize(),
            str(m["income_base"]).replace(".", ","),
            str(m["income_total"]).replace(".", ","),
            str(m["vat_output"]).replace(".", ","),
            str(m["costs_base"]).replace(".", ","),
            str(m["costs_total"]).replace(".", ","),
            str(m["vat_input"]).replace(".", ","),
            str(m["vat_liability"]).replace(".", ","),
        ])

    writer.writerow([])
    writer.writerow([
        "CELKEM",
        str(data["income_base"]).replace(".", ","),
        str(data["income_total"]).replace(".", ","),
        str(data["vat_output"]).replace(".", ","),
        str(data["costs_base"]).replace(".", ","),
        str(data["costs_total"]).replace(".", ","),
        str(data["vat_input"]).replace(".", ","),
        str(data["vat_liability"]).replace(".", ","),
    ])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="prehled_{year}.csv"'},
    )


@router.get("/rok/pdf")
async def yearly_pdf(
    db: Session = Depends(get_db),
    rok: int = Query(default=None),
    basis: str = Query(default="duzp"),
):
    if basis not in _BASIS_LABELS:
        basis = "duzp"
    year = rok or date.today().year
    data = _compute(db, year, basis)

    templates_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))
    env = Environment(loader=FileSystemLoader(templates_dir))
    env.filters["czk"] = _fmt_czk
    env.filters["date_cs"] = _fmt_date

    from .profile import get_profile
    profile = get_profile(db)

    template = env.get_template("overview/year_pdf.html")
    html_content = template.render(
        profile=profile,
        **data,
    )

    base_url = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
    pdf_bytes = HTML(string=html_content, base_url=base_url).write_pdf()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="prehled_{year}.pdf"'},
    )
