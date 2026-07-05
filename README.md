# Sentinel 🛡️
### Agentic Linux Security Audit & Hardening Assistant

> **Kaggle Capstone — 5-Day AI Agents: Intensive Vibe Coding Course with Google (June 2026)**
> Track: Agents for Business | Built with Google ADK · MCP · Gemini · Antigravity

Sentinel is a multi-agent AI system that audits the security posture of a Linux machine, reasons about what the findings mean in combination, proposes safe remediations, and walks you through applying them — one command at a time, with your explicit approval at every step.

It goes beyond what a static shell script can do. A script checks whether SELinux is enforcing. Sentinel looks at the full picture — permissive SELinux *plus* 974 unpatched packages *plus* a firewall with 64,000 ports open — and tells you what that combination actually means, why it matters, and what to fix first.

---

## The Problem

Every Linux system administrator has a mental security checklist. Is SELinux enforcing? Is the firewall configured correctly? Are packages up to date? In practice, that checklist gets run inconsistently — the output is noisy, findings are listed without context, and the most important part (*why does this combination of issues actually matter?*) gets left to whoever happens to be reading the terminal that day.

Static scripts automate the checking. They don't automate the thinking.

---

## The Solution

A four-agent pipeline that separates concerns clearly:

- **Audit Agent** — gathers raw facts from the system via read-only MCP tools. No LLM involved here.
- **Risk Reasoning Agent** — uses Gemini to look at the *combination* of findings and prioritize by real-world severity, not just list them.
- **Remediation Agent** — proposes specific fix commands. Checks every command against an allowlist before returning it. Cannot execute anything.
- **Reporting Agent** — assembles everything into a clean markdown report + a self-contained HTML dashboard.

---

## Demo

```
$ sentinel audit

🔍  Running security audit…

## Summary
Mixed security posture. SELinux is enforcing — good. However three
high-severity findings need immediate attention: 974 pending package
updates, 64,511 firewall ports open on both TCP and UDP, and USBGuard
active with zero rules loaded.

## Findings by severity

| Finding                      | Severity | Why it matters                               |
|-----------------------------|----------|----------------------------------------------|
| 974 pending package updates  | HIGH     | Most common attacker entry point             |
| Firewall: 1025-65535 open    | HIGH     | 64,511 ports exposed unnecessarily           |
| USBGuard: 0 rules loaded     | HIGH     | Any USB device automatically trusted         |
| DNS-over-TLS not enabled     | MEDIUM   | DNS queries visible to ISP                   |
| SELinux enforcing            | GOOD     | Mandatory access control is active           |

📄  HTML report saved → /home/user/.sentinel/report.html
```

```
$ sentinel harden --execute

  [1/3] Proposed fix:
        Command : sudo dnf upgrade
        Purpose : Update all pending packages

  Run this command? [y = yes / n = skip / q = quit]: y

  ✅  Executed successfully (exit 0)
```

---

## Architecture

```
CLI (sentinel audit / harden / report)
          │
          ▼
  Orchestrator (ADK SequentialAgent)
    │
    ├─► Audit Agent ──────────► MCP Tool Server (read-only)
    │                               ├ check_selinux
    │                               ├ check_firewall
    │                               ├ check_open_ports
    │                               ├ check_package_updates
    │                               ├ check_usbguard
    │                               └ check_dns_privacy
    │
    ├─► Risk Reasoning Agent (Gemini)
    │         Prioritizes findings by combined severity
    │
    ├─► Remediation Agent ────► Allowlist Gate (propose-only)
    │                               └ Human Approval Required ◄── YOU
    │
    └─► Reporting Agent (Gemini)
              Markdown report + self-contained HTML dashboard
```

The LLM is involved in exactly two steps: reasoning about severity and writing the report. Everything else is deterministic Python. This keeps API costs low, keeps behavior predictable, and means the system degrades gracefully if the model is unavailable.

---

## Security Design

**The LLM cannot run anything. Ever.**

The remediation agent's only tool is `propose_remediation` — it returns a dry-run preview and checks against an allowlist. Real execution only happens through `sentinel harden --execute`, which requires:

1. The command matches an approved prefix in the allowlist
2. The user explicitly types `y` at the terminal for that specific command
3. Both conditions must be true simultaneously

Additional guardrails:

| Guardrail | Implementation |
|---|---|
| Command allowlist | Only `firewall-cmd`, `dnf upgrade`, `apt upgrade`, `systemctl enable/start` eligible |
| Audit log | Every decision written to `~/.sentinel/audit.log` (append-only JSON-lines) |
| No secrets in code | API key in `.env` only, excluded from repo via `.gitignore` |
| Read-only MCP tools | MCP server exposes inspection commands only, never modification |

---

## Course Concepts Demonstrated

| Concept | Where |
|---|---|
| Multi-agent system (ADK SequentialAgent) | `src/sentinel/orchestrator.py` |
| MCP Server | `src/sentinel/mcp_server/server.py` |
| Security features | `src/sentinel/security/allowlist.py` + `audit_log.py` |
| Agent skills / CLI | `src/sentinel/cli.py` |
| Deployability | `pyproject.toml` — `pip install -e .` installs the `sentinel` CLI |
| Antigravity | Used throughout development — see video |

---

## What It Checks

| Check | Tool | What It Looks For |
|---|---|---|
| SELinux | `sestatus` | Enforcing mode (parses the `Current mode:` line — not a naive substring match) |
| Firewall | `firewall-cmd` | Active zone config; flags port ranges > 1,000 ports |
| Open ports | `ss` | Sockets bound to `0.0.0.0` or `::` |
| Package updates | `dnf` / `apt` | Pending updates — distro-aware |
| USBGuard | `usbguard` | Whether active and how many rules loaded |
| DNS privacy | `resolvectl` | DNS-over-TLS via systemd-resolved |

Works on Fedora, RHEL, Ubuntu, and Debian.

---

## Getting Started

### Prerequisites
- Python 3.10+
- Linux (Fedora/RHEL or Debian/Ubuntu)
- A [Google AI Studio](https://aistudio.google.com/apikey) API key (free tier works)

### Install

```bash
git clone https://github.com/rahulv/sentinel.git
cd sentinel
python3 -m venv .venv --upgrade-deps
source .venv/bin/activate
pip install -e .
```

### Configure

```bash
cp .env.example .env
nano .env
```

Paste your key — the file should contain exactly three lines:

```
GOOGLE_API_KEY=your_key_here
GOOGLE_GENAI_USE_VERTEXAI=FALSE
SENTINEL_MODEL=gemini-3.5-flash
```

### Run

```bash
sentinel audit              # read-only audit + HTML report
sentinel harden             # show proposed fixes, dry-run
sentinel harden --execute   # human-approved fix execution
```

### Test

```bash
pip install pytest
pytest tests/ -v
```

18 tests, no API key needed, no network calls. Includes regression tests derived from real machine output captured during development — including the `sestatus` lowercase parsing bug that a real VM run exposed.

---

## Project Structure

```
sentinel/
├── src/sentinel/
│   ├── agents/
│   │   ├── audit_agent.py        # Gathers system facts via MCP tools
│   │   ├── risk_agent.py         # Prioritizes findings by severity (LLM)
│   │   ├── remediation_agent.py  # Proposes fix commands (dry-run only)
│   │   └── reporting_agent.py    # Generates the final markdown report
│   ├── mcp_server/
│   │   ├── server.py             # FastMCP server — 6 read-only tools
│   │   └── tools/
│   │       ├── selinux.py
│   │       ├── firewall.py       # Includes broad-port-range detector
│   │       ├── ports.py
│   │       ├── packages.py       # dnf / apt distro-aware
│   │       ├── usbguard.py
│   │       └── dns.py
│   ├── security/
│   │   ├── allowlist.py          # The execution boundary
│   │   └── audit_log.py          # Append-only audit trail
│   ├── orchestrator.py           # Pipeline + retry logic for quota management
│   ├── cli.py                    # CLI with full human-approval gate
│   ├── report.py                 # Self-contained HTML report generator
│   └── config.py
├── tests/
│   ├── test_tools.py             # MCP tool tests + VM regression fixtures
│   └── test_allowlist.py         # Security gate tests
├── .env.example
├── pyproject.toml
└── README.md
```

---

## Built With

- [Google ADK](https://google.github.io/adk-docs/) — multi-agent orchestration
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) — tool server
- [Gemini 3.5 Flash](https://aistudio.google.com) — LLM reasoning (free tier)
- [Antigravity](https://antigravity.dev) — development environment

---

## Author

Built by **Rahul Verma** — Kaggle Capstone, 5-Day AI Agents: Intensive Vibe Coding Course with Google, June 2026.

---

## License

MIT — use it, modify it, run it on your own infrastructure. Just don't commit your API key.
