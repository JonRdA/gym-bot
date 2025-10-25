"""
Handlers for all reporting-related commands.
"""
import logging
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
)

from config import Settings
from services.mongo import MongoService
from services.reporting_service import ReportingService
from services.training_config_service import TrainingConfigService

logger = logging.getLogger(__name__)

# --- Conversation states for /view_sessions ---
SELECT_WORKOUT_FILTER, SELECT_SESSION = range(2)


async def calendar_command(update: Update, context: CallbackContext, reporting_service: ReportingService):
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


async def view_training_start(update: Update, context: CallbackContext, config_service: TrainingConfigService):
    """Starts the /view_sessions convo by asking for a workout filter."""
    user_id = update.effective_user.id
    logger.info("User %s started /view_sessions.", user_id)
    
    try:
        months_back = int(context.args[0]) if context.args else 0
    except (ValueError, IndexError):
        months_back = 0
    
    # Calculate date range
    t1 = datetime.now()
    t0 = (t1 - relativedelta(months=months_back)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    context.user_data['sessions_t0'] = t0
    context.user_data['sessions_t1'] = t1
    
    # Get available workouts to build the filter
    workout_names = config_service.get_workout_names(user_id)
    keyboard = []
    for name in workout_names:
        keyboard.append([InlineKeyboardButton(name.title(), callback_data=f"filter_{name}")])
    keyboard.append([InlineKeyboardButton("All Workouts", callback_data="filter_all")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Which workout type would you like to see?", reply_markup=reply_markup)
    
    return SELECT_WORKOUT_FILTER


async def list_sessions_after_filter(update: Update, context: CallbackContext, mongo: MongoService, reporting_service: ReportingService, settings: Settings):
    """Handles the workout filter selection and lists the matching sessions."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    filter_choice = query.data.split('_')[1]
    
    t0 = context.user_data['sessions_t0']
    t1 = context.user_data['sessions_t1']
    
    required_workout = None if filter_choice == 'all' else filter_choice
    
    trainings = mongo.query_between_dates_including_workouts(
        user_id=user_id,
        t0=t0,
        t1=t1,
        required_workouts=[required_workout]
    )
    
    if not trainings:
        await query.edit_message_text(f"No '{filter_choice}' sessions found in the selected period.")
        return ConversationHandler.END

    keyboard = []
    for training in trainings:
        summary_line = reporting_service.format_training_summary(training).split('\n')[0]
        callback_data = str(training.mongo_id)
        keyboard.append([InlineKeyboardButton(summary_line, callback_data=callback_data)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Which of these sessions would you like to view?", reply_markup=reply_markup)
    
    return SELECT_SESSION


async def select_session_to_view(update: Update, context: CallbackContext, mongo: MongoService, reporting_service: ReportingService):
    """Handles user's selection and displays the detailed summary."""
    query = update.callback_query
    await query.answer()
    training_id = query.data
    
    training = mongo.get_training_by_id(training_id)
    
    if not training:
        await query.edit_message_text("Sorry, I couldn't find that training session.")
        return ConversationHandler.END

    summary = reporting_service.format_training_details(training)
    await query.edit_message_text(summary, parse_mode='Markdown')
    
    # Clean up user_data
    if 'sessions_t0' in context.user_data:
        del context.user_data['sessions_t0']
    if 'sessions_t1' in context.user_data:
        del context.user_data['sessions_t1']
        
    return ConversationHandler.END


async def cancel_view(update: Update, context: CallbackContext):
    """Cancels the view_sessions conversation."""
    await update.effective_message.reply_text("Cancelled viewing sessions.")
    # Clean up user_data
    if 'sessions_t0' in context.user_data:
        del context.user_data['sessions_t0']
    if 'sessions_t1' in context.user_data:
        del context.user_data['sessions_t1']
    return ConversationHandler.END


def get_reporting_handlers(
    mongo: MongoService, 
    reporting_service: ReportingService, 
    config_service: TrainingConfigService,
    settings: Settings
) -> list:
    """Creates and returns all reporting-related handlers."""
    
    view_sessions_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("view_training", lambda u, c: view_training_start(u, c, config_service=config_service))],
        states={
            SELECT_WORKOUT_FILTER: [CallbackQueryHandler(lambda u, c: list_sessions_after_filter(u, c, mongo=mongo, reporting_service=reporting_service, settings=settings), pattern="^filter_")],
            SELECT_SESSION: [CallbackQueryHandler(lambda u, c: select_session_to_view(u, c, mongo=mongo, reporting_service=reporting_service))],
        },
        fallbacks=[CommandHandler("cancel", cancel_view)]
    )
    
    return [
        CommandHandler("calendar", lambda u, c: calendar_command(u, c, reporting_service=reporting_service)),
        view_sessions_conv_handler
    ]

