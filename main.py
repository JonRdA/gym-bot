import logging

from src.models.domain import TrainingName
from src.services.flow_service import WorkoutFlowService
from src.services.program_loader import ProgramLoader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_demo():
    """Demonstrates the workout flow service."""
    logger.info("--- Starting Workout Flow Demo ---")

    # 1. Setup services (Dependency Injection)
    program_loader = ProgramLoader()
    flow_service = WorkoutFlowService(program_loader)

    # 2. Simulate a user starting a training session
    user_id = 12345
    training_name = TrainingName.UPPER_FRONTSPLIT
    
    print("\n[BOT]")
    question = flow_service.start_training(user_id, training_name)
    print(question)

    # 3. Simulate the user providing data (we will build the logic for this next)
    # For now, we'll just manually advance the state to show the flow.
    state = flow_service.active_sessions.get(user_id)
    if state:
        print("\n[USER] provides data for pullups...")
        state.current_exercise_index += 1 # Manually advance to the next exercise
        
        print("\n[BOT]")
        question = flow_service._get_current_question(user_id)
        print(question)

        print("\n[USER] provides data for dips...")
        state.current_exercise_index += 1
        
        print("\n[BOT]")
        question = flow_service._get_current_question(user_id)
        print(question)

        print("\n[USER] provides data for pike pushups...")
        state.current_exercise_index += 1
        
        # Now we should move to the next workout (frontsplit)
        print("\n[BOT]")
        question = flow_service._get_current_question(user_id)
        print(question)

        print("\n[USER] provides data for wide split squat...")
        state.current_exercise_index += 1

        # Now we should finish the training
        print("\n[BOT]")
        question = flow_service._get_current_question(user_id)
        print(question)

    logger.info("--- Demo Finished ---")


if __name__ == "__main__":
    run_demo()