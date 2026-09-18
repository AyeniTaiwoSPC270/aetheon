"""Lore Checker (HR-05; BUILD_PLAN.md §8; docs/superpowers/specs/
2026-09-01-phase6-wrapper-core-design.md decisions 5-7). First live wiring
of prompts/lore_checker.md to a real model call -- see that file's own
header comment for why it sat unwired until now."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from google import genai

from src.checks.name_registry import KNOWN_CHARACTERS
from src.magic_index.query import Chunk, query_lore

PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "lore_checker.md"
MODEL = "gemini-flash-latest"


@dataclass(frozen=True)
class LoreIssue:
    severity: str
    quote: str
    rule: str
    fix_instruction: str


@dataclass
class LoreCheckResult:
    verdict: str
    issues: list[LoreIssue] = field(default_factory=list)


def _load_prompt() -> str:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    return text.split("<!--\nNot yet wired")[0].strip()


def _matched_characters(chapter_text: str) -> list[str]:
    return [name for name in KNOWN_CHARACTERS if name in chapter_text]


def _format_chunks(chunks: list[Chunk]) -> str:
    if not chunks:
        return "(no canon chunks retrieved)"
    return "\n\n".join(f"[{chunk.source}]\n{chunk.text}" for chunk in chunks)


def run(
    chapter_text: str,
    saga: int,
    book_id: str,
    character_knowledge_states: str,
    client: Any | None = None,
) -> LoreCheckResult:
    chunks = query_lore(
        question=chapter_text,
        saga=saga,
        characters=_matched_characters(chapter_text),
        k=6,
    )
    full_prompt = (
        f"{_load_prompt()}\n\n"
        f"## Chapter draft\n{chapter_text}\n\n"
        f"## Retrieved canon chunks\n{_format_chunks(chunks)}\n\n"
        f"## Current character knowledge states\n{character_knowledge_states}"
    )
    client = client or genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(model=MODEL, contents=full_prompt)
    response_text = response.text
    assert response_text is not None, "Gemini returned an empty response"
    payload = json.loads(response_text)
    issues = [LoreIssue(**issue) for issue in payload.get("issues", [])]
    return LoreCheckResult(verdict=payload["verdict"], issues=issues)
