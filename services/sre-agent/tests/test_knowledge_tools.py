"""
Unit tests for Knowledge Agent tools.
"""
import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

# Path setup so tests can import from agents/knowledge and common
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../agents/knowledge"))


class TestSearchIncidents(unittest.TestCase):
    """Tests for search_incidents tool."""

    def setUp(self):
        """Ensure Memory API is not available (use local fallback)."""
        os.environ.pop("MEMORY_ID", None)

    def test_returns_results_from_local_fallback(self):
        """search_incidents returns results from seed.json without Memory API."""
        from tools.search_incidents import search_incidents
        result = search_incidents("5xx spike payment service")
        self.assertIn("incidents", result)
        self.assertIsInstance(result["incidents"], list)
        self.assertEqual(result["source"], "local_mock")

    def test_category_filter(self):
        """Category filter returns only matching incidents."""
        from tools.search_incidents import search_incidents
        result = search_incidents("pod crash", category="POD_CRASHLOOP")
        for inc in result["incidents"]:
            self.assertEqual(inc["category"], "POD_CRASHLOOP")

    def test_top_k_limit(self):
        """top_k parameter limits the number of results."""
        from tools.search_incidents import search_incidents
        result = search_incidents("error", top_k=3)
        self.assertLessEqual(len(result["incidents"]), 3)

    def test_relevance_scores_present(self):
        """Relevance scores are included and in valid range."""
        from tools.search_incidents import search_incidents
        result = search_incidents("memory oom pod restart")
        scores = result.get("relevance_scores", [])
        for score in scores:
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)

    def test_empty_query_still_returns_results(self):
        """Empty query returns incidents (no crash)."""
        from tools.search_incidents import search_incidents
        result = search_incidents("")
        self.assertIn("incidents", result)

    def test_score_field_not_in_output(self):
        """Internal _score field is not exposed in the output incidents."""
        from tools.search_incidents import search_incidents
        result = search_incidents("latency spike")
        for inc in result["incidents"]:
            self.assertNotIn("_score", inc)


class TestGetRunbook(unittest.TestCase):
    """Tests for get_runbook tool."""

    def test_known_category_returns_content(self):
        """Known category returns runbook markdown content."""
        from tools.get_runbook import get_runbook
        result = get_runbook("API_5XX_SPIKE")
        self.assertNotIn("error", result)
        self.assertIn("content", result)
        self.assertGreater(len(result["content"]), 10)
        self.assertEqual(result["category"], "API_5XX_SPIKE")

    def test_pod_crashloop_runbook(self):
        """POD_CRASHLOOP runbook loads correctly."""
        from tools.get_runbook import get_runbook
        result = get_runbook("POD_CRASHLOOP")
        self.assertNotIn("error", result)
        self.assertEqual(result["filename"], "pod_crashloop.md")

    def test_high_latency_runbook(self):
        """HIGH_LATENCY runbook loads correctly."""
        from tools.get_runbook import get_runbook
        result = get_runbook("HIGH_LATENCY")
        self.assertNotIn("error", result)
        self.assertEqual(result["filename"], "high_latency.md")

    def test_unknown_category_returns_error(self):
        """Unknown category returns error key in result."""
        from tools.get_runbook import get_runbook
        result = get_runbook("UNKNOWN_CATEGORY")
        self.assertIn("error", result)
        self.assertEqual(result["error"], "category_not_found")

    def test_case_insensitive_category(self):
        """Category matching is case-insensitive."""
        from tools.get_runbook import get_runbook
        result = get_runbook("api_5xx_spike")
        self.assertNotIn("error", result)


if __name__ == "__main__":
    unittest.main()
