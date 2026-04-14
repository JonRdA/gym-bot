import logging
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId

from gym_bot.db.mongo import Database
from gym_bot.domain.errors import TrainingNotFoundError
from gym_bot.domain.models import Training

logger = logging.getLogger(__name__)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class TrainingRepository:
    def __init__(self, db: Database):
        self._col = db.trainings

    async def save(self, training: Training) -> str:
        doc = training.model_dump(by_alias=True, exclude_none=True)
        result = await self._col.insert_one(doc)
        logger.info("Saved training for user %s", training.user_id)
        return str(result.inserted_id)

    async def find_by_id(self, training_id: str) -> Training:
        doc = await self._col.find_one({"_id": ObjectId(training_id)})
        if doc is None:
            raise TrainingNotFoundError(f"Training {training_id} not found")
        return Training(**doc)

    async def find_between_dates(
        self,
        user_id: int,
        t0: datetime,
        t1: datetime,
    ) -> list[Training]:
        query = self._date_query(user_id, t0, t1)
        return await self._execute(query)

    async def find_with_workout_filter(
        self,
        user_id: int,
        t0: datetime,
        t1: datetime,
        include: Optional[list[str]] = None,
        exclude: Optional[list[str]] = None,
    ) -> list[Training]:
        query = self._date_query(user_id, t0, t1)
        if include:
            query["workouts.name"] = {"$in": include}
        elif exclude:
            query["workouts.name"] = {"$nin": exclude}
        return await self._execute(query)

    async def find_all(self) -> list[Training]:
        cursor = self._col.find().sort("date", -1)
        return [Training(**doc) async for doc in cursor]

    def _date_query(self, user_id: int, t0: datetime, t1: datetime) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "date": {"$gte": _ensure_utc(t0), "$lte": _ensure_utc(t1)},
        }

    async def _execute(self, query: dict) -> list[Training]:
        cursor = self._col.find(query).sort("date", -1)
        return [Training(**doc) async for doc in cursor]
