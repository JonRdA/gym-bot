from bot.keyboards import *
from services.training_config_service import TrainingConfigService

config_service = TrainingConfigService(config_path="training_config.yaml")
workout_names = config_service.get_workout_names()
keyboard = create_workout_selection_keyboard(workout_names)