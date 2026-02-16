"""
Bot command handlers.

This module contains all individual command handler functions.
"""

import logging
from typing import TYPE_CHECKING

from src.database.repository import add_chat_id, remove_chat_id, get_latest_summary

if TYPE_CHECKING:
    # Avoid circular imports
    from src.services.telegram_client import send_message
    from src.config import config

logger = logging.getLogger(__name__)


async def handle_start_command(chat_id: int, send_message_func, bot_token: str) -> bool:
    """
    Handle /start command - welcome message.
    
    Args:
        chat_id: Telegram chat ID
        send_message_func: Function to send messages
        bot_token: Telegram bot token
        
    Returns:
        True if message sent successfully, False otherwise
    """
    from src.bot.messages import get_welcome_message
    
    welcome_message = get_welcome_message()
    return await send_message_func(bot_token, chat_id, welcome_message)


async def handle_subscribe_command(chat_id: int, send_message_func, bot_token: str) -> bool:
    """
    Handle /subscribe command - add user to subscription list.
    
    Args:
        chat_id: Telegram chat ID
        send_message_func: Function to send messages
        bot_token: Telegram bot token
        
    Returns:
        True if message sent successfully, False otherwise
    """
    from src.bot.messages import (
        get_subscribe_success_message,
        get_subscribe_already_message,
        get_subscribe_error_message
    )
    
    try:
        success = add_chat_id(chat_id)
        if success:
            message = get_subscribe_success_message()
        else:
            message = get_subscribe_already_message()
        return await send_message_func(bot_token, chat_id, message)
    except Exception as e:
        logger.error(f"Error in subscribe command: {e}")
        error_message = get_subscribe_error_message()
        return await send_message_func(bot_token, chat_id, error_message)


async def handle_unsubscribe_command(chat_id: int, send_message_func, bot_token: str) -> bool:
    """
    Handle /unsubscribe command - remove user from subscription list.
    
    Args:
        chat_id: Telegram chat ID
        send_message_func: Function to send messages
        bot_token: Telegram bot token
        
    Returns:
        True if message sent successfully, False otherwise
    """
    from src.bot.messages import (
        get_unsubscribe_success_message,
        get_unsubscribe_not_subscribed_message,
        get_unsubscribe_error_message
    )
    
    try:
        success = remove_chat_id(chat_id)
        if success:
            message = get_unsubscribe_success_message()
        else:
            message = get_unsubscribe_not_subscribed_message()
        return await send_message_func(bot_token, chat_id, message)
    except Exception as e:
        logger.error(f"Error in unsubscribe command: {e}")
        error_message = get_unsubscribe_error_message()
        return await send_message_func(bot_token, chat_id, error_message)


async def handle_get_latest_command(chat_id: int, send_message_func, bot_token: str) -> bool:
    """
    Handle /get_latest command - get the latest market summary.
    
    Args:
        chat_id: Telegram chat ID
        send_message_func: Function to send messages
        bot_token: Telegram bot token
        
    Returns:
        True if message sent successfully, False otherwise
    """
    from src.bot.messages import get_no_summary_message, get_latest_error_message
    
    try:
        summary = get_latest_summary()
        if summary:
            return await send_message_func(bot_token, chat_id, summary)
        else:
            message = get_no_summary_message()
            return await send_message_func(bot_token, chat_id, message)
    except Exception as e:
        logger.error(f"Error in get_latest command: {e}")
        error_message = get_latest_error_message()
        return await send_message_func(bot_token, chat_id, error_message)


async def handle_help_command(chat_id: int, send_message_func, bot_token: str) -> bool:
    """
    Handle /help command - show available commands.
    
    Args:
        chat_id: Telegram chat ID
        send_message_func: Function to send messages
        bot_token: Telegram bot token
        
    Returns:
        True if message sent successfully, False otherwise
    """
    from src.bot.messages import get_help_message
    
    help_message = get_help_message()
    return await send_message_func(bot_token, chat_id, help_message)


async def handle_unknown_command(chat_id: int, command: str, send_message_func, bot_token: str) -> bool:
    """
    Handle unknown commands.
    
    Args:
        chat_id: Telegram chat ID
        command: Unknown command name
        send_message_func: Function to send messages
        bot_token: Telegram bot token
        
    Returns:
        True if message sent successfully, False otherwise
    """
    from src.bot.messages import get_unknown_command_message
    
    error_message = get_unknown_command_message(command)
    return await send_message_func(bot_token, chat_id, error_message)

