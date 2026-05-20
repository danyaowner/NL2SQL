"""
schema_selector.py -- Селекция релевантных таблиц и колонок
Для demo-режима использует ключевые слова, для full-режима эмбеддинги
"""
import re

HAS_SENTENCE_TRANSFORMERS = False
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    pass

SCHEMA = {
    "employees": {
        "description": "Информация о сотрудниках",
        "columns": {
            "employee_id": "ID сотрудника",
            "full_name": "Полное имя",
            "department": "Отдел (Разработка, Продажи, Маркетинг, Бухгалтерия, HR)",
            "position": "Должность",
            "salary": "Зарплата",
            "hire_date": "Дата найма",
            "manager_id": "ID руководителя",
        },
    },
    "projects": {
        "description": "Информация о проектах",
        "columns": {
            "project_id": "ID проекта",
            "project_name": "Название проекта",
            "start_date": "Дата начала",
            "end_date": "Дата окончания",
            "budget": "Бюджет",
            "status": "Статус (active, completed, on_hold)",
        },
    },
    "tasks": {
        "description": "Информация о задачах",
        "columns": {
            "task_id": "ID задачи",
            "task_name": "Название задачи",
            "description": "Описание",
            "assignee_id": "ID исполнителя",
            "project_id": "ID проекта",
            "priority": "Приоритет (low, medium, high, critical)",
            "status": "Статус (open, in_progress, completed)",
            "due_date": "Срок выполнения",
        },
    },
    "comments": {
        "description": "Комментарии к задачам",
        "columns": {
            "comment_id": "ID комментария",
            "task_id": "ID задачи",
            "author_id": "ID автора",
            "comment_text": "Текст",
            "created_at": "Дата создания",
            "is_internal": "Внутренний (0/1)",
        },
    },
}

TABLE_KEYWORDS = {
    "employees": ["сотрудник","работник","персонал","зарплат","salary","отдел","department","должност","position","employee","найм","hire","manager","имя"],
    "projects": ["проект","project","бюджет","budget","status"],
    "tasks": ["задач","task","приоритет","priority","срок","due","assignee","выполнен","completed"],
    "comments": ["комментар","comment","автор","author","created_at"],
}

TABLE_RELATIONS = {
    "comments": ["tasks", "employees"],
    "tasks": ["employees", "projects"],
}

def select_tables_keyword(query: str) -> list:
    """Выбор таблиц по ключевым словам."""
    tl = query.lower()
    scores = []
    for table, kws in TABLE_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in tl)
        if table in tl:
            score += 3
        if score > 0:
            scores.append((table, score))
    if not scores:
        return ["employees", "projects"]
    scores.sort(key=lambda x: -x[1])
    selected = [s[0] for s in scores]
    for t in list(selected):
        for r in TABLE_RELATIONS.get(t, []):
            if r not in selected:
                selected.append(r)
    return selected

def select_columns_keyword(query: str, tables: list) -> dict:
    """Выбор колонок."""
    tl = query.lower()
    col_kw = {
        "full_name": ["имя","name","фамили","фио"],
        "department": ["отдел","department"],
        "salary": ["зарплат","salary","зп"],
        "position": ["должност","position"],
        "budget": ["бюджет","budget"],
        "project_name": ["назван","project_name","проект"],
        "priority": ["приоритет","priority"],
        "status": ["статус","status"],
        "task_name": ["назван","task_name"],
    }
    result = {}
    for table in tables:
        cols = list(SCHEMA[table]["columns"].keys())
        scored = [(c, sum(1 for k in col_kw.get(c,[]) if k in tl)) for c in cols]
        scored.sort(key=lambda x: -x[1])
        result[table] = [c for c, s in scored]
    return result

def select_schema(query: str, mode: str = "demo") -> dict:
    """Полная селекция схемы."""
    text_clean = re.sub(r"[^\w\s]", " ", query)
    tables = select_tables_keyword(text_clean)
    columns = select_columns_keyword(text_clean, tables)
    lines = []
    for t in tables:
        lines.append(f"\nТаблица {t} ({SCHEMA[t]['description']}):")
        for c in columns[t]:
            lines.append(f"  - {c}: {SCHEMA[t]['columns'].get(c, '')}")
    return {"tables": tables, "columns": columns, "text": "\n".join(lines)}

if __name__ == "__main__":
    for q in [
        "Найди сотрудников отдела разработки",
        "Покажи проекты с бюджетом более 300000",
    ]:
        r = select_schema(q)
        print(f"Query: {q}")
        print(f"Tables: {r['tables']}")
        print()
