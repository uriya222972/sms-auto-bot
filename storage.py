# storage.py
import json
import os
from datetime import datetime, timedelta

DATA_FILE = "data.json"

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # Convert string timestamps back to datetime where needed
    if "scheduled_retries" in raw:
        raw["scheduled_retries"] = {
            int(k): datetime.fromisoformat(v)
            for k, v in raw["scheduled_retries"].items()
        }
    return raw
