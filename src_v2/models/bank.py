"""Bank transaction schema."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class BankTransaction:
    """Represents a bank transaction record."""

    id: str
    date: date
    amount: Decimal
    description: str
    customer_id: Optional[str] = None
    reference: Optional[str] = None
    payment_method: Optional[str] = None  # WIRE, ACH, CHECK, etc.

    def __post_init__(self) -> None:
        """Ensure amount is Decimal."""
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))
