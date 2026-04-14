import pytest
from pydantic import ValidationError

from gym_bot.config.models import ExerciseConfig, UserConfig


def _make_config(exercises: dict | None = None, workouts: dict | None = None) -> UserConfig:
    return UserConfig(
        user_id=1,
        exercises=exercises
        or {
            "pullup": ExerciseConfig(metrics=["reps", "weight"]),
            "row": ExerciseConfig(metrics=["reps"]),
            "chest2wall": ExerciseConfig(metrics=["time"]),
        },
        workouts=workouts
        or {
            "pull": ["pullup", "row"],
            "handstand": ["chest2wall"],
        },
    )


def test_exercise_config_accepts_known_metrics():
    cfg = ExerciseConfig(metrics=["reps", "weight"])

    assert cfg.metrics == ["reps", "weight"]
    assert cfg.track_rest is False


def test_exercise_config_rejects_unknown_metric():
    with pytest.raises(ValidationError, match="bogus"):
        ExerciseConfig(metrics=["reps", "bogus"])


def test_user_config_rejects_workout_referencing_unknown_exercise():
    with pytest.raises(ValidationError, match="ghost"):
        UserConfig(
            user_id=1,
            exercises={"pullup": ExerciseConfig(metrics=["reps"])},
            workouts={"pull": ["pullup", "ghost"]},
        )


def test_resolve_workout_returns_configs_in_declared_order():
    cfg = _make_config()

    resolved = cfg.resolve_workout("pull")

    assert [name for name, _ in resolved] == ["pullup", "row"]
    assert all(isinstance(c, ExerciseConfig) for _, c in resolved)


def test_resolve_workout_returns_empty_for_unknown_workout():
    cfg = _make_config()

    assert cfg.resolve_workout("missing") == []


def test_get_exercise_returns_none_for_unknown_name():
    cfg = _make_config()

    assert cfg.get_exercise("missing") is None


def test_get_workouts_for_exercise_finds_every_containing_workout():
    cfg = _make_config(
        exercises={"pushup": ExerciseConfig(metrics=["reps"])},
        workouts={"push": ["pushup"], "home": ["pushup"]},
    )

    assert sorted(cfg.get_workouts_for_exercise("pushup")) == ["home", "push"]


def test_get_workouts_for_exercise_returns_empty_when_unused():
    cfg = _make_config()

    assert cfg.get_workouts_for_exercise("chest2wall") == ["handstand"]
    assert cfg.get_workouts_for_exercise("nothing") == []


def test_workout_names_lists_all_workouts():
    cfg = _make_config()

    assert set(cfg.workout_names) == {"pull", "handstand"}
