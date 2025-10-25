"""
Connects to a MongoDB instance via MongoService and saves each training
as a separate JSON file in a specified backup directory.

This script is designed to be run from the command line, targeting a
specific environment (e.g., 'local' or 'raspy').
"""
import argparse
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

from bson import ObjectId

# Add project root to path to allow importing from services
sys.path.append(str(Path(__file__).resolve().parents[1]))

from config import Settings
from services.mongo_service import MongoService

# --- Setup Logging ---
logging.basicConfig( level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def json_serializer(obj):
    """Custom JSON serializer for datetime and ObjectId objects."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


def run_export(mongo_service: MongoService, settings: Settings) -> bool:
    """
    Fetches all trainings from the MongoService and saves them to individual files.
    """
    backup_dir = settings.backup.directory
    
    # Ensure the backup directory exists
    try:
        os.makedirs(backup_dir, exist_ok=True)
        logger.info(f"Using backup directory: '{backup_dir}'")
    except OSError:
        logger.critical(f"Error: Could not create backup directory '{backup_dir}'.", exc_info=True)
        return False

    logger.info("Fetching all training documents from database...")
    # This now returns a list of Pydantic Training models
    documents = mongo_service.query_all_trainings()
    
    if not documents:
        logger.warning("No documents found to back up.")
        return True  # Not an error, just nothing to do

    logger.info(f"Found {len(documents)} documents. Writing to individual files...")
    
    success_count = 0
    fail_count = 0
    
    for training in documents:
        try:
            # Convert the Pydantic model to a dict for serialization
            # by_alias=True ensures fields like 'id' are dumped as '_id'
            doc_dict = training.model_dump(by_alias=True, exclude_none=True)

            # Pop '_id' from the dict: use it for the filename, but don't save it in the JSON
            # This makes the JSON content pure data, without the db identifier
            mongo_id = training.mongo_id
            
            # Get the date directly from the model for the filename
            training_date = training.date
            
            filename = f"{training_date.strftime('%Y-%m-%d')}_{training.mongo_id}.json"
            filepath = os.path.join(backup_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                # Use the custom serializer to handle datetimes
                json.dump(doc_dict, f, default=json_serializer, indent=2)
            success_count += 1
            
        except (IOError, TypeError, KeyError) as e:
            doc_id_for_log = training.id if hasattr(training, 'id') else 'unknown_id'
            logger.error(f"Error processing document with id {doc_id_for_log}: {e}", exc_info=True)
            fail_count += 1
            continue  # Move to the next document

    logger.info(f"Export complete. {success_count} files written, {fail_count} files failed.")
    return fail_count == 0


def main():
    """Main function to parse arguments and trigger the export."""
    parser = argparse.ArgumentParser(
        description="Export training data from MongoDB to JSON files.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--env",
        type=str,
        required=True,
        choices=['local', 'raspy'],
        help="Environment to target ('local' or 'raspy')."
    )
    args = parser.parse_args()
    
    logger.info(f"--- Starting Training Export for '{args.env}' environment ---")
    
    try:
        # --- Dependency Injection ---
        # Use the new Settings.load classmethod
        settings = Settings.load(env=args.env)
        logger.info(f"Targeting host: {settings.mongo.host}")
        
        mongo_service = MongoService(settings)
        
        # --- Run Business Logic ---
        if run_export(mongo_service, settings):
            logger.info("--- Export finished successfully ---")
        else:
            logger.warning("--- Export finished with errors ---")

    except FileNotFoundError:
        logger.critical(f"Configuration Error: config-{args.env}.yaml not found.")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

