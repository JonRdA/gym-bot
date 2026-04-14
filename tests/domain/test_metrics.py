import pytest

from gym_bot.domain.metrics import METRIC_REGISTRY, format_metric_prompt, get_metric


def test_get_metric_returns_definition_for_known_name():
    defn = get_metric("weight")

    assert defn.name == "weight"
    assert defn.unit == "kg"
    assert defn.value_type is float


def test_get_metric_raises_for_unknown_name():
    with pytest.raises(KeyError, match="nope"):
        get_metric("nope")


def test_format_metric_prompt_includes_unit_when_present():
    assert format_metric_prompt(["weight"]) == "<weight(kg)>"


def test_format_metric_prompt_omits_unit_when_empty():
    assert format_metric_prompt(["reps"]) == "<reps>"


def test_format_metric_prompt_joins_multiple_metrics_in_order():
    assert format_metric_prompt(["reps", "weight"]) == "<reps> <weight(kg)>"


def test_registry_is_consistent_with_get_metric():
    for name in METRIC_REGISTRY:
        assert get_metric(name) is METRIC_REGISTRY[name]
