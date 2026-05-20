"""
sql_generator.py -- Генерация SQL-запросов
Режимы: demo (правила) / full (OpenAI API)
"""
import re
import sqlparse
from typing import Optional

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

from schema_selector import SCHEMA

SYSTEM_PROMPT = (
    "Ты - эксперт по SQL. Преобразуй запрос на естественном языке "
    "в SQL-запрос. Используй только указанные таблицы и колонки. "
    "Отвечай только SQL-запросом без пояснений."
)

FEW_SHOT = [
    ("Найди всех сотрудников отдела разработки",
     "SELECT * FROM employees WHERE department = 'Разработка'"),
    ("Покажи проекты с бюджетом более 200000",
     "SELECT * FROM projects WHERE budget > 200000"),
    ("Сколько задач в каждом проекте",
     "SELECT p.project_name, COUNT(t.task_id) AS task_count "
     "FROM projects p LEFT JOIN tasks t ON p.project_id = t.project_id "
     "GROUP BY p.project_name"),
    ("Средняя зарплата по отделам",
     "SELECT department, AVG(salary) AS avg_salary FROM employees GROUP BY department"),
    ("Найди сотрудников с зарплатой выше 100000",
     "SELECT * FROM employees WHERE salary > 100000"),
    ("Топ-3 сотрудников по количеству задач",
     "SELECT e.full_name, COUNT(t.task_id) AS task_count "
     "FROM employees e JOIN tasks t ON e.employee_id = t.assignee_id "
     "GROUP BY e.full_name ORDER BY task_count DESC LIMIT 3"),
]


def _demo_generate(query_info: dict, schema_info: dict) -> str:
    """Генерация SQL по правилам (demo-режим, без API)."""
    tables = schema_info["tables"]
    qtype = query_info["query_type"]
    conds = query_info["conditions"]
    text = query_info["cleaned"].lower()

    # Определяем основную таблицу
    main_table = tables[0] if tables else "employees"

    # Определяем SELECT часть
    if qtype == "count":
        select = "COUNT(*) AS count"
    elif qtype == "aggregate":
        if "средн" in text or "avg" in text or "average" in text:
            if "зарплат" in text or "salary" in text:
                select = "department, AVG(salary) AS avg_value"
            elif "бюджет" in text or "budget" in text:
                select = "AVG(budget) AS avg_value"
            else:
                select = "AVG(salary) AS avg_value"
        elif "сумм" in text or "sum" in text:
            select = "SUM(salary) AS total"
        elif "макс" in text or "max" in text:
            select = "MAX(salary) AS max_value"
        elif "мин" in text or "min" in text:
            select = "MIN(salary) AS min_value"
        else:
            select = "*"
    else:
        select = "*"

    # Определяем FROM и JOIN
    if len(tables) > 1 or (len(tables) == 1 and qtype == "count" and "проект" in text):
        if "employees" in tables and "tasks" in tables and "projects" in tables:
            from_clause = (
                "FROM employees e "
                "JOIN tasks t ON e.employee_id = t.assignee_id "
                "JOIN projects p ON t.project_id = p.project_id"
            )
        elif "tasks" in tables and "employees" in tables:
            from_clause = (
                "FROM employees e "
                "JOIN tasks t ON e.employee_id = t.assignee_id"
            )
        elif "tasks" in tables and "projects" in tables:
            from_clause = (
                "FROM projects p "
                "LEFT JOIN tasks t ON p.project_id = t.project_id"
            )
        elif "comments" in tables and "tasks" in tables:
            from_clause = (
                "FROM comments c "
                "JOIN tasks t ON c.task_id = t.task_id"
            )
        else:
            from_clause = f"FROM {main_table}"
    else:
        from_clause = f"FROM {main_table}"

    # WHERE условия
    where_parts = []
    for field, info in conds.items():
        if field == "salary":
            where_parts.append(f"salary {info['op']} {info['value']}")
        elif field == "budget":
            where_parts.append(f"budget {info['op']} {info['value']}")
        elif field == "department":
            where_parts.append(f"department = '{info['value']}'")
        elif field == "priority":
            if info['op'] == 'in':
                where_parts.append("priority IN ('high', 'critical')")
            else:
                where_parts.append(f"priority = '{info['value']}'")
        elif field == "status":
            where_parts.append(f"status = '{info['value']}'")

    # Также проверяем упоминания отдела в entities
    for ent in query_info["entities"]:
        if ent.startswith("department:"):
            dep = ent.split(":", 1)[1]
            if not any("department" in w for w in where_parts):
                where_parts.append(f"department = '{dep}'")

    where = ""
    if where_parts:
        where = "WHERE " + " AND ".join(where_parts)

    # GROUP BY — фикс: скобки для правильного приоритета
    has_project = "project" in text or "проект" in text
    has_department = "отдел" in text or "department" in text

    group_by = ""
    if qtype == "count" and has_project:
        if "project_name" in str(schema_info.get("columns", {}).get("projects", [])):
            group_by = "GROUP BY p.project_name"
        else:
            group_by = "GROUP BY department"
    elif qtype == "aggregate" and has_department:
        group_by = "GROUP BY department"
    elif has_department and ("кажд" in text or "по" in text):
        group_by = "GROUP BY department"

    # ORDER BY и LIMIT для топа
    order_limit = ""
    if "топ" in text or "top" in text or "best" in text:
        order_limit = "ORDER BY count DESC LIMIT 3"
    elif "больше всего" in text or "highest" in text:
        order_limit = "ORDER BY value DESC LIMIT 1"

    sql = f"SELECT {select} {from_clause} {where} {group_by} {order_limit}"
    sql = re.sub(r"\s+", " ", sql).strip()
    return sqlparse.format(sql, keyword_case="upper", reindent=True)


def _openai_generate(query: str, schema_text: str, api_key: str) -> Optional[str]:
    """Генерация через OpenAI API."""
    if not HAS_OPENAI:
        return None
    try:
        client = openai.OpenAI(api_key=api_key)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.append({"role": "user", "content": f"Schema:\n{schema_text}"})
        for q, s in FEW_SHOT[:3]:
            messages.append({"role": "user", "content": q})
            messages.append({"role": "assistant", "content": s})
        messages.append({"role": "user", "content": query})

        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.2,
            max_tokens=1000,
        )
        content = resp.choices[0].message.content or ""

        # Ищем SQL в markdown-блоке или отдельной строке
        sql = None
        for line in content.strip().split("\n"):
            stripped = line.strip()
            if stripped.upper().startswith(("SELECT", "WITH")):
                sql = stripped
                break
        if not sql:
            # Ищем первый SQL-подобный блок
            lines = content.strip().split("\n")
            # Пропускаем markdown-разметку
            clean_lines = [l for l in lines if not l.strip().startswith("```")]
            for l in clean_lines:
                if l.strip() and not l.strip().startswith(("```", "#", "//", "--")):
                    sql = l.strip()
                    break
        if not sql:
            sql = content.strip()

        if sql:
            return sqlparse.format(sql, keyword_case="upper", reindent=True)
        return None
    except Exception as e:
        return None


def generate(query_info: dict, schema_info: dict,
             mode: str = "demo", api_key: Optional[str] = None) -> Optional[str]:
    """Главная функция генерации."""
    if mode == "full" and api_key:
        sql = _openai_generate(query_info["original"], schema_info["text"], api_key)
        if sql:
            return sql
    return _demo_generate(query_info, schema_info)


if __name__ == "__main__":
    from nl_module import process_query
    from schema_selector import select_schema

    tests = [
        "Найди всех сотрудников отдела разработки",
        "Покажи проекты с бюджетом более 200000",
        "Сколько задач в каждом проекте",
        "Средняя зарплата по отделам",
        "Найди сотрудников с зарплатой выше 100000",
        "Show all employees in the marketing department",
        "Find projects with budget over 300000",
    ]
    for q in tests:
        qi = process_query(q)
        si = select_schema(q)
        sql = generate(qi, si, mode="demo")
        print(f"\nQuery: {q}")
        print(f"  SQL: {sql}")
