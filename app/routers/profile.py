"""Profil podnikatele — údaje uložené v DB."""
import os
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.profile import Profile
from ..services.qr_code import compute_czech_iban
from ..tmpl import templates
from .utils import flash

UPLOADS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads"))
ALLOWED_LOGO_TYPES = {"image/png", "image/jpeg", "image/svg+xml", "image/webp"}
MAX_LOGO_SIZE = 512 * 1024  # 512 KB

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


@router.get("/logo")
async def serve_logo(db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse, Response
    profile = get_profile(db)
    if profile.logo_mode == "custom" and profile.logo_path and os.path.exists(profile.logo_path):
        return FileResponse(profile.logo_path)
    return Response(status_code=404)


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

    # Logo
    logo_mode = form.get("logo_mode", "default")
    if logo_mode in ("default", "custom", "none"):
        profile.logo_mode = logo_mode
    logo_file = form.get("logo_file")
    if logo_mode == "custom" and logo_file and hasattr(logo_file, "filename") and logo_file.filename:
        content = await logo_file.read()
        if len(content) > MAX_LOGO_SIZE:
            flash(request, "Logo je příliš velké (max 512 KB).", "error")
        elif logo_file.content_type not in ALLOWED_LOGO_TYPES:
            flash(request, "Nepodporovaný formát loga (PNG, JPG, SVG, WebP).", "error")
        else:
            ext = logo_file.filename.rsplit(".", 1)[-1].lower()
            dest = os.path.join(UPLOADS_DIR, f"logo_{profile.id}.{ext}")
            # Smazat staré logo
            if profile.logo_path and os.path.exists(profile.logo_path):
                os.remove(profile.logo_path)
            with open(dest, "wb") as f:
                f.write(content)
            profile.logo_path = dest

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
    profile.iban = compute_czech_iban(profile.bank_account) if profile.bank_account else ""
    profile.currency = form.get("currency", "CZK").strip()

    # Sekce 3 — Finanční úřad
    profile.fu_ufo = form.get("fu_ufo", "").strip()
    profile.fu_pracufo = form.get("fu_pracufo", "").strip()
    profile.okec = form.get("okec", "").strip()
    profile.ds_type = form.get("ds_type", "F").strip()

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
