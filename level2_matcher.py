"""
Level 2 Matching: Remittance Line Item ↔ Invoice

Phase 1 Deterministic Rules (Customer-Scoped):
- Rule 2.1: Customer + Exact Invoice Reference (100% confidence)
- Rule 2.2: Customer + Fuzzy Invoice Reference (95% confidence)
- Rule 2.3: Customer + Amount + Due Date Proximity - fallback when no reference (85% confidence)

Matching is REFERENCE-BASED, not amount-based:
- Customer MUST match for all rules
- Multiple remittance line items can pay the same invoice (partial payments)
- Payments are tracked cumulatively per invoice

Invoice Status:
- OPEN: No payment received
- PARTIAL: Underpayment - pending_amount > 0
- CLOSED: Fully paid - pending_amount = 0

Exception Detection:
- E002: Overpayment - cumulative payments exceed invoice amount (Invoice Level)
- E004: Duplicate payment - invoice already closed (Invoice Level)
- E005: Invalid invoice reference - not found in system (Remittance Level)
- E009: Customer not identified (Remittance Level)
"""
from decimal import Decimal
from typing import Optional

from models import (
    Remittance,
    RemittanceLineItem,
    Invoice,
    InvoiceStatus,
    MatchResult,
    MatchOutcome,
    Level2Match,
    ExceptionCode,
)
from normalizers import invoice_ids_match, normalize_invoice_id


def match_remittance_to_invoices(
    remittance: Remittance,
    invoices: list[Invoice],
    customer_id: str,
) -> list[Level2Match]:
    """
    Match each line item in a remittance to invoices.

    Matching is REFERENCE-BASED:
    - First match all line items by invoice reference
    - Track cumulative payments per invoice
    - Detect overpayment when total exceeds invoice amount

    Args:
        remittance: The remittance to match
        invoices: All available invoices
        customer_id: The identified customer ID for this remittance

    Returns:
        List of Level2Match results, one per line item
    """
    results = []

    # Filter invoices for this customer
    customer_invoices = [inv for inv in invoices if inv.customer_id == customer_id]

    # Track cumulative payments per invoice for overpayment detection
    cumulative_payments: dict[str, Decimal] = {}

    for idx, line_item in enumerate(remittance.line_items):
        match = match_line_item_to_invoice(
            remittance_id=remittance.id,
            line_index=idx,
            line_item=line_item,
            customer_invoices=customer_invoices,
            customer_id=customer_id,
        )

        # Track cumulative payment if matched to an invoice
        if match.invoice_id and match.result.outcome == MatchOutcome.AUTO_MATCHED:
            if match.invoice_id not in cumulative_payments:
                cumulative_payments[match.invoice_id] = Decimal("0")
            cumulative_payments[match.invoice_id] += line_item.amount

        results.append(match)

    # Post-match: Check for overpayments (E002 exception)
    results = _check_overpayments(results, remittance, invoices, cumulative_payments)

    return results


def _check_overpayments(
    results: list[Level2Match],
    remittance: Remittance,
    invoices: list[Invoice],
    cumulative_payments: dict[str, Decimal],
) -> list[Level2Match]:
    """
    Check for overpayment after all line items are matched.

    Overpayment IS an exception (E002) - cumulative payments exceed invoice amount.
    Marks the LAST payment to that invoice as the exception.

    Returns:
        Updated results with overpayment exceptions
    """
    # Build invoice lookup
    invoice_map = {inv.invoice_id: inv for inv in invoices}

    # Find invoices with overpayment
    overpaid_invoices = {}
    for inv_id, total_paid in cumulative_payments.items():
        if inv_id in invoice_map:
            invoice = invoice_map[inv_id]
            if total_paid > invoice.pending_amount:
                overpaid_invoices[inv_id] = {
                    'total_paid': total_paid,
                    'pending': invoice.pending_amount,
                    'overpayment': total_paid - invoice.pending_amount,
                }

    if not overpaid_invoices:
        return results

    # Mark the last line item for each overpaid invoice as exception
    updated_results = []
    marked_invoices = set()

    for match in reversed(results):
        if (match.invoice_id in overpaid_invoices
            and match.invoice_id not in marked_invoices
            and match.result.outcome == MatchOutcome.AUTO_MATCHED):

            overpay_info = overpaid_invoices[match.invoice_id]
            marked_invoices.add(match.invoice_id)

            # Convert this match to an overpayment exception
            updated_match = Level2Match(
                remittance_id=match.remittance_id,
                remittance_line_index=match.remittance_line_index,
                invoice_id=match.invoice_id,
                result=MatchResult(
                    outcome=MatchOutcome.EXCEPTION,
                    confidence=0,
                    rule_applied="Overpayment Check",
                    source_id=match.result.source_id,
                    target_id=match.invoice_id,
                    exception_code=ExceptionCode.E002,
                    exception_detail=f"Total ${overpay_info['total_paid']} exceeds pending ${overpay_info['pending']} by ${overpay_info['overpayment']}",
                )
            )
            updated_results.append(updated_match)
        else:
            updated_results.append(match)

    # Reverse back to original order
    return list(reversed(updated_results))


def match_line_item_to_invoice(
    remittance_id: str,
    line_index: int,
    line_item: RemittanceLineItem,
    customer_invoices: list[Invoice],
    customer_id: str,
) -> Level2Match:
    """
    Match a single remittance line item to an invoice.

    Matching is REFERENCE-BASED (not amount-based):
    1. Check for exceptions first (invalid invoice, wrong customer, duplicate)
    2. Rule 2.1: Exact Invoice Reference Match
    3. Rule 2.2: Fuzzy Invoice Reference Match
    4. Rule 2.3: Amount + Customer Match (fallback when no reference)

    Note: Overpayment is checked AFTER all line items are matched,
    since multiple line items can pay the same invoice.

    Returns:
        Level2Match with the result
    """
    # First, try to find the invoice by ID (exact or fuzzy)
    invoice = _find_invoice_by_id(line_item.invoice_number, customer_invoices)

    # Check for E005: Invalid invoice (not found in customer's invoices)
    # Only if a specific invoice reference was provided
    if line_item.invoice_number and not invoice:
        return Level2Match(
            remittance_id=remittance_id,
            remittance_line_index=line_index,
            invoice_id=None,
            result=MatchResult(
                outcome=MatchOutcome.EXCEPTION,
                confidence=0,
                rule_applied="Exception Check",
                source_id=f"{remittance_id}:{line_index}",
                exception_code=ExceptionCode.E005,
                exception_detail=f"Invoice {line_item.invoice_number} not found",
            )
        )

    # If invoice found, check for duplicate payment (already closed)
    if invoice and invoice.status == InvoiceStatus.CLOSED:
        return Level2Match(
            remittance_id=remittance_id,
            remittance_line_index=line_index,
            invoice_id=invoice.invoice_id,
            result=MatchResult(
                outcome=MatchOutcome.EXCEPTION,
                confidence=0,
                rule_applied="Exception Check",
                source_id=f"{remittance_id}:{line_index}",
                target_id=invoice.invoice_id,
                exception_code=ExceptionCode.E004,
                exception_detail=f"Invoice {invoice.invoice_id} is already closed (possible duplicate payment)",
            )
        )

    # NOTE: Overpayment (E002) is NOT checked here.
    # It's checked in _check_overpayments() after ALL line items are matched,
    # since multiple line items can pay the same invoice.

    # Apply matching rules (customer must match for 2.1 and 2.2)
    if invoice:
        # Rule 2.1: Customer + Exact Invoice Reference
        result = _try_rule_2_1(
            remittance_id=remittance_id,
            line_index=line_index,
            line_item=line_item,
            invoice=invoice,
            customer_id=customer_id,
        )
        if result:
            return result

        # Rule 2.2: Customer + Fuzzy Invoice Reference
        result = _try_rule_2_2(
            remittance_id=remittance_id,
            line_index=line_index,
            line_item=line_item,
            invoice=invoice,
            customer_id=customer_id,
        )
        if result:
            return result

    # Rule 2.3: Fallback - try to match by amount + customer + due date when no reference
    result = _try_rule_2_3(
        remittance_id=remittance_id,
        line_index=line_index,
        line_item=line_item,
        customer_invoices=customer_invoices,
    )
    if result:
        return result

    # No match found
    return Level2Match(
        remittance_id=remittance_id,
        remittance_line_index=line_index,
        invoice_id=invoice.invoice_id if invoice else None,
        result=MatchResult(
            outcome=MatchOutcome.UNMATCHED,
            confidence=0,
            rule_applied="None",
            source_id=f"{remittance_id}:{line_index}",
            target_id=invoice.invoice_id if invoice else None,
        )
    )


def _find_invoice_by_id(
    invoice_number: str,
    invoices: list[Invoice]
) -> Optional[Invoice]:
    """
    Find an invoice by ID, using both exact and fuzzy matching.
    """
    # Try exact match first
    for inv in invoices:
        if inv.invoice_id == invoice_number:
            return inv

    # Try normalized match
    normalized_search = normalize_invoice_id(invoice_number)
    for inv in invoices:
        if normalize_invoice_id(inv.invoice_id) == normalized_search:
            return inv

    return None


def _try_rule_2_1(
    remittance_id: str,
    line_index: int,
    line_item: RemittanceLineItem,
    invoice: Invoice,
    customer_id: str,
) -> Optional[Level2Match]:
    """
    Rule 2.1: Customer + Exact Invoice Reference Match (100% confidence)

    IF customer_identified
    AND invoice.customer_id = customer_id (customer must match)
    AND remittance_line.invoice_number EXACTLY matches invoice.invoice_id
    AND invoice.status = 'Open' or 'Partial'
    → AUTO-MATCH

    Note: Amount is NOT checked here - multiple line items can pay same invoice.
    Overpayment is detected after all matches are made.
    """
    if invoice.status != InvoiceStatus.OPEN and invoice.status != InvoiceStatus.PARTIAL:
        return None

    # Verify customer matches
    if invoice.customer_id != customer_id:
        return None

    # Check for EXACT invoice match (case-insensitive, normalized)
    if line_item.invoice_number and invoice.invoice_id:
        if normalize_invoice_id(line_item.invoice_number) == normalize_invoice_id(invoice.invoice_id):
            return Level2Match(
                remittance_id=remittance_id,
                remittance_line_index=line_index,
                invoice_id=invoice.invoice_id,
                result=MatchResult(
                    outcome=MatchOutcome.AUTO_MATCHED,
                    confidence=100,
                    rule_applied="2.1: Customer + Exact Invoice Reference",
                    source_id=f"{remittance_id}:{line_index}",
                    target_id=invoice.invoice_id,
                )
            )

    return None


def _try_rule_2_2(
    remittance_id: str,
    line_index: int,
    line_item: RemittanceLineItem,
    invoice: Invoice,
    customer_id: str,
) -> Optional[Level2Match]:
    """
    Rule 2.2: Customer + Fuzzy Invoice Reference Match (95% confidence)

    IF customer_identified
    AND invoice.customer_id = customer_id (customer must match)
    AND remittance_line.invoice_number fuzzy matches invoice.invoice_id (≥80% similarity)
    AND invoice.status = 'Open' or 'Partial'
    → AUTO-MATCH

    Note: Amount is NOT checked here - multiple line items can pay same invoice.
    """
    if invoice.status != InvoiceStatus.OPEN and invoice.status != InvoiceStatus.PARTIAL:
        return None

    # Verify customer matches
    if invoice.customer_id != customer_id:
        return None

    # Check for fuzzy invoice match (uses similarity threshold)
    if line_item.invoice_number and invoice.invoice_id:
        if invoice_ids_match(line_item.invoice_number, invoice.invoice_id):
            return Level2Match(
                remittance_id=remittance_id,
                remittance_line_index=line_index,
                invoice_id=invoice.invoice_id,
                result=MatchResult(
                    outcome=MatchOutcome.AUTO_MATCHED,
                    confidence=95,
                    rule_applied="2.2: Customer + Fuzzy Invoice Reference",
                    source_id=f"{remittance_id}:{line_index}",
                    target_id=invoice.invoice_id,
                )
            )

    return None


def _try_rule_2_3(
    remittance_id: str,
    line_index: int,
    line_item: RemittanceLineItem,
    customer_invoices: list[Invoice],
    payment_date: Optional[str] = None,
) -> Optional[Level2Match]:
    """
    Rule 2.3: Amount + Customer + Due Date Proximity (85% confidence)

    Fallback when no invoice reference is available:
    IF customer_identified
    AND remittance_line.amount matches an open invoice amount (within tolerance)
    AND invoice.due_date is in vicinity of payment date (±30 days)
    → AUTO-MATCH

    This is for cases where the remittance has no invoice reference but we can
    infer the match from amount and timing.
    """
    from datetime import datetime, timedelta

    # Amount tolerance for matching
    AMOUNT_TOLERANCE = Decimal("0.50")
    # Due date proximity window (days before/after payment)
    DUE_DATE_WINDOW_DAYS = 30

    best_match = None
    best_score = 0

    for invoice in customer_invoices:
        if invoice.status != InvoiceStatus.OPEN and invoice.status != InvoiceStatus.PARTIAL:
            continue

        # Check amount match within tolerance
        amount_diff = abs(line_item.amount - invoice.pending_amount)
        if amount_diff > AMOUNT_TOLERANCE:
            continue

        # Calculate match score
        score = 85  # Base score

        # Bonus for exact amount match
        if amount_diff == Decimal("0"):
            score += 5

        # Check due date proximity if we have payment date
        if payment_date and invoice.due_date:
            try:
                pay_dt = datetime.fromisoformat(payment_date.replace('Z', '+00:00'))
                due_dt = datetime.fromisoformat(invoice.due_date.replace('Z', '+00:00'))
                days_diff = abs((pay_dt - due_dt).days)

                if days_diff <= DUE_DATE_WINDOW_DAYS:
                    # Closer to due date = higher score
                    proximity_bonus = max(0, 10 - (days_diff // 3))
                    score += proximity_bonus
                else:
                    # Outside window, reduce score significantly
                    score -= 20
            except (ValueError, TypeError):
                pass  # Can't parse dates, skip proximity check

        if score > best_score:
            best_score = score
            best_match = invoice

    if best_match and best_score >= 75:
        return Level2Match(
            remittance_id=remittance_id,
            remittance_line_index=line_index,
            invoice_id=best_match.invoice_id,
            result=MatchResult(
                outcome=MatchOutcome.AUTO_MATCHED,
                confidence=min(best_score, 85),  # Cap at 85%
                rule_applied="2.3: Amount + Customer + Due Date",
                source_id=f"{remittance_id}:{line_index}",
                target_id=best_match.invoice_id,
            )
        )

    return None


def apply_invoice_updates(
    matches: list[Level2Match],
    invoices: list[Invoice],
    remittances: list[Remittance],
) -> list[Invoice]:
    """
    Apply the matched payments to invoices, updating pending amounts and status.

    Tracks cumulative payments per invoice - multiple line items can pay same invoice.

    Invoice Status Updates:
    - PARTIAL: pending_amount > 0 (underpayment)
    - CLOSED: pending_amount = 0 (fully paid)

    Note: Overpayment is an EXCEPTION (E002), not a status.

    Returns the updated list of invoices.
    """
    # Create a mutable copy
    invoice_map = {inv.invoice_id: Invoice(
        invoice_id=inv.invoice_id,
        customer_id=inv.customer_id,
        due_date=inv.due_date,
        amount=inv.amount,
        pending_amount=inv.pending_amount,
        status=inv.status,
    ) for inv in invoices}

    # Build remittance lookup for getting line item amounts
    remittance_map = {rem.id: rem for rem in remittances}

    # Track cumulative payments per invoice
    cumulative_payments: dict[str, Decimal] = {}

    for match in matches:
        if match.result.outcome != MatchOutcome.AUTO_MATCHED:
            continue

        if not match.invoice_id or match.invoice_id not in invoice_map:
            continue

        # Get the payment amount from the line item
        remittance = remittance_map.get(match.remittance_id)
        if not remittance or match.remittance_line_index >= len(remittance.line_items):
            continue

        payment_amount = remittance.line_items[match.remittance_line_index].amount

        # Track cumulative payment
        if match.invoice_id not in cumulative_payments:
            cumulative_payments[match.invoice_id] = Decimal("0")
        cumulative_payments[match.invoice_id] += payment_amount

    # Apply cumulative payments to invoices
    for inv_id, total_paid in cumulative_payments.items():
        if inv_id not in invoice_map:
            continue

        invoice = invoice_map[inv_id]
        original_pending = invoice.pending_amount

        # Calculate new pending amount (don't go below 0 - overpayment is exception)
        new_pending = max(Decimal("0"), original_pending - total_paid)

        # Update status based on payment result
        if new_pending == Decimal("0"):
            invoice.status = InvoiceStatus.CLOSED
            invoice.pending_amount = Decimal("0")
        else:
            invoice.status = InvoiceStatus.PARTIAL
            invoice.pending_amount = new_pending

    return list(invoice_map.values())
