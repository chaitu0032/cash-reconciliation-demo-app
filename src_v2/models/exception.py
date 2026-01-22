"""Exception types and schemas for reconciliation issues."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ExceptionType(Enum):
    """Types of exceptions that can occur during reconciliation."""

    # Bank ↔ Remittance exceptions
    AMOUNT_MISMATCH = "amount_mismatch"
    DATE_DISCREPANCY = "date_discrepancy"
    MULTIPLE_REMITTANCES_ONE_BANK = "multiple_remittances_one_bank"
    MULTIPLE_BANKS_ONE_REMITTANCE = "multiple_banks_one_remittance"
    ORPHAN_REMITTANCE_NO_BANK = "orphan_remittance_no_bank"

    # Remittance ↔ Invoice exceptions
    INVOICE_NOT_FOUND = "invoice_not_found"
    CUSTOMER_MISMATCH = "customer_mismatch"
    DUPLICATE_PAYMENT = "duplicate_payment"
    OVERPAYMENT = "overpayment"
    CREDIT_NOTE_NOT_FOUND = "credit_note_not_found"

    # Internal consistency exceptions
    LINE_ITEMS_SUM_MISMATCH = "line_items_sum_mismatch"
    DEDUCTION_WITHOUT_REASON = "deduction_without_reason"


class Severity(Enum):
    """Severity levels for exceptions."""

    CRITICAL = "critical"  # Requires immediate attention
    WARNING = "warning"  # Should be reviewed
    INFO = "info"  # Informational, may auto-resolve


@dataclass
class MatchException:
    """Represents an exception/issue found during reconciliation."""

    type: ExceptionType
    severity: Severity
    entity_id: str
    details: Dict[str, Any] = field(default_factory=dict)
    suggested_resolution: Optional[str] = None

    @property
    def is_critical(self) -> bool:
        """Check if exception is critical severity."""
        return self.severity == Severity.CRITICAL

    @property
    def is_blocking(self) -> bool:
        """Check if exception blocks auto-approval."""
        return self.severity in (Severity.CRITICAL, Severity.WARNING)
