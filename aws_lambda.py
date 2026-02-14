#!/usr/bin/env python3
"""
Standalone Azure Functions script for daily news processing:
1. Dumps previous day's news from Telegram (in memory)
2. Generates a summary using OpenAI
3. Sends the summary to all users in the database via Telegram bot

This script is completely self-contained with no external dependencies on Redis or servers.
All functionality (dumper, summarizer) is included and runs in memory.

Usage in Azure Functions:
    This script can be used directly in Azure Functions with timer trigger.
    
Required Environment Variables:
    - TELEGRAM_API_ID: Telegram API ID
    - TELEGRAM_API_HASH: Telegram API hash
    - TELEGRAM_SESSION_STRING: Telegram session string
    - TELEGRAM_CHANNEL_USERNAME: Telegram channel username (default: MarketTwits)
    - TELEGRAM_BOT_TOKEN: Telegram bot token
    - OPENAI_API_KEY: OpenAI API key
    - OPENAI_MODEL: OpenAI model (optional, defaults to gpt-3.5-turbo)
    
Note: User IDs are stored in the database (chat_ids table), not in environment variables.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone, date
from typing import List, Optional, Any, Dict, Tuple
from dataclasses import dataclass, field
from dotenv import load_dotenv

from database import add_message_to_database, get_chat_ids, add_chat_id, remove_chat_id, get_latest_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
    force=True,
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Load environment variables
load_dotenv()

# ============================================================================
# Configuration
# ============================================================================

class Config:
    """Configuration class."""
    TELEGRAM_API_ID: str = os.getenv("TELEGRAM_API_ID", "")
    TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
    TELEGRAM_CHANNEL_USERNAME: str = os.getenv("TELEGRAM_CHANNEL_USERNAME", "MarketTwits")
    TELEGRAM_SESSION_STRING: str = os.getenv("TELEGRAM_SESSION_STRING", "")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    
    @classmethod
    def validate(cls) -> bool:
        """Validate configuration."""
        required = [
            "TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION_STRING",
            "TELEGRAM_BOT_TOKEN", "OPENAI_API_KEY"
        ]
        missing = [var for var in required if not getattr(cls, var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        return True

config = Config()

# ============================================================================
# Models
# ============================================================================

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
        """Format date object to string."""
        if isinstance(date_obj, datetime):
            return date_obj.strftime('%Y-%m-%d')
        elif hasattr(date_obj, 'strftime'):
            return date_obj.strftime('%Y-%m-%d')
        else:
            return str(date_obj)

# ============================================================================
# Telegram Dumper
# ============================================================================

class TelegramDumper:
    """Telegram channel dumper using Telethon."""
    
    def __init__(self):
        """Initialize the dumper."""
        self.api_id = config.TELEGRAM_API_ID
        self.api_hash = config.TELEGRAM_API_HASH
        self.channel_username = config.TELEGRAM_CHANNEL_USERNAME
        self.client = None
        self._is_connected = False
    
    async def connect(self) -> bool:
        """Connect to Telegram."""
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            
            self.client = TelegramClient(
                StringSession(config.TELEGRAM_SESSION_STRING),
                self.api_id,
                self.api_hash
            )
            await self.client.start()
            self._is_connected = True
            logging.info("Connected to Telegram")
            return True
        except ImportError:
            logging.error("Telethon not installed. Install with: pip install telethon")
            return False
        except Exception as e:
            logging.error(f"Failed to connect to Telegram: {e}")
            return False
    
    async def close(self):
        """Close Telegram connection."""
        if self.client and self._is_connected:
            await self.client.disconnect()
            self._is_connected = False
            logging.info("Disconnected from Telegram")
    
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
            
            logging.info(f"Fetched {len(messages)} messages from channel")
            return messages
        except Exception as e:
            logging.error(f"Failed to get channel messages: {e}")
            return []
    
    async def dump_news_for_date(self, target_date: datetime) -> List[NewsItem]:
        try:
            target_start = target_date.replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
            )
            target_end = target_date.replace(
                hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc
            )

            logging.info(f"Dumping news for {target_start.date()}")

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

            logging.info(f"Found {len(filtered_messages)} messages for {target_start.date()}")
            return filtered_messages

        except Exception:
            logging.exception("Failed to dump news")
            return []


# ============================================================================
# News Summarizer
# ============================================================================

class NewsSummarizer:
    """News summarizer using OpenAI API."""
    
    def __init__(self):
        """Initialize the summarizer."""
        self.api_key = config.OPENAI_API_KEY
        self.model = config.OPENAI_MODEL
    
    def _create_prompt(self, news_items: List[str], date: str) -> str:
        """Create summarization prompt."""
        all_news = "\n".join([f"• {item}" for item in news_items])
        
        return f"""
Сегодня {date}

Дай мне краткое резюме на основе твитов из новостного канала о финансовых рынках. Дай мне только основные новости о мировом рынке и политике, не используй российские новости, криптовалюты, мемы, кроме случаев, когда они важны.

ВОТ все твиты:
"
{all_news}
"

Используй формат как пронумерованный список кратких новостей, отсортированных от самых важных к менее важным.

Формат ответа в JSON:
{{
    "summary": "Краткий обзор самых важных рыночных событий",
    "key_topics": ["важная новость 1", "важная новость 2", ...]
}}

Фокусируйся на:
- Крупных движениях мировых рынков
- Важных политических событиях, влияющих на рынки
- Решениях центральных банков
- Экономических показателях
- Корпоративных доходах и крупных бизнес-новостях
- Геополитических событиях с рыночным воздействием

Исключи:
- Российские внутренние новости (если не глобально значимые)
- Новости о криптовалютах (если не имеют большого рыночного воздействия)
- Мемы и шутки (если не важны)
- Мелкие местные новости
- Спекуляции без содержания

Пиши на русском языке в формате пронумерованного списка.
"""
    
    async def summarize_news(self, news_items: List[NewsItem], target_date: date) -> Optional[Summary]:
        """Summarize a list of news items."""
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=self.api_key)
            
            news_texts = [item.text for item in news_items if item.text.strip()]
            if not news_texts:
                logging.warning("No text content found in news items")
                return None
            
            # Limit text length
            max_length = 8000
            combined_text = "\n\n".join(news_texts)
            if len(combined_text) > max_length:
                combined_text = combined_text[:max_length] + "..."
                news_texts = [combined_text]
            
            date_str = target_date.strftime("%Y-%m-%d")
            prompt = self._create_prompt(news_texts, date_str)
            
            logging.info(f"Calling OpenAI API to summarize {len(news_items)} news items...")
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional financial news analyst."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            try:
                summary_data = json.loads(content)
                summary_text = summary_data.get("summary", content)
                key_topics = summary_data.get("key_topics", [])
            except json.JSONDecodeError:
                summary_text = content
                key_topics = []
            
            summary = Summary(
                date=target_date,
                summary_text=summary_text,
                news_count=len(news_items),
                key_topics=key_topics
            )
            
            logging.info("Successfully created news summary")
            return summary
            
        except ImportError:
            logging.error("OpenAI library not installed. Install with: pip install openai")
            return None
        except Exception as e:
            logging.error(f"Failed to summarize news: {e}")
            return None

# ============================================================================
# Telegram Bot
# ============================================================================

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
        
        logging.info(f"Successfully sent message to user {user_id}")
        return True
        
    except TelegramError as e:
        logging.error(f"Telegram error sending message to user {user_id}: {e}")
        return False
    except Exception as e:
        logging.error(f"Error sending message to user {user_id}: {e}")
        return False

# ============================================================================
# Daily Job
# ============================================================================

def _validate_config() -> bool:
    """
    Validate configuration.
    
    Returns:
        True if validation succeeds, False otherwise.
    """
    try:
        config.validate()
        return True
    except ValueError as e:
        logging.error(f"Configuration validation failed: {e}")
        return False


def _calculate_target_date() -> Tuple[datetime, date]:
    """
    Calculate the target date (yesterday) for processing.
    
    Returns:
        Tuple of (yesterday datetime, yesterday date)
    """
    now_utc = datetime.now(timezone.utc)
    yesterday = now_utc - timedelta(days=1)
    yesterday_date = yesterday.date()
    
    logging.info(f"Processing news for {yesterday_date}")
    return yesterday, yesterday_date


async def _fetch_news_for_date(
    dumper: TelegramDumper, 
    target_datetime: datetime, 
    target_date: date
) -> Optional[List[NewsItem]]:
    """
    Fetch news items for the target date.
    
    Args:
        dumper: TelegramDumper instance
        target_datetime: Target datetime for fetching news
        target_date: Target date for logging
        
    Returns:
        List of news items if successful, None otherwise.
    """
    logging.info("Step 1: Dumping previous day's news...")
    news_items = await dumper.dump_news_for_date(target_datetime)
    
    if not news_items:
        logging.warning(f"No news found for {target_date}")
        return None
    
    logging.info(f"Found {len(news_items)} news items for {target_date}")
    return news_items


async def _create_summary_from_news(
    summarizer: NewsSummarizer,
    news_items: List[NewsItem],
    target_date: date
) -> Optional[Summary]:
    """
    Create a summary from news items.
    
    Args:
        summarizer: NewsSummarizer instance
        news_items: List of news items to summarize
        target_date: Target date for the summary
        
    Returns:
        Summary object if successful, None otherwise.
    """
    logging.info("Step 2: Generating summary...")
    summary = await summarizer.summarize_news(news_items, target_date)
    
    if not summary:
        logging.error("Failed to generate summary")
        return None
    
    return summary


def _format_summary_message(summary: Summary) -> str:
    """
    Format the summary into a message string for Telegram.
    
    Args:
        summary: Summary object to format
        
    Returns:
        Formatted message string
    """
    date_str = summary._format_date(summary.date)
    message = f"📈 <b>Daily Market Summary - {date_str}</b>\n\n"
    message += f"{summary.summary_text}\n\n"
    
    if summary.key_topics:
        key_topics = [f"{idx+1}. {topic}" for idx, topic in enumerate(summary.key_topics)]
        key_topics = '\n'.join(key_topics)
        message += f"🔑 <b>Key Topics:</b>\n{key_topics}\n\n"
    
    message += f"📊 Based on {summary.news_count} news items"
    return message


async def _send_summary_to_user(
    user_id: int,
    message: str
) -> bool:
    """
    Send summary message to a single user.
    
    Args:
        user_id: Telegram user ID to send message to
        message: Formatted message string
        
    Returns:
        True if message sent successfully, False otherwise.
    """
    success = await send_message(config.TELEGRAM_BOT_TOKEN, user_id, message)
    return success


async def _send_and_save_summary(
    chat_ids: List[int],
    message: str,
    timestamp: datetime
) -> bool:
    """
    Send summary message to all chat IDs and save to database.
    
    Args:
        chat_ids: List of Telegram chat IDs to send message to
        message: Formatted message string
        timestamp: UTC timestamp for database entry
        
    Returns:
        True if at least one message sent successfully, False otherwise.
    """
    logging.info("Step 3: Sending summary to users...")
    
    total_count = len(chat_ids)
    success_count = 0
    
    if total_count == 0:
        logging.warning("No chat IDs found to send messages to")
        return False
    
    # Send message to each chat ID
    for chat_id in chat_ids:
        try:
            success = await _send_summary_to_user(chat_id, message)
            if success:
                success_count += 1
                logging.debug(f"Successfully sent message to chat_id: {chat_id}")
            else:
                logging.warning(f"Failed to send message to chat_id: {chat_id}")
        except Exception as e:
            logging.error(f"Error sending message to chat_id {chat_id}: {e}")
    
    # Log success rate
    logging.info(f"Message sending completed: {success_count}/{total_count} successful")
    
    # Save to database only once if at least one message was sent successfully
    try:
        add_message_to_database(timestamp, message)
        logging.info("Successfully saved message to database")
    except Exception as e:
        logging.error(f"Failed to save message to database: {e}")
            # Don't fail the job if database save fails
    
    return success_count > 0


async def run_daily_job_async() -> bool:
    """
    Run the complete daily job asynchronously.
    
    Returns:
        True if job succeeded, False otherwise.
    """
    try:
        logging.info("Starting daily job...")
        
        # Step 1: Validate configuration
        if not _validate_config():
            return False
        
        # Step 2: Initialize components
        dumper = TelegramDumper()
        summarizer = NewsSummarizer()
        
        try:
            # Step 3: Calculate target date
            target_datetime, target_date = _calculate_target_date()
            
            # Step 4: Fetch news items
            news_items = await _fetch_news_for_date(dumper, target_datetime, target_date)
            if news_items is None:
                return False
            
            # Step 5: Create summary
            summary = await _create_summary_from_news(summarizer, news_items, target_date)
            if summary is None:
                return False
            
            # Step 6: Format message
            message = _format_summary_message(summary)
            
            # Step 7: Send message and save to database
            now_utc = datetime.now(timezone.utc)
            chat_ids = get_chat_ids()
            success = await _send_and_save_summary(chat_ids, message, now_utc)
            
            if success:
                logging.info("Daily job completed successfully!")
                return True
            else:
                logging.error("Failed to send message to any user")
                return False
                
        finally:
            await dumper.close()
            
    except Exception as e:
        logging.error(f"Error in daily job: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False


# ============================================================================
# Webhook Command Processing
# ============================================================================

def _is_api_gateway_event(event: Dict[str, Any]) -> bool:
    """
    Check if the event is from API Gateway.
    
    Args:
        event: Lambda event object
        
    Returns:
        True if event is from API Gateway, False otherwise
    """
    return (
        "httpMethod" in event or 
        "requestContext" in event or 
        ("path" in event and "body" in event)
    )


def _is_eventbridge_event(event: Dict[str, Any]) -> bool:
    """
    Check if the event is from EventBridge.
    
    Args:
        event: Lambda event object
        
    Returns:
        True if event is from EventBridge, False otherwise
    """
    return "source" in event and event.get("source") == "aws.events"


def parse_command(message_text: str) -> Tuple[Optional[str], List[str]]:
    """
    Parse command from message text.
    
    Args:
        message_text: Message text from Telegram
        
    Returns:
        Tuple of (command, args) or (None, []) if not a command
    """
    if not message_text or not message_text.startswith("/"):
        return None, []
    
    # Split command and arguments
    parts = message_text.split()
    command = parts[0][1:].lower()  # Remove '/' and convert to lowercase
    args = parts[1:] if len(parts) > 1 else []
    
    return command, args


async def handle_start_command(chat_id: int) -> bool:
    """Handle /start command - welcome message."""
    welcome_message = (
        "👋 <b>Welcome to MarketTwits Summarizer Bot!</b>\n\n"
        "I provide daily market summaries and financial news updates as a silent message at 3:00 AM UTC.\n\n"
        "Use /help to see all available commands."
    )
    return await send_message(config.TELEGRAM_BOT_TOKEN, chat_id, welcome_message)


async def handle_subscribe_command(chat_id: int) -> bool:
    """Handle /subscribe command - add user to subscription list."""
    try:
        success = add_chat_id(chat_id)
        if success:
            message = "✅ <b>Successfully subscribed!</b>\n\nYou will now receive daily market summaries."
        else:
            message = "ℹ️ You are already subscribed to daily market summaries."
        return await send_message(config.TELEGRAM_BOT_TOKEN, chat_id, message)
    except Exception as e:
        logging.error(f"Error in subscribe command: {e}")
        error_message = "❌ Error subscribing. Please try again later."
        return await send_message(config.TELEGRAM_BOT_TOKEN, chat_id, error_message)


async def handle_unsubscribe_command(chat_id: int) -> bool:
    """Handle /unsubscribe command - remove user from subscription list."""
    try:
        success = remove_chat_id(chat_id)
        if success:
            message = "✅ <b>Successfully unsubscribed!</b>\n\nYou will no longer receive daily market summaries."
        else:
            message = "ℹ️ You are not currently subscribed."
        return await send_message(config.TELEGRAM_BOT_TOKEN, chat_id, message)
    except Exception as e:
        logging.error(f"Error in unsubscribe command: {e}")
        error_message = "❌ Error unsubscribing. Please try again later."
        return await send_message(config.TELEGRAM_BOT_TOKEN, chat_id, error_message)


async def handle_get_latest_command(chat_id: int) -> bool:
    """Handle /get_latest command - get the latest market summary."""
    try:
        summary = get_latest_summary()
        if summary:
            return await send_message(config.TELEGRAM_BOT_TOKEN, chat_id, summary)
        else:
            message = (
                "📭 <b>No summary available</b>\n\n"
                "No market summaries have been generated yet. "
                "Check back later or subscribe to receive daily summaries automatically."
            )
            return await send_message(config.TELEGRAM_BOT_TOKEN, chat_id, message)
    except Exception as e:
        logging.error(f"Error in get_latest command: {e}")
        error_message = "❌ Error retrieving latest summary. Please try again later."
        return await send_message(config.TELEGRAM_BOT_TOKEN, chat_id, error_message)


async def handle_help_command(chat_id: int) -> bool:
    """Handle /help command - show available commands."""
    help_message = (
        "📚 <b>Available Commands:</b>\n\n"
        "/start - Стартовать бота\n"
        "/subscribe - Подписаться на получение саммари\n"
        "/unsubscribe - Отписаться от получения саммари\n"
        "/get_latest - Получить последнее саммари\n"
        "/help - Команды бота"
    )
    return await send_message(config.TELEGRAM_BOT_TOKEN, chat_id, help_message)


async def handle_unknown_command(chat_id: int, command: str) -> bool:
    """Handle unknown commands."""
    error_message = (
        f"❓ Unknown command: <code>{command}</code>\n\n"
        "Use /help to see all available commands."
    )
    return await send_message(config.TELEGRAM_BOT_TOKEN, chat_id, error_message)


async def process_command(chat_id: int, message_text: str) -> bool:
    """
    Process bot commands and route to appropriate handler.
    
    Args:
        chat_id: Telegram chat ID
        message_text: Message text from user
        
    Returns:
        True if command processed successfully, False otherwise
    """
    command, args = parse_command(message_text)
    
    if not command:
        # Not a command, ignore non-command messages
        logging.info(f"Received non-command message from chat_id {chat_id}, ignoring")
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
            return await handler(chat_id)
        except Exception as e:
            logging.error(f"Error processing command {command}: {e}")
            return await send_message(
                config.TELEGRAM_BOT_TOKEN,
                chat_id,
                "❌ Error processing command. Please try again."
            )
    else:
        return await handle_unknown_command(chat_id, command)


def handle_webhook_update(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle webhook update from API Gateway.
    
    Args:
        event: API Gateway event object
        
    Returns:
        API Gateway response dictionary
    """
    try:
        # Parse the event body (API Gateway sends body as JSON string at top level)
        # Try standard location first, then fallback to requestContext.body for custom setups
        body = event.get("body") or event.get("requestContext", {}).get("body", "{}")
        if isinstance(body, str):
            update = json.loads(body)
        else:
            update = body
        
        # Validate update structure
        if "message" not in update:
            logging.warning("Webhook update does not contain message field")
            return {
                "statusCode": 200,  # Return 200 to acknowledge webhook
                "body": json.dumps({"ok": True, "message": "No message in update"})
            }
        
        message = update["message"]
        
        # Extract chat_id and message text
        if "chat" not in message or "id" not in message["chat"]:
            logging.warning("Message does not contain chat.id")
            return {
                "statusCode": 200,
                "body": json.dumps({"ok": True, "message": "No chat ID in message"})
            }
        
        chat_id = message["chat"]["id"]
        message_text = message.get("text", "")
        
        if not message_text:
            logging.warning(f"No text in message from chat_id {chat_id}")
            return {
                "statusCode": 200,
                "body": json.dumps({"ok": True, "message": "No text in message"})
            }
        
        # Process command
        logging.info(f"Processing webhook update: chat_id={chat_id}, text={message_text}")
        success = asyncio.run(process_command(chat_id, message_text))
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "ok": success,
                "message": "Command processed" if success else "Failed to process command"
            })
        }
        
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse webhook body: {e}")
        return {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({"ok": False, "error": "Invalid JSON in request body"})
        }
    except Exception as e:
        logging.error(f"Error handling webhook update: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({"ok": False, "error": str(e)})
        }


# ============================================================================
# Standalone Entry Point
# ============================================================================

def lambda_handler(event, context):
    try:
        # Detect event source and route accordingly
        if _is_api_gateway_event(event):
            logging.info("Detected API Gateway event - processing webhook")
            return handle_webhook_update(event)
        elif _is_eventbridge_event(event):
            logging.info("Detected EventBridge event - running daily job")
            success = asyncio.run(run_daily_job_async())
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "success": success
                })
            }
        else:
            # Default to daily job for backward compatibility
            logging.info("Unknown event type - defaulting to daily job")
            success = asyncio.run(run_daily_job_async())
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "success": success
                })
            }
    except Exception as e:
        import traceback
        logging.error(f"Error in lambda_handler: {e}")
        logging.error(traceback.format_exc())
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "error": str(e),
                "trace": traceback.format_exc()
            })
        }

