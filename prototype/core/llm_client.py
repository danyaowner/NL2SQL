"""
llm_client.py — Клиент для Google Gemini API.
С rate limiter, экспоненциальным backoff, таймаутом и классификацией ошибок.
"""
import os
import time
import random
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


# ─── Rate Limiter (Token Bucket) ──────────────────────────────────────
# Gemini free tier: ~60 RPM. Берем с запасом — 30 запросов в минуту.

class RateLimiter:
    """Token bucket rate limiter — предотвращает 429 до того, как он случился."""

    def __init__(self, max_rpm: int = 30):
        self.max_tokens = max_rpm
        self.tokens = max_rpm
        self.last_refill = time.monotonic()
        self.refill_interval = 60.0 / max_rpm  # секунд на 1 токен

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed / self.refill_interval)
        self.last_refill = now

    def acquire(self, block: bool = True) -> bool:
        """Захватить токен. Если block=True — ждать, пока токен не появится."""
        self._refill()
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        if not block:
            return False
        # Ждём, пока появится токен
        wait = self.refill_interval * (1 - self.tokens)
        logger.info(f"Rate limiter: waiting {wait:.1f}s for token...")
        time.sleep(wait)
        self._refill()
        self.tokens -= 1
        return True

    def wait_if_needed(self):
        """Захватить токен (с ожиданием, если нужно)."""
        self.acquire(block=True)


# Глобальный rate limiter (один на весь процесс)
_rate_limiter = RateLimiter(max_rpm=30)


def _exponential_backoff(attempt: int, base_delay: float = 5.0, max_delay: float = 120.0) -> float:
    """Экспоненциальная задержка с jitter: 5, 10, 20, 40, 80, 120, 120..."""
    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = random.uniform(0.5, 1.5)
    return delay * jitter


def generate_sql(prompt: str, temperature: float = 0.2, max_retries: int = 6) -> Tuple[Optional[str], Optional[str]]:
    """
    Отправляет промпт в Gemini и получает SQL-запрос.

    - Rate limiter: не даёт превысить лимит запросов
    - Экспоненциальный backoff: до 120 секунд между попытками
    - Всего max_retries+1 = 7 попыток при 429

    Returns:
        (sql, None) — успех
        (None, error_detail) — ошибка с описанием
    """
    if not HAS_GEMINI:
        return None, "Google Gemini SDK не установлен. Установите: pip install google-genai"

    if not settings.GEMINI_API_KEY:
        return None, "GEMINI_API_KEY не задан"

    model_name = settings.GEMINI_MODEL
    timeout = settings.GEMINI_TIMEOUT
    last_error: Optional[str] = None

    for attempt in range(max_retries + 1):
        # Ждём перед первым запросом, если лимит исчерпан
        _rate_limiter.wait_if_needed()

        try:
            client = _genai.Client(
                api_key=settings.GEMINI_API_KEY,
                http_options={"timeout": timeout * 1000},  # миллисекунды
            )
            logger.info(f"Gemini request: model={model_name}, attempt={attempt+1}/{max_retries+1}")

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
                    delay = _exponential_backoff(attempt)
                    logger.warning(f"{last_error} — повтор через {delay:.0f}с")
                    time.sleep(delay)
                    continue
                return None, last_error

            sql = _extract_sql(raw_output)
            if sql:
                return sql, None

            last_error = "Не удалось извлечь SQL из ответа"
            if attempt < max_retries:
                delay = _exponential_backoff(attempt)
                logger.warning(f"{last_error} — повтор через {delay:.0f}с")
                time.sleep(delay)
                continue
            return None, last_error

        except Exception as e:
            error_str = str(e).lower()
            status_code = getattr(e, "code", 0) or getattr(e, "status_code", 0)

            # 429 Too Many Requests — превышен лимит
            if status_code == 429 or "429" in error_str or "quota" in error_str or "rate" in error_str or "resource exhausted" in error_str or "too many" in error_str:
                if attempt < max_retries:
                    delay = _exponential_backoff(attempt)
                    last_error = f"Превышен лимит запросов Gemini (429). Повтор через {delay:.0f}с (попытка {attempt+2}/{max_retries+1})"
                    logger.warning(last_error)
                    time.sleep(delay)
                    continue
                # Все попытки исчерпаны — последняя попытка с максимальной паузой
                last_error = "Превышен лимит запросов Gemini (429). Все попытки исчерпаны. Попробуйте позже."
                logger.error(last_error)
                break

            # 401/403 — проблема с ключом
            elif status_code in (401, 403) or "api key" in error_str or "unauthorized" in error_str or "permission" in error_str or "401" in error_str:
                last_error = "Неверный или заблокированный API ключ Gemini. Проверьте GEMINI_API_KEY."
                logger.error(last_error)
                break

            # Модель не найдена
            elif status_code == 404 or ("not found" in error_str and "model" in error_str):
                last_error = f"Модель '{model_name}' не найдена или недоступна. Проверьте GEMINI_MODEL."
                logger.error(last_error)
                break

            # Таймаут
            elif "timeout" in error_str or "deadline" in error_str or "timed out" in error_str:
                last_error = f"Таймаут запроса к Gemini ({timeout}с)."
                if attempt < max_retries:
                    delay = _exponential_backoff(attempt)
                    logger.warning(f"Timeout — повтор через {delay:.0f}с")
                    time.sleep(delay)
                    continue
                break

            # 500/503 — временная ошибка сервера
            elif status_code in (500, 502, 503, 504) or "server" in error_str or "temporarily" in error_str or "unavailable" in error_str:
                last_error = f"Временная ошибка сервера Gemini ({status_code or 503})."
                if attempt < max_retries:
                    delay = _exponential_backoff(attempt)
                    logger.warning(f"Server error — повтор через {delay:.0f}с")
                    time.sleep(delay)
                    continue
                break

            # Все остальные ошибки
            else:
                last_error = f"Ошибка Gemini: {e}"
                if attempt < max_retries:
                    delay = _exponential_backoff(attempt)
                    logger.warning(f"{last_error} — повтор через {delay:.0f}с")
                    time.sleep(delay)
                    continue
                break

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
