from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship

from ..database import Base


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    ico = Column(String, index=True)
    dic = Column(String)
    street = Column(String)
    city = Column(String)
    zip_code = Column(String)
    country = Column(String, default="Česká republika")
    email = Column(String)
    phone = Column(String)
    contact_type = Column(String, default="Obojí")  # Odběratel / Dodavatel / Obojí
    created_at = Column(DateTime, server_default=func.now())

    invoices = relationship("Invoice", back_populates="contact", foreign_keys="Invoice.contact_id")
    expenses = relationship("Expense", back_populates="contact", foreign_keys="Expense.contact_id")

    @property
    def full_address(self) -> str:
        parts = []
        if self.street:
            parts.append(self.street)
        city_part = ""
        if self.zip_code:
            city_part = self.zip_code + " "
        if self.city:
            city_part += self.city
        if city_part.strip():
            parts.append(city_part.strip())
        if self.country and self.country != "Česká republika":
            parts.append(self.country)
        return ", ".join(parts)
