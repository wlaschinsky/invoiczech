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
    from ..models.invoice import Invoice
    from ..models.expense import Expense
    from sqlalchemy import func

    query = db.query(Contact)
    if q:
        query = query.filter(
            Contact.name.ilike(f"%{q}%") | Contact.ico.ilike(f"%{q}%")
        )
    if typ:
        query = query.filter(Contact.contact_type == typ)
    contacts = query.order_by(Contact.name).all()

    # Počítat podle contact_id i contact_name (starší záznamy nemají FK)
    inv_by_id = dict(
        db.query(Invoice.contact_id, func.count())
        .filter(Invoice.contact_id.isnot(None))
        .group_by(Invoice.contact_id)
        .all()
    )
    inv_by_name = dict(
        db.query(Invoice.contact_name, func.count())
        .filter(Invoice.contact_name.isnot(None), Invoice.contact_id.is_(None))
        .group_by(Invoice.contact_name)
        .all()
    )
    exp_by_id = dict(
        db.query(Expense.contact_id, func.count())
        .filter(Expense.contact_id.isnot(None))
        .group_by(Expense.contact_id)
        .all()
    )
    exp_by_name = dict(
        db.query(Expense.contact_name, func.count())
        .filter(Expense.contact_name.isnot(None), Expense.contact_id.is_(None))
        .group_by(Expense.contact_name)
        .all()
    )

    inv_counts = {}
    exp_counts = {}
    for c in contacts:
        inv_counts[c.id] = inv_by_id.get(c.id, 0) + inv_by_name.get(c.name, 0)
        exp_counts[c.id] = exp_by_id.get(c.id, 0) + exp_by_name.get(c.name, 0)

    total_count = db.query(Contact).count()

    return templates.TemplateResponse(
        "contacts/list.html",
        {
            "request": request,
            "contacts": contacts,
            "q": q,
            "typ": typ,
            "inv_counts": inv_counts,
            "exp_counts": exp_counts,
            "total_count": total_count,
        },
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
    from ..models.invoice import Invoice
    from ..models.expense import Expense

    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Kontakt nenalezen")

    inv_count = (
        db.query(Invoice).filter(
            (Invoice.contact_id == contact_id) |
            ((Invoice.contact_id.is_(None)) & (Invoice.contact_name == contact.name))
        ).count()
    )
    exp_count = (
        db.query(Expense).filter(
            (Expense.contact_id == contact_id) |
            ((Expense.contact_id.is_(None)) & (Expense.contact_name == contact.name))
        ).count()
    )

    return templates.TemplateResponse(
        "contacts/detail.html",
        {"request": request, "contact": contact, "inv_count": inv_count, "exp_count": exp_count},
    )


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
async def ares_lookup(ico: str, db: Session = Depends(get_db)):
    """AJAX endpoint — zkontroluj adresář, pokud tam není, dotáhni z ARES."""
    existing = db.query(Contact).filter(Contact.ico == ico).first()
    if existing:
        return JSONResponse({
            "source": "adresar",
            "id": existing.id,
            "name": existing.name,
            "ico": existing.ico or "",
            "dic": existing.dic or "",
            "street": existing.street or "",
            "zip_code": existing.zip_code or "",
            "city": existing.city or "",
            "email": existing.email or "",
        })

    result = await lookup_ico(ico)
    if result is None:
        return JSONResponse({"error": "Nepodařilo se načíst data z ARES"}, status_code=503)
    result["source"] = "ares"
    return JSONResponse(result)


@router.post("/ares/ulozit")
async def save_ares_contact(request: Request, db: Session = Depends(get_db)):
    """AJAX endpoint — uloží kontakt načtený z ARES do adresáře."""
    data = await request.json()
    ico = data.get("ico", "").strip()
    if not ico:
        return JSONResponse({"error": "IČO je povinné"}, status_code=400)

    existing = db.query(Contact).filter(Contact.ico == ico).first()
    if existing:
        return JSONResponse({"id": existing.id, "name": existing.name})

    contact = Contact(
        name=data.get("name", "").strip(),
        ico=ico,
        dic=data.get("dic", "").strip(),
        street=data.get("street", "").strip(),
        city=data.get("city", "").strip(),
        zip_code=data.get("zip_code", "").strip(),
        country="Česká republika",
        contact_type=data.get("contact_type", "Obojí"),
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return JSONResponse({"id": contact.id, "name": contact.name})
