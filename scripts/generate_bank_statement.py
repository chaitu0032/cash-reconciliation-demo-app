#!/usr/bin/env python3
"""
Generate a bank statement from JSON transaction data.
Outputs HTML and optionally PDF formats.
"""

import json
import argparse
from datetime import datetime
from pathlib import Path


def load_transactions(json_path: str) -> list:
    """Load transactions from JSON file."""
    with open(json_path, 'r') as f:
        return json.load(f)


def format_transaction_row(txn: dict) -> str:
    """Format a single transaction row as HTML."""
    amount_class = 'credit' if txn['amount'] > 0 else 'debit'
    amount_sign = '+' if txn['amount'] > 0 else ''
    return f"""
    <tr>
        <td class="date">{txn['date']}</td>
        <td class="description">{txn['description']}</td>
        <td class="reference">{txn.get('reference', '')}</td>
        <td class="amount {amount_class}">{amount_sign}${txn['amount']:,.2f}</td>
        <td class="balance">${txn['running_balance']:,.2f}</td>
    </tr>"""


def generate_bank_statement_html(
    transactions: list,
    account_name: str = "Business Account",
    account_number: str = "****1234",
    bank_name: str = "Bank of America",
    start_date: str = None,
    end_date: str = None,
    opening_balance: float = 0.0
) -> str:
    """Generate HTML bank statement from transactions."""

    # Filter by date range if provided
    if start_date:
        transactions = [t for t in transactions if t['date'] >= start_date]
    if end_date:
        transactions = [t for t in transactions if t['date'] <= end_date]

    # Sort by date
    transactions = sorted(transactions, key=lambda x: (x['date'], x['id']))

    # Calculate running balance
    running_balance = opening_balance
    for txn in transactions:
        running_balance += txn['amount']
        txn['running_balance'] = running_balance

    closing_balance = running_balance
    total_credits = sum(t['amount'] for t in transactions if t['amount'] > 0)
    total_debits = sum(t['amount'] for t in transactions if t['amount'] < 0)

    # Determine statement period
    if transactions:
        period_start = start_date or transactions[0]['date']
        period_end = end_date or transactions[-1]['date']
    else:
        period_start = start_date or datetime.now().strftime('%Y-%m-%d')
        period_end = end_date or datetime.now().strftime('%Y-%m-%d')

    # Build transaction rows
    if transactions:
        transaction_rows = ''.join(format_transaction_row(txn) for txn in transactions)
        transactions_html = f"""
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Description</th>
                        <th>Reference</th>
                        <th>Amount</th>
                        <th>Balance</th>
                    </tr>
                </thead>
                <tbody>
                    {transaction_rows}
                </tbody>
            </table>"""
    else:
        transactions_html = "<p class='no-transactions'>No transactions for this period.</p>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bank Statement - {account_name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }}
        .container {{
            max-width: 900px;
            margin: 20px auto;
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #1a365d 0%, #2c5282 100%);
            color: white;
            padding: 30px 40px;
        }}
        .bank-name {{
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .statement-title {{
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 2px;
            opacity: 0.9;
        }}
        .account-info {{
            display: flex;
            justify-content: space-between;
            padding: 25px 40px;
            background: #f8fafc;
            border-bottom: 1px solid #e2e8f0;
        }}
        .account-details h3 {{
            color: #1a365d;
            font-size: 18px;
            margin-bottom: 8px;
        }}
        .account-details p {{
            color: #64748b;
            font-size: 14px;
        }}
        .statement-period {{
            text-align: right;
        }}
        .statement-period h4 {{
            color: #64748b;
            font-size: 12px;
            text-transform: uppercase;
            margin-bottom: 5px;
        }}
        .statement-period p {{
            color: #1a365d;
            font-size: 14px;
            font-weight: 500;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            padding: 25px 40px;
            background: white;
            border-bottom: 2px solid #e2e8f0;
        }}
        .summary-item {{
            text-align: center;
            padding: 15px;
            background: #f8fafc;
            border-radius: 8px;
        }}
        .summary-item .label {{
            font-size: 11px;
            text-transform: uppercase;
            color: #64748b;
            margin-bottom: 5px;
        }}
        .summary-item .value {{
            font-size: 20px;
            font-weight: bold;
            color: #1a365d;
        }}
        .summary-item.credit .value {{
            color: #059669;
        }}
        .summary-item.debit .value {{
            color: #dc2626;
        }}
        .transactions {{
            padding: 20px 40px 40px;
        }}
        .transactions h3 {{
            color: #1a365d;
            margin-bottom: 20px;
            font-size: 16px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            background: #1a365d;
            color: white;
            padding: 12px 15px;
            text-align: left;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        th:last-child, th:nth-child(4) {{
            text-align: right;
        }}
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #e2e8f0;
            font-size: 13px;
        }}
        tr:hover {{
            background: #f8fafc;
        }}
        .date {{
            color: #64748b;
            white-space: nowrap;
        }}
        .description {{
            max-width: 300px;
        }}
        .reference {{
            color: #64748b;
            font-family: monospace;
            font-size: 11px;
        }}
        .amount {{
            text-align: right;
            font-weight: 500;
            font-family: monospace;
        }}
        .amount.credit {{
            color: #059669;
        }}
        .amount.debit {{
            color: #dc2626;
        }}
        .balance {{
            text-align: right;
            font-family: monospace;
            color: #1a365d;
        }}
        .footer {{
            background: #f8fafc;
            padding: 20px 40px;
            text-align: center;
            font-size: 11px;
            color: #64748b;
            border-top: 1px solid #e2e8f0;
        }}
        .no-transactions {{
            text-align: center;
            padding: 40px;
            color: #64748b;
        }}
        @media print {{
            body {{
                background: white;
            }}
            .container {{
                box-shadow: none;
                margin: 0;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="bank-name">{bank_name}</div>
            <div class="statement-title">Account Statement</div>
        </div>

        <div class="account-info">
            <div class="account-details">
                <h3>{account_name}</h3>
                <p>Account Number: {account_number}</p>
            </div>
            <div class="statement-period">
                <h4>Statement Period</h4>
                <p>{period_start} to {period_end}</p>
            </div>
        </div>

        <div class="summary">
            <div class="summary-item">
                <div class="label">Opening Balance</div>
                <div class="value">${opening_balance:,.2f}</div>
            </div>
            <div class="summary-item credit">
                <div class="label">Total Credits</div>
                <div class="value">+${total_credits:,.2f}</div>
            </div>
            <div class="summary-item debit">
                <div class="label">Total Debits</div>
                <div class="value">${total_debits:,.2f}</div>
            </div>
            <div class="summary-item">
                <div class="label">Closing Balance</div>
                <div class="value">${closing_balance:,.2f}</div>
            </div>
        </div>

        <div class="transactions">
            <h3>Transaction Details</h3>
            {transactions_html}
        </div>

        <div class="footer">
            <p>This statement was generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Please review all transactions and report any discrepancies within 30 days.</p>
        </div>
    </div>
</body>
</html>"""

    return html


def main():
    parser = argparse.ArgumentParser(description='Generate bank statement from JSON transactions')
    parser.add_argument('input', help='Path to JSON file containing transactions')
    parser.add_argument('-o', '--output', help='Output file path (default: bank_statement.html)')
    parser.add_argument('--account-name', default='Business Account', help='Account name')
    parser.add_argument('--account-number', default='****1234', help='Account number (masked)')
    parser.add_argument('--bank-name', default='Bank of America', help='Bank name')
    parser.add_argument('--start-date', help='Start date filter (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='End date filter (YYYY-MM-DD)')
    parser.add_argument('--opening-balance', type=float, default=0.0, help='Opening balance')

    args = parser.parse_args()

    # Load transactions
    transactions = load_transactions(args.input)

    # Generate HTML
    html = generate_bank_statement_html(
        transactions=transactions,
        account_name=args.account_name,
        account_number=args.account_number,
        bank_name=args.bank_name,
        start_date=args.start_date,
        end_date=args.end_date,
        opening_balance=args.opening_balance
    )

    # Determine output path
    output_path = args.output or 'bank_statement.html'

    # Write output
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)

    print(f"Bank statement generated: {output_path}")
    print(f"Transactions included: {len(transactions)}")


if __name__ == '__main__':
    main()
