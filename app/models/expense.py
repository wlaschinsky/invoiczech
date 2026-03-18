from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, ForeignKey, Text, Boolean, func
from sqlalchemy.orm import relationship

from ..database import Base


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False, default="")

    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    contact_name = Column(String)  # denormalizovaný název pro rychlé zobrazení

    supplier_document_number = Column(String)
    issue_date = Column(Date, nullable=False)
    duzp = Column(Date)
    payment_method = Column(String, default="Bankovní převod")
    paid_date = Column(Date)
    document_type = Column(String, default="Faktura")  # Faktura / Účtenka / Jiný
    tax_deductible = Column(String, default="Nevím")  # Ano / Ne / Nevím
    fulfillment_code = Column(String)
    price_includes_vat = Column(Boolean, default=True)
    attachment_path = Column(String)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    contact = relationship("Contact", back_populates="expenses", foreign_keys=[contact_id])
    items = relationship(
        "ExpenseItem",
        back_populates="expense",
        cascade="all, delete-orphan",
        order_by="ExpenseItem.position",
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


class ExpenseItem(Base):
    __tablename__ = "expense_items"

    id = Column(Integer, primary_key=True, index=True)
    expense_id = Column(Integer, ForeignKey("expenses.id"), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False, default=1)
    unit = Column(String, default="ks")
    description = Column(String, nullable=False)
    # unit_price je vždy cena BEZ DPH (konverze probíhá při uložení)
    unit_price = Column(Numeric(12, 4), nullable=False)
    vat_rate = Column(Integer, nullable=False, default=21)
    position = Column(Integer, default=0)

    expense = relationship("Expense", back_populates="items")

    @property
    def subtotal(self) -> Decimal:
        return (Decimal(str(self.quantity)) * Decimal(str(self.unit_price))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def vat_amount(self) -> Decimal:
        return (self.subtotal * Decimal(str(self.vat_rate)) / 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def total(self) -> Decimal:
        return self.subtotal + self.vat_amount
