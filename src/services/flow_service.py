import logging
from datetime import date
from typing import Dict, Optional

from src.models.domain import Training, TrainingName
from src.models.state import TrainingState
from src.services.program_loader import ProgramLoader

logger = logging.getLogger(__name__)

class WorkoutFlowService:
    """Manages the state and flow of active training sessions."""

    def __init__(self, program_loader: ProgramLoader):
        """
        Initializes the service.
        
        Args:
            program_loader: An instance of ProgramLoader to get training configs.
        """
        self.program_loader = program_loader
        self.active_sessions: Dict[int, TrainingState] = {}

    def start_training(self, user_id: int, training_name: TrainingName) -> str:
        """
        Begins a new training session for a user.

        Args:
            user_id: The ID of the user starting the session.
            training_name: The name of the training program to start.

        Returns:
            The first question to ask the user.
        """
        if user_id in self.active_sessions:
            return "You already have a training session in progress! Please complete or cancel it first."

        program = self.program_loader.load_program()
        training_program_config = program.get(training_name.value)

        if not training_program_config:
            logger.warning("User %d tried to start a non-existent training: %s", user_id, training_name.value)
            return f"Sorry, I don't know the training program '{training_name.value}'."

        # Create the initial Training object that we will build upon
        new_training = Training(
            user_id=user_id,
            session_date=date.today(),
            name=training_name,
            duration_minutes=0, # Will be calculated at the end
            workouts=[]
        )

        # Create and store the session state
        state = TrainingState(
            user_id=user_id,
            training_program=training_program_config,
            training_in_progress=new_training
        )
        self.active_sessions[user_id] = state
        
        logger.info("User %d started training: %s", user_id, training_name.value)

        return self._get_current_question(user_id)

    def _get_current_question(self, user_id: int) -> str:
        """Determines the next question based on the user's current state."""
        state = self.active_sessions.get(user_id)
        if not state:
            return "No active session found."

        # Check if we have finished all workouts
        if state.current_workout_index >= len(state.training_program):
            return self._finish_training(user_id)

        current_workout_config = state.training_program[state.current_workout_index]
        
        # Check if we have finished all exercises in the current workout
        if state.current_exercise_index >= len(current_workout_config["exercises"]):
            # Move to the next workout
            state.current_workout_index += 1
            state.current_exercise_index = 0
            # Recursively call to get the next question or finish
            return self._get_current_question(user_id)

        current_exercise_config = current_workout_config["exercises"][state.current_exercise_index]
        
        exercise_name = current_exercise_config["name"]
        metrics = ", ".join(current_exercise_config["metrics"])

        # This is where we format the question for the user
        question = (
            f"🏋️ Workout: *{current_workout_config['name'].upper()}*\n"
            f"➡️ Exercise: *{exercise_name.replace('_', ' ').title()}*\n\n"
            f"Please enter your set data. Required metrics: `{metrics}`"
        )
        
        return question
    
    def _finish_training(self, user_id: int) -> str:
        """Finalizes and cleans up the training session."""
        # This is where we'll save to MongoDB in the future.
        # For now, we just clean up the session.
        state = self.active_sessions.pop(user_id, None)
        if state:
            logger.info("User %d finished training.", user_id)
            # Here we would calculate duration, etc.
            return "🎉 Training complete! Well done."
        return "Could not find a session to finish."

    # NOTE: We still need a method to process user answers, like:
    # def handle_user_response(self, user_id: int, message: str) -> str:
    #     ...
    # This will be the next step.