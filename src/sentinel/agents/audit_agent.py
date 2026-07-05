"""
Audit agent.

Purely a fact-gatherer. It calls every MCP tool exactly once and hands
back structured findings - it does NOT judge severity. That separation
matters: keeping "what is true" separate from "how bad is it" makes
both steps easier to test and easier to trust independently.
"""

import sys

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import MCPToolset, StdioConnectionParams
from mcp import StdioServerParameters

from sentinel.config import MODEL_NAME

# Connects to our own MCP server as a subprocess over stdio. Using the
# current interpreter (sys.executable) keeps this portable across venvs
# instead of hardcoding "python" or "python3". ADK 2.3.0+ wraps the
# underlying mcp.StdioServerParameters in its own StdioConnectionParams -
# both layers are needed.
mcp_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["-m", "sentinel.mcp_server.server"],
        ),
        timeout=15,
    )
)

audit_agent = LlmAgent(
    name="audit_agent",
    model=MODEL_NAME,
    description="Gathers raw Linux security posture facts via MCP tools.",
    instruction="""
You are a Linux security auditor. Call every available tool exactly once
to gather facts about this machine: SELinux status, firewall rules, open
ports, pending package updates, USBGuard status, and DNS privacy
configuration.

Do not assess severity or recommend fixes here - that happens later in
the pipeline. Just collect and report what each tool returned, plainly.

Output a JSON list where each item has: "check" (the area checked),
"finding" (the plain-language result), and "raw" (any raw data returned).
""",
    tools=[mcp_toolset],
    output_key="audit_findings",
)
