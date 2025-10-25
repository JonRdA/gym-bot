import calendar
import json
import logging
import os
from datetime import datetime, timedelta

from config import Settings
from models.domain import Training, Workout, WoSet
from services.mongo import MongoService
from services.reporting_service import ReportingService

logger = logging.getLogger(__name__)


def load_training(filepath: str):
    """Reads a single JSON file and loads training."""
    logger.info("Processing file: %s", filepath)
    filename = os.path.basename(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        training_data = json.load(f)
        training = Training(**training_data)
    
    return training



def main():
    filepath = "trainings_backup/2025-10-14_68f029be9e13ea7a414692e6.json"
    rs = ReportingService(None, None)
    training = load_training(filepath)
    msg = rs.format_training_details(training)
    msg = rs.format_training_details2(training)
    print(msg)

if __name__ == "__main__":
    main()