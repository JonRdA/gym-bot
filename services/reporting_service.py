"""
Service layer for handling all data processing for reporting.
"""
import calendar
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Optional

from config import Settings
from models.domain import Training, Workout, WoSet
from services.mongo import MongoService

logger = logging.getLogger(__name__)

class ReportingService:
    """Handles logic for generating reports and summaries."""

    def __init__(self, mongo: MongoService, settings: Settings):
        self.mongo = mongo
        self.settings = settings

    def get_trainings_for_last_n_days(self, user_id: int, days: int) -> list:
        """Gets trainings for a user over the last N days."""
        t1 = datetime.now()
        t0 = t1 - timedelta(days=days)
        # Note: This query uses default exclusions.
        return self.mongo.query_between_dates(
            user_id, t0, t1
        )

    def generate_activity_calendar(self, user_id: int, year: int, month: int, workout_filter: Optional[str]) -> str | None:
        """Generates a text-based calendar for a specific month with training days marked."""
        
        t0 = datetime(year, month, 1)
        # Get first day of next month
        t1 = (t0 + timedelta(days=32)).replace(day=1)
        
        if workout_filter:
            # A specific workout was selected
            logger.debug(
                "Querying calendar for user %s, %s-%s, filter: %s", 
                user_id, year, month, workout_filter
            )
            trainings = self.mongo.query_between_dates_including_workouts(
                user_id, t0, t1, required_workouts=[workout_filter]
            )
        else:
            # "All" was selected, so use the default excluded list
            logger.debug(
                "Querying calendar for user %s, %s-%s, filter: All (with exclusions)", 
                user_id, year, month
            )
            excluded = self.settings.reporting.excluded_workouts
            trainings = self.mongo.query_between_dates_excluding_workouts(
                user_id, t0, t1, excluded_workouts=excluded
            )
        
        # Map day number -> True if all workouts completed, False otherwise
        training_days: Dict[int, bool] = {}
        for training in trainings:
            day = training.date.day
            all_completed = all(w.completed for w in training.workouts)
            training_days[day] = training_days.get(day, True) and all_completed

        cal = calendar.TextCalendar(calendar.MONDAY)
        month_calendar = cal.formatmonth(year, month).split('\n')

        month_name = t0.strftime('%B %Y')
        header = f"🗓️ Activity for {month_name}\n"

        # Use MarkdownV2 code block
        calendar_str = f"`{month_calendar[0]}\n{month_calendar[1]}\n"

        for line in month_calendar[2:]:
            if not line.strip():
                continue
            new_line = line
            for day_num, completed in training_days.items():
                day_str = f"{day_num: >2}"
                marker = "🟢" if completed else "🔶"
                # Use digit-boundary guards to avoid matching substrings
                # e.g. day 2 must not match "20", "21", "28", etc.
                pattern = rf'(?<!\d){re.escape(day_str)}(?!\d)'
                new_line = re.sub(pattern, marker, new_line)
            calendar_str += new_line + "\n"
        
        calendar_str += "`"
        return header + calendar_str

    def format_training_summary(self, training: Training) -> str:
        """Formats a single training document into a human-readable summary."""
        summary = f"{training.date.strftime('%Y-%m-%d')} ({training.duration_minutes} min)\n"
        workout_names = ", ".join([w.name.title() for w in training.workouts])
        summary += f"_{workout_names}_"
        return summary
        
    def format_training_details(self, training: Training) -> str:
        """Formats a training session into a compact, stylish summary."""
        summary = f"🏋️ *{training.date.strftime('%Y-%m-%d')}*\n"
        summary += f"⏱️ {training.duration_minutes} min\n\n"

        for workout in training.workouts:
            status = "✅" if workout.completed else "❌"
            summary += f"*{workout.name.title()}* {status}\n"

            if not workout.exercises:
                summary += "  _No exercises logged_\n"
                continue

            for exercise in workout.exercises:
                if not exercise.sets:
                    summary += f"  • *{exercise.name.replace('_', ' ').title()}* (No sets)\n"
                    continue
                
                metrics_format = ", ".join(exercise.sets[0].metrics.keys())
                summary += f"  • *{exercise.name.replace('_', ' ').title()}* ({metrics_format})\n"

                for i, s in enumerate(exercise.sets, start=1):
                    values = ", ".join(str(v) for v in s.metrics.values())
                    summary += f"       #{i} → {values}\n"

            summary += "\n"

        return summary.strip()
