import io
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import matplotlib
import pytest

matplotlib.use("Agg")

from gym_bot.config.models import ExerciseConfig, UserConfig
from gym_bot.reporting.exercise_reports import (
    _NO_REST_COLOR,
    ExerciseReportingService,
    _bar_width,
    _format_pace,
    _per_session,
    _rest_color,
)


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


def test_per_session_keeps_rest_aligned_with_kept_sessions():
    base = datetime(2026, 4, 1)
    sessions = [
        {"date": base, "sets": [{"reps": 5}], "rest": 120},
        {"date": base + timedelta(days=1), "sets": [{"reps": 0}], "rest": 60},
        {"date": base + timedelta(days=2), "sets": [{"reps": 8}], "rest": None},
    ]

    series = _per_session(sessions, lambda sets: sum(m["reps"] for m in sets))

    assert series.values == [5, 8]
    assert series.rests == [120, None]


def test_rest_color_clamps_to_scale_ends_and_greys_missing():
    assert _rest_color(None) == _NO_REST_COLOR
    assert _rest_color(30) == _rest_color(60)
    assert _rest_color(600) == _rest_color(300)
    assert _rest_color(60) != _rest_color(300)


def test_bar_width_follows_tightest_session_gap():
    base = datetime(2026, 4, 1, 18)
    assert _bar_width([base, base + timedelta(days=5), base + timedelta(days=15)]) == 4.0
    assert _bar_width([base]) == 0.7
    assert _bar_width([base, base + timedelta(hours=2)]) == 0.7


@pytest.mark.parametrize("rest", [None, 120])
def test_bar_reports_render_with_and_without_rest(rest):
    sessions = _sessions([[{"reps": 5, "weight": 100}], [{"reps": 5, "weight": 110}]], rest=rest)

    result = _svc()._report_total_volume(sessions, "backsquat")

    _assert_chart_and_text(result)


def test_bar_report_renders_mixed_rest_and_missing():
    sessions = _sessions([[{"reps": 10}], [{"reps": 12}], [{"reps": 11}]])
    sessions[1]["rest"] = 90

    result = _svc()._report_total_reps(sessions, "pullup")

    _assert_chart_and_text(result)


def test_run_report_derives_pace_distance_and_climb():
    sessions = _sessions(
        [
            [{"time_min": 30, "distance": 5000.0, "elevation": 50}],  # 6:00 /km
            [{"time_min": 55, "distance": 10000.0, "elevation": 120}],  # 5:30 /km
            [{"time_min": 25, "distance": 4000.0, "elevation": 20}],  # 6:15 /km
        ]
    )

    result = _svc()._report_run(sessions, "run")

    _assert_chart_and_text(result)
    assert "Runs: *3* (19.0 km total)" in result["text"]
    assert "Best pace: *5:30 /km* (10.0 km)" in result["text"]
    assert "Longest run: *10.0 km*" in result["text"]
    assert "Last run: *4.0 km at 6:15 /km*, 20 m climb" in result["text"]


def test_run_report_sums_split_sets_into_one_run():
    sessions = _sessions(
        [[{"time_min": 12, "distance": 2000.0, "elevation": 10}, {"time_min": 18, "distance": 3000.0, "elevation": 15}]]
    )

    result = _svc()._report_run(sessions, "run")

    _assert_chart_and_text(result)
    assert "Runs: *1* (5.0 km total)" in result["text"]
    assert "Best pace: *6:00 /km*" in result["text"]


def test_run_report_renders_without_elevation():
    sessions = _sessions([[{"time_min": 30, "distance": 5000.0}], [{"time_min": 28, "distance": 5000.0}]])

    result = _svc()._report_run(sessions, "run")

    _assert_chart_and_text(result)


def test_run_report_skips_sessions_without_distance_or_time():
    sessions = _sessions([[{"time_min": 30, "distance": 0.0}], [{"time_min": 0, "distance": 5000.0}]])

    result = _svc()._report_run(sessions, "run")

    assert "No run data" in result["text"]
    assert "chart" not in result


@pytest.mark.parametrize("pace, expected", [(6.0, "6:00"), (5.5, "5:30"), (4.999, "5:00"), (5 + 59.6 / 60, "6:00")])
def test_format_pace(pace, expected):
    assert _format_pace(pace) == expected


@pytest.mark.parametrize(
    "exercise_config, expected",
    [
        (ExerciseConfig(metrics=["reps"]), {("total_reps", "Total Reps")}),
        (ExerciseConfig(metrics=["reps", "feet2floor"]), {("total_reps", "Total Reps")}),
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
        (
            ExerciseConfig(metrics=["time_min", "distance", "elevation"]),
            {("run", "Run")},
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
