"""
prompt_builder.py — Сборка промпта для LLM.
Инжектирует: system-инструкции, схему БД, few-shot примеры, запрос пользователя.
Цель: заставить LLM генерировать ТОЛЬКО валидный SELECT SQL.
"""

def _system_instructions(dialect: str = "sqlite") -> str:
    """Системные инструкции с учётом диалекта СУБД."""
    dialect_hints = {
        "sqlite": "для SQLite",
        "postgresql": "для PostgreSQL (используй двойные кавычки для идентификаторов, ILIKE для регистронезависимого поиска, синтаксис PostgreSQL)",
        "mysql": "для MySQL (используй обратные кавычки для идентификаторов, синтаксис MySQL)",
    }
    dialect_text = dialect_hints.get(dialect, f"для {dialect}")
    return f"""Ты — SQL-эксперт. Твоя задача — преобразовать запрос на русском языке в корректный SQL-запрос {dialect_text}.

ПРАВИЛА:
1. Генерируй ТОЛЬКО SELECT-запросы. Никаких INSERT/UPDATE/DELETE/DROP.
2. Используй ТОЛЬКО таблицы и колонки из предоставленной схемы базы данных.
3. Не выдумывай таблицы или колонки, которых нет в схеме.
4. Если запрос неоднозначный — выбери наиболее вероятную интерпретацию.
5. Для агрегаций (COUNT, SUM, AVG, MAX, MIN) всегда используй GROUP BY для неагрегированных колонок.
6. Для JOIN используй внешние ключи, указанные в схеме.
7. Возвращай ТОЛЬКО SQL-запрос, без пояснений, без markdown."""

FEW_SHOT_EXAMPLES = [
    {
        "query": "Найди всех сотрудников отдела разработки.",
        "sql": "SELECT * FROM employees WHERE department = 'Разработка'",
    },
    {
        "query": "Покажи среднюю зарплату по отделам.",
        "sql": "SELECT department, AVG(salary) AS avg_salary FROM employees GROUP BY department",
    },
    {
        "query": "Сколько задач в каждом проекте?",
        "sql": "SELECT p.project_name, COUNT(t.task_id) AS task_count FROM projects p LEFT JOIN tasks t ON p.project_id = t.project_id GROUP BY p.project_name",
    },
    {
        "query": "Найди сотрудников с зарплатой выше 100000.",
        "sql": "SELECT * FROM employees WHERE salary > 100000",
    },
    {
        "query": "Топ-5 проектов по бюджету.",
        "sql": "SELECT project_name, budget FROM projects ORDER BY budget DESC LIMIT 5",
    },
    {
        "query": "Покажи задачи со статусом 'completed'.",
        "sql": "SELECT * FROM tasks WHERE status = 'completed'",
    },
    {
        "query": "Сотрудники и количество их задач.",
        "sql": "SELECT e.full_name, COUNT(t.task_id) AS task_count FROM employees e LEFT JOIN tasks t ON e.employee_id = t.assignee_id GROUP BY e.full_name",
    },
]


def build_prompt(
    user_query: str,
    schema_text: str,
    include_few_shot: bool = True,
    dialect: str = "sqlite",
) -> str:
    """
    Собирает полный промпт для отправки в LLM.

    Структура промпта:
    1. System instructions (роль, правила, ограничения)
    2. Схема базы данных
    3. Few-shot примеры (опционально, для повышения точности)
    4. Запрос пользователя
    """
    parts = []

    # 1. Системные инструкции
    parts.append(_system_instructions(dialect))

    # 2. Схема БД
    parts.append("\n--- СХЕМА БАЗЫ ДАННЫХ ---")
    parts.append(schema_text)

    # 3. Few-shot примеры
    if include_few_shot:
        parts.append("\n--- ПРИМЕРЫ ---")
        # Chain-of-Thought: показываем reasoning для первых 2 примеров
        for i, example in enumerate(FEW_SHOT_EXAMPLES):
            if i < 2:
                parts.append(
                    f"\nЗапрос: {example['query']}\n"
                    f"SQL: {example['sql']}"
                )
            else:
                parts.append(
                    f"Запрос: {example['query']}\n"
                    f"SQL: {example['sql']}"
                )

    # 4. Запрос пользователя
    parts.append("\n--- ЗАПРОС ---")
    parts.append(user_query)
    parts.append("\nSQL:")

    return "\n".join(parts)


def build_comparison_prompt(
    user_query: str,
    schema_text: str,
) -> dict:
    """
    Собирает два варианта промпта: с few-shot и без.
    Для сравнительного анализа в курсовой.
    """
    return {
        "with_few_shot": build_prompt(user_query, schema_text, include_few_shot=True),
        "without_few_shot": build_prompt(user_query, schema_text, include_few_shot=False),
    }
