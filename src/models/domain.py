from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# --- Enums ---

class TrainingName(str, Enum):
    UPPER_FRONTSPLIT = "upper_frontsplit"
    LOWER_MOVGH = "lower_movgh"
    HOME = "home"
    MISC = "misc"

class Metric(str, Enum):
    REPS = "reps"
    WEIGHT = "weight"
    THIGH2FLOOR = "thigh2floor"
    KNEE2FLOOR = "knee2floor"
    FEET2FLOOR = "feet2floor"
    TIME = "time"

class WorkoutName(str, Enum):
    UPPER = "upper"
    FRONTSPLIT = "frontsplit"
    LOWER = "lower"
    MOV_GH = "movgh"
    HOME = "home"

class ExerciseName(str, Enum):
    # upper
    PULLUP = "pullup"
    DIP = "dip"
    PIKE_PUSHUP = "pike_pushup"
    # frontsplit
    WIDE_SPLIT_SQUAT = "wide_split_squat"
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

# --- Pydantic Models ---

class WoSet(BaseModel):
    """A single set that has been performed."""
    metrics: Dict[Metric, Any]

class Exercise(BaseModel):
    """An exercise that has been performed."""
    name: ExerciseName
    rest_time_sec: Optional[int] = None
    sets: List[WoSet]

class Workout(BaseModel):
    """A workout session that has been performed."""
    name: WorkoutName
    completed: bool = True
    exercises: List[Exercise]

class Training(BaseModel):
    """The top-level document for a completed training session."""
    user_id: int
    session_date: date
    name: TrainingName
    duration_minutes: int
    workouts: List[Workout]