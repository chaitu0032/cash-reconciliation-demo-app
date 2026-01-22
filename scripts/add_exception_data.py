"""
Add exception-causing data for Phase 1 and Phase 2 reconciliation testing.
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


def add_exception_data():
    banks = load_json('bank_transactions.json')
    remittances = load_json('remittances.json')
    invoices = load_json('invoices.json')

    # Get next IDs
    next_bank_id = len(banks) + 1
    next_rem_id = len(remittances) + 1
    next_inv_id = len(invoices) + 1

    print(f"Starting IDs: Bank={next_bank_id}, Rem={next_rem_id}, Inv={next_inv_id}")

    # =========================================================================
    # EXCEPTION 1: Amount Mismatch (Bank $25,000 vs Remittance $26,500 = 6% diff)
    # =========================================================================
    inv_num = f"INV-2026-{next_inv_id:04d}"
    invoices.append({
        "invoice_number": inv_num,
        "customer_id": "CUST-011",
        "customer_name": "Exception Test Corp",
        "invoice_date": "2025-12-01",
        "due_date": "2025-12-31",
        "payment_terms": "Net 30",
        "currency": "USD",
        "line_items": [{"line_id": 1, "description": "Test Service", "quantity": 1, "unit_price": 25000.00, "line_total": 25000.00}],
        "subtotal": 25000.00,
        "tax_rate": 0,
        "tax_amount": 0,
        "total_amount": 25000.00,
        "amount_paid": 0.0,
        "balance_due": 25000.00,
        "status": "OPEN",
        "payment_date": None,
        "remittance_id": None
    })
    next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-15",
        "amount": 25000.00,  # Bank says 25,000
        "description": "ACH CREDIT EXCEPTION TEST CORP TRN*EXCTEST001",
        "customer_id": "CUST-011",
        "customer_name": "Exception Test Corp",
        "reference": "EXCTEST001",
        "payment_method": "ACH"
    })
    next_bank_id += 1

    remittances.append({
        "id": f"REM-{next_rem_id:03d}",
        "payer_name": "Exception Test Corp",
        "payer_id": "CUST-011",
        "payment_date": "2026-01-15",
        "payment_amount_total": 26500.00,  # Remittance says 26,500 (6% mismatch - CRITICAL)
        "payment_reference": "EXCTEST001",
        "currency": "USD",
        "payment_method": "ACH",
        "source": "EMAIL",
        "line_items": [{"invoice_number": inv_num, "amount_paid": 26500.00}]
    })
    next_rem_id += 1
    print("Added: Amount Mismatch (CRITICAL - 6% diff)")

    # =========================================================================
    # EXCEPTION 2: Amount Mismatch Minor (Bank $15,000 vs Remittance $15,600 = 4% diff)
    # =========================================================================
    inv_num = f"INV-2026-{next_inv_id:04d}"
    invoices.append({
        "invoice_number": inv_num,
        "customer_id": "CUST-012",
        "customer_name": "Minor Diff LLC",
        "invoice_date": "2025-12-05",
        "due_date": "2026-01-04",
        "payment_terms": "Net 30",
        "currency": "USD",
        "line_items": [{"line_id": 1, "description": "Consulting", "quantity": 1, "unit_price": 15000.00, "line_total": 15000.00}],
        "subtotal": 15000.00,
        "tax_rate": 0,
        "tax_amount": 0,
        "total_amount": 15000.00,
        "amount_paid": 0.0,
        "balance_due": 15000.00,
        "status": "OPEN",
        "payment_date": None,
        "remittance_id": None
    })
    next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-16",
        "amount": 15000.00,
        "description": "WIRE TFR MINOR DIFF LLC REF:MINORDIFF001",
        "customer_id": "CUST-012",
        "customer_name": "Minor Diff LLC",
        "reference": "MINORDIFF001",
        "payment_method": "WIRE"
    })
    next_bank_id += 1

    remittances.append({
        "id": f"REM-{next_rem_id:03d}",
        "payer_name": "Minor Diff LLC",
        "payer_id": "CUST-012",
        "payment_date": "2026-01-16",
        "payment_amount_total": 15600.00,  # 4% diff - WARNING
        "payment_reference": "MINORDIFF001",
        "currency": "USD",
        "payment_method": "WIRE",
        "source": "PORTAL",
        "line_items": [{"invoice_number": inv_num, "amount_paid": 15600.00}]
    })
    next_rem_id += 1
    print("Added: Amount Mismatch (WARNING - 4% diff)")

    # =========================================================================
    # EXCEPTION 3: Customer Mismatch (Bank has CUST-013, Remittance has CUST-099)
    # =========================================================================
    inv_num = f"INV-2026-{next_inv_id:04d}"
    invoices.append({
        "invoice_number": inv_num,
        "customer_id": "CUST-013",
        "customer_name": "Correct Customer Inc",
        "invoice_date": "2025-12-10",
        "due_date": "2026-01-09",
        "payment_terms": "Net 30",
        "currency": "USD",
        "line_items": [{"line_id": 1, "description": "Equipment", "quantity": 1, "unit_price": 18500.00, "line_total": 18500.00}],
        "subtotal": 18500.00,
        "tax_rate": 0,
        "tax_amount": 0,
        "total_amount": 18500.00,
        "amount_paid": 0.0,
        "balance_due": 18500.00,
        "status": "OPEN",
        "payment_date": None,
        "remittance_id": None
    })
    next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-17",
        "amount": 18500.00,
        "description": "ACH PMT CORRECT CUSTOMER INC TRACE#CUSTMIS001",
        "customer_id": "CUST-013",  # Bank says CUST-013
        "customer_name": "Correct Customer Inc",
        "reference": "CUSTMIS001",
        "payment_method": "ACH"
    })
    next_bank_id += 1

    remittances.append({
        "id": f"REM-{next_rem_id:03d}",
        "payer_name": "Wrong Customer Corp",  # Different name
        "payer_id": "CUST-099",  # Remittance says CUST-099 - MISMATCH!
        "payment_date": "2026-01-17",
        "payment_amount_total": 18500.00,
        "payment_reference": "CUSTMIS001",
        "currency": "USD",
        "payment_method": "ACH",
        "source": "EDI",
        "line_items": [{"invoice_number": inv_num, "amount_paid": 18500.00}]
    })
    next_rem_id += 1
    print("Added: Customer Mismatch (WARNING)")

    # =========================================================================
    # EXCEPTION 4: Invoice Not Found (Line item references non-existent invoice)
    # =========================================================================
    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-18",
        "amount": 12000.00,
        "description": "WIRE TRANSFER PHANTOM INVOICES LLC REF:PHANTOM001",
        "customer_id": "CUST-014",
        "customer_name": "Phantom Invoices LLC",
        "reference": "PHANTOM001",
        "payment_method": "WIRE"
    })
    next_bank_id += 1

    remittances.append({
        "id": f"REM-{next_rem_id:03d}",
        "payer_name": "Phantom Invoices LLC",
        "payer_id": "CUST-014",
        "payment_date": "2026-01-18",
        "payment_amount_total": 12000.00,
        "payment_reference": "PHANTOM001",
        "currency": "USD",
        "payment_method": "WIRE",
        "source": "EMAIL",
        "line_items": [
            {"invoice_number": "INV-GHOST-0001", "amount_paid": 7000.00},  # Non-existent!
            {"invoice_number": "INV-GHOST-0002", "amount_paid": 5000.00}   # Non-existent!
        ]
    })
    next_rem_id += 1
    print("Added: Invoice Not Found (WARNING)")

    # =========================================================================
    # EXCEPTION 5: Overpayment (Pays more than invoice balance)
    # =========================================================================
    inv_num = f"INV-2026-{next_inv_id:04d}"
    invoices.append({
        "invoice_number": inv_num,
        "customer_id": "CUST-015",
        "customer_name": "Overpay Industries",
        "invoice_date": "2025-12-15",
        "due_date": "2026-01-14",
        "payment_terms": "Net 30",
        "currency": "USD",
        "line_items": [{"line_id": 1, "description": "Services", "quantity": 1, "unit_price": 8000.00, "line_total": 8000.00}],
        "subtotal": 8000.00,
        "tax_rate": 0,
        "tax_amount": 0,
        "total_amount": 8000.00,
        "amount_paid": 0.0,
        "balance_due": 8000.00,  # Only $8,000 due
        "status": "OPEN",
        "payment_date": None,
        "remittance_id": None
    })
    next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-19",
        "amount": 10000.00,
        "description": "ACH CREDIT OVERPAY INDUSTRIES TRN*OVERPAY001",
        "customer_id": "CUST-015",
        "customer_name": "Overpay Industries",
        "reference": "OVERPAY001",
        "payment_method": "ACH"
    })
    next_bank_id += 1

    remittances.append({
        "id": f"REM-{next_rem_id:03d}",
        "payer_name": "Overpay Industries",
        "payer_id": "CUST-015",
        "payment_date": "2026-01-19",
        "payment_amount_total": 10000.00,
        "payment_reference": "OVERPAY001",
        "currency": "USD",
        "payment_method": "ACH",
        "source": "PORTAL",
        "line_items": [{"invoice_number": inv_num, "amount_paid": 10000.00}]  # Paying $10,000 on $8,000 invoice!
    })
    next_rem_id += 1
    print("Added: Overpayment (WARNING)")

    # =========================================================================
    # EXCEPTION 6: Line Items Sum Mismatch (Total != sum of line items)
    # =========================================================================
    inv_num1 = f"INV-2026-{next_inv_id:04d}"
    invoices.append({
        "invoice_number": inv_num1,
        "customer_id": "CUST-016",
        "customer_name": "Sum Mismatch Co",
        "invoice_date": "2025-12-20",
        "due_date": "2026-01-19",
        "payment_terms": "Net 30",
        "currency": "USD",
        "line_items": [{"line_id": 1, "description": "Product A", "quantity": 1, "unit_price": 5000.00, "line_total": 5000.00}],
        "subtotal": 5000.00,
        "tax_rate": 0,
        "tax_amount": 0,
        "total_amount": 5000.00,
        "amount_paid": 0.0,
        "balance_due": 5000.00,
        "status": "OPEN",
        "payment_date": None,
        "remittance_id": None
    })
    next_inv_id += 1

    inv_num2 = f"INV-2026-{next_inv_id:04d}"
    invoices.append({
        "invoice_number": inv_num2,
        "customer_id": "CUST-016",
        "customer_name": "Sum Mismatch Co",
        "invoice_date": "2025-12-21",
        "due_date": "2026-01-20",
        "payment_terms": "Net 30",
        "currency": "USD",
        "line_items": [{"line_id": 1, "description": "Product B", "quantity": 1, "unit_price": 7000.00, "line_total": 7000.00}],
        "subtotal": 7000.00,
        "tax_rate": 0,
        "tax_amount": 0,
        "total_amount": 7000.00,
        "amount_paid": 0.0,
        "balance_due": 7000.00,
        "status": "OPEN",
        "payment_date": None,
        "remittance_id": None
    })
    next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-20",
        "amount": 12000.00,
        "description": "WIRE SUM MISMATCH CO REF:SUMMIS001",
        "customer_id": "CUST-016",
        "customer_name": "Sum Mismatch Co",
        "reference": "SUMMIS001",
        "payment_method": "WIRE"
    })
    next_bank_id += 1

    remittances.append({
        "id": f"REM-{next_rem_id:03d}",
        "payer_name": "Sum Mismatch Co",
        "payer_id": "CUST-016",
        "payment_date": "2026-01-20",
        "payment_amount_total": 12000.00,  # Total says 12,000
        "payment_reference": "SUMMIS001",
        "currency": "USD",
        "payment_method": "WIRE",
        "source": "EMAIL",
        "line_items": [
            {"invoice_number": inv_num1, "amount_paid": 5000.00},
            {"invoice_number": inv_num2, "amount_paid": 6000.00}  # Sum = 11,000, not 12,000!
        ]
    })
    next_rem_id += 1
    print("Added: Line Items Sum Mismatch (WARNING)")

    # =========================================================================
    # EXCEPTION 7: Deduction Without Reason
    # =========================================================================
    inv_num = f"INV-2026-{next_inv_id:04d}"
    invoices.append({
        "invoice_number": inv_num,
        "customer_id": "CUST-017",
        "customer_name": "Mysterious Deduction Inc",
        "invoice_date": "2025-12-22",
        "due_date": "2026-01-21",
        "payment_terms": "Net 30",
        "currency": "USD",
        "line_items": [{"line_id": 1, "description": "Full Service", "quantity": 1, "unit_price": 20000.00, "line_total": 20000.00}],
        "subtotal": 20000.00,
        "tax_rate": 0,
        "tax_amount": 0,
        "total_amount": 20000.00,
        "amount_paid": 0.0,
        "balance_due": 20000.00,
        "status": "OPEN",
        "payment_date": None,
        "remittance_id": None
    })
    next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-21",
        "amount": 18500.00,
        "description": "ACH PMT MYSTERIOUS DEDUCTION INC TRN*DEDUCT001",
        "customer_id": "CUST-017",
        "customer_name": "Mysterious Deduction Inc",
        "reference": "DEDUCT001",
        "payment_method": "ACH"
    })
    next_bank_id += 1

    remittances.append({
        "id": f"REM-{next_rem_id:03d}",
        "payer_name": "Mysterious Deduction Inc",
        "payer_id": "CUST-017",
        "payment_date": "2026-01-21",
        "payment_amount_total": 18500.00,
        "payment_reference": "DEDUCT001",
        "currency": "USD",
        "payment_method": "ACH",
        "source": "EDI",
        "line_items": [{
            "invoice_number": inv_num,
            "amount_paid": 18500.00,
            "deduction_amount": 1500.00,  # Deduction without reason!
            "deduction_reason": None  # No reason given
        }]
    })
    next_rem_id += 1
    print("Added: Deduction Without Reason (INFO)")

    # =========================================================================
    # EXCEPTION 8: Multiple Issues - Amount Mismatch + Customer Mismatch
    # =========================================================================
    inv_num = f"INV-2026-{next_inv_id:04d}"
    invoices.append({
        "invoice_number": inv_num,
        "customer_id": "CUST-018",
        "customer_name": "Multi Problem Corp",
        "invoice_date": "2025-12-25",
        "due_date": "2026-01-24",
        "payment_terms": "Net 30",
        "currency": "USD",
        "line_items": [{"line_id": 1, "description": "Complex Service", "quantity": 1, "unit_price": 30000.00, "line_total": 30000.00}],
        "subtotal": 30000.00,
        "tax_rate": 0,
        "tax_amount": 0,
        "total_amount": 30000.00,
        "amount_paid": 0.0,
        "balance_due": 30000.00,
        "status": "OPEN",
        "payment_date": None,
        "remittance_id": None
    })
    next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-22",
        "amount": 30000.00,
        "description": "WIRE MULTI PROBLEM CORP REF:MULTI001",
        "customer_id": "CUST-018",
        "customer_name": "Multi Problem Corp",
        "reference": "MULTI001",
        "payment_method": "WIRE"
    })
    next_bank_id += 1

    remittances.append({
        "id": f"REM-{next_rem_id:03d}",
        "payer_name": "Different Company Name",  # Wrong name
        "payer_id": "CUST-098",  # Wrong customer ID
        "payment_date": "2026-01-22",
        "payment_amount_total": 32000.00,  # Wrong amount (6.67% diff)
        "payment_reference": "MULTI001",
        "currency": "USD",
        "payment_method": "WIRE",
        "source": "PORTAL",
        "line_items": [{"invoice_number": inv_num, "amount_paid": 32000.00}]
    })
    next_rem_id += 1
    print("Added: Multiple Issues - Amount + Customer Mismatch (CRITICAL)")

    # =========================================================================
    # EXCEPTION 9: Duplicate Payment (Invoice marked as already paid via amount_paid > 0)
    # =========================================================================
    inv_num = f"INV-2026-{next_inv_id:04d}"
    invoices.append({
        "invoice_number": inv_num,
        "customer_id": "CUST-019",
        "customer_name": "Double Pay Enterprises",
        "invoice_date": "2025-12-01",
        "due_date": "2025-12-31",
        "payment_terms": "Net 30",
        "currency": "USD",
        "line_items": [{"line_id": 1, "description": "Single Service", "quantity": 1, "unit_price": 9500.00, "line_total": 9500.00}],
        "subtotal": 9500.00,
        "tax_rate": 0,
        "tax_amount": 0,
        "total_amount": 9500.00,
        "amount_paid": 9500.00,  # Already paid!
        "balance_due": 0.0,
        "status": "CLOSED",  # Already closed
        "payment_date": "2025-12-28",
        "remittance_id": "REM-PREV-001"
    })
    next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-23",
        "amount": 9500.00,
        "description": "ACH CREDIT DOUBLE PAY ENTERPRISES TRN*DUPE001",
        "customer_id": "CUST-019",
        "customer_name": "Double Pay Enterprises",
        "reference": "DUPE001",
        "payment_method": "ACH"
    })
    next_bank_id += 1

    remittances.append({
        "id": f"REM-{next_rem_id:03d}",
        "payer_name": "Double Pay Enterprises",
        "payer_id": "CUST-019",
        "payment_date": "2026-01-23",
        "payment_amount_total": 9500.00,
        "payment_reference": "DUPE001",
        "currency": "USD",
        "payment_method": "ACH",
        "source": "EMAIL",
        "line_items": [{"invoice_number": inv_num, "amount_paid": 9500.00}]  # Trying to pay again!
    })
    next_rem_id += 1
    print("Added: Duplicate Payment (CRITICAL)")

    # =========================================================================
    # EXCEPTION 10: Date Discrepancy (Payment date far from invoice due date)
    # =========================================================================
    inv_num = f"INV-2026-{next_inv_id:04d}"
    invoices.append({
        "invoice_number": inv_num,
        "customer_id": "CUST-020",
        "customer_name": "Late Payer Inc",
        "invoice_date": "2025-10-01",
        "due_date": "2025-10-31",  # Due date was October 31st
        "payment_terms": "Net 30",
        "currency": "USD",
        "line_items": [{"line_id": 1, "description": "Old Service", "quantity": 1, "unit_price": 14000.00, "line_total": 14000.00}],
        "subtotal": 14000.00,
        "tax_rate": 0,
        "tax_amount": 0,
        "total_amount": 14000.00,
        "amount_paid": 0.0,
        "balance_due": 14000.00,
        "status": "OPEN",
        "payment_date": None,
        "remittance_id": None
    })
    next_inv_id += 1

    banks.append({
        "id": f"TXN-{next_bank_id:03d}",
        "date": "2026-01-24",  # Payment in late January - months late!
        "amount": 14000.00,
        "description": "WIRE LATE PAYER INC REF:LATE001",
        "customer_id": "CUST-020",
        "customer_name": "Late Payer Inc",
        "reference": "LATE001",
        "payment_method": "WIRE"
    })
    next_bank_id += 1

    remittances.append({
        "id": f"REM-{next_rem_id:03d}",
        "payer_name": "Late Payer Inc",
        "payer_id": "CUST-020",
        "payment_date": "2026-01-24",
        "payment_amount_total": 14000.00,
        "payment_reference": "LATE001",
        "currency": "USD",
        "payment_method": "WIRE",
        "source": "MANUAL",
        "line_items": [{"invoice_number": inv_num, "amount_paid": 14000.00}]
    })
    next_rem_id += 1
    print("Added: Date Discrepancy / Late Payment (INFO)")

    # Save all files
    save_json('bank_transactions.json', banks)
    save_json('remittances.json', remittances)
    save_json('invoices.json', invoices)

    print("\n" + "=" * 60)
    print(f"Added 10 exception scenarios")
    print(f"New totals: Banks={len(banks)}, Remittances={len(remittances)}, Invoices={len(invoices)}")
    print("=" * 60)


if __name__ == '__main__':
    add_exception_data()
