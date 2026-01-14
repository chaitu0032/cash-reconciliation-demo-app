"""
Example usage of the Cash Reconciliation Platform - Phase 1

Demonstrates deterministic matching rules with sample data.
"""
from datetime import date
from decimal import Decimal

from models import (
    BankTransaction,
    Remittance,
    RemittanceLineItem,
    Invoice,
    Customer,
    InvoiceStatus,
)
from reconciler import Reconciler


def create_sample_data():
    """Create sample data demonstrating various matching scenarios."""

    # Customers
    customers = [
        Customer(
            customer_id="CUST-001",
            name="Acme Corp",
            aliases=["ACME", "Acme Corporation"],
            payment_ref_patterns=["PAY-AC-*"],
            account_numbers=["90001234"],
        ),
        Customer(
            customer_id="CUST-002",
            name="Beta LLC",
            aliases=["Beta", "Beta Co"],
            payment_ref_patterns=["BT-*"],
            account_numbers=["90005678"],
        ),
        Customer(
            customer_id="CUST-003",
            name="Gamma Industries",
            aliases=["Gamma"],
        ),
    ]

    # Invoices
    invoices = [
        # Acme Corp invoices
        Invoice(
            invoice_id="INV-2024-001",
            customer_id="CUST-001",
            due_date=date(2024, 1, 15),
            amount=Decimal("5000.00"),
            pending_amount=Decimal("5000.00"),
            status=InvoiceStatus.OPEN,
        ),
        Invoice(
            invoice_id="INV-2024-002",
            customer_id="CUST-001",
            due_date=date(2024, 1, 20),
            amount=Decimal("3000.00"),
            pending_amount=Decimal("3000.00"),
            status=InvoiceStatus.OPEN,
        ),
        Invoice(
            invoice_id="INV-2024-003",
            customer_id="CUST-001",
            due_date=date(2024, 1, 25),
            amount=Decimal("2000.00"),
            pending_amount=Decimal("2000.00"),
            status=InvoiceStatus.CLOSED,  # Already paid
        ),
        # Beta LLC invoices
        Invoice(
            invoice_id="INV-2024-010",
            customer_id="CUST-002",
            due_date=date(2024, 1, 18),
            amount=Decimal("7500.00"),
            pending_amount=Decimal("7500.00"),
            status=InvoiceStatus.OPEN,
        ),
        Invoice(
            invoice_id="INV-2024-011",
            customer_id="CUST-002",
            due_date=date(2024, 1, 22),
            amount=Decimal("4000.00"),
            pending_amount=Decimal("4000.00"),
            status=InvoiceStatus.OPEN,
        ),
        # Gamma Industries invoices
        Invoice(
            invoice_id="INV-2024-020",
            customer_id="CUST-003",
            due_date=date(2024, 1, 30),
            amount=Decimal("10000.00"),
            pending_amount=Decimal("10000.00"),
            status=InvoiceStatus.OPEN,
        ),
    ]

    # Remittances
    remittances = [
        # Scenario 1: Rule 1.1 - Exact Reference + Exact Amount
        Remittance(
            id="REM-001",
            customer_id="CUST-001",
            customer_name="Acme Corp",
            customer_address="123 Main St",
            payment_reference="PAY-AC-7890",
            payment_date=date(2024, 1, 14),
            line_items=[
                RemittanceLineItem(
                    invoice_number="INV-2024-001",
                    description="Payment for January invoice",
                    payment_method="Wire",
                    amount=Decimal("5000.00"),
                ),
            ],
        ),
        # Scenario 2: Rule 1.2 - Exact Reference + Tolerance (bank fee deducted)
        Remittance(
            id="REM-002",
            customer_id="CUST-001",
            customer_name="Acme Corp",
            customer_address="123 Main St",
            payment_reference="PAY-AC-7891",
            payment_date=date(2024, 1, 19),
            line_items=[
                RemittanceLineItem(
                    invoice_number="INV-2024-002",
                    description="Payment for second invoice",
                    payment_method="Wire",
                    amount=Decimal("3000.00"),
                ),
            ],
        ),
        # Scenario 3: Rule 1.3 - Fuzzy Reference (different format)
        Remittance(
            id="REM-003",
            customer_id="CUST-002",
            customer_name="Beta LLC",
            customer_address="456 Oak Ave",
            payment_reference="BT-00012345",  # Has leading zeros
            payment_date=date(2024, 1, 17),
            line_items=[
                RemittanceLineItem(
                    invoice_number="INV-2024-010",
                    description="Beta payment",
                    payment_method="ACH",
                    amount=Decimal("7500.00"),
                ),
            ],
        ),
        # Scenario 4: Rule 1.5 - Reference in description
        Remittance(
            id="REM-004",
            customer_id="CUST-002",
            customer_name="Beta LLC",
            customer_address="456 Oak Ave",
            payment_reference="BT-54321",
            payment_date=date(2024, 1, 21),
            line_items=[
                RemittanceLineItem(
                    invoice_number="INV-2024-011",
                    description="Second Beta payment",
                    payment_method="Check",
                    amount=Decimal("4000.00"),
                ),
            ],
        ),
        # Scenario 5: Exception E004 - Duplicate payment
        Remittance(
            id="REM-005",
            customer_id="CUST-001",
            customer_name="Acme Corp",
            customer_address="123 Main St",
            payment_reference="PAY-AC-7892",
            payment_date=date(2024, 1, 24),
            line_items=[
                RemittanceLineItem(
                    invoice_number="INV-2024-003",  # Already closed!
                    description="Duplicate payment attempt",
                    payment_method="Wire",
                    amount=Decimal("2000.00"),
                ),
            ],
        ),
        # Scenario 6: Exception E005 - Invalid invoice
        Remittance(
            id="REM-006",
            customer_id="CUST-003",
            customer_name="Gamma Industries",
            customer_address="789 Pine Rd",
            payment_reference="GAM-001",
            payment_date=date(2024, 1, 28),
            line_items=[
                RemittanceLineItem(
                    invoice_number="INV-9999-999",  # Does not exist
                    description="Payment for non-existent invoice",
                    payment_method="Wire",
                    amount=Decimal("1000.00"),
                ),
            ],
        ),
        # Scenario 7: Rule 2.2 - Partial payment
        Remittance(
            id="REM-007",
            customer_id="CUST-003",
            customer_name="Gamma Industries",
            customer_address="789 Pine Rd",
            payment_reference="GAM-002",
            payment_date=date(2024, 1, 29),
            line_items=[
                RemittanceLineItem(
                    invoice_number="INV-2024-020",
                    description="Partial payment",
                    payment_method="Wire",
                    amount=Decimal("6000.00"),  # $6000 of $10000
                ),
            ],
        ),
    ]

    # Bank Transactions
    bank_transactions = [
        # Matches REM-001 via Rule 1.1 (exact reference + exact amount)
        BankTransaction(
            id="BANK-001",
            amount=Decimal("5000.00"),
            date=date(2024, 1, 14),
            reference="PAY-AC-7890",
            description="ACME CORP WIRE TRANSFER",
        ),
        # Matches REM-002 via Rule 1.2 (exact reference + tolerance)
        BankTransaction(
            id="BANK-002",
            amount=Decimal("2999.50"),  # $0.50 less due to bank fee
            date=date(2024, 1, 19),
            reference="PAY-AC-7891",
            description="ACME CORP PAYMENT",
        ),
        # Matches REM-003 via Rule 1.3 (fuzzy reference - no leading zeros)
        BankTransaction(
            id="BANK-003",
            amount=Decimal("7500.00"),
            date=date(2024, 1, 17),
            reference="BT12345",  # Without leading zeros
            description="BETA LLC ACH",
        ),
        # Matches REM-004 via Rule 1.5 (reference in description)
        BankTransaction(
            id="BANK-004",
            amount=Decimal("4000.00"),
            date=date(2024, 1, 21),
            reference="CHK-98765",  # Different reference
            description="BETA LLC CHECK BT-54321 DEPOSIT",  # Remittance ref in desc
        ),
        # Matches REM-005 (will trigger E004 at Level 2)
        BankTransaction(
            id="BANK-005",
            amount=Decimal("2000.00"),
            date=date(2024, 1, 24),
            reference="PAY-AC-7892",
            description="ACME CORP DUPLICATE",
        ),
        # Matches REM-006 (will trigger E005 at Level 2)
        BankTransaction(
            id="BANK-006",
            amount=Decimal("1000.00"),
            date=date(2024, 1, 28),
            reference="GAM-001",
            description="GAMMA INDUSTRIES PAYMENT",
        ),
        # Matches REM-007 (partial payment - Rule 2.2)
        BankTransaction(
            id="BANK-007",
            amount=Decimal("6000.00"),
            date=date(2024, 1, 29),
            reference="GAM-002",
            description="GAMMA PARTIAL PAYMENT",
        ),
        # Unmatched bank transaction (no remittance)
        BankTransaction(
            id="BANK-008",
            amount=Decimal("999.00"),
            date=date(2024, 1, 30),
            reference="UNKNOWN-123",
            description="WIRE TRANSFER",
        ),
    ]

    return customers, invoices, remittances, bank_transactions


def main():
    """Run the reconciliation example."""
    print("Cash Reconciliation Platform - Phase 1 Demo")
    print("=" * 60)

    # Create sample data
    customers, invoices, remittances, bank_transactions = create_sample_data()

    # Initialize reconciler
    reconciler = Reconciler(
        bank_transactions=bank_transactions,
        remittances=remittances,
        invoices=invoices,
        customers=customers,
    )

    # Run reconciliation
    results = reconciler.run()

    # Print detailed results
    print("\nDETAILED RESULTS")
    print("-" * 60)

    for result in results:
        bank = result.bank_transaction
        print(f"\nBank Transaction: {bank.id}")
        print(f"  Amount: ${bank.amount}")
        print(f"  Reference: {bank.reference}")
        print(f"  Description: {bank.description}")

        if result.level1_match:
            l1 = result.level1_match
            print(f"\n  Level 1 Match:")
            print(f"    Outcome: {l1.result.outcome.value}")
            print(f"    Confidence: {l1.result.confidence}%")
            print(f"    Rule: {l1.result.rule_applied}")
            if l1.remittance_id:
                print(f"    Matched Remittance: {l1.remittance_id}")
            if l1.result.exception_code:
                print(f"    Exception: {l1.result.exception_code.name} - {l1.result.exception_code.value}")
            if l1.result.exception_detail:
                print(f"    Detail: {l1.result.exception_detail}")

        if result.level2_matches:
            print(f"\n  Level 2 Matches:")
            for l2 in result.level2_matches:
                print(f"    Line {l2.remittance_line_index}:")
                print(f"      Outcome: {l2.result.outcome.value}")
                print(f"      Confidence: {l2.result.confidence}%")
                print(f"      Rule: {l2.result.rule_applied}")
                if l2.invoice_id:
                    print(f"      Invoice: {l2.invoice_id}")
                if l2.result.exception_code:
                    print(f"      Exception: {l2.result.exception_code.name} - {l2.result.exception_code.value}")
                if l2.result.exception_detail:
                    print(f"      Detail: {l2.result.exception_detail}")

        print(f"\n  Fully Reconciled: {'Yes' if result.fully_reconciled else 'No'}")
        print("-" * 60)

    # Print summary
    reconciler.print_summary()


if __name__ == "__main__":
    main()
