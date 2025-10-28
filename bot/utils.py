"""
Utility functions for the workout bot.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Tuple


def chunk_list(items: List, chunk_size: int) -> List[List]:
    """Splits a list into sublists of fixed size."""
    if chunk_size < 1:
        chunk_size = 1
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def get_date_range_from_days(days_back: Optional[int], default: int) -> Tuple[datetime, datetime]:
    """
    Calculates a date range from N days ago to now.
    """
    try:
        days = int(days_back) if days_back is not None else default
    except (ValueError, TypeError):
        days = default
        
    if days < 1:
        days = 1
        
    t1 = datetime.now()
    t0 = t1 - timedelta(days=days)
    return t0, t1


def get_date_range_for_month(year: int, month: int) -> Tuple[datetime, datetime]:
    """
    Calculates the start and end datetimes for a given month.
    """
    t0 = datetime(year, month, 1)
    # Get first day of next month, then subtract one microsecond
    t1_month = month % 12 + 1
    t1_year = year + (1 if month == 12 else 0)
    t1 = datetime(t1_year, t1_month, 1) - timedelta(microseconds=1)
    
    return t0, t1