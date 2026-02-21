"""
Incident search tool for Knowledge Agent.
Searches past incident records using Memory API (semantic search).
Falls back to local mock/incidents/seed.json for demo environments.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

from strands import tool

logger = logging.getLogger(__name__)

# Resolved at import time; works from any working directory
_SEED_PATH = os.path.join(
    os.path.dirname(__file__),
    "../../../mock/incidents/seed.json",
)


def _load_seed() -> List[Dict[str, Any]]:
    """Load incident seed data from mock file."""
    try:
        with open(_SEED_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load seed incidents: %s", e)
        return []


def _relevance_score(incident: Dict[str, Any], query: str) -> float:
    """
    Simple keyword-overlap relevance score (0.0–1.0).
    In production this is replaced by Memory API semantic score.
    """
    query_tokens = set(query.lower().split())
    searchable = " ".join([
        incident.get("title", ""),
        incident.get("description", ""),
        incident.get("root_cause", ""),
        incident.get("resolution", ""),
        incident.get("category", ""),
        " ".join(incident.get("tags", [])),
    ]).lower()

    if not query_tokens:
        return 0.0

    matched = sum(1 for token in query_tokens if token in searchable)
    return round(matched / len(query_tokens), 3)


def _search_local(query: str, top_k: int) -> List[Dict[str, Any]]:
    """Search incidents from seed.json with keyword-based scoring."""
    incidents = _load_seed()
    scored = [
        {**inc, "_score": _relevance_score(inc, query)}
        for inc in incidents
    ]
    # Sort by score descending, then by timestamp descending
    scored.sort(key=lambda x: (x["_score"], x.get("timestamp", "")), reverse=True)
    return scored[:top_k]


def _search_memory_api(
    query: str,
    category: Optional[str],
    top_k: int,
) -> Optional[List[Dict[str, Any]]]:
    """
    Search incidents via AgentCore Memory API.
    Returns None if Memory API is unavailable.
    """
    try:
        from bedrock_agentcore.memory import MemoryClient

        memory_id = os.environ.get("MEMORY_ID", "")
        if not memory_id:
            return None

        region = os.environ.get("AWS_REGION", "ap-northeast-1")
        client = MemoryClient(region_name=region)

        search_query = query
        if category:
            search_query = f"{category} {query}"

        results = client.search_memories(
            memory_id=memory_id,
            query=search_query,
            top_k=top_k,
        )

        if not results:
            return None

        return [
            {
                "id": r.get("id", ""),
                "title": r.get("content", {}).get("title", ""),
                "description": r.get("content", {}).get("description", ""),
                "root_cause": r.get("content", {}).get("root_cause", ""),
                "resolution": r.get("content", {}).get("resolution", ""),
                "severity": r.get("content", {}).get("severity", ""),
                "category": r.get("content", {}).get("category", ""),
                "duration_minutes": r.get("content", {}).get("duration_minutes", 0),
                "timestamp": r.get("content", {}).get("timestamp", ""),
                "tags": r.get("content", {}).get("tags", []),
                "lessons_learned": r.get("content", {}).get("lessons_learned", ""),
                "_score": r.get("score", 0.0),
            }
            for r in results
        ]
    except Exception as e:
        logger.debug("Memory API unavailable: %s", e)
        return None


@tool
def search_incidents(
    query: str,
    category: Optional[str] = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Search past incident records relevant to the current alert.

    Retrieves historical incidents with similar symptoms, root causes, and resolutions.
    Uses semantic search via AgentCore Memory API, with local JSON fallback for demos.
    Results are ranked by relevance score (0.0–1.0, higher is more relevant).

    Use this tool when:
    - An alert arrives and you need precedents for similar issues
    - Comparing current symptoms with known root causes
    - Finding proven resolutions for recurring incident patterns

    Args:
        query: Natural language description of the issue (e.g., "5xx error spike payment service")
        category: Optional category filter ("API_5XX_SPIKE", "POD_CRASHLOOP", "HIGH_LATENCY")
        top_k: Maximum number of results to return (default: 5)

    Returns:
        Dict with incidents list and relevance scores
    """
    # Try Memory API first
    results = _search_memory_api(query, category, top_k)
    source = "memory_api"

    # Fall back to local seed.json
    if results is None:
        results = _search_local(query, top_k)
        source = "local_mock"
        logger.info("Using local fallback for incident search: source=%s", source)

    # Apply category filter if provided (both local_mock and memory_api)
    if category:
        results = [r for r in results if r.get("category") == category or not r.get("category")][:top_k]

    scores = [r.get("_score", 0.0) for r in results]

    # Trace search quality via telemetry helper (best-effort)
    try:
        from opentelemetry import trace as otel_trace
        from common.telemetry import trace_knowledge_search
        tracer = otel_trace.get_tracer("sre-agent")
        trace_knowledge_search(tracer, query, results, scores)
    except Exception:
        pass  # Telemetry is non-critical

    # Strip internal score field from public output
    clean_results = [
        {k: v for k, v in r.items() if k != "_score"}
        for r in results
    ]

    return {
        "query": query,
        "category_filter": category,
        "source": source,
        "total_found": len(clean_results),
        "incidents": clean_results,
        "relevance_scores": scores,
    }
