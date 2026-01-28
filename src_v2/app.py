"""
Cash Reconciliation UI - FastAPI Application
Shows results of the 3-phase matching algorithm.
"""

import sys
import os
from pathlib import Path
from decimal import Decimal
from typing import Optional

import json
import httpx
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src_v2.data_loader import load_all_data
from src_v2.engine import ReconciliationEngine
from src_v2.config import ReconciliationConfig

app = FastAPI(title="Cash Reconciliation", description="3-Phase Matching Results")

# Mount static files from main project
STATIC_DIR = Path(__file__).parent.parent / 'static'
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_DIR.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Global state for reconciliation results
_reconciliation_cache = {
    'result': None,
    'banks': None,
    'invoices': None,
    'remittances': None,
    'bank_index': {},
    'invoice_index': {},
    'remittance_index': {}
}


def decimal_to_float(obj):
    """Convert Decimal to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    return obj


def run_reconciliation():
    """Run the reconciliation engine and cache results."""
    if _reconciliation_cache['result'] is not None:
        return _reconciliation_cache['result']

    # Load data
    data_dir = Path(__file__).parent.parent / 'data'
    banks, invoices, remittances = load_all_data(str(data_dir))

    # Build indexes
    _reconciliation_cache['banks'] = banks
    _reconciliation_cache['invoices'] = invoices
    _reconciliation_cache['remittances'] = remittances
    _reconciliation_cache['bank_index'] = {b.id: b for b in banks}
    _reconciliation_cache['invoice_index'] = {i.invoice_number: i for i in invoices}
    _reconciliation_cache['remittance_index'] = {r.id: r for r in remittances}

    # Run reconciliation
    config = ReconciliationConfig()
    engine = ReconciliationEngine(config)
    result = engine.reconcile(banks, invoices, remittances)

    _reconciliation_cache['result'] = result
    return result


def get_bank(bank_id: str):
    """Get bank transaction by ID."""
    return _reconciliation_cache['bank_index'].get(bank_id)


def get_invoice(invoice_number: str):
    """Get invoice by number."""
    return _reconciliation_cache['invoice_index'].get(invoice_number)


def get_remittance(remittance_id: str):
    """Get remittance by ID."""
    return _reconciliation_cache['remittance_index'].get(remittance_id)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get('/api/summary')
def get_summary():
    """Get reconciliation summary statistics."""
    result = run_reconciliation()

    # Calculate totals
    auto_total = sum(
        float(alloc.amount)
        for match in result.auto_approved
        for alloc in match.allocations
    )

    exception_total = sum(
        float(alloc.amount)
        for match in result.exceptions
        for alloc in match.allocations
    )

    suggestion_total = sum(
        float(alloc.amount)
        for sugg in result.suggestions
        for alloc in sugg.allocations
    )

    manual_total = sum(
        float(get_bank(m.bank_id).amount) if get_bank(m.bank_id) else 0
        for m in result.manual
    )

    return {
        'success': True,
        'summary': {
            'total_banks': len(_reconciliation_cache['banks']),
            'total_invoices': len(_reconciliation_cache['invoices']),
            'total_remittances': len(_reconciliation_cache['remittances']),
            'auto_approved': {
                'count': len(result.auto_approved),
                'amount': auto_total
            },
            'exceptions': {
                'count': len(result.exceptions),
                'amount': exception_total
            },
            'suggestions': {
                'count': len(result.suggestions),
                'amount': suggestion_total
            },
            'manual': {
                'count': len(result.manual),
                'amount': manual_total
            },
            'orphan_remittances': len(result.orphan_remittances)
        }
    }


@app.get('/api/auto-approved')
def get_auto_approved():
    """Get all auto-approved matches."""
    result = run_reconciliation()

    matches = []
    for match in result.auto_approved:
        bank = get_bank(match.bank_id)
        matches.append({
            'bank_id': match.bank_id,
            'bank_amount': float(bank.amount) if bank else 0,
            'bank_date': str(bank.date) if bank else None,
            'bank_description': bank.description[:50] if bank else None,
            'customer_id': bank.customer_id if bank else None,
            'match_type': match.match_type.value if hasattr(match.match_type, 'value') else str(match.match_type),
            'remittance_id': match.remittance_id,
            'allocations': [
                {
                    'invoice_number': a.invoice_number,
                    'amount': float(a.amount),
                    'is_partial': a.is_partial
                }
                for a in match.allocations
            ]
        })

    return {'success': True, 'matches': matches}


@app.get('/api/exceptions')
def get_exceptions():
    """Get all exception matches."""
    result = run_reconciliation()

    matches = []
    for match in result.exceptions:
        bank = get_bank(match.bank_id)
        matches.append({
            'bank_id': match.bank_id,
            'bank_amount': float(bank.amount) if bank else 0,
            'bank_date': str(bank.date) if bank else None,
            'bank_description': bank.description[:50] if bank else None,
            'customer_id': bank.customer_id if bank else None,
            'match_type': match.match_type.value if hasattr(match.match_type, 'value') else str(match.match_type),
            'remittance_id': match.remittance_id,
            'exceptions': [
                {
                    'type': e.type.value if hasattr(e.type, 'value') else str(e.type),
                    'severity': e.severity.value if hasattr(e.severity, 'value') else str(e.severity),
                    'details': e.details
                }
                for e in match.exceptions
            ],
            'allocations': [
                {
                    'invoice_number': a.invoice_number,
                    'amount': float(a.amount),
                    'is_partial': a.is_partial
                }
                for a in match.allocations
            ]
        })

    return {'success': True, 'matches': matches}


@app.get('/api/suggestions')
def get_suggestions():
    """Get all suggestions."""
    result = run_reconciliation()

    suggestions = []
    for sugg in result.suggestions:
        bank = get_bank(sugg.bank_id)
        suggestions.append({
            'bank_id': sugg.bank_id,
            'bank_amount': float(bank.amount) if bank else 0,
            'bank_date': str(bank.date) if bank else None,
            'bank_description': bank.description[:50] if bank else None,
            'customer_id': bank.customer_id if bank else None,
            'suggestion_type': sugg.suggestion_type.value if hasattr(sugg.suggestion_type, 'value') else str(sugg.suggestion_type),
            'confidence': float(sugg.confidence),
            'tier': sugg.tier.value if hasattr(sugg.tier, 'value') else str(sugg.tier),
            'explanation': sugg.explanation,
            'allocations': [
                {
                    'invoice_number': a.invoice_number,
                    'amount': float(a.amount),
                    'is_partial': a.is_partial
                }
                for a in sugg.allocations
            ]
        })

    return {'success': True, 'suggestions': suggestions}


@app.get('/api/manual')
def get_manual():
    """Get all manual review items."""
    result = run_reconciliation()

    items = []
    for m in result.manual:
        bank = get_bank(m.bank_id)
        items.append({
            'bank_id': m.bank_id,
            'bank_amount': float(bank.amount) if bank else 0,
            'bank_date': str(bank.date) if bank else None,
            'bank_description': bank.description if bank else None,
            'customer_id': bank.customer_id if bank else None,
            'reason': m.reason,
            'candidate_invoices': [
                {
                    'invoice_number': c.invoice_number,
                    'amount': float(c.amount),
                    'pending_amount': float(c.pending_amount),
                    'customer_id': c.customer_id
                }
                for c in (m.candidate_invoices or [])
            ]
        })

    return {'success': True, 'items': items}


@app.get('/api/match/{bank_id}')
def get_match_detail(bank_id: str):
    """Get full match detail - bank, remittance, and invoices."""
    result = run_reconciliation()

    # Find the match for this bank
    match = None
    for m in result.auto_approved:
        if m.bank_id == bank_id:
            match = m
            break
    if not match:
        for m in result.exceptions:
            if m.bank_id == bank_id:
                match = m
                break

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    bank = get_bank(bank_id)
    remittance = get_remittance(match.remittance_id) if match.remittance_id else None

    # Get invoice details for each allocation
    invoices_detail = []
    for alloc in match.allocations:
        inv = get_invoice(alloc.invoice_number)
        if inv:
            invoices_detail.append({
                'invoice_number': inv.invoice_number,
                'customer_id': inv.customer_id,
                'total_amount': float(inv.amount),
                'pending_amount': float(inv.pending_amount),
                'due_date': str(inv.due_date),
                'allocated_amount': float(alloc.amount),
                'is_partial': alloc.is_partial
            })

    return {
        'success': True,
        'match': {
            'bank_id': match.bank_id,
            'match_type': match.match_type.value if hasattr(match.match_type, 'value') else str(match.match_type),
            'status': match.status.value if hasattr(match.status, 'value') else str(match.status),
            'remittance_id': match.remittance_id,
            'bank': {
                'id': bank.id,
                'date': str(bank.date),
                'amount': float(bank.amount),
                'description': bank.description,
                'customer_id': bank.customer_id,
                'reference': bank.reference,
                'payment_method': bank.payment_method
            } if bank else None,
            'remittance': {
                'id': remittance.id,
                'payer_name': remittance.payer_name,
                'payer_id': remittance.payer_id,
                'payment_date': str(remittance.payment_date),
                'payment_amount_total': float(remittance.payment_amount_total),
                'payment_reference': remittance.payment_reference,
                'currency': remittance.currency,
                'payment_method': remittance.payment_method,
                'source': remittance.source,
                'line_items': [
                    {
                        'invoice_number': li.invoice_number,
                        'amount_paid': float(li.amount_paid),
                        'deduction_amount': float(li.deduction_amount) if li.deduction_amount else None,
                        'deduction_reason': li.deduction_reason
                    }
                    for li in remittance.line_items
                ]
            } if remittance else None,
            'invoices': invoices_detail,
            'exceptions': [
                {
                    'type': e.type.value if hasattr(e.type, 'value') else str(e.type),
                    'severity': e.severity.value if hasattr(e.severity, 'value') else str(e.severity),
                    'details': e.details
                }
                for e in (match.exceptions or [])
            ]
        }
    }


@app.get('/api/remittances/{remittance_id}')
def get_remittance_detail(remittance_id: str):
    """Get remittance detail by ID."""
    run_reconciliation()  # Ensure data is loaded

    remittance = get_remittance(remittance_id)
    if not remittance:
        raise HTTPException(status_code=404, detail="Remittance not found")

    return {
        'success': True,
        'remittance': {
            'id': remittance.id,
            'payer_name': remittance.payer_name,
            'payer_id': remittance.payer_id,
            'payment_date': str(remittance.payment_date),
            'payment_amount_total': float(remittance.payment_amount_total),
            'payment_reference': remittance.payment_reference,
            'currency': remittance.currency,
            'payment_method': remittance.payment_method,
            'source': remittance.source,
            'line_items': [
                {
                    'invoice_number': li.invoice_number,
                    'amount_paid': float(li.amount_paid),
                    'invoice_date': str(li.invoice_date) if li.invoice_date else None,
                    'invoice_amount_original': float(li.invoice_amount_original) if li.invoice_amount_original else None,
                    'remaining_balance': float(li.remaining_balance) if li.remaining_balance else None,
                    'deduction_amount': float(li.deduction_amount) if li.deduction_amount else None,
                    'deduction_reason': li.deduction_reason,
                    'credit_note_reference': li.credit_note_reference
                }
                for li in remittance.line_items
            ]
        }
    }


ERP_BASE_URL = "http://localhost:5001"


@app.post('/api/parse-bank-statement')
async def parse_bank_statement(file: UploadFile = File(...)):
    """Mock bank statement PDF parsing - returns sample bank transactions JSON."""
    import asyncio

    # Simulate processing delay (10 seconds)
    await asyncio.sleep(10)

    # In production, this would use OCR/AI to parse the PDF
    # For now, return the existing bank transactions as mock parsed data

    data_path = Path(__file__).parent.parent / 'data' / 'bank_transactions.json'
    with open(data_path, 'r') as f:
        bank_transactions = json.load(f)

    return {
        'success': True,
        'filename': file.filename,
        'message': 'Bank statement parsed successfully',
        'transactions_count': len(bank_transactions),
        'transactions': bank_transactions
    }


@app.post('/api/approve/{bank_id}')
async def approve_match(bank_id: str):
    """Approve a match - updates all linked invoices to CLOSED in ERP."""
    result = run_reconciliation()

    # Find the match
    match = None
    for m in result.auto_approved:
        if m.bank_id == bank_id:
            match = m
            break
    if not match:
        for m in result.exceptions:
            if m.bank_id == bank_id:
                match = m
                break

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # Update each invoice status to CLOSED in ERP
    results = []
    async with httpx.AsyncClient() as client:
        for alloc in match.allocations:
            try:
                response = await client.put(
                    f"{ERP_BASE_URL}/api/invoices/{alloc.invoice_number}/status",
                    json={"status": "CLOSED"},
                    timeout=10.0
                )
                if response.status_code == 200:
                    results.append({
                        "invoice_number": alloc.invoice_number,
                        "status": "success",
                        "message": "Updated to CLOSED"
                    })
                else:
                    results.append({
                        "invoice_number": alloc.invoice_number,
                        "status": "error",
                        "message": response.text
                    })
            except Exception as e:
                results.append({
                    "invoice_number": alloc.invoice_number,
                    "status": "error",
                    "message": str(e)
                })

    success_count = sum(1 for r in results if r["status"] == "success")

    return {
        "success": success_count == len(results),
        "bank_id": bank_id,
        "total_invoices": len(results),
        "updated_count": success_count,
        "results": results
    }


@app.get('/remittances/{remittance_id}/pdf')
def get_remittance_pdf(remittance_id: str):
    """Get remittance PDF file."""
    pdf_path = Path(__file__).parent.parent / 'output' / 'remittances' / 'pdf' / f'remittance_{remittance_id}.pdf'

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")

    return FileResponse(
        path=str(pdf_path),
        media_type='application/pdf',
        headers={"Content-Disposition": f"inline; filename={remittance_id}.pdf"}
    )


# ============================================================================
# HTML PAGES
# ============================================================================

@app.get('/', response_class=HTMLResponse)
def landing_page(request: Request):
    """Landing page with upload options."""
    return templates.TemplateResponse("landing.html", {"request": request})


@app.get('/dashboard', response_class=HTMLResponse)
def dashboard(request: Request):
    """Main dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get('/auto-approved', response_class=HTMLResponse)
def auto_approved_page(request: Request):
    """Auto-approved matches page."""
    return templates.TemplateResponse("auto_approved.html", {"request": request})


@app.get('/exceptions', response_class=HTMLResponse)
def exceptions_page(request: Request):
    """Exception queue page."""
    return templates.TemplateResponse("exceptions.html", {"request": request})


@app.get('/suggestions', response_class=HTMLResponse)
def suggestions_page(request: Request):
    """Suggestions page."""
    return templates.TemplateResponse("suggestions.html", {"request": request})


@app.get('/manual', response_class=HTMLResponse)
def manual_page(request: Request):
    """Manual review page."""
    return templates.TemplateResponse("manual.html", {"request": request})


@app.get('/exceptions/{bank_id}', response_class=HTMLResponse)
def exception_detail_page(request: Request, bank_id: str):
    """Exception detail page."""
    result = run_reconciliation()

    # Find the exception
    match = None
    for m in result.exceptions:
        if m.bank_id == bank_id:
            match = m
            break

    if not match:
        raise HTTPException(status_code=404, detail="Exception not found")

    bank = get_bank(bank_id)

    # Get allocations
    allocations = [
        {
            'invoice_number': a.invoice_number,
            'amount': float(a.amount),
            'is_partial': a.is_partial
        }
        for a in match.allocations
    ]

    # Get exceptions
    exceptions = [
        {
            'type': e.type.value if hasattr(e.type, 'value') else str(e.type),
            'severity': e.severity.value if hasattr(e.severity, 'value') else str(e.severity),
            'details': e.details
        }
        for e in match.exceptions
    ]

    return templates.TemplateResponse("exception_detail.html", {
        "request": request,
        "bank": bank,
        "allocations": allocations,
        "exceptions": exceptions
    })


@app.get('/suggestions/{bank_id}', response_class=HTMLResponse)
def suggestion_detail_page(request: Request, bank_id: str):
    """Suggestion detail page."""
    result = run_reconciliation()

    # Find the suggestion
    suggestion = None
    for s in result.suggestions:
        if s.bank_id == bank_id:
            suggestion = s
            break

    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    bank = get_bank(bank_id)

    # Get allocations
    allocations = [
        {
            'invoice_number': a.invoice_number,
            'amount': float(a.amount),
            'is_partial': a.is_partial
        }
        for a in suggestion.allocations
    ]

    return templates.TemplateResponse("suggestion_detail.html", {
        "request": request,
        "bank": bank,
        "allocations": allocations,
        "confidence": suggestion.confidence,
        "tier": suggestion.tier.value if hasattr(suggestion.tier, 'value') else str(suggestion.tier),
        "explanation": suggestion.explanation
    })


@app.get('/manual/{bank_id}', response_class=HTMLResponse)
def manual_detail_page(request: Request, bank_id: str):
    """Manual matching detail page."""
    result = run_reconciliation()

    # Find the manual item
    manual_item = None
    for m in result.manual:
        if m.bank_id == bank_id:
            manual_item = m
            break

    if not manual_item:
        raise HTTPException(status_code=404, detail="Manual item not found")

    bank = get_bank(bank_id)

    # Get candidate invoices
    candidates = [
        {
            'invoice_number': c.invoice_number,
            'amount': float(c.amount),
            'pending_amount': float(c.pending_amount),
            'customer_id': c.customer_id,
            'due_date': str(c.due_date),
            'status': 'OPEN' if c.pending_amount > 0 else 'PAID'
        }
        for c in (manual_item.candidate_invoices or [])
    ]

    return templates.TemplateResponse("manual_detail.html", {
        "request": request,
        "bank": bank,
        "reason": manual_item.reason,
        "candidates": candidates
    })


@app.get('/match/{bank_id}', response_class=HTMLResponse)
def match_detail_page(request: Request, bank_id: str):
    """Match detail page showing bank, remittance, and invoices."""
    result = run_reconciliation()

    # Find the match
    match = None
    for m in result.auto_approved:
        if m.bank_id == bank_id:
            match = m
            break
    if not match:
        for m in result.exceptions:
            if m.bank_id == bank_id:
                match = m
                break

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    bank = get_bank(bank_id)
    remittance = get_remittance(match.remittance_id) if match.remittance_id else None

    # Get invoice details
    invoices_detail = []
    for alloc in match.allocations:
        inv = get_invoice(alloc.invoice_number)
        if inv:
            invoices_detail.append({
                'invoice': inv,
                'allocation': alloc
            })

    # Check if PDF exists
    has_pdf = False
    if remittance:
        pdf_path = Path(__file__).parent.parent / 'output' / 'remittances' / 'pdf' / f'remittance_{remittance.id}.pdf'
        has_pdf = pdf_path.exists()

    return templates.TemplateResponse("match_detail.html", {
        "request": request,
        "match": match,
        "bank": bank,
        "remittance": remittance,
        "invoices_detail": invoices_detail,
        "has_pdf": has_pdf
    })


@app.get('/remittances/{remittance_id}', response_class=HTMLResponse)
def remittance_detail_page(request: Request, remittance_id: str):
    """Remittance detail page with parsed data and PDF view."""
    run_reconciliation()  # Ensure data is loaded

    remittance = get_remittance(remittance_id)
    if not remittance:
        raise HTTPException(status_code=404, detail="Remittance not found")

    # Check if PDF exists
    pdf_path = Path(__file__).parent.parent / 'output' / 'remittances' / 'pdf' / f'remittance_{remittance_id}.pdf'
    has_pdf = pdf_path.exists()

    return templates.TemplateResponse("remittance_detail.html", {
        "request": request,
        "remittance": remittance,
        "has_pdf": has_pdf
    })


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    import uvicorn
    print("=" * 60)
    print("  Cash Reconciliation UI")
    print("=" * 60)
    print("\n  Starting server at http://localhost:5002")
    print("\n  Pages:")
    print("    Dashboard:      http://localhost:5002/")
    print("    Auto-Approved:  http://localhost:5002/auto-approved")
    print("    Exceptions:     http://localhost:5002/exceptions")
    print("    Suggestions:    http://localhost:5002/suggestions")
    print("    Manual:         http://localhost:5002/manual")
    print("\n" + "=" * 60)

    uvicorn.run(app, host='0.0.0.0', port=5002)
