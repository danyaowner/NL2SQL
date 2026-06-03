"""
preprocessor.py — Минимальная очистка текста запроса.
Никакого keyword matching, entity extraction, классификации.
Только санитарная обработка текста перед отправкой в LLM.
"""
import re


def clean_query(text: str) -> str:
    """
    Очистка запроса: удаление лишних пробелов, нормализация.
    НЕ извлекает сущности, НЕ классифицирует — это задача LLM.
    """
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text
