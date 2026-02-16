"""
Telegram news dumper service.

This module provides functionality for fetching messages from Telegram channels.
"""

import logging
from typing import List, Optional
from datetime import datetime, timezone

from src.models.news import NewsItem
from src.config import config

logger = logging.getLogger(__name__)


class TelegramDumper:
    """Telegram channel dumper using Telethon."""
    
    def __init__(self, api_id: str = None, api_hash: str = None, channel_username: str = None, session_string: str = None):
        """
        Initialize the dumper.
        
        Args:
            api_id: Telegram API ID (defaults to config.TELEGRAM_API_ID)
            api_hash: Telegram API hash (defaults to config.TELEGRAM_API_HASH)
            channel_username: Channel username (defaults to config.TELEGRAM_CHANNEL_USERNAME)
            session_string: Session string (defaults to config.TELEGRAM_SESSION_STRING)
        """
        self.api_id = api_id or config.TELEGRAM_API_ID
        self.api_hash = api_hash or config.TELEGRAM_API_HASH
        self.channel_username = channel_username or config.TELEGRAM_CHANNEL_USERNAME
        self.session_string = session_string or config.TELEGRAM_SESSION_STRING
        self.client = None
        self._is_connected = False
    
    async def connect(self) -> bool:
        """Connect to Telegram."""
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            
            self.client = TelegramClient(
                StringSession(self.session_string),
                self.api_id,
                self.api_hash
            )
            await self.client.start()
            self._is_connected = True
            logger.info("Connected to Telegram")
            return True
        except ImportError:
            logger.error("Telethon not installed. Install with: pip install telethon")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Telegram: {e}")
            return False
    
    async def close(self):
        """Close Telegram connection."""
        if self.client and self._is_connected:
            await self.client.disconnect()
            self._is_connected = False
            logger.info("Disconnected from Telegram")
    
    async def get_channel_messages(
        self, 
        from_date: Optional[datetime] = None, 
        limit: int = 1000
    ) -> List[NewsItem]:
        """Get messages from the Telegram channel."""
        if not self._is_connected:
            if not await self.connect():
                return []
        
        try:
            channel = await self.client.get_entity(self.channel_username)
            messages = []
            
            async for message in self.client.iter_messages(
                channel,
                offset_date=from_date,
                limit=limit
            ):
                if message.text:
                    news_item = NewsItem(
                        message_id=message.id,
                        text=message.text,
                        date=message.date,
                        views=getattr(message, 'views', None),
                        forwards=getattr(message, 'forwards', None)
                    )
                    messages.append(news_item)
            
            logger.info(f"Fetched {len(messages)} messages from channel")
            return messages
        except Exception as e:
            logger.error(f"Failed to get channel messages: {e}")
            return []
    
    async def dump_news_for_date(self, target_date: datetime) -> List[NewsItem]:
        """
        Dump news messages for a specific date.
        
        Args:
            target_date: Target date to fetch messages for
            
        Returns:
            List of NewsItem objects for the target date
        """
        try:
            target_start = target_date.replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
            )
            target_end = target_date.replace(
                hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc
            )

            logger.info(f"Dumping news for {target_start.date()}")

            if not self._is_connected:
                if not await self.connect():
                    return []

            channel = await self.client.get_entity(self.channel_username)

            filtered_messages = []

            async for message in self.client.iter_messages(
                channel,
                offset_date=target_end,
                limit=2000
            ):
                if not message.date:
                    continue

                msg_date = message.date.astimezone(timezone.utc)

                if msg_date < target_start:
                    break  # ⬅️ VERY IMPORTANT

                if message.text:
                    filtered_messages.append(
                        NewsItem(
                            message_id=message.id,
                            text=message.text,
                            date=msg_date,
                            views=getattr(message, "views", None),
                            forwards=getattr(message, "forwards", None),
                        )
                    )

            logger.info(f"Found {len(filtered_messages)} messages for {target_start.date()}")
            return filtered_messages

        except Exception:
            logger.exception("Failed to dump news")
            return []

