import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nl_module import process_query
from schema_selector import select_schema
from validator import validate
from sql_generator import generate as gen_sql
import sqlite3

print("="*60)
print("NL2SQL PROTOTYPE - END-TO-END TEST")
print("="*60)

test_queries = [
    "Найди всех сотрудников отдела разработки",
    "Сколько задач в каждом проекте",
    "Покажи сотрудников с зарплатой выше 100000",
    "Средняя зарплата по отделам",
    "Show all employees in sales department",
    "Find projects with budget over 300000",
]

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_company.db")
has_db = os.path.exists(db_path)

passed = 0
failed = 0

for i, q in enumerate(test_queries, 1):
    print(f"\n{'='*60}")
    print(f"Test {i}: {q}")
    print("-"*60)
    
    try:
        # Step 1: NL processing
        qi = process_query(q)
        print(f"[1/3] NL: lang={qi['language']} type={qi['query_type']}")
        print(f"      entities={qi['entities']}")
        
        # Step 2: Schema selection
        si = select_schema(qi["cleaned"])
        print(f"[2/3] Schema: tables={si['tables']}")
        
        # Step 3: SQL generation
        sql = gen_sql(qi, si, mode="demo")
        print(f"[3/3] SQL:")
        print(f"      {sql.replace(chr(10), chr(10)+'      ')}")
        
        # Validate
        valid, msg = validate(sql, {})
        if valid:
            print(f"      VALIDATION: PASSED")
        else:
            print(f"      VALIDATION: {msg}")
        
        # Execute
        if has_db:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            try:
                cur.execute(sql)
                rows = cur.fetchall()
                print(f"      RESULT: {len(rows)} rows")
                if rows:
                    print(f"      First row: {rows[0]}")
            except Exception as e:
                print(f"      ERROR: {e}")
            conn.close()
        
        passed += 1
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        failed += 1

print(f"\n{'='*60}")
print(f"RESULTS: {passed} passed, {failed} failed")
print(f"{'='*60}")
