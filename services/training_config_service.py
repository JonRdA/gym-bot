"""Service to load and access the training program configuration from YAML."""
import logging
from typing import Any, Dict, List, Optional

import yaml

from models.enums import ExerciseName, Metric, TrainingName, WorkoutName

logger = logging.getLogger(__name__)


class TrainingConfigService:
    """Handles loading and providing access to the training config."""

    def __init__(self, config_path: str):
        """
        Initializes the service by loading the training configuration.

        Args:
            config_path: The file path to the training_config.yaml file.
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
                logger.info("Training configuration loaded successfully from %s", config_path)
        except FileNotFoundError:
            logger.error("Training configuration file not found at %s", config_path)
            self._config = {"trainings": {}}
        except yaml.YAMLError as e:
            logger.error("Error parsing YAML file %s: %s", config_path, e)
            self._config = {"trainings": {}}

    def get_training_names(self) -> List[TrainingName]:
        """Returns a list of all available training names from the config."""
        return [TrainingName(name) for name in self._config.get("trainings", {}).keys()]

    def get_workouts_for_training(self, training_name: TrainingName) -> List[Dict[str, Any]]:
        """
        Gets the list of workout configurations for a given training name.
        
        Args:
            training_name: The name of the training.

        Returns:
            A list of workout dictionaries, or an empty list if not found.
        """
        return self._config.get("trainings", {}).get(training_name.value, [])

    def get_exercises_for_workout(self, training_name: TrainingName, workout_name: WorkoutName) -> List[Dict[str, Any]]:
        """
        Gets the list of exercise configurations for a given workout in a training.

        Args:
            training_name: The name of the training.
            workout_name: The name of the workout.
        
        Returns:
            A list of exercise dictionaries, or an empty list if not found.
        """
        workouts = self.get_workouts_for_training(training_name)
        for workout in workouts:
            if workout.get("name") == workout_name.value:
                return workout.get("exercises", [])
        return []

    def get_exercise_details(self, training_name: TrainingName, workout_name: WorkoutName, exercise_name: ExerciseName) -> Optional[Dict[str, Any]]:
        """
        Gets the configuration details for a specific exercise.

        Args:
            training_name: The name of the training.
            workout_name: The name of the workout.
            exercise_name: The name of the exercise.

        Returns:
            A dictionary with the exercise details or None if not found.
        """
        exercises = self.get_exercises_for_workout(training_name, workout_name)
        for exercise in exercises:
            if exercise.get("name") == exercise_name.value:
                return exercise
        return None

    def get_metrics_for_exercise(self, training_name: TrainingName, workout_name: WorkoutName, exercise_name: ExerciseName) -> List[Metric]:
        """
        Gets the list of metrics to track for a specific exercise.

        Args:
            training_name: The name of the training.
            workout_name: The name of the workout.
            exercise_name: The name of the exercise.

        Returns:
            A list of Metric enums.
        """
        exercise_details = self.get_exercise_details(training_name, workout_name, exercise_name)
        if not exercise_details:
            return []
        return [Metric(m) for m in exercise_details.get("metrics", [])]
