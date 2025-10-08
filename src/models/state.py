from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.models.domain import Training, WoSet


class TrainingState(BaseModel):
    """Represents the current state of an active training session for a user."""
    user_id: int
    training_program: list
    
    # Pointers to the user's current position
    current_workout_index: int = 0
    current_exercise_index: int = 0
    
    # The final Training object we are building
    training_in_progress: Training
    
    # Used to implement the 'repeat' command
    last_logged_set: Optional[WoSet] = None

    # Flag to handle rest time
    awaiting_rest_time: bool = False
    
    start_time: datetime = Field(default_factory=datetime.now)