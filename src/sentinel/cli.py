"""
Sentinel CLI.

The "agent skill" surface — a small, documented, installable command set.
This is also the ONLY place in the codebase where a real remediation
command can ever execute, and only after:

  1. The command is on the explicit allowlist  (enforced in allowlist.py)
  2. The user runs  sentinel harden --execute  (opt-in flag)
  3. The user types 'y' at the keyboard        (per-command confirmation)

All three gates must pass simultaneously. The agents themselves have no
path to execution — this file is the entire execution surface.

Commands:
    sentinel audit              — full audit + HTML report (read-only)
    sentinel harden             — audit + show proposed fixes (dry-run)
    sentinel harden --execute   — audit + human-approved fix execution
"""

import argparse
import asyncio
import re
import shlex
import subprocess
import sys

from sentinel.orchestrator import run_pipeline
from sentinel.report import _parse_actions, save_and_open
from sentinel.security.allowlist import ALLOWED_PREFIXES, execute_if_allowed
from sentinel.security.audit_log import log_event

# ANSI colours — degrade gracefully on terminals without colour support
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_RED    = "\033[31m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_DIM    = "\033[2m"

def _c(text: str, *codes: str) -> str:
    """Wrap text in ANSI codes if stdout is a TTY, strip them otherwise."""
    if not sys.stdout.isatty():
        return text
    return "".join(codes) + text + _RESET


def _print_report(report: str) -> None:
    print("\n" + report + "\n")


# ── sentinel audit ────────────────────────────────────────────────────────────

def cmd_audit(_args: argparse.Namespace) -> None:
    """Run a full audit and save the HTML report. Read-only — no changes."""
    print(_c("🔍  Running security audit…", _CYAN, _BOLD))
    report = asyncio.run(run_pipeline())
    _print_report(report)
    path = save_and_open(report, auto_open=True)
    print(_c(f"📄  HTML report saved → {path}", _DIM))
    print()


# ── sentinel harden ───────────────────────────────────────────────────────────

def cmd_harden(args: argparse.Namespace) -> None:
    """
    Audit this machine, show proposed fixes, then — if --execute is given —
    walk through each allowlisted command one by one and ask the user
    explicitly before running anything.
    """
    print(_c("🔍  Running security audit…", _CYAN, _BOLD))
    report = asyncio.run(run_pipeline())
    _print_report(report)

    path = save_and_open(report, auto_open=True)
    print(_c(f"📄  HTML report saved → {path}", _DIM))
    print()

    # Parse the recommended actions from the report
    actions = _parse_actions(report)
    allowed_actions = [a for a in actions if a["allowlisted"]]
    manual_actions  = [a for a in actions if a["manual"]]
    unknown_actions = [a for a in actions if not a["allowlisted"] and not a["manual"]]

    if not actions:
        print(_c("✅  No remediation actions were proposed.", _GREEN))
        return

    # ── Summary of proposed fixes ────────────────────────────────────────
    print(_c("━" * 60, _DIM))
    print(_c("  PROPOSED REMEDIATION ACTIONS", _BOLD))
    print(_c("━" * 60, _DIM))
    print()

    if allowed_actions:
        print(_c(f"  🔧  {len(allowed_actions)} allowlisted action(s) — eligible for execution:", _GREEN))
        for i, a in enumerate(allowed_actions, 1):
            print(f"      {i}. {a['text']}")
        print()

    if manual_actions:
        print(_c(f"  🔒  {len(manual_actions)} manual action(s) — require independent review:", _YELLOW))
        for a in manual_actions:
            print(f"      • {a['text']}")
        print()

    if unknown_actions:
        print(_c(f"  ○   {len(unknown_actions)} action(s) — review carefully:", _DIM))
        for a in unknown_actions:
            print(f"      • {a['text']}")
        print()

    # ── Dry-run mode (no --execute flag) ────────────────────────────────
    if not args.execute:
        print(_c("━" * 60, _DIM))
        print(_c(
            "  DRY-RUN MODE — no changes have been made.\n"
            "  Re-run with  sentinel harden --execute  to be prompted\n"
            "  for confirmation on each allowlisted fix individually.",
            _YELLOW
        ))
        print(_c("━" * 60, _DIM))
        print()
        return

    # ── Execute mode — human approval gate ───────────────────────────────
    if not allowed_actions:
        print(_c(
            "⚠️   No allowlisted commands to execute.\n"
            "    The proposed fixes require manual review and must be\n"
            "    run directly — Sentinel will not execute them automatically.",
            _YELLOW
        ))
        return

    print(_c("━" * 60, _DIM))
    print(_c("  EXECUTE MODE — HUMAN APPROVAL REQUIRED", _RED, _BOLD))
    print(_c("━" * 60, _DIM))
    print(_c(
        "\n  You will be asked to confirm EACH command individually.\n"
        "  Type  y  to run it,  n  to skip,  q  to quit without\n"
        "  running any further commands.\n"
        "\n  ⚠️  Review each command carefully before approving.\n"
        "      Sentinel will not proceed without your explicit 'y'.\n",
        _YELLOW
    ))

    executed   = []
    skipped    = []
    blocked    = []

    for i, action in enumerate(allowed_actions, 1):
        raw_text = action["text"]

        # Extract the shell command — everything up to the first " — " or "✓"
        # e.g. "sudo dnf upgrade — update all packages ✓ allowlisted"
        #  → "sudo dnf upgrade"
        command_part = re.split(r"\s+[—–]\s+|\s+✓", raw_text)[0].strip()

        print(_c(f"  [{i}/{len(allowed_actions)}] Proposed fix:", _BOLD))
        print(f"        Command : {_c(command_part, _CYAN)}")

        # Show the explanation (text after the dash/tick separator)
        explanation_match = re.split(r"\s+[—–]\s+", raw_text, maxsplit=1)
        if len(explanation_match) > 1:
            print(f"        Purpose : {explanation_match[1].split('✓')[0].strip()}")

        print()

        while True:
            try:
                choice = input(
                    _c("  Run this command? [y = yes / n = skip / q = quit]: ", _BOLD)
                ).strip().lower()
            except (KeyboardInterrupt, EOFError):
                print("\n\nAborted by user.")
                sys.exit(0)

            if choice in ("y", "yes"):
                result = execute_if_allowed(command_part, confirmed=True, dry_run=False)
                if result.get("executed"):
                    print(_c(f"\n  ✅  Executed successfully (exit {result.get('returncode', 0)})\n", _GREEN))
                    if result.get("stdout"):
                        print(_c("  Output:", _DIM))
                        print("  " + result["stdout"].replace("\n", "\n  ")[:800])
                    executed.append(command_part)
                else:
                    reason = result.get("reason", "Unknown error")
                    print(_c(f"\n  ❌  Blocked: {reason}\n", _RED))
                    blocked.append(command_part)
                break

            elif choice in ("n", "no", ""):
                log_event("remediation_skipped", command=command_part)
                print(_c("  ⏭   Skipped.\n", _DIM))
                skipped.append(command_part)
                break

            elif choice in ("q", "quit", "exit"):
                log_event("remediation_quit", remaining=len(allowed_actions) - i)
                print(_c("\n  Stopped. Remaining commands were not evaluated.\n", _YELLOW))
                break

            else:
                print(_c("  Please type y, n, or q.", _DIM))
                continue
        else:
            continue
        break

    # ── Final summary ─────────────────────────────────────────────────────
    print(_c("━" * 60, _DIM))
    print(_c("  SESSION COMPLETE", _BOLD))
    print(_c("━" * 60, _DIM))
    if executed:
        print(_c(f"  ✅  Executed : {len(executed)} command(s)", _GREEN))
        for cmd in executed:
            print(f"        • {cmd}")
    if skipped:
        print(_c(f"  ⏭   Skipped  : {len(skipped)} command(s)", _DIM))
    if blocked:
        print(_c(f"  ❌  Blocked  : {len(blocked)} command(s)", _RED))
    if manual_actions:
        print(_c(
            f"\n  🔒  {len(manual_actions)} action(s) still require manual review:\n"
            + "\n".join(f"        • {a['text']}" for a in manual_actions),
            _YELLOW
        ))
    print()
    print(_c(
        "  Full audit log → ~/.sentinel/audit.log", _DIM
    ))
    print()


# ── sentinel report ───────────────────────────────────────────────────────────

def cmd_report(_args: argparse.Namespace) -> None:
    """Alias for audit — runs the full pipeline and opens the HTML report."""
    cmd_audit(_args)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sentinel",
        description="Agentic Linux security audit and hardening assistant.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  sentinel audit                 # read-only audit + HTML report\n"
            "  sentinel harden                # show proposed fixes (dry-run)\n"
            "  sentinel harden --execute      # walk through fixes with human approval\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("audit",  help="Run a full security audit (read-only)") \
       .set_defaults(func=cmd_audit)

    sub.add_parser("report", help="Alias for audit") \
       .set_defaults(func=cmd_report)

    h = sub.add_parser("harden", help="Audit then optionally apply fixes")
    h.add_argument(
        "--execute", action="store_true",
        help="Enable human-approved execution of allowlisted fixes",
    )
    h.set_defaults(func=cmd_harden)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
