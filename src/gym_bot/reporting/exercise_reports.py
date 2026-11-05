import io
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.collections import PathCollection
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MultipleLocator

from gym_bot.config.service import UserConfigService
from gym_bot.db.repositories import TrainingRepository

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class ReportRule:
    requires: frozenset[str]
    reports: tuple[tuple[str, str], ...]
    excludes: frozenset[str] = frozenset()

    def applies_to(self, metrics: set[str]) -> bool:
        return self.requires <= metrics and not self.excludes & metrics


REPORT_REGISTRY: tuple[ReportRule, ...] = (
    ReportRule(
        requires=frozenset({"reps"}),
        excludes=frozenset({"weight"}),
        reports=(("total_reps", "Total Reps"),),
    ),
    ReportRule(
        requires=frozenset({"reps", "weight"}),
        reports=(("total_volume", "Total Volume"), ("max_weight", "Max Weight")),
    ),
    ReportRule(
        requires=frozenset({"time"}),
        reports=(("total_time", "Total Time"), ("max_time", "Max Time")),
    ),
    ReportRule(
        requires=frozenset({"time_min", "distance"}),
        reports=(("run", "Run"),),
    ),
)


@dataclass(frozen=True)
class _Run:
    date: datetime
    minutes: float
    km: float
    climb_m: float

    @property
    def pace(self) -> float:
        return self.minutes / self.km

    @property
    def climb_per_km(self) -> float:
        return self.climb_m / self.km


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
        for rule in REPORT_REGISTRY:
            if rule.applies_to(metrics):
                reports.extend(rule.reports)
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
            "run": self._report_run,
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

    def _report_run(self, sessions: list[dict], exercise_name: str) -> dict:
        runs = _collect_runs(sessions)
        if not runs:
            return {"text": f"No run data found for {exercise_name}."}

        best = min(runs, key=lambda r: r.pace)
        longest = max(runs, key=lambda r: r.km)
        last = runs[-1]

        title = f"{_title(exercise_name)}: Pace"
        text = (
            f"*{title}*\n\n"
            f"Runs: *{len(runs)}* ({sum(r.km for r in runs):,.1f} km total)\n"
            f"Best pace: *{_format_pace(best.pace)} /km* ({best.km:.1f} km)\n"
            f"Longest run: *{longest.km:.1f} km*\n"
            f"Last run: *{last.km:.1f} km at {_format_pace(last.pace)} /km*, "
            f"{last.climb_m:.0f} m climb"
        )
        return {"text": text, "chart": _pace_chart(runs, title)}


# --- Helpers ---

def _title(exercise_name: str) -> str:
    return exercise_name.replace("_", " ").title()


def _collect_runs(sessions: list[dict]) -> list[_Run]:
    runs = []
    for s in sessions:
        minutes = sum(m.get("time_min", 0) for m in s["sets"])
        km = sum(m.get("distance", 0) for m in s["sets"]) / 1000
        climb = sum(m.get("elevation", 0) for m in s["sets"])
        if minutes > 0 and km > 0:
            runs.append(_Run(date=s["date"], minutes=minutes, km=km, climb_m=climb))
    return runs


def _format_pace(minutes_per_km: float) -> str:
    seconds = round(minutes_per_km * 60)
    return f"{seconds // 60}:{seconds % 60:02d}"


_BAR_COLOR = "#2f5d8a"
_GRID_COLOR = "#e8e8e8"
_AXIS_COLOR = "#888888"
_TEXT_COLOR = "#2b2b2b"
_LEGEND_MARKER_COLOR = "#b0b0b0"
_CLIMB_CMAP = LinearSegmentedColormap.from_list(
    "climb", ["#2e9e5b", "#c8b42a", "#e8743b", "#a3202a"]
)
_MIN_CLIMB_SCALE = 15  # m/km; keeps near-flat periods from looking hilly

_MIN_DATE_PAD = timedelta(days=3)
_MIN_BUBBLE_AREA = 40
_MAX_BUBBLE_AREA = 420


def _bar_chart(
    dates: list[datetime],
    values: list[float],
    title: str,
    ylabel: str,
) -> Optional[io.BytesIO]:
    if not dates:
        return None

    def draw(fig: Figure, ax: Axes) -> None:
        ax.bar(dates, values, width=0.7, color=_BAR_COLOR, edgecolor="none", zorder=2)

    return _render_chart(dates, title, ylabel, draw)


def _pace_chart(runs: list[_Run], title: str) -> Optional[io.BytesIO]:
    """Pace over time (faster is up); bubble area = distance, color = climb per km."""
    dates = [r.date for r in runs]
    paces = [r.pace for r in runs]
    kms = [r.km for r in runs]
    climbs = [r.climb_per_km for r in runs]
    hilly = any(c > 0 for c in climbs)

    def area(km: float) -> float:
        return max(_MIN_BUBBLE_AREA, _MAX_BUBBLE_AREA * km / max(kms))

    def draw(fig: Figure, ax: Axes) -> None:
        color = (
            {
                "c": climbs,
                "cmap": _CLIMB_CMAP,
                "vmin": 0,
                "vmax": max(_MIN_CLIMB_SCALE, max(climbs)),
            }
            if hilly
            else {"color": _BAR_COLOR}
        )
        points = ax.scatter(
            dates, paces, s=[area(km) for km in kms],
            edgecolors="white", linewidths=1.5, zorder=3, **color,
        )

        ax.invert_yaxis()
        ax.yaxis.set_major_locator(_pace_locator(max(paces) - min(paces)))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _format_pace(v)))
        ax.margins(y=0.15)

        _add_distance_legend(fig, ax, kms, area)
        if hilly:
            _add_climb_colorbar(fig, ax, points)

    return _render_chart(dates, title, "Pace (min/km)", draw)


def _add_distance_legend(
    fig: Figure, ax: Axes, kms: list[float], area: Callable[[float], float]
) -> None:
    reference_kms = sorted({max(1, round(min(kms))), max(1, round(max(kms)))})
    handles = [
        ax.scatter([], [], s=area(km), color=_LEGEND_MARKER_COLOR, edgecolors="white", label=f"{km} km")
        for km in reference_kms
    ]
    fig.legend(
        handles=handles,
        loc="outside lower center",
        ncol=len(handles),
        frameon=False,
        fontsize=10,
        labelcolor=_TEXT_COLOR,
    )


def _add_climb_colorbar(fig: Figure, ax: Axes, points: PathCollection) -> None:
    cbar = fig.colorbar(points, ax=ax, location="bottom", shrink=0.7, aspect=30)
    cbar.set_label("Climb (m/km)", fontsize=10, color=_TEXT_COLOR)
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(colors=_AXIS_COLOR, labelsize=9, length=0)


def _pace_locator(span_minutes: float) -> MultipleLocator:
    for step_seconds in (5, 10, 15, 30, 60, 120):
        if span_minutes * 60 / step_seconds <= 6:
            return MultipleLocator(step_seconds / 60)
    return MultipleLocator(5)


def _render_chart(
    dates: list[datetime],
    title: str,
    ylabel: str,
    draw: Callable[[Figure, Axes], None],
) -> Optional[io.BytesIO]:
    fig, ax = plt.subplots(figsize=(5.5, 7.5), dpi=160, layout="constrained")
    try:
        draw(fig, ax)
        _style_axes(ax, dates, title, ylabel)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
        buf.seek(0)
        return buf
    except Exception:
        logger.error("Failed to generate chart", exc_info=True)
        return None
    finally:
        plt.close(fig)


def _date_limits(dates: list[datetime]) -> tuple[datetime, datetime]:
    first, last = min(dates), max(dates)
    pad = max((last - first) * 0.05, _MIN_DATE_PAD)
    return first - pad, last + pad


def _style_axes(ax: Axes, dates: list[datetime], title: str, ylabel: str) -> None:
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
    ax.set_xlim(*_date_limits(dates))

    for label in ax.get_xticklabels():
        label.set_rotation(35)
        label.set_horizontalalignment("right")
