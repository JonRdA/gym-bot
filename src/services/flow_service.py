import logging
from datetime import date, datetime
from typing import Dict

from src.models.domain import (
    Exercise,
    ExerciseName,
    Metric,
    Training,
    TrainingName,
    Workout,
    WorkoutName,
    WoSet,
)
from src.models.state import TrainingState
from src.services.input_parser import InputParser, SpecialCommand
from src.services.mongo_service import MongoService
from src.services.program_loader import ProgramLoader

logger = logging.getLogger(__name__)

class WorkoutFlowService:
    """Manages the state and flow of active training sessions."""

    def __init__(self, program_loader: ProgramLoader, mongo_service: MongoService, input_parser: InputParser):
        """Initializes the service with its dependencies."""
        self.program_loader = program_loader
        self.mongo_service = mongo_service
        self.input_parser = input_parser
        self.active_sessions: Dict[int, TrainingState] = {}

    def start_training(self, user_id: int, training_name: TrainingName) -> str:
        """Begins a new training session for a user."""
        if user_id in self.active_sessions:
            return "You already have a training session in progress! Please complete or cancel it first."

        program = self.program_loader.load_program()
        training_program_config = program.get(training_name.value)
        if not training_program_config:
            return f"Sorry, I don't know the training program '{training_name.value}'."
        
        # Create the initial structures
        new_training = Training(user_id=user_id, date=date.today(), name=training_name, duration=0, workouts=[])
        state = TrainingState(user_id=user_id, training_program=training_program_config, training_in_progress=new_training)
        self.active_sessions[user_id] = state
        
        self._prepare_current_structures(state)
        logger.info("User %d started training: %s", user_id, training_name.value)
        return self._get_current_question(user_id)

    def handle_user_response(self, user_id: int, message_text: str) -> str:
        """Processes a user's text message and returns the next bot message."""
        state = self.active_sessions.get(user_id)
        if not state:
            return "You don't have an active training session. Use /startlog to begin."

        current_exercise_config = self._get_current_exercise_config(state)
        expected_metrics = [Metric(m) for m in current_exercise_config["metrics"]]

        parse_result = self.input_parser.parse(message_text, expected_metrics)

        if parse_result.error_message:
            return parse_result.error_message
        
        # Handle parsed commands or data
        if parse_result.data == SpecialCommand.DONE_EXERCISE:
            state.current_exercise_index += 1
            state.last_logged_set = None # Reset for next exercise
            self._prepare_current_structures(state)
            return self._get_current_question(user_id)
            
        elif parse_result.data == SpecialCommand.REPEAT_SET:
            if not state.last_logged_set:
                return "There is no previous set to repeat."
            set_to_add = state.last_logged_set
        
        else: # It's parsed metric data
            set_to_add = WoSet(metrics=parse_result.data)

        # Add the set to the training object and update state
        state.training_in_progress.workouts[-1].exercises[-1].sets.append(set_to_add)
        state.last_logged_set = set_to_add
        
        return "✅ Set logged! Enter next set, or type 'done'."

    def _get_current_question(self, user_id: int) -> str:
        """Determines the next question based on the user's current state."""
        state = self.active_sessions.get(user_id)
        
        if state.current_workout_index >= len(state.training_program):
            return self._finish_training(user_id)

        workout_config = state.training_program[state.current_workout_index]
        if state.current_exercise_index >= len(workout_config["exercises"]):
            state.current_workout_index += 1
            state.current_exercise_index = 0
            self._prepare_current_structures(state)
            return self._get_current_question(user_id) # Recursive call for next workout/finish

        exercise_config = self._get_current_exercise_config(state)
        exercise_name = exercise_config["name"]
        metrics = ", ".join(exercise_config["metrics"])

        return (
            f"🏋️ Workout: *{workout_config['name'].upper()}*\n"
            f"➡️ Exercise: *{exercise_name.replace('_', ' ').title()}*\n\n"
            f"Enter metrics for your set ({metrics}), or type 'done'."
        )

    def _prepare_current_structures(self, state: TrainingState):
        """Ensures the Workout and Exercise objects exist in the state before adding sets."""
        if state.current_workout_index >= len(state.training_program):
            return # Finished

        # Ensure current workout object exists
        if len(state.training_in_progress.workouts) <= state.current_workout_index:
            workout_config = state.training_program[state.current_workout_index]
            state.training_in_progress.workouts.append(
                Workout(name=WorkoutName(workout_config["name"]), exercises=[])
            )
        
        current_workout = state.training_in_progress.workouts[state.current_workout_index]
        workout_config = state.training_program[state.current_workout_index]

        if state.current_exercise_index >= len(workout_config["exercises"]):
            return # Finished with this workout's exercises

        # Ensure current exercise object exists
        if len(current_workout.exercises) <= state.current_exercise_index:
            exercise_config = self._get_current_exercise_config(state)
            current_workout.exercises.append(
                Exercise(name=ExerciseName(exercise_config["name"]), sets=[])
            )

    def _get_current_exercise_config(self, state: TrainingState) -> dict:
        """Safely gets the config for the current exercise."""
        return state.training_program[state.current_workout_index]["exercises"][state.current_exercise_index]

    def _finish_training(self, user_id: int) -> str:
        """Finalizes, saves, and cleans up the training session."""
        state = self.active_sessions.pop(user_id, None)
        if not state:
            return "Could not find a session to finish."

        # Calculate final duration
        duration = (datetime.now() - state.start_time).total_seconds()
        state.training_in_progress.duration = round(duration / 60)
        
        try:
            self.mongo_service.save_training(state.training_in_progress)
            logger.info("User %d finished and saved training.", user_id)
            return "🎉 Training complete! Saved successfully. Well done."
        except Exception as e:
            logger.error("Failed to save training for user %d: %s", user_id, e)
            return "Could not save your training due to an error. Please check the logs."