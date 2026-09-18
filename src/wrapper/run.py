"""run_once() -- the Phase 6 sub-project 1 orchestrator (docs/superpowers/
specs/2026-09-01-phase6-wrapper-core-design.md). Thin orchestration shell:
no business logic of its own, only sequencing calls into the other
src/wrapper modules and src/checks."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.checks import hard_rules, lore_checker
from src.wrapper import chapter_log, halts, log, snapshot
from src.wrapper.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class RunResult:
    halted: bool
    halt_reason: str | None = None
    chapter_number: int | None = None
    delivered: bool = False
    needs_author_eyes: bool = False
    revision_loops: int = 0


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _current_chapter_number(repo_root: Path, book_id: str) -> int:
    entries = _read_json(repo_root / "books" / book_id / "chapters" / "index.json")
    return max(entry["number"] for entry in entries)  # type: ignore[union-attr,arg-type]


def _chapter_text(repo_root: Path, book_id: str, chapter_number: int) -> str:
    chapters_dir = repo_root / "books" / book_id / "chapters"
    matches = sorted(chapters_dir.glob(f"{chapter_number:04d}_*.md"))
    if not matches:
        raise FileNotFoundError(f"no chapter file found for chapter {chapter_number} in {chapters_dir}")
    return matches[0].read_text(encoding="utf-8")


def _read_state_file(repo_root: Path, book_id: str, name: str) -> str:
    path = repo_root / "books" / book_id / "story" / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _draft(repo_root: Path, book_id: str, word_count: int) -> None:
    # No --dry-run flag exists on `inkos draft` (confirmed via `inkos draft
    # --help`) -- dry_run's effect in run_once() is narrower than the
    # spec's one-liner suggests; see this plan's Global Constraints ruling.
    cmd = [str(repo_root / "scripts" / "inkos-gemini.sh"), "draft", book_id, "--words", str(word_count)]
    subprocess.run(cmd, cwd=repo_root, check=True)


def _revise(repo_root: Path, book_id: str, chapter_number: int, brief: str) -> None:
    cmd = [
        str(repo_root / "scripts" / "inkos-gemini.sh"), "revise", book_id, str(chapter_number),
        "--mode", "spot-fix", "--brief", brief,
    ]
    subprocess.run(cmd, cwd=repo_root, check=True)


def _audit(repo_root: Path, book_id: str, chapter_number: int) -> dict:
    cmd = [str(repo_root / "scripts" / "inkos-gemini.sh"), "audit", book_id, str(chapter_number), "--json"]
    result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)  # type: ignore[no-any-return]


def run_once(
    book_id: str = "aethon", *, dry_run: bool = False, repo_root: Path | None = None
) -> RunResult:
    repo_root = repo_root or REPO_ROOT
    config = load_config(repo_root / "config.yaml")
    log_path = repo_root / "sandbox" / "wrapper_run.log"

    halt_reason = halts.check_all(repo_root, book_id, config)
    if halt_reason is not None:
        log.log_event(log_path, {"event": "halt", "check": halt_reason.check, "detail": halt_reason.detail})
        return RunResult(halted=True, halt_reason=halt_reason.check)

    snap_hash = None if dry_run else snapshot.snapshot(repo_root)
    log.log_event(log_path, {"event": "snapshot", "hash": snap_hash})

    try:
        book = _read_json(repo_root / "books" / book_id / "book.json")
        _draft(repo_root, book_id, book["chapterWordCount"])  # type: ignore[index]
        chapter_number = _current_chapter_number(repo_root, book_id)
        log.log_event(log_path, {"event": "draft", "chapter": chapter_number})

        new_canon_items: list[str] = []
        revision_loops = 0
        needs_author_eyes = True

        for loop_index in range(config.max_revision_loops):
            chapter_text = _chapter_text(repo_root, book_id, chapter_number)
            critical_found = False

            hr_result = hard_rules.check_chapter(chapter_text, saga=config.current_saga)
            log.log_event(log_path, {"event": "hard_rules", "loop": loop_index, "verdict": hr_result.verdict})
            if hr_result.verdict == "CRITICAL":
                brief = "; ".join(i.detail for i in hr_result.issues if i.severity == "critical")
                _revise(repo_root, book_id, chapter_number, brief)
                revision_loops += 1
                critical_found = True

            if not critical_found:
                knowledge = (
                    _read_state_file(repo_root, book_id, "character_matrix.md")
                    + "\n"
                    + _read_state_file(repo_root, book_id, "current_state.md")
                )
                lore_result = lore_checker.run(
                    chapter_text=chapter_text, saga=config.current_saga, book_id=book_id,
                    character_knowledge_states=knowledge,
                )
                log.log_event(log_path, {"event": "lore_checker", "loop": loop_index, "verdict": lore_result.verdict})
                new_canon_items.extend(i.rule for i in lore_result.issues if i.severity == "flag")
                if lore_result.verdict == "CRITICAL":
                    brief = "; ".join(i.fix_instruction for i in lore_result.issues if i.severity == "critical")
                    _revise(repo_root, book_id, chapter_number, brief)
                    revision_loops += 1
                    critical_found = True

            if not critical_found:
                audit_report = _audit(repo_root, book_id, chapter_number)
                audit_issues = audit_report.get("issues", [])
                log.log_event(log_path, {"event": "inkos_audit", "loop": loop_index, "issues": len(audit_issues)})
                critical_issues = [i for i in audit_issues if i.get("severity") == "critical"]
                if critical_issues:
                    brief = "; ".join(i.get("description", "") for i in critical_issues)
                    _revise(repo_root, book_id, chapter_number, brief)
                    revision_loops += 1
                    critical_found = True

            if not critical_found:
                needs_author_eyes = False
                break

        chapter_text = _chapter_text(repo_root, book_id, chapter_number)
        log_entry = chapter_log.build(
            repo_root, book_id, chapter_number, chapter_text, config, new_canon_items
        )
        log_dir = repo_root / "sandbox" / "chapter_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"ch{chapter_number}.md").write_text(log_entry, encoding="utf-8")

        log.log_event(
            log_path,
            {
                "event": "delivered", "chapter": chapter_number,
                "needs_author_eyes": needs_author_eyes, "revision_loops": revision_loops,
            },
        )
        return RunResult(
            halted=False, chapter_number=chapter_number, delivered=True,
            needs_author_eyes=needs_author_eyes, revision_loops=revision_loops,
        )
    except Exception as exc:
        if snap_hash is not None:
            snapshot.rollback(repo_root, snap_hash, [f"books/{book_id}/", "vault/"])
        log.log_event(log_path, {"event": "exception", "error": str(exc)})
        raise
