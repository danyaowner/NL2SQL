"""
server.py — FastAPI сервер NL2SQL системы.
Предоставляет REST API для веб-интерфейса: обработка запросов,
интроспекция схемы, выполнение SQL.

Запуск: python run.py
API docs: http://localhost:8000/docs
"""
import os
import sys
import tempfile
import sqlite3
from pathlib import Path

# Добавляем родительскую директорию в путь для импорта core
sys.path.insert(0, str(Path(__file__).parent.parent))

# Загружаем .env при старте (если есть)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.pipeline import process_nl_query
from core.schema_manager import introspect_schema, get_schema_summary


def _init_demo_database():
    """Ленивый импорт init_db — не роняет сервер при ошибке."""
    from init_db import init_database as _do_init
    _do_init()


# === Модели данных ===

class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    query: str
    cleaned: str
    sql: str | None = None
    formatted_sql: str | None = None
    rows: list | None = None
    columns: list = []
    error: str | None = None
    steps: list = []
    timing_ms: int = 0
    success: bool = False


class SchemaResponse(BaseModel):
    tables: dict
    db_path: str
    db_loaded: bool


class UploadResponse(BaseModel):
    success: bool
    name: str | None = None
    original_name: str | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    db_loaded: bool
    db_path: str | None = None
    api_key_configured: bool


# === Конфигурация ===

BASE_DIR = Path(__file__).parent.parent
DEFAULT_DB = BASE_DIR / "test_company.db"
UPLOAD_DIR = Path(tempfile.gettempdir()) / "nl2sql_uploads"

# Текущая активная БД (может меняться при upload)
_current_db = None

app = FastAPI(
    title="NL2SQL API",
    description="Преобразование запросов на естественном языке в SQL с использованием нейросетевых моделей",
    version="2.0.0",
)

# CORS для веб-интерфейса
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """При старте: авто-создание demo БД, если её нет."""
    demo_path = str(DEFAULT_DB)
    if not os.path.exists(demo_path):
        try:
            _init_demo_database()
            print(f"[OK] Demo database created: {demo_path}")
        except Exception as e:
            print(f"[WARN] Could not create demo database: {e}")


def _get_db_path() -> str:
    """Определяет путь к активной БД."""
    global _current_db
    # Если была загружена пользовательская БД — используем её
    if _current_db and os.path.exists(_current_db):
        return _current_db
    # Иначе — дефолтная
    db_path = os.environ.get("DB_PATH", str(DEFAULT_DB))
    if os.path.exists(db_path):
        _current_db = db_path
    return db_path


# === API Endpoints ===

@app.post("/api/upload-database", response_model=UploadResponse)
async def upload_database(file: UploadFile = File(...)):
    """
    Загрузить SQLite базу данных (.db файл).
    После загрузки становится активной БД для всех запросов.
    """
    global _current_db

    # Валидация расширения
    if not file.filename or not file.filename.lower().endswith(".db"):
        return UploadResponse(
            success=False,
            error="Принимаются только .db файлы"
        )

    # Читаем содержимое
    content = await file.read()
    if not content:
        return UploadResponse(success=False, error="Пустой файл")

    # Сохраняем файл
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    save_path = UPLOAD_DIR / file.filename

    # Уникальное имя при конфликте
    counter = 1
    while save_path.exists():
        stem = Path(file.filename).stem
        ext = Path(file.filename).suffix
        save_path = UPLOAD_DIR / f"{stem}_{counter}{ext}"
        counter += 1

    try:
        save_path.write_bytes(content)
    except OSError as e:
        return UploadResponse(
            success=False,
            error=f"Не удалось сохранить файл: {e}"
        )

    # Валидация: это реальная SQLite БД?
    try:
        conn = sqlite3.connect(str(save_path))
        conn.execute("SELECT 1")
        conn.close()
    except Exception:
        save_path.unlink(missing_ok=True)
        return UploadResponse(
            success=False,
            error="Файл не является валидной SQLite базой данных"
        )

    # Устанавливаем как активную БД
    _current_db = str(save_path)

    return UploadResponse(
        success=True,
        name=save_path.name,
        original_name=file.filename,
    )


@app.post("/api/init-demo-db", response_model=UploadResponse)
async def init_demo_db():
    """Инициализация встроенной демо-БД (одним кликом)."""
    global _current_db
    demo_path = str(DEFAULT_DB)

    if not os.path.exists(demo_path):
        try:
            _init_demo_database()
        except Exception as e:
            return UploadResponse(
                success=False,
                error=f"Не удалось создать демо-БД: {e}"
            )

    if not os.path.exists(demo_path):
        return UploadResponse(
            success=False,
            error="Не удалось создать демо-БД"
        )

    _current_db = demo_path
    return UploadResponse(
        success=True,
        name=DEFAULT_DB.name,
        original_name="demo (тестовая компания)",
    )


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Проверка состояния системы."""
    db_path = _get_db_path()
    db_loaded = os.path.exists(db_path)
    api_key = os.environ.get("GEMINI_API_KEY", "")

    # Проверяем .env если ключ не в окружении
    if not api_key:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.environ.get("GEMINI_API_KEY", "")
        except ImportError:
            pass

    return HealthResponse(
        status="ok",
        db_loaded=db_loaded,
        db_path=db_path if db_loaded else None,
        api_key_configured=bool(api_key),
    )


@app.get("/api/schema", response_model=SchemaResponse)
async def get_schema():
    """Получить схему базы данных."""
    db_path = _get_db_path()

    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="База данных не найдена")

    try:
        schema = introspect_schema(db_path)
        summary = get_schema_summary(schema)
        return SchemaResponse(
            tables=summary,
            db_path=db_path,
            db_loaded=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка чтения схемы: {e}")


@app.post("/api/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """
    Обработать NL-запрос: преобразовать в SQL и выполнить.
    
    Pipeline:
    1. Preprocessing (очистка текста)
    2. Schema Introspection (чтение схемы БД)
    3. Prompt Building (сборка промпта для LLM)
    4. LLM Generation (Gemini генерирует SQL)
    5. Validation (проверка безопасности)
    6. Execution (выполнение SQL)
    """
    db_path = _get_db_path()

    if not os.path.exists(db_path):
        raise HTTPException(
            status_code=404,
            detail="База данных не найдена. Загрузите .db файл."
        )

    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Запрос не может быть пустым")

    result = process_nl_query(request.query, db_path)

    return QueryResponse(**result)


# === Статические файлы ===

website_dir = BASE_DIR / "website"
if website_dir.exists():
    app.mount("/", StaticFiles(directory=str(website_dir), html=True), name="static")


# === Точка входа для прямого запуска ===

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
