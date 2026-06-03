#!/usr/bin/env python3
"""
test_comprehensive.py — Comprehensive NL2SQL testing via Gemini pipeline (core.pipeline).
Requires GEMINI_API_KEY in environment or .env file.
Respects Gemini free tier rate limit (~15 RPM) with 4s delay between requests.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.pipeline import process_nl_query

# Load .env without dotenv dependency
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            if _line.startswith("GEMINI_API_KEY="):
                os.environ["GEMINI_API_KEY"] = _line.split("=", 1)[1].strip()
                break

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_company.db")
has_db = os.path.exists(db_path)

# Rate limiting: Gemini free tier = 15 RPM, so 4s between requests
DELAY_SECONDS = 4
MAX_RETRIES = 1
RETRY_DELAY = 8

test_queries = [
    # === Простые SELECT ===
    ("Покажи всех сотрудников.", "employees"),
    ("Выведи список сотрудников.", "employees"),
    ("Кто работает в компании?", "employees"),
    ("Отобрази все записи из таблицы сотрудников.", "employees"),
    ("Покажи все проекты.", "projects"),
    ("Какие проекты есть в системе?", "projects"),
    ("Выведи все задачи.", "tasks"),
    ("Покажи все комментарии.", "comments"),
    ("Сколько сотрудников зарегистрировано?", "count"),
    ("Сколько проектов существует?", "count"),
    ("Сколько задач создано?", "count"),
    ("Сколько комментариев оставлено?", "count"),

    # === Фильтрация сотрудников ===
    ("Покажи сотрудников отдела IT.", "employees_filter"),
    ("Найди всех разработчиков.", "employees_filter"),
    ("Кто работает в отделе маркетинга?", "employees_filter"),
    ("Покажи сотрудников с зарплатой больше 100000.", "salary_filter"),
    ("Найди сотрудников с зарплатой меньше 50000.", "salary_filter"),
    ("Кто получает больше всех?", "aggregate"),
    ("Кто получает меньше всех?", "aggregate"),
    ("Покажи сотрудников, принятых после 2023 года.", "date_filter"),
    ("Кто был нанят в прошлом году?", "date_filter"),
    ("Найди сотрудников без руководителя.", "null_filter"),
    ("Покажи всех менеджеров.", "position_filter"),
    ("Кто работает на должности аналитика?", "position_filter"),
    ("Покажи сотрудников из отдела продаж.", "department_filter"),

    # === Сортировка ===
    ("Отсортируй сотрудников по зарплате.", "sort"),
    ("Покажи сотрудников по убыванию зарплаты.", "sort_desc"),
    ("Кто получает больше всего денег?", "aggregate"),
    ("Отсортируй сотрудников по дате найма.", "sort"),
    ("Покажи самых новых сотрудников.", "sort_newest"),
    ("Покажи самые старые проекты.", "sort"),
    ("Отсортируй задачи по сроку выполнения.", "sort"),
    ("Какие проекты имеют самый большой бюджет?", "sort_budget"),

    # === Агрегации ===
    ("Средняя зарплата сотрудников.", "aggregate"),
    ("Максимальная зарплата в компании.", "aggregate"),
    ("Минимальная зарплата.", "aggregate"),
    ("Сумма всех зарплат.", "aggregate"),
    ("Средний бюджет проектов.", "aggregate"),
    ("Общий бюджет всех проектов.", "aggregate"),
    ("Сколько сотрудников в каждом отделе?", "group_by"),
    ("Сколько проектов находится в статусе Active?", "status_filter"),
    ("Сколько задач имеет высокий приоритет?", "priority_filter"),
    ("Сколько внутренних комментариев существует?", "filter"),
    ("Средняя зарплата по отделам.", "group_by_avg"),

    # === GROUP BY ===
    ("Покажи количество сотрудников по отделам.", "group_by"),
    ("Сколько сотрудников на каждой должности?", "group_by"),
    ("Количество задач по статусам.", "group_by"),
    ("Количество проектов по статусам.", "group_by"),
    ("Средняя зарплата по должностям.", "group_by_avg"),
    ("Общий бюджет проектов по статусам.", "group_by_sum"),
    ("Сколько задач назначено каждому сотруднику?", "group_by"),
    ("Кто оставил больше всего комментариев?", "group_by_top"),
    ("Сколько комментариев у каждой задачи?", "group_by"),

    # === JOIN сотрудников и задач ===
    ("Покажи задачи вместе с именами исполнителей.", "join_emp_task"),
    ("Какие задачи назначены Ивану Иванову?", "join_emp_task_name"),
    ("Кто отвечает за каждую задачу?", "join_emp_task"),
    ("Покажи сотрудника и название его задач.", "join_emp_task"),
    ("Найди сотрудников без назначенных задач.", "join_no_task"),
    ("Кто имеет больше всего задач?", "join_most_tasks"),
    ("Покажи задачи сотрудников отдела IT.", "join_dept_tasks"),
    ("Какие задачи назначены менеджерам?", "join_mgr_tasks"),
    ("Сколько задач у каждого сотрудника?", "join_task_count"),
    ("Кто выполняет задачу \"Разработка API\"?", "join_task_by_name"),

    # === JOIN задач и проектов ===
    ("Покажи задачи вместе с проектами.", "join_task_project"),
    ("Какие задачи относятся к проекту CRM?", "join_task_project_name"),
    ("Сколько задач в каждом проекте?", "join_task_count_project"),
    ("Найди проекты без задач.", "join_no_tasks"),
    ("Какой проект содержит больше всего задач?", "join_most_tasks_project"),
    ("Покажи открытые задачи проекта ERP.", "join_open_tasks"),
    ("Какие проекты имеют просроченные задачи?", "join_overdue_tasks"),
    ("Выведи проект для каждой задачи.", "join_task_project"),
    ("Найди задачи по проектам со статусом Active.", "join_active_project_tasks"),

    # === JOIN комментариев ===
    ("Покажи комментарии вместе с авторами.", "join_comment_author"),
    ("Кто написал каждый комментарий?", "join_comment_author"),
    ("Покажи комментарии к задаче №5.", "join_comment_task"),
    ("Сколько комментариев у каждой задачи?", "join_comment_count"),
    ("Кто оставил больше всего комментариев?", "join_comment_author_count"),
    ("Покажи только внутренние комментарии.", "filter"),
    ("Покажи только публичные комментарии.", "filter"),
    ("Найди последние комментарии.", "sort"),
    ("Выведи комментарии сотрудников отдела IT.", "join_dept_comments"),
    ("Покажи комментарии к проекту CRM.", "multi_join"),

    # === Самоссылка (manager_id) ===
    ("Покажи сотрудников и их руководителей.", "self_join"),
    ("Кто подчиняется Ивану Петрову?", "self_join_name"),
    ("У кого нет руководителя?", "null_filter"),
    ("Покажи структуру подчинения сотрудников.", "self_join"),
    ("Сколько подчинённых у каждого менеджера?", "self_join_count"),
    ("Кто руководит самым большим количеством сотрудников?", "self_join_top"),
    ("Покажи менеджеров и их команды.", "self_join"),
    ("Кто является руководителем сотрудника №7?", "self_join_by_id"),

    # === Работа с датами ===
    ("Какие сотрудники были наняты в 2024 году?", "date_filter"),
    ("Кто работает в компании более двух лет?", "date_filter"),
    ("Покажи проекты, начатые после января 2024.", "date_filter"),
    ("Какие проекты завершились в прошлом месяце?", "date_filter"),
    ("Найди задачи со сроком до конца недели.", "date_filter"),
    ("Какие задачи просрочены?", "date_filter"),
    ("Какие проекты сейчас активны?", "status_filter"),
    ("Покажи комментарии за последние 7 дней.", "date_filter"),
    ("Какие сотрудники были наняты в этом месяце?", "date_filter"),
    ("Покажи задачи, срок которых истекает сегодня.", "date_filter"),

    # === Поиск по тексту ===
    ("Найди сотрудников, в имени которых есть \"Алекс\".", "text_search"),
    ("Найди проекты, содержащие слово \"CRM\".", "text_search"),
    ("Покажи задачи, содержащие слово \"отчет\".", "text_search"),
    ("Найди комментарии со словом \"ошибка\".", "text_search"),
    ("Покажи задачи, где описание содержит \"API\".", "text_search"),
    ("Найди сотрудников с фамилией Иванов.", "text_search"),
    ("Покажи проекты, начинающиеся на букву A.", "text_search"),
    ("Найди комментарии со словом \"срочно\".", "text_search"),

    # === Сложные аналитические запросы ===
    ("Кто получает зарплату выше средней по компании?", "complex"),
    ("Какие отделы имеют среднюю зарплату выше 100000?", "complex"),
    ("Какие сотрудники не имеют ни одной задачи?", "complex"),
    ("Какие проекты имеют бюджет выше среднего?", "complex"),
    ("Покажи топ-5 самых загруженных сотрудников.", "complex"),
    ("Найди сотрудников, у которых больше задач, чем в среднем по компании.", "complex"),
    ("Какие проекты имеют больше всего комментариев?", "complex"),
    ("Какие задачи имеют наибольшее количество комментариев?", "complex"),
    ("Кто оставил комментарии к наибольшему числу разных задач?", "complex"),
    ("Покажи сотрудников с максимальной зарплатой в каждом отделе.", "complex"),
    ("Найди самый дорогой проект.", "complex"),
    ("Найди самый длинный проект по срокам.", "complex"),

    # === Естественные формулировки ===
    ("Кто у нас сейчас самый дорогой сотрудник?", "natural"),
    ("Какая команда получает больше всех?", "natural"),
    ("Над чем работает Алексей?", "natural"),
    ("Какие задачи ещё не завершены?", "natural"),
    ("Что просрочено на сегодняшний день?", "natural"),
    ("Какие проекты идут прямо сейчас?", "natural"),
    ("Кто перегружен задачами?", "natural"),
    ("У кого нет ни одной задачи?", "natural"),
    ("Какие проекты требуют больше всего денег?", "natural"),
    ("Кто чаще остальных пишет комментарии?", "natural"),
    ("Кто руководит отделом разработки?", "natural"),
    ("Какие сотрудники работают без менеджера?", "natural"),
    ("Какие задачи требуют срочного внимания?", "natural"),
    ("Какие проекты скоро заканчиваются?", "natural"),
    ("Кто недавно пришёл в компанию?", "natural"),
    ("Какие сотрудники работают дольше всех?", "natural"),
    ("Где самая высокая средняя зарплата?", "natural"),
    ("Какие задачи зависли без комментариев?", "natural"),
    ("Кто отвечает за больше всего проектов?", "natural"),
    ("Покажи полную информацию по проекту CRM.", "natural"),

    # === Негативные тесты (ожидается graceful failure) ===
    ("Покажи клиентов компании.", "negative"),
    ("Сколько заказов оформлено?", "negative"),
    ("Какие товары есть на складе?", "negative"),
    ("Покажи таблицу payments.", "negative"),
    ("Кто является заказчиком проекта?", "negative"),
    ("Сколько продаж было в мае?", "negative"),
    ("Покажи адреса сотрудников.", "negative"),
    ("Найди телефон сотрудника Иванова.", "negative"),
    ("Выведи прибыль компании.", "negative"),
    ("Покажи список поставщиков.", "negative"),

    # === Edge-case: сложные условия ===
    ("Покажи активные проекты с бюджетом от 100000 до 500000.", "complex"),
    ("Найди сотрудников с зарплатой между 80000 и 150000 в отделе разработки.", "complex"),
    ("Покажи просроченные задачи высокого приоритета.", "complex"),
    ("Найди проекты, завершённые в 2024 году с бюджетом больше 200000.", "complex"),
    ("Покажи внутренние комментарии к задачам проекта CRM.", "complex"),

    # === Edge-case: HAVING ===
    ("Покажи отделы, где средняя зарплата выше 100000.", "complex"),
    ("Покажи проекты, в которых больше 3 задач.", "complex"),
    ("Какие сотрудники имеют больше 2 комментариев?", "complex"),

    # === Edge-case: множественные JOIN ===
    ("Покажи задачи с проектами и исполнителями.", "multi_join"),
    ("Выведи все комментарии к задачам проекта ERP с именами авторов.", "multi_join"),
    ("Покажи сотрудников, их задачи и проекты, над которыми они работают.", "multi_join"),

    # === Edge-case: NULL handling ===
    ("Найди проекты без даты окончания.", "complex"),
    ("Покажи сотрудников, у которых не указан руководитель.", "null_filter"),
    ("Найди задачи без описания.", "complex"),

    # === Edge-case: агрегация с условиями ===
    ("Средняя зарплата активных сотрудников.", "complex"),
    ("Общий бюджет активных проектов.", "aggregate"),
    ("Максимальная зарплата в отделе маркетинга.", "complex"),

    # === Edge-case: точные формулировки ===
    ("Покажи ID, имя и зарплату всех сотрудников.", "employees"),
    ("Найди проекты со статусом active и бюджетом больше средней зарплаты.", "complex"),
    ("Какие задачи находятся в работе у команды разработки?", "natural"),
]

results = {
    "pass": 0, "fail": 0,
    "categories": {}
}

def get_category_label(cat):
    labels = {
        "employees": "Простые SELECT",
        "count": "Простые SELECT (COUNT)",
        "employees_filter": "Фильтрация сотрудников",
        "salary_filter": "Фильтрация по зарплате",
        "date_filter": "Работа с датами",
        "null_filter": "Поиск NULL",
        "position_filter": "Фильтрация по должности",
        "department_filter": "Фильтрация по отделу",
        "sort": "Сортировка",
        "sort_desc": "Сортировка (убывание)",
        "sort_newest": "Сортировка (новые)",
        "sort_budget": "Сортировка (бюджет)",
        "aggregate": "Агрегации",
        "group_by": "GROUP BY",
        "group_by_avg": "GROUP BY AVG",
        "group_by_sum": "GROUP BY SUM",
        "group_by_top": "GROUP BY TOP",
        "status_filter": "Фильтрация по статусу",
        "priority_filter": "Фильтрация по приоритету",
        "filter": "Фильтрация",
        "join_emp_task": "JOIN сотрудники-задачи",
        "join_emp_task_name": "JOIN сотрудники-задачи (имя)",
        "join_no_task": "JOIN (нет задач)",
        "join_most_tasks": "JOIN (больше задач)",
        "join_dept_tasks": "JOIN задачи отдела",
        "join_mgr_tasks": "JOIN задачи менеджеров",
        "join_task_count": "JOIN кол-во задач",
        "join_task_by_name": "JOIN задача по имени",
        "join_task_project": "JOIN задачи-проекты",
        "join_task_project_name": "JOIN задачи-проекты (имя)",
        "join_task_count_project": "JOIN кол-во задач в проекте",
        "join_no_tasks": "JOIN проекты без задач",
        "join_most_tasks_project": "JOIN больше задач в проекте",
        "join_open_tasks": "JOIN открытые задачи",
        "join_overdue_tasks": "JOIN просроченные задачи",
        "join_active_project_tasks": "JOIN активные проекты",
        "join_comment_author": "JOIN комментарии-авторы",
        "join_comment_task": "JOIN комментарии к задаче",
        "join_comment_count": "JOIN кол-во комментариев",
        "join_comment_author_count": "JOIN автор комментариев",
        "join_dept_comments": "JOIN комментарии отдела",
        "multi_join": "Множественный JOIN",
        "self_join": "Самоссылка (manager_id)",
        "self_join_name": "Самоссылка по имени",
        "self_join_count": "Самоссылка подсчёт",
        "self_join_top": "Самоссылка топ",
        "self_join_by_id": "Самоссылка по ID",
        "text_search": "Поиск по тексту",
        "complex": "Сложные аналитические",
        "natural": "Естественные формулировки",
        "negative": "Негативные тесты",
    }
    return labels.get(cat, cat)

print("=" * 70)
print("NL2SQL PROTOTYPE - FULL TESTING (Gemini pipeline)")
print("=" * 70)
print(f"Total queries: {len(test_queries)}")
print(f"Database: {'Yes' if has_db else 'NO!'}")
print(f"Mode: Gemini LLM (no keyword matching)")
print("=" * 70)

for q, category in test_queries:
    # Rate limiting: respect Gemini free tier (skip first request)
    if results["pass"] + results["fail"] > 0:
        time.sleep(DELAY_SECONDS)
    
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = process_nl_query(q, db_path)
            sql = result.get("formatted_sql") or result.get("sql", "")
            
            if not sql:
                print(f"  NO SQL: {result.get('error', 'unknown')[:80]}")
                results["fail"] += 1
                results["categories"].setdefault(category, {"pass": 0, "fail": 0})["fail"] += 1
                break

            if result.get("success"):
                rows = result.get("rows") or []
                print(f"  OK ({len(rows)} rows)")
                results["pass"] += 1
                results["categories"].setdefault(category, {"pass": 0, "fail": 0})["pass"] += 1
                break
            else:
                error_msg = result.get("error", "Unknown error")
                # Check for rate limiting
                if "429" in str(error_msg) or "quota" in str(error_msg).lower() or "rate" in str(error_msg).lower():
                    if attempt < MAX_RETRIES:
                        print(f"  RATE LIMITED, retry in {RETRY_DELAY}s (attempt {attempt+1}/{MAX_RETRIES+1})...")
                        time.sleep(RETRY_DELAY)
                        continue
                print(f"  ERROR: {error_msg[:80]}")
                results["fail"] += 1
                results["categories"].setdefault(category, {"pass": 0, "fail": 0})["fail"] += 1
                break

        except Exception as e:
            if "429" in str(e) and attempt < MAX_RETRIES:
                print(f"  RATE LIMITED, retry in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
                continue
            print(f"  EXCEPTION: {e}")
            results["fail"] += 1
            results["categories"].setdefault(category, {"pass": 0, "fail": 0})["fail"] += 1
            break

# Summary
print("\n" + "=" * 70)
print("РЕЗУЛЬТАТЫ ПО КАТЕГОРИЯМ:")
print("=" * 70)
for cat, res in sorted(results["categories"].items()):
    label = get_category_label(cat)
    total = res["pass"] + res["fail"]
    status = "✓" if res["fail"] == 0 else "✗"
    print(f"  {status} {label}: {res['pass']}/{total}")

print("\n" + "=" * 70)
total = results["pass"] + results["fail"]
print(f"ИТОГО: {results['pass']}/{total} прошло ({results['fail']} ошибок)")
print("=" * 70)

if results["fail"] > 0:
    print("\nНУЖНА ДОРАБОТКА! Есть ошибки, которые нужно исправить.")
    sys.exit(1)
else:
    print("\nВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    sys.exit(0)
