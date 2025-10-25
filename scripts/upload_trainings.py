"""
Updates or inserts training records in MongoDB from JSON files.
Selects the target environment via a command-line argument.
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from config import Settings
from models.domain import Training
from services.mongo import MongoService

logging.basicConfig( level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def upload_single_file(filepath: str, mongo: MongoService) -> bool:
    """Reads a single JSON file and upserts it to MongoDB."""
    logger.info("Processing file: %s", filepath)
    try:
        filename = os.path.basename(filepath)
        training_id = filename.split('_')[-1].replace('.json', '')
        if len(training_id) != 24:
            raise ValueError("Invalid ObjectId format in filename")

        with open(filepath, 'r', encoding='utf-8') as f:
            training_data = json.load(f)
            training = Training(**training_data)
        
        return mongo.update_training(training_id, training)

    except (IndexError, ValueError) as e:
        logger.error("Skipping '%s'. Could not parse ObjectId. Details: %s", filename, e, exc_info=True)
        return False
    except (json.JSONDecodeError, IOError) as e:
        logger.error("Skipping '%s'. Error reading file. Details: %s", filename, e, exc_info=True)
        return False


def main():
    """Main function to parse arguments and trigger the upload."""
    parser = argparse.ArgumentParser(
        description="Upload training data to MongoDB from JSON files.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("path", type=str, help="Path to a single .json file or a directory.")
    parser.add_argument(
        "--env",
        type=str,
        required=True,
        choices=['local', 'raspy'],
        help="Environment to target ('local' or 'raspy')."
    )
    args = parser.parse_args()
    input_path = args.path

    try:
        # The factory creates settings based on the command-line argument.
        settings = Settings.load(args.env)
        logger.info("--> Targeting '%s' environment (host: %s)", args.env, settings.mongo.host)

        mongo = MongoService(settings)
        success_count = 0
        fail_count = 0

        if os.path.isfile(input_path):
            if input_path.endswith('.json'):
                if upload_single_file(input_path, mongo):
                    success_count += 1
                else:
                    fail_count += 1
            else:
                logger.error("Error: Provided file is not a .json file.")
                sys.exit(1)

        elif os.path.isdir(input_path):
            logger.info("Processing all .json files in directory: %s", input_path)
            for filename in os.listdir(input_path):
                if filename.endswith('.json'):
                    filepath = os.path.join(input_path, filename)
                    if upload_single_file(filepath, mongo):
                        success_count += 1
                    else:
                        fail_count += 1
        else:
            logger.error("Error: Path does not exist or is not a valid file/directory: %s", input_path)
            sys.exit(1)
            
        logger.info("--- Upload Complete ---")
        logger.info("✅ Succeeded: %d", success_count)
        logger.info("❌ Failed:    %d", fail_count)

    except Exception as e:
        logger.critical("An unexpected error occurred during the process: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

