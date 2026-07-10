from pathlib import Path

from src.checks.hard_rules import check_chapter

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_hr01_new_phasite_is_critical():
    text = (FIXTURES / "poisoned" / "hr01_phasite_12.md").read_text(encoding="utf-8")
    result = check_chapter(text, saga=5)
    assert result.verdict == "CRITICAL"
    critical = [i for i in result.issues if i.rule == "HR-01"]
    assert critical
    assert "12" in critical[0].quote


def test_hr03_unbound_named_early_is_critical():
    text = (FIXTURES / "poisoned" / "hr03_unbound_saga1.md").read_text(encoding="utf-8")
    result = check_chapter(text, saga=1)
    assert result.verdict == "CRITICAL"
    assert any(i.rule == "HR-03" for i in result.issues)


def test_hr07_misspellings_caught_and_logged():
    text = (FIXTURES / "poisoned" / "hr07_misspellings.md").read_text(encoding="utf-8")
    result = check_chapter(text, saga=1)
    assert result.verdict == "CRITICAL"
    found_quotes = {i.quote for i in result.issues if i.rule == "HR-07"}
    assert "Valdenmeer" in found_quotes
    assert "Greyvale Academy" in found_quotes


def test_clean_chapter_13_passes_with_at_most_two_flags():
    text = (FIXTURES / "golden" / "chapter_13.md").read_text(encoding="utf-8")
    result = check_chapter(text, saga=1)
    critical = [i for i in result.issues if i.severity == "critical"]
    flags = [i for i in result.issues if i.severity == "flag"]
    assert result.verdict == "PASS"
    assert not critical
    assert len(flags) <= 2


def test_hr01_fixed_draft_passes_within_the_checker_alone():
    # Full revision-loop integration (inkos revise --mode spot-fix, re-check,
    # <=3 attempts) is the Phase 6 wrapper's job. What Phase 3 owns is that
    # the checker itself is a pure, re-runnable function: same CRITICAL
    # input twice gives CRITICAL twice, and a manually fixed draft gives PASS.
    poisoned = (FIXTURES / "poisoned" / "hr01_phasite_12.md").read_text(encoding="utf-8")
    first = check_chapter(poisoned, saga=5)
    second = check_chapter(poisoned, saga=5)
    assert first.verdict == second.verdict == "CRITICAL"

    fixed = poisoned.replace(
        '"Phasite 12," the man said, dust sliding off his shoulders like it\n'
        "had never touched him. \"Phasite 12, Kael the Stormborn. You didn't think\n"
        "you were the last one Varek found, did you?\"",
        '"You\'re not the last one Varek found," the man said, dust sliding off '
        "his shoulders like it had never touched him.",
    )
    third = check_chapter(fixed, saga=5)
    assert third.verdict == "PASS"


def test_unimplemented_rules_raise_not_pass_silently():
    from src.checks.hard_rules import (
        check_hr04_authorization,
        check_hr05_knowledge_boundaries,
        check_hr06_unknown_entities,
        check_hr10_author_notes,
    )

    for fn in (
        check_hr04_authorization,
        check_hr05_knowledge_boundaries,
        check_hr06_unknown_entities,
        check_hr10_author_notes,
    ):
        try:
            fn()
            assert False, f"{fn.__name__} should not silently succeed"
        except NotImplementedError:
            pass
