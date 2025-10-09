import logging
from typing import Dict

import yaml

logger = logging.getLogger(__name__)

class ProgramLoader:
    """Loads the training program configuration from a YAML file."""

    def __init__(self, config_path: str = "config/trainings.yaml"):
        """Initializes the loader with the path to the config file."""
        self.config_path = config_path
        self._program = None

    def load_program(self) -> Dict:
        """Loads the program from YAML, caching the result."""
        if self._program:
            return self._program
            
        logger.info("Loading training program from %s", self.config_path)
        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)
                self._program = config["trainings"]
                return self._program
        except FileNotFoundError:
            logger.error("Training config file not found at %s", self.config_path)
            raise
        except Exception as e:
            logger.error("Error parsing YAML config: %s", e)
            raise