"""
db_adapter.py — Database adapter supporting SQLite, PostgreSQL, and MySQL.
Поддерживает SQLite (read-only), PostgreSQL, MySQL/MariaDB.
"""
import os
import sqlite3
from typing import Dict, Any, List, Tuple, Optional


class DBConnectionInfo:
    """Параметры подключения к базе данных через СУБД."""
    def __init__(
        self,
        db_type: str = "sqlite",
        host: str = "",
        port: int = 0,
        user: str = "",
        password: str = "",
        database: str = "",
        db_path: str = "",
    ):
        self.db_type = db_type.lower()
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.db_path = db_path

    def to_dict(self) -> dict:
        return {
            "db_type": self.db_type,
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "database": self.database,
            "db_path": self.db_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DBConnectionInfo":
        return cls(
            db_type=data.get("db_type", "sqlite"),
            host=data.get("host", ""),
            port=data.get("port", 0),
            user=data.get("user", ""),
            password=data.get("password", ""),
            database=data.get("database", ""),
            db_path=data.get("db_path", ""),
        )

    @property
    def display_name(self) -> str:
        if self.db_type == "sqlite":
            return os.path.basename(self.db_path) if self.db_path else "SQLite"
        return f"{self.db_type}://{self.host}:{self.port}/{self.database}"


class DatabaseAdapter:
    """Универсальный адаптер для SQLite, PostgreSQL и MySQL."""

    def __init__(self, conn_info: Optional[DBConnectionInfo] = None):
        self.conn_info = conn_info or DBConnectionInfo()
        self.conn = None
        self._db_type = self.conn_info.db_type

    def connect(self) -> Tuple[bool, Optional[str]]:
        try:
            if self._db_type == "sqlite":
                return self._connect_sqlite()
            elif self._db_type == "postgresql":
                return self._connect_postgresql()
            elif self._db_type == "mysql":
                return self._connect_mysql()
            else:
                return False, f"Неподдерживаемый тип СУБД: {self._db_type}"
        except Exception as e:
            return False, str(e)

    def _connect_sqlite(self) -> Tuple[bool, Optional[str]]:
        if not self.conn_info.db_path or not os.path.exists(self.conn_info.db_path):
            return False, f"Файл БД не найден: {self.conn_info.db_path}"
        self.conn = sqlite3.connect(f"file:{self.conn_info.db_path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
        return True, None

    def _connect_postgresql(self) -> Tuple[bool, Optional[str]]:
        try:
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(
                host=self.conn_info.host,
                port=self.conn_info.port or 5432,
                user=self.conn_info.user,
                password=self.conn_info.password,
                dbname=self.conn_info.database,
                connect_timeout=10,
            )
            conn.autocommit = True
            self.conn = conn
            # Настраиваем курсор для возврата dict-подобных строк
            self.conn.cursor_factory = psycopg2.extras.RealDictCursor
            return True, None
        except ImportError:
            return False, "psycopg2 не установлен. Установите: pip install psycopg2-binary"
        except Exception as e:
            return False, f"PostgreSQL error: {e}"

    def _connect_mysql(self) -> Tuple[bool, Optional[str]]:
        try:
            import pymysql
            conn = pymysql.connect(
                host=self.conn_info.host,
                port=self.conn_info.port or 3306,
                user=self.conn_info.user,
                password=self.conn_info.password,
                database=self.conn_info.database,
                connect_timeout=10,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
            )
            self.conn = conn
            return True, None
        except ImportError:
            return False, "pymysql не установлен. Установите: pip install pymysql"
        except Exception as e:
            return False, f"MySQL error: {e}"

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
            return None, "Нет подключения к базе данных"
        try:
            if self._db_type == "sqlite":
                return self._execute_sqlite(sql, max_rows)
            elif self._db_type == "postgresql":
                return self._execute_postgresql(sql, max_rows)
            elif self._db_type == "mysql":
                return self._execute_mysql(sql, max_rows)
            return None, f"Неподдерживаемый тип СУБД: {self._db_type}"
        except Exception as e:
            return None, f"Ошибка выполнения: {e}"

    def _execute_sqlite(self, sql: str, max_rows: int) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        import sqlite3
        self.conn.execute("PRAGMA query_only = ON")
        cursor = self.conn.cursor()
        cursor.execute(sql)
        rows = []
        for row in cursor.fetchall():
            rows.append(dict(row))
            if len(rows) >= max_rows:
                break
        return rows, None

    def _execute_postgresql(self, sql: str, max_rows: int) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        cursor = self.conn.cursor()
        cursor.execute(sql)
        if cursor.description is None:
            return [], None
        rows = []
        for row in cursor.fetchall():
            rows.append(dict(row))
            if len(rows) >= max_rows:
                break
        cursor.close()
        return rows, None

    def _execute_mysql(self, sql: str, max_rows: int) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        cursor = self.conn.cursor()
        cursor.execute(sql)
        if cursor.description is None:
            return [], None
        rows = []
        for row in cursor.fetchall():
            rows.append(dict(row))
            if len(rows) >= max_rows:
                break
        cursor.close()
        return rows, None

    def get_tables(self) -> Tuple[List[str], Optional[str]]:
        if not self.conn:
            return [], "Нет подключения"
        try:
            if self._db_type == "sqlite":
                return self._get_tables_sqlite()
            elif self._db_type == "postgresql":
                return self._get_tables_postgresql()
            elif self._db_type == "mysql":
                return self._get_tables_mysql()
            return [], f"Неподдерживаемый тип: {self._db_type}"
        except Exception as e:
            return [], str(e)

    def _get_tables_sqlite(self) -> Tuple[List[str], Optional[str]]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT GLOB 'sqlite_*' AND name NOT GLOB '_*'"
        )
        return [r["name"] for r in cursor.fetchall()], None

    def _get_tables_postgresql(self) -> Tuple[List[str], Optional[str]]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        )
        return [r["table_name"] for r in cursor.fetchall()], None

    def _get_tables_mysql(self) -> Tuple[List[str], Optional[str]]:
        cursor = self.conn.cursor()
        cursor.execute("SHOW TABLES")
        # pymysql DictCursor returns column name like 'Tables_in_<dbname>'
        rows = cursor.fetchall()
        if not rows:
            return [], None
        key = list(rows[0].keys())[0]
        return [r[key] for r in rows], None

    def get_columns(self, table: str) -> Tuple[Dict[str, str], Optional[str]]:
        if not self.conn:
            return {}, "Нет подключения"
        try:
            if self._db_type == "sqlite":
                return self._get_columns_sqlite(table)
            elif self._db_type == "postgresql":
                return self._get_columns_postgresql(table)
            elif self._db_type == "mysql":
                return self._get_columns_mysql(table)
            return {}, f"Неподдерживаемый тип: {self._db_type}"
        except Exception as e:
            return {}, str(e)

    def _get_columns_sqlite(self, table: str) -> Tuple[Dict[str, str], Optional[str]]:
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA table_info('{table}')")
        return {r["name"]: (r["type"] or "TEXT") for r in cursor.fetchall()}, None

    def _get_columns_postgresql(self, table: str) -> Tuple[Dict[str, str], Optional[str]]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT column_name, data_type "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "ORDER BY ordinal_position",
            (table,),
        )
        return {r["column_name"]: r["data_type"] for r in cursor.fetchall()}, None

    def _get_columns_mysql(self, table: str) -> Tuple[Dict[str, str], Optional[str]]:
        cursor = self.conn.cursor()
        cursor.execute(f"SHOW COLUMNS FROM `{table}`")
        rows = cursor.fetchall()
        columns = {}
        for r in rows:
            name = r.get("Field", "")
            col_type = r.get("Type", "TEXT")
            columns[name] = col_type
        return columns, None

    def get_foreign_keys(self, table: str) -> Tuple[List[Dict[str, str]], Optional[str]]:
        if not self.conn:
            return [], "Нет подключения"
        try:
            if self._db_type == "sqlite":
                return self._get_fk_sqlite(table)
            elif self._db_type == "postgresql":
                return self._get_fk_postgresql(table)
            elif self._db_type == "mysql":
                return self._get_fk_mysql(table)
            return [], None
        except Exception as e:
            return [], str(e)

    def _get_fk_sqlite(self, table: str) -> Tuple[List[Dict[str, str]], Optional[str]]:
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA foreign_key_list('{table}')")
        return [
            {"from": r["from"], "table": r["table"], "to": r["to"]}
            for r in cursor.fetchall()
        ], None

    def _get_fk_postgresql(self, table: str) -> Tuple[List[Dict[str, str]], Optional[str]]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT
                kcu.column_name AS "from",
                ccu.table_name AS "table",
                ccu.column_name AS "to"
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
                AND tc.table_schema = ccu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = %s
                AND tc.table_schema = 'public'
            """,
            (table,),
        )
        return [dict(r) for r in cursor.fetchall()], None

    def _get_fk_mysql(self, table: str) -> Tuple[List[Dict[str, str]], Optional[str]]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT
                COLUMN_NAME AS `from`,
                REFERENCED_TABLE_NAME AS `table`,
                REFERENCED_COLUMN_NAME AS `to`
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = %s
                AND REFERENCED_TABLE_NAME IS NOT NULL
            """,
            (table,),
        )
        return [dict(r) for r in cursor.fetchall()], None

    def get_row_count(self, table: str) -> int:
        rows, err = self.execute(f'SELECT COUNT(*) AS cnt FROM "{table}"')
        if err or not rows:
            return 0
        return rows[0].get("cnt", 0)

    def get_sample_rows(self, table: str, limit: int = 2) -> List[Dict[str, Any]]:
        rows, _ = self.execute(f'SELECT * FROM "{table}" LIMIT {limit}')
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
        return self.conn_info.display_name if self.conn_info else "SQLite"


# ─── Factory functions для обратной совместимости ─────────────────────

def create_adapter(db_path: str = "") -> DatabaseAdapter:
    """Создать SQLite адаптер по пути к файлу."""
    conn_info = DBConnectionInfo(db_type="sqlite", db_path=db_path)
    return DatabaseAdapter(conn_info)


def create_db_adapter(
    db_type: str = "sqlite",
    host: str = "",
    port: int = 0,
    user: str = "",
    password: str = "",
    database: str = "",
    db_path: str = "",
) -> DatabaseAdapter:
    """Создать адаптер для указанного типа СУБД."""
    conn_info = DBConnectionInfo(
        db_type=db_type,
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        db_path=db_path,
    )
    return DatabaseAdapter(conn_info)
