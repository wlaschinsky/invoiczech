"""Generování PDF faktur pomocí WeasyPrint."""
import base64
import os
from decimal import Decimal

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

from ..models.invoice import Invoice
from .qr_code import generate_payment_qr


def _get_template_env() -> Environment:
    templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    return Environment(loader=FileSystemLoader(os.path.abspath(templates_dir)))


def _fmt_czk(value) -> str:
    if value is None:
        return "0,00"
    d = Decimal(str(value))
    formatted = f"{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", " ")
    return formatted


def _fmt_date(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    return str(value)


def _fmt_num(value, decimals: int = 2) -> str:
    if value is None:
        return "0"
    d = Decimal(str(value))
    return f"{d:.{decimals}f}".replace(".", ",")


def _get_profile():
    from ..database import SessionLocal
    from ..models.profile import Profile
    db = SessionLocal()
    try:
        profile = db.query(Profile).first()
        if not profile:
            profile = Profile(id=1)
            db.add(profile)
            db.commit()
            db.refresh(profile)
        db.expunge(profile)
        return profile
    finally:
        db.close()


def generate_invoice_pdf(invoice: Invoice) -> bytes:
    """Vygeneruje PDF faktury a vrátí bytes."""
    profile = _get_profile()

    env = _get_template_env()
    env.filters["czk"] = _fmt_czk
    env.filters["date_cs"] = _fmt_date
    env.filters["num"] = _fmt_num
    template = env.get_template("invoices/pdf.html")

    qr_base64 = generate_payment_qr(
        amount=invoice.total,
        variable_symbol=invoice.variable_symbol or "",
        iban=profile.iban or None,
        account_number=profile.bank_account,
        message=f"Faktura {invoice.number}",
    )

    logo_base64 = None
    if getattr(profile, "logo_mode", "default") == "custom" and profile.logo_path:
        try:
            with open(profile.logo_path, "rb") as f:
                raw = f.read()
            ext = profile.logo_path.rsplit(".", 1)[-1].lower()
            mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                    "svg": "image/svg+xml", "webp": "image/webp"}.get(ext, "image/png")
            logo_base64 = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
        except OSError:
            pass

    html_content = template.render(
        invoice=invoice,
        profile=profile,
        qr_base64=qr_base64,
        logo_base64=logo_base64,
    )

    base_url = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
    pdf_bytes = HTML(string=html_content, base_url=base_url).write_pdf()
    return pdf_bytes
