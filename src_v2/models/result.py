"""Result schemas for reconciliation output."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List

from .exception import ExceptionType
from .invoice import Invoice
from .match import InvoiceAllocation, ReconciliationMatch
from .remittance import Remittance


class SuggestionType(Enum):
    """How a suggestion was generated."""

    SINGLE_INVOICE = "single_invoice"  # Customer has only one open invoice
    UNIQUE_AMOUNT = "unique_amount"  # Amount uniquely matches one invoice
    UNIQUE_COMBINATION = "unique_combination"  # Amount matches unique combo
    FLOW_MATCH = "flow_match"  # Flow network suggestion


class ConfidenceTier(Enum):
    """Confidence level tiers for suggestions."""

    HIGH = "high"  # 85%+ confidence
    MEDIUM = "medium"  # 65-84% confidence
    LOW = "low"  # Below 65% confidence


@dataclass
class Suggestion:
    """Represents a suggested match for user review."""

    bank_id: str
    allocations: List[InvoiceAllocation]
    suggestion_type: SuggestionType
    confidence: float
    tier: ConfidenceTier
    explanation: str
    alternatives: List[List[InvoiceAllocation]] = field(default_factory=list)

    @property
    def total_amount(self) -> Decimal:
        """Total amount in primary suggestion."""
        return sum(
            (alloc.amount for alloc in self.allocations), start=Decimal("0")
        )

    @property
    def has_alternatives(self) -> bool:
        """Check if suggestion has alternative matches."""
        return len(self.alternatives) > 0


@dataclass
class ManualItem:
    """Represents an item requiring manual reconciliation."""

    bank_id: str
    amount: Decimal
    reason: str
    candidate_invoices: List[Invoice] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Ensure amount is Decimal."""
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))


@dataclass
class ReconciliationStats:
    """Statistics from a reconciliation run."""

    total_banks: int
    total_remittances: int
    auto_approved_count: int
    auto_approved_amount: Decimal
    exception_count: int
    exception_by_type: Dict[ExceptionType, int]
    suggestion_count: int
    manual_count: int
    orphan_remittance_count: int

    def __post_init__(self) -> None:
        """Ensure amount is Decimal."""
        if not isinstance(self.auto_approved_amount, Decimal):
            self.auto_approved_amount = Decimal(str(self.auto_approved_amount))

    @property
    def total_processed(self) -> int:
        """Total items processed (excluding orphans)."""
        return (
            self.auto_approved_count
            + self.exception_count
            + self.suggestion_count
            + self.manual_count
        )

    @property
    def auto_approval_rate(self) -> float:
        """Percentage of items auto-approved."""
        if self.total_processed == 0:
            return 0.0
        return self.auto_approved_count / self.total_processed


@dataclass
class ReconciliationResult:
    """Complete result from a reconciliation run."""

    auto_approved: List[ReconciliationMatch]
    exceptions: List[ReconciliationMatch]
    suggestions: List[Suggestion]
    manual: List[ManualItem]
    orphan_remittances: List[Remittance]
    stats: ReconciliationStats

    @property
    def all_matches(self) -> List[ReconciliationMatch]:
        """All matches (auto-approved + exceptions)."""
        return self.auto_approved + self.exceptions

    @property
    def total_auto_approved_amount(self) -> Decimal:
        """Total amount auto-approved."""
        return sum(
            (match.total_allocated for match in self.auto_approved),
            start=Decimal("0"),
        )

    @property
    def total_exception_amount(self) -> Decimal:
        """Total amount in exceptions."""
        return sum(
            (match.total_allocated for match in self.exceptions),
            start=Decimal("0"),
        )
