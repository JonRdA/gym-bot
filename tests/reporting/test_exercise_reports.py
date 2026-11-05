import io
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import matplotlib
import pytest

matplotlib.use("Agg")

from gym_bot.config.models import ExerciseConfig, UserConfig
from gym_bot.reporting.exercise_reports import ExerciseReportingService


def _svc() -> ExerciseReportingService:
    return ExerciseReportingService(training_repo=None, config_service=None)  # type: ignore[arg-type]


def _sessions(values_per_day: list[list[dict]], rest: int | None = None) -> list[dict]:
    base = datetime(2026, 4, 1)
    return [
        {"date": base + timedelta(days=i), "sets": sets, "rest": rest}
        for i, sets in enumerate(values_per_day)
    ]


def _assert_chart_and_text(result: dict) -> None:
    assert isinstance(result["text"], str) and result["text"]
    assert isinstance(result["chart"], io.BytesIO)
    assert result["chart"].getvalue()  # non-empty PNG bytes


def test_total_reps_sums_reps_per_session():
    sessions = _sessions(
        [
            [{"reps": 10}, {"reps": 8}],
            [{"reps": 5}, {"reps": 5}, {"reps": 5}],
        ]
    )

    result = _svc()._report_total_reps(sessions, "pullup")

    _assert_chart_and_text(result)
    assert "Max reps in a day: *18*" in result["text"]
    assert "Last session: *15*" in result["text"]


def test_total_reps_returns_text_only_when_all_sessions_are_empty():
    sessions = _sessions([[{"reps": 0}]])

    result = _svc()._report_total_reps(sessions, "pullup")

    assert "No reps data" in result["text"]
    assert "chart" not in result


def test_total_volume_multiplies_reps_by_weight():
    sessions = _sessions(
        [
            [{"reps": 5, "weight": 100}, {"reps": 5, "weight": 100}],  # 1000
            [{"reps": 4, "weight": 120}],  # 480
        ]
    )

    result = _svc()._report_total_volume(sessions, "backsquat")

    _assert_chart_and_text(result)
    assert "2 sessions" in result["text"]
    assert "1,000" in result["text"]  # max volume


def test_max_weight_picks_heaviest_set_per_session():
    sessions = _sessions(
        [
            [{"reps": 5, "weight": 80}, {"reps": 3, "weight": 95}],
            [{"reps": 5, "weight": 100}],
        ]
    )

    result = _svc()._report_max_weight(sessions, "backsquat")

    _assert_chart_and_text(result)
    assert "All-time max: *100.0 kg*" in result["text"]
    assert "Last session: *100.0 kg*" in result["text"]


def test_total_time_sums_time_metric():
    sessions = _sessions(
        [
            [{"time": 30}, {"time": 45}],
            [{"time": 60}],
        ]
    )

    result = _svc()._report_total_time(sessions, "chest2wall")

    _assert_chart_and_text(result)
    assert "Max total in a day: *75s*" in result["text"]
    assert "Last session: *60s*" in result["text"]


def test_max_time_picks_longest_hold_per_session():
    sessions = _sessions(
        [
            [{"time": 30}, {"time": 45}, {"time": 40}],
            [{"time": 50}],
        ]
    )

    result = _svc()._report_max_time(sessions, "chest2wall")

    _assert_chart_and_text(result)
    assert "All-time max: *50s*" in result["text"]


@pytest.mark.parametrize(
    "exercise_config, expected",
    [
        (ExerciseConfig(metrics=["reps"]), set()),
        (
            ExerciseConfig(metrics=["reps", "weight"]),
            {
                ("total_volume", "Total Volume"),
                ("max_weight", "Max Weight"),
            },
        ),
        (
            ExerciseConfig(metrics=["time"]),
            {("total_time", "Total Time"), ("max_time", "Max Time")},
        ),
    ],
)
async def test_get_available_reports_from_metric_combinations(exercise_config, expected):
    config = UserConfig(
        user_id=1,
        exercises={"ex": exercise_config},
        workouts={"w": ["ex"]},
    )
    config_service = AsyncMock()
    config_service.get_config.return_value = config
    svc = ExerciseReportingService(training_repo=None, config_service=config_service)  # type: ignore[arg-type]

    reports = await svc.get_available_reports(user_id=1, exercise_name="ex")

    assert set(reports) == expected


async def test_get_available_reports_ignores_track_rest():
    config = UserConfig(
        user_id=1,
        exercises={"pullup": ExerciseConfig(metrics=["reps", "weight"], track_rest=True)},
        workouts={"pull": ["pullup"]},
    )
    config_service = AsyncMock()
    config_service.get_config.return_value = config
    svc = ExerciseReportingService(training_repo=None, config_service=config_service)  # type: ignore[arg-type]

    reports = await svc.get_available_reports(user_id=1, exercise_name="pullup")

    assert set(reports) == {("total_volume", "Total Volume"), ("max_weight", "Max Weight")}


async def test_get_available_reports_returns_empty_for_unknown_exercise():
    config = UserConfig(
        user_id=1,
        exercises={"pullup": ExerciseConfig(metrics=["reps"])},
        workouts={"pull": ["pullup"]},
    )
    config_service = AsyncMock()
    config_service.get_config.return_value = config
    svc = ExerciseReportingService(training_repo=None, config_service=config_service)  # type: ignore[arg-type]

    reports = await svc.get_available_reports(user_id=1, exercise_name="nope")

    assert reports == []
