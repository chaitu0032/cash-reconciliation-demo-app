"""
Cash Reconciliation Orchestrator - Phase 1

Coordinates the full reconciliation flow:
Bank Transaction → Remittance → Invoice(s)

Entity Relationships:
- Bank Transaction ↔ Remittance: 1:1 (bidirectional link)
- Remittance Line Item → Invoice: N:1 (multiple lines can pay one invoice)

Uses deterministic matching rules with high confidence (≥75%).
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from models import (
    BankTransaction,
    BankTransactionStatus,
    Remittance,
    RemittanceStatus,
    Invoice,
    InvoiceStatus,
    Customer,
    MatchOutcome,
    ExceptionCode,
    ReconciliationResult,
    Level1Match,
    Level2Match,
    RemittanceLineRef,
    InvoiceReconciliationStatus,
)
from level1_matcher import match_bank_to_remittance, apply_level1_match
from level2_matcher import match_remittance_to_invoices


@dataclass
class ReconciliationSummary:
    """Summary statistics for a reconciliation run"""
    total_bank_transactions: int = 0
    total_remittances: int = 0
    total_invoices: int = 0

    # Level 1 stats
    level1_auto_matched: int = 0
    level1_auto_matched_virtual: int = 0  # Virtual remittance matches
    level1_exceptions: int = 0
    level1_unmatched: int = 0

    # Level 2 stats
    level2_auto_matched: int = 0
    level2_exceptions: int = 0
    level2_unmatched: int = 0

    # Exception breakdown
    exceptions_by_code: dict[str, int] = field(default_factory=dict)

    # Fully reconciled (bank → remittance → all invoices matched)
    fully_reconciled: int = 0

    @property
    def level1_match_rate(self) -> float:
        if self.total_bank_transactions == 0:
            return 0.0
        total_matched = self.level1_auto_matched + self.level1_auto_matched_virtual
        return total_matched / self.total_bank_transactions * 100

    @property
    def full_reconciliation_rate(self) -> float:
        if self.total_bank_transactions == 0:
            return 0.0
        return self.fully_reconciled / self.total_bank_transactions * 100


class Reconciler:
    """
    Main reconciliation engine for Phase 1.

    Implements deterministic matching with high-confidence rules.
    """

    def __init__(
        self,
        bank_transactions: list[BankTransaction],
        remittances: list[Remittance],
        invoices: list[Invoice],
        customers: list[Customer],
    ):
        self.bank_transactions = bank_transactions
        self.remittances = remittances
        self.invoices = invoices
        self.customers = customers

        # Index customers by ID for quick lookup
        self.customer_map = {c.customer_id: c for c in customers}

        # Results
        self.results: list[ReconciliationResult] = []
        self.virtual_remittances: list[Remittance] = []  # Track virtual remittances
        self.summary = ReconciliationSummary()

    def run(self) -> list[ReconciliationResult]:
        """
        Execute the full reconciliation process.

        Returns list of ReconciliationResult for each bank transaction.
        """
        self.summary = ReconciliationSummary(
            total_bank_transactions=len(self.bank_transactions),
            total_remittances=len(self.remittances),
            total_invoices=len(self.invoices),
        )

        matched_remittance_ids = set()

        for bank_txn in self.bank_transactions:
            result = self._reconcile_bank_transaction(
                bank_txn,
                matched_remittance_ids,
            )
            self.results.append(result)

            # Track matched remittances to avoid double-matching
            if result.level1_match and result.level1_match.remittance_id:
                matched_remittance_ids.add(result.level1_match.remittance_id)

        # Final pass: Reset status to Open for invoices with exceptions
        # Invoices with exceptions need manual review and should not be closed
        self._reset_exception_invoice_statuses()

        return self.results

    def _reset_exception_invoice_statuses(self) -> None:
        """
        Reset status to Open for invoices that have exceptions.

        Invoices with E002 (Overpayment), E004 (Duplicate Payment) etc.
        should remain Open for manual review, not auto-closed.
        """
        # Collect all invoice IDs with exceptions
        invoices_with_exceptions = set()
        for result in self.results:
            for l2_match in result.level2_matches:
                if l2_match.result.exception_code and l2_match.invoice_id:
                    invoices_with_exceptions.add(l2_match.invoice_id)

        # Reset their status to Open and restore pending amount
        invoice_map = {inv.invoice_id: inv for inv in self.invoices}
        for inv_id in invoices_with_exceptions:
            if inv_id in invoice_map:
                invoice = invoice_map[inv_id]
                # Reset status to Open - needs manual review
                invoice.status = InvoiceStatus.OPEN
                # Reset pending amount to original (full amount)
                invoice.pending_amount = invoice.amount

    def _reconcile_bank_transaction(
        self,
        bank_txn: BankTransaction,
        matched_remittance_ids: set[str],
    ) -> ReconciliationResult:
        """
        Reconcile a single bank transaction through both levels.

        Updates entity statuses and links as matches are made.
        """
        result = ReconciliationResult(bank_transaction=bank_txn)

        # Filter available remittances (not already matched)
        available_remittances = [
            r for r in self.remittances if r.id not in matched_remittance_ids
        ]

        # Level 1: Bank → Remittance (with virtual remittance fallback)
        level1_match, virtual_remittance = match_bank_to_remittance(
            bank_txn, available_remittances, self.customers
        )
        result.level1_match = level1_match

        # Track virtual remittance if created
        if virtual_remittance:
            self.virtual_remittances.append(virtual_remittance)

        # Update Level 1 stats
        is_virtual = virtual_remittance is not None
        self._update_level1_stats(level1_match, is_virtual)

        # If Level 1 matched, apply the match and proceed to Level 2
        if level1_match.result.outcome == MatchOutcome.AUTO_MATCHED:
            # Get the matched remittance
            if virtual_remittance:
                remittance = virtual_remittance
            else:
                remittance = self._get_remittance_by_id(level1_match.remittance_id)

            if remittance:
                # Apply Level 1 match - update statuses and IDs on both sides
                apply_level1_match(level1_match, bank_txn, remittance)

                # Identify customer
                customer_id = self._identify_customer(remittance)

                if customer_id:
                    # Level 2: Remittance Line Items → Invoices
                    level2_matches = match_remittance_to_invoices(
                        remittance,
                        self.invoices,
                        customer_id,
                    )
                    result.level2_matches = level2_matches

                    # Apply Level 2 matches - update line items and invoices
                    self._apply_level2_matches(level2_matches, remittance)

                    # Update Level 2 stats
                    self._update_level2_stats(level2_matches)

                    # Check if fully reconciled
                    result.fully_reconciled = self._check_fully_reconciled(level2_matches)
                    if result.fully_reconciled:
                        self.summary.fully_reconciled += 1
                else:
                    # Customer not identified - flag exception
                    self._record_exception(ExceptionCode.E009)

        return result

    def _get_remittance_by_id(self, remittance_id: Optional[str]) -> Optional[Remittance]:
        """Look up a remittance by ID."""
        if not remittance_id:
            return None
        for r in self.remittances:
            if r.id == remittance_id:
                return r
        return None

    def _identify_customer(self, remittance: Remittance) -> Optional[str]:
        """
        Identify customer from remittance data.

        Phase 1: Uses direct customer_id if available.
        Future: Will implement fuzzy matching rules.
        """
        # Direct customer ID match
        if remittance.customer_id:
            if remittance.customer_id in self.customer_map:
                return remittance.customer_id

        # Try matching by customer name (exact match only in Phase 1)
        for customer in self.customers:
            if customer.name.upper() == remittance.customer_name.upper():
                return customer.customer_id
            # Check aliases
            for alias in customer.aliases:
                if alias.upper() == remittance.customer_name.upper():
                    return customer.customer_id

        return None

    def _update_level1_stats(self, match: Level1Match, is_virtual: bool = False) -> None:
        """Update Level 1 summary statistics."""
        if match.result.outcome == MatchOutcome.AUTO_MATCHED:
            if is_virtual:
                self.summary.level1_auto_matched_virtual += 1
            else:
                self.summary.level1_auto_matched += 1
        elif match.result.outcome == MatchOutcome.EXCEPTION:
            self.summary.level1_exceptions += 1
            self._record_exception(match.result.exception_code)
        else:
            self.summary.level1_unmatched += 1
            if match.result.exception_code:
                self._record_exception(match.result.exception_code)

    def _update_level2_stats(self, matches: list[Level2Match]) -> None:
        """Update Level 2 summary statistics."""
        for match in matches:
            if match.result.outcome == MatchOutcome.AUTO_MATCHED:
                self.summary.level2_auto_matched += 1
            elif match.result.outcome == MatchOutcome.EXCEPTION:
                self.summary.level2_exceptions += 1
                self._record_exception(match.result.exception_code)
            else:
                self.summary.level2_unmatched += 1

    def _record_exception(self, exception_code: Optional[ExceptionCode]) -> None:
        """Record an exception in the summary."""
        if exception_code:
            code = exception_code.name
            self.summary.exceptions_by_code[code] = (
                self.summary.exceptions_by_code.get(code, 0) + 1
            )

    def _check_fully_reconciled(self, level2_matches: list[Level2Match]) -> bool:
        """Check if all line items were successfully matched."""
        if not level2_matches:
            return False
        return all(
            m.result.outcome == MatchOutcome.AUTO_MATCHED
            for m in level2_matches
        )

    def _apply_level2_matches(
        self,
        matches: list[Level2Match],
        remittance: Remittance,
    ) -> None:
        """
        Apply Level 2 match results to entities.

        Updates:
        - RemittanceLineItem.matched_invoice_id
        - Invoice.matched_remittance_lines
        - Invoice.pending_amount
        - Invoice.status
        """
        # Build invoice lookup
        invoice_map = {inv.invoice_id: inv for inv in self.invoices}

        # Track cumulative payments per invoice
        cumulative_payments: dict[str, Decimal] = {}

        for match in matches:
            # Only process AUTO_MATCHED - exceptions should NOT update invoice status
            # E002 (Overpayment) and E004 (Duplicate Payment) are exceptions that need manual review
            if match.result.outcome != MatchOutcome.AUTO_MATCHED:
                continue

            if not match.invoice_id or match.invoice_id not in invoice_map:
                continue

            # Update line item
            if match.remittance_line_index < len(remittance.line_items):
                line_item = remittance.line_items[match.remittance_line_index]
                line_item.matched_invoice_id = match.invoice_id

                # Track payment amount
                payment_amount = line_item.amount
                if match.invoice_id not in cumulative_payments:
                    cumulative_payments[match.invoice_id] = Decimal("0")
                cumulative_payments[match.invoice_id] += payment_amount

                # Add reference to invoice
                invoice = invoice_map[match.invoice_id]
                invoice.matched_remittance_lines.append(
                    RemittanceLineRef(
                        remittance_id=remittance.id,
                        line_index=match.remittance_line_index,
                        amount=payment_amount,
                    )
                )

        # Update invoice pending amounts and statuses
        for inv_id, total_paid in cumulative_payments.items():
            invoice = invoice_map[inv_id]
            original_pending = invoice.pending_amount

            # Calculate new pending amount
            new_pending = max(Decimal("0"), original_pending - total_paid)

            # Update pending amount
            invoice.pending_amount = new_pending

            # Update status based on payment result
            if new_pending == Decimal("0"):
                invoice.status = InvoiceStatus.CLOSED
            elif new_pending < invoice.amount:
                invoice.status = InvoiceStatus.PARTIAL

    def get_summary(self) -> ReconciliationSummary:
        """Return the reconciliation summary."""
        return self.summary

    def print_summary(self) -> None:
        """Print a human-readable summary of the reconciliation."""
        s = self.summary
        print("\n" + "=" * 60)
        print("RECONCILIATION SUMMARY - Phase 1 (Deterministic)")
        print("=" * 60)

        print(f"\nInput Data:")
        print(f"  Bank Transactions: {s.total_bank_transactions}")
        print(f"  Remittances:       {s.total_remittances}")
        print(f"  Invoices:          {s.total_invoices}")

        total_l1_matched = s.level1_auto_matched + s.level1_auto_matched_virtual
        print(f"\nLevel 1 (Bank → Remittance):")
        print(f"  Auto-Matched (actual):  {s.level1_auto_matched}")
        print(f"  Auto-Matched (virtual): {s.level1_auto_matched_virtual}")
        print(f"  Total Matched:          {total_l1_matched} ({s.level1_match_rate:.1f}%)")
        print(f"  Exceptions:             {s.level1_exceptions}")
        print(f"  Unmatched:              {s.level1_unmatched}")

        print(f"\nLevel 2 (Remittance → Invoice):")
        print(f"  Auto-Matched: {s.level2_auto_matched}")
        print(f"  Exceptions:   {s.level2_exceptions}")
        print(f"  Unmatched:    {s.level2_unmatched}")

        print(f"\nFull Reconciliation:")
        print(f"  Fully Reconciled: {s.fully_reconciled} ({s.full_reconciliation_rate:.1f}%)")

        if s.exceptions_by_code:
            print(f"\nExceptions by Type:")
            for code, count in sorted(s.exceptions_by_code.items()):
                exc = ExceptionCode[code]
                print(f"  {code}: {exc.value} ({count})")

        print("\n" + "=" * 60)

    def get_invoice_reconciliation_statuses(self) -> list[InvoiceReconciliationStatus]:
        """
        Get invoice-centric reconciliation statuses.

        Returns a list showing each invoice with its full chain:
        Invoice ← Remittance Line ← Remittance ← Bank Transaction

        An invoice is RECONCILED only when the entire chain has no exceptions.
        """
        invoice_statuses = []

        # Build lookup maps
        remittance_map = {r.id: r for r in self.remittances + self.virtual_remittances}
        bank_txn_map = {bt.id: bt for bt in self.bank_transactions}

        # Track which Level 1/2 matches apply to each invoice
        # Structure: invoice_id -> list of (remittance_id, line_index, l2_match)
        invoice_matches: dict[str, list[tuple[str, int, Level2Match]]] = {}

        for result in self.results:
            if not result.level1_match or not result.level2_matches:
                continue

            remittance_id = result.level1_match.remittance_id
            for l2_match in result.level2_matches:
                if l2_match.invoice_id:
                    if l2_match.invoice_id not in invoice_matches:
                        invoice_matches[l2_match.invoice_id] = []
                    invoice_matches[l2_match.invoice_id].append(
                        (remittance_id, l2_match.remittance_line_index, l2_match)
                    )

        # Build status for each invoice
        for invoice in self.invoices:
            status = InvoiceReconciliationStatus(invoice=invoice)

            if invoice.invoice_id in invoice_matches:
                matches = invoice_matches[invoice.invoice_id]

                # Get matched lines
                status.matched_lines = invoice.matched_remittance_lines.copy()

                # Get remittance info (use first match for now)
                if matches:
                    rem_id, line_idx, l2_match = matches[0]
                    status.remittance_id = rem_id
                    status.remittance_match_confidence = l2_match.result.confidence

                    # Check for remittance-level exceptions
                    if l2_match.result.exception_code in [ExceptionCode.E005, ExceptionCode.E009]:
                        status.remittance_exception = l2_match.result.exception_code

                    # Check for invoice-level exceptions
                    if l2_match.result.exception_code in [ExceptionCode.E002, ExceptionCode.E004]:
                        status.invoice_exception = l2_match.result.exception_code

                    # Get remittance details and matched line reference
                    remittance = remittance_map.get(rem_id)
                    if remittance:
                        status.remittance_reference = remittance.payment_reference

                        # Get the line item reference that matched this invoice
                        if 0 <= line_idx < len(remittance.line_items):
                            status.matched_line_ref = remittance.line_items[line_idx].invoice_number

                        # Get bank transaction info
                        if remittance.matched_bank_transaction_id:
                            status.bank_transaction_id = remittance.matched_bank_transaction_id
                            bank_txn = bank_txn_map.get(remittance.matched_bank_transaction_id)

                            # Get bank reference
                            if bank_txn:
                                status.bank_reference = bank_txn.reference

                            # Get L1 match confidence
                            for result in self.results:
                                if result.bank_transaction.id == status.bank_transaction_id:
                                    if result.level1_match:
                                        status.bank_match_confidence = result.level1_match.result.confidence
                                        if result.level1_match.result.exception_code:
                                            status.bank_exception = result.level1_match.result.exception_code
                                    break

            invoice_statuses.append(status)

        return invoice_statuses

    def print_invoice_reconciliation(self) -> None:
        """Print invoice-centric reconciliation report."""
        statuses = self.get_invoice_reconciliation_statuses()

        print("\n" + "=" * 80)
        print("INVOICE RECONCILIATION STATUS")
        print("=" * 80)

        reconciled = sum(1 for s in statuses if s.is_reconciled)
        partial = sum(1 for s in statuses if s.invoice.status == InvoiceStatus.PARTIAL)
        with_exceptions = [s for s in statuses if s.invoice_exception or s.remittance_exception or s.bank_exception]

        print(f"\nSummary: {reconciled} Reconciled | {partial} Partial | {len(with_exceptions)} With Exceptions | {len(statuses)} Total")
        print("-" * 80)

        for status in statuses:
            inv = status.invoice
            print(f"\n{inv.invoice_id}: {status.reconciliation_status}")
            print(f"  Amount: ${inv.amount} | Pending: ${inv.pending_amount} | Status: {inv.status.value}")

            if status.matched_lines:
                print(f"  Matched Lines: {len(status.matched_lines)}")
                for ref in status.matched_lines:
                    print(f"    - {ref.remittance_id}[{ref.line_index}]: ${ref.amount}")

            if status.remittance_id:
                print(f"  Remittance: {status.remittance_id} (Confidence: {status.remittance_match_confidence}%)")

            if status.bank_transaction_id:
                print(f"  Bank Txn: {status.bank_transaction_id} (Confidence: {status.bank_match_confidence}%)")

        # Show exceptions by level
        print("\n" + "=" * 80)
        print("EXCEPTIONS BY LEVEL")
        print("=" * 80)

        # Document Level (Bank Transaction)
        bank_exceptions = [(s, s.bank_exception) for s in statuses if s.bank_exception]
        print(f"\n[DOCUMENT LEVEL - Bank Transaction] ({len(bank_exceptions)} exceptions)")
        if bank_exceptions:
            for status, exc in bank_exceptions:
                print(f"  {status.invoice.invoice_id} -> Bank {status.bank_transaction_id or 'N/A'}")
                print(f"    {exc.name}: {exc.value}")
        else:
            print("  None")

        # Remittance Level
        rem_exceptions = [(s, s.remittance_exception) for s in statuses if s.remittance_exception]
        print(f"\n[REMITTANCE LEVEL] ({len(rem_exceptions)} exceptions)")
        if rem_exceptions:
            for status, exc in rem_exceptions:
                print(f"  {status.invoice.invoice_id} -> Remittance {status.remittance_id or 'N/A'}")
                print(f"    {exc.name}: {exc.value}")
        else:
            print("  None")

        # Invoice Level
        inv_exceptions = [(s, s.invoice_exception) for s in statuses if s.invoice_exception]
        print(f"\n[INVOICE LEVEL] ({len(inv_exceptions)} exceptions)")
        if inv_exceptions:
            for status, exc in inv_exceptions:
                print(f"  {status.invoice.invoice_id}")
                print(f"    {exc.name}: {exc.value}")
        else:
            print("  None")

        print("\n" + "=" * 80)
