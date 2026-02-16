"""
News summarizer service.

This module provides functionality for summarizing news using OpenAI API.
"""

import json
import logging
from typing import List, Optional
from datetime import date

from src.models.news import NewsItem, Summary
from src.config import config

logger = logging.getLogger(__name__)


class NewsSummarizer:
    """News summarizer using OpenAI API."""
    
    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize the summarizer.
        
        Args:
            api_key: OpenAI API key (defaults to config.OPENAI_API_KEY)
            model: OpenAI model name (defaults to config.OPENAI_MODEL)
        """
        self.api_key = api_key or config.OPENAI_API_KEY
        self.model = model or config.OPENAI_MODEL
    
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
        """
        Summarize a list of news items.
        
        Args:
            news_items: List of NewsItem objects to summarize
            target_date: Target date for the summary
            
        Returns:
            Summary object if successful, None otherwise
        """
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=self.api_key)
            
            news_texts = [item.text for item in news_items if item.text.strip()]
            if not news_texts:
                logger.warning("No text content found in news items")
                return None
            
            # Limit text length
            max_length = 8000
            combined_text = "\n\n".join(news_texts)
            if len(combined_text) > max_length:
                combined_text = combined_text[:max_length] + "..."
                news_texts = [combined_text]
            
            date_str = target_date.strftime("%Y-%m-%d")
            prompt = self._create_prompt(news_texts, date_str)
            
            logger.info(f"Calling OpenAI API to summarize {len(news_items)} news items...")
            
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
            
            logger.info("Successfully created news summary")
            return summary
            
        except ImportError:
            logger.error("OpenAI library not installed. Install with: pip install openai")
            return None
        except Exception as e:
            logger.error(f"Failed to summarize news: {e}")
            return None

