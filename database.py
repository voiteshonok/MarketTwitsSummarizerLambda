import os
import logging
from typing import List
import psycopg2

logger = logging.getLogger(__name__)


def add_message_to_database(now_utc, message: str) -> None:
    """
    Add a message to the database.
    
    Args:
        now_utc: UTC timestamp for the message
        message: The message content to store
    """
    conn = None
    cursor = None
    try:
        # Get database connection parameters
        db_host = os.getenv("DB_HOST")
        db_name = os.getenv("DB_NAME")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        
        if not all([db_host, db_name, db_user, db_password]):
            logger.error("Missing database environment variables (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD)")
            raise ValueError("Missing required database environment variables")
        
        logger.info(f"Connecting to database: {db_name} at {db_host}")
        
        # Create a new database connection to postgres
        conn = psycopg2.connect(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password
        )
        logger.info("Successfully connected to database")
        
        cursor = conn.cursor()
        logger.debug(f"Inserting message with timestamp: {now_utc}")
        cursor.execute("INSERT INTO twits_summary (timestamp, message) VALUES (%s, %s)", (now_utc, message))
        conn.commit()
        logger.info("Successfully inserted message into database")
        
    except psycopg2.Error as e:
        logger.error(f"Database error occurred: {e}")
        if conn:
            conn.rollback()
            logger.debug("Transaction rolled back due to error")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error while adding message to database: {e}")
        if conn:
            conn.rollback()
            logger.debug("Transaction rolled back due to error")
        raise
    finally:
        if cursor:
            cursor.close()
            logger.debug("Database cursor closed")
        if conn:
            conn.close()
            logger.debug("Database connection closed")


def get_chat_ids() -> List[int]:
    """
    Get all chat IDs from the database.
    
    Returns:
        List of chat IDs as integers
        
    Raises:
        ValueError: If database environment variables are missing
        psycopg2.Error: If database error occurs
    """
    conn = None
    cursor = None
    try:
        # Get database connection parameters
        db_host = os.getenv("DB_HOST")
        db_name = os.getenv("DB_NAME")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        
        if not all([db_host, db_name, db_user, db_password]):
            logger.error("Missing database environment variables (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD)")
            raise ValueError("Missing required database environment variables")
        
        logger.info(f"Connecting to database: {db_name} at {db_host}")
        
        # Create a new database connection to postgres
        conn = psycopg2.connect(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password
        )
        logger.info("Successfully connected to database")
        
        cursor = conn.cursor()
        logger.debug("Selecting all chat IDs from chat_ids table")
        cursor.execute("SELECT * FROM chat_ids")
        
        rows = cursor.fetchall()
        
        # Extract chat IDs from rows
        # Assuming the first column contains the chat ID
        chat_ids = []
        for row in rows:
            if row:
                # Get the first column value and convert to int
                chat_id = int(row[0])
                chat_ids.append(chat_id)
        
        logger.info(f"Successfully retrieved {len(chat_ids)} chat IDs from database")
        return chat_ids
        
    except psycopg2.Error as e:
        logger.error(f"Database error occurred while fetching chat IDs: {e}")
        raise
    except ValueError as e:
        logger.error(f"Value error while fetching chat IDs: {e}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error while fetching chat IDs: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
            logger.debug("Database cursor closed")
        if conn:
            conn.close()
            logger.debug("Database connection closed")