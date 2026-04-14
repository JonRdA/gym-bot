from types import SimpleNamespace

from gym_bot.bot.state import (
    AddTrainingState,
    ReportState,
    clear_add_state,
    clear_calendar_state,
    clear_report_state,
    get_add_state,
    get_calendar_months,
    get_report_state,
    set_calendar_months,
)


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(user_data={})


def test_get_add_state_creates_fresh_instance_then_returns_same_one():
    ctx = _ctx()

    first = get_add_state(ctx)
    second = get_add_state(ctx)

    assert isinstance(first, AddTrainingState)
    assert first is second


def test_clear_add_state_drops_instance_so_next_get_is_fresh():
    ctx = _ctx()
    original = get_add_state(ctx)

    clear_add_state(ctx)
    new = get_add_state(ctx)

    assert new is not original


def test_clear_add_state_is_safe_when_nothing_stored():
    ctx = _ctx()

    clear_add_state(ctx)  # must not raise


def test_get_report_state_creates_and_reuses_instance():
    ctx = _ctx()

    first = get_report_state(ctx)
    second = get_report_state(ctx)

    assert isinstance(first, ReportState)
    assert first is second


def test_clear_report_state_drops_instance():
    ctx = _ctx()
    original = get_report_state(ctx)

    clear_report_state(ctx)

    assert get_report_state(ctx) is not original


def test_calendar_months_defaults_to_one():
    assert get_calendar_months(_ctx()) == 1


def test_set_and_get_calendar_months_round_trip():
    ctx = _ctx()

    set_calendar_months(ctx, 3)

    assert get_calendar_months(ctx) == 3


def test_clear_calendar_state_resets_to_default():
    ctx = _ctx()
    set_calendar_months(ctx, 6)

    clear_calendar_state(ctx)

    assert get_calendar_months(ctx) == 1
