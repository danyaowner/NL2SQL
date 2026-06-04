"""
pipeline.py — Оркестрация полного NL→SQL pipeline.
Связывает все модули: preprocessing → schema → prompt → LLM → validation → execution.
"""
import time
from typing import Dict, Any, Optional

from .preprocessor import clean_query
from .schema_manager import introspect_schema, format_schema_for_prompt, get_schema_summary
from .prompt_builder import build_prompt
from .llm_client import generate_sql
from .sql_validator import validate, get_sql_info
from .executor import execute_query

def process_nl_query(
    user_query: str,
    db_path: str,
    api_key: Optional[str] = None,
    adapter: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Полный pipeline обработки запроса на естественном языке.

    Этапы:
    1. Preprocessing — очистка текста
    2. Schema Introspection — чтение схемы БД
    3. Prompt Building — сборка промпта для LLM
    4. LLM Generation — генерация SQL через OpenRouter
    5. Validation — проверка безопасности и синтаксиса
    6. Execution — выполнение SQL и получение результатов

    Returns:
        {
            "query": str,          # оригинальный запрос
            "cleaned": str,         # очищенный запрос
            "sql": str | None,      # сгенерированный SQL
            "formatted_sql": str,   # отформатированный SQL
            "rows": list | None,    # результаты запроса
            "columns": list,        # названия колонок
            "error": str | None,    # ошибка (если есть)
            "steps": list,          # пошаговый лог
            "timing_ms": int,       # общее время выполнения
            "success": bool,        # успех
        }
    """
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

    # === Шаг 1: Preprocessing ===
    step_start = time.time()
    cleaned = clean_query(user_query)
    result["cleaned"] = cleaned

    if not cleaned:
        result["error"] = "Пустой запрос"
        result["steps"].append({
            "name": "Preprocessing",
            "status": "error",
            "detail": "Пустой запрос",
            "ms": int((time.time() - step_start) * 1000),
        })
        return result

    result["steps"].append({
        "name": "Preprocessing",
        "status": "success",
        "detail": f"Запрос очищен: '{cleaned}'",
        "ms": int((time.time() - step_start) * 1000),
    })

    # === Шаг 2: Schema Introspection ===
    step_start = time.time()
    try:
        if adapter and adapter.is_connected:
            schema = adapter.get_full_schema()
        else:
            schema = introspect_schema(db_path)
        schema_text = format_schema_for_prompt(schema)
        schema_summary = get_schema_summary(schema)
    except Exception as e:
        result["error"] = f"Ошибка чтения схемы: {e}"
        result["steps"].append({
            "name": "Schema",
            "status": "error",
            "detail": str(e),
            "ms": int((time.time() - step_start) * 1000),
        })
        return result

    result["steps"].append({
        "name": "Schema",
        "status": "success",
        "detail": f"Найдено таблиц: {len(schema)}",
        "tables": list(schema.keys()),
        "ms": int((time.time() - step_start) * 1000),
    })

    # === Шаг 3: Prompt Building ===
    step_start = time.time()
    dialect = adapter.dialect if adapter else "sqlite"
    prompt = build_prompt(cleaned, schema_text, dialect=dialect)
    result["steps"].append({
        "name": "Prompt",
        "status": "success",
        "detail": f"Промпт собран ({len(prompt)} символов)",
        "ms": int((time.time() - step_start) * 1000),
    })

    # === Шаг 4: LLM Generation ===
    step_start = time.time()
    sql = generate_sql(prompt)
    result["sql"] = sql

    if not sql:
        result["error"] = "LLM не смогла сгенерировать SQL. Проверьте OPENROUTER_API_KEY."
        result["steps"].append({
            "name": "LLM Generation",
            "status": "error",
            "detail": "Не получен SQL от OpenRouter",
            "ms": int((time.time() - step_start) * 1000),
        })
        return result

    result["steps"].append({
        "name": "LLM Generation",
        "status": "success",
        "detail": f"SQL сгенерирован через OpenRouter",
        "ms": int((time.time() - step_start) * 1000),
    })

    # === Шаг 5: Validation ===
    step_start = time.time()
    is_valid, validation_result = validate(sql)

    if not is_valid:
        result["error"] = f"SQL не прошёл валидацию: {validation_result}"
        result["steps"].append({
            "name": "Validation",
            "status": "error",
            "detail": validation_result,
            "ms": int((time.time() - step_start) * 1000),
        })
        return result

    result["formatted_sql"] = validation_result
    sql_info = get_sql_info(validation_result)

    result["steps"].append({
        "name": "Validation",
        "status": "success",
        "detail": "SQL корректен и безопасен",
        "sql_info": sql_info,
        "ms": int((time.time() - step_start) * 1000),
    })

    # === Шаг 6: Execution ===
    step_start = time.time()
    if adapter and adapter.is_connected:
        rows, exec_error = adapter.execute(sql)
    else:
        rows, exec_error = execute_query(db_path, sql)

    if exec_error:
        result["error"] = f"Ошибка выполнения: {exec_error}"
        result["steps"].append({
            "name": "Execution",
            "status": "error",
            "detail": exec_error,
            "ms": int((time.time() - step_start) * 1000),
        })
        return result

    result["rows"] = rows
    if rows:
        result["columns"] = list(rows[0].keys())

    result["steps"].append({
        "name": "Execution",
        "status": "success",
        "detail": f"Получено {len(rows) if rows else 0} строк",
        "ms": int((time.time() - step_start) * 1000),
    })

    # === Финал ===
    result["success"] = True
    result["timing_ms"] = int((time.time() - start_time) * 1000)

    return result
