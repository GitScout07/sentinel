# Sentinel — Demo Video Script
## 5 minutes | Rahul Verma | Kaggle Capstone June 2026

---

### BEFORE YOU RECORD

Set your terminal font to at least 16pt. Open the VM. Have `sentinel audit` ready to run.
Record in sections — one take per section is far easier than one 5-minute take.
Speak naturally. These are talking points, not lines to read word for word.

---

### [0:00 – 0:30] THE PROBLEM

*Show: a terminal with a long, messy shell script output scrolling by — or just your desktop*

"Every Linux system has a security posture — a set of configuration choices that determines how exposed it is to attack. And in most teams, assessing that posture means running a shell script, reading a wall of output, and hoping whoever's looking at it knows what to care about.

Scripts give you facts. They don't give you judgment. They tell you SELinux is in permissive mode. They don't tell you what that means when 974 packages are also unpatched and your firewall has 64,000 ports open.

That triage step is the hard part. And it's exactly what an AI agent can do."

---

### [0:30 – 1:00] WHY AGENTS

*Show: the architecture diagram from the README*

"I built Sentinel to solve this — a multi-agent system that audits a real Linux machine, reasons about what the findings mean in combination, and proposes safe fixes.

The key word is combination. A single unpatched package is low risk. The same package on a machine with permissive SELinux and a wide-open firewall is a completely different situation. That's the kind of cross-finding reasoning that language models handle well — and that no static script can do.

But there's a catch. Agents that can reason about security risks shouldn't be the same agents that execute changes on your system. Sentinel keeps those two things structurally separate."

---

### [1:00 – 2:00] ARCHITECTURE

*Show: architecture diagram, then briefly flip through the agent files in your editor*

"Sentinel runs as a four-agent pipeline using Google ADK's SequentialAgent.

The first agent is the Audit Agent. It connects to a custom MCP server that exposes six read-only system checks as tools — SELinux status, firewall rules, open ports, pending package updates, USBGuard, and DNS privacy. No LLM involved here — this is pure deterministic Python. Facts only.

Those findings pass to the Risk Reasoning Agent, where Gemini comes in. It looks at the combination of results and assigns severity — critical, high, medium, or low — with a plain-language explanation for each one. This is where the 'connecting findings' work actually happens.

Next, the Remediation Agent proposes specific fix commands. But here's the important part — it can only propose. Its only tool returns a dry-run preview and checks every command against an explicit allowlist. The LLM has no execution capability at all.

Finally, the Reporting Agent assembles everything into a clean markdown report and a self-contained HTML dashboard."

---

### [2:00 – 2:20] SECURITY DESIGN

*Show: allowlist.py briefly — just enough to see the ALLOWED_PREFIXES list*

"The security boundary is worth a moment because it's structural, not just a promise in a prompt.

The LLM cannot run anything. The remediation agent's tool registry has no function that executes shell commands. Real execution only happens in the CLI, through `sentinel harden --execute`, which asks you to type y for each command individually after showing you what it does.

Even if the model hallucinates a dangerous command, the allowlist blocks it. Even if it gets past the allowlist, you still have to approve it. That's two independent gates, enforced in code."

---

### [2:20 – 4:00] LIVE DEMO

*Show: terminal in your VM, font size large, clean dark theme*

"Let me show you this running on a real Fedora machine."

*Run: `sentinel audit`*

"You can see it connecting to the MCP server and calling each of the six tools in sequence. That's the audit agent working — no model call yet, just Python reading the system."

*Wait for the 6 CallToolRequest lines to appear*

"Now the risk agent picks up those findings..."

*Wait for report to print*

"And here's the output.

SELinux is enforcing — that's the one green result. Then three high-severity findings: 974 pending package updates, the firewall with the entire ephemeral port range open on both TCP and UDP — that's 64,511 ports — and USBGuard running but protecting nothing because it has zero rules loaded.

Notice how the risk agent explains *why* these matter, not just lists them. The firewall finding and the package finding together are worse than either alone — broad network exposure plus an unpatched attack surface.

This is a real machine. These are real findings from a default Fedora install. I didn't set them up to look bad."

*Open the HTML report in Firefox*

"And at the same time, it generated this — a self-contained HTML report with a risk score, color-coded severity table, and the proposed actions with their authorization status clearly marked."

---

### [4:00 – 4:30] THE BUILD

*Show: briefly: Antigravity IDE with a few files open, then the GitHub repo page*

"The whole thing is built in Python using Google ADK for the agent orchestration, the Model Context Protocol for the tool server, and Gemini 3.5 Flash as the reasoning layer — which runs on the free tier.

Development happened in Antigravity IDE, which made it easy to work across the agent files and test individual tools in the MCP Inspector before wiring them into the pipeline.

The repository includes 18 unit tests — all free to run, no API key needed — including regression tests that were written directly from real machine output captured during testing. Two of those tests exist because the code had actual bugs that only showed up against a real VM."

---

### [4:30 – 5:00] CLOSE

*Show: the HTML report with the risk score visible, or back to the terminal with the report printed*

"Sentinel won't replace a dedicated security engineer. But it gives any developer or system administrator something genuinely useful — a clear, prioritized, plain-language answer to the question 'how exposed is this machine right now, and what should I do about it first?'

The code is on GitHub, link in the description. Thank you."

---

### RECORDING NOTES

**Total runtime target: 4:45 — 5:00.** The demo section is your buffer; let it breathe.

**Section order for recording** (easiest to hardest):
1. Record the live demo first while the terminal is clean and ready
2. Record the architecture section (just talking to a diagram — easy to re-take)
3. Record problem/agents/security (intro sections — also easy)
4. Record close last

**In Kdenlive:**
- Drop in sections in order, trim dead air at start/end of each clip
- Add a title card at the very start: "Sentinel · Agentic Linux Security Audit · Rahul Verma"
- Export: H.264, 1080p, high quality preset
- Upload to YouTube as **Public** (not Unlisted — the rubric requires public access)
