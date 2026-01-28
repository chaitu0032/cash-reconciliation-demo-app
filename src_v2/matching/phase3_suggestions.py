"""Phase 3: Suggestion generation.

This phase generates suggestions for bank transactions that couldn't
be matched via remittance or reference matching.

Strategies (in order of confidence):
1. Single invoice - customer has only one open invoice (95%)
2. Unique amount - amount uniquely matches one invoice (90%)
3. Unique combination - amount matches unique combination (85%)
4. Flow matching - use flow network for remaining (variable)
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple

from ..config import ReconciliationConfig
from ..models.bank import BankTransaction
from ..models.invoice import Invoice
from ..models.match import InvoiceAllocation
from ..models.result import CandidateInvoice, ConfidenceTier, ManualItem, Suggestion, SuggestionType
from ..utils.validators import amounts_match
from .flow_network import build_reconciliation_network, solve_flow_network


@dataclass
class Phase3Result:
    """Result from Phase 3 processing."""

    suggestions: List[Suggestion] = field(default_factory=list)
    manual_items: List[ManualItem] = field(default_factory=list)


class Phase3SuggestionGenerator:
    """Phase 3: Suggestion generation algorithm."""

    def __init__(self, config: ReconciliationConfig):
        self.config = config

    def _customers_compatible(
        self, bank_customer_id: Optional[str], invoice_customer_id: str
    ) -> bool:
        """Check if bank and invoice customers are compatible for matching.

        Returns True if:
        - Bank customer_id is unknown (None) - we can't rule it out
        - Customer IDs match

        Returns False if:
        - Both are known and different - definite mismatch
        """
        if not bank_customer_id:
            # Bank customer unknown - can't rule out any invoice
            return True
        return bank_customer_id == invoice_customer_id

    def process(
        self,
        banks: List[BankTransaction],
        invoices: List[Invoice],
        already_matched_bank_ids: Set[str],
        already_matched_invoice_ids: Set[str] | None = None,
    ) -> Phase3Result:
        """Execute Phase 3 suggestion generation.

        Args:
            banks: All bank transactions.
            invoices: Available invoices.
            already_matched_bank_ids: Banks already matched in Phase 1/2.
            already_matched_invoice_ids: Invoices already allocated in Phase 1/2.

        Returns:
            Phase3Result with suggestions and manual items.
        """
        result = Phase3Result()
        already_matched_invoice_ids = already_matched_invoice_ids or set()

        # Filter to unmatched banks and available invoices
        # Exclude invoices already allocated in Phase 1/2
        unmatched_banks = [b for b in banks if b.id not in already_matched_bank_ids]
        open_invoices = [
            inv for inv in invoices
            if not inv.is_fully_paid and inv.id not in already_matched_invoice_ids
        ]

        if not unmatched_banks:
            return result

        # Build indexes
        invoices_by_customer = self._build_customer_index(open_invoices)
        invoice_by_amount = self._build_amount_index(open_invoices)

        # Track suggested banks to avoid duplicates
        suggested_bank_ids: Set[str] = set()

        # Strategy 1: Single invoice per customer
        for bank in unmatched_banks:
            if bank.id in suggested_bank_ids:
                continue

            suggestion = self._check_single_invoice(bank, invoices_by_customer)
            if suggestion:
                result.suggestions.append(suggestion)
                suggested_bank_ids.add(bank.id)

        # Strategy 2: Unique amount match
        for bank in unmatched_banks:
            if bank.id in suggested_bank_ids:
                continue

            suggestion = self._check_unique_amount(bank, invoice_by_amount, open_invoices)
            if suggestion:
                result.suggestions.append(suggestion)
                suggested_bank_ids.add(bank.id)

        # Strategy 3: Unique combination
        for bank in unmatched_banks:
            if bank.id in suggested_bank_ids:
                continue

            suggestion = self._check_unique_combination(bank, open_invoices)
            if suggestion:
                result.suggestions.append(suggestion)
                suggested_bank_ids.add(bank.id)

        # Strategy 4: Flow network for remaining
        remaining_banks = [b for b in unmatched_banks if b.id not in suggested_bank_ids]
        remaining_invoices = [
            inv for inv in open_invoices
            if not any(
                s.allocations[0].invoice_id == inv.id
                for s in result.suggestions
                if s.allocations
            )
        ]

        if remaining_banks and remaining_invoices:
            flow_suggestions, manual = self._run_flow_matching(
                remaining_banks, remaining_invoices
            )
            result.suggestions.extend(flow_suggestions)
            suggested_bank_ids.update(s.bank_id for s in flow_suggestions)

        # Any remaining banks go to manual
        for bank in unmatched_banks:
            if bank.id not in suggested_bank_ids:
                # Find candidate invoices with scores (same customer or close amount)
                candidates_with_scores = self._find_candidates(bank, open_invoices)
                candidate_invoices = [
                    CandidateInvoice(invoice=inv, score=score)
                    for inv, score in candidates_with_scores
                ]
                result.manual_items.append(
                    ManualItem(
                        bank_id=bank.id,
                        amount=bank.amount,
                        reason="No confident match found",
                        candidate_invoices=candidate_invoices,
                    )
                )

        return result

    def _build_customer_index(
        self, invoices: List[Invoice]
    ) -> Dict[str, List[Invoice]]:
        """Build index of invoices by customer ID."""
        index: Dict[str, List[Invoice]] = {}
        for inv in invoices:
            if inv.customer_id not in index:
                index[inv.customer_id] = []
            index[inv.customer_id].append(inv)
        return index

    def _build_amount_index(
        self, invoices: List[Invoice]
    ) -> Dict[Decimal, List[Invoice]]:
        """Build index of invoices by pending amount."""
        index: Dict[Decimal, List[Invoice]] = {}
        for inv in invoices:
            # Round to 2 decimal places for grouping
            rounded = inv.pending_amount.quantize(Decimal("0.01"))
            if rounded not in index:
                index[rounded] = []
            index[rounded].append(inv)
        return index

    def _check_single_invoice(
        self,
        bank: BankTransaction,
        invoices_by_customer: Dict[str, List[Invoice]],
    ) -> Optional[Suggestion]:
        """Check if customer has only one open invoice.

        95% confidence if customer ID matches and has exactly one invoice.
        """
        if not bank.customer_id:
            return None

        customer_invoices = invoices_by_customer.get(bank.customer_id, [])

        if len(customer_invoices) != 1:
            return None

        invoice = customer_invoices[0]

        # Verify amount is reasonable
        if not amounts_match(
            bank.amount,
            invoice.pending_amount,
            self.config.amount_tolerance_percent * 10,  # More lenient
            self.config.amount_tolerance_absolute * 5,
        ):
            return None

        confidence = 0.95
        alloc_amount = min(bank.amount, invoice.pending_amount)
        remaining = invoice.pending_amount - alloc_amount

        return Suggestion(
            bank_id=bank.id,
            allocations=[
                InvoiceAllocation(
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    amount=alloc_amount,
                    is_partial=remaining > Decimal("0"),
                    remaining_after=max(remaining, Decimal("0")),
                )
            ],
            suggestion_type=SuggestionType.SINGLE_INVOICE,
            confidence=confidence,
            tier=self._get_confidence_tier(confidence),
            explanation=f"Customer {bank.customer_id} has only one open invoice",
        )

    def _check_unique_amount(
        self,
        bank: BankTransaction,
        invoice_by_amount: Dict[Decimal, List[Invoice]],
        all_invoices: List[Invoice],
    ) -> Optional[Suggestion]:
        """Check if amount uniquely matches one invoice.

        90% confidence if amount matches exactly one invoice.
        Only matches invoices with compatible customer IDs.
        """
        rounded_amount = bank.amount.quantize(Decimal("0.01"))

        # Check for exact match
        matching = invoice_by_amount.get(rounded_amount, [])

        # Also check within tolerance
        if not matching:
            for amount, invs in invoice_by_amount.items():
                if amounts_match(
                    bank.amount,
                    amount,
                    self.config.amount_tolerance_percent,
                    self.config.amount_tolerance_absolute,
                ):
                    matching.extend(invs)

        # Filter to only compatible customers (same or unknown)
        matching = [
            inv for inv in matching
            if self._customers_compatible(bank.customer_id, inv.customer_id)
        ]

        if len(matching) != 1:
            return None

        invoice = matching[0]
        confidence = 0.90

        # Boost confidence if customer matches
        if bank.customer_id and invoice.customer_id == bank.customer_id:
            confidence = 0.93

        return Suggestion(
            bank_id=bank.id,
            allocations=[
                InvoiceAllocation(
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    amount=invoice.pending_amount,
                    is_partial=False,
                    remaining_after=Decimal("0"),
                )
            ],
            suggestion_type=SuggestionType.UNIQUE_AMOUNT,
            confidence=confidence,
            tier=self._get_confidence_tier(confidence),
            explanation=f"Amount {bank.amount} uniquely matches invoice {invoice.invoice_number}",
        )

    def _check_unique_combination(
        self,
        bank: BankTransaction,
        invoices: List[Invoice],
    ) -> Optional[Suggestion]:
        """Check if amount matches a unique combination of invoices.

        85% confidence if amount matches exactly one combination.
        Only considers invoices with compatible customer IDs.
        """
        # Filter to only compatible customers (same or unknown)
        candidate_invoices = [
            inv for inv in invoices
            if self._customers_compatible(bank.customer_id, inv.customer_id)
        ]

        if not candidate_invoices:
            return None

        # Limit search space
        if len(candidate_invoices) > 15:
            # Sort by amount and take closest
            sorted_invs = sorted(
                candidate_invoices,
                key=lambda i: abs(i.pending_amount - bank.amount),
            )
            candidate_invoices = sorted_invs[:15]

        # Find all combinations that match
        matching_combos = self._find_matching_combinations(
            bank.amount, candidate_invoices
        )

        if len(matching_combos) != 1:
            return None

        combo = matching_combos[0]
        confidence = 0.85

        # Boost if customer matches
        if bank.customer_id and all(
            inv.customer_id == bank.customer_id for inv in combo
        ):
            confidence = 0.88

        allocations = [
            InvoiceAllocation(
                invoice_id=inv.id,
                invoice_number=inv.invoice_number,
                amount=inv.pending_amount,
                is_partial=False,
                remaining_after=Decimal("0"),
            )
            for inv in combo
        ]

        return Suggestion(
            bank_id=bank.id,
            allocations=allocations,
            suggestion_type=SuggestionType.UNIQUE_COMBINATION,
            confidence=confidence,
            tier=self._get_confidence_tier(confidence),
            explanation=f"Amount {bank.amount} uniquely matches {len(combo)} invoices",
        )

    def _find_matching_combinations(
        self, target: Decimal, invoices: List[Invoice], max_size: int = 4
    ) -> List[List[Invoice]]:
        """Find all invoice combinations that sum to target.

        Args:
            target: Target amount.
            invoices: Available invoices.
            max_size: Maximum combination size.

        Returns:
            List of matching combinations.
        """
        matches: List[List[Invoice]] = []

        def search(
            idx: int, current: List[Invoice], current_sum: Decimal
        ) -> None:
            # Check if current combination matches
            if amounts_match(
                current_sum,
                target,
                self.config.amount_tolerance_percent,
                self.config.amount_tolerance_absolute,
            ):
                if current:  # Don't add empty combinations
                    matches.append(current.copy())
                    if len(matches) >= 5:  # Limit results
                        return

            # Pruning
            if len(current) >= max_size:
                return
            if idx >= len(invoices):
                return
            if len(matches) >= 5:
                return

            # Try including current invoice
            inv = invoices[idx]
            current.append(inv)
            search(idx + 1, current, current_sum + inv.pending_amount)
            current.pop()

            # Try excluding current invoice
            search(idx + 1, current, current_sum)

        search(0, [], Decimal("0"))
        return matches

    def _run_flow_matching(
        self,
        banks: List[BankTransaction],
        invoices: List[Invoice],
    ) -> Tuple[List[Suggestion], List[ManualItem]]:
        """Run flow network matching for remaining items.

        Args:
            banks: Unmatched bank transactions.
            invoices: Available invoices.

        Returns:
            Tuple of (suggestions, manual_items).
        """
        suggestions: List[Suggestion] = []
        manual_items: List[ManualItem] = []

        # Build input for flow network
        bank_amounts = {b.id: b.amount for b in banks}
        invoice_amounts = {inv.id: inv.pending_amount for inv in invoices}

        # Build edge confidences
        edge_confidences = self._calculate_edge_confidences(banks, invoices)

        # Build and solve flow network (using NetworkX)
        network = build_reconciliation_network(
            bank_amounts,
            invoice_amounts,
            edge_confidences,
            self.config.reject_penalty,
        )

        assignments = solve_flow_network(network)

        # Convert assignments to suggestions
        invoice_by_id = {inv.id: inv for inv in invoices}

        for bank_id, allocs in assignments.items():
            if not allocs:
                continue

            # Filter out reject edges and low-confidence matches
            valid_allocs = [
                (inv_id, amount, cost)
                for inv_id, amount, cost in allocs
                if inv_id in invoice_by_id and cost < self.config.reject_penalty
            ]

            if not valid_allocs:
                continue

            # Calculate overall confidence
            total_amount = sum(a[1] for a in valid_allocs)
            weighted_confidence = sum(
                float(a[1]) * (1.0 - a[2]) for a in valid_allocs
            ) / float(total_amount) if total_amount else 0.0

            if weighted_confidence < self.config.min_suggestion_confidence:
                continue

            allocations = [
                InvoiceAllocation(
                    invoice_id=inv_id,
                    invoice_number=invoice_by_id[inv_id].invoice_number,
                    amount=amount,
                    is_partial=amount < invoice_by_id[inv_id].pending_amount,
                    remaining_after=invoice_by_id[inv_id].pending_amount - amount,
                )
                for inv_id, amount, _ in valid_allocs
            ]

            suggestions.append(
                Suggestion(
                    bank_id=bank_id,
                    allocations=allocations,
                    suggestion_type=SuggestionType.FLOW_MATCH,
                    confidence=weighted_confidence,
                    tier=self._get_confidence_tier(weighted_confidence),
                    explanation=f"Flow network match with {len(allocations)} invoice(s)",
                )
            )

        return suggestions, manual_items

    def _calculate_edge_confidences(
        self,
        banks: List[BankTransaction],
        invoices: List[Invoice],
    ) -> Dict[Tuple[str, str], float]:
        """Calculate confidence scores for bank-invoice edges.

        Confidence based on:
        - Customer match: +0.3
        - Amount proximity: +0.4
        - Base: 0.1

        Excludes edges where customer IDs are known but different.

        Args:
            banks: Bank transactions.
            invoices: Invoices.

        Returns:
            Dict of (bank_id, invoice_id) -> confidence.
        """
        confidences: Dict[Tuple[str, str], float] = {}

        for bank in banks:
            for invoice in invoices:
                # Skip if customers are known but different
                if not self._customers_compatible(bank.customer_id, invoice.customer_id):
                    continue

                confidence = 0.1  # Base confidence

                # Customer match bonus
                if bank.customer_id and bank.customer_id == invoice.customer_id:
                    confidence += 0.3

                # Amount proximity
                if bank.amount == invoice.pending_amount:
                    confidence += 0.4
                elif amounts_match(
                    bank.amount,
                    invoice.pending_amount,
                    self.config.amount_tolerance_percent,
                    self.config.amount_tolerance_absolute,
                ):
                    confidence += 0.3
                elif amounts_match(
                    bank.amount,
                    invoice.pending_amount,
                    self.config.amount_tolerance_percent * 5,
                    self.config.amount_tolerance_absolute * 5,
                ):
                    confidence += 0.15

                # Amount within invoice bounds (partial payment possible)
                if bank.amount <= invoice.pending_amount:
                    confidence += 0.1

                # Only include edges above minimum threshold
                if confidence >= self.config.min_flow_edge_confidence:
                    confidences[(bank.id, invoice.id)] = min(confidence, 1.0)

        return confidences

    def _find_candidates(
        self,
        bank: BankTransaction,
        invoices: List[Invoice],
        max_candidates: int = 5,
    ) -> List[Tuple[Invoice, float]]:
        """Find candidate invoices for manual matching with relevance scores.

        Args:
            bank: Bank transaction.
            invoices: Available invoices.
            max_candidates: Maximum candidates to return.

        Returns:
            List of (invoice, score) tuples, sorted by relevance.
            Score is normalized to 0-100 scale.
        """
        scored: List[Tuple[float, Invoice]] = []

        for invoice in invoices:
            score = 0.0

            # Customer match (+50)
            if bank.customer_id and bank.customer_id == invoice.customer_id:
                score += 50.0

            # Amount proximity (+30 max)
            diff = abs(bank.amount - invoice.pending_amount)
            max_amount = max(bank.amount, invoice.pending_amount)
            if max_amount > Decimal("0"):
                pct_diff = float(diff / max_amount)
                score += max(0, 30.0 * (1.0 - pct_diff))

            # Exact amount match bonus (+20)
            if bank.amount == invoice.pending_amount:
                score += 20.0

            scored.append((score, invoice))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Return tuples of (invoice, score) normalized to 0-100
        return [(inv, min(score, 100.0)) for score, inv in scored[:max_candidates]]

    def _get_confidence_tier(self, confidence: float) -> ConfidenceTier:
        """Determine confidence tier from score.

        Args:
            confidence: Confidence score (0-1).

        Returns:
            ConfidenceTier enum value.
        """
        if confidence >= self.config.high_confidence_threshold:
            return ConfidenceTier.HIGH
        elif confidence >= self.config.medium_confidence_threshold:
            return ConfidenceTier.MEDIUM
        else:
            return ConfidenceTier.LOW
