"""
Service layer for generating reports on specific exercises.
"""
import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.dates as mdates

# You will need to install this: pip install matplotlib
import matplotlib.pyplot as plt

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
        ("reps_per_session", "Reps per Session (Avg)"),
    ],
    # Reports requiring 'reps' AND 'weight'
    ("reps", "weight"): [
        ("total_volume", "Total Volume"),
        ("max_weight", "Max Weight"),
        ("volume_per_session", "Volume per Session"),
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

    def generate_report(
        self,
        report_type: str,
        user_id: int,
        exercise_name: str,
        t0: datetime,
        t1: datetime,
    ) -> Optional[Dict[str, Any]]:
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

    def _get_exercise_data(
        self, user_id: int, exercise_name: str, t0: datetime, t1: datetime
    ) -> List[Dict[str, Any]]:
        """
        Queries Mongo and filters down to a flat list of sets for a specific exercise.
        """
        trainings = self.mongo.query_between_dates(user_id, t0, t1)
        
        exercise_sets = []
        for training in trainings:
            session_data = {"date": training.date, "sets": []}
            for workout in training.workouts:
                for exercise in workout.exercises:
                    if exercise.name == exercise_name:
                        session_data["sets"].extend(
                            [s.metrics for s in exercise.sets]
                        )
            
            if session_data["sets"]:
                exercise_sets.append(session_data)
                
        logger.debug("Found %d sessions with exercise '%s'", len(exercise_sets), exercise_name)
        return exercise_sets

    # --- Specific Report Generators ---

    def _generate_total_reps_report(
        self, exercise_data: List[Dict], exercise_name: str
    ) -> Dict[str, Any]:
        """Calculates total reps and generates a plot of reps per session."""
        total_reps = 0
        dates = []
        session_reps = []

        for session in exercise_data:
            reps_in_this_session = 0
            for s in session["sets"]:
                reps_in_this_session += s.get("reps", 0)
            
            if reps_in_this_session > 0:
                total_reps += reps_in_this_session
                dates.append(session["date"])
                session_reps.append(reps_in_this_session)

        title = f"{exercise_name.title()} Report: Total Reps"
        text = (
            f"*{title}*\n\n"
            f"You completed *{total_reps:,}* total reps "
            f"across *{len(dates)}* sessions."
        )

        chart = self._generate_simple_plot(
            dates,
            session_reps,
            title="Reps per Session",
            ylabel="Total Reps",
        )
        return {"title": title, "text": text, "chart": chart}

    def _generate_total_volume_report(
        self, exercise_data: List[Dict], exercise_name: str
    ) -> Dict[str, Any]:
        """Calculates total volume and generates a plot of volume per session."""
        total_volume = 0
        dates = []
        session_volumes = []

        for session in exercise_data:
            volume_in_this_session = 0
            for s in session["sets"]:
                reps = s.get("reps", 0)
                weight = s.get("weight", 0)
                volume_in_this_session += reps * weight
            
            if volume_in_this_session > 0:
                total_volume += volume_in_this_session
                dates.append(session["date"])
                session_volumes.append(volume_in_this_session)

        # Assuming weight is in KG
        title = f"{exercise_name.title()} Report: Total Volume (kg)"
        text = (
            f"*{title}*\n\n"
            f"You lifted a total volume of *{total_volume:,.0f} kg* "
            f"across *{len(dates)}* sessions."
        )

        chart = self._generate_simple_plot(
            dates,
            session_volumes,
            title="Volume per Session",
            ylabel="Total Volume (kg)",
        )
        return {"title": title, "text": text, "chart": chart}

    # --- Plotting Utility ---

    def _generate_simple_plot(
        self,
        dates: List[datetime],
        values: List[float],
        title: str,
        ylabel: str,
    ) -> Optional[io.BytesIO]:
        """
        Generates a simple date-based line plot and returns it as a BytesIO object.
        """
        if not dates or len(dates) < 2:
            logger.info("Not enough data to plot for '%s'", title)
            return None  # Can't plot less than 2 points

        try:
            plt.figure(figsize=(10, 6))
            plt.plot(dates, values, marker='o', linestyle='-')
            
            # Format x-axis to show dates nicely
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
            plt.gcf().autofmt_xdate() # Auto-rotate dates
            
            plt.title(title)
            plt.ylabel(ylabel)
            plt.xlabel("Date")
            plt.grid(True, linestyle='--', alpha=0.6)
            plt.tight_layout()

            # Save plot to a bytes buffer
            buf = io.BytesIO()
            plt.savefig(buf, format="png")
            buf.seek(0)
            plt.close() # Close the figure to free memory
            return buf
        
        except Exception as e:
            logger.error("Failed to generate plot: %s", e, exc_info=True)
            return None