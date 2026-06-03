"""
schema_manager.py — Интроспекция схемы SQLite базы данных.
Никакого хардкода. Динамически читает структуру таблиц и колонок.
"""
import sqlite3
import os
from typing import Optional


def introspect_schema(db_path: str) -> dict:
    """
    Интроспекция SQLite базы данных.
    Возвращает словарь: {table_name: {columns: {col: type}, description: ...}}
    """
    if not os.path.exists(db_path):
        return {}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Получаем список таблиц (GLOB для literal underscore, т.к. LIKE _ = wildcard)
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT GLOB 'sqlite_*' AND name NOT GLOB '_*'"
    )
    tables = [row["name"] for row in cursor.fetchall()]

    schema = {}
    for table in tables:
        # Получаем колонки через PRAGMA
        cursor.execute(f"PRAGMA table_info('{table}')")
        columns = {}
        for row in cursor.fetchall():
            col_name = row["name"]
            col_type = row["type"] if row["type"] else "TEXT"
            columns[col_name] = col_type

        # Получаем внешние ключи
        cursor.execute(f"PRAGMA foreign_key_list('{table}')")
        foreign_keys = []
        for row in cursor.fetchall():
            foreign_keys.append({
                "from": row["from"],
                "table": row["table"],
                "to": row["to"],
            })

        # Считаем количество строк
        cursor.execute(f"SELECT COUNT(*) as cnt FROM '{table}'")
        row_count = cursor.fetchone()["cnt"]

        # Получаем пример данных (первые 2 строки)
        try:
            cursor.execute(f"SELECT * FROM '{table}' LIMIT 2")
            sample_rows = [dict(r) for r in cursor.fetchall()]
        except Exception:
            sample_rows = []

        schema[table] = {
            "columns": columns,
            "foreign_keys": foreign_keys,
            "row_count": row_count,
            "sample_rows": sample_rows,
        }

    conn.close()
    return schema


def format_schema_for_prompt(schema: dict) -> str:
    """
    Форматирует схему БД в текстовое описание для промпта LLM.
    Включает: таблицы, колонки с типами, связи, примеры данных.
    """
    if not schema:
        return "Схема базы данных недоступна."

    lines = ["Схема базы данных (SQLite):"]

    for table_name, info in schema.items():
        cols = info["columns"]
        fks = info["foreign_keys"]
        sample = info.get("sample_rows", [])

        lines.append(f"\nТаблица: {table_name} ({info['row_count']} записей)")
        lines.append("Колонки:")

        for col_name, col_type in cols.items():
            # Отмечаем внешние ключи
            fk_note = ""
            for fk in fks:
                if fk["from"] == col_name:
                    fk_note = f" -> REFERENCES {fk['table']}({fk['to']})"
                    break
            lines.append(f"  {col_name} ({col_type}){fk_note}")

        # Примеры данных
        if sample:
            lines.append("Примеры данных:")
            for i, row in enumerate(sample[:2]):
                values = ", ".join(
                    f"{k}={v}" for k, v in list(row.items())[:5]
                )
                lines.append(f"  [{i+1}] {values}")

    return "\n".join(lines)


def get_schema_summary(schema: dict) -> dict:
    """
    Краткая сводка схемы для UI: список таблиц с описанием.
    """
    summary = {}
    for table_name, info in schema.items():
        summary[table_name] = {
            "columns": list(info["columns"].keys()),
            "row_count": info["row_count"],
        }
    return summary
