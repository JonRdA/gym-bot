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

REST_REPORT = ("rest_trend", "Rest")


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
        if exercise_config.track_rest:
            reports.append(REST_REPORT)
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
            "rest_trend": self._report_rest_trend,
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
            rest = None
            for workout in training.workouts:
                if workout.name in relevant_workouts:
                    for exercise in workout.exercises:
                        if exercise.name == exercise_name:
                            sets.extend(s.metrics for s in exercise.sets)
                            if exercise.rest is not None:
                                rest = exercise.rest
            if sets:
                sessions.append({"date": training.date, "sets": sets, "rest": rest})

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

        title = f"{_title(exercise_name)}: Volume (reps x kg)"
        text = (
            f"*{title}*\n\n"
            f"*{len(dates)} sessions*\n"
            f"Max volume in a day: *{max(values):,.0f} reps x kg*"
        )
        return {"text": text, "chart": _bar_chart(dates, values, title, "Volume (reps x kg)")}

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

    def _report_rest_trend(self, sessions: list[dict], exercise_name: str) -> dict:
        dates, values = [], []
        for s in sessions:
            if s.get("rest") is not None:
                dates.append(s["date"])
                values.append(s["rest"])

        if not dates:
            return {"text": f"No rest data found for {exercise_name}."}

        title = f"{_title(exercise_name)}: Rest (s)"
        text = (
            f"*{title}*\n\n"
            f"Overall avg: *{sum(values) / len(values):,.0f}s*\n"
            f"Shortest: *{min(values)}s*\n"
            f"Last session: *{values[-1]}s*"
        )
        return {"text": text, "chart": _bar_chart(dates, values, title, "Rest (s)")}

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


_BAR_COLOR = "#2f5d8a"
_GRID_COLOR = "#e8e8e8"
_AXIS_COLOR = "#888888"
_TEXT_COLOR = "#2b2b2b"


def _bar_chart(
    dates: list[datetime],
    values: list[float],
    title: str,
    ylabel: str,
) -> Optional[io.BytesIO]:
    if not dates:
        return None
    try:
        fig, ax = plt.subplots(figsize=(5.5, 7.5), dpi=160)

        ax.bar(dates, values, width=0.7, color=_BAR_COLOR, edgecolor="none", zorder=2)

        ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=6))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))

        ax.set_title(title, fontsize=15, pad=16, color=_TEXT_COLOR, fontweight="semibold")
        ax.set_ylabel(ylabel, fontsize=12, labelpad=10, color=_TEXT_COLOR)

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(_AXIS_COLOR)
        ax.spines["bottom"].set_color(_AXIS_COLOR)

        ax.tick_params(axis="both", colors=_AXIS_COLOR, labelsize=11, length=0)
        ax.yaxis.grid(True, linestyle="-", linewidth=0.7, color=_GRID_COLOR, zorder=1)
        ax.set_axisbelow(True)
        ax.margins(x=0.05)

        for label in ax.get_xticklabels():
            label.set_rotation(35)
            label.set_horizontalalignment("right")

        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
        buf.seek(0)
        return buf
    except Exception:
        logger.error("Failed to generate chart", exc_info=True)
        return None
    finally:
        plt.close(fig)
