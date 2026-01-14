"""
Normalization functions for reference matching - Phase 1

Handles variations like:
- Leading zeros: "00012345" → "12345"
- Prefixes: "PAY-12345" → "12345"
- Spaces/dashes: "PAY 123-45" → "PAY12345"
"""
import re
from typing import Optional


def normalize_reference(ref: Optional[str]) -> str:
    """
    Normalize a payment/transaction reference for matching.

    Transformations:
    1. Convert to uppercase
    2. Remove spaces, dashes, underscores
    3. Strip leading zeros from numeric portions
    4. Remove common prefixes for comparison
    """
    if not ref:
        return ""

    # Uppercase and strip whitespace
    normalized = ref.upper().strip()

    # Remove common separators
    normalized = re.sub(r'[\s\-_]+', '', normalized)

    return normalized


def normalize_reference_aggressive(ref: Optional[str]) -> str:
    """
    More aggressive normalization - extracts just the numeric/alphanumeric core.

    Used for fuzzy matching when exact match fails.
    """
    if not ref:
        return ""

    normalized = normalize_reference(ref)

    # Remove common prefixes (sorted by length desc to match longer first)
    prefixes = [
        'PAYMENT', 'TRANSFER', 'PAY', 'REF', 'TXN', 'INV', 'PMT',
        'ACH', 'CHK', 'WIR', 'BT', 'AC',  # Common short prefixes
    ]
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break

    # Strip leading zeros from pure numeric strings
    if normalized.isdigit():
        normalized = normalized.lstrip('0') or '0'

    return normalized


def extract_numeric_part(ref: Optional[str]) -> str:
    """Extract just the numeric portion of a reference."""
    if not ref:
        return ""

    numbers = re.findall(r'\d+', ref)
    if numbers:
        # Return the longest numeric sequence, stripped of leading zeros
        longest = max(numbers, key=len)
        return longest.lstrip('0') or '0'
    return ""


def normalize_invoice_id(invoice_id: Optional[str]) -> str:
    """
    Normalize an invoice ID for matching.

    Handles:
    - INV-2024-001 vs INV2024001
    - Invoice #123 vs INV-123
    - Leading zeros in invoice numbers
    """
    if not invoice_id:
        return ""

    normalized = invoice_id.upper().strip()

    # Remove common invoice prefixes and separators
    normalized = re.sub(r'^(INVOICE\s*#?\s*|INV[-:#\s]*)', '', normalized)

    # Remove remaining separators
    normalized = re.sub(r'[\s\-_#:]+', '', normalized)

    # Strip leading zeros if purely numeric
    if normalized.isdigit():
        normalized = normalized.lstrip('0') or '0'

    return normalized


def normalize_customer_name(name: Optional[str]) -> str:
    """
    Normalize a customer name for matching.

    Handles:
    - Case differences
    - Common suffixes (Corp, Corporation, Inc, LLC, Ltd)
    - Extra whitespace
    """
    if not name:
        return ""

    normalized = name.upper().strip()

    # Collapse multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized)

    # Remove common legal suffixes for comparison
    suffixes = [
        r'\s+CORPORATION$', r'\s+CORP\.?$', r'\s+INC\.?$',
        r'\s+LLC\.?$', r'\s+LTD\.?$', r'\s+LIMITED$',
        r'\s+CO\.?$', r'\s+COMPANY$', r'\s+PLC\.?$'
    ]
    for suffix in suffixes:
        normalized = re.sub(suffix, '', normalized)

    return normalized.strip()


def references_match(ref1: Optional[str], ref2: Optional[str], strict: bool = True) -> bool:
    """
    Check if two references match.

    Args:
        ref1: First reference
        ref2: Second reference
        strict: If True, use basic normalization. If False, use aggressive normalization.

    Returns:
        True if references match after normalization
    """
    if not ref1 or not ref2:
        return False

    if strict:
        return normalize_reference(ref1) == normalize_reference(ref2)
    else:
        return normalize_reference_aggressive(ref1) == normalize_reference_aggressive(ref2)


def invoice_ids_match(inv1: Optional[str], inv2: Optional[str]) -> bool:
    """Check if two invoice IDs match after normalization."""
    if not inv1 or not inv2:
        return False

    return normalize_invoice_id(inv1) == normalize_invoice_id(inv2)


def description_contains_reference(description: str, reference: str) -> bool:
    """
    Check if a bank description contains a reference.

    Handles partial matches and normalized comparison.
    """
    if not description or not reference:
        return False

    desc_normalized = normalize_reference(description)
    ref_normalized = normalize_reference(reference)

    # Direct containment check
    if ref_normalized in desc_normalized:
        return True

    # Try aggressive normalization
    ref_aggressive = normalize_reference_aggressive(reference)
    if len(ref_aggressive) >= 4 and ref_aggressive in desc_normalized:
        return True

    # Try numeric extraction
    ref_numeric = extract_numeric_part(reference)
    if len(ref_numeric) >= 4 and ref_numeric in description:
        return True

    return False
