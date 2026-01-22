"""Debug NetworkX flow network."""

from decimal import Decimal
import networkx as nx
from src_v2.matching.flow_network import build_reconciliation_network, solve_flow_network


# Setup simple test
bank_amounts = {
    "B1": Decimal("100.00"),
}

invoice_amounts = {
    "INV-001": Decimal("100.00"),
}

edge_confidences = {
    ("B1", "INV-001"): 0.90,  # Good match
}

print("Building network...")
G = build_reconciliation_network(
    bank_amounts,
    invoice_amounts,
    edge_confidences,
    reject_penalty=0.8
)

print("\nGraph nodes:", list(G.nodes()))
print("\nNode demands:")
for node in G.nodes():
    demand = G.nodes[node].get('demand', 0)
    print(f"  {node}: demand={demand}")

print("\nGraph edges:")
for u, v, data in G.edges(data=True):
    print(f"  {u} → {v}: capacity={data.get('capacity')}, weight={data.get('weight')}")

print("\nTrying to solve...")
try:
    flow_dict = nx.min_cost_flow(G)
    print("\nFlow result:")
    for from_node, flows in flow_dict.items():
        for to_node, flow in flows.items():
            if flow > 0:
                print(f"  {from_node} → {to_node}: {flow}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
