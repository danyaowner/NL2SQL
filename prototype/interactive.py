"""
interactive.py - Interactive NL2SQL Prototype
Usage: python3 interactive.py
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nl_module import process_query
from schema_selector import select_schema, SCHEMA
from validator import validate
from sql_generator import generate as gen_sql
import sqlite3

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
    res = {"query": text, "sql": None, "rows": None, "error": None, "success": False}
    try:
        qi = process_query(text)
        si = select_schema(qi["cleaned"])
        sql = gen_sql(qi, si, mode="demo")
        res["sql"] = sql
        if sql:
            valid, msg = validate(sql, {})
            if valid:
                rows, err = run_sql(sql)
                if rows is not None:
                    res["rows"] = rows
                    res["success"] = True
                else:
                    res["error"] = err
            else:
                res["error"] = msg
        else:
            res["error"] = "Failed to generate SQL"
    except Exception as e:
        res["error"] = str(e)
    return res


def print_table(rows):
    if not rows:
        return
    cols = list(rows[0].keys())
    widths = {c: min(max(len(str(c)), max((len(str(r[c])) if r[c] else 0 for r in rows))), 50) for c in cols}
    sep = "  +" + "+".join("-" * (widths[c] + 2) for c in cols) + "+"
    hdr = "  |" + "|".join(" " + c.ljust(widths[c]) + " " for c in cols) + "|"
    print(sep)
    print(hdr)
    print(sep.replace("-", "="))
    for row in rows:
        line = "  |"
        for c in cols:
            v = str(row[c]) if row[c] is not None else ""
            line += " " + v.ljust(widths[c]) + " |"
        print(line)
    print(sep)
    print(f"  -> Rows: {len(rows)}")


def main():
    print()
    print("=" * 60)
    print("  NL2SQL Prototype - Interactive Console")
    print("  Type a question in Russian or English")
    print("=" * 60)
    print("  Commands: /examples /schema /quit")
    print("=" * 60)

    EXAMPLES = [
        "Найди всех сотрудников отдела разработки",
        "Сколько задач в каждом проекте",
        "Покажи сотрудников с зарплатой >100000",
        "Find all employees in sales department",
    ]

    while True:
        try:
            q = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if not q:
            continue
        if q in ("/quit", "/exit", "exit"):
            print("Bye!")
            break
        if q == "/schema":
            print("\n" + "=" * 60)
            for name, info in SCHEMA.items():
                print(f"  [{name}] {info['description']}")
                for cn, ct in info["columns"].items():
                    print(f"    {cn}: {ct}")
            print("=" * 60)
            continue
        if q == "/examples":
            print()
            for i, ex in enumerate(EXAMPLES, 1):
                print(f"  {i}. {ex}")
            continue

        print("\n" + "-" * 60)
        r = process_query_full(q)

        if r["sql"]:
            print("\n  SQL:")
            for line in r["sql"].split("\n"):
                print(f"    {line}")

        if r["rows"] is not None:
            print()
            print_table(r["rows"])
        elif r["success"]:
            print("\n  Done, no data")

        if r["error"]:
            print(f"\n  Error: {r['error']}")
        print("-" * 60)


if __name__ == "__main__":
    main()
