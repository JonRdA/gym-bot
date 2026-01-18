"""
Service layer for generating reports on specific exercises.
"""
import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

from models.domain import Training
from services.mongo import MongoService
from services.training_config_service import TrainingConfigService

logger = logging.getLogger(__name__)

# --- Report Definitions ---
# This "registry" maps metrics to the reports they enable.
# We can easily add new reports here.
REPORT_REGISTRY = {
    # Reports requiring 'reps'
    ("reps",): [
        ("total_reps", "Total Reps"),
    ],
    # Reports requiring 'reps' AND 'weight'
    ("reps", "weight"): [
        ("total_volume", "Total Volume"),
        ("max_weight", "Max Weight"),
    ],
    # Reports requiring 'time'
    ("time",): [
        ("total_time", "Total Time (Hold)"),
        ("max_time", "Max Time (Hold)"),
    ],
}


class ExerciseReportingService:
    """Handles all logic for generating exercise-specific reports."""

    def __init__(self, mongo: MongoService, config_service: TrainingConfigService):
        self.mongo = mongo
        self.config_service = config_service

    def get_available_reports_for_exercise(self, user_id: int, exercise_name: str) -> List[Tuple[str, str]]:
        """
        Checks an exercise's metrics and returns a list of available report types.
        """
        exercise_config = self.config_service.get_exercise_details(user_id, exercise_name)
        if not exercise_config:
            return []

        metrics = set(exercise_config.get("metrics", []))
        available_reports = []

        for required_metrics, reports in REPORT_REGISTRY.items():
            # Check if the exercise's metrics contain all required metrics for this report
            if metrics.issuperset(required_metrics):
                available_reports.extend(reports)
        
        # Remove duplicates and sort
        return sorted(list(set(available_reports)))

    def generate_report(self, report_type: str, user_id: int, exercise_name: str,
            t0: datetime, t1: datetime,) -> Optional[Dict[str, Any]]:
        """
        Main dispatcher function to generate a specific report.
        """
        # 1. Get all raw data for the exercise in the time period
        exercise_data = self._get_exercise_data(user_id, exercise_name, t0, t1)
        if not exercise_data:
            return None  # No data found

        # 2. Dispatch to the correct report generator
        logger.info("Generating report '%s' for exercise '%s'", report_type, exercise_name)
        try:
            if report_type == "total_reps":
                return self._generate_total_reps_report(exercise_data, exercise_name)
            elif report_type == "total_volume":
                return self._generate_total_volume_report(exercise_data, exercise_name)
            # --- Add other report function calls here ---
            # elif report_type == "max_weight":
            #     return self._generate_max_weight_report(exercise_data, exercise_name)
            else:
                logger.warning("Unknown report type requested: %s", report_type)
                return {
                    "text": f"Sorry, the report type '{report_type}' is not yet implemented."
                }
        except Exception as e:
            logger.error(
                "Failed to generate report '%s' for %s: %s",
                report_type, exercise_name, e, exc_info=True
            )
            return {"text": "Sorry, an error occurred while generating your report."}

    def _get_workouts_for_exercise(self, user_id: int, exercise_name: str) -> List[str]:
        """
        Finds all workout names that contain a given exercise, using the config.
        """
        workout_names = self.config_service.get_workout_names(user_id)
        relevant_workouts = []
        for name in workout_names:
            workout_details = self.config_service.get_workout_details(user_id, name)
            if workout_details:
                for ex in workout_details.get("exercises", []):
                    if ex.get("name") == exercise_name:
                        relevant_workouts.append(name)
                        break  # Move to the next workout name
        
        logger.debug("Exercise '%s' is in workouts: %s", exercise_name, relevant_workouts)
        return relevant_workouts

    def _get_exercise_data(self, user_id: int, exercise_name: str, t0: datetime, t1: datetime) -> List[Dict[str, Any]]:
        """
        Queries Mongo efficiently and filters to a flat list of sets for a specific exercise.
        """
        # --- OPTIMIZATION ---
        # 1. Find which workouts contain this exercise
        relevant_workouts = self._get_workouts_for_exercise(user_id, exercise_name)
        if not relevant_workouts:
            logger.info("No workouts found containing '%s' in config.", exercise_name)
            return []

        # 2. Query Mongo *only* for trainings containing those workouts
        trainings = self.mongo.query_between_dates_including_workouts(
            user_id, t0, t1, required_workouts=relevant_workouts
        )
        
        exercise_sessions = []
        for training in trainings:
            session_data = {"date": training.date, "sets": []}
            for workout in training.workouts:
                # We still check workout name in case user did two workouts (e.g., 'push' and 'pull')
                # but 'pull' doesn't have the exercise.
                if workout.name in relevant_workouts:
                    for exercise in workout.exercises:
                        if exercise.name == exercise_name:
                            session_data["sets"].extend([s.metrics for s in exercise.sets])
            
            if session_data["sets"]:
                exercise_sessions.append(session_data)
                
        logger.debug("Found %d sessions with exercise '%s'", len(exercise_sessions), exercise_name)
        return sorted(exercise_sessions, key=lambda x: x['date'])

    # --- Specific Report Generators ---
    def _generate_total_reps_report(self, exercise_data: List[Dict], exercise_name: str) -> Dict[str, Any]:
        """Calculates total reps and generates a plot of reps per session."""
        dates = []
        session_reps = []

        for session in exercise_data:
            reps_in_this_session = sum(s.get("reps", 0) for s in session["sets"])
            if reps_in_this_session > 0:
                dates.append(session["date"])
                session_reps.append(reps_in_this_session)

        if not dates:
            return {"text": f"No sessions with reps found for {exercise_name.title()}."}

        max_reps = max(session_reps)
        title = f"{exercise_name.replace('_', ' ').title()} Report: Reps per Session"
        
        # --- MODIFIED TEXT ---
        text = (
            f"*{title}*\n\n"
            f"Max reps in day: *{max_reps:,.0f}*.\n"
            f"Last training reps: *{session_reps[-1]:,.0f}*."
        )

        chart = self._generate_bar_chart(
            dates,
            session_reps,
            title=title,
            ylabel="Total Reps",
        )
        return {"title": title, "text": text, "chart": chart}

    def _generate_total_volume_report(self, exercise_data: List[Dict], exercise_name: str) -> Dict[str, Any]:
        """Calculates total volume and generates a plot of volume per session."""
        dates = []
        session_volumes = []

        for session in exercise_data:
            volume_in_this_session = sum(
                s.get("reps", 0) * s.get("weight", 0) for s in session["sets"]
            )
            if volume_in_this_session > 0:
                dates.append(session["date"])
                session_volumes.append(volume_in_this_session)
        
        if not dates:
            return {"text": f"No sessions with volume found for {exercise_name.title()}."}

        max_volume = max(session_volumes)
        title = f"{exercise_name.replace('_', ' ').title()} Report: Volume (kg)"

        # --- MODIFIED TEXT ---
        text = (
            f"*{title}*\n\n"
            f"Report based on *{len(dates)} sessions*.\n"
            f"Your max volume in a single day was *{max_volume:,.0f} kg*."
        )

        chart = self._generate_bar_chart(
            dates,
            session_volumes,
            title=title,
            ylabel="Total Volume (kg)",
        )
        return {"title": title, "text": text, "chart": chart}

    # --- Plotting Utility (Modified) ---

    def _generate_bar_chart(
        self,
        dates: List[datetime],
        values: List[float],
        title: str,
        ylabel: str,
    ) -> Optional[io.BytesIO]:
        if not dates:
            return None

        try:
            plt.figure(figsize=(8, 4))
            
            # 1. Pass 'dates' directly instead of indices
            # We set a width (in days) for the bars. 0.8 is usually good for daily data.
            plt.bar(dates, values, width=0.8, align='center')

            # 2. Use Date Formatter to ensure the X-axis looks clean
            import matplotlib.dates as mdates
            ax = plt.gca()
            
            # This automatically picks the best intervals (days, months, etc.)
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))
            
            plt.title(title, fontsize=14)
            plt.ylabel(ylabel, fontsize=10)
            plt.grid(True, axis='y', linestyle='--', alpha=0.6)
            
            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format="png")
            buf.seek(0)
            plt.close()
            return buf
        
        except Exception as e:
            logger.error("Failed to generate plot: %s", e, exc_info=True)
            return None