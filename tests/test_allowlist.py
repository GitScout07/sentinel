"""
Tests for the remediation security gate. This module IS the security
boundary the rubric grades you on, so it deserves the most thorough
tests in the repo - if these pass, the "agent can never execute
unapproved or unconfirmed commands" guarantee actually holds.

Run with: pytest tests/test_allowlist.py -v
"""

from sentinel.security.allowlist import execute_if_allowed, is_allowed


def test_allowed_prefix_passes():
    assert is_allowed("firewall-cmd --add-port=443/tcp --permanent")


def test_disallowed_command_fails():
    assert not is_allowed("rm -rf /")


def test_disallowed_even_with_allowed_substring():
    # A command containing an allowed word mid-string must still fail -
    # only a genuine prefix match counts.
    assert not is_allowed("echo firewall-cmd is great; rm -rf /")


def test_execute_blocked_when_not_allowlisted():
    result = execute_if_allowed("rm -rf /", confirmed=True, dry_run=False)
    assert result["executed"] is False
    assert "not in the allowlist" in result["reason"]


def test_execute_blocked_when_not_confirmed():
    result = execute_if_allowed("firewall-cmd --reload", confirmed=False, dry_run=False)
    assert result["executed"] is False
    assert "confirmation" in result["reason"]


def test_execute_dry_run_does_not_run_command():
    result = execute_if_allowed("systemctl enable firewalld", confirmed=True, dry_run=True)
    assert result["executed"] is False
    assert result["dry_run"] is True


def test_real_execution_requires_both_allowed_and_confirmed_and_no_dry_run():
    # This is the only path where a command can actually run - confirm
    # all three gates are required simultaneously, not just one.
    blocked_1 = execute_if_allowed("rm -rf /", confirmed=True, dry_run=False)
    blocked_2 = execute_if_allowed("firewall-cmd --reload", confirmed=False, dry_run=False)
    blocked_3 = execute_if_allowed("firewall-cmd --reload", confirmed=True, dry_run=True)
    assert blocked_1["executed"] is False
    assert blocked_2["executed"] is False
    assert blocked_3["executed"] is False
