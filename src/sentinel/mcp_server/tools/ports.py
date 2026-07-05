"""Read-only listening-port inspection via ss."""

import shutil
import subprocess


def get_open_ports() -> dict:
    """List listening TCP/UDP sockets and, where visible, their owning process."""
    if shutil.which("ss") is None:
        return {"ok": False, "finding": "ss not found - cannot inspect sockets."}
    try:
        result = subprocess.run(
            ["ss", "-tulnp"], capture_output=True, text=True, timeout=5, check=False
        )
        lines = [line for line in result.stdout.splitlines()[1:] if line.strip()]
        return {
            "ok": True,
            "listening_count": len(lines),
            "raw_output": result.stdout.strip(),
            "finding": f"{len(lines)} listening sockets found. Flag any bound "
                       f"to 0.0.0.0 or :: that don't need to be reachable "
                       f"from the network.",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "finding": "ss timed out."}
