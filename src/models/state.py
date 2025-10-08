from datetime import datetime

from pydantic import BaseModel, Field

from src.models.domain import Training


class TrainingState(BaseModel):
    """Represents the current state of an active training session for a user."""
    user_id: int
    training_program: list # The list of workouts/exercises from the YAML config
    
    # Pointers to the user's current position in the training
    current_workout_index: int = 0
    current_exercise_index: int = 0
    
    # The final Training object we are building
    training_in_progress: Training
    
    start_time: datetime = Field(default_factory=datetime.now)