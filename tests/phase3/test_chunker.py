# tests/phase3/test_chunker.py
from pathlib import Path

from src.magic_index.chunker import chunk_bible_file

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_chunks_split_on_headings_and_bold_entries(tmp_path):
    sample = tmp_path / "sample-bible.md"
    sample.write_text(
        "# SECTION I\n\n"
        "**Alpha** *— a tag*\n\n"
        "Alpha's content here, short and plain.\n\n"
        "**Beta** *— a tag*\n\n"
        "Beta's content here, also short.\n",
        encoding="utf-8",
    )
    chunks = chunk_bible_file(str(sample), known_characters=[])
    labels = {c.source.split("::")[-1] for c in chunks}
    assert "Alpha" in labels
    assert "Beta" in labels
    alpha_chunk = next(c for c in chunks if c.source.endswith("::Alpha"))
    assert "Beta's content" not in alpha_chunk.text


def test_phasite_entries_get_isolated_saga_gates():
    bible = REPO_ROOT / "vault" / "00-Bibles" / "power-system-bible.md"
    chunks = chunk_bible_file(str(bible), known_characters=[])
    aldric_chunks = [c for c in chunks if "ALDRIC VANE" in c.source.upper()]
    serath_chunks = [c for c in chunks if "SERATH VOSS" in c.source.upper()]
    assert aldric_chunks and all(c.saga_available == 1 for c in aldric_chunks)
    assert serath_chunks and all(c.saga_available == 6 for c in serath_chunks)


def test_exactly_11_phasites_rule_is_its_own_saga1_chunk():
    bible = REPO_ROOT / "vault" / "00-Bibles" / "power-system-bible.md"
    chunks = chunk_bible_file(str(bible), known_characters=[])
    matches = [c for c in chunks if "exactly 11" in c.text]
    assert matches
    assert all(c.saga_available == 1 for c in matches)


def test_gravity_spike_gated_but_siblings_are_not():
    bible = REPO_ROOT / "vault" / "00-Bibles" / "lore-glossary-bible.md"
    chunks = chunk_bible_file(str(bible), known_characters=[])
    gravity_spike = [c for c in chunks if c.source.endswith("::Gravity Spike")]
    pressure_field = [c for c in chunks if c.source.endswith("::Pressure Field")]
    assert gravity_spike and all(c.saga_available == 3 for c in gravity_spike)
    assert pressure_field and all(c.saga_available == 1 for c in pressure_field)


def test_power_progression_stage_headings_gate_by_section_not_body():
    bible = REPO_ROOT / "vault" / "00-Bibles" / "power-system-bible.md"
    chunks = chunk_bible_file(str(bible), known_characters=[])
    stage2_chunks = [c for c in chunks if "Stage 2" in c.source]
    stage3_chunks = [c for c in chunks if "Stage 3" in c.source]
    assert stage2_chunks and all(c.saga_available == 3 for c in stage2_chunks)
    assert stage3_chunks and all(c.saga_available == 6 for c in stage3_chunks)
