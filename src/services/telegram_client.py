"""
Telegram bot client service.

This module provides functionality for sending messages via Telegram bot API.
"""

import logging

logger = logging.getLogger(__name__)


async def send_message(bot_token: str, user_id: int, message: str) -> bool:
    """
    Send a message to a user via Telegram bot.
    
    Args:
        bot_token: Telegram bot token
        user_id: Telegram user ID to send message to
        message: Message text to send
        
    Returns:
        True if message sent successfully, False otherwise
    """
    try:
        from telegram import Bot
        from telegram.error import TelegramError
        
        bot = Bot(token=bot_token)
        
        # Send message to user
        await bot.send_message(
            chat_id=user_id,
            text=message,
            disable_notification=True,
            parse_mode='HTML'
        )
        
        logger.info(f"Successfully sent message to user {user_id}")
        return True
        
    except Exception as e:
        if hasattr(e, '__class__') and 'TelegramError' in str(e.__class__):
            logger.error(f"Telegram error sending message to user {user_id}: {e}")
        else:
            logger.error(f"Error sending message to user {user_id}: {e}")
        return False

