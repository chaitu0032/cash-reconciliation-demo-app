"""
Bank Description Parser - Virtual Remittance Creation

Parses bank transaction descriptions to extract payment information
and create virtual remittances when actual remittance documents are not available.

Extracts:
- Invoice numbers (INV-xxxx, Invoice #xxxx, etc.)
- Customer name (matched against customer master)
- Payment reference (REF:xxxx, PAY-xxxx)
- Customer account numbers (A/C:xxxx, ACCT-xxxx)
- Individual amounts per invoice (INV-XXX $amount)
"""
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from models import (
    BankTransaction,
    Customer,
    Remittance,
    RemittanceLineItem,
    RemittanceSource,
)


@dataclass
class ParsedBankData:
    """Intermediate data extracted from bank description"""
    invoice_numbers: list[str]
    invoice_amounts: dict[str, Decimal]  # invoice_number -> amount
    customer_name: Optional[str]
    customer_account: Optional[str]
    payment_reference: Optional[str]
    total_amount: Decimal


def parse_bank_description(
    bank_txn: BankTransaction,
    customers: list[Customer],
) -> Optional[Remittance]:
    """
    Parse a bank transaction description to create a virtual remittance.

    Returns a virtual Remittance if sufficient data is found:
    - At least one invoice number
    - Customer identifiable (by name, account, or payment ref pattern)

    Returns None if insufficient data to create virtual remittance.
    """
    parsed = _extract_data_from_description(bank_txn.description, bank_txn.amount)

    if not parsed.invoice_numbers:
        return None

    # Try to identify customer
    customer = _identify_customer(parsed, customers)
    if not customer:
        return None

    # Create virtual remittance
    return _create_virtual_remittance(bank_txn, parsed, customer)


def _extract_data_from_description(description: str, total_amount: Decimal) -> ParsedBankData:
    """Extract all identifiable data from bank description."""
    desc_upper = description.upper()

    # Extract invoice numbers
    invoice_numbers = _extract_invoice_numbers(description)

    # Extract amounts per invoice (if present)
    invoice_amounts = _extract_invoice_amounts(description, invoice_numbers, total_amount)

    # Extract customer name (will be matched later)
    customer_name = _extract_customer_name(description, invoice_numbers)

    # Extract account number
    customer_account = _extract_account_number(description)

    # Extract payment reference
    payment_reference = _extract_payment_reference(description)

    return ParsedBankData(
        invoice_numbers=invoice_numbers,
        invoice_amounts=invoice_amounts,
        customer_name=customer_name,
        customer_account=customer_account,
        payment_reference=payment_reference,
        total_amount=total_amount,
    )


def _extract_invoice_numbers(description: str) -> list[str]:
    """
    Extract invoice numbers from description.

    Patterns handled:
    - INV-2024-001, INV:2024001, INV 2024-001
    - Invoice #123, Invoice#123
    - Pure numeric sequences following "INV" context
    """
    invoices = []

    # Pattern: INV[-:#\s]?\d+[-\d]*
    inv_pattern = r'INV[-:#\s]?(\d+[-\d]*)'
    matches = re.findall(inv_pattern, description, re.IGNORECASE)
    for match in matches:
        # Reconstruct with INV prefix
        invoices.append(f"INV-{match.replace('-', '-')}")

    # Pattern: Invoice\s*#?\s*(\d+)
    invoice_pattern = r'INVOICE\s*#?\s*(\d+[-\d]*)'
    matches = re.findall(invoice_pattern, description, re.IGNORECASE)
    for match in matches:
        inv_id = f"INV-{match}"
        if inv_id not in invoices:
            invoices.append(inv_id)

    return invoices


def _extract_invoice_amounts(
    description: str,
    invoice_numbers: list[str],
    total_amount: Decimal,
) -> dict[str, Decimal]:
    """
    Extract amounts for each invoice if specified in description.

    Pattern: INV-XXX $amount or INV-XXX amount
    If amounts not specified, distribute total evenly.
    """
    amounts = {}

    # Try to find amounts near invoice numbers
    # Pattern: INV-XXX followed by $amount or just amount
    amount_pattern = r'INV[-:#\s]?(\d+[-\d]*)\s*\$?([\d,]+(?:\.\d{2})?)'
    matches = re.findall(amount_pattern, description, re.IGNORECASE)

    for inv_num, amount_str in matches:
        inv_id = f"INV-{inv_num}"
        try:
            amount = Decimal(amount_str.replace(',', ''))
            amounts[inv_id] = amount
        except:
            pass

    # If no amounts found or not all invoices have amounts, distribute evenly
    if not amounts or len(amounts) != len(invoice_numbers):
        if invoice_numbers:
            per_invoice = total_amount / len(invoice_numbers)
            for inv in invoice_numbers:
                if inv not in amounts:
                    amounts[inv] = per_invoice

    return amounts


def _extract_customer_name(description: str, invoice_numbers: list[str]) -> Optional[str]:
    """
    Extract potential customer name from description.

    Strategy: After removing known tokens (invoice numbers, amounts, etc.),
    the remaining text at the start is likely the customer name.
    """
    text = description.upper()

    # Remove invoice patterns
    text = re.sub(r'INV[-:#\s]?\d+[-\d]*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'INVOICE\s*#?\s*\d+[-\d]*', '', text, flags=re.IGNORECASE)

    # Remove amounts
    text = re.sub(r'\$[\d,]+(?:\.\d{2})?', '', text)
    text = re.sub(r'\b\d+\.\d{2}\b', '', text)

    # Remove common payment keywords
    keywords = [
        'PAYMENT', 'WIRE', 'TRANSFER', 'ACH', 'CHECK', 'CHK',
        'DEPOSIT', 'FROM', 'FOR', 'REF', 'REFERENCE', 'PMT',
    ]
    for kw in keywords:
        text = re.sub(rf'\b{kw}\b', '', text)

    # Remove reference patterns
    text = re.sub(r'REF[-:#]?\s*[\w-]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'A/?C[-:#]?\s*\d+', '', text, flags=re.IGNORECASE)

    # Clean up
    text = re.sub(r'\s+', ' ', text).strip()

    # Return if we have something meaningful (at least 2 chars)
    if len(text) >= 2:
        return text

    return None


def _extract_account_number(description: str) -> Optional[str]:
    """
    Extract customer account number from description.

    Patterns: A/C:12345, ACCT-12345, A/C 12345
    """
    patterns = [
        r'A/?C[-:#\s]?(\d+)',
        r'ACCT[-:#\s]?(\d+)',
        r'ACCOUNT[-:#\s]?(\d+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def _extract_payment_reference(description: str) -> Optional[str]:
    """
    Extract payment reference from description.

    Patterns: REF:xxxx, PAY-xxxx, TXN:xxxx
    """
    patterns = [
        r'REF[-:#\s]?([\w-]+)',
        r'PAY[-:#\s]?([\w-]+)',
        r'TXN[-:#\s]?([\w-]+)',
        r'PMT[-:#\s]?([\w-]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            ref = match.group(1)
            # Avoid matching just numbers that could be invoice numbers
            if not ref.isdigit():
                return ref

    return None


def _identify_customer(
    parsed: ParsedBankData,
    customers: list[Customer],
) -> Optional[Customer]:
    """
    Identify customer from parsed bank data.

    Matching priority:
    1. Account number match
    2. Exact name match
    3. Alias match
    4. Fuzzy name match (contained in)
    """
    # Try account number match
    if parsed.customer_account:
        for customer in customers:
            if parsed.customer_account in customer.account_numbers:
                return customer

    if not parsed.customer_name:
        return None

    name_upper = parsed.customer_name.upper()

    # Try exact name match
    for customer in customers:
        if customer.name.upper() == name_upper:
            return customer

    # Try alias match
    for customer in customers:
        for alias in customer.aliases:
            if alias.upper() == name_upper:
                return customer

    # Try fuzzy match (name contains or is contained)
    for customer in customers:
        cust_name = customer.name.upper()
        if cust_name in name_upper or name_upper in cust_name:
            return customer
        for alias in customer.aliases:
            alias_upper = alias.upper()
            if alias_upper in name_upper or name_upper in alias_upper:
                return customer

    return None


def _create_virtual_remittance(
    bank_txn: BankTransaction,
    parsed: ParsedBankData,
    customer: Customer,
) -> Remittance:
    """Create a virtual remittance from parsed bank data."""
    line_items = []

    for inv_num in parsed.invoice_numbers:
        amount = parsed.invoice_amounts.get(inv_num, parsed.total_amount / len(parsed.invoice_numbers))
        line_items.append(RemittanceLineItem(
            invoice_number=inv_num,
            description=f"Parsed from bank: {bank_txn.description[:50]}",
            payment_method="BANK_PARSED",
            amount=amount,
        ))

    return Remittance(
        id=f"VREM-{bank_txn.id}",  # Virtual remittance ID derived from bank txn
        customer_id=customer.customer_id,
        customer_name=customer.name,
        customer_address=customer.address,
        payment_reference=parsed.payment_reference or bank_txn.reference,
        payment_date=bank_txn.date,
        line_items=line_items,
        source=RemittanceSource.BANK_PARSED,
    )


def is_description_parseable(description: str) -> bool:
    """
    Quick check if a description likely contains parseable invoice data.

    Used for pre-filtering before full parsing.
    """
    desc_upper = description.upper()

    # Must contain invoice-related keywords
    has_invoice = bool(re.search(r'INV|INVOICE', desc_upper))

    return has_invoice
