"""Saga-gated semantic search over the Magic Index (BUILD_PLAN.md §8)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from chromadb.api import ClientAPI
from chromadb.api.types import Where

from src.magic_index.embed import get_client, get_collection


@dataclass
class Chunk:
    text: str
    source: str
    type: str
    saga_available: int
    characters: list[str]


def query_lore(
    question: str,
    saga: int,
    characters: list[str] | None = None,
    k: int = 6,
    client: ClientAPI | None = None,
) -> list[Chunk]:
    """Semantic search over the Magic Index, filtered to
    saga_available <= saga, then re-ranked to boost chunks mentioning the
    given characters."""
    characters = characters or []
    client = client or get_client()
    collection = get_collection(client)

    # cast(), not a `Where`-annotated literal: mypy still infers the nested
    # {"$lte": saga} dict literal as plain dict[str, int] and widens even
    # under a declared target type, so a direct assignment still fails
    # dict-item checking against chromadb's Literal-keyed operator union.
    # The value is a valid Where at runtime (chromadb's own documented
    # usage) — this cast tells mypy that. Same stub-precision gap as the
    # get_collection type-ignore in embed.py.
    where = cast(Where, {"saga_available": {"$lte": saga}})
    raw = collection.query(
        query_texts=[question],
        n_results=max(k * 3, k),
        where=where,
    )

    results: list[Chunk] = []
    docs = raw["documents"][0] if raw["documents"] else []
    metas = raw["metadatas"][0] if raw["metadatas"] else []
    for doc, meta in zip(docs, metas):
        chunk_characters = [c for c in str(meta.get("characters", "")).split(",") if c]
        # embed.py always writes saga_available as a plain int (see
        # embed_bible_file's metadatas=[...]); the broader
        # str|int|float|bool|SparseVector|list|None union is chromadb's
        # generic metadata-value type, not a real possibility here. str()
        # first so mypy sees a type int() actually accepts.
        saga_available_raw = meta["saga_available"]
        results.append(
            Chunk(
                text=doc,
                source=str(meta["source"]),
                type=str(meta["type"]),
                saga_available=int(str(saga_available_raw)),
                characters=chunk_characters,
            )
        )

    def score(c: Chunk) -> int:
        return len(set(c.characters) & set(characters))

    results.sort(key=score, reverse=True)
    return results[:k]
