import logging
from datetime import datetime, timedelta

from bson import ObjectId
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
)

from gym_bot.bot.services import get_services
from gym_bot.bot.callbacks import SELECT_SESSION, make_callback, parse_callback
from gym_bot.domain.errors import TrainingNotFoundError

logger = logging.getLogger(__name__)

PICK_SESSION = 0


def _parse_days_arg(args: list[str] | None, default: int = 10) -> int:
    if not args:
        return default
    try:
        return max(1, int(args[0]))
    except (ValueError, TypeError):
        return default


async def view_start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    services = get_services(context)
    days = _parse_days_arg(context.args)

    t1 = datetime.now()
    t0 = t1 - timedelta(days=days)

    trainings = await services.trainings.find_between_dates(user_id, t0, t1)
    if not trainings:
        await update.message.reply_text(f"No sessions found in the last {days} days.")
        return ConversationHandler.END

    keyboard = []
    for t in trainings:
        date_str = t.date.strftime("%y-%m-%d")
        workouts = ", ".join(w.name.lower() for w in t.workouts)
        label = f"{date_str} ({workouts})"
        keyboard.append([
            InlineKeyboardButton(label, callback_data=make_callback(SELECT_SESSION, str(t.id)))
        ])

    await update.message.reply_text(
        f"Sessions from the last {days} days:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return PICK_SESSION


async def session_selected(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    _, training_id = parse_callback(query.data)
    services = get_services(context)

    if not ObjectId.is_valid(training_id):
        await query.edit_message_text("Invalid session reference.")
        return ConversationHandler.END

    try:
        training = await services.trainings.find_by_id(training_id)
    except TrainingNotFoundError:
        await query.edit_message_text("Session not found.")
        return ConversationHandler.END

    summary = services.reporting.format_training_details(training)
    await query.edit_message_text(summary, parse_mode="Markdown")
    return ConversationHandler.END


async def cancel_view(update: Update, context: CallbackContext):
    await update.effective_message.reply_text("Cancelled.")
    return ConversationHandler.END


def build_view_training_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("view_training", view_start)],
        states={
            PICK_SESSION: [
                CallbackQueryHandler(session_selected, pattern=rf"^{SELECT_SESSION}:"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_view)],
    )
