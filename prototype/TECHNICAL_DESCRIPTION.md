# NL2SQL — Техническая документация

## Преобразование естественного языка в SQL через Google Gemini

---

# Содержание

1. [Общая архитектура](#1-общая-архитектура)
2. [Структура проекта](#2-структура-проекта)
3. [API сервер (FastAPI)](#3-api-сервер-fastapi)
4. [Core модули](#4-core-модули)
5. [База данных](#5-база-данных)
6. [Полный pipeline обработки запроса](#6-pipeline)
7. [Веб-интерфейс (Frontend)](#7-веб-интерфейс-frontend)
8. [Тестирование](#8-тестирование)
9. [Запуск проекта](#9-запуск-проекта)
10. [Стек технологий](#10-стек-технологий)


# 1. Общая архитектура

## 1.1. Концепция

NL2SQL — это веб-приложение, которое принимает запрос на естественном языке (русском или английском) и преобразует его в SQL-запрос через Google Gemini LLM, затем выполняет его на подключённой базе данных и возвращает результат.

## 1.2. Pipeline

```
Пользователь → FastAPI → Preprocessor → Schema Manager → Prompt Builder → Gemini → SQL Validator → Executor → Результат
```

Все преобразования идут исключительно через Gemini — никакого keyword matching или правил.

## 1.3. Поддерживаемые СУБД

| СУБД | Режим | Адаптер |
|------|-------|---------|
| SQLite | Файловый / через адаптер | `executor.py` / `db_adapter.py` |
| PostgreSQL | Через адаптер | `db_adapter.py` |
| MySQL | Через адаптер | `db_adapter.py` |

## 1.4. Ключевые принципы

| Принцип | Описание |
|---------|----------|
| LLM-only | Никаких правил — только Gemini генерирует SQL |
| Безопасность | Только SELECT, блокировка DROP/DELETE/INSERT/UPDATE |
| Динамическая схема | Интроспекция через PRAGMA (SQLite) или information_schema |
| Read-only | Все запросы выполняются в режиме только для чтения |
| Модульность | Каждый модуль core/ изолирован и тестируется независимо |


# 2. Структура проекта

```
prototype/
├── api/
│   └── server.py          # FastAPI сервер (REST API)
├── core/
│   ├── pipeline.py         # Оркестратор пайплайна
│   ├── llm_client.py       # Gemini API клиент
│   ├── schema_manager.py   # Интроспекция схемы БД
│   ├── prompt_builder.py   # Сборка промпта для LLM
│   ├── sql_validator.py    # Валидация и безопасность SQL
│   ├── executor.py         # Выполнение SQL (SQLite, read-only)
│   ├── preprocessor.py     # Очистка текста
│   └── db_adapter.py       # Адаптер PostgreSQL/MySQL
├── website/
│   ├── index.html          # Главная страница (SPA)
│   ├── styles.css          # Стили
│   ├── script.js           # Логика фронтенда
│   └── report.html         # Страница отчёта
├── run.py                  # Точка входа (uvicorn)
├── test_core.py            # Тесты ядра (без API ключа)
├── test_proto.py           # E2E тесты (требуют Gemini)
├── test_comprehensive.py   # Полный набор (~160 запросов)
├── test_introspect.py      # Проверка интроспекции БД
├── requirements.txt        # Зависимости
├── Procfile                # Heroku
├── vercel.json             # Vercel (фронтенд)
└── TECHNICAL_DESCRIPTION.md
```


# 3. API сервер (FastAPI)

**Файл:** `api/server.py`

## 3.1. Эндпоинты

| Метод | Путь | Назначение |
|-------|------|-----------|
| `POST` | `/api/query` | Главный: NL → SQL → выполнение |
| `GET` | `/api/schema` | Схема активной БД |
| `GET` | `/api/health` | Проверка состояния |
| `POST` | `/api/upload-database` | Загрузка `.db` файла |
| `POST` | `/api/connect-db` | Подключение к PostgreSQL/MySQL |

## 3.2. Pydantic модели

- `QueryRequest` — входящий запрос: `{query: str}`
- `QueryResponse` — результат: SQL, строки, колонки, ошибки, timing
- `SchemaResponse` — схема: таблицы, колонки, размеры
- `ConnectRequest` — параметры подключения к СУБД
- `HealthResponse` — статус системы

## 3.3. Особенности

- **CORS middleware** — разрешены все источники
- **StaticFiles** — раздаёт `website/` как SPA
- **Auto-reload** — не используется в продакшене
- **Swagger** — авто-документация на `/docs`


# 4. Core модули

## 4.1. Preprocessor (`preprocessor.py`)

Минимальная очистка текста:
- Удаление лишних пробелов
- Удаление управляющих символов
- **Без** извлечения сущностей, классификации, keyword matching

```python
clean_query("  Find   all   employees  ")  # → "Find all employees"
```

## 4.2. Schema Manager (`schema_manager.py`)

Динамическая интроспекция SQLite через `PRAGMA`:
- `introspect_schema(db_path)` — читает таблицы, колонки, типы, FK, примеры данных
- `format_schema_for_prompt(schema)` — форматирует для LLM-промпта
- `get_schema_summary(schema)` — краткая сводка для UI

**Не использует хардкод** — всё читается из БД.

## 4.3. Prompt Builder (`prompt_builder.py`)

Собирает промпт для Gemini из:
1. **System instructions** — роль SQL-эксперта, правила (только SELECT, только из схемы)
2. **Схема БД** — таблицы, колонки, внешние ключи, примеры данных
3. **Few-shot примеры** — 7 пар (запрос → SQL) для повышения точности
4. **Запрос пользователя**

Учитывает диалект СУБД (SQLite/PostgreSQL/MySQL).

## 4.4. LLM Client (`llm_client.py`)

Клиент для Google Gemini API:
- Использует **только** новый SDK: `google-genai`
- Модель по умолчанию: `gemini-2.5-flash` (меняется через `GEMINI_MODEL`)
- Temperature: 0.2 (почти детерминированно)
- `_extract_sql()` — извлекает чистый SQL из ответа (убирает markdown, пояснения)
- API ключ из `GEMINI_API_KEY` (окружение или `.env`)

## 4.5. SQL Validator (`sql_validator.py`)

Проверка безопасности и синтаксиса:
- **Блокировка** опасных операторов: DROP, DELETE, INSERT, UPDATE, ALTER, CREATE, TRUNCATE, etc.
- **Только SELECT/WITH** — проверка первого слова
- **Один запрос** — множественные statements запрещены
- **Форматирование** — через `sqlparse` (upper case keywords, reindent)

## 4.6. Executor (`executor.py`)

Безопасное выполнение SQL (SQLite):
- **Read-only** транзакции (`PRAGMA query_only = ON`)
- **URI mode** — `file:path?mode=ro`
- **Лимит строк** — `max_rows` (по умолчанию 100)
- **Row factory** — строки возвращаются как `dict`

## 4.7. Pipeline (`pipeline.py`)

Оркестратор — связывает все модули в единый процесс:

```
1. Preprocessing  →  clean_query()
2. Schema         →  introspect_schema() / adapter.get_full_schema()
3. Prompt         →  build_prompt()
4. LLM            →  generate_sql()
5. Validation     →  validate()
6. Execution      →  execute_query() / adapter.execute()
```

Каждый шаг логирует статус, время и детали в `result["steps"]`.

## 4.8. DB Adapter (`db_adapter.py`)

Универсальный адаптер для разных СУБД:
- `connect()` / `close()` / `is_connected`
- `get_tables()` — список таблиц
- `get_full_schema()` — полная схема
- `execute(sql)` — выполнение запроса


# 5. База данных

## 5.1. Загрузка базы данных

База данных загружается пользователем через веб-интерфейс (`.db` файл через `/api/upload-database`) или подключается к внешней СУБД (PostgreSQL/MySQL через `/api/connect-db`). Также можно указать путь к `.db` файлу через `--db` при запуске.

## 5.2. Связи (пример)

```
employees.manager_id  →  employees.employee_id  (самоссылка)
tasks.assignee_id     →  employees.employee_id
tasks.project_id      →  projects.project_id
comments.task_id      →  tasks.task_id
comments.author_id    →  employees.employee_id
```



# 6. Pipeline

**Пример:** *«Найди всех сотрудников отдела разработки»*

| Шаг | Модуль | Результат |
|-----|--------|-----------|
| 1 | Preprocessor | `"Найди всех сотрудников отдела разработки"` |
| 2 | Schema Manager | 4 таблицы: employees(15), projects(8), tasks(25), comments(30) |
| 3 | Prompt Builder | ~1600 символов: инструкции + схема + few-shot + запрос |
| 4 | Gemini | `SELECT * FROM employees WHERE department = 'Разработка'` |
| 5 | Validator | PASSED, форматирован |
| 6 | Executor | 6 rows (Иванов, Петрова, Васильев, Белова, Новикова, Алексеев) |


# 7. Веб-интерфейс (Frontend)

**Директория:** `prototype/website/`

Чистый HTML/CSS/JS (без фреймворков):
- `index.html` — главная SPA: поле ввода, результаты, схема БД
- `report.html` — страница отчёта
- `styles.css` — стили (адаптивный дизайн)
- `script.js` — логика: запросы к API, отображение результатов

Раздаётся FastAPI как статические файлы.


# 8. Тестирование

## 8.1. test_core.py — базовые тесты

Тестирует модули **без API-ключа Gemini**:
- Preprocessor: очистка текста
- SQL Validator: валидация, блокировка DROP
- Schema Manager: чтение схемы, форматирование
- Prompt Builder: сборка промпта
- LLM Client: извлечение SQL из ответа
- Executor: выполнение SQL

```bash
python3 prototype/test_core.py
```

## 8.2. test_proto.py — E2E тесты

7 запросов через полный pipeline (требует `GEMINI_API_KEY`).

## 8.3. test_comprehensive.py — полный набор

~160 тестовых запросов по категориям:
- Простые SELECT, COUNT
- Фильтрация (по отделу, зарплате, дате, должности)
- Сортировка, агрегации
- GROUP BY, HAVING
- JOIN (все комбинации таблиц)
- Самоссылка (manager_id)
- Поиск по тексту, работа с датами
- Сложные аналитические запросы
- Естественные формулировки
- Негативные тесты (несуществующие таблицы)

Rate limiting: 4s между запросами (Gemini free tier = 15 RPM).


# 9. Запуск проекта

## 9.1. Установка

```bash
cd prototype
pip install -r requirements.txt
```

## 9.2. Конфигурация

Создать `.env` файл в `prototype/`:
```
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

Получить ключ: https://aistudio.google.com/apikey

## 9.3. Загрузка БД

Загрузите `.db` файл через веб-интерфейс или укажите путь через `--db`.

## 9.4. Запуск сервера

```bash
python run.py                # http://localhost:8000
python run.py --port 3000    # другой порт
python run.py --no-browser   # без авто-открытия браузера
```

## 9.5. Запуск тестов

```bash
python test_core.py           # базовые (без API ключа)
python test_proto.py          # E2E (нужен GEMINI_API_KEY)
python test_comprehensive.py  # полный набор ~160 запросов (нужен GEMINI_API_KEY)
python test_introspect.py     # интроспекция БД
```


# 10. Стек технологий

| Компонент | Технология |
|-----------|-----------|
| Язык | Python 3.x |
| Веб-фреймворк | FastAPI + uvicorn |
| LLM | Google Gemini (`google-genai`) |
| Базы данных | SQLite, PostgreSQL, MySQL |
| SQL парсинг | `sqlparse` |
| Валидация | Pydantic v2 |
| Фронтенд | HTML5 + CSS + vanilla JS |
| Деплой | Vercel (фронтенд), Heroku (бэкенд) |
| Окружение | `python-dotenv` |

---

*Документация обновлена: июнь 2026. Соответствует текущей архитектуре.*
