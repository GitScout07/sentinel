"""
Orchestrator.

Uses ADK's SequentialAgent rather than letting an LLM dynamically decide
the order of operations - audit must always happen before risk
assessment, which must always happen before remediation, which must
always happen before reporting. That ordering is a property of the
problem, not something worth spending a model call deciding. Reserve
LLM judgment for steps that actually need it (severity reasoning,
remediation wording, report writing) - this is the quota-aware design
choice mentioned in the project plan.
"""

import asyncio
import time
import warnings

# Suppress ADK's EXPERIMENTAL feature warnings - they're informational
# noise for end users and clutter the report output. Remove this if you
# want to see them during deep debugging.
warnings.filterwarnings("ignore", category=UserWarning, module="google.adk")

from google.adk.agents import SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from sentinel.agents.audit_agent import audit_agent
from sentinel.agents.remediation_agent import remediation_agent
from sentinel.agents.reporting_agent import reporting_agent
from sentinel.agents.risk_agent import risk_agent
from sentinel.config import require_api_key

APP_NAME = "sentinel"
USER_ID = "local_user"

sentinel_pipeline = SequentialAgent(
    name="sentinel_orchestrator",
    description="Runs a full Linux security audit end-to-end: audit -> risk -> remediation -> report.",
    sub_agents=[audit_agent, risk_agent, remediation_agent, reporting_agent],
)

root_agent = sentinel_pipeline


async def _try_pipeline(session_id: str) -> str:
    """Single attempt at running the pipeline."""
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id
    )
    runner = Runner(
        agent=root_agent, app_name=APP_NAME, session_service=session_service
    )
    content = types.Content(
        role="user",
        parts=[types.Part(text="Run a full security audit of this machine.")],
    )
    final_text = ""
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=content
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text or final_text
    return final_text


async def run_pipeline(session_id: str = "default") -> str:
    """
    Run the full pipeline with automatic retry on transient server errors.
    503 (overloaded) and 429 (rate limited) are both retried with
    increasing waits - these are common on the free tier, especially when
    the course is running and thousands of participants are all hitting
    the same model endpoints simultaneously.
    """
    require_api_key()

    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            result = await _try_pipeline(f"{session_id}_{attempt}")
            if result:
                return result
            # Empty response without an exception - treat as soft failure
            if attempt < max_attempts:
                print(f"Empty response on attempt {attempt}, retrying...")
                time.sleep(15)
        except Exception as e:
            err = str(e)
            if attempt == max_attempts:
                raise
            if "503" in err or "UNAVAILABLE" in err:
                wait = attempt * 20
                print(f"Server overloaded (attempt {attempt}/{max_attempts}) - waiting {wait}s...")
                time.sleep(wait)
            elif "429" in err or "EXHAUSTED" in err:
                print(f"Rate limited (attempt {attempt}/{max_attempts}) - waiting 60s...")
                time.sleep(60)
            else:
                raise

    return "Pipeline failed after all retry attempts."
