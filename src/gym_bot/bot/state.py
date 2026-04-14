from dataclasses import dataclass, field
from typing import Optional

from gym_bot.config.models import ExerciseConfig
from gym_bot.domain.models import Exercise, ExerciseSet, Training, Workout


@dataclass
class AddTrainingState:
    training: Optional[Training] = None
    current_exercises: list[tuple[str, ExerciseConfig]] = field(default_factory=list)
    current_workout: Optional[Workout] = None
    current_exercise_idx: int = 0
    current_exercise: Optional[Exercise] = None
    last_set: Optional[ExerciseSet] = None


@dataclass
class ReportState:
    t0: object = None
    t1: object = None
    days: int = 0
    exercise_name: Optional[str] = None


_ADD_KEY = "_add_training"
_REPORT_KEY = "_exercise_report"
_CALENDAR_KEY = "_calendar"


def get_add_state(context) -> AddTrainingState:
    if _ADD_KEY not in context.user_data:
        context.user_data[_ADD_KEY] = AddTrainingState()
    return context.user_data[_ADD_KEY]


def clear_add_state(context) -> None:
    context.user_data.pop(_ADD_KEY, None)


def get_report_state(context) -> ReportState:
    if _REPORT_KEY not in context.user_data:
        context.user_data[_REPORT_KEY] = ReportState()
    return context.user_data[_REPORT_KEY]


def clear_report_state(context) -> None:
    context.user_data.pop(_REPORT_KEY, None)


def get_calendar_months(context) -> int:
    return context.user_data.get(_CALENDAR_KEY, 1)


def set_calendar_months(context, months: int) -> None:
    context.user_data[_CALENDAR_KEY] = months


def clear_calendar_state(context) -> None:
    context.user_data.pop(_CALENDAR_KEY, None)
