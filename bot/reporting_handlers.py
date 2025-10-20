"""
Handlers for all reporting-related commands.
"""
import calendar
import logging
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
)

from services.mongo_service import MongoService

logger = logging.getLogger(__name__)

# --- Conversation states for /view_training ---
SELECT_TRAINING, SHOW_TRAINING = range(2)


async def activity_calendar_command(update: Update, context: CallbackContext, mongo_service: MongoService):
    """Displays a calendar of the current month showing training days."""
    user_id = update.effective_user.id
    now = datetime.now()
    
    try:
        training_dates = mongo_service.get_training_dates_for_month(user_id, now.year, now.month)
        training_days = {d.day for d in training_dates}

        cal = calendar.TextCalendar(calendar.MONDAY)
        month_calendar = cal.formatmonth(now.year, now.month).split('\n')
        
        header = f"🗓️ Activity for {now.strftime('%B %Y')}\n"
        calendar_str = f"`{month_calendar[0]}\n{month_calendar[1]}\n"

        for line in month_calendar[2:]:
            if not line.strip(): continue
            new_line = line
            for day_num in training_days:
                # Pad day number to handle single-digit days correctly
                day_str = f"{day_num: >2}"
                if day_str in new_line:
                    new_line = new_line.replace(day_str, "🏋️")
            calendar_str += new_line + "\n"
        
        calendar_str += "`"
        
        await update.message.reply_text(header + calendar_str, parse_mode='MarkdownV2')

    except Exception as e:
        logger.error("Error generating activity calendar for user %s: %s", user_id, e, exc_info=True)
        await update.message.reply_text("Sorry, I couldn't generate your activity calendar right now.")


async def view_training_start(update: Update, context: CallbackContext, mongo_service: MongoService):
    """Starts the /view_training convo by showing the last 4 trainings."""
    user_id = update.effective_user.id
    logger.info("User %s started /view_training.", user_id)
    
    last_trainings = mongo_service.get_last_n_trainings(user_id, n=4)
    
    if not last_trainings:
        await update.message.reply_text("You haven't logged any trainings yet!")
        return ConversationHandler.END

    keyboard = []
    for training in last_trainings:
        # Extract workout names, show 'N/A' if workouts list is missing/empty
        workout_names = ", ".join([w.get('name', 'N/A') for w in training.get('workouts', [])])
        label = f"{training['date'].strftime('%Y-%m-%d')} - [{workout_names.lower()}]"
        
        # Callback data is the MongoDB document ID
        callback_data = str(training['_id'])
        keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Which training session would you like to view?", reply_markup=reply_markup)
    
    return SELECT_TRAINING


async def select_training_to_view(update: Update, context: CallbackContext, mongo_service: MongoService):
    """Handles user's selection and displays the detailed summary."""
    query = update.callback_query
    await query.answer()
    training_id = query.data
    
    training = mongo_service.get_training_by_id(training_id)
    
    if not training:
        await query.edit_message_text("Sorry, I couldn't find that training session.")
        return ConversationHandler.END

    # --- Format the detailed summary ---
    summary = f"*Training on {training['date'].strftime('%Y-%m-%d')}*\n"
    summary += f"Duration: {training['duration']} minutes\n\n"
    
    for workout in training.get('workouts', []):
        completed_emoji = "✅" if workout.get('completed', False) else "❌"
        summary += f"*{workout.get('name', 'N/A').title()}* {completed_emoji}\n"
        
        for exercise in workout.get('exercises', []):
            metrics_list = " ".join(exercise.get('sets')[0].get('metrics').keys())
            summary += f"  - *{exercise.get('name', 'N/A').replace('_', ' ').title()}*\n    {metrics_list}\n"
            metrics_str = metrics_list
            for i, s in enumerate(exercise.get('sets', [])):
                metrics_str = ", ".join([f"{v}" for k, v in s.get('metrics', {}).items()])
                summary += f"      set {i+1}: [{metrics_str}\n]"

    await query.edit_message_text(summary, parse_mode='Markdown')
    return ConversationHandler.END


async def cancel_view(update: Update, context: CallbackContext):
    """Cancels the view_training conversation."""
    await update.message.reply_text("Cancelled viewing training.")
    return ConversationHandler.END


def get_reporting_handlers(mongo_service: MongoService) -> list:
    """Creates and returns all reporting-related handlers."""
    
    view_training_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("view_training", lambda u, c: view_training_start(u, c, mongo_service=mongo_service))],
        states={
            SELECT_TRAINING: [CallbackQueryHandler(lambda u, c: select_training_to_view(u, c, mongo_service=mongo_service))],
        },
        fallbacks=[CommandHandler("cancel", cancel_view)]
    )
    
    return [
        CommandHandler("activity_calendar", lambda u, c: activity_calendar_command(u, c, mongo_service=mongo_service)),
        view_training_conv_handler
    ]
