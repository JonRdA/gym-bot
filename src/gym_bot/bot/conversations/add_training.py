import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from gym_bot.bot import messages
from gym_bot.bot.services import get_services
from gym_bot.bot.callbacks import ADD_WORKOUT, COMPLETED, FINISH_TRAINING, parse_callback
from gym_bot.bot.keyboards import completion_keyboard, workout_selection_keyboard
from gym_bot.bot.state import clear_add_state, get_add_state
from gym_bot.domain.metrics import METRIC_REGISTRY, format_metric_prompt
from gym_bot.domain.models import Exercise, ExerciseSet, Training, Workout

logger = logging.getLogger(__name__)

AWAITING_DATE, AWAITING_DURATION, SELECTING_WORKOUT, AWAITING_COMPLETION, PROCESSING_EXERCISES = range(5)


# --- Helpers ---

async def _prompt_workout_selection(update: Update, context: CallbackContext):
    services = get_services(context)
    state = get_add_state(context)
    user_id = update.effective_user.id

    config = await services.config.get_config(user_id)
    keyboard = workout_selection_keyboard(config.workout_names)

    text = messages.PROMPT_WORKOUT_NEXT if state.training.workouts else messages.PROMPT_WORKOUT_FIRST

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)

    return SELECTING_WORKOUT


async def _prompt_current_exercise(update: Update, context: CallbackContext):
    state = get_add_state(context)
    exercise_config = state.current_workout_config.exercises[state.current_exercise_idx]

    state.current_exercise = Exercise(name=exercise_config.name)

    if exercise_config.track_rest:
        name = exercise_config.name.replace("_", " ").title()
        await update.effective_message.reply_text(
            messages.PROMPT_REST_TIME.format(exercise_name=name)
        )
    else:
        await _prompt_sets(update, context)

    return PROCESSING_EXERCISES


async def _prompt_sets(update: Update, context: CallbackContext):
    state = get_add_state(context)
    exercise_config = state.current_workout_config.exercises[state.current_exercise_idx]

    title = exercise_config.name.replace("_", " ").title()
    metric_names = format_metric_prompt(exercise_config.metrics)

    await update.effective_message.reply_text(
        messages.PROMPT_SETS.format(exercise_title=title, metric_names=metric_names),
        parse_mode="MarkdownV2",
    )


# --- Entry / Exit ---

async def start_command(update: Update, context: CallbackContext):
    clear_add_state(context)
    user_id = update.effective_user.id
    logger.info("User %s started /add", user_id)

    state = get_add_state(context)
    state.training = Training(
        user_id=user_id,
        date=datetime.now(timezone.utc),
        duration=0,
    )

    await update.message.reply_text(
        f"{messages.START_MESSAGE}\n{messages.PROMPT_DATE}",
        parse_mode="MarkdownV2",
    )
    return AWAITING_DATE


async def cancel_command(update: Update, context: CallbackContext):
    logger.info("User %s cancelled /add", update.effective_user.id)
    clear_add_state(context)
    await update.message.reply_text(messages.CANCEL_MESSAGE)
    return ConversationHandler.END


# --- State handlers ---

async def received_date(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    state = get_add_state(context)

    try:
        if text.lower() == "today":
            date_obj = datetime.now(timezone.utc).date()
        else:
            date_obj = datetime.strptime(text, "%Y-%m-%d").date()

        state.training.date = datetime.combine(
            date_obj, datetime.min.time(), tzinfo=timezone.utc
        )
        await update.message.reply_text(messages.PROMPT_DURATION)
        return AWAITING_DURATION

    except ValueError:
        await update.message.reply_text(messages.ERROR_INVALID_DATE, parse_mode="MarkdownV2")
        return AWAITING_DATE


async def received_duration(update: Update, context: CallbackContext):
    try:
        duration = int(update.message.text.strip())
        if duration <= 0:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(messages.ERROR_INVALID_DURATION)
        return AWAITING_DURATION

    state = get_add_state(context)
    state.training.duration = duration
    return await _prompt_workout_selection(update, context)


async def selected_workout(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    _, workout_name = parse_callback(query.data)
    user_id = update.effective_user.id
    services = get_services(context)

    config = await services.config.get_config(user_id)
    workout_config = config.get_workout(workout_name)

    if not workout_config or not workout_config.exercises:
        await query.edit_message_text(
            messages.ERROR_NO_EXERCISES.format(workout_name=workout_name)
        )
        return SELECTING_WORKOUT

    state = get_add_state(context)
    state.current_workout_config = workout_config
    state.current_workout = Workout(name=workout_name, completed=True)
    state.current_exercise_idx = 0
    state.last_set = None

    logger.info("User %s selected workout '%s'", user_id, workout_name)

    await query.edit_message_text(messages.PROMPT_COMPLETION, reply_markup=completion_keyboard())
    return AWAITING_COMPLETION


async def finish_training(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    state = get_add_state(context)
    if not state.training.workouts:
        await query.edit_message_text(messages.ERROR_NO_WORKOUTS)
        return await _prompt_workout_selection(update, context)

    services = get_services(context)
    await query.edit_message_text("Saving your training session...")

    await services.trainings.save(state.training)
    await query.edit_message_text(messages.SAVE_SUCCESS)

    clear_add_state(context)
    return ConversationHandler.END


async def received_completion(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    _, value = parse_callback(query.data)
    state = get_add_state(context)
    state.current_workout.completed = value == "yes"

    workout_title = state.current_workout.name.replace("_", " ").title()
    await query.edit_message_text(messages.LOGGING_EXERCISES.format(workout_name=workout_title))

    return await _prompt_current_exercise(update, context)


async def received_text_in_exercise(update: Update, context: CallbackContext):
    state = get_add_state(context)
    exercise_config = state.current_workout_config.exercises[state.current_exercise_idx]

    # Route: rest time or set data
    if exercise_config.track_rest and state.current_exercise.rest_time is None:
        return await _handle_rest_time(update, context)
    return await _handle_set(update, context)


async def _handle_rest_time(update: Update, context: CallbackContext):
    try:
        rest_time = int(update.message.text.strip())
        if rest_time < 0:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text("Enter a valid number of seconds.")
        return PROCESSING_EXERCISES

    state = get_add_state(context)
    state.current_exercise.rest_time = rest_time
    await _prompt_sets(update, context)
    return PROCESSING_EXERCISES


async def _handle_set(update: Update, context: CallbackContext):
    state = get_add_state(context)
    exercise_config = state.current_workout_config.exercises[state.current_exercise_idx]
    metrics = exercise_config.metrics
    values = update.message.text.strip().split()

    if len(values) != len(metrics):
        await update.message.reply_text(
            messages.ERROR_INVALID_SET.format(count=len(metrics))
        )
        return PROCESSING_EXERCISES

    try:
        parsed = {}
        for name, raw in zip(metrics, values):
            defn = METRIC_REGISTRY[name]
            parsed[name] = defn.value_type(raw)

        new_set = ExerciseSet(metrics=parsed)
        state.current_exercise.sets.append(new_set)
        state.last_set = new_set

        count = len(state.current_exercise.sets)
        await update.message.reply_text(messages.SET_ADDED.format(count=count + 1))

    except (ValueError, KeyError):
        await update.message.reply_text(messages.ERROR_PROCESSING_SET)

    return PROCESSING_EXERCISES


async def done_command(update: Update, context: CallbackContext):
    state = get_add_state(context)

    if state.current_exercise and state.current_exercise.sets:
        state.current_workout.exercises.append(state.current_exercise)

    state.current_exercise = None
    state.last_set = None
    state.current_exercise_idx += 1

    if state.current_exercise_idx < len(state.current_workout_config.exercises):
        return await _prompt_current_exercise(update, context)

    # All exercises done for this workout
    state.training.workouts.append(state.current_workout)
    state.current_workout = None
    state.current_workout_config = None

    return await _prompt_workout_selection(update, context)


async def repeat_command(update: Update, context: CallbackContext):
    state = get_add_state(context)

    if state.last_set is None:
        await update.message.reply_text(messages.NO_SET_TO_REPEAT)
    else:
        state.current_exercise.sets.append(state.last_set)
        count = len(state.current_exercise.sets)
        await update.message.reply_text(messages.SET_ADDED.format(count=count + 1))

    return PROCESSING_EXERCISES


def build_add_training_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("add", start_command)],
        states={
            AWAITING_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_date),
            ],
            AWAITING_DURATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_duration),
            ],
            SELECTING_WORKOUT: [
                CallbackQueryHandler(selected_workout, pattern=rf"^{ADD_WORKOUT}:"),
                CallbackQueryHandler(finish_training, pattern=rf"^{FINISH_TRAINING}:"),
            ],
            AWAITING_COMPLETION: [
                CallbackQueryHandler(received_completion, pattern=rf"^{COMPLETED}:"),
            ],
            PROCESSING_EXERCISES: [
                CommandHandler("done", done_command),
                CommandHandler("repeat", repeat_command),
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_text_in_exercise),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        per_user=True,
        per_chat=True,
    )
