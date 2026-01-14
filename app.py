"""
Cash Reconciliation Dashboard - FastAPI Application

A visually striking web dashboard for the cash reconciliation platform.
"""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from models import (
    BankTransaction,
    Remittance,
    RemittanceLineItem,
    Invoice,
    Customer,
    InvoiceStatus,
    MatchOutcome,
    RemittanceSource,
)
from reconciler import Reconciler

app = FastAPI(title="Cash Reconciliation Dashboard")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Store current reconciliation results in memory
current_results = {
    "summary": None,
    "results": [],
    "bank_transactions": [],
    "remittances": [],
    "invoices": [],
    "customers": [],
    "virtual_remittances": [],
    "invoice_statuses": [],
}

# Store reconciler for serializing invoice statuses
_current_reconciler = None


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


def serialize_results(reconciler: Reconciler) -> dict:
    """Serialize reconciliation results to JSON-compatible format."""
    summary = reconciler.summary

    results_data = []
    for result in reconciler.results:
        bank = result.bank_transaction
        l1 = result.level1_match

        result_item = {
            "bank_id": bank.id,
            "bank_amount": float(bank.amount),
            "bank_date": bank.date.isoformat(),
            "bank_reference": bank.reference,
            "bank_description": bank.description,
            "level1_outcome": l1.result.outcome.value if l1 else None,
            "level1_confidence": l1.result.confidence if l1 else 0,
            "level1_rule": l1.result.rule_applied if l1 else None,
            "level1_remittance_id": l1.remittance_id if l1 else None,
            "level1_exception_code": l1.result.exception_code.name if l1 and l1.result.exception_code else None,
            "level1_exception_detail": l1.result.exception_detail if l1 else None,
            "level2_matches": [],
            "fully_reconciled": result.fully_reconciled,
        }

        for l2 in result.level2_matches:
            result_item["level2_matches"].append({
                "remittance_id": l2.remittance_id,
                "line_index": l2.remittance_line_index,
                "invoice_id": l2.invoice_id,
                "outcome": l2.result.outcome.value,
                "confidence": l2.result.confidence,
                "rule": l2.result.rule_applied,
                "exception_code": l2.result.exception_code.name if l2.result.exception_code else None,
                "exception_detail": l2.result.exception_detail,
            })

        results_data.append(result_item)

    # Calculate invoice reconciliation rate
    invoice_statuses = reconciler.get_invoice_reconciliation_statuses()
    total_invoices = len(invoice_statuses)
    reconciled_invoices = sum(1 for s in invoice_statuses if s.is_reconciled)
    invoice_reconciliation_rate = (reconciled_invoices / total_invoices * 100) if total_invoices > 0 else 0

    return {
        "summary": {
            "total_bank_transactions": summary.total_bank_transactions,
            "total_remittances": summary.total_remittances,
            "total_invoices": summary.total_invoices,
            "level1_auto_matched": summary.level1_auto_matched,
            "level1_auto_matched_virtual": summary.level1_auto_matched_virtual,
            "level1_exceptions": summary.level1_exceptions,
            "level1_unmatched": summary.level1_unmatched,
            "level2_auto_matched": summary.level2_auto_matched,
            "level2_exceptions": summary.level2_exceptions,
            "level2_unmatched": summary.level2_unmatched,
            "fully_reconciled": summary.fully_reconciled,
            "exceptions_by_code": summary.exceptions_by_code,
            "level1_match_rate": summary.level1_match_rate,
            "full_reconciliation_rate": summary.full_reconciliation_rate,
            "invoice_reconciliation_rate": invoice_reconciliation_rate,
            "reconciled_invoices": reconciled_invoices,
        },
        "results": results_data,
    }


def serialize_invoice_statuses(reconciler: Reconciler) -> list:
    """Serialize invoice reconciliation statuses to JSON-compatible format."""
    statuses = reconciler.get_invoice_reconciliation_statuses()
    result = []

    # Build remittance lookup for references
    remittance_map = {r.id: r for r in reconciler.remittances}
    for vr in reconciler.virtual_remittances:
        remittance_map[vr.id] = vr

    # Build bank transaction lookup
    bank_map = {b.id: b for b in reconciler.bank_transactions}

    # Build lookup for ALL payments per invoice (not just first)
    invoice_payments = {}  # invoice_id -> list of payments
    for rec_result in reconciler.results:
        for l2 in rec_result.level2_matches:
            if l2.invoice_id:
                if l2.invoice_id not in invoice_payments:
                    invoice_payments[l2.invoice_id] = []

                # Get remittance details
                rem = remittance_map.get(l2.remittance_id)
                rem_ref = rem.payment_reference if rem else None
                line_ref = None
                line_amount = None
                if rem and 0 <= l2.remittance_line_index < len(rem.line_items):
                    line_item = rem.line_items[l2.remittance_line_index]
                    line_ref = line_item.invoice_number
                    line_amount = float(line_item.amount)

                # Get bank transaction details
                bank_id = rem.matched_bank_transaction_id if rem else None
                bank_ref = None
                if bank_id and bank_id in bank_map:
                    bank_ref = bank_map[bank_id].reference

                invoice_payments[l2.invoice_id].append({
                    "remittance_id": l2.remittance_id,
                    "remittance_reference": rem_ref,
                    "line_index": l2.remittance_line_index,
                    "line_ref": line_ref,
                    "amount": line_amount,
                    "bank_transaction_id": bank_id,
                    "bank_reference": bank_ref,
                    "outcome": l2.result.outcome.value,
                    "confidence": l2.result.confidence,
                    "exception_code": l2.result.exception_code.name if l2.result.exception_code else None,
                    "exception_detail": l2.result.exception_detail,
                })

    for status in statuses:
        inv = status.invoice
        payments = invoice_payments.get(inv.invoice_id, [])
        # Get first payment for backward compatibility
        first_payment = payments[0] if payments else {}
        # Find payment with exception (if any) - for correct exception detail
        exception_payment = next(
            (p for p in payments if p.get("exception_code")),
            first_payment
        )

        result.append({
            "invoice": {
                "invoice_id": inv.invoice_id,
                "customer_id": inv.customer_id,
                "due_date": inv.due_date.isoformat(),
                "amount": float(inv.amount),
                "pending_amount": float(inv.pending_amount),
                "status": inv.status.value,
            },
            "remittance_id": status.remittance_id,
            "remittance_reference": status.remittance_reference,
            "remittance_match_confidence": status.remittance_match_confidence,
            "remittance_exception": status.remittance_exception.name if status.remittance_exception else None,
            "bank_transaction_id": status.bank_transaction_id,
            "bank_reference": status.bank_reference,
            "bank_match_confidence": status.bank_match_confidence,
            "bank_exception": status.bank_exception.name if status.bank_exception else None,
            "matched_line_ref": status.matched_line_ref,
            "line_match_outcome": exception_payment.get("outcome") or first_payment.get("outcome"),
            "line_match_exception": exception_payment.get("exception_code"),
            "line_match_exception_detail": exception_payment.get("exception_detail"),
            "invoice_exception": status.invoice_exception.name if status.invoice_exception else None,
            "is_reconciled": status.is_reconciled,
            "reconciliation_status": status.reconciliation_status,
            "all_payments": payments,  # All payments for this invoice
        })

    return result


def parse_json_input(data: dict) -> tuple:
    """Parse JSON input into model objects."""

    # Parse customers
    customers = []
    for c in data.get("customers", []):
        customers.append(Customer(
            customer_id=c["customer_id"],
            name=c["name"],
            aliases=c.get("aliases", []),
            address=c.get("address"),
            payment_ref_patterns=c.get("payment_ref_patterns", []),
            account_numbers=c.get("account_numbers", []),
        ))

    # Parse invoices
    invoices = []
    for inv in data.get("invoices", []):
        status = InvoiceStatus(inv.get("status", "Open"))
        invoices.append(Invoice(
            invoice_id=inv["invoice_id"],
            customer_id=inv["customer_id"],
            due_date=date.fromisoformat(inv["due_date"]) if isinstance(inv["due_date"], str) else inv["due_date"],
            amount=Decimal(str(inv["amount"])),
            pending_amount=Decimal(str(inv["pending_amount"])),
            status=status,
        ))

    # Parse remittances
    remittances = []
    for rem in data.get("remittances", []):
        line_items = []
        for li in rem.get("line_items", []):
            line_items.append(RemittanceLineItem(
                invoice_number=li["invoice_number"],
                description=li.get("description", ""),
                payment_method=li.get("payment_method", ""),
                amount=Decimal(str(li["amount"])),
            ))

        remittances.append(Remittance(
            id=rem["id"],
            customer_id=rem.get("customer_id"),
            customer_name=rem["customer_name"],
            customer_address=rem.get("customer_address"),
            payment_reference=rem["payment_reference"],
            payment_date=date.fromisoformat(rem["payment_date"]) if isinstance(rem["payment_date"], str) else rem["payment_date"],
            line_items=line_items,
            source=RemittanceSource.ACTUAL,
        ))

    # Parse bank transactions
    bank_transactions = []
    for bt in data.get("bank_transactions", []):
        bank_transactions.append(BankTransaction(
            id=bt["id"],
            amount=Decimal(str(bt["amount"])),
            date=date.fromisoformat(bt["date"]) if isinstance(bt["date"], str) else bt["date"],
            reference=bt["reference"],
            description=bt["description"],
        ))

    return customers, invoices, remittances, bank_transactions


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the main dashboard HTML."""
    html_path = Path("templates/index.html")
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text())
    return HTMLResponse(content="<h1>Dashboard template not found</h1>", status_code=404)


@app.post("/api/reconcile")
async def reconcile(file: UploadFile = File(...)):
    """Run reconciliation on uploaded JSON data."""
    try:
        content = await file.read()
        data = json.loads(content)

        customers, invoices, remittances, bank_transactions = parse_json_input(data)

        # Run reconciliation
        reconciler = Reconciler(
            bank_transactions=bank_transactions,
            remittances=remittances,
            invoices=invoices,
            customers=customers,
        )
        reconciler.run()

        # Store results
        serialized = serialize_results(reconciler)
        current_results["summary"] = serialized["summary"]
        current_results["results"] = serialized["results"]
        current_results["bank_transactions"] = [
            {
                "id": bt.id,
                "amount": float(bt.amount),
                "date": bt.date.isoformat(),
                "reference": bt.reference,
                "description": bt.description,
            }
            for bt in bank_transactions
        ]
        current_results["remittances"] = [
            {
                "id": rem.id,
                "customer_id": rem.customer_id,
                "customer_name": rem.customer_name,
                "payment_reference": rem.payment_reference,
                "payment_date": rem.payment_date.isoformat(),
                "total_amount": float(rem.total_amount),
                "line_items": [
                    {
                        "invoice_number": li.invoice_number,
                        "amount": float(li.amount),
                        "payment_method": li.payment_method,
                    }
                    for li in rem.line_items
                ],
                "source": rem.source.value,
                "status": rem.status.value,
                "matched_bank_transaction_id": rem.matched_bank_transaction_id,
            }
            for rem in remittances
        ]
        current_results["invoices"] = [
            {
                "invoice_id": inv.invoice_id,
                "customer_id": inv.customer_id,
                "due_date": inv.due_date.isoformat(),
                "amount": float(inv.amount),
                "pending_amount": float(inv.pending_amount),
                "status": inv.status.value,
            }
            for inv in invoices
        ]
        current_results["customers"] = [
            {
                "customer_id": c.customer_id,
                "name": c.name,
                "aliases": c.aliases,
            }
            for c in customers
        ]
        current_results["virtual_remittances"] = [
            {
                "id": vr.id,
                "customer_id": vr.customer_id,
                "customer_name": vr.customer_name,
                "payment_reference": vr.payment_reference,
                "payment_date": vr.payment_date.isoformat(),
                "total_amount": float(vr.total_amount),
                "line_items": [
                    {
                        "invoice_number": li.invoice_number,
                        "amount": float(li.amount),
                    }
                    for li in vr.line_items
                ],
                "source": vr.source.value,
                "status": vr.status.value,
                "matched_bank_transaction_id": vr.matched_bank_transaction_id,
            }
            for vr in reconciler.virtual_remittances
        ]

        # Store invoice reconciliation statuses
        current_results["invoice_statuses"] = serialize_invoice_statuses(reconciler)

        return JSONResponse(content=serialized)

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reconciliation error: {str(e)}")


@app.get("/api/results")
async def get_results():
    """Get current reconciliation results."""
    if current_results["summary"] is None:
        raise HTTPException(status_code=404, detail="No reconciliation results. Upload data first.")

    return JSONResponse(content={
        "summary": current_results["summary"],
        "results": current_results["results"],
    })


@app.get("/api/data")
async def get_all_data():
    """Get all current data including transactions, remittances, invoices."""
    if current_results["summary"] is None:
        raise HTTPException(status_code=404, detail="No data loaded. Upload data first.")

    return JSONResponse(content=current_results)


@app.get("/api/transaction/{bank_id}")
async def get_transaction(bank_id: str):
    """Get detailed transaction information."""
    for result in current_results["results"]:
        if result["bank_id"] == bank_id:
            # Find associated remittance
            remittance = None
            if result["level1_remittance_id"]:
                for rem in current_results["remittances"] + current_results["virtual_remittances"]:
                    if rem["id"] == result["level1_remittance_id"]:
                        remittance = rem
                        break

            # Find associated invoices
            matched_invoices = []
            for l2 in result["level2_matches"]:
                if l2["invoice_id"]:
                    for inv in current_results["invoices"]:
                        if inv["invoice_id"] == l2["invoice_id"]:
                            matched_invoices.append({
                                **inv,
                                "match_outcome": l2["outcome"],
                                "match_rule": l2["rule"],
                                "match_confidence": l2["confidence"],
                                "exception_code": l2["exception_code"],
                                "exception_detail": l2["exception_detail"],
                            })
                            break

            return JSONResponse(content={
                "transaction": result,
                "remittance": remittance,
                "invoices": matched_invoices,
            })

    raise HTTPException(status_code=404, detail=f"Transaction {bank_id} not found")


@app.get("/api/exceptions")
async def get_exceptions(code: Optional[str] = None):
    """Get filtered exceptions."""
    exceptions = []

    for result in current_results["results"]:
        # Level 1 exceptions
        if result["level1_exception_code"]:
            if code is None or result["level1_exception_code"] == code:
                exceptions.append({
                    "type": "level1",
                    "bank_id": result["bank_id"],
                    "code": result["level1_exception_code"],
                    "detail": result["level1_exception_detail"],
                    "amount": result["bank_amount"],
                })

        # Level 2 exceptions
        for l2 in result["level2_matches"]:
            if l2["exception_code"]:
                if code is None or l2["exception_code"] == code:
                    exceptions.append({
                        "type": "level2",
                        "bank_id": result["bank_id"],
                        "remittance_id": l2["remittance_id"],
                        "invoice_id": l2["invoice_id"],
                        "code": l2["exception_code"],
                        "detail": l2["exception_detail"],
                    })

    return JSONResponse(content={"exceptions": exceptions, "count": len(exceptions)})


@app.post("/api/load-sample")
async def load_sample():
    """Load sample data for demo."""
    sample_path = Path("sample_data/example.json")
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="Sample data not found")

    with open(sample_path) as f:
        data = json.load(f)

    customers, invoices, remittances, bank_transactions = parse_json_input(data)

    # Run reconciliation
    reconciler = Reconciler(
        bank_transactions=bank_transactions,
        remittances=remittances,
        invoices=invoices,
        customers=customers,
    )
    reconciler.run()

    # Store results (same as /api/reconcile)
    serialized = serialize_results(reconciler)
    current_results["summary"] = serialized["summary"]
    current_results["results"] = serialized["results"]
    current_results["bank_transactions"] = [
        {
            "id": bt.id,
            "amount": float(bt.amount),
            "date": bt.date.isoformat(),
            "reference": bt.reference,
            "description": bt.description,
        }
        for bt in bank_transactions
    ]
    current_results["remittances"] = [
        {
            "id": rem.id,
            "customer_id": rem.customer_id,
            "customer_name": rem.customer_name,
            "payment_reference": rem.payment_reference,
            "payment_date": rem.payment_date.isoformat(),
            "total_amount": float(rem.total_amount),
            "line_items": [
                {
                    "invoice_number": li.invoice_number,
                    "amount": float(li.amount),
                    "payment_method": li.payment_method,
                }
                for li in rem.line_items
            ],
            "source": rem.source.value,
            "status": rem.status.value,
            "matched_bank_transaction_id": rem.matched_bank_transaction_id,
        }
        for rem in remittances
    ]
    current_results["invoices"] = [
        {
            "invoice_id": inv.invoice_id,
            "customer_id": inv.customer_id,
            "due_date": inv.due_date.isoformat(),
            "amount": float(inv.amount),
            "pending_amount": float(inv.pending_amount),
            "status": inv.status.value,
        }
        for inv in invoices
    ]
    current_results["customers"] = [
        {
            "customer_id": c.customer_id,
            "name": c.name,
            "aliases": c.aliases,
        }
        for c in customers
    ]
    current_results["virtual_remittances"] = [
        {
            "id": vr.id,
            "customer_id": vr.customer_id,
            "customer_name": vr.customer_name,
            "payment_reference": vr.payment_reference,
            "payment_date": vr.payment_date.isoformat(),
            "total_amount": float(vr.total_amount),
            "line_items": [
                {
                    "invoice_number": li.invoice_number,
                    "amount": float(li.amount),
                }
                for li in vr.line_items
            ],
            "source": vr.source.value,
            "status": vr.status.value,
            "matched_bank_transaction_id": vr.matched_bank_transaction_id,
        }
        for vr in reconciler.virtual_remittances
    ]

    # Store invoice reconciliation statuses
    current_results["invoice_statuses"] = serialize_invoice_statuses(reconciler)

    return JSONResponse(content=serialized)


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
