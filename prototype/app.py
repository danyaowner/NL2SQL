"""
app.py -- Streamlit UI для NL2QL прототипа
"""
import sys, os

import streamlit as st
st.set_page_config(page_title="NL2SQL Prototype", layout="wide")

# Add current dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nl_module import process_query
from schema_selector import select_schema, SCHEMA
from validator import validate

HAS_DB = False
try:
    import sqlite3
    from init_db import get_schema, DB_PATH
    HAS_DB = True
except Exception:
    pass

# ---------- init DB if needed ----------
if HAS_DB and not os.path.exists(DB_PATH):
    from init_db import main as init_db
    try:
        init_db()
    except Exception:
        pass

# ---------- lazy imports ----------
try:
    from sql_generator import generate as gen_sql
    HAS_SQL_GEN = True
except Exception:
    HAS_SQL_GEN = False


def run_sql(sql: str):
    """Выполнение SQL и возврат результатов."""
    if not HAS_DB:
        return None, "sqlite3 не доступен"
    if not os.path.exists(DB_PATH):
        return None, "База данных не найдена. Запустите init_db.py"
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows, None
    except Exception as e:
        return None, str(e)


# ---------- UI ----------
st.title("\U0001F50D NL2SQL Prototype")
st.markdown("Преобразование запросов на естественном языке в SQL")

col1, col2 = st.columns([2, 1])

with col2:
    st.subheader("\U0001F4DB Схема БД")
    for t_name, t_info in SCHEMA.items():
        with st.expander(f"{t_name}"):
            for c_name, c_desc in t_info["columns"].items():
                st.code(f"{c_name}: {c_desc}", language="text")

with col1:
    st.subheader("\U0001F4AC Запрос")
    query = st.text_input(
        "Введите запрос на русском или английском:",
        placeholder="Например: Найди всех сотрудников отдела разработки",
        label_visibility="collapsed",
    )

    if query:
        with st.status("\U0001F504 Обработка...") as status:
            # 1. NL обработка
            status.update(label="1/5 \U0001F50D Анализ запроса...")
            qi = process_query(query)

            # 2. Селекция схемы
            status.update(label="2/5 \U0001F4DA Выбор схемы...")
            si = select_schema(qi["cleaned"])

            # 3. Генерация SQL
            status.update(label="3/5 \U0001F4DD Генерация SQL...")
            if HAS_SQL_GEN:
                sql = gen_sql(qi, si, mode="demo")
            else:
                sql = None

            # 4. Валидация
            status.update(label="4/5 \u2705 Валидация...")
            if sql:
                db_schema = get_schema() if HAS_DB else {}
                valid, msg = validate(sql, db_schema)
            else:
                valid, msg = False, "Генератор SQL не загружен"

            # 5. Выполнение
            status.update(label="5/5 \U0001F680 Выполнение...")
            if sql:
                rows, err = run_sql(sql)
            else:
                rows, err = None, "Нет SQL"

            status.update(label="\u2705 Готово", state="complete")

        # ---------- Results ----------
        col_q, col_s = st.columns(2)

        with col_q:
            with st.expander("\U0001F50D Анализ запроса", expanded=True):
                kv = {
                    "\U0001F30D Язык": "Русский" if qi["language"] == "ru" else "English",
                    "\U0001F4CB Тип": qi["query_type"],
                    "\U0001F4E6 Сущности": ", ".join(qi["entities"]) if qi["entities"] else "—",
                    "\U0001F522 Числа": str(qi["numbers"]) if qi["numbers"] else "—",
                }
                for k, v in kv.items():
                    st.markdown(f"**{k}:** {v}")

        with col_s:
            with st.expander("\U0001F4DA Выбранные таблицы", expanded=True):
                for t in si["tables"]:
                    pk = "\u2B50"
                    cols = si["columns"].get(t, [])
                    st.markdown(f"**{pk} {t}** ({', '.join(cols[:4])}{'...' if len(cols) > 4 else ''})")

        # SQL Result
        st.subheader("\U0001F4DD Сгенерированный SQL")
        if sql:
            st.code(sql, language="sql")
        else:
            st.error("Не удалось сгенерировать SQL")

        # Validation
        if valid:
            st.success(f"\u2705 Валидация пройдена")
        else:
            st.warning(f"\u26A0\uFE0F {msg}")

        # Execution results
        if rows is not None:
            st.subheader(f"\U0001F4CA Результаты ({len(rows)} строк)")
            if rows:
                st.dataframe(rows, use_container_width=True)
            else:
                st.info("\U0001F4ED Нет данных, удовлетворяющих условиям")
        elif err:
            st.error(f"\u274C Ошибка выполнения: {err}")

    else:
        st.info("\U0001F447 Введите запрос на естественном языке для генерации SQL")

# ---------- Footer ----------
st.divider()
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    st.caption(f"Режим: **demo** (без API)")
with col_f2:
    st.caption("\U0001F4E6 База данных: " + ("test_company.db" if HAS_DB else "не подключена"))
with col_f3:
    st.caption("\U0001F4F1 Streamlit UI \u00B7 NL2SQL Prototype")
