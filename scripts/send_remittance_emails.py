#!/usr/bin/env python3
"""
Send remittance advice emails with HTML content and PDF attachments.
"""

import smtplib
import json
import argparse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
import time


# Email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "yhgaa1122@gmail.com"
APP_PASSWORD = "fdso hzhd usvf puik"  # Gmail App Password


def send_remittance_email(
    recipient_email: str,
    remittance_id: str,
    html_content: str,
    pdf_path: str = None,
    payer_name: str = "",
    amount: float = 0.0
) -> bool:
    """Send a single remittance email."""

    try:
        # Create message
        msg = MIMEMultipart('mixed')
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient_email
        msg['Subject'] = f"Remittance Advice - {remittance_id} - {payer_name} - ${amount:,.2f}"

        # Create HTML part
        html_part = MIMEMultipart('alternative')
        html_body = MIMEText(html_content, 'html')
        html_part.attach(html_body)
        msg.attach(html_part)

        # Attach PDF if provided
        if pdf_path and Path(pdf_path).exists():
            with open(pdf_path, 'rb') as f:
                pdf_attachment = MIMEApplication(f.read(), _subtype='pdf')
                pdf_attachment.add_header(
                    'Content-Disposition',
                    'attachment',
                    filename=f'{remittance_id}.pdf'
                )
                msg.attach(pdf_attachment)

        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, APP_PASSWORD.replace(" ", ""))
            server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())

        return True

    except Exception as e:
        print(f"Error sending email for {remittance_id}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Send remittance emails')
    parser.add_argument('--recipient', default='hyperbots.remmitancebox@gmail.com',
                        help='Recipient email address')
    parser.add_argument('--remittances-json', default='data/remittances.json',
                        help='Path to remittances JSON file')
    parser.add_argument('--html-dir', default='output/remittances',
                        help='Directory containing HTML remittance files')
    parser.add_argument('--pdf-dir', default='output/remittances/pdf',
                        help='Directory containing PDF remittance files')
    parser.add_argument('--id', dest='remittance_id',
                        help='Send only specific remittance ID')
    parser.add_argument('--limit', type=int,
                        help='Limit number of emails to send')
    parser.add_argument('--delay', type=float, default=1.0,
                        help='Delay between emails in seconds (default: 1.0)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print what would be sent without actually sending')

    args = parser.parse_args()

    # Load remittances data
    with open(args.remittances_json, 'r') as f:
        remittances = json.load(f)

    # Filter by ID if specified
    if args.remittance_id:
        remittances = [r for r in remittances if r['id'] == args.remittance_id]

    # Apply limit
    if args.limit:
        remittances = remittances[:args.limit]

    html_dir = Path(args.html_dir)
    pdf_dir = Path(args.pdf_dir)

    print(f"Sending {len(remittances)} remittance emails to {args.recipient}")
    print("-" * 60)

    sent_count = 0
    failed_count = 0

    for i, rem in enumerate(remittances, 1):
        rem_id = rem['id']
        payer_name = rem['payer_name']
        amount = rem['payment_amount_total']

        html_file = html_dir / f"remittance_{rem_id}.html"
        pdf_file = pdf_dir / f"remittance_{rem_id}.pdf"

        if not html_file.exists():
            print(f"[{i}/{len(remittances)}] SKIP {rem_id} - HTML file not found")
            failed_count += 1
            continue

        html_content = html_file.read_text()
        pdf_path = str(pdf_file) if pdf_file.exists() else None

        if args.dry_run:
            print(f"[{i}/{len(remittances)}] DRY-RUN {rem_id} - {payer_name} - ${amount:,.2f}")
            sent_count += 1
        else:
            success = send_remittance_email(
                recipient_email=args.recipient,
                remittance_id=rem_id,
                html_content=html_content,
                pdf_path=pdf_path,
                payer_name=payer_name,
                amount=amount
            )

            if success:
                print(f"[{i}/{len(remittances)}] SENT {rem_id} - {payer_name} - ${amount:,.2f}")
                sent_count += 1
            else:
                print(f"[{i}/{len(remittances)}] FAILED {rem_id}")
                failed_count += 1

            # Delay between emails to avoid rate limiting
            if i < len(remittances):
                time.sleep(args.delay)

    print("-" * 60)
    print(f"Complete! Sent: {sent_count}, Failed: {failed_count}")


if __name__ == '__main__':
    main()
