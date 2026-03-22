from datetime import date, timedelta
from decimal import Decimal

from ..tmpl import templates
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.invoice import Invoice
from ..models.expense import Expense

router = APIRouter()

_MONTHS_CS = [
    "", "leden", "únor", "březen", "duben",
    "květen", "červen", "červenec", "srpen",
    "září", "říjen", "listopad", "prosinec",
]


def _month_label(m: int, y: int) -> str:
    return f"{_MONTHS_CS[m]} {y}"


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    # Previous month range
    prev_month_end = month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)

    # --- Faktury (filter by DUZP) ---
    all_invoices = db.query(Invoice).filter(Invoice.status != "Stornována").all()

    invoices_month = [i for i in all_invoices if i.duzp and i.duzp >= month_start]
    invoices_year = [i for i in all_invoices if i.duzp and i.duzp >= year_start]
    invoices_prev_month = [
        i for i in all_invoices
        if i.duzp and prev_month_start <= i.duzp <= prev_month_end
    ]

    income_month_total = sum(i.total for i in invoices_month)
    income_month_base = sum(i.subtotal for i in invoices_month)
    income_year_total = sum(i.total for i in invoices_year)
    income_year_base = sum(i.subtotal for i in invoices_year)

    # Daň na výstupu předchozí měsíc (VAT from invoices)
    vat_output_prev = sum(i.vat_total for i in invoices_prev_month)

    # Neuhrazené faktury
    unpaid = [i for i in all_invoices if i.status == "Vystavena"]
    unpaid_total = sum(i.total for i in unpaid)

    # --- Náklady (daňově uznatelné: Ano + Nevím, filter by issue_date) ---
    all_expenses = db.query(Expense).all()
    deductible = [e for e in all_expenses if e.tax_deductible in ("Ano", "Nevím")]

    exp_month = [e for e in deductible if e.issue_date >= month_start]
    exp_prev_month = [
        e for e in deductible
        if prev_month_start <= e.issue_date <= prev_month_end
    ]
    exp_year = [e for e in deductible if e.issue_date >= year_start]

    costs_month_total = sum(e.total for e in exp_month)
    costs_month_vat = sum(e.vat_total for e in exp_month)
    costs_prev_total = sum(e.total for e in exp_prev_month)
    costs_prev_vat = sum(e.vat_total for e in exp_prev_month)
    costs_year_total = sum(e.total for e in exp_year)
    costs_year_vat = sum(e.vat_total for e in exp_year)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            # Labels
            "current_month_label": _month_label(today.month, today.year),
            "prev_month_label": _month_label(prev_month_start.month, prev_month_start.year),
            "current_year": today.year,
            # Příjmy
            "income_month_total": income_month_total,
            "income_month_base": income_month_base,
            "income_year_total": income_year_total,
            "income_year_base": income_year_base,
            # Náklady
            "costs_month_total": costs_month_total,
            "costs_month_vat": costs_month_vat,
            "costs_prev_total": costs_prev_total,
            "costs_prev_vat": costs_prev_vat,
            "costs_year_total": costs_year_total,
            "costs_year_vat": costs_year_vat,
            # DPH
            "vat_output_prev": vat_output_prev,
            "vat_liability_prev": vat_output_prev - costs_prev_vat,
            # Neuhrazené
            "unpaid_count": len(unpaid),
            "unpaid_total": unpaid_total,
            "today": today,
        },
    )
