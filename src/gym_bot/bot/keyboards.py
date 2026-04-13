from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from gym_bot.bot.callbacks import ADD_WORKOUT, COMPLETED, FINISH_TRAINING, make_callback


def chunk_buttons(items: list, size: int) -> list[list]:
    if size < 1:
        size = 1
    return [items[i : i + size] for i in range(0, len(items), size)]


def workout_selection_keyboard(workout_names: list[str]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            name.replace("_", " ").lower(),
            callback_data=make_callback(ADD_WORKOUT, name),
        )
        for name in workout_names
    ]
    rows = chunk_buttons(buttons, 3)
    rows.append([InlineKeyboardButton("Finish Training", callback_data=make_callback(FINISH_TRAINING, ""))])
    return InlineKeyboardMarkup(rows)


def completion_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Yes", callback_data=make_callback(COMPLETED, "yes")),
            InlineKeyboardButton("No", callback_data=make_callback(COMPLETED, "no")),
        ]
    ])
