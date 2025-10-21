import logging
from datetime import datetime
from typing import Any

from bson.objectid import ObjectId
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

from config import Settings
from models.domain import Training

logger = logging.getLogger(__name__)

class MongoService:
    """A service for handling all database operations with MongoDB."""

    def __init__(self, settings: Settings):
        """Initializes the MongoDB client and database connection."""
        self.settings = settings
        try:
            self.client = MongoClient(self.settings.mongo_uri)
            self.client.admin.command('ismaster')
            self.db = self.client[self.settings.mongo.db_name]
            logger.info("Successfully connected to MongoDB.")
        except ConnectionFailure as e:
            logger.error("Could not connect to MongoDB: %s", e, exc_info=True)
            raise

    def save_training(self, training_data: Training) -> bool:
        """Saves a completed training document to the database."""
        try:
            collection = self.db[self.settings.mongo.trainings_collection]
            training_dict = training_data.model_dump(by_alias=True, exclude_none=True)
            result = collection.insert_one(training_dict)
            logger.info("Successfully saved training with id: %s", result.inserted_id)
            return True
        except OperationFailure as e:
            logger.error("Failed to save training: %s", e, exc_info=True)
            return False
    
    def update_training(self, training_id: str, training_data: dict) -> bool:
        """Updates or inserts a training document using its ObjectId."""
        try:
            collection = self.db[self.settings.mongo.trainings_collection]
            obj_id = ObjectId(training_id)
            if 'date' in training_data and isinstance(training_data['date'], str):
                iso_string = training_data['date'].replace('Z', '+00:00')
                training_data['date'] = datetime.fromisoformat(iso_string)
            result = collection.replace_one({'_id': obj_id}, training_data, upsert=True)
            if not result.acknowledged:
                logging.warning("Update/Upsert was not acknowledged for id: %s", training_id)
                return False
            logging.info("Processed training %s. Matched: %d, Modified: %d, Upserted: %s",
                         training_id, result.matched_count, result.modified_count, result.upserted_id is not None)
            return True
        except OperationFailure as e:
            logger.error("Failed to update training %s: %s", training_id, e, exc_info=True)
            return False
        except Exception as e:
            logger.error("An unexpected error occurred updating training %s: %s", training_id, e, exc_info=True)
            return False

    def get_user_config(self, user_id: int) -> dict | None:
        """Retrieves a user's workout configuration."""
        try:
            collection = self.db[self.settings.mongo.config_collection]
            config = collection.find_one({"user_id": user_id})
            return config.get("workouts", {}) if config else None
        except OperationFailure as e:
            logger.error("Failed to get user config for %s: %s", user_id, e, exc_info=True)
            return None

    def get_training_by_id(self, training_id: str) -> dict | None:
        """Retrieves a single training document by its ObjectId."""
        try:
            collection = self.db[self.settings.mongo.trainings_collection]
            return collection.find_one({"_id": ObjectId(training_id)})
        except Exception as e:
            logger.error("Failed to get training by id %s: %s", training_id, e, exc_info=True)
            return None
    
    def query_trainings_between_dates(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        excluded_workouts: list[str] | None = None,
        projection: dict[str, Any] | None = None
    ) -> list[dict]:
        """
        Generic function to query trainings for a user within a date range.
        """
        try:
            collection = self.db[self.settings.mongo.trainings_collection]
            query = {
                "user_id": user_id,
                "date": {"$gte": start_date, "$lte": end_date}
            }
            if excluded_workouts:
                query["workouts.name"] = {"$nin": excluded_workouts}
            
            cursor = collection.find(query, projection).sort("date", -1)
            return list(cursor)
        except Exception as e:
            logger.error("Failed to query trainings for user %s: %s", user_id, e, exc_info=True)
            return []

