# Sentinel — Agentic Linux Security Audit & Hardening Assistant

**Track:** Agents for Business
**Author:** Rahul Verma
**Submitted for:** 5-Day AI Agents: Intensive Vibe Coding Course with Google — Kaggle Capstone, June 2026

---

## The Problem Worth Solving

Linux powers the majority of the world's servers, containers, and cloud infrastructure. Every one of those machines has a security posture — a combination of configuration choices that determines how exposed it is to attack. And in most organizations, that posture is assessed the same way it was twenty years ago: manually, inconsistently, by whoever happens to have time.

Tools exist to help. `lynis`, `openscap`, and countless shell scripts will check SELinux status, list open ports, and report pending package updates. They all share the same limitation: they give you facts without judgment. They tell you SELinux is in permissive mode. They don't tell you that permissive SELinux *combined with* 974 unpatched packages *combined with* a firewall that has 64,000 ports open is a materially different risk profile than any one of those findings alone.

That triage step — connecting findings, weighing combinations, explaining severity in language a non-expert can act on — is the part that takes judgment. It's the part that doesn't scale. And it's exactly the problem that an LLM-backed reasoning agent can solve.

---

## Why Agents, Specifically

A single LLM call could summarize a list of security findings. That's not what Sentinel does, and the distinction matters.

Sentinel uses a multi-agent architecture because the problem naturally separates into distinct concerns that shouldn't share context:

**Fact gathering** should be deterministic and fast. An LLM has no business deciding whether a port is open — that's a syscall. The audit layer is pure Python: six read-only system checks exposed as MCP tools, called by an agent that collects facts without any reasoning overhead.

**Risk reasoning** is where an LLM genuinely earns its place. Given six structured findings, a model can recognize that "USBGuard active with zero rules" combined with "no firewall enforcement on inbound USB" is a physical access vulnerability that raw data won't surface. That combination-awareness is what separates a reasoning agent from a rule engine.

**Remediation proposal** needs a different constraint: the agent must know the exact commands that fix each issue. Separating this into its own agent with its own tools (including an explicit allowlist check) keeps the reasoning clean and makes the security boundary auditable in code.

**Report generation** is a communication problem. The audience for the final report isn't the agent that ran the checks — it's a human who needs to understand what happened and what to do next.

Keeping these four concerns in separate agents, wired sequentially through ADK's `SequentialAgent`, means each step can be tested, debugged, and trusted independently. The ordering is deterministic because the problem requires it, not because an LLM decided it.

---

## Architecture

The pipeline runs as follows:

```
sentinel audit
      │
      ▼
Audit Agent → MCP Server (6 read-only tools)
      │
      ▼
Risk Reasoning Agent (Gemini 3.5 Flash)
      │
      ▼
Remediation Agent → Allowlist Gate → propose_remediation()
      │
      ▼
Reporting Agent (Gemini 3.5 Flash)
      │
      ▼
Markdown terminal output + self-contained HTML dashboard
```

The MCP server is implemented with FastMCP and exposes six tools: `check_selinux`, `check_firewall`, `check_open_ports`, `check_package_updates`, `check_usbguard`, and `check_dns_privacy`. Each tool runs a real system command, parses the output into a structured dict, and returns a human-readable `finding` string alongside the raw data.

The risk reasoning and reporting agents are the only components that call the LLM. This is a deliberate quota-conservation choice for the free tier: instead of calling the model for every tool result, the audit agent collects all six findings in one pass and passes the full set to the risk agent. Total cost per `sentinel audit` run is two LLM calls.

---

## The Security Boundary

The single most important design choice in Sentinel is structural, not architectural.

**The LLM cannot run anything.**

The remediation agent's only tool is `propose_remediation`, which checks a command against an allowlist of safe prefixes and returns a dry-run preview. There is no function in the agent's tool registry that can execute a shell command. This isn't a guardrail in a prompt — it's a capability that was never provided.

Real execution only happens in `cli.py`, through `sentinel harden --execute`. That path requires:
1. The command must match an approved prefix in `allowlist.py`
2. The user must type `y` explicitly at the terminal, per command, after reading a description of what it does

Every decision — proposed, blocked, skipped, or executed — is written to `~/.sentinel/audit.log` in JSON-lines format. The audit trail is append-only and exists outside the repository.

This design means that even a fully compromised LLM call (hallucinated command, prompt injection from a tool result, adversarial model output) cannot mutate the target system. The worst case is a bad dry-run proposal that a human reads and rejects.

---

## Real Findings from a Real Machine

The findings shown in this submission are not synthetic examples. They are the actual output from running Sentinel against a fresh Fedora Workstation VM during development:

- **SELinux**: enforcing — the one green result
- **Firewall**: `FedoraWorkstation` zone with `ports: 1025-65535/udp 1025-65535/tcp` — 64,511 ports open on each protocol, the default GNOME Boxes networking configuration
- **Open ports**: 22 listening sockets at time of test
- **Package updates**: 974 pending on a freshly installed system
- **USBGuard**: installed and active, but with zero rules — protecting nothing
- **DNS-over-TLS**: not enabled, DNS queries going out in plaintext

The firewall finding exposed a real bug in the original tool code: the `finding` field was computed from a dead variable that was never used. Real machine testing found it. The fix (a regex-based port range detector) and its regression test (using the actual captured `firewall-cmd --list-all` output) are both in the repository.

Similarly, the SELinux check was initially written to match the substring `"Enforcing"` (capital E). Real `sestatus` output uses lowercase `enforcing`. The tool silently reported "not enforcing" on an enforcing machine until live testing caught it.

These bugs matter not as failures but as evidence: the development process included real testing against real systems, not just synthetic unit tests.

---

## Implementation Quality Notes

**Retry logic**: the free-tier Gemini API is subject to 503 overload errors, especially during the capstone period when thousands of participants are hitting the same endpoints. The orchestrator implements exponential backoff (20s, 40s, 60s, 80s) with up to 5 attempts, logging each retry so the user knows what's happening.

**Distro awareness**: the package update tool detects `dnf` or `apt` and handles both, including `dnf check-update`'s non-standard exit code 100 (updates available) vs 0 (up to date).

**HTML report**: the report generator parses the reporting agent's markdown output into a structured representation (findings table, action items, summary text) and renders a self-contained HTML file with no external runtime dependencies. An animated risk score ring (0–100) gives a non-expert an immediate visual answer. A fallback renderer handles cases where the model formatted its output differently than expected.

**Test coverage**: 18 unit tests, all runnable without an API key. Includes regression tests derived directly from captured real-machine output.

---

## What I Learned

The most valuable thing this project taught me was the difference between an agent that *uses* an LLM and one that *is* an LLM.

Sentinel uses Gemini for reasoning and synthesis. It doesn't use it for fact-finding, command execution, or decision-making on behalf of the user. Every place where deterministic code could be used instead of a model call, it was. The LLM earns its place in exactly two steps and is deliberately kept out of everything else.

That discipline — knowing *where* the model adds value, not just *that* it can be used — is what I'd take forward into any future agent work.

---

## Links

- **GitHub**: https://github.com/rahulv/sentinel
- **Demo Video**: [YouTube link]
- **Live Demo**: N/A — this is a local CLI tool. Full setup instructions and a demo video are provided above.
