import os
import pymysql
from dbutils.pooled_db import PooledDB

# WSL2 needs to connect to Windows host IP, not 127.0.0.1
# Auto-detect: if running in WSL, use the default gateway as DB host
def _detect_db_host():
    if os.path.exists("/proc/version"):
        try:
            with open("/proc/version") as f:
                if "microsoft" in f.read().lower():
                    import subprocess
                    result = subprocess.run(
                        ["ip", "route", "show", "default"],
                        capture_output=True, text=True
                    )
                    parts = result.stdout.strip().split()
                    if "via" in parts:
                        return parts[parts.index("via") + 1]
        except Exception:
            pass
    return "127.0.0.1"

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", _detect_db_host()),
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "chatforum",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

_pool = PooledDB(pymysql, maxconnections=20, **DB_CONFIG)


def get_db_cursor():
    conn = _pool.connection()
    cursor = conn.cursor()
    return cursor, conn
