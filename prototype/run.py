"""
run.py — Точка входа NL2SQL системы.
"""
import os
import sys
import argparse
import logging

from core.config import settings, load_env

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger("run")


def main():
    parser = argparse.ArgumentParser(description="NL2SQL — преобразование русского языка в SQL через нейросеть")
    parser.add_argument("--port", type=int, default=None, help="Порт для сервера")
    parser.add_argument("--no-browser", action="store_true", help="Не открывать браузер")
    parser.add_argument("--db", type=str, default=None, help="Путь к SQLite базе")
    args = parser.parse_args()

    # Загружаем .env
    load_env()
    settings._load()

    if args.port:
        os.environ["PORT"] = str(args.port)
        settings._load()
    if args.db:
        os.environ["DB_PATH"] = args.db
        settings._load()

    print("=" * 50)
    print("  NL2SQL — Neural NL→SQL Converter")
    print("=" * 50)

    # Валидация API ключа
    errors = settings.validate()
    if errors:
        for err in errors:
            print(f"\n[ERROR] {err}")
        print("\n[INFO] Создайте .env файл:")
        print("  echo OPENROUTER_API_KEY=sk-or-v1-... > prototype/.env")
        print("  Получить ключ: https://openrouter.ai/keys\n")
    else:
        print(f"[OK] OpenRouter API ключ: {settings.OPENROUTER_API_KEY[:15]}...")
        print(f"[OK] Модель: {settings.OPENROUTER_MODEL}")

    # Проверяем БД
    if settings.DB_PATH and os.path.exists(settings.DB_PATH):
        print(f"[OK] База данных: {settings.DB_PATH}")
    else:
        if settings.DB_PATH:
            print(f"[WARN] База не найдена: {settings.DB_PATH}")
        print("[INFO] Загрузите .db файл через веб-интерфейс")

    url = f"http://localhost:{settings.PORT}"
    print(f"\n[OK] Сервер запускается на {url}")
    print(f"[OK] API: {url}/docs")
    print("[OK] Нажмите Ctrl+C для остановки\n")

    if not errors and not args.no_browser:
        import threading, webbrowser
        def _open():
            import time
            time.sleep(1.5)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()

    try:
        import uvicorn
        uvicorn.run(
            "api.server:app",
            host="0.0.0.0",
            port=settings.PORT,
            reload=False,
            log_level="info",
        )
    except ImportError:
        print("[ERROR] uvicorn не установлен. pip install uvicorn")
        sys.exit(1)


if __name__ == "__main__":
    main()
