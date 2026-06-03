#!/usr/bin/env python3
"""
test_proto.py — End-to-end тесты через Gemini-пайплайн (core.pipeline).
Требует GEMINI_API_KEY в окружении или .env файле.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.pipeline import process_nl_query

print("="*60)
print("NL2SQL PROTOTYPE - END-TO-END TEST (Gemini pipeline)")
print("="*60)

test_queries = [
    "Найди всех сотрудников отдела разработки",
    "Сколько задач в каждом проекте",
    "Покажи сотрудников с зарплатой выше 100000",
    "Средняя зарплата по отделам",
    "Show all employees in sales department",
    "Find projects with budget over 300000",
    "найди всех сотрудников с фамилией иванов",
]

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_company.db")
if not os.path.exists(db_path):
    print("ERROR: test_company.db not found! Run: python3 init_db.py --clean")
    sys.exit(1)

passed = 0
failed = 0

for i, q in enumerate(test_queries, 1):
    print(f"\n{'='*60}")
    print(f"Test {i}: {q}")
    print("-"*60)
    
    try:
        result = process_nl_query(q, db_path)
        
        if result["success"]:
            sql = result.get("formatted_sql") or result.get("sql") or ""
            rows = result.get("rows") or []
            print(f"  SQL: {sql[:90].replace(chr(10), ' ')}...")
            print(f"  RESULT: {len(rows)} rows")
            if rows:
                print(f"  First row: {list(rows[0].values())[:3]}")
            passed += 1
        else:
            print(f"  ERROR: {result.get('error', 'Unknown error')}")
            failed += 1
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        failed += 1

print(f"\n{'='*60}")
print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_queries)}")
print(f"{'='*60}")
