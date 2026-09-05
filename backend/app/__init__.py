import sys

try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    # Fallback to system sqlite3 if pysqlite3 is not available
    pass
