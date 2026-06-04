"""
pipeline.py — Оркестрация полного NL->SQL pipeline.
"""
import time
import logging
from typing import Dict, Any, Optional

from .preprocessor import clean_query
from .schema_manager import introspect_schema, format_schema_for_prompt, get_schema_summary
from .prompt_builder import build_prompt
from .llm_client import generate_sql
from .sql_validator import validate, get_sql_info
from .executor import execute_query

logger = logging.getLogger("pipeline")


def process_nl_query(
    user_query: str,
    db_path: str,
    adapter: Optional[Any] = None,
) -> Dict[str, Any]:
    start_time = time.time()
    result = {
        "query": user_query,
        "cleaned": "",
        "sql": None,
        "formatted_sql": None,
        "rows": None,
        "columns": [],
        "error": None,
        "steps": [],
        "timing_ms": 0,
        "success": False,
    }

    def add_step(name, status, detail, ms=0, **extra):
        step = {"name": name, "status": status, "detail": detail, "ms": ms}
        step.update(extra)
        result["steps"].append(step)

    # === Шаг 1: Preprocessing ===
    t = time.time()
    cleaned = clean_query(user_query)
    result["cleaned"] = cleaned
    if not cleaned:
        result["error"] = "Пустой запрос"
        add_step("Preprocessing", "error", "Пустой запрос", ms=int((time.time()-t)*1000))
        return result
    add_step("Preprocessing", "success", "Запрос очищен", ms=int((time.time()-t)*1000))

    # === Шаг 2: Schema ===
    t = time.time()
    try:
        if adapter and adapter.is_connected:
            schema = adapter.get_full_schema()
        else:
            schema = introspect_schema(db_path)
        schema_text = format_schema_for_prompt(schema)
        add_step("Schema", "success", f"Найдено таблиц: {len(schema)}", ms=int((time.time()-t)*1000), tables=list(schema.keys()))
    except Exception as e:
        result["error"] = f"Ошибка чтения схемы: {e}"
        add_step("Schema", "error", str(e), ms=int((time.time()-t)*1000))
        return result

    # === Шаг 3: Prompt ===
    t = time.time()
    dialect = adapter.dialect if adapter else "sqlite"
    prompt = build_prompt(cleaned, schema_text, dialect=dialect)
    add_step("Prompt", "success", f"Промпт ({len(prompt)} символов)", ms=int((time.time()-t)*1000))

    # === Шаг 4: LLM Generation ===
    t = time.time()
    sql, llm_error = generate_sql(prompt)
    result["sql"] = sql
    elapsed = int((time.time()-t)*1000)

    if not sql:
        error_msg = llm_error or "Неизвестная ошибка LLM"
        result["error"] = f"Ошибка генерации SQL: {error_msg}"
        add_step("LLM Generation", "error", error_msg, ms=elapsed)
        return result

    add_step("LLM Generation", "success", "SQL сгенерирован", ms=elapsed)

    # === Шаг 5: Validation ===
    t = time.time()
    is_valid, validation_result = validate(sql)
    if not is_valid:
        result["error"] = f"SQL не прошёл валидацию: {validation_result}"
        add_step("Validation", "error", validation_result, ms=int((time.time()-t)*1000))
        return result
    result["formatted_sql"] = validation_result
    add_step("Validation", "success", "SQL корректен и безопасен", ms=int((time.time()-t)*1000))

    # === Шаг 6: Execution ===
    t = time.time()
    if adapter and adapter.is_connected:
        rows, exec_error = adapter.execute(sql)
    else:
        rows, exec_error = execute_query(db_path, sql)
    if exec_error:
        result["error"] = f"Ошибка выполнения: {exec_error}"
        add_step("Execution", "error", exec_error, ms=int((time.time()-t)*1000))
        return result
    result["rows"] = rows
    if rows:
        result["columns"] = list(rows[0].keys())
    add_step("Execution", "success", f"Получено {len(rows) if rows else 0} строк", ms=int((time.time()-t)*1000))

    result["success"] = True
    result["timing_ms"] = int((time.time()-start_time)*1000)
    return result
