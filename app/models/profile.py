from sqlalchemy import Column, Integer, String, Text, Boolean

from ..database import Base


class Profile(Base):
    __tablename__ = "profile"

    id = Column(Integer, primary_key=True, default=1)

    # Osobní a firemní údaje
    first_name = Column(String, default="")
    last_name = Column(String, default="")
    email = Column(String, default="")
    phone = Column(String, default="")
    company_name = Column(String, default="")
    ico = Column(String, default="")
    dic = Column(String, default="")
    vat_payer = Column(Boolean, default=True)

    # Adresa
    street = Column(String, default="")
    house_number = Column(String, default="")
    orientation_number = Column(String, default="")
    city = Column(String, default="")
    zip_code = Column(String, default="")
    country = Column(String, default="Česká republika")

    # Bankovní spojení
    bank_name = Column(String, default="")
    bank_account = Column(String, default="")
    iban = Column(String, default="")
    currency = Column(String, default="CZK")

    # Finanční úřad
    fu_ufo = Column(String, default="")
    fu_pracufo = Column(String, default="")
    okec = Column(String, default="")
    ds_type = Column(String, default="F")

    # Výchozí nastavení faktur
    default_due_days = Column(Integer, default=10)
    default_payment_method = Column(String, default="Bankovní převod")
    default_invoice_text = Column(Text, default="")
    default_vat_rate = Column(Integer, default=21)
    expense_flat_rate = Column(Integer, default=60)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def full_street(self) -> str:
        parts = [self.street]
        if self.house_number:
            parts.append(self.house_number)
            if self.orientation_number:
                parts[-1] += f"/{self.orientation_number}"
        return " ".join(parts)
