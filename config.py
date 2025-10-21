import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Load non-sensitive config from YAML ---
CONFIG_FILE_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
try:
    with open(CONFIG_FILE_PATH, 'r') as f:
        YAML_CONFIG = yaml.safe_load(f)
except (FileNotFoundError, yaml.YAMLError):
    YAML_CONFIG = {}

# --- Pydantic Models for structured config ---
class MongoSettings(BaseModel):
    db_name: str = YAML_CONFIG.get('mongo', {}).get('db_name', 'workout_tracker')
    trainings_collection: str = YAML_CONFIG.get('mongo', {}).get('trainings_collection', 'trainings')
    config_collection: str = YAML_CONFIG.get('mongo', {}).get('config_collection', 'user_configurations')

class BackupSettings(BaseModel):
    directory: str = YAML_CONFIG.get('backup', {}).get('directory', 'trainings_backup')

class ReportingSettings(BaseModel):
    excluded_workouts: list[str] = YAML_CONFIG.get('reporting', {}).get('excluded_workouts', [])

class Settings(BaseSettings):
    """
    Main settings class. It validates data from environment variables or passed-in values.
    Intended to be instantiated ONLY by the create_settings factory.
    """
    model_config = SettingsConfigDict(extra='ignore') # Ignore extra fields passed in

    telegram_bot_token: str
    mongo_host: str = "localhost"
    mongo_port: int = 27017
    mongo_user: str | None = None
    mongo_password: str | None = None

    @computed_field
    @property
    def mongo_uri(self) -> str:
        """Constructs the MongoDB connection URI from components."""
        if self.mongo_user and self.mongo_password:
            return f"mongodb://{self.mongo_user}:{self.mongo_password}@{self.mongo_host}:{self.mongo_port}/"
        return f"mongodb://{self.mongo_host}:{self.mongo_port}/"

    mongo: MongoSettings = MongoSettings()
    backup: BackupSettings = BackupSettings()
    reporting: ReportingSettings = ReportingSettings()

def create_settings(env: str = 'local') -> Settings:
    """
    Settings Factory: Creates a Settings instance by explicitly loading the correct .env file.
    This is the single point of entry for loading configuration.
    """
    env_file = Path(__file__).resolve().parent / f".env.{env}"
    if not env_file.exists():
        raise FileNotFoundError(f"Environment file not found for env '{env}': {env_file}")

    # Step 1: Manually load the specified .env file into a dictionary.
    env_vars = {k.lower(): v for k, v in dotenv_values(env_file).items()}

    
    # Step 2: Pass the loaded dictionary to the Settings constructor.
    # Pydantic will now use these values to populate the model fields.
    return Settings(**env_vars)

