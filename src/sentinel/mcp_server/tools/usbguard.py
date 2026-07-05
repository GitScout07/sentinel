"""Read-only USBGuard status check."""

import shutil
import subprocess


def get_usbguard_status() -> dict:
    """Check whether USBGuard is active and how many rules are loaded."""
    if shutil.which("usbguard") is None:
        return {
            "ok": True,
            "installed": False,
            "finding": "USBGuard is not installed - USB device access is "
                       "unrestricted at the OS level.",
        }
    try:
        active = subprocess.run(
            ["systemctl", "is-active", "usbguard"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        is_active = active.stdout.strip() == "active"
        if not is_active:
            return {
                "ok": True,
                "installed": True,
                "active": False,
                "finding": "USBGuard is installed but not running.",
            }
        rules = subprocess.run(
            ["usbguard", "list-rules"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        rule_count = len([l for l in rules.stdout.splitlines() if l.strip()])
        return {
            "ok": True,
            "installed": True,
            "active": True,
            "rule_count": rule_count,
            "finding": f"USBGuard active with {rule_count} rule(s) loaded.",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "finding": "usbguard command timed out."}
