"""
Level 1 Matching: Bank Transaction ↔ Remittance (1:1 relationship)

Phase 1 Deterministic Rules:
- Rule 1.1: Exact Reference + Exact Amount (100% confidence)
- Rule 1.2: Exact Reference + Amount Tolerance (95% confidence)
- Rule 1.3: Fuzzy Reference + Exact Amount (85% confidence)
- Rule 1.5: Description Contains Reference + Exact Amount (75% confidence)
- Virtual: Bank description parsed to create virtual remittance (70% confidence)

Exceptions:
- E007: Orphan bank txn - no matching remittance found
- E008: Duplicate remittance match - bank txn already MATCHED
"""
from decimal import Decimal
from typing import Optional

from models import (
    BankTransaction,
    BankTransactionStatus,
    Customer,
    Remittance,
    RemittanceStatus,
    MatchResult,
    MatchOutcome,
    Level1Match,
    ExceptionCode,
)
from normalizers import (
    normalize_reference,
    references_match,
    description_contains_reference,
)
from bank_parser import parse_bank_description, is_description_parseable


# Configuration
AMOUNT_TOLERANCE = Decimal("0.99")


def match_bank_to_remittance(
    bank_txn: BankTransaction,
    remittances: list[Remittance],
    customers: Optional[list[Customer]] = None,
) -> tuple[Level1Match, Optional[Remittance]]:
    """
    Match a bank transaction to a remittance using deterministic rules.

    1:1 relationship - one bank transaction matches exactly one remittance.

    Applies rules in order of confidence:
    1. Rule 1.1: Exact Reference + Exact Amount
    2. Rule 1.2: Exact Reference + Amount Tolerance
    3. Rule 1.3: Fuzzy Reference + Exact Amount
    4. Rule 1.5: Description Contains Reference + Exact Amount
    5. Virtual: Parse bank description to create virtual remittance

    Args:
        bank_txn: Bank transaction to match
        remittances: List of actual remittances to match against
        customers: Optional list of customers for virtual remittance creation

    Returns:
        Tuple of (Level1Match result, Optional virtual Remittance if created)
    """
    # Check E008: Bank transaction already matched
    if bank_txn.status == BankTransactionStatus.MATCHED:
        return Level1Match(
            bank_transaction_id=bank_txn.id,
            remittance_id=None,
            result=MatchResult(
                outcome=MatchOutcome.EXCEPTION,
                confidence=0,
                rule_applied="Duplicate Check",
                source_id=bank_txn.id,
                target_id=None,
                exception_code=ExceptionCode.E008,
                exception_detail=f"Bank txn already matched to remittance {bank_txn.matched_remittance_id}",
            )
        ), None

    # Filter to only OPEN remittances (not already matched)
    available_remittances = [r for r in remittances if r.status == RemittanceStatus.OPEN]

    # Try each rule in order of confidence
    for rule_fn in [
        _try_rule_1_1,
        _try_rule_1_2,
        _try_rule_1_3,
        _try_rule_1_5,
    ]:
        result = rule_fn(bank_txn, available_remittances)
        if result:
            return result, None

    # Try virtual remittance creation if customers provided
    if customers and is_description_parseable(bank_txn.description):
        virtual_remittance = parse_bank_description(bank_txn, customers)
        if virtual_remittance:
            return Level1Match(
                bank_transaction_id=bank_txn.id,
                remittance_id=virtual_remittance.id,
                result=MatchResult(
                    outcome=MatchOutcome.AUTO_MATCHED,
                    confidence=70,
                    rule_applied="Virtual: Bank Description Parsed",
                    source_id=bank_txn.id,
                    target_id=virtual_remittance.id,
                    exception_detail="Created virtual remittance from bank description",
                )
            ), virtual_remittance

    # No match found - just unmatched (not an exception)
    return Level1Match(
        bank_transaction_id=bank_txn.id,
        remittance_id=None,
        result=MatchResult(
            outcome=MatchOutcome.UNMATCHED,
            confidence=0,
            rule_applied="None",
            source_id=bank_txn.id,
            target_id=None,
        )
    ), None


def _try_rule_1_1(
    bank_txn: BankTransaction,
    remittances: list[Remittance]
) -> Optional[Level1Match]:
    """
    Rule 1.1: Exact Reference + Exact Amount (100% confidence)

    IF bank.reference = remittance.reference
    AND bank.amount = remittance.total_amount
    → AUTO-MATCH
    """
    bank_ref_normalized = normalize_reference(bank_txn.reference)

    for remittance in remittances:
        rem_ref_normalized = normalize_reference(remittance.payment_reference)

        if bank_ref_normalized == rem_ref_normalized:
            if bank_txn.amount == remittance.total_amount:
                return Level1Match(
                    bank_transaction_id=bank_txn.id,
                    remittance_id=remittance.id,
                    result=MatchResult(
                        outcome=MatchOutcome.AUTO_MATCHED,
                        confidence=100,
                        rule_applied="1.1: Exact Reference + Exact Amount",
                        source_id=bank_txn.id,
                        target_id=remittance.id,
                    )
                )
    return None


def _try_rule_1_2(
    bank_txn: BankTransaction,
    remittances: list[Remittance]
) -> Optional[Level1Match]:
    """
    Rule 1.2: Exact Reference + Amount Tolerance (95% confidence)

    IF bank.reference = remittance.reference
    AND ABS(bank.amount - remittance.total_amount) <= $0.99
    → AUTO-MATCH (flag for review if tolerance used)
    """
    bank_ref_normalized = normalize_reference(bank_txn.reference)

    for remittance in remittances:
        rem_ref_normalized = normalize_reference(remittance.payment_reference)

        if bank_ref_normalized == rem_ref_normalized:
            amount_diff = abs(bank_txn.amount - remittance.total_amount)
            if amount_diff <= AMOUNT_TOLERANCE and amount_diff > 0:
                return Level1Match(
                    bank_transaction_id=bank_txn.id,
                    remittance_id=remittance.id,
                    result=MatchResult(
                        outcome=MatchOutcome.AUTO_MATCHED,
                        confidence=95,
                        rule_applied="1.2: Exact Reference + Amount Tolerance",
                        source_id=bank_txn.id,
                        target_id=remittance.id,
                        exception_detail=f"Amount difference: ${amount_diff}",
                    )
                )
    return None


def _try_rule_1_3(
    bank_txn: BankTransaction,
    remittances: list[Remittance]
) -> Optional[Level1Match]:
    """
    Rule 1.3: Fuzzy Reference + Exact Amount (85% confidence)

    IF normalize(bank.reference) = normalize(remittance.reference)
    AND bank.amount = remittance.total_amount
    → AUTO-MATCH

    Uses aggressive normalization to handle:
    - Leading zeros: "00012345" → "12345"
    - Prefixes: "PAY-12345" → "12345"
    - Spaces/dashes: "PAY 123-45" → "PAY12345"
    """
    for remittance in remittances:
        # Use non-strict (aggressive) matching
        if references_match(bank_txn.reference, remittance.payment_reference, strict=False):
            if bank_txn.amount == remittance.total_amount:
                return Level1Match(
                    bank_transaction_id=bank_txn.id,
                    remittance_id=remittance.id,
                    result=MatchResult(
                        outcome=MatchOutcome.AUTO_MATCHED,
                        confidence=85,
                        rule_applied="1.3: Fuzzy Reference + Exact Amount",
                        source_id=bank_txn.id,
                        target_id=remittance.id,
                    )
                )
    return None


def _try_rule_1_5(
    bank_txn: BankTransaction,
    remittances: list[Remittance]
) -> Optional[Level1Match]:
    """
    Rule 1.5: Description Contains Reference + Exact Amount (75% confidence)

    IF bank.description CONTAINS remittance.reference
    AND bank.amount = remittance.total_amount
    → AUTO-MATCH (only if exactly one candidate)
    """
    matches = []

    for remittance in remittances:
        if description_contains_reference(bank_txn.description, remittance.payment_reference):
            if bank_txn.amount == remittance.total_amount:
                matches.append(remittance)

    # Only auto-match if exactly one candidate
    # Multiple matches = ambiguous, skip this rule (try virtual remittance next)
    if len(matches) == 1:
        remittance = matches[0]
        return Level1Match(
            bank_transaction_id=bank_txn.id,
            remittance_id=remittance.id,
            result=MatchResult(
                outcome=MatchOutcome.AUTO_MATCHED,
                confidence=75,
                rule_applied="1.5: Description Contains Reference",
                source_id=bank_txn.id,
                target_id=remittance.id,
            )
        )

    return None


def match_all_bank_transactions(
    bank_transactions: list[BankTransaction],
    remittances: list[Remittance],
    customers: Optional[list[Customer]] = None,
) -> tuple[list[Level1Match], list[Remittance]]:
    """
    Match all bank transactions to remittances.

    Args:
        bank_transactions: List of bank transactions to match
        remittances: List of actual remittances
        customers: Optional list of customers for virtual remittance creation

    Returns:
        Tuple of (list of Level1Match results, list of virtual remittances created)
    """
    results = []
    virtual_remittances = []
    matched_remittance_ids = set()

    for bank_txn in bank_transactions:
        # Filter out already-matched remittances
        available_remittances = [
            r for r in remittances if r.id not in matched_remittance_ids
        ]

        match, virtual_rem = match_bank_to_remittance(bank_txn, available_remittances, customers)
        results.append(match)

        if match.remittance_id:
            matched_remittance_ids.add(match.remittance_id)

        if virtual_rem:
            virtual_remittances.append(virtual_rem)

    return results, virtual_remittances


def apply_level1_match(
    match: Level1Match,
    bank_txn: BankTransaction,
    remittance: Optional[Remittance],
) -> None:
    """
    Apply a Level 1 match result to the entities.

    Updates status and matched IDs on both bank transaction and remittance.

    Args:
        match: The Level1Match result
        bank_txn: The bank transaction entity to update
        remittance: The remittance entity to update (can be None if no match)
    """
    if match.result.outcome == MatchOutcome.AUTO_MATCHED and remittance:
        # Update bank transaction
        bank_txn.status = BankTransactionStatus.MATCHED
        bank_txn.matched_remittance_id = remittance.id

        # Update remittance
        remittance.status = RemittanceStatus.MATCHED
        remittance.matched_bank_transaction_id = bank_txn.id
