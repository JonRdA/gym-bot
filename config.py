import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# --- Helper function ---
def yaml_config_settings_source() -> Dict[str, Any]:
    """Load variables from a YAML config file."""
    config_path = Path("application_config.yaml")
    logger.debug(f"Loading YAML from: {config_path.resolve()}")
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return data
    logger.debug("YAML file not found!")
    return {}

# --- Nested models ---
class MongoSettings(BaseSettings):
    db_name: str = "kk"
    trainings_collection: str = "kk"
    config_collection: str = "kk"

class BackupSettings(BaseSettings):
    directory: str = "trainings_backup"

class ReportingSettings(BaseSettings):
    excluded_workouts: List[str] = ["home"]

# --- Main settings ---
class Settings(BaseSettings):
    telegram_bot_token: str | None = None
    mongo_uri: str | None = None

    mongo: MongoSettings = Field(default_factory=MongoSettings)
    backup: BackupSettings = Field(default_factory=BackupSettings)
    reporting: ReportingSettings = Field(default_factory=ReportingSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Callable[..., dict],
        env_settings: Callable[..., dict],
        dotenv_settings: Callable[..., dict],
        file_secret_settings: Callable[..., dict],
    ) -> Tuple[Callable[..., dict], ...]:
        """Define the order of settings sources."""
        return (env_settings, dotenv_settings, yaml_config_settings_source, init_settings, file_secret_settings)

# Instantiate the settings object to be used throughout the application
settings = Settings()

if __name__ == "__main__":
    s = Settings()
    print("Mongo DB:", s.mongo.db_name)
    print("Mongo collection:", s.mongo.trainings_collection)
    print("Backup directory:", s.backup.directory)
    print("Excluded workouts", s.reporting.excluded_workouts)
