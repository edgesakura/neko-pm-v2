"""
Runbook retrieval tool for Knowledge Agent.
Loads and returns Markdown runbooks keyed by alert category.
"""
import logging
import os
from typing import Dict, Optional

from strands import tool

logger = logging.getLogger(__name__)

_RUNBOOK_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "../../../mock/runbooks",
)

# Mapping from alert category to runbook filename
_CATEGORY_TO_FILE: Dict[str, str] = {
    "API_5XX_SPIKE": "api_5xx_spike.md",
    "POD_CRASHLOOP": "pod_crashloop.md",
    "HIGH_LATENCY": "high_latency.md",
}


@tool
def get_runbook(category: str) -> Dict[str, str]:
    """
    Retrieve the Runbook (step-by-step response procedure) for a given alert category.

    Returns the full Markdown content of the Runbook including:
    - Overview and typical root causes
    - Immediate response steps
    - Diagnostic commands and verification steps
    - Escalation criteria and post-incident tasks

    Use this tool when:
    - An alert is confirmed and you need the structured response procedure
    - Guiding the on-call engineer through investigation and mitigation steps
    - Checking escalation criteria for the current incident

    Args:
        category: Alert category ("API_5XX_SPIKE", "POD_CRASHLOOP", "HIGH_LATENCY")

    Returns:
        Dict with category, filename, and markdown content
    """
    filename = _CATEGORY_TO_FILE.get(category.upper())

    if not filename:
        available = list(_CATEGORY_TO_FILE.keys())
        logger.warning("Unknown runbook category: %s (available: %s)", category, available)
        return {
            "category": category,
            "filename": None,
            "content": (
                f"No runbook found for category '{category}'. "
                f"Available categories: {', '.join(available)}"
            ),
            "error": "category_not_found",
        }

    runbook_path = os.path.join(_RUNBOOK_DIR, filename)

    try:
        with open(runbook_path, encoding="utf-8") as f:
            content = f.read()

        logger.info("Runbook loaded: category=%s, file=%s, size=%d", category, filename, len(content))
        return {
            "category": category,
            "filename": filename,
            "content": content,
        }

    except FileNotFoundError:
        logger.error("Runbook file not found: category=%s, file=%s", category, filename)
        return {
            "category": category,
            "filename": filename,
            "content": f"Runbook for category '{category}' is not available.",
            "error": "file_not_found",
        }
    except Exception as e:
        logger.error("Failed to load runbook: category=%s, error=%s", category, str(e), exc_info=True)
        return {
            "category": category,
            "filename": filename,
            "content": "An internal error occurred while loading the runbook.",
            "error": "read_error",
        }
