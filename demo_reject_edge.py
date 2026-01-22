"""Demonstrate reject edge (drain) mechanism in flow network."""

from decimal import Decimal
from src_v2.matching.flow_network import build_reconciliation_network, solve_flow_network


def demo_partial_rejection():
    """Show how bank amount gets partially allocated and partially rejected."""

    print("=" * 70)
    print("SCENARIO: Bank has $1000, but best match is only $600 invoice")
    print("=" * 70)

    bank_amounts = {
        "BANK-001": Decimal("1000.00"),
    }

    invoice_amounts = {
        "INV-001": Decimal("600.00"),  # Only $600 available
    }

    # Decent confidence match
    edge_confidences = {
        ("BANK-001", "INV-001"): 0.75,  # 75% confidence
    }

    print(f"\nBank BANK-001: ${bank_amounts['BANK-001']}")
    print(f"Invoice INV-001: ${invoice_amounts['INV-001']} (confidence: 75%)")

    # Build and solve
    network = build_reconciliation_network(
        bank_amounts,
        invoice_amounts,
        edge_confidences,
        reject_penalty=0.8
    )

    assignments = solve_flow_network(network)

    print("\n" + "=" * 70)
    print("FLOW NETWORK DECISION:")
    print("=" * 70)

    # Check allocations
    bank_allocs = assignments.get("BANK-001", [])

    if bank_allocs:
        print("\n✅ Bank BANK-001 allocations:")
        total_allocated = Decimal("0")

        for invoice_id, amount, cost in bank_allocs:
            confidence = 1.0 - cost
            total_allocated += amount
            print(f"  → {invoice_id}: ${amount} (confidence: {confidence:.1%}, cost: {cost:.3f})")

        print(f"\n  Total allocated: ${total_allocated}")

        unallocated = bank_amounts["BANK-001"] - total_allocated
        if unallocated > 0:
            print(f"  ⚠️  Unallocated (went to reject edge): ${unallocated}")
            print(f"\n  💡 This happened because:")
            print(f"     - Only ${invoice_amounts['INV-001']} of invoices available")
            print(f"     - Remaining ${unallocated} had no good match")
            print(f"     - Algorithm chose reject edge (cost 0.8) over forcing bad match")
    else:
        print("\n❌ No allocations (entire amount rejected)")

    return assignments


def demo_full_rejection():
    """Show complete rejection when no good matches exist."""

    print("\n\n" + "=" * 70)
    print("SCENARIO: Bank $1000 but NO good invoice matches")
    print("=" * 70)

    bank_amounts = {
        "BANK-002": Decimal("1000.00"),
    }

    invoice_amounts = {
        "INV-002": Decimal("5000.00"),  # Too large, amount mismatch
        "INV-003": Decimal("100.00"),   # Too small, amount mismatch
    }

    # Very low confidence (below threshold)
    edge_confidences = {
        ("BANK-002", "INV-002"): 0.15,  # 15% confidence (poor)
        ("BANK-002", "INV-003"): 0.10,  # 10% confidence (poor)
    }

    print(f"\nBank BANK-002: ${bank_amounts['BANK-002']}")
    print(f"Invoice INV-002: ${invoice_amounts['INV-002']} (confidence: 15% - too large)")
    print(f"Invoice INV-003: ${invoice_amounts['INV-003']} (confidence: 10% - too small)")

    # Build and solve
    network = build_reconciliation_network(
        bank_amounts,
        invoice_amounts,
        edge_confidences,
        reject_penalty=0.8
    )

    assignments = solve_flow_network(network)

    print("\n" + "=" * 70)
    print("FLOW NETWORK DECISION:")
    print("=" * 70)

    bank_allocs = assignments.get("BANK-002", [])

    if bank_allocs:
        print("\n✅ Bank BANK-002 allocations:")
        for invoice_id, amount, cost in bank_allocs:
            confidence = 1.0 - cost
            print(f"  → {invoice_id}: ${amount} (confidence: {confidence:.1%}, cost: {cost:.3f})")
    else:
        print("\n⚠️  Bank BANK-002: FULLY REJECTED (went to drain)")
        print(f"     Amount: ${bank_amounts['BANK-002']}")
        print(f"\n  💡 This happened because:")
        print(f"     - INV-002 match cost: {1.0 - 0.15:.3f} (850 > 800 reject penalty)")
        print(f"     - INV-003 match cost: {1.0 - 0.10:.3f} (900 > 800 reject penalty)")
        print(f"     - Reject edge cost: 0.800 (cheapest path!)")
        print(f"     - Algorithm chose to NOT match rather than force poor match")

    return assignments


def demo_cost_comparison():
    """Show the cost calculation that determines rejection."""

    print("\n\n" + "=" * 70)
    print("COST COMPARISON: Why Algorithm Rejects vs Matches")
    print("=" * 70)

    reject_penalty = 0.8

    print("\nReject edge cost: 0.800 (fixed penalty)")
    print("\nInvoice match costs (1.0 - confidence):")
    print("-" * 70)

    confidences = [0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.50, 0.40, 0.30, 0.20, 0.10]

    for conf in confidences:
        cost = 1.0 - conf
        decision = "✅ MATCH" if cost < reject_penalty else "❌ REJECT"
        symbol = "  " if cost < reject_penalty else "⚠️ "
        print(f"  {symbol}Confidence: {conf:.0%} → Cost: {cost:.3f} → {decision}")

    print("\n" + "=" * 70)
    print("RULE: If (1.0 - confidence) < 0.8 → Match invoice")
    print("      If (1.0 - confidence) ≥ 0.8 → Use reject edge (drain)")
    print("=" * 70)


def show_network_edges():
    """Visualize all edges in network including reject edges."""

    print("\n\n" + "=" * 70)
    print("NETWORK STRUCTURE: All Edges Including Reject Paths")
    print("=" * 70)

    bank_amounts = {
        "B1": Decimal("1000"),
    }

    invoice_amounts = {
        "I1": Decimal("800"),
    }

    edge_confidences = {
        ("B1", "I1"): 0.75,
    }

    network = build_reconciliation_network(
        bank_amounts,
        invoice_amounts,
        edge_confidences,
        reject_penalty=0.8
    )

    print("\nNodes:")
    for node in network.nodes():
        demand = network.nodes[node].get('demand', 0)
        if demand != 0:
            supply_type = "SUPPLY" if demand < 0 else "DEMAND"
            print(f"  {node}: {supply_type} = {abs(demand)}")
        else:
            print(f"  {node}: transit node")

    print("\nEdges:")
    for u, v, data in network.edges(data=True):
        capacity = data['capacity']
        weight = data['weight']
        cost = weight / 1000.0

        # Identify edge type
        if v == 'sink' and u.startswith('bank_'):
            edge_type = "🚫 REJECT EDGE (drain)"
        elif u == 'source':
            edge_type = "💰 Source supply"
        elif v == 'sink':
            edge_type = "🎯 Invoice to sink"
        else:
            edge_type = "🔗 Bank-Invoice match"

        print(f"  {u:15} → {v:15}  capacity: ${capacity:8.2f}  cost: {cost:.3f}  {edge_type}")

    print("\n" + "=" * 70)
    print("The algorithm routes flow through LOWEST COST paths")
    print("Reject edges act as 'pressure relief' - better to reject than force bad match")
    print("=" * 70)


if __name__ == "__main__":
    demo_partial_rejection()
    demo_full_rejection()
    demo_cost_comparison()
    show_network_edges()

    print("\n\n" + "=" * 70)
    print("KEY TAKEAWAY:")
    print("=" * 70)
    print("""
Reject edges (drain) provide THREE benefits:

1. ✅ Allows partial matching
   - Bank can pay $600 to invoice, leave $400 unallocated

2. ✅ Prevents forced bad matches
   - Better to reject than match with <20% confidence

3. ✅ Makes network always feasible
   - Algorithm never fails - worst case is full rejection

The 0.8 penalty is tuned so:
- Good matches (>20% confidence) are preferred over rejection
- Bad matches (<20% confidence) are rejected automatically
""")
    print("=" * 70)
