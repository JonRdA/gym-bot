from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_token: str
    mongo_uri: str = "mongodb://localhost:27017/"
    mongo_database: str = "gym-bot"
    default_config_path: str = "training_config_default.yaml"
    excluded_workouts: list[str] = ["home"]

    model_config = {"env_prefix": "GYMBOT_", "env_file": ".env"}
