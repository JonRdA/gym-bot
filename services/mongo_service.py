"""Service responsible for all interactions with the MongoDB database."""
import logging

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

from config import Settings
from models.domain import Training

logger = logging.getLogger(__name__)

class MongoService:
    """Handles all MongoDB operations for the workout tracker."""

    def __init__(self, settings: Settings):
        """
        Initializes the database connection.

        Args:
            settings: The application settings object with DB config.
        """
        try:
            self.client = MongoClient(settings.mongo_uri)
            # The ismaster command is cheap and does not require auth.
            self.client.admin.command('ismaster')
            self.db = self.client[settings.mongo_db_name]
            self.trainings_collection = self.db["trainings"]
            logger.info("Successfully connected to MongoDB.")
        except ConnectionFailure as e:
            logger.error("Could not connect to MongoDB: %s", e)
            self.client = None
            self.db = None
            self.trainings_collection = None


    def save_training(self, training: Training) -> bool:
        """
        Saves a completed training session to the database.

        Args:
            training: The Training Pydantic model instance.

        Returns:
            True if insertion was successful, False otherwise.
        """
        if not self.trainings_collection:
            logger.error("Cannot save training, no database connection.")
            return False

        try:
            # Pydantic's model_dump is used to convert the object to a dict.
            # `mode='json'` ensures that types like date are serialized correctly.
            training_dict = training.model_dump(mode='json')
            result = self.trainings_collection.insert_one(training_dict)
            logger.info("Successfully saved training with id: %s", result.inserted_id)
            return True
        except OperationFailure as e:
            logger.error("Failed to save training to MongoDB: %s", e)
            return False
