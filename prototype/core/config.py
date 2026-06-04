"""
config.py - Централизованная конфигурация проекта.
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

def load_env() -> None:
    try:
        from dotenv import load_dotenv
        if ENV_PATH.exists():
            load_dotenv(ENV_PATH)
    except ImportError:
        pass

class Settings:
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TIMEOUT: int = 60
    GEMINI_MAX_TOKENS: int = 1000
    PORT: int = 8000
    DB_PATH: str = ""
    SQL_MAX_ROWS: int = 100

    def __init__(self):
        self._load()

    def _load(self):
        self.GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
        self.GEMINI_MODEL = os.environ.get("GEMINI_MODEL", self.GEMINI_MODEL)
        self.GEMINI_TIMEOUT = int(os.environ.get("GEMINI_TIMEOUT", str(self.GEMINI_TIMEOUT)))
        self.GEMINI_MAX_TOKENS = int(os.environ.get("GEMINI_MAX_TOKENS", str(self.GEMINI_MAX_TOKENS)))
        port_str = os.environ.get("PORT", "")
        self.PORT = int(port_str) if port_str.isdigit() else self.PORT
        self.DB_PATH = os.environ.get("DB_PATH", "")

    def validate(self):
        errors = []
        if not self.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY не задан. Создайте .env файл с ключом.")
        elif not self.GEMINI_API_KEY.startswith("AQ."):
            errors.append("GEMINI_API_KEY имеет неверный формат.")
        return errors

load_env()
settings = Settings()
