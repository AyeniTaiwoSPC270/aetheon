from src.magic_index.query import query_lore


def test_phasite_count_query_surfaces_exactly_11(indexed_client):
    # Top-3 tolerance, not strict top-1: embedding rank order for a
    # paraphrased question isn't perfectly predictable by hand, and the
    # requirement that matters is "the fact is retrievable near the top,"
    # not "it's always literally result[0]."
    results = query_lore("How many Phasites exist?", saga=8, client=indexed_client)
    assert results
    top = results[0]
    assert "power-system-bible" in top.source
    combined_top3 = " ".join(r.text for r in results[:3])
    assert "exactly 11" in combined_top3


def test_aldric_techniques_saga1_excludes_gravity_spike(indexed_client):
    results = query_lore(
        "What techniques does Aldric use?", saga=1, characters=["Aldric Vane"], client=indexed_client
    )
    assert results
    assert all(r.saga_available <= 1 for r in results)
    combined = " ".join(r.text for r in results)
    assert "Pressure Field" in combined
    assert "Kinetic Reflect" in combined
    assert "Gravity Spike" not in combined


def test_mira_solh_excluded_at_saga_1(indexed_client):
    results = query_lore("Tell me about Mira Solh's wound transfer ability", saga=1, client=indexed_client)
    assert all(r.saga_available <= 1 for r in results)
    assert not any("Wound Transfer" in r.text for r in results)
