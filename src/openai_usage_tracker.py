import os
import json
import datetime
import time
import sqlite3

TOKEN_CAP = 2_000_000
SPENT_PATH = "spent.json"
DB_PATH = "usage.db"

class UsageTracker:
    def __init__(self, path: str = SPENT_PATH, cap: int = TOKEN_CAP, model: str = "openai"):
        self.path = path
        self.cap = cap
        self.model = model
        self.init_db()

    def get_conn(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_conn() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                filename TEXT NOT NULL,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                reasoning_tokens INTEGER,
                cached_tokens INTEGER,
                total_tokens INTEGER NOT NULL,
                time_spent REAL NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)

    def update_db(self, u):
        with self.get_conn() as conn:
            conn.execute("""
            INSERT INTO llm_usage (
                provider, model, filename, 
                prompt_tokens, completion_tokens,
                reasoning_tokens, cached_tokens,
                total_tokens, time_spent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                u["provider"],
                u["model"],
                u["filename"],
                u["prompt_tokens"],
                u["completion_tokens"],
                u["reasoning_tokens"],
                u["cached_tokens"],
                u["total_tokens"],
                u["time_spent"],
            ))

    def extract_db(self, qry="SELECT * FROM llm_usage"):
        with self.get_conn() as conn:
            rows = conn.execute(qry).fetchall()
        return [dict(r) for r in rows]

    @property
    def today(self) -> str:
        return '%s_%s' % (datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d"),
                          self.model)

    def _empty_day(self) -> dict:
        return {"spent": 0, "cap": self.cap, "updated_at": None}

    def _load_all(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            bak = self.path + ".corrupt." + str(int(time.time()))
            try:
                os.replace(self.path, bak)
            except Exception:
                pass
            return {}

    def get(self) -> dict:
        all_data = self._load_all()
        day = all_data.get(self.today, {})
        if not isinstance(day, dict):
            day = {}
        # defaults
        day.setdefault("spent", 0)
        day.setdefault("cap", self.cap)
        day.setdefault("updated_at", None)
        return day

    def set(self, usage: int) -> None:
        all_data = self._load_all()
        day_key = self.today

        if day_key not in all_data:
            all_data[day_key] = self._empty_day()

        all_data[day_key]["spent"] += int(usage)
        all_data[day_key]["updated_at"] =  datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)
        return all_data[day_key]["spent"]
