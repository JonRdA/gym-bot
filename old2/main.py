import logging

from src.config import settings
from src.models.domain import TrainingName
from src.services.flow_service import WorkoutFlowService
from src.services.input_parser import InputParser
from src.services.mongo_service import MongoService
from src.services.program_loader import ProgramLoader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_demo():
    """Demonstrates the full interactive workout flow."""
    logger.info("--- Starting Interactive Workout Flow Demo ---")

    # 1. Setup all services (Dependency Injection)
    program_loader = ProgramLoader()
    mongo_service = MongoService(settings)
    input_parser = InputParser()
    flow_service = WorkoutFlowService(program_loader, mongo_service, input_parser)

    # 2. Simulate a full user conversation
    user_id = 67890
    
    # Helper function to simulate a turn
    def user_turn(message: str):
        print(f"\n> USER: {message}")
        response = flow_service.handle_user_response(user_id, message)
        print(f"< BOT: {response}")

    # Start the training
    print(f"< BOT: Starting training for user {user_id}...")
    start_message = flow_service.start_training(user_id, TrainingName.LOWER_MOVGH)
    print(f"< BOT: {start_message}")

    # Log sets for the first exercise
    user_turn("10, 15")    # reps, weight for cossack_squat
    user_turn("10, 15.5")
    user_turn("r")         # repeat the last set
    user_turn("done")      # finish cossack_squat

    # Log sets for the second exercise
    user_turn("12, 5")     # reps, knee2floor for shrimp
    user_turn("done")

    # Log sets for the third exercise
    user_turn("8, 50")     # reps, weight for stride_stance_deadlift
    user_turn("done")

    # Log sets for the fourth exercise (next workout)
    user_turn("60, 20")    # time, feet2floor for bridge
    user_turn("done")

    # Log sets for the final exercise
    user_turn("45")        # time for chest2wall
    user_turn("done")

    # Check that the session is closed
    if user_id not in flow_service.active_sessions:
        print("\n✅ Session closed and saved successfully.")

    logger.info("--- Demo Finished ---")

if __name__ == "__main__":
    run_demo()