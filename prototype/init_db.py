"""
init_db.py -- Создание и наполнение тестовой БД SQLite
Структура: employees, projects, tasks, comments
"""
import sqlite3, os, argparse

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_company.db")

def create_tables(cur):
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS employees (
            employee_id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            department TEXT,
            position TEXT,
            salary REAL,
            hire_date TEXT,
            manager_id INTEGER,
            FOREIGN KEY (manager_id) REFERENCES employees(employee_id)
        );
        CREATE TABLE IF NOT EXISTS projects (
            project_id INTEGER PRIMARY KEY,
            project_name TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            budget REAL,
            status TEXT
        );
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY,
            task_name TEXT NOT NULL,
            description TEXT,
            assignee_id INTEGER,
            project_id INTEGER,
            priority TEXT,
            status TEXT,
            due_date TEXT,
            FOREIGN KEY (assignee_id) REFERENCES employees(employee_id),
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );
        CREATE TABLE IF NOT EXISTS comments (
            comment_id INTEGER PRIMARY KEY,
            task_id INTEGER,
            author_id INTEGER,
            comment_text TEXT,
            created_at TEXT,
            is_internal INTEGER,
            FOREIGN KEY (task_id) REFERENCES tasks(task_id),
            FOREIGN KEY (author_id) REFERENCES employees(employee_id)
        );
    """)

def insert_data(cur):
    employees = [
        (1, "Иванов А.А.", "Разработка", "Senior Developer", 150000, "2020-03-15", None),
        (2, "Петрова М.И.", "Разработка", "Junior Developer", 80000, "2022-06-01", 1),
        (3, "Сидоров К.В.", "Продажи", "Sales Manager", 120000, "2021-01-10", None),
        (4, "Кузнецов Д.С.", "Продажи", "Sales Rep", 70000, "2023-02-20", 3),
        (5, "Смирнова Е.А.", "Маркетинг", "Marketing Lead", 130000, "2020-09-01", None),
        (6, "Васильев П.Р.", "Разработка", "Team Lead", 180000, "2019-06-15", None),
        (7, "Зайцева О.В.", "Маркетинг", "Marketing Specialist", 90000, "2021-11-01", 5),
        (8, "Морозов И.Н.", "Бухгалтерия", "Accountant", 95000, "2020-04-20", None),
        (9, "Белова Т.С.", "Разработка", "QA Engineer", 85000, "2022-09-01", 6),
        (10, "Козлов А.В.", "HR", "HR Manager", 110000, "2021-03-01", None),
        (11, "Новикова Е.Д.", "Разработка", "Frontend Developer", 140000, "2021-07-15", 6),
        (12, "Григорьев В.П.", "Продажи", "Sales Rep", 75000, "2023-05-10", 3),
        (13, "Фёдорова И.М.", "Бухгалтерия", "Senior Accountant", 105000, "2019-12-01", 8),
        (14, "Алексеев Д.Н.", "Разработка", "Backend Developer", 145000, "2020-10-01", 6),
        (15, "Тимофеева А.С.", "HR", "HR Specialist", 70000, "2023-08-15", 10),
    ]
    projects = [
        (1, "CRM Platform", "2024-01-15", "2024-12-31", 500000, "active"),
        (2, "Mobile App", "2024-03-01", "2024-10-31", 300000, "active"),
        (3, "Legacy Migration", "2023-06-01", "2024-06-01", 200000, "completed"),
        (4, "Analytics Dashboard", "2024-05-01", None, 150000, "on_hold"),
        (5, "Data Pipeline", "2024-04-01", "2024-09-30", 250000, "active"),
        (6, "DevOps Tools", "2024-02-01", "2024-08-31", 180000, "completed"),
        (7, "Customer Portal", "2024-06-01", None, 350000, "active"),
        (8, "Security Audit", "2024-07-01", "2024-09-01", 100000, "completed"),
    ]
    tasks = [
        (1, "Design DB schema", "Create initial database schema", 1, 1, "high", "completed", "2024-02-01"),
        (2, "Implement auth", "JWT authentication module", 1, 1, "high", "completed", "2024-03-15"),
        (3, "Develop API", "REST API for CRM", 14, 1, "high", "in_progress", "2024-06-30"),
        (4, "Write tests", "Unit tests for API", 2, 1, "medium", "in_progress", "2024-07-15"),
        (5, "Design UI mockups", "Figma mockups", 5, 2, "medium", "completed", "2024-04-01"),
        (6, "Develop mobile UI", "React Native screens", 11, 2, "high", "in_progress", "2024-08-01"),
        (7, "Push notifications", "Implement push", 11, 2, "low", "open", "2024-09-30"),
        (8, "Data migration", "Migrate legacy data", 14, 3, "critical", "completed", "2024-03-01"),
        (9, "Verify migrated data", "Check integrity", 9, 3, "high", "completed", "2024-05-01"),
        (10, "Design dashboard", "Dashboard wireframes", 5, 4, "medium", "completed", "2024-06-01"),
        (11, "Implement charts", "Interactive charts", 14, 4, "high", "open", "2024-09-01"),
        (12, "ETL pipeline", "ETL pipeline", 14, 5, "high", "in_progress", "2024-08-15"),
        (13, "Data validation", "Validate incoming data", 9, 5, "medium", "open", "2024-09-30"),
        (14, "CI/CD setup", "CI/CD pipelines", 6, 6, "high", "completed", "2024-04-01"),
        (15, "Docker config", "Docker compose files", 6, 6, "medium", "completed", "2024-06-01"),
        (16, "Deploy monitoring", "Monitoring setup", 6, 6, "low", "completed", "2024-07-01"),
        (17, "User feedback", "Feedback form", 11, 7, "medium", "in_progress", "2024-07-15"),
        (18, "Payment integration", "Stripe gateway", 1, 7, "high", "open", "2024-09-30"),
        (19, "SSO integration", "Okta SSO", 6, 7, "medium", "open", "2024-10-31"),
        (20, "Vulnerability scan", "Security audit", 6, 8, "critical", "completed", "2024-08-01"),
        (21, "Penetration testing", "Pen test", 6, 8, "high", "completed", "2024-09-01"),
        (22, "Code review", "Review modules", 1, 1, "medium", "open", "2024-08-01"),
        (23, "Performance opt", "Optimize queries", 14, 1, "low", "open", "2024-09-30"),
        (24, "User docs", "User guide", 5, 2, "low", "open", "2024-10-15"),
        (25, "Deploy production", "Prod deployment", 1, 1, "high", "open", "2024-12-01"),
    ]
    comments = [
        (1, 1, 1, "Initial schema draft ready", "2024-01-20", 0),
        (2, 2, 1, "Using JWT RS256", "2024-02-10", 0),
        (3, 3, 14, "REST design review needed", "2024-04-01", 0),
        (4, 3, 6, "Reviewed, looks good", "2024-04-02", 1),
        (5, 5, 5, "Mockups ready for review", "2024-03-15", 0),
        (6, 6, 11, "Need design specs", "2024-05-01", 0),
        (7, 6, 5, "Specs uploaded", "2024-05-02", 0),
        (8, 8, 14, "Migration script done", "2024-02-15", 0),
        (9, 8, 9, "Testing in progress", "2024-02-20", 0),
        (10, 9, 9, "All data verified", "2024-04-15", 0),
        (11, 10, 5, "Dashboard layout approved", "2024-06-10", 0),
        (12, 12, 14, "ETL needs more workers", "2024-06-15", 0),
        (13, 14, 6, "CI/CD with GitHub Actions", "2024-03-01", 0),
        (14, 15, 6, "Docker setup complete", "2024-04-10", 0),
        (15, 16, 6, "Prometheus+Grafana", "2024-05-15", 0),
        (16, 17, 11, "Feedback form v1 ready", "2024-07-01", 0),
        (17, 20, 6, "Critical vulns fixed", "2024-08-10", 0),
        (18, 21, 6, "Pen test passed", "2024-08-25", 1),
        (19, 4, 2, "Tests for API v1 done", "2024-06-20", 0),
        (20, 4, 1, "Need edge case tests", "2024-06-25", 0),
        (21, 12, 6, "Consider Apache Airflow", "2024-06-16", 1),
        (22, 18, 1, "Stripe docs reviewed", "2024-08-01", 0),
        (23, 7, 11, "Via Firebase", "2024-06-01", 0),
        (24, 25, 1, "Deploy scheduled Dec", "2024-10-01", 0),
        (25, 22, 6, "Review assigned", "2024-07-15", 0),
        (26, 17, 5, "UX improvements", "2024-07-20", 0),
        (27, 3, 1, "API rate limiting done", "2024-05-10", 0),
        (28, 11, 14, "Chart.js selected", "2024-07-01", 0),
        (29, 19, 6, "Okta SSO", "2024-08-15", 0),
        (30, 23, 14, "DB indexing strategy", "2024-07-20", 0),
    ]
    cur.executemany("INSERT INTO employees VALUES (?,?,?,?,?,?,?)", employees)
    cur.executemany("INSERT INTO projects VALUES (?,?,?,?,?,?)", projects)
    cur.executemany("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?)", tasks)
    cur.executemany("INSERT INTO comments VALUES (?,?,?,?,?,?)", comments)

def get_schema():
    return {
        "employees": {"columns": ["employee_id","full_name","department","position","salary","hire_date","manager_id"],"pk":"employee_id","fk":{"manager_id":"employees"}},
        "projects": {"columns": ["project_id","project_name","start_date","end_date","budget","status"],"pk":"project_id","fk":{}},
        "tasks": {"columns": ["task_id","task_name","description","assignee_id","project_id","priority","status","due_date"],"pk":"task_id","fk":{"assignee_id":"employees","project_id":"projects"}},
        "comments": {"columns": ["comment_id","task_id","author_id","comment_text","created_at","is_internal"],"pk":"comment_id","fk":{"task_id":"tasks","author_id":"employees"}},
    }

def init_database():
    """Создание/пересоздание БД (без argparse — для вызова из app.py)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    create_tables(cur)
    insert_data(cur)
    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()
    if args.clean and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_database()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for t in ["employees","projects","tasks","comments"]:
        cnt = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {cnt} rows")
    conn.close()
    print(f"\nDatabase: {DB_PATH}")

if __name__ == "__main__":
    main()
