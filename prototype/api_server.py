"""
api_server.py — HTTP API сервер для веб-сайта NL2SQL
Запуск: python3 api_server.py
Открыть: http://localhost:8000
"""
import http.server
import json
import os
import sys
import tempfile
import threading
import urllib.parse
import webbrowser
from email import policy
from email.parser import BytesParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.pipeline import process_nl_query
from core.schema_manager import introspect_schema, get_schema_summary
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(tempfile.gettempdir(), "nl2sql_uploads"))
DEFAULT_DB = os.path.join(BASE_DIR, "test_company.db")

# Current selected database (None until user uploads one)
current_db = None


def _init_default_database():
    """Подключить встроенную тестовую БД, если она есть."""
    global current_db
    if os.path.exists(DEFAULT_DB):
        current_db = DEFAULT_DB


def get_schema_info():
    """Get schema from the currently active database via introspection."""
    if current_db and os.path.exists(current_db):
        schema = introspect_schema(current_db)
        return get_schema_summary(schema)
    return {}



def process_query_full(query_text):
    """Process NL query through Gemini pipeline - NO keyword matching."""
    if current_db is None or not os.path.exists(current_db):
        return {"query": query_text, "steps": [], "sql": None, "rows": None, "error": "No database loaded", "success": False}
    return process_nl_query(query_text, current_db)


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
                "db_loaded": current_db is not None and os.path.exists(current_db),
                "current_db": os.path.basename(current_db) if current_db and os.path.exists(current_db) else None
            })
        elif path == "/" or path == "" or path == "/index.html":
            self.path = "/website/index.html"
            return super().do_GET()
        elif path.startswith("/website/"):
            self.path = path
            return super().do_GET()
        else:
            # Try serving from website/ directory (supports root-relative paths like /styles.css)
            static_path = "/website" + path
            full_path = os.path.join(BASE_DIR, static_path.lstrip("/"))
            if os.path.exists(full_path) and not os.path.isdir(full_path):
                self.path = static_path
                return super().do_GET()
            self.send_error(404, "Not found")

    def _read_request_body(self) -> bytes:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            return b""
        old_timeout = self.request.gettimeout() if hasattr(self, "request") else None
        if hasattr(self, "request"):
            self.request.settimeout(60)
        try:
            return self.rfile.read(content_length)
        finally:
            if hasattr(self, "request") and old_timeout is not None:
                self.request.settimeout(old_timeout)

    def _parse_multipart_body(self):
        """Парсинг multipart/form-data (Chrome, Firefox, Edge)."""
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type.lower():
            return None

        raw = self._read_request_body()
        if not raw:
            return None

        result = {}
        try:
            mime_headers = (
                f"Content-Type: {content_type}\r\n"
                "MIME-Version: 1.0\r\n\r\n"
            ).encode("utf-8")
            message = BytesParser(policy=policy.HTTP).parsebytes(mime_headers + raw)
            for part in message.iter_parts():
                cd = part.get("Content-Disposition", "")
                if not cd:
                    continue
                params = {}
                for item in cd.split(";"):
                    item = item.strip()
                    if "=" in item:
                        key, val = item.split("=", 1)
                        params[key.strip().lower()] = val.strip().strip('"')
                name = params.get("name")
                filename = params.get("filename")
                payload = part.get_payload(decode=True) or b""
                if filename:
                    result["file"] = (payload, filename)
                elif name:
                    result[name] = payload.decode("utf-8", errors="replace")
        except Exception:
            result = {}

        if result.get("file"):
            return result

        # Fallback: ручной разбор, если email.parser не справился
        boundary = None
        for piece in content_type.split(";"):
            piece = piece.strip()
            if piece.startswith("boundary="):
                boundary = piece[9:].strip('"')
                break
        if not boundary:
            return None

        b_boundary = ("--" + boundary).encode()
        for part in raw.split(b_boundary):
            if not part or part.strip() in (b"", b"--"):
                continue
            if b"\r\n\r\n" not in part:
                continue
            header_bytes, data = part.split(b"\r\n\r\n", 1)
            if data.endswith(b"\r\n"):
                data = data[:-2]
            headers_str = header_bytes.decode("utf-8", errors="replace")
            field_name = None
            filename = None
            for line in headers_str.split("\r\n"):
                if not line.lower().startswith("content-disposition:"):
                    continue
                for dp in line.split(";"):
                    dp = dp.strip()
                    if dp.startswith('name="'):
                        field_name = dp[6:-1]
                    elif dp.startswith("name="):
                        field_name = dp[5:]
                    if dp.startswith('filename="'):
                        filename = dp[10:-1]
                    elif dp.startswith("filename="):
                        filename = dp[9:]
            if filename:
                result["file"] = (data, filename)
            elif field_name:
                result[field_name] = data.decode("utf-8", errors="replace")

        return result if result.get("file") else None

    def do_POST(self):
        global current_db
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/query":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                data = json.loads(body)
                query = data.get("query", "")
                if not query.strip():
                    self._send_json({"error": "Запрос не может быть пустым"})
                    return
                if current_db is None or not os.path.exists(current_db):
                    self._send_json({"error": "База данных не загружена. Загрузите .db файл через /api/upload-database"})
                    return
                results = process_query_full(query)
                self._send_json(results)
            except Exception as e:
                self._send_json({"error": f"Ошибка обработки запроса: {str(e)}"})
        elif path == "/api/upload-database":
            try:
                self._handle_upload()
            except Exception as e:
                self._send_json({"success": False, "error": f"Ошибка загрузки: {str(e)}"})
        elif path == "/api/init-demo-db":
            try:
                self._handle_init_demo_db()
            except Exception as e:
                self._send_json({"success": False, "error": f"Ошибка инициализации демо-БД: {str(e)}"})
        else:
            self.send_error(404, "Not found")

    def _handle_upload(self):
        """Обработка загрузки .db файла."""
        global current_db
        form = self._parse_multipart_body()
        if not form or "file" not in form:
            self._send_json({"success": False, "error": "Файл не найден в запросе. Используйте multipart/form-data с полем 'file'."})
            return

        file_data, original_filename = form["file"]
        if not file_data:
            self._send_json({"success": False, "error": "Пустой файл"})
            return

        filename = os.path.basename(original_filename)

        # Validate extension
        if not filename.lower().endswith(".db"):
            self._send_json({"success": False, "error": "Принимаются только .db файлы"})
            return

        os.makedirs(UPLOAD_DIR, exist_ok=True)

        # Сохраняем во временную папку
        save_path = os.path.join(UPLOAD_DIR, filename)
        counter = 1
        while os.path.exists(save_path):
            name, ext = os.path.splitext(filename)
            save_path = os.path.join(UPLOAD_DIR, f"{name}_{counter}{ext}")
            counter += 1

        try:
            with open(save_path, "wb") as f:
                f.write(file_data)
        except OSError as e:
            self._send_json({
                "success": False,
                "error": (
                    f"Не удалось сохранить файл: {e}. "
                    "Закройте файл в других программах или скопируйте его на диск."
                ),
            })
            return

        # Validate it's a real SQLite database
        try:
            conn = sqlite3.connect(save_path)
            conn.execute("SELECT 1")
            conn.close()
        except Exception:
            if os.path.exists(save_path):
                os.remove(save_path)
            self._send_json({"success": False, "error": "Файл не является валидной SQLite базой данных"})
            return

        # Set as active database
        current_db = save_path
        saved_name = os.path.basename(save_path)

        self._send_json({
            "success": True,
            "name": saved_name,
            "original_name": original_filename
        })

    def _handle_init_demo_db(self):
        """Инициализация встроенной демо-БД."""
        global current_db
        from init_db import init_database, DB_PATH as DEMO_DB_PATH

        # Создаём демо-БД, если её ещё нет
        if not os.path.exists(DEMO_DB_PATH):
            init_database()

        if not os.path.exists(DEMO_DB_PATH):
            self._send_json({"success": False, "error": "Не удалось создать демо-БД"})
            return

        current_db = DEMO_DB_PATH
        self._send_json({
            "success": True,
            "name": os.path.basename(DEMO_DB_PATH),
            "original_name": "demo (тестовая компания)"
        })

    def _send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))


def open_browser():
    """Открыть браузер с небольшой задержкой после старта сервера.
    В WSL использует explorer.exe, на Linux/Mac — xdg-open / open.
    """
    url = "http://localhost:8000"
    try:
        # WSL: открываем через Windows explorer.exe
        if os.name == "nt" or (hasattr(os, "uname") and "microsoft" in os.uname().release.lower()):
            import subprocess
            explorer = "/mnt/c/Windows/explorer.exe"
            if os.path.exists(explorer):
                subprocess.Popen([explorer, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"Browser opened: {url}")
                return
        # Обычный способ
        webbrowser.open(url)
        print(f"Browser opened: {url}")
    except Exception:
        pass


def main():
    port = int(os.environ.get("PORT", 8000))
    server_address = ("", port)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    _init_default_database()
    httpd = http.server.HTTPServer(server_address, APIHandler)
    print("NL2SQL Prototype Website")
    print("=" * 40)
    print(f"Server: http://0.0.0.0:{port}")
    if current_db:
        print(f"Database: {os.path.basename(current_db)} (auto-loaded)")
    else:
        print("Database: upload .db on the website")
    print("Press Ctrl+C to stop")
    print("=" * 40)
    # Авто-открытие браузера через 1.5 секунды (только для localhost)
    if port == 8000:
        threading.Timer(1.5, open_browser).start()
    httpd.serve_forever()


if __name__ == "__main__":
    main()
