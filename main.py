import logging
from datetime import date

from src.config import settings
from src.models.domain import (
    Exercise,
    ExerciseName,
    Metric,
    Training,
    TrainingName,
    Workout,
    WorkoutName,
    WoSet,
)
from src.services.mongo_service import MongoService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_demo():
    """Demonstrates creating and saving a training session."""
    logger.info("--- Starting Workout Bot Demo ---")

    # 1. Initialize the service
    # This single line gives us access to our database.
    mongo_service = MongoService(settings)

    # 2. Simulate user input and create a training object
    # In the real bot, this data would come from the user conversation.
    sample_training = Training(
        user_id=12345,
        session_date=date.today(),
        name=TrainingName.LOWER_MOVGH,
        duration_minutes=55,
        workouts=[
            Workout(
                name=WorkoutName.LOWER,
                exercises=[
                    Exercise(
                        name=ExerciseName.COSSACK_SQUAT,
                        sets=[
                            WoSet(metrics={Metric.REPS: 8, Metric.WEIGHT: 10}),
                            WoSet(metrics={Metric.REPS: 8, Metric.WEIGHT: 10}),
                        ]
                    ),
                    Exercise(
                        name=ExerciseName.SHRIMP,
                        sets=[
                            WoSet(metrics={Metric.REPS: 10, Metric.KNEE2FLOOR: 5}),
                            WoSet(metrics={Metric.REPS: 10, Metric.KNEE2FLOOR: 5}),
                        ]
                    ),
                ]
            ),
            Workout(
                name=WorkoutName.MOV_GH,
                exercises=[
                    Exercise(
                        name=ExerciseName.BRIDGE,
                        sets=[
                            WoSet(metrics={Metric.TIME: 60, Metric.FEET2FLOOR: 20})
                        ]
                    )
                ]
            )
        ]
    )

    # 3. Save the training session
    try:
        mongo_service.save_training(sample_training)
    except Exception as e:
        logger.error(f"An error occurred during the demo: {e}")
    finally:
        # 4. Clean up the connection
        mongo_service.close_connection()
    
    logger.info("--- Demo Finished ---")


if __name__ == "__main__":
    run_demo()