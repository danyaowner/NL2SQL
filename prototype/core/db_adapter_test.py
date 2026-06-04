"""
db_adapter.py - Universal adapter for SQLite, PostgreSQL and MySQL.
"""
import os
import sqlite3
from typing import Dict, Any, List, Tuple, Optional

try:
    import psycopg2
    import psycopg2.extras
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

try:
    import pymysql
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False