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
    
    # Извлекаем числа для LIMIT (топ N)
    numbers = query_info.get("numbers", [])

    # Определяем SELECT часть
    has_project = "project" in text or "проект" in text
    has_department = "отдел" in text or "department" in text or "кажд" in text
    
    # Определяем алиас для ORDER BY (должен совпадать с выходным алиасом SELECT)
    order_alias = None
    
    # Проверяем, что подразумевается под "самый/больше всего" - агрегация или simple select
    has_top_intent = False
    if "больше всего" in text or "самый" in text or "самых" in text or "наибольшее" in text:
        has_top_intent = True
    
    if qtype == "count":
        if "comments" in tables and "задач" in text:
            select = "t.task_name, COUNT(c.comment_id) AS comment_count"
            order_alias = "comment_count"
        elif has_project and "projects" in tables and "tasks" in tables:
            select = "p.project_name, COUNT(t.task_id) AS task_count"
            order_alias = "task_count"
        else:
            select = "COUNT(*) AS count"
            order_alias = "count"
    elif qtype == "aggregate":
        if "средн" in text or "avg" in text or "average" in text:
            if "зарплат" in text or "salary" in text:
                if has_department:
                    select = "department, AVG(salary) AS avg_value"
                else:
                    select = "AVG(salary) AS avg_value"
                order_alias = "avg_value"
            elif "бюджет" in text or "budget" in text:
                if has_department:
                    select = "department, AVG(budget) AS avg_value"
                else:
                    select = "AVG(budget) AS avg_value"
                order_alias = "avg_value"
            else:
                select = "AVG(salary) AS avg_value"
                order_alias = "avg_value"
        elif "сумм" in text or "sum" in text or "общ" in text or "total" in text:
            if "зарплат" in text or "salary" in text:
                select = "SUM(salary) AS total"
            elif "бюджет" in text or "budget" in text:
                if has_department:
                    select = "department, SUM(budget) AS total"
                else:
                    select = "SUM(budget) AS total"
            else:
                select = "SUM(salary) AS total"
            order_alias = "total"
        elif "макс" in text or "max" in text:
            if "зарплат" in text or "salary" in text:
                select = "MAX(salary) AS max_value"
            elif "бюджет" in text or "budget" in text:
                select = "MAX(budget) AS max_value"
            else:
                select = "MAX(salary) AS max_value"
            order_alias = "max_value"
        elif "мин" in text or "min" in text:
            select = "MIN(salary) AS min_value"
            order_alias = "min_value"
        else:
            select = "*"
    else:
        select = "*"

    # Определяем FROM и JOIN
    if len(tables) > 1 or (len(tables) == 1 and qtype == "count" and has_project):
        if "comments" in tables:
            if "tasks" in tables:
                if "кажд" in text or "each" in text or "per" in text:
                    from_clause = (
                        "FROM tasks t "
                        "LEFT JOIN comments c ON t.task_id = c.task_id"
                    )
                else:
                    from_clause = (
                        "FROM comments c "
                        "JOIN tasks t ON c.task_id = t.task_id"
                    )
            else:
                from_clause = "FROM comments"
        elif qtype == "count" and has_project and "projects" in tables and "tasks" in tables:
            # Count tasks per project - use LEFT JOIN to include projects with 0 tasks
            from_clause = (
                "FROM projects p "
                "LEFT JOIN tasks t ON p.project_id = t.project_id"
            )
        elif "employees" in tables and "tasks" in tables and "projects" in tables:
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
        else:
            from_clause = f"FROM {main_table}"
    else:
        from_clause = f"FROM {main_table}"

    # WHERE условия
    where_parts = []
    for field, info in conds.items():
        if field == "salary":
            if main_table == "projects":
                # Generic > N on projects means budget, not salary
                where_parts.append(f"budget {info['op']} {info['value']}")
            else:
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
            # Determine which table's status column to use
            # Only use prefix if there's a JOIN (multiple tables)
            has_join = "JOIN" in from_clause
            if has_join and len(tables) > 1:
                has_tasks = "tasks" in tables
                has_projects = "projects" in tables
                if has_tasks and has_projects:
                    # Both tables have status - check context
                    if "задач" in text or "task" in text:
                        where_parts.append(f"t.status = '{info['value']}'")
                    else:
                        where_parts.append(f"p.status = '{info['value']}'")
                elif has_tasks:
                    where_parts.append(f"t.status = '{info['value']}'")
                elif has_projects:
                    where_parts.append(f"p.status = '{info['value']}'")
                else:
                    where_parts.append(f"status = '{info['value']}'")
            else:
                where_parts.append(f"status = '{info['value']}'")
        elif field == "assignee_id":
            if info['op'] == 'is_null':
                where_parts.append("assignee_id IS NULL")
        elif field == "due_date":
            if info['op'] == 'overdue':
                where_parts.append("due_date < date('now')")
        elif field == "task_id":
            if info['op'] == '=':
                where_parts.append(f"t.task_id = {info['value']}")
        elif field == "project_id":
            if info['op'] == '=':
                where_parts.append(f"p.project_id = {info['value']}")

    # Также проверяем упоминания отдела в entities
    # Если нужен department, но его нет в основной таблице - добавляем JOIN к employees
    needs_department_join = False
    dep_filter_value = None
    for ent in query_info["entities"]:
        if ent.startswith("department:"):
            dep_filter_value = ent.split(":", 1)[1]
    
    if dep_filter_value:
        if not any("department" in w for w in where_parts):
            has_employees_in_from = "employees" in from_clause
            if has_employees_in_from:
                where_parts.append(f"department = '{dep_filter_value}'")
            else:
                # Only add department join if the query has explicit department context
                has_dept_context = any(ctx in text for ctx in ["из", "в", "отдел", "department", "dep"])
                if has_dept_context:
                    needs_department_join = True
    
    if needs_department_join and dep_filter_value:
        # Add employee join for department filter
        # Determine the correct alias for the join condition
        if "comments" in tables:
            if "tasks" in tables and ("JOIN tasks" in from_clause or "JOIN tasks" in from_clause.upper()):
                # comments + tasks - tasks is aliased as t
                from_clause += " JOIN employees e ON t.assignee_id = e.employee_id"
            else:
                # comments only - join via author_id
                from_clause += " JOIN employees e ON comments.author_id = e.employee_id"
        elif "tasks" in tables:
            if "JOIN" in from_clause.upper():
                # tasks is aliased as t in JOINs
                from_clause += " JOIN employees e ON t.assignee_id = e.employee_id"
            else:
                # tasks is the main table without alias
                from_clause += " JOIN employees e ON tasks.assignee_id = e.employee_id"
        else:
            from_clause += " JOIN employees e ON e.employee_id = e.employee_id"
        where_parts.append(f"e.department = '{dep_filter_value}'")
    
    where = ""
    if where_parts:
        where = "WHERE " + " AND ".join(where_parts)

    # GROUP BY - определяем колонку для группировки
    has_department = "отдел" in text or "department" in text
    has_status = "статус" in text or "status" in text
    has_position = "должност" in text or "position" in text
    
    group_col = None
    if has_department:
        group_col = "department"
    elif has_position:
        group_col = "position"
    elif has_status and "projects" in tables:
        group_col = "status"
    
    group_by = ""
    needs_group_by = False
    
    if "комментари" in text and "задач" in text and "кажд" in text:
        group_by = "GROUP BY t.task_name"
        needs_group_by = True
    elif qtype == "count" and has_project and "projects" in tables and "tasks" in tables:
        group_by = "GROUP BY p.project_name"
        needs_group_by = True
    elif qtype == "aggregate" and group_col:
        # Проверяем что колонка существует в основной таблице
        if group_col == "department":
            if "employees" in tables or main_table == "employees":
                group_by = "GROUP BY department"
                needs_group_by = True
        elif group_col == "position":
            if "employees" in tables or main_table == "employees":
                group_by = "GROUP BY position"
                needs_group_by = True
        elif group_col == "status":
            group_by = "GROUP BY status"
            needs_group_by = True
        else:
            group_by = f"GROUP BY {group_col}"
            needs_group_by = True
    elif has_department and "сколько" in text and "кажд" in text:
        if "employees" in tables or main_table == "employees":
            group_by = "GROUP BY department"
            needs_group_by = True
    elif has_status and "сколько" in text and "кажд" in text:
        group_by = "GROUP BY status"
        needs_group_by = True
    
    # Если SELECT содержит GROUP BY-зависимые колонки, но GROUP BY не задан - убираем их
    if not needs_group_by and not group_by:
        # Убираем department из SELECT если нет GROUP BY
        if select.startswith("department,"):
            select = select.replace("department, ", "", 1)
        # Убираем p.project_name из SELECT если нет GROUP BY
        if "p.project_name" in select and "GROUP BY" not in group_by:
            select = "*"
        # Убираем t.task_name из SELECT если нет GROUP BY
        if "t.task_name" in select and "GROUP BY" not in group_by:
            select = "*"

    # ORDER BY и LIMIT для топа
    order_limit = ""
    if "оплач" in text or ("высокоопл" in text):
        if "сам" in text or "больше всего" in text or "топ" in text or "top" in text:
            order_limit = "ORDER BY salary DESC"
            if not "все" in text:
                order_limit += " LIMIT 5"
    if not order_limit:
        if "топ" in text or "top" in text or "best" in text:
            if select == "*":
                # For SELECT * with "top", try to order by a sensible column
                if "зарплат" in text or "salary" in text:
                    limit_val = numbers[0] if numbers else 5
                    order_limit = f"ORDER BY salary DESC LIMIT {limit_val}"
                elif "бюджет" in text or "budget" in text:
                    limit_val = numbers[0] if numbers else 5
                    order_limit = f"ORDER BY budget DESC LIMIT {limit_val}"
            else:
                # Use the actual alias from SELECT for ordering
                order_col = order_alias if order_alias else "count"
                limit_val = numbers[0] if numbers else 3
                order_limit = f"ORDER BY {order_col} DESC LIMIT {limit_val}"
        elif "больше всего" in text or "highest" in text:
            # Determine proper ORDER BY based on context
            if order_alias:
                # We have a proper alias from aggregate/count query
                if order_alias == "avg_value":
                    order_limit = "ORDER BY avg_value DESC LIMIT 1"
                elif order_alias == "max_value":
                    order_limit = "ORDER BY max_value DESC LIMIT 1"
                elif order_alias == "min_value":
                    order_limit = "ORDER BY min_value ASC LIMIT 1"
                elif order_alias == "total":
                    order_limit = "ORDER BY total DESC LIMIT 1"
                elif order_alias == "comment_count":
                    order_limit = "ORDER BY comment_count DESC LIMIT 1"
                elif order_alias == "task_count":
                    order_limit = "ORDER BY task_count DESC LIMIT 1"
                elif order_alias == "count":
                    order_limit = "ORDER BY count DESC LIMIT 1"
                else:
                    order_limit = f"ORDER BY {order_alias} DESC LIMIT 1"
            elif has_top_intent:
                # For SELECT * queries with "больше всего" - skip ORDER BY
                # (no aggregation column to sort by)
                pass
        elif "сам" in text and ("высок" in text or "дорог" in text):
            if "зарплат" in text or "salary" in text or main_table == "employees":
                order_limit = "ORDER BY salary DESC LIMIT 5"
            elif "бюджет" in text or "budget" in text or main_table == "projects":
                order_limit = "ORDER BY budget DESC LIMIT 5"
            elif order_alias:
                order_limit = f"ORDER BY {order_alias} DESC LIMIT 5"
            else:
                order_limit = "ORDER BY salary DESC LIMIT 5"

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
