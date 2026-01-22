"""Main reconciliation engine orchestrator.

This module provides the main entry point for cash reconciliation,
coordinating the three phases of matching.
"""

from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Set

from .config import ReconciliationConfig
from .matching.phase1_remittance import Phase1RemittanceMatcher
from .matching.phase2_reference import Phase2ReferenceMatcher
from .matching.phase3_suggestions import Phase3SuggestionGenerator
from .models.bank import BankTransaction
from .models.exception import ExceptionType, MatchException
from .models.invoice import Invoice
from .models.match import MatchStatus, ReconciliationMatch
from .models.remittance import Remittance
from .models.result import ReconciliationResult, ReconciliationStats


class ReconciliationEngine:
    """Main orchestrator for cash reconciliation.

    Coordinates the three phases:
    1. Remittance-backed matching
    2. Direct reference matching
    3. Suggestion generation

    Usage:
        engine = ReconciliationEngine()
        result = engine.reconcile(banks, invoices, remittances)
    """

    def __init__(self, config: ReconciliationConfig | None = None):
        """Initialize the reconciliation engine.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or ReconciliationConfig()
        self._phase1 = Phase1RemittanceMatcher(self.config)
        self._phase2 = Phase2ReferenceMatcher(self.config)
        self._phase3 = Phase3SuggestionGenerator(self.config)

    def reconcile(
        self,
        banks: List[BankTransaction],
        invoices: List[Invoice],
        remittances: List[Remittance] | None = None,
    ) -> ReconciliationResult:
        """Execute the complete reconciliation process.

        Args:
            banks: Bank transactions to reconcile.
            invoices: Available invoices.
            remittances: Optional remittance advices.

        Returns:
            ReconciliationResult with all matches, suggestions, and exceptions.
        """
        remittances = remittances or []

        # Track progress
        matched_bank_ids: Set[str] = set()
        matched_invoice_ids: Set[str] = set()  # Track allocated invoices
        auto_approved: List[ReconciliationMatch] = []
        exceptions: List[ReconciliationMatch] = []

        # Phase 1: Remittance-backed matching
        if remittances:
            phase1_result = self._phase1.process(banks, remittances, invoices)

            for match in phase1_result.matches:
                if match.status == MatchStatus.AUTO_APPROVED:
                    auto_approved.append(match)
                else:
                    exceptions.append(match)
                # Track allocated invoice IDs
                for alloc in match.allocations:
                    matched_invoice_ids.add(alloc.invoice_id)

            matched_bank_ids.update(phase1_result.matched_bank_ids)
            orphan_remittances = phase1_result.orphan_remittances
        else:
            orphan_remittances = []

        # Phase 2: Direct reference matching
        phase2_result = self._phase2.process(banks, invoices, matched_bank_ids)

        for match in phase2_result.matches:
            if match.status == MatchStatus.AUTO_APPROVED:
                auto_approved.append(match)
            else:
                exceptions.append(match)
            # Track allocated invoice IDs
            for alloc in match.allocations:
                matched_invoice_ids.add(alloc.invoice_id)

        matched_bank_ids.update(phase2_result.matched_bank_ids)

        # Phase 3: Suggestion generation
        phase3_result = self._phase3.process(
            banks, invoices, matched_bank_ids, matched_invoice_ids
        )

        # Compile statistics
        stats = self._compile_stats(
            banks=banks,
            remittances=remittances,
            auto_approved=auto_approved,
            exceptions=exceptions,
            suggestions=phase3_result.suggestions,
            manual=phase3_result.manual_items,
            orphan_remittances=orphan_remittances,
        )

        return ReconciliationResult(
            auto_approved=auto_approved,
            exceptions=exceptions,
            suggestions=phase3_result.suggestions,
            manual=phase3_result.manual_items,
            orphan_remittances=orphan_remittances,
            stats=stats,
        )

    def _compile_stats(
        self,
        banks: List[BankTransaction],
        remittances: List[Remittance],
        auto_approved: List[ReconciliationMatch],
        exceptions: List[ReconciliationMatch],
        suggestions: list,
        manual: list,
        orphan_remittances: List[Remittance],
    ) -> ReconciliationStats:
        """Compile reconciliation statistics.

        Args:
            banks: All bank transactions.
            remittances: All remittances.
            auto_approved: Auto-approved matches.
            exceptions: Matches with exceptions.
            suggestions: Generated suggestions.
            manual: Manual items.
            orphan_remittances: Orphan remittances.

        Returns:
            ReconciliationStats object.
        """
        # Count exceptions by type
        exception_by_type: Dict[ExceptionType, int] = defaultdict(int)
        for match in exceptions:
            for exc in match.exceptions:
                exception_by_type[exc.type] += 1

        # Calculate auto-approved amount
        auto_approved_amount = sum(
            (match.total_allocated for match in auto_approved),
            start=Decimal("0"),
        )

        return ReconciliationStats(
            total_banks=len(banks),
            total_remittances=len(remittances),
            auto_approved_count=len(auto_approved),
            auto_approved_amount=auto_approved_amount,
            exception_count=len(exceptions),
            exception_by_type=dict(exception_by_type),
            suggestion_count=len(suggestions),
            manual_count=len(manual),
            orphan_remittance_count=len(orphan_remittances),
        )

    def reconcile_single(
        self,
        bank: BankTransaction,
        invoices: List[Invoice],
        remittance: Remittance | None = None,
    ) -> ReconciliationMatch | None:
        """Reconcile a single bank transaction.

        Convenience method for matching one transaction at a time.

        Args:
            bank: Bank transaction to reconcile.
            invoices: Available invoices.
            remittance: Optional associated remittance.

        Returns:
            ReconciliationMatch if matched, None otherwise.
        """
        remittances = [remittance] if remittance else []
        result = self.reconcile([bank], invoices, remittances)

        # Return the first match found
        if result.auto_approved:
            return result.auto_approved[0]
        if result.exceptions:
            return result.exceptions[0]

        return None

    def validate_match(
        self,
        match: ReconciliationMatch,
        invoices: List[Invoice],
    ) -> List[MatchException]:
        """Validate an existing match for consistency.

        Useful for re-validating manual matches or imported data.

        Args:
            match: Match to validate.
            invoices: Available invoices.

        Returns:
            List of any exceptions found.
        """
        exceptions: List[MatchException] = []
        invoice_by_id = {inv.id: inv for inv in invoices}

        for alloc in match.allocations:
            invoice = invoice_by_id.get(alloc.invoice_id)
            if not invoice:
                exceptions.append(
                    MatchException(
                        type=ExceptionType.INVOICE_NOT_FOUND,
                        severity=ExceptionType.INVOICE_NOT_FOUND,
                        entity_id=match.bank_id,
                        details={"invoice_id": alloc.invoice_id},
                    )
                )
                continue

            # Check for overpayment
            if alloc.amount > invoice.pending_amount:
                exceptions.append(
                    MatchException(
                        type=ExceptionType.OVERPAYMENT,
                        severity=ExceptionType.OVERPAYMENT,
                        entity_id=match.bank_id,
                        details={
                            "invoice_id": alloc.invoice_id,
                            "allocated": str(alloc.amount),
                            "pending": str(invoice.pending_amount),
                        },
                    )
                )

        return exceptions


def reconcile(
    banks: List[BankTransaction],
    invoices: List[Invoice],
    remittances: List[Remittance] | None = None,
    config: ReconciliationConfig | None = None,
) -> ReconciliationResult:
    """Convenience function for one-shot reconciliation.

    Args:
        banks: Bank transactions to reconcile.
        invoices: Available invoices.
        remittances: Optional remittance advices.
        config: Optional configuration.

    Returns:
        ReconciliationResult with all matches, suggestions, and exceptions.
    """
    engine = ReconciliationEngine(config)
    return engine.reconcile(banks, invoices, remittances)
