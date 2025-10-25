from pathlib import Path
from typing import List, Literal

import yaml
from pydantic import BaseModel, computed_field


class MongoConfig(BaseModel):
    database: str
    trainings_collection: str
    config_collection: str
    host: str
    port: int
    user: str
    password: str

    @computed_field
    @property
    def uri(self) -> str:
        """Constructs the MongoDB connection URI from components."""
        if self.user and self.password:
            return f"mongodb://{self.user}:{self.password}@{self.host}:{self.port}/"
        return f"mongodb://{self.host}:{self.port}/"


class BackupConfig(BaseModel):
    directory: str

class BotConfig(BaseModel):
    telegram_token: str

class ReportingConfig(BaseModel):
    excluded_workouts: List[str]


class Settings(BaseModel):
    mongo: MongoConfig
    backup: BackupConfig
    reporting: ReportingConfig
    bot: BotConfig

    @classmethod
    def load(cls, environment: Literal["local", "raspy"]) -> "Settings":
        """Load all configuration from a YAML file for the given environment."""
        path = Path(f"config-{environment}.yaml")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)

