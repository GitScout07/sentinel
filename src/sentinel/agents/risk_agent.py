"""
Risk reasoning agent.

This is the one step in the pipeline where the LLM call genuinely earns
its keep over a static script: it looks at the COMBINATION of findings,
not each one in isolation, and explains why a combination is worse than
the sum of its parts (e.g. permissive SELinux + an open SSH port is a
materially different risk than either fact alone).
"""

from google.adk.agents import LlmAgent

from sentinel.config import MODEL_NAME

risk_agent = LlmAgent(
    name="risk_agent",
    model=MODEL_NAME,
    description="Prioritizes audit findings by severity and explains why they matter.",
    instruction="""
You will receive a list of raw audit findings in state['audit_findings'].

For each finding, and for any meaningful COMBINATION of findings, assign
a severity: critical, high, medium, or low. Explain in one or two plain
sentences why that severity is warranted - assume the reader is not a
security expert.

Pay particular attention to combinations that compound risk (e.g. a
disabled firewall plus an open management port, or permissive SELinux
plus outdated packages with known CVEs).

Output a JSON list where each item has: "finding", "severity", and
"why_it_matters". Order the list from most to least severe.
""",
    output_key="risk_assessment",
)
