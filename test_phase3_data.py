"""Test data generator for Phase 3 suggestions.

This creates realistic test scenarios for all Phase 3 strategies:
1. Single invoice per customer (95% confidence)
2. Unique amount match (90% confidence)
3. Unique combination (85% confidence)
4. Flow network matching (variable confidence)
"""

from decimal import Decimal
from datetime import date, timedelta
from typing import List

from src_v2.models.bank import BankTransaction
from src_v2.models.invoice import Invoice


def generate_strategy1_data() -> tuple[List[BankTransaction], List[Invoice]]:
    """Strategy 1: Single invoice per customer.

    Customer has exactly ONE open invoice → 95% confidence
    """
    banks = [
        BankTransaction(
            id="B-S1-001",
            date=date(2024, 1, 15),
            amount=Decimal("1250.00"),
            description="Payment from Acme Corp",
            customer_id="CUST-001",  # Has only one invoice
        ),
        BankTransaction(
            id="B-S1-002",
            date=date(2024, 1, 16),
            amount=Decimal("3500.50"),
            description="Wire transfer",
            customer_id="CUST-002",  # Has only one invoice
        ),
        BankTransaction(
            id="B-S1-003",
            date=date(2024, 1, 17),
            amount=Decimal("890.00"),
            description="Payment",
            customer_id="CUST-003",  # Has only one invoice (partial payment)
        ),
    ]

    invoices = [
        Invoice(
            id="INV-S1-001",
            invoice_number="INV-2024-001",
            customer_id="CUST-001",
            amount=Decimal("1250.00"),
            pending_amount=Decimal("1250.00"),
            due_date=date(2024, 1, 31),
        ),
        Invoice(
            id="INV-S1-002",
            invoice_number="INV-2024-002",
            customer_id="CUST-002",
            amount=Decimal("3500.50"),
            pending_amount=Decimal("3500.50"),
            due_date=date(2024, 1, 31),
        ),
        Invoice(
            id="INV-S1-003",
            invoice_number="INV-2024-003",
            customer_id="CUST-003",
            amount=Decimal("2000.00"),
            pending_amount=Decimal("2000.00"),  # Larger than bank amount
            due_date=date(2024, 1, 31),
        ),
    ]

    return banks, invoices


def generate_strategy2_data() -> tuple[List[BankTransaction], List[Invoice]]:
    """Strategy 2: Unique amount match.

    Amount uniquely matches ONE invoice → 90% confidence (93% if customer matches)
    """
    banks = [
        BankTransaction(
            id="B-S2-001",
            amount=Decimal("4567.89"),  # Unique amount
            date=date(2024, 1, 15),
            description="Payment",
            customer_id=None,  # No customer info
        ),
        BankTransaction(
            id="B-S2-002",
            amount=Decimal("1999.99"),  # Unique amount with customer match
            date=date(2024, 1, 16),
            description="Payment from Beta Inc",
            customer_id="CUST-010",
        ),
        BankTransaction(
            id="B-S2-003",
            amount=Decimal("750.25"),  # Unique amount within tolerance
            date=date(2024, 1, 17),
            description="Wire",
            customer_id=None,
        ),
    ]

    invoices = [
        # Multiple invoices, but unique amounts
        Invoice(
            id="INV-S2-001",
            invoice_number="INV-2024-101",
            customer_id="CUST-005",
            amount=Decimal("4567.89"),  # Matches B-S2-001
            pending_amount=Decimal("4567.89"),
            due_date=date(2024, 2, 1),
        ),
        Invoice(
            id="INV-S2-002",
            invoice_number="INV-2024-102",
            customer_id="CUST-010",
            amount=Decimal("1999.99"),  # Matches B-S2-002
            pending_amount=Decimal("1999.99"),
            due_date=date(2024, 2, 1),
        ),
        Invoice(
            id="INV-S2-003",
            invoice_number="INV-2024-103",
            customer_id="CUST-007",
            amount=Decimal("752.00"),  # Close to 750.25 (within tolerance)
            pending_amount=Decimal("752.00"),
            due_date=date(2024, 2, 1),
        ),
        Invoice(
            id="INV-S2-004",
            invoice_number="INV-2024-104",
            customer_id="CUST-010",
            amount=Decimal("5000.00"),  # Different amount, same customer
            pending_amount=Decimal("5000.00"),
            due_date=date(2024, 2, 1),
        ),
    ]

    return banks, invoices


def generate_strategy3_data() -> tuple[List[BankTransaction], List[Invoice]]:
    """Strategy 3: Unique combination.

    Amount matches ONE unique combination of invoices → 85% confidence (88% if customer matches)
    """
    banks = [
        BankTransaction(
            id="B-S3-001",
            amount=Decimal("3500.00"),  # = 1500 + 2000 (unique combo)
            date=date(2024, 1, 15),
            description="Payment for multiple invoices",
            customer_id="CUST-020",
        ),
        BankTransaction(
            id="B-S3-002",
            amount=Decimal("2750.00"),  # = 1000 + 1750 (unique combo, no customer)
            date=date(2024, 1, 16),
            description="Bulk payment",
            customer_id=None,
        ),
        BankTransaction(
            id="B-S3-003",
            amount=Decimal("4250.00"),  # = 1500 + 1000 + 1750 (3 invoices)
            date=date(2024, 1, 17),
            description="Multiple invoices",
            customer_id="CUST-020",
        ),
    ]

    invoices = [
        # Customer 20 invoices
        Invoice(
            id="INV-S3-001",
            invoice_number="INV-2024-201",
            customer_id="CUST-020",
            amount=Decimal("1500.00"),
            pending_amount=Decimal("1500.00"),
            due_date=date(2024, 2, 1),
        ),
        Invoice(
            id="INV-S3-002",
            invoice_number="INV-2024-202",
            customer_id="CUST-020",
            amount=Decimal("2000.00"),
            pending_amount=Decimal("2000.00"),
            due_date=date(2024, 2, 1),
        ),
        Invoice(
            id="INV-S3-003",
            invoice_number="INV-2024-203",
            customer_id="CUST-020",
            amount=Decimal("1000.00"),
            pending_amount=Decimal("1000.00"),
            due_date=date(2024, 2, 1),
        ),
        # Different customer
        Invoice(
            id="INV-S3-004",
            invoice_number="INV-2024-204",
            customer_id="CUST-021",
            amount=Decimal("1750.00"),
            pending_amount=Decimal("1750.00"),
            due_date=date(2024, 2, 1),
        ),
    ]

    return banks, invoices


def generate_strategy4_data() -> tuple[List[BankTransaction], List[Invoice]]:
    """Strategy 4: Flow network matching.

    Complex many-to-many scenarios with varying confidence levels.
    """
    banks = [
        # High confidence matches (customer + amount)
        BankTransaction(
            id="B-S4-001",
            amount=Decimal("5000.00"),
            date=date(2024, 1, 15),
            description="Payment",
            customer_id="CUST-030",
        ),
        # Medium confidence (amount close, no customer)
        BankTransaction(
            id="B-S4-002",
            amount=Decimal("2500.00"),
            date=date(2024, 1, 16),
            description="Payment",
            customer_id=None,
        ),
        # Low confidence (poor amount match)
        BankTransaction(
            id="B-S4-003",
            amount=Decimal("1234.56"),
            date=date(2024, 1, 17),
            description="Payment",
            customer_id="CUST-031",
        ),
        # Partial payment scenario
        BankTransaction(
            id="B-S4-004",
            amount=Decimal("600.00"),
            date=date(2024, 1, 18),
            description="Partial payment",
            customer_id="CUST-032",
        ),
        # Multiple allocation scenario
        BankTransaction(
            id="B-S4-005",
            amount=Decimal("8000.00"),
            date=date(2024, 1, 19),
            description="Large payment",
            customer_id="CUST-033",
        ),
    ]

    invoices = [
        # Perfect match for B-S4-001 (high confidence)
        Invoice(
            id="INV-S4-001",
            invoice_number="INV-2024-301",
            customer_id="CUST-030",
            amount=Decimal("5000.00"),
            pending_amount=Decimal("5000.00"),
            due_date=date(2024, 2, 1),
        ),
        # Close match for B-S4-002 (medium confidence)
        Invoice(
            id="INV-S4-002",
            invoice_number="INV-2024-302",
            customer_id="CUST-035",
            amount=Decimal("2520.00"),  # Close to 2500
            pending_amount=Decimal("2520.00"),
            due_date=date(2024, 2, 1),
        ),
        # Poor match for B-S4-003 (low confidence)
        Invoice(
            id="INV-S4-003",
            invoice_number="INV-2024-303",
            customer_id="CUST-031",
            amount=Decimal("5678.90"),  # Very different amount
            pending_amount=Decimal("5678.90"),
            due_date=date(2024, 2, 1),
        ),
        # Partial payment scenario for B-S4-004
        Invoice(
            id="INV-S4-004",
            invoice_number="INV-2024-304",
            customer_id="CUST-032",
            amount=Decimal("2000.00"),  # Bank only pays 600
            pending_amount=Decimal("2000.00"),
            due_date=date(2024, 2, 1),
        ),
        # Multiple invoices for B-S4-005
        Invoice(
            id="INV-S4-005",
            invoice_number="INV-2024-305",
            customer_id="CUST-033",
            amount=Decimal("3000.00"),
            pending_amount=Decimal("3000.00"),
            due_date=date(2024, 2, 1),
        ),
        Invoice(
            id="INV-S4-006",
            invoice_number="INV-2024-306",
            customer_id="CUST-033",
            amount=Decimal("2500.00"),
            pending_amount=Decimal("2500.00"),
            due_date=date(2024, 2, 1),
        ),
        Invoice(
            id="INV-S4-007",
            invoice_number="INV-2024-307",
            customer_id="CUST-033",
            amount=Decimal("2500.00"),
            pending_amount=Decimal("2500.00"),
            due_date=date(2024, 2, 1),
        ),
    ]

    return banks, invoices


def generate_edge_cases() -> tuple[List[BankTransaction], List[Invoice]]:
    """Edge cases and challenging scenarios."""
    banks = [
        # No customer ID, ambiguous amount
        BankTransaction(
            id="B-EDGE-001",
            amount=Decimal("1000.00"),  # Multiple invoices have this amount
            date=date(2024, 1, 15),
            description="Payment",
            customer_id=None,
        ),
        # Customer ID but no matching invoices
        BankTransaction(
            id="B-EDGE-002",
            amount=Decimal("999.99"),
            date=date(2024, 1, 16),
            description="Payment",
            customer_id="CUST-NONEXISTENT",
        ),
        # Very poor confidence - should go to manual
        BankTransaction(
            id="B-EDGE-003",
            amount=Decimal("123.45"),
            date=date(2024, 1, 17),
            description="Small payment",
            customer_id=None,
        ),
        # Below reject threshold - should use reject edge
        BankTransaction(
            id="B-EDGE-004",
            amount=Decimal("50000.00"),  # Way larger than any invoice
            date=date(2024, 1, 18),
            description="Large mismatched payment",
            customer_id="CUST-040",
        ),
        # Exact tie - two equally good matches
        BankTransaction(
            id="B-EDGE-005",
            amount=Decimal("2222.22"),
            date=date(2024, 1, 19),
            description="Payment",
            customer_id=None,
        ),
    ]

    invoices = [
        # Multiple $1000 invoices (ambiguous for B-EDGE-001)
        Invoice(
            id="INV-EDGE-001",
            invoice_number="INV-2024-401",
            customer_id="CUST-040",
            amount=Decimal("1000.00"),
            pending_amount=Decimal("1000.00"),
            due_date=date(2024, 2, 1),
        ),
        Invoice(
            id="INV-EDGE-002",
            invoice_number="INV-2024-402",
            customer_id="CUST-041",
            amount=Decimal("1000.00"),
            pending_amount=Decimal("1000.00"),
            due_date=date(2024, 2, 1),
        ),
        Invoice(
            id="INV-EDGE-003",
            invoice_number="INV-2024-403",
            customer_id="CUST-042",
            amount=Decimal("1000.00"),
            pending_amount=Decimal("1000.00"),
            due_date=date(2024, 2, 1),
        ),
        # Small invoices (poor match for large amounts)
        Invoice(
            id="INV-EDGE-004",
            invoice_number="INV-2024-404",
            customer_id="CUST-040",
            amount=Decimal("100.00"),
            pending_amount=Decimal("100.00"),
            due_date=date(2024, 2, 1),
        ),
        # Exact tie scenario (same amount, different customers)
        Invoice(
            id="INV-EDGE-005",
            invoice_number="INV-2024-405",
            customer_id="CUST-043",
            amount=Decimal("2222.22"),
            pending_amount=Decimal("2222.22"),
            due_date=date(2024, 2, 1),
        ),
        Invoice(
            id="INV-EDGE-006",
            invoice_number="INV-2024-406",
            customer_id="CUST-044",
            amount=Decimal("2222.22"),
            pending_amount=Decimal("2222.22"),
            due_date=date(2024, 2, 1),
        ),
    ]

    return banks, invoices


def generate_comprehensive_test_data() -> tuple[List[BankTransaction], List[Invoice]]:
    """Generate comprehensive test dataset covering all scenarios."""
    all_banks = []
    all_invoices = []

    # Strategy 1 data
    banks, invoices = generate_strategy1_data()
    all_banks.extend(banks)
    all_invoices.extend(invoices)

    # Strategy 2 data
    banks, invoices = generate_strategy2_data()
    all_banks.extend(banks)
    all_invoices.extend(invoices)

    # Strategy 3 data
    banks, invoices = generate_strategy3_data()
    all_banks.extend(banks)
    all_invoices.extend(invoices)

    # Strategy 4 data
    banks, invoices = generate_strategy4_data()
    all_banks.extend(banks)
    all_invoices.extend(invoices)

    # Edge cases
    banks, invoices = generate_edge_cases()
    all_banks.extend(banks)
    all_invoices.extend(invoices)

    return all_banks, all_invoices


if __name__ == "__main__":
    """Print summary of test data."""

    print("=" * 70)
    print("PHASE 3 TEST DATA SUMMARY")
    print("=" * 70)

    print("\n📊 STRATEGY 1: Single Invoice Per Customer (95% confidence)")
    print("-" * 70)
    banks, invoices = generate_strategy1_data()
    print(f"Banks: {len(banks)}")
    for b in banks:
        print(f"  {b.id}: ${b.amount} (customer: {b.customer_id})")
    print(f"Invoices: {len(invoices)}")
    for inv in invoices:
        print(f"  {inv.invoice_number}: ${inv.pending_amount} (customer: {inv.customer_id})")

    print("\n📊 STRATEGY 2: Unique Amount Match (90% confidence)")
    print("-" * 70)
    banks, invoices = generate_strategy2_data()
    print(f"Banks: {len(banks)}")
    for b in banks:
        print(f"  {b.id}: ${b.amount} (customer: {b.customer_id or 'None'})")
    print(f"Invoices: {len(invoices)}")
    for inv in invoices:
        print(f"  {inv.invoice_number}: ${inv.pending_amount} (customer: {inv.customer_id})")

    print("\n📊 STRATEGY 3: Unique Combination (85% confidence)")
    print("-" * 70)
    banks, invoices = generate_strategy3_data()
    print(f"Banks: {len(banks)}")
    for b in banks:
        print(f"  {b.id}: ${b.amount} (customer: {b.customer_id or 'None'})")
    print(f"Invoices: {len(invoices)}")
    for inv in invoices:
        print(f"  {inv.invoice_number}: ${inv.pending_amount} (customer: {inv.customer_id})")

    print("\n📊 STRATEGY 4: Flow Network Matching (variable confidence)")
    print("-" * 70)
    banks, invoices = generate_strategy4_data()
    print(f"Banks: {len(banks)}")
    for b in banks:
        print(f"  {b.id}: ${b.amount} (customer: {b.customer_id or 'None'})")
    print(f"Invoices: {len(invoices)}")
    for inv in invoices:
        print(f"  {inv.invoice_number}: ${inv.pending_amount} (customer: {inv.customer_id})")

    print("\n📊 EDGE CASES")
    print("-" * 70)
    banks, invoices = generate_edge_cases()
    print(f"Banks: {len(banks)}")
    for b in banks:
        print(f"  {b.id}: ${b.amount} (customer: {b.customer_id or 'None'})")
    print(f"Invoices: {len(invoices)}")
    for inv in invoices:
        print(f"  {inv.invoice_number}: ${inv.pending_amount} (customer: {inv.customer_id})")

    print("\n" + "=" * 70)
    all_banks, all_invoices = generate_comprehensive_test_data()
    print(f"TOTAL: {len(all_banks)} banks, {len(all_invoices)} invoices")
    print("=" * 70)
