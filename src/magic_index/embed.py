"""Embed Aethon bible chunks into a local, persisted ChromaDB collection
(BUILD_PLAN.md §8, D5 — RAG, not fine-tuning; $0 cost)."""
from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.api import ClientAPI
from chromadb.utils import embedding_functions

from src.checks.name_registry import KNOWN_CHARACTERS
from src.magic_index.chunker import chunk_bible_file

VAULT_BIBLES_DIR = Path(__file__).resolve().parents[2] / "vault" / "00-Bibles"
CHROMA_DIR = Path(__file__).resolve().parents[2] / ".chroma"
COLLECTION_NAME = "aethon_bibles"

_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-small-en-v1.5"
)


def get_client(persist_dir: Path = CHROMA_DIR) -> ClientAPI:
    return chromadb.PersistentClient(path=str(persist_dir))


def get_collection(client: ClientAPI) -> chromadb.Collection:
    # NOTE: the ignore below works around a chromadb 1.5.9 stub issue, not a
    # real type error. Its EmbeddingFunction generic is contravariant, so
    # EmbeddingFunction[list[str]] is only a subtype of
    # EmbeddingFunction[list[str] | list[ndarray]] if the latter is a subtype
    # of list[str] — which it isn't (list[ndarray] doesn't qualify). So
    # SentenceTransformerEmbeddingFunction doesn't structurally satisfy
    # get_or_create_collection's parameter type even though this is the
    # library's own documented usage.
    return client.get_or_create_collection(
        name=COLLECTION_NAME, embedding_function=_embedding_fn  # type: ignore[arg-type]
    )


def embed_bible_file(path: Path, client: ClientAPI | None = None) -> int:
    """(Re)embed one bible file: deletes its existing chunks by source
    file, then inserts freshly chunked+tagged text. Returns chunk count."""
    client = client or get_client()
    collection = get_collection(client)
    stem = path.stem

    existing = collection.get(where={"source_file": stem})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    chunks = chunk_bible_file(str(path), KNOWN_CHARACTERS)
    if not chunks:
        return 0

    collection.add(
        ids=[f"{stem}::{i}" for i in range(len(chunks))],
        documents=[c.text for c in chunks],
        metadatas=[
            {
                "source": c.source,
                "source_file": stem,
                "type": c.type,
                "saga_available": c.saga_available,
                "characters": ",".join(c.characters),
                "hard_rule": c.hard_rule,
            }
            for c in chunks
        ],
    )
    return len(chunks)


def embed_all_bibles(client: ClientAPI | None = None) -> dict[str, int]:
    client = client or get_client()
    counts: dict[str, int] = {}
    for path in sorted(VAULT_BIBLES_DIR.glob("*.md")):
        counts[path.stem] = embed_bible_file(path, client)
    return counts
