# --- Conversation Start/End ---
START_MESSAGE = "Let's add a new training session\\! 🏋️"
SAVE_SUCCESS = "Great job! 💪 Training saved."
SAVE_ERROR = "Oh no! There was an error saving your session."
CANCEL_MESSAGE = "Logging cancelled. See you next time!"

# --- Prompts ---
PROMPT_DATE = "Insert date\\. `YYYY-MM-DD` or `today`"
PROMPT_DURATION = "Training duration in minutes?"
PROMPT_WORKOUT_SELECTION_FIRST = "Let's add the first workout."
PROMPT_WORKOUT_SELECTION_NEXT = "Add another workout, or finish."
PROMPT_WORKOUT_COMPLETION = "Did you complete this workout?"
PROMPT_REST_TIME = "Rest time in seconds for {exercise_name}?"
PROMPT_SETS = (
    "Enter sets for *{exercise_title}*\\.\n"
    "Format: `{metric_names}`\n"
    "/done"
)

# --- Confirmations & Info ---
LOGGING_EXERCISES_FOR = "Add exercises for {workout_name}."
ADD_SET = "Set {count}: /repeat or /done."
# REPEATED_SET = "Set {count} (repeated). Next, /repeat, or /done."
NO_SET_TO_REPEAT = "No previous set to repeat."

# --- Errors ---
ERROR_INVALID_DATE = "Use YYYY-MM-DD or `today`\\."
ERROR_INVALID_DURATION = "Enter a valid number of minutes."
ERROR_NO_WORKOUTS_ADDED = "No workouts added yet. Add one or /cancel."
ERROR_NO_EXERCISES_CONFIGURED = "Workout '{workout_name}' has no exercises. Select another."
ERROR_INVALID_SET_INPUT = "Invalid input. Provide {count} values."
ERROR_PROCESSING_SET = "Error processing values. Check and try again."
