import logging
from typing import List, Optional

from .connection import get_cursor

logger = logging.getLogger(__name__)


def add_message_to_database(now_utc, message: str) -> None:
    """
    Add a message to the database.

    Args:
        now_utc: UTC timestamp for the message
        message: The message content to store
    """
    try:
        with get_cursor() as (_, cursor):
            logger.debug(f"Inserting message with timestamp: {now_utc}")
            cursor.execute(
                "INSERT INTO twits_summary (timestamp, message) VALUES (%s, %s)",
                (now_utc, message),
            )
            logger.info("Successfully inserted message into database")
    except Exception:
        logger.exception("Unexpected error while adding message to database")
        raise


def get_chat_ids() -> List[int]:
    """
    Get all chat IDs from the database.

    Returns:
        List of chat IDs as integers
    """
    try:
        with get_cursor() as (_, cursor):
            logger.debug("Selecting all chat IDs from chat_ids table")
            cursor.execute("SELECT * FROM chat_ids")
            rows = cursor.fetchall()

        chat_ids: List[int] = []
        for row in rows:
            if row:
                chat_id = int(row[0])
                chat_ids.append(chat_id)

        logger.info(f"Successfully retrieved {len(chat_ids)} chat IDs from database")
        return chat_ids
    except Exception:
        logger.exception("Unexpected error while fetching chat IDs")
        raise


def add_chat_id(chat_id: int) -> bool:
    """
    Add a chat ID to the database (subscribe).

    Args:
        chat_id: Telegram chat ID to add

    Returns:
        True if successfully added, False if already exists or error occurs
    """
    try:
        from psycopg2 import IntegrityError  # local import to avoid hard dependency

        with get_cursor() as (conn, cursor):
            try:
                cursor.execute(
                    "INSERT INTO chat_ids (chat_id) VALUES (%s)", (chat_id,)
                )
                logger.info(f"Successfully added chat_id {chat_id} to database")
                return True
            except IntegrityError:
                conn.rollback()
                logger.info(f"Chat ID {chat_id} already exists in database")
                return False
    except Exception:
        logger.exception(f"Error adding chat_id {chat_id}")
        return False


def remove_chat_id(chat_id: int) -> bool:
    """
    Remove a chat ID from the database (unsubscribe).

    Args:
        chat_id: Telegram chat ID to remove

    Returns:
        True if successfully removed, False if not found or error occurs
    """
    try:
        with get_cursor() as (_, cursor):
            cursor.execute("DELETE FROM chat_ids WHERE chat_id = %s", (chat_id,))
            if cursor.rowcount > 0:
                logger.info(f"Successfully removed chat_id {chat_id} from database")
                return True
            else:
                logger.info(f"Chat ID {chat_id} not found in database")
                return False
    except Exception:
        logger.exception(f"Error removing chat_id {chat_id}")
        return False


def get_latest_summary() -> Optional[str]:
    """
    Get the latest summary from the database.

    Returns:
        Latest summary message as string, or None if no summary found
    """
    try:
        with get_cursor() as (_, cursor):
            cursor.execute(
                "SELECT message FROM twits_summary ORDER BY timestamp DESC LIMIT 1"
            )
            row = cursor.fetchone()

        if row:
            logger.info("Successfully retrieved latest summary from database")
            return row[0]
        else:
            logger.info("No summaries found in database")
            return None
    except Exception:
        logger.exception("Error getting latest summary")
        return None


