# Cash Reconciliation Algorithm

## Overview

This document describes the complete cash reconciliation algorithm for matching bank transactions to customer invoices using **remittances as an intermediary layer**. The system uses a three-way matching approach:

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│     BANK     │◄───────►│  REMITTANCE  │◄───────►│   INVOICE    │
│ TRANSACTION  │         │   (Header +  │         │              │
│              │  Match  │  Line Items) │  Match  │              │
│              │   by    │              │   by    │              │
│              │ REF +   │              │ INV #   │              │
│              │ CUST    │              │ + CUST  │              │
└──────────────┘         └──────────────┘         └──────────────┘
```

**Output Categories:**
1. **Auto-Approved**: Remittance-backed or reference-based matches with no exceptions
2. **Exception Queue**: Matches found but validation issues detected
3. **Suggestions**: No remittance/reference, algorithm suggests based on uniqueness/flow
4. **Manual**: No confident match, human assigns from scratch

---

## Table of Contents

1. [The Problem](#the-problem)
2. [Core Principles](#core-principles)
3. [Remittance Schema](#remittance-schema)
4. [Matching vs Validation](#matching-vs-validation)
5. [Exception Taxonomy](#exception-taxonomy)
6. [Algorithm Pipeline](#algorithm-pipeline)
7. [Phase 1: Remittance-Backed Matching](#phase-1-remittance-backed-matching)
8. [Phase 2: Direct Reference Matching](#phase-2-direct-reference-matching)
9. [Phase 3: Suggestion Generation](#phase-3-suggestion-generation)
10. [Flow Network for Suggestions](#flow-network-for-suggestions)
11. [All-or-Nothing Enforcement](#all-or-nothing-enforcement)
12. [Confidence Tiers](#confidence-tiers)
13. [Complete Example](#complete-example)
14. [Data Model](#data-model)
15. [Configuration Parameters](#configuration-parameters)
16. [Summary](#summary)

---

## The Problem

We receive money from customers. For each bank transaction, we need to answer:

| Question | What we need to determine |
|----------|--------------------------|
| **WHO paid?** | Customer identification |
| **FOR WHAT?** | Which invoice(s) |
| **HOW MUCH?** | Amount per invoice |

### Constraints

- A bank transaction can pay one or more invoices
- An invoice can receive multiple payments (partial payments allowed)
- An invoice cannot receive more than its pending amount
- Every bank transaction must be fully accounted for (matched or exception)

### The Challenge

Directly matching bank transactions to invoices is difficult because:
- Bank descriptions are often vague or inconsistent
- Customers may combine multiple invoice payments
- Amounts may not match exactly (bank fees, FX, partial payments)

**Solution**: Use **remittances** as an intermediary layer. Remittances are payment advice documents from customers that explicitly state what they're paying for.

---

## Core Principles

### 1. Matching is Binary

Matching criteria are strict and deterministic. Either entities match or they don't. No scoring, no ambiguity.

```
Bank ↔ Remittance:  Reference + Customer (both required)
Remittance ↔ Invoice:  Invoice Number + Customer (both required)
```

### 2. Validation is Separate from Matching

After a match is established, we validate for exceptions. Validation failures don't prevent matching—they flag the match for human review.

| Aspect | Matching | Validation |
|--------|----------|------------|
| **Purpose** | Identify which entities belong together | Check if the match is clean |
| **Criteria** | Reference + Customer | Amount, Date, Duplicates, etc. |
| **Result** | Binary: Match or No Match | Exceptions list (can be empty) |
| **Failure** | Goes to next phase | Goes to Exception Queue |

### 3. Exceptions Block Auto-Approval

If ANY exception is detected, the match goes to the Exception Queue. Auto-approval only happens when the match is completely clean.

```
IF exceptions.is_empty():
    → AUTO-APPROVE
ELSE:
    → EXCEPTION QUEUE (do NOT auto-approve)
```

### 4. Amount is NEVER a Matching Signal

Amount and date are validation checks, not matching criteria. They're unreliable for matching:
- Multiple invoices can have the same amount
- Bank fees can reduce received amount
- Customers pay early/late unpredictably

### 5. Exception is a Valid Outcome

Sending uncertain payments to manual review is NOT failure. Wrong auto-matches ARE failure.

### 6. All-or-Nothing for Suggestions

A suggestion must allocate the entire bank amount. Partial suggestions are confusing and error-prone.

---

## Remittance Schema

Remittances have two levels of data:

### Payment-Level (Header) Fields

These describe the one payment transaction:

| Field | Description | Example |
|-------|-------------|---------|
| `payer_name` | Customer/company name | "ACME Corporation" |
| `payer_id` | Customer identifier (optional) | "CUST-001" |
| `payment_date` | Date of payment | 2024-01-15 |
| `payment_amount_total` | Total payment amount | $10,000.00 |
| `currency` | Payment currency | USD |
| `payment_method` | How payment was made | ACH, Wire, Check, Card, Lockbox |
| `payment_reference` | Unique reference (UTR, bank ref, check #) | "RM-2024-001" |

### Invoice-Level (Line Items) Fields

These describe how the payment is applied:

| Field | Description | Example |
|-------|-------------|---------|
| `invoice_number` | Invoice being paid | "INV-001" |
| `invoice_date` | Original invoice date (optional) | 2024-01-01 |
| `invoice_amount_original` | Original invoice amount (optional) | $6,000.00 |
| `amount_paid` | Amount applied to this invoice | $5,500.00 |
| `remaining_balance` | Balance after payment (optional) | $500.00 |
| `deduction_amount` | Any deductions taken (optional) | $100.00 |
| `deduction_reason` | Reason for deduction (optional) | "Early payment discount" |
| `credit_note_reference` | Related credit note (optional) | "CN-001" |

---

## Matching vs Validation

### Bank ↔ Remittance Matching Rule

```
MATCH if and only if:
    1. remittance.payment_reference FOUND IN bank.description
    AND
    2. remittance.payer_id == bank.customer_id

Both REQUIRED. No scoring. No exceptions.
```

**After match is established**, validate:
- Amount difference within tolerance?
- Date difference within tolerance?
- Multiple remittances for same bank?

### Remittance Line ↔ Invoice Matching Rule

```
MATCH if and only if:
    1. Invoice with line_item.invoice_number EXISTS
    AND
    2. invoice.customer_id == remittance.payer_id

Both REQUIRED. No scoring. No exceptions.
```

**After match is established**, validate:
- Invoice already fully paid? (duplicate)
- Amount paid > invoice pending? (overpayment)
- Line items sum to remittance total?

---

## Exception Taxonomy

### Bank ↔ Remittance Validation Exceptions

| Exception | Trigger | Severity |
|-----------|---------|----------|
| `AMOUNT_MISMATCH` | \|bank.amount - remittance.total\| > tolerance | CRITICAL |
| `DATE_DISCREPANCY` | \|bank.date - remittance.payment_date\| > 14 days | WARNING |
| `MULTIPLE_REMITTANCES_ONE_BANK` | 2+ remittances match same bank | CRITICAL |
| `MULTIPLE_BANKS_ONE_REMITTANCE` | 1 remittance matches 2+ banks | CRITICAL |

### Remittance Line ↔ Invoice Validation Exceptions

| Exception | Trigger | Severity |
|-----------|---------|----------|
| `INVOICE_NOT_FOUND` | Referenced invoice doesn't exist | CRITICAL |
| `CUSTOMER_MISMATCH` | Invoice belongs to different customer | CRITICAL |
| `DUPLICATE_PAYMENT` | Invoice already fully paid (pending = 0) | CRITICAL |
| `OVERPAYMENT` | line.amount_paid > invoice.pending | WARNING |
| `CREDIT_NOTE_NOT_FOUND` | Referenced credit note doesn't exist | WARNING |

### Internal Consistency Exceptions

| Exception | Trigger | Severity |
|-----------|---------|----------|
| `LINE_ITEMS_SUM_MISMATCH` | Σ(line.amount_paid) + Σ(deductions) ≠ remittance.total | CRITICAL |
| `DEDUCTION_WITHOUT_REASON` | deduction_amount > 0 but no deduction_reason | WARNING |

### Orphan Exceptions

| Exception | Trigger | Severity |
|-----------|---------|----------|
| `ORPHAN_REMITTANCE_NO_BANK` | Remittance has no matching bank | WARNING |
| `ORPHAN_BANK_NO_REMITTANCE` | Bank has no matching remittance (goes to Phase 2) | INFO |

### Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | Blocks auto-approval | Must go to Exception Queue |
| **WARNING** | Flags for review | Goes to Exception Queue but may be acceptable |
| **INFO** | Logged only | Does not affect auto-approval |

---

## Algorithm Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 0: DATA INGESTION & NORMALIZATION                                    │
│                                                                              │
│  - Parse banks, remittances, invoices                                       │
│  - Identify customer from bank descriptions                                  │
│  - Normalize schemas                                                         │
│  - Build indexes:                                                            │
│      • invoices by invoice_number                                           │
│      • remittances by payment_reference                                     │
│      • banks by customer_id                                                 │
│                                                                              │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 1: REMITTANCE-BACKED MATCHING (Auto-Approval with Remittance)        │
│                                                                              │
│  1A. Bank ↔ Remittance Matching (by Reference + Customer)                   │
│  1B. Bank ↔ Remittance Validation (amount, date)                            │
│  1C. Remittance Line ↔ Invoice Matching & Validation                        │
│  1D. Decision: AUTO-APPROVE or EXCEPTION QUEUE                              │
│                                                                              │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 2: DIRECT REFERENCE MATCHING (Banks without remittance)              │
│                                                                              │
│  - Extract invoice references from bank description                         │
│  - Match directly to invoices                                                │
│  - AUTO-APPROVE if references found and matched                             │
│                                                                              │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 3: SUGGESTION GENERATION (Remaining unmatched banks)                 │
│                                                                              │
│  - Uniqueness checks (high confidence)                                       │
│  - Flow network optimization (medium/low confidence)                        │
│  - Generate suggestions with alternatives                                    │
│                                                                              │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  OUTPUT                                                                      │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                                │
│  │  AUTO-APPROVED   │  │    EXCEPTION     │                                │
│  │                  │  │      QUEUE       │                                │
│  │  • Remittance-   │  │                  │                                │
│  │    backed        │  │  • Matched but   │                                │
│  │  • Reference-    │  │    has issues    │                                │
│  │    based         │  │  • Grouped by    │                                │
│  │                  │  │    exception     │                                │
│  │  Apply now       │  │    type          │                                │
│  └──────────────────┘  └──────────────────┘                                │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                                │
│  │   SUGGESTION     │  │     MANUAL       │                                │
│  │      QUEUE       │  │      QUEUE       │                                │
│  │                  │  │                  │                                │
│  │  • No remittance │  │  • No confident  │                                │
│  │  • No reference  │  │    match found   │                                │
│  │  • Algorithm     │  │  • Human assigns │                                │
│  │    suggestions   │  │    from scratch  │                                │
│  │  • With          │  │                  │                                │
│  │    confidence    │  │                  │                                │
│  └──────────────────┘  └──────────────────┘                                │
│                                                                              │
│  ┌──────────────────┐                                                       │
│  │     ORPHAN       │                                                       │
│  │   REMITTANCES    │                                                       │
│  │                  │                                                       │
│  │  • No matching   │                                                       │
│  │    bank found    │                                                       │
│  │  • Investigate   │                                                       │
│  └──────────────────┘                                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Remittance-Backed Matching

### Phase 1A: Bank ↔ Remittance Matching

```
FOR each remittance:
    FOR each bank:

        # MATCHING (binary - both required)
        reference_found = remittance.payment_reference IN bank.description
        customer_matches = remittance.payer_id == bank.customer_id

        IF reference_found AND customer_matches:
            → MATCH ESTABLISHED
            Link bank ↔ remittance

Check for conflicts:
    IF multiple remittances → same bank: flag MULTIPLE_REMITTANCES_ONE_BANK
    IF multiple banks → same remittance: flag MULTIPLE_BANKS_ONE_REMITTANCE
    IF remittance has no bank match: flag ORPHAN_REMITTANCE_NO_BANK
```

### Phase 1B: Bank ↔ Remittance Validation

```
FOR each linked (bank, remittance) pair:

    exceptions = []

    # Amount validation
    IF |bank.amount - remittance.total| > AMOUNT_TOLERANCE:
        exceptions.add(AMOUNT_MISMATCH, {
            bank_amount: bank.amount,
            remittance_amount: remittance.total,
            difference: bank.amount - remittance.total
        })

    # Date validation
    IF |bank.date - remittance.payment_date| > 14 days:
        exceptions.add(DATE_DISCREPANCY, {
            bank_date: bank.date,
            remittance_date: remittance.payment_date,
            days_apart: |bank.date - remittance.payment_date|
        })
```

### Phase 1C: Remittance Line ↔ Invoice Matching & Validation

```
FOR each linked (bank, remittance) pair:
    FOR each line_item in remittance.line_items:

        # MATCHING (binary - both required)
        invoice = lookup(line_item.invoice_number)

        IF invoice is NULL:
            exceptions.add(INVOICE_NOT_FOUND, {
                invoice_number: line_item.invoice_number
            })
            CONTINUE

        IF invoice.customer_id != remittance.payer_id:
            exceptions.add(CUSTOMER_MISMATCH, {
                invoice_number: line_item.invoice_number,
                invoice_customer: invoice.customer_id,
                remittance_payer: remittance.payer_id
            })
            CONTINUE

        → MATCH ESTABLISHED
        Link line_item ↔ invoice

        # VALIDATION (after match)
        IF invoice.pending == 0:
            exceptions.add(DUPLICATE_PAYMENT, {
                invoice_number: line_item.invoice_number,
                message: "Invoice already fully paid"
            })
        ELIF line_item.amount_paid > invoice.pending:
            exceptions.add(OVERPAYMENT, {
                invoice_number: line_item.invoice_number,
                invoice_pending: invoice.pending,
                amount_paid: line_item.amount_paid,
                overpayment: line_item.amount_paid - invoice.pending
            })

    # Internal consistency validation
    line_items_sum = SUM(line_items.amount_paid)
    deductions_sum = SUM(line_items.deduction_amount)

    IF |line_items_sum + deductions_sum - remittance.total| > 0.01:
        exceptions.add(LINE_ITEMS_SUM_MISMATCH, {
            line_items_sum: line_items_sum,
            deductions_sum: deductions_sum,
            remittance_total: remittance.total
        })
```

### Phase 1D: Decision

```
FOR each (bank, remittance, invoice_matches, exceptions):

    IF exceptions.is_empty():
        ─────────────────────────────────────────────────────────
        │  AUTO-APPROVE                                         │
        │  - Apply all allocations                              │
        │  - Update invoice.pending amounts                     │
        │  - Mark bank as MATCHED                               │
        │  - Mark remittance as MATCHED                         │
        ─────────────────────────────────────────────────────────

    ELSE:
        ─────────────────────────────────────────────────────────
        │  EXCEPTION QUEUE                                      │
        │  - Do NOT apply allocations                           │
        │  - Attach all exceptions with details                 │
        │  - Human resolves specific issues                     │
        ─────────────────────────────────────────────────────────
```

---

## Phase 2: Direct Reference Matching

For banks that didn't match to a remittance (no reference found, or no matching remittance exists), check if the bank description contains invoice references directly.

### What Qualifies for Auto-Approval

Bank transactions where invoice references are found directly in the description.

Examples of valid references:
- `"ACME CORP INV-001 INV-002"` → References: INV-001, INV-002
- `"PAYMENT FOR INVOICE #1234"` → Reference: 1234
- `"BETA LLC REF:INV-2024-001"` → Reference: INV-2024-001

### Algorithm

```
FOR each unmatched bank:

    references = extract_invoice_references(bank.description)

    IF references NOT EMPTY:

        allocations = []
        remaining = bank.amount

        FOR each ref IN references:
            invoice = lookup_invoice(ref, customer's open invoices)

            IF invoice AND invoice.pending > 0:
                alloc = min(remaining, invoice.pending)
                allocations.ADD({invoice, alloc})
                remaining -= alloc
                invoice.pending -= alloc

        IF allocations NOT EMPTY:
            → AUTO-APPROVE (reference-based)

            IF remaining > 0:
                → Excess goes to suggestion phase

    ELSE:
        → Goes to Phase 3 (Suggestion Generation)
```

### Reference Extraction Patterns

```
Pattern 1: INV-XXX, INV-XXXX-XXX
Regex: INV[-:#\s]*([\w-]+)

Pattern 2: Invoice #XXX, Invoice: XXX
Regex: INVOICE\s*[:#]?\s*([\w-]+)

Pattern 3: Custom patterns per customer (configurable)
```

---

## Phase 3: Suggestion Generation

Banks without remittance matches AND without direct references go through suggestion generation.

### Step 1: Uniqueness Checks (High Confidence)

Before using the flow network, check for unique matches:

#### Check 1: Single Invoice

```
IF customer has only ONE open invoice:
    → Suggest that invoice
    → Confidence: 95%
    → Reason: "Only one open invoice for this customer"
```

#### Check 2: Unique Amount

```
IF exactly ONE invoice matches the bank amount:
    → Suggest that invoice
    → Confidence: 90%
    → Reason: "Only invoice with amount $X"
```

#### Check 3: Unique Combination

```
IF exactly ONE combination of invoices sums to bank amount:
    → Suggest that combination
    → Confidence: 85%
    → Reason: "Only combination summing to $X"
```

### Step 2: Flow Network (Medium/Low Confidence)

For banks that don't have unique matches, use flow optimization.

---

## Flow Network for Suggestions

### Why Use a Flow Network?

When multiple banks compete for the same invoices, we need to find an optimal assignment that:
- Respects invoice capacity (can't overpay)
- Maximizes overall confidence
- Handles multi-invoice allocations

### Network Structure

```
SOURCE                                                        SINK
   │                                                           ▲
   │ bank.amount                              invoice.pending  │
   ▼                                                           │
┌──────┐                                          ┌──────┐    │
│  B1  │────────────────────────────────────────▶│  I1  │────┘
└──────┘                                          └──────┘
   │        cost = 1 - confidence
   │
   │         ┌──────┐
   └────────▶│  I2  │────────────────────────────────────────▶
             └──────┘

   │
   ▼
┌──────────┐
│  REJECT  │─────────────────────────────────────────────────▶
└──────────┘
     ▲
     │
     cost = REJECT_PENALTY (high)
```

### Edge Definitions

| Edge | Capacity | Cost |
|------|----------|------|
| SOURCE → Bank | bank.amount | 0 |
| Bank → Invoice | min(bank.amount, invoice.pending) | 1 - confidence |
| Bank → REJECT | bank.amount | 0.80 (high penalty) |
| Invoice → SINK | invoice.pending | 0 |
| REJECT → SINK | ∞ | 0 |

**Note**: Bank → Invoice edges are only created if confidence ≥ 0.40 (minimum threshold).

### Confidence Calculation for Flow Edges

```
confidence = 0

# Amount match (50% weight)
amount_diff = |bank.amount - invoice.pending| / max(bank, invoice)
IF amount_diff == 0:     amount_score = 1.00
ELIF amount_diff <= 1%:  amount_score = 0.90
ELIF amount_diff <= 5%:  amount_score = 0.70
ELIF amount_diff <= 10%: amount_score = 0.50
ELIF amount_diff <= 20%: amount_score = 0.30
ELSE:                    amount_score = 0.10

confidence += 0.50 × amount_score

# Date proximity (25% weight)
days_apart = |bank.date - invoice.due_date|
IF days_apart <= 7:      date_score = 1.00
ELIF days_apart <= 14:   date_score = 0.70
ELIF days_apart <= 30:   date_score = 0.40
ELSE:                    date_score = 0.10

confidence += 0.25 × date_score

# Base score (25% weight)
confidence += 0.25 × 0.50

RETURN confidence
```

### Solving the Flow

Use min-cost max-flow algorithm:

1. Find shortest (cheapest) augmenting path from SOURCE to SINK
2. Push maximum flow along that path
3. Repeat until no more augmenting paths exist

This naturally prefers high-confidence matches (lower cost).

---

## All-or-Nothing Enforcement

### The Problem

Flow networks can produce **partial allocations**:

```
Bank B1: $10,000
Invoice I1: $7,000 (only option)

Flow result:
  B1 → I1: $7,000
  B1 → REJECT: $3,000

This is a PARTIAL allocation - bad for suggestions!
```

### The Solution: Iterative Elimination

```
remaining_banks = all banks needing suggestions

WHILE remaining_banks NOT EMPTY:

    1. Build and solve flow network

    2. Classify each bank:
       - FULLY_MATCHED: 100% flows to invoices
       - FULLY_REJECTED: 100% flows to REJECT
       - PARTIAL: Split between invoices and REJECT

    3. Process FULLY_MATCHED:
       - Create suggestion
       - Remove from remaining_banks
       - Reduce invoice capacities

    4. Process FULLY_REJECTED:
       - Add to manual queue
       - Remove from remaining_banks

    5. Handle PARTIAL:
       IF no progress made (no FULLY_MATCHED):
           - Find worst partial (lowest confidence)
           - Force it to manual queue
           - Remove from remaining_banks
           - Loop again (others may now fully match)
```

### Why This Works

- Each iteration either produces suggestions or identifies manual cases
- Removing "problem" banks lets others fully match
- Algorithm always terminates
- No partial suggestions ever produced

---

## Confidence Tiers

### Suggestion Types and Confidence

| Match Type | Confidence | Tier | Description |
|------------|------------|------|-------------|
| SINGLE_INVOICE | 95% | HIGH ★★★ | Only one open invoice exists |
| UNIQUE_AMOUNT | 90% | HIGH ★★★ | Only one invoice has this amount |
| UNIQUE_COMBINATION | 85% | HIGH ★★★ | Only one subset sums to amount |
| FLOW_MATCH (good) | 70-84% | MEDIUM ★★☆ | Best match from flow optimization |
| FLOW_MATCH (weak) | 50-69% | LOW ★☆☆ | Possible match but weak evidence |
| Below threshold | <50% | NONE | No suggestion, manual only |

### UI Treatment by Tier

| Tier | Visual | Recommended Action |
|------|--------|-------------------|
| HIGH ★★★ | Green highlight | Quick approve |
| MEDIUM ★★☆ | Yellow highlight | Review before approving |
| LOW ★☆☆ | Gray/muted | Likely needs correction |
| NONE | No suggestion shown | Manual assignment required |

---

## Complete Example

### Input

```
Banks:
  B1: $10,000  "ACME CORP REF:RM-001"        customer=ACME
  B2: $8,000   "BETA LLC REF:RM-002"         customer=BETA
  B3: $7,500   "ACME CORP PAYMENT"           customer=ACME  (no remittance ref)
  B4: $5,000   "GAMMA INC WIRE"              customer=GAMMA (no remittance ref)
  B5: $3,000   "ACME CORP INV-004"           customer=ACME  (direct invoice ref)

Remittances:
  RM-001: payer=ACME, $10,000, ref="RM-001"
          Line: INV-001 $6,000
          Line: INV-002 $4,000

  RM-002: payer=BETA, $8,500, ref="RM-002"    ← Amount mismatch with B2!
          Line: INV-003 $8,500

  RM-003: payer=ACME, $3,000, ref="RM-003"    ← No matching bank (orphan)
          Line: INV-010 $3,000

Invoices:
  INV-001: ACME,  $6,000 pending
  INV-002: ACME,  $4,000 pending
  INV-003: BETA,  $8,500 pending
  INV-004: ACME,  $3,000 pending
  INV-005: ACME,  $7,500 pending              ← Unique amount for ACME
  INV-006: GAMMA, $5,000 pending
  INV-007: GAMMA, $5,000 pending              ← Same amount as INV-006
  INV-010: ACME,  $3,000 pending
```

### Phase 1A: Bank ↔ Remittance Matching

```
B1 ↔ RM-001:
  - Reference "RM-001" found in B1.description? ✓
  - Customer ACME == ACME? ✓
  → MATCH ESTABLISHED

B2 ↔ RM-002:
  - Reference "RM-002" found in B2.description? ✓
  - Customer BETA == BETA? ✓
  → MATCH ESTABLISHED

B3: No remittance reference found → Goes to Phase 2
B4: No remittance reference found → Goes to Phase 2
B5: No remittance reference found → Goes to Phase 2

RM-003: No bank with "RM-003" and customer=ACME → ORPHAN_REMITTANCE
```

### Phase 1B: Bank ↔ Remittance Validation

```
B1 ↔ RM-001:
  - Amount: |$10,000 - $10,000| = $0 ✓
  - Date: within tolerance ✓
  → No exceptions

B2 ↔ RM-002:
  - Amount: |$8,000 - $8,500| = $500 (6.25% difference) ✗
  → Exception: AMOUNT_MISMATCH
```

### Phase 1C: Remittance Line ↔ Invoice Matching & Validation

```
RM-001 lines:
  INV-001: Found? ✓  Customer=ACME match? ✓  Pending=$6,000, paying=$6,000 ✓
  INV-002: Found? ✓  Customer=ACME match? ✓  Pending=$4,000, paying=$4,000 ✓
  Sum: $10,000 == RM-001.total $10,000 ✓
  → No exceptions

RM-002 lines:
  INV-003: Found? ✓  Customer=BETA match? ✓  Pending=$8,500, paying=$8,500 ✓
  Sum: $8,500 == RM-002.total $8,500 ✓
  → No additional exceptions (but bank amount mismatch already flagged)
```

### Phase 1D: Decision

```
B1 + RM-001: exceptions.is_empty() == true
  → AUTO-APPROVE
  → Apply: INV-001 ← $6,000, INV-002 ← $4,000

B2 + RM-002: exceptions = [AMOUNT_MISMATCH]
  → EXCEPTION QUEUE
  → Human reviews: bank=$8,000 vs remittance=$8,500
```

### Phase 2: Direct Reference Matching

```
B3: "ACME CORP PAYMENT"
  - Extract references: none found
  → Goes to Phase 3

B4: "GAMMA INC WIRE"
  - Extract references: none found
  → Goes to Phase 3

B5: "ACME CORP INV-004"
  - Extract references: [INV-004]
  - INV-004: Found? ✓  Customer=ACME? ✓  Pending=$3,000
  - Allocate: $3,000 to INV-004
  → AUTO-APPROVE (reference-based)
```

### Phase 3: Suggestion Generation

```
B3: $7,500 (ACME)
  - ACME open invoices: [INV-005 $7,500, INV-010 $3,000]
  - Unique amount check: Only INV-005 has $7,500 ✓
  → SUGGESTION (90% confidence, "Unique amount match")

B4: $5,000 (GAMMA)
  - GAMMA open invoices: [INV-006 $5,000, INV-007 $5,000]
  - Not unique (two invoices with same amount)
  - Flow network picks INV-006 (arbitrary tie-break)
  → SUGGESTION (70% confidence, alternatives: [INV-007])
```

### Final Output

```
AUTO-APPROVED (Apply immediately):
  B1: $10,000 → RM-001 → [INV-001 $6K, INV-002 $4K]  (Remittance-backed)
  B5: $3,000  → INV-004 $3K                          (Reference-based)

EXCEPTION QUEUE (Human resolves specific issue):
  B2: $8,000 → RM-002 → [INV-003 $8.5K]
      Exception: AMOUNT_MISMATCH
        bank_amount: $8,000
        remittance_amount: $8,500
        difference: -$500

SUGGESTIONS (Human reviews and approves/rejects):
  B3: $7,500 → INV-005 $7,500   ★★★ HIGH (90%)   "Unique amount match"
  B4: $5,000 → INV-006 $5,000   ★★☆ MED (70%)    alternatives: [INV-007]

MANUAL (No suggestion):
  (none in this example)

ORPHAN REMITTANCES (No matching bank):
  RM-003: ACME, $3,000, ref="RM-003" - No bank transaction found
```

---

## Data Model

### Input Entities

```python
@dataclass
class BankTransaction:
    id: str
    date: date
    amount: Decimal
    description: str
    customer_id: Optional[str]  # Identified from description
    reference: Optional[str]    # Bank's reference number

@dataclass
class Remittance:
    id: str
    payer_name: str
    payer_id: str               # Customer identifier
    payment_date: date
    payment_amount_total: Decimal
    currency: str
    payment_method: str         # ACH, Wire, Check, Card, Lockbox
    payment_reference: str      # Key for matching to bank
    line_items: List[RemittanceLineItem]
    source: str                 # EDI_820, PDF, EMAIL, SYNTHETIC

@dataclass
class RemittanceLineItem:
    invoice_number: str
    invoice_date: Optional[date]
    invoice_amount_original: Optional[Decimal]
    amount_paid: Decimal
    remaining_balance: Optional[Decimal]
    deduction_amount: Optional[Decimal]
    deduction_reason: Optional[str]
    credit_note_reference: Optional[str]

@dataclass
class Invoice:
    id: str
    invoice_number: str
    customer_id: str
    amount: Decimal
    pending_amount: Decimal
    due_date: date
```

### Output Entities

```python
@dataclass
class ReconciliationMatch:
    bank_id: str
    remittance_id: Optional[str]
    match_type: MatchType
    allocations: List[InvoiceAllocation]
    exceptions: List[Exception]
    status: Status

class MatchType(Enum):
    REMITTANCE_BACKED = "remittance_backed"  # Phase 1
    REFERENCE_BASED = "reference_based"       # Phase 2
    SUGGESTED = "suggested"                   # Phase 3
    MANUAL = "manual"                         # Human assigned

class Status(Enum):
    AUTO_APPROVED = "auto_approved"
    EXCEPTION = "exception"
    SUGGESTION = "suggestion"
    MANUAL = "manual"

@dataclass
class InvoiceAllocation:
    invoice_id: str
    invoice_number: str
    amount: Decimal
    is_partial: bool
    remaining_after: Decimal

@dataclass
class Exception:
    type: ExceptionType
    severity: Severity
    entity_id: str              # Which entity caused it
    details: dict
    suggested_resolution: Optional[str]

class ExceptionType(Enum):
    # Bank ↔ Remittance
    AMOUNT_MISMATCH = "amount_mismatch"
    DATE_DISCREPANCY = "date_discrepancy"
    MULTIPLE_REMITTANCES_ONE_BANK = "multiple_remittances_one_bank"
    MULTIPLE_BANKS_ONE_REMITTANCE = "multiple_banks_one_remittance"
    ORPHAN_REMITTANCE_NO_BANK = "orphan_remittance_no_bank"

    # Remittance ↔ Invoice
    INVOICE_NOT_FOUND = "invoice_not_found"
    CUSTOMER_MISMATCH = "customer_mismatch"
    DUPLICATE_PAYMENT = "duplicate_payment"
    OVERPAYMENT = "overpayment"
    CREDIT_NOTE_NOT_FOUND = "credit_note_not_found"

    # Internal
    LINE_ITEMS_SUM_MISMATCH = "line_items_sum_mismatch"
    DEDUCTION_WITHOUT_REASON = "deduction_without_reason"

class Severity(Enum):
    CRITICAL = "critical"   # Blocks auto-approval
    WARNING = "warning"     # Flags for review
    INFO = "info"           # Logged only

@dataclass
class Suggestion:
    bank_id: str
    allocations: List[InvoiceAllocation]
    match_type: SuggestionType  # SINGLE_INVOICE, UNIQUE_AMOUNT, etc.
    confidence: float
    tier: ConfidenceTier        # HIGH, MEDIUM, LOW
    explanation: str
    alternatives: List[InvoiceAllocation]

@dataclass
class ManualItem:
    bank_id: str
    amount: Decimal
    reason: str
    candidate_invoices: List[Invoice]
```

### Final Output Structure

```python
@dataclass
class ReconciliationResult:
    auto_approved: List[ReconciliationMatch]
    exceptions: List[ReconciliationMatch]
    suggestions: List[Suggestion]
    manual: List[ManualItem]
    orphan_remittances: List[Remittance]
    stats: ReconciliationStats

@dataclass
class ReconciliationStats:
    total_banks: int
    total_remittances: int
    auto_approved_count: int
    auto_approved_amount: Decimal
    exception_count: int
    exception_by_type: Dict[ExceptionType, int]
    suggestion_count: int
    manual_count: int
    orphan_remittance_count: int
```

---

## Configuration Parameters

```python
@dataclass
class ReconciliationConfig:
    # Amount tolerance for bank ↔ remittance validation
    amount_tolerance_percent: float = 0.5    # 0.5%
    amount_tolerance_absolute: Decimal = 10  # $10
    # Use whichever is GREATER

    # Date tolerance for validation
    date_tolerance_days: int = 14

    # Orphan remittance timing
    orphan_grace_period_days: int = 5  # Wait before flagging as orphan

    # Suggestion thresholds (Phase 3)
    min_suggestion_confidence: float = 0.50
    min_flow_edge_confidence: float = 0.40
    reject_penalty: float = 0.80

    # Amount tolerance for "exact match" in suggestions
    amount_match_tolerance: float = 0.02  # 2%
```

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `amount_tolerance_percent` | 0.5% | Allow small bank fee deductions |
| `amount_tolerance_absolute` | $10 | Minimum tolerance regardless of percentage |
| `date_tolerance_days` | 14 | Flag large date gaps as warning |
| `orphan_grace_period_days` | 5 | Don't flag remittance as orphan if recent |
| `min_suggestion_confidence` | 0.50 | Don't suggest below this |
| `min_flow_edge_confidence` | 0.40 | Don't create flow edges below this |
| `reject_penalty` | 0.80 | Cost of rejecting in flow network |

---

## Summary

| Category | Trigger | Action | Human Involved? |
|----------|---------|--------|-----------------|
| **AUTO-APPROVED (Remittance)** | Remittance match + zero exceptions | Apply immediately | No |
| **AUTO-APPROVED (Reference)** | Invoice reference in description | Apply immediately | No |
| **EXCEPTION** | Match found but validation failed | Human fixes specific issue | Yes |
| **SUGGESTION (High)** | Unique match found | Present for quick approval | Yes |
| **SUGGESTION (Med/Low)** | Flow finds best match | Present with alternatives | Yes |
| **MANUAL** | No confident match | Human assigns from scratch | Yes |
| **ORPHAN REMITTANCE** | No matching bank found | Investigate | Yes |

### Key Principles Recap

| Principle | Implementation |
|-----------|----------------|
| **Matching is binary** | Reference + Customer = Match. No scoring. |
| **Validation is separate** | Amount, date, duplicates checked AFTER match |
| **Exceptions block auto-approval** | Any exception → Exception Queue |
| **Exceptions are specific** | Human knows exactly what to fix |
| **Graceful degradation** | Phase 1 → Phase 2 → Phase 3 → Manual |
| **All-or-nothing** | Clean = auto-approve, Not clean = exception queue |

### The Golden Rule

> **Remittance + Reference + Customer = Auto-approval (if clean)**
> **Any exception = Exception Queue (human resolves specific issue)**
> **No remittance/reference = Suggestion or Manual**

This ensures maximum automation when data is clean while guaranteeing zero wrong auto-approvals through comprehensive exception detection.
