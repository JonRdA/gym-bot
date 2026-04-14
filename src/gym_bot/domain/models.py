from datetime import datetime
from typing import Any, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer, WithJsonSchema
from typing_extensions import Annotated


def _validate_object_id(value: Any) -> ObjectId | None:
    if value is None:
        return None
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, (str, bytes)):
        return ObjectId(value)
    raise ValueError(f"Invalid ObjectId: {value}")


PyObjectId = Annotated[
    ObjectId,
    BeforeValidator(_validate_object_id),
    PlainSerializer(lambda v: str(v), return_type=str, when_used="json"),
    WithJsonSchema({"type": "string"}, mode="serialization"),
]


class ExerciseSet(BaseModel):
    metrics: dict[str, int | float]


class Exercise(BaseModel):
    name: str
    rest_time: Optional[int] = Field(default=None, alias="rest_time")
    sets: list[ExerciseSet] = []


class Workout(BaseModel):
    name: str
    completed: bool
    exercises: list[Exercise] = []


class Training(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[PyObjectId] = Field(None, alias="_id")
    user_id: int
    date: datetime
    duration: int
    workouts: list[Workout] = []
