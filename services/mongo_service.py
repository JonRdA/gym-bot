import logging
from datetime import datetime, timedelta

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
            logger.error("Could not connect to MongoDB: %s", e, exc_info=True)
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
            logger.error("Failed to save training to MongoDB: %s", e, exc_info=True)
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

            # Use replace_one with upsert=True. This will create the document if it
            # doesn't exist, which is perfect for populating a new database.
            result = collection.replace_one({'_id': obj_id}, training_data, upsert=True)

            if result.matched_count == 0 and not result.upserted_id:
                logging.warning("Update/Upsert failed for id: %s", training_id)
                return False

            logging.info(
                "Processed training %s. Matched: %s, Modified: %s, Upserted: %s",
                training_id, result.matched_count, result.modified_count, result.upserted_id is not None
            )
            return True
        except OperationFailure as e:
            logging.error("Failed to update training %s: %s", training_id, e)
            return False
        except Exception as e:
            logging.error("An error occurred updating training %s: %s", training_id, e)
            return False

    def get_user_config(self, user_id: int) -> dict | None:
        """Retrieves a user's workout configuration."""
        try:
            collection = self.db[settings.mongo.config_collection]
            config = collection.find_one({"user_id": user_id})
            if config:
                logging.info("Found configuration for user_id: %s", user_id)
                return config.get("workouts", {})
            logging.warning("No configuration found for user_id: %s", user_id)
            return None
        except OperationFailure as e:
            logging.error("Failed to get user config: %s", e)
            return None

    # --- Reporting Methods ---

    def get_trainings_for_last_n_days(self, user_id: int, days: int, excluded_workouts: list[str] | None = None) -> list:
        """
        Retrieves training documents for a user from the last N days.
        Can optionally exclude trainings containing certain workout names.
        """
        try:
            collection = self.db[settings.mongo.trainings_collection]
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            query = {
                "user_id": user_id,
                "date": {"$gte": start_date, "$lte": end_date}
            }

            if excluded_workouts:
                # Add a condition to exclude documents where the 'workouts.name' array
                # contains any of the excluded workout names.
                query["workouts.name"] = {"$nin": excluded_workouts}

            cursor = collection.find(query).sort("date", -1)
            return list(cursor)
        except Exception as e:
            logging.error("Failed to get trainings for last %d days for user %s: %s", days, user_id, e)
            return []

    def get_training_by_id(self, training_id: str) -> dict | None:
        """Retrieves a single training document by its ObjectId."""
        try:
            collection = self.db[settings.mongo.trainings_collection]
            return collection.find_one({"_id": ObjectId(training_id)})
        except Exception as e:
            logging.error("Failed to get training by id %s: %s", training_id, e)
            return None

    def get_training_dates_for_month(self, user_id: int, year: int, month: int, excluded_workouts: list[str] | None = None) -> list[datetime]:
        """Retrieves all training dates for a user in a given month and year."""
        start_date = datetime(year, month, 1)
        # Handles month wrapping correctly
        end_date = (start_date + timedelta(days=32)).replace(day=1)
        
        query = {
            "user_id": user_id,
            "date": {
                "$gte": start_date,
                "$lt": end_date
            }
        }

        if excluded_workouts:
            query["workouts.name"] = {"$nin": excluded_workouts}

        try:
            collection = self.db[settings.mongo.trainings_collection]
            # Use projection to only return the 'date' field for efficiency
            cursor = collection.find(query, {"date": 1, "_id": 0})
            return [doc["date"] for doc in cursor]
        except Exception as e:
            logging.error("Failed to get training dates for user %s: %s", user_id, e)
            return []

