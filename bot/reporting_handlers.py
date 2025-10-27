"""
Handlers for all reporting-related commands.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from dateutil.relativedelta import relativedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
)

# Assuming keyboards.py is in the same directory or accessible
from bot.keyboards import chunk_list
from config import Settings
from services.mongo import MongoService
from services.reporting_service import ReportingService
from services.training_config_service import TrainingConfigService

logger = logging.getLogger(__name__)

# --- Conversation states ---
SELECT_CALENDAR_WORKOUT = 0
# State for view_training
SELECT_SESSION = 1 


async def calendar_start(update: Update, context: CallbackContext, config_service: TrainingConfigService):
    """Starts the /calendar convo by parsing month arg and asking for a workout filter."""
    user_id = update.effective_user.id
    logger.info("User %s started /calendar command.", user_id)
    
    try:
        months_to_plot = int(context.args[0]) if context.args else 1
    except (ValueError, IndexError):
        months_to_plot = 1
    
    if months_to_plot < 1:
        months_to_plot = 1
    
    context.user_data['calendar_months'] = months_to_plot
    
    # Get available workouts to build the filter
    workout_names = config_service.get_workout_names(user_id)
    
    # Create buttons with lowercase text
    buttons = [
        InlineKeyboardButton(
            name.lower(), 
            callback_data=f"cal_{name}"
        ) 
        for name in workout_names
    ]
    
    # Group into rows of 3
    keyboard = chunk_list(buttons, 3)
    # Add "All Workouts" button on its own row at the end
    keyboard.append(
        [InlineKeyboardButton("All Workouts", callback_data="cal_all")]
    )
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Which workout type would you like to see in the calendar?", 
        reply_markup=reply_markup
    )
    
    return SELECT_CALENDAR_WORKOUT


async def display_calendar_for_workout(update: Update, context: CallbackContext, reporting_service: ReportingService):
    """Handles workout filter selection and displays the correct calendar(s)."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    filter_choice = query.data.split('_', 1)[1]
    
    workout_filter: Optional[str] = None
    if filter_choice != "all":
        workout_filter = filter_choice
        
    months_to_plot = context.user_data.get('calendar_months', 1)
    now = datetime.now()
    calendar_strings = []
    
    logger.info(
        "User %s selected calendar filter '%s' for %s months", 
        user_id, filter_choice, months_to_plot
    )
    
    try:
        for i in range(months_to_plot):
            target_date = now - relativedelta(months=i)
            cal_str = reporting_service.generate_activity_calendar(
                user_id=user_id,
                year=target_date.year,
                month=target_date.month,
                workout_filter=workout_filter
            )
            if cal_str:
                calendar_strings.append(cal_str)
        
        if not calendar_strings:
            await query.edit_message_text("No activity found for this filter in the selected period.")
        else:
            # Join multiple calendars with double newlines
            final_message = "\n\n".join(calendar_strings)
            await query.edit_message_text(final_message, parse_mode='MarkdownV2')

    except Exception as e:
        logger.error("Error generating activity calendar for user %s: %s", user_id, e, exc_info=True)
        await query.edit_message_text("Sorry, I couldn't generate your activity calendar right now.")
    
    # Clean up user_data
    if 'calendar_months' in context.user_data:
        del context.user_data['calendar_months']
        
    return ConversationHandler.END


async def view_training_start(update: Update, context: CallbackContext, mongo: MongoService):
    """Starts /view_training: parses days, fetches sessions, and shows them in a keyboard."""
    user_id = update.effective_user.id
    logger.info("User %s started /view_training.", user_id)
    
    try:
        days_back = int(context.args[0]) if context.args else 10
    except (ValueError, IndexError):
        days_back = 10
    
    if days_back < 1:
        days_back = 1
    
    # Calculate date range
    t1 = datetime.now()
    t0 = t1 - timedelta(days=days_back)
    
    # Query for all trainings in the period
    trainings = mongo.query_between_dates(
        user_id=user_id,
        t0=t0,
        t1=t1,
    )
    
    if not trainings:
        await update.message.reply_text(
            f"No sessions found in the last {days_back} days."
        )
        return ConversationHandler.END

    keyboard = []
    for training in trainings:
        # Format: "DD-MM"
        date_str = training.date.strftime('%y-%m-%d')
        # Format: "(workout1, workout2)" in lowercase
        workout_names_str = ", ".join(
            [w.name.lower() for w in training.workouts]
        )
        
        summary_line = f"{date_str}:  ({workout_names_str})"
        callback_data = str(training.mongo_id)
        
        keyboard.append(
            [InlineKeyboardButton(summary_line, callback_data=callback_data)]
        )
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Here are your sessions from the last {days_back} days:", 
        reply_markup=reply_markup
    )
    
    return SELECT_SESSION


async def select_session_to_view(update: Update, context: CallbackContext, mongo: MongoService, reporting_service: ReportingService):
    """Handles user's selection and displays the detailed summary."""
    query = update.callback_query
    await query.answer()
    training_id = query.data
    
    # Check if data is a valid Mongo ID to avoid processing other callbacks
    if not training_id or len(training_id) != 24:
        logger.warning("Invalid callback data received in select_session_to_view: %s", training_id)
        await query.edit_message_text("An unexpected error occurred. Please try again.")
        return ConversationHandler.END

    logger.debug("User %s selected training_id: %s", query.from_user.id, training_id)
    training = mongo.get_training_by_id(training_id)
    
    if not training:
        await query.edit_message_text("Sorry, I couldn't find that training session.")
        return ConversationHandler.END

    summary = reporting_service.format_training_details(training)
    await query.edit_message_text(summary, parse_mode='Markdown')
        
    return ConversationHandler.END


async def cancel_conversation(update: Update, context: CallbackContext):
    """Cancels the ongoing conversation."""
    user_id = update.effective_user.id
    logger.info("User %s cancelled ongoing conversation.", user_id)
    await update.effective_message.reply_text("Cancelled conversation.")
    return ConversationHandler.END


def get_reporting_handlers(
    mongo: MongoService, 
    reporting_service: ReportingService, 
    config_service: TrainingConfigService,
    settings: Settings
) -> list:
    """Creates and returns all reporting-related handlers."""
    
    # New ConversationHandler for /calendar
    calendar_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("calendar", lambda u, c: calendar_start(u, c, config_service=config_service))],
        states={
            SELECT_CALENDAR_WORKOUT: [
                CallbackQueryHandler(
                    lambda u, c: display_calendar_for_workout(u, c, reporting_service=reporting_service), 
                    pattern="^cal_"
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        conversation_timeout=300  # 5 minutes
    )
    
    # Refactored ConversationHandler for /view_training
    view_sessions_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("view_training", lambda u, c: view_training_start(u, c, mongo=mongo))
        ],
        states={
            # State to handle the button press with the training_id
            SELECT_SESSION: [
                CallbackQueryHandler(
                    lambda u, c: select_session_to_view(u, c, mongo=mongo, reporting_service=reporting_service)
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    
    return [
        calendar_conv_handler,
        view_sessions_conv_handler
    ]