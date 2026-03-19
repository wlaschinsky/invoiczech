from sqlalchemy import Column, Integer, String, Text

from ..database import Base


class Profile(Base):
    __tablename__ = "profile"

    id = Column(Integer, primary_key=True, default=1)

    # Osobní údaje
    first_name = Column(String, default="")
    last_name = Column(String, default="")
    email = Column(String, default="")
    phone = Column(String, default="")

    # Adresa
    street = Column(String, default="")
    house_number = Column(String, default="")       # číslo popisné
    orientation_number = Column(String, default="")  # číslo orientační
    city = Column(String, default="")
    zip_code = Column(String, default="")

    # Podnikatelské údaje
    company_name = Column(String, default="")
    ico = Column(String, default="")
    dic = Column(String, default="")

    # Bankovní údaje
    bank_account = Column(String, default="")
    iban = Column(String, default="")

    # Finanční úřad
    fu_ufo = Column(String, default="")
    fu_pracufo = Column(String, default="")
    okec = Column(String, default="")

    # Výchozí text faktury
    default_invoice_text = Column(Text, default="")

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
