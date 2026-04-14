from dataclasses import dataclass

from gym_bot.config.service import UserConfigService
from gym_bot.db.repositories import TrainingRepository, UserConfigRepository
from gym_bot.reporting.exercise_reports import ExerciseReportingService
from gym_bot.reporting.service import ReportingService
from gym_bot.settings import Settings


@dataclass
class Services:
    trainings: TrainingRepository
    config: UserConfigService
    reporting: ReportingService
    exercise_reporting: ExerciseReportingService
    settings: Settings


def get_services(context) -> Services:
    return context.bot_data["services"]
