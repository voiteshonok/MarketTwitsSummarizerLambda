import logging
import os
from contextlib import contextmanager
from typing import Iterator, Tuple

import psycopg2
from psycopg2.extensions import connection as PGConnection, cursor as PGCursor

logger = logging.getLogger(__name__)


def _get_db_params() -> Tuple[str, str, str, str]:
    """
    Read database connection parameters from environment variables.

    Returns:
        Tuple of (host, name, user, password)

    Raises:
        ValueError: If any required env var is missing.
    """
    db_host = os.getenv("DB_HOST")
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")

    if not all([db_host, db_name, db_user, db_password]):
        logger.error(
            "Missing database environment variables (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD)"
        )
        raise ValueError("Missing required database environment variables")

    return db_host, db_name, db_user, db_password


def get_connection() -> PGConnection:
    """
    Create a new database connection.

    Returns:
        psycopg2 connection instance
    """
    db_host, db_name, db_user, db_password = _get_db_params()
    logger.info(f"Connecting to database: {db_name} at {db_host}")
    conn = psycopg2.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password,
    )
    logger.info("Successfully connected to database")
    return conn


@contextmanager
def get_cursor() -> Iterator[Tuple[PGConnection, PGCursor]]:
    """
    Context manager that yields (connection, cursor) and handles commit/rollback.

    Usage:
        with get_cursor() as (conn, cur):
            cur.execute(...)
    """
    conn: PGConnection | None = None
    cur: PGCursor | None = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        yield conn, cur
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        logger.exception("Database operation failed")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


