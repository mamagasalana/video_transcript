import sqlite3
from typing import Optional, Dict, Any


DB_PATH = "usage.db"


class FolderSchemaTracker:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_db()

    def get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS folder_schema (
                    schema TEXT NOT NULL,
                    model TEXT NOT NULL,
                    folder TEXT PRIMARY KEY
                )
                """
            )

    def set(self, folder: str, model: str, schema: str) -> None:
        if not folder:
            raise ValueError("folder must be a non-empty string")

        with self.get_conn() as conn:
            conn.execute(
                """
                INSERT INTO folder_schema (schema, model, folder)
                VALUES (?, ?, ?)
                ON CONFLICT(folder) DO UPDATE SET
                    schema = excluded.schema,
                    model = excluded.model
                """,
                (schema, model, folder),
            )

    def get(self, folder: str) -> Optional[Dict[str, Any]]:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT schema, model, folder FROM folder_schema WHERE folder = ?",
                (folder,),
            ).fetchone()
        return dict(row) if row else None

    def extract_db(self, qry="SELECT * FROM folder_schema"):
        with self.get_conn() as conn:
            rows = conn.execute(qry).fetchall()
        return [dict(r) for r in rows]