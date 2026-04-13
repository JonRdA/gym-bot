import logging
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
)

from gym_bot.bot.services import get_services
from gym_bot.bot.callbacks import REPORT_TYPE, SELECT_EXERCISE, make_callback, parse_callback
from gym_bot.bot.keyboards import chunk_buttons
from gym_bot.bot.state import clear_report_state, get_report_state

logger = logging.getLogger(__name__)

PICK_EXERCISE, PICK_REPORT = range(2)


def _parse_days_arg(args: list[str] | None, default: int = 30) -> int:
    if not args:
        return default
    try:
        return max(1, int(args[0]))
    except (ValueError, TypeError):
        return default


async def report_start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    services = get_services(context)
    days = _parse_days_arg(context.args)

    state = get_report_state(context)
    state.t1 = datetime.now()
    state.t0 = state.t1 - timedelta(days=days)
    state.days = days

    config = await services.config.get_config(user_id)
    names = sorted(config.get_all_exercise_names())

    if not names:
        await update.message.reply_text("No exercises configured.")
        clear_report_state(context)
        return ConversationHandler.END

    buttons = [
        InlineKeyboardButton(
            n.replace("_", " ").title(),
            callback_data=make_callback(SELECT_EXERCISE, n),
        )
        for n in names
    ]
    rows = chunk_buttons(buttons, 2)

    await update.message.reply_text(
        f"Which exercise? (last {days} days)",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return PICK_EXERCISE


async def exercise_selected(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    services = get_services(context)
    _, exercise_name = parse_callback(query.data)

    state = get_report_state(context)
    state.exercise_name = exercise_name

    reports = await services.exercise_reporting.get_available_reports(user_id, exercise_name)
    if not reports:
        await query.edit_message_text(f"No reports available for '{exercise_name}'.")
        clear_report_state(context)
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton(display, callback_data=make_callback(REPORT_TYPE, key))]
        for key, display in reports
    ]

    title = exercise_name.replace("_", " ").title()
    await query.edit_message_text(
        f"Report for *{title}*?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return PICK_REPORT


async def report_type_selected(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    services = get_services(context)
    _, report_type = parse_callback(query.data)
    state = get_report_state(context)

    await query.edit_message_text("Generating report...")

    report = await services.exercise_reporting.generate_report(
        report_type=report_type,
        user_id=user_id,
        exercise_name=state.exercise_name,
        t0=state.t0,
        t1=state.t1,
    )

    if not report:
        title = state.exercise_name.replace("_", " ").title()
        await query.edit_message_text(
            f"No data found for *{title}* in the last {state.days} days.",
            parse_mode="Markdown",
        )
        clear_report_state(context)
        return ConversationHandler.END

    text = report.get("text", "Report failed.")
    chart = report.get("chart")

    await query.delete_message()

    if chart:
        await context.bot.send_photo(
            chat_id=user_id, photo=chart, caption=text, parse_mode="Markdown"
        )
    else:
        await context.bot.send_message(
            chat_id=user_id, text=text, parse_mode="Markdown"
        )

    clear_report_state(context)
    return ConversationHandler.END


async def cancel_report(update: Update, context: CallbackContext):
    clear_report_state(context)
    await update.effective_message.reply_text("Cancelled.")
    return ConversationHandler.END


def build_exercise_report_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("exercise_report", report_start)],
        states={
            PICK_EXERCISE: [
                CallbackQueryHandler(exercise_selected, pattern=rf"^{SELECT_EXERCISE}:"),
            ],
            PICK_REPORT: [
                CallbackQueryHandler(report_type_selected, pattern=rf"^{REPORT_TYPE}:"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_report)],
    )
