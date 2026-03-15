import os
import shutil
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.expense import Expense, ExpenseItem
from ..models.contact import Contact
from ..tmpl import templates
from ..config import get_settings
from .utils import flash, parse_date, parse_decimal, generate_expense_number

router = APIRouter(prefix="/naklady")
settings = get_settings()


@router.get("", response_class=HTMLResponse)
async def expenses_list(
    request: Request,
    status: str = "",
    typ: str = "",
    rok: str = "",
    q: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(Expense)
    if typ:
        query = query.filter(Expense.document_type == typ)
    if rok:
        try:
            year = int(rok)
            query = query.filter(
                Expense.issue_date >= date(year, 1, 1),
                Expense.issue_date <= date(year, 12, 31),
            )
        except ValueError:
            pass
    if q:
        query = query.filter(
            Expense.contact_name.ilike(f"%{q}%") | Expense.number.ilike(f"%{q}%")
        )

    expenses = query.order_by(Expense.issue_date.desc(), Expense.number.desc()).all()
    years = sorted(
        {e.issue_date.year for e in db.query(Expense).all()},
        reverse=True,
    )

    return templates.TemplateResponse(
        "expenses/list.html",
        {
            "request": request,
            "expenses": expenses,
            "typ_filter": typ,
            "rok_filter": rok,
            "q": q,
            "years": years,
        },
    )


@router.get("/novy", response_class=HTMLResponse)
async def new_expense_form(request: Request, db: Session = Depends(get_db)):
    contacts = db.query(Contact).filter(
        Contact.contact_type.in_(["Dodavatel", "Obojí"])
    ).order_by(Contact.name).all()
    today = date.today()
    next_number = generate_expense_number(db)
    return templates.TemplateResponse(
        "expenses/form.html",
        {
            "request": request,
            "expense": None,
            "contacts": contacts,
            "today": today,
            "next_number": next_number,
        },
    )


@router.post("/novy")
async def create_expense(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    contacts = db.query(Contact).filter(
        Contact.contact_type.in_(["Dodavatel", "Obojí"])
    ).order_by(Contact.name).all()

    issue_date = parse_date(form.get("issue_date", ""))
    duzp = parse_date(form.get("duzp", ""))
    paid_date = parse_date(form.get("paid_date", ""))

    today = date.today()
    next_number = generate_expense_number(db)
    form_ctx = {
        "request": request, "expense": None, "contacts": contacts,
        "today": today, "next_number": next_number,
    }

    if not issue_date:
        flash(request, "Datum vystavení je povinné.", "error")
        return templates.TemplateResponse("expenses/form.html", form_ctx)

    contact_id_raw = form.get("contact_id", "").strip()
    contact_id = int(contact_id_raw) if contact_id_raw else None
    contact = db.query(Contact).filter(Contact.id == contact_id).first() if contact_id else None
    contact_name = contact.name if contact else form.get("contact_name", "").strip()

    price_includes_vat = form.get("price_includes_vat") == "1"

    expense = Expense(
        number=next_number,
        contact_id=contact_id,
        contact_name=contact_name,
        supplier_document_number=form.get("supplier_document_number", "").strip(),
        issue_date=issue_date,
        duzp=duzp or issue_date,
        payment_method=form.get("payment_method", "Bankovní převod"),
        paid_date=paid_date,
        document_type=form.get("document_type", "Faktura"),
        tax_deductible=form.get("tax_deductible", "Nevím"),
        fulfillment_code=form.get("fulfillment_code", "").strip(),
        price_includes_vat=price_includes_vat,
        notes=form.get("notes", "").strip(),
    )

    db.add(expense)
    db.flush()

    _save_items(form, expense, price_includes_vat, db)
    db.flush()

    # Zpracování přílohy
    attachment = form.get("attachment")
    if attachment and hasattr(attachment, "filename") and attachment.filename:
        expense.attachment_path = _save_attachment(attachment, expense.id)

    db.expire(expense, ["items"])
    if not expense.items:
        db.rollback()
        flash(request, "Náklad musí mít alespoň jednu položku.", "error")
        return templates.TemplateResponse("expenses/form.html", form_ctx)

    db.commit()
    flash(request, f"Náklad {expense.number} byl přidán.", "success")
    return RedirectResponse(url=f"/naklady/{expense.id}", status_code=302)


@router.get("/{expense_id}", response_class=HTMLResponse)
async def expense_detail(request: Request, expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Náklad nenalezen")
    return templates.TemplateResponse(
        "expenses/detail.html",
        {"request": request, "expense": expense},
    )


@router.get("/{expense_id}/upravit", response_class=HTMLResponse)
async def edit_expense_form(request: Request, expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Náklad nenalezen")
    contacts = db.query(Contact).filter(
        Contact.contact_type.in_(["Dodavatel", "Obojí"])
    ).order_by(Contact.name).all()
    return templates.TemplateResponse(
        "expenses/form.html",
        {
            "request": request,
            "expense": expense,
            "contacts": contacts,
            "today": date.today(),
            "next_number": expense.number,
        },
    )


@router.post("/{expense_id}/upravit")
async def update_expense(request: Request, expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Náklad nenalezen")

    form = await request.form()
    contacts = db.query(Contact).filter(
        Contact.contact_type.in_(["Dodavatel", "Obojí"])
    ).order_by(Contact.name).all()

    issue_date = parse_date(form.get("issue_date", ""))
    duzp = parse_date(form.get("duzp", ""))
    paid_date = parse_date(form.get("paid_date", ""))

    form_ctx = {
        "request": request, "expense": expense, "contacts": contacts,
        "today": date.today(), "next_number": expense.number,
    }

    if not issue_date:
        flash(request, "Datum vystavení je povinné.", "error")
        return templates.TemplateResponse("expenses/form.html", form_ctx)

    contact_id_raw = form.get("contact_id", "").strip()
    contact_id = int(contact_id_raw) if contact_id_raw else None
    contact = db.query(Contact).filter(Contact.id == contact_id).first() if contact_id else None

    expense.contact_id = contact_id
    expense.contact_name = contact.name if contact else form.get("contact_name", "").strip()
    expense.supplier_document_number = form.get("supplier_document_number", "").strip()
    expense.issue_date = issue_date
    expense.duzp = duzp or issue_date
    expense.payment_method = form.get("payment_method", "Bankovní převod")
    expense.paid_date = paid_date
    expense.document_type = form.get("document_type", "Faktura")
    expense.tax_deductible = form.get("tax_deductible", "Nevím")
    expense.fulfillment_code = form.get("fulfillment_code", "").strip()
    expense.price_includes_vat = form.get("price_includes_vat") == "1"
    expense.notes = form.get("notes", "").strip()

    for item in list(expense.items):
        db.delete(item)
    db.flush()

    _save_items(form, expense, expense.price_includes_vat, db)
    db.flush()

    # Nová příloha
    attachment = form.get("attachment")
    if attachment and hasattr(attachment, "filename") and attachment.filename:
        expense.attachment_path = _save_attachment(attachment, expense.id)

    db.expire(expense, ["items"])
    if not expense.items:
        db.rollback()
        flash(request, "Náklad musí mít alespoň jednu položku.", "error")
        return templates.TemplateResponse("expenses/form.html", form_ctx)

    db.commit()
    flash(request, "Náklad byl uložen.", "success")
    return RedirectResponse(url=f"/naklady/{expense_id}", status_code=302)


@router.post("/{expense_id}/smazat")
async def delete_expense(request: Request, expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Náklad nenalezen")
    if expense.attachment_path and os.path.exists(expense.attachment_path):
        os.remove(expense.attachment_path)
    db.delete(expense)
    db.commit()
    flash(request, "Náklad byl smazán.", "success")
    return RedirectResponse(url="/naklady", status_code=302)


@router.get("/{expense_id}/priloha")
async def download_attachment(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense or not expense.attachment_path:
        raise HTTPException(status_code=404, detail="Příloha nenalezena")
    if not os.path.exists(expense.attachment_path):
        raise HTTPException(status_code=404, detail="Soubor přílohy neexistuje")
    return FileResponse(expense.attachment_path)


def _save_items(form, expense: Expense, price_includes_vat: bool, db: Session) -> None:
    descriptions = form.getlist("description")
    quantities = form.getlist("quantity")
    units = form.getlist("unit")
    unit_prices = form.getlist("unit_price")
    vat_rates = form.getlist("vat_rate")

    for i, desc in enumerate(descriptions):
        desc = desc.strip()
        if not desc:
            continue
        try:
            qty = parse_decimal(quantities[i]) if i < len(quantities) else Decimal("1")
            price_entered = parse_decimal(unit_prices[i]) if i < len(unit_prices) else Decimal("0")
            vat = int(vat_rates[i]) if i < len(vat_rates) else 21
            unit = units[i].strip() if i < len(units) else "ks"
        except (ValueError, IndexError):
            continue

        # Pokud je cena s DPH, převeď na cenu bez DPH
        if price_includes_vat and vat > 0:
            price_net = (price_entered / (1 + Decimal(str(vat)) / 100)).quantize(Decimal("0.0001"))
        else:
            price_net = price_entered

        item = ExpenseItem(
            expense_id=expense.id,
            quantity=qty,
            unit=unit,
            description=desc,
            unit_price=price_net,
            vat_rate=vat,
            position=i,
        )
        db.add(item)


def _save_attachment(upload_file, expense_id: int) -> str:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(upload_file.filename)[1].lower()
    filename = f"expense_{expense_id}{ext}"
    dest_path = os.path.join(settings.UPLOAD_DIR, filename)
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(upload_file.file, f)
    return dest_path
