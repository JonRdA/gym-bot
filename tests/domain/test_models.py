from datetime import datetime

from bson import ObjectId

from gym_bot.domain.models import Exercise, ExerciseSet, Training, Workout


def test_exercise_set_accepts_mixed_int_float_metrics():
    s = ExerciseSet(metrics={"reps": 10, "weight": 42.5})

    assert s.metrics == {"reps": 10, "weight": 42.5}


def test_exercise_rest_defaults_to_none():
    ex = Exercise(name="pullup")

    assert ex.rest is None
    assert ex.sets == []


def test_exercise_accepts_rest_as_int():
    ex = Exercise(name="pullup", rest=180)

    assert ex.rest == 180


def test_training_parses_mongo_document_with_object_id():
    oid = ObjectId()
    doc = {
        "_id": oid,
        "user_id": 42,
        "date": datetime(2026, 4, 1, 18, 0),
        "duration": 60,
        "workouts": [
            {
                "name": "pull",
                "completed": True,
                "exercises": [
                    {"name": "pullup", "rest": 120, "sets": [{"metrics": {"reps": 8}}]}
                ],
            }
        ],
    }

    training = Training(**doc)

    assert training.id == oid
    assert training.user_id == 42
    assert training.workouts[0].exercises[0].rest == 120
    assert training.workouts[0].exercises[0].sets[0].metrics == {"reps": 8}


def test_training_round_trips_through_model_dump():
    original = Training(
        user_id=1,
        date=datetime(2026, 4, 1),
        duration=45,
        workouts=[Workout(name="push", completed=False)],
    )

    restored = Training(**original.model_dump())

    assert restored.user_id == original.user_id
    assert restored.workouts[0].name == "push"
    assert restored.workouts[0].completed is False


def test_models_ignore_extra_fields():
    ex = Exercise(name="pullup", sets=[], not_a_field="ignored")

    assert not hasattr(ex, "not_a_field")
