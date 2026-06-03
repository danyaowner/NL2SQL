"""
executor.py — Безопасное выполнение SQL-запросов.
Только чтение (read-only транзакции).
"""
import sqlite3
import os
from typing import Tuple, Optional, List, Dict, Any


def execute_query(
    db_path: str, sql: str, max_rows: int = 100
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    Выполняет SQL-запрос к SQLite базе данных в режиме read-only.

    Args:
        db_path: Путь к файлу .db
        sql: SQL-запрос (только SELECT)
        max_rows: Максимальное число возвращаемых строк

    Returns:
        (rows, None) — успех, список словарей с данными
        (None, error_msg) — ошибка
    """
    if not os.path.exists(db_path):
        return None, f"База данных не найдена: {db_path}"

    conn = None
    try:
        # Подключаемся к SQLite
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

        # Устанавливаем таймаут и лимиты
        conn.execute("PRAGMA query_only = ON")
        conn.execute(f"PRAGMA max_rows = {max_rows}")

        cursor = conn.cursor()
        cursor.execute(sql)

        # Получаем результаты (ограничиваем число строк)
        rows = []
        for row in cursor.fetchall():
            rows.append(dict(row))
            if len(rows) >= max_rows:
                break

        return rows, None

    except sqlite3.OperationalError as e:
        return None, f"Ошибка SQLite: {e}"
    except sqlite3.DatabaseError as e:
        return None, f"Ошибка базы данных: {e}"
    except Exception as e:
        return None, f"Неизвестная ошибка: {e}"
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def get_table_sample(db_path: str, table: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Получает пример данных из таблицы.
    """
    rows, err = execute_query(db_path, f"SELECT * FROM '{table}' LIMIT {limit}")
    if err:
        return []
    return rows or []


def get_row_count(db_path: str, table: str) -> int:
    """
    Возвращает количество строк в таблице.
    """
    rows, err = execute_query(db_path, f"SELECT COUNT(*) as cnt FROM '{table}'")
    if err or not rows:
        return 0
    return rows[0].get("cnt", 0)
