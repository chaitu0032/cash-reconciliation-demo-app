"""Data loader utilities to convert JSON to model objects."""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Any

from .models.bank import BankTransaction
from .models.invoice import Invoice
from .models.remittance import Remittance, RemittanceLineItem


def parse_date(date_str: str):
    """Parse date string to date object."""
    if not date_str:
        return None
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def load_bank_transactions(filepath: str) -> List[BankTransaction]:
    """Load bank transactions from JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    transactions = []
    for item in data:
        tx = BankTransaction(
            id=item['id'],
            date=parse_date(item['date']),
            amount=Decimal(str(item['amount'])),
            description=item.get('description', ''),
            customer_id=item.get('customer_id'),
            reference=item.get('reference'),
            payment_method=item.get('payment_method')
        )
        transactions.append(tx)

    return transactions


def load_invoices(filepath: str) -> List[Invoice]:
    """Load invoices from JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    invoices = []
    for item in data:
        # Use balance_due as pending_amount if available, otherwise total_amount
        pending = item.get('balance_due', item.get('pending_amount', item['total_amount']))

        inv = Invoice(
            id=item.get('id', item['invoice_number']),
            invoice_number=item['invoice_number'],
            customer_id=item['customer_id'],
            amount=Decimal(str(item['total_amount'])),
            pending_amount=Decimal(str(pending)),
            due_date=parse_date(item['due_date'])
        )
        invoices.append(inv)

    return invoices


def load_remittances(filepath: str) -> List[Remittance]:
    """Load remittances from JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    remittances = []
    for item in data:
        # Parse line items
        line_items = []
        for li in item.get('line_items', []):
            line_item = RemittanceLineItem(
                invoice_number=li['invoice_number'],
                amount_paid=Decimal(str(li['amount_paid'])),
                invoice_date=parse_date(li.get('invoice_date')) if li.get('invoice_date') else None,
                invoice_amount_original=Decimal(str(li['invoice_amount_original'])) if li.get('invoice_amount_original') else None,
                remaining_balance=Decimal(str(li['remaining_balance'])) if li.get('remaining_balance') else None,
                deduction_amount=Decimal(str(li['deduction_amount'])) if li.get('deduction_amount') else None,
                deduction_reason=li.get('deduction_reason'),
                credit_note_reference=li.get('credit_note_reference')
            )
            line_items.append(line_item)

        rem = Remittance(
            id=item['id'],
            payer_name=item['payer_name'],
            payer_id=item['payer_id'],
            payment_date=parse_date(item['payment_date']),
            payment_amount_total=Decimal(str(item['payment_amount_total'])),
            payment_reference=item['payment_reference'],
            line_items=line_items,
            currency=item.get('currency', 'USD'),
            payment_method=item.get('payment_method', 'WIRE'),
            source=item.get('source', 'MANUAL')
        )
        remittances.append(rem)

    return remittances


def load_all_data(data_dir: str = 'data') -> tuple:
    """Load all data files and return model objects.

    Returns: (banks, invoices, remittances) - order matches engine.reconcile()
    """
    data_path = Path(data_dir)

    banks = load_bank_transactions(data_path / 'bank_transactions.json')
    invoices = load_invoices(data_path / 'invoices.json')
    remittances = load_remittances(data_path / 'remittances.json')

    return banks, invoices, remittances
