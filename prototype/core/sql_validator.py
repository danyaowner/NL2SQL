"""
validator.py — Валидация и проверка безопасности SQL-запросов.
Блокирует опасные операции, проверяет синтаксис, форматирует.
"""
import sqlparse
from typing import Tuple, Optional

# Запрещённые SQL-операторы (только SELECT разрешён)
BLOCKED_KEYWORDS = [
    "DROP", "DELETE", "INSERT", "UPDATE", "ALTER",
    "CREATE", "TRUNCATE", "REPLACE", "GRANT", "REVOKE",
    "EXEC", "EXECUTE", "ATTACH", "DETACH", "PRAGMA",
]


def validate(sql: str) -> Tuple[bool, Optional[str]]:
    """
    Полная валидация SQL-запроса.

    Returns:
        (True, formatted_sql) — запрос валиден
        (False, error_message) — запрос невалиден
    """
    if not sql or not sql.strip():
        return False, "Пустой SQL-запрос"

    sql_clean = sql.strip()

    # 1. Проверка на запрещённые ключевые слова
    sql_upper = sql_clean.upper()
    for keyword in BLOCKED_KEYWORDS:
        # Ищем keyword как отдельное слово (не в составе другого)
        if _is_standalone_keyword(sql_upper, keyword):
            return False, f"Запрещённый оператор: {keyword}. Разрешены только SELECT-запросы."

    # 2. Проверка что запрос начинается с SELECT или WITH
    first_word = sql_upper.split()[0] if sql_upper.split() else ""
    if first_word not in ("SELECT", "WITH"):
        return False, f"Ожидается SELECT или WITH, получено: {first_word}"

    # 3. Синтаксическая валидация через sqlparse
    try:
        parsed = sqlparse.parse(sql_clean)
        if not parsed or not parsed[0].tokens:
            return False, "Не удалось распарсить SQL"
    except Exception as e:
        return False, f"Ошибка парсинга SQL: {e}"

    # 4. Проверка на множественные запросы (sql injection prevention)
    statements = sqlparse.split(sql_clean)
    if len(statements) > 1:
        return False, "Обнаружено несколько SQL-запросов. Разрешён только один."

    # 5. Форматирование
    try:
        formatted = sqlparse.format(
            sql_clean,
            keyword_case="upper",
            reindent=True,
            indent_width=2,
        )
    except Exception:
        formatted = sql_clean

    return True, formatted


def _is_standalone_keyword(sql_upper: str, keyword: str) -> bool:
    """
    Проверяет, является ли keyword отдельным словом в SQL.
    Например: 'DROP' в 'DROP TABLE' — да, 'DROP' в 'DROPDOWN' — нет.
    """
    import re
    pattern = r'\b' + re.escape(keyword) + r'\b'
    return bool(re.search(pattern, sql_upper))


def get_sql_info(sql: str) -> dict:
    """
    Возвращает мета-информацию о SQL-запросе.
    """
    sql_upper = sql.upper()
    info = {
        "has_join": "JOIN" in sql_upper,
        "has_group_by": "GROUP BY" in sql_upper,
        "has_order_by": "ORDER BY" in sql_upper,
        "has_limit": "LIMIT" in sql_upper,
        "has_aggregation": any(
            fn in sql_upper
            for fn in ["COUNT(", "SUM(", "AVG(", "MAX(", "MIN("]
        ),
        "has_subquery": "SELECT" in sql_upper[7:],  # После первого SELECT
    }
    return info
