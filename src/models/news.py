"""
News-related data models.

This module contains data models for news items, batches, and summaries.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Optional, Any


@dataclass
class NewsItem:
    """Model for a single news item."""
    message_id: int
    text: str
    date: datetime
    views: Optional[int] = None
    forwards: Optional[int] = None


@dataclass
class NewsBatch:
    """Model for a batch of news items."""
    items: List[NewsItem]
    start_date: datetime
    end_date: datetime
    total_count: int


@dataclass
class Summary:
    """Model for the daily summary."""
    date: Any  # Can be datetime or date
    summary_text: str
    news_count: int
    key_topics: List[str] = field(default_factory=list)
    
    def _format_date(self, date_obj: Any) -> str:
        """
        Format date object to string.
        
        Args:
            date_obj: Date or datetime object to format
            
        Returns:
            Formatted date string (YYYY-MM-DD)
        """
        if isinstance(date_obj, datetime):
            return date_obj.strftime('%Y-%m-%d')
        elif hasattr(date_obj, 'strftime'):
            return date_obj.strftime('%Y-%m-%d')
        else:
            return str(date_obj)

