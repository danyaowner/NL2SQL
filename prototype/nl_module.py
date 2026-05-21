"""
nl_module.py -- Модуль обработки естественного языка
Очистка, определение языка, выделение сущностей, классификация
"""
import re
from typing import Optional

try:
    from langdetect import detect as _detect_lang
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False

try:
    import dateparser
    HAS_DATEPARSER = True
except ImportError:
    HAS_DATEPARSER = False

TABLE_ALIASES = {
    "employees": ["сотрудник","сотрудники","работник","работники","employee","employees"],
    "projects": ["проект","проекты","project","projects"],
    "tasks": ["задача","задачи","задание","задания","task","tasks","таск","таски"],
    "comments": ["комментари","комментар","comment","comments","комменти"],
}

QUERY_TYPES = {
    "count": ["сколько","количество","сколько всего","число","посчитай","how many","count","total"],
    "find": ["найди","покажи","выведи","найти","отобрази","find","show","display","get","list"],
    "aggregate": ["сумма","среднее","максимум","минимум","avg","sum","average","maximum","minimum","итог","общий","общая","всего","итого"],
    "compare": ["сравни","кто больше","выше чем","топ","compare","top","highest","lowest"],
}

def clean_query(text: str) -> str:
    """Очистка запроса."""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[^\w\s.,!?;:\'\"()а-яА-Яa-zA-Z0-9<>=-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def detect_language(text: str) -> str:
    """Определение языка."""
    if HAS_LANGDETECT:
        try:
            lang = _detect_lang(text)
            if lang == "ru":
                return "ru"
            return "en"
        except Exception:
            pass
    if re.search(r"[а-яА-Я]", text):
        return "ru"
    return "en"

def extract_entities(text: str) -> list:
    """Выделение упомянутых таблиц."""
    text_lower = text.lower()
    entities = []
    for table, aliases in TABLE_ALIASES.items():
        for alias in aliases:
            if alias in text_lower and table not in entities:
                entities.append(table)
                break
    dep_map = {
        "разработк": "Разработка", "продаж": "Продажи",
        "маркетинг": "Маркетинг", "бухгалтер": "Бухгалтерия",
        "hr": "HR", "кадры": "HR", "sales": "Продажи",
        "developer": "Разработка", "dev": "Разработка",
        "it": "Разработка", "айти": "Разработка",
        "аналит": "Аналитика",
    }
    # Для ключей it/айти проверяем контекст — не путать с англ. словом "it"
    dept_context_words = ["из", "в", "отдел", "department", "dep"]
    for word in text_lower.split():
        for key, dep in dep_map.items():
            if key in word and f"department:{dep}" not in entities:
                if key in ("it", "айти"):
                    if any(ctx in text_lower for ctx in dept_context_words):
                        entities.append(f"department:{dep}")
                else:
                    entities.append(f"department:{dep}")
    return entities

def classify_query(text: str, lang: str = "ru") -> str:
    """Классификация типа запроса."""
    text_lower = text.lower()
    for qtype, keywords in QUERY_TYPES.items():
        for kw in keywords:
            if kw in text_lower:
                return qtype
    return "select"

def extract_numbers(text: str) -> list:
    """Извлечение чисел из текста."""
    numbers = []
    # Обычные числа
    for m in re.finditer(r"\b\d+\b", text):
        numbers.append(int(m.group()))
    # Числа с суффиксом к/кк (100к = 100000, 5кк = 5000000)
    for m in re.finditer(r"\b(\d+)\s*к(к)?\b", text.lower()):
        val = int(m.group(1))
        if m.group(2):  # кк = миллионы
            numbers.append(val * 1000000)
        else:  # к = тысячи
            numbers.append(val * 1000)
    word_nums = {"один":1,"два":2,"три":3,"четыре":4,"пять":5,"сто":100,"тысяч":1000,"миллион":1000000}
    text_lower = text.lower()
    for word, val in word_nums.items():
        if word in text_lower:
            numbers.append(val)
    return numbers

def extract_conditions(text: str) -> dict:
    """Извлечение условий из запроса."""
    conds = {}
    tl = text.lower()
    pats = [
        (r"зарплат[а-я]*\s*(?:выше|больше|>)\s*(\d+)", "salary", ">"),
        (r"зарплат[а-я]*\s*(?:ниже|меньше|<)\s*(\d+)", "salary", "<"),
        (r"salary\s*(?:above|greater|>)\s*(\d+)", "salary", ">"),
        (r"salary\s*(?:below|less|<)\s*(\d+)", "salary", "<"),
        (r"бюджет[а-я]*\s*(?:выше|больше|>)\s*(\d+)", "budget", ">"),
        (r"бюджет[а-я]*\s*(?:ниже|меньше|<)\s*(\d+)", "budget", "<"),
        (r"budget\s*(?:above|greater|>)\s*(\d+)", "budget", ">"),
        (r"budget\s*(?:below|less|<)\s*(\d+)", "budget", "<"),
    ]
    for pat, field, op in pats:
        m = re.search(pat, tl)
        if m:
            conds[field] = {"value": int(m.group(1)), "op": op}
            break
    # Generic number comparison (> N, < N) - as fallback when no field prefix
    has_field_prefix = False
    for pat, _, _ in pats:
        if re.search(pat, tl):
            has_field_prefix = True
            break
    
    if not has_field_prefix:
        for m in re.finditer(r">\s*(\d+)\s*к?\b", tl):
            val = int(m.group(1))
            # Check if there's a "к" suffix (100к = 100000)
            after_digit = tl[m.end(1):m.end()]
            if "к" in after_digit:
                val *= 1000
            conds["salary"] = {"value": val, "op": ">"}
            break
        for m in re.finditer(r"<\s*(\d+)\s*к?\b", tl):
            if "salary" not in conds:
                val = int(m.group(1))
                after_digit = tl[m.end(1):m.end()]
                if "к" in after_digit:
                    val *= 1000
                conds["salary"] = {"value": val, "op": "<"}
            break
    
    if "оплач" in tl:
        conds["salary"] = {"value": 0, "op": ">"}
    elif "высок" in tl or "high" in tl or "critical" in tl or "критич" in tl:
        if "зарплат" in tl or "salary" in tl:
            conds["salary"] = {"value": 0, "op": ">"}
        else:
            conds["priority"] = {"value": "high", "op": "in"}
    elif "средн" in tl or "medium" in tl:
        # Avoid confusing "средняя зарплата" (average salary) with priority=medium
        if "приоритет" in tl or "priority" in tl:
            conds["priority"] = {"value": "medium", "op": "="}
        elif "зарплат" in tl or "salary" in tl or "бюджет" in tl or "budget" in tl:
            pass  # This is "average salary/budget", not priority
        else:
            conds["priority"] = {"value": "medium", "op": "="}
    if "активн" in tl or "active" in tl:
        conds["status"] = {"value": "active", "op": "="}
    elif "заверш" in tl or "completed" in tl or "выполнен" in tl or "готов" in tl:
        conds["status"] = {"value": "completed", "op": "="}
    # Задачи без исполнителя
    if "без" in tl and ("исполнител" in tl or "assignee" in tl or "назначен" in tl):
        conds["assignee_id"] = {"value": None, "op": "is_null"}
    # Просрочка
    if "просроч" in tl or "overdue" in tl or "просрочен" in tl:
        conds["due_date"] = {"value": "now", "op": "overdue"}
    # "задача N" или "task N" → task_id = N
    task_num = re.search(r"(?:задач[а-я]*|task)\s+(\d+)", tl)
    if task_num:
        conds["task_id"] = {"value": int(task_num.group(1)), "op": "="}
    # "проект N" или "project N" → project_id = N
    proj_num = re.search(r"(?:проект[а-я]*|project)\s+(\d+)", tl)
    if proj_num:
        conds["project_id"] = {"value": int(proj_num.group(1)), "op": "="}
    return conds

def process_query(text: str) -> dict:
    """Полная обработка запроса."""
    cleaned = clean_query(text)
    lang = detect_language(cleaned)
    entities = extract_entities(cleaned)
    qtype = classify_query(cleaned, lang)
    conds = extract_conditions(cleaned)
    nums = extract_numbers(cleaned)
    return {
        "original": text, "cleaned": cleaned,
        "language": lang, "entities": entities,
        "query_type": qtype, "conditions": conds,
        "numbers": nums,
    }

if __name__ == "__main__":
    tests = [
        "Найди всех сотрудников отдела разработки",
        "Сколько задач в проекте CRM Platform",
        "Покажи сотрудников с зарплатой выше 100000",
        "Выведи среднюю зарплату по отделам",
        "Find all employees in sales department",
    ]
    for q in tests:
        r = process_query(q)
        print(f"\n{q}")
        print(f"  Lang={r['language']} Type={r['query_type']}")
        print(f"  Entities={r['entities']} Conditions={r['conditions']}")
