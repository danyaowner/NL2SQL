"""
web_app.py — Flask веб-сайт для NL2SQL Prototype
Запуск: py web_app.py (Windows) / python3 web_app.py (WSL)
Открыть: http://localhost:5000
"""
import os, sys, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify, render_template

from nl_module import process_query
from schema_selector import select_schema, SCHEMA
from validator import validate
from sql_generator import generate as gen_sql
import sqlite3

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_company.db")


def run_sql(sql):
    if not os.path.exists(DB_PATH):
        return None, "BD not found"
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


def process_query_full(text):
    steps = []
    res = {"query": text, "sql": None, "rows": None, "error": None, "success": False, "steps": steps}
    
    # Step 1: Natural language understanding
    try:
        qi = process_query(text)
        steps.append({
            "name": "Анализ запроса",
            "status": "ok",
            "details": f"Язык: {qi.get('language','?')}, "
                       f"Тип: {qi.get('query_type','?')}, "
                       f"Сущности: {qi.get('entities', [])}"
        })
    except Exception as e:
        steps.append({"name": "Анализ запроса", "status": "error", "details": str(e)})
        res["error"] = str(e)
        return res
    
    # Step 2: Schema selection
    try:
        si = select_schema(qi["cleaned"])
        steps.append({
            "name": "Выбор схемы",
            "status": "ok",
            "details": f"Таблицы: {', '.join(si.get('tables', []))}"
        })
    except Exception as e:
        steps.append({"name": "Выбор схемы", "status": "error", "details": str(e)})
        res["error"] = str(e)
        return res
    
    # Step 3: SQL generation
    try:
        sql = gen_sql(qi, si, mode="demo")
        res["sql"] = sql
        if sql:
            steps.append({"name": "Генерация SQL", "status": "ok", "sql": sql})
        else:
            steps.append({"name": "Генерация SQL", "status": "error", "details": "Не удалось сгенерировать SQL"})
            res["error"] = "SQL generation failed"
            return res
    except Exception as e:
        steps.append({"name": "Генерация SQL", "status": "error", "details": str(e)})
        res["error"] = str(e)
        return res
    
    # Step 4: Validation
    try:
        valid, msg = validate(sql, {})
        if valid:
            steps.append({"name": "Валидация", "status": "ok"})
        else:
            steps.append({"name": "Валидация", "status": "warning", "details": msg})
    except Exception as e:
        steps.append({"name": "Валидация", "status": "error", "details": str(e)})
    
    # Step 5: Execution
    try:
        rows, err = run_sql(sql)
        if rows is not None:
            res["rows"] = rows
            res["success"] = True
            steps.append({"name": "Выполнение", "status": "ok", "details": f"Найдено строк: {len(rows)}"})
        else:
            steps.append({"name": "Выполнение", "status": "error", "details": err})
            res["error"] = err
    except Exception as e:
        steps.append({"name": "Выполнение", "status": "error", "details": str(e)})
        res["error"] = str(e)
    
    return res


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/query", methods=["POST"])
def api_query():
    data = request.get_json()
    if not data or "query" not in data:
        return jsonify({"success": False, "error": "No query provided"})
    result = process_query_full(data["query"])
    # Convert rows to serializable format
    if result.get("rows"):
        result["rows"] = [dict(r) if hasattr(r, "keys") else r for r in result["rows"]]
    return jsonify(result)


@app.route("/api/schema")
def api_schema():
    result = {}
    for t_name, t_info in SCHEMA.items():
        result[t_name] = {
            "description": t_info["description"],
            "columns": t_info["columns"]
        }
    return jsonify(result)


@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok", "db_exists": os.path.exists(DB_PATH)})


if __name__ == "__main__":
    print("=" * 50)
    print("  NL2SQL Prototype - Web Interface")
    print("  " + "=" * 30)
    print(f"  Open: http://localhost:5000")
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    app.run(debug=False, host="127.0.0.1", port=5000)
