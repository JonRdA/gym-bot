import calendar
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from gym_bot.db.repositories import TrainingRepository
from gym_bot.domain.models import Training
from gym_bot.settings import Settings

logger = logging.getLogger(__name__)


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
        calendar_str = f"`{month_calendar[0]}\n{month_calendar[1]}\n"

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

        calendar_str += "`"
        return header + calendar_str

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
