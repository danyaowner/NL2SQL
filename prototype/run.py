"""
run.py — Точка входа NL2SQL системы.
Запускает FastAPI сервер с авто-открытием браузера.

Использование:
    python run.py              # Запуск на порту 8000
    python run.py --port 3000  # Запуск на порту 3000
"""
import os
import sys
import argparse
import threading
import webbrowser


def open_browser(url: str, delay: float = 1.5):
    """Открывает браузер с задержкой."""
    def _open():
        import time
        time.sleep(delay)
        try:
            if os.name == "nt":
                webbrowser.open(url)
            else:
                webbrowser.open(url)
            print(f"[OK] Браузер открыт: {url}")
        except Exception as e:
            print(f"[INFO] Браузер не открыт: {e}")
            print(f"[INFO] Откройте {url} вручную")

    threading.Thread(target=_open, daemon=True).start()


def main():
    parser = argparse.ArgumentParser(
        description="NL2SQL — преобразование русского языка в SQL через нейросеть"
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Порт для сервера (по умолчанию: 8000)"
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Не открывать браузер автоматически"
    )
    parser.add_argument(
        "--db", type=str, default=None,
        help="Путь к SQLite базе данных"
    )
    args = parser.parse_args()

    # Устанавливаем переменные окружения
    if args.db:
        os.environ["DB_PATH"] = args.db

    # Проверяем наличие API ключа
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        try:
            from dotenv import load_dotenv
            # Ищем .env в текущей директории и родительской
            for env_path in [".env", "prototype/.env", "../.env"]:
                if os.path.exists(env_path):
                    load_dotenv(env_path)
                    api_key = os.environ.get("GEMINI_API_KEY", "")
                    if api_key:
                        break
        except ImportError:
            pass

    print("=" * 50)
    print("  NL2SQL — Neural NL→SQL Converter")
    print("  Курсовая работа: Преобразование NL в SQL")
    print("=" * 50)

    if not api_key:
        print("\n[WARN] GEMINI_API_KEY не найден!")
        print("[WARN] Создайте .env файл с ключом:")
        print("[WARN]   echo GEMINI_API_KEY=your_key > prototype/.env")
        print("[WARN] Получить ключ: https://aistudio.google.com/apikey")
        print()

    # Проверяем БД
    db_path = os.environ.get("DB_PATH", "")
    if db_path and os.path.exists(db_path):
        print(f"[OK] База данных: {db_path}")
    else:
        if db_path:
            print(f"[WARN] База данных не найдена: {db_path}")
        print("[INFO] Загрузите .db файл через веб-интерфейс")

    url = f"http://localhost:{args.port}"
    print(f"\n[OK] Сервер запускается на {url}")
    print(f"[OK] API документация: {url}/docs")
    print("[OK] Нажмите Ctrl+C для остановки\n")

    # Авто-открытие браузера
    if not args.no_browser:
        open_browser(url)

    # Запуск FastAPI через uvicorn
    try:
        import uvicorn
        uvicorn.run(
            "api.server:app",
            host="0.0.0.0",
            port=args.port,
            reload=False,
            log_level="info",
        )
    except ImportError:
        print("[ERROR] uvicorn не установлен. Установите: pip install uvicorn")
        sys.exit(1)


if __name__ == "__main__":
    main()
