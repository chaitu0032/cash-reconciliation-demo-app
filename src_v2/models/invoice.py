"""Invoice schema."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class Invoice:
    """Represents an invoice record."""

    id: str
    invoice_number: str
    customer_id: str
    amount: Decimal
    pending_amount: Decimal
    due_date: date

    def __post_init__(self) -> None:
        """Ensure amounts are Decimal."""
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))
        if not isinstance(self.pending_amount, Decimal):
            self.pending_amount = Decimal(str(self.pending_amount))

    @property
    def is_fully_paid(self) -> bool:
        """Check if invoice is fully paid."""
        return self.pending_amount <= Decimal("0")

    @property
    def is_partially_paid(self) -> bool:
        """Check if invoice has partial payment."""
        return Decimal("0") < self.pending_amount < self.amount
