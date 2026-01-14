# Graph-Based Matching Approach for Cash Reconciliation

## Why Not Greedy?

Greedy algorithms have fundamental flaws for cash reconciliation:

1. **Order dependency** — results change based on processing sequence
2. **Local optima** — miss globally optimal solutions
3. **No backtracking** — early mistakes propagate
4. **Ignores interdependencies** — matches aren't independent

---

## The Problem as a Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   BANK                  REMITTANCES              INVOICES       │
│   TRANSACTIONS          (actual or virtual)                     │
│                                                                 │
│      B1 ─────────────────── R1 ─────────────────── I1          │
│        \                 /      \                /              │
│         \               /        \              /               │
│      B2 ──────────────── R2 ─────────────────── I2             │
│        \               /    \    /             /                │
│         \             /      \  /             /                 │
│      B3 ─────────────────── R3 ─────────────────── I3          │
│                                                                 │
│   Edges = potential matches with confidence weights             │
│   Goal = find optimal assignment across entire graph            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

This is a **constrained bipartite matching** problem with:
- Weighted edges (match confidence)
- Flow constraints (amounts must balance)
- Cardinality constraints (one-to-one, one-to-many relationships)
- Online arrivals (data streams in continuously)

---

## Why Greedy Fails: Example

```
Bank B1: $5,000
Bank B2: $5,000

Invoice I1: $5,000 (Customer A)
Invoice I2: $5,000 (Customer B)

Remittance R1: $5,000 from Customer A

Greedy (processing B1 first):
  B1 → I1 (best amount match)
  B2 → I2
  R1 → ??? (I1 already taken, but R1 is from Customer A!)

Optimal:
  B1 → R1 → I1 (Customer A's payment)
  B2 → I2 (unidentified, but correct assignment)

Greedy locked in a suboptimal match because it didn't see the full picture.
```

---

## Graph-Based Formulations

### Formulation 1: Minimum Cost Maximum Flow

Model the entire system as a flow network:

```
                    ┌─────────┐
                    │ SOURCE  │
                    └────┬────┘
                         │ (capacity = bank amounts)
                         ▼
              ┌─────────────────────┐
              │  BANK TRANSACTIONS  │
              │    B1, B2, B3...    │
              └──────────┬──────────┘
                         │ (capacity = ∞, cost = -confidence)
                         ▼
              ┌─────────────────────┐
              │    REMITTANCES      │
              │    R1, R2, R3...    │
              └──────────┬──────────┘
                         │ (capacity = line item amounts, cost = -confidence)
                         ▼
              ┌─────────────────────┐
              │      INVOICES       │
              │    I1, I2, I3...    │
              └──────────┬──────────┘
                         │ (capacity = pending amounts)
                         ▼
                    ┌─────────┐
                    │  SINK   │
                    └─────────┘

Objective: Find maximum flow with minimum cost
           (equivalent to maximum total confidence)

Algorithms:
- Successive Shortest Path
- Cycle-Canceling
- Cost Scaling
```

**Advantages:**
- Global optimum guaranteed
- Amount constraints naturally enforced via capacities
- Handles partial payments (flow < capacity)

---

### Formulation 2: Weighted Bipartite Matching (Assignment Problem)

```
         INVOICES
         I1    I2    I3    I4
      ┌─────┬─────┬─────┬─────┐
   B1 │ 0.9 │ 0.2 │ 0.1 │ 0.0 │
      ├─────┼─────┼─────┼─────┤
   B2 │ 0.3 │ 0.85│ 0.1 │ 0.0 │
 B    ├─────┼─────┼─────┼─────┤
 A  B3│ 0.0 │ 0.1 │ 0.7 │ 0.6 │
 N    ├─────┼─────┼─────┼─────┤
 K  B4│ 0.0 │ 0.0 │ 0.5 │ 0.8 │
      └─────┴─────┴─────┴─────┘

Objective: Find assignment maximizing total weight
           such that each row/column selected at most once

Algorithm: Hungarian Algorithm - O(n³)
```

**With Side Constraints:**
- Amount matching: |B.amount - I.amount| ≤ tolerance
- Customer scoping: Match only within customer
- Temporal: Date constraints

---

### Formulation 3: Integer Linear Program (ILP)

```
Variables:
  x_ij ∈ {0,1} = 1 if bank i matches to invoice j

Objective:
  Maximize Σᵢⱼ confidence_ij × x_ij

Subject to:

  (1) Each bank matches to at least one invoice (if matchable)
      Σⱼ x_ij ≥ 1  for all i where match exists

  (2) Each invoice matched at most once
      Σᵢ x_ij ≤ 1  for all j

  (3) Amount conservation (with tolerance)
      |bank_i.amount - Σⱼ(x_ij × invoice_j.amount)| ≤ tolerance

  (4) Customer constraint (if customer identified)
      x_ij = 0  if invoice_j.customer ≠ identified_customer_i

  (5) Mutual exclusivity (business rules)
      Additional constraints as needed
```

**Solvers:** CPLEX, Gurobi, OR-Tools, SCIP

---

## The Online Challenge

Data arrives continuously — we can't wait for all transactions before matching.

### Online Bipartite Matching Framework

```
Known side (offline):     INVOICES (relatively stable)
Arriving side (online):   BANK TRANSACTIONS (stream in daily)

When new bank transaction arrives:
1. Compute edges to all candidate invoices
2. Make irrevocable matching decision
3. Cannot undo previous matches
```

### Classic Online Algorithms

**RANKING Algorithm** (Karp-Vazirani-Vazirani):
```
Preprocessing:
  Assign random rank r(j) ∈ [0,1] to each invoice j

Online (when bank i arrives):
  Match i to highest-ranked available neighbor

Competitive ratio: 1 - 1/e ≈ 0.632
(Achieves 63.2% of optimal offline solution)
```

**Balance Algorithm:**
```
Track "load" L(j) for each invoice j (number of times nearly matched)

Online (when bank i arrives):
  Match i to neighbor j minimizing L(j)
  Update L(j)

Better for scenarios with repeated similar transactions
```

---

## Recommended Approach: Deferred Acceptance with Reoptimization

Combine online responsiveness with global optimization:

```
┌─────────────────────────────────────────────────────────────────┐
│                    MATCHING STATES                              │
├─────────────────────────────────────────────────────────────────┤
│  TENTATIVE  │  Suggested match, not yet confirmed               │
│  CONFIRMED  │  User-approved or high-confidence auto-match      │
│  LOCKED     │  Accounting closed, cannot change                 │
└─────────────────────────────────────────────────────────────────┘
```

### Algorithm: Online Matching with Periodic Reoptimization

```
INITIALIZE:
  G = empty bipartite graph
  M = empty matching (set of edges)

ON NEW BANK TRANSACTION b:
  1. Add node b to graph G
  2. Compute edges: E(b) = {(b, i, conf) for all candidate invoices i}
  3. Add edges to G
  4. Run INCREMENTAL MATCHING on b
  5. If high confidence: Add to M as TENTATIVE

ON NEW INVOICE i:
  1. Add node i to graph G
  2. Compute edges to existing unmatched bank transactions
  3. Check if improves any TENTATIVE matches
  4. Run AUGMENTING PATH search

PERIODIC REOPTIMIZATION (e.g., hourly):
  1. Collect all TENTATIVE matches
  2. Run GLOBAL OPTIMIZATION on unconfirmed subgraph
  3. Update M with improved matching
  4. Notify users of changes

ON USER CONFIRMATION:
  1. Move match from TENTATIVE to CONFIRMED
  2. Remove from reoptimization pool
  3. Update graph: remove confirmed nodes

ON ACCOUNTING CLOSE:
  1. Move CONFIRMED to LOCKED
  2. Permanently remove from graph
```

---

## Incremental Matching: Augmenting Paths

When a new node arrives, find if it enables a better global matching:

```
AUGMENTING PATH ALGORITHM:

Given: Current matching M, new bank transaction b

1. Find all invoices i where edge (b,i) exists
2. For each candidate i:
   a. If i is unmatched:
      - Direct augmenting path found
      - Add (b,i) to M
   b. If i is matched to b':
      - Can we find alternative for b'?
      - Recursively search for augmenting path from b'
      - If found: "swap" matches for better global solution

Example:
─────────
Current: B1 → I1 (conf: 0.7)
New:     B2 arrives, wants I1 (conf: 0.9)

Search: Can B1 match elsewhere?
Found:  B1 → I2 (conf: 0.65)

Compare:
  Old total: 0.7 (B1→I1)
  New total: 0.9 + 0.65 = 1.55 (B2→I1, B1→I2)

Decision: Swap! New matching is globally better.
```

```
     BEFORE                    AFTER

  B1 ──(0.7)──→ I1          B1 ──(0.65)──→ I2

  B2            I2          B2 ──(0.9)───→ I1
```

---

## Handling Amount Constraints in Graph

The tricky part: one bank transaction might match **multiple** invoices.

### Approach: Hypergraph / Set Matching

```
Instead of:  Bank → Invoice (one-to-one)
Model as:    Bank → {Invoice Set} (one-to-many)

Each "super-node" represents a valid combination:

  Bank ($15,000) can match to:
    - Combo1: {I1: $15,000}           (single invoice)
    - Combo2: {I2: $8,000, I3: $7,000} (two invoices)
    - Combo3: {I4: $5,000, I5: $5,000, I6: $5,000} (three invoices)

  Each combo is a node; select at most one combo per bank
```

### Alternative: Multi-Commodity Flow

```
Model amounts as flow quantities:

  Bank B1 ($10,000)
    → can send $6,000 to Invoice I1
    → can send $4,000 to Invoice I2

  Flow conservation at each node
  Total flow out of B1 = $10,000
  Total flow into I1 ≤ I1.pending_amount
```

---

## Belief Propagation Approach

For uncertain/probabilistic matching, use message passing:

```
FACTOR GRAPH:

  Variable nodes: x_ij (match decisions)
  Factor nodes:
    - Confidence factors: ψ(x_ij) = confidence_ij
    - Constraint factors: ensure valid matching

MESSAGE PASSING:

  1. Initialize beliefs uniformly
  2. Iterate until convergence:
     - Variable → Factor messages
     - Factor → Variable messages
  3. Read marginal probabilities P(x_ij = 1)
  4. Threshold to get final matching

Advantages:
  - Handles uncertainty naturally
  - Provides confidence estimates
  - Works with soft constraints
```

---

## Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MATCHING ENGINE                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   GRAPH      │    │   MATCHING   │    │  CONSTRAINT  │      │
│  │   STORE      │◄──►│   ALGORITHM  │◄──►│  VALIDATOR   │      │
│  │              │    │              │    │              │      │
│  │ - Nodes      │    │ - Hungarian  │    │ - Amounts    │      │
│  │ - Edges      │    │ - Min-Cost   │    │ - Customers  │      │
│  │ - Weights    │    │   Flow       │    │ - Dates      │      │
│  │ - State      │    │ - Augmenting │    │ - Business   │      │
│  │              │    │   Paths      │    │   Rules      │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│          │                  │                   │               │
│          └──────────────────┼───────────────────┘               │
│                             │                                   │
│                             ▼                                   │
│                    ┌──────────────┐                             │
│                    │  OPTIMIZER   │                             │
│                    │              │                             │
│                    │ - Online     │                             │
│                    │   incremental│                             │
│                    │ - Batch      │                             │
│                    │   reoptimize │                             │
│                    └──────────────┘                             │
│                             │                                   │
│          ┌──────────────────┼───────────────────┐               │
│          ▼                  ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  TENTATIVE   │    │  CONFIRMED   │    │   EXCEPTION  │      │
│  │  MATCHES     │    │  MATCHES     │    │   QUEUE      │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Algorithm Selection Guide

| Scenario | Best Algorithm |
|----------|----------------|
| Small scale, batch processing | Hungarian Algorithm |
| Large scale, batch processing | Min-Cost Max-Flow |
| Real-time, irrevocable matches | Online RANKING |
| Real-time, can revise tentative | Augmenting Paths + Reoptimization |
| Uncertain matches, soft constraints | Belief Propagation |
| Complex constraints | ILP Solver |
| Very large scale | Approximate algorithms (auction, relaxation) |

---

## Comparison: Greedy vs Graph-Based

| Aspect | Greedy | Graph-Based |
|--------|--------|-------------|
| Optimality | Local | Global |
| Order dependency | Yes | No |
| Handles interdependencies | No | Yes |
| Computational cost | O(n) | O(n³) or better |
| Can backtrack | No | Yes (tentative) |
| Explainability | Simple | Requires effort |
| Online capability | Natural | Requires design |

---

## Practical Hybrid Approach

```
PHASE 1: DETERMINISTIC MATCHING
  - Apply high-confidence rules (reference matches)
  - These become CONFIRMED immediately
  - Remove from graph

PHASE 2: GRAPH OPTIMIZATION
  - Build graph from remaining unmatched
  - Run global optimization (Hungarian/Min-Cost Flow)
  - Generate TENTATIVE matches

PHASE 3: ONLINE UPDATES
  - New arrivals trigger incremental matching
  - Augmenting paths improve existing solution
  - Periodic batch reoptimization

PHASE 4: HUMAN-IN-THE-LOOP
  - Low-confidence matches go to exception queue
  - User decisions become constraints
  - System learns from corrections
```

---

## Next Steps

1. Choose primary algorithm based on scale and requirements
2. Design graph data structure for efficient operations
3. Implement constraint validation layer
4. Build incremental update mechanism
5. Create reoptimization scheduler
6. Design exception handling workflow
