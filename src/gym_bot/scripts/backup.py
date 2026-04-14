"""Download and upload training backups.

Usage:
    python -m gym_bot.scripts.backup download
    python -m gym_bot.scripts.backup upload <path>
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import date, datetime

from bson import ObjectId

from gym_bot.db.mongo import Database
from gym_bot.db.repositories import TrainingRepository
from gym_bot.domain.models import Training
from gym_bot.settings import Settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _json_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


async def download(settings: Settings):
    db = Database(settings.mongo_uri, settings.mongo_database)
    repo = TrainingRepository(db)

    backup_dir = "trainings_backup"
    os.makedirs(backup_dir, exist_ok=True)

    trainings = await repo.find_all()
    if not trainings:
        logger.warning("No trainings to download")
        return

    logger.info("Downloading %d trainings", len(trainings))
    for training in trainings:
        doc = training.model_dump(by_alias=True, exclude_none=True)
        filename = f"{training.date.strftime('%Y-%m-%d')}_{training.id}.json"
        filepath = os.path.join(backup_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(doc, f, default=_json_serializer, indent=2)

    logger.info("Downloaded %d files to %s", len(trainings), backup_dir)
    db.close()


async def upload(settings: Settings, path: str):
    db = Database(settings.mongo_uri, settings.mongo_database)
    repo = TrainingRepository(db)
    col = db.trainings

    files = []
    if os.path.isfile(path) and path.endswith(".json"):
        files = [path]
    elif os.path.isdir(path):
        files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith(".json")]
    else:
        logger.error("Invalid path: %s", path)
        sys.exit(1)

    success, failed = 0, 0
    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            training = Training(**data)
            doc = training.model_dump(mode="python", by_alias=True)
            await col.replace_one(
                {"_id": training.id}, doc, upsert=True
            )
            success += 1
        except Exception:
            logger.error("Failed to upload %s", filepath, exc_info=True)
            failed += 1

    logger.info("Upload complete: %d ok, %d failed", success, failed)
    db.close()


def main():
    parser = argparse.ArgumentParser(description="Backup/restore training data")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("download")
    up = sub.add_parser("upload")
    up.add_argument("path", help="JSON file or directory")
    args = parser.parse_args()

    settings = Settings()

    if args.command == "download":
        asyncio.run(download(settings))
    elif args.command == "upload":
        asyncio.run(upload(settings, args.path))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
