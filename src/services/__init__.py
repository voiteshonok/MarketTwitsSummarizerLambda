"""
Services layer for business logic.

This module contains service classes and functions that handle core business operations:
- Telegram client for sending messages
- News dumper for fetching Telegram channel messages
- News summarizer using OpenAI
- Daily job orchestration
"""

from src.services.telegram_client import send_message
from src.services.news_dumper import TelegramDumper
from src.services.summarizer import NewsSummarizer
from src.services.daily_job import run_daily_job_async

__all__ = [
    "send_message",
    "TelegramDumper",
    "NewsSummarizer",
    "run_daily_job_async",
]

