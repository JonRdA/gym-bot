import logging
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

from src.models.domain import Metric

logger = logging.getLogger(__name__)

class SpecialCommand(Enum):
    """Enumeration for special user commands."""
    DONE_EXERCISE = auto()
    REPEAT_SET = auto()

class ParseResult(BaseModel):
    """Structured result for the input parser."""
    data: Union[Dict[Metric, Any], SpecialCommand, None] = None
    error_message: Optional[str] = None

class InputParser:
    """Parses user text input into structured data or commands."""

    def parse(self, text: str, expected_metrics: List[Metric]) -> ParseResult:
        """Parses a user's message for a set."""
        clean_text = text.strip().lower()

        # Check for special commands first
        if clean_text in ["done", "d", "/done"]:
            return ParseResult(data=SpecialCommand.DONE_EXERCISE)
        if clean_text in ["repeat", "r", "s", "/repeat", "same"]:
            return ParseResult(data=SpecialCommand.REPEAT_SET)

        # Attempt to parse as metric values
        parts = [p.strip() for p in clean_text.split(',')]
        
        if len(parts) != len(expected_metrics):
            msg = f"Invalid input. Expected {len(expected_metrics)} values for ({', '.join(m.value for m in expected_metrics)}), but got {len(parts)}."
            return ParseResult(error_message=msg)
        
        try:
            parsed_metrics: Dict[Metric, Any] = {}
            for i, metric in enumerate(expected_metrics):
                # Attempt to convert to float, then to int if it's a whole number
                value = float(parts[i])
                if value.is_integer():
                    value = int(value)
                parsed_metrics[metric] = value
            return ParseResult(data=parsed_metrics)
        except ValueError:
            msg = f"Invalid value. Please enter numbers for the metrics. You entered: '{text}'"
            return ParseResult(error_message=msg)