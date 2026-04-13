from pydantic import BaseModel, field_validator

from gym_bot.domain.metrics import METRIC_REGISTRY


class ExerciseConfig(BaseModel):
    name: str
    metrics: list[str]
    track_rest: bool = False

    @field_validator("metrics")
    @classmethod
    def validate_metrics(cls, v: list[str]) -> list[str]:
        for m in v:
            if m not in METRIC_REGISTRY:
                raise ValueError(f"Unknown metric: {m!r}")
        return v


class WorkoutConfig(BaseModel):
    exercises: list[ExerciseConfig]


class UserConfig(BaseModel):
    user_id: int
    workouts: dict[str, WorkoutConfig]

    @property
    def workout_names(self) -> list[str]:
        return list(self.workouts.keys())

    def get_workout(self, name: str) -> WorkoutConfig | None:
        return self.workouts.get(name)

    def get_exercise(self, exercise_name: str) -> ExerciseConfig | None:
        for workout in self.workouts.values():
            for ex in workout.exercises:
                if ex.name == exercise_name:
                    return ex
        return None

    def get_all_exercise_names(self) -> list[str]:
        names = []
        for workout in self.workouts.values():
            for ex in workout.exercises:
                names.append(ex.name)
        return names

    def get_workouts_for_exercise(self, exercise_name: str) -> list[str]:
        result = []
        for wo_name, workout in self.workouts.items():
            if any(ex.name == exercise_name for ex in workout.exercises):
                result.append(wo_name)
        return result
