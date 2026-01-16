import sqlite3
import os
from datetime import datetime

class IncidentLogger:
    def __init__(self, db_path="ghost_incidents.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                component TEXT,
                level TEXT,
                message TEXT,
                data TEXT
            )
        """)
        conn.commit()
        conn.close()

    def log(self, component, message, level="INFO", data=None):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO incidents (component, level, message, data)
                VALUES (?, ?, ?, ?)
            """, (component, level, message, str(data) if data else None))
            conn.commit()
            conn.close()
            print(f"📝 [INCIDENT] {level} | {component}: {message}")
        except Exception as e:
            print(f"❌ [INCIDENT] Logging Error: {e}")

# Global logger instance
logger = IncidentLogger()
