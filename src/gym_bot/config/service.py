import logging

import yaml
from cachetools import TTLCache

from gym_bot.config.models import UserConfig
from gym_bot.db.repositories import UserConfigRepository

logger = logging.getLogger(__name__)


def load_default_config(path: str) -> dict:
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data.get("workouts", {})


class UserConfigService:
    def __init__(self, repo: UserConfigRepository, default_workouts: dict):
        self._repo = repo
        self._default_workouts = default_workouts
        self._cache: TTLCache = TTLCache(maxsize=100, ttl=3600)

    async def get_config(self, user_id: int) -> UserConfig:
        if user_id in self._cache:
            return self._cache[user_id]

        doc = await self._repo.find_by_user_id(user_id)
        if doc is None:
            config = UserConfig(user_id=user_id, workouts=self._default_workouts)
            await self._repo.upsert(user_id, config.model_dump()["workouts"])
            logger.info("Created default config for new user %s", user_id)
        else:
            config = UserConfig(user_id=doc["user_id"], workouts=doc["workouts"])

        self._cache[user_id] = config
        return config

    async def update_config(self, config: UserConfig) -> None:
        await self._repo.upsert(config.user_id, config.model_dump()["workouts"])
        self._cache[config.user_id] = config

    def invalidate(self, user_id: int) -> None:
        self._cache.pop(user_id, None)
