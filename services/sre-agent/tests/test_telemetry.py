"""
Unit tests for common/telemetry.py
"""
import os
import unittest
from unittest.mock import MagicMock, patch

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


class TestFilteringSpanProcessor(unittest.TestCase):
    """FilteringSpanProcessor のユニットテスト"""

    def _make_processor(self, agent_name="test-agent"):
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from common.telemetry import FilteringSpanProcessor

        self.exporter = InMemorySpanExporter()
        delegate = SimpleSpanProcessor(self.exporter)
        return FilteringSpanProcessor(delegate, agent_name)

    def _run_span(self, span_name: str):
        """スパンを生成して processor に流す"""
        from common.telemetry import FilteringSpanProcessor

        processor = self._make_processor()
        provider = TracerProvider()
        provider.add_span_processor(processor)
        tracer = provider.get_tracer("test")

        with tracer.start_as_current_span(span_name):
            pass

        provider.shutdown()
        return self.exporter.get_finished_spans()

    def test_excluded_a2a_prefix(self):
        """a2a.* スパンはフィルタされること"""
        spans = self._run_span("a2a.internal_method")
        self.assertEqual(len(spans), 0)

    def test_excluded_starlette_prefix(self):
        """starlette.* スパンはフィルタされること"""
        spans = self._run_span("starlette.routing")
        self.assertEqual(len(spans), 0)

    def test_tool_span_passes(self):
        """tool.* スパンは通過すること"""
        spans = self._run_span("tool.query_cpu_metrics")
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].name, "tool.query_cpu_metrics")

    def test_knowledge_span_passes(self):
        """knowledge.* スパンは通過すること"""
        spans = self._run_span("knowledge.search")
        self.assertEqual(len(spans), 1)

    def test_agent_name_attribute(self):
        """on_start でエージェント名が付与されること"""
        from common.telemetry import FilteringSpanProcessor

        exporter = InMemorySpanExporter()
        delegate = SimpleSpanProcessor(exporter)
        processor = FilteringSpanProcessor(delegate, "diagnostic-agent")

        provider = TracerProvider()
        provider.add_span_processor(processor)
        tracer = provider.get_tracer("test")

        with tracer.start_as_current_span("tool.check_health"):
            pass

        provider.shutdown()
        spans = exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].attributes.get("agent.name"), "diagnostic-agent")


class TestCreateExporter(unittest.TestCase):
    """_create_exporter のユニットテスト"""

    def setUp(self):
        # 環境変数をクリア
        for key in ("OTEL_EXPORTER_ENDPOINT", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
            os.environ.pop(key, None)

    def test_fallback_to_console_when_no_env(self):
        """環境変数未設定時は ConsoleSpanExporter になること"""
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        from common.telemetry import _create_exporter

        exporter = _create_exporter()
        self.assertIsInstance(exporter, ConsoleSpanExporter)

    def test_langfuse_exporter_with_keys(self):
        """Langfuse キー設定時は OTLPSpanExporter になること"""
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from common.telemetry import _create_exporter

        os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-test"
        os.environ["LANGFUSE_SECRET_KEY"] = "sk-test"
        exporter = _create_exporter()
        self.assertIsInstance(exporter, OTLPSpanExporter)

    def test_datadog_endpoint_takes_priority(self):
        """OTEL_EXPORTER_ENDPOINT が設定されている場合は Datadog 優先"""
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from common.telemetry import _create_exporter

        os.environ["OTEL_EXPORTER_ENDPOINT"] = "http://localhost:4318"
        os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-test"
        os.environ["LANGFUSE_SECRET_KEY"] = "sk-test"
        exporter = _create_exporter()
        self.assertIsInstance(exporter, OTLPSpanExporter)


class TestTraceHelpers(unittest.TestCase):
    """trace_knowledge_search / trace_tool_call ヘルパーのテスト"""

    def _make_tracer(self):
        """テスト用 Tracer（InMemory）"""
        self.exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        return provider.get_tracer("test")

    def test_trace_knowledge_search_attributes(self):
        """trace_knowledge_search がスパン属性を正しく設定すること"""
        from common.telemetry import trace_knowledge_search

        tracer = self._make_tracer()
        results = [{"title": "doc1"}, {"title": "doc2"}]
        scores = [0.9, 0.7]

        trace_knowledge_search(tracer, "CPU spike cause", results, scores)

        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        attrs = spans[0].attributes
        self.assertEqual(attrs["knowledge.query"], "CPU spike cause")
        self.assertEqual(attrs["knowledge.result_count"], 2)
        self.assertAlmostEqual(attrs["knowledge.top1_relevance"], 0.9)
        self.assertAlmostEqual(attrs["knowledge.avg_relevance"], 0.8)

    def test_trace_tool_call_attributes(self):
        """trace_tool_call がスパン属性を正しく設定すること"""
        from common.telemetry import trace_tool_call

        tracer = self._make_tracer()
        trace_tool_call(
            tracer,
            tool_name="query_cpu_metrics",
            tool_input={"start_time": "2026-01-01", "end_time": "2026-01-02"},
            tool_output={"metrics": [1, 2, 3]},
        )

        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].name, "tool.query_cpu_metrics")
        attrs = spans[0].attributes
        self.assertEqual(attrs["tool.name"], "query_cpu_metrics")


if __name__ == "__main__":
    unittest.main()
