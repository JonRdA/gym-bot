import logging

from pymongo import MongoClient
from src.config import Settings
from src.models.domain import Training

logger = logging.getLogger(__name__)

class MongoService:
    """A service for handling all MongoDB interactions."""

    def __init__(self, settings: Settings):
        """Initializes the MongoDB connection."""
        try:
            self.client = MongoClient(settings.MONGO_URI)
            self.db = self.client[settings.MONGO_DB_NAME]
            self.trainings_collection = self.db["trainings"]
            logger.info("✅ Successfully connected to MongoDB.")
        except Exception as e:
            logger.error(f"🔥 Could not connect to MongoDB: {e}")
            raise

    def save_training(self, training: Training) -> str:
        """Saves a Training document to the database."""
        logger.info(f"Attempting to save training for user {training.user_id}...")
        
        # Pydantic's model_dump is used to convert the object to a dict
        training_dict = training.model_dump()
        
        # Convert enums and date to strings for MongoDB compatibility
        training_dict['name'] = training_dict['name'].value
        training_dict['session_date'] = training_dict['session_date'].isoformat()
        for workout in training_dict['workouts']:
            workout['name'] = workout['name'].value
            for exercise in workout['exercises']:
                exercise['name'] = exercise['name'].value
                for woset in exercise['sets']:
                    woset['metrics'] = {k.value: v for k, v in woset['metrics'].items()}

        result = self.trainings_collection.insert_one(training_dict)
        logger.info(f"💪 Training saved with id: {result.inserted_id}")
        return str(result.inserted_id)

    def close_connection(self):
        """Closes the MongoDB connection."""
        self.client.close()
        logger.info("MongoDB connection closed.")