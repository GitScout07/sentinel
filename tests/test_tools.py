"""
Tests for the read-only system-check tools. These never touch the LLM,
so they're free to run as often as you want - run them first, every
time, before spending any Gemini quota on the agent layers.

Run with: pytest tests/test_tools.py -v
"""

from sentinel.mcp_server.tools import dns, firewall, packages, ports, selinux, usbguard

# Real sestatus output captured from a live Fedora VM during manual MCP
# Inspector testing - this is what originally exposed the enforcing-mode
# detection bug (lowercase "enforcing" vs. the old capital-E substring
# check). Keeping the exact fixture pins the regression.
REAL_FIREWALL_LIST_ALL_OUTPUT = """FedoraWorkstation (default, active)
  target: default
  ingress-priority: 0
  egress-priority: 0
  icmp-block-inversion: no
  interfaces: enp1s0
  sources: 
  services: dhcpv6-client samba-client ssh
  ports: 1025-65535/udp 1025-65535/tcp
  protocols: 
  forward: yes
  masquerade: no
  forward-ports: 
  source-ports: 
  icmp-blocks: 
  rich rules:"""


def test_find_broad_port_ranges_detects_real_wide_range():
    broad = firewall._find_broad_port_ranges(REAL_FIREWALL_LIST_ALL_OUTPUT)
    assert len(broad) == 2  # both the udp and tcp 1025-65535 ranges
    assert any("1025-65535/udp" in r for r in broad)
    assert any("1025-65535/tcp" in r for r in broad)


def test_find_broad_port_ranges_ignores_narrow_range():
    narrow_output = "ports: 8080-8090/tcp"
    assert firewall._find_broad_port_ranges(narrow_output) == []


# Real sestatus output captured from a live Fedora VM during manual MCP
# Inspector testing - this is what originally exposed the enforcing-mode
# detection bug (lowercase "enforcing" vs. the old capital-E substring
# check). Keeping the exact fixture pins the regression.
REAL_SESTATUS_ENFORCING_OUTPUT = """SELinux status:                 enabled
SELinuxfs mount:                /sys/fs/selinux
SELinux root directory:         /etc/selinux
Loaded policy name:             targeted
Current mode:                   enforcing
Mode from config file:          enforcing
Policy MLS status:              enabled
Policy deny_unknown status:     allowed
Memory protection checking:     actual (secure)
Max kernel policy version:      34"""


def test_parse_current_mode_detects_real_enforcing_output():
    assert selinux._parse_current_mode(REAL_SESTATUS_ENFORCING_OUTPUT) == "enforcing"


def test_parse_current_mode_detects_permissive():
    permissive_output = REAL_SESTATUS_ENFORCING_OUTPUT.replace(
        "Current mode:                   enforcing",
        "Current mode:                   permissive",
    )
    assert selinux._parse_current_mode(permissive_output) == "permissive"


def test_selinux_returns_ok_key():
    result = selinux.get_selinux_status()
    assert "ok" in result
    assert "finding" in result


def test_firewall_returns_ok_key():
    result = firewall.get_firewall_rules()
    assert "ok" in result
    assert "finding" in result


def test_ports_returns_ok_key():
    result = ports.get_open_ports()
    assert "ok" in result
    assert "finding" in result


def test_packages_returns_ok_key():
    result = packages.get_pending_updates()
    assert "ok" in result
    assert "finding" in result


def test_usbguard_returns_ok_key():
    result = usbguard.get_usbguard_status()
    assert "ok" in result
    assert "finding" in result


def test_dns_returns_ok_key():
    result = dns.get_dns_privacy_status()
    assert "ok" in result
    assert "finding" in result


def test_all_tools_never_raise():
    # The real contract that matters: even on a machine missing every
    # binary (this sandbox, for instance), no tool should ever throw -
    # they must degrade to a structured {"ok": False, ...} response.
    # An agent calling these mid-run cannot survive a raised exception.
    for fn in (
        selinux.get_selinux_status,
        firewall.get_firewall_rules,
        ports.get_open_ports,
        packages.get_pending_updates,
        usbguard.get_usbguard_status,
        dns.get_dns_privacy_status,
    ):
        result = fn()
        assert isinstance(result, dict)
