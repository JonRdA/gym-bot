import logging
import warnings

from telegram.warnings import PTBUserWarning

from gym_bot.bot.app import build_application
from gym_bot.bot.services import Services
from gym_bot.config.service import UserConfigService
from gym_bot.db.mongo import Database
from gym_bot.db.repositories import TrainingRepository
from gym_bot.reporting.exercise_reports import ExerciseReportingService
from gym_bot.reporting.service import ReportingService
from gym_bot.settings import Settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("matplotlib").setLevel(logging.WARNING)

warnings.filterwarnings(
    "ignore",
    message=r".*per_message=False.*",
    category=PTBUserWarning,
)

logger = logging.getLogger(__name__)


def main() -> None:
    settings = Settings()
    logger.info("Starting gym-bot")

    db = Database(settings.mongo_uri, settings.mongo_database)

    training_repo = TrainingRepository(db)
    config_service = UserConfigService(
        db, settings.default_config_path, settings.owner_user_id
    )
    reporting_service = ReportingService(training_repo, settings)
    exercise_reporting = ExerciseReportingService(training_repo, config_service)

    services = Services(
        trainings=training_repo,
        config=config_service,
        reporting=reporting_service,
        exercise_reporting=exercise_reporting,
        settings=settings,
    )

    app = build_application(services, settings.telegram_token)

    async def post_init(_app):
        await db.ping()
        await db.ensure_indexes()
        await config_service.sync_owner()

    app.post_init = post_init

    logger.info("Bot is ready and listening for commands")
    app.run_polling()


if __name__ == "__main__":
    main()
