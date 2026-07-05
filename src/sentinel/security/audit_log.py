"""
Append-only audit log. Every remediation decision - proposed, blocked,
pending, dry-run, or executed - gets a line here. JSON-lines so it's
trivial to grep, tail, or load into pandas later if you want a history
view in the report.
"""

import json
import os
import time

from sentinel.config import SENTINEL_HOME

LOG_PATH = os.path.join(SENTINEL_HOME, "audit.log")


def log_event(event_type: str, **fields) -> None:
    os.makedirs(SENTINEL_HOME, exist_ok=True)
    entry = {"timestamp": time.time(), "event": event_type, **fields}
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
