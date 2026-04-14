from datetime import datetime

from gym_bot.domain.models import Exercise, ExerciseSet, Training, Workout
from gym_bot.reporting.service import ReportingService


def _svc() -> ReportingService:
    # Neither method under test touches the repo or settings.
    return ReportingService(training_repo=None, settings=None)  # type: ignore[arg-type]


def _training(**overrides) -> Training:
    base = dict(
        user_id=1,
        date=datetime(2026, 4, 1, 18, 30),
        duration=45,
        workouts=[],
    )
    base.update(overrides)
    return Training(**base)


def test_format_training_summary_shows_date_duration_and_workout_names():
    t = _training(
        workouts=[
            Workout(name="pull", completed=True),
            Workout(name="lower", completed=False),
        ]
    )

    out = _svc().format_training_summary(t)

    assert "2026-04-01" in out
    assert "45 min" in out
    assert "Pull" in out and "Lower" in out


def test_format_training_details_renders_workout_completion_status():
    t = _training(
        workouts=[Workout(name="pull", completed=True), Workout(name="push", completed=False)]
    )

    out = _svc().format_training_details(t)

    assert "*Pull*" in out and "(completed)" in out
    assert "*Push*" in out and "(not completed)" in out


def test_format_training_details_notes_empty_workout():
    t = _training(workouts=[Workout(name="pull", completed=True)])

    out = _svc().format_training_details(t)

    assert "No exercises logged" in out


def test_format_training_details_notes_empty_exercise():
    t = _training(
        workouts=[
            Workout(
                name="pull",
                completed=True,
                exercises=[Exercise(name="pullup", sets=[])],
            )
        ]
    )

    out = _svc().format_training_details(t)

    assert "Pullup" in out and "No sets" in out


def test_format_training_details_numbers_sets_from_one():
    t = _training(
        workouts=[
            Workout(
                name="pull",
                completed=True,
                exercises=[
                    Exercise(
                        name="pullup",
                        sets=[
                            ExerciseSet(metrics={"reps": 10}),
                            ExerciseSet(metrics={"reps": 8}),
                            ExerciseSet(metrics={"reps": 6}),
                        ],
                    )
                ],
            )
        ]
    )

    out = _svc().format_training_details(t)

    assert "#1 → 10" in out
    assert "#2 → 8" in out
    assert "#3 → 6" in out
