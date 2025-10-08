import logging
from datetime import date, datetime, timedelta
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

    def select_training(self, user_id: int, training_name: TrainingName) -> str:
        """Initiates the logging flow after a user selects a training program."""
        if user_id in self.active_sessions:
            return "You already have a training session in progress! Please complete or /cancel it first."

        program = self.program_loader.load_program()
        training_program_config = program.get(training_name.value)
        if not training_program_config:
            return f"Sorry, I don't know the training program '{training_name.value}'."

        state = TrainingState(
            user_id=user_id,
            training_program=training_program_config,
            selected_training_name=training_name
        )
        self.active_sessions[user_id] = state
        
        logger.info("User %d selected training: %s. Awaiting date.", user_id, training_name.value)
        return "What date was this training? (e.g., 2025-10-08, 'today', or 'yesterday')"

    def handle_user_response(self, user_id: int, message_text: str) -> str:
        """Processes a user's text message based on the current state of the conversation."""
        state = self.active_sessions.get(user_id)
        if not state:
            return "You don't have an active training session. Use /startlog to begin."

        # State Machine Router
        if state.awaiting_input_type == "date":
            return self._handle_date_input(state, message_text)
        elif state.awaiting_input_type == "duration":
            return self._handle_duration_input(state, message_text)
        elif state.awaiting_input_type == "set_data":
            return self._handle_set_input(state, message_text)
        elif state.awaiting_input_type == "rest_time":
            return self._handle_rest_time_input(state, message_text)
        
        return "Sorry, I'm a bit confused. You can /cancel and start over."

    def _handle_date_input(self, state: TrainingState, text: str) -> str:
        """Parses the date input from the user."""
        clean_text = text.strip().lower()
        try:
            if clean_text == "today":
                state.selected_date = date.today()
            elif clean_text == "yesterday":
                state.selected_date = date.today() - timedelta(days=1)
            else:
                state.selected_date = date.fromisoformat(clean_text)
            
            state.awaiting_input_type = "duration"
            return "Got it. What was the total duration of the workout in minutes?"
        except ValueError:
            return "Invalid date format. Please use YYYY-MM-DD, 'today', or 'yesterday'."

    def _handle_duration_input(self, state: TrainingState, text: str) -> str:
        """Parses the duration input and starts the main workout logging."""
        try:
            duration_minutes = int(text.strip())
            
            # Now we have all initial info, create the full Training object
            state.training_in_progress = Training(
                user_id=state.user_id,
                date=state.selected_date,
                name=state.selected_training_name,
                duration=duration_minutes,
                workouts=[]
            )
            state.awaiting_input_type = "set_data"
            self._prepare_current_structures(state)
            logger.info("User %d started logging workout details.", state.user_id)
            return self._get_current_question(state.user_id)
        except ValueError:
            return "Invalid duration. Please enter a number (e.g., 90)."

    def _handle_set_input(self, state: TrainingState, text: str) -> str:
        """Handles user input for a specific set (metrics, done, repeat)."""
        current_exercise_config = self._get_current_exercise_config(state)
        expected_metrics = [Metric(m) for m in current_exercise_config["metrics"]]
        parse_result = self.input_parser.parse(text, expected_metrics)

        if parse_result.error_message:
            return parse_result.error_message
        
        if parse_result.data == SpecialCommand.DONE_EXERCISE:
            if current_exercise_config.get("track_rest", False):
                state.awaiting_input_type = "rest_time"
                exercise_name = current_exercise_config["name"].replace('_', ' ').title()
                return f"✅ Exercise complete. What was your rest time between sets for *{exercise_name}* (in seconds)?"
            else:
                state.current_exercise_index += 1
                state.last_logged_set = None
                self._prepare_current_structures(state)
                return self._get_current_question(state.user_id)
        
        elif parse_result.data == SpecialCommand.REPEAT_SET:
            if not state.last_logged_set:
                return "There is no previous set to repeat."
            set_to_add = state.last_logged_set
        
        else: # It's parsed metric data
            set_to_add = WoSet(metrics=parse_result.data)
        
        state.training_in_progress.workouts[-1].exercises[-1].sets.append(set_to_add)
        state.last_logged_set = set_to_add
        
        return "✅ Set logged! Enter next set, or use /done or /repeat."

    def _handle_rest_time_input(self, state: TrainingState, text: str) -> str:
        """Parses the rest time input."""
        try:
            rest_time = int(text.strip())
            state.training_in_progress.workouts[-1].exercises[-1].rest_time = rest_time
            
            # Reset state for the next exercise
            state.awaiting_input_type = "set_data"
            state.current_exercise_index += 1
            state.last_logged_set = None
            
            self._prepare_current_structures(state)
            return self._get_current_question(state.user_id)
        except ValueError:
            return "Invalid input. Please enter the rest time in seconds (e.g., 90)."
            
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

        try:
            self.mongo_service.save_training(state.training_in_progress)
            logger.info("User %d finished and saved training.", user_id)
            return "🎉 Training complete! Saved successfully. Well done."
        except Exception as e:
            logger.error("Failed to save training for user %d: %s", user_id, e)
            return "Could not save your training due to an error. Please check the logs."
