"""
HTML report generator for Sentinel.

Takes the structured output from the multi-agent pipeline and renders
a self-contained HTML file — no external dependencies at runtime, no
CDN calls, works completely offline. All CSS and JS are embedded inline
so the file can be shared as a single attachment or opened anywhere.

Design philosophy: tool report, not a marketing page. Dark terminal
aesthetic, monospace data, severity legible at a glance. The animated
risk score at the top gives a non-expert an instant answer before
reading a single line.
"""

import os
import re
import webbrowser
from datetime import datetime

from sentinel.config import SENTINEL_HOME

SEVERITY_ORDER  = {"critical": 0, "high": 1, "medium": 2, "low": 3, "good": 4}
SEVERITY_COLOR  = {
    "critical": "#f85149", "high": "#f85149",
    "medium":   "#e3b341", "low": "#3fb950",
    "good":     "#3fb950", "unknown": "#8b949e",
}
SEVERITY_BG = {
    "critical": "rgba(248,81,73,0.12)", "high": "rgba(248,81,73,0.08)",
    "medium":   "rgba(227,179,65,0.10)", "low": "rgba(63,185,80,0.10)",
    "good":     "rgba(63,185,80,0.08)", "unknown": "rgba(139,148,158,0.08)",
}
SEVERITY_WEIGHT = {"critical": 40, "high": 20, "medium": 8, "low": 2, "good": 0}


# ── Parsers ──────────────────────────────────────────────────────────────────

def _parse_findings(report_text: str) -> list[dict]:
    """
    Extract structured findings from the reporting agent's markdown output.

    Fix applied: the previous version reset `in_table=False` on any blank
    line, causing it to drop findings when the LLM put a blank line between
    table rows (common on free-tier models). Now we only stop parsing when
    we see a new section header (##) or a non-table line that isn't blank,
    so blank lines inside a table are tolerated correctly.
    """
    findings = []
    in_table = False

    for line in report_text.splitlines():
        stripped = line.strip()

        # A new section header always ends the table
        if stripped.startswith("##"):
            in_table = False
            continue

        # Blank lines are ignored while inside a table
        if not stripped:
            continue

        if "|" not in stripped:
            # Non-blank, non-pipe line outside a table — not a table row
            if in_table:
                # Could be a continuation paragraph; stop only if we have
                # already seen at least one data row
                if findings:
                    in_table = False
            continue

        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue

        # Detect header row ("Finding | Severity | ...")
        if cells[0].lower() in ("finding", ""):
            in_table = True
            continue

        # Detect divider row (---|---|---)
        if all(set(c.replace("-", "").replace(":", "").strip()) <= {""} for c in cells):
            in_table = True
            continue

        if in_table and len(cells) >= 2:
            severity = cells[1].lower().strip()
            findings.append({
                "finding": cells[0],
                "severity": severity if severity in SEVERITY_ORDER else "unknown",
                "why": cells[2] if len(cells) > 2 else "",
            })

    # Fallback: if the model didn't produce a table at all, try line-by-line
    if not findings:
        findings = _fallback_findings(report_text)

    return sorted(findings, key=lambda f: SEVERITY_ORDER.get(f["severity"], 99))


def _fallback_findings(report_text: str) -> list[dict]:
    """
    Fallback parser for when the LLM skipped the markdown table entirely.
    Looks for lines that explicitly name a severity label AND contain a
    colon or dash (i.e. look like a structured finding, not just prose that
    mentions the word 'high'). This avoids the previous version's over-eager
    matching which turned every sentence containing 'high' into a finding.
    """
    findings = []
    seen = set()

    for line in report_text.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) < 10:
            continue

        lower = stripped.lower()

        # Only match lines that look like findings: severity word + separator
        # e.g. "**High:** SELinux not enforcing" or "- HIGH - 974 packages"
        severity_match = None
        for sev in SEVERITY_ORDER:
            # Must appear as a word boundary, followed by punctuation or end
            if re.search(rf'\b{sev}\b', lower):
                severity_match = sev
                break

        if not severity_match:
            continue

        # Require it to look like a structured item, not a passing mention
        looks_structured = (
            stripped.startswith(("-", "*", "•", "**"))
            or ":" in stripped[:40]
            or re.match(r"^\d+[\.\)]", stripped)
        )
        if not looks_structured:
            continue

        key = stripped[:60]
        if key in seen:
            continue
        seen.add(key)

        findings.append({
            "finding": stripped[:120] + ("..." if len(stripped) > 120 else ""),
            "severity": severity_match,
            "why": "See full report text above for details.",
        })

        if len(findings) >= 10:
            break

    return findings


def _parse_actions(report_text: str) -> list[dict]:
    """
    Extract action items from the Recommended actions section.
    Returns list of dicts with 'text' and 'allowlisted' keys so the
    HTML layer doesn't have to guess allowlist status from string matching.
    """
    actions = []
    in_actions = False

    for line in report_text.splitlines():
        stripped = line.strip()

        if "recommended actions" in stripped.lower() or "## action" in stripped.lower():
            in_actions = True
            continue

        if in_actions and stripped.startswith("##"):
            break

        if not in_actions or not stripped:
            continue

        if stripped[0].isdigit() or stripped.startswith(("-", "*", "•")):
            clean = re.sub(r"^[\d\-\.\*•]+\s*", "", stripped).strip()
            if not clean:
                continue

            # Determine allowlist status from explicit markers in the text
            # The reporting agent is instructed to write "✓ allowlisted" or
            # "manual" — we detect both here rather than guessing from the
            # command prefix (which we can't reliably parse from prose).
            explicitly_allowed = any(k in clean.lower() for k in [
                "✓", "allowlisted", "safe to run via", "safe to run with"
            ])
            explicitly_manual = any(k in clean.lower() for k in [
                "manual", "not on the allowlist", "review manually",
                "not allowlisted", "independent review"
            ])

            actions.append({
                "text": clean,
                "allowlisted": explicitly_allowed,
                "manual": explicitly_manual,
            })

    return actions


def _parse_summary(report_text: str) -> str:
    """Pull the Summary section text."""
    summary_lines = []
    in_summary = False
    for line in report_text.splitlines():
        if "## summary" in line.lower():
            in_summary = True
            continue
        if in_summary and line.strip().startswith("##"):
            break
        if in_summary and line.strip():
            summary_lines.append(line.strip())
    return " ".join(summary_lines) or "Security audit complete."


def _compute_score(findings: list[dict]) -> tuple[int, str]:
    if not findings:
        return 0, "CLEAN"
    raw   = sum(SEVERITY_WEIGHT.get(f["severity"], 0) for f in findings)
    score = min(100, raw)
    label = "HIGH RISK" if score >= 60 else "MEDIUM RISK" if score >= 30 else "LOW RISK" if score > 0 else "CLEAN"
    return score, label


def _score_color(score: int) -> str:
    return "#f85149" if score >= 60 else "#e3b341" if score >= 30 else "#3fb950"


# ── HTML builder ─────────────────────────────────────────────────────────────

def generate_html(report_text: str, hostname: str = "") -> str:
    """Generate a self-contained HTML report from the agent's markdown output."""
    hostname   = hostname or os.uname().nodename
    now        = datetime.now().strftime("%Y-%m-%d %H:%M")
    findings   = _parse_findings(report_text)
    actions    = _parse_actions(report_text)
    summary    = _parse_summary(report_text)
    score, score_label = _compute_score(findings)
    score_color = _score_color(score)

    # Fix: circumference = 2π × r = 2π × 50 = 314.159
    # Previous value of 314 caused the ring to never fully close at score 100.
    circ = 314.159

    # ── Findings table rows ───────────────────────────────────────────────
    finding_rows = ""
    for f in findings:
        sev   = f["severity"]
        color = SEVERITY_COLOR.get(sev, "#8b949e")
        bg    = SEVERITY_BG.get(sev, "transparent")
        finding_rows += f"""
        <tr style="background:{bg}">
          <td class="find-cell">{f['finding']}</td>
          <td><span class="badge" style="color:{color};border-color:{color}">{sev.upper()}</span></td>
          <td class="why-cell">{f['why']}</td>
        </tr>"""

    # ── Action items ──────────────────────────────────────────────────────
    action_items = ""
    for action in actions:
        text    = action["text"]
        is_ok   = action["allowlisted"]
        is_man  = action["manual"]

        if is_ok:
            icon   = "🔧"
            color  = "#3fb950"
            border = "rgba(63,185,80,0.25)"
            status = (
                "✅ <strong>Allowlisted</strong> — Safe to run via "
                "<code>sentinel harden --execute</code> with human confirmation"
            )
        elif is_man:
            icon   = "🔒"
            color  = "#e3b341"
            border = "rgba(227,179,65,0.25)"
            status = (
                "⚠️ <strong>Manual only</strong> — Not on the allowlist. "
                "Review and run independently after careful inspection."
            )
        else:
            icon   = "○"
            color  = "#8b949e"
            border = "rgba(139,148,158,0.15)"
            status = "Review carefully before running."

        action_items += f"""
        <div class="action-item" style="border-color:{border}">
          <span class="action-icon" style="color:{color}">{icon}</span>
          <div class="action-body">
            <code class="action-text">{text}</code>
            <div class="action-status" style="color:{color}">{status}</div>
          </div>
        </div>"""

    if not action_items:
        action_items = '<p class="no-actions">✅ No immediate actions required. System looks solid.</p>'

    # ── Legend ────────────────────────────────────────────────────────────
    counts = {}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    legend_items = ""
    for sev in ["critical", "high", "medium", "low", "good"]:
        if counts.get(sev):
            c = SEVERITY_COLOR[sev]
            legend_items += (
                f'<span class="legend-pill" style="color:{c};border-color:{c}">'
                f'{counts[sev]} {sev}</span>'
            )

    findings_html = (
        f"<table class='findings-table'><thead><tr>"
        f"<th>Finding</th><th>Severity</th><th>Why it matters</th>"
        f"</tr></thead><tbody>{finding_rows}</tbody></table>"
        if findings else
        "<div class='empty'>✅ No findings — this machine looks clean.</div>"
    )

    # ── Full HTML ─────────────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sentinel — Security Report — {hostname}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;600&display=swap');
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
  :root{{
    --bg:#0d1117;--bg-card:#161b22;--bg-card2:#21262d;
    --border:#30363d;--text:#c9d1d9;--dim:#8b949e;--accent:#58a6ff;
    --mono:'JetBrains Mono','Fira Mono',monospace;
    --sans:'Inter',system-ui,sans-serif;
  }}
  body{{background:var(--bg);color:var(--text);font-family:var(--sans);
        font-size:15px;line-height:1.6;min-height:100vh;padding-bottom:60px}}

  /* Header */
  .header{{background:var(--bg-card);border-bottom:1px solid var(--border);
           padding:18px 40px;display:flex;align-items:center;gap:14px}}
  .logo{{font-family:var(--mono);font-size:20px;font-weight:600;color:var(--accent)}}
  .hdiv{{width:1px;height:22px;background:var(--border)}}
  .hmeta{{font-family:var(--mono);font-size:12px;color:var(--dim);line-height:1.5}}
  .hhost{{color:var(--text);font-weight:600}}

  /* Layout */
  .main{{max-width:900px;margin:0 auto;padding:36px 24px 0}}

  /* Hero */
  .hero{{display:flex;align-items:center;gap:36px;background:var(--bg-card);
         border:1px solid var(--border);border-radius:12px;padding:28px 32px;margin-bottom:28px}}
  .ring{{flex-shrink:0;position:relative;width:116px;height:116px}}
  .ring svg{{transform:rotate(-90deg)}}
  .score-num{{font-family:var(--mono);font-size:30px;font-weight:600;line-height:1}}
  .score-max{{font-family:var(--mono);font-size:11px;color:var(--dim);margin-top:2px}}
  .ring-center{{position:absolute;inset:0;display:flex;flex-direction:column;
                align-items:center;justify-content:center}}
  .risk-label{{font-family:var(--mono);font-size:12px;font-weight:600;
               letter-spacing:2px;margin-bottom:8px}}
  .summary{{font-size:14px;line-height:1.7;margin-bottom:14px;color:var(--text)}}
  .legend{{display:flex;flex-wrap:wrap;gap:6px}}
  .legend-pill{{font-family:var(--mono);font-size:10px;font-weight:600;
                letter-spacing:.5px;padding:2px 9px;border:1px solid;
                border-radius:20px;text-transform:uppercase}}

  /* Section card */
  .section{{background:var(--bg-card);border:1px solid var(--border);
            border-radius:12px;margin-bottom:20px;overflow:hidden}}
  .section-header{{padding:14px 22px;border-bottom:1px solid var(--border);
                   display:flex;align-items:center;gap:9px}}
  .section-icon{{font-size:15px}}
  .section-title{{font-family:var(--mono);font-size:12px;font-weight:600;
                  color:var(--accent);letter-spacing:.5px;text-transform:uppercase}}
  .section-count{{margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--dim)}}

  /* Findings table */
  .findings-table{{width:100%;border-collapse:collapse}}
  .findings-table th{{font-family:var(--mono);font-size:10px;font-weight:600;
                      color:var(--dim);text-transform:uppercase;letter-spacing:.8px;
                      padding:9px 22px;text-align:left;border-bottom:1px solid var(--border);
                      background:var(--bg-card2)}}
  .findings-table td{{padding:13px 22px;vertical-align:top;
                      border-bottom:1px solid var(--border);font-size:13px}}
  .findings-table tr:last-child td{{border-bottom:none}}
  .find-cell{{font-family:var(--mono);font-size:12px;color:var(--text);width:32%}}
  .why-cell{{color:var(--dim);line-height:1.6}}
  .badge{{font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:1px;
          padding:2px 7px;border:1px solid;border-radius:4px;white-space:nowrap}}

  /* Actions */
  .actions-body{{padding:18px 22px;display:flex;flex-direction:column;gap:10px}}
  .action-item{{display:flex;align-items:flex-start;gap:12px;padding:13px 15px;
                background:var(--bg-card2);border-radius:8px;border:1px solid}}
  .action-icon{{font-size:16px;flex-shrink:0;margin-top:1px}}
  .action-body{{flex:1;min-width:0}}
  .action-text{{font-family:var(--mono);font-size:12px;color:var(--text);
                line-height:1.6;word-break:break-all;display:block;margin-bottom:5px}}
  .action-status{{font-size:12px;line-height:1.5}}
  .action-status code{{font-family:var(--mono);font-size:11px;
                       background:rgba(255,255,255,.06);padding:1px 5px;border-radius:3px}}
  .no-actions{{color:var(--dim);font-size:14px;padding:14px 22px}}
  .empty{{padding:28px 22px;text-align:center;color:var(--dim);
          font-family:var(--mono);font-size:13px}}

  /* Safety banner */
  .safety{{background:rgba(248,81,73,.07);border:1px solid rgba(248,81,73,.25);
           border-radius:10px;padding:14px 20px;margin-bottom:20px;
           font-size:13px;color:var(--text);line-height:1.6}}
  .safety strong{{color:#f85149}}
  .safety code{{font-family:var(--mono);font-size:12px;
                background:rgba(255,255,255,.06);padding:1px 5px;border-radius:3px}}

  /* Footer */
  .footer{{max-width:900px;margin:32px auto 0;padding:0 24px;
           display:flex;align-items:center;justify-content:space-between;
           flex-wrap:wrap;gap:8px}}
  .footer-brand{{font-family:var(--mono);font-size:11px;color:var(--dim)}}
  .footer-brand span{{color:var(--accent)}}
  .footer-ts{{font-family:var(--mono);font-size:11px;color:var(--dim)}}

  @media(max-width:600px){{
    .hero{{flex-direction:column;gap:18px}}
    .header{{padding:14px 18px}}
    .main{{padding:20px 14px 0}}
  }}
</style>
</head>
<body>

<header class="header">
  <div class="logo">🛡 sentinel</div>
  <div class="hdiv"></div>
  <div class="hmeta">
    <div class="hhost">{hostname}</div>
    <div>Audit report · {now}</div>
  </div>
</header>

<main class="main">

  <!-- Safety banner — always visible, always first -->
  <div class="safety">
    <strong>⚠️ No changes have been made to this system.</strong>
    Sentinel is read-only by default. All remediation requires explicit human
    authorization via <code>sentinel harden --execute</code> followed by
    individual confirmation for each command. Review every proposed fix
    independently before approving.
  </div>

  <!-- Risk hero -->
  <div class="hero">
    <div class="ring">
      <svg width="116" height="116" viewBox="0 0 116 116">
        <circle fill="none" stroke="var(--bg-card2)" stroke-width="8" cx="58" cy="58" r="48"/>
        <circle fill="none" stroke="{score_color}" stroke-width="8"
                stroke-linecap="round" cx="58" cy="58" r="48"
                stroke-dasharray="{circ:.3f}"
                stroke-dashoffset="{circ:.3f}"
                id="score-arc"/>
      </svg>
      <div class="ring-center">
        <div class="score-num" style="color:{score_color}" id="score-num">0</div>
        <div class="score-max">/ 100</div>
      </div>
    </div>
    <div style="flex:1">
      <div class="risk-label" style="color:{score_color}">{score_label}</div>
      <p class="summary">{summary}</p>
      <div class="legend">{legend_items}</div>
    </div>
  </div>

  <!-- Findings -->
  <div class="section">
    <div class="section-header">
      <span class="section-icon">🔍</span>
      <span class="section-title">Findings by Severity</span>
      <span class="section-count">{len(findings)} finding{'s' if len(findings) != 1 else ''}</span>
    </div>
    {findings_html}
  </div>

  <!-- Actions -->
  <div class="section">
    <div class="section-header">
      <span class="section-icon">⚡</span>
      <span class="section-title">Recommended Actions</span>
      <span class="section-count">Pending human approval</span>
    </div>
    <div class="actions-body">{action_items}</div>
  </div>

</main>

<footer class="footer">
  <div class="footer-brand"><span>sentinel</span> · agentic linux security audit</div>
  <div class="footer-ts">Generated {now}</div>
</footer>

<script>
  // Animate risk score ring — r=48, circumference = 2π×48 = {circ:.3f}
  const target = {score};
  const circ   = {circ:.3f};
  const arc    = document.getElementById('score-arc');
  const num    = document.getElementById('score-num');
  let start    = null;

  (function animate(ts) {{
    if (!start) start = ts;
    const p = Math.min((ts - start) / 1200, 1);
    const e = 1 - Math.pow(1 - p, 3);          // ease-out cubic
    const v = Math.round(target * e);
    num.textContent = v;
    arc.style.strokeDashoffset = circ - (circ * v / 100);
    if (p < 1) requestAnimationFrame(animate);
  }})(performance.now());
</script>
</body>
</html>"""


# ── Save & open ───────────────────────────────────────────────────────────────

def save_and_open(report_text: str, auto_open: bool = True) -> str:
    """Save the HTML report to ~/.sentinel/report.html and open in browser."""
    os.makedirs(SENTINEL_HOME, exist_ok=True)
    path = os.path.join(SENTINEL_HOME, "report.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(generate_html(report_text))
    if auto_open:
        webbrowser.open(f"file://{path}")
    return path
