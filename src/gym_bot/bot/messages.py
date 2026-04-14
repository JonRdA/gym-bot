# Conversation start/end
START_MESSAGE = "Let's add a new training session\\! 🏋️"
SAVE_SUCCESS = "Training saved 💪"
SAVE_ERROR = "Error saving your session. Try again later."
CANCEL_MESSAGE = "Logging cancelled."

# Prompts
PROMPT_DATE = "Insert date\\. `YYYY-MM-DD` or `today`"
PROMPT_DURATION = "Training duration in minutes?"
PROMPT_WORKOUT_FIRST = "Let's add the first workout."
PROMPT_WORKOUT_NEXT = "Add another workout, or finish."
PROMPT_COMPLETION = "Did you complete this workout?"
PROMPT_SETS = (
    "Enter sets for *{exercise_title}*\\.\n"
    "Format: `{metric_names}`\n"
    "/done"
)

# Confirmations
LOGGING_EXERCISES = "Add exercises for {workout_name}."
SET_ADDED = "Set {count}: /repeat or /done."
NO_SET_TO_REPEAT = "No previous set to repeat."

# Errors
ERROR_INVALID_DATE = "Use YYYY-MM-DD or `today`\\."
ERROR_INVALID_DURATION = "Enter a valid number of minutes."
ERROR_NO_WORKOUTS = "No workouts added yet. Add one or /cancel."
ERROR_NO_EXERCISES = "Workout '{workout_name}' has no exercises configured."
ERROR_INVALID_SET = "Invalid input. Provide {count} values."
ERROR_PROCESSING_SET = "Error processing values. Check and try again."
ERROR_GENERIC = "Something went wrong. Please try again."
