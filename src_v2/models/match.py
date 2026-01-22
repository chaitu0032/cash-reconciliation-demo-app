"""Match and allocation schemas."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from .exception import MatchException


class MatchType(Enum):
    """How a match was established."""

    REMITTANCE_BACKED = "remittance_backed"  # Phase 1: via remittance advice
    REFERENCE_BASED = "reference_based"  # Phase 2: via bank description reference
    SUGGESTED = "suggested"  # Phase 3: algorithm suggestion
    MANUAL = "manual"  # User manually matched


class MatchStatus(Enum):
    """Current status of a match."""

    AUTO_APPROVED = "auto_approved"  # Automatically approved
    EXCEPTION = "exception"  # Has exceptions requiring review
    SUGGESTION = "suggestion"  # Suggested match awaiting approval
    MANUAL = "manual"  # Requires manual intervention


@dataclass
class InvoiceAllocation:
    """Represents allocation of payment to a specific invoice."""

    invoice_id: str
    invoice_number: str
    amount: Decimal
    is_partial: bool = False
    remaining_after: Decimal = field(default_factory=lambda: Decimal("0"))

    def __post_init__(self) -> None:
        """Ensure amounts are Decimal."""
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))
        if not isinstance(self.remaining_after, Decimal):
            self.remaining_after = Decimal(str(self.remaining_after))


@dataclass
class ReconciliationMatch:
    """Represents a complete reconciliation match for a bank transaction."""

    bank_id: str
    allocations: List[InvoiceAllocation]
    match_type: MatchType
    status: MatchStatus
    remittance_id: Optional[str] = None
    exceptions: List[MatchException] = field(default_factory=list)
    confidence: Optional[float] = None

    @property
    def total_allocated(self) -> Decimal:
        """Calculate total amount allocated across all invoices."""
        return sum(
            (alloc.amount for alloc in self.allocations), start=Decimal("0")
        )

    @property
    def has_exceptions(self) -> bool:
        """Check if match has any exceptions."""
        return len(self.exceptions) > 0

    @property
    def has_critical_exceptions(self) -> bool:
        """Check if match has critical exceptions."""
        return any(exc.is_critical for exc in self.exceptions)

    @property
    def invoice_count(self) -> int:
        """Number of invoices in this match."""
        return len(self.allocations)
