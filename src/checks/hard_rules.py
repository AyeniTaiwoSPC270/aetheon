"""Deterministic Hard-Rule Checker — HR-01, HR-02, HR-03, HR-07, HR-08,
HR-09, HR-11 (BUILD_PLAN.md §4). Runs before any LLM call and before
InkOS's own Validator/Auditor, per CLAUDE.md rule 1 — zero LLM cost.

HR-04, HR-05, HR-06, and HR-10 are intentionally not implemented here; see
their functions below for exactly what's missing and which phase supplies
it. Never delete these stubs to "make it pass" — an unimplemented rule
must raise, not silently no-op (CLAUDE.md: "never suppress issues to force
a pass").
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import NoReturn

from src.checks.name_registry import find_near_misses
from src.checks.technique_registry import TECHNIQUES

PHASITE_NUMBER_RE = re.compile(r"\bPhasite\s+(\d+)\b")
DRAGONITE_DESCRIPTORS = [
    "scales", "scaled", "wings", "wingspan", "claws", "talons", "fangs",
    "horns", "snout", "tail", "feet long", "feet tall", "colour", "color",
]
CIRCUIT_SEVER_RE = re.compile(
    r"\bsever(?:s|ed|ing)?\b.{0,40}\bcircuit", re.IGNORECASE | re.DOTALL
)
POV_HEADER_RE = re.compile(r"^—\s*\[?[A-Za-z][\w' ]*\]?\s*—\s*$", re.MULTILINE)
POV_LINE_RE = re.compile(r"^—.*—$", re.MULTILINE)


@dataclass
class Issue:
    rule: str
    severity: str  # "flag" | "critical"
    quote: str
    detail: str


@dataclass
class CheckResult:
    verdict: str  # "PASS" | "CRITICAL"
    issues: list[Issue] = field(default_factory=list)


def _check_hr01_phasite_count(text: str) -> list[Issue]:
    issues = []
    for m in PHASITE_NUMBER_RE.finditer(text):
        if int(m.group(1)) > 11:
            issues.append(
                Issue(
                    "HR-01", "critical", m.group(0),
                    "Only 11 Phasites exist; no new Phasite may be named or implied.",
                )
            )
    return issues


def _check_hr02_dragonite_description(text: str, saga: int) -> list[Issue]:
    if saga >= 7:
        return []
    issues = []
    for dm in re.finditer(r"Dragonite", text):
        window = text[max(0, dm.start() - 100): dm.end() + 100].lower()
        for descriptor in DRAGONITE_DESCRIPTORS:
            if descriptor in window:
                issues.append(
                    Issue(
                        "HR-02", "critical", text[dm.start(): dm.end()],
                        f"Dragonites have no physical description before Saga 7 "
                        f"(found '{descriptor}' near 'Dragonite' at saga {saga}).",
                    )
                )
                break
    return issues


def _check_hr03_the_unbound(text: str, saga: int) -> list[Issue]:
    if saga >= 4:
        return []
    return [
        Issue(
            "HR-03", "critical", m.group(0),
            f"'The Unbound' is not publicly known before Saga 4 (saga={saga}).",
        )
        for m in re.finditer(r"\bThe Unbound\b", text)
    ]


def _check_hr07_spellings(text: str) -> list[Issue]:
    return [
        Issue(
            "HR-07", "critical", nm.found,
            f"Near-miss of canonical spelling '{nm.canonical}' "
            f"(edit distance {nm.distance}); auto-corrected.",
        )
        for nm in find_near_misses(text)
    ]


def _check_hr08_saga_gated_techniques(text: str, saga: int) -> list[Issue]:
    issues = []
    for technique in TECHNIQUES:
        if technique.saga_available > saga and technique.name in text:
            issues.append(
                Issue(
                    "HR-08", "critical", technique.name,
                    f"'{technique.name}' unlocks in saga {technique.saga_available}, "
                    f"used at saga {saga}.",
                )
            )
    return issues


def _check_hr09_structure(text: str) -> list[Issue]:
    issues = []
    word_count = len(text.split())
    if not (2000 <= word_count <= 3000):
        issues.append(
            Issue(
                "HR-09", "flag", f"{word_count} words",
                "Chapter word count outside the 2000-3000 target band.",
            )
        )
    for m in POV_LINE_RE.finditer(text):
        if not POV_HEADER_RE.match(m.group(0)):
            issues.append(
                Issue(
                    "HR-09", "flag", m.group(0),
                    "POV shift line does not match the '— [Name] —' format.",
                )
            )
    return issues


def _check_hr11_circuit_severing(text: str, authorized: bool) -> list[Issue]:
    if authorized:
        return []
    return [
        Issue(
            "HR-11", "critical", m.group(0),
            "Circuit severing requires plan authorization.",
        )
        for m in CIRCUIT_SEVER_RE.finditer(text)
    ]


def check_chapter(
    text: str, saga: int, circuit_severing_authorized: bool = False
) -> CheckResult:
    """Run all implemented deterministic hard rules against a chapter draft."""
    issues: list[Issue] = []
    issues += _check_hr01_phasite_count(text)
    issues += _check_hr02_dragonite_description(text, saga)
    issues += _check_hr03_the_unbound(text, saga)
    issues += _check_hr07_spellings(text)
    issues += _check_hr08_saga_gated_techniques(text, saga)
    issues += _check_hr09_structure(text)
    issues += _check_hr11_circuit_severing(text, circuit_severing_authorized)

    verdict = "CRITICAL" if any(i.severity == "critical" for i in issues) else "PASS"
    return CheckResult(verdict=verdict, issues=issues)


def check_hr04_authorization(*args: object, **kwargs: object) -> NoReturn:
    raise NotImplementedError(
        "HR-04 (kill/rename/repower without plan authorization) needs a diff "
        "against the approved plan's authorization tokens, which don't exist "
        "until the Phase 6 wrapper tracks per-chapter plan state. Do not stub "
        "a fake pass — wire this when the wrapper lands."
    )


def check_hr05_knowledge_boundaries(*args: object, **kwargs: object) -> NoReturn:
    raise NotImplementedError(
        "HR-05 is explicitly an LLM pass against character_matrix "
        "(BUILD_PLAN.md §4), not a deterministic rule — it belongs to the "
        "Lore Checker prompt (prompts/lore_checker.md, BUILD_PLAN.md §8), "
        "not this module."
    )


def check_hr06_unknown_entities(*args: object, **kwargs: object) -> NoReturn:
    raise NotImplementedError(
        "HR-06 needs NER-quality entity extraction against a full registry "
        "built from Magic Index chunk metadata, not the ~18-name hand-typed "
        "list in name_registry.py (which exists only to serve HR-07). "
        "Building real NER is a separate task — do not approximate it with "
        "the HR-07 name list, which would misfire on every legitimate name "
        "not yet in that list."
    )


def check_hr10_author_notes(*args: object, **kwargs: object) -> NoReturn:
    raise NotImplementedError(
        "HR-10 scans beat maps in vault/01-Sagas/ for '[AUTHOR NOTE]', but "
        "that directory is empty and author-edited-only right now — nothing "
        "to scan yet. Wire this once Saga 2 beat maps exist."
    )
