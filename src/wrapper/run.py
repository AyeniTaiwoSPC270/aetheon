"""run_once() -- the Phase 6 sub-project 1 orchestrator (docs/superpowers/
specs/2026-09-01-phase6-wrapper-core-design.md). Thin orchestration shell:
no business logic of its own, only sequencing calls into the other
src/wrapper modules and src/checks."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from telegram import Bot

from src.checks import canon_proposals, hard_rules, lore_checker
from src.telegram.delivery import notify_delivery
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


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _current_chapter_number(repo_root: Path, book_id: str) -> int:
    entries: list[dict[str, Any]] = _read_json(repo_root / "books" / book_id / "chapters" / "index.json")
    return int(max(entry["number"] for entry in entries))


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


def _audit(repo_root: Path, book_id: str, chapter_number: int) -> dict[str, Any]:
    cmd = [str(repo_root / "scripts" / "inkos-gemini.sh"), "audit", book_id, str(chapter_number), "--json"]
    result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=True)
    return cast(dict[str, Any], json.loads(result.stdout))


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
        _draft(repo_root, book_id, int(book["chapterWordCount"]))
        chapter_number = _current_chapter_number(repo_root, book_id)
        log.log_event(log_path, {"event": "draft", "chapter": chapter_number})

        latest_lore_result: lore_checker.LoreCheckResult | None = None
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
                latest_lore_result = lore_result
                log.log_event(log_path, {"event": "lore_checker", "loop": loop_index, "verdict": lore_result.verdict})
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

        new_canon_items: list[str] = []
        if latest_lore_result is not None:
            for issue in latest_lore_result.issues:
                if issue.severity != "flag":
                    continue
                new_canon_items.append(issue.rule)
                if issue.new_entity is not None:
                    proposal_path = canon_proposals.write_proposal(
                        repo_root, chapter_number, issue.new_entity, flagged_by="lore_checker"
                    )
                    log.log_event(
                        log_path,
                        {
                            "event": "canon_proposal",
                            "entity": issue.new_entity.name,
                            "written": proposal_path is not None,
                        },
                    )

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


async def _notify_result(result: RunResult, book_id: str, repo_root: Path) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram not configured (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID missing) -- skipping notification.")
        return
    async with Bot(token) as bot:
        if result.halted:
            await bot.send_message(chat_id=int(chat_id), text=f"⏸️ Halted: {result.halt_reason}")
        else:
            await notify_delivery(bot, int(chat_id), result, book_id, repo_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one pass of the Aethon wrapper pipeline.")
    parser.add_argument("--book-id", default="aethon", help="Book ID (default: aethon)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Skip the git snapshot/rollback; halt checks still run for real",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="No-op flag for compatibility with cron/daemon invocations -- run_once() always runs exactly once",
    )
    args = parser.parse_args(argv)

    result = run_once(args.book_id, dry_run=args.dry_run)

    if not args.dry_run:
        asyncio.run(_notify_result(result, args.book_id, REPO_ROOT))

    if result.halted:
        print(f"Halted: {result.halt_reason}")
        return 1

    print(f"Chapter {result.chapter_number} delivered (revision loops: {result.revision_loops})")
    if result.needs_author_eyes:
        print("NEEDS AUTHOR EYES -- revision loop exhausted without a clean pass")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
