"""
llm_client.py — Клиент для Google Gemini API.
Отправляет промпт, получает SQL, обрабатывает ошибки.
Использует бесплатный tier Google Gemini.

Поддерживает как google-genai (новый SDK), так и google-generativeai (legacy).
"""
import os
from typing import Optional

# Пробуем новый SDK (google-genai), затем legacy (google-generativeai)
HAS_GEMINI = False
_genai_module = None

# Новый SDK: google-genai
try:
    from google import genai as _genai_new
    HAS_GEMINI = True
    _genai_module = "new"  # google-genai
except ImportError:
    pass

# Legacy SDK: google-generativeai
if not HAS_GEMINI:
    try:
        import google.generativeai as _genai_legacy
        HAS_GEMINI = True
        _genai_module = "legacy"  # google-generativeai
    except ImportError:
        pass


def _get_client():
    """Инициализация клиента Gemini API."""
    if not HAS_GEMINI:
        raise ImportError(
            "Google Gemini SDK not installed. "
            "Run: pip install google-genai (новый SDK) "
            "или pip install google-generativeai (legacy)"
        )

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        # Попробуем .env файл
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.environ.get("GEMINI_API_KEY", "")
        except ImportError:
            pass

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY не найден. Установите переменную окружения "
            "или создайте .env файл с GEMINI_API_KEY=your_key_here\n"
            "Получить ключ: https://aistudio.google.com/apikey"
        )

    return api_key


def generate_sql(prompt: str, temperature: float = 0.2) -> Optional[str]:
    """
    Отправляет промпт в Gemini и получает SQL-запрос.

    Args:
        prompt: Полный промпт с инструкциями, схемой и запросом пользователя
        temperature: Креативность модели (0.0-1.0). 0.2 = почти детерминированно

    Returns:
        Строка с SQL-запросом или None при ошибке
    """
    try:
        api_key = _get_client()
    except (ImportError, ValueError) as e:
        print(f"[LLM] Ошибка инициализации: {e}")
        return None

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    try:
        if _genai_module == "new":
            # Новый SDK: google-genai
            client = _genai_new.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    "temperature": temperature,
                    "max_output_tokens": 1000,
                },
            )
            raw_output = response.text.strip() if response.text else ""
        else:
            # Legacy SDK: google-generativeai
            _genai_legacy.configure(api_key=api_key)
            model = _genai_legacy.GenerativeModel(
                model_name=model_name,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": 1000,
                },
            )
            response = model.generate_content(prompt)
            raw_output = response.text.strip() if response.text else ""

        if not raw_output:
            print("[LLM] Пустой ответ от Gemini")
            return None

        # Извлекаем SQL из ответа (Gemini может обернуть в markdown)
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
