"""
Bot command handling module.

This module contains all Telegram bot command processing logic including:
- Command parsing
- Message templates
- Command handlers
- Command routing
"""

from src.bot.parser import parse_command
from src.bot.router import process_command

__all__ = ["parse_command", "process_command"]

