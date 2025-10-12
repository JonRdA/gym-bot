"""Service to load and access the training program configuration from YAML."""
import logging
from typing import Any, Dict, List, Optional

import yaml

from models.enums import ExerciseName, Metric, WorkoutName

logger = logging.getLogger(__name__)


class TrainingConfigService:
    """Handles loading and providing access to the training config."""

    def __init__(self, config_path: str):
        """Initializes the service by loading the workout configurations."""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
                logger.info("Workout configuration loaded successfully from %s", config_path)
        except FileNotFoundError:
            logger.error("Workout configuration file not found at %s", config_path)
            self._config = {"workouts": {}}
        except yaml.YAMLError as e:
            logger.error("Error parsing YAML file %s: %s", config_path, e)
            self._config = {"workouts": {}}

    def get_workout_names(self) -> List[WorkoutName]:
        """Returns a list of all available workout names from the config."""
        return [WorkoutName(name) for name in self._config.get("workouts", {}).keys()]

    def get_workout_details(self, workout_name: WorkoutName) -> Optional[Dict[str, Any]]:
        """
        Gets the configuration details for a given workout name.
        
        Args:
            workout_name: The name of the workout.

        Returns:
            A dictionary with the workout details (e.g., exercises) or None if not found.
        """
        return self._config.get("workouts", {}).get(workout_name.value)

    def get_exercises_for_workout(self, workout_name: WorkoutName) -> List[Dict[str, Any]]:
        """
        Gets the list of exercise configurations for a given workout.

        Args:
            workout_name: The name of the workout.
        
        Returns:
            A list of exercise dictionaries, or an empty list if not found.
        """
        workout_details = self.get_workout_details(workout_name)
        if workout_details:
            return workout_details.get("exercises", [])
        return []

