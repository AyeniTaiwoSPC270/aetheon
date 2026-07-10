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


def test_technique_saga_lookup():
    assert saga_available("Pressure Field") == 1
    assert saga_available("Gravity Spike") == 3
    assert saga_available("Unknown Technique") is None


def test_techniques_for_saga_filters_correctly():
    names = {t.name for t in techniques_for_saga(1)}
    assert names == {"Pressure Field", "Kinetic Reflect"}
