"""Main entry point for the Telegram Workout Bot."""

import logging

from telegram.ext import Application

from bot.handlers import get_conversation_handler
from config import settings
from services.mongo_service import MongoService
from services.training_config_service import TrainingConfigService

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
# Set higher logging level for httpx to avoid noisy GET and POST requests
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def main() -> None:
    """Starts the bot."""
    logger.info("Initializing services...")

    # 1. Initialize services
    # Architectural decision: Services are instantiated here at the top level
    # and passed down to the handlers that need them (Dependency Injection).
    # This decouples the handlers from the service creation process.
    config_service = TrainingConfigService(config_path="training_config.yaml")
    mongo_service = MongoService()

    if not mongo_service.client:
        logger.error("Failed to connect to MongoDB. Bot cannot start.")
        return

    logger.info("Setting up Telegram bot...")
    # 2. Create the Telegram Application
    application = Application.builder().token(settings.telegram_bot_token).build()

    # 3. Get and add the conversation handler
    conv_handler = get_conversation_handler(config_service, mongo_service)
    application.add_handler(conv_handler)

    logger.info("Bot is starting to poll...")
    # 4. Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    main()
