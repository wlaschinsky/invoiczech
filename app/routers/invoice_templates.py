from decimal import Decimal

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.invoice_template import InvoiceTemplate, InvoiceTemplateItem
from ..models.contact import Contact
from ..tmpl import templates
from .utils import flash, parse_decimal

router = APIRouter(prefix="/sablony")


@router.get("", response_class=HTMLResponse)
async def templates_list(request: Request, db: Session = Depends(get_db)):
    tpls = db.query(InvoiceTemplate).order_by(InvoiceTemplate.name).all()
    return templates.TemplateResponse(
        "invoice_templates/list.html",
        {"request": request, "templates": tpls},
    )


@router.get("/nova", response_class=HTMLResponse)
async def new_template_form(request: Request, db: Session = Depends(get_db)):
    contacts = db.query(Contact).filter(
        Contact.contact_type.in_(["Odběratel", "Obojí"])
    ).order_by(Contact.name).all()
    return templates.TemplateResponse(
        "invoice_templates/form.html",
        {"request": request, "tpl": None, "contacts": contacts},
    )


@router.post("/nova")
async def create_template(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    contacts = db.query(Contact).filter(
        Contact.contact_type.in_(["Odběratel", "Obojí"])
    ).order_by(Contact.name).all()

    name = form.get("name", "").strip()
    if not name:
        flash(request, "Název šablony je povinný.", "error")
        return templates.TemplateResponse(
            "invoice_templates/form.html",
            {"request": request, "tpl": None, "contacts": contacts},
        )

    contact_id_raw = form.get("contact_id", "").strip()
    contact_id = int(contact_id_raw) if contact_id_raw else None

    payment_method = form.get("payment_method", "Bankovní převod")
    try:
        due_days = int(form.get("due_days", "10"))
    except ValueError:
        due_days = 10

    tpl = InvoiceTemplate(
        name=name,
        contact_id=contact_id,
        contact_name=form.get("contact_name", "").strip() or None,
        contact_ico=form.get("contact_ico", "").strip() or None,
        contact_dic=form.get("contact_dic", "").strip() or None,
        contact_street=form.get("contact_street", "").strip() or None,
        contact_city=form.get("contact_city", "").strip() or None,
        contact_zip=form.get("contact_zip", "").strip() or None,
        payment_method=payment_method,
        due_days=due_days,
    )
    db.add(tpl)
    db.flush()

    _save_items(form, tpl, db)
    db.commit()
    flash(request, f"Šablona '{name}' byla vytvořena.", "success")
    return RedirectResponse(url="/sablony", status_code=302)


@router.get("/{tpl_id}/upravit", response_class=HTMLResponse)
async def edit_template_form(request: Request, tpl_id: int, db: Session = Depends(get_db)):
    tpl = db.query(InvoiceTemplate).filter(InvoiceTemplate.id == tpl_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Šablona nenalezena")
    contacts = db.query(Contact).filter(
        Contact.contact_type.in_(["Odběratel", "Obojí"])
    ).order_by(Contact.name).all()
    return templates.TemplateResponse(
        "invoice_templates/form.html",
        {"request": request, "tpl": tpl, "contacts": contacts},
    )


@router.post("/{tpl_id}/upravit")
async def update_template(request: Request, tpl_id: int, db: Session = Depends(get_db)):
    tpl = db.query(InvoiceTemplate).filter(InvoiceTemplate.id == tpl_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Šablona nenalezena")

    form = await request.form()
    contacts = db.query(Contact).filter(
        Contact.contact_type.in_(["Odběratel", "Obojí"])
    ).order_by(Contact.name).all()

    name = form.get("name", "").strip()
    if not name:
        flash(request, "Název šablony je povinný.", "error")
        return templates.TemplateResponse(
            "invoice_templates/form.html",
            {"request": request, "tpl": tpl, "contacts": contacts},
        )

    contact_id_raw = form.get("contact_id", "").strip()
    tpl.name = name
    tpl.contact_id = int(contact_id_raw) if contact_id_raw else None
    tpl.contact_name = form.get("contact_name", "").strip() or None
    tpl.contact_ico = form.get("contact_ico", "").strip() or None
    tpl.contact_dic = form.get("contact_dic", "").strip() or None
    tpl.contact_street = form.get("contact_street", "").strip() or None
    tpl.contact_city = form.get("contact_city", "").strip() or None
    tpl.contact_zip = form.get("contact_zip", "").strip() or None
    tpl.payment_method = form.get("payment_method", "Bankovní převod")
    try:
        tpl.due_days = int(form.get("due_days", "10"))
    except ValueError:
        tpl.due_days = 10

    for item in list(tpl.items):
        db.delete(item)
    db.flush()

    _save_items(form, tpl, db)
    db.commit()
    flash(request, "Šablona byla uložena.", "success")
    return RedirectResponse(url="/sablony", status_code=302)


@router.post("/{tpl_id}/smazat")
async def delete_template(request: Request, tpl_id: int, db: Session = Depends(get_db)):
    tpl = db.query(InvoiceTemplate).filter(InvoiceTemplate.id == tpl_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Šablona nenalezena")
    db.delete(tpl)
    db.commit()
    flash(request, f"Šablona '{tpl.name}' byla smazána.", "success")
    return RedirectResponse(url="/sablony", status_code=302)


@router.get("/{tpl_id}/json")
async def template_json(tpl_id: int, db: Session = Depends(get_db)):
    """AJAX endpoint — vrátí data šablony pro předvyplnění formuláře faktury."""
    tpl = db.query(InvoiceTemplate).filter(InvoiceTemplate.id == tpl_id).first()
    if not tpl:
        return JSONResponse({"error": "not found"}, status_code=404)

    contact = tpl.contact
    return JSONResponse({
        "payment_method": tpl.payment_method or "Bankovní převod",
        "due_days": tpl.due_days or 10,
        "contact_id": tpl.contact_id,
        "contact_name": tpl.contact_name or (contact.name if contact else ""),
        "contact_ico": tpl.contact_ico or (contact.ico if contact else ""),
        "contact_dic": tpl.contact_dic or (contact.dic if contact else ""),
        "contact_street": tpl.contact_street or (contact.street if contact else ""),
        "contact_city": tpl.contact_city or (contact.city if contact else ""),
        "contact_zip": tpl.contact_zip or (contact.zip_code if contact else ""),
        "contact_email": contact.email if contact else "",
        "items": [
            {
                "description": item.description,
                "quantity": str(item.quantity),
                "unit_price": str(item.unit_price),
                "vat_rate": item.vat_rate,
            }
            for item in tpl.items
        ],
    })


def _save_items(form, tpl: InvoiceTemplate, db: Session) -> None:
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

        item = InvoiceTemplateItem(
            template_id=tpl.id,
            description=desc,
            quantity=qty,
            unit_price=price,
            vat_rate=vat,
            position=i,
        )
        db.add(item)
