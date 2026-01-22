"""Min-cost max-flow using NetworkX for reconciliation matching.

This module uses NetworkX's optimized min-cost flow algorithm to find
optimal assignments between bank transactions and invoices.

NetworkX provides a well-tested, performant implementation that replaces
the custom Bellman-Ford algorithm with production-ready code.
"""

import networkx as nx
from decimal import Decimal
from typing import Dict, List, Tuple


def build_reconciliation_network(
    bank_amounts: Dict[str, Decimal],
    invoice_amounts: Dict[str, Decimal],
    edge_confidences: Dict[Tuple[str, str], float],
    reject_penalty: float = 0.8,
) -> nx.DiGraph:
    """Build a flow network for reconciliation using NetworkX.

    Creates a directed graph with:
    - Source node (supplies all money)
    - Bank nodes (one per transaction)
    - Invoice nodes (one per unpaid invoice)
    - Sink node (consumes all money)
    - Edges with capacity and cost (weight)

    Args:
        bank_amounts: Dict of bank_id -> amount.
        invoice_amounts: Dict of invoice_id -> pending_amount.
        edge_confidences: Dict of (bank_id, invoice_id) -> confidence score (0-1).
        reject_penalty: Penalty cost for not matching a bank transaction (default 0.8).

    Returns:
        NetworkX DiGraph configured for min-cost flow solving.

    Example:
        >>> bank_amounts = {"B1": Decimal("1000"), "B2": Decimal("500")}
        >>> invoice_amounts = {"I1": Decimal("800"), "I2": Decimal("450")}
        >>> edge_confidences = {("B1", "I1"): 0.8, ("B2", "I2"): 0.9}
        >>> G = build_reconciliation_network(bank_amounts, invoice_amounts, edge_confidences)
        >>> assignments = solve_flow_network(G)
    """
    G = nx.DiGraph()

    # Calculate total supply/demand
    total_supply = float(sum(bank_amounts.values()))
    total_demand = float(sum(invoice_amounts.values()))
    total_flow = min(total_supply, total_demand)

    # Add source and sink nodes with demand attributes
    G.add_node('source', demand=-total_flow)  # Supplies money (negative)
    G.add_node('sink', demand=total_flow)     # Demands money (positive)

    # Add edges from source to banks
    for bank_id, amount in bank_amounts.items():
        G.add_edge(
            'source',
            f'bank_{bank_id}',
            capacity=float(amount),
            weight=0  # Zero cost from source
        )

    # Add edges from invoices to sink
    for invoice_id, amount in invoice_amounts.items():
        G.add_edge(
            f'invoice_{invoice_id}',
            'sink',
            capacity=float(amount),
            weight=0  # Zero cost to sink
        )

    # Add bank-to-invoice edges with confidence-based costs
    for (bank_id, invoice_id), confidence in edge_confidences.items():
        # Convert confidence (0-1, higher is better) to cost (lower is better)
        # Scale by 1000 for better precision in NetworkX integer arithmetic
        cost = int((1.0 - confidence) * 1000)

        # Capacity is limited by both bank and invoice amounts
        capacity = min(bank_amounts[bank_id], invoice_amounts[invoice_id])

        G.add_edge(
            f'bank_{bank_id}',
            f'invoice_{invoice_id}',
            capacity=float(capacity),
            weight=cost
        )

    # Add reject edges (bank can flow directly to sink with penalty)
    # This allows partial matching - banks that don't have good invoice matches
    for bank_id, amount in bank_amounts.items():
        G.add_edge(
            f'bank_{bank_id}',
            'sink',
            capacity=float(amount),
            weight=int(reject_penalty * 1000)  # High cost = avoid unless necessary
        )

    return G


def solve_flow_network(G: nx.DiGraph) -> Dict[str, List[Tuple[str, Decimal, float]]]:
    """Solve the min-cost max-flow problem and extract bank-to-invoice assignments.

    Uses NetworkX's min_cost_flow algorithm which implements the network simplex
    algorithm - highly efficient and well-tested.

    Args:
        G: NetworkX DiGraph built by build_reconciliation_network.

    Returns:
        Dict mapping bank_ids to list of (invoice_id, flow_amount, cost) tuples.
        Only returns flows from banks to invoices (filters out source/sink flows).

    Example:
        >>> assignments = solve_flow_network(G)
        >>> # {
        >>> #   "B1": [("I1", Decimal("800"), 0.2)],
        >>> #   "B2": [("I2", Decimal("450"), 0.1)]
        >>> # }
    """
    try:
        # Solve min-cost flow problem
        # NetworkX returns a dict of dicts: {from_node: {to_node: flow}}
        flow_dict = nx.min_cost_flow(G)
    except nx.NetworkXUnfeasible:
        # Network is infeasible (shouldn't happen with reject edges, but handle gracefully)
        return {}
    except nx.NetworkXError:
        # Other NetworkX errors (invalid graph, etc.)
        return {}

    # Extract bank-to-invoice assignments from flow solution
    assignments: Dict[str, List[Tuple[str, Decimal, float]]] = {}

    for from_node, flows in flow_dict.items():
        # Only process bank nodes (skip source, invoices, sink)
        if not from_node.startswith('bank_'):
            continue

        bank_id = from_node.replace('bank_', '')
        assignments[bank_id] = []

        for to_node, flow_amount in flows.items():
            # Only process flows to invoice nodes (skip sink, reject edges)
            if flow_amount <= 0 or not to_node.startswith('invoice_'):
                continue

            invoice_id = to_node.replace('invoice_', '')

            # Get the cost from the edge data (unscale from integer)
            edge_data = G[from_node][to_node]
            cost = edge_data['weight'] / 1000.0  # Unscale cost

            # Convert flow to Decimal for financial precision
            flow_decimal = Decimal(str(flow_amount))

            assignments[bank_id].append((invoice_id, flow_decimal, cost))

    return assignments


# Legacy compatibility: maintain FlowNetwork class interface for existing code
class FlowNetwork:
    """Compatibility wrapper around NetworkX implementation.

    Maintains the same interface as the old custom implementation
    for backward compatibility. New code should use the functions directly.
    """

    def __init__(self) -> None:
        """Initialize empty flow network."""
        self._graph: nx.DiGraph | None = None
        self._bank_amounts: Dict[str, Decimal] = {}
        self._invoice_amounts: Dict[str, Decimal] = {}
        self._edge_confidences: Dict[Tuple[str, str], float] = {}
        self._reject_penalty: float = 0.8

    def solve(self) -> Dict[str, List[Tuple[str, Decimal, float]]]:
        """Solve the min-cost max-flow problem.

        Note: This method is for backward compatibility only.
        Prefer using build_reconciliation_network() and solve_flow_network() directly.

        Returns:
            Dict mapping bank_ids to list of (invoice_id, flow_amount, cost).
        """
        # Build network if not already built
        if self._graph is None:
            self._graph = build_reconciliation_network(
                self._bank_amounts,
                self._invoice_amounts,
                self._edge_confidences,
                self._reject_penalty
            )

        return solve_flow_network(self._graph)
