# NL2SQL Prototype - Техническая документация

## Разработка прототипа интеллектуального интерфейса для генерации SQL-запросов на основе естественного языка

---

# Содержание

1. [Общая архитектура](#1-общая-архитектура)
2. [Структура проекта](#2-структура-проекта)
3. [nl_module.py - Обработка естественного языка](#3-nl-module-py)
4. [schema_selector.py - Селекция схемы данных](#4-schema-selector-py)
5. [sql_generator.py - Генерация SQL](#5-sql-generator-py)
6. [validator.py - Валидация SQL](#6-validator-py)
7. [app.py - Streamlit UI](#7-app-py)
8. [init_db.py - База данных](#8-init-db-py)
9. [test_proto.py - End-to-end тесты](#9-test-proto-py)
10. [Схема данных](#10-схема-данных)
11. [Полный pipeline обработки запроса](#11-pipeline)
12. [Примеры работы](#12-примеры-работы)
13. [Известные проблемы и ограничения](#13-проблемы)
14. [Пути улучшения](#14-пути-улучшения)


# 1. Общая архитектура

## 1.1. Концепция

Система NL2SQL представляет собой пайплайн из 5 последовательных модулен, каждый из которых выполняет строго определённую функцию преобразования.



## 1.2. Ключевые принципы проектирования

| Принцип | Обоснование |
|---------|-------------|
| Lazy imports | Приложение не падает при отсутствии зависимостей |
| Два режима | Demo (бесплатно) и Full (OpenAI GPT-4o) |
| Правила, а не ML | NLP на словарях и регэкспах |
| Изоляция модулей | Каждый модуль работает независимо |
| Graceful degradation | Информативные сообщения об ошибках |

## 1.3. Формат данных

Модули общаются через словари Python.


**qi (NLP-анализ):**




# 2. Структура проекта





# 3. Модуль 1: nl_module.py - Обработка естественного языка

**Назначение:** Преобразование текста в структурированные данные.

**Функции:**
| Функция | Назначение |
|---------|-----------|
| clean_query() | Удаление спецсимволов, лишних пробелов |
| detect_language() | Определение RU/EN (langdetect или кириллица) |
| extract_entities() | Поиск таблиц (employees) и отделов (department:) |
| classify_query() | Определение типа: count/find/aggregate/compare |
| extract_conditions() | Извлечение условии (salary > 100000) |
| extract_numbers() | Числа из текста (цифры + прописью) |
| process_query() | Главная - вызывает все функции и возвращает dict |

**Типы запросов:**
- count: сколько, количество, how many, count
- find: найди, покажи, find, show, display
- aggregate: среднее, сумма, avg, sum, maximum
- compare: сравни, топ, compare, top, highest



# 4. Модуль 2: schema_selector.py - Селекция схемы данных

**Назначение:** Выбор релевантных таблиц и колонок.

## 4.1. select_tables_keyword()
Скоринг таблиц по ключевым словам. Если найдено -> score +1. Если таблица упомянута явно -> +3.
Связанные таблицы добавляются через TABLE_RELATIONS: tasks -> employees + projects.
Fallback: ["employees", "projects"]

## 4.2. select_columns_keyword()
Сортирует колонки каждой таблицы по релевантности.

## 4.3. select_schema()
Главная функция. Возвращает dict с tables, columns и text для OpenAI.



# 5. Модуль 3: sql_generator.py - Генерация SQL

**Назначение:** Сердце системы. Преобразует структурированный запрос в SQL.

## 5.1. Два режима
- **Demo** - генерация по правилам, без API
- **Full** - через OpenAI GPT-4o (few-shot с 3 примерами)

## 5.2. Demo-режим: _demo_generate()

**SELECT:** count->COUNT(*), aggregate->AVG()/SUM()/MAX(), find->*
**FROM/JOIN:** автоматический выбор JOIN по комбинации таблиц
**WHERE:** из conditions + entities (department:) через AND
**GROUP BY:** по project_name или department
**ORDER BY/LIMIT:** для топ/best/highest

## 5.3. Full-режим: _openai_generate()
Few-shot промптинг: 3 примера + схема БД + запрос пользователя.
Модель: gpt-4o, temperature=0.2, max_tokens=1000.
Постобработка: извлечение SQL из markdown-ответа.



# 6. Модуль 4: validator.py - Валидация SQL

**Назначение:** Проверка SQL на корректность и безопасность.

## 6.1. validate_syntax()
1. Парсинг через sqlparse
2. Проверка: первый токен = SELECT
3. Блокировка: DROP, DELETE, INSERT, UPDATE, ALTER, CREATE, TRUNCATE

## 6.2. validate_schema()
Проверка существования таблиц в схеме БД.

## 6.3. validate()
Объединяет оба шага + форматирует SQL через sqlparse.
Возвращает (True, formatted_sql) или (False, error_message).



# 7. Модуль 5: app.py - Streamlit UI

**Назначение:** Веб-интерфейс.

## 7.1. Структура
2 колонки (2:1):
- **col1 (левая):** поле ввода, прогресс 1/5->5/5, результаты
- **col2 (правая):** схема БД в expander-секция

## 7.2. 5 шагов обработки
1/5 NLP-анализ (process_query)
2/5 Выбор схемы (select_schema)
3/5 Генерация SQL (generate)
4/5 Валидация (validate)
5/5 Выполнение (run_sql)

## 7.3. run_sql()
conn.row_factory = sqlite3.Row - строки как dict для st.dataframe.



# 8. Модуль 6: init_db.py - База данных

**Назначение:** Создание и наполнение тестовой БД SQLite.

**4 таблицы:**
- employees - 15 сотрудников (5 отделов)
- projects - 8 проектов (active/completed/on_hold)
- tasks - 25 задач (low/medium/high/critical priority)
- comments - 30 комментариев (28 публичных, 2 внутренних)

**Связи:** employees.employee_id -> tasks.assignee_id -> comments.author_id
projects.project_id -> tasks.project_id
tasks.task_id -> comments.task_id
employees.manager_id -> employees.employee_id (self-ref)

**get_schema():** возвращает мета-описание для валидатора.
**--clean:** удаляет .db перед созданием.



# 9. Модуль 7: test_proto.py - E2E тесты

**Назначение:** Сквозное тестирование.

**6 тестов:**
1. Найди всех сотрудников отдела разработки
2. Сколько задач в каждом проекте
3. Покажи сотрудников с зарплатой выше 100000
4. Средняя зарплата по отделам (проблема с priority)
5. Show all employees in sales department
6. Find projects with budget over 300000

**Результат:** 6/6 passed.



# 10. Схема данных

## Распределение сотрудников

| Отдел | Кол-во | Зарплаты |
|-------|--------|----------|
| Разработка | 6 | 80000-180000 |
| Продажи | 3 | 70000-120000 |
| Маркетинг | 2 | 90000-130000 |
| Бухгалтерия | 2 | 95000-105000 |
| HR | 2 | 70000-110000 |



# 11. Полный pipeline

**Запрос:** "Найди всех сотрудников отдела разработки"

**Шаг 1:** process_query -> lang=ru, type=find, entities=[employees, department:Разработка]
**Шаг 2:** select_schema -> tables=[employees]
**Шаг 3:** generate -> SELECT * FROM employees WHERE department = "Разработка"
**Шаг 4:** validate -> PASSED
**Шаг 5:** run_sql -> 6 rows (Иванов, Петрова, Васильев, ...)



# 12. Примеры работы

| # | Запрос | SQL | Результат |
|---|--------|-----|-----------|
| 1 | Найди всех сотрудников отдела разработки | SELECT * FROM employees WHERE department = "Разработка" | 6 rows |
| 2 | Сколько задач в каждом проекте | SELECT p.project_name, COUNT(*) FROM projects p LEFT JOIN tasks t ... GROUP BY project_name | 8 rows |
| 3 | Сотрудники с зарплатой выше 100000 | SELECT * FROM employees WHERE salary > 100000 | 8 rows |
| 4 | Средняя зарплата по отделам | SELECT department, AVG(salary) FROM employees GROUP BY department | 5 rows |
| 5 | Show all employees in sales | SELECT * FROM employees WHERE department = "Продажи" | 3 rows |
| 6 | Find projects with budget > 300000 | SELECT * FROM projects WHERE budget > 300000 | 3 rows |



# 13. Известные проблемы и ограничения

## Критические
- **Путаница "средняя"**: слово "средн" совпадает для AVG и medium priority
  Запрос "средняя зарплата" добавляет лишнее условие priority=medium

## Функциональные
- Только AND, нет OR
- Только SQLite, нет PostgreSQL/MySQL
- Одна фиксированная БД, нет переключения
- Нет кэширования
- Ограниченный словарь (~30 ключевых слов)
- Нет подзапросов в demo-режиме
- Однопоточный Streamlit
- Full-режим требует платный API-ключ OpenAI



# 14. Пути улучшения

## Quick wins
1. Исправить путаницу "средняя" - проверять контекст перед добавлением priority
2. Дополнить словари синонимов
3. Добавить поддержку OR в WHERE
4. Кэширование частых запросов

## Среднесрочные
1. Sentence-transformers вместо ключевых слов
2. Динамическая схема через PRAGMA table_info
3. Поддержка PostgreSQL через psycopg2
4. Оконные функции (ROW_NUMBER, RANK)
5. История запросов в UI

## Фундаментальные
1. Локальная LLM (Llama 3, Mistral) вместо правил
2. Multi-Turn диалог с уточняющими вопросами
3. RAG с векторной БД для повторного использования
4. EXPLAIN ANALYZE перед выполнением
5. Дашборд метрик (latency, accuracy)

---
*Документация создана автоматически на основе анализа исходного кода.*







# 15. Запуск проекта

## 15.1. Локальный запуск (Windows cmd)

Откройте **командную строку (cmd)** или **PowerShell** и выполните:

```cmd
cd C:/Users/Danila/OneDrive/Desktop/agent/prototype
python -m pip install -r requirements.txt
python init_db.py --clean
python -m streamlit run app.py
```

После запуска Streamlit сам откроет браузер с адресом **http://localhost:8501**

## 15.2. Запуск из WSL (Linux)

```bash
cd /mnt/c/Users/Danila/OneDrive/Desktop/agent/prototype
pip3 install -r requirements.txt
python3 init_db.py --clean
python3 -m streamlit run app.py --server.headless true
```

Доступ в браузере Windows: **http://172.19.2.43:8501**

## 15.3. Запуск из клонированного репозитория

```cmd
cd C:/Users/Danila/OneDrive/Desktop
git clone https://github.com/danyaowner/NL2SQL.git
cd NL2SQL\prototype
python -m pip install -r requirements.txt
python init_db.py --clean
python -m streamlit run app.py
```

## 15.4. Инициализация базы данных

```cmd
cd prototype
python init_db.py --clean
```

Флаг --clean удаляет существующую БД перед созданием.

## 15.5. Запуск тестов

```cmd
cd prototype
python test_proto.py
```

Ожидаемый результат: **All 6 tests PASSED**

## 15.6. Установка зависимостей

```cmd
cd prototype
python -m pip install -r requirements.txt
```

### Полный список зависимостей:

- streamlit - веб-интерфейс
- sqlparse - форматирование SQL
- langdetect - определение языка (RU/EN)
- nltk - NLP-обработка
- dateparser - парсинг дат
- openai - (опционально) для FULL-режима с GPT-4o

---
*Документация создана автоматически на основе анализа исходного кода.*
