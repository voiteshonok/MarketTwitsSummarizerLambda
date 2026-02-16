"""
Message templates for bot responses.

This module contains all message templates used by the bot commands.
"""


def get_welcome_message() -> str:
    """Get welcome message for /start command."""
    return (
        "👋 <b>Welcome to MarketTwits Summarizer Bot!</b>\n\n"
        "I provide daily market summaries and financial news updates as a silent message at 3:00 AM UTC.\n\n"
        "Use /help to see all available commands."
    )


def get_help_message() -> str:
    """Get help message for /help command."""
    return (
        "📚 <b>Available Commands:</b>\n\n"
        "/start - Стартовать бота\n"
        "/subscribe - Подписаться на получение саммари\n"
        "/unsubscribe - Отписаться от получения саммари\n"
        "/get_latest - Получить последнее саммари\n"
        "/help - Команды бота"
    )


def get_subscribe_success_message() -> str:
    """Get message for successful subscription."""
    return "✅ <b>Successfully subscribed!</b>\n\nYou will now receive daily market summaries."


def get_subscribe_already_message() -> str:
    """Get message when user is already subscribed."""
    return "ℹ️ You are already subscribed to daily market summaries."


def get_unsubscribe_success_message() -> str:
    """Get message for successful unsubscription."""
    return "✅ <b>Successfully unsubscribed!</b>\n\nYou will no longer receive daily market summaries."


def get_unsubscribe_not_subscribed_message() -> str:
    """Get message when user is not subscribed."""
    return "ℹ️ You are not currently subscribed."


def get_no_summary_message() -> str:
    """Get message when no summary is available."""
    return (
        "📭 <b>No summary available</b>\n\n"
        "No market summaries have been generated yet. "
        "Check back later or subscribe to receive daily summaries automatically."
    )


def get_unknown_command_message(command: str) -> str:
    """Get message for unknown command."""
    return (
        f"❓ Unknown command: <code>{command}</code>\n\n"
        "Use /help to see all available commands."
    )


def get_error_message() -> str:
    """Get generic error message."""
    return "❌ Error processing command. Please try again."


def get_subscribe_error_message() -> str:
    """Get error message for subscribe command."""
    return "❌ Error subscribing. Please try again later."


def get_unsubscribe_error_message() -> str:
    """Get error message for unsubscribe command."""
    return "❌ Error unsubscribing. Please try again later."


def get_latest_error_message() -> str:
    """Get error message for get_latest command."""
    return "❌ Error retrieving latest summary. Please try again later."

