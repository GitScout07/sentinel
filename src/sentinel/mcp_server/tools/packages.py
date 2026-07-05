"""
Read-only pending-update check. Works on both dnf (Fedora) and apt
(Debian/Ubuntu) systems, since this project's owner has built on both.
"""

import shutil
import subprocess


def get_pending_updates() -> dict:
    """Return a count of pending package updates, distro-agnostic."""
    if shutil.which("dnf"):
        return _check_dnf()
    if shutil.which("apt"):
        return _check_apt()
    return {"ok": False, "finding": "Neither dnf nor apt found on this system."}


def _check_dnf() -> dict:
    try:
        # check-update returns exit code 100 when updates ARE available -
        # that's expected, not an error, so check=False.
        result = subprocess.run(
            ["dnf", "check-update", "--quiet"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        pkg_lines = [
            line for line in result.stdout.splitlines()
            if line.strip() and not line.startswith(("Last metadata", "Obsoleting"))
        ]
        count = len(pkg_lines)
        return {
            "ok": True,
            "pending_updates": count,
            "finding": f"{count} package(s) have pending updates."
                       if count else "System packages are up to date.",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "finding": "dnf check-update timed out."}


def _check_apt() -> dict:
    try:
        subprocess.run(
            ["apt", "list", "--upgradable"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        result = subprocess.run(
            ["apt", "list", "--upgradable"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        lines = [
            line for line in result.stdout.splitlines()
            if "/" in line and "Listing" not in line
        ]
        count = len(lines)
        return {
            "ok": True,
            "pending_updates": count,
            "finding": f"{count} package(s) have pending updates."
                       if count else "System packages are up to date.",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "finding": "apt list timed out."}
