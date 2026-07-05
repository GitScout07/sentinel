"""Read-only firewalld inspection."""

import re
import shutil
import subprocess

# Matches port-range tokens like "1025-65535/udp" in `firewall-cmd --list-all`
# output. Used to flag suspiciously wide ranges deterministically, since
# that's cheap to catch here and shouldn't depend on an LLM reading it
# correctly out of multi-line raw text.
_PORT_RANGE_RE = re.compile(r"(\d+)-(\d+)/(tcp|udp)")

# A range wider than this is almost certainly not intentional - flag it
# so the risk agent doesn't have to infer "is 64,000 ports a lot" itself.
_WIDE_RANGE_THRESHOLD = 1000


def _find_broad_port_ranges(raw_output: str) -> list[str]:
    broad = []
    for low, high, proto in _PORT_RANGE_RE.findall(raw_output):
        span = int(high) - int(low)
        if span >= _WIDE_RANGE_THRESHOLD:
            broad.append(f"{low}-{high}/{proto} ({span + 1} ports)")
    return broad


def get_firewall_rules() -> dict:
    """Return the active firewalld zone configuration."""
    if shutil.which("firewall-cmd") is None:
        return {
            "ok": False,
            "finding": "firewall-cmd not found - firewalld is not installed.",
        }
    try:
        active = subprocess.run(
            ["firewall-cmd", "--state"], capture_output=True, text=True,
            timeout=5, check=False,
        )
        if "running" not in active.stdout:
            return {
                "ok": True,
                "running": False,
                "finding": "firewalld is installed but not running - "
                           "this host has no active firewall enforcement.",
            }
        details = subprocess.run(
            ["firewall-cmd", "--list-all"], capture_output=True, text=True,
            timeout=5, check=False,
        )
        raw = details.stdout
        broad_ranges = _find_broad_port_ranges(raw)

        finding = "firewalld is active."
        if broad_ranges:
            finding += (
                f" WARNING: unusually broad port range(s) open: "
                f"{', '.join(broad_ranges)} - verify these are intentional."
            )
        else:
            finding += " No unusually broad port ranges detected."

        return {
            "ok": True,
            "running": True,
            "raw_output": raw.strip(),
            "broad_port_ranges": broad_ranges,
            "finding": finding,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "finding": "firewall-cmd timed out."}
