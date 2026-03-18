from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.invoice import Invoice
from ..models.expense import Expense
from ..models.contact import Contact

router = APIRouter()


@router.get("/hledat")
async def global_search(q: str = "", db: Session = Depends(get_db)):
    if not q or len(q) < 2:
        return JSONResponse({"results": []})

    term = f"%{q}%"
    results = []

    invoices = (
        db.query(Invoice)
        .filter(Invoice.number.ilike(term) | Invoice.contact_name.ilike(term))
        .order_by(Invoice.issue_date.desc())
        .limit(5)
        .all()
    )
    for inv in invoices:
        results.append({
            "category": "Faktury",
            "label": inv.number,
            "detail": inv.contact_name or "",
            "url": f"/faktury/{inv.id}",
        })

    expenses = (
        db.query(Expense)
        .filter(Expense.number.ilike(term) | Expense.contact_name.ilike(term) | Expense.title.ilike(term))
        .order_by(Expense.issue_date.desc())
        .limit(5)
        .all()
    )
    for exp in expenses:
        results.append({
            "category": "Náklady",
            "label": exp.number,
            "detail": exp.contact_name or "",
            "url": f"/naklady/{exp.id}",
        })

    contacts = (
        db.query(Contact)
        .filter(Contact.name.ilike(term) | Contact.ico.ilike(term))
        .order_by(Contact.name)
        .limit(5)
        .all()
    )
    for c in contacts:
        results.append({
            "category": "Adresář",
            "label": c.name,
            "detail": c.ico or "",
            "url": f"/adresar/{c.id}",
        })

    return JSONResponse({"results": results})
