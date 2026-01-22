"""
Dummy ERP System - Invoice Management (FastAPI)
Simulates an ERP system where invoices can be fetched, viewed, and exported as PDF.
"""

import json
import io
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Dummy ERP System", description="Invoice Management API")

# Mount static files from main project
STATIC_DIR = Path(__file__).parent.parent / 'static'
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR.parent / 'data'
OUTPUT_DIR = BASE_DIR.parent / 'output' / 'invoices'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Templates
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ============================================================================
# STARTUP EVENT - Reset all invoices to OPEN on reload
# ============================================================================

@app.on_event("startup")
def reset_invoices_on_startup():
    """Reset all invoice statuses to OPEN when the app starts."""
    invoices_file = DATA_DIR / 'invoices.json'
    if not invoices_file.exists():
        print("No invoices file found, skipping reset.")
        return

    with open(invoices_file, 'r') as f:
        invoices = json.load(f)

    reset_count = 0
    for inv in invoices:
        if inv.get('status') != 'OPEN':
            inv['status'] = 'OPEN'
            # Reset payment fields
            inv['amount_paid'] = 0.0
            inv['balance_due'] = inv.get('total_amount', 0)
            reset_count += 1

    if reset_count > 0:
        with open(invoices_file, 'w') as f:
            json.dump(invoices, f, indent=2)
        print(f"Reset {reset_count} invoice(s) to OPEN status.")
    else:
        print("All invoices already OPEN.")


# Pydantic models
class StatusUpdate(BaseModel):
    status: str


def load_invoices():
    """Load invoices from JSON file."""
    invoices_file = DATA_DIR / 'invoices.json'
    if not invoices_file.exists():
        return []
    with open(invoices_file, 'r') as f:
        return json.load(f)


def save_invoices(invoices: list):
    """Save invoices to JSON file."""
    invoices_file = DATA_DIR / 'invoices.json'
    with open(invoices_file, 'w') as f:
        json.dump(invoices, f, indent=2, default=decimal_default)


def get_invoice_by_number(invoice_number: str):
    """Get a single invoice by its number."""
    invoices = load_invoices()
    for inv in invoices:
        if inv.get('invoice_number') == invoice_number:
            return inv
    return None


def decimal_default(obj):
    """JSON serializer for Decimal objects."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get('/api/invoices')
def list_invoices(
    status: Optional[str] = Query(None, description="Filter by status"),
    customer_id: Optional[str] = Query(None, description="Filter by customer"),
    limit: int = Query(50, description="Max results"),
    offset: int = Query(0, description="Pagination offset")
):
    """
    List all invoices with optional filtering.
    """
    invoices = load_invoices()

    # Apply filters
    if status:
        invoices = [inv for inv in invoices if inv.get('status', '').upper() == status.upper()]

    if customer_id:
        invoices = [inv for inv in invoices if inv.get('customer_id') == customer_id]

    total = len(invoices)
    invoices = invoices[offset:offset + limit]

    return {
        'success': True,
        'total': total,
        'limit': limit,
        'offset': offset,
        'invoices': invoices
    }


@app.get('/api/invoices/summary')
def get_invoice_summary():
    """Get summary statistics of all invoices."""
    invoices = load_invoices()

    summary = {
        'total_invoices': len(invoices),
        'by_status': {},
        'total_amount': 0,
        'total_paid': 0,
        'total_outstanding': 0
    }

    for inv in invoices:
        status = inv.get('status', 'UNKNOWN')
        summary['by_status'][status] = summary['by_status'].get(status, 0) + 1
        summary['total_amount'] += float(inv.get('total_amount', 0))
        summary['total_paid'] += float(inv.get('amount_paid', 0))
        summary['total_outstanding'] += float(inv.get('balance_due', 0))

    return {
        'success': True,
        'summary': summary
    }


@app.get('/api/invoices/{invoice_number}')
def get_invoice(invoice_number: str):
    """Get a single invoice by number."""
    invoice = get_invoice_by_number(invoice_number)

    if not invoice:
        raise HTTPException(status_code=404, detail=f'Invoice {invoice_number} not found')

    return {
        'success': True,
        'invoice': invoice
    }


@app.put('/api/invoices/{invoice_number}/status')
def update_invoice_status(invoice_number: str, data: StatusUpdate):
    """
    Update invoice status (simulate ERP status change).
    """
    new_status = data.status.upper()

    valid_statuses = ['OPEN', 'PARTIAL', 'CLOSED']
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f'Invalid status. Must be one of: {valid_statuses}'
        )

    # Load and update
    invoices = load_invoices()
    updated = False

    for inv in invoices:
        if inv.get('invoice_number') == invoice_number:
            inv['status'] = new_status
            if new_status == 'CLOSED':
                inv['balance_due'] = 0.0
                inv['amount_paid'] = inv.get('total_amount', 0)
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail=f'Invoice {invoice_number} not found')

    # Save back
    save_invoices(invoices)

    return {
        'success': True,
        'message': f'Invoice {invoice_number} status updated to {new_status}'
    }


# ============================================================================
# HTML & PDF VIEWS
# ============================================================================

@app.get('/invoices/{invoice_number}/html', response_class=HTMLResponse)
def view_invoice_html(invoice_number: str):
    """View invoice as HTML."""
    invoice = get_invoice_by_number(invoice_number)

    if not invoice:
        raise HTTPException(status_code=404, detail=f'Invoice {invoice_number} not found')

    html = generate_invoice_html(invoice)
    return HTMLResponse(content=html)


@app.get('/invoices/{invoice_number}/pdf')
def download_invoice_pdf(invoice_number: str):
    """Download invoice as PDF."""
    invoice = get_invoice_by_number(invoice_number)

    if not invoice:
        raise HTTPException(status_code=404, detail=f'Invoice {invoice_number} not found')

    # Generate HTML first
    html = generate_invoice_html(invoice)

    # Convert to PDF
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html).write_pdf()

        # Save to output directory
        pdf_path = OUTPUT_DIR / f'invoice_{invoice_number}.pdf'
        with open(pdf_path, 'wb') as f:
            f.write(pdf_bytes)

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type='application/pdf',
            headers={'Content-Disposition': f'attachment; filename=invoice_{invoice_number}.pdf'}
        )
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail='PDF generation requires weasyprint. Install with: pip install weasyprint'
        )


@app.get('/invoices/{invoice_number}/pdf/view')
def view_invoice_pdf(invoice_number: str):
    """View invoice PDF in browser (inline)."""
    invoice = get_invoice_by_number(invoice_number)

    if not invoice:
        raise HTTPException(status_code=404, detail=f'Invoice {invoice_number} not found')

    html = generate_invoice_html(invoice)

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html).write_pdf()

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type='application/pdf',
            headers={'Content-Disposition': f'inline; filename=invoice_{invoice_number}.pdf'}
        )
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail='PDF generation requires weasyprint. Install with: pip install weasyprint'
        )


# ============================================================================
# DASHBOARD ROUTES
# ============================================================================

@app.get('/', response_class=HTMLResponse)
def dashboard(request: Request):
    """Main ERP dashboard."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get('/invoices', response_class=HTMLResponse)
def invoices_list(request: Request):
    """Invoice listing page."""
    return templates.TemplateResponse("invoices.html", {"request": request})


@app.get('/invoices/{invoice_number}', response_class=HTMLResponse)
def invoice_detail(request: Request, invoice_number: str):
    """Invoice detail page."""
    invoice = get_invoice_by_number(invoice_number)
    if not invoice:
        return templates.TemplateResponse(
            "404.html",
            {"request": request, "message": f'Invoice {invoice_number} not found'},
            status_code=404
        )
    return templates.TemplateResponse("invoice_detail.html", {"request": request, "invoice": invoice})


# ============================================================================
# HTML GENERATOR
# ============================================================================

def generate_invoice_html(invoice: dict, company_info: dict = None) -> str:
    """
    Generate HTML representation of an invoice.
    Similar styling to remittance documents for consistency.
    """
    if company_info is None:
        company_info = {
            'name': 'TechCorp Solutions Inc.',
            'address': '123 Business Park Drive, Suite 400',
            'city': 'San Francisco, CA 94105',
            'phone': '+1 (555) 123-4567',
            'email': 'billing@techcorp.com',
            'website': 'www.techcorp.com'
        }

    # Determine status color
    status = invoice.get('status', 'UNKNOWN').upper()
    status_colors = {
        'OPEN': ('#2563eb', '#dbeafe', 'OPEN'),        # Blue
        'PARTIAL': ('#d97706', '#fef3c7', 'PARTIAL'),  # Amber
        'CLOSED': ('#059669', '#d1fae5', 'CLOSED'),    # Green
    }
    status_color, status_bg, status_label = status_colors.get(status, ('#6b7280', '#f3f4f6', status))

    # Format currency
    currency = invoice.get('currency', 'USD')
    currency_symbols = {'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥'}
    symbol = currency_symbols.get(currency, currency + ' ')

    # Build line items HTML
    line_items_html = ""
    for item in invoice.get('line_items', []):
        line_items_html += f"""
        <tr>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e5e7eb; text-align: left;">{item.get('description', 'N/A')}</td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e5e7eb; text-align: center;">{item.get('quantity', 1)}</td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e5e7eb; text-align: right; font-family: 'Courier New', monospace;">{symbol}{item.get('unit_price', 0):,.2f}</td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e5e7eb; text-align: right; font-family: 'Courier New', monospace;">{symbol}{item.get('line_total', 0):,.2f}</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Invoice {invoice.get('invoice_number', 'N/A')}</title>
    <style>
        @page {{
            size: A4;
            margin: 1cm;
        }}
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            font-size: 14px;
            line-height: 1.5;
            color: #1f2937;
            background-color: #f9fafb;
            padding: 20px;
        }}
        .invoice-container {{
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
            color: white;
            padding: 30px;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }}
        .company-info h1 {{
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 8px;
        }}
        .company-info p {{
            font-size: 12px;
            opacity: 0.9;
        }}
        .invoice-title {{
            text-align: right;
        }}
        .invoice-title h2 {{
            font-size: 32px;
            font-weight: 300;
            letter-spacing: 2px;
        }}
        .invoice-title .invoice-number {{
            font-size: 14px;
            font-family: 'Courier New', monospace;
            margin-top: 8px;
            opacity: 0.9;
        }}
        .status-badge {{
            display: inline-block;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            background-color: {status_bg};
            color: {status_color};
            margin-top: 10px;
        }}
        .meta-section {{
            display: flex;
            justify-content: space-between;
            padding: 24px 30px;
            background-color: #f8fafc;
            border-bottom: 1px solid #e5e7eb;
        }}
        .meta-block h3 {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #6b7280;
            margin-bottom: 8px;
        }}
        .meta-block p {{
            font-size: 14px;
            color: #1f2937;
        }}
        .meta-block .highlight {{
            font-weight: 600;
            color: #1e40af;
        }}
        .bill-to {{
            padding: 24px 30px;
            border-bottom: 1px solid #e5e7eb;
        }}
        .bill-to h3 {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #6b7280;
            margin-bottom: 8px;
        }}
        .bill-to .customer-name {{
            font-size: 18px;
            font-weight: 600;
            color: #1f2937;
        }}
        .bill-to .customer-id {{
            font-size: 12px;
            color: #6b7280;
            font-family: 'Courier New', monospace;
        }}
        .line-items {{
            padding: 0 30px;
        }}
        .line-items table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .line-items th {{
            background-color: #f1f5f9;
            padding: 12px 16px;
            text-align: left;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #475569;
            font-weight: 600;
        }}
        .line-items th:nth-child(2),
        .line-items th:nth-child(3),
        .line-items th:nth-child(4) {{
            text-align: right;
        }}
        .totals {{
            padding: 20px 30px;
            background-color: #f8fafc;
        }}
        .totals table {{
            width: 300px;
            margin-left: auto;
        }}
        .totals td {{
            padding: 8px 0;
        }}
        .totals td:first-child {{
            color: #6b7280;
        }}
        .totals td:last-child {{
            text-align: right;
            font-family: 'Courier New', monospace;
        }}
        .totals .total-row {{
            font-size: 18px;
            font-weight: 700;
            border-top: 2px solid #e5e7eb;
            padding-top: 12px;
        }}
        .totals .total-row td:last-child {{
            color: #1e40af;
        }}
        .payment-info {{
            padding: 24px 30px;
            border-top: 1px solid #e5e7eb;
            display: flex;
            justify-content: space-between;
        }}
        .payment-block h3 {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #6b7280;
            margin-bottom: 8px;
        }}
        .payment-block p {{
            font-size: 14px;
        }}
        .amount-paid {{
            color: #059669;
            font-weight: 600;
        }}
        .balance-due {{
            color: #dc2626;
            font-weight: 600;
        }}
        .footer {{
            padding: 20px 30px;
            background-color: #1e293b;
            color: #94a3b8;
            font-size: 12px;
            text-align: center;
        }}
        .footer a {{
            color: #60a5fa;
            text-decoration: none;
        }}
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .invoice-container {{
                box-shadow: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="invoice-container">
        <!-- Header -->
        <div class="header">
            <div class="company-info">
                <h1>{company_info['name']}</h1>
                <p>{company_info['address']}</p>
                <p>{company_info['city']}</p>
                <p>{company_info['phone']} | {company_info['email']}</p>
            </div>
            <div class="invoice-title">
                <h2>INVOICE</h2>
                <div class="invoice-number">{invoice.get('invoice_number', 'N/A')}</div>
                <div class="status-badge">{status_label}</div>
            </div>
        </div>

        <!-- Meta Section -->
        <div class="meta-section">
            <div class="meta-block">
                <h3>Invoice Date</h3>
                <p>{invoice.get('invoice_date', 'N/A')}</p>
            </div>
            <div class="meta-block">
                <h3>Due Date</h3>
                <p class="highlight">{invoice.get('due_date', 'N/A')}</p>
            </div>
            <div class="meta-block">
                <h3>Payment Terms</h3>
                <p>{invoice.get('payment_terms', 'N/A')}</p>
            </div>
            <div class="meta-block">
                <h3>Currency</h3>
                <p>{currency}</p>
            </div>
        </div>

        <!-- Bill To -->
        <div class="bill-to">
            <h3>Bill To</h3>
            <p class="customer-name">{invoice.get('customer_name', 'N/A')}</p>
            <p class="customer-id">Customer ID: {invoice.get('customer_id', 'N/A')}</p>
        </div>

        <!-- Line Items -->
        <div class="line-items">
            <table>
                <thead>
                    <tr>
                        <th style="text-align: left;">Description</th>
                        <th style="text-align: center;">Qty</th>
                        <th style="text-align: right;">Unit Price</th>
                        <th style="text-align: right;">Amount</th>
                    </tr>
                </thead>
                <tbody>
                    {line_items_html}
                </tbody>
            </table>
        </div>

        <!-- Totals -->
        <div class="totals">
            <table>
                <tr>
                    <td>Subtotal</td>
                    <td>{symbol}{invoice.get('subtotal', 0):,.2f}</td>
                </tr>
                <tr>
                    <td>Tax ({invoice.get('tax_rate', 0) * 100:.1f}%)</td>
                    <td>{symbol}{invoice.get('tax_amount', 0):,.2f}</td>
                </tr>
                <tr class="total-row">
                    <td>Total</td>
                    <td>{symbol}{invoice.get('total_amount', 0):,.2f}</td>
                </tr>
            </table>
        </div>

        <!-- Payment Info -->
        <div class="payment-info">
            <div class="payment-block">
                <h3>Amount Paid</h3>
                <p class="amount-paid">{symbol}{invoice.get('amount_paid', 0):,.2f}</p>
            </div>
            <div class="payment-block">
                <h3>Balance Due</h3>
                <p class="balance-due">{symbol}{invoice.get('balance_due', 0):,.2f}</p>
            </div>
            <div class="payment-block">
                <h3>Payment Date</h3>
                <p>{invoice.get('payment_date', 'Pending')}</p>
            </div>
            <div class="payment-block">
                <h3>Remittance ID</h3>
                <p style="font-family: 'Courier New', monospace;">{invoice.get('remittance_id', 'N/A')}</p>
            </div>
        </div>

        <!-- Footer -->
        <div class="footer">
            <p>Thank you for your business!</p>
            <p style="margin-top: 8px;">
                Questions? Contact us at <a href="mailto:{company_info['email']}">{company_info['email']}</a>
                or visit <a href="https://{company_info['website']}">{company_info['website']}</a>
            </p>
        </div>
    </div>
</body>
</html>"""

    return html


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    import uvicorn
    print("=" * 60)
    print("  Dummy ERP System - Invoice Management (FastAPI)")
    print("=" * 60)
    print("\nEndpoints:")
    print("  Dashboard:     http://localhost:5001/")
    print("  API Invoices:  http://localhost:5001/api/invoices")
    print("  Invoice HTML:  http://localhost:5001/invoices/<number>/html")
    print("  Invoice PDF:   http://localhost:5001/invoices/<number>/pdf")
    print("\n")

    uvicorn.run(app, host='0.0.0.0', port=5001)
