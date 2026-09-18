"""`/query` command logic -- BUILD_PLAN.md §10's "/query <lore question>"
routes to the Magic Index. Returns raw retrieved canon chunks with source
citations, not an LLM-synthesized answer -- $0 cost, deterministic, no
new quota/failure surface (brainstormed 2026-09-18)."""
from __future__ import annotations

from src.checks.name_registry import KNOWN_CHARACTERS
from src.magic_index.query import query_lore

_EXCERPT_LIMIT = 280


def _matched_characters(question: str) -> list[str]:
    return [name for name in KNOWN_CHARACTERS if name in question]


def _excerpt(text: str) -> str:
    if len(text) <= _EXCERPT_LIMIT:
        return text
    return text[:_EXCERPT_LIMIT] + "..."


def build_query_reply(question: str, saga: int, k: int = 4) -> str:
    chunks = query_lore(question, saga, characters=_matched_characters(question), k=k)
    header = f'🔍 Query: "{question}"'
    if not chunks:
        return f"{header}\n\nNo canon found for this question."
    lines = [
        f"{i}. [{chunk.source}] {_excerpt(chunk.text)}"
        for i, chunk in enumerate(chunks, start=1)
    ]
    return header + "\n\n" + "\n".join(lines)
