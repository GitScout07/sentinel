"""
Read-only SELinux check. Never modifies state - that's the remediation
agent's job, and even it only proposes commands, it doesn't run them.
"""

import shutil
import subprocess


def _parse_current_mode(sestatus_output: str) -> str | None:
    """
    Pull the value out of the 'Current mode:' line specifically, rather
    than substring-matching "Enforcing" anywhere in the output - that
    naive approach silently breaks because real sestatus output uses
    lowercase ('Current mode:  enforcing'), so a capital-E match never
    fires and the tool always reports "not enforcing" even when it is.
    """
    for line in sestatus_output.splitlines():
        if line.strip().lower().startswith("current mode:"):
            return line.split(":", 1)[1].strip().lower()
    return None


def get_selinux_status() -> dict:
    """Return SELinux enforcement mode and policy type via sestatus."""
    if shutil.which("sestatus") is None:
        return {
            "ok": False,
            "finding": "sestatus not found - SELinux tooling is not installed.",
        }
    try:
        result = subprocess.run(
            ["sestatus"], capture_output=True, text=True, timeout=5, check=False
        )
        output = result.stdout
        enforcing = _parse_current_mode(output) == "enforcing"
        return {
            "ok": True,
            "enforcing": enforcing,
            "raw_output": output.strip(),
            "finding": (
                "SELinux is enforcing." if enforcing
                else "SELinux is NOT enforcing - this significantly weakens "
                     "mandatory access control on this system."
            ),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "finding": "sestatus timed out."}
