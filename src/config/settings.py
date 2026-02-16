"""
Application settings and configuration.

This module defines the configuration class for managing environment variables.
"""

import os


class Config:
    """Configuration class for managing environment variables."""
    
    TELEGRAM_API_ID: str = os.getenv("TELEGRAM_API_ID", "")
    TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
    TELEGRAM_CHANNEL_USERNAME: str = os.getenv("TELEGRAM_CHANNEL_USERNAME", "MarketTwits")
    TELEGRAM_SESSION_STRING: str = os.getenv("TELEGRAM_SESSION_STRING", "")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    
    @classmethod
    def validate(cls) -> bool:
        """
        Validate configuration.
        
        Checks that all required environment variables are set.
        
        Returns:
            True if validation succeeds
            
        Raises:
            ValueError: If any required environment variables are missing
        """
        required = [
            "TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION_STRING",
            "TELEGRAM_BOT_TOKEN", "OPENAI_API_KEY"
        ]
        missing = [var for var in required if not getattr(cls, var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        return True

