from src.checks.name_registry import find_near_misses
from src.checks.technique_registry import saga_available, techniques_for_saga


def test_exact_canonical_names_not_flagged():
    assert find_near_misses("Aldric Vane walked through Valdris Prime.") == []


def test_near_miss_valdenmeer_flagged():
    misses = find_near_misses("He came from Valdenmeer.")
    assert any(m.canonical == "Valdenmere" and m.found == "Valdenmeer" for m in misses)


def test_near_miss_greyvale_academy_flagged():
    misses = find_near_misses("He studied at Greyvale Academy.")
    assert any(m.canonical == "Greyveil Academy" and m.found == "Greyvale Academy" for m in misses)


# Regression tests (final whole-branch review): find_near_misses() was
# flagging ordinary English words and legitimate new character names as
# near-misses of short canonical names (<=6 chars), because at edit
# distance 1 almost any similar-length capitalized word matches. Short
# canonical names are now excluded from fuzzy scanning entirely
# (_MIN_FUZZY_NAME_LENGTH in name_registry.py) — only exact matches count
# for them.


def test_stolen_not_flagged_as_near_miss_of_solen():
    assert find_near_misses("Stolen goods lined the cart.") == []


def test_ryan_not_flagged_as_near_miss_of_rynn():
    assert find_near_misses("Ryan walked in.") == []


def test_doran_and_baran_not_flagged_as_near_miss_of_daran():
    assert find_near_misses("Doran and Baran argued in the hall.") == []


def test_daren_and_soren_not_flagged_as_near_misses():
    assert find_near_misses("Daren looked up. Soren said nothing.") == []


def test_technique_saga_lookup():
    assert saga_available("Pressure Field") == 1
    assert saga_available("Gravity Spike") == 3
    assert saga_available("Unknown Technique") is None


def test_techniques_for_saga_filters_correctly():
    names = {t.name for t in techniques_for_saga(1)}
    assert names == {"Pressure Field", "Kinetic Reflect"}
