"""Extract invoice references from text."""

import re
from typing import List, Set


def extract_invoice_references(text: str) -> List[str]:
    """Extract invoice numbers from bank description or other text.

    Looks for common invoice reference patterns:
    - INV-12345, INV#12345, INV:12345
    - INVOICE 12345, Invoice: 12345
    - Bare numbers that look like invoice numbers

    Args:
        text: Text to search for invoice references.

    Returns:
        List of unique invoice references found.
    """
    if not text:
        return []

    # Normalize text
    text = text.upper()

    references: Set[str] = set()

    # Pattern 1: INV followed by separator and alphanumeric
    # Matches: INV-12345, INV#12345, INV:12345, INV 12345
    pattern1 = r"INV[-:#\s]*([\w-]+)"
    for match in re.finditer(pattern1, text):
        ref = match.group(1).strip("-")
        if ref:
            references.add(ref)

    # Pattern 2: INVOICE followed by optional separator
    # Matches: INVOICE 12345, INVOICE: 12345, INVOICE#12345
    pattern2 = r"INVOICE\s*[:#]?\s*([\w-]+)"
    for match in re.finditer(pattern2, text):
        ref = match.group(1).strip("-")
        if ref:
            references.add(ref)

    # Pattern 3: Reference pattern (REF, REF#, etc.)
    # Matches: REF-12345, REF#12345, REFERENCE: 12345
    pattern3 = r"REF(?:ERENCE)?[-:#\s]*([\w-]+)"
    for match in re.finditer(pattern3, text):
        ref = match.group(1).strip("-")
        if ref:
            references.add(ref)

    # Pattern 4: Payment reference pattern
    # Matches: PMT-12345, PYMT#12345
    pattern4 = r"P(?:Y)?MT[-:#\s]*([\w-]+)"
    for match in re.finditer(pattern4, text):
        ref = match.group(1).strip("-")
        if ref:
            references.add(ref)

    # Pattern 5: Common invoice number formats
    # Matches standalone patterns like 2024-001, 2024001, etc.
    pattern5 = r"\b(20\d{2}[-/]?\d{3,6})\b"
    for match in re.finditer(pattern5, text):
        ref = match.group(1)
        references.add(ref)

    return sorted(references)


def normalize_reference(ref: str) -> str:
    """Normalize a reference string for comparison.

    Removes common separators and converts to uppercase.

    Args:
        ref: Reference string to normalize.

    Returns:
        Normalized reference string.
    """
    if not ref:
        return ""

    # Remove common separators and whitespace
    normalized = re.sub(r"[-:#\s/]", "", ref.upper())
    return normalized


def references_match(ref1: str, ref2: str) -> bool:
    """Check if two references match after normalization.

    Args:
        ref1: First reference.
        ref2: Second reference.

    Returns:
        True if references match.
    """
    return normalize_reference(ref1) == normalize_reference(ref2)
