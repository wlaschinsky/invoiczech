"""Generování QR kódu pro českou platbu (formát SPD)."""
import base64
import io
from decimal import Decimal
from typing import Optional

import qrcode
import qrcode.constants


def compute_czech_iban(account_number: str) -> str:
    """
    Vypočítá IBAN z českého čísla účtu ve formátu [PREFIX-]CISLO/BANKA.
    Vrátí prázdný řetězec, pokud výpočet selže.
    """
    try:
        if "/" not in account_number:
            return ""
        account_part, bank_code = account_number.rsplit("/", 1)
        bank_code = bank_code.strip()

        if "-" in account_part:
            prefix, number = account_part.strip().split("-", 1)
        else:
            prefix = "0"
            number = account_part.strip()

        if len(number) > 10 or len(prefix) > 6 or len(bank_code) != 4:
            return ""

        bban = bank_code + prefix.zfill(6) + number.zfill(10)
        if len(bban) != 20:
            return ""

        # CZ = C(12) + Z(35)
        rearranged = bban + "1235" + "00"
        remainder = int(rearranged) % 97
        check = str(98 - remainder).zfill(2)
        return f"CZ{check}{bban}"
    except Exception:
        return ""


def generate_payment_qr(
    amount: Decimal,
    variable_symbol: str,
    iban: Optional[str] = None,
    account_number: Optional[str] = None,
    message: str = "",
) -> str:
    """
    Vygeneruje QR kód pro českou platbu ve formátu SPD a vrátí base64 PNG.
    Vrátí prázdný řetězec, pokud není k dispozici IBAN.
    """
    resolved_iban = iban or ""
    if not resolved_iban and account_number:
        resolved_iban = compute_czech_iban(account_number)

    if not resolved_iban:
        return ""

    spd_parts = [
        "SPD",
        "1.0",
        f"ACC:{resolved_iban}",
        f"AM:{float(amount):.2f}",
        "CC:CZK",
    ]
    if variable_symbol:
        spd_parts.append(f"VS:{variable_symbol}")
    if message:
        spd_parts.append(f"MSG:{message[:35]}")

    spd = "*".join(spd_parts)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=5,
        border=2,
    )
    qr.add_data(spd)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode("utf-8")
