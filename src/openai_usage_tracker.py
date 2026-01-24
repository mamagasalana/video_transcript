import os
import json
import datetime
import time

TOKEN_CAP = 2_000_000
SPENT_PATH = "spent.json"

class UsageTracker:
    def __init__(self, path: str = SPENT_PATH, cap: int = TOKEN_CAP, model: str = "openai"):
        self.path = path
        self.cap = cap
        self.model = model

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
