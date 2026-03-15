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


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    # --- Faktury ---
    all_invoices = db.query(Invoice).filter(Invoice.status != "Stornována").all()

    def inv_total(inv: Invoice) -> Decimal:
        return inv.total

    def inv_base(inv: Invoice) -> Decimal:
        return inv.subtotal

    invoices_month = [
        i for i in all_invoices
        if i.issue_date >= month_start
    ]
    invoices_year = [
        i for i in all_invoices
        if i.issue_date >= year_start
    ]

    income_month = sum(inv_base(i) for i in invoices_month)
    income_year = sum(inv_base(i) for i in invoices_year)

    unpaid = [i for i in all_invoices if i.status == "Vystavena"]
    unpaid_total = sum(inv_total(i) for i in unpaid)

    overdue = [i for i in unpaid if i.due_date < today]

    # --- Náklady ---
    all_expenses = db.query(Expense).all()
    expenses_month = [e for e in all_expenses if e.issue_date >= month_start]
    expenses_year = [e for e in all_expenses if e.issue_date >= year_start]

    costs_month = sum(e.total for e in expenses_month)
    costs_year = sum(e.total for e in expenses_year)

    # --- Odhadovaná DPH za aktuální měsíc ---
    inv_vat_month = sum(
        sum(item.vat_amount for item in i.items if item.vat_rate == 21)
        for i in invoices_month
    )
    exp_vat_month = sum(
        sum(item.vat_amount for item in e.items if item.vat_rate == 21)
        for e in expenses_month
        if e.tax_deductible in ("Ano", "Nevím")
    )
    estimated_vat = max(Decimal("0"), inv_vat_month - exp_vat_month)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "income_month": income_month,
            "income_year": income_year,
            "costs_month": costs_month,
            "costs_year": costs_year,
            "unpaid_count": len(unpaid),
            "unpaid_total": unpaid_total,
            "overdue": overdue,
            "estimated_vat": estimated_vat,
            "today": today,
        },
    )
