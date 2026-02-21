"""
SRE Diagnostic Agent
Performs deep technical analysis of alerts using metrics, logs, and health checks.

Phase 1: Mock tools + Langfuse tracing
Phase 3: Real Datadog API tools + Datadog LLM Obs
"""
import json
import logging
import time
from typing import Any, Dict

from strands import Agent
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Import all 15 diagnostic tools
from tools.query_metrics import (
    query_cpu_metrics,
    query_memory_metrics,
    query_disk_metrics,
    query_network_metrics,
    query_latency_metrics,
)
from tools.query_logs import (
    query_application_logs,
    query_infrastructure_logs,
    query_audit_logs,
)
from tools.check_health import (
    check_pod_health,
    check_node_health,
    check_service_endpoint,
)
from tools.check_db import (
    check_connection_pool,
    query_slow_queries,
)
from tools.check_eks import (
    list_pods,
    describe_deployment,
)

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

SYSTEM_PROMPT = """You are the SRE Diagnostic Agent, specialized in technical investigation of production incidents.

## Your Role
- Analyze alerts by querying metrics, logs, and performing health checks
- Identify root causes using systematic investigation
- Provide concrete, actionable findings to the Orchestrator Agent

## Available Tools
**Metrics**: query_cpu_metrics, query_memory_metrics, query_disk_metrics, query_network_metrics, query_latency_metrics
**Logs**: query_application_logs, query_infrastructure_logs, query_audit_logs
**Health**: check_pod_health, check_node_health, check_service_endpoint
**Database**: check_connection_pool, query_slow_queries
**Kubernetes**: list_pods, describe_deployment

## Investigation Strategy
1. Start with the most relevant metrics for the alert type:
   - API_5XX_SPIKE: query_latency_metrics, query_cpu_metrics, check_connection_pool, query_application_logs
   - POD_CRASHLOOP: check_pod_health, list_pods, query_memory_metrics, query_application_logs
   - HIGH_LATENCY: query_latency_metrics, query_cpu_metrics, check_service_endpoint, query_slow_queries
2. Query logs for error patterns during the incident window
3. Run health checks on affected services
4. Check dependencies (DB connection pool, downstream services)

## Response Format
Provide a structured Diagnosis:
```
## Alert Summary
[Alert title, severity, category]

## Findings
### Metrics
[Key metric findings with specific values]

### Logs
[Error patterns, frequencies, specific error messages]

### Health Status
[Pod/node/endpoint health summary]

## Root Cause Analysis
[Probable root cause based on evidence]

## Recommended Actions
1. [Immediate action - priority: immediate]
2. [Short-term fix - priority: short-term]
3. [Long-term improvement - priority: long-term]
```
"""

# Initialize AgentCore App and tracer
app = BedrockAgentCoreApp()
tracer = setup_telemetry(
    agent_name="diagnostic-agent",
    agent_role="diagnostic",
    service_name="sre-agent",
)

# All 15 tools
ALL_TOOLS = [
    query_cpu_metrics,
    query_memory_metrics,
    query_disk_metrics,
    query_network_metrics,
    query_latency_metrics,
    query_application_logs,
    query_infrastructure_logs,
    query_audit_logs,
    check_pod_health,
    check_node_health,
    check_service_endpoint,
    check_connection_pool,
    query_slow_queries,
    list_pods,
    describe_deployment,
]


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
    AgentCore entrypoint for Diagnostic Agent.

    Args:
        payload: Request containing alert details and affected service
        context: AgentCore execution context

    Returns:
        Diagnostic response with findings and recommended actions
    """
    t_start = time.time()

    try:
        session_id = getattr(context, "session_id", None) or payload.get("session_id", "default")
        alert_title = payload.get("alert_title", "")
        alert_category = payload.get("alert_category", "")
        alert_severity = payload.get("alert_severity", "high")
        service_name = payload.get("service_name", "")
        description = payload.get("description", "")

        _log_json("info", "diagnostic_invoke_start",
                  session_id=session_id,
                  category=alert_category,
                  severity=alert_severity,
                  service=service_name)

        query = f"""
Please diagnose the following production alert:

**Alert Title**: {alert_title}
**Category**: {alert_category}
**Severity**: {alert_severity}
**Affected Service**: {service_name}
**Description**: {description}

Follow the investigation strategy for {alert_category}:
1. Query relevant metrics for the affected service
2. Search application and infrastructure logs for error patterns
3. Run health checks on pods, nodes, and service endpoints
4. Check database connection pool and slow queries if relevant
5. List pods and describe deployment status

Provide a complete structured Diagnosis with root cause analysis and recommended actions.
""".strip()

        with tracer.start_as_current_span("agent.diagnostic.invoke") as span:
            span.set_attribute("alert.category", alert_category)
            span.set_attribute("alert.severity", alert_severity)
            span.set_attribute("service.name", service_name)
            span.set_attribute("session.id", session_id)

            agent = Agent(
                model="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                system_prompt=SYSTEM_PROMPT,
                tools=ALL_TOOLS,
            )

            t0 = time.time()
            response = agent(query)
            agent_ms = round((time.time() - t0) * 1000)

            span.set_attribute("agent.duration_ms", agent_ms)

        diagnosis_text = _extract_text(response)

        _log_json("info", "diagnostic_invoke_complete",
                  session_id=session_id,
                  agent_duration_ms=agent_ms,
                  total_ms=round((time.time() - t_start) * 1000),
                  response_length=len(diagnosis_text))

        return {
            "diagnosis": diagnosis_text,
            "alert_category": alert_category,
            "alert_severity": alert_severity,
            "service_name": service_name,
            "session_id": session_id,
        }

    except Exception as e:
        total_ms = round((time.time() - t_start) * 1000)
        logger.error("Diagnostic error: %s", str(e), exc_info=True)
        _log_json("error", "diagnostic_invoke_error",
                  total_ms=total_ms)
        return {
            "error": "An internal error occurred",
            "status": "error",
        }


if __name__ == "__main__":
    app.run()
