import logging
from datetime import datetime

from bson.objectid import ObjectId
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
    
    def update_training(self, training_id: str, training_data: dict) -> bool:
        """
        Updates an existing training document using its ObjectId.
        The provided data dictionary will completely replace the existing document.
        """
        try:
            collection = self.db[settings.mongo.trainings_collection]
            obj_id = ObjectId(training_id)

            # The date in the JSON file is an ISO string, convert it back to datetime
            if 'date' in training_data and isinstance(training_data['date'], str):
                # Handle 'Z' suffix from MongoDB's BSON date representation
                iso_string = training_data['date'].replace('Z', '+00:00')
                training_data['date'] = datetime.fromisoformat(iso_string)

            result = collection.replace_one({'_id': obj_id}, training_data)

            if result.matched_count == 0:
                logger.warning("Update failed: No training found with id: %s", training_id)
                return False

            logger.info(
                "Updated training %s. Matched: %s, Modified: %s",
                training_id, result.matched_count, result.modified_count
            )
            return True
        except OperationFailure as e:
            logger.error("Failed to update training %s: %s", training_id, e)
            return False
        except Exception as e:
            logger.error("An error occurred updating training %s", training_id, exc_info=e)
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

