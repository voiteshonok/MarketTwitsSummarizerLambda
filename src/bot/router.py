"""
Command routing logic.

This module handles routing of parsed commands to their respective handlers.
"""

import logging
from typing import Callable, Awaitable

from src.bot.parser import parse_command
from src.bot.commands import (
    handle_start_command,
    handle_subscribe_command,
    handle_unsubscribe_command,
    handle_get_latest_command,
    handle_help_command,
    handle_unknown_command,
)

logger = logging.getLogger(__name__)


async def process_command(
    chat_id: int,
    message_text: str,
    send_message_func: Callable[[str, int, str], Awaitable[bool]],
    bot_token: str
) -> bool:
    """
    Process bot commands and route to appropriate handler.
    
    Args:
        chat_id: Telegram chat ID
        message_text: Message text from user
        send_message_func: Function to send messages (bot_token, chat_id, message)
        bot_token: Telegram bot token
        
    Returns:
        True if command processed successfully, False otherwise
    """
    command, args = parse_command(message_text)
    
    if not command:
        # Not a command, ignore non-command messages
        logger.info(f"Received non-command message from chat_id {chat_id}, ignoring")
        return True
    
    # Route commands to handlers
    command_handlers = {
        "start": handle_start_command,
        "subscribe": handle_subscribe_command,
        "unsubscribe": handle_unsubscribe_command,
        "get_latest": handle_get_latest_command,
        "help": handle_help_command,
    }
    
    handler = command_handlers.get(command)
    
    if handler:
        try:
            return await handler(chat_id, send_message_func, bot_token)
        except Exception as e:
            logger.error(f"Error processing command {command}: {e}")
            from src.bot.messages import get_error_message
            error_message = get_error_message()
            return await send_message_func(bot_token, chat_id, error_message)
    else:
        return await handle_unknown_command(chat_id, command, send_message_func, bot_token)

