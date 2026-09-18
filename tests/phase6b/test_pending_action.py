from src.telegram.pending_action import PendingAction, pop_pending, set_pending


def test_set_then_pop_returns_the_action():
    set_pending(101, PendingAction(kind="revise_chapter", target="14"))

    result = pop_pending(101)

    assert result == PendingAction(kind="revise_chapter", target="14")


def test_pop_clears_the_pending_state():
    set_pending(102, PendingAction(kind="modify_proposal", target="ch14-solen.md"))
    pop_pending(102)

    assert pop_pending(102) is None


def test_pop_when_never_set_returns_none():
    assert pop_pending(999999) is None


def test_set_overwrites_a_previous_pending_action():
    set_pending(103, PendingAction(kind="revise_chapter", target="1"))
    set_pending(103, PendingAction(kind="revise_chapter", target="2"))

    assert pop_pending(103) == PendingAction(kind="revise_chapter", target="2")
