import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, uri: str, db_name: str):
        self.client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        self.db: AsyncIOMotorDatabase = self.client[db_name]

    @property
    def trainings(self) -> AsyncIOMotorCollection:
        return self.db["trainings"]

    @property
    def user_configs(self) -> AsyncIOMotorCollection:
        return self.db["user_configs"]

    async def ping(self):
        await self.client.admin.command("ping")
        logger.info("Connected to MongoDB")

    async def ensure_indexes(self):
        await self.trainings.create_index([("user_id", 1), ("date", 1)])
        await self.user_configs.create_index("user_id", unique=True)
        logger.info("Database indexes ensured")

    def close(self):
        self.client.close()
