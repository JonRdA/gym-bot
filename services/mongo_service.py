import logging
from datetime import date

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

from config import settings
from models.domain import Training

logger = logging.getLogger(__name__)

class MongoService:
    """A service for handling all database operations with MongoDB."""

    def __init__(self):
        """Initializes the MongoDB client and database connection."""
        try:
            self.client = MongoClient(settings.mongo_uri)
            # The ismaster command is cheap and does not require auth.
            self.client.admin.command('ismaster')
            self.db = self.client[settings.mongo.db_name]
            logger.info("Successfully connected to MongoDB.")
        except ConnectionFailure as e:
            logger.error("Could not connect to MongoDB: %s", e)
            raise

    def save_training(self, training_data: Training) -> bool:
        """Saves a completed training document to the database."""
        try:
            collection = self.db[settings.mongo.trainings_collection]
            # Use model_dump with exclude_none=True to prevent saving null fields
            training_dict = training_data.model_dump(by_alias=True, exclude_none=True)
            
            # The date is already a datetime object, no conversion needed.
            
            result = collection.insert_one(training_dict)
            logger.info("Successfully saved training with id: %s", result.inserted_id)
            return True
        except OperationFailure as e:
            logger.error("Failed to save training to MongoDB: %s", e)
            return False

    def get_user_config(self, user_id: int) -> dict | None:
        """Retrieves a user's workout configuration."""
        try:
            collection = self.db[settings.mongo.config_collection]
            config = collection.find_one({"user_id": user_id})
            if config:
                logger.info("Found configuration for user_id: %s", user_id)
                return config.get("workouts", {})
            logger.warning("No configuration found for user_id: %s", user_id)
            return None
        except OperationFailure as e:
            logger.error("Failed to get user config: %s", e)
            return None

