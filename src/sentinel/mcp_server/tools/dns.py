"""
Read-only DNS privacy check via systemd-resolved. Ties directly into prior
work hardening DNS with Quad9 DoT - this just makes the current state
machine-checkable instead of remembered by hand.
"""

import shutil
import subprocess


def get_dns_privacy_status() -> dict:
    """Check whether systemd-resolved has DNS-over-TLS enabled."""
    if shutil.which("resolvectl") is None:
        return {
            "ok": False,
            "finding": "resolvectl not found - cannot inspect DNS configuration.",
        }
    try:
        result = subprocess.run(
            ["resolvectl", "status"], capture_output=True, text=True,
            timeout=5, check=False,
        )
        raw = result.stdout
        dot_enabled = "DNSOverTLS setting: yes" in raw or "+DNSOverTLS" in raw
        return {
            "ok": True,
            "dns_over_tls": dot_enabled,
            "raw_output": raw.strip(),
            "finding": (
                "DNS-over-TLS is enabled." if dot_enabled
                else "DNS-over-TLS is NOT enabled - DNS queries may be "
                     "visible to the network path or ISP."
            ),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "finding": "resolvectl timed out."}
