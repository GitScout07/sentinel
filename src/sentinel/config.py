"""
Central configuration for Sentinel.

Design decision: every other module imports settings from here instead of
calling os.environ directly. That keeps secrets out of agent/tool code and
makes it obvious, in one file, what the project depends on at runtime.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# Model used by the reasoning-heavy agents (risk assessment, reporting).
# gemini-2.0-flash was retired from the free tier in early 2026 - this
# defaults to 2.5 Flash instead. Verify the current free-tier model name
# for your account at https://aistudio.google.com before relying on this
# default; the Flash lineup has moved fast and this may already be stale.
MODEL_NAME = os.environ.get("SENTINEL_MODEL", "gemini-3.5-flash")

# Where audit logs and run history get written. Kept outside the repo
# (see .gitignore) since logs may contain machine-specific details.
SENTINEL_HOME = os.path.expanduser(os.environ.get("SENTINEL_HOME", "~/.sentinel"))

# Fail loudly and early if the API key is missing, rather than letting
# the first agent call produce a confusing downstream error.
def require_api_key() -> None:
    if not os.environ.get("GOOGLE_API_KEY"):
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Copy .env.example to .env and add your key."
        )
