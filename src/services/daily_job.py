"""
Daily job orchestration service.

This module orchestrates the daily news processing workflow:
1. Fetch news from Telegram channel
2. Generate summary using OpenAI
3. Send summary to subscribed users
4. Save summary to database
"""

import logging
import traceback
from datetime import datetime, timedelta, timezone, date
from typing import List, Optional, Tuple

from src.database.repository import add_message_to_database, get_chat_ids
from src.services.telegram_client import send_message
from src.services.news_dumper import TelegramDumper
from src.services.summarizer import NewsSummarizer

from src.models.news import NewsItem, Summary
from src.config import config

logger = logging.getLogger(__name__)


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
        logger.error(f"Configuration validation failed: {e}")
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
    
    logger.info(f"Processing news for {yesterday_date}")
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
    logger.info("Step 1: Dumping previous day's news...")
    news_items = await dumper.dump_news_for_date(target_datetime)
    
    if not news_items:
        logger.warning(f"No news found for {target_date}")
        return None
    
    logger.info(f"Found {len(news_items)} news items for {target_date}")
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
    logger.info("Step 2: Generating summary...")
    summary = await summarizer.summarize_news(news_items, target_date)
    
    if not summary:
        logger.error("Failed to generate summary")
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
    message: str,
    bot_token: str
) -> bool:
    """
    Send summary message to a single user.
    
    Args:
        user_id: Telegram user ID to send message to
        message: Formatted message string
        bot_token: Telegram bot token
        
    Returns:
        True if message sent successfully, False otherwise.
    """
    success = await send_message(bot_token, user_id, message)
    return success


async def _send_and_save_summary(
    chat_ids: List[int],
    message: str,
    timestamp: datetime,
    bot_token: str
) -> bool:
    """
    Send summary message to all chat IDs and save to database.
    
    Args:
        chat_ids: List of Telegram chat IDs to send message to
        message: Formatted message string
        timestamp: UTC timestamp for database entry
        bot_token: Telegram bot token
        
    Returns:
        True if at least one message sent successfully, False otherwise.
    """
    try:
        add_message_to_database(timestamp, message)
        logger.info("Successfully saved message to database")
    except Exception as e:
        logger.error(f"Failed to save message to database: {e}")
        # Don't fail the job if database save fails

    logger.info("Step 3: Sending summary to users...")
    
    total_count = len(chat_ids)
    success_count = 0
    
    if total_count == 0:
        logger.warning("No chat IDs found to send messages to")
        return False
    
    # Send message to each chat ID
    for chat_id in chat_ids:
        try:
            success = await _send_summary_to_user(chat_id, message, bot_token)
            if success:
                success_count += 1
                logger.debug(f"Successfully sent message to chat_id: {chat_id}")
            else:
                logger.warning(f"Failed to send message to chat_id: {chat_id}")
        except Exception as e:
            logger.error(f"Error sending message to chat_id {chat_id}: {e}")
    
    # Log success rate
    logger.info(f"Message sending completed: {success_count}/{total_count} successful")
    
    return success_count > 0


async def run_daily_job_async() -> bool:
    """
    Run the complete daily job asynchronously.
    
    Returns:
        True if job succeeded, False otherwise.
    """
    try:
        logger.info("Starting daily job...")
        
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
            success = await _send_and_save_summary(chat_ids, message, now_utc, config.TELEGRAM_BOT_TOKEN)
            
            if success:
                logger.info("Daily job completed successfully!")
                return True
            else:
                logger.error("Failed to send message to any user")
                return False
                
        finally:
            await dumper.close()
            
    except Exception as e:
        logger.error(f"Error in daily job: {e}")
        logger.error(traceback.format_exc())
        return False

