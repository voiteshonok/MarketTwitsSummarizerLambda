"""
LLM-based summary quality metrics (aligned with research/Metrics.ipynb).

Iterates dates present in both grouped_news and summaries, builds news_texts and
text_summary, calls relevance / faithfulness / redundancy judges, returns scores
and writes full reasoning to a JSON file.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from src.models.news import NewsItem, Summary

logger = logging.getLogger(__name__)

DateKey = Union[date, datetime]


def _normalize_date_key(d: DateKey) -> date:
    if isinstance(d, datetime):
        return d.date()
    return d


def _date_sort_key(d: DateKey) -> date:
    return _normalize_date_key(d)


def _format_date_for_output(d: DateKey) -> str:
    return _normalize_date_key(d).isoformat()


def build_news_texts(
    news_items: Sequence[NewsItem],
    max_combined_chars: int = 8000,
) -> List[str]:
    """Match summarizer.py: list of texts, or one truncated blob if too long."""
    texts = [item.text for item in news_items if item.text and item.text.strip()]
    if not texts:
        return []
    combined = "\n\n".join(texts)
    if len(combined) > max_combined_chars:
        return [combined[:max_combined_chars] + "..."]
    return texts


def build_text_summary(summary: Summary) -> str:
    return "\n".join(summary.key_topics or [])


def _prompt_relevance(original_news: Any, summary_text: str) -> str:
    return f"""
    Дан полный список новостей: {original_news}
    Дан итоговый топ-10: {summary_text}

    Оцени по шкале от 1 до 10, насколько выбранные 10 новостей являются
    самыми важными событиями дня. Игнорируй стиль письма, оценивай только выбор тем.
    Выдай ответ в формате JSON: {{"score": float, "reasoning": str}}
    """


def _prompt_faithfulness(original_news: Any, summary_text: str) -> str:
    return f"""
    Ты — фактчекер. Сравни итоговый ТОП-10 с исходными новостями.
    Твоя цель: найти любые искажения, ошибки в именах, цифрах или выдуманные факты (галлюцинации).

    Оценка 10: Всё строго соответствует исходнику.
    Оценка 0: В ТОП-10 есть факты, которых не было в источнике.

    ИСХОДНЫЕ ДАННЫЕ: {original_news}
    ТОП-10 ДЛЯ ПРОВЕРКИ: {summary_text}

    Верни ответ строго в формате JSON: {{"score": float, "reasoning": "список найденных неточностей или подтверждение их отсутствия"}}
    """


def _prompt_redundancy(summary_text: str) -> str:
    return f"""
    Проанализируй список из 10 новостей на предмет смысловых дублей.
    Если две или более новости описывают одно и то же событие — снижай балл.

    Оценка 10: Все новости уникальны.
    Оценка 5: Есть 1-2 дублирующих темы.
    Оценка 0: Список состоит из повторов.

    ТОП-10 ДЛЯ АНАЛИЗА: {summary_text}

    Верни ответ строго в формате JSON: {{"score": float, "reasoning": "какие новости дублируют друг друга"}}
    """


async def _call_judge_llm(
    client: Any,
    model: str,
    prompt: str,
) -> Dict[str, Any]:
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = response.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception as e:
        logger.exception("Judge LLM call failed")
        return {"score": 0.0, "reasoning": f"Error: {e!s}"}


@dataclass
class DayMetrics:
    date: str
    relevance_score: float
    faithfulness_score: float
    redundancy_score: float
    relevance_reasoning: str = ""
    faithfulness_reasoning: str = ""
    redundancy_reasoning: str = ""
    skipped: bool = False
    skip_reason: str = ""

    def scores_triple(self) -> Tuple[float, float, float]:
        return (self.relevance_score, self.faithfulness_score, self.redundancy_score)


def _parse_score_reasoning(d: Dict[str, Any]) -> Tuple[float, str]:
    score = d.get("score")
    try:
        score_f = float(score) if score is not None else 0.0
    except (TypeError, ValueError):
        score_f = 0.0
    reasoning = d.get("reasoning")
    return score_f, str(reasoning) if reasoning is not None else ""


async def metrics_for_one_date(
    news_texts: List[str],
    text_summary: str,
    client: Any,
    judge_model: str,
) -> Tuple[Tuple[float, float, float], Dict[str, str]]:
    """Returns (relevance, faithfulness, redundancy) and reasoning strings."""
    rel_raw = await _call_judge_llm(client, judge_model, _prompt_relevance(news_texts, text_summary))
    faith_raw = await _call_judge_llm(
        client, judge_model, _prompt_faithfulness(news_texts, text_summary)
    )
    #red_raw = await _call_judge_llm(client, judge_model, _prompt_redundancy(text_summary))

    r_s, r_r = _parse_score_reasoning(rel_raw)
    f_s, f_r = _parse_score_reasoning(faith_raw)
    d_s, d_r = 0, "" #_parse_score_reasoning(red_raw)
    return (r_s, f_s, d_s), {
        "relevance": r_r,
        "faithfulness": f_r,
        "redundancy": d_r,
    }


async def evaluate_grouped_summaries(
    grouped_news: Mapping[DateKey, Sequence[NewsItem]],
    summaries: Mapping[DateKey, Summary],
    *,
    api_key: Optional[str] = None,
    judge_model: str = "gpt-4o",
    max_combined_chars: int = 8000,
    reasoning_log_path: Optional[Union[str, Path]] = None,
) -> Tuple[List[float], List[DayMetrics]]:
    """
    For each date in the intersection of keys (sorted), compute three metrics.

    Returns:
        flat_scores: [rel, faith, red, rel, faith, red, ...] per processed date
        details: one DayMetrics per date (including skipped days with skip_reason)
    """
    from openai import AsyncOpenAI

    from src.config import config

    key = api_key or config.OPENAI_API_KEY
    client = AsyncOpenAI(api_key=key)

    dates = sorted(
        set(_normalize_date_key(d) for d in grouped_news.keys())
        & set(_normalize_date_key(d) for d in summaries.keys())
    )

    if reasoning_log_path is None:
        reasoning_log_path = Path("research") / "metrics_reasoning.json"
    log_path = Path(reasoning_log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    flat_scores: List[float] = []
    details: List[DayMetrics] = []
    log_payload: Dict[str, Any] = {"judge_model": judge_model, "dates": []}

    for d in dates:
        # Resolve items/summary for either date or datetime keys
        news_items = None
        for k, v in grouped_news.items():
            if _normalize_date_key(k) == d:
                news_items = v
                break
        summary_obj = None
        for k, v in summaries.items():
            if _normalize_date_key(k) == d:
                summary_obj = v
                break

        date_str = d.isoformat()
        if news_items is None or summary_obj is None:
            dm = DayMetrics(
                date=date_str,
                relevance_score=0.0,
                faithfulness_score=0.0,
                redundancy_score=0.0,
                skipped=True,
                skip_reason="missing news or summary",
            )
            details.append(dm)
            log_payload["dates"].append({"date": date_str, "skipped": True, "reason": dm.skip_reason})
            continue

        news_texts = build_news_texts(news_items, max_combined_chars=max_combined_chars)
        text_summary = build_text_summary(summary_obj)
        if not news_texts or not text_summary.strip():
            dm = DayMetrics(
                date=date_str,
                relevance_score=0.0,
                faithfulness_score=0.0,
                redundancy_score=0.0,
                skipped=True,
                skip_reason="empty news_texts or summary",
            )
            details.append(dm)
            log_payload["dates"].append({"date": date_str, "skipped": True, "reason": dm.skip_reason})
            continue

        (r_s, f_s, d_s), reasoning = await metrics_for_one_date(
            news_texts, text_summary, client, judge_model
        )
        flat_scores.extend([r_s, f_s, d_s])
        dm = DayMetrics(
            date=date_str,
            relevance_score=r_s,
            faithfulness_score=f_s,
            redundancy_score=d_s,
            relevance_reasoning=reasoning["relevance"],
            faithfulness_reasoning=reasoning["faithfulness"],
            redundancy_reasoning=reasoning["redundancy"],
        )
        details.append(dm)
        log_payload["dates"].append(
            {
                "date": date_str,
                "news_texts": news_texts,
                "text_summary": text_summary,
                "scores": {"relevance": r_s, "faithfulness": f_s, "redundancy": d_s},
                "reasoning": reasoning,
            }
        )

    log_path.write_text(json.dumps(log_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote metrics reasoning to %s", log_path.resolve())
    return flat_scores, details


def scores_matrix(details: Iterable[DayMetrics]) -> List[List[float]]:
    """Per-day [relevance, faithfulness, redundancy] for non-skipped rows."""
    return [list(m.scores_triple()) for m in details if not m.skipped]
