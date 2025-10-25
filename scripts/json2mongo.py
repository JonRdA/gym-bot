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
from services.mongo_service import MongoService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def upload_single_file(filepath: str, mongo_service: MongoService) -> bool:
    """Reads a single JSON file and upserts it to MongoDB."""
    logging.info("Processing file: %s", filepath)
    try:
        filename = os.path.basename(filepath)
        training_id = filename.split('_')[-1].replace('.json', '')
        if len(training_id) != 24:
            raise ValueError("Invalid ObjectId format in filename")

        with open(filepath, 'r', encoding='utf-8') as f:
            training_data = json.load(f)
            training = Training(**training_data)
        
        return mongo_service.update_training(training_id, training)

    except (IndexError, ValueError) as e:
        logging.error("Skipping '%s'. Could not parse ObjectId. Details: %s", filename, e, exc_info=True)
        return False
    except (json.JSONDecodeError, IOError) as e:
        logging.error("Skipping '%s'. Error reading file. Details: %s", filename, e, exc_info=True)
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
        default='local',  # Default to 'local' for safety
        choices=['local', 'raspy'],
        help="Environment to target ('local' or 'raspy'). Defaults to 'local'."
    )
    args = parser.parse_args()
    input_path = args.path

    try:
        # The factory creates settings based on the command-line argument.
        settings = Settings.load(args.env)
        logging.info("--> Targeting '%s' environment (host: %s)", args.env, settings.mongo.host)

        mongo_service = MongoService(settings)
        success_count = 0
        fail_count = 0

        if os.path.isfile(input_path):
            if input_path.endswith('.json'):
                if upload_single_file(input_path, mongo_service):
                    success_count += 1
                else:
                    fail_count += 1
            else:
                logging.error("Error: Provided file is not a .json file.")
                sys.exit(1)

        elif os.path.isdir(input_path):
            logging.info("Processing all .json files in directory: %s", input_path)
            for filename in os.listdir(input_path):
                if filename.endswith('.json'):
                    filepath = os.path.join(input_path, filename)
                    if upload_single_file(filepath, mongo_service):
                        success_count += 1
                    else:
                        fail_count += 1
        else:
            logging.error("Error: Path does not exist or is not a valid file/directory: %s", input_path)
            sys.exit(1)
            
        logging.info("--- Upload Complete ---")
        logging.info("✅ Succeeded: %d", success_count)
        logging.info("❌ Failed:    %d", fail_count)

    except Exception as e:
        logging.critical("An unexpected error occurred during the process: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

