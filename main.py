import logging
import os  # Import the os module
from datetime import timedelta

from telegram import Update
from telegram.ext import Application

from bot.handlers import get_conversation_handler
from bot.reporting_handlers import get_reporting_handlers
from config import Settings

# --- Import the new service ---
from services.exercise_reporting_service import ExerciseReportingService
from services.mongo import MongoService
from services.reporting_service import ReportingService
from services.training_config_service import TrainingConfigService

# --- Setup Logging ---
logging.basicConfig( level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger("httpx").setLevel(logging.WARNING)
# --- Set matplotlib logging to WARNING to reduce noise ---
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def main() -> None:
    """Instantiates dependencies based on environment and starts the bot."""
    
    # --- Environment Selection ---
    env = os.getenv('BOT_ENV', 'local')
    logger.info("Starting bot in '%s' environment.", env)

    try:
        settings = Settings.load(env)
        
        mongo = MongoService(settings)
        reporting_service = ReportingService(mongo, settings)
        config_service = TrainingConfigService("training_config.yaml", mongo)
        
        # --- Instantiate the new service ---
        exercise_reporting_service = ExerciseReportingService(mongo, config_service)

    except FileNotFoundError as e:
        logger.critical("Configuration Error: %s. Ensure your .env.%s file exists.", e, env)
        return
    except Exception as e:
        logger.critical("Failed to initialize services. Bot cannot start.", exc_info=True)
        return

    # --- Create the Telegram Application ---
    application = Application.builder().token(settings.bot.telegram_token).build()

    # --- Register Handlers ---
    conv_handler = get_conversation_handler(config_service, mongo)
    
    # --- Pass all services to the handler factory ---
    reporting_handlers = get_reporting_handlers(mongo, reporting_service, config_service, settings,
            exercise_reporting_service)
    
    application.add_handler(conv_handler)
    for handler in reporting_handlers:
        application.add_handler(handler)

    logger.info("Bot is ready and listening for commands.")
    application.run_polling()
    ptb.run_polling(poll_interval=0, timeout=timedelta(seconds=45), allowed_updates=Update.MESSAGE)


if __name__ == "__main__":
    main()