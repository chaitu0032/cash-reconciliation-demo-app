"""Remittance and line item schemas."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Optional


@dataclass
class RemittanceLineItem:
    """Represents a single line item in a remittance advice."""

    invoice_number: str
    amount_paid: Decimal
    invoice_date: Optional[date] = None
    invoice_amount_original: Optional[Decimal] = None
    remaining_balance: Optional[Decimal] = None
    deduction_amount: Optional[Decimal] = None
    deduction_reason: Optional[str] = None
    credit_note_reference: Optional[str] = None

    def __post_init__(self) -> None:
        """Ensure amounts are Decimal."""
        if not isinstance(self.amount_paid, Decimal):
            self.amount_paid = Decimal(str(self.amount_paid))
        if self.invoice_amount_original is not None and not isinstance(
            self.invoice_amount_original, Decimal
        ):
            self.invoice_amount_original = Decimal(str(self.invoice_amount_original))
        if self.remaining_balance is not None and not isinstance(
            self.remaining_balance, Decimal
        ):
            self.remaining_balance = Decimal(str(self.remaining_balance))
        if self.deduction_amount is not None and not isinstance(
            self.deduction_amount, Decimal
        ):
            self.deduction_amount = Decimal(str(self.deduction_amount))

    @property
    def has_deduction(self) -> bool:
        """Check if line item has a deduction."""
        return (
            self.deduction_amount is not None and self.deduction_amount > Decimal("0")
        )


@dataclass
class Remittance:
    """Represents a remittance advice document."""

    id: str
    payer_name: str
    payer_id: str
    payment_date: date
    payment_amount_total: Decimal
    payment_reference: str
    line_items: List[RemittanceLineItem] = field(default_factory=list)
    currency: str = "USD"
    payment_method: str = "WIRE"
    source: str = "MANUAL"

    def __post_init__(self) -> None:
        """Ensure amount is Decimal."""
        if not isinstance(self.payment_amount_total, Decimal):
            self.payment_amount_total = Decimal(str(self.payment_amount_total))

    @property
    def line_items_total(self) -> Decimal:
        """Calculate sum of all line item amounts."""
        return sum(
            (item.amount_paid for item in self.line_items), start=Decimal("0")
        )

    @property
    def has_line_items_mismatch(self) -> bool:
        """Check if line items sum doesn't match total."""
        if not self.line_items:
            return False
        return self.line_items_total != self.payment_amount_total

    @property
    def total_deductions(self) -> Decimal:
        """Calculate total deductions across all line items."""
        return sum(
            (item.deduction_amount or Decimal("0") for item in self.line_items),
            start=Decimal("0"),
        )
