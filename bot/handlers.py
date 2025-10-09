"""
Contains the ConversationHandler and all related logic for the bot.
Architectural decision:
A ConversationHandler is used to guide the user through the multi-step
process of logging a workout. This maintains state between messages.
The user's progress is stored in `context.user_data`, which is a dict
persisted between handler calls for the same user and chat. This is where
we will build the `Training` object step-by-step.
"""

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.keyboards import create_training_selection_keyboard, create_yes_no_keyboard
from models.domain import Exercise, Training, Workout, WoSet
from models.enums import ExerciseName, Metric, TrainingName, WorkoutName
from services.mongo_service import MongoService
from services.training_config_service import TrainingConfigService

logger = logging.getLogger(__name__)

# States for the conversation
(
    SELECTING_TRAINING,
    AWAITING_DATE,
    AWAITING_DURATION,
    AWAITING_WORKOUT_COMPLETION,
    AWAITING_REST_TIME,
    AWAITING_SETS,
) = range(6)


# --- Helper Functions ---
def _cleanup_user_data(context: CallbackContext):
    """Resets the user_data dictionary for a new conversation."""
    keys_to_clear = [
        'training_obj', 'training_config', 'current_workout_idx', 
        'current_exercise_idx', 'last_set'
    ]
    for key in keys_to_clear:
        if key in context.user_data:
            del context.user_data[key]


async def _save_and_finish(update: Update, context: CallbackContext, mongo_service: MongoService):
    """Saves the final training object and ends the conversation."""
    training = context.user_data.get('training_obj')
    if mongo_service.save_training(training):
        await update.effective_message.reply_text("Great job! 💪 Training session saved successfully.")
    else:
        await update.effective_message.reply_text("Oh no! There was an error saving your training session. Please try again later.")
    
    _cleanup_user_data(context)
    return ConversationHandler.END


# --- Command Handlers (Entry & Exit) ---

async def start_logging_command(update: Update, context: CallbackContext, config_service: TrainingConfigService):
    """Starts the conversation to log a new training session."""
    _cleanup_user_data(context)
    
    training_names = config_service.get_training_names()
    if not training_names:
        await update.message.reply_text("No training programs are configured. Please contact the administrator.")
        return ConversationHandler.END

    keyboard = create_training_selection_keyboard(training_names)
    await update.message.reply_text(
        "Let's log a new training session! Which one did you complete?",
        reply_markup=keyboard,
    )
    return SELECTING_TRAINING


async def cancel_command(update: Update, context: CallbackContext):
    """Cancels and exits the current conversation."""
    _cleanup_user_data(context)
    await update.message.reply_text("Logging cancelled. Talk to you later!")
    return ConversationHandler.END


# --- State Handlers ---

async def selected_training(update: Update, context: CallbackContext, config_service: TrainingConfigService):
    """Handles the user's selection of a training program."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    training_name_str = query.data
    training_name = TrainingName(training_name_str)
    
    # Store the selected training config for later use
    workouts_config = config_service.get_workouts_for_training(training_name)
    context.user_data['training_config'] = {'workouts': workouts_config}
    
    # Initialize the main Training object
    context.user_data['training_obj'] = Training(
        user_id=user_id,
        name=training_name,
        date=datetime.now().date(), # Placeholder, will be updated
        duration=0 # Placeholder, will be updated
    )
    
    await query.edit_message_text(text=f"Selected Training: {training_name.value.title()}.")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="What was the date of the training? (e.g., YYYY-MM-DD, or 'today')"
    )
    return AWAITING_DATE

# Placeholder for the next steps
async def received_date(update: Update, context: CallbackContext):
    """Handles receiving the date of the training."""
    # This is a placeholder. The full implementation will be complex.
    # We will add date parsing and validation here.
    text = update.message.text
    try:
        if text.lower() == 'today':
            training_date = datetime.now().date()
        else:
            training_date = datetime.strptime(text, "%Y-%m-%d").date()
        
        context.user_data['training_obj'].date = training_date
        await update.message.reply_text("Got it. How long was the training in minutes?")
        return AWAITING_DURATION
    except ValueError:
        await update.message.reply_text("That doesn't look like a valid date. Please use YYYY-MM-DD format or write 'today'.")
        return AWAITING_DATE


async def not_implemented_yet(update: Update, context: CallbackContext):
    """A placeholder for features not yet implemented."""
    await update.message.reply_text("This part of the conversation isn't built yet. The conversation will now end.")
    _cleanup_user_data(context)
    return ConversationHandler.END


def get_conversation_handler(config_service: TrainingConfigService, mongo_service: MongoService) -> ConversationHandler:
    """Creates and returns the main ConversationHandler for the bot."""
    
    # Use functools.partial or lambda to pass services to handlers
    start_handler = lambda u, c: start_logging_command(u, c, config_service=config_service)
    selected_training_handler = lambda u, c: selected_training(u, c, config_service=config_service)

    return ConversationHandler(
        entry_points=[CommandHandler("log", start_handler)],
        states={
            SELECTING_TRAINING: [CallbackQueryHandler(selected_training_handler)],
            AWAITING_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_date)],
            # The next states will be added here as we build them out
            AWAITING_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, not_implemented_yet)],
            AWAITING_WORKOUT_COMPLETION: [CallbackQueryHandler(not_implemented_yet)],
            AWAITING_REST_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, not_implemented_yet)],
            AWAITING_SETS: [
                # We will need multiple handlers here for text, /done, /repeat, etc.
                MessageHandler(filters.TEXT & ~filters.COMMAND, not_implemented_yet)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )
