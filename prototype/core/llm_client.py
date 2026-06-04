"""
llm_client.py — Клиент для Google Gemini API.
С retry, таймаутом и классификацией ошибок.
"""
import os
import time
import logging
from typing import Optional, Tuple

from .config import settings

logger = logging.getLogger("llm")

HAS_GEMINI = False
try:
    from google import genai as _genai
    HAS_GEMINI = True
except ImportError:
    pass


def generate_sql(prompt: str, temperature: float = 0.2, max_retries: int = 2) -> Tuple[Optional[str], Optional[str]]:
    """
    Отправляет промпт в Gemini и получает SQL-запрос.
    
    Returns:
        (sql, None) — успех
        (None, error_detail) — ошибка с описанием
    """
    if not HAS_GEMINI:
        return None, "Google Gemini SDK не установлен. Установите: pip install google-genai"

    if not settings.GEMINI_API_KEY:
        return None, "GEMINI_API_KEY не задан"

    model_name = settings.GEMINI_MODEL
    last_error: Optional[str] = None

    for attempt in range(max_retries + 1):
        try:
            client = _genai.Client(api_key=settings.GEMINI_API_KEY)
            logger.info(f"Gemini request: model={model_name}, attempt={attempt+1}")

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    "temperature": temperature,
                    "max_output_tokens": settings.GEMINI_MAX_TOKENS,
                },
            )
            raw_output = response.text.strip() if response.text else ""

            if not raw_output:
                last_error = "Модель вернула пустой ответ"
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                return None, last_error

            sql = _extract_sql(raw_output)
            if sql:
                return sql, None

            last_error = "Не удалось извлечь SQL из ответа"
            if attempt < max_retries:
                continue
            return None, last_error

        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str or "rate" in error_str:
                last_error = f"Превышен лимит запросов Gemini (429). Попробуйте позже."
                if attempt < max_retries:
                    time.sleep((attempt + 1) * 4)
                    continue
            elif "api key" in error_str or "unauthorized" in error_str or "401" in error_str:
                last_error = "Неверный API ключ Gemini. Проверьте GEMINI_API_KEY."
                break
            elif "not found" in error_str or "model" in error_str and "not" in error_str:
                last_error = f"Модель '{model_name}' не найдена или недоступна."
                break
            elif "timeout" in error_str or "deadline" in error_str:
                last_error = "Таймаут запроса к Gemini."
                if attempt < max_retries:
                    continue
            else:
                last_error = f"Ошибка Gemini: {e}"
                if attempt < max_retries:
                    time.sleep(2)
                    continue

    return None, last_error


def _extract_sql(text: str) -> str:
    """Извлекает SQL из ответа LLM, обрабатывая markdown-блоки."""
    text = text.strip()
    if "```sql" in text:
        start = text.index("```sql") + 6
        rest = text[start:]
        end = rest.index("```") if "```" in rest else len(rest)
        return rest[:end].strip()
    if "```" in text:
        start = text.index("```") + 3
        rest = text[start:]
        end = rest.index("```") if "```" in rest else len(rest)
        return rest[:end].strip()
    for line in text.split("\n"):
        s = line.strip().upper()
        if s.startswith("SELECT") or s.startswith("WITH"):
            return line.strip()
    return text
