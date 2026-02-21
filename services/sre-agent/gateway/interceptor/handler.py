"""
Gateway Interceptor Lambda
アラート種別に応じてツールをフィルタリングし、コンテキストを最適化する。
三菱電機パターン (Bedrock Night 2026 Session 8)
"""
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# アラート種別 → 必要なツールのマッピング
# Gateway Semantic Search と組み合わせて 15 → 5 ツールに絞り込む
TOOL_FILTERS = {
    "API_5XX_SPIKE": [
        "query_latency_metrics",
        "query_application_logs",
        "check_service_endpoint",
        "search_incidents",
        "get_runbook",
    ],
    "POD_CRASHLOOP": [
        "check_pod_health",
        "check_node_health",
        "query_infrastructure_logs",
        "list_pods",
        "describe_deployment",
        "search_incidents",
        "get_runbook",
    ],
    "HIGH_LATENCY": [
        "query_latency_metrics",
        "query_network_metrics",
        "check_service_endpoint",
        "query_slow_queries",
        "check_connection_pool",
        "search_incidents",
    ],
}

# デフォルト（未知のカテゴリ）: 全ツール
DEFAULT_TOOLS = None  # None = フィルタなし（全ツール通過）

# フェイルクローズ時の最小ツールセット（分類のみ許可）
MINIMUM_TOOLS = ["classify_alert"]


def lambda_handler(event, context):
    """
    Gateway Interceptor: リクエストを検査し、ツールフィルタ情報を付与。

    Gateway はこの Lambda のレスポンスに基づいて
    Semantic Search のスコープを調整する。
    """
    logger.info(json.dumps({"event": "interceptor_invoked"}))

    try:
        # リクエストボディからアラート情報を抽出
        body = _extract_body(event)
        category = _classify_category(body)

        # ツールフィルタリング
        allowed_tools = TOOL_FILTERS.get(category, DEFAULT_TOOLS)

        result = {
            "category": category,
            "allowed_tools": allowed_tools,
            "tool_count": len(allowed_tools) if allowed_tools else "all",
        }

        logger.info(json.dumps({
            "event": "interceptor_result",
            "category": category,
            "tool_count": result["tool_count"],
            "action": "filter_tools",
        }))

        # Gateway に返却: フィルタ情報付きのリクエスト
        return {
            "statusCode": 200,
            "body": json.dumps(result, default=str),
            "headers": {
                "Content-Type": "application/json",
                "X-Alert-Category": category,
            },
        }

    except Exception as e:
        logger.error(json.dumps({"event": "interceptor_error", "error": str(e)}))
        # フェイルクローズ: エラー時は最小ツールセットのみ許可
        return {
            "statusCode": 200,
            "body": json.dumps({"category": "UNKNOWN", "allowed_tools": MINIMUM_TOOLS, "error": "fail-closed"}),
        }


def _extract_body(event):
    """Lambda event からリクエストボディを抽出。JSON parse 失敗時は空 dict を返す。"""
    if isinstance(event, dict):
        body = event.get("body", event)
        if isinstance(body, str):
            try:
                return json.loads(body)
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(json.dumps({"event": "body_parse_error", "error": str(e)}))
                return {}
        return body
    return {}


def _classify_category(body):
    """リクエストからアラートカテゴリを抽出"""
    # 明示的なカテゴリ指定
    category = body.get("category", "")
    if category in TOOL_FILTERS:
        return category

    # アラートオブジェクトからカテゴリ抽出
    alert = body.get("alert", body)
    category = alert.get("category", "")
    if category in TOOL_FILTERS:
        return category

    # タイトルベースの推論（フォールバック）
    title = alert.get("title", "").lower()
    if "5xx" in title or "error rate" in title:
        return "API_5XX_SPIKE"
    elif "crashloop" in title or "oom" in title:
        return "POD_CRASHLOOP"
    elif "latency" in title or "slow" in title:
        return "HIGH_LATENCY"

    return "UNKNOWN"
