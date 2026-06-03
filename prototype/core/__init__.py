"""
core — модули NL2SQL системы на основе LLM (Google Gemini)
Без keyword matching, вся генерация SQL через нейросеть.
"""

from .pipeline import process_nl_query
from .schema_manager import introspect_schema, format_schema_for_prompt
from .llm_client import generate_sql
from .sql_validator import validate
from .executor import execute_query

__all__ = [
    "process_nl_query",
    "introspect_schema",
    "format_schema_for_prompt",
    "generate_sql",
    "validate",
    "execute_query",
]
