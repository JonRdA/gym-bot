import logging
import os  # Import the os module

from telegram.ext import Application

from bot.handlers import get_conversation_handler
from bot.reporting_handlers import get_reporting_handlers
from config import create_settings
from services.mongo_service import MongoService
from services.reporting_service import ReportingService
from services.training_config_service import TrainingConfigService

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def main() -> None:
    """Instantiates dependencies based on environment and starts the bot."""
    
    # --- Environment Selection ---
    # Read the BOT_ENV environment variable. Default to 'local' if not set.
    # This makes running locally the default, safe behavior.
    env = os.getenv('BOT_ENV', 'local')
    logger.info("Starting bot in '%s' environment.", env)

    try:
        # --- Dependency Injection ---
        # The factory creates the correct settings object for the environment.
        settings = create_settings(env=env)
        
        mongo_service = MongoService(settings)
        # The reporting service needs settings for excluded workouts
        reporting_service = ReportingService(mongo_service, settings)
        # Config service needs mongo to check for user-specific configs
        config_service = TrainingConfigService("training_config.yaml", mongo_service)

    except FileNotFoundError as e:
        logger.critical("Configuration Error: %s. Ensure your .env.%s file exists.", e, env)
        return
    except Exception as e:
        logger.critical("Failed to initialize services. Bot cannot start.", exc_info=True)
        return

    # --- Create the Telegram Application ---
    application = Application.builder().token(settings.telegram_bot_token).build()

    # --- Register Handlers ---
    conv_handler = get_conversation_handler(config_service, mongo_service)
    reporting_handlers = get_reporting_handlers(mongo_service, reporting_service, config_service)
    
    application.add_handler(conv_handler)
    for handler in reporting_handlers:
        application.add_handler(handler)

    logger.info("Bot is ready and listening for commands.")
    application.run_polling()


if __name__ == "__main__":
    main()

