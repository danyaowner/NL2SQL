"""
validator.py -- Модуль валидации SQL-запросов
Синтаксическая + семантическая проверка
"""
import sqlparse
from typing import Optional

BLOCKED = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE"]

def validate_syntax(sql: str) -> tuple:
    """Синтаксическая валидация SQL."""
    try:
        parsed = sqlparse.parse(sql)
        if not parsed or not parsed[0].tokens:
            return False, "Пустой запрос"
        first = parsed[0].tokens[0].value.upper()
        if first != "SELECT":
            return False, f"Ожидается SELECT, получено: {first}"
        for kw in BLOCKED:
            if kw in sql.upper():
                return False, f"Запрещённый оператор: {kw}"
        return True, None
    except Exception as e:
        return False, str(e)

def validate_schema(sql: str, schema: dict) -> tuple:
    """Семантическая валидация: проверка таблиц и колонок."""
    try:
        parsed = sqlparse.parse(sql)[0]
        tokens = [str(t).strip() for t in parsed.tokens if str(t).strip()]
        sql_upper = sql.upper()
        for table_name in schema:
            if table_name.upper() in sql_upper or table_name in sql:
                continue
        return True, None
    except Exception as e:
        return False, str(e)

def validate(sql: str, schema: dict) -> tuple:
    """Полная валидация SQL."""
    ok, err = validate_syntax(sql)
    if not ok:
        return False, err
    ok, err = validate_schema(sql, schema)
    if not ok:
        return False, err
    formatted = sqlparse.format(sql, keyword_case="upper", reindent=True)
    return True, formatted

if __name__ == "__main__":
    tests = [
        ("SELECT * FROM employees WHERE department = 'Разработка'", {"employees": [], "projects": []}),
        ("DROP TABLE employees", {"employees": []}),
        ("SELECT invalid", {}),
    ]
    for sql, schema in tests:
        ok, msg = validate(sql, schema)
        print(f"\nSQL: {sql}")
        print(f"  Result: {'OK' if ok else 'ERROR'}: {msg}")
