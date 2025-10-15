"""
Connects to a MongoDB instance, fetches all training documents, and saves
each training as a separate JSON file in a specified backup directory.

This strategy is ideal for version control systems like Git, as it creates
an atomic commit for each new training log.
"""
import json
import os
import sys
from datetime import date, datetime

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# Use the centralized settings object
from config import settings


def json_serializer(obj):
    """Custom JSON serializer for datetime objects."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def backup_trainings_to_files():
    """Fetches all trainings and saves them to individual files."""
    backup_dir = settings.backup.directory
    print(backup_dir)
    print(settings.mongo.db_name)
    print(settings.mongo.trainings_collection)
    
    # Ensure the backup directory exists
    try:
        os.makedirs(backup_dir, exist_ok=True)
        sys.stderr.write(f"Using backup directory: '{backup_dir}'\n")
    except OSError as e:
        sys.stderr.write(f"Error: Could not create backup directory '{backup_dir}'.\nDetails: {e}\n")
        sys.exit(1)
        
    sys.stderr.write(f"Connecting to MongoDB at {settings.mongo_uri}...\n")
    
    try:
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ismaster')
        
        db = client[settings.mongo.db_name]
        collection = db[settings.mongo.trainings_collection]
        
        sys.stderr.write(f"Fetching documents from collection '{collection.name}'...\n")
        documents = list(collection.find({}))
        
        if not documents:
            sys.stderr.write("No documents found to back up.\n")
            return

        sys.stderr.write(f"Found {len(documents)} documents. Writing to individual files...\n")
        
        for doc in documents:
            # Create a filename based on the training date and MongoDB ObjectId
            doc_id = str(doc.pop("_id")) # Remove _id from JSON, but use it for filename
            training_date = doc['date']
            filename = f"{training_date.strftime('%Y-%m-%d')}_{doc_id[:6]}.json"
            filepath = os.path.join(backup_dir, filename)

            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(doc, f, default=json_serializer, indent=2)
            except IOError as e:
                sys.stderr.write(f"Error writing to file {filepath}: {e}\n")
                continue # Move to the next document

        sys.stderr.write(f"\nSuccessfully backed up {len(documents)} trainings.\n")

    except ConnectionFailure as e:
        sys.stderr.write(f"Error: Could not connect to MongoDB.\nDetails: {e}\n")
        sys.exit(1)
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    backup_trainings_to_files()

