from ..tmpl import templates
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.contact import Contact
from ..services.ares import lookup_ico
from .utils import flash

router = APIRouter(prefix="/adresar")


@router.get("", response_class=HTMLResponse)
async def contacts_list(request: Request, q: str = "", typ: str = "", db: Session = Depends(get_db)):
    query = db.query(Contact)
    if q:
        query = query.filter(
            Contact.name.ilike(f"%{q}%") | Contact.ico.ilike(f"%{q}%")
        )
    if typ:
        query = query.filter(Contact.contact_type == typ)
    contacts = query.order_by(Contact.name).all()
    return templates.TemplateResponse(
        "contacts/list.html",
        {"request": request, "contacts": contacts, "q": q, "typ": typ},
    )


@router.get("/novy", response_class=HTMLResponse)
async def new_contact_form(request: Request):
    return templates.TemplateResponse("contacts/form.html", {"request": request, "contact": None})


@router.post("/novy")
async def create_contact(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    contact = Contact(
        name=form.get("name", "").strip(),
        ico=form.get("ico", "").strip(),
        dic=form.get("dic", "").strip(),
        street=form.get("street", "").strip(),
        city=form.get("city", "").strip(),
        zip_code=form.get("zip_code", "").strip(),
        country=form.get("country", "Česká republika").strip(),
        email=form.get("email", "").strip(),
        phone=form.get("phone", "").strip(),
        contact_type=form.get("contact_type", "Obojí"),
    )
    if not contact.name:
        flash(request, "Název je povinný.", "error")
        return templates.TemplateResponse("contacts/form.html", {"request": request, "contact": contact})

    db.add(contact)
    db.commit()
    db.refresh(contact)
    flash(request, f"Kontakt '{contact.name}' byl pridan.", "success")
    return RedirectResponse(url=f"/adresar/{contact.id}", status_code=302)


@router.get("/{contact_id}", response_class=HTMLResponse)
async def contact_detail(request: Request, contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Kontakt nenalezen")
    return templates.TemplateResponse("contacts/detail.html", {"request": request, "contact": contact})


@router.get("/{contact_id}/upravit", response_class=HTMLResponse)
async def edit_contact_form(request: Request, contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Kontakt nenalezen")
    return templates.TemplateResponse("contacts/form.html", {"request": request, "contact": contact})


@router.post("/{contact_id}/upravit")
async def update_contact(request: Request, contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Kontakt nenalezen")

    form = await request.form()
    contact.name = form.get("name", "").strip()
    contact.ico = form.get("ico", "").strip()
    contact.dic = form.get("dic", "").strip()
    contact.street = form.get("street", "").strip()
    contact.city = form.get("city", "").strip()
    contact.zip_code = form.get("zip_code", "").strip()
    contact.country = form.get("country", "Česká republika").strip()
    contact.email = form.get("email", "").strip()
    contact.phone = form.get("phone", "").strip()
    contact.contact_type = form.get("contact_type", "Obojí")

    if not contact.name:
        flash(request, "Název je povinný.", "error")
        return templates.TemplateResponse("contacts/form.html", {"request": request, "contact": contact})

    db.commit()
    flash(request, "Kontakt byl uložen.", "success")
    return RedirectResponse(url=f"/adresar/{contact_id}", status_code=302)


@router.post("/{contact_id}/smazat")
async def delete_contact(request: Request, contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Kontakt nenalezen")

    from ..models.invoice import Invoice
    from ..models.expense import Expense
    inv_count = db.query(Invoice).filter(Invoice.contact_id == contact_id).count()
    exp_count = db.query(Expense).filter(Expense.contact_id == contact_id).count()
    if inv_count + exp_count > 0:
        flash(request, f"Kontakt nelze smazat — je použit v {inv_count} fakturách a {exp_count} nákladech.", "error")
        return RedirectResponse(url=f"/adresar/{contact_id}", status_code=302)

    db.delete(contact)
    db.commit()
    flash(request, "Kontakt byl smazán.", "success")
    return RedirectResponse(url="/adresar", status_code=302)


@router.get("/ares/{ico}")
async def ares_lookup(ico: str):
    """AJAX endpoint pro načtení dat z ARES."""
    result = await lookup_ico(ico)
    if result is None:
        return JSONResponse({"error": "Nepodařilo se načíst data z ARES"}, status_code=503)
    return JSONResponse(result)
