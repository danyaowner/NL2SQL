"""
generate_report.py — Генерирует HTML-отчёт с результатами работы прототипа
Запуск: python3 generate_report.py
Открыть: website/report.html (просто дважды кликнуть в браузере)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.pipeline import process_nl_query
from core.schema_manager import introspect_schema, get_schema_summary
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_company.db")


def process_query_full(query_text):
    """Process NL query through Gemini pipeline - NO keyword matching."""
    if not os.path.exists(DB_PATH):
        return {"query": query_text, "sql": None, "rows": None, "error": "DB not found", "success": False}
    result = process_nl_query(query_text, DB_PATH)
    # Convert to old format for backward compatibility
    return {
        "query": query_text,
        "sql": result.get("formatted_sql") or result.get("sql"),
        "rows": result.get("rows"),
        "error": result.get("error"),
        "success": result.get("success", False),
    }


def rows_to_html_table(rows):
    if not rows:
        return "<p style='color: var(--text2); padding: 20px; text-align: center;'>Нет данных</p>"
    cols = list(rows[0].keys())
    html = "<table class='result-table'><thead><tr>"
    for col in cols:
        html += f"<th>{col}</th>"
    html += "</tr></thead><tbody>"
    for row in rows:
        html += "<tr>"
        for col in cols:
            val = str(row[col]) if row[col] is not None else ""
            html += f"<td>{val}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html


TEST_QUERIES = [
    "Найди всех сотрудников отдела разработки",
    "Сколько задач в каждом проекте",
    "Средняя зарплата по отделам",
    "Покажи сотрудников с зарплатой выше 100000",
    "Find all employees in sales department",
]


def main():
    print("=" * 50)
    print("  NL2SQL Prototype - Генерация отчёта")
    print("=" * 50)
    all_results = []
    for i, q in enumerate(TEST_QUERIES, 1):
        print(f"\n[{i}] {q}")
        r = process_query_full(q)
        all_results.append(r)
        if r["sql"]:
            print(f"  SQL: {r['sql'][:60].replace(chr(10), ' ')}...")
        print(f"  {'OK' if r['success'] else 'ERR'}: {r.get('error', '')}")
        if r.get("rows") is not None:
            print(f"  Rows: {len(r['rows'])}")

    # Schema via introspection
    schema_info = {}
    if os.path.exists(DB_PATH):
        schema = introspect_schema(DB_PATH)
        schema_info = get_schema_summary(schema)

    # Build HTML
    html = '<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>NL2SQL Отчёт</title><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"><style>'
    html += '*{margin:0;padding:0;box-sizing:border-box}body{font-family:Inter,sans-serif;background:#0a0e1a;color:#e8edf5;padding:32px 24px;max-width:1200px;margin:0 auto;line-height:1.5}'
    html += 'h1{font-size:28px;font-weight:800;background:linear-gradient(135deg,#60a5fa,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px}'
    html += '.subtitle{color:#8899b4;font-size:14px;margin-bottom:32px}'
    html += '.card{background:#111827;border:1px solid #1e2d4a;border-radius:12px;padding:24px;margin-bottom:20px}'
    html += '.card h3{font-size:16px;font-weight:600;margin-bottom:12px;display:flex;align-items:center;gap:8px}'
    html += '.badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600}'
    html += '.badge-ok{background:rgba(34,197,94,0.15);color:#22c55e}.badge-err{background:rgba(239,68,68,0.15);color:#ef4444}'
    html += '.sql{background:#0d1117;border:1px solid #1a2332;border-radius:8px;padding:16px;font-family:"JetBrains Mono",monospace;font-size:14px;color:#7ec699;overflow-x:auto;margin-bottom:16px;white-space:pre-wrap}'
    html += 'table{width:100%;border-collapse:collapse;font-size:14px;border:1px solid #1e2d4a;border-radius:8px;overflow:hidden}'
    html += 'th{background:#1a2236;padding:10px 14px;text-align:left;font-weight:600;font-size:13px;color:#8899b4;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid #1e2d4a}'
    html += 'td{padding:8px 14px;border-bottom:1px solid rgba(30,45,74,0.5)}'
    html += 'tr:hover td{background:rgba(59,130,246,0.03)}'
    html += '.schema-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;margin-top:32px}'
    html += '.schema-table{background:#1a2236;border:1px solid #1e2d4a;border-radius:8px;padding:16px}'
    html += '.schema-table h3{font-size:15px;font-weight:600;margin-bottom:4px;color:#3b82f6}'
    html += '.schema-table .desc{font-size:12px;color:#8899b4;margin-bottom:12px}'
    html += '.schema-table li{font-size:13px;padding:3px 0;color:#8899b4;list-style:none}'
    html += '.schema-table li::before{content:"\u25b8";color:#3b82f6;margin-right:6px}'
    html += '.row-count{color:#22c55e;font-weight:600;font-size:13px;margin-bottom:8px}'
    html += '.footer{margin-top:48px;padding-top:16px;border-top:1px solid #1e2d4a;color:#8899b4;font-size:13px;text-align:center}'
    html += '</style></head><body>'
    html += '<h1>NL2SQL Prototype — Отчёт</h1><p class="subtitle">Результаты работы прототипа</p>'

    for r in all_results:
        cls = "ok" if r["success"] else "err"
        txt = "OK" if r["success"] else "ERR"
        html += f'<div class="card"><h3>{r["query"]} <span class="badge badge-{cls}">{txt}</span></h3>'
        if r.get("sql"):
            html += f'<div class="sql">{r["sql"]}</div>'
        if r.get("rows") is not None:
            html += f'<div class="row-count">Rows: {len(r["rows"])}</div>'
            html += rows_to_html_table(r["rows"])
        if r.get("error"):
            html += f'<div style="color:#ef4444;font-size:14px">Error: {r["error"]}</div>'
        html += '</div>'

    html += '<h2 style="margin-top:40px;font-size:22px;font-weight:700">Schema</h2><div class="schema-grid">'
    for name, info in schema_info.items():
        html += f'<div class="schema-table"><h3>{name}</h3><div class="desc">{info["description"]}</div><ul>'
        for cn, ct in info["columns"]:
            html += f"<li>{cn}: {ct}</li>"
        html += '</ul></div>'
    html += '</div><div class="footer">NL2SQL Prototype</div></body></html>'

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "website")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "report.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nOK -> {out_path}")
    print(f"Open in browser: {out_path}")


if __name__ == "__main__":
    main()
