import calendar
import io
import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta
from matplotlib.colors import LinearSegmentedColormap, Normalize

from gym_bot.db.repositories import TrainingRepository
from gym_bot.domain.models import Training
from gym_bot.settings import Settings

logger = logging.getLogger(__name__)

_NO_TRAINING_COLOR = "#ebedf0"
_HEATMAP_TEXT_COLOR = "#444444"
_HEATMAP_AXIS_COLOR = "#888888"
_HEATMAP_CMAP = LinearSegmentedColormap.from_list(
    "training_greens",
    [plt.cm.Greens(0.20), plt.cm.Greens(0.95)],
)


class ReportingService:
    def __init__(self, training_repo: TrainingRepository, settings: Settings):
        self._repo = training_repo
        self._settings = settings

    async def generate_activity_calendar(
        self,
        user_id: int,
        year: int,
        month: int,
        workout_filter: Optional[str],
    ) -> str | None:
        t0 = datetime(year, month, 1)
        t1 = (t0 + timedelta(days=32)).replace(day=1)

        if workout_filter:
            trainings = await self._repo.find_with_workout_filter(
                user_id, t0, t1, include=[workout_filter]
            )
        else:
            trainings = await self._repo.find_with_workout_filter(
                user_id, t0, t1, exclude=self._settings.excluded_workouts
            )

        # Map day -> completed status
        training_days: dict[int, bool] = {}
        for training in trainings:
            day = training.date.day
            all_completed = all(w.completed for w in training.workouts)
            training_days[day] = training_days.get(day, True) and all_completed

        cal = calendar.TextCalendar(calendar.MONDAY)
        month_calendar = cal.formatmonth(year, month).split("\n")

        month_name = t0.strftime("%B %Y")
        header = f"Activity for {month_name}\n"
        calendar_str = f"```\n{month_calendar[0]}\n{month_calendar[1]}\n"

        for line in month_calendar[2:]:
            if not line.strip():
                continue
            new_line = line
            for day_num, completed in training_days.items():
                day_str = f"{day_num: >2}"
                marker = "🟢" if completed else "🔶"
                pattern = rf"(?<!\d){re.escape(day_str)}(?!\d)"
                new_line = re.sub(pattern, marker, new_line)
            calendar_str += new_line + "\n"

        calendar_str += "```"
        return header + calendar_str

    async def generate_duration_heatmap(
        self,
        user_id: int,
        months: int,
        workout_filter: Optional[str] = None,
    ) -> Optional[io.BytesIO]:
        now = datetime.now()
        end_date = now.date()
        start_dt = (now - relativedelta(months=months - 1)).replace(day=1)
        start_date = start_dt.date()
        t0 = datetime(start_date.year, start_date.month, start_date.day)
        t1 = datetime(end_date.year, end_date.month, end_date.day) + timedelta(days=1)

        if workout_filter:
            trainings = await self._repo.find_with_workout_filter(
                user_id, t0, t1, include=[workout_filter]
            )
        else:
            trainings = await self._repo.find_with_workout_filter(
                user_id, t0, t1, exclude=self._settings.excluded_workouts
            )

        day_durations: dict[date, int] = {}
        for training in trainings:
            day = training.date.date()
            if start_date <= day <= end_date:
                day_durations[day] = day_durations.get(day, 0) + training.duration

        return _duration_heatmap(day_durations, start_date, end_date)

    def format_training_summary(self, training: Training) -> str:
        date_str = training.date.strftime("%Y-%m-%d")
        workouts = ", ".join(w.name.title() for w in training.workouts)
        return f"{date_str} ({training.duration} min)\n_{workouts}_"

    def format_training_details(self, training: Training) -> str:
        lines = [
            f"*{training.date.strftime('%Y-%m-%d')}*",
            f"{training.duration} min\n",
        ]

        for workout in training.workouts:
            status = "completed" if workout.completed else "not completed"
            lines.append(f"*{workout.name.replace('_', ' ').title()}* ({status})")

            if not workout.exercises:
                lines.append("  _No exercises logged_")
                continue

            for exercise in workout.exercises:
                if not exercise.sets:
                    lines.append(f"  *{exercise.name.replace('_', ' ').title()}* (No sets)")
                    continue

                metric_keys = ", ".join(exercise.sets[0].metrics.keys())
                lines.append(f"  *{exercise.name.replace('_', ' ').title()}* ({metric_keys})")

                for i, s in enumerate(exercise.sets, start=1):
                    values = ", ".join(str(v) for v in s.metrics.values())
                    lines.append(f"       #{i} → {values}")

            lines.append("")

        return "\n".join(lines).strip()


def _duration_heatmap(
    day_durations: dict[date, int],
    start_date: date,
    end_date: date,
) -> Optional[io.BytesIO]:
    grid_start = start_date - timedelta(days=start_date.weekday())

    weeks: list[list[date]] = []
    current = grid_start
    while current <= end_date:
        weeks.append([current + timedelta(days=d) for d in range(7)])
        current += timedelta(weeks=1)

    n_weeks = len(weeks)
    max_dur = max(day_durations.values(), default=60)
    norm = Normalize(vmin=0, vmax=max_dur)

    def cell_color(d: date):
        if d < start_date or d > end_date:
            return "white"
        dur = day_durations.get(d, 0)
        if dur == 0:
            return _NO_TRAINING_COLOR
        return _HEATMAP_CMAP(norm(dur))

    fig_w = max(4.0, n_weeks * 0.38 + 1.8)
    fig_h = 2.4

    try:
        fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)

        for col, week in enumerate(weeks):
            for row_idx, d in enumerate(week):
                rect = mpatches.Rectangle(
                    (col + 0.05, 6 - row_idx + 0.05), 0.85, 0.85,
                    linewidth=0, facecolor=cell_color(d),
                )
                ax.add_patch(rect)

        # Month labels at first column where each month appears
        seen_months: dict[tuple[int, int], int] = {}
        for col, week in enumerate(weeks):
            for d in week:
                if start_date <= d <= end_date:
                    key = (d.year, d.month)
                    if key not in seen_months:
                        seen_months[key] = col
        for (year, month), col in seen_months.items():
            ax.text(
                col + 0.5, 7.3, date(year, month, 1).strftime("%b"),
                ha="center", va="bottom", fontsize=8, color=_HEATMAP_TEXT_COLOR,
            )

        # Day-of-week labels (Mon / Wed / Fri)
        for row_idx, label in enumerate(["Mon", "", "Wed", "", "Fri", "", ""]):
            if label:
                ax.text(
                    -0.2, 6.5 - row_idx, label,
                    ha="right", va="center", fontsize=7, color=_HEATMAP_TEXT_COLOR,
                )

        ax.set_xlim(-0.8, n_weeks + 0.1)
        ax.set_ylim(-0.2, 7.8)
        ax.axis("off")

        sm = plt.cm.ScalarMappable(cmap=_HEATMAP_CMAP, norm=norm)
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=ax, orientation="vertical",
                            fraction=0.025, pad=0.01, shrink=0.75)
        cbar.set_label("min", fontsize=8, color=_HEATMAP_TEXT_COLOR)
        cbar.ax.tick_params(labelsize=7, colors=_HEATMAP_AXIS_COLOR, length=0)
        cbar.outline.set_visible(False)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white", dpi=150)
        buf.seek(0)
        return buf
    except Exception:
        logger.error("Failed to generate duration heatmap", exc_info=True)
        return None
    finally:
        plt.close(fig)
