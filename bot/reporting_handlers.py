"""
Handlers for all reporting-related commands.
"""
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

from config import Settings
from services.mongo import MongoService
from services.reporting_service import ReportingService
from services.training_config_service import TrainingConfigService

logger = logging.getLogger(__name__)

# --- Conversation states ---
SELECT_CALENDAR_WORKOUT = 0
SELECT_WORKOUT_FILTER, SELECT_SESSION = range(1, 3) # Renumbered


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
    keyboard = []
    for name in workout_names:
        # Use a 'cal_' prefix to avoid conflicts with other handlers
        keyboard.append([InlineKeyboardButton(name.title(), callback_data=f"cal_{name}")])
    keyboard.append([InlineKeyboardButton("All Workouts", callback_data="cal_all")])
    
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


async def cancel_calendar(update: Update, context: CallbackContext):
    """Cancels the calendar generation conversation."""
    user_id = update.effective_user.id
    logger.info("User %s cancelled calendar generation.", user_id)
    await update.effective_message.reply_text("Cancelled calendar generation.")
    # Clean up user_data
    if 'calendar_months' in context.user_data:
        del context.user_data['calendar_months']
    return ConversationHandler.END


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
    
    # This logic is different from the calendar's "All"
    # This one *includes* all, calendar *excludes* some.
    if filter_choice == 'all':
        trainings = mongo.query_between_dates(
            user_id=user_id, t0=t0, t1=t1
        )
    else:
        trainings = mongo.query_between_dates_including_workouts(
            user_id=user_id,
            t0=t0,
            t1=t1,
            required_workouts=[filter_choice]
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
        fallbacks=[CommandHandler("cancel", cancel_calendar)],
        conversation_timeout=300  # 5 minutes
    )
    
    view_sessions_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("view_training", lambda u, c: view_training_start(u, c, config_service=config_service))],
        states={
            SELECT_WORKOUT_FILTER: [CallbackQueryHandler(lambda u, c: list_sessions_after_filter(u, c, mongo=mongo, reporting_service=reporting_service, settings=settings), pattern="^filter_")],
            SELECT_SESSION: [CallbackQueryHandler(lambda u, c: select_session_to_view(u, c, mongo=mongo, reporting_service=reporting_service))],
        },
        fallbacks=[CommandHandler("cancel", cancel_view)],
        conversation_timeout=300 # 5 minutes
    )
    
    return [
        calendar_conv_handler,
        view_sessions_conv_handler
    ]
