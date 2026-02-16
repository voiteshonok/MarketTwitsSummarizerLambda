"""
Configuration module.

This module provides configuration management for the application.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.config.settings import Config

# Create a global config instance
config = Config()

__all__ = ["Config", "config"]

