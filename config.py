"""
Pydantic-based configuration management for the application.
Architectural decision:
Using Pydantic's BaseSettings allows us to define our configuration
as a typed Python class. It automatically loads variables from environment
variables or a .env file, providing validation and type hints for our settings.
This is cleaner and more robust than manually accessing os.environ.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Defines application settings."""
    
    # To load from a .env file
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    # Telegram Bot Token from BotFather
    telegram_bot_token: str

    # MongoDB connection details
    mongo_uri: str = "mongodb://localhost:27017/"
    mongo_db_name: str = "workout_tracker"


# Create a single, importable instance of the settings
settings = Settings()
