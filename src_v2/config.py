"""Configuration for the reconciliation engine."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ReconciliationConfig:
    """Configuration parameters for the reconciliation algorithm."""

    # Amount matching tolerances
    amount_tolerance_percent: float = 0.5  # 0.5% tolerance
    amount_tolerance_absolute: Decimal = Decimal("10")  # $10 absolute tolerance

    # Date matching
    date_tolerance_days: int = 14  # Days allowed between bank and remittance dates

    # Orphan handling
    orphan_grace_period_days: int = 5  # Days to wait before marking as orphan

    # Suggestion thresholds
    min_suggestion_confidence: float = 0.50  # Minimum confidence for suggestions
    min_flow_edge_confidence: float = 0.40  # Minimum confidence for flow edges

    # Flow network parameters
    reject_penalty: float = 0.80  # Penalty for rejecting a match
    amount_match_tolerance: float = 0.02  # 2% tolerance for amount matching

    # Confidence thresholds for tiers
    high_confidence_threshold: float = 0.85
    medium_confidence_threshold: float = 0.65

    def __post_init__(self) -> None:
        """Ensure Decimal types."""
        if not isinstance(self.amount_tolerance_absolute, Decimal):
            self.amount_tolerance_absolute = Decimal(
                str(self.amount_tolerance_absolute)
            )

    def get_amount_tolerance(self, amount: Decimal) -> Decimal:
        """Calculate the allowed tolerance for a given amount.

        Uses the larger of percentage-based or absolute tolerance.
        """
        percent_tolerance = amount * Decimal(str(self.amount_tolerance_percent / 100))
        return max(percent_tolerance, self.amount_tolerance_absolute)
