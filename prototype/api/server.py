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
from core.db_adapter import create_db_adapter, create_adapter, DBConnectionInfo

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

class ConnectRequest(BaseModel):
    db_type: str = "postgresql"
    host: str = "localhost"
    port: int = 5432
    user: str = ""
    password: str = ""
    database: str = ""

class ConnectResponse(BaseModel):
    success: bool
    name: str | None = None
    db_type: str | None = None
    error: str | None = None

class HealthResponse(BaseModel):
    status: str
    db_loaded: bool
    db_path: str | None = None
    api_key_configured: bool
    errors: list[str] = []


BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = Path(tempfile.gettempdir()) / "nl2sql_uploads"
_current_db = None          # путь к .db файлу для SQLite
_current_conn_info = None   # DBConnectionInfo для remote СУБД

app = FastAPI(
    title="NL2SQL API",
    description="NL в SQL через нейросеть (Google Gemini)",
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
    logger.info(f"Model: {settings.GEMINI_MODEL}")
    logger.info(f"API key configured: {bool(settings.GEMINI_API_KEY)}")
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


def _get_active_adapter():
    """Вернуть активный DatabaseAdapter или None."""
    if _current_conn_info:
        adapter = create_db_adapter(
            db_type=_current_conn_info.db_type,
            host=_current_conn_info.host,
            port=_current_conn_info.port,
            user=_current_conn_info.user,
            password=_current_conn_info.password,
            database=_current_conn_info.database,
        )
        ok, err = adapter.connect()
        if ok:
            return adapter
        return None
    db_path = _get_db_path()
    if db_path:
        adapter = create_adapter(db_path)
        ok, err = adapter.connect()
        if ok:
            return adapter
    return None


@app.post("/api/connect-database", response_model=ConnectResponse)
async def connect_database(req: ConnectRequest):
    """Подключение к удалённой СУБД (PostgreSQL/MySQL)."""
    global _current_db, _current_conn_info
    if not req.db_type or req.db_type not in ("postgresql", "mysql"):
        return ConnectResponse(success=False, error="Поддерживаются только PostgreSQL и MySQL")
    if not req.host or not req.user or not req.database:
        return ConnectResponse(success=False, error="Заполните host, user и database")
    port = req.port
    if not port:
        port = 5432 if req.db_type == "postgresql" else 3306
    info = DBConnectionInfo(
        db_type=req.db_type,
        host=req.host,
        port=port,
        user=req.user,
        password=req.password,
        database=req.database,
    )
    adapter = create_db_adapter(
        db_type=info.db_type,
        host=info.host,
        port=info.port,
        user=info.user,
        password=info.password,
        database=info.database,
    )
    ok, err = adapter.connect()
    if not ok:
        return ConnectResponse(success=False, error=err or "Не удалось подключиться")
    adapter.close()
    _current_db = None
    _current_conn_info = info
    name = f"{info.db_type}://{info.host}:{info.port}/{info.database}"
    logger.info(f"Connected to {name}")
    return ConnectResponse(success=True, name=name, db_type=info.db_type)


@app.post("/api/upload-database", response_model=UploadResponse)
async def upload_database(file: UploadFile = File(...)):
    global _current_db, _current_conn_info
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
    _current_conn_info = None  # сбрасываем remote-подключение
    logger.info(f"Database uploaded: {save_path.name}")
    return UploadResponse(success=True, name=save_path.name, original_name=file.filename)


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    global _current_conn_info
    path = _get_db_path() or ""
    db_loaded = (bool(path) and os.path.exists(path)) or _current_conn_info is not None
    errors = settings.validate()
    return HealthResponse(
        status="ok",
        db_loaded=db_loaded,
        db_path=(
            _current_conn_info.display_name
            if _current_conn_info
            else (path if db_loaded else None)
        ),
        api_key_configured=bool(settings.GEMINI_API_KEY),
        errors=errors,
    )


@app.get("/api/schema", response_model=SchemaResponse)
async def get_schema():
    global _current_conn_info
    # Проверяем remote-подключение
    if _current_conn_info:
        adapter = _get_active_adapter()
        if not adapter:
            raise HTTPException(status_code=500, detail="Не удалось подключиться к удалённой БД")
        try:
            schema = adapter.get_full_schema()
            adapter.close()
            return SchemaResponse(tables=schema, db_path=_current_conn_info.display_name, db_loaded=True)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка чтения схемы: {e}")
    # SQLite через файл
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
    global _current_conn_info
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Запрос не может быть пустым")
    if not settings.GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY не настроен. Сервер не может обрабатывать запросы.")
    # Remote СУБД
    if _current_conn_info:
        logger.info(f"Query (remote {_current_conn_info.db_type}): {request.query[:100]}")
        result = process_nl_query(request.query, _current_conn_info)
        return QueryResponse(**result)
    # SQLite через файл
    db_path = _get_db_path()
    if not db_path or not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="База данных не найдена. Загрузите .db файл или подключитесь к СУБД.")
    logger.info(f"Query (SQLite): {request.query[:100]}")
    result = process_nl_query(request.query, db_path)
    return QueryResponse(**result)


website_dir = BASE_DIR / "website"
if website_dir.exists():
    app.mount("/", StaticFiles(directory=str(website_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
