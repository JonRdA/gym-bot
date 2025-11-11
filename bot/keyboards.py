"""Functions for generating interactive keyboards for the Telegram bot."""

from typing import List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from models.enums import WorkoutName


def chunk_list(items: List, chunk_size: int) -> List[List]:
    """Splits a list into sublists of fixed size."""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

def create_workout_selection_keyboard(workout_names: List[WorkoutName]) -> InlineKeyboardMarkup:
    """Creates a keyboard with workout names in rows of 3 and a finish button."""
    # Create buttons for each workout
    buttons = [
        InlineKeyboardButton(name.name.replace("_", " ").lower(), callback_data=f"addworkout_{name.name}")
        for name in workout_names
    ]

    # Group into rows of 3 & add finish button
    keyboard = chunk_list(buttons, 3)
    keyboard.append([InlineKeyboardButton("✅ Finish Training", callback_data="finish_training")])

    return InlineKeyboardMarkup(keyboard)
    
def create_completion_keyboard() -> InlineKeyboardMarkup:
    """Creates a 'Yes'/'No' inline keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="completed_yes"),
            InlineKeyboardButton("❌ No", callback_data="completed_no"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
