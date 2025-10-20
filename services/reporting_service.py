"""
Service layer for handling all data processing for reporting.
"""
import calendar
from datetime import datetime

from config import settings
from services.mongo_service import MongoService


class ReportingService:
    """Handles logic for generating reports and summaries."""

    def __init__(self, mongo_service: MongoService):
        self.mongo_service = mongo_service

    def generate_activity_calendar(self, user_id: int) -> str | None:
        """Generates a text-based calendar of the current month with training days marked."""
        now = datetime.now()
        excluded = settings.reporting.excluded_workouts
        
        training_dates = self.mongo_service.get_training_dates_for_month(user_id, now.year, now.month, excluded_workouts=excluded)
        training_days = {d.day for d in training_dates}

        cal = calendar.TextCalendar(calendar.MONDAY)
        month_calendar = cal.formatmonth(now.year, now.month).split('\n')
        
        header = f"🗓️ Activity for {now.strftime('%B %Y')}\n"
        # Use a full block character '■' for better alignment
        calendar_str = f"`{month_calendar[0]}\n{month_calendar[1]}\n"

        for line in month_calendar[2:]:
            if not line.strip(): continue
            new_line = line
            for day_num in training_days:
                day_str = f"{day_num: >2}"
                if day_str in new_line:
                    # Replace with a monospace-friendly character
                    new_line = new_line.replace(day_str, " ■")
            calendar_str += new_line + "\n"
        
        calendar_str += "`"
        return header + calendar_str

    def format_training_summary(self, training: dict) -> str:
        """Formats a single training document into a human-readable summary."""
        summary = f"*{training['date'].strftime('%Y-%m-%d')}* ({training['duration']} min)\n\n"
        
        for workout in training.get('workouts', []):
            completed_emoji = "✅" if workout.get('completed', False) else "❌"
            summary += f"*{workout.get('name', 'N/A').title()}* {completed_emoji}\n"
            
            if not workout.get('exercises'):
                summary += "  _(No exercises logged)_\n"

            for exercise in workout.get('exercises', []):
                ex_name = exercise.get('name', 'N/A').replace('_', ' ').title()
                set_count = len(exercise.get('sets', []))
                summary += f"  - {ex_name}: {set_count} set{'s' if set_count != 1 else ''}\n"
                
        return summary
        
    def format_training_details(self, training: dict) -> str:
        """Formats a single training document into a detailed, human-readable summary."""
        summary = f"*Training on {training['date'].strftime('%Y-%m-%d')}*\n"
        summary += f"Duration: {training['duration']} minutes\n\n"
        
        for workout in training.get('workouts', []):
            completed_emoji = "✅" if workout.get('completed', False) else "❌"
            summary += f"*{workout.get('name', 'N/A').title()}* {completed_emoji}\n"
            
            if not workout.get('exercises'):
                summary += "  _(No exercises logged)_\n"

            for exercise in workout.get('exercises', []):
                metrics_list = " ".join(exercise.get('sets')[0].get('metrics').keys())
                summary += f"  - *{exercise.get('name', 'N/A').replace('_', ' ').title()}*\n    {metrics_list}\n"
                for i, s in enumerate(exercise.get('sets', [])):
                    metrics_str = ", ".join([f"{k}: {v}" for k, v in s.get('metrics', {}).items()])
                    summary += f"    *Set {i+1}:* {metrics_str}\n"

        return summary
