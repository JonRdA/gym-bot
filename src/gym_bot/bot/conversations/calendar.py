import logging
from datetime import datetime
from typing import Optional

from dateutil.relativedelta import relativedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
)

from gym_bot.bot.services import get_services
from gym_bot.bot.callbacks import CALENDAR_FILTER, make_callback, parse_callback
from gym_bot.bot.keyboards import chunk_buttons
from gym_bot.bot.state import clear_calendar_state, get_calendar_months, set_calendar_months

logger = logging.getLogger(__name__)

SELECT_WORKOUT = 0


async def calendar_start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    services = get_services(context)

    try:
        months = int(context.args[0]) if context.args else 1
    except (ValueError, IndexError):
        months = 1
    months = max(1, min(months, 12))
    set_calendar_months(context, months)

    config = await services.config.get_config(user_id)
    buttons = [
        InlineKeyboardButton(
            name.replace("_", " ").lower(),
            callback_data=make_callback(CALENDAR_FILTER, name),
        )
        for name in config.workout_names
    ]
    rows = chunk_buttons(buttons, 3)
    rows.append([InlineKeyboardButton("All Workouts", callback_data=make_callback(CALENDAR_FILTER, "all"))])

    await update.message.reply_text(
        "Which workout type for the calendar?",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return SELECT_WORKOUT


async def display_calendar(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    services = get_services(context)
    _, filter_choice = parse_callback(query.data)

    workout_filter: Optional[str] = None if filter_choice == "all" else filter_choice
    months = get_calendar_months(context)
    now = datetime.now()

    calendars = []
    for i in range(months):
        target = now - relativedelta(months=i)
        cal_str = await services.reporting.generate_activity_calendar(
            user_id, target.year, target.month, workout_filter
        )
        if cal_str:
            calendars.append(cal_str)

    if not calendars:
        await query.edit_message_text("No activity found for this filter.")
    else:
        await query.edit_message_text("\n\n".join(calendars), parse_mode="MarkdownV2")

    clear_calendar_state(context)
    return ConversationHandler.END


async def cancel_calendar(update: Update, context: CallbackContext):
    clear_calendar_state(context)
    await update.effective_message.reply_text("Cancelled.")
    return ConversationHandler.END


def build_calendar_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("calendar", calendar_start)],
        states={
            SELECT_WORKOUT: [
                CallbackQueryHandler(display_calendar, pattern=rf"^{CALENDAR_FILTER}:"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_calendar)],
    )
