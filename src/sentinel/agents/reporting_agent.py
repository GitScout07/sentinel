"""
Reporting agent.

Pulls together everything earlier agents wrote to session state and
produces one readable markdown report. This is deliberately the only
agent whose output a non-technical person needs to be able to read -
everything upstream is allowed to be terse and structured because this
step exists to translate it.
"""

from google.adk.agents import LlmAgent

from sentinel.config import MODEL_NAME

reporting_agent = LlmAgent(
    name="reporting_agent",
    model=MODEL_NAME,
    description="Generates the final markdown security report.",
    instruction="""
You have access to three pieces of session state:
- state['audit_findings']: raw facts gathered about the system
- state['risk_assessment']: severity-ranked findings with explanations
- state['remediation_plan']: proposed fix commands, if any

Write a single markdown report with these sections:
1. "## Summary" - 2-3 sentences, plain language, overall posture
2. "## Findings by severity" - a table: Finding | Severity | Why it matters
3. "## Recommended actions" - the proposed remediation commands, each
   labeled with whether it is allowlisted and safe to run via the CLI
4. "## Notes" - anything that needs human judgment Sentinel couldn't
   resolve automatically

Keep it concise enough that someone could read it in under two minutes
and know exactly what to do next.
""",
    output_key="final_report",
)
