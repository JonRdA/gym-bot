"""Functions for generating interactive keyboards for the Telegram bot."""

from typing import List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from models.enums import TrainingName


def create_training_selection_keyboard(training_names: List[TrainingName]) -> InlineKeyboardMarkup:
    """Creates a keyboard for the user to select a training program."""
    keyboard = [
        [InlineKeyboardButton(name.value.replace("_", " ").title(), callback_data=name.value)]
        for name in training_names
    ]
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
