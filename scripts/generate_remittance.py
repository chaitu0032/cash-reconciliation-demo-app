#!/usr/bin/env python3
"""
Generate remittance advice email/HTML template from JSON data.
Can output HTML or plain text email format.
"""

import json
import argparse
from datetime import datetime
from pathlib import Path


def load_remittances(json_path: str) -> list:
    """Load remittances from JSON file."""
    with open(json_path, 'r') as f:
        return json.load(f)


def generate_remittance_html(remittance: dict, company_info: dict = None) -> str:
    """Generate HTML remittance advice from a single remittance record."""

    if company_info is None:
        company_info = {
            'name': 'Your Company Name',
            'address': '123 Business Street, Suite 100',
            'city_state_zip': 'New York, NY 10001',
            'phone': '(555) 123-4567',
            'email': 'accounts@company.com'
        }

    line_items_html = ""
    for item in remittance.get('line_items', []):
        line_items_html += f"""
        <tr>
            <td style="padding: 12px 15px; border-bottom: 1px solid #e5e7eb; font-family: monospace;">{item['invoice_number']}</td>
            <td style="padding: 12px 15px; border-bottom: 1px solid #e5e7eb; text-align: right; font-family: monospace;">{remittance.get('currency', 'USD')} {item['amount_paid']:,.2f}</td>
        </tr>
        """

    payment_method_display = {
        'ACH': 'ACH Transfer',
        'WIRE': 'Wire Transfer',
        'SWIFT': 'SWIFT Transfer',
        'CHECK': 'Check Payment'
    }.get(remittance.get('payment_method', ''), remittance.get('payment_method', 'N/A'))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Remittance Advice - {remittance['id']}</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f3f4f6;">
    <table cellpadding="0" cellspacing="0" width="100%" style="max-width: 650px; margin: 20px auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        <!-- Header -->
        <tr>
            <td style="background: linear-gradient(135deg, #059669 0%, #047857 100%); padding: 30px 40px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600;">Remittance Advice</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0; font-size: 14px;">Payment Notification</p>
            </td>
        </tr>

        <!-- Payer Info -->
        <tr>
            <td style="padding: 30px 40px; border-bottom: 1px solid #e5e7eb;">
                <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                        <td width="50%" style="vertical-align: top;">
                            <p style="margin: 0 0 5px; font-size: 11px; text-transform: uppercase; color: #6b7280; letter-spacing: 1px;">From</p>
                            <p style="margin: 0; font-size: 18px; font-weight: 600; color: #111827;">{remittance['payer_name']}</p>
                            <p style="margin: 5px 0 0; font-size: 13px; color: #6b7280;">Customer ID: {remittance['payer_id']}</p>
                        </td>
                        <td width="50%" style="vertical-align: top; text-align: right;">
                            <p style="margin: 0 0 5px; font-size: 11px; text-transform: uppercase; color: #6b7280; letter-spacing: 1px;">Remittance ID</p>
                            <p style="margin: 0; font-size: 16px; font-weight: 600; color: #059669; font-family: monospace;">{remittance['id']}</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>

        <!-- Payment Details -->
        <tr>
            <td style="padding: 25px 40px; background-color: #f9fafb;">
                <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                        <td width="33%" style="padding: 10px 0;">
                            <p style="margin: 0 0 5px; font-size: 11px; text-transform: uppercase; color: #6b7280;">Payment Date</p>
                            <p style="margin: 0; font-size: 15px; font-weight: 500; color: #111827;">{remittance['payment_date']}</p>
                        </td>
                        <td width="33%" style="padding: 10px 0;">
                            <p style="margin: 0 0 5px; font-size: 11px; text-transform: uppercase; color: #6b7280;">Payment Method</p>
                            <p style="margin: 0; font-size: 15px; font-weight: 500; color: #111827;">{payment_method_display}</p>
                        </td>
                        <td width="33%" style="padding: 10px 0;">
                            <p style="margin: 0 0 5px; font-size: 11px; text-transform: uppercase; color: #6b7280;">Reference</p>
                            <p style="margin: 0; font-size: 13px; font-weight: 500; color: #111827; font-family: monospace; word-break: break-all;">{remittance['payment_reference']}</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>

        <!-- Total Amount Banner -->
        <tr>
            <td style="padding: 25px 40px; background: linear-gradient(135deg, #10b981 0%, #059669 100%); text-align: center;">
                <p style="margin: 0 0 5px; font-size: 12px; text-transform: uppercase; color: rgba(255,255,255,0.8); letter-spacing: 1px;">Total Payment Amount</p>
                <p style="margin: 0; font-size: 32px; font-weight: 700; color: #ffffff;">{remittance.get('currency', 'USD')} {remittance['payment_amount_total']:,.2f}</p>
            </td>
        </tr>

        <!-- Invoice Details -->
        <tr>
            <td style="padding: 30px 40px;">
                <h3 style="margin: 0 0 20px; font-size: 14px; text-transform: uppercase; color: #374151; letter-spacing: 1px;">Invoice Details</h3>
                <table width="100%" cellpadding="0" cellspacing="0" style="border: 1px solid #e5e7eb; border-radius: 6px; overflow: hidden;">
                    <thead>
                        <tr style="background-color: #374151;">
                            <th style="padding: 12px 15px; text-align: left; font-size: 12px; text-transform: uppercase; color: #ffffff; letter-spacing: 0.5px;">Invoice Number</th>
                            <th style="padding: 12px 15px; text-align: right; font-size: 12px; text-transform: uppercase; color: #ffffff; letter-spacing: 0.5px;">Amount Paid</th>
                        </tr>
                    </thead>
                    <tbody>
                        {line_items_html}
                    </tbody>
                    <tfoot>
                        <tr style="background-color: #f3f4f6;">
                            <td style="padding: 15px; font-weight: 600; color: #374151;">Total</td>
                            <td style="padding: 15px; text-align: right; font-weight: 700; color: #059669; font-family: monospace; font-size: 16px;">{remittance.get('currency', 'USD')} {remittance['payment_amount_total']:,.2f}</td>
                        </tr>
                    </tfoot>
                </table>
            </td>
        </tr>

        <!-- Footer -->
        <tr>
            <td style="padding: 25px 40px; background-color: #f9fafb; border-top: 1px solid #e5e7eb;">
                <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                        <td style="vertical-align: top;">
                            <p style="margin: 0 0 5px; font-size: 14px; font-weight: 600; color: #374151;">{company_info['name']}</p>
                            <p style="margin: 0; font-size: 12px; color: #6b7280;">{company_info['address']}</p>
                            <p style="margin: 0; font-size: 12px; color: #6b7280;">{company_info['city_state_zip']}</p>
                        </td>
                        <td style="vertical-align: top; text-align: right;">
                            <p style="margin: 0; font-size: 12px; color: #6b7280;">{company_info['phone']}</p>
                            <p style="margin: 0; font-size: 12px; color: #6b7280;">{company_info['email']}</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>

        <!-- Disclaimer -->
        <tr>
            <td style="padding: 20px 40px; background-color: #374151; text-align: center;">
                <p style="margin: 0; font-size: 11px; color: #9ca3af;">This is an automated remittance advice. Please retain for your records.</p>
                <p style="margin: 5px 0 0; font-size: 11px; color: #9ca3af;">Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </td>
        </tr>
    </table>
</body>
</html>"""

    return html


def generate_remittance_text(remittance: dict, company_info: dict = None) -> str:
    """Generate plain text remittance advice for email."""

    if company_info is None:
        company_info = {
            'name': 'Your Company Name',
            'email': 'accounts@company.com'
        }

    payment_method_display = {
        'ACH': 'ACH Transfer',
        'WIRE': 'Wire Transfer',
        'SWIFT': 'SWIFT Transfer',
        'CHECK': 'Check Payment'
    }.get(remittance.get('payment_method', ''), remittance.get('payment_method', 'N/A'))

    lines = [
        "=" * 60,
        "REMITTANCE ADVICE",
        "=" * 60,
        "",
        f"Remittance ID:    {remittance['id']}",
        f"From:             {remittance['payer_name']}",
        f"Customer ID:      {remittance['payer_id']}",
        "",
        "-" * 60,
        "PAYMENT DETAILS",
        "-" * 60,
        f"Payment Date:     {remittance['payment_date']}",
        f"Payment Method:   {payment_method_display}",
        f"Reference:        {remittance['payment_reference']}",
        f"Currency:         {remittance.get('currency', 'USD')}",
        "",
        f"TOTAL AMOUNT:     {remittance.get('currency', 'USD')} {remittance['payment_amount_total']:,.2f}",
        "",
        "-" * 60,
        "INVOICE DETAILS",
        "-" * 60,
        f"{'Invoice Number':<25} {'Amount Paid':>20}",
        "-" * 60,
    ]

    for item in remittance.get('line_items', []):
        lines.append(f"{item['invoice_number']:<25} {remittance.get('currency', 'USD')} {item['amount_paid']:>15,.2f}")

    lines.extend([
        "-" * 60,
        f"{'TOTAL':<25} {remittance.get('currency', 'USD')} {remittance['payment_amount_total']:>15,.2f}",
        "=" * 60,
        "",
        f"From: {company_info['name']}",
        f"Contact: {company_info['email']}",
        "",
        "This is an automated remittance advice. Please retain for your records.",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='Generate remittance advice from JSON data')
    parser.add_argument('input', help='Path to JSON file containing remittances')
    parser.add_argument('-o', '--output', help='Output file path (default: remittance_<id>.html)')
    parser.add_argument('--format', choices=['html', 'text', 'both'], default='html',
                        help='Output format (default: html)')
    parser.add_argument('--id', dest='remittance_id', help='Generate for specific remittance ID')
    parser.add_argument('--all', action='store_true', help='Generate for all remittances')
    parser.add_argument('--output-dir', default='.', help='Output directory for multiple files')
    parser.add_argument('--company-name', default='Your Company Name', help='Company name')
    parser.add_argument('--company-email', default='accounts@company.com', help='Company email')

    args = parser.parse_args()

    # Load remittances
    remittances = load_remittances(args.input)

    company_info = {
        'name': args.company_name,
        'address': '123 Business Street, Suite 100',
        'city_state_zip': 'New York, NY 10001',
        'phone': '(555) 123-4567',
        'email': args.company_email
    }

    # Filter remittances
    if args.remittance_id:
        remittances = [r for r in remittances if r['id'] == args.remittance_id]
        if not remittances:
            print(f"Error: Remittance ID '{args.remittance_id}' not found.")
            return
    elif not args.all:
        # Default to first remittance if no filter specified
        remittances = remittances[:1]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create output directory for single file output if needed
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    for remittance in remittances:
        rem_id = remittance['id']

        if args.format in ['html', 'both']:
            html_content = generate_remittance_html(remittance, company_info)
            if args.output and len(remittances) == 1:
                html_path = args.output
            else:
                html_path = output_dir / f"remittance_{rem_id}.html"

            with open(html_path, 'w') as f:
                f.write(html_content)
            print(f"Generated HTML: {html_path}")

        if args.format in ['text', 'both']:
            text_content = generate_remittance_text(remittance, company_info)
            if args.output and len(remittances) == 1 and args.format == 'text':
                text_path = args.output
            else:
                text_path = output_dir / f"remittance_{rem_id}.txt"

            with open(text_path, 'w') as f:
                f.write(text_content)
            print(f"Generated text: {text_path}")

    print(f"\nTotal remittances processed: {len(remittances)}")


if __name__ == '__main__':
    main()
