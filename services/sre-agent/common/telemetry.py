"""
SRE Agent Observability Pipeline
OTel → Langfuse (Phase 1) / Datadog LLM Obs (Phase 3)
Based on umitsu's FilteringSpanProcessor pattern (Bedrock Night 2026 Session 6)
"""
import base64
import logging
import os
from typing import Optional, Sequence

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FilteringSpanProcessor
# ---------------------------------------------------------------------------

class FilteringSpanProcessor(SpanProcessor):
    """
    A2A SDK 内部スパンを除外し、重要スパンのみを通す。
    umitsu パターン: @trace_class の67メソッド等をフィルタ。
    """

    # フィルタ対象の span name prefix（A2A SDK 内部・フレームワーク内部）
    EXCLUDED_PREFIXES = (
        "a2a.",           # A2A SDK 内部メソッド
        "starlette.",     # Starlette フレームワーク内部
        "uvicorn.",       # Uvicorn 内部
        "httpx.request",  # HTTPクライアント内部（計装は別途）
    )

    # 通過させる重要スパン
    IMPORTANT_PREFIXES = (
        "tool.",          # ツール呼び出し
        "llm.",           # LLM 呼び出し
        "agent.",         # エージェント間通信
        "memory.",        # Memory API
        "knowledge.",     # ナレッジ検索
    )

    def __init__(self, delegate: SpanProcessor, agent_name: str) -> None:
        self._delegate = delegate
        self._agent_name = agent_name

    def on_start(self, span, parent_context=None) -> None:
        # エージェント名をスパン属性に付与
        span.set_attribute("agent.name", self._agent_name)
        self._delegate.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        span_name = span.name

        # 除外対象チェック（重要スパンが先に一致しても除外しない）
        for prefix in self.EXCLUDED_PREFIXES:
            if span_name.startswith(prefix):
                # 重要スパンとして明示的にマークされていれば通す
                for imp in self.IMPORTANT_PREFIXES:
                    if span_name.startswith(imp):
                        self._delegate.on_end(span)
                        return
                return  # フィルタ（通さない）

        self._delegate.on_end(span)

    def shutdown(self) -> None:
        self._delegate.shutdown()

    def force_flush(self, timeout_millis: Optional[int] = None) -> bool:
        if timeout_millis is not None:
            return self._delegate.force_flush(timeout_millis)
        return self._delegate.force_flush()


# ---------------------------------------------------------------------------
# Telemetry Setup
# ---------------------------------------------------------------------------

_initialized = False
_tracer = None


def setup_telemetry(
    agent_name: str,
    agent_role: str = "worker",
    service_name: str = "sre-agent",
) -> trace.Tracer:
    """
    OTel TracerProvider をセットアップし、Langfuse に送信する。
    冪等: 2回目以降の呼び出しでは既存の Tracer を返す。

    Phase 1: Langfuse Cloud (OTLP HTTP)
    Phase 3: Datadog LLM Obs (OTLP gRPC) に差し替え

    環境変数:
    - LANGFUSE_PUBLIC_KEY
    - LANGFUSE_SECRET_KEY
    - LANGFUSE_HOST (default: https://cloud.langfuse.com)
    - OTEL_EXPORTER_ENDPOINT (Phase 3 用: Datadog Agent endpoint)
    """
    global _initialized, _tracer
    if _initialized:
        return _tracer

    resource = Resource.create({
        "service.name": service_name,
        "agent.name": agent_name,
        "agent.role": agent_role,
    })

    exporter = _create_exporter()

    # FilteringSpanProcessor でノイズ除去しながら BatchSpanProcessor に委譲
    batch_processor = BatchSpanProcessor(exporter)
    filtering_processor = FilteringSpanProcessor(batch_processor, agent_name)

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(filtering_processor)

    trace.set_tracer_provider(provider)

    _setup_auto_instrumentation()

    logger.info("Telemetry initialized: agent=%s, role=%s", agent_name, agent_role)

    _tracer = trace.get_tracer(service_name)
    _initialized = True
    return _tracer


def _create_exporter() -> SpanExporter:
    """Phase に応じた Exporter を作成する。"""

    # Phase 3: Datadog LLM Obs（環境変数で切替）
    datadog_endpoint = os.environ.get("OTEL_EXPORTER_ENDPOINT")
    if datadog_endpoint:
        logger.info("Using Datadog OTLP exporter: %s", datadog_endpoint)
        return OTLPSpanExporter(endpoint=datadog_endpoint)

    # Phase 1: Langfuse Cloud（OTLP HTTP + Basic Auth）
    langfuse_host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")

    if public_key and secret_key:
        logger.info("Using Langfuse OTLP exporter: %s", langfuse_host)
        return OTLPSpanExporter(
            endpoint=f"{langfuse_host}/api/public/otel/v1/traces",
            headers={
                "Authorization": f"Basic {_encode_langfuse_auth(public_key, secret_key)}",
            },
        )

    # フォールバック: ローカル開発用コンソール出力
    logger.warning(
        "No OTLP exporter configured (set LANGFUSE_PUBLIC_KEY/SECRET_KEY or "
        "OTEL_EXPORTER_ENDPOINT). Falling back to ConsoleSpanExporter."
    )
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter
    return ConsoleSpanExporter()


def _encode_langfuse_auth(public_key: str, secret_key: str) -> str:
    """Langfuse Basic Auth ヘッダー用に Base64 エンコードする。"""
    credentials = f"{public_key}:{secret_key}"
    return base64.b64encode(credentials.encode()).decode()


_httpx_instrumented = False


def _setup_auto_instrumentation() -> None:
    """自動計装（Bedrock API 呼び出しなど HTTPX ベースのクライアント）をセットアップする。"""
    global _httpx_instrumented
    if _httpx_instrumented:
        return
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
        _httpx_instrumented = True
        logger.debug("HTTPXClientInstrumentor activated")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-httpx not installed; skipping")


# ---------------------------------------------------------------------------
# Knowledge Quality Tracing Helpers
# ---------------------------------------------------------------------------

def trace_knowledge_search(
    tracer: trace.Tracer,
    query: str,
    results: list,
    relevance_scores: Optional[list] = None,
) -> None:
    """
    Knowledge Agent の検索品質をトレースに記録する。
    Langfuse ダッシュボードで Relevance Score 分布を可視化できる。

    Args:
        tracer: setup_telemetry() が返す Tracer
        query: 検索クエリ文字列
        results: 検索結果リスト（各要素に "title" キーがあること推奨）
        relevance_scores: 結果ごとの Relevance Score（0.0–1.0）リスト
    """
    with tracer.start_as_current_span("knowledge.search") as span:
        span.set_attribute("knowledge.query", query)
        span.set_attribute("knowledge.result_count", len(results))

        if relevance_scores:
            top1 = relevance_scores[0] if relevance_scores else 0.0
            avg = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
            span.set_attribute("knowledge.top1_relevance", top1)
            span.set_attribute("knowledge.avg_relevance", avg)

        # 結果サマリー（トークン節約のため上位5件の title のみ）
        result_titles = [r.get("title", "unknown") for r in results[:5]]
        span.set_attribute("knowledge.result_titles", str(result_titles))


def trace_tool_call(
    tracer: trace.Tracer,
    tool_name: str,
    tool_input: dict,
    tool_output: dict,
) -> None:
    """
    ツール呼び出しをトレースに記録する。

    Args:
        tracer: setup_telemetry() が返す Tracer
        tool_name: ツール名（例: "query_cpu_metrics"）
        tool_input: ツールへの入力 dict
        tool_output: ツールからの出力 dict
    """
    with tracer.start_as_current_span(f"tool.{tool_name}") as span:
        span.set_attribute("tool.name", tool_name)
        span.set_attribute("tool.input_keys", str(list(tool_input.keys())))
        span.set_attribute("tool.output_size", len(str(tool_output)))
