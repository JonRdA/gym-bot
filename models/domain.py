"""Pydantic models representing the core data structures of a workout."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
)
from typing_extensions import Annotated

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

def validate_objectid(value: Any) -> ObjectId:
    """Custom validator to convert str or bytes to ObjectId."""
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, (str, bytes)):
        try:
            return ObjectId(value)
        except Exception:
            pass  # Let Pydantic handle the final validation error
    
    # If the value is None (for Optional fields), return it
    if value is None:
        return value
    raise ValueError(f"Invalid ObjectId: {value}")

# 💡 Pydantic V2 Recommended way to create a custom type
# Annotated[Type, Validator]
PyObjectId = Annotated[
    ObjectId,
    BeforeValidator(validate_objectid),
    # Optional: Add serializer to convert it back to a string when exporting
    PlainSerializer(lambda v: str(v), return_type=str, when_used='json'),
    # Optional: For OpenAPI schema generation
    WithJsonSchema({"type": "string", "title": "PyObjectId"}, mode="serialization"),
]

class Training(BaseModel):
    """The top-level document for a completed training session."""
    mongo_id: Optional[PyObjectId] = Field(None, alias="_id")
    user_id: int
    date: datetime
    duration_minutes: int = Field(alias="duration")
    workouts: List[Workout] = []

    # 2. Configure Pydantic to handle the ObjectId type
    model_config = ConfigDict(
        # Allows Pydantic to map '_id' from the database to 'mongo_id' in the model
        populate_by_name=True,
        # Defines custom encoders for specific types when converting the model to JSON/dict
        json_encoders={ObjectId: str},
        arbitrary_types_allowed=True
    )

    # 3. Custom Validator (Optional but Recommended for robust handling):
    # This classmethod ensures that when data is loaded, if the input is a string,
    # it's converted to an ObjectId if the field expects ObjectId.
    @classmethod
    def __get_validators__(cls):
        yield cls.validate_objectid

