import pytest

from gym_bot.bot import callbacks
from gym_bot.bot.callbacks import make_callback, parse_callback

_PREFIXES = [
    callbacks.ADD_WORKOUT,
    callbacks.FINISH_TRAINING,
    callbacks.COMPLETED,
    callbacks.CALENDAR_FILTER,
    callbacks.SELECT_SESSION,
    callbacks.SELECT_EXERCISE,
    callbacks.REPORT_TYPE,
]


@pytest.mark.parametrize("prefix", _PREFIXES)
def test_make_and_parse_round_trip(prefix):
    data = make_callback(prefix, "pull")

    assert parse_callback(data) == (prefix, "pull")


def test_parse_callback_splits_on_first_colon_only():
    # A value that itself contains a colon must survive intact.
    data = make_callback("ex", "biceps:curl")

    prefix, value = parse_callback(data)

    assert prefix == "ex"
    assert value == "biceps:curl"


def test_parse_callback_handles_missing_separator():
    prefix, value = parse_callback("noseparator")

    assert prefix == "noseparator"
    assert value == ""
