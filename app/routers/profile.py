"""Profil podnikatele — údaje uložené v DB."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.profile import Profile
from ..tmpl import templates
from .utils import flash

router = APIRouter(prefix="/profil")


def get_profile(db: Session) -> Profile:
    """Vrátí profil (singleton, vytvoří pokud neexistuje)."""
    profile = db.query(Profile).first()
    if not profile:
        profile = Profile(id=1)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.get("", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    profile = get_profile(db)
    return templates.TemplateResponse(
        "profile.html",
        {"request": request, "profile": profile},
    )


@router.post("")
async def save_profile(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    profile = get_profile(db)

    # Sekce 1 — Osobní a firemní
    profile.first_name = form.get("first_name", "").strip()
    profile.last_name = form.get("last_name", "").strip()
    profile.email = form.get("email", "").strip()
    profile.phone = form.get("phone", "").strip()
    profile.company_name = form.get("company_name", "").strip()
    profile.ico = form.get("ico", "").strip()
    profile.dic = form.get("dic", "").strip()
    profile.vat_payer = form.get("vat_payer") == "1"

    # Adresa
    profile.street = form.get("street", "").strip()
    profile.house_number = form.get("house_number", "").strip()
    profile.orientation_number = form.get("orientation_number", "").strip()
    profile.city = form.get("city", "").strip()
    profile.zip_code = form.get("zip_code", "").strip()
    profile.country = form.get("country", "Česká republika").strip()

    # Sekce 2 — Bankovní spojení
    profile.bank_name = form.get("bank_name", "").strip()
    profile.bank_account = form.get("bank_account", "").strip()
    profile.iban = form.get("iban", "").strip()
    profile.currency = form.get("currency", "CZK").strip()

    # Sekce 3 — Finanční úřad
    profile.fu_ufo = form.get("fu_ufo", "").strip()
    profile.fu_pracufo = form.get("fu_pracufo", "").strip()
    profile.okec = form.get("okec", "").strip()
    profile.ds_type = form.get("ds_type", "F").strip()
    try:
        profile.expense_flat_rate = int(form.get("expense_flat_rate", 60))
    except ValueError:
        profile.expense_flat_rate = 60

    # Sekce 4 — Výchozí nastavení faktur
    try:
        profile.default_due_days = int(form.get("default_due_days", 10))
    except ValueError:
        profile.default_due_days = 10
    profile.default_payment_method = form.get("default_payment_method", "Bankovní převod").strip()
    profile.default_invoice_text = form.get("default_invoice_text", "").strip()
    try:
        profile.default_vat_rate = int(form.get("default_vat_rate", 21))
    except ValueError:
        profile.default_vat_rate = 21

    db.commit()
    flash(request, "Profil uložen.", "success")
    return RedirectResponse(url="/profil", status_code=303)
