#!/usr/bin/env python3
"""
Broadcast a custom message to every chat_id in the database (chat_ids table).

Uses the same stack as aws_lambda / daily_job:
  - DB: DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
  - Bot: TELEGRAM_BOT_TOKEN

Messages are sent with HTML parse mode (see telegram_client.send_message).

Examples:
  python broadcast_message.py "Hello from the bot"
  python broadcast_message.py -m "Line1\\nLine2"
  python broadcast_message.py --file notice.txt
  python broadcast_message.py --dry-run "test"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from src.config import config
from src.database.repository import get_chat_ids
from src.services.telegram_client import send_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


async def _broadcast(chat_ids: list[int], text: str, bot_token: str) -> tuple[int, int]:
    ok = 0
    for chat_id in chat_ids:
        if await send_message(bot_token, chat_id, text):
            ok += 1
    return ok, len(chat_ids)


def main() -> int:
    text = """
    !UPDATE!
    Значится решил я пофиксить глюки с саммаризацией и заодно посчитать метрики.
    Было две основных:
    • 𝐑𝐞𝐥𝐞𝐯𝐚𝐧𝐜𝐞: Does the summary capture the global market movers, or is it getting distracted by local noise and memes?
    • 𝐅𝐚𝐢𝐭𝐡𝐟𝐮𝐥𝐧𝐞𝐬𝐬: Is the bot staying "grounded"? I’m checking for those sneaky hallucinations—if it wasn't in the source tweets, it shouldn't be in the summary.
    
    Через LLM judge прошу оценить качество суммризации и дать скор.

    Итак на каждый день будет скор по каждой метрике. Можно смотреть на изменение среднего, но можно еще и стат тест посчить, наприер, тест Вилкоксона
    Сжег немного баксов на оценку и получил:
    • 𝐑𝐞𝐥𝐞𝐯𝐚𝐧𝐜𝐞: 𝟖.𝟏𝟔 ➔ 𝟖.𝟒 (статистически незначимо)
    • 𝐅𝐚𝐢𝐭𝐡𝐟𝐮𝐥𝐧𝐞𝐬𝐬: .𝟏𝟐𝟓 (статистически значимо)

    Вот так вот.
    """

    if not config.TELEGRAM_BOT_TOKEN:
        logging.error("TELEGRAM_BOT_TOKEN is not set.")
        return 1

    # try:
    #     chat_ids = get_chat_ids()
    # except Exception as e:
    #     logging.error("Failed to load chat IDs: %s", e)
    #     return 1
    chat_ids = [427988146]

    if not chat_ids:
        logging.warning("No chat_ids in database.")
        return 0

    logging.info("Recipients: %d chat_id(s)", len(chat_ids))

    sent, total = asyncio.run(_broadcast(chat_ids, text, config.TELEGRAM_BOT_TOKEN))
    logging.info("Done: sent %d / %d", sent, total)
    return 0 if sent == total else 2


if __name__ == "__main__":
    sys.exit(main())
