# Cash Reconciliation Platform - Design Plan

## Overview

Design a cash reconciliation platform that matches payments across three data sources to ensure all money received is properly accounted for.

---

## Data Sources

### 1. Bank Statements
- Amount
- Date
- Reference Number
- Description

### 2. Remittances (payment advice from customers)
- Customer Information (name, address)
- Payment Reference Number
- Payment Date
- Line Items (one or more):
  - Invoice Number
  - Description
  - Payment Method
  - Amount

### 3. Invoices
- Invoice ID
- Customer ID
- Due Date
- Amount
- Pending Amount
- Status (Open/Closed/Partial)

---

## Key Relationships

- One remittance line item → One invoice (each line in a remittance pays a specific invoice)
- One remittance → One bank transaction (the total remittance amount should match a single bank deposit)
- Invoice Unique Key = (customer_id + invoice_id)

---

## Reconciliation Goals

### Primary Goals

1. **Bank-to-Remittance Matching**: Ensure every bank deposit is supported by customer payment advice
2. **Remittance-to-Invoice Matching**: Ensure every payment is applied to valid outstanding invoices
3. **Full Chain Reconciliation**: Bank Deposit → Remittance → Invoice(s)

### Success Metrics
- **Match rate**: % of transactions auto-reconciled without manual intervention
- **Exception rate**: % requiring human review
- **Aging**: Time to clear unmatched items

---

## Matching Flow (Parse-First Approach)

```
┌──────────────────┐
│  Bank Statement  │
└────────┬─────────┘
         ▼
┌──────────────────────────┐
│ Step 1: Parse Bank       │
│ Description              │
└────────┬─────────────────┘
         ▼
    ┌───────────────────┐
    │ Actual Remittance │──Yes──→ Use Remittance Data
    │ Exists?           │         (richer source)
    └─────────┬─────────┘              │
              │No                      │
              ▼                        │
    ┌───────────────────┐              │
    │ Parsed Data       │──Yes──→ Create Virtual Remittance
    │ Sufficient?       │              │
    └─────────┬─────────┘              │
              │No                      │
              ▼                        │
    ┌───────────────────┐              │
    │ Match by Amount + │              │
    │ Date Only         │              │
    └─────────┬─────────┘              │
              │                        │
              ▼◄───────────────────────┘
┌──────────────────────────┐
│ Step 2: Identify Customer│
│ (from parsed/remittance) │
└────────┬─────────────────┘
         ▼
┌──────────────────────────┐
│ Step 3: Match to         │
│ Customer's Open Invoices │
└────────┬─────────────────┘
         ▼
┌──────────────────────────┐
│ Reconciled / Exception   │
└──────────────────────────┘
```

---

## Step 1: Bank Description Parsing Rules

### Data Points to Extract

| Data Point | Pattern Examples |
|------------|------------------|
| Invoice Numbers | `INV-xxxx`, `Invoice #xxxx`, `INV:xxxx` |
| Payment Reference | `REF:xxxx`, `PAY-xxxx`, `TXN:xxxx` |
| Customer Name | Free text, often at start |
| Customer Account | `A/C:xxxx`, `ACCT-xxxx` |
| PO Numbers | `PO-xxxx`, `PO#xxxx` |

### Parsing Rules

#### Rule P1: Extract Invoice Numbers
```
Pattern: INV[-:#]?\s*\d{4,}[-\d]*
         Invoice\s*#?\s*\d+

Input:  "PAYMENT FOR INV-2024-001 AND INV-2024-002"
Output: ["INV-2024-001", "INV-2024-002"]
```

#### Rule P2: Extract Payment Reference
```
Pattern: REF[-:#]?\s*[\w-]+
         PAY[-:#]?\s*[\w-]+

Input:  "ACME CORP REF:PAY-AC-789"
Output: "PAY-AC-789"
```

#### Rule P3: Extract Customer Account
```
Pattern: A/?C[-:#]?\s*\d+
         ACCT[-:#]?\s*\d+

Input:  "PAYMENT A/C:90001234 INV-001"
Output: "90001234"
```

#### Rule P4: Extract Customer Name
```
After removing extracted tokens, remaining text is likely customer name
Or match against known customer names/aliases

Input:  "ACME CORP REF:PAY-AC-789 INV-001"
After extraction: "ACME CORP"
Output: "ACME CORP"
```

### Sufficiency Rules

```
Sufficient for Direct Match:
─────────────────────────────
IF extracted.invoice_numbers.length > 0
AND (extracted.customer_name OR extracted.customer_account OR extracted.payment_ref)
→ SUFFICIENT, create virtual remittance

Sufficient for Customer-Only Match:
─────────────────────────────
IF extracted.customer_name OR extracted.customer_account
AND bank.amount matches single open invoice for customer
→ SUFFICIENT, suggest match

Insufficient:
─────────────────────────────
IF only amount available
OR no identifiable tokens
→ LOOK FOR ACTUAL REMITTANCE DOCUMENT
```

### Virtual Remittance Creation

```
Bank Record:
  amount: $10,000
  date: 2024-01-15
  reference: "TXN123456"
  description: "ACME CORP INV-2024-001 $6000 INV-2024-002 $4000 REF:PAY-AC-789"

        ↓ Parse & Transform ↓

Virtual Remittance:
  source: "BANK_PARSED"
  payment_reference: "PAY-AC-789"
  payment_date: 2024-01-15
  total_amount: $10,000
  customer_name: "ACME CORP"
  line_items:
    - invoice: "INV-2024-001", amount: $6,000
    - invoice: "INV-2024-002", amount: $4,000
```

---

## Step 2: Customer Identification Rules

### Customer Master Data Structure

| Customer ID | Name | Aliases | Address | Payment Refs | Account Numbers |
|-------------|------|---------|---------|--------------|-----------------|
| CUST-001 | Acme Corp | Acme, ACME Inc | 123 Main St | PAY-AC-* | 90001234 |
| CUST-002 | Beta LLC | Beta, Beta Co | 456 Oak Ave | BT-* | 90005678 |

### Customer Identifier Categories

| Category | Identifiers |
|----------|-------------|
| Primary (Strong) | Customer ID, Account Number, Tax ID, Payment Reference Pattern |
| Secondary (Medium) | Company Name, Trading Name, Bank Account (sender) |
| Tertiary (Weak) | Address, City, Postal Code, Contact Email, Phone |

### Customer Identification Rules

#### Rule 0.1 — Exact Customer ID (Confidence: 100%)
```
IF remittance.customer_id = customer_master.customer_id
→ CUSTOMER IDENTIFIED
```

#### Rule 0.2 — Payment Reference Pattern (Confidence: 95%)
```
IF remittance.payment_reference MATCHES customer_master.payment_ref_pattern
→ CUSTOMER IDENTIFIED

Example: "PAY-AC-7890" matches pattern "PAY-AC-*" → Acme Corp
```

#### Rule 0.3 — Account Number Match (Confidence: 95%)
```
IF remittance.account_number = customer_master.account_number
→ CUSTOMER IDENTIFIED
```

#### Rule 0.4 — Exact Name Match (Confidence: 90%)
```
IF normalize(remittance.customer_name) = normalize(customer_master.name)
→ CUSTOMER IDENTIFIED
```

#### Rule 0.5 — Alias Match (Confidence: 85%)
```
IF normalize(remittance.customer_name) IN customer_master.aliases
→ CUSTOMER IDENTIFIED
```

#### Rule 0.6 — Fuzzy Name Match (Confidence: 70%)
```
IF similarity(remittance.customer_name, customer_master.name) >= 85%
→ SUGGEST CUSTOMER (needs confirmation)

Handles: "Acme Corporation" vs "Acme Corp"
```

#### Rule 0.7 — Address Match (Confidence: 75%)
```
IF normalize(remittance.address) = normalize(customer_master.address)
OR postal_code matches AND partial street match
→ CUSTOMER IDENTIFIED (or SUGGEST if partial)
```

#### Rule 0.8 — Bank Description Contains Customer Info (Confidence: 70%)
```
IF bank.description CONTAINS customer_master.name
OR bank.description CONTAINS customer_master.account_number
→ SUGGEST CUSTOMER
```

---

## Level 1: Bank ↔ Remittance Matching Rules

### Rule 1.1 — Exact Reference + Exact Amount (Confidence: 100%)
```
IF bank.reference = remittance.reference
AND bank.amount = remittance.total_amount
→ AUTO-MATCH
```

### Rule 1.2 — Exact Reference + Amount Tolerance (Confidence: 95%)
```
IF bank.reference = remittance.reference
AND ABS(bank.amount - remittance.total_amount) <= $0.99
→ AUTO-MATCH (flag for review if tolerance used)
```

### Rule 1.3 — Fuzzy Reference + Exact Amount (Confidence: 85%)
```
IF normalize(bank.reference) = normalize(remittance.reference)
AND bank.amount = remittance.total_amount
→ AUTO-MATCH

Normalization handles:
- Leading zeros: "00012345" → "12345"
- Prefixes: "PAY-12345" → "12345"
- Spaces/dashes: "PAY 123-45" → "PAY12345"
```

### Rule 1.4 — Amount + Date Match (Confidence: 70%)
```
IF bank.amount = remittance.total_amount
AND ABS(bank.date - remittance.payment_date) <= 3 days
AND no other remittance has same amount in date range
→ SUGGEST-MATCH (requires confirmation)
```

### Rule 1.5 — Description Contains Reference (Confidence: 75%)
```
IF bank.description CONTAINS remittance.reference
AND bank.amount = remittance.total_amount
→ AUTO-MATCH
```

### Rule 1.6 — Customer Name in Description (Confidence: 60%)
```
IF bank.description CONTAINS remittance.customer_name
AND bank.amount = remittance.total_amount
AND ABS(bank.date - remittance.payment_date) <= 5 days
→ SUGGEST-MATCH
```

---

## Level 2: Remittance ↔ Invoice Matching Rules (Customer-Scoped)

### Rule 2.1 — Customer + Exact Invoice + Exact Amount (Confidence: 100%)
```
IF customer_identified
AND remittance_line.invoice_number = invoice.invoice_id
AND invoice.customer_id = identified_customer_id
AND remittance_line.amount = invoice.pending_amount
AND invoice.status = 'Open'
→ AUTO-MATCH, set invoice status = 'Closed'
```

### Rule 2.2 — Customer + Exact Invoice + Partial Payment (Confidence: 95%)
```
IF customer_identified
AND remittance_line.invoice_number = invoice.invoice_id
AND invoice.customer_id = identified_customer_id
AND remittance_line.amount < invoice.pending_amount
AND invoice.status = 'Open'
→ AUTO-MATCH, update invoice.pending_amount, status = 'Partial'
```

### Rule 2.3 — Customer + Fuzzy Invoice Reference (Confidence: 85%)
```
IF customer_identified
AND normalize(remittance_line.invoice_number) = normalize(invoice.invoice_id)
AND invoice.customer_id = identified_customer_id
→ AUTO-MATCH
```

### Rule 2.4 — Customer + Amount Match (Confidence: 70%)
```
IF customer_identified
AND remittance_line.amount = invoice.pending_amount
AND invoice.customer_id = identified_customer_id
AND only ONE open invoice matches amount
→ SUGGEST-MATCH
```

### Rule 2.5 — Customer + Oldest Open Invoice / FIFO (Confidence: 60%)
```
IF customer_identified
AND no invoice reference provided
AND invoice.customer_id = identified_customer_id
AND invoice.status = 'Open'
→ SUGGEST applying to oldest due invoice (FIFO)
```

### Rule 2.6 — Exact Invoice + Overpayment (Confidence: 80%)
```
IF customer_identified
AND remittance_line.invoice_number = invoice.invoice_id
AND remittance_line.amount > invoice.pending_amount
AND invoice.status = 'Open'
→ FLAG-EXCEPTION (overpayment requires manual review)
```

### Rule 2.7 — Invoice Already Closed (Confidence: N/A)
```
IF remittance_line.invoice_number = invoice.invoice_id
AND invoice.status = 'Closed'
→ FLAG-EXCEPTION (possible duplicate payment)
```

---

## Tolerance Configuration

| Parameter | Recommended Value | Adjustable |
|-----------|------------------|------------|
| Amount tolerance | $0.99 or 0.1% | Yes |
| Date tolerance (bank vs remittance) | 3-5 days | Yes |
| Reference fuzzy match threshold | 90% similarity | Yes |
| Minimum confidence for auto-match | 85% | Yes |
| Minimum confidence for suggestion | 60% | Yes |

---

## Match Outcomes

| Outcome | Criteria |
|---------|----------|
| AUTO-MATCHED | Confidence ≥ 85%, no exceptions |
| SUGGEST-MATCH | Confidence 60-84%, needs confirmation |
| EXCEPTION | Rule violation or ambiguity |
| UNMATCHED | No matching candidate found |

---

## Exception Types

| Code | Description | Cause |
|------|-------------|-------|
| `E001` | Amount mismatch | Bank ≠ Remittance total |
| `E002` | Overpayment | Paid more than invoice amount |
| `E003` | Underpayment | Paid less than invoice amount |
| `E004` | Duplicate payment | Invoice already closed |
| `E005` | Invalid invoice | Invoice ID not found |
| `E006` | Multiple matches | Ambiguous—several candidates |
| `E007` | Orphan bank txn | No remittance found |
| `E008` | Orphan remittance | No bank txn found |
| `E009` | Customer not identified | Cannot determine customer |
| `E010` | Multiple customer matches | Ambiguous customer |
| `E011` | Invoice found but wrong customer | Customer mismatch |
| `E012` | Customer identified but no open invoices | No payable invoices |

---

## Parsing Confidence Levels

| Extracted Data | Confidence |
|----------------|------------|
| Invoice number (exact pattern) | 95% |
| Customer account number | 90% |
| Payment reference (known pattern) | 90% |
| Customer name (exact match to master) | 85% |
| Customer name (fuzzy match) | 70% |
| Amount embedded in description | 80% |

---

## Data Source Priority

| Priority | Source |
|----------|--------|
| 1 | Actual Remittance Document (most complete) |
| 2 | Parsed Bank Description (if sufficient) |
| 3 | Customer Payment History (learned patterns) |

Use highest priority source available. If actual remittance exists, prefer it over parsed data. Parsed data fills gaps when remittance is missing.

---

## Reconciliation Scenarios

### Scenario A: Full Data Available
```
Bank + Remittance Document exists
→ Match bank to remittance (Level 1)
→ Use remittance for customer ID + invoice matching
```

### Scenario B: Bank Only, Parseable
```
Bank description contains customer + invoice info
→ Parse and create virtual remittance
→ Proceed with customer ID + invoice matching
```

### Scenario C: Bank Only, Minimal Data
```
Bank description: "WIRE TRANSFER $5000"
→ Cannot parse meaningful data
→ Check for matching remittance by amount/date
→ If none, mark as UNMATCHED for manual review
```

### Scenario D: Remittance Only, No Bank Yet
```
Remittance received, bank deposit not yet posted
→ Hold remittance in pending state
→ Auto-match when bank posts
```

---

## Customer Learning (Future Enhancement)

Build confidence over time:

```
IF bank.sender_account = X
AND historically matched to Customer Y (>3 times)
→ Increase confidence for Customer Y on future matches
```

---

## Next Steps

1. Design the customer master schema with all identifier fields
2. Build the normalization functions for names/addresses
3. Write the parsing functions for common bank description formats
4. Design the data schema for storing parsed vs actual remittance
5. Build the matching algorithm in code
6. Design exception workflows for manual review
