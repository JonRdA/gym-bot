import logging

from telegram import Update
from telegram.ext import Application

from gym_bot.bot.conversations.add_training import build_add_training_handler
from gym_bot.bot.conversations.calendar import build_calendar_handler
from gym_bot.bot.conversations.exercise_report import build_exercise_report_handler
from gym_bot.bot.conversations.view_training import build_view_training_handler
from gym_bot.bot.services import Services

logger = logging.getLogger(__name__)


async def error_handler(update: object, context) -> None:
    logger.error("Unhandled exception", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "Something went wrong. Please try again."
        )


def build_application(services: Services, token: str) -> Application:
    app = Application.builder().token(token).build()
    app.bot_data["services"] = services

    app.add_handler(build_add_training_handler())
    app.add_handler(build_calendar_handler())
    app.add_handler(build_view_training_handler())
    app.add_handler(build_exercise_report_handler())

    app.add_error_handler(error_handler)

    return app
