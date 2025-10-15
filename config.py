from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Manages application settings and environment variables."""

    # Load variables from a .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    telegram_bot_token: str
    mongo_uri: str
    mongo_db_name: str = "workout_tracker"
    mongo_trainings_collection: str = "trainings"
    mongo_config_collection: str = "user_configurations"


# Instantiate the settings object to be used throughout the application
settings = Settings()

