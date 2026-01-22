"""Validation utilities for reconciliation."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Tuple


def amounts_match(
    amount1: Decimal,
    amount2: Decimal,
    tolerance_percent: float = 0.5,
    tolerance_absolute: Decimal = Decimal("10"),
) -> bool:
    """Check if two amounts match within tolerance.

    Uses the larger of percentage-based or absolute tolerance.

    Args:
        amount1: First amount.
        amount2: Second amount.
        tolerance_percent: Percentage tolerance (default 0.5%).
        tolerance_absolute: Absolute tolerance (default $10).

    Returns:
        True if amounts match within tolerance.
    """
    if not isinstance(amount1, Decimal):
        amount1 = Decimal(str(amount1))
    if not isinstance(amount2, Decimal):
        amount2 = Decimal(str(amount2))

    difference = abs(amount1 - amount2)

    # Calculate percentage-based tolerance using the larger amount
    max_amount = max(abs(amount1), abs(amount2))
    percent_tolerance = max_amount * Decimal(str(tolerance_percent / 100))

    # Use the larger of the two tolerances
    effective_tolerance = max(percent_tolerance, tolerance_absolute)

    return difference <= effective_tolerance


def calculate_amount_difference(
    amount1: Decimal, amount2: Decimal
) -> Tuple[Decimal, float]:
    """Calculate the difference between two amounts.

    Args:
        amount1: First amount.
        amount2: Second amount.

    Returns:
        Tuple of (absolute difference, percentage difference).
    """
    if not isinstance(amount1, Decimal):
        amount1 = Decimal(str(amount1))
    if not isinstance(amount2, Decimal):
        amount2 = Decimal(str(amount2))

    abs_diff = abs(amount1 - amount2)

    # Calculate percentage based on the larger amount
    max_amount = max(abs(amount1), abs(amount2))
    if max_amount == Decimal("0"):
        pct_diff = 0.0
    else:
        pct_diff = float(abs_diff / max_amount * 100)

    return abs_diff, pct_diff


def dates_within_tolerance(
    date1: date, date2: date, tolerance_days: int = 14
) -> bool:
    """Check if two dates are within the specified tolerance.

    Args:
        date1: First date.
        date2: Second date.
        tolerance_days: Maximum allowed difference in days.

    Returns:
        True if dates are within tolerance.
    """
    difference = abs((date1 - date2).days)
    return difference <= tolerance_days


def calculate_date_difference(date1: date, date2: date) -> int:
    """Calculate the difference between two dates in days.

    Args:
        date1: First date.
        date2: Second date.

    Returns:
        Difference in days (can be negative if date2 > date1).
    """
    return (date1 - date2).days


def is_within_grace_period(
    transaction_date: date, current_date: date, grace_days: int = 5
) -> bool:
    """Check if a transaction is within the grace period.

    Used for orphan detection - transactions within grace period
    may still have matching counterparts arriving.

    Args:
        transaction_date: Date of the transaction.
        current_date: Current/processing date.
        grace_days: Number of grace days.

    Returns:
        True if within grace period.
    """
    cutoff_date = current_date - timedelta(days=grace_days)
    return transaction_date >= cutoff_date


def amount_allows_overpayment(
    payment_amount: Decimal, invoice_amount: Decimal, max_overpayment_percent: float = 5.0
) -> bool:
    """Check if payment amount is a reasonable overpayment.

    Sometimes customers slightly overpay. This checks if the overpayment
    is within acceptable bounds.

    Args:
        payment_amount: Amount paid.
        invoice_amount: Invoice amount.
        max_overpayment_percent: Maximum allowed overpayment percentage.

    Returns:
        True if overpayment is acceptable.
    """
    if not isinstance(payment_amount, Decimal):
        payment_amount = Decimal(str(payment_amount))
    if not isinstance(invoice_amount, Decimal):
        invoice_amount = Decimal(str(invoice_amount))

    if payment_amount <= invoice_amount:
        return True  # Not an overpayment

    if invoice_amount == Decimal("0"):
        return False  # Can't overpay a zero invoice

    overpayment_pct = float((payment_amount - invoice_amount) / invoice_amount * 100)
    return overpayment_pct <= max_overpayment_percent
