from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.invoice import Invoice, InvoiceItem
from ..models.contact import Contact
from ..tmpl import templates
from ..config import get_settings
from .utils import flash, parse_date, parse_decimal, generate_invoice_number

router = APIRouter(prefix="/faktury")
settings = get_settings()


@router.get("", response_class=HTMLResponse)
async def invoices_list(
    request: Request,
    status: str = "",
    rok: str = "",
    q: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(Invoice)
    if status:
        query = query.filter(Invoice.status == status)
    if rok:
        try:
            year = int(rok)
            query = query.filter(
                Invoice.issue_date >= date(year, 1, 1),
                Invoice.issue_date <= date(year, 12, 31),
            )
        except ValueError:
            pass
    if q:
        query = query.filter(Invoice.contact_name.ilike(f"%{q}%") | Invoice.number.ilike(f"%{q}%"))

    invoices = query.order_by(Invoice.issue_date.desc(), Invoice.number.desc()).all()
    today = date.today()

    years = sorted(
        {i.issue_date.year for i in db.query(Invoice).all()},
        reverse=True,
    )

    return templates.TemplateResponse(
        "invoices/list.html",
        {
            "request": request,
            "invoices": invoices,
            "today": today,
            "status_filter": status,
            "rok_filter": rok,
            "q": q,
            "years": years,
        },
    )


@router.get("/nova", response_class=HTMLResponse)
async def new_invoice_form(request: Request, db: Session = Depends(get_db)):
    contacts = db.query(Contact).filter(
        Contact.contact_type.in_(["Odběratel", "Obojí"])
    ).order_by(Contact.name).all()
    today = date.today()
    next_number = generate_invoice_number(db)
    return templates.TemplateResponse(
        "invoices/form.html",
        {
            "request": request,
            "invoice": None,
            "contacts": contacts,
            "today": today,
            "due_default": today + timedelta(days=10),
            "next_number": next_number,
            "default_text": settings.DEFAULT_INVOICE_TEXT,
        },
    )


@router.post("/nova")
async def create_invoice(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    contacts = db.query(Contact).filter(
        Contact.contact_type.in_(["Odběratel", "Obojí"])
    ).order_by(Contact.name).all()

    issue_date = parse_date(form.get("issue_date", ""))
    due_date = parse_date(form.get("due_date", ""))
    duzp = parse_date(form.get("duzp", ""))

    today = date.today()
    next_number = generate_invoice_number(db)
    form_ctx = {
        "request": request, "invoice": None, "contacts": contacts,
        "today": today, "due_default": today + timedelta(days=10),
        "next_number": next_number, "default_text": settings.DEFAULT_INVOICE_TEXT,
    }

    if not issue_date or not due_date:
        flash(request, "Datum vystavení a splatnosti jsou povinné.", "error")
        return templates.TemplateResponse("invoices/form.html", form_ctx)

    # Kontakt
    contact_id_raw = form.get("contact_id", "").strip()
    contact_id = int(contact_id_raw) if contact_id_raw else None
    contact = db.query(Contact).filter(Contact.id == contact_id).first() if contact_id else None

    number = next_number
    variable_symbol = number.replace("FA ", "")

    invoice = Invoice(
        number=number,
        contact_id=contact_id,
        contact_name=contact.name if contact else form.get("contact_name", "").strip(),
        contact_ico=contact.ico if contact else form.get("contact_ico", "").strip(),
        contact_dic=contact.dic if contact else form.get("contact_dic", "").strip(),
        contact_street=contact.street if contact else form.get("contact_street", "").strip(),
        contact_city=contact.city if contact else form.get("contact_city", "").strip(),
        contact_zip=contact.zip_code if contact else form.get("contact_zip", "").strip(),
        contact_email=contact.email if contact else form.get("contact_email", "").strip(),
        issue_date=issue_date,
        due_date=due_date,
        duzp=duzp or issue_date,
        payment_method=form.get("payment_method", "Bankovní převod"),
        variable_symbol=variable_symbol,
        invoice_text=form.get("invoice_text", settings.DEFAULT_INVOICE_TEXT).strip(),
        status="Vystavena",
    )

    db.add(invoice)
    db.flush()  # get ID

    _save_items(form, invoice, db)
    db.flush()
    db.expire(invoice, ["items"])

    if not invoice.items:
        db.rollback()
        flash(request, "Faktura musí mít alespoň jednu položku.", "error")
        return templates.TemplateResponse("invoices/form.html", form_ctx)

    db.commit()
    flash(request, f"Faktura {invoice.number} byla vystavena.", "success")
    return RedirectResponse(url=f"/faktury/{invoice.id}", status_code=302)


@router.get("/{invoice_id}", response_class=HTMLResponse)
async def invoice_detail(request: Request, invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Faktura nenalezena")
    return templates.TemplateResponse(
        "invoices/detail.html",
        {"request": request, "invoice": invoice, "today": date.today(), "settings": settings},
    )


@router.get("/{invoice_id}/upravit", response_class=HTMLResponse)
async def edit_invoice_form(request: Request, invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Faktura nenalezena")
    if invoice.status == "Stornována":
        flash(request, "Stornovanou fakturu nelze upravovat.", "error")
        return RedirectResponse(url=f"/faktury/{invoice_id}", status_code=302)

    contacts = db.query(Contact).filter(
        Contact.contact_type.in_(["Odběratel", "Obojí"])
    ).order_by(Contact.name).all()
    return templates.TemplateResponse(
        "invoices/form.html",
        {
            "request": request,
            "invoice": invoice,
            "contacts": contacts,
            "today": date.today(),
            "due_default": invoice.due_date,
            "next_number": invoice.number,
            "default_text": settings.DEFAULT_INVOICE_TEXT,
        },
    )


@router.post("/{invoice_id}/upravit")
async def update_invoice(request: Request, invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Faktura nenalezena")

    form = await request.form()
    contacts = db.query(Contact).filter(
        Contact.contact_type.in_(["Odběratel", "Obojí"])
    ).order_by(Contact.name).all()

    issue_date = parse_date(form.get("issue_date", ""))
    due_date = parse_date(form.get("due_date", ""))
    duzp = parse_date(form.get("duzp", ""))

    form_ctx = {
        "request": request, "invoice": invoice, "contacts": contacts,
        "today": date.today(), "due_default": invoice.due_date,
        "next_number": invoice.number, "default_text": settings.DEFAULT_INVOICE_TEXT,
    }

    if not issue_date or not due_date:
        flash(request, "Datum vystavení a splatnosti jsou povinné.", "error")
        return templates.TemplateResponse("invoices/form.html", form_ctx)

    contact_id_raw = form.get("contact_id", "").strip()
    contact_id = int(contact_id_raw) if contact_id_raw else None
    contact = db.query(Contact).filter(Contact.id == contact_id).first() if contact_id else None

    invoice.contact_id = contact_id
    invoice.contact_name = contact.name if contact else form.get("contact_name", "").strip()
    invoice.contact_ico = contact.ico if contact else form.get("contact_ico", "").strip()
    invoice.contact_dic = contact.dic if contact else form.get("contact_dic", "").strip()
    invoice.contact_street = contact.street if contact else form.get("contact_street", "").strip()
    invoice.contact_city = contact.city if contact else form.get("contact_city", "").strip()
    invoice.contact_zip = contact.zip_code if contact else form.get("contact_zip", "").strip()
    invoice.contact_email = contact.email if contact else form.get("contact_email", "").strip()
    invoice.issue_date = issue_date
    invoice.due_date = due_date
    invoice.duzp = duzp or issue_date
    invoice.payment_method = form.get("payment_method", "Bankovní převod")
    invoice.invoice_text = form.get("invoice_text", "").strip()

    # Smaž staré položky a ulož nové
    for item in list(invoice.items):
        db.delete(item)
    db.flush()

    _save_items(form, invoice, db)
    db.flush()
    db.expire(invoice, ["items"])

    if not invoice.items:
        db.rollback()
        flash(request, "Faktura musí mít alespoň jednu položku.", "error")
        return templates.TemplateResponse("invoices/form.html", form_ctx)

    db.commit()
    flash(request, "Faktura byla uložena.", "success")
    return RedirectResponse(url=f"/faktury/{invoice_id}", status_code=302)


@router.post("/{invoice_id}/uhradit")
async def mark_paid(request: Request, invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Faktura nenalezena")
    form = await request.form()
    paid_date = parse_date(form.get("paid_date", "")) or date.today()
    invoice.status = "Uhrazena"
    invoice.paid_date = paid_date
    db.commit()
    flash(request, f"Faktura {invoice.number} označena jako uhrazená.", "success")
    return RedirectResponse(url=f"/faktury/{invoice_id}", status_code=302)


@router.post("/{invoice_id}/neuhrazena")
async def mark_unpaid(request: Request, invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Faktura nenalezena")
    invoice.status = "Vystavena"
    invoice.paid_date = None
    db.commit()
    flash(request, f"Faktura {invoice.number} vrácena na stav Vystavena.", "info")
    return RedirectResponse(url=f"/faktury/{invoice_id}", status_code=302)


@router.post("/{invoice_id}/stornovat")
async def cancel_invoice(request: Request, invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Faktura nenalezena")
    invoice.status = "Stornována"
    db.commit()
    flash(request, f"Faktura {invoice.number} byla stornována.", "warning")
    return RedirectResponse(url=f"/faktury/{invoice_id}", status_code=302)


@router.post("/{invoice_id}/smazat")
async def delete_invoice(request: Request, invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Faktura nenalezena")
    db.delete(invoice)
    db.commit()
    flash(request, f"Faktura {invoice.number} byla smazána.", "success")
    return RedirectResponse(url="/faktury", status_code=302)


@router.get("/{invoice_id}/pdf")
async def download_pdf(request: Request, invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Faktura nenalezena")
    from ..services.pdf_generator import generate_invoice_pdf
    pdf_bytes = generate_invoice_pdf(invoice)
    filename = f"{invoice.number.replace(' ', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _save_items(form, invoice: Invoice, db: Session) -> None:
    descriptions = form.getlist("description")
    quantities = form.getlist("quantity")
    unit_prices = form.getlist("unit_price")
    vat_rates = form.getlist("vat_rate")

    for i, desc in enumerate(descriptions):
        desc = desc.strip()
        if not desc:
            continue
        try:
            qty = parse_decimal(quantities[i]) if i < len(quantities) else Decimal("1")
            price = parse_decimal(unit_prices[i]) if i < len(unit_prices) else Decimal("0")
            vat = int(vat_rates[i]) if i < len(vat_rates) else 21
        except (ValueError, IndexError):
            continue

        item = InvoiceItem(
            invoice_id=invoice.id,
            description=desc,
            quantity=qty,
            unit_price=price,
            vat_rate=vat,
            position=i,
        )
        db.add(item)
