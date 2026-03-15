"""Generování PDF faktur pomocí WeasyPrint."""
import os
from decimal import Decimal

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

from ..config import get_settings
from ..models.invoice import Invoice
from .qr_code import generate_payment_qr

settings = get_settings()


def _get_template_env() -> Environment:
    templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    return Environment(loader=FileSystemLoader(os.path.abspath(templates_dir)))


def _fmt_czk(value) -> str:
    if value is None:
        return "0,00"
    d = Decimal(str(value))
    formatted = f"{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", " ")
    return formatted


def generate_invoice_pdf(invoice: Invoice) -> bytes:
    """Vygeneruje PDF faktury a vrátí bytes."""
    env = _get_template_env()
    env.filters["czk"] = _fmt_czk
    template = env.get_template("invoices/pdf.html")

    qr_base64 = generate_payment_qr(
        amount=invoice.total,
        variable_symbol=invoice.variable_symbol or "",
        iban=settings.SUPPLIER_IBAN or None,
        account_number=settings.SUPPLIER_ACCOUNT,
        message=f"Faktura {invoice.number}",
    )

    html_content = template.render(
        invoice=invoice,
        settings=settings,
        qr_base64=qr_base64,
    )

    base_url = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
    pdf_bytes = HTML(string=html_content, base_url=base_url).write_pdf()
    return pdf_bytes
