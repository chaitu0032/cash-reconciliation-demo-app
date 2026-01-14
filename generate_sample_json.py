"""Generate sample JSON data from complex_example for the dashboard."""
import json
import random
from datetime import date, timedelta
from decimal import Decimal

from models import InvoiceStatus

# Reuse functions from complex_example
from complex_example import (
    create_customers,
    create_invoices,
    create_remittances,
    inject_exceptions,
    create_bank_transactions,
)


class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def main():
    random.seed(42)

    customers = create_customers()
    invoices = create_invoices(customers)
    remittances = create_remittances(customers, invoices)
    remittances = inject_exceptions(remittances, invoices, customers)
    bank_transactions = create_bank_transactions(remittances, invoices, customers)

    data = {
        "customers": [
            {
                "customer_id": c.customer_id,
                "name": c.name,
                "aliases": c.aliases,
                "address": c.address,
                "payment_ref_patterns": c.payment_ref_patterns,
                "account_numbers": c.account_numbers,
            }
            for c in customers
        ],
        "invoices": [
            {
                "invoice_id": inv.invoice_id,
                "customer_id": inv.customer_id,
                "due_date": inv.due_date,
                "amount": inv.amount,
                "pending_amount": inv.pending_amount,
                "status": inv.status.value,
            }
            for inv in invoices
        ],
        "remittances": [
            {
                "id": rem.id,
                "customer_id": rem.customer_id,
                "customer_name": rem.customer_name,
                "customer_address": rem.customer_address,
                "payment_reference": rem.payment_reference,
                "payment_date": rem.payment_date,
                "line_items": [
                    {
                        "invoice_number": li.invoice_number,
                        "description": li.description,
                        "payment_method": li.payment_method,
                        "amount": li.amount,
                    }
                    for li in rem.line_items
                ],
            }
            for rem in remittances
        ],
        "bank_transactions": [
            {
                "id": bt.id,
                "amount": bt.amount,
                "date": bt.date,
                "reference": bt.reference,
                "description": bt.description,
            }
            for bt in bank_transactions
        ],
    }

    with open("sample_data/example.json", "w") as f:
        json.dump(data, f, cls=DateEncoder, indent=2)

    print(f"Generated sample_data/example.json")
    print(f"  Customers: {len(data['customers'])}")
    print(f"  Invoices: {len(data['invoices'])}")
    print(f"  Remittances: {len(data['remittances'])}")
    print(f"  Bank Transactions: {len(data['bank_transactions'])}")


if __name__ == "__main__":
    main()
