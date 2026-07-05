"""
Remediation agent.

Hard security boundary: this agent's only tool is `propose_remediation`,
which checks a command against the allowlist and returns a dry-run
preview. It has NO path to real execution - that capability simply
doesn't exist in any tool exposed to it. Actual execution only happens
later, outside the agent entirely, when a human runs `sentinel harden
--execute` and explicitly confirms each command at the CLI.

This means even a fully compromised or misbehaving LLM call cannot
mutate the system - the worst it can do is propose a bad dry-run preview,
which a human still has to read and approve before anything runs for real.
"""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from sentinel.config import MODEL_NAME
from sentinel.security.allowlist import is_allowed
from sentinel.security.audit_log import log_event


def propose_remediation(finding: str, command: str, explanation: str) -> dict:
    """
    Propose a fix for a finding. Always returns a dry-run preview -
    never executes anything. Real execution requires a separate, human-
    driven CLI step outside this agent's reach.
    """
    allowed = is_allowed(command)
    log_event(
        "remediation_proposed",
        finding=finding, command=command, allowlisted=allowed,
    )
    return {
        "finding": finding,
        "proposed_command": command,
        "explanation": explanation,
        "allowlisted": allowed,
        "note": (
            "This command is on the approved allowlist and could be run "
            "with explicit human confirmation via the CLI."
            if allowed else
            "This command is NOT on the allowlist and cannot be executed "
            "through Sentinel even with confirmation - it would need to "
            "be run manually after independent review."
        ),
    }


remediation_agent = LlmAgent(
    name="remediation_agent",
    model=MODEL_NAME,
    description="Proposes safe, reviewable remediation commands for high-severity findings.",
    instruction="""
You will receive a prioritized list of findings in state['risk_assessment'].

For every finding with severity "critical" or "high", call the
propose_remediation tool with: the finding, the exact shell command that
would fix it, and a one-sentence explanation of what that command does.

Prefer the least invasive command that actually fixes the problem.
Do not propose destructive commands (no rm -rf, no disabling logging,
no commands that remove audit trails). If you are not confident a safe
command exists, say so instead of guessing.

You cannot execute anything - only propose. Output a JSON list of the
remediation proposals you made.
""",
    tools=[FunctionTool(propose_remediation)],
    output_key="remediation_plan",
)
