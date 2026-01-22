"""Phase 2: Direct reference matching.

This phase handles matching when no remittance is available
but invoice references are found in bank transaction descriptions.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Set

from ..config import ReconciliationConfig
from ..models.bank import BankTransaction
from ..models.invoice import Invoice
from ..models.match import (
    InvoiceAllocation,
    MatchStatus,
    MatchType,
    ReconciliationMatch,
)
from ..utils.reference_extractor import (
    extract_invoice_references,
    normalize_reference,
)
from ..utils.validators import amounts_match


@dataclass
class Phase2Result:
    """Result from Phase 2 processing."""

    matches: List[ReconciliationMatch] = field(default_factory=list)
    matched_bank_ids: Set[str] = field(default_factory=set)


class Phase2ReferenceMatcher:
    """Phase 2: Direct reference matching algorithm."""

    def __init__(self, config: ReconciliationConfig):
        self.config = config

    def process(
        self,
        banks: List[BankTransaction],
        invoices: List[Invoice],
        already_matched_bank_ids: Set[str],
    ) -> Phase2Result:
        """Execute Phase 2 matching.

        Args:
            banks: Bank transactions to match.
            invoices: Available invoices.
            already_matched_bank_ids: Banks already matched in Phase 1.

        Returns:
            Phase2Result with matches found.
        """
        result = Phase2Result()

        # Build invoice indexes
        invoice_by_number = self._build_invoice_index(invoices)
        invoice_by_id = {inv.id: inv for inv in invoices}

        # Process unmatched banks
        for bank in banks:
            if bank.id in already_matched_bank_ids:
                continue

            match = self._try_reference_match(
                bank, invoice_by_number, invoice_by_id
            )
            if match:
                result.matches.append(match)
                result.matched_bank_ids.add(bank.id)

        return result

    def _build_invoice_index(
        self, invoices: List[Invoice]
    ) -> Dict[str, List[Invoice]]:
        """Build index of invoices by normalized invoice number."""
        index: Dict[str, List[Invoice]] = {}
        for inv in invoices:
            normalized = normalize_reference(inv.invoice_number)
            if normalized not in index:
                index[normalized] = []
            index[normalized].append(inv)
        return index

    def _try_reference_match(
        self,
        bank: BankTransaction,
        invoice_by_number: Dict[str, List[Invoice]],
        invoice_by_id: Dict[str, Invoice],
    ) -> ReconciliationMatch | None:
        """Try to match a bank transaction via reference extraction.

        Args:
            bank: Bank transaction to match.
            invoice_by_number: Index of invoices by number.
            invoice_by_id: Index of invoices by ID.

        Returns:
            ReconciliationMatch if successful, None otherwise.
        """
        # Extract references from description
        refs = extract_invoice_references(bank.description)
        if not refs:
            return None

        # Find matching invoices
        matched_invoices: List[Invoice] = []
        for ref in refs:
            normalized = normalize_reference(ref)
            if normalized in invoice_by_number:
                # Add all matches, filtering by customer if available
                for inv in invoice_by_number[normalized]:
                    if bank.customer_id and inv.customer_id != bank.customer_id:
                        continue
                    if inv not in matched_invoices:
                        matched_invoices.append(inv)

        if not matched_invoices:
            return None

        # Filter to open invoices
        open_invoices = [inv for inv in matched_invoices if not inv.is_fully_paid]
        if not open_invoices:
            return None

        # Try to allocate bank amount to matched invoices
        allocations = self._allocate_to_invoices(bank.amount, open_invoices)
        if not allocations:
            return None

        # Calculate confidence based on amount match
        total_allocated = sum(a.amount for a in allocations)
        if amounts_match(
            bank.amount,
            total_allocated,
            self.config.amount_tolerance_percent,
            self.config.amount_tolerance_absolute,
        ):
            confidence = 0.95  # High confidence - amount matches
            status = MatchStatus.AUTO_APPROVED
        else:
            confidence = 0.75  # Medium confidence - amount doesn't match exactly
            status = MatchStatus.SUGGESTION

        return ReconciliationMatch(
            bank_id=bank.id,
            allocations=allocations,
            match_type=MatchType.REFERENCE_BASED,
            status=status,
            remittance_id=None,
            exceptions=[],
            confidence=confidence,
        )

    def _allocate_to_invoices(
        self, amount: Decimal, invoices: List[Invoice]
    ) -> List[InvoiceAllocation]:
        """Allocate a bank amount to a list of invoices.

        Strategy:
        1. If single invoice and amount matches - allocate fully
        2. If single invoice and amount doesn't match - partial allocation
        3. If multiple invoices - try to find combination that matches

        Args:
            amount: Amount to allocate.
            invoices: Invoices to allocate to.

        Returns:
            List of allocations.
        """
        if not invoices:
            return []

        # Sort invoices by pending amount (smallest first for better matching)
        sorted_invoices = sorted(invoices, key=lambda i: i.pending_amount)

        # Case 1: Single invoice
        if len(sorted_invoices) == 1:
            invoice = sorted_invoices[0]
            alloc_amount = min(amount, invoice.pending_amount)
            remaining = invoice.pending_amount - alloc_amount
            return [
                InvoiceAllocation(
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    amount=alloc_amount,
                    is_partial=remaining > Decimal("0"),
                    remaining_after=remaining,
                )
            ]

        # Case 2: Multiple invoices - try exact match first
        exact_match = self._find_exact_combination(amount, sorted_invoices)
        if exact_match:
            return exact_match

        # Case 3: Multiple invoices - allocate in order
        allocations: List[InvoiceAllocation] = []
        remaining_amount = amount

        for invoice in sorted_invoices:
            if remaining_amount <= Decimal("0"):
                break

            alloc_amount = min(remaining_amount, invoice.pending_amount)
            remaining = invoice.pending_amount - alloc_amount

            allocations.append(
                InvoiceAllocation(
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    amount=alloc_amount,
                    is_partial=remaining > Decimal("0"),
                    remaining_after=remaining,
                )
            )

            remaining_amount -= alloc_amount

        return allocations

    def _find_exact_combination(
        self, target: Decimal, invoices: List[Invoice]
    ) -> List[InvoiceAllocation] | None:
        """Find a combination of invoices that exactly matches the target.

        Uses subset sum approach with tolerance.

        Args:
            target: Target amount to match.
            invoices: Available invoices.

        Returns:
            Allocations if exact match found, None otherwise.
        """
        # Limit search for performance
        if len(invoices) > 10:
            invoices = invoices[:10]

        # Try single invoices first
        for inv in invoices:
            if amounts_match(
                inv.pending_amount,
                target,
                self.config.amount_tolerance_percent,
                self.config.amount_tolerance_absolute,
            ):
                return [
                    InvoiceAllocation(
                        invoice_id=inv.id,
                        invoice_number=inv.invoice_number,
                        amount=inv.pending_amount,
                        is_partial=False,
                        remaining_after=Decimal("0"),
                    )
                ]

        # Try pairs
        for i, inv1 in enumerate(invoices):
            for inv2 in invoices[i + 1 :]:
                combined = inv1.pending_amount + inv2.pending_amount
                if amounts_match(
                    combined,
                    target,
                    self.config.amount_tolerance_percent,
                    self.config.amount_tolerance_absolute,
                ):
                    return [
                        InvoiceAllocation(
                            invoice_id=inv1.id,
                            invoice_number=inv1.invoice_number,
                            amount=inv1.pending_amount,
                            is_partial=False,
                            remaining_after=Decimal("0"),
                        ),
                        InvoiceAllocation(
                            invoice_id=inv2.id,
                            invoice_number=inv2.invoice_number,
                            amount=inv2.pending_amount,
                            is_partial=False,
                            remaining_after=Decimal("0"),
                        ),
                    ]

        # Try triples (limit to first 6 invoices for performance)
        limited_invoices = invoices[:6]
        for i, inv1 in enumerate(limited_invoices):
            for j, inv2 in enumerate(limited_invoices[i + 1 :], i + 1):
                for inv3 in limited_invoices[j + 1 :]:
                    combined = (
                        inv1.pending_amount + inv2.pending_amount + inv3.pending_amount
                    )
                    if amounts_match(
                        combined,
                        target,
                        self.config.amount_tolerance_percent,
                        self.config.amount_tolerance_absolute,
                    ):
                        return [
                            InvoiceAllocation(
                                invoice_id=inv1.id,
                                invoice_number=inv1.invoice_number,
                                amount=inv1.pending_amount,
                                is_partial=False,
                                remaining_after=Decimal("0"),
                            ),
                            InvoiceAllocation(
                                invoice_id=inv2.id,
                                invoice_number=inv2.invoice_number,
                                amount=inv2.pending_amount,
                                is_partial=False,
                                remaining_after=Decimal("0"),
                            ),
                            InvoiceAllocation(
                                invoice_id=inv3.id,
                                invoice_number=inv3.invoice_number,
                                amount=inv3.pending_amount,
                                is_partial=False,
                                remaining_after=Decimal("0"),
                            ),
                        ]

        return None
