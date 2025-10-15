"""
Connects to a remote MongoDB instance to fetch all training documents
and print them to stdout as a JSON array.

Prerequisites on your local machine:
- pip install pymongo python-dotenv

Usage:
1. Ensure the MongoDB port (27017) is exposed in the docker-compose.yml
   on your Raspberry Pi (e.g., ports: - "27017:27017").
2. Run the script and redirect the output to a file:
   python backup_script.py > trainings_backup_$(date +%F).json
3. Use a diff tool to compare backups:
   diff trainings_backup_2025-10-12.json trainings_backup_2025-10-13.json
"""
import json
import os
import sys
from datetime import date, datetime

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

load_dotenv()

# --- Configuration ---
# Details for your Raspberry Pi running MongoDB
RASPBERRY_PI_IP = os.getenv("RASPBERRY_PI_IP", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))

# MongoDB connection details
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "workout_tracker")
MONGO_COLLECTION = "trainings"


def json_serializer(obj):
    """Custom JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def fetch_trainings():
    """Establishes a direct connection and fetches all training documents."""
    mongo_uri = f"mongodb://{RASPBERRY_PI_IP}:{MONGO_PORT}/"
    sys.stderr.write(f"Connecting to MongoDB at {mongo_uri}...\n")
    
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        # The ismaster command is cheap and does not require auth.
        client.admin.command('ismaster')
        
        db = client[MONGO_DB_NAME]
        collection = db[MONGO_COLLECTION]
        
        sys.stderr.write(f"Fetching documents from collection '{MONGO_COLLECTION}'...\n")
        documents = list(collection.find({}, {"_id": 0})) # Find all, exclude the _id field
        
        sys.stderr.write(f"Found {len(documents)} documents. Serializing to JSON...\n")
        
        # Pretty-print the JSON to make diffs more readable
        json_output = json.dumps(documents, default=json_serializer, indent=2)
        
        # Print the final JSON to stdout
        print(json_output)
        sys.stderr.write("\nExport complete.\n")

    except ConnectionFailure as e:
        sys.stderr.write(f"Error: Could not connect to MongoDB.\n")
        sys.stderr.write(f"Please ensure MongoDB is running on '{RASPBERRY_PI_IP}' and the port {MONGO_PORT} is accessible.\n")
        sys.stderr.write(f"Details: {e}\n")
        sys.exit(1)
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    fetch_trainings()

