"""
api_server.py — HTTP API сервер для веб-сайта NL2SQL
Запуск: python3 api_server.py
Открыть: http://localhost:8000
"""
import http.server
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nl_module import process_query
from schema_selector import select_schema, SCHEMA
from validator import validate
from sql_generator import generate as gen_sql
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(BASE_DIR, "test_company.db")

# Current selected database (per-session via API)
current_db = DEFAULT_DB

# Init default DB if not exists
if not os.path.exists(DEFAULT_DB):
    try:
        from init_db import main as init_db
        init_db()
    except Exception:
        pass


def get_available_databases():
    """Сканирование директории на .db файлы."""
    dbs = []
    for f in os.listdir(BASE_DIR):
        if f.endswith(".db"):
            path = os.path.join(BASE_DIR, f)
            size = os.path.getsize(path)
            dbs.append({
                "name": f,
                "path": path,
                "size": size,
                "size_hr": f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/(1024*1024):.1f} MB"
            })
    return dbs


def get_database_info(db_path):
    """Получение информации о таблицах в БД."""
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = []
        for row in cur.fetchall():
            tname = row[0]
            cnt = cur.execute(f"SELECT COUNT(*) FROM \"{tname}\"").fetchone()[0]
            cur.execute(f"PRAGMA table_info(\"{tname}\")")
            cols = [{"name": r[1], "type": r[2]} for r in cur.fetchall()]
            tables.append({"name": tname, "row_count": cnt, "columns": cols})
        conn.close()
        return {"tables": tables, "total_tables": len(tables)}
    except Exception as e:
        return {"error": str(e)}


def get_schema_info():
    result = {}
    for t_name, t_info in SCHEMA.items():
        result[t_name] = {
            "description": t_info["description"],
            "columns": {k: v for k, v in t_info["columns"].items()}
        }
    return result


def run_sql(sql, db_path=None):
    if db_path is None:
        db_path = current_db
    if not os.path.exists(db_path):
        return None, "База данных не найдена"
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows, None
    except Exception as e:
        return None, str(e)


def process_query_full(query_text):
    results = {
        "query": query_text,
        "steps": [],
        "sql": None,
        "rows": None,
        "error": None,
        "success": False,
    }

    # Step 1: NL Processing
    try:
        qi = process_query(query_text)
        results["steps"].append({
            "name": "Анализ запроса",
            "icon": "🔍",
            "status": "success",
            "details": {
                "Язык": "Русский" if qi["language"] == "ru" else "English",
                "Тип запроса": qi["query_type"],
                "Сущности": ", ".join(qi["entities"]) if qi["entities"] else "—",
                "Числа": str(qi["numbers"]) if qi["numbers"] else "—",
                "Условия": str(qi["conditions"]) if qi["conditions"] else "—",
            },
            "raw": qi,
        })
    except Exception as e:
        results["steps"].append({"name": "Анализ запроса", "icon": "🔍", "status": "error", "error": str(e)})
        results["error"] = str(e)
        return results

    # Step 2: Schema Selection
    try:
        si = select_schema(qi["cleaned"])
        tables_info = []
        for t in si["tables"]:
            cols = si["columns"].get(t, [])
            tables_info.append({
                "name": t,
                "description": SCHEMA[t]["description"],
                "columns": cols[:6],
            })
        results["steps"].append({
            "name": "Выбор схемы",
            "icon": "📚",
            "status": "success",
            "details": {"Таблицы": ", ".join(si["tables"])},
            "tables": tables_info,
        })
    except Exception as e:
        results["steps"].append({"name": "Выбор схемы", "icon": "📚", "status": "error", "error": str(e)})
        results["error"] = str(e)
        return results

    # Step 3: SQL Generation
    try:
        sql = gen_sql(qi, si, mode="demo")
        results["sql"] = sql
        results["steps"].append({
            "name": "Генерация SQL",
            "icon": "💡",
            "status": "success" if sql else "error",
            "sql": sql,
            "error": None if sql else "Не удалось сгенерировать SQL",
        })
    except Exception as e:
        results["steps"].append({"name": "Генерация SQL", "icon": "💡", "status": "error", "error": str(e)})
        results["error"] = str(e)
        return results

    if not sql:
        results["error"] = "Не удалось сгенерировать SQL"
        return results

    # Step 4: Validation
    try:
        db_schema = {}
        valid, msg = validate(sql, db_schema)
        results["steps"].append({
            "name": "Валидация",
            "icon": "✅",
            "status": "success" if valid else "warning",
            "valid": valid,
            "message": msg if not valid else "SQL корректен и безопасен",
        })
    except Exception as e:
        results["steps"].append({"name": "Валидация", "icon": "✅", "status": "error", "error": str(e)})
        results["error"] = str(e)
        return results

    if not valid:
        results["error"] = msg
        return results

    # Step 5: Execution
    try:
        rows, err = run_sql(sql)
        results["rows"] = rows
        results["steps"].append({
            "name": "Выполнение",
            "icon": "🚀",
            "status": "success" if rows is not None else "error",
            "row_count": len(rows) if rows else 0,
            "error": err,
            "columns": list(rows[0].keys()) if rows else [],
        })
        if rows is not None:
            results["success"] = True
    except Exception as e:
        results["steps"].append({"name": "Выполнение", "icon": "🚀", "status": "error", "error": str(e)})
        results["error"] = str(e)
        return results

    return results


class APIHandler(http.server.SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/api/schema":
            self._send_json(get_schema_info())
        elif path == "/api/health":
            self._send_json({
                "status": "ok",
                "db_exists": os.path.exists(current_db),
                "current_db": os.path.basename(current_db) if current_db else None
            })
        elif path == "/api/databases":
            """Список доступных .db файлов."""
            dbs = get_available_databases()
            # Add info for each db
            for db in dbs:
                info = get_database_info(db["path"])
                if info:
                    db["tables"] = info["tables"]
                    db["total_tables"] = info["total_tables"]
                db["is_current"] = (db["path"] == current_db)
            self._send_json({"databases": dbs, "current": os.path.basename(current_db) if current_db else None})
        elif path == "/api/database-info":
            """Информация о выбранной БД."""
            db_name = qs.get("name", [None])[0]
            if db_name:
                db_path = os.path.join(BASE_DIR, db_name)
            else:
                db_path = current_db
            info = get_database_info(db_path)
            if info:
                info["name"] = os.path.basename(db_path)
                self._send_json(info)
            else:
                self._send_json({"error": "Database not found"})
        elif path == "/api/current-db":
            """Текущая БД."""
            self._send_json({
                "name": os.path.basename(current_db) if current_db else None,
                "path": current_db,
                "exists": os.path.exists(current_db) if current_db else False
            })
        elif path == "/" or path == "" or path == "/index.html":
            self.path = "/website/index.html"
            return super().do_GET()
        elif path.startswith("/website/"):
            self.path = path
            return super().do_GET()
        else:
            self.send_error(404, "Not found")

    def _parse_multipart_body(self):
        """Парсинг multipart/form-data тела запроса.
        Возвращает dict с ключами: field_name -> значение (str) и 'file' -> (data, filename).
        """
        content_type = self.headers.get("Content-Type", "")
        boundary = None
        for part in content_type.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part[9:].strip('"')
                break
        if not boundary:
            return None

        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length)

        b_boundary = ("--" + boundary).encode()
        b_boundary_end = ("--" + boundary + "--").encode()
        parts = raw.split(b_boundary)

        result = {}
        for part in parts:
            if not part or part.strip() == b"" or b_boundary_end in part:
                continue
            if b"\r\n\r\n" not in part:
                continue
            header_bytes, data = part.split(b"\r\n\r\n", 1)
            # Remove trailing \r\n
            if data.endswith(b"\r\n"):
                data = data[:-2]

            headers_str = header_bytes.decode("utf-8", errors="replace")
            field_name = None
            filename = None
            for line in headers_str.split("\r\n"):
                if line.lower().startswith("content-disposition:"):
                    for dp in line.split(";"):
                        dp = dp.strip()
                        if dp.startswith("name=\""):
                            field_name = dp[6:-1]
                        elif dp.startswith("name="):
                            field_name = dp[5:]
                        if dp.startswith("filename=\""):
                            filename = dp[10:-1]
                        elif dp.startswith("filename="):
                            filename = dp[9:]

            if filename:
                result["file"] = (data, filename)
            elif field_name:
                result[field_name] = data.decode("utf-8", errors="replace")

        return result

    def do_POST(self):
        global current_db
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/query":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            query = data.get("query", "")
            if not query.strip():
                self._send_json({"error": "Запрос не может быть пустым"})
                return
            results = process_query_full(query)
            self._send_json(results)
        elif path == "/api/select-database":
            """Выбор активной БД."""
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            db_name = data.get("name", "")
            if not db_name:
                self._send_json({"success": False, "error": "No database name provided"})
                return
            db_path = os.path.join(BASE_DIR, db_name)
            if not os.path.exists(db_path):
                self._send_json({"success": False, "error": f"Database '{db_name}' not found"})
                return
            current_db = db_path
            info = get_database_info(db_path)
            self._send_json({
                "success": True,
                "name": db_name,
                "info": info
            })
        elif path == "/api/upload-database":
            """Загрузка .db файла через multipart/form-data."""
            form = self._parse_multipart_body()
            if not form or "file" not in form:
                self._send_json({"success": False, "error": "No file uploaded. Use multipart/form-data with a 'file' field."})
                return

            file_data, original_filename = form["file"]
            filename = os.path.basename(original_filename)

            # Validate extension
            if not filename.lower().endswith(".db"):
                self._send_json({"success": False, "error": "Only .db files are accepted"})
                return

            # Ensure unique filename
            save_path = os.path.join(BASE_DIR, filename)
            counter = 1
            while os.path.exists(save_path):
                name, ext = os.path.splitext(filename)
                save_path = os.path.join(BASE_DIR, f"{name}_{counter}{ext}")
                counter += 1

            try:
                with open(save_path, "wb") as f:
                    f.write(file_data)
            except Exception as e:
                self._send_json({"success": False, "error": f"Failed to save file: {str(e)}"})
                return

            # Validate it's a real SQLite database
            try:
                conn = sqlite3.connect(save_path)
                conn.execute("SELECT 1")
                conn.close()
            except Exception:
                os.remove(save_path)
                self._send_json({"success": False, "error": "File is not a valid SQLite database"})
                return

            # Auto-select the uploaded database
            current_db = save_path
            saved_name = os.path.basename(save_path)
            info = get_database_info(save_path)

            self._send_json({
                "success": True,
                "name": saved_name,
                "original_name": original_filename,
                "info": info
            })
        else:
            self.send_error(404, "Not found")

    def _send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))


def main():
    port = 8000
    server_address = ("", port)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    httpd = http.server.HTTPServer(server_address, APIHandler)
    print("🌐 NL2SQL Prototype Website")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📡 Сервер запущен: http://localhost:{port}")
    print(f"📖 Откройте в браузере: http://localhost:{port}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("💡 Нажмите Ctrl+C для остановки")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
