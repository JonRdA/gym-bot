"""Functions for generating interactive keyboards for the Telegram bot."""

from typing import List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from models.enums import WorkoutName


def create_workout_selection_keyboard(workout_names: List[WorkoutName]) -> InlineKeyboardMarkup:
    """Creates a keyboard for selecting workouts to add, plus a finish button."""
    keyboard = [
        [InlineKeyboardButton(name.value.replace("_", " ").title(), callback_data=f"addworkout_{name.value}")]
        for name in workout_names
    ]
    # Add the finish button at the end
    keyboard.append([InlineKeyboardButton("✅ Finish Training", callback_data="finish_training")])
    return InlineKeyboardMarkup(keyboard)


def create_yes_no_keyboard(yes_callback: str, no_callback: str) -> InlineKeyboardMarkup:
    """Creates a simple Yes/No keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data=yes_callback),
            InlineKeyboardButton("❌ No", callback_data=no_callback),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

