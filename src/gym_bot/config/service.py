import logging

import yaml

from gym_bot.config.models import UserConfig
from gym_bot.db.mongo import Database

logger = logging.getLogger(__name__)


class UserConfigService:
    def __init__(self, db: Database, yaml_path: str, owner_user_id: int | None):
        self._col = db.user_configs
        self._yaml_path = yaml_path
        self._owner_user_id = owner_user_id
        self._cache: dict[int, UserConfig] = {}

    async def sync_owner(self) -> None:
        if self._owner_user_id is None:
            return
        config = UserConfig(user_id=self._owner_user_id, **self._load_yaml())
        await self._upsert(config)
        self._cache[self._owner_user_id] = config
        logger.info("Synced owner config for user %s from YAML", self._owner_user_id)

    async def get_config(self, user_id: int) -> UserConfig:
        if user_id in self._cache:
            return self._cache[user_id]

        doc = await self._col.find_one({"user_id": user_id})
        if doc is None:
            config = UserConfig(user_id=user_id, **self._load_yaml())
            await self._upsert(config)
            logger.info("Seeded config for new user %s from YAML", user_id)
        else:
            config = UserConfig(**doc)

        self._cache[user_id] = config
        return config

    def _load_yaml(self) -> dict:
        with open(self._yaml_path, "r") as f:
            data = yaml.safe_load(f) or {}
        return {
            "exercises": data.get("exercises", {}),
            "workouts": data.get("workouts", {}),
        }

    async def _upsert(self, config: UserConfig) -> None:
        dumped = config.model_dump()
        await self._col.update_one(
            {"user_id": config.user_id},
            {
                "$set": {
                    "user_id": config.user_id,
                    "exercises": dumped["exercises"],
                    "workouts": dumped["workouts"],
                }
            },
            upsert=True,
        )
