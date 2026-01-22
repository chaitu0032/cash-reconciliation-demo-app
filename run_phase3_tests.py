"""Test runner for Phase 3 suggestions using generated test data."""

from decimal import Decimal
from src_v2.config import ReconciliationConfig
from src_v2.matching.phase3_suggestions import Phase3SuggestionGenerator
from src_v2.models.result import ConfidenceTier, SuggestionType
from test_phase3_data import (
    generate_strategy1_data,
    generate_strategy2_data,
    generate_strategy3_data,
    generate_strategy4_data,
    generate_edge_cases,
    generate_comprehensive_test_data,
)


def print_suggestion(suggestion):
    """Pretty print a suggestion."""
    print(f"  Bank: {suggestion.bank_id}")
    print(f"  Type: {suggestion.suggestion_type.value}")
    print(f"  Confidence: {suggestion.confidence:.1%} ({suggestion.tier.value})")
    print(f"  Allocations:")
    for alloc in suggestion.allocations:
        partial = " (PARTIAL)" if alloc.is_partial else ""
        print(f"    → {alloc.invoice_number}: ${alloc.amount}{partial}")
        if alloc.is_partial:
            print(f"      Remaining: ${alloc.remaining_after}")
    print(f"  Explanation: {suggestion.explanation}")


def test_strategy1():
    """Test Strategy 1: Single invoice per customer."""
    print("\n" + "=" * 70)
    print("TEST: Strategy 1 - Single Invoice Per Customer")
    print("=" * 70)

    banks, invoices = generate_strategy1_data()
    config = ReconciliationConfig()
    generator = Phase3SuggestionGenerator(config)

    result = generator.process(banks, invoices, already_matched_bank_ids=set())

    print(f"\n✅ Generated {len(result.suggestions)} suggestions")
    print(f"⚠️  {len(result.manual_items)} manual items\n")

    # Count strategy types
    strategy1_count = sum(
        1 for s in result.suggestions
        if s.suggestion_type == SuggestionType.SINGLE_INVOICE
    )

    for suggestion in result.suggestions:
        print_suggestion(suggestion)
        print()

    # Verify expectations - at least 2 should match via Strategy 1
    assert strategy1_count >= 2, f"Expected at least 2 Strategy 1 matches, got {strategy1_count}"

    # Check that Strategy 1 suggestions have correct confidence
    for suggestion in result.suggestions:
        if suggestion.suggestion_type == SuggestionType.SINGLE_INVOICE:
            assert suggestion.confidence == 0.95
            assert suggestion.tier == ConfidenceTier.HIGH

    print(f"✓ Strategy 1 test passed! ({strategy1_count} matches via Strategy 1)")
    return result


def test_strategy2():
    """Test Strategy 2: Unique amount match."""
    print("\n" + "=" * 70)
    print("TEST: Strategy 2 - Unique Amount Match")
    print("=" * 70)

    banks, invoices = generate_strategy2_data()
    config = ReconciliationConfig()
    generator = Phase3SuggestionGenerator(config)

    result = generator.process(banks, invoices, already_matched_bank_ids=set())

    print(f"\n✅ Generated {len(result.suggestions)} suggestions")
    print(f"⚠️  {len(result.manual_items)} manual items\n")

    # Count strategy types
    strategy2_count = sum(
        1 for s in result.suggestions
        if s.suggestion_type == SuggestionType.UNIQUE_AMOUNT
    )

    for suggestion in result.suggestions:
        print_suggestion(suggestion)
        print()

    # Verify expectations - at least 2 should match via Strategy 2
    assert strategy2_count >= 2, f"Expected at least 2 Strategy 2 matches, got {strategy2_count}"

    # Check confidence for Strategy 2 suggestions
    for suggestion in result.suggestions:
        if suggestion.suggestion_type == SuggestionType.UNIQUE_AMOUNT:
            assert suggestion.confidence >= 0.90
            assert suggestion.tier == ConfidenceTier.HIGH

    print(f"✓ Strategy 2 test passed! ({strategy2_count} matches via Strategy 2)")
    return result


def test_strategy3():
    """Test Strategy 3: Unique combination."""
    print("\n" + "=" * 70)
    print("TEST: Strategy 3 - Unique Combination")
    print("=" * 70)

    banks, invoices = generate_strategy3_data()
    config = ReconciliationConfig()
    generator = Phase3SuggestionGenerator(config)

    result = generator.process(banks, invoices, already_matched_bank_ids=set())

    print(f"\n✅ Generated {len(result.suggestions)} suggestions")
    print(f"⚠️  {len(result.manual_items)} manual items\n")

    # Count strategy types
    strategy3_count = sum(
        1 for s in result.suggestions
        if s.suggestion_type == SuggestionType.UNIQUE_COMBINATION
    )

    for suggestion in result.suggestions:
        print_suggestion(suggestion)
        print()

    # Verify expectations - at least 1 should match via Strategy 3
    assert strategy3_count >= 1, f"Expected at least 1 Strategy 3 match, got {strategy3_count}"

    # Check confidence for Strategy 3 suggestions
    for suggestion in result.suggestions:
        if suggestion.suggestion_type == SuggestionType.UNIQUE_COMBINATION:
            assert suggestion.confidence >= 0.85
            assert suggestion.tier == ConfidenceTier.HIGH

    print(f"✓ Strategy 3 test passed! ({strategy3_count} matches via Strategy 3)")
    return result


def test_strategy4():
    """Test Strategy 4: Flow network matching."""
    print("\n" + "=" * 70)
    print("TEST: Strategy 4 - Flow Network Matching")
    print("=" * 70)

    banks, invoices = generate_strategy4_data()
    config = ReconciliationConfig()
    generator = Phase3SuggestionGenerator(config)

    result = generator.process(banks, invoices, already_matched_bank_ids=set())

    print(f"\n✅ Generated {len(result.suggestions)} suggestions")
    print(f"⚠️  {len(result.manual_items)} manual items\n")

    for suggestion in result.suggestions:
        print_suggestion(suggestion)
        print()

    print("✓ Strategy 4 test completed!")
    return result


def test_edge_cases():
    """Test edge cases and challenging scenarios."""
    print("\n" + "=" * 70)
    print("TEST: Edge Cases")
    print("=" * 70)

    banks, invoices = generate_edge_cases()
    config = ReconciliationConfig()
    generator = Phase3SuggestionGenerator(config)

    result = generator.process(banks, invoices, already_matched_bank_ids=set())

    print(f"\n✅ Generated {len(result.suggestions)} suggestions")
    print(f"⚠️  {len(result.manual_items)} manual items\n")

    if result.suggestions:
        print("Suggestions:")
        for suggestion in result.suggestions:
            print_suggestion(suggestion)
            print()

    if result.manual_items:
        print("Manual Items:")
        for manual in result.manual_items:
            print(f"  Bank: {manual.bank_id}")
            print(f"  Amount: ${manual.amount}")
            print(f"  Reason: {manual.reason}")
            print(f"  Candidates: {len(manual.candidate_invoices)} invoices")
            print()

    print("✓ Edge cases test completed!")
    return result


def test_comprehensive():
    """Test all scenarios together."""
    print("\n" + "=" * 70)
    print("TEST: Comprehensive - All Scenarios Combined")
    print("=" * 70)

    banks, invoices = generate_comprehensive_test_data()
    config = ReconciliationConfig()
    generator = Phase3SuggestionGenerator(config)

    result = generator.process(banks, invoices, already_matched_bank_ids=set())

    print(f"\nTotal Banks: {len(banks)}")
    print(f"Total Invoices: {len(invoices)}")
    print(f"\n✅ Generated {len(result.suggestions)} suggestions")
    print(f"⚠️  {len(result.manual_items)} manual items")

    # Group by suggestion type
    by_type = {}
    by_tier = {}

    for suggestion in result.suggestions:
        stype = suggestion.suggestion_type.value
        tier = suggestion.tier.value

        by_type[stype] = by_type.get(stype, 0) + 1
        by_tier[tier] = by_tier.get(tier, 0) + 1

    print("\n📊 Suggestions by Type:")
    for stype, count in sorted(by_type.items()):
        print(f"  {stype}: {count}")

    print("\n📊 Suggestions by Confidence Tier:")
    for tier, count in sorted(by_tier.items()):
        print(f"  {tier}: {count}")

    # Calculate total flow
    total_bank_amount = sum(b.amount for b in banks)
    total_suggested = sum(
        sum(alloc.amount for alloc in s.allocations)
        for s in result.suggestions
    )
    manual_amount = sum(m.amount for m in result.manual_items)

    print(f"\n💰 Flow Analysis:")
    print(f"  Total Bank Money: ${total_bank_amount}")
    print(f"  Suggested (with confidence): ${total_suggested} ({total_suggested/total_bank_amount:.1%})")
    print(f"  Requires Manual Review: ${manual_amount} ({manual_amount/total_bank_amount:.1%})")

    print("\n✓ Comprehensive test completed!")
    return result


def test_partial_allocations():
    """Test scenarios with partial invoice payments."""
    print("\n" + "=" * 70)
    print("TEST: Partial Allocations")
    print("=" * 70)

    from src_v2.models.bank import BankTransaction
    from src_v2.models.invoice import Invoice
    from datetime import date

    banks = [
        BankTransaction(
            id="B-PARTIAL-001",
            amount=Decimal("500.00"),  # Less than invoice
            date=date(2024, 1, 15),
            description="Partial payment",
            customer_id="CUST-PARTIAL",
        ),
    ]

    invoices = [
        Invoice(
            id="INV-PARTIAL-001",
            invoice_number="INV-2024-999",
            customer_id="CUST-PARTIAL",
            amount=Decimal("2000.00"),
            pending_amount=Decimal("2000.00"),
            due_date=date(2024, 2, 1),
        ),
    ]

    config = ReconciliationConfig()
    generator = Phase3SuggestionGenerator(config)
    result = generator.process(banks, invoices, already_matched_bank_ids=set())

    print(f"\n✅ Generated {len(result.suggestions)} suggestions\n")

    for suggestion in result.suggestions:
        print_suggestion(suggestion)

        # Verify partial allocation
        assert len(suggestion.allocations) == 1
        alloc = suggestion.allocations[0]
        assert alloc.is_partial == True
        assert alloc.amount == Decimal("500.00")
        assert alloc.remaining_after == Decimal("1500.00")
        print("\n✓ Partial allocation verified!")

    return result


if __name__ == "__main__":
    """Run all Phase 3 tests."""

    try:
        print("\n" + "🧪" * 35)
        print("PHASE 3 SUGGESTION GENERATION - TEST SUITE")
        print("🧪" * 35)

        # Run individual strategy tests
        test_strategy1()
        test_strategy2()
        test_strategy3()
        test_strategy4()
        test_edge_cases()
        test_partial_allocations()

        # Run comprehensive test
        test_comprehensive()

        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
