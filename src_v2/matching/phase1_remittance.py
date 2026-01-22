"""Phase 1: Remittance-backed matching.

This phase handles matching when remittance advice is available.
Steps:
    1A: Match banks to remittances (binary matching on reference + customer)
    1B: Validate bank-remittance pairs (amount/date checks)
    1C: Match remittance line items to invoices
    1D: Decide auto-approve or exception
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple

from ..config import ReconciliationConfig
from ..models.bank import BankTransaction
from ..models.exception import ExceptionType, MatchException, Severity
from ..models.invoice import Invoice
from ..models.match import (
    InvoiceAllocation,
    MatchStatus,
    MatchType,
    ReconciliationMatch,
)
from ..models.remittance import Remittance, RemittanceLineItem
from ..utils.reference_extractor import normalize_reference, references_match
from ..utils.validators import (
    amounts_match,
    calculate_amount_difference,
    dates_within_tolerance,
)


@dataclass
class Phase1Result:
    """Result from Phase 1 processing."""

    matches: List[ReconciliationMatch] = field(default_factory=list)
    orphan_remittances: List[Remittance] = field(default_factory=list)
    matched_bank_ids: Set[str] = field(default_factory=set)
    matched_remittance_ids: Set[str] = field(default_factory=set)


class Phase1RemittanceMatcher:
    """Phase 1: Remittance-backed matching algorithm."""

    def __init__(self, config: ReconciliationConfig):
        self.config = config

    def process(
        self,
        banks: List[BankTransaction],
        remittances: List[Remittance],
        invoices: List[Invoice],
    ) -> Phase1Result:
        """Execute Phase 1 matching.

        Args:
            banks: Bank transactions to match.
            remittances: Remittance advices.
            invoices: Available invoices.

        Returns:
            Phase1Result with matches and orphans.
        """
        result = Phase1Result()

        # Build indexes
        invoice_by_number = self._build_invoice_index(invoices)
        invoice_by_id = {inv.id: inv for inv in invoices}

        # Phase 1A: Match banks to remittances
        bank_to_remittances = self._match_banks_to_remittances(banks, remittances)

        # Track which remittances got matched
        matched_remittance_ids: Set[str] = set()

        for bank in banks:
            matched_rems = bank_to_remittances.get(bank.id, [])

            if not matched_rems:
                # No remittance match - will be handled by Phase 2/3
                continue

            # Handle multiple remittances for one bank
            if len(matched_rems) > 1:
                match = self._handle_multiple_remittances(
                    bank, matched_rems, invoice_by_number, invoice_by_id
                )
            else:
                remittance = matched_rems[0]
                match = self._process_single_remittance(
                    bank, remittance, invoice_by_number, invoice_by_id
                )

            result.matches.append(match)
            result.matched_bank_ids.add(bank.id)
            for rem in matched_rems:
                matched_remittance_ids.add(rem.id)

        # Check for orphan remittances (remittances without matching bank)
        for remittance in remittances:
            if remittance.id not in matched_remittance_ids:
                # Check if any bank could match this remittance
                has_potential_match = self._check_potential_bank_matches(
                    remittance, banks, result.matched_bank_ids
                )
                if not has_potential_match:
                    result.orphan_remittances.append(remittance)

        result.matched_remittance_ids = matched_remittance_ids
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

    def _match_banks_to_remittances(
        self, banks: List[BankTransaction], remittances: List[Remittance]
    ) -> Dict[str, List[Remittance]]:
        """Phase 1A: Binary matching of banks to remittances.

        Matches on:
        1. Payment reference (exact or normalized match)
        2. Customer ID (if available)
        3. Amount (within tolerance)
        """
        bank_to_remittances: Dict[str, List[Remittance]] = {}

        for bank in banks:
            matches = []
            for remittance in remittances:
                if self._bank_remittance_match(bank, remittance):
                    matches.append(remittance)

            if matches:
                bank_to_remittances[bank.id] = matches

        return bank_to_remittances

    def _bank_remittance_match(
        self, bank: BankTransaction, remittance: Remittance
    ) -> bool:
        """Check if bank and remittance match.

        Two matching strategies:
        1. PRIMARY: Reference match (most reliable)
        2. FALLBACK: Customer + Amount + Date + Payment Method (all must match)
        """
        # Try primary match first: Reference
        if self._match_by_reference(bank, remittance):
            return True

        # Try fallback match: Customer + Amount + Date + Payment Method
        if self._match_by_attributes(bank, remittance):
            return True

        return False

    def _match_by_reference(
        self, bank: BankTransaction, remittance: Remittance
    ) -> bool:
        """Primary matching: by payment reference."""
        # Both must have references
        if not bank.reference or not remittance.payment_reference:
            return False

        if not references_match(bank.reference, remittance.payment_reference):
            return False

        # Customer must match if both are known
        if bank.customer_id and remittance.payer_id:
            if bank.customer_id != remittance.payer_id:
                return False

        # Amount should be reasonably close
        if not amounts_match(
            bank.amount,
            remittance.payment_amount_total,
            self.config.amount_tolerance_percent * 2,
            self.config.amount_tolerance_absolute * 2,
        ):
            return False

        return True

    def _match_by_attributes(
        self, bank: BankTransaction, remittance: Remittance
    ) -> bool:
        """Fallback matching: by customer + amount + date + payment method.

        All criteria must match for this to succeed.
        This is used when reference matching fails.
        """
        # Customer ID is REQUIRED for fallback match
        if not bank.customer_id or not remittance.payer_id:
            return False
        if bank.customer_id != remittance.payer_id:
            return False

        # Amount must match exactly (strict for fallback)
        if not amounts_match(
            bank.amount,
            remittance.payment_amount_total,
            self.config.amount_tolerance_percent,
            self.config.amount_tolerance_absolute,
        ):
            return False

        # Date must be within tolerance
        if not dates_within_tolerance(
            bank.date,
            remittance.payment_date,
            self.config.date_tolerance_days,
        ):
            return False

        # Payment method must match if both are known
        if bank.payment_method and remittance.payment_method:
            if bank.payment_method.upper() != remittance.payment_method.upper():
                return False

        return True

    def _process_single_remittance(
        self,
        bank: BankTransaction,
        remittance: Remittance,
        invoice_by_number: Dict[str, List[Invoice]],
        invoice_by_id: Dict[str, Invoice],
    ) -> ReconciliationMatch:
        """Process a bank matched to a single remittance."""
        exceptions: List[MatchException] = []

        # Phase 1B: Validate bank-remittance pair
        exceptions.extend(
            self._validate_bank_remittance_pair(bank, remittance)
        )

        # Check internal remittance consistency
        exceptions.extend(self._validate_remittance_internal(remittance))

        # Phase 1C: Match line items to invoices
        allocations, line_exceptions = self._match_line_items_to_invoices(
            remittance, invoice_by_number, invoice_by_id
        )
        exceptions.extend(line_exceptions)

        # Phase 1D: Decide status
        status = self._decide_status(exceptions)

        return ReconciliationMatch(
            bank_id=bank.id,
            allocations=allocations,
            match_type=MatchType.REMITTANCE_BACKED,
            status=status,
            remittance_id=remittance.id,
            exceptions=exceptions,
            confidence=1.0 if status == MatchStatus.AUTO_APPROVED else 0.8,
        )

    def _handle_multiple_remittances(
        self,
        bank: BankTransaction,
        remittances: List[Remittance],
        invoice_by_number: Dict[str, List[Invoice]],
        invoice_by_id: Dict[str, Invoice],
    ) -> ReconciliationMatch:
        """Handle case where multiple remittances match one bank."""
        exceptions: List[MatchException] = []

        # Add exception for multiple remittances
        exceptions.append(
            MatchException(
                type=ExceptionType.MULTIPLE_REMITTANCES_ONE_BANK,
                severity=Severity.WARNING,
                entity_id=bank.id,
                details={
                    "remittance_ids": [r.id for r in remittances],
                    "remittance_amounts": [
                        str(r.payment_amount_total) for r in remittances
                    ],
                    "bank_amount": str(bank.amount),
                },
                suggested_resolution="Review and select the correct remittance",
            )
        )

        # Check if combined amount matches
        total_remittance_amount = sum(
            r.payment_amount_total for r in remittances
        )
        if amounts_match(
            bank.amount,
            total_remittance_amount,
            self.config.amount_tolerance_percent,
            self.config.amount_tolerance_absolute,
        ):
            # Combined remittances match - this might be intentional
            exceptions[-1].severity = Severity.INFO
            exceptions[-1].suggested_resolution = (
                "Combined remittance amounts match bank amount"
            )

        # Collect all allocations from all remittances
        all_allocations: List[InvoiceAllocation] = []
        for remittance in remittances:
            allocations, line_exceptions = self._match_line_items_to_invoices(
                remittance, invoice_by_number, invoice_by_id
            )
            all_allocations.extend(allocations)
            exceptions.extend(line_exceptions)

        return ReconciliationMatch(
            bank_id=bank.id,
            allocations=all_allocations,
            match_type=MatchType.REMITTANCE_BACKED,
            status=MatchStatus.EXCEPTION,
            remittance_id=remittances[0].id,  # Primary remittance
            exceptions=exceptions,
            confidence=0.6,
        )

    def _validate_bank_remittance_pair(
        self, bank: BankTransaction, remittance: Remittance
    ) -> List[MatchException]:
        """Phase 1B: Validate a bank-remittance pair."""
        exceptions: List[MatchException] = []

        # Amount check
        if not amounts_match(
            bank.amount,
            remittance.payment_amount_total,
            self.config.amount_tolerance_percent,
            self.config.amount_tolerance_absolute,
        ):
            abs_diff, pct_diff = calculate_amount_difference(
                bank.amount, remittance.payment_amount_total
            )
            exceptions.append(
                MatchException(
                    type=ExceptionType.AMOUNT_MISMATCH,
                    severity=Severity.WARNING if pct_diff < 5 else Severity.CRITICAL,
                    entity_id=bank.id,
                    details={
                        "bank_amount": str(bank.amount),
                        "remittance_amount": str(remittance.payment_amount_total),
                        "difference": str(abs_diff),
                        "difference_percent": f"{pct_diff:.2f}%",
                    },
                    suggested_resolution="Verify amounts with customer",
                )
            )

        # Date check
        if not dates_within_tolerance(
            bank.date, remittance.payment_date, self.config.date_tolerance_days
        ):
            days_diff = abs((bank.date - remittance.payment_date).days)
            exceptions.append(
                MatchException(
                    type=ExceptionType.DATE_DISCREPANCY,
                    severity=Severity.INFO,
                    entity_id=bank.id,
                    details={
                        "bank_date": str(bank.date),
                        "remittance_date": str(remittance.payment_date),
                        "days_difference": days_diff,
                    },
                    suggested_resolution="Date discrepancy may be due to processing delays",
                )
            )

        # Customer mismatch check
        if bank.customer_id and remittance.payer_id:
            if bank.customer_id != remittance.payer_id:
                exceptions.append(
                    MatchException(
                        type=ExceptionType.CUSTOMER_MISMATCH,
                        severity=Severity.WARNING,
                        entity_id=bank.id,
                        details={
                            "bank_customer_id": bank.customer_id,
                            "remittance_payer_id": remittance.payer_id,
                        },
                        suggested_resolution="Verify customer identity",
                    )
                )

        return exceptions

    def _validate_remittance_internal(
        self, remittance: Remittance
    ) -> List[MatchException]:
        """Validate internal consistency of remittance."""
        exceptions: List[MatchException] = []

        # Check line items sum
        if remittance.line_items and remittance.has_line_items_mismatch:
            abs_diff, pct_diff = calculate_amount_difference(
                remittance.line_items_total, remittance.payment_amount_total
            )
            exceptions.append(
                MatchException(
                    type=ExceptionType.LINE_ITEMS_SUM_MISMATCH,
                    severity=Severity.WARNING,
                    entity_id=remittance.id,
                    details={
                        "line_items_total": str(remittance.line_items_total),
                        "payment_total": str(remittance.payment_amount_total),
                        "difference": str(abs_diff),
                    },
                    suggested_resolution="Review remittance for missing line items",
                )
            )

        # Check deductions have reasons
        for item in remittance.line_items:
            if item.has_deduction and not item.deduction_reason:
                exceptions.append(
                    MatchException(
                        type=ExceptionType.DEDUCTION_WITHOUT_REASON,
                        severity=Severity.INFO,
                        entity_id=remittance.id,
                        details={
                            "invoice_number": item.invoice_number,
                            "deduction_amount": str(item.deduction_amount),
                        },
                        suggested_resolution="Request deduction explanation from customer",
                    )
                )

        return exceptions

    def _match_line_items_to_invoices(
        self,
        remittance: Remittance,
        invoice_by_number: Dict[str, List[Invoice]],
        invoice_by_id: Dict[str, Invoice],
    ) -> Tuple[List[InvoiceAllocation], List[MatchException]]:
        """Phase 1C: Match remittance line items to invoices."""
        allocations: List[InvoiceAllocation] = []
        exceptions: List[MatchException] = []

        for item in remittance.line_items:
            normalized_inv_num = normalize_reference(item.invoice_number)
            matching_invoices = invoice_by_number.get(normalized_inv_num, [])

            if not matching_invoices:
                exceptions.append(
                    MatchException(
                        type=ExceptionType.INVOICE_NOT_FOUND,
                        severity=Severity.WARNING,
                        entity_id=remittance.id,
                        details={
                            "invoice_number": item.invoice_number,
                            "amount_paid": str(item.amount_paid),
                        },
                        suggested_resolution="Create or locate missing invoice",
                    )
                )
                continue

            # Use the first matching invoice (or filter by customer if multiple)
            invoice = matching_invoices[0]
            if len(matching_invoices) > 1:
                # Try to find one matching the remittance customer
                for inv in matching_invoices:
                    if inv.customer_id == remittance.payer_id:
                        invoice = inv
                        break

            # Check for duplicate payment
            if invoice.is_fully_paid:
                exceptions.append(
                    MatchException(
                        type=ExceptionType.DUPLICATE_PAYMENT,
                        severity=Severity.CRITICAL,
                        entity_id=remittance.id,
                        details={
                            "invoice_number": item.invoice_number,
                            "invoice_id": invoice.id,
                            "payment_amount": str(item.amount_paid),
                        },
                        suggested_resolution="Invoice already paid - verify or refund",
                    )
                )

            # Check for overpayment
            is_partial = False
            remaining = Decimal("0")

            if item.amount_paid > invoice.pending_amount:
                overpayment = item.amount_paid - invoice.pending_amount
                if overpayment > self.config.amount_tolerance_absolute:
                    exceptions.append(
                        MatchException(
                            type=ExceptionType.OVERPAYMENT,
                            severity=Severity.WARNING,
                            entity_id=remittance.id,
                            details={
                                "invoice_number": item.invoice_number,
                                "pending_amount": str(invoice.pending_amount),
                                "amount_paid": str(item.amount_paid),
                                "overpayment": str(overpayment),
                            },
                            suggested_resolution="Apply overpayment to future invoices or refund",
                        )
                    )
            elif item.amount_paid < invoice.pending_amount:
                is_partial = True
                remaining = invoice.pending_amount - item.amount_paid

            # Customer mismatch
            if invoice.customer_id != remittance.payer_id:
                exceptions.append(
                    MatchException(
                        type=ExceptionType.CUSTOMER_MISMATCH,
                        severity=Severity.WARNING,
                        entity_id=remittance.id,
                        details={
                            "invoice_customer_id": invoice.customer_id,
                            "remittance_payer_id": remittance.payer_id,
                            "invoice_number": item.invoice_number,
                        },
                        suggested_resolution="Verify payment is from correct customer",
                    )
                )

            # Credit note handling
            if item.credit_note_reference:
                # Try to find credit note
                normalized_cn = normalize_reference(item.credit_note_reference)
                if normalized_cn not in invoice_by_number:
                    exceptions.append(
                        MatchException(
                            type=ExceptionType.CREDIT_NOTE_NOT_FOUND,
                            severity=Severity.INFO,
                            entity_id=remittance.id,
                            details={
                                "credit_note_reference": item.credit_note_reference,
                                "invoice_number": item.invoice_number,
                            },
                            suggested_resolution="Locate or create credit note",
                        )
                    )

            allocations.append(
                InvoiceAllocation(
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    amount=item.amount_paid,
                    is_partial=is_partial,
                    remaining_after=remaining,
                )
            )

        return allocations, exceptions

    def _decide_status(self, exceptions: List[MatchException]) -> MatchStatus:
        """Phase 1D: Decide match status based on exceptions."""
        if not exceptions:
            return MatchStatus.AUTO_APPROVED

        # Check for blocking exceptions
        has_critical = any(e.severity == Severity.CRITICAL for e in exceptions)
        has_warning = any(e.severity == Severity.WARNING for e in exceptions)

        if has_critical:
            return MatchStatus.EXCEPTION

        if has_warning:
            return MatchStatus.EXCEPTION

        # Only INFO-level exceptions - can auto-approve
        return MatchStatus.AUTO_APPROVED

    def _check_potential_bank_matches(
        self,
        remittance: Remittance,
        banks: List[BankTransaction],
        already_matched: Set[str],
    ) -> bool:
        """Check if any unmatched bank could potentially match this remittance."""
        for bank in banks:
            if bank.id in already_matched:
                continue

            # Check if amounts are close
            if amounts_match(
                bank.amount,
                remittance.payment_amount_total,
                self.config.amount_tolerance_percent * 3,
                self.config.amount_tolerance_absolute * 3,
            ):
                # Check date proximity
                if dates_within_tolerance(
                    bank.date,
                    remittance.payment_date,
                    self.config.date_tolerance_days * 2,
                ):
                    return True

        return False
