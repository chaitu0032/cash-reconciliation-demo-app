"""
Data models for Cash Reconciliation Platform - Phase 1
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional


class BankTransactionStatus(Enum):
    """Bank transaction matching status"""
    OPEN = "Open"           # Not yet matched to a remittance
    MATCHED = "Matched"     # Matched to exactly one remittance


class RemittanceStatus(Enum):
    """Remittance matching status"""
    OPEN = "Open"           # Not yet matched to a bank transaction
    MATCHED = "Matched"     # Matched to exactly one bank transaction


class InvoiceStatus(Enum):
    """Invoice payment status - tracks payment progress"""
    OPEN = "Open"           # No payment received yet
    PARTIAL = "Partial"     # Some payment received, amount still pending (underpayment)
    CLOSED = "Closed"       # Fully paid (pending_amount = 0)


class MatchOutcome(Enum):
    AUTO_MATCHED = "AUTO_MATCHED"
    SUGGEST_MATCH = "SUGGEST_MATCH"
    EXCEPTION = "EXCEPTION"
    UNMATCHED = "UNMATCHED"


class ExceptionCode(Enum):
    """
    Exceptions organized by level:

    DOCUMENT LEVEL (Bank Transaction):
    - E007: Orphan bank transaction - no matching remittance found
    - E008: Duplicate remittance match - bank txn already matched, another remittance matches

    REMITTANCE LEVEL:
    - E005: Invalid invoice - remittance references invoice not found in system
    - E009: Customer not identified from remittance data

    INVOICE LEVEL:
    - E002: Overpayment - cumulative payments exceed invoice amount
    - E004: Duplicate payment - invoice already closed, receiving another payment

    Note:
    - Underpayment is NOT an exception - it's invoice status PARTIAL
    """
    # Document Level (Bank Transaction)
    E007 = "Orphan bank txn"
    E008 = "Duplicate remittance match"

    # Remittance Level
    E005 = "Invalid invoice reference"
    E009 = "Customer not identified"

    # Invoice Level
    E002 = "Overpayment"
    E004 = "Duplicate payment"


class RemittanceSource(Enum):
    ACTUAL = "ACTUAL"  # Real remittance document from customer
    BANK_PARSED = "BANK_PARSED"  # Virtual remittance created from bank description


@dataclass
class BankTransaction:
    """Bank statement transaction - 1:1 relationship with Remittance"""
    id: str
    amount: Decimal
    date: date
    reference: str
    description: str
    status: BankTransactionStatus = BankTransactionStatus.OPEN
    matched_remittance_id: Optional[str] = None  # 1:1 - exactly one remittance


@dataclass
class RemittanceLineItem:
    """Single line item in a remittance - matched to one invoice (N:1)"""
    invoice_number: str
    description: str
    payment_method: str
    amount: Decimal
    matched_invoice_id: Optional[str] = None  # The invoice this line item pays


@dataclass
class Remittance:
    """Payment advice from customer - 1:1 relationship with BankTransaction"""
    id: str
    customer_id: Optional[str]
    customer_name: str
    customer_address: Optional[str]
    payment_reference: str
    payment_date: date
    line_items: list[RemittanceLineItem] = field(default_factory=list)
    source: RemittanceSource = RemittanceSource.ACTUAL
    status: RemittanceStatus = RemittanceStatus.OPEN
    matched_bank_transaction_id: Optional[str] = None  # 1:1 - exactly one bank txn

    @property
    def total_amount(self) -> Decimal:
        return sum(item.amount for item in self.line_items)


@dataclass
class RemittanceLineRef:
    """Reference to a remittance line item that paid an invoice"""
    remittance_id: str
    line_index: int
    amount: Decimal


@dataclass
class Invoice:
    """Customer invoice - can be paid by multiple remittance line items (N:1)"""
    invoice_id: str
    customer_id: str
    due_date: date
    amount: Decimal
    pending_amount: Decimal
    status: InvoiceStatus = InvoiceStatus.OPEN
    matched_remittance_lines: list[RemittanceLineRef] = field(default_factory=list)


@dataclass
class Customer:
    """Customer master data"""
    customer_id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    address: Optional[str] = None
    payment_ref_patterns: list[str] = field(default_factory=list)
    account_numbers: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    """Result of a matching operation"""
    outcome: MatchOutcome
    confidence: int  # 0-100
    rule_applied: str
    source_id: str
    target_id: Optional[str] = None
    exception_code: Optional[ExceptionCode] = None
    exception_detail: Optional[str] = None


@dataclass
class Level1Match:
    """Bank to Remittance match result"""
    bank_transaction_id: str
    remittance_id: Optional[str]
    result: MatchResult


@dataclass
class Level2Match:
    """Remittance line to Invoice match result"""
    remittance_id: str
    remittance_line_index: int
    invoice_id: Optional[str]
    result: MatchResult


@dataclass
class ReconciliationResult:
    """Full reconciliation result for a bank transaction"""
    bank_transaction: BankTransaction
    level1_match: Optional[Level1Match] = None
    level2_matches: list[Level2Match] = field(default_factory=list)
    fully_reconciled: bool = False


@dataclass
class InvoiceReconciliationStatus:
    """
    Invoice-centric reconciliation status.

    Shows the full chain: Invoice ← Remittance Line ← Remittance ← Bank Transaction
    An invoice is RECONCILED only when the entire chain has no exceptions.
    """
    invoice: Invoice

    # Matched remittance lines (can be multiple - partial payments)
    matched_lines: list[RemittanceLineRef] = field(default_factory=list)

    # Remittance details (with confidence)
    remittance_id: Optional[str] = None
    remittance_reference: Optional[str] = None  # payment_reference from Remittance
    remittance_match_confidence: int = 0  # Level 2 match confidence
    remittance_exception: Optional[ExceptionCode] = None

    # Bank transaction details (with confidence)
    bank_transaction_id: Optional[str] = None
    bank_reference: Optional[str] = None  # reference from BankTransaction
    bank_match_confidence: int = 0  # Level 1 match confidence
    bank_exception: Optional[ExceptionCode] = None

    # Matched line item reference (invoice_number from RemittanceLineItem)
    matched_line_ref: Optional[str] = None

    # Invoice-level exception
    invoice_exception: Optional[ExceptionCode] = None

    @property
    def is_reconciled(self) -> bool:
        """
        Invoice is reconciled only when:
        1. Invoice has no exception (E002, E004)
        2. Remittance has no exception (E005, E009)
        3. Bank transaction has no exception (E007, E008)
        """
        return (
            self.invoice_exception is None
            and self.remittance_exception is None
            and self.bank_exception is None
            and self.invoice.status == InvoiceStatus.CLOSED
        )

    @property
    def reconciliation_status(self) -> str:
        """Human-readable reconciliation status"""
        if self.is_reconciled:
            return "RECONCILED"
        if self.invoice_exception:
            return f"EXCEPTION: {self.invoice_exception.value}"
        if self.remittance_exception:
            return f"EXCEPTION: {self.remittance_exception.value}"
        if self.bank_exception:
            return f"EXCEPTION: {self.bank_exception.value}"
        if self.invoice.status == InvoiceStatus.PARTIAL:
            return "PARTIAL"
        if self.invoice.status == InvoiceStatus.OPEN:
            return "UNMATCHED"
        return "UNKNOWN"
