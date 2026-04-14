import io
import logging
from datetime import datetime
from typing import Any, Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from gym_bot.config.service import UserConfigService
from gym_bot.db.repositories import TrainingRepository

logger = logging.getLogger(__name__)

# Maps required metric combinations to available report types
REPORT_REGISTRY: dict[tuple[str, ...], list[tuple[str, str]]] = {
    ("reps",): [
        ("total_reps", "Total Reps"),
    ],
    ("reps", "weight"): [
        ("total_volume", "Total Volume"),
        ("max_weight", "Max Weight"),
    ],
    ("time",): [
        ("total_time", "Total Time"),
        ("max_time", "Max Time"),
    ],
}


class ExerciseReportingService:
    def __init__(self, training_repo: TrainingRepository, config_service: UserConfigService):
        self._repo = training_repo
        self._config = config_service

    async def get_available_reports(
        self, user_id: int, exercise_name: str
    ) -> list[tuple[str, str]]:
        config = await self._config.get_config(user_id)
        exercise_config = config.get_exercise(exercise_name)
        if not exercise_config:
            return []

        metrics = set(exercise_config.metrics)
        reports = []
        for required, report_list in REPORT_REGISTRY.items():
            if metrics.issuperset(required):
                reports.extend(report_list)
        return sorted(set(reports))

    async def generate_report(
        self,
        report_type: str,
        user_id: int,
        exercise_name: str,
        t0: datetime,
        t1: datetime,
    ) -> Optional[dict[str, Any]]:
        sessions = await self._get_exercise_sessions(user_id, exercise_name, t0, t1)
        if not sessions:
            return None

        generators = {
            "total_reps": self._report_total_reps,
            "total_volume": self._report_total_volume,
            "max_weight": self._report_max_weight,
            "total_time": self._report_total_time,
            "max_time": self._report_max_time,
        }

        generator = generators.get(report_type)
        if not generator:
            return {"text": f"Report type '{report_type}' is not implemented."}

        return generator(sessions, exercise_name)

    async def _get_exercise_sessions(
        self, user_id: int, exercise_name: str, t0: datetime, t1: datetime
    ) -> list[dict[str, Any]]:
        config = await self._config.get_config(user_id)
        relevant_workouts = config.get_workouts_for_exercise(exercise_name)
        if not relevant_workouts:
            return []

        trainings = await self._repo.find_with_workout_filter(
            user_id, t0, t1, include=relevant_workouts
        )

        sessions = []
        for training in trainings:
            sets = []
            for workout in training.workouts:
                if workout.name in relevant_workouts:
                    for exercise in workout.exercises:
                        if exercise.name == exercise_name:
                            sets.extend(s.metrics for s in exercise.sets)
            if sets:
                sessions.append({"date": training.date, "sets": sets})

        return sorted(sessions, key=lambda x: x["date"])

    # --- Report generators ---

    def _report_total_reps(self, sessions: list[dict], exercise_name: str) -> dict:
        dates, values = [], []
        for s in sessions:
            total = sum(m.get("reps", 0) for m in s["sets"])
            if total > 0:
                dates.append(s["date"])
                values.append(total)

        if not dates:
            return {"text": f"No reps data found for {exercise_name}."}

        title = f"{_title(exercise_name)}: Reps per Session"
        text = (
            f"*{title}*\n\n"
            f"Max reps in a day: *{max(values):,.0f}*\n"
            f"Last session: *{values[-1]:,.0f}*"
        )
        return {"text": text, "chart": _bar_chart(dates, values, title, "Total Reps")}

    def _report_total_volume(self, sessions: list[dict], exercise_name: str) -> dict:
        dates, values = [], []
        for s in sessions:
            vol = sum(m.get("reps", 0) * m.get("weight", 0) for m in s["sets"])
            if vol > 0:
                dates.append(s["date"])
                values.append(vol)

        if not dates:
            return {"text": f"No volume data found for {exercise_name}."}

        title = f"{_title(exercise_name)}: Volume (kg)"
        text = (
            f"*{title}*\n\n"
            f"*{len(dates)} sessions*\n"
            f"Max volume in a day: *{max(values):,.0f} kg*"
        )
        return {"text": text, "chart": _bar_chart(dates, values, title, "Total Volume (kg)")}

    def _report_max_weight(self, sessions: list[dict], exercise_name: str) -> dict:
        dates, values = [], []
        for s in sessions:
            weights = [m.get("weight", 0) for m in s["sets"] if m.get("weight", 0) > 0]
            if weights:
                dates.append(s["date"])
                values.append(max(weights))

        if not dates:
            return {"text": f"No weight data found for {exercise_name}."}

        title = f"{_title(exercise_name)}: Max Weight (kg)"
        text = (
            f"*{title}*\n\n"
            f"All-time max: *{max(values):,.1f} kg*\n"
            f"Last session: *{values[-1]:,.1f} kg*"
        )
        return {"text": text, "chart": _bar_chart(dates, values, title, "Max Weight (kg)")}

    def _report_total_time(self, sessions: list[dict], exercise_name: str) -> dict:
        dates, values = [], []
        for s in sessions:
            total = sum(m.get("time", 0) for m in s["sets"])
            if total > 0:
                dates.append(s["date"])
                values.append(total)

        if not dates:
            return {"text": f"No time data found for {exercise_name}."}

        title = f"{_title(exercise_name)}: Total Time (s)"
        text = (
            f"*{title}*\n\n"
            f"Max total in a day: *{max(values)}s*\n"
            f"Last session: *{values[-1]}s*"
        )
        return {"text": text, "chart": _bar_chart(dates, values, title, "Total Time (s)")}

    def _report_max_time(self, sessions: list[dict], exercise_name: str) -> dict:
        dates, values = [], []
        for s in sessions:
            times = [m.get("time", 0) for m in s["sets"] if m.get("time", 0) > 0]
            if times:
                dates.append(s["date"])
                values.append(max(times))

        if not dates:
            return {"text": f"No time data found for {exercise_name}."}

        title = f"{_title(exercise_name)}: Max Hold (s)"
        text = (
            f"*{title}*\n\n"
            f"All-time max: *{max(values)}s*\n"
            f"Last session: *{values[-1]}s*"
        )
        return {"text": text, "chart": _bar_chart(dates, values, title, "Max Hold (s)")}


# --- Helpers ---

def _title(exercise_name: str) -> str:
    return exercise_name.replace("_", " ").title()


def _bar_chart(
    dates: list[datetime],
    values: list[float],
    title: str,
    ylabel: str,
) -> Optional[io.BytesIO]:
    if not dates:
        return None
    try:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(dates, values, width=0.8, align="center")
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%m"))
        ax.set_title(title, fontsize=14)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.grid(True, axis="y", linestyle="--", alpha=0.6)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        return buf
    except Exception:
        logger.error("Failed to generate chart", exc_info=True)
        return None
    finally:
        plt.close(fig)
