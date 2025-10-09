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
            logger.error("🔥 Could not connect to MongoDB: %s", e)
            raise

    def save_training(self, training: Training) -> str:
        """Saves a Training document to the database."""
        logger.info("Attempting to save training for user %s...", training.user_id)
        
        training_dict = training.model_dump(mode='json') # Use mode='json' for better serialization
        
        result = self.trainings_collection.insert_one(training_dict)
        logger.info("💪 Training saved with id: %s", result.inserted_id)
        return str(result.inserted_id)

    def close_connection(self):
        """Closes the MongoDB connection."""
        self.client.close()
        logger.info("MongoDB connection closed.")