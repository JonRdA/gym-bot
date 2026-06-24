import logging
from datetime import datetime
from typing import Optional

from dateutil.relativedelta import relativedelta
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler

from gym_bot.bot.services import get_services

logger = logging.getLogger(__name__)


def _parse_args(args: list[str]) -> tuple[int, Optional[str]]:
    if not args:
        return 1, None
    if args[0].isdigit():
        months = max(1, min(int(args[0]), 12))
        workout_filter = args[1] if len(args) > 1 else None
    else:
        months = 1
        workout_filter = args[0]
    return months, workout_filter


async def calendar_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    services = get_services(context)
    months, workout_filter = _parse_args(context.args or [])

    now = datetime.now()
    calendars = []
    for i in range(months):
        target = now - relativedelta(months=i)
        cal_str = await services.reporting.generate_activity_calendar(
            user_id, target.year, target.month, workout_filter
        )
        if cal_str:
            calendars.append(cal_str)

    text = "\n\n".join(calendars) if calendars else "No activity found."
    await update.message.reply_text(text, parse_mode="MarkdownV2")

    heatmap = await services.reporting.generate_duration_heatmap(user_id, months, workout_filter)
    if heatmap:
        await update.message.reply_photo(heatmap)


def build_calendar_handler() -> CommandHandler:
    return CommandHandler("calendar", calendar_command)
