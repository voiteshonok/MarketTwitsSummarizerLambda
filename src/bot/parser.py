"""
Command parsing utilities.

This module handles parsing of Telegram bot commands from message text.
"""

from typing import Optional, List, Tuple


def parse_command(message_text: str) -> Tuple[Optional[str], List[str]]:
    """
    Parse command from message text.
    
    Args:
        message_text: Message text from Telegram
        
    Returns:
        Tuple of (command, args) or (None, []) if not a command
        
    Examples:
        >>> parse_command("/start")
        ('start', [])
        >>> parse_command("/subscribe")
        ('subscribe', [])
        >>> parse_command("hello")
        (None, [])
    """
    if not message_text or not message_text.startswith("/"):
        return None, []
    
    # Split command and arguments
    parts = message_text.split()
    command = parts[0][1:].lower()  # Remove '/' and convert to lowercase
    args = parts[1:] if len(parts) > 1 else []
    
    return command, args

