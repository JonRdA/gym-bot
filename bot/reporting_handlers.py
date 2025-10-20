"""
Handlers for all reporting-related commands.
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
)

from config import settings
from services.mongo_service import MongoService
from services.reporting_service import ReportingService

logger = logging.getLogger(__name__)

# --- Conversation states for /view_training ---
SELECT_TRAINING, SHOW_TRAINING = range(2)


async def activity_calendar_command(update: Update, context: CallbackContext, reporting_service: ReportingService):
    """Displays a calendar of the current month showing training days."""
    user_id = update.effective_user.id
    try:
        calendar_str = reporting_service.generate_activity_calendar(user_id)
        if calendar_str:
            await update.message.reply_text(calendar_str, parse_mode='MarkdownV2')
        else:
            await update.message.reply_text("Could not generate calendar.")
    except Exception as e:
        logger.error("Error generating activity calendar for user %s: %s", user_id, e, exc_info=True)
        await update.message.reply_text("Sorry, I couldn't generate your activity calendar right now.")


async def view_training_start(update: Update, context: CallbackContext, mongo_service: MongoService, reporting_service: ReportingService):
    """Starts the /view_training convo by showing recent trainings."""
    user_id = update.effective_user.id
    logger.info("User %s started /view_training.", user_id)
    
    # Default to 7 days, but allow user to override with an argument
    try:
        days_to_show = int(context.args[0]) if context.args else 7
    except (ValueError, IndexError):
        days_to_show = 7

    excluded = settings.reporting.excluded_workouts
    last_trainings = mongo_service.get_trainings_for_last_n_days(user_id, days=days_to_show, excluded_workouts=excluded)
    
    if not last_trainings:
        await update.message.reply_text(f"You haven't logged any trainings (excluding '{', '.join(excluded)}') in the last {days_to_show} days!")
        return ConversationHandler.END

    keyboard = []
    for training in last_trainings:
        summary_line = reporting_service.format_training_summary(training).split('\n')[0] # Get first line
        callback_data = str(training['_id'])
        keyboard.append([InlineKeyboardButton(summary_line, callback_data=callback_data)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Which of the last {days_to_show} days' sessions would you like to view?", reply_markup=reply_markup)
    
    return SELECT_TRAINING


async def select_training_to_view(update: Update, context: CallbackContext, mongo_service: MongoService, reporting_service: ReportingService):
    """Handles user's selection and displays the detailed summary."""
    query = update.callback_query
    await query.answer()
    training_id = query.data
    
    training = mongo_service.get_training_by_id(training_id)
    
    if not training:
        await query.edit_message_text("Sorry, I couldn't find that training session.")
        return ConversationHandler.END

    summary = reporting_service.format_training_details(training)
    await query.edit_message_text(summary, parse_mode='Markdown')
    return ConversationHandler.END


async def cancel_view(update: Update, context: CallbackContext):
    """Cancels the view_training conversation."""
    await update.effective_message.reply_text("Cancelled viewing training.")
    return ConversationHandler.END


def get_reporting_handlers(mongo_service: MongoService, reporting_service: ReportingService) -> list:
    """Creates and returns all reporting-related handlers."""
    
    view_training_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("view_training", lambda u, c: view_training_start(u, c, mongo_service=mongo_service, reporting_service=reporting_service))],
        states={
            SELECT_TRAINING: [CallbackQueryHandler(lambda u, c: select_training_to_view(u, c, mongo_service=mongo_service, reporting_service=reporting_service))],
        },
        fallbacks=[CommandHandler("cancel", cancel_view)]
    )
    
    return [
        CommandHandler("activity_calendar", lambda u, c: activity_calendar_command(u, c, reporting_service=reporting_service)),
        view_training_conv_handler
    ]

