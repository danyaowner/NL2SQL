"""
db_adapter.py - Universal database adapter for SQLite, PostgreSQL and MySQL.
"""
import os
import sqlite3
from typing import Dict, Any, List, Tuple, Optional

try:
    import psycopg2
    import psycopg2.extras
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

try:
    import pymysql
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False


class DatabaseAdapter:
    def __init__(self, dialect: str = "sqlite", **params):
        self.dialect = dialect.lower()
        self.params = params
        self.conn = None
        self._db_path = params.get("db_path", "")

    def connect(self) -> Tuple[bool, Optional[str]]:
        try:
            if self.dialect == "sqlite":
                return self._connect_sqlite()
            elif self.dialect == "postgresql":
                return self._connect_postgres()
            elif self.dialect == "mysql":
                return self._connect_mysql()
            else:
                return False, f"Unsupported dialect: {self.dialect}"
        except Exception as e:
            return False, str(e)

    def _connect_sqlite(self) -> Tuple[bool, Optional[str]]:
        db_path = self.params.get("db_path", "")
        if not db_path or not os.path.exists(db_path):
            return False, f"DB file not found: {db_path}"
        self.conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
        return True, None

    def _connect_postgres(self) -> Tuple[bool, Optional[str]]:
        if not HAS_POSTGRES:
            return False, "psycopg2 not installed. Run: pip install psycopg2-binary"
        self.conn = psycopg2.connect(
            host=self.params.get("host", "localhost"),
            port=self.params.get("port", 5432),
            dbname=self.params.get("database", ""),
            user=self.params.get("username", ""),
            password=self.params.get("password", ""),
        )
        return True, None

    def _connect_mysql(self) -> Tuple[bool, Optional[str]]:
        if not HAS_MYSQL:
            return False, "pymysql not installed. Run: pip install pymysql"
        self.conn = pymysql.connect(
            host=self.params.get("host", "localhost"),
            port=int(self.params.get("port", 3306)),
            user=self.params.get("username", ""),
            password=self.params.get("password", ""),
            database=self.params.get("database", ""),
            cursorclass=pymysql.cursors.DictCursor,
        )
        return True, None

    def close(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    @property
    def is_connected(self) -> bool:
        return self.conn is not None

    def execute(self, sql: str, max_rows: int = 100) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        if not self.conn:
            return None, "No database connection"
        try:
            if self.dialect == "sqlite":
                return self._execute_sqlite(sql, max_rows)
            else:
                return self._execute_pep249(sql, max_rows)
        except Exception as e:
            return None, f"Execution error: {e}"

    def _execute_sqlite(self, sql: str, max_rows: int) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        try:
            self.conn.execute("PRAGMA query_only = ON")
            cursor = self.conn.cursor()
            cursor.execute(sql)
            rows = []
            for row in cursor.fetchall():
                rows.append(dict(row))
                if len(rows) >= max_rows:
                    break
            return rows, None
        except sqlite3.OperationalError as e:
            return None, f"SQLite error: {e}"
        except sqlite3.DatabaseError as e:
            return None, f"Database error: {e}"

    def _execute_pep249(self, sql: str, max_rows: int) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = []
            for row in cursor.fetchall():
                if isinstance(row, dict):
                    rows.append(row)
                else:
                    rows.append(dict(zip(columns, row)))
                if len(rows) >= max_rows:
                    break
            return rows, None
        except Exception as e:
            self.conn.rollback()
            return None, f"Execution error: {e}"

    def get_tables(self) -> Tuple[List[str], Optional[str]]:
        if not self.conn:
            return [], "No connection"
        try:
            if self.dialect == "sqlite":
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT GLOB 'sqlite_*' AND name NOT GLOB '_*'"
                )
                return [r["name"] for r in cursor.fetchall()], None
            elif self.dialect == "postgresql":
                cursor = self.conn.cursor()
                schema = self.params.get("schema", "public")
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = %s AND table_type = 'BASE TABLE'",
                    (schema,)
                )
                return [r[0] for r in cursor.fetchall()], None
            elif self.dialect == "mysql":
                cursor = self.conn.cursor()
                cursor.execute("SHOW TABLES")
                return [
                    list(r.values())[0] if isinstance(r, dict) else r[0]
                    for r in cursor.fetchall()
                ], None
            return [], f"Unsupported dialect: {self.dialect}"
        except Exception as e:
            return [], str(e)

    def get_columns(self, table: str) -> Tuple[Dict[str, str], Optional[str]]:
        if not self.conn:
            return {}, "No connection"
        try:
            if self.dialect == "sqlite":
                cursor = self.conn.cursor()
                cursor.execute(f"PRAGMA table_info('{table}')")
                return {r["name"]: (r["type"] or "TEXT") for r in cursor.fetchall()}, None
            elif self.dialect == "postgresql":
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_name = %s ORDER BY ordinal_position",
                    (table,)
                )
                return {r[0]: r[1] for r in cursor.fetchall()}, None
            elif self.dialect == "mysql":
                cursor = self.conn.cursor()
                cursor.execute(f"DESCRIBE `{table}`")
                rows = cursor.fetchall()
                if rows and isinstance(rows[0], dict):
                    return {r["Field"]: r["Type"] for r in rows}, None
                else:
                    return {r[0]: r[1] for r in rows}, None
            return {}, f"Unsupported dialect: {self.dialect}"
        except Exception as e:
            return {}, str(e)

    def get_foreign_keys(self, table: str) -> Tuple[List[Dict[str, str]], Optional[str]]:
        if not self.conn:
            return [], "No connection"
        try:
            if self.dialect == "sqlite":
                cursor = self.conn.cursor()
                cursor.execute(f"PRAGMA foreign_key_list('{table}')")
                return [
                    {"from": r["from"], "table": r["table"], "to": r["to"]}
                    for r in cursor.fetchall()
                ], None
            elif self.dialect == "postgresql":
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT kcu.column_name, ccu.table_name, ccu.column_name "
                    "FROM information_schema.table_constraints tc "
                    "JOIN information_schema.key_column_usage kcu "
                    "ON tc.constraint_name = kcu.constraint_name "
                    "JOIN information_schema.constraint_column_usage ccu "
                    "ON ccu.constraint_name = tc.constraint_name "
                    "WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = %s",
                    (table,)
                )
                return [
                    {"from": r[0], "table": r[1], "to": r[2]}
                    for r in cursor.fetchall()
                ], None
            elif self.dialect == "mysql":
                cursor = self.conn.cursor()
                db_name = self.params.get("database", "")
                cursor.execute(
                    "SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
                    "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                    "AND REFERENCED_TABLE_NAME IS NOT NULL",
                    (db_name, table)
                )
                rows = cursor.fetchall()
                if rows and isinstance(rows[0], dict):
                    return [
                        {"from": r["COLUMN_NAME"], "table": r["REFERENCED_TABLE_NAME"],
                         "to": r["REFERENCED_COLUMN_NAME"]}
                        for r in rows
                    ], None
                return [
                    {"from": r[0], "table": r[1], "to": r[2]}
                    for r in rows
                ], None
            return [], f"Unsupported dialect: {self.dialect}"
        except Exception as e:
            return [], str(e)

    def get_row_count(self, table: str) -> int:
        quote = '"' if self.dialect != "mysql" else "`"
        rows, err = self.execute(f"SELECT COUNT(*) AS cnt FROM {quote}{table}{quote}")
        if err or not rows:
            return 0
        return rows[0].get("cnt", 0)

    def get_sample_rows(self, table: str, limit: int = 2) -> List[Dict[str, Any]]:
        quote = '"' if self.dialect != "mysql" else "`"
        rows, _ = self.execute(f"SELECT * FROM {quote}{table}{quote} LIMIT {limit}")
        return rows or []

    def get_full_schema(self) -> Dict[str, Any]:
        tables, err = self.get_tables()
        if err:
            return {}
        schema = {}
        for table in tables:
            columns, _ = self.get_columns(table)
            foreign_keys, _ = self.get_foreign_keys(table)
            row_count = self.get_row_count(table)
            sample_rows = self.get_sample_rows(table)
            schema[table] = {
                "columns": columns,
                "foreign_keys": foreign_keys,
                "row_count": row_count,
                "sample_rows": sample_rows,
            }
        return schema

    @property
    def display_name(self) -> str:
        if self.dialect == "sqlite":
            return os.path.basename(self._db_path) if self._db_path else "SQLite"
        elif self.dialect in ("postgresql", "mysql"):
            host = self.params.get("host", "localhost")
            db = self.params.get("database", "?")
            return f"{self.dialect}://{host}/{db}"
        return self.dialect
