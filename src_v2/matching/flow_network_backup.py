"""Min-cost max-flow implementation for reconciliation matching.

BACKUP OF ORIGINAL CUSTOM IMPLEMENTATION - DO NOT USE
This file is kept for reference only.
Use flow_network.py (NetworkX implementation) instead.

This module implements a flow network to find optimal assignments
between bank transactions and invoices when simpler methods fail.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class FlowEdge:
    """Represents an edge in the flow network."""

    from_node: str
    to_node: str
    capacity: Decimal  # Maximum flow (usually invoice pending amount)
    cost: float  # Cost per unit flow (negative confidence)
    flow: Decimal = field(default_factory=lambda: Decimal("0"))

    @property
    def residual_capacity(self) -> Decimal:
        """Remaining capacity on this edge."""
        return self.capacity - self.flow


@dataclass
class FlowNode:
    """Represents a node in the flow network."""

    id: str
    node_type: str  # "source", "bank", "invoice", "sink"
    supply: Decimal = field(default_factory=lambda: Decimal("0"))

    def __hash__(self) -> int:
        return hash(self.id)


class FlowNetwork:
    """Min-cost max-flow network for reconciliation.

    Network structure:
        source -> bank_nodes -> invoice_nodes -> sink

    Bank nodes have supply = bank amount
    Invoice nodes have capacity = pending amount
    Edge costs = negative confidence (to maximize confidence via min-cost)
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, FlowNode] = {}
        self.edges: Dict[str, List[FlowEdge]] = {}  # adjacency list
        self.reverse_edges: Dict[Tuple[str, str], FlowEdge] = {}

    def add_node(self, node_id: str, node_type: str, supply: Decimal = Decimal("0")) -> None:
        """Add a node to the network.

        Args:
            node_id: Unique identifier for the node.
            node_type: Type of node (source, bank, invoice, sink).
            supply: Supply at this node (for source/sink).
        """
        self.nodes[node_id] = FlowNode(id=node_id, node_type=node_type, supply=supply)
        if node_id not in self.edges:
            self.edges[node_id] = []

    def add_edge(
        self,
        from_node: str,
        to_node: str,
        capacity: Decimal,
        cost: float,
    ) -> None:
        """Add an edge to the network.

        Args:
            from_node: Source node ID.
            to_node: Destination node ID.
            capacity: Maximum flow on this edge.
            cost: Cost per unit of flow (use negative confidence).
        """
        # Ensure nodes exist
        if from_node not in self.edges:
            self.edges[from_node] = []
        if to_node not in self.edges:
            self.edges[to_node] = []

        # Add forward edge
        forward_edge = FlowEdge(
            from_node=from_node,
            to_node=to_node,
            capacity=capacity,
            cost=cost,
        )
        self.edges[from_node].append(forward_edge)

        # Add reverse edge (for residual graph)
        reverse_edge = FlowEdge(
            from_node=to_node,
            to_node=from_node,
            capacity=Decimal("0"),  # Initially 0, increases as flow is pushed
            cost=-cost,  # Negative cost for reverse
        )
        self.edges[to_node].append(reverse_edge)

        # Link edges for residual updates
        self.reverse_edges[(from_node, to_node)] = reverse_edge
        self.reverse_edges[(to_node, from_node)] = forward_edge

    def solve(self) -> Dict[str, List[Tuple[str, Decimal, float]]]:
        """Solve the min-cost max-flow problem.

        Uses successive shortest paths algorithm (Bellman-Ford for negative costs).

        Returns:
            Dict mapping bank_ids to list of (invoice_id, flow_amount, cost).
        """
        source_id = "source"
        sink_id = "sink"

        # Repeatedly find augmenting paths and push flow
        while True:
            # Find shortest path using Bellman-Ford (handles negative costs)
            path, path_cost = self._find_shortest_path(source_id, sink_id)
            if not path:
                break  # No more augmenting paths

            # Find bottleneck capacity
            bottleneck = self._find_bottleneck(path)
            if bottleneck <= Decimal("0"):
                break

            # Push flow along path
            self._push_flow(path, bottleneck)

        # Extract results
        return self._extract_assignments()

    def _find_shortest_path(
        self, source: str, sink: str
    ) -> Tuple[List[FlowEdge], float]:
        """Find shortest path using Bellman-Ford algorithm.

        Args:
            source: Source node ID.
            sink: Sink node ID.

        Returns:
            Tuple of (path as list of edges, total cost).
        """
        # Initialize distances
        dist: Dict[str, float] = {node: float("inf") for node in self.nodes}
        dist[source] = 0.0
        prev_edge: Dict[str, Optional[FlowEdge]] = {node: None for node in self.nodes}

        # Relax edges repeatedly
        for _ in range(len(self.nodes)):
            updated = False
            for node_id in self.edges:
                if dist[node_id] == float("inf"):
                    continue
                for edge in self.edges[node_id]:
                    if edge.residual_capacity <= Decimal("0"):
                        continue
                    new_dist = dist[node_id] + edge.cost
                    if new_dist < dist[edge.to_node]:
                        dist[edge.to_node] = new_dist
                        prev_edge[edge.to_node] = edge
                        updated = True
            if not updated:
                break

        # Check if sink is reachable
        if dist[sink] == float("inf"):
            return [], 0.0

        # Reconstruct path
        path: List[FlowEdge] = []
        current = sink
        while prev_edge[current] is not None:
            edge = prev_edge[current]
            path.append(edge)
            current = edge.from_node

        path.reverse()
        return path, dist[sink]

    def _find_bottleneck(self, path: List[FlowEdge]) -> Decimal:
        """Find the minimum residual capacity along a path.

        Args:
            path: List of edges forming the path.

        Returns:
            Bottleneck capacity.
        """
        if not path:
            return Decimal("0")
        return min(edge.residual_capacity for edge in path)

    def _push_flow(self, path: List[FlowEdge], amount: Decimal) -> None:
        """Push flow along a path.

        Args:
            path: List of edges to push flow through.
            amount: Amount of flow to push.
        """
        for edge in path:
            edge.flow += amount
            # Update reverse edge
            reverse_key = (edge.to_node, edge.from_node)
            if reverse_key in self.reverse_edges:
                self.reverse_edges[reverse_key].capacity += amount

    def _extract_assignments(self) -> Dict[str, List[Tuple[str, Decimal, float]]]:
        """Extract bank-to-invoice assignments from flow.

        Returns:
            Dict mapping bank_ids to list of (invoice_id, amount, cost).
        """
        assignments: Dict[str, List[Tuple[str, Decimal, float]]] = {}

        for node_id, edges in self.edges.items():
            node = self.nodes.get(node_id)
            if not node or node.node_type != "bank":
                continue

            bank_id = node_id.replace("bank_", "")
            assignments[bank_id] = []

            for edge in edges:
                if edge.flow > Decimal("0"):
                    to_node = self.nodes.get(edge.to_node)
                    if to_node and to_node.node_type == "invoice":
                        invoice_id = edge.to_node.replace("invoice_", "")
                        assignments[bank_id].append(
                            (invoice_id, edge.flow, edge.cost)
                        )

        return assignments

    def get_total_flow(self) -> Decimal:
        """Get total flow through the network."""
        total = Decimal("0")
        for edges in self.edges.values():
            for edge in edges:
                if edge.from_node == "source":
                    total += edge.flow
        return total

    def get_total_cost(self) -> float:
        """Get total cost of the current flow."""
        total = 0.0
        for edges in self.edges.values():
            for edge in edges:
                if edge.flow > Decimal("0") and edge.cost > 0:
                    # Only count forward edges
                    total += float(edge.flow) * edge.cost
        return total


def build_reconciliation_network(
    bank_amounts: Dict[str, Decimal],
    invoice_amounts: Dict[str, Decimal],
    edge_confidences: Dict[Tuple[str, str], float],
    reject_penalty: float = 0.8,
) -> FlowNetwork:
    """Build a flow network for reconciliation.

    Args:
        bank_amounts: Dict of bank_id -> amount.
        invoice_amounts: Dict of invoice_id -> pending_amount.
        edge_confidences: Dict of (bank_id, invoice_id) -> confidence score.
        reject_penalty: Penalty for not matching (cost to reject edge).

    Returns:
        Configured FlowNetwork ready to solve.
    """
    network = FlowNetwork()

    # Add source and sink
    total_bank = sum(bank_amounts.values())
    total_invoice = sum(invoice_amounts.values())
    max_flow = min(total_bank, total_invoice)

    network.add_node("source", "source", supply=max_flow)
    network.add_node("sink", "sink", supply=-max_flow)

    # Add bank nodes
    for bank_id, amount in bank_amounts.items():
        node_id = f"bank_{bank_id}"
        network.add_node(node_id, "bank", supply=Decimal("0"))
        # Edge from source to bank
        network.add_edge("source", node_id, amount, cost=0.0)

    # Add invoice nodes
    for invoice_id, amount in invoice_amounts.items():
        node_id = f"invoice_{invoice_id}"
        network.add_node(node_id, "invoice", supply=Decimal("0"))
        # Edge from invoice to sink
        network.add_edge(node_id, "sink", amount, cost=0.0)

    # Add bank-to-invoice edges with confidence-based costs
    for (bank_id, invoice_id), confidence in edge_confidences.items():
        bank_node = f"bank_{bank_id}"
        invoice_node = f"invoice_{invoice_id}"

        if bank_node not in network.nodes or invoice_node not in network.nodes:
            continue

        # Cost = negative confidence (to maximize confidence via min-cost)
        # Lower cost = higher confidence = preferred
        cost = 1.0 - confidence

        # Capacity = minimum of bank amount and invoice amount
        capacity = min(bank_amounts[bank_id], invoice_amounts[invoice_id])

        network.add_edge(bank_node, invoice_node, capacity, cost)

    # Add reject edges (allows banks to not match completely)
    for bank_id, amount in bank_amounts.items():
        bank_node = f"bank_{bank_id}"
        # Reject edge goes directly to sink with penalty
        network.add_edge(bank_node, "sink", amount, cost=reject_penalty)

    return network
