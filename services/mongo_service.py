import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.cursor import Cursor
from pymongo.errors import ConnectionFailure, OperationFailure

from config import Settings
from models.domain import Training

logger = logging.getLogger(__name__)


class MongoService:
    """Handles all MongoDB operations for the workout tracker bot."""

    def __init__(self, settings: Settings) -> None:
        """Initialize MongoDB client and collections."""
        self.settings = settings
        try:
            self.client: MongoClient = MongoClient(settings.mongo.uri, serverSelectionTimeoutMS=5000)
            self.client.admin.command("ismaster")  # Quick connection check
            self.db = self.client[settings.mongo.database]
            self.trainings: Collection = self.db[settings.mongo.trainings_collection]
            self.configs: Collection = self.db[settings.mongo.config_collection]
            logger.info("Connected to MongoDB at %s", settings.mongo.host)
        except ConnectionFailure as exc:
            logger.critical("Could not connect to MongoDB.", exc_info=True)
            raise exc

    # ------------------------------
    # CRUD Operations
    # ------------------------------
    def save_training(self, training: Training) -> bool:
        """Insert a new training document."""
        try:
            training_dict: Dict[str, Any] = training.model_dump(by_alias=True, exclude_none=True)
            logger.debug("Saving training: %s", training_dict)
            self.trainings.insert_one(training_dict)
            logger.info("Saved training for user %s", training.user_id)
            return True
        except OperationFailure as exc:
            logger.error("Failed to save training for user %s: %s", training.user_id, exc, exc_info=True)
            return False

    def get_training_by_id(self, training_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a training by its ObjectId."""
        logger.debug("Fetching training by id=%s", training_id)
        try:
            doc = self.trainings.find_one({"_id": ObjectId(training_id)})
            logger.debug("Training fetched: %s", doc)
            return Training(**doc)
        except Exception as exc:
            logger.error("Error fetching training %s: %s", training_id, exc, exc_info=True)
            return None

    def update_training(self, training_id: str, training: Training) -> bool:
        """Replace a training document."""
        logger.debug("Updating training id=%s with data=%s", training_id, training)
        try:
            data = training.model_dump(mode="python", by_alias=True)
            result = self.trainings.replace_one(
                {"_id": ObjectId(training_id)},
                data,
                upsert=True
            )
            success = result.modified_count > 0 or result.upserted_id is not None
            logger.info("Update training id=%s success=%s", training_id, success)
            return success

        except OperationFailure as exc:
            logger.error("Failed to update training %s: %s", training_id, exc, exc_info=True)
            return False

    # ------------------------------
    # Query Operations
    # ------------------------------
    def query( self, user_id: int, projection: Optional[Dict[str, int]] = None,) -> List[Dict[str, Any]]:
        """Return trainings between two dates."""
        query = {"user_id": user_id}
        return self._execute_query(user_id, query, projection)

    def query_between_dates(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        projection: Optional[Dict[str, int]] = None,
    ) -> List[Dict[str, Any]]:
        """Return trainings between two dates."""
        query = self._build_base_query(user_id, start_date, end_date)
        return self._execute_query(user_id, query, projection)

    def query_between_dates_excluding_workouts(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        excluded_workouts: List[str],
        projection: Optional[Dict[str, int]] = None,
    ) -> List[Dict[str, Any]]:
        """Return trainings between dates excluding workouts."""
        query = self._build_base_query(user_id, start_date, end_date)
        query["workouts.name"] = {"$nin": excluded_workouts}
        return self._execute_query(user_id, query, projection)

    def query_between_dates_including_workouts(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        required_workouts: List[str],
        projection: Optional[Dict[str, int]] = None,
    ) -> List[Dict[str, Any]]:
        """Return trainings between dates including workouts."""
        query = self._build_base_query(user_id, start_date, end_date)
        query["workouts.name"] = {"$in": required_workouts}
        return self._execute_query(user_id, query, projection)

    # ------------------------------
    # Internal Helpers
    # ------------------------------
    def _build_base_query(self, user_id: int, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Build base user/date query."""
        start_date = self._ensure_utc(start_date)
        end_date = self._ensure_utc(end_date)
        query = {"user_id": user_id, "date": {"$gte": start_date, "$lte": end_date}}
        logger.debug("Base query built: %s", query)
        return query

    def _execute_query( self, user_id: int, query: dict, projection: dict | None) -> List[Training]:
        """Execute a Mongo query and return Training models."""
        logger.debug("Executing Mongo query for user=%s: %s", user_id, query)
        try:
            cursor: Cursor = self.trainings.find(query, projection).sort("date", -1)
            # for doc in cursor:
            #     print("\n\n\n\n")
            #     a = Training(**doc)
            #     print(a)
            results = [Training(**doc) for doc in cursor]
            logger.debug("Query returned %d trainings for user=%s", len(results), user_id)
            return results
        except OperationFailure as exc:
            logger.error("Failed to query trainings for user %s: %s", user_id, exc, exc_info=True)
            return []

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        """Ensure datetime is UTC-aware."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
