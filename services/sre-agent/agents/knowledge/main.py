"""
SRE Knowledge Agent
Retrieves past incident records and Runbooks to support diagnosis.

Phase 1: Langfuse tracing, local mock data
Phase 3: Real Memory API, Datadog LLM Obs
"""
import json
import logging
import time
from typing import Any, Dict

from strands import Agent
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from tools.search_incidents import search_incidents
from tools.get_runbook import get_runbook

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
from common.telemetry import setup_telemetry

logger = logging.getLogger(__name__)

# Ensure logs reach CloudWatch (AgentCore captures stdout)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger().addHandler(_handler)
logging.getLogger().setLevel(logging.INFO)

SYSTEM_PROMPT = """You are the SRE Knowledge Agent, specialized in retrieving incident history and operational runbooks.

## Your Role
- Search past incident records to find similar issues and proven resolutions
- Retrieve step-by-step Runbooks for the current alert category
- Provide structured, actionable knowledge to the Orchestrator Agent

## Tool Usage Rules
1. Always call search_incidents first with the alert description and category
2. Then call get_runbook for the matching alert category
3. Return both the similar incidents and the runbook content in your response

## Response Format
- Summarize top 3 similar incidents (title, root cause, resolution, duration)
- Include the full runbook content for the alert category
- Highlight any patterns or recurring issues from historical data

## Important Notes
- Focus on facts from the incident database, not speculation
- Include relevance scores to indicate how closely past incidents match
- If no similar incidents found, clearly state this and still provide the runbook
"""

# Initialize AgentCore App and tracer
app = BedrockAgentCoreApp()
tracer = setup_telemetry(
    agent_name="knowledge-agent",
    agent_role="knowledge",
    service_name="sre-agent",
)


def _log_json(level: str, event: str, **kwargs: Any) -> None:
    """Emit a structured JSON log line for CloudWatch Insights."""
    record = {"event": event, "level": level.upper(), **kwargs}
    print(json.dumps(record, ensure_ascii=False, default=str))


def _extract_text(response: Any) -> str:
    """Safely extract plain text from a Strands Agent response."""
    msg = response.message if hasattr(response, "message") else response

    if isinstance(msg, str):
        return msg

    if isinstance(msg, dict):
        content = msg.get("content", [])
        if isinstance(content, list):
            texts = [c.get("text", "") for c in content if isinstance(c, dict) and "text" in c]
            if texts:
                return "\n".join(texts)
        if isinstance(msg.get("text"), str):
            return msg["text"]

    return str(msg)


@app.entrypoint
def invoke(payload: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AgentCore entrypoint for Knowledge Agent.

    Args:
        payload: Request containing alert description and category
        context: AgentCore execution context

    Returns:
        Knowledge response with similar incidents and runbook
    """
    t_start = time.time()

    try:
        session_id = getattr(context, "session_id", None) or payload.get("session_id", "default")
        alert_description = payload.get("alert_description", "")
        alert_category = payload.get("alert_category", "")

        _log_json("info", "knowledge_invoke_start",
                  session_id=session_id,
                  category=alert_category,
                  description_length=len(alert_description))

        # Build query for the agent
        query = f"""
Alert Category: {alert_category}
Alert Description: {alert_description}

Please search for similar past incidents and retrieve the appropriate runbook.
Provide:
1. Top similar incidents from history with root causes and resolutions
2. The complete runbook for this alert category
3. Any patterns or recurring themes you notice
""".strip()

        with tracer.start_as_current_span("agent.knowledge.invoke") as span:
            span.set_attribute("alert.category", alert_category)
            span.set_attribute("session.id", session_id)

            agent = Agent(
                model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
                system_prompt=SYSTEM_PROMPT,
                tools=[search_incidents, get_runbook],
            )

            t0 = time.time()
            response = agent(query)
            agent_ms = round((time.time() - t0) * 1000)

            span.set_attribute("agent.duration_ms", agent_ms)

        knowledge_text = _extract_text(response)

        _log_json("info", "knowledge_invoke_complete",
                  session_id=session_id,
                  agent_duration_ms=agent_ms,
                  total_ms=round((time.time() - t_start) * 1000),
                  response_length=len(knowledge_text))

        return {
            "knowledge": knowledge_text,
            "alert_category": alert_category,
            "session_id": session_id,
        }

    except Exception as e:
        total_ms = round((time.time() - t_start) * 1000)
        logger.error("Knowledge error: %s", str(e), exc_info=True)
        _log_json("error", "knowledge_invoke_error",
                  total_ms=total_ms)
        return {
            "error": "An internal error occurred",
            "status": "error",
        }


if __name__ == "__main__":
    app.run()
