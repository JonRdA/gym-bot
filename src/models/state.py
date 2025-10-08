from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.models.domain import Training, TrainingName, WoSet


class TrainingState(BaseModel):
    """Represents the current state of an active training session for a user."""
    user_id: int
    training_program: list
    
    # Track what the bot is currently asking the user for
    awaiting_input_type: str = "date" # Can be: date, duration, set_data, rest_time
    
    # Temporarily store data before creating the final Training object
    selected_training_name: TrainingName
    selected_date: Optional[date] = None
    
    # Pointers to the user's current position in the training
    current_workout_index: int = 0
    current_exercise_index: int = 0
    
    # The final Training object, created after date/duration are provided
    training_in_progress: Optional[Training] = None
    
    # Used to implement the 'repeat' command
    last_logged_set: Optional[WoSet] = None
    
    start_time: datetime = Field(default_factory=datetime.now)