import csv
import io
import os
import shutil
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.expense import Expense, ExpenseItem, ExpenseAttachment
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
    od: str = "",
    do: str = "",
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
            Expense.contact_name.ilike(f"%{q}%") | Expense.number.ilike(f"%{q}%") | Expense.title.ilike(f"%{q}%")
        )
    if od:
        d = parse_date(od)
        if d:
            query = query.filter(Expense.issue_date >= d)
    if do:
        d = parse_date(do)
        if d:
            query = query.filter(Expense.issue_date <= d)

    expenses = query.order_by(Expense.issue_date.desc(), Expense.number.desc()).all()
    years = sorted(
        {e.issue_date.year for e in db.query(Expense).all()},
        reverse=True,
    )

    total_count = db.query(Expense).count()

    return templates.TemplateResponse(
        "expenses/list.html",
        {
            "request": request,
            "expenses": expenses,
            "typ_filter": typ,
            "rok_filter": rok,
            "q": q,
            "od": od,
            "do": do,
            "years": years,
            "total_count": total_count,
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
        title=form.get("title", "").strip(),
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

    # Zpracování příloh (multiple)
    attachments = form.getlist("attachment")
    position = 0
    for attachment in attachments:
        if not attachment or not hasattr(attachment, "filename") or not attachment.filename:
            continue
        err = _validate_attachment(attachment)
        if err:
            db.rollback()
            flash(request, err, "error")
            return templates.TemplateResponse("expenses/form.html", form_ctx)
        filepath = _save_attachment(attachment, expense.id, position)
        att = ExpenseAttachment(
            expense_id=expense.id,
            filename=attachment.filename,
            filepath=filepath,
            position=position,
        )
        db.add(att)
        position += 1

    db.expire(expense, ["items"])
    if not expense.items:
        db.rollback()
        flash(request, "Náklad musí mít alespoň jednu položku.", "error")
        return templates.TemplateResponse("expenses/form.html", form_ctx)

    db.commit()
    flash(request, f"Náklad {expense.number} byl přidán.", "success")
    return RedirectResponse(url=f"/naklady/{expense.id}", status_code=302)


@router.post("/hromadne/smazat")
async def bulk_delete(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    ids = [int(x) for x in form.getlist("ids") if x.isdigit()]
    if not ids:
        flash(request, "Nejsou vybrány žádné náklady.", "error")
        return RedirectResponse(url="/naklady", status_code=302)
    expenses = db.query(Expense).filter(Expense.id.in_(ids)).all()
    count = len(expenses)
    for exp in expenses:
        for att in exp.attachments:
            if os.path.exists(att.filepath):
                os.remove(att.filepath)
        if exp.attachment_path and os.path.exists(exp.attachment_path):
            os.remove(exp.attachment_path)
        db.delete(exp)
    db.commit()
    flash(request, f"{count} nákladů smazáno.", "success")
    return RedirectResponse(url="/naklady", status_code=302)


@router.post("/hromadne/csv")
async def bulk_csv(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    ids = [int(x) for x in form.getlist("ids") if x.isdigit()]
    if not ids:
        flash(request, "Nejsou vybrány žádné náklady.", "error")
        return RedirectResponse(url="/naklady", status_code=302)
    expenses = db.query(Expense).filter(Expense.id.in_(ids)).order_by(Expense.issue_date.desc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Číslo", "Název", "Dodavatel", "Typ", "Datum", "DUZP", "Základ", "DPH", "Celkem", "Daň. uznatelný"])
    for exp in expenses:
        writer.writerow([
            exp.number, exp.title or "", exp.contact_name or "", exp.document_type,
            exp.issue_date.isoformat(), exp.duzp.isoformat() if exp.duzp else "",
            str(exp.subtotal), str(exp.vat_total), str(exp.total), exp.tax_deductible,
        ])
    content = buf.getvalue().encode("utf-8-sig")
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="naklady_export.csv"'},
    )


@router.get("/{expense_id}", response_class=HTMLResponse)
async def expense_detail(request: Request, expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Náklad nenalezen")
    attachments_info = []
    for att in expense.attachments:
        ext = os.path.splitext(att.filepath)[1].lower()
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"):
            att_type = "image"
        elif ext == ".pdf":
            att_type = "pdf"
        else:
            att_type = "other"
        attachments_info.append({"id": att.id, "filename": att.filename, "type": att_type})
    return templates.TemplateResponse(
        "expenses/detail.html",
        {"request": request, "expense": expense, "attachments_info": attachments_info},
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

    expense.title = form.get("title", "").strip()
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

    # Smazání vybraných příloh
    delete_ids = form.getlist("delete_attachment")
    for att_id in delete_ids:
        if not att_id.isdigit():
            continue
        att = db.query(ExpenseAttachment).filter(
            ExpenseAttachment.id == int(att_id),
            ExpenseAttachment.expense_id == expense.id,
        ).first()
        if att:
            if os.path.exists(att.filepath):
                os.remove(att.filepath)
            db.delete(att)
    db.flush()

    # Nové přílohy
    attachments = form.getlist("attachment")
    max_pos = db.query(ExpenseAttachment).filter(
        ExpenseAttachment.expense_id == expense.id
    ).count()
    for attachment in attachments:
        if not attachment or not hasattr(attachment, "filename") or not attachment.filename:
            continue
        err = _validate_attachment(attachment)
        if err:
            db.rollback()
            flash(request, err, "error")
            return templates.TemplateResponse("expenses/form.html", form_ctx)
        filepath = _save_attachment(attachment, expense.id, max_pos)
        att = ExpenseAttachment(
            expense_id=expense.id,
            filename=attachment.filename,
            filepath=filepath,
            position=max_pos,
        )
        db.add(att)
        max_pos += 1

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
    for att in expense.attachments:
        if os.path.exists(att.filepath):
            os.remove(att.filepath)
    if expense.attachment_path and os.path.exists(expense.attachment_path):
        os.remove(expense.attachment_path)
    db.delete(expense)
    db.commit()
    flash(request, "Náklad byl smazán.", "success")
    return RedirectResponse(url="/naklady", status_code=302)


@router.get("/{expense_id}/priloha/{attachment_id}")
async def view_attachment(expense_id: int, attachment_id: int, db: Session = Depends(get_db)):
    att = db.query(ExpenseAttachment).filter(
        ExpenseAttachment.id == attachment_id,
        ExpenseAttachment.expense_id == expense_id,
    ).first()
    if not att:
        raise HTTPException(status_code=404, detail="Příloha nenalezena")
    if not os.path.exists(att.filepath):
        raise HTTPException(status_code=404, detail="Soubor přílohy neexistuje")
    return FileResponse(att.filepath)


@router.get("/{expense_id}/priloha/{attachment_id}/stahnout")
async def download_attachment(expense_id: int, attachment_id: int, db: Session = Depends(get_db)):
    att = db.query(ExpenseAttachment).filter(
        ExpenseAttachment.id == attachment_id,
        ExpenseAttachment.expense_id == expense_id,
    ).first()
    if not att:
        raise HTTPException(status_code=404, detail="Příloha nenalezena")
    if not os.path.exists(att.filepath):
        raise HTTPException(status_code=404, detail="Soubor přílohy neexistuje")
    return FileResponse(
        att.filepath,
        headers={"Content-Disposition": f'attachment; filename="{att.filename}"'},
    )


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


ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


def _validate_attachment(upload_file) -> str | None:
    """Return error message or None if valid."""
    ext = os.path.splitext(upload_file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return f"Nepodporovaný typ souboru ({ext}). Povolené: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
    upload_file.file.seek(0, 2)
    size = upload_file.file.tell()
    upload_file.file.seek(0)
    if size > MAX_UPLOAD_SIZE:
        return f"Soubor je příliš velký ({size // (1024*1024)} MB). Maximum je 10 MB."
    return None


def _save_attachment(upload_file, expense_id: int, position: int = 0) -> str:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(upload_file.filename)[1].lower()
    filename = f"expense_{expense_id}_{position}{ext}"
    dest_path = os.path.join(settings.UPLOAD_DIR, filename)
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(upload_file.file, f)
    return dest_path
