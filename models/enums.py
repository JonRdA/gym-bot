"""Contains all the Enum definitions for the application domain."""

from enum import Enum


class Unit(str, Enum):
    """Units for metrics."""
    S = "s"
    CM = "cm"
    KG = "kg"
    REPS = ""


class Metric(str, Enum):
    """Metrics that can be tracked in an exercise set."""
    REPS = ("reps", Unit.REPS)
    WEIGHT = ("weight", Unit.KG)
    THIGH2FLOOR = ("thigh2floor", Unit.CM)
    KNEE2FLOOR = ("knee2floor", Unit.CM)
    FEET2FLOOR = ("feet2floor", Unit.CM)
    TIME = ("time", Unit.S)

    def __new__(cls, value: str, unit: Unit | None):
        """Override __new__ to allow attaching a unit to each metric."""
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.unit = unit
        return obj


class WorkoutName(str, Enum):
    """Enum for the names of individual workouts within a training session."""
    PULL = "pull"
    PUSH = "push"
    FRONTSPLIT = "frontsplit"
    LOWER = "lower"
    HANDSTAND = "handstand"
    HOME = "home"


class ExerciseName(str, Enum):
    """Enum for the names of specific exercises."""
    # upper
    PULLUP = "pullup"
    DIP = "dip"
    PIKE_PUSHUP = "pike_pushup"
    PRESS = "press"

    # frontsplit
    WIDE_SPLIT_SQUAT = "wide_split_squat"
    JEFFERSON_CURL = "jefferson_curl"
    GOODMORNING = "goodmorning"

    # lower
    SHRIMP = "shrimp"
    BACKSQUAT = "backsquat"
    DEADLIFT = "deadlift"
    STRIDE_STANCE_DEADLIFT = "stride_stance_deadlift"
    SISSY_SQUAT = "sissy_squat"
    COSSACK_SQUAT = "cossack_squat"

    # mov-gh
    BRIDGE = "bridge"
    CHEST2WALL = "chest2wall"

    # home
    RICE_BUCKET = "rice_bucket"
    HEEL_ELEVATION = "heel_elevation"
    SQUAT2SISSY = "squat2sissy"
    TOWEL_ROLL = "towel_roll"

