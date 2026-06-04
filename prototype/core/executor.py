"""
executor.py — Безопасное выполнение SQL-запросов (только SELECT).
Поддерживает SQLite, PostgreSQL, MySQL.
"""
import sqlite3
import os
import re
from typing import Tuple, Optional, List, Dict, Any

from .config import settings
from .db_adapter import DBConnectionInfo, create_db_adapter


def execute_query(
    db_path: str, sql: str, max_rows: int = 100
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Выполнить SQL-запрос на SQLite по пути к файлу."""
    if not os.path.exists(db_path):
        return None, f"База данных не найдена: {db_path}"
    conn = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        limited_sql = _add_row_limit(sql, max_rows or settings.SQL_MAX_ROWS)
        cursor.execute(limited_sql)
        rows = [dict(row) for row in cursor.fetchall()]
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


def execute_query_adapter(
    conn_info: DBConnectionInfo, sql: str, max_rows: int = 100
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Выполнить SQL-запрос на remote СУБД через адаптер."""
    adapter = create_db_adapter(
        db_type=conn_info.db_type,
        host=conn_info.host,
        port=conn_info.port,
        user=conn_info.user,
        password=conn_info.password,
        database=conn_info.database,
    )
    ok, err = adapter.connect()
    if not ok:
        return None, err or "Не удалось подключиться к СУБД"
    try:
        limited_sql = _add_row_limit(sql, max_rows or settings.SQL_MAX_ROWS)
        rows, exec_err = adapter.execute(limited_sql, max_rows or settings.SQL_MAX_ROWS)
        return rows, exec_err
    finally:
        adapter.close()


def _add_row_limit(sql: str, max_rows: int) -> str:
    """Добавляет LIMIT, если его нет. Учитывает SQL-комментарии."""
    # Удаляем строковые комментарии для проверки
    clean = re.sub(r"--.*$|/\*.*?\*/", "", sql, flags=re.MULTILINE | re.DOTALL)
    upper = clean.strip().upper()
    if "LIMIT" not in upper:
        sql = sql.rstrip().rstrip(";") + f" LIMIT {max_rows}"
    return sql


def get_table_sample(db_path: str, table: str, limit: int = 3) -> List[Dict[str, Any]]:
    rows, err = execute_query(db_path, f"SELECT * FROM \"{table}\" LIMIT {limit}")
    return rows or []

def get_row_count(db_path: str, table: str) -> int:
    rows, err = execute_query(db_path, f"SELECT COUNT(*) as cnt FROM \"{table}\"")
    if err or not rows:
        return 0
    return rows[0].get("cnt", 0)
