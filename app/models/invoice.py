from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, ForeignKey, Text, func
from sqlalchemy.orm import relationship

from ..database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String, unique=True, nullable=False, index=True)

    # Vazba na adresář (volitelná)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)

    # Snapshot odběratele v době vystavení
    contact_name = Column(String)
    contact_ico = Column(String)
    contact_dic = Column(String)
    contact_street = Column(String)
    contact_city = Column(String)
    contact_zip = Column(String)
    contact_email = Column(String)

    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    duzp = Column(Date)
    payment_method = Column(String, default="Bankovní převod")
    variable_symbol = Column(String)
    invoice_text = Column(Text)
    status = Column(String, default="Vystavena")  # Vystavena / Uhrazena / Stornována
    paid_date = Column(Date)
    created_at = Column(DateTime, server_default=func.now())

    contact = relationship("Contact", back_populates="invoices", foreign_keys=[contact_id])
    items = relationship(
        "InvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceItem.position",
    )

    @property
    def subtotal(self) -> Decimal:
        return sum((item.subtotal for item in self.items), Decimal("0"))

    @property
    def vat_total(self) -> Decimal:
        return sum((item.vat_amount for item in self.items), Decimal("0"))

    @property
    def total(self) -> Decimal:
        return self.subtotal + self.vat_total

    @property
    def vat_breakdown(self) -> dict:
        """Vrátí dict {vat_rate: {base, vat, total}} seřazený sestupně."""
        breakdown: dict = {}
        for item in self.items:
            rate = item.vat_rate
            if rate not in breakdown:
                breakdown[rate] = {"base": Decimal("0"), "vat": Decimal("0")}
            breakdown[rate]["base"] += item.subtotal
            breakdown[rate]["vat"] += item.vat_amount
        for rate, vals in breakdown.items():
            vals["total"] = vals["base"] + vals["vat"]
        return dict(sorted(breakdown.items(), reverse=True))

    @property
    def contact_address(self) -> str:
        parts = []
        if self.contact_street:
            parts.append(self.contact_street)
        city_part = ""
        if self.contact_zip:
            city_part = self.contact_zip + " "
        if self.contact_city:
            city_part += self.contact_city
        if city_part.strip():
            parts.append(city_part.strip())
        return ", ".join(parts)


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    description = Column(String, nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False, default=1)
    unit_price = Column(Numeric(12, 2), nullable=False)
    vat_rate = Column(Integer, nullable=False, default=21)
    position = Column(Integer, default=0)

    invoice = relationship("Invoice", back_populates="items")

    @property
    def subtotal(self) -> Decimal:
        return Decimal(str(self.quantity)) * Decimal(str(self.unit_price))

    @property
    def vat_amount(self) -> Decimal:
        return (self.subtotal * Decimal(str(self.vat_rate)) / 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def total(self) -> Decimal:
        return self.subtotal + self.vat_amount
