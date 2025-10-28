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

from bot.keyboards import chunk_list
from bot.utils import chunk_list, get_date_range_for_month, get_date_range_from_days
from config import Settings
from services.exercise_reporting_service import ExerciseReportingService
from services.mongo import MongoService
from services.reporting_service import ReportingService
from services.training_config_service import TrainingConfigService

logger = logging.getLogger(__name__)

# --- Conversation states ---
SELECT_CALENDAR_WORKOUT = 0
SELECT_SESSION = 1
# --- New states for exercise reporting ---
SELECT_EXERCISE, SELECT_REPORT_TYPE = range(2, 4)


# --- Calendar Conversation (Unchanged) ---
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
    
    workout_names = config_service.get_workout_names(user_id)
    buttons = [
        InlineKeyboardButton(name.lower(), callback_data=f"cal_{name}") 
        for name in workout_names
    ]
    keyboard = chunk_list(buttons, 3)
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
    
    logger.info("User %s selected calendar filter '%s' for %s months", user_id, filter_choice, months_to_plot)
    
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
            final_message = "\n\n".join(calendar_strings)
            await query.edit_message_text(final_message, parse_mode='MarkdownV2')

    except Exception as e:
        logger.error("Error generating activity calendar for user %s: %s", user_id, e, exc_info=True)
        await query.edit_message_text("Sorry, I couldn't generate your activity calendar right now.")
    
    if 'calendar_months' in context.user_data:
        del context.user_data['calendar_months']
    return ConversationHandler.END

async def cancel_calendar(update: Update, context: CallbackContext):
    """Cancels the calendar generation conversation."""
    user_id = update.effective_user.id
    logger.info("User %s cancelled calendar generation.", user_id)
    await update.effective_message.reply_text("Cancelled calendar generation.")
    if 'calendar_months' in context.user_data:
        del context.user_data['calendar_months']
    return ConversationHandler.END

# --- View Training Conversation (Unchanged) ---
async def view_training_start(update: Update, context: CallbackContext, mongo: MongoService):
    """Starts /view_training: parses days, fetches sessions, and shows them in a keyboard."""
    user_id = update.effective_user.id
    logger.info("User %s started /view_training.", user_id)

    days_arg = context.args[0] if context.args else None
    t0, t1 = get_date_range_from_days(days_arg, default=10)
    days_back = (t1 - t0).days
    
    trainings = mongo.query_between_dates(user_id=user_id, t0=t0, t1=t1)
    
    if not trainings:
        await update.message.reply_text(f"No sessions found in the last {days_back} days.")
        return ConversationHandler.END

    keyboard = []
    for training in trainings:
        date_str = training.date.strftime('%d-%m')
        workout_names_str = ", ".join([w.name.lower() for w in training.workouts])
        summary_line = f"{date_str} ({workout_names_str})"
        callback_data = str(training.mongo_id)
        keyboard.append([InlineKeyboardButton(summary_line, callback_data=callback_data)])
    
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

async def cancel_view(update: Update, context: CallbackContext):
    """Cancels the view_sessions conversation."""
    user_id = update.effective_user.id
    logger.info("User %s cancelled viewing sessions.", user_id)
    await update.effective_message.reply_text("Cancelled viewing sessions.")
    return ConversationHandler.END


# --- 🆕 New Conversation: Exercise Report ---

async def exercise_report_start(update: Update, context: CallbackContext, config_service: TrainingConfigService):
    """Starts /exercise_report: parses days, asks for exercise."""
    user_id = update.effective_user.id
    logger.info("User %s started /exercise_report.", user_id)

    days_arg = context.args[0] if context.args else None
    t0, t1 = get_date_range_from_days(days_arg, default=30)
    days_back = (t1 - t0).days
    
    context.user_data['report_t0'] = t0
    context.user_data['report_t1'] = t1
    context.user_data['report_days'] = days_back

    # Get all exercises from config
    exercise_names = config_service.get_all_exercise_names(user_id)
    buttons = [
        InlineKeyboardButton(
            name.replace("_", " ").title(), 
            callback_data=f"ex_{name}"
        ) 
        for name in sorted(exercise_names)
    ]
    
    if not buttons:
        await update.message.reply_text("I couldn't find any exercises configured.")
        return ConversationHandler.END

    keyboard = chunk_list(buttons, 2) # Rows of 2 for readability
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Which exercise do you want to report on for the last {days_back} days?",
        reply_markup=reply_markup
    )
    return SELECT_EXERCISE


async def select_exercise_for_report(update: Update, context: CallbackContext, exercise_reporting_service: ExerciseReportingService):
    """Handles exercise selection, asks for report type."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    exercise_name = query.data.split('_', 1)[1]
    context.user_data['report_exercise'] = exercise_name
    
    logger.info("User %s selected exercise '%s' for report.", user_id, exercise_name)

    # Call the service to see what reports are available
    available_reports = exercise_reporting_service.get_available_reports_for_exercise(
        user_id, exercise_name
    )
    
    if not available_reports:
        await query.edit_message_text(
            f"No report types are available for '{exercise_name}'. "
            "This might be because its metrics aren't configured for reporting."
        )
        return ConversationHandler.END
    
    # Build keyboard for available reports
    keyboard = [
        [InlineKeyboardButton(display_name, callback_data=f"rt_{key}")]
        for key, display_name in available_reports
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Which report would you like for *{exercise_name.replace('_', ' ').title()}*?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return SELECT_REPORT_TYPE


async def generate_and_send_report(update: Update, context: CallbackContext,
        exercise_reporting_service: ExerciseReportingService):
    """Handles report type selection, generates and sends the report."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("Generating your report, please wait...")

    user_id = query.from_user.id
    report_type = query.data.split('_', 1)[1]
    
    # Get all data from context
    try:
        t0 = context.user_data['report_t0']
        t1 = context.user_data['report_t1']
        days = context.user_data['report_days']
        exercise_name = context.user_data['report_exercise']
    except KeyError as e:
        logger.error("Missing user_data in generate_report: %s", e)
        await query.edit_message_text("Sorry, your session expired. Please start over.")
        return ConversationHandler.END

    logger.info("User %s generating '%s' report for '%s'", user_id, report_type, exercise_name)

    # Call the service to get the report data
    report_data = exercise_reporting_service.generate_report(report_type=report_type, user_id=user_id,
        exercise_name=exercise_name, t0=t0, t1=t1,
    )

    if not report_data:
        await query.edit_message_text(
            f"No data found for *{exercise_name.replace('_', ' ').title()}* "
            f"in the last {days} days."
        )
        return ConversationHandler.END
    
    # Send the report
    text_summary = report_data.get("text", "Report generation failed.")
    chart = report_data.get("chart") # This is a BytesIO object

    await query.delete_message() # Delete the "Generating..." message
    
    if chart:
        # Send chart as a photo with the text summary as a caption
        await context.bot.send_photo(
            chat_id=user_id,
            photo=chart,
            caption=text_summary,
            parse_mode='Markdown'
        )
    else:
        # Just send the text
        await context.bot.send_message(
            chat_id=user_id,
            text=text_summary,
            parse_mode='Markdown'
        )

    # Clean up context
    for key in ['report_t0', 'report_t1', 'report_days', 'report_exercise']:
        if key in context.user_data:
            del context.user_data[key]
            
    return ConversationHandler.END


async def cancel_exercise_report(update: Update, context: CallbackContext):
    """Cancels the exercise report conversation."""
    user_id = update.effective_user.id
    logger.info("User %s cancelled exercise report.", user_id)
    await update.effective_message.reply_text("Cancelled exercise report.")
    
    # Clean up context
    for key in ['report_t0', 'report_t1', 'report_days', 'report_exercise']:
        if key in context.user_data:
            del context.user_data[key]
            
    return ConversationHandler.END


# --- Handler Factory ---

def get_reporting_handlers(
    mongo: MongoService, 
    reporting_service: ReportingService, 
    config_service: TrainingConfigService,
    settings: Settings,
    exercise_reporting_service: ExerciseReportingService # <-- Add new service
) -> list:
    """Creates and returns all reporting-related handlers."""
    
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
        conversation_timeout=300
    )
    
    view_sessions_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("view_training", lambda u, c: view_training_start(u, c, mongo=mongo))],
        states={
            SELECT_SESSION: [
                CallbackQueryHandler(
                    lambda u, c: select_session_to_view(u, c, mongo=mongo, reporting_service=reporting_service)
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_view)],
        conversation_timeout=300
    )
    
    exercise_report_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("exercise_report", lambda u, c: exercise_report_start(u, c, config_service=config_service))
        ],
        states={
            SELECT_EXERCISE: [
                CallbackQueryHandler(
                    lambda u, c: select_exercise_for_report(u, c, exercise_reporting_service=exercise_reporting_service),
                    pattern="^ex_"
                )
            ],
            SELECT_REPORT_TYPE: [
                CallbackQueryHandler(
                    lambda u, c: generate_and_send_report(u, c, exercise_reporting_service=exercise_reporting_service),
                    pattern="^rt_"
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_exercise_report)],
        conversation_timeout=300 # 5 minutes
    )
    
    return [
        calendar_conv_handler,
        view_sessions_conv_handler,
        exercise_report_conv_handler # <-- Add new handler to the list
    ]