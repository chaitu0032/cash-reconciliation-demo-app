# ILP Matching Approach for Cash Reconciliation

## Overview

This document describes the Integer Linear Programming (ILP) approach for cash reconciliation, with **customer identification as a pre-processing stage** before graph/ILP matching.

---

## Architecture: Customer-First Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  STAGE 1: DATA INGESTION                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │    BANKS    │  │ REMITTANCES │  │  INVOICES   │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                     │
│         └────────────────┼────────────────┘                     │
│                          ▼                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STAGE 2: CUSTOMER IDENTIFICATION (Pre-Graph)                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                                                          │  │
│  │  For each Bank Transaction:                              │  │
│  │    1. Parse description                                  │  │
│  │    2. Match to remittance (if exists)                   │  │
│  │    3. Identify customer using all signals               │  │
│  │    4. Tag with customer_id (or "UNKNOWN")               │  │
│  │                                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STAGE 3: PARTITION BY CUSTOMER                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                                                          │  │
│  │   CUSTOMER A        CUSTOMER B        UNKNOWN            │  │
│  │  ┌──────────┐      ┌──────────┐      ┌──────────┐       │  │
│  │  │ Banks    │      │ Banks    │      │ Banks    │       │  │
│  │  │ B1, B4   │      │ B2, B5   │      │ B3, B6   │       │  │
│  │  │          │      │          │      │          │       │  │
│  │  │ Invoices │      │ Invoices │      │ Invoices │       │  │
│  │  │ I1,I2,I5 │      │ I3,I4    │      │ ALL      │       │  │
│  │  └──────────┘      └──────────┘      └──────────┘       │  │
│  │                                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│         ┌────────────────┼────────────────┐                     │
│         ▼                ▼                ▼                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STAGE 4: ILP MATCHING (Per Customer Partition)                 │
│                                                                 │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐            │
│  │ ILP for    │    │ ILP for    │    │ ILP for    │            │
│  │ Customer A │    │ Customer B │    │ UNKNOWN    │            │
│  └─────┬──────┘    └─────┬──────┘    └─────┬──────┘            │
│        │                 │                 │                    │
│        └─────────────────┼─────────────────┘                    │
│                          ▼                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STAGE 5: MERGE & OUTPUT                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Why Customer-First?

| Aspect | In-Graph Filtering | Pre-Graph Filtering |
|--------|---------------------|---------------------|
| Problem size | N banks × M invoices | N/K banks × M/K invoices per partition |
| Complexity | O((NM)³) | O(K × (N/K × M/K)³) = much smaller |
| Parallelization | Hard | Easy (solve partitions in parallel) |
| Customer constraint | Soft (in objective) | Hard (by design) |
| Debugging | Complex | Isolated per customer |
| Incremental updates | Rebuild all | Update only affected partition |

---

## Stage 2: Customer Identification

### Customer Master Data

```
┌─────────────────────────────────────────────────────────────────┐
│                    CUSTOMER MASTER                              │
├──────────────┬──────────────────────────────────────────────────┤
│ customer_id  │ Unique identifier                                │
│ name         │ Official company name                            │
│ aliases      │ Alternative names ["Acme", "ACME Inc"]          │
│ account_nums │ Bank account numbers ["90001234", "90005678"]   │
│ ref_patterns │ Payment reference patterns ["PAY-AC-*", "AC*"]  │
│ address      │ Address for matching                             │
└──────────────┴──────────────────────────────────────────────────┘
```

### Identification Methods (Priority Order)

```
┌─────┬─────────────────────────────────┬────────────┐
│ # │ Method                          │ Confidence │
├─────┼─────────────────────────────────┼────────────┤
│ 1   │ Remittance customer_id          │ 1.00       │
│ 2   │ Account number match            │ 0.95       │
│ 3   │ Payment reference pattern       │ 0.92       │
│ 4   │ Exact name match                │ 0.90       │
│ 5   │ Sender bank account             │ 0.90       │
│ 6   │ Alias match                     │ 0.85       │
│ 7   │ Fuzzy name match (≥85%)        │ 0.70       │
│ 8   │ Address match                   │ 0.65       │
└─────┴─────────────────────────────────┴────────────┘
```

### Bank Description Parsing

Extract structured data from bank descriptions:

```
Input:  "ACME CORP REF:PAY-AC-789 INV-2024-001 A/C:90001234"

Output:
{
    "customer_name": "ACME CORP",
    "payment_ref": "PAY-AC-789",
    "invoice_numbers": ["INV-2024-001"],
    "account_number": "90001234"
}
```

### Parsing Patterns

```
Invoice Numbers:  INV[-:#]?\s*[\w-]+
Payment Reference: REF[-:#]?\s*[\w-]+
Account Number:   A/?C[-:#]?\s*\d+
```

---

## Stage 3: Partition by Customer

### Partitioning Logic

```
FOR each identified bank transaction:
    IF customer_id is known:
        Add to customer's partition
        Partition gets only that customer's invoices
    ELSE:
        Add to UNKNOWN partition
        UNKNOWN partition gets ALL invoices (can match any)
```

### Example

```
Input:
  Banks: B1(CustA), B2(CustB), B3(UNKNOWN), B4(CustA)
  Invoices: I1(CustA), I2(CustA), I3(CustB), I4(CustB)

Partitions:
  Customer A: Banks=[B1,B4], Invoices=[I1,I2]
  Customer B: Banks=[B2], Invoices=[I3,I4]
  UNKNOWN:    Banks=[B3], Invoices=[I1,I2,I3,I4]
```

---

## Stage 4: ILP Mathematical Formulation

### The Real Business Goal

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   GOAL: Account for every dollar received                       │
│                                                                 │
│   For each bank payment, answer:                                │
│     1. WHO paid? (customer)                                     │
│     2. FOR WHAT? (which invoices)                               │
│     3. HOW MUCH? (amount allocation)                            │
│                                                                 │
│   KEY INSIGHT: Correctness over completeness                    │
│   An unassigned payment going to manual review is BETTER        │
│   than an auto-matched payment that's WRONG.                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Objective Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                     OBJECTIVE PRIORITY                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PRIMARY: Match payments to CORRECT invoices                    │
│           (correctness over completeness)                       │
│                                                                 │
│  SECONDARY: Maximize amount matched                             │
│             (but only confident matches)                        │
│                                                                 │
│  TERTIARY: Minimize manual work                                 │
│            (clear exceptions, not forced matches)               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Decision Variables

```
x_ij ∈ {0, 1}    : 1 if Bank i is linked to Invoice j
f_ij ∈ ℝ≥0       : Amount allocated from Bank i to Invoice j
u_i  ∈ ℝ≥0       : Unallocated amount from Bank i (acceptable outcome)
```

### Objective Function (Revised)

```
MAXIMIZE:
    Σᵢⱼ (confidence_ij × f_ij)

    ─────────────────────────
    Maximize confident matches only

NO PENALTY for unallocated - unassigned is acceptable if no good match exists.
```

### Confidence Threshold (Critical)

Only create match variables for pairs above minimum confidence:

```
MIN_CONFIDENCE = 0.5

For each (bank_i, invoice_j):
    IF confidence_ij < MIN_CONFIDENCE:
        Do NOT create x_ij or f_ij variables
        This pair cannot be matched
```

**Philosophy**: Better to leave unassigned than make wrong match.

### Constraints

```
(1) Bank Amount Conservation:
    Σⱼ f_ij + u_i = Bank_i.amount    ∀ bank i

    "Every dollar from a bank must go somewhere"

(2) Invoice Capacity:
    Σᵢ f_ij ≤ Invoice_j.pending_amount    ∀ invoice j

    "Invoice cannot receive more than pending amount"

(3) Flow-Match Linkage:
    f_ij ≤ Bank_i.amount × x_ij    ∀ i,j

    "Flow only exists if match exists"

(4) Binary Constraint:
    x_ij ∈ {0, 1}    ∀ i,j

(5) Non-negativity:
    f_ij ≥ 0, u_i ≥ 0    ∀ i,j
```

### Complete Model

```
MAXIMIZE:
    Σᵢⱼ (confidence_ij × f_ij) - P_u × Σᵢ u_i

SUBJECT TO:
    Σⱼ f_ij + u_i = B_i                    ∀ i ∈ Banks
    Σᵢ f_ij ≤ I_j                          ∀ j ∈ Invoices
    f_ij ≤ B_i × x_ij                      ∀ i,j
    x_ij ∈ {0, 1}                          ∀ i,j
    f_ij ≥ 0, u_i ≥ 0                      ∀ i,j

WHERE:
    B_i = Bank i amount
    I_j = Invoice j pending amount
    P_u = Penalty for unallocated funds (e.g., 0.01)
    confidence_ij = Match confidence between bank i and invoice j
```

---

## Confidence Calculation (Within Partition)

Since customer is already validated by partitioning, confidence is based on other signals:

```
Base Score: 0.5 (same customer - guaranteed by partition)

Amount Match:
  Exact match:           +0.30
  Within 1%:             +0.20
  Within 5%:             +0.10

Date Proximity:
  Within 3 days:         +0.15
  Within 7 days:         +0.10
  Within 14 days:        +0.05

Invoice Reference Found:
  In bank description:   +0.25

Maximum Score: 1.0
```

---

## Implementation (Python with OR-Tools)

### Customer Identifier

```python
class CustomerIdentifier:
    def __init__(self, customer_master: List[dict]):
        self.customers = {c['customer_id']: c for c in customer_master}
        self.build_indexes()

    def build_indexes(self):
        # Account number -> customer
        self.account_index = {}
        for cust in self.customers.values():
            for acc in cust.get('account_numbers', []):
                self.account_index[self.normalize(acc)] = cust['customer_id']

        # Name/alias -> customer
        self.name_index = {}
        for cust in self.customers.values():
            self.name_index[self.normalize(cust['name'])] = cust['customer_id']
            for alias in cust.get('aliases', []):
                self.name_index[self.normalize(alias)] = cust['customer_id']

        # Payment reference patterns
        self.ref_patterns = []
        for cust in self.customers.values():
            for pattern in cust.get('payment_ref_patterns', []):
                self.ref_patterns.append((pattern, cust['customer_id']))

    def normalize(self, text: str) -> str:
        if not text:
            return ""
        return text.upper().strip().replace(" ", "").replace("-", "")

    def identify(self, bank_txn: dict, remittance: dict = None) -> dict:
        candidates = []

        # Method 1: From remittance
        if remittance and remittance.get('customer_id'):
            return {
                'customer_id': remittance['customer_id'],
                'confidence': 1.0,
                'method': 'REMITTANCE_CUSTOMER_ID'
            }

        # Method 2: Parse bank description
        parsed = self.parse_bank_description(bank_txn.get('description', ''))

        # Try account number
        if parsed.get('account_number'):
            norm_acc = self.normalize(parsed['account_number'])
            if norm_acc in self.account_index:
                candidates.append({
                    'customer_id': self.account_index[norm_acc],
                    'confidence': 0.95,
                    'method': 'ACCOUNT_NUMBER'
                })

        # Try payment reference pattern
        if parsed.get('payment_ref'):
            for pattern, cust_id in self.ref_patterns:
                if re.match(pattern, parsed['payment_ref']):
                    candidates.append({
                        'customer_id': cust_id,
                        'confidence': 0.92,
                        'method': 'PAYMENT_REF_PATTERN'
                    })

        # Try name match
        if parsed.get('customer_name'):
            norm_name = self.normalize(parsed['customer_name'])
            if norm_name in self.name_index:
                candidates.append({
                    'customer_id': self.name_index[norm_name],
                    'confidence': 0.90,
                    'method': 'NAME_MATCH'
                })

        # Return best candidate or UNKNOWN
        if candidates:
            candidates.sort(key=lambda x: x['confidence'], reverse=True)
            return candidates[0]

        return {'customer_id': None, 'confidence': 0.0, 'method': 'UNKNOWN'}

    def parse_bank_description(self, description: str) -> dict:
        result = {}

        # Extract account number
        acc_match = re.search(r'A/?C[-:#]?\s*(\d+)', description, re.I)
        if acc_match:
            result['account_number'] = acc_match.group(1)

        # Extract payment reference
        ref_match = re.search(r'REF[-:#]?\s*([\w-]+)', description, re.I)
        if ref_match:
            result['payment_ref'] = ref_match.group(1)

        # Extract invoice numbers
        inv_matches = re.findall(r'INV[-:#]?\s*([\w-]+)', description, re.I)
        if inv_matches:
            result['invoice_numbers'] = inv_matches

        # Remaining text is customer name
        clean = description
        for pattern in [r'A/?C[-:#]?\s*\d+', r'REF[-:#]?\s*[\w-]+',
                        r'INV[-:#]?\s*[\w-]+', r'\$[\d,.]+']:
            clean = re.sub(pattern, '', clean, flags=re.I)
        clean = clean.strip()
        if clean and len(clean) > 2:
            result['customer_name'] = clean

        return result
```

### Customer Partitioner

```python
class CustomerPartitioner:
    def __init__(self, invoices: List[dict]):
        self.invoices_by_customer = defaultdict(list)
        for inv in invoices:
            self.invoices_by_customer[inv['customer_id']].append(inv)
        self.all_invoices = invoices

    def partition(self, banks: List[dict]) -> dict:
        partitions = defaultdict(lambda: {'banks': [], 'invoices': []})

        for bank in banks:
            cust_id = bank.get('customer_id') or 'UNKNOWN'
            partitions[cust_id]['banks'].append(bank)

        for cust_id, partition in partitions.items():
            if cust_id == 'UNKNOWN':
                partition['invoices'] = self.all_invoices.copy()
            else:
                partition['invoices'] = self.invoices_by_customer.get(cust_id, [])

        return dict(partitions)
```

### ILP Solver

```python
from ortools.linear_solver import pywraplp

def solve_partition(banks: List[dict], invoices: List[dict]) -> dict:
    solver = pywraplp.Solver.CreateSolver('SCIP')

    # Variables
    x = {}  # Binary match
    f = {}  # Flow amount
    u = {}  # Unallocated

    for i, bank in enumerate(banks):
        u[i] = solver.NumVar(0, bank['amount'], f'u_{i}')

        for j, invoice in enumerate(invoices):
            x[i, j] = solver.BoolVar(f'x_{i}_{j}')
            max_flow = min(bank['amount'], invoice['pending_amount'])
            f[i, j] = solver.NumVar(0, max_flow, f'f_{i}_{j}')

    # Constraint 1: Bank conservation
    for i, bank in enumerate(banks):
        solver.Add(
            sum(f[i, j] for j in range(len(invoices))) + u[i] == bank['amount']
        )

    # Constraint 2: Invoice capacity
    for j, invoice in enumerate(invoices):
        solver.Add(
            sum(f[i, j] for i in range(len(banks))) <= invoice['pending_amount']
        )

    # Constraint 3: Flow-match linkage
    for i, bank in enumerate(banks):
        for j in range(len(invoices)):
            solver.Add(f[i, j] <= bank['amount'] * x[i, j])

    # Objective
    objective = solver.Objective()
    UNALLOC_PENALTY = 0.01

    for i, bank in enumerate(banks):
        for j, invoice in enumerate(invoices):
            conf = calculate_confidence(bank, invoice)
            objective.SetCoefficient(f[i, j], conf)
        objective.SetCoefficient(u[i], -UNALLOC_PENALTY)

    objective.SetMaximization()
    solver.Solve()

    return extract_results(solver, banks, invoices, x, f, u)


def calculate_confidence(bank: dict, invoice: dict) -> float:
    score = 0.5  # Base (customer validated)

    # Amount match
    diff = abs(bank['amount'] - invoice['pending_amount'])
    if diff == 0:
        score += 0.3
    elif diff < bank['amount'] * 0.01:
        score += 0.2
    elif diff < bank['amount'] * 0.05:
        score += 0.1

    # Date proximity
    if bank.get('date') and invoice.get('due_date'):
        days = abs((bank['date'] - invoice['due_date']).days)
        if days <= 3:
            score += 0.15
        elif days <= 7:
            score += 0.10
        elif days <= 14:
            score += 0.05

    # Invoice reference in description
    if invoice.get('invoice_id') in bank.get('description', ''):
        score += 0.25

    return min(score, 1.0)


def extract_results(solver, banks, invoices, x, f, u) -> dict:
    results = {'matches': [], 'unallocated': []}

    for i, bank in enumerate(banks):
        for j, invoice in enumerate(invoices):
            if x[i, j].solution_value() > 0.5:
                results['matches'].append({
                    'bank_id': bank['id'],
                    'invoice_id': invoice['id'],
                    'amount': f[i, j].solution_value(),
                    'confidence': calculate_confidence(bank, invoice)
                })

        unalloc = u[i].solution_value()
        if unalloc > 0.01:
            results['unallocated'].append({
                'bank_id': bank['id'],
                'amount': unalloc
            })

    return results
```

### Complete Pipeline

```python
class CashReconciliationEngine:
    def __init__(self, customer_master: List[dict], invoices: List[dict]):
        self.identifier = CustomerIdentifier(customer_master)
        self.partitioner = CustomerPartitioner(invoices)

    def reconcile(self, banks: List[dict], remittances: List[dict] = None) -> dict:
        # Build remittance lookup
        remittance_lookup = {}
        if remittances:
            for rem in remittances:
                key = (rem.get('reference'), rem.get('amount'))
                remittance_lookup[key] = rem

        # STAGE 2: Identify customers
        identified_banks = []
        for bank in banks:
            rem_key = (bank.get('reference'), bank.get('amount'))
            remittance = remittance_lookup.get(rem_key)

            identification = self.identifier.identify(bank, remittance)

            identified_banks.append({
                **bank,
                'customer_id': identification['customer_id'],
                'customer_confidence': identification['confidence'],
                'customer_method': identification['method']
            })

        # STAGE 3: Partition
        partitions = self.partitioner.partition(identified_banks)

        # STAGE 4: Solve each partition
        all_matches = []
        all_unallocated = []
        all_exceptions = []

        for cust_id, partition in partitions.items():
            if not partition['banks']:
                continue

            if not partition['invoices']:
                for bank in partition['banks']:
                    all_exceptions.append({
                        'bank': bank,
                        'reason': 'NO_INVOICES_FOR_CUSTOMER'
                    })
                continue

            result = solve_partition(partition['banks'], partition['invoices'])

            for match in result['matches']:
                match['customer_id'] = cust_id
                all_matches.append(match)

            for unalloc in result['unallocated']:
                unalloc['customer_id'] = cust_id
                all_unallocated.append(unalloc)

        return {
            'matches': all_matches,
            'unallocated': all_unallocated,
            'exceptions': all_exceptions
        }
```

---

## Example Walkthrough

### Input

```
Banks:
  B1: $10,000, desc="ACME CORP REF:AC-123"
  B2: $8,000,  desc="PAYMENT A/C:90005678"
  B3: $5,000,  desc="WIRE TRANSFER"

Invoices:
  I1: $6,000,  customer=CUST_A
  I2: $4,000,  customer=CUST_A
  I3: $8,000,  customer=CUST_B
  I4: $5,000,  customer=CUST_B

Customer Master:
  CUST_A: name="Acme Corp", ref_patterns=["AC-*"], account_nums=["90001234"]
  CUST_B: name="Beta LLC", account_nums=["90005678"]
```

### Stage 2: Identification

```
B1: "ACME CORP REF:AC-123"
    → Parsed: customer_name="ACME CORP", payment_ref="AC-123"
    → Pattern "AC-*" matches CUST_A
    → Result: customer_id=CUST_A, confidence=0.92

B2: "PAYMENT A/C:90005678"
    → Parsed: account_number="90005678"
    → Account matches CUST_B
    → Result: customer_id=CUST_B, confidence=0.95

B3: "WIRE TRANSFER"
    → Parsed: (nothing extracted)
    → Result: customer_id=None (UNKNOWN), confidence=0.0
```

### Stage 3: Partitioning

```
CUST_A:  Banks=[B1], Invoices=[I1, I2]
CUST_B:  Banks=[B2], Invoices=[I3, I4]
UNKNOWN: Banks=[B3], Invoices=[I1, I2, I3, I4]
```

### Stage 4: ILP Solving

```
Partition CUST_A:
  B1 ($10,000) must allocate to I1 ($6,000) + I2 ($4,000)
  Solution: B1 → I1: $6,000, B1 → I2: $4,000

Partition CUST_B:
  B2 ($8,000) can allocate to I3 ($8,000) or I4 ($5,000)
  Solution: B2 → I3: $8,000 (exact match preferred)

Partition UNKNOWN:
  B3 ($5,000) can match any invoice
  Best match: I4 ($5,000) - exact amount
  Solution: B3 → I4: $5,000 (low confidence, needs review)
```

### Output

```
Matches:
  B1 → I1: $6,000 (CUST_A, conf=0.85)
  B1 → I2: $4,000 (CUST_A, conf=0.85)
  B2 → I3: $8,000 (CUST_B, conf=0.95)
  B3 → I4: $5,000 (UNKNOWN, conf=0.50, needs_review=True)

Unallocated: (none)
Exceptions: (none)
```

---

## Edge Cases

### 1. No Invoices for Identified Customer

```
Bank identified as CUST_C, but CUST_C has no open invoices
→ Exception: NO_INVOICES_FOR_CUSTOMER
→ Manual review required
```

### 2. Amount Doesn't Match Any Combination

```
Bank: $7,500
Customer invoices: $5,000, $4,000 (no subset sums to $7,500)
→ ILP allocates $5,000 + partial $2,500 to one invoice
→ Or: $7,500 unallocated if no valid match
→ Flag for review
```

### 3. Multiple Customers with Same Confidence

```
Bank matches both CUST_A and CUST_B with same confidence
→ Return candidates list
→ Manual selection required
```

### 4. UNKNOWN Partition Conflicts

```
B3 (UNKNOWN) matches I4
But I4 already matched by B2 (CUST_B)
→ UNKNOWN partition runs AFTER known partitions
→ Remove already-matched invoices from UNKNOWN
```

---

## Performance Optimization

### Parallel Partition Solving

```python
from concurrent.futures import ProcessPoolExecutor

def reconcile_parallel(partitions: dict) -> dict:
    with ProcessPoolExecutor() as executor:
        futures = {
            cust_id: executor.submit(solve_partition, p['banks'], p['invoices'])
            for cust_id, p in partitions.items()
            if p['banks'] and p['invoices']
        }

        results = {cust_id: f.result() for cust_id, f in futures.items()}

    return merge_results(results)
```

### Problem Size Reduction

```
Original: 10,000 banks × 50,000 invoices = 500M pairs

After partitioning (1,000 customers):
  Average: 10 banks × 50 invoices = 500 pairs per partition
  Total: 1,000 × 500 = 500K pairs

Reduction: 1000x smaller problem
```

---

## Unassigned Payments

### When Unassigned Happens

| Scenario | Example | Result |
|----------|---------|--------|
| No invoices for customer | Customer identified but has no open invoices | 100% unassigned |
| Amount mismatch | Bank $7,500 but invoices are $5,000 + $4,000 | $7,500 unassigned (no valid combo) |
| Invoices already paid | All customer invoices already closed | 100% unassigned |
| Low confidence | No matches above threshold | Unassigned by design |

### Unassigned Is Information, Not Failure

```
Unassigned payment tells us:
  - Customer known → "Unapplied Cash" (credit balance)
  - Customer unknown → "Exception" (needs manual review)

Both are VALID outcomes. Don't force bad matches to avoid them.
```

---

## Output Categories

```
┌─────────────────────────────────────────────────────────────────┐
│                      MATCH OUTCOMES                             │
├─────────────────┬───────────────────────────────────────────────┤
│                 │                                               │
│  MATCHED        │  Bank fully allocated to invoice(s)          │
│  (Confident)    │  Confidence ≥ threshold                      │
│                 │  → Auto-apply to invoices                    │
│                 │                                               │
├─────────────────┼───────────────────────────────────────────────┤
│                 │                                               │
│  PARTIALLY      │  Bank partially allocated                     │
│  MATCHED        │  Some amount unassigned                       │
│                 │  → Apply matched portion                     │
│                 │  → Remainder to unapplied cash               │
│                 │                                               │
├─────────────────┼───────────────────────────────────────────────┤
│                 │                                               │
│  UNAPPLIED      │  Customer known, but no matching invoices    │
│  CASH           │  → Credit balance for customer               │
│                 │  → Will auto-apply to future invoices        │
│                 │                                               │
├─────────────────┼───────────────────────────────────────────────┤
│                 │                                               │
│  EXCEPTION      │  Customer unknown, no confident matches      │
│                 │  → Manual review queue                       │
│                 │  → Human assigns customer + invoices         │
│                 │                                               │
└─────────────────┴───────────────────────────────────────────────┘
```

---

## Revised Decision Flow

```
Bank Payment Arrives
        │
        ▼
┌───────────────────┐
│ Identify Customer │
└─────────┬─────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
 KNOWN       UNKNOWN
    │           │
    ▼           ▼
┌─────────┐  ┌─────────────┐
│ ILP     │  │ Low-conf    │
│ Match   │  │ ILP or      │
│         │  │ Exception   │
└────┬────┘  └──────┬──────┘
     │              │
     ▼              ▼
┌─────────────────────────┐
│ Matched? │ Unassigned?  │
├──────────┼──────────────┤
│ Yes      │ No           │ → FULLY MATCHED (auto-apply)
│ Yes      │ Yes          │ → PARTIAL + UNAPPLIED CASH
│ No       │ Yes (known)  │ → UNAPPLIED CASH
│ No       │ Yes (unknown)│ → EXCEPTION QUEUE
└──────────┴──────────────┘
```

---

## Revised ILP Solver (With Threshold)

```python
from ortools.linear_solver import pywraplp

MIN_CONFIDENCE = 0.5  # Critical threshold

def solve_partition(banks: List[dict], invoices: List[dict]) -> dict:
    solver = pywraplp.Solver.CreateSolver('SCIP')

    # Variables (only for confident pairs)
    x = {}  # Binary match
    f = {}  # Flow amount
    u = {}  # Unallocated (acceptable outcome)

    for i, bank in enumerate(banks):
        u[i] = solver.NumVar(0, bank['amount'], f'u_{i}')

        for j, invoice in enumerate(invoices):
            conf = calculate_confidence(bank, invoice)

            # CRITICAL: Skip low-confidence pairs
            if conf < MIN_CONFIDENCE:
                continue

            x[i, j] = solver.BoolVar(f'x_{i}_{j}')
            max_flow = min(bank['amount'], invoice['pending_amount'])
            f[i, j] = solver.NumVar(0, max_flow, f'f_{i}_{j}')

    # Constraint 1: Bank conservation (includes unallocated)
    for i, bank in enumerate(banks):
        flow_sum = sum(f[i, j] for j in range(len(invoices)) if (i, j) in f)
        solver.Add(flow_sum + u[i] == bank['amount'])

    # Constraint 2: Invoice capacity
    for j, invoice in enumerate(invoices):
        flow_sum = sum(f[i, j] for i in range(len(banks)) if (i, j) in f)
        solver.Add(flow_sum <= invoice['pending_amount'])

    # Constraint 3: Flow-match linkage
    for (i, j) in f:
        solver.Add(f[i, j] <= banks[i]['amount'] * x[i, j])

    # Objective: Maximize confident flow (NO penalty for unallocated)
    objective = solver.Objective()
    for (i, j) in f:
        conf = calculate_confidence(banks[i], invoices[j])
        objective.SetCoefficient(f[i, j], conf)
    objective.SetMaximization()

    solver.Solve()

    return extract_results(solver, banks, invoices, x, f, u)


def extract_results(solver, banks, invoices, x, f, u) -> dict:
    results = {
        'matched': [],
        'partially_matched': [],
        'unapplied_cash': [],
        'exceptions': []
    }

    for i, bank in enumerate(banks):
        matches_for_bank = []
        total_matched = 0

        for j, invoice in enumerate(invoices):
            if (i, j) in x and x[i, j].solution_value() > 0.5:
                flow = f[i, j].solution_value()
                matches_for_bank.append({
                    'invoice_id': invoice['id'],
                    'amount': flow,
                    'confidence': calculate_confidence(bank, invoice)
                })
                total_matched += flow

        unalloc = u[i].solution_value()

        if matches_for_bank and unalloc < 0.01:
            # Fully matched
            results['matched'].append({
                'bank_id': bank['id'],
                'total_amount': bank['amount'],
                'allocations': matches_for_bank
            })
        elif matches_for_bank and unalloc >= 0.01:
            # Partially matched
            results['partially_matched'].append({
                'bank_id': bank['id'],
                'matched_amount': total_matched,
                'unallocated_amount': unalloc,
                'allocations': matches_for_bank
            })
        elif bank.get('customer_id'):
            # Customer known but no matches - unapplied cash
            results['unapplied_cash'].append({
                'bank_id': bank['id'],
                'customer_id': bank['customer_id'],
                'amount': bank['amount']
            })
        else:
            # Unknown customer, no matches - exception
            results['exceptions'].append({
                'bank_id': bank['id'],
                'amount': bank['amount'],
                'reason': 'NO_CONFIDENT_MATCH'
            })

    return results
```

---

## Unapplied Cash Handling

When a payment is identified to a customer but cannot be matched to invoices:

```python
class UnappliedCashManager:
    """
    Manages unapplied cash (credit balances) for customers.
    """

    def __init__(self):
        self.unapplied_balances = defaultdict(list)

    def add_unapplied(self, customer_id: str, bank_id: str, amount: float):
        """Record unapplied cash for a customer."""
        self.unapplied_balances[customer_id].append({
            'bank_id': bank_id,
            'amount': amount,
            'date': datetime.now(),
            'status': 'PENDING'
        })

    def apply_to_new_invoice(self, customer_id: str, invoice: dict) -> List[dict]:
        """
        When new invoice arrives, check if customer has unapplied cash.
        Returns list of applications made.
        """
        applications = []
        remaining = invoice['amount']

        for unapplied in self.unapplied_balances[customer_id]:
            if unapplied['status'] != 'PENDING':
                continue
            if remaining <= 0:
                break

            apply_amount = min(unapplied['amount'], remaining)

            applications.append({
                'invoice_id': invoice['id'],
                'from_bank_id': unapplied['bank_id'],
                'amount': apply_amount
            })

            unapplied['amount'] -= apply_amount
            remaining -= apply_amount

            if unapplied['amount'] <= 0:
                unapplied['status'] = 'APPLIED'

        return applications
```

---

## Exception Queue Handling

For payments that cannot be auto-matched:

```python
class ExceptionQueue:
    """
    Manages payments that need manual review.
    """

    def __init__(self):
        self.exceptions = []

    def add_exception(self, bank: dict, reason: str, candidates: List[dict] = None):
        """Add payment to exception queue."""
        self.exceptions.append({
            'bank': bank,
            'reason': reason,
            'candidates': candidates or [],
            'created_at': datetime.now(),
            'status': 'PENDING'
        })

    def resolve(self, bank_id: str, resolution: dict):
        """
        Human resolves exception.

        resolution: {
            'customer_id': str,
            'allocations': [{'invoice_id': str, 'amount': float}, ...]
        }
        """
        for exc in self.exceptions:
            if exc['bank']['id'] == bank_id:
                exc['resolution'] = resolution
                exc['status'] = 'RESOLVED'
                exc['resolved_at'] = datetime.now()

                # Learn from this resolution for future
                self.learn_from_resolution(exc)
                break

    def learn_from_resolution(self, exception: dict):
        """
        Capture patterns from human resolution for future matching.
        """
        # Example: If human identified customer from bank description,
        # add that pattern to customer master
        pass
```

---

## Summary: Key Principles

| Principle | Implementation |
|-----------|----------------|
| Correctness over completeness | Confidence threshold filters bad matches |
| Unassigned is acceptable | No penalty in objective function |
| Clear outcomes | 4 categories: Matched, Partial, Unapplied, Exception |
| Human in the loop | Exception queue for uncertain cases |
| Learn from feedback | Resolution patterns improve future matching |

---

## Next Steps

1. Implement customer identification module
2. Build partition logic
3. Implement ILP solver with OR-Tools
4. Add parallel processing for partitions
5. Build exception handling workflow
6. Add unapplied cash management
7. Add feedback loop for learning from resolutions
