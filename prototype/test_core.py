import sys, os
sys.path.insert(0, '.')

print("=== Testing core modules ===")

# 1. Preprocessor
from core.preprocessor import clean_query
result = clean_query('  Find   all   employees  ')
print(f"1. Preprocessor: {repr(result)}")
assert result == 'Find all employees', f"Unexpected: {result}"
print("   OK")

# 2. Validator
from core.sql_validator import validate
ok, formatted = validate('SELECT * FROM employees WHERE department = "Dev"')
print(f"2. Validator (valid): {ok}")
assert ok, "Valid SQL should pass"

ok2, err = validate('DROP TABLE employees')
print(f"   Validator (blocked): {ok2}, {err}")
assert not ok2, "DROP should be blocked"
print("   OK")

# 3. Schema Manager
_test_db = os.environ.get("DB_PATH")
if _test_db and os.path.exists(_test_db):
    from core.schema_manager import introspect_schema, format_schema_for_prompt
    schema = introspect_schema(_test_db)
    print(f"3. Schema: {len(schema)} tables: {list(schema.keys())}")
    assert len(schema) > 0, "Schema should have tables"
    text = format_schema_for_prompt(schema)
    print(f"   Schema text length: {len(text)} chars")
    print("   OK")
else:
    print(f"3. Schema: DB_PATH not set or file not found, skipping")

# 4. Prompt Builder
from core.prompt_builder import build_prompt
prompt = build_prompt("Find all employees", "Table: employees (id, name)")
print(f"4. Prompt: {len(prompt)} chars")
assert "Find all employees" in prompt, "Query should be in prompt"
assert "employees" in prompt, "Schema should be in prompt"
print("   OK")

# 5. LLM Client - extract SQL
from core.llm_client import _extract_sql
sql = _extract_sql('```sql\nSELECT * FROM users\n```')
print(f"5. SQL extract: {repr(sql)}")
assert sql == "SELECT * FROM users", f"Unexpected: {repr(sql)}"

sql2 = _extract_sql("Here is the query:\nSELECT * FROM users")
print(f"   SQL extract line: {repr(sql2)}")
assert sql2 == "SELECT * FROM users", f"Unexpected: {repr(sql2)}"

sql3 = _extract_sql("   SELECT * FROM users   ")
print(f"   SQL extract plain: {repr(sql3)}")
assert sql3 == "SELECT * FROM users"
print("   OK")

# 6. Executor
if _test_db and os.path.exists(_test_db):
    from core.executor import execute_query
    rows, err = execute_query(_test_db, 'SELECT 1 as test')
    print(f"6. Executor: rows={rows}, error={err}")
    assert err is None, f"Should not error: {err}"
    assert len(rows) >= 1, "Should have at least 1 row"
    print("   OK")
else:
    print(f"6. Executor: DB_PATH not set or file not found, skipping")

print("\n=== ALL TESTS PASSED ===")
