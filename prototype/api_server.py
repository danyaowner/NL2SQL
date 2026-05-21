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

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_company.db")

if not os.path.exists(DB_PATH):
    try:
        from init_db import main as init_db
        init_db()
    except Exception:
        pass


def get_schema_info():
    result = {}
    for t_name, t_info in SCHEMA.items():
        result[t_name] = {
            "description": t_info["description"],
            "columns": {k: v for k, v in t_info["columns"].items()}
        }
    return result


def run_sql(sql):
    if not os.path.exists(DB_PATH):
        return None, "База данных не найдена"
    try:
        conn = sqlite3.connect(DB_PATH)
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

        if path == "/api/schema":
            self._send_json(get_schema_info())
        elif path == "/api/health":
            self._send_json({"status": "ok", "db_exists": os.path.exists(DB_PATH)})
        elif path == "/" or path == "" or path == "/index.html":
            self.path = "/website/index.html"
            return super().do_GET()
        elif path.startswith("/website/"):
            self.path = path
            return super().do_GET()
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
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
