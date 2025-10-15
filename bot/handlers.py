import logging
from datetime import datetime, timezone
from typing import List

from pydantic import ValidationError
from telegram import Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot import messages
from bot.keyboards import create_completion_keyboard, create_workout_selection_keyboard
from models.domain import Exercise, Training, Workout, WoSet
from models.enums import ExerciseName, Metric, WorkoutName
from services.mongo_service import MongoService
from services.training_config_service import TrainingConfigService

logger = logging.getLogger(__name__)

# States for the conversation
(
    AWAITING_DATE,
    AWAITING_DURATION,
    SELECTING_WORKOUT,
    AWAITING_WORKOUT_COMPLETION,
    PROCESSING_EXERCISES,
) = range(5)


# --- Helper Functions ---
def _cleanup_user_data(context: CallbackContext):
    """Resets the user_data dictionary for a new conversation."""
    keys_to_clear = [
        'training_obj', 'current_workout_config', 'current_workout_obj',
        'current_exercise_idx', 'current_exercise_obj', 'last_set'
    ]
    for key in keys_to_clear:
        if key in context.user_data:
            del context.user_data[key]
    logger.debug("Cleaned up user_data for chat_id: %s", context._chat_id)


async def _ask_to_select_workout(update: Update, context: CallbackContext, config_service: TrainingConfigService):
    """Asks the user to add a workout to the training or finish."""
    workout_names = config_service.get_workout_names()
    keyboard = create_workout_selection_keyboard(workout_names)
    
    message = (
        messages.PROMPT_WORKOUT_SELECTION_NEXT
        if context.user_data['training_obj'].workouts
        else messages.PROMPT_WORKOUT_SELECTION_FIRST
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=keyboard)
    else:
        await update.message.reply_text(message, reply_markup=keyboard)
        
    return SELECTING_WORKOUT


async def _ask_about_current_exercise(update: Update, context: CallbackContext):
    """Asks about rest time or sets for the current exercise."""
    exercise_idx = context.user_data['current_exercise_idx']
    exercise_config = context.user_data['current_workout_config']['exercises'][exercise_idx]
    exercise_name = ExerciseName(exercise_config['name'])

    context.user_data['current_exercise_obj'] = Exercise(name=exercise_name)

    if exercise_config.get('track_rest'):
        prompt = messages.PROMPT_REST_TIME.format(exercise_name=exercise_name.value.replace("_", " ").title())
        await update.effective_message.reply_text(prompt)
    else:
        await _ask_for_sets(update, context)
    return PROCESSING_EXERCISES


async def _ask_for_sets(update: Update, context: CallbackContext):
    """Constructs and sends the prompt for entering sets."""
    exercise_idx = context.user_data['current_exercise_idx']
    exercise_config = context.user_data['current_workout_config']['exercises'][exercise_idx]
    exercise_name = ExerciseName(exercise_config['name'])
    metrics = [Metric[m.upper()] for m in exercise_config['metrics']]
    
    exercise_title = exercise_name.value.replace("_", " ").title()
    metric_names = " ".join([f"<{m.value}\\({m.unit.value}\\)>" if m.unit else f"<{m.value}>" for m in metrics])
    
    prompt = messages.PROMPT_SETS.format(exercise_title=exercise_title, metric_names=metric_names)
    await update.effective_message.reply_text(prompt, parse_mode='MarkdownV2')


# --- Command Handlers (Entry & Exit) ---

async def start_logger_command(update: Update, context: CallbackContext):
    """Starts the conversation to log a new training session."""
    _cleanup_user_data(context)
    user_id = update.effective_user.id
    logger.info("User %s started a new training log conversation.", user_id)
    
    context.user_data['training_obj'] = Training(
        user_id=user_id, date=datetime.now().date(), duration=0
    )
    
    await update.message.reply_text(f"{messages.START_MESSAGE}\n{messages.PROMPT_DATE}", parse_mode="MarkdownV2")
    return AWAITING_DATE


async def cancel_command(update: Update, context: CallbackContext):
    """Cancels and exits the current conversation."""
    logger.info("User %s cancelled the conversation.", update.effective_user.id)
    _cleanup_user_data(context)
    await update.message.reply_text(messages.CANCEL_MESSAGE)
    return ConversationHandler.END


# --- State Handlers ---

async def received_date(update: Update, context: CallbackContext):
    """Handles receiving the date of the training."""
    text = update.message.text
    try:
        if text.lower() == 'today':
            # Get today's date and combine with midnight time in UTC
            training_date_obj = datetime.now(timezone.utc).date()
            training_datetime = datetime.combine(training_date_obj, datetime.min.time(), tzinfo=timezone.utc)
        else:
            # Parse date string and combine with midnight time, making it UTC
            training_date_obj = datetime.strptime(text, "%Y-%m-%d").date()
            training_datetime = datetime.combine(training_date_obj, datetime.min.time(), tzinfo=timezone.utc)
        
        context.user_data['training_obj'].date = training_datetime
        logger.debug("User %s set date to %s", update.effective_user.id, training_datetime)
        await update.message.reply_text(messages.PROMPT_DURATION)
        return AWAITING_DURATION
    except ValueError:
        logger.warning("User %s entered an invalid date format: %s", update.effective_user.id, text)
        await update.message.reply_text(messages.ERROR_INVALID_DATE, parse_mode='MarkdownV2')
        return AWAITING_DATE


async def received_duration(update: Update, context: CallbackContext, config_service: TrainingConfigService):
    """Handles receiving the duration and moves to workout selection."""
    try:
        duration = int(update.message.text)
        if duration <= 0: raise ValueError
        context.user_data['training_obj'].duration_minutes = duration
        logger.debug("User %s set duration to %d minutes", update.effective_user.id, duration)
        return await _ask_to_select_workout(update, context, config_service)
    except (ValueError, TypeError):
        logger.warning("User %s entered an invalid duration.", update.effective_user.id)
        await update.message.reply_text(messages.ERROR_INVALID_DURATION)
        return AWAITING_DURATION

# --- SELECTING_WORKOUT State ---

async def selected_workout_to_add(update: Update, context: CallbackContext, config_service: TrainingConfigService):
    """Handles a user selecting a workout and asks if it was completed."""
    query = update.callback_query
    await query.answer()
    
    workout_name_str = query.data.split('_')[1] # from "addworkout_upper"
    workout_name = WorkoutName(workout_name_str)
    context.user_data['current_workout_name'] = workout_name
    
    logger.info("User %s selected workout '%s'", query.from_user.id, workout_name_str)
    
    workout_config = config_service.get_workout_details(workout_name)
    if not workout_config or not workout_config.get('exercises'):
        await query.edit_message_text(messages.ERROR_NO_EXERCISES_CONFIGURED.format(workout_name=workout_name_str))
        return SELECTING_WORKOUT

    context.user_data['current_workout_config'] = workout_config

    keyboard = create_completion_keyboard()
    await query.edit_message_text(messages.PROMPT_WORKOUT_COMPLETION, reply_markup=keyboard)
    return AWAITING_WORKOUT_COMPLETION


async def finish_training_command(update: Update, context: CallbackContext, mongo_service: MongoService):
    """Handles the user finishing the training log."""
    query = update.callback_query
    await query.answer()
    
    if not context.user_data['training_obj'].workouts:
        await query.edit_message_text(messages.ERROR_NO_WORKOUTS_ADDED)
        return await _ask_to_select_workout(update, context, config_service)
        
    await query.edit_message_text("Saving your training session...")
    
    training = context.user_data.get('training_obj')
    if mongo_service.save_training(training):
        await query.edit_message_text(messages.SAVE_SUCCESS)
    else:
        await query.edit_message_text(messages.SAVE_ERROR)

    _cleanup_user_data(context)
    return ConversationHandler.END

# --- AWAITING_WORKOUT_COMPLETION State ---

async def received_workout_completion(update: Update, context: CallbackContext):
    """Handles the 'Yes'/'No' response for workout completion."""
    query = update.callback_query
    await query.answer()
    
    workout_name = context.user_data['current_workout_name']

    completed = query.data == "completed_yes"
    context.user_data['current_workout_obj'] = Workout(name=workout_name, completed=completed)
    context.user_data['current_workout_obj'].completed = completed
    context.user_data['current_exercise_idx'] = 0
    
    workout_name = context.user_data['current_workout_obj'].name.value.title()
    await query.edit_message_text(messages.LOGGING_EXERCISES_FOR.format(workout_name=workout_name))
    
    return await _ask_about_current_exercise(update, context)

# --- PROCESSING_EXERCISES State ---

async def handle_next_exercise(update: Update, context: CallbackContext, config_service: TrainingConfigService):
    """Logic to move to the next exercise or back to workout selection."""
    if context.user_data['current_exercise_obj'].sets:
        context.user_data['current_workout_obj'].exercises.append(context.user_data['current_exercise_obj'])
    else:
        logger.debug("No sets logged for exercise %s.", context.user_data['current_exercise_obj'].name.value)
        
    del context.user_data['current_exercise_obj']
    if 'last_set' in context.user_data: del context.user_data['last_set']

    context.user_data['current_exercise_idx'] += 1
    exercise_idx = context.user_data['current_exercise_idx']
    workout_config = context.user_data['current_workout_config']

    if exercise_idx < len(workout_config['exercises']):
        logger.debug("Moving to next exercise: index %s", exercise_idx)
        return await _ask_about_current_exercise(update, context)
    else:
        logger.info("Finished all exercises for workout '%s'", context.user_data['current_workout_obj'].name.value)
        context.user_data['training_obj'].workouts.append(context.user_data['current_workout_obj'])
        del context.user_data['current_workout_obj']
        del context.user_data['current_workout_config']
        
        return await _ask_to_select_workout(update, context, config_service)


async def received_set(update: Update, context: CallbackContext):
    """Handles a message containing set data."""
    values = update.message.text.split()
    
    exercise_idx = context.user_data['current_exercise_idx']
    exercise_config = context.user_data['current_workout_config']['exercises'][exercise_idx]
    metrics: List[Metric] = [Metric[m.upper()] for m in exercise_config['metrics']]

    if len(values) != len(metrics):
        await update.message.reply_text(messages.ERROR_INVALID_SET_INPUT.format(count=len(metrics)))
        return PROCESSING_EXERCISES
    
    try:
        metrics_dict = {m: (float(v) if '.' in v else int(v)) for m, v in zip(metrics, values)}
        new_set = WoSet(metrics=metrics_dict)
        context.user_data['current_exercise_obj'].sets.append(new_set)
        context.user_data['last_set'] = new_set
        
        logger.debug("Added set for user %s: %s", update.effective_user.id, new_set.model_dump_json())
        count = len(context.user_data['current_exercise_obj'].sets)
        await update.message.reply_text(messages.ADDED_SET.format(count=count))
    except (ValueError, ValidationError) as e:
        logger.error("Error parsing set data '%s': %s", update.message.text, e)
        await update.message.reply_text(messages.ERROR_PROCESSING_SET)
    return PROCESSING_EXERCISES


async def received_rest_time(update: Update, context: CallbackContext):
    """Handles receiving the rest time for an exercise."""
    try:
        rest_time = int(update.message.text)
        if rest_time < 0: raise ValueError
        context.user_data['current_exercise_obj'].rest_time_seconds = rest_time
        await _ask_for_sets(update, context)
    except (ValueError, TypeError):
        await update.message.reply_text("Please enter a valid number for rest time in seconds.")
    return PROCESSING_EXERCISES


async def repeat_set_command(update: Update, context: CallbackContext):
    """Handles the /repeat command to log the last set again."""
    if 'last_set' not in context.user_data:
        await update.message.reply_text(messages.NO_SET_TO_REPEAT)
    else:
        context.user_data['current_exercise_obj'].sets.append(context.user_data['last_set'])
        count = len(context.user_data['current_exercise_obj'].sets)
        await update.message.reply_text(messages.ADDED_SET.format(count=count))
    return PROCESSING_EXERCISES


async def rest_time_or_set_router(update: Update, context: CallbackContext):
    """Routes message to either rest time or set handler."""
    exercise_obj = context.user_data.get('current_exercise_obj')
    exercise_config = context.user_data['current_workout_config']['exercises'][context.user_data['current_exercise_idx']]

    if exercise_config.get('track_rest') and exercise_obj.rest_time_seconds is None:
        return await received_rest_time(update, context)
    else:
        return await received_set(update, context)


def get_conversation_handler(config_service: TrainingConfigService, mongo_service: MongoService) -> ConversationHandler:
    """Creates and returns the main ConversationHandler for the bot."""
    
    # --- Handler setup using lambdas for dependency injection ---
    received_duration_handler = lambda u, c: received_duration(u, c, config_service=config_service)
    selected_workout_handler = lambda u, c: selected_workout_to_add(u, c, config_service=config_service)
    finish_training_handler = lambda u, c: finish_training_command(u, c, mongo_service=mongo_service)
    done_exercise_handler = lambda u, c: handle_next_exercise(u, c, config_service=config_service)

    return ConversationHandler(
        entry_points=[CommandHandler("add_training", start_logger_command)],
        states={
            AWAITING_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_date)],
            AWAITING_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_duration_handler)],
            SELECTING_WORKOUT: [
                CallbackQueryHandler(selected_workout_handler, pattern="^addworkout_"),
                CallbackQueryHandler(finish_training_handler, pattern="^finish_training$"),
            ],
            AWAITING_WORKOUT_COMPLETION: [
                CallbackQueryHandler(received_workout_completion, pattern="^completed_"),
            ],
            PROCESSING_EXERCISES: [
                CommandHandler("done", done_exercise_handler),
                CommandHandler("repeat", repeat_set_command),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rest_time_or_set_router),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        per_user=True,
        per_chat=True,
    )
