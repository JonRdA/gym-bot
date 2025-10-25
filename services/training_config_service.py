import logging
from typing import Iterable

import yaml
from cachetools import TTLCache, cached

from models.enums import WorkoutName
from services.mongo import MongoService

logger = logging.getLogger(__name__)

class TrainingConfigService:
    """Manages loading and accessing workout configurations with caching."""

    def __init__(self, config_path: str, mongo: MongoService):
        # self.mongo = mongo
        # Cache holds up to 100 users' configs, each for 1 hour (3600 seconds)
        # self._user_config_cache = TTLCache(maxsize=100, ttl=3600)
        
        try:
            with open(config_path, 'r') as file:
                self._default_config = yaml.safe_load(file).get('workouts', {})
            logger.info("Successfully loaded default training config from %s", config_path)
        except (FileNotFoundError, yaml.YAMLError) as e:
            logger.error("Failed to load training config file: %s", e, exc_info=True)
            self._default_config = {}

    def get_workout_names(self, user_id: int) -> list[str]:
        """Returns a list of available workout names for a user, checking cache first."""
        # user_config = self._get_user_config_from_mongo(user_id)
        # if user_config:
        #     return list(user_config.keys())
        return list(self._default_config.keys())

    def get_workout_details(self, user_id: int, workout_name: WorkoutName) -> dict | None:
        """Gets the configuration for a specific workout for a user, using cache."""
        # user_config = self._get_user_config_from_mongo(user_id)
        # if user_config and workout_name.value in user_config:
        #     return user_config[workout_name.value]
        
        return self._default_config.get(workout_name.value)

    # @cached(cache=lambda self: self._user_config_cache)
    # def _get_user_config_from_mongo(self, user_id: int) -> dict | None:
    #     """
    #     Internal method that fetches user config from MongoDB.
    #     This method is cached, so the DB is only hit on a cache miss.
    #     """
    #     logger.debug("CACHE MISS: Fetching config from MongoDB for user %s", user_id)
    #     return self.mongo.get_user_config(user_id)

    def get_exercise_details(self, user_id: int, exercise_name: str) -> dict | None:
        """Finds the details of a specific exercise across all of a user's workouts."""
        # user_config = self._get_user_config_from_mongo(user_id)
        # if user_config:
        #     details = self._get_exercise_details_from_config(user_config.values(), exercise_name)
        #     if details:
        #         return details
        
        # Fallback to default config if not found in user's config
        return self._get_exercise_details_from_config(self._default_config.values(), exercise_name)

    def _get_exercise_details_from_config(self, workouts: Iterable[dict], exercise_name: str) -> dict | None: 
        """Helper to find an exercise in a list of workout configs."""
        for workout in workouts:
            for ex in workout.get('exercises', []):
                if ex.get('name') == exercise_name:
                    return ex
        return None

