"""
server.py — FastAPI сервер NL2SQL системы.
"""
import os
import sys
import tempfile
import sqlite3
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import settings  # config.load_env() called automatically at import

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.pipeline import process_nl_query
from core.schema_manager import introspect_schema, get_schema_summary

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger("server")


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
    errors: list[str] = []


BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = Path(tempfile.gettempdir()) / "nl2sql_uploads"
_current_db = None

app = FastAPI(
    title="NL2SQL API",
    description="NL в SQL через нейросеть (OpenRouter)",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    logger.info("Server starting...")
    logger.info(f"Model: {settings.OPENROUTER_MODEL}")
    logger.info(f"API key configured: {bool(settings.OPENROUTER_API_KEY)}")
    if errors := settings.validate():
        for err in errors:
            logger.warning(f"Config: {err}")
    else:
        logger.info("Configuration OK")


def _get_db_path() -> str:
    global _current_db
    if _current_db and os.path.exists(_current_db):
        return _current_db
    if settings.DB_PATH and os.path.exists(settings.DB_PATH):
        _current_db = settings.DB_PATH
    return _current_db


@app.post("/api/upload-database", response_model=UploadResponse)
async def upload_database(file: UploadFile = File(...)):
    global _current_db
    if not file.filename or not file.filename.lower().endswith(".db"):
        return UploadResponse(success=False, error="Принимаются только .db файлы")
    content = await file.read()
    if not content:
        return UploadResponse(success=False, error="Пустой файл")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    save_path = UPLOAD_DIR / file.filename
    counter = 1
    while save_path.exists():
        save_path = UPLOAD_DIR / f"{Path(file.filename).stem}_{counter}{Path(file.filename).suffix}"
        counter += 1
    try:
        save_path.write_bytes(content)
    except OSError as e:
        return UploadResponse(success=False, error=f"Не удалось сохранить: {e}")
    try:
        conn = sqlite3.connect(str(save_path))
        conn.execute("SELECT 1")
        conn.close()
    except Exception:
        save_path.unlink(missing_ok=True)
        return UploadResponse(success=False, error="Файл не является валидной SQLite базой")
    _current_db = str(save_path)
    logger.info(f"Database uploaded: {save_path.name}")
    return UploadResponse(success=True, name=save_path.name, original_name=file.filename)


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    path = _get_db_path()
    db_loaded = path and os.path.exists(path)
    errors = settings.validate()
    return HealthResponse(
        status="ok",
        db_loaded=db_loaded,
        db_path=path if db_loaded else None,
        api_key_configured=bool(settings.OPENROUTER_API_KEY),
        errors=errors,
    )


@app.get("/api/schema", response_model=SchemaResponse)
async def get_schema():
    db_path = _get_db_path()
    if not db_path or not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="База данных не найдена")
    try:
        schema = introspect_schema(db_path)
        summary = get_schema_summary(schema)
        return SchemaResponse(tables=summary, db_path=db_path, db_loaded=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка чтения схемы: {e}")


@app.post("/api/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    db_path = _get_db_path()
    if not db_path or not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="База данных не найдена. Загрузите .db файл.")
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Запрос не может быть пустым")
    if not settings.OPENROUTER_API_KEY:
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY не настроен. Сервер не может обрабатывать запросы.")
    logger.info(f"Query: {request.query[:100]}")
    result = process_nl_query(request.query, db_path)
    return QueryResponse(**result)


website_dir = BASE_DIR / "website"
if website_dir.exists():
    app.mount("/", StaticFiles(directory=str(website_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
