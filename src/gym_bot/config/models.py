from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from gym_bot.domain.metrics import METRIC_REGISTRY


class ExerciseConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    metrics: list[str]
    track_rest: bool = False

    @field_validator("metrics")
    @classmethod
    def _validate_metrics(cls, v: list[str]) -> list[str]:
        for m in v:
            if m not in METRIC_REGISTRY:
                raise ValueError(f"Unknown metric: {m!r}")
        return v


class UserConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: int
    exercises: dict[str, ExerciseConfig]
    workouts: dict[str, list[str]]

    @model_validator(mode="after")
    def _validate_workout_refs(self) -> "UserConfig":
        for workout_name, names in self.workouts.items():
            unknown = [n for n in names if n not in self.exercises]
            if unknown:
                raise ValueError(
                    f"Workout {workout_name!r} references unknown exercises: {unknown}"
                )
        return self

    @property
    def workout_names(self) -> list[str]:
        return list(self.workouts.keys())

    def get_exercise(self, name: str) -> ExerciseConfig | None:
        return self.exercises.get(name)

    def resolve_workout(self, workout_name: str) -> list[tuple[str, ExerciseConfig]]:
        return [(n, self.exercises[n]) for n in self.workouts.get(workout_name, [])]

    def get_all_exercise_names(self) -> list[str]:
        return list(self.exercises.keys())

    def get_workouts_for_exercise(self, exercise_name: str) -> list[str]:
        return [w for w, names in self.workouts.items() if exercise_name in names]
