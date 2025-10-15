"""Pydantic models representing the core data structures of a workout."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from models.enums import ExerciseName, Metric, WorkoutName


class WoSet(BaseModel):
    """A single set that has been performed."""
    metrics: Dict[Metric, Any]


class Exercise(BaseModel):
    """An exercise that has been performed."""
    name: ExerciseName
    rest_time_seconds: Optional[int] = Field(default=None, alias="rest_time")
    sets: List[WoSet] = []


class Workout(BaseModel):
    """A workout session that has been performed."""
    name: WorkoutName
    completed: bool
    exercises: List[Exercise] = []


class Training(BaseModel):
    """The top-level document for a completed training session."""
    user_id: int
    date: datetime
    duration_minutes: int = Field(alias="duration")
    workouts: List[Workout] = []
