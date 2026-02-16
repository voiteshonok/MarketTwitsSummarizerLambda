#!/usr/bin/env python3
"""
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

from src.database.repository import (
    add_message_to_database,
    get_chat_ids,
)
from src.bot.router import process_command
from src.services.telegram_client import send_message
from src.services.daily_job import run_daily_job_async

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
    force=True,
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ============================================================================
# Configuration
# ============================================================================

from src.config import config

# ============================================================================
# Models
# ============================================================================

from src.models.news import NewsItem, NewsBatch, Summary



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
        success = asyncio.run(process_command(chat_id, message_text, send_message, config.TELEGRAM_BOT_TOKEN))
        
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

