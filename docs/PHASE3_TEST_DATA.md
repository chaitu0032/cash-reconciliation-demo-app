# Phase 3 Test Data Documentation

This document describes the test data created for testing Phase 3 suggestion generation.

## Files Created

### `test_phase3_data.py`
Test data generator creating comprehensive scenarios for all Phase 3 strategies.

### `run_phase3_tests.py`
Test runner that uses the generated data to verify Phase 3 suggestion logic.

## Test Scenarios

### Strategy 1: Single Invoice Per Customer (95% confidence)

**Scenario:** Customer has exactly ONE open invoice

**Test Data:**
- **Bank B-S1-001**: $1,250.00 → Customer CUST-001
  - Match: INV-2024-001 ($1,250.00) ✅ Perfect match

- **Bank B-S1-002**: $3,500.50 → Customer CUST-002
  - Match: INV-2024-002 ($3,500.50) ✅ Perfect match

- **Bank B-S1-003**: $890.00 → Customer CUST-003
  - Invoice: INV-2024-003 ($2,000.00) ⚠️ Amount too different, falls to flow network

**Expected Results:**
- B-S1-001 & B-S1-002: Match via Strategy 1 (95% confidence)
- B-S1-003: Falls through to flow network (partial payment)

---

### Strategy 2: Unique Amount Match (90% confidence)

**Scenario:** Bank amount uniquely matches ONE invoice (regardless of customer)

**Test Data:**
- **Bank B-S2-001**: $4,567.89 (no customer)
  - Match: INV-2024-101 ($4,567.89) ✅ Unique amount (90% confidence)

- **Bank B-S2-002**: $1,999.99 → Customer CUST-010
  - Match: INV-2024-102 ($1,999.99) ✅ Unique amount + customer (93% confidence)

- **Bank B-S2-003**: $750.25 (no customer)
  - Match: INV-2024-103 ($752.00) ✅ Within tolerance (90% confidence)

**Expected Results:**
- All 3 banks match via Strategy 2
- B-S2-002 gets boosted confidence (93%) due to customer match

---

### Strategy 3: Unique Combination (85% confidence)

**Scenario:** Bank amount matches ONE unique combination of invoices

**Test Data:**
- **Bank B-S3-001**: $3,500.00 → Customer CUST-020
  - Combination: INV-2024-201 ($1,500) + INV-2024-202 ($2,000) = $3,500
  - ⚠️ Note: Also equals INV-2024-203 ($1,000) + INV-2024-202 ($2,000) + ?
  - Falls through due to multiple combinations

- **Bank B-S3-002**: $2,750.00 (no customer)
  - Combination: INV-2024-203 ($1,000) + INV-2024-204 ($1,750) = $2,750 ✅

- **Bank B-S3-003**: $4,250.00 → Customer CUST-020
  - Combination: INV-2024-201 + INV-2024-203 + INV-2024-204 = $4,250
  - Multiple combinations possible, falls through

**Expected Results:**
- B-S3-002: Matches via Strategy 3 (85% confidence)
- Others: Fall through to flow network or manual

---

### Strategy 4: Flow Network Matching (Variable confidence)

**Scenario:** Complex many-to-many scenarios where strategies 1-3 don't apply

**Test Data:**

#### High Confidence Match
- **Bank B-S4-001**: $5,000.00 → Customer CUST-030
  - Invoice: INV-2024-301 ($5,000.00)
  - Confidence factors: Customer match (30%) + Exact amount (40%) = **90%**

#### Medium Confidence
- **Bank B-S4-002**: $2,500.00 (no customer)
  - Invoice: INV-2024-302 ($2,520.00)
  - Confidence: Amount proximity (~30%) = **60%**

#### Low Confidence / Poor Match
- **Bank B-S4-003**: $1,234.56 → Customer CUST-031
  - Invoice: INV-2024-303 ($5,678.90)
  - Confidence: Customer match (30%) only = **30%** → Likely manual

#### Partial Payment
- **Bank B-S4-004**: $600.00 → Customer CUST-032
  - Invoice: INV-2024-304 ($2,000.00)
  - Confidence: Customer (30%) + Partial (10%) = **50%**
  - Partial allocation: $600 of $2,000

#### Multiple Invoices
- **Bank B-S4-005**: $8,000.00 → Customer CUST-033
  - Invoices: INV-2024-305 ($3,000) + INV-2024-306 ($2,500) + INV-2024-307 ($2,500)
  - Strategy 3 catches this (unique combination, 88% confidence)

**Expected Results:**
- B-S4-001: Strategy 1 catches it (single invoice)
- B-S4-005: Strategy 3 catches it (unique combo)
- Others: Flow network with varying confidence

---

### Edge Cases

**Test Data:**

#### Ambiguous Amount
- **Bank B-EDGE-001**: $1,000.00 (no customer)
  - Multiple invoices: INV-2024-401, INV-2024-402, INV-2024-403 (all $1,000)
  - Flow network picks one arbitrarily (low confidence ~60%)

#### Customer Doesn't Exist
- **Bank B-EDGE-002**: $999.99 → Customer CUST-NONEXISTENT
  - No invoices for this customer
  - Falls to flow network or manual

#### Very Low Amount (No Good Match)
- **Bank B-EDGE-003**: $123.45 (no customer)
  - No invoices close to this amount
  - → **Manual queue**

#### Amount Too Large (Reject Edge)
- **Bank B-EDGE-004**: $50,000.00 → Customer CUST-040
  - Available invoice: INV-2024-404 ($100.00)
  - Confidence too low (<20%)
  - → **Manual queue**

#### Exact Tie (Multiple Equally Good Matches)
- **Bank B-EDGE-005**: $2,222.22 (no customer)
  - Two invoices: INV-2024-405 & INV-2024-406 (both $2,222.22)
  - Flow network picks one (60% confidence)

**Expected Results:**
- B-EDGE-001, B-EDGE-002, B-EDGE-005: Flow matches (low confidence)
- B-EDGE-003, B-EDGE-004: Manual queue

---

## Confidence Calculation Examples

### Strategy 4 (Flow Network) Edge Confidence

Formula:
```
confidence = 0.1 (base)
           + 0.3 (customer match)
           + 0.4 (exact amount) OR 0.3 (close) OR 0.15 (loose)
           + 0.1 (partial payment possible)
```

**Examples:**

| Bank | Invoice | Customer | Amount | Calculation | Total |
|------|---------|----------|--------|-------------|-------|
| $5,000 (CUST-030) | $5,000 (CUST-030) | ✅ 0.3 | ✅ 0.4 | 0.1 + 0.3 + 0.4 + 0.1 | **0.9** |
| $2,500 (none) | $2,520 (CUST-035) | ❌ 0.0 | ✅ 0.3 | 0.1 + 0.0 + 0.3 + 0.1 | **0.5** |
| $600 (CUST-032) | $2,000 (CUST-032) | ✅ 0.3 | ❌ 0.0 | 0.1 + 0.3 + 0.0 + 0.1 | **0.5** |
| $1,000 (none) | $1,000 (CUST-040) | ❌ 0.0 | ✅ 0.4 | 0.1 + 0.0 + 0.4 + 0.1 | **0.6** |

---

## Running the Tests

### Run all tests:
```bash
python run_phase3_tests.py
```

### View test data summary:
```bash
python test_phase3_data.py
```

### Run individual strategy tests:
```python
from run_phase3_tests import test_strategy1, test_strategy2, test_strategy3, test_strategy4

# Test specific strategy
test_strategy1()
```

---

## Test Results Summary

From the comprehensive test run:

```
Total Banks: 19
Total Invoices: 24

✅ Generated 15 suggestions (79%)
⚠️  Requires Manual Review: 4 banks (21%)

Suggestions by Type:
  - flow_match: 7
  - single_invoice: 3
  - unique_amount: 4
  - unique_combination: 1

Confidence Tiers:
  - HIGH (≥85%): 8 suggestions
  - LOW (50-64%): 7 suggestions

Flow Analysis:
  - Total Bank Money: $95,138.85
  - Suggested (with confidence): $38,017.65 (40%)
  - Requires Manual Review: $57,123.45 (60%)
```

---

## Key Insights

1. **Strategy Priority Works:** Banks are matched in order (1→2→3→4), preventing duplicate suggestions

2. **Customer Matching is Powerful:** Banks with customer IDs get:
   - Higher priority matching (Strategy 1)
   - Boosted confidence scores (+3% to +30%)

3. **Flow Network is Flexible:** Handles:
   - Partial payments
   - Multiple invoices per bank
   - Many-to-many scenarios
   - Reject edges for poor matches

4. **Manual Queue is Appropriate:** Banks with:
   - No customer ID + ambiguous amounts
   - Very poor confidence (<50%)
   - Amount mismatches beyond tolerance
   → Go to manual queue for human review

---

## Adding More Test Cases

To add new test scenarios, edit `test_phase3_data.py`:

```python
def generate_my_custom_scenario():
    """Your scenario description."""
    banks = [
        BankTransaction(
            id="B-CUSTOM-001",
            date=date(2024, 1, 15),
            amount=Decimal("1000.00"),
            description="Payment",
            customer_id="CUST-100",
        ),
    ]

    invoices = [
        Invoice(
            id="INV-CUSTOM-001",
            invoice_number="INV-2024-999",
            customer_id="CUST-100",
            amount=Decimal("1000.00"),
            pending_amount=Decimal("1000.00"),
            due_date=date(2024, 2, 1),
        ),
    ]

    return banks, invoices
```

Then add it to `run_phase3_tests.py`:
```python
def test_my_custom_scenario():
    banks, invoices = generate_my_custom_scenario()
    config = ReconciliationConfig()
    generator = Phase3SuggestionGenerator(config)
    result = generator.process(banks, invoices, already_matched_bank_ids=set())
    # Add assertions...
```

---

## Configuration

Tests use default config from `src_v2/config.py`:

```python
ReconciliationConfig(
    amount_tolerance_percent=0.5,        # 0.5%
    amount_tolerance_absolute=Decimal("10"),  # $10
    min_suggestion_confidence=0.50,      # 50%
    min_flow_edge_confidence=0.40,       # 40%
    reject_penalty=0.80,                 # 80%
    high_confidence_threshold=0.85,      # 85%
    medium_confidence_threshold=0.65,    # 65%
)
```

You can override these in tests:
```python
config = ReconciliationConfig(
    reject_penalty=0.70,  # Lower threshold
    min_suggestion_confidence=0.60,  # Higher bar
)
```
