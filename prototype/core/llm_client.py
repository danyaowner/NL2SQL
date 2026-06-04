"""
llm_client.py — Клиент для OpenRouter API (OpenAI-совместимый).
Отправляет промпт, получает SQL, обрабатывает ошибки.
Использует OpenRouter с моделью google/gemma-4-26b-a4b-it:free.
"""
import os
from typing import Optional

HAS_OPENAI = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    pass


def _get_client() -> OpenAI:
    """Инициализация клиента OpenRouter API."""
    if not HAS_OPENAI:
        raise ImportError(
            "OpenAI SDK not installed. "
            "Run: pip install openai"
        )

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.environ.get("OPENROUTER_API_KEY", "")
        except ImportError:
            pass

    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY не найден. Установите переменную окружения "
            "или создайте .env файл с OPENROUTER_API_KEY=your_key_here\n"
            "Получить ключ: https://openrouter.ai/keys"
        )

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/nl2sql",
            "X-Title": "NL2SQL",
        },
    )
    return client


def generate_sql(prompt: str, temperature: float = 0.2) -> Optional[str]:
    """
    Отправляет промпт в OpenRouter и получает SQL-запрос.

    Args:
        prompt: Полный промпт с инструкциями, схемой и запросом пользователя
        temperature: Креативность модели (0.0-1.0). 0.2 = почти детерминированно

    Returns:
        Строка с SQL-запросом или None при ошибке
    """
    try:
        client = _get_client()
    except (ImportError, ValueError) as e:
        print(f"[LLM] Ошибка инициализации: {e}")
        return None

    model_name = os.environ.get("OPENROUTER_MODEL", "openrouter/free")

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=temperature,
            max_tokens=1000,
        )
        raw_output = response.choices[0].message.content.strip() if response.choices else ""

        if not raw_output:
            print("[LLM] Пустой ответ от OpenRouter")
            return None

        # Извлекаем SQL из ответа (LLM может обернуть в markdown)
        sql = _extract_sql(raw_output)
        return sql

    except Exception as e:
        print(f"[LLM] Ошибка при генерации: {e}")
        return None


def _extract_sql(text: str) -> str:
    """
    Извлекает чистый SQL из ответа LLM.
    Обрабатывает markdown-блоки, лишний текст, пояснения.
    """
    text = text.strip()

    # Удаляем markdown-блоки SQL
    if "```sql" in text:
        start = text.index("```sql") + 6
        end = text.index("```", start) if "```" in text[start:] else len(text)
        return text[start:end].strip()
    if "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start) if "```" in text[start:] else len(text)
        return text[start:end].strip()

    # Ищем строку, начинающуюся с SELECT или WITH
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.upper().startswith(("SELECT", "WITH")):
            return stripped

    # Если нет явного SELECT — возвращаем как есть
    return text
