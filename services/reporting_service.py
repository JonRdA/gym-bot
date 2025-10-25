"""
Service layer for handling all data processing for reporting.
"""
import calendar
import logging
from datetime import datetime, timedelta

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
        excluded = self.settings.reporting.excluded_workouts
        return self.mongo.query_between_dates(
            user_id, t0, t1, excluded_workouts=excluded
        )

    def generate_activity_calendar(self, user_id: int) -> str | None:
        """Generates a text-based calendar of the current month with training days marked."""
        now = datetime.now()
        t0 = now.replace(day=1)
        t1 = (t0 + timedelta(days=32)).replace(day=1)
        excluded = self.settings.reporting.excluded_workouts
        
        trainings = self.mongo.query_between_dates_excluding_workouts(
            user_id, t0, t1, excluded_workouts=excluded
        )
        training_days = {training.date.day for training in trainings}

        cal = calendar.TextCalendar(calendar.MONDAY)
        month_calendar = cal.formatmonth(now.year, now.month).split('\n')
        
        header = f"🗓️ Activity for {now.strftime('%B %Y')}\n"
        calendar_str = f"`{month_calendar[0]}\n{month_calendar[1]}\n"

        for line in month_calendar[2:]:
            if not line.strip(): continue
            new_line = line
            for day_num in training_days:
                day_str = f"{day_num: >2}"
                if day_str in new_line:
                    new_line = new_line.replace(day_str, " ■")
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
                metrics_format = ", ".join(exercise.sets[0].metrics.keys())
                summary += f"  • *{exercise.name.replace('_', ' ').title()}* ({metrics_format})\n"

                for i, s in enumerate(exercise.sets, start=1):
                    values = ", ".join(str(v) for v in s.metrics.values())
                    summary += f"       #{i} → {values}\n"

            summary += "\n"

        return summary.strip()


    def get_available_report_types(self, exercise_config: dict) -> list[tuple[str, str]]:
        """Determines which report types are available based on an exercise's metrics."""
        metrics = exercise_config.get('metrics', [])
        available_reports = []
        if 'reps' in metrics:
            available_reports.append(('total_reps', 'Total Reps'))
        if 'reps' in metrics and 'weight' in metrics:
            available_reports.append(('total_volume', 'Total Volume'))
        if 'time' in metrics:
            available_reports.append(('total_time', 'Total Time'))
        return available_reports

    def generate_exercise_report(self, user_id: int, exercise_name: str, report_type: str, days: int) -> str:
        """Calculates and formats a specific report for a given exercise."""
        trainings = self.get_trainings_for_last_n_days(user_id, days)
        
        total_value = 0
        sets_counted = 0

        for training in trainings:
            for workout in training.get('workouts', []):
                for exercise in workout.get('exercises', []):
                    if exercise.get('name') == exercise_name:
                        for s in exercise.get('sets', []):
                            metrics = s.get('metrics', {})
                            if report_type == 'total_reps':
                                total_value += metrics.get('reps', 0)
                            elif report_type == 'total_volume':
                                total_value += metrics.get('reps', 0) * metrics.get('weight', 0)
                            elif report_type == 'total_time':
                                total_value += metrics.get('time', 0)
                            sets_counted += 1
        
        report_title = report_type.replace('_', ' ').title()
        exercise_title = exercise_name.replace('_', ' ').title()
        
        if sets_counted == 0:
            return f"No sets found for *{exercise_title}* in the last {days} days."

        return (
            f"*{exercise_title} Report*\n"
            f"Period: Last {days} days\n"
            f"_{report_title}_: *{total_value:,.0f}*"
        )

