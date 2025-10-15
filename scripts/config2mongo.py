"""
Loads a YAML workout configuration file and upserts it into the user_configurations
collection in MongoDB for a specific user.

This script allows you to set the initial workout templates for a user.

Prerequisites:
- pip install pymongo pyyaml python-dotenv

Usage:
- Make sure your .env file is in the same directory or a parent directory.
- Run the script with the user ID as an argument:
  python scripts/load_config.py 123456789
"""
import argparse
import os
import sys

import yaml
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
MONGO_CONFIG_COLLECTION = os.getenv("MONGO_CONFIG_COLLECTION")
YAML_CONFIG_FILE = "training_config.yaml"


def load_and_insert_config(user_id: int):
    """Loads YAML config and upserts it for the given user_id."""
    if not MONGO_URI:
        sys.stderr.write("Error: MONGO_URI not found in environment variables.\n")
        sys.exit(1)

    try:
        with open(YAML_CONFIG_FILE, 'r') as f:
            config_data = yaml.safe_load(f)
            if 'workouts' not in config_data:
                sys.stderr.write(f"Error: 'workouts' key not found in {YAML_CONFIG_FILE}\n")
                sys.exit(1)
            workouts_config = config_data['workouts']

    except FileNotFoundError:
        sys.stderr.write(f"Error: Configuration file '{YAML_CONFIG_FILE}' not found.\n")
        sys.exit(1)
    except yaml.YAMLError as e:
        sys.stderr.write(f"Error parsing YAML file: {e}\n")
        sys.exit(1)

    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB_NAME]
        collection = db[MONGO_CONFIG_COLLECTION]

        # Use update_one with upsert=True to either insert a new document
        # or update the existing one for the user.
        result = collection.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, "workouts": workouts_config}},
            upsert=True
        )

        if result.upserted_id:
            print(f"Successfully inserted new configuration for user_id: {user_id}")
        elif result.matched_count > 0:
            print(f"Successfully updated existing configuration for user_id: {user_id}")

    except ConnectionFailure as e:
        sys.stderr.write(f"Error: Could not connect to MongoDB.\nDetails: {e}\n")
        sys.exit(1)
    finally:
        if 'client' in locals():
            client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load workout configurations from YAML into MongoDB for a specific user."
    )
    parser.add_argument(
        "user_id",
        help="The integer Telegram user ID to associate with this configuration.",
        type=int
    )
    args = parser.parse_args()

    load_and_insert_config(user_id=args.user_id)
