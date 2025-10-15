import logging

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
            self.db = self.client[settings.mongo_db_name]
            logging.info("Successfully connected to MongoDB.")
        except ConnectionFailure as e:
            logging.error("Could not connect to MongoDB: %s", e)
            raise

    def save_training(self, training_data: Training) -> bool:
        """Saves a completed training document to the database."""
        try:
            collection = self.db[settings.mongo_trainings_collection]
            # Pydantic's model_dump is used to get a dict suitable for MongoDB
            training_dict = training_data.model_dump(by_alias=True)
            result = collection.insert_one(training_dict)
            logging.info("Successfully saved training with id: %s", result.inserted_id)
            return True
        except OperationFailure as e:
            logging.error("Failed to save training to MongoDB: %s", e)
            return False

    def get_user_config(self, user_id: int) -> dict | None:
        """Retrieves a user's workout configuration."""
        try:
            collection = self.db[settings.mongo_config_collection]
            config = collection.find_one({"user_id": user_id})
            if config:
                logging.info("Found configuration for user_id: %s", user_id)
                return config.get("workouts", {})
            logging.warning("No configuration found for user_id: %s", user_id)
            return None
        except OperationFailure as e:
            logging.error("Failed to get user config: %s", e)
            return None

