"""Sdílené utility pro routery."""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session


def flash(request: Request, message: str, category: str = "info") -> None:
    if "_flashes" not in request.session:
        request.session["_flashes"] = []
    msgs = list(request.session["_flashes"])
    msgs.append({"message": message, "category": category})
    request.session["_flashes"] = msgs


def get_flashes(request: Request) -> list:
    msgs = list(request.session.get("_flashes", []))
    request.session["_flashes"] = []
    return msgs


def parse_date(value: str) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_decimal(value: str) -> Decimal:
    try:
        return Decimal(value.replace(",", "."))
    except Exception:
        return Decimal("0")


def generate_invoice_number(db: Session) -> str:
    from ..models.invoice import Invoice
    year = date.today().year
    prefix = f"FA {year}"
    last = (
        db.query(Invoice)
        .filter(Invoice.number.like(f"{prefix}%"))
        .order_by(Invoice.number.desc())
        .first()
    )
    if last:
        try:
            seq = int(last.number[len(prefix):]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


def generate_expense_number(db: Session) -> str:
    from ..models.expense import Expense
    year = date.today().year
    prefix = f"N{year}"
    last = (
        db.query(Expense)
        .filter(Expense.number.like(f"{prefix}%"))
        .order_by(Expense.number.desc())
        .first()
    )
    if last:
        try:
            seq = int(last.number[len(prefix):]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"
