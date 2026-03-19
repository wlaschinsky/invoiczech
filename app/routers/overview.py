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


def _compute(db: Session, year: int) -> dict:
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    invoices = [
        i for i in db.query(Invoice).filter(Invoice.status != "Stornována").all()
        if i.duzp and year_start <= i.duzp <= year_end
    ]
    expenses = [
        e for e in db.query(Expense).all()
        if e.issue_date and year_start <= e.issue_date <= year_end
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
        if m == 12:
            m_end = date(year, 12, 31)
        else:
            m_end = date(year, m + 1, 1)

        m_inv = [i for i in invoices if m_start <= i.duzp < m_end] if m < 12 else [i for i in invoices if i.duzp >= m_start]
        m_exp = [e for e in expenses if m_start <= e.issue_date < m_end] if m < 12 else [e for e in expenses if e.issue_date >= m_start]

        m_income_base = sum(i.subtotal for i in m_inv)
        m_income_total = sum(i.total for i in m_inv)
        m_vat_out = sum(i.vat_total for i in m_inv)
        m_costs_base = sum(e.subtotal for e in m_exp)
        m_costs_total = sum(e.total for e in m_exp)
        m_vat_in = sum(e.vat_total for e in m_exp)

        months.append({
            "name": _MONTHS_CS[m],
            "income_base": m_income_base,
            "income_total": m_income_total,
            "vat_output": m_vat_out,
            "costs_base": m_costs_base,
            "costs_total": m_costs_total,
            "vat_input": m_vat_in,
            "vat_liability": m_vat_out - m_vat_in,
        })

    return {
        "year": year,
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
):
    year = rok or date.today().year
    data = _compute(db, year)

    # Roky s daty (DUZP faktur + issue_date nákladů)
    inv_years = {
        i.duzp.year for i in db.query(Invoice).all()
        if i.duzp
    }
    exp_years = {
        e.issue_date.year for e in db.query(Expense).all()
        if e.issue_date
    }
    available_years = sorted(inv_years | exp_years | {year}, reverse=True)

    return templates.TemplateResponse(
        "overview/year.html",
        {"request": request, "available_years": available_years, **data},
    )


@router.get("/rok/csv")
async def yearly_csv(
    db: Session = Depends(get_db),
    rok: int = Query(default=None),
):
    year = rok or date.today().year
    data = _compute(db, year)

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
):
    year = rok or date.today().year
    data = _compute(db, year)

    templates_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))
    env = Environment(loader=FileSystemLoader(templates_dir))
    env.filters["czk"] = _fmt_czk
    env.filters["date_cs"] = _fmt_date

    template = env.get_template("overview/year_pdf.html")
    html_content = template.render(
        settings=settings,
        **data,
    )

    base_url = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
    pdf_bytes = HTML(string=html_content, base_url=base_url).write_pdf()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="prehled_{year}.pdf"'},
    )
