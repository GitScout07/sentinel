"""
Sentinel MCP server.

Exposes every read-only system check as an MCP tool. This is the only
part of the system that touches the real machine - everything upstream
of it (the agents) only ever sees structured dicts coming back, never
raw shell access. That boundary is deliberate: it's the easiest place
to reason about "what can this agent actually do to my system."

Run standalone for local testing:
    python -m sentinel.mcp_server.server
ADK connects to this same entrypoint via MCPToolset + StdioServerParameters.
"""

from mcp.server.fastmcp import FastMCP

from sentinel.mcp_server.tools import dns, firewall, packages, ports, selinux, usbguard

mcp = FastMCP("sentinel-tools")


@mcp.tool()
def check_selinux() -> dict:
    """Check SELinux enforcement status and policy on this Linux host."""
    return selinux.get_selinux_status()


@mcp.tool()
def check_firewall() -> dict:
    """Check whether firewalld is running and return its active rule set."""
    return firewall.get_firewall_rules()


@mcp.tool()
def check_open_ports() -> dict:
    """List all listening TCP/UDP ports and their owning processes."""
    return ports.get_open_ports()


@mcp.tool()
def check_package_updates() -> dict:
    """Check for pending security-relevant package updates (dnf or apt)."""
    return packages.get_pending_updates()


@mcp.tool()
def check_usbguard() -> dict:
    """Check whether USBGuard is installed, active, and how many rules it has."""
    return usbguard.get_usbguard_status()


@mcp.tool()
def check_dns_privacy() -> dict:
    """Check whether DNS-over-TLS is enabled via systemd-resolved."""
    return dns.get_dns_privacy_status()


if __name__ == "__main__":
    mcp.run()
