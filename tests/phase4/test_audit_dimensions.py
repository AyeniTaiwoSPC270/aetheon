"""T4.2 (humor placement) and T4.4 (ending variety) — proves the new
additionalAuditDimensions in book_rules.md actually fire, per BUILD_PLAN.md
§9's test table. Runs against the disposable `aethon-fixtures` sandbox
book (never the real `aethon` book) via InkOS's own Auditor, routed
through Gemini like every other live `inkos` call in this repo (see
CLAUDE.md's MODEL ROUTING section) — a bare `inkos` call would silently
hit dead Anthropic defaults instead.

Chapter mapping (confirmed against the actual sandbox book on disk, which
diverges from the original implementation plan's assumed 1=filler/
2=humor/3=filler/4=third): Chapter 1 already holds the humor_at_climax.md
content (drafted 2026-07-10, see that fixture's own header comment for why
a full-scene swap was abandoned in favor of editing the real AI-drafted
scene in place). Chapters 2-4 (filler_cliffhanger.md twice, then
third_cliffhanger.md) do not exist yet as of this test's authoring — they
need three more `inkos draft` calls plus overwriting each with the
poisoned/filler text (Task 4 Steps 4-5 of the implementation plan),
which is quota-consuming and deliberately not run as part of writing this
test. test_t4_4_third_cliffhanger_is_flagged is expected to fail (chapter
not found) until that bootstrapping is done.

Real InkOS audit JSON is confirmed from @actalk/inkos-core's
PipelineRunner.auditDraft/evaluateMergedAudit source (dist/pipeline/
runner.js): `{passed, issues: [{severity, category, description}, ...],
summary, chapterNumber}` — no `dimension` field, so dimension detection
here matches on `category` + `description` text instead.

2026-09-01: a live audit of Chapter 1 (already the humor_at_climax.md
content) against gemini-flash-latest came back with zero humor-related
issues. Root cause: book_rules.md's "Humor placement" dimension was
worded as "Aldric's dry humor..." — since the sandbox protagonist is
never named Aldric in the text, the auditor never bound the rule to it.
Fixed at the source: book_rules.md (both the real `aethon` copy and this
sandbox's copy, kept identical) now reads "the protagonist's dry humor"
instead — semantically identical for the real book (Aldric is its sole
protagonist) but no longer character-name-coupled, so it fires
regardless of what the sandbox's auto-generated cast is named. Chapter 1
has not been re-audited against the corrected wording yet (holding
further Gemini calls for quota reasons as of this writing) — do that
before trusting test_t4_2_humor_at_climax_is_flagged's result.

Also 2026-09-01: `gemini-2.0-flash-001` hard-404'd (see CLAUDE.md's
MODEL ROUTING section) — GEMINI_ROUTING_FLAGS below now uses
`gemini-flash-latest`, confirmed working via a real `inkos audit` call
against this same sandbox book.
"""
from __future__ import annotations

import json
import shutil
import subprocess

INKOS = shutil.which("inkos")
BOOK_ID = "aethon-fixtures"

GEMINI_ROUTING_FLAGS = [
    "--service", "google",
    "--model", "gemini-flash-latest",
    "--api-key-env", "GEMINI_API_KEY",
    "--api-format", "responses",
]


def _run_audit(chapter: int) -> dict:
    assert INKOS, "inkos CLI not found on PATH"
    result = subprocess.run(
        [INKOS, *GEMINI_ROUTING_FLAGS, "audit", BOOK_ID, str(chapter), "--json"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def _issue_text(issue: dict) -> str:
    return (str(issue.get("category", "")) + " " + str(issue.get("description", ""))).lower()


def test_t4_2_humor_at_climax_is_flagged():
    report = _run_audit(1)
    issues = report.get("issues", [])
    assert any("humor" in _issue_text(i) for i in issues), report


def test_t4_4_third_cliffhanger_is_flagged():
    report = _run_audit(4)
    issues = report.get("issues", [])
    assert any(
        "ending" in _issue_text(i) or "cliffhanger" in _issue_text(i) for i in issues
    ), report
