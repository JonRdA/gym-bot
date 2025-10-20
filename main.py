import logging

from telegram.ext import Application

from bot.handlers import get_conversation_handler
from bot.reporting_handlers import get_reporting_handlers
from config import settings
from services.mongo_service import MongoService
from services.reporting_service import ReportingService
from services.training_config_service import TrainingConfigService

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Suppress noisy httpx logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def main() -> None:
    """Start the bot."""
    logger.info("Starting bot...")

    # --- Initialize Services (Dependencies) ---
    try:
        mongo_service = MongoService()
        config_service = TrainingConfigService(config_path="training_config.yaml")
        reporting_service = ReportingService(mongo_service)
        # config_service = TrainingConfigService("training_config.yaml", mongo_service)
    except Exception as e:
        logger.critical("Failed to initialize services. Bot cannot start. Error: %s", e, exc_info=True)
        return

    # --- Create the Telegram Application ---
    application = Application.builder().token(settings.telegram_bot_token).build()

    # --- Register Handlers ---
    conv_handler = get_conversation_handler(config_service, mongo_service)
    reporting_handlers = get_reporting_handlers(mongo_service, reporting_service)
    
    application.add_handler(conv_handler)
    for handler in reporting_handlers:
        application.add_handler(handler)

    logger.info("Bot is ready and listening for commands.")

    # --- Start the Bot ---
    application.run_polling()


if __name__ == "__main__":
    main()

