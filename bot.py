import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.config import settings
from src.models.domain import TrainingName
from src.services.flow_service import WorkoutFlowService
from src.services.input_parser import InputParser
from src.services.mongo_service import MongoService
from src.services.program_loader import ProgramLoader

# --- Basic Bot Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Service Initialization (Dependency Injection) ---
# Initialize all services once when the bot starts
program_loader = ProgramLoader()
mongo_service = MongoService(settings)
input_parser = InputParser()
flow_service = WorkoutFlowService(program_loader, mongo_service, input_parser)

# --- Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    await update.message.reply_text("Welcome to the Workout Logger Bot! Use /startlog to begin logging a new session.")

async def start_log_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asks the user which training program they want to log."""
    trainings = program_loader.load_program().keys()
    keyboard = [
        [InlineKeyboardButton(name.replace("_", " ").title(), callback_data=name)]
        for name in trainings
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please choose your training program:", reply_markup=reply_markup)

# --- Callback & Message Handlers ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button presses from the inline keyboard."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    training_name = TrainingName(query.data)

    # This now kicks off the conversation by asking for the date
    response = flow_service.select_training(user_id, training_name)
    await query.edit_message_text(text=response, parse_mode='Markdown')

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles all regular text messages, processing them as user input for the workout flow."""
    user_id = update.message.from_user.id
    text = update.message.text

    # Pass the user's message to the flow service and get the response
    response = flow_service.handle_user_response(user_id, text)
    await update.message.reply_text(response, parse_mode='Markdown')

# --- Main Bot Execution ---

def main():
    """Starts the bot."""
    logger.info("Bot is starting...")
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("startlog", start_log_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Start polling
    logger.info("Bot is polling...")
    app.run_polling()

if __name__ == "__main__":
    main()