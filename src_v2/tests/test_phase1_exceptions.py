"""Tests for Phase 1 exception scenarios.

This module contains comprehensive test cases for all exception types
that can be raised during Phase 1 (Remittance-backed matching).
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from typing import List

from ..config import ReconciliationConfig
from ..matching.phase1_remittance import Phase1RemittanceMatcher, Phase1Result
from ..models.bank import BankTransaction
from ..models.exception import ExceptionType, Severity
from ..models.invoice import Invoice
from ..models.remittance import Remittance, RemittanceLineItem


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def config() -> ReconciliationConfig:
    """Default configuration for tests."""
    return ReconciliationConfig(
        amount_tolerance_percent=0.5,
        amount_tolerance_absolute=Decimal("10"),
        date_tolerance_days=14,
    )


@pytest.fixture
def matcher(config: ReconciliationConfig) -> Phase1RemittanceMatcher:
    """Phase 1 matcher instance."""
    return Phase1RemittanceMatcher(config)


def make_bank(
    id: str = "TXN-001",
    amount: Decimal = Decimal("1000.00"),
    reference: str = "REF-001",
    customer_id: str = "CUST-001",
    txn_date: date = None,
    payment_method: str = "WIRE",
) -> BankTransaction:
    """Helper to create bank transactions."""
    return BankTransaction(
        id=id,
        date=txn_date or date(2026, 1, 15),
        amount=amount,
        description=f"Payment from {customer_id}",
        customer_id=customer_id,
        reference=reference,
        payment_method=payment_method,
    )


def make_remittance(
    id: str = "REM-001",
    amount: Decimal = Decimal("1000.00"),
    reference: str = "REF-001",
    payer_id: str = "CUST-001",
    payer_name: str = "Test Customer",
    payment_date: date = None,
    payment_method: str = "WIRE",
    line_items: List[RemittanceLineItem] = None,
) -> Remittance:
    """Helper to create remittances."""
    return Remittance(
        id=id,
        payer_name=payer_name,
        payer_id=payer_id,
        payment_date=payment_date or date(2026, 1, 15),
        payment_amount_total=amount,
        payment_reference=reference,
        line_items=line_items or [],
        payment_method=payment_method,
    )


def make_invoice(
    id: str = "INV-001",
    invoice_number: str = "INV-2026-0001",
    customer_id: str = "CUST-001",
    amount: Decimal = Decimal("1000.00"),
    pending_amount: Decimal = None,
    due_date: date = None,
) -> Invoice:
    """Helper to create invoices."""
    return Invoice(
        id=id,
        invoice_number=invoice_number,
        customer_id=customer_id,
        amount=amount,
        pending_amount=pending_amount if pending_amount is not None else amount,
        due_date=due_date or date(2026, 1, 30),
    )


def make_line_item(
    invoice_number: str = "INV-2026-0001",
    amount_paid: Decimal = Decimal("1000.00"),
    deduction_amount: Decimal = None,
    deduction_reason: str = None,
    credit_note_reference: str = None,
) -> RemittanceLineItem:
    """Helper to create remittance line items."""
    return RemittanceLineItem(
        invoice_number=invoice_number,
        amount_paid=amount_paid,
        deduction_amount=deduction_amount,
        deduction_reason=deduction_reason,
        credit_note_reference=credit_note_reference,
    )


# ============================================================================
# AMOUNT_MISMATCH Tests
# ============================================================================

class TestAmountMismatch:
    """Tests for AMOUNT_MISMATCH exception scenarios."""

    def test_small_amount_difference_warning(self, matcher: Phase1RemittanceMatcher):
        """Small amount difference (< 5%) should create WARNING severity."""
        bank = make_bank(amount=Decimal("1000.00"))
        remittance = make_remittance(
            amount=Decimal("980.00"),  # 2% difference
            line_items=[make_line_item(amount_paid=Decimal("980.00"))],
        )
        invoice = make_invoice(amount=Decimal("980.00"), pending_amount=Decimal("980.00"))

        result = matcher.process([bank], [remittance], [invoice])

        assert len(result.matches) == 1
        exceptions = result.matches[0].exceptions
        amount_exceptions = [e for e in exceptions if e.type == ExceptionType.AMOUNT_MISMATCH]
        assert len(amount_exceptions) == 1
        assert amount_exceptions[0].severity == Severity.WARNING

    def test_large_amount_difference_critical(self, config: ReconciliationConfig):
        """Large amount difference (>= 5%) should create CRITICAL severity.

        Algorithm: Matching uses 2x tolerance, validation uses 1x tolerance.
        For 6% actual difference with 3% tolerance:
        - Matching: 2*3% = 6% tolerance -> match succeeds
        - Validation: 3% tolerance -> 6% exceeds it -> exception created
        - Severity: 6% >= 5% -> CRITICAL
        """
        config.amount_tolerance_percent = 3.0  # Matching allows 6% (2x), validation allows 3%
        config.amount_tolerance_absolute = Decimal("1")
        matcher = Phase1RemittanceMatcher(config)

        bank = make_bank(amount=Decimal("1000.00"))
        remittance = make_remittance(
            amount=Decimal("940.00"),  # 6% difference
            line_items=[make_line_item(amount_paid=Decimal("940.00"))],
        )
        invoice = make_invoice(amount=Decimal("940.00"), pending_amount=Decimal("940.00"))

        result = matcher.process([bank], [remittance], [invoice])

        assert len(result.matches) == 1
        exceptions = result.matches[0].exceptions
        amount_exceptions = [e for e in exceptions if e.type == ExceptionType.AMOUNT_MISMATCH]
        assert len(amount_exceptions) == 1
        assert amount_exceptions[0].severity == Severity.CRITICAL

    def test_bank_higher_than_remittance(self, matcher: Phase1RemittanceMatcher):
        """Bank amount higher than remittance should flag mismatch.

        Uses amounts within 2x initial tolerance (1%) but outside validation tolerance (0.5%).
        """
        # $5000 with 1% tolerance = $50 allowed, we use $30 diff (0.6% - within initial, outside validation)
        bank = make_bank(amount=Decimal("5000.00"))
        remittance = make_remittance(
            amount=Decimal("4970.00"),  # Bank is $30 higher (0.6%)
            line_items=[make_line_item(amount_paid=Decimal("4970.00"))],
        )
        invoice = make_invoice(amount=Decimal("4970.00"), pending_amount=Decimal("4970.00"))

        result = matcher.process([bank], [remittance], [invoice])

        assert len(result.matches) == 1
        exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.AMOUNT_MISMATCH]
        assert len(exceptions) == 1
        assert "5000" in exceptions[0].details["bank_amount"]
        assert "4970" in exceptions[0].details["remittance_amount"]

    def test_remittance_higher_than_bank(self, matcher: Phase1RemittanceMatcher):
        """Remittance amount higher than bank should flag mismatch.

        Uses amounts within 2x initial tolerance (1%) but outside validation tolerance (0.5%).
        """
        # $5000 with 1% tolerance = $50 allowed, we use $35 diff (0.7%)
        bank = make_bank(amount=Decimal("4965.00"))
        remittance = make_remittance(
            amount=Decimal("5000.00"),  # Remittance is $35 higher (0.7%)
            line_items=[make_line_item(amount_paid=Decimal("5000.00"))],
        )
        invoice = make_invoice(amount=Decimal("5000.00"), pending_amount=Decimal("5000.00"))

        result = matcher.process([bank], [remittance], [invoice])

        assert len(result.matches) == 1
        exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.AMOUNT_MISMATCH]
        assert len(exceptions) == 1

    def test_amount_within_tolerance_no_exception(self, matcher: Phase1RemittanceMatcher):
        """Amount within tolerance should not create exception."""
        bank = make_bank(amount=Decimal("1000.00"))
        remittance = make_remittance(
            amount=Decimal("1003.00"),  # Within 0.5% tolerance
            line_items=[make_line_item(amount_paid=Decimal("1003.00"))],
        )
        invoice = make_invoice(amount=Decimal("1003.00"), pending_amount=Decimal("1003.00"))

        result = matcher.process([bank], [remittance], [invoice])

        assert len(result.matches) == 1
        amount_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.AMOUNT_MISMATCH]
        assert len(amount_exceptions) == 0

    def test_amount_mismatch_with_fees_deducted(self, matcher: Phase1RemittanceMatcher):
        """Bank fees causing amount difference should be flagged.

        With $4000 amount and default 0.5% tolerance:
        - Percentage tolerance: 0.5% * $4000 = $20
        - Absolute tolerance: $10
        - Effective tolerance: $20
        - $25 wire fee exceeds $20 tolerance -> exception

        For matching (2x tolerance), $25 is within $40 -> match succeeds
        """
        # Common scenario: Wire transfer fees deducted from smaller payment
        bank = make_bank(amount=Decimal("3975.00"))  # After $25 wire fee
        remittance = make_remittance(
            amount=Decimal("4000.00"),  # Original amount
            line_items=[make_line_item(amount_paid=Decimal("4000.00"))],
        )
        invoice = make_invoice(amount=Decimal("4000.00"), pending_amount=Decimal("4000.00"))

        result = matcher.process([bank], [remittance], [invoice])

        assert len(result.matches) == 1
        exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.AMOUNT_MISMATCH]
        assert len(exceptions) == 1
        assert "25" in exceptions[0].details["difference"]


# ============================================================================
# DATE_DISCREPANCY Tests
# ============================================================================

class TestDateDiscrepancy:
    """Tests for DATE_DISCREPANCY exception scenarios."""

    def test_date_outside_tolerance_creates_exception(self, matcher: Phase1RemittanceMatcher):
        """Dates outside tolerance should create INFO exception."""
        bank = make_bank(txn_date=date(2026, 1, 30))
        remittance = make_remittance(
            payment_date=date(2026, 1, 10),  # 20 days difference (> 14 day tolerance)
            line_items=[make_line_item()],
        )
        invoice = make_invoice()

        result = matcher.process([bank], [remittance], [invoice])

        assert len(result.matches) == 1
        date_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.DATE_DISCREPANCY]
        assert len(date_exceptions) == 1
        assert date_exceptions[0].severity == Severity.INFO

    def test_bank_date_before_remittance(self, matcher: Phase1RemittanceMatcher):
        """Bank date significantly before remittance should flag discrepancy."""
        bank = make_bank(txn_date=date(2026, 1, 1))
        remittance = make_remittance(
            payment_date=date(2026, 1, 20),  # 19 days later
            line_items=[make_line_item()],
        )
        invoice = make_invoice()

        result = matcher.process([bank], [remittance], [invoice])

        date_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.DATE_DISCREPANCY]
        assert len(date_exceptions) == 1
        assert date_exceptions[0].details["days_difference"] == 19

    def test_bank_date_after_remittance(self, matcher: Phase1RemittanceMatcher):
        """Bank date significantly after remittance should flag discrepancy."""
        bank = make_bank(txn_date=date(2026, 1, 25))
        remittance = make_remittance(
            payment_date=date(2026, 1, 5),  # 20 days earlier
            line_items=[make_line_item()],
        )
        invoice = make_invoice()

        result = matcher.process([bank], [remittance], [invoice])

        date_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.DATE_DISCREPANCY]
        assert len(date_exceptions) == 1

    def test_date_within_tolerance_no_exception(self, matcher: Phase1RemittanceMatcher):
        """Dates within tolerance should not create exception."""
        bank = make_bank(txn_date=date(2026, 1, 15))
        remittance = make_remittance(
            payment_date=date(2026, 1, 10),  # 5 days difference (within 14 day tolerance)
            line_items=[make_line_item()],
        )
        invoice = make_invoice()

        result = matcher.process([bank], [remittance], [invoice])

        date_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.DATE_DISCREPANCY]
        assert len(date_exceptions) == 0

    def test_same_date_no_exception(self, matcher: Phase1RemittanceMatcher):
        """Same date should not create exception."""
        same_date = date(2026, 1, 15)
        bank = make_bank(txn_date=same_date)
        remittance = make_remittance(
            payment_date=same_date,
            line_items=[make_line_item()],
        )
        invoice = make_invoice()

        result = matcher.process([bank], [remittance], [invoice])

        date_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.DATE_DISCREPANCY]
        assert len(date_exceptions) == 0

    def test_weekend_processing_delay(self, matcher: Phase1RemittanceMatcher):
        """Simulate weekend processing delay scenario."""
        # Payment sent Friday, processed Monday - common scenario
        bank = make_bank(txn_date=date(2026, 1, 20))  # Monday
        remittance = make_remittance(
            payment_date=date(2026, 1, 17),  # Friday
            line_items=[make_line_item()],
        )
        invoice = make_invoice()

        result = matcher.process([bank], [remittance], [invoice])

        # 3 days is within tolerance, should be no exception
        date_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.DATE_DISCREPANCY]
        assert len(date_exceptions) == 0


# ============================================================================
# CUSTOMER_MISMATCH Tests
# ============================================================================

class TestCustomerMismatch:
    """Tests for CUSTOMER_MISMATCH exception scenarios.

    Note: Bank↔Remittance customer mismatch prevents initial matching (by design).
    CUSTOMER_MISMATCH exceptions are raised for Invoice↔Remittance mismatches.
    """

    def test_bank_without_customer_matches_any_remittance(self, matcher: Phase1RemittanceMatcher):
        """Bank without customer_id can match remittance, allowing validation to proceed."""
        bank = make_bank(customer_id=None)  # No customer on bank
        remittance = make_remittance(
            payer_id="CUST-002",
            line_items=[make_line_item()],
        )
        invoice = make_invoice(customer_id="CUST-002")

        result = matcher.process([bank], [remittance], [invoice])

        # Match succeeds because bank has no customer_id
        assert len(result.matches) == 1

    def test_invoice_remittance_customer_mismatch(self, matcher: Phase1RemittanceMatcher):
        """Invoice belonging to different customer should flag mismatch."""
        bank = make_bank(customer_id="CUST-001")
        remittance = make_remittance(
            payer_id="CUST-001",
            line_items=[make_line_item(invoice_number="INV-2026-0001")],
        )
        invoice = make_invoice(
            invoice_number="INV-2026-0001",
            customer_id="CUST-999",  # Invoice belongs to different customer
        )

        result = matcher.process([bank], [remittance], [invoice])

        customer_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.CUSTOMER_MISMATCH]
        assert len(customer_exceptions) >= 1
        # Should mention the invoice customer mismatch
        assert any("CUST-999" in str(e.details) for e in customer_exceptions)

    def test_third_party_payment_scenario(self, matcher: Phase1RemittanceMatcher):
        """Simulate third-party payment (parent company paying for subsidiary)."""
        bank = make_bank(customer_id="PARENT-CO")
        remittance = make_remittance(
            payer_id="PARENT-CO",
            payer_name="Parent Corporation",
            line_items=[make_line_item(invoice_number="INV-2026-0001")],
        )
        invoice = make_invoice(
            invoice_number="INV-2026-0001",
            customer_id="SUBSIDIARY-001",  # Invoice is for subsidiary
        )

        result = matcher.process([bank], [remittance], [invoice])

        customer_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.CUSTOMER_MISMATCH]
        assert len(customer_exceptions) >= 1

    def test_matching_customers_no_exception(self, matcher: Phase1RemittanceMatcher):
        """Matching customers should not create exception."""
        customer_id = "CUST-001"
        bank = make_bank(customer_id=customer_id)
        remittance = make_remittance(
            payer_id=customer_id,
            line_items=[make_line_item()],
        )
        invoice = make_invoice(customer_id=customer_id)

        result = matcher.process([bank], [remittance], [invoice])

        customer_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.CUSTOMER_MISMATCH]
        assert len(customer_exceptions) == 0


# ============================================================================
# MULTIPLE_REMITTANCES_ONE_BANK Tests
# ============================================================================

class TestMultipleRemittancesOneBank:
    """Tests for MULTIPLE_REMITTANCES_ONE_BANK exception scenarios.

    Note: Each remittance must individually match the bank (by reference + amount within 2x tolerance)
    for multiple remittances to be detected. This tests scenarios where a reference was reused.
    """

    def test_two_remittances_same_reference(self, config: ReconciliationConfig):
        """Two remittances with same reference matching one bank should create exception.

        Scenario: Customer reused a payment reference, creating two remittances.
        Both have amounts close to bank (within matching tolerance).
        """
        # Use wider tolerance to allow both remittances to match
        config.amount_tolerance_percent = 50.0  # Allow wide tolerance for this test
        config.amount_tolerance_absolute = Decimal("3000")
        matcher = Phase1RemittanceMatcher(config)

        bank = make_bank(amount=Decimal("5000.00"), reference="REF-MULTI")
        rem1 = make_remittance(
            id="REM-001",
            amount=Decimal("5000.00"),  # Same as bank
            reference="REF-MULTI",
            line_items=[make_line_item(invoice_number="INV-001", amount_paid=Decimal("2500.00")),
                       make_line_item(invoice_number="INV-002", amount_paid=Decimal("2500.00"))],
        )
        rem2 = make_remittance(
            id="REM-002",
            amount=Decimal("5000.00"),  # Same as bank - duplicate remittance
            reference="REF-MULTI",
            line_items=[make_line_item(invoice_number="INV-003", amount_paid=Decimal("2500.00")),
                       make_line_item(invoice_number="INV-004", amount_paid=Decimal("2500.00"))],
        )
        invoices = [
            make_invoice(id=f"I{i}", invoice_number=f"INV-00{i}", amount=Decimal("2500.00"), pending_amount=Decimal("2500.00"))
            for i in range(1, 5)
        ]

        result = matcher.process([bank], [rem1, rem2], invoices)

        assert len(result.matches) == 1
        multi_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.MULTIPLE_REMITTANCES_ONE_BANK]
        assert len(multi_exceptions) == 1
        assert "REM-001" in multi_exceptions[0].details["remittance_ids"]
        assert "REM-002" in multi_exceptions[0].details["remittance_ids"]

    def test_combined_remittances_match_bank_amount(self, config: ReconciliationConfig):
        """When combined remittance amounts match bank, severity should be INFO.

        Scenario: Two partial remittances that together equal the bank amount.
        """
        config.amount_tolerance_percent = 50.0
        config.amount_tolerance_absolute = Decimal("3000")
        matcher = Phase1RemittanceMatcher(config)

        bank = make_bank(amount=Decimal("5000.00"), reference="REF-COMBINED")
        rem1 = make_remittance(
            id="REM-001",
            amount=Decimal("3000.00"),
            reference="REF-COMBINED",
            line_items=[make_line_item(invoice_number="INV-001", amount_paid=Decimal("3000.00"))],
        )
        rem2 = make_remittance(
            id="REM-002",
            amount=Decimal("2000.00"),
            reference="REF-COMBINED",
            line_items=[make_line_item(invoice_number="INV-002", amount_paid=Decimal("2000.00"))],
        )
        inv1 = make_invoice(id="I1", invoice_number="INV-001", amount=Decimal("3000.00"), pending_amount=Decimal("3000.00"))
        inv2 = make_invoice(id="I2", invoice_number="INV-002", amount=Decimal("2000.00"), pending_amount=Decimal("2000.00"))

        result = matcher.process([bank], [rem1, rem2], [inv1, inv2])

        assert len(result.matches) == 1
        multi_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.MULTIPLE_REMITTANCES_ONE_BANK]
        assert len(multi_exceptions) == 1
        # When combined amount matches, severity should be INFO
        assert multi_exceptions[0].severity == Severity.INFO

    def test_three_remittances_one_bank(self, config: ReconciliationConfig):
        """Three remittances for one bank transaction."""
        config.amount_tolerance_percent = 70.0
        config.amount_tolerance_absolute = Decimal("7000")
        matcher = Phase1RemittanceMatcher(config)

        bank = make_bank(amount=Decimal("9000.00"), reference="REF-TRIPLE")
        remittances = [
            make_remittance(id=f"REM-{i}", amount=Decimal("3000.00"), reference="REF-TRIPLE",
                          line_items=[make_line_item(invoice_number=f"INV-{i}", amount_paid=Decimal("3000.00"))])
            for i in range(1, 4)
        ]
        invoices = [
            make_invoice(id=f"I{i}", invoice_number=f"INV-{i}", amount=Decimal("3000.00"), pending_amount=Decimal("3000.00"))
            for i in range(1, 4)
        ]

        result = matcher.process([bank], remittances, invoices)

        assert len(result.matches) == 1
        multi_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.MULTIPLE_REMITTANCES_ONE_BANK]
        assert len(multi_exceptions) == 1
        assert len(multi_exceptions[0].details["remittance_ids"]) == 3

    def test_duplicate_remittance_exact_match(self, matcher: Phase1RemittanceMatcher):
        """Two identical remittances (exact duplicates) for same bank.

        Most realistic scenario: system error created duplicate remittance.
        """
        bank = make_bank(amount=Decimal("1000.00"), reference="REF-DUP")
        rem1 = make_remittance(
            id="REM-001",
            amount=Decimal("1000.00"),
            reference="REF-DUP",
            line_items=[make_line_item(invoice_number="INV-001", amount_paid=Decimal("1000.00"))],
        )
        rem2 = make_remittance(
            id="REM-002",
            amount=Decimal("1000.00"),  # Exact duplicate
            reference="REF-DUP",
            line_items=[make_line_item(invoice_number="INV-001", amount_paid=Decimal("1000.00"))],
        )
        invoice = make_invoice(invoice_number="INV-001", amount=Decimal("1000.00"), pending_amount=Decimal("1000.00"))

        result = matcher.process([bank], [rem1, rem2], [invoice])

        assert len(result.matches) == 1
        multi_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.MULTIPLE_REMITTANCES_ONE_BANK]
        assert len(multi_exceptions) == 1


# ============================================================================
# INVOICE_NOT_FOUND Tests
# ============================================================================

class TestInvoiceNotFound:
    """Tests for INVOICE_NOT_FOUND exception scenarios."""

    def test_referenced_invoice_does_not_exist(self, matcher: Phase1RemittanceMatcher):
        """Remittance referencing non-existent invoice should flag."""
        bank = make_bank()
        remittance = make_remittance(
            line_items=[make_line_item(invoice_number="INV-NONEXISTENT")],
        )
        # No matching invoice provided

        result = matcher.process([bank], [remittance], [])

        assert len(result.matches) == 1
        not_found_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.INVOICE_NOT_FOUND]
        assert len(not_found_exceptions) == 1
        assert "INV-NONEXISTENT" in not_found_exceptions[0].details["invoice_number"]

    def test_multiple_missing_invoices(self, matcher: Phase1RemittanceMatcher):
        """Multiple missing invoices should create multiple exceptions."""
        bank = make_bank(amount=Decimal("3000.00"))
        remittance = make_remittance(
            amount=Decimal("3000.00"),
            line_items=[
                make_line_item(invoice_number="INV-MISSING-1", amount_paid=Decimal("1000.00")),
                make_line_item(invoice_number="INV-MISSING-2", amount_paid=Decimal("1000.00")),
                make_line_item(invoice_number="INV-MISSING-3", amount_paid=Decimal("1000.00")),
            ],
        )

        result = matcher.process([bank], [remittance], [])

        not_found_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.INVOICE_NOT_FOUND]
        assert len(not_found_exceptions) == 3

    def test_partial_invoice_match(self, matcher: Phase1RemittanceMatcher):
        """Some invoices found, some missing."""
        bank = make_bank(amount=Decimal("2000.00"))
        remittance = make_remittance(
            amount=Decimal("2000.00"),
            line_items=[
                make_line_item(invoice_number="INV-EXISTS", amount_paid=Decimal("1000.00")),
                make_line_item(invoice_number="INV-MISSING", amount_paid=Decimal("1000.00")),
            ],
        )
        invoice = make_invoice(invoice_number="INV-EXISTS", amount=Decimal("1000.00"), pending_amount=Decimal("1000.00"))

        result = matcher.process([bank], [remittance], [invoice])

        not_found_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.INVOICE_NOT_FOUND]
        assert len(not_found_exceptions) == 1
        assert "INV-MISSING" in not_found_exceptions[0].details["invoice_number"]

    def test_invoice_number_typo_scenario(self, matcher: Phase1RemittanceMatcher):
        """Simulate typo in invoice number (common real-world issue)."""
        bank = make_bank()
        remittance = make_remittance(
            line_items=[make_line_item(invoice_number="INV-2026-O001")],  # Letter O instead of 0
        )
        invoice = make_invoice(invoice_number="INV-2026-0001")  # Correct number

        result = matcher.process([bank], [remittance], [invoice])

        # Should flag as not found (exact match required)
        not_found_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.INVOICE_NOT_FOUND]
        assert len(not_found_exceptions) == 1


# ============================================================================
# DUPLICATE_PAYMENT Tests
# ============================================================================

class TestDuplicatePayment:
    """Tests for DUPLICATE_PAYMENT exception scenarios."""

    def test_invoice_already_fully_paid(self, matcher: Phase1RemittanceMatcher):
        """Payment for already paid invoice should flag as duplicate."""
        bank = make_bank()
        remittance = make_remittance(
            line_items=[make_line_item(invoice_number="INV-PAID")],
        )
        invoice = make_invoice(
            invoice_number="INV-PAID",
            amount=Decimal("1000.00"),
            pending_amount=Decimal("0.00"),  # Already fully paid
        )

        result = matcher.process([bank], [remittance], [invoice])

        dup_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.DUPLICATE_PAYMENT]
        assert len(dup_exceptions) == 1
        assert dup_exceptions[0].severity == Severity.CRITICAL

    def test_multiple_duplicate_payments(self, matcher: Phase1RemittanceMatcher):
        """Multiple invoices already paid should flag each."""
        bank = make_bank(amount=Decimal("2000.00"))
        remittance = make_remittance(
            amount=Decimal("2000.00"),
            line_items=[
                make_line_item(invoice_number="INV-PAID-1", amount_paid=Decimal("1000.00")),
                make_line_item(invoice_number="INV-PAID-2", amount_paid=Decimal("1000.00")),
            ],
        )
        invoices = [
            make_invoice(id="I1", invoice_number="INV-PAID-1", amount=Decimal("1000.00"), pending_amount=Decimal("0.00")),
            make_invoice(id="I2", invoice_number="INV-PAID-2", amount=Decimal("1000.00"), pending_amount=Decimal("0.00")),
        ]

        result = matcher.process([bank], [remittance], invoices)

        dup_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.DUPLICATE_PAYMENT]
        assert len(dup_exceptions) == 2

    def test_negative_pending_amount_duplicate(self, matcher: Phase1RemittanceMatcher):
        """Invoice with negative pending (overpaid) flagged as duplicate."""
        bank = make_bank()
        remittance = make_remittance(
            line_items=[make_line_item(invoice_number="INV-OVERPAID")],
        )
        invoice = make_invoice(
            invoice_number="INV-OVERPAID",
            amount=Decimal("1000.00"),
            pending_amount=Decimal("-50.00"),  # Already overpaid
        )

        result = matcher.process([bank], [remittance], [invoice])

        dup_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.DUPLICATE_PAYMENT]
        assert len(dup_exceptions) == 1

    def test_partial_payment_not_duplicate(self, matcher: Phase1RemittanceMatcher):
        """Partially paid invoice should not flag as duplicate."""
        bank = make_bank()
        remittance = make_remittance(
            line_items=[make_line_item(invoice_number="INV-PARTIAL", amount_paid=Decimal("500.00"))],
        )
        invoice = make_invoice(
            invoice_number="INV-PARTIAL",
            amount=Decimal("1000.00"),
            pending_amount=Decimal("500.00"),  # Half paid, half remaining
        )

        result = matcher.process([bank], [remittance], [invoice])

        dup_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.DUPLICATE_PAYMENT]
        assert len(dup_exceptions) == 0


# ============================================================================
# OVERPAYMENT Tests
# ============================================================================

class TestOverpayment:
    """Tests for OVERPAYMENT exception scenarios."""

    def test_payment_exceeds_pending_amount(self, matcher: Phase1RemittanceMatcher):
        """Payment exceeding pending amount should flag overpayment."""
        bank = make_bank(amount=Decimal("1500.00"))
        remittance = make_remittance(
            amount=Decimal("1500.00"),
            line_items=[make_line_item(invoice_number="INV-001", amount_paid=Decimal("1500.00"))],
        )
        invoice = make_invoice(
            invoice_number="INV-001",
            amount=Decimal("1000.00"),
            pending_amount=Decimal("1000.00"),  # Only $1000 pending
        )

        result = matcher.process([bank], [remittance], [invoice])

        overpay_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.OVERPAYMENT]
        assert len(overpay_exceptions) == 1
        assert "500" in overpay_exceptions[0].details["overpayment"]

    def test_small_overpayment_within_tolerance(self, matcher: Phase1RemittanceMatcher):
        """Small overpayment within tolerance should not flag."""
        bank = make_bank(amount=Decimal("1005.00"))
        remittance = make_remittance(
            amount=Decimal("1005.00"),
            line_items=[make_line_item(invoice_number="INV-001", amount_paid=Decimal("1005.00"))],
        )
        invoice = make_invoice(
            invoice_number="INV-001",
            amount=Decimal("1000.00"),
            pending_amount=Decimal("1000.00"),
        )

        result = matcher.process([bank], [remittance], [invoice])

        # $5 overpayment is within $10 tolerance
        overpay_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.OVERPAYMENT]
        assert len(overpay_exceptions) == 0

    def test_large_overpayment(self, matcher: Phase1RemittanceMatcher):
        """Large overpayment should flag with details."""
        bank = make_bank(amount=Decimal("10000.00"))
        remittance = make_remittance(
            amount=Decimal("10000.00"),
            line_items=[make_line_item(invoice_number="INV-001", amount_paid=Decimal("10000.00"))],
        )
        invoice = make_invoice(
            invoice_number="INV-001",
            amount=Decimal("5000.00"),
            pending_amount=Decimal("5000.00"),
        )

        result = matcher.process([bank], [remittance], [invoice])

        overpay_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.OVERPAYMENT]
        assert len(overpay_exceptions) == 1
        assert overpay_exceptions[0].severity == Severity.WARNING
        assert "5000" in overpay_exceptions[0].details["overpayment"]

    def test_overpayment_on_partial_invoice(self, matcher: Phase1RemittanceMatcher):
        """Overpaying on partially paid invoice."""
        bank = make_bank(amount=Decimal("800.00"))
        remittance = make_remittance(
            amount=Decimal("800.00"),
            line_items=[make_line_item(invoice_number="INV-001", amount_paid=Decimal("800.00"))],
        )
        invoice = make_invoice(
            invoice_number="INV-001",
            amount=Decimal("1000.00"),
            pending_amount=Decimal("500.00"),  # Already $500 paid, only $500 remaining
        )

        result = matcher.process([bank], [remittance], [invoice])

        overpay_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.OVERPAYMENT]
        assert len(overpay_exceptions) == 1
        assert "300" in overpay_exceptions[0].details["overpayment"]  # $800 - $500 = $300 overpayment


# ============================================================================
# CREDIT_NOTE_NOT_FOUND Tests
# ============================================================================

class TestCreditNoteNotFound:
    """Tests for CREDIT_NOTE_NOT_FOUND exception scenarios."""

    def test_referenced_credit_note_missing(self, matcher: Phase1RemittanceMatcher):
        """Credit note referenced but not found should flag."""
        bank = make_bank(amount=Decimal("900.00"))
        remittance = make_remittance(
            amount=Decimal("900.00"),
            line_items=[
                make_line_item(
                    invoice_number="INV-001",
                    amount_paid=Decimal("900.00"),
                    credit_note_reference="CN-001",  # Credit note referenced
                )
            ],
        )
        invoice = make_invoice(invoice_number="INV-001", amount=Decimal("1000.00"), pending_amount=Decimal("1000.00"))
        # No credit note provided

        result = matcher.process([bank], [remittance], [invoice])

        cn_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.CREDIT_NOTE_NOT_FOUND]
        assert len(cn_exceptions) == 1
        assert cn_exceptions[0].severity == Severity.INFO
        assert "CN-001" in cn_exceptions[0].details["credit_note_reference"]

    def test_multiple_missing_credit_notes(self, matcher: Phase1RemittanceMatcher):
        """Multiple missing credit notes should flag each."""
        bank = make_bank(amount=Decimal("1800.00"))
        remittance = make_remittance(
            amount=Decimal("1800.00"),
            line_items=[
                make_line_item(invoice_number="INV-001", amount_paid=Decimal("900.00"), credit_note_reference="CN-001"),
                make_line_item(invoice_number="INV-002", amount_paid=Decimal("900.00"), credit_note_reference="CN-002"),
            ],
        )
        invoices = [
            make_invoice(id="I1", invoice_number="INV-001", amount=Decimal("1000.00"), pending_amount=Decimal("1000.00")),
            make_invoice(id="I2", invoice_number="INV-002", amount=Decimal("1000.00"), pending_amount=Decimal("1000.00")),
        ]

        result = matcher.process([bank], [remittance], invoices)

        cn_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.CREDIT_NOTE_NOT_FOUND]
        assert len(cn_exceptions) == 2

    def test_no_credit_note_reference_no_exception(self, matcher: Phase1RemittanceMatcher):
        """No credit note reference should not create exception."""
        bank = make_bank()
        remittance = make_remittance(
            line_items=[make_line_item(invoice_number="INV-001", credit_note_reference=None)],
        )
        invoice = make_invoice(invoice_number="INV-001")

        result = matcher.process([bank], [remittance], [invoice])

        cn_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.CREDIT_NOTE_NOT_FOUND]
        assert len(cn_exceptions) == 0


# ============================================================================
# LINE_ITEMS_SUM_MISMATCH Tests
# ============================================================================

class TestLineItemsSumMismatch:
    """Tests for LINE_ITEMS_SUM_MISMATCH exception scenarios."""

    def test_line_items_dont_sum_to_total(self, matcher: Phase1RemittanceMatcher):
        """Line items not summing to total should flag."""
        bank = make_bank(amount=Decimal("1000.00"))
        remittance = make_remittance(
            amount=Decimal("1000.00"),  # Total is $1000
            line_items=[
                make_line_item(invoice_number="INV-001", amount_paid=Decimal("600.00")),
                make_line_item(invoice_number="INV-002", amount_paid=Decimal("300.00")),
                # Sum is $900, not $1000
            ],
        )
        invoices = [
            make_invoice(id="I1", invoice_number="INV-001", amount=Decimal("600.00"), pending_amount=Decimal("600.00")),
            make_invoice(id="I2", invoice_number="INV-002", amount=Decimal("300.00"), pending_amount=Decimal("300.00")),
        ]

        result = matcher.process([bank], [remittance], invoices)

        sum_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.LINE_ITEMS_SUM_MISMATCH]
        assert len(sum_exceptions) == 1
        assert sum_exceptions[0].severity == Severity.WARNING
        assert "900" in sum_exceptions[0].details["line_items_total"]
        assert "1000" in sum_exceptions[0].details["payment_total"]

    def test_line_items_exceed_total(self, matcher: Phase1RemittanceMatcher):
        """Line items exceeding total should flag."""
        bank = make_bank(amount=Decimal("1000.00"))
        remittance = make_remittance(
            amount=Decimal("1000.00"),
            line_items=[
                make_line_item(invoice_number="INV-001", amount_paid=Decimal("600.00")),
                make_line_item(invoice_number="INV-002", amount_paid=Decimal("500.00")),
                # Sum is $1100, exceeds $1000
            ],
        )
        invoices = [
            make_invoice(id="I1", invoice_number="INV-001", amount=Decimal("600.00"), pending_amount=Decimal("600.00")),
            make_invoice(id="I2", invoice_number="INV-002", amount=Decimal("500.00"), pending_amount=Decimal("500.00")),
        ]

        result = matcher.process([bank], [remittance], invoices)

        sum_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.LINE_ITEMS_SUM_MISMATCH]
        assert len(sum_exceptions) == 1

    def test_line_items_match_total_no_exception(self, matcher: Phase1RemittanceMatcher):
        """Line items matching total should not flag."""
        bank = make_bank(amount=Decimal("1000.00"))
        remittance = make_remittance(
            amount=Decimal("1000.00"),
            line_items=[
                make_line_item(invoice_number="INV-001", amount_paid=Decimal("600.00")),
                make_line_item(invoice_number="INV-002", amount_paid=Decimal("400.00")),
                # Sum is exactly $1000
            ],
        )
        invoices = [
            make_invoice(id="I1", invoice_number="INV-001", amount=Decimal("600.00"), pending_amount=Decimal("600.00")),
            make_invoice(id="I2", invoice_number="INV-002", amount=Decimal("400.00"), pending_amount=Decimal("400.00")),
        ]

        result = matcher.process([bank], [remittance], invoices)

        sum_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.LINE_ITEMS_SUM_MISMATCH]
        assert len(sum_exceptions) == 0

    def test_missing_line_item_scenario(self, matcher: Phase1RemittanceMatcher):
        """Simulate missing line item in remittance (common data quality issue)."""
        bank = make_bank(amount=Decimal("5000.00"))
        remittance = make_remittance(
            amount=Decimal("5000.00"),
            line_items=[
                make_line_item(invoice_number="INV-001", amount_paid=Decimal("2000.00")),
                make_line_item(invoice_number="INV-002", amount_paid=Decimal("1500.00")),
                # Missing INV-003 for $1500
            ],
        )
        invoices = [
            make_invoice(id="I1", invoice_number="INV-001", amount=Decimal("2000.00"), pending_amount=Decimal("2000.00")),
            make_invoice(id="I2", invoice_number="INV-002", amount=Decimal("1500.00"), pending_amount=Decimal("1500.00")),
        ]

        result = matcher.process([bank], [remittance], invoices)

        sum_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.LINE_ITEMS_SUM_MISMATCH]
        assert len(sum_exceptions) == 1
        assert "1500" in sum_exceptions[0].details["difference"]


# ============================================================================
# DEDUCTION_WITHOUT_REASON Tests
# ============================================================================

class TestDeductionWithoutReason:
    """Tests for DEDUCTION_WITHOUT_REASON exception scenarios."""

    def test_deduction_without_reason(self, matcher: Phase1RemittanceMatcher):
        """Deduction without explanation should flag."""
        bank = make_bank(amount=Decimal("900.00"))
        remittance = make_remittance(
            amount=Decimal("900.00"),
            line_items=[
                RemittanceLineItem(
                    invoice_number="INV-001",
                    amount_paid=Decimal("900.00"),
                    deduction_amount=Decimal("100.00"),  # $100 deducted
                    deduction_reason=None,  # No reason provided
                )
            ],
        )
        invoice = make_invoice(invoice_number="INV-001", amount=Decimal("1000.00"), pending_amount=Decimal("1000.00"))

        result = matcher.process([bank], [remittance], [invoice])

        deduction_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.DEDUCTION_WITHOUT_REASON]
        assert len(deduction_exceptions) == 1
        assert deduction_exceptions[0].severity == Severity.INFO
        assert "100" in deduction_exceptions[0].details["deduction_amount"]

    def test_multiple_unexplained_deductions(self, matcher: Phase1RemittanceMatcher):
        """Multiple unexplained deductions should flag each."""
        bank = make_bank(amount=Decimal("1700.00"))
        remittance = make_remittance(
            amount=Decimal("1700.00"),
            line_items=[
                RemittanceLineItem(
                    invoice_number="INV-001",
                    amount_paid=Decimal("900.00"),
                    deduction_amount=Decimal("100.00"),
                    deduction_reason=None,
                ),
                RemittanceLineItem(
                    invoice_number="INV-002",
                    amount_paid=Decimal("800.00"),
                    deduction_amount=Decimal("200.00"),
                    deduction_reason=None,
                ),
            ],
        )
        invoices = [
            make_invoice(id="I1", invoice_number="INV-001", amount=Decimal("1000.00"), pending_amount=Decimal("1000.00")),
            make_invoice(id="I2", invoice_number="INV-002", amount=Decimal("1000.00"), pending_amount=Decimal("1000.00")),
        ]

        result = matcher.process([bank], [remittance], invoices)

        deduction_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.DEDUCTION_WITHOUT_REASON]
        assert len(deduction_exceptions) == 2

    def test_deduction_with_reason_no_exception(self, matcher: Phase1RemittanceMatcher):
        """Deduction with reason should not flag."""
        bank = make_bank(amount=Decimal("900.00"))
        remittance = make_remittance(
            amount=Decimal("900.00"),
            line_items=[
                RemittanceLineItem(
                    invoice_number="INV-001",
                    amount_paid=Decimal("900.00"),
                    deduction_amount=Decimal("100.00"),
                    deduction_reason="Early payment discount",  # Reason provided
                )
            ],
        )
        invoice = make_invoice(invoice_number="INV-001", amount=Decimal("1000.00"), pending_amount=Decimal("1000.00"))

        result = matcher.process([bank], [remittance], [invoice])

        deduction_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.DEDUCTION_WITHOUT_REASON]
        assert len(deduction_exceptions) == 0

    def test_zero_deduction_no_exception(self, matcher: Phase1RemittanceMatcher):
        """Zero deduction should not flag."""
        bank = make_bank()
        remittance = make_remittance(
            line_items=[
                RemittanceLineItem(
                    invoice_number="INV-001",
                    amount_paid=Decimal("1000.00"),
                    deduction_amount=Decimal("0.00"),  # Zero deduction
                    deduction_reason=None,
                )
            ],
        )
        invoice = make_invoice(invoice_number="INV-001")

        result = matcher.process([bank], [remittance], [invoice])

        deduction_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.DEDUCTION_WITHOUT_REASON]
        assert len(deduction_exceptions) == 0

    def test_common_deduction_scenarios(self, matcher: Phase1RemittanceMatcher):
        """Test common deduction scenarios - damaged goods, returns, etc."""
        bank = make_bank(amount=Decimal("2500.00"))
        remittance = make_remittance(
            amount=Decimal("2500.00"),
            line_items=[
                RemittanceLineItem(
                    invoice_number="INV-001",
                    amount_paid=Decimal("900.00"),
                    deduction_amount=Decimal("100.00"),
                    deduction_reason="Damaged goods - claim #12345",
                ),
                RemittanceLineItem(
                    invoice_number="INV-002",
                    amount_paid=Decimal("800.00"),
                    deduction_amount=Decimal("200.00"),
                    deduction_reason="Return authorization #RA-789",
                ),
                RemittanceLineItem(
                    invoice_number="INV-003",
                    amount_paid=Decimal("800.00"),
                    deduction_amount=Decimal("200.00"),
                    deduction_reason=None,  # This one has no reason
                ),
            ],
        )
        invoices = [
            make_invoice(id="I1", invoice_number="INV-001", amount=Decimal("1000.00"), pending_amount=Decimal("1000.00")),
            make_invoice(id="I2", invoice_number="INV-002", amount=Decimal("1000.00"), pending_amount=Decimal("1000.00")),
            make_invoice(id="I3", invoice_number="INV-003", amount=Decimal("1000.00"), pending_amount=Decimal("1000.00")),
        ]

        result = matcher.process([bank], [remittance], invoices)

        deduction_exceptions = [e for e in result.matches[0].exceptions if e.type == ExceptionType.DEDUCTION_WITHOUT_REASON]
        # Only the third line item should flag
        assert len(deduction_exceptions) == 1
        assert "INV-003" in deduction_exceptions[0].details["invoice_number"]


# ============================================================================
# Combined/Complex Scenarios
# ============================================================================

class TestComplexScenarios:
    """Tests for complex real-world scenarios with multiple exceptions."""

    def test_multiple_exception_types(self, config: ReconciliationConfig):
        """Single match can have multiple different exception types.

        Tests a scenario with:
        - Amount mismatch (3.5% difference, config set to allow matching but flag)
        - Date discrepancy (outside 14 day tolerance)
        - Invoice not found
        - Customer mismatch (invoice vs remittance)
        - Deduction without reason
        """
        # Configure tolerance so 3.5% difference triggers exception but allows matching
        config.amount_tolerance_percent = 2.0  # Matching: 4%, Validation: 2%
        config.amount_tolerance_absolute = Decimal("5")
        matcher = Phase1RemittanceMatcher(config)

        bank = make_bank(
            amount=Decimal("965.00"),  # 3.5% difference from $1000
            txn_date=date(2026, 1, 30),  # 29 days from remittance - outside 14 day tolerance
            customer_id="CUST-001",
        )
        remittance = make_remittance(
            amount=Decimal("1000.00"),
            payment_date=date(2026, 1, 1),  # 29 days different
            payer_id="CUST-001",  # Same customer to allow matching
            line_items=[
                make_line_item(invoice_number="INV-MISSING", amount_paid=Decimal("500.00")),
                RemittanceLineItem(
                    invoice_number="INV-EXISTS",
                    amount_paid=Decimal("500.00"),
                    deduction_amount=Decimal("50.00"),
                    deduction_reason=None,
                ),
            ],
        )
        # Invoice belongs to different customer than remittance payer
        invoice = make_invoice(id="I1", invoice_number="INV-EXISTS", customer_id="CUST-999", amount=Decimal("550.00"), pending_amount=Decimal("550.00"))

        result = matcher.process([bank], [remittance], [invoice])

        assert len(result.matches) == 1
        exceptions = result.matches[0].exceptions

        # Should have multiple exception types
        exception_types = {e.type for e in exceptions}
        assert ExceptionType.AMOUNT_MISMATCH in exception_types
        assert ExceptionType.DATE_DISCREPANCY in exception_types
        assert ExceptionType.CUSTOMER_MISMATCH in exception_types  # Invoice vs remittance
        assert ExceptionType.INVOICE_NOT_FOUND in exception_types
        assert ExceptionType.DEDUCTION_WITHOUT_REASON in exception_types

    def test_clean_match_no_exceptions(self, matcher: Phase1RemittanceMatcher):
        """Perfect match should have no exceptions and be auto-approved."""
        bank = make_bank(
            amount=Decimal("1000.00"),
            txn_date=date(2026, 1, 15),
            customer_id="CUST-001",
            reference="REF-PERFECT",
        )
        remittance = make_remittance(
            amount=Decimal("1000.00"),
            payment_date=date(2026, 1, 15),
            payer_id="CUST-001",
            reference="REF-PERFECT",
            line_items=[make_line_item(invoice_number="INV-001", amount_paid=Decimal("1000.00"))],
        )
        invoice = make_invoice(
            invoice_number="INV-001",
            customer_id="CUST-001",
            amount=Decimal("1000.00"),
            pending_amount=Decimal("1000.00"),
        )

        result = matcher.process([bank], [remittance], [invoice])

        assert len(result.matches) == 1
        assert len(result.matches[0].exceptions) == 0
        from ..models.match import MatchStatus
        assert result.matches[0].status == MatchStatus.AUTO_APPROVED

    def test_high_volume_batch(self, matcher: Phase1RemittanceMatcher):
        """Test processing multiple transactions in a batch."""
        banks = [make_bank(id=f"TXN-{i:03d}", reference=f"REF-{i:03d}") for i in range(10)]
        remittances = [
            make_remittance(
                id=f"REM-{i:03d}",
                reference=f"REF-{i:03d}",
                line_items=[make_line_item(invoice_number=f"INV-{i:03d}")],
            )
            for i in range(10)
        ]
        invoices = [make_invoice(id=f"I{i}", invoice_number=f"INV-{i:03d}") for i in range(10)]

        result = matcher.process(banks, remittances, invoices)

        assert len(result.matches) == 10
        assert len(result.matched_bank_ids) == 10
        assert len(result.matched_remittance_ids) == 10
