"""Simple standalone test for NetworkX flow network implementation."""

from decimal import Decimal
from src_v2.matching.flow_network import build_reconciliation_network, solve_flow_network


def test_basic_flow():
    """Test basic flow network matching."""

    # Setup test data
    bank_amounts = {
        "B1": Decimal("1000.00"),
        "B2": Decimal("500.00"),
        "B3": Decimal("750.00"),
    }

    invoice_amounts = {
        "INV-001": Decimal("800.00"),
        "INV-002": Decimal("450.00"),
        "INV-003": Decimal("700.00"),
    }

    # Edge confidences (bank_id, invoice_id) -> confidence
    edge_confidences = {
        ("B1", "INV-001"): 0.75,  # Good match
        ("B1", "INV-003"): 0.50,  # Okay match
        ("B2", "INV-002"): 0.90,  # Excellent match
        ("B3", "INV-003"): 0.80,  # Good match
    }

    # Build and solve
    print("Building flow network...")
    network = build_reconciliation_network(
        bank_amounts,
        invoice_amounts,
        edge_confidences,
        reject_penalty=0.8
    )

    print("Solving flow network...")
    assignments = solve_flow_network(network)

    # Display results
    print("\n=== RESULTS ===")
    for bank_id, allocs in assignments.items():
        print(f"\nBank {bank_id} (${bank_amounts[bank_id]}):")
        total_allocated = Decimal("0")
        for invoice_id, amount, cost in allocs:
            confidence = 1.0 - cost
            print(f"  → {invoice_id}: ${amount} (confidence: {confidence:.1%})")
            total_allocated += amount
        print(f"  Total allocated: ${total_allocated}")

        if total_allocated < bank_amounts[bank_id]:
            remaining = bank_amounts[bank_id] - total_allocated
            print(f"  Unallocated: ${remaining}")

    # Verify expectations
    print("\n=== VERIFICATION ===")

    # B2 should match INV-002 (highest confidence)
    b2_allocs = assignments.get("B2", [])
    assert len(b2_allocs) > 0, "B2 should have allocations"
    assert b2_allocs[0][0] == "INV-002", "B2 should match INV-002"
    print("✓ B2 correctly matched to INV-002")

    # B1 should match INV-001 (better confidence)
    b1_allocs = assignments.get("B1", [])
    assert len(b1_allocs) > 0, "B1 should have allocations"
    assert b1_allocs[0][0] == "INV-001", "B1 should match INV-001"
    print("✓ B1 correctly matched to INV-001")

    # B3 should match INV-003
    b3_allocs = assignments.get("B3", [])
    assert len(b3_allocs) > 0, "B3 should have allocations"
    assert b3_allocs[0][0] == "INV-003", "B3 should match INV-003"
    print("✓ B3 correctly matched to INV-003")

    print("\n✅ All tests passed!")
    return True


def test_multiple_invoices():
    """Test one bank paying multiple invoices."""

    print("\n\n=== TEST: One Bank → Multiple Invoices ===")

    bank_amounts = {
        "B1": Decimal("1500.00"),
    }

    invoice_amounts = {
        "INV-001": Decimal("800.00"),
        "INV-002": Decimal("700.00"),
    }

    edge_confidences = {
        ("B1", "INV-001"): 0.85,
        ("B1", "INV-002"): 0.80,
    }

    network = build_reconciliation_network(
        bank_amounts,
        invoice_amounts,
        edge_confidences,
        reject_penalty=0.8
    )

    assignments = solve_flow_network(network)

    b1_allocs = assignments.get("B1", [])
    print(f"\nBank B1 ($1500) allocated to:")
    total = Decimal("0")
    for invoice_id, amount, cost in b1_allocs:
        print(f"  → {invoice_id}: ${amount}")
        total += amount

    print(f"Total: ${total}")

    # Should allocate to both invoices
    assert len(b1_allocs) == 2, "B1 should match both invoices"
    assert total == Decimal("1500.00"), "Should allocate full amount"

    print("✅ Multiple invoice allocation works!")
    return True


if __name__ == "__main__":
    try:
        print("=" * 60)
        print("Testing NetworkX Flow Network Implementation")
        print("=" * 60)

        test_basic_flow()
        test_multiple_invoices()

        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
