"""
Security guardrails for remediation commands.

Design principle: the remediation agent is allowed to PROPOSE shell
commands but is never allowed to run them itself. Execution only ever
happens through `execute_if_allowed`, which:
  1. requires the command to match an explicit allowlist prefix
  2. requires an explicit human `confirmed=True` - never auto-set by the
     agent's own reasoning
  3. defaults to dry-run (prints what would happen, doesn't run it)
  4. logs every attempt, allowed or denied, to the audit log

This keeps the "agent decides, human approves, system logs" boundary
enforced in code rather than just described in a prompt - prompts can
be argued with, this can't.
"""

import shlex
import subprocess

from sentinel.security.audit_log import log_event

# Only remediation commands that start with one of these prefixes are
# ever eligible to run. Everything else is rejected outright, regardless
# of confirmation. Keep this list narrow and reviewed - it's the actual
# security boundary, not the LLM's judgment.
ALLOWED_PREFIXES = (
    "firewall-cmd",
    "sudo firewall-cmd",
    "setenforce",
    "sudo setenforce",
    "dnf upgrade",
    "sudo dnf upgrade",
    "apt upgrade",
    "sudo apt upgrade",
    "systemctl enable",
    "systemctl start",
    "sudo systemctl enable",
    "sudo systemctl start",
)


def is_allowed(command: str) -> bool:
    """Return True only if the command matches an approved prefix exactly."""
    normalized = command.strip()
    return any(normalized.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def execute_if_allowed(command: str, confirmed: bool, dry_run: bool = True) -> dict:
    """
    Gate function the remediation agent calls. Never bypassed, never
    wrapped in a way that lets the agent set confirmed=True itself -
    that flag must come from the human-facing CLI layer.
    """
    allowed = is_allowed(command)

    if not allowed:
        log_event("remediation_blocked", command=command, reason="not in allowlist")
        return {"executed": False, "reason": "Command is not in the allowlist."}

    if not confirmed:
        log_event("remediation_pending", command=command, reason="awaiting human confirmation")
        return {"executed": False, "reason": "Awaiting explicit human confirmation."}

    if dry_run:
        log_event("remediation_dry_run", command=command)
        return {"executed": False, "dry_run": True, "would_run": command}

    try:
        result = subprocess.run(
            shlex.split(command), capture_output=True, text=True,
            timeout=30, check=False,
        )
        log_event("remediation_executed", command=command, returncode=result.returncode)
        return {
            "executed": True,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        log_event("remediation_timeout", command=command)
        return {"executed": False, "reason": "Command timed out."}
