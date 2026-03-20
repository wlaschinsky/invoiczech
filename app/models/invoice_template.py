from decimal import Decimal

from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Text
from sqlalchemy.orm import relationship

from ..database import Base


class InvoiceTemplate(Base):
    __tablename__ = "invoice_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    contact_name = Column(String)
    contact_ico = Column(String)
    contact_dic = Column(String)
    contact_street = Column(String)
    contact_city = Column(String)
    contact_zip = Column(String)
    payment_method = Column(String, default="Bankovní převod")
    due_days = Column(Integer, default=10)

    items = relationship(
        "InvoiceTemplateItem",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="InvoiceTemplateItem.position",
    )
    contact = relationship("Contact", foreign_keys=[contact_id])

    @property
    def total(self) -> Decimal:
        return sum(
            (Decimal(str(i.quantity)) * Decimal(str(i.unit_price))
             * (1 + Decimal(str(i.vat_rate)) / 100)
             for i in self.items),
            Decimal("0"),
        )


class InvoiceTemplateItem(Base):
    __tablename__ = "invoice_template_items"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("invoice_templates.id"), nullable=False)
    description = Column(String, nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False, default=1)
    unit_price = Column(Numeric(12, 2), nullable=False)
    vat_rate = Column(Integer, nullable=False, default=21)
    position = Column(Integer, default=0)

    template = relationship("InvoiceTemplate", back_populates="items")

    @property
    def subtotal(self) -> Decimal:
        return Decimal(str(self.quantity)) * Decimal(str(self.unit_price))

    @property
    def total(self) -> Decimal:
        return self.subtotal * (1 + Decimal(str(self.vat_rate)) / 100)
