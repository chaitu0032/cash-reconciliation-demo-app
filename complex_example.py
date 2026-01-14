"""
Complex Example - Cash Reconciliation Platform

Comprehensive test with:
- 150 bank statements
- 120 remittances (170 line items)
- 200 invoices
- 10 customers

Tests all matching rules and exception scenarios.
"""
import random
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from models import (
    BankTransaction,
    Remittance,
    RemittanceLineItem,
    Invoice,
    Customer,
    InvoiceStatus,
    RemittanceSource,
)
from reconciler import Reconciler


# Seed for reproducibility
random.seed(42)


def create_customers() -> list[Customer]:
    """Create 10 test customers with various configurations."""
    return [
        Customer(
            customer_id="CUST-001",
            name="Acme Corporation",
            aliases=["ACME", "Acme Corp", "ACME CORP"],
            address="123 Main Street, New York, NY 10001",
            payment_ref_patterns=["PAY-AC-*", "ACME-*"],
            account_numbers=["90001001", "AC001"],
        ),
        Customer(
            customer_id="CUST-002",
            name="Beta Technologies",
            aliases=["Beta Tech", "BETA", "BT Inc"],
            address="456 Tech Park, San Francisco, CA 94102",
            payment_ref_patterns=["BT-*", "BETA-*"],
            account_numbers=["90002002", "BT002"],
        ),
        Customer(
            customer_id="CUST-003",
            name="Gamma Industries",
            aliases=["Gamma Ind", "GAMMA", "Gamma Inc"],
            address="789 Industrial Ave, Chicago, IL 60601",
            payment_ref_patterns=["GAM-*", "GAMMA-*"],
            account_numbers=["90003003"],
        ),
        Customer(
            customer_id="CUST-004",
            name="Delta Services LLC",
            aliases=["Delta", "Delta Svc", "DELTA"],
            address="321 Service Road, Houston, TX 77001",
            payment_ref_patterns=["DEL-*", "DELTA-*"],
            account_numbers=["90004004"],
        ),
        Customer(
            customer_id="CUST-005",
            name="Epsilon Group",
            aliases=["Epsilon", "EPS", "Epsilon Inc"],
            address="654 Corporate Blvd, Phoenix, AZ 85001",
            payment_ref_patterns=["EPS-*", "EPSILON-*"],
            account_numbers=["90005005"],
        ),
        Customer(
            customer_id="CUST-006",
            name="Zeta Holdings",
            aliases=["Zeta", "ZH", "Zeta Corp"],
            address="987 Holdings Way, Philadelphia, PA 19101",
            payment_ref_patterns=["ZET-*", "ZETA-*"],
            account_numbers=["90006006"],
        ),
        Customer(
            customer_id="CUST-007",
            name="Theta Partners",
            aliases=["Theta", "TP", "Theta Inc"],
            address="147 Partner Lane, San Antonio, TX 78201",
            payment_ref_patterns=["THE-*", "THETA-*"],
            account_numbers=["90007007"],
        ),
        Customer(
            customer_id="CUST-008",
            name="Iota Corp",
            aliases=["Iota", "IOTA"],
            address="258 Corp Street, San Diego, CA 92101",
            payment_ref_patterns=["IOT-*"],
            account_numbers=["90008008"],
        ),
        Customer(
            customer_id="CUST-009",
            name="Kappa Ltd",
            aliases=["Kappa", "K Ltd", "KAPPA"],
            address="369 Ltd Avenue, Dallas, TX 75201",
            payment_ref_patterns=["KAP-*", "KAPPA-*"],
            account_numbers=["90009009"],
        ),
        Customer(
            customer_id="CUST-010",
            name="Lambda Inc",
            aliases=["Lambda", "LAMBDA"],
            address="741 Inc Road, San Jose, CA 95101",
            payment_ref_patterns=["LAM-*", "LAMBDA-*"],
            account_numbers=["90010010"],
        ),
    ]


def create_invoices(customers: list[Customer]) -> list[Invoice]:
    """
    Create 200 invoices distributed across customers.

    Distribution:
    - 140 Standard Open (for actual remittances)
    - 15 Partial Status (for partial payment testing)
    - 15 Closed (for E004 duplicate payment testing)
    - 25 Virtual remittance targets
    - 5 True orphan invoices
    """
    invoices = []
    base_date = date(2024, 1, 1)
    invoice_idx = 0

    # Distribute invoices across customers
    invoices_per_customer = {
        "CUST-001": 30,  # High volume
        "CUST-002": 25,
        "CUST-003": 25,
        "CUST-004": 20,
        "CUST-005": 20,
        "CUST-006": 20,
        "CUST-007": 20,
        "CUST-008": 15,
        "CUST-009": 15,
        "CUST-010": 10,
    }

    for customer in customers:
        count = invoices_per_customer.get(customer.customer_id, 10)

        for i in range(count):
            invoice_idx += 1
            amount = Decimal(str(random.randint(500, 50000)))
            due_date = base_date + timedelta(days=random.randint(1, 90))

            # Determine status
            if invoice_idx <= 140:
                status = InvoiceStatus.OPEN
                pending = amount
            elif invoice_idx <= 155:
                status = InvoiceStatus.PARTIAL
                pending = amount * Decimal("0.5")  # 50% remaining
            elif invoice_idx <= 170:
                status = InvoiceStatus.CLOSED
                pending = Decimal("0")
            else:
                # Remaining for virtual remittances and orphans
                status = InvoiceStatus.OPEN
                pending = amount

            invoices.append(Invoice(
                invoice_id=f"INV-2024-{invoice_idx:03d}",
                customer_id=customer.customer_id,
                due_date=due_date,
                amount=amount,
                pending_amount=pending,
                status=status,
            ))

    return invoices


def create_remittances(
    customers: list[Customer],
    invoices: list[Invoice],
) -> list[Remittance]:
    """
    Create 120 remittances with 170 line items total.

    Distribution:
    - 80 single-line remittances (80 lines)
    - 25 two-line remittances (50 lines)
    - 10 three-line remittances (30 lines)
    - 5 four+ line remittances (10 lines)
    """
    remittances = []
    base_date = date(2024, 1, 1)

    # Get open/partial invoices (excluding closed and those reserved for virtual remittances)
    # We need at least 170 line items, so get plenty of invoices
    available_invoices = [inv for inv in invoices if inv.status != InvoiceStatus.CLOSED]

    # Track used invoices
    invoice_queue = list(available_invoices)
    random.shuffle(invoice_queue)

    remittance_idx = 0

    # Single-line remittances (80)
    for i in range(80):
        if not invoice_queue:
            break

        remittance_idx += 1
        inv = invoice_queue.pop(0)
        customer = next(c for c in customers if c.customer_id == inv.customer_id)

        # Vary the payment reference format
        ref_formats = [
            f"PAY-{customer.customer_id[-3:]}-{remittance_idx:04d}",
            f"{customer.aliases[0].upper()[:3]}-{remittance_idx:04d}",
            f"REM-{remittance_idx:04d}",
        ]
        payment_ref = random.choice(ref_formats)

        remittances.append(Remittance(
            id=f"REM-{remittance_idx:03d}",
            customer_id=inv.customer_id,
            customer_name=customer.name,
            customer_address=customer.address,
            payment_reference=payment_ref,
            payment_date=base_date + timedelta(days=random.randint(1, 60)),
            line_items=[
                RemittanceLineItem(
                    invoice_number=inv.invoice_id,
                    description=f"Payment for {inv.invoice_id}",
                    payment_method=random.choice(["Wire", "ACH", "Check"]),
                    amount=inv.pending_amount,
                )
            ],
            source=RemittanceSource.ACTUAL,
        ))

    # Two-line remittances (25)
    for i in range(25):
        if len(invoice_queue) < 2:
            break

        remittance_idx += 1
        inv1 = invoice_queue.pop(0)
        # Find another invoice from same customer
        same_customer_inv = next(
            (inv for inv in invoice_queue if inv.customer_id == inv1.customer_id),
            None
        )
        if same_customer_inv:
            invoice_queue.remove(same_customer_inv)
            inv2 = same_customer_inv
        else:
            inv2 = invoice_queue.pop(0)

        customer = next(c for c in customers if c.customer_id == inv1.customer_id)
        payment_ref = f"PAY-{customer.customer_id[-3:]}-{remittance_idx:04d}"

        remittances.append(Remittance(
            id=f"REM-{remittance_idx:03d}",
            customer_id=inv1.customer_id,
            customer_name=customer.name,
            customer_address=customer.address,
            payment_reference=payment_ref,
            payment_date=base_date + timedelta(days=random.randint(1, 60)),
            line_items=[
                RemittanceLineItem(
                    invoice_number=inv1.invoice_id,
                    description=f"Payment for {inv1.invoice_id}",
                    payment_method="Wire",
                    amount=inv1.pending_amount,
                ),
                RemittanceLineItem(
                    invoice_number=inv2.invoice_id,
                    description=f"Payment for {inv2.invoice_id}",
                    payment_method="Wire",
                    amount=inv2.pending_amount,
                ),
            ],
            source=RemittanceSource.ACTUAL,
        ))

    # Three-line remittances (10)
    for i in range(10):
        if len(invoice_queue) < 3:
            break

        remittance_idx += 1
        invs = [invoice_queue.pop(0) for _ in range(3)]
        customer = next(c for c in customers if c.customer_id == invs[0].customer_id)
        payment_ref = f"PAY-{customer.customer_id[-3:]}-{remittance_idx:04d}"

        line_items = [
            RemittanceLineItem(
                invoice_number=inv.invoice_id,
                description=f"Payment for {inv.invoice_id}",
                payment_method="ACH",
                amount=inv.pending_amount,
            )
            for inv in invs
        ]

        remittances.append(Remittance(
            id=f"REM-{remittance_idx:03d}",
            customer_id=invs[0].customer_id,
            customer_name=customer.name,
            customer_address=customer.address,
            payment_reference=payment_ref,
            payment_date=base_date + timedelta(days=random.randint(1, 60)),
            line_items=line_items,
            source=RemittanceSource.ACTUAL,
        ))

    # Four+ line remittances (5)
    for i in range(5):
        if len(invoice_queue) < 2:
            break

        remittance_idx += 1
        num_lines = min(random.randint(2, 4), len(invoice_queue))
        invs = [invoice_queue.pop(0) for _ in range(num_lines)]
        if not invs:
            break

        customer = next(c for c in customers if c.customer_id == invs[0].customer_id)
        payment_ref = f"PAY-{customer.customer_id[-3:]}-{remittance_idx:04d}"

        line_items = [
            RemittanceLineItem(
                invoice_number=inv.invoice_id,
                description=f"Payment for {inv.invoice_id}",
                payment_method="Wire",
                amount=inv.pending_amount,
            )
            for inv in invs
        ]

        remittances.append(Remittance(
            id=f"REM-{remittance_idx:03d}",
            customer_id=invs[0].customer_id,
            customer_name=customer.name,
            customer_address=customer.address,
            payment_reference=payment_ref,
            payment_date=base_date + timedelta(days=random.randint(1, 60)),
            line_items=line_items,
            source=RemittanceSource.ACTUAL,
        ))

    # Fill remaining to reach 120 remittances with single-line items
    while len(remittances) < 120 and invoice_queue:
        remittance_idx += 1
        inv = invoice_queue.pop(0)
        customer = next(c for c in customers if c.customer_id == inv.customer_id)
        payment_ref = f"PAY-{customer.customer_id[-3:]}-{remittance_idx:04d}"

        remittances.append(Remittance(
            id=f"REM-{remittance_idx:03d}",
            customer_id=inv.customer_id,
            customer_name=customer.name,
            customer_address=customer.address,
            payment_reference=payment_ref,
            payment_date=base_date + timedelta(days=random.randint(1, 60)),
            line_items=[
                RemittanceLineItem(
                    invoice_number=inv.invoice_id,
                    description=f"Payment for {inv.invoice_id}",
                    payment_method=random.choice(["Wire", "ACH", "Check"]),
                    amount=inv.pending_amount,
                )
            ],
            source=RemittanceSource.ACTUAL,
        ))

    return remittances


def inject_exceptions(
    remittances: list[Remittance],
    invoices: list[Invoice],
    customers: list[Customer],
) -> list[Remittance]:
    """
    Inject exception scenarios into remittances.

    Exceptions:
    - E002: Overpayment (5 cases)
    - E004: Duplicate payment - already handled by closed invoices
    - E005: Invalid invoice (5 cases)
    - E011: Wrong customer (5 cases)
    """
    # E002: Overpayment - modify 5 line items to have higher amounts
    for i, rem in enumerate(remittances[:5]):
        if rem.line_items:
            original_amount = rem.line_items[0].amount
            rem.line_items[0].amount = original_amount + Decimal("500.00")

    # E004: Duplicate payment - change 5 remittances to reference closed invoices
    closed_invoices = [inv for inv in invoices if inv.status == InvoiceStatus.CLOSED]
    for i, rem in enumerate(remittances[5:10]):
        if closed_invoices and rem.line_items:
            closed_inv = closed_invoices[i % len(closed_invoices)]
            rem.line_items[0].invoice_number = closed_inv.invoice_id

    # E005: Invalid invoice - change 5 remittances to reference non-existent invoices
    for i, rem in enumerate(remittances[10:15]):
        if rem.line_items:
            rem.line_items[0].invoice_number = f"INV-9999-{i:03d}"

    # E011: Wrong customer - change 5 remittances to have mismatched customer
    for i, rem in enumerate(remittances[15:20]):
        if rem.line_items:
            # Find an invoice from a different customer
            other_customer = customers[(i + 1) % len(customers)]
            other_inv = next(
                (inv for inv in invoices
                 if inv.customer_id == other_customer.customer_id
                 and inv.status == InvoiceStatus.OPEN),
                None
            )
            if other_inv:
                rem.line_items[0].invoice_number = other_inv.invoice_id

    return remittances


def create_bank_transactions(
    remittances: list[Remittance],
    invoices: list[Invoice],
    customers: list[Customer],
) -> list[BankTransaction]:
    """
    Create 150 bank transactions.

    Distribution:
    - 40: Rule 1.1 - Exact Reference + Exact Amount
    - 25: Rule 1.2 - Exact Reference + Tolerance
    - 30: Rule 1.3 - Fuzzy Reference
    - 22: Rule 1.5 - Description Contains Reference
    - 3: E006 - Multiple matches (ambiguous)
    - 25: Virtual remittance (bank description with invoice refs)
    - 5: E007 - True orphan (unparseable)
    """
    bank_transactions = []
    base_date = date(2024, 1, 1)
    bank_idx = 0

    num_remittances = len(remittances)

    # Rule 1.1: Exact Reference + Exact Amount (40)
    rule_1_1_end = min(40, num_remittances)
    for rem in remittances[:rule_1_1_end]:
        bank_idx += 1
        bank_transactions.append(BankTransaction(
            id=f"BANK-{bank_idx:03d}",
            amount=rem.total_amount,
            date=rem.payment_date,
            reference=rem.payment_reference,
            description=f"{rem.customer_name} PAYMENT",
        ))

    # Rule 1.2: Exact Reference + Tolerance (25)
    rule_1_2_end = min(65, num_remittances)
    for rem in remittances[rule_1_1_end:rule_1_2_end]:
        bank_idx += 1
        # Apply small tolerance (bank fees)
        tolerance = Decimal(str(random.uniform(0.01, 0.99)))
        if random.choice([True, False]):
            amount = rem.total_amount - tolerance
        else:
            amount = rem.total_amount + tolerance

        bank_transactions.append(BankTransaction(
            id=f"BANK-{bank_idx:03d}",
            amount=amount.quantize(Decimal("0.01")),
            date=rem.payment_date,
            reference=rem.payment_reference,
            description=f"{rem.customer_name} WIRE TRANSFER",
        ))

    # Rule 1.3: Fuzzy Reference (30)
    rule_1_3_end = min(95, num_remittances)
    for rem in remittances[rule_1_2_end:rule_1_3_end]:
        bank_idx += 1
        # Create fuzzy reference variations
        variations = [
            rem.payment_reference.replace("-", ""),  # Remove dashes
            f"00{rem.payment_reference}",  # Add leading zeros
            rem.payment_reference.lower(),  # Lowercase
            rem.payment_reference.replace("PAY", "PMT"),  # Different prefix
        ]
        fuzzy_ref = random.choice(variations)

        bank_transactions.append(BankTransaction(
            id=f"BANK-{bank_idx:03d}",
            amount=rem.total_amount,
            date=rem.payment_date,
            reference=fuzzy_ref,
            description=f"{rem.customer_name} ACH",
        ))

    # Rule 1.5: Description Contains Reference (remaining remittances)
    rule_1_5_end = num_remittances
    for rem in remittances[rule_1_3_end:rule_1_5_end]:
        bank_idx += 1
        bank_transactions.append(BankTransaction(
            id=f"BANK-{bank_idx:03d}",
            amount=rem.total_amount,
            date=rem.payment_date,
            reference=f"TXN-{bank_idx:06d}",  # Different reference
            description=f"{rem.customer_name} PAYMENT REF:{rem.payment_reference}",
        ))

    # E006: Multiple matches - ambiguous (3)
    # Create 3 bank txns that could match multiple remittances
    for i in range(3):
        bank_idx += 1
        # Use first few remittances for ambiguity testing
        rem = remittances[i]
        bank_transactions.append(BankTransaction(
            id=f"BANK-{bank_idx:03d}",
            amount=rem.total_amount,
            date=rem.payment_date,
            reference=f"AMBIG-{i:03d}",
            description=f"PAYMENT {rem.payment_reference} {remittances[i+1].payment_reference}",
        ))

    # Virtual remittance targets (25) - bank with parseable description
    virtual_invoices = [inv for inv in invoices if inv.status == InvoiceStatus.OPEN][150:175]
    for i, inv in enumerate(virtual_invoices):
        bank_idx += 1
        customer = next(c for c in customers if c.customer_id == inv.customer_id)

        # Create parseable descriptions
        desc_formats = [
            f"{customer.name} {inv.invoice_id} ${inv.pending_amount}",
            f"PAYMENT FROM {customer.aliases[0]} FOR INVOICE {inv.invoice_id}",
            f"A/C:{customer.account_numbers[0]} {inv.invoice_id}",
            f"{customer.name} INV:{inv.invoice_id.replace('INV-', '')}",
        ]

        bank_transactions.append(BankTransaction(
            id=f"BANK-{bank_idx:03d}",
            amount=inv.pending_amount,
            date=base_date + timedelta(days=random.randint(1, 60)),
            reference=f"VIR-{bank_idx:06d}",
            description=random.choice(desc_formats),
        ))

    # E007: True orphan - unparseable (fill remaining to 150)
    orphan_descriptions = [
        "WIRE TRANSFER",
        "MISC PAYMENT",
        "BANK FEE REVERSAL",
        "DEPOSIT",
        "TRANSFER FROM UNKNOWN",
        "SUNDRY CREDIT",
        "CASH DEPOSIT",
        "UNKNOWN SENDER",
        "REVERSAL",
        "CREDIT MEMO",
    ]
    while len(bank_transactions) < 150:
        bank_idx += 1
        desc = orphan_descriptions[(bank_idx - 1) % len(orphan_descriptions)]
        bank_transactions.append(BankTransaction(
            id=f"BANK-{bank_idx:03d}",
            amount=Decimal(str(random.randint(100, 5000))),
            date=base_date + timedelta(days=random.randint(1, 60)),
            reference=f"UNK-{bank_idx:06d}",
            description=desc,
        ))

    return bank_transactions


def validate_test_data(
    customers: list[Customer],
    invoices: list[Invoice],
    remittances: list[Remittance],
    bank_transactions: list[BankTransaction],
) -> None:
    """Validate that test data meets requirements."""
    print("\nValidating test data...")

    print(f"  Customers: {len(customers)}")
    print(f"  Invoices: {len(invoices)}")
    print(f"  Remittances: {len(remittances)}")
    print(f"  Bank Transactions: {len(bank_transactions)}")

    assert len(customers) == 10, f"Expected 10 customers, got {len(customers)}"
    assert len(invoices) == 200, f"Expected 200 invoices, got {len(invoices)}"
    assert len(remittances) >= 118, f"Expected ~120 remittances, got {len(remittances)}"
    assert len(bank_transactions) == 150, f"Expected 150 bank transactions, got {len(bank_transactions)}"

    # Count line items
    total_lines = sum(len(r.line_items) for r in remittances)
    print(f"  Total remittance line items: {total_lines}")

    # Count invoice statuses
    open_count = sum(1 for inv in invoices if inv.status == InvoiceStatus.OPEN)
    partial_count = sum(1 for inv in invoices if inv.status == InvoiceStatus.PARTIAL)
    closed_count = sum(1 for inv in invoices if inv.status == InvoiceStatus.CLOSED)
    print(f"  Invoice statuses: {open_count} open, {partial_count} partial, {closed_count} closed")

    print("  All validations passed!")


def main():
    """Run the complex reconciliation example."""
    print("=" * 70)
    print("CASH RECONCILIATION PLATFORM - Complex Example")
    print("150 Bank Transactions | 120 Remittances | 200 Invoices | 10 Customers")
    print("=" * 70)

    # Create test data
    print("\nGenerating test data...")
    customers = create_customers()
    invoices = create_invoices(customers)
    remittances = create_remittances(customers, invoices)
    remittances = inject_exceptions(remittances, invoices, customers)
    bank_transactions = create_bank_transactions(remittances, invoices, customers)

    # Validate
    validate_test_data(customers, invoices, remittances, bank_transactions)

    # Run reconciliation
    print("\nRunning reconciliation...")
    reconciler = Reconciler(
        bank_transactions=bank_transactions,
        remittances=remittances,
        invoices=invoices,
        customers=customers,
    )

    results = reconciler.run()

    # Print summary
    reconciler.print_summary()

    # Print detailed exception breakdown
    print("\nDETAILED EXCEPTION EXAMPLES")
    print("-" * 70)

    exception_examples = {"E002": [], "E004": [], "E005": [], "E006": [], "E007": [], "E011": []}

    for result in results:
        if result.level1_match and result.level1_match.result.exception_code:
            code = result.level1_match.result.exception_code.name
            if code in exception_examples and len(exception_examples[code]) < 2:
                exception_examples[code].append({
                    "bank_id": result.bank_transaction.id,
                    "detail": result.level1_match.result.exception_detail,
                })

        for l2 in result.level2_matches:
            if l2.result.exception_code:
                code = l2.result.exception_code.name
                if code in exception_examples and len(exception_examples[code]) < 2:
                    exception_examples[code].append({
                        "remittance_id": l2.remittance_id,
                        "line": l2.remittance_line_index,
                        "detail": l2.result.exception_detail,
                    })

    for code, examples in exception_examples.items():
        if examples:
            print(f"\n{code}:")
            for ex in examples:
                print(f"  {ex}")

    # Print sample fully reconciled transactions
    print("\n" + "-" * 70)
    print("SAMPLE FULLY RECONCILED TRANSACTIONS (first 5)")
    print("-" * 70)

    fully_reconciled_count = 0
    for result in results:
        if result.fully_reconciled and fully_reconciled_count < 5:
            fully_reconciled_count += 1
            bank = result.bank_transaction
            print(f"\n{bank.id}: ${bank.amount}")
            print(f"  Reference: {bank.reference}")
            print(f"  Rule: {result.level1_match.result.rule_applied}")
            if result.level2_matches:
                invoices_matched = [m.invoice_id for m in result.level2_matches]
                print(f"  Invoices: {', '.join(invoices_matched)}")

    # Print virtual remittance examples
    print("\n" + "-" * 70)
    print("VIRTUAL REMITTANCE EXAMPLES (first 3)")
    print("-" * 70)

    virtual_count = 0
    for result in results:
        if (result.level1_match and
            "Virtual" in result.level1_match.result.rule_applied and
            virtual_count < 3):
            virtual_count += 1
            bank = result.bank_transaction
            print(f"\n{bank.id}: ${bank.amount}")
            print(f"  Description: {bank.description[:60]}...")
            print(f"  Virtual Remittance: {result.level1_match.remittance_id}")
            if result.level2_matches:
                for m in result.level2_matches:
                    print(f"  -> Invoice: {m.invoice_id} ({m.result.outcome.value})")

    print("\n" + "=" * 70)
    print("Complex example completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
