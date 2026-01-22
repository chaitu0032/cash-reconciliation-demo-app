"""
Add suggestion-causing data for Phase 3 reconciliation testing.
Creates scenarios for:
1. Rules-based: SINGLE_INVOICE, UNIQUE_AMOUNT, UNIQUE_COMBINATION
2. Flow-based: FLOW_MATCH (complex multi-invoice matching)
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / 'data'


def load_json(filename):
    with open(DATA_DIR / filename, 'r') as f:
        return json.load(f)


def save_json(filename, data):
    with open(DATA_DIR / filename, 'w') as f:
        json.dump(data, f, indent=2)


def create_invoice(inv_num, customer_id, customer_name, amount, status="OPEN"):
    """Helper to create invoice dict."""
    return {
        "invoice_number": inv_num,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "invoice_date": "2025-12-15",
        "due_date": "2026-01-14",
        "payment_terms": "Net 30",
        "currency": "USD",
        "line_items": [{"line_id": 1, "description": "Services", "quantity": 1, "unit_price": amount, "line_total": amount}],
        "subtotal": amount,
        "tax_rate": 0,
        "tax_amount": 0,
        "total_amount": amount,
        "amount_paid": 0.0,
        "balance_due": amount,
        "status": status,
        "payment_date": None,
        "remittance_id": None
    }


def add_suggestion_data():
    banks = load_json('bank_transactions.json')
    invoices = load_json('invoices.json')

    # Get next IDs
    next_bank_id = len(banks) + 1
    next_inv_id = len(invoices) + 1

    print(f"Starting IDs: Bank={next_bank_id}, Inv={next_inv_id}")
    print("\n" + "=" * 60)
    print("ADDING RULES-BASED SUGGESTION DATA")
    print("=" * 60)

    # =========================================================================
    # SUGGESTION TYPE 1: SINGLE_INVOICE (95% confidence)
    # Customer has exactly ONE open invoice
    # =========================================================================

    # Scenario 1a: Perfect single invoice match
    inv_num = f"INV-2026-{next_inv_id:04d}"
    invoices.append(create_invoice(inv_num, "CUST-SINGLE-001", "Single Invoice Corp", 7500.00))
    next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-25",
        "amount": 7500.00,  # Exact match
        "description": "ACH PAYMENT SINGLE INVOICE CORP",
        "customer_id": "CUST-SINGLE-001",
        "customer_name": "Single Invoice Corp",
        "reference": None,  # No reference - skips Phase 1/2
        "payment_method": "ACH"
    })
    print(f"Added TXN-{next_bank_id:03d}: SINGLE_INVOICE - exact amount $7,500")
    next_bank_id += 1

    # Scenario 1b: Single invoice with slight amount difference (within tolerance)
    inv_num = f"INV-2026-{next_inv_id:04d}"
    invoices.append(create_invoice(inv_num, "CUST-SINGLE-002", "Solo Payment LLC", 12000.00))
    next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-25",
        "amount": 12050.00,  # Slightly higher but within 5x tolerance
        "description": "WIRE SOLO PAYMENT LLC",
        "customer_id": "CUST-SINGLE-002",
        "customer_name": "Solo Payment LLC",
        "reference": None,
        "payment_method": "WIRE"
    })
    print(f"Added TXN-{next_bank_id:03d}: SINGLE_INVOICE - $12,050 vs $12,000 invoice")
    next_bank_id += 1

    # =========================================================================
    # SUGGESTION TYPE 2: UNIQUE_AMOUNT (90-93% confidence)
    # Bank amount uniquely matches exactly one invoice
    # =========================================================================

    # Scenario 2a: Unique amount match (no customer on bank)
    inv_num = f"INV-2026-{next_inv_id:04d}"
    invoices.append(create_invoice(inv_num, "CUST-UNIQUE-001", "Unique Amount Inc", 8765.43))
    next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-26",
        "amount": 8765.43,  # Very specific amount - likely unique
        "description": "CHECK DEPOSIT #55123",
        "customer_id": None,  # Unknown customer
        "customer_name": None,
        "reference": None,
        "payment_method": "CHECK"
    })
    print(f"Added TXN-{next_bank_id:03d}: UNIQUE_AMOUNT - $8,765.43 (no customer)")
    next_bank_id += 1

    # Scenario 2b: Unique amount with customer match (higher confidence)
    inv_num = f"INV-2026-{next_inv_id:04d}"
    invoices.append(create_invoice(inv_num, "CUST-UNIQUE-002", "Precise Payments Co", 23456.78))
    next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-26",
        "amount": 23456.78,
        "description": "ACH CREDIT PRECISE PAYMENTS CO",
        "customer_id": "CUST-UNIQUE-002",
        "customer_name": "Precise Payments Co",
        "reference": None,
        "payment_method": "ACH"
    })
    print(f"Added TXN-{next_bank_id:03d}: UNIQUE_AMOUNT - $23,456.78 (with customer match)")
    next_bank_id += 1

    # =========================================================================
    # SUGGESTION TYPE 3: UNIQUE_COMBINATION (85-88% confidence)
    # Bank amount matches a unique sum of 2-4 invoices
    # =========================================================================

    # Scenario 3a: Two invoices combine to match bank amount
    inv_num1 = f"INV-2026-{next_inv_id:04d}"
    invoices.append(create_invoice(inv_num1, "CUST-COMBO-001", "Combo Payer Inc", 5000.00))
    next_inv_id += 1

    inv_num2 = f"INV-2026-{next_inv_id:04d}"
    invoices.append(create_invoice(inv_num2, "CUST-COMBO-001", "Combo Payer Inc", 3500.00))
    next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-27",
        "amount": 8500.00,  # 5000 + 3500 = 8500
        "description": "WIRE COMBO PAYER INC",
        "customer_id": "CUST-COMBO-001",
        "customer_name": "Combo Payer Inc",
        "reference": None,
        "payment_method": "WIRE"
    })
    print(f"Added TXN-{next_bank_id:03d}: UNIQUE_COMBINATION - $8,500 = $5,000 + $3,500")
    next_bank_id += 1

    # Scenario 3b: Three invoices combine
    inv_num1 = f"INV-2026-{next_inv_id:04d}"
    invoices.append(create_invoice(inv_num1, "CUST-COMBO-002", "Triple Pay Corp", 4200.00))
    next_inv_id += 1

    inv_num2 = f"INV-2026-{next_inv_id:04d}"
    invoices.append(create_invoice(inv_num2, "CUST-COMBO-002", "Triple Pay Corp", 2800.00))
    next_inv_id += 1

    inv_num3 = f"INV-2026-{next_inv_id:04d}"
    invoices.append(create_invoice(inv_num3, "CUST-COMBO-002", "Triple Pay Corp", 1500.00))
    next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-27",
        "amount": 8500.00,  # 4200 + 2800 + 1500 = 8500
        "description": "ACH TRIPLE PAY CORP",
        "customer_id": "CUST-COMBO-002",
        "customer_name": "Triple Pay Corp",
        "reference": None,
        "payment_method": "ACH"
    })
    print(f"Added TXN-{next_bank_id:03d}: UNIQUE_COMBINATION - $8,500 = $4,200 + $2,800 + $1,500")
    next_bank_id += 1

    # Scenario 3c: Four invoices combine
    inv_num1 = f"INV-2026-{next_inv_id:04d}"
    invoices.append(create_invoice(inv_num1, "CUST-COMBO-003", "Quad Payment LLC", 3000.00))
    next_inv_id += 1

    inv_num2 = f"INV-2026-{next_inv_id:04d}"
    invoices.append(create_invoice(inv_num2, "CUST-COMBO-003", "Quad Payment LLC", 2500.00))
    next_inv_id += 1

    inv_num3 = f"INV-2026-{next_inv_id:04d}"
    invoices.append(create_invoice(inv_num3, "CUST-COMBO-003", "Quad Payment LLC", 2000.00))
    next_inv_id += 1

    inv_num4 = f"INV-2026-{next_inv_id:04d}"
    invoices.append(create_invoice(inv_num4, "CUST-COMBO-003", "Quad Payment LLC", 1500.00))
    next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-27",
        "amount": 9000.00,  # 3000 + 2500 + 2000 + 1500 = 9000
        "description": "WIRE QUAD PAYMENT LLC",
        "customer_id": "CUST-COMBO-003",
        "customer_name": "Quad Payment LLC",
        "reference": None,
        "payment_method": "WIRE"
    })
    print(f"Added TXN-{next_bank_id:03d}: UNIQUE_COMBINATION - $9,000 = $3,000 + $2,500 + $2,000 + $1,500")
    next_bank_id += 1

    print("\n" + "=" * 60)
    print("ADDING FLOW-BASED SUGGESTION DATA")
    print("=" * 60)

    # =========================================================================
    # SUGGESTION TYPE 4: FLOW_MATCH (variable confidence)
    # Complex scenarios requiring network flow algorithm
    # =========================================================================

    # Scenario 4a: Multiple banks, multiple invoices (same customer)
    # Customer has 5 invoices, 2 bank payments that need allocation
    for i, amt in enumerate([6000, 4500, 3200, 2800, 1800], 1):
        inv_num = f"INV-2026-{next_inv_id:04d}"
        invoices.append(create_invoice(inv_num, "CUST-FLOW-001", "Flow Network Inc", amt))
        next_inv_id += 1

    # Bank 1: Partial payment covering some invoices
    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-28",
        "amount": 10500.00,  # Could be 6000+4500 or other combinations
        "description": "ACH FLOW NETWORK INC PARTIAL 1",
        "customer_id": "CUST-FLOW-001",
        "customer_name": "Flow Network Inc",
        "reference": None,
        "payment_method": "ACH"
    })
    print(f"Added TXN-{next_bank_id:03d}: FLOW_MATCH - $10,500 vs 5 invoices ($6k,$4.5k,$3.2k,$2.8k,$1.8k)")
    next_bank_id += 1

    # Bank 2: Another partial payment
    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-29",
        "amount": 7800.00,  # Could be 3200+2800+1800 or other combinations
        "description": "ACH FLOW NETWORK INC PARTIAL 2",
        "customer_id": "CUST-FLOW-001",
        "customer_name": "Flow Network Inc",
        "reference": None,
        "payment_method": "ACH"
    })
    print(f"Added TXN-{next_bank_id:03d}: FLOW_MATCH - $7,800 (remaining invoices)")
    next_bank_id += 1

    # Scenario 4b: Cross-customer flow (unknown bank customer)
    # Bank with no customer ID could match invoices from multiple customers
    for cust_num, amounts in [("CUST-FLOW-002", [5500, 3300]), ("CUST-FLOW-003", [4400, 2200])]:
        for amt in amounts:
            inv_num = f"INV-2026-{next_inv_id:04d}"
            cust_name = f"Flow Customer {cust_num[-1]}"
            invoices.append(create_invoice(inv_num, cust_num, cust_name, amt))
            next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-29",
        "amount": 8800.00,  # Could be 5500+3300 from CUST-FLOW-002 or 4400+2200+2200 etc
        "description": "CHECK DEPOSIT #99887",
        "customer_id": None,  # Unknown - flow network will determine best match
        "customer_name": None,
        "reference": None,
        "payment_method": "CHECK"
    })
    print(f"Added TXN-{next_bank_id:03d}: FLOW_MATCH - $8,800 (unknown customer, multiple possibilities)")
    next_bank_id += 1

    # Scenario 4c: Partial invoice payments (flow splits across invoices)
    # Large invoices that will be partially paid
    for i, amt in enumerate([15000, 12000, 10000], 1):
        inv_num = f"INV-2026-{next_inv_id:04d}"
        invoices.append(create_invoice(inv_num, "CUST-FLOW-004", "Big Invoice Corp", amt))
        next_inv_id += 1

    # Two smaller payments that need to be allocated across large invoices
    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-30",
        "amount": 18000.00,  # Partial of 15000+12000+10000
        "description": "WIRE BIG INVOICE CORP PAYMENT 1",
        "customer_id": "CUST-FLOW-004",
        "customer_name": "Big Invoice Corp",
        "reference": None,
        "payment_method": "WIRE"
    })
    print(f"Added TXN-{next_bank_id:03d}: FLOW_MATCH - $18,000 partial across 3 large invoices")
    next_bank_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-30",
        "amount": 14000.00,
        "description": "WIRE BIG INVOICE CORP PAYMENT 2",
        "customer_id": "CUST-FLOW-004",
        "customer_name": "Big Invoice Corp",
        "reference": None,
        "payment_method": "WIRE"
    })
    print(f"Added TXN-{next_bank_id:03d}: FLOW_MATCH - $14,000 (second partial payment)")
    next_bank_id += 1

    # Scenario 4d: Many small invoices, one large payment
    for i in range(8):
        inv_num = f"INV-2026-{next_inv_id:04d}"
        amt = 1000 + (i * 250)  # 1000, 1250, 1500, 1750, 2000, 2250, 2500, 2750
        invoices.append(create_invoice(inv_num, "CUST-FLOW-005", "Many Invoices Ltd", amt))
        next_inv_id += 1

    # Sum of all: 1000+1250+1500+1750+2000+2250+2500+2750 = 15000
    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-31",
        "amount": 15000.00,
        "description": "ACH MANY INVOICES LTD BULK PAYMENT",
        "customer_id": "CUST-FLOW-005",
        "customer_name": "Many Invoices Ltd",
        "reference": None,
        "payment_method": "ACH"
    })
    print(f"Added TXN-{next_bank_id:03d}: FLOW_MATCH - $15,000 across 8 small invoices")
    next_bank_id += 1

    # Scenario 4e: Ambiguous amount scenario (needs flow to resolve)
    # Multiple invoices with same amount - flow picks based on other factors
    for i in range(3):
        inv_num = f"INV-2026-{next_inv_id:04d}"
        invoices.append(create_invoice(inv_num, f"CUST-FLOW-00{6+i}", f"Same Amount Corp {i+1}", 5000.00))
        next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-31",
        "amount": 5000.00,
        "description": "WIRE PAYMENT AMBIGUOUS",
        "customer_id": None,  # Unknown - multiple $5000 invoices from different customers
        "customer_name": None,
        "reference": None,
        "payment_method": "WIRE"
    })
    print(f"Added TXN-{next_bank_id:03d}: FLOW_MATCH - $5,000 (3 different customers with $5k invoices)")
    next_bank_id += 1

    # Save all files
    save_json('bank_transactions.json', banks)
    save_json('invoices.json', invoices)

    print("\n" + "=" * 60)
    print(f"Added suggestion test data:")
    print(f"  - 4 SINGLE_INVOICE scenarios (2 banks, 2 invoices)")
    print(f"  - 2 UNIQUE_AMOUNT scenarios (2 banks, 2 invoices)")
    print(f"  - 3 UNIQUE_COMBINATION scenarios (3 banks, 9 invoices)")
    print(f"  - 5 FLOW_MATCH scenarios (8 banks, 21 invoices)")
    print(f"\nNew totals: Banks={len(banks)}, Invoices={len(invoices)}")
    print("=" * 60)


if __name__ == '__main__':
    add_suggestion_data()
