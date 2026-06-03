import os
from core.schema_manager import introspect_schema

db = 'test_company.db'
print('DB exists:', os.path.exists(db))
print('DB size:', os.path.getsize(db), 'bytes')

schema = introspect_schema(db)
print('Tables found:', list(schema.keys()))
for t, info in schema.items():
    print(f"  {t}: {len(info['columns'])} cols, {info['row_count']} rows")
