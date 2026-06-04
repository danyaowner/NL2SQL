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
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_TIMEOUT: int = 60
    OPENROUTER_MAX_TOKENS: int = 1000
    OPENROUTER_FALLBACK_MODEL: str = "openrouter/free"
    PORT: int = 8000
    DB_PATH: str = ""
    SQL_MAX_ROWS: int = 100

    def __init__(self):
        self._load()

    def _load(self):
        self.OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
        self.OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", self.OPENROUTER_MODEL)
        self.OPENROUTER_TIMEOUT = int(os.environ.get("OPENROUTER_TIMEOUT", str(self.OPENROUTER_TIMEOUT)))
        self.OPENROUTER_MAX_TOKENS = int(os.environ.get("OPENROUTER_MAX_TOKENS", str(self.OPENROUTER_MAX_TOKENS)))
        port_str = os.environ.get("PORT", "")
        self.PORT = int(port_str) if port_str.isdigit() else self.PORT
        self.DB_PATH = os.environ.get("DB_PATH", "")

    def validate(self):
        errors = []
        if not self.OPENROUTER_API_KEY:
            errors.append("OPENROUTER_API_KEY не задан.")
        elif not self.OPENROUTER_API_KEY.startswith("sk-or-"):
            errors.append("OPENROUTER_API_KEY имеет неверный формат.")
        return errors

# Load .env BEFORE creating settings so env vars are available
load_env()
settings = Settings()
