"""
Unit tests for gateway/interceptor/handler.py
Gateway Interceptor Lambda のツールフィルタリングロジックをテストする。
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../gateway/interceptor"))

from gateway.interceptor.handler import (
    lambda_handler,
    _extract_body,
    _classify_category,
    TOOL_FILTERS,
    MINIMUM_TOOLS,
)


class TestExtractBody(unittest.TestCase):
    """_extract_body のユニットテスト"""

    def test_dict_event_returns_directly(self):
        """dict event はそのまま返ること"""
        event = {"category": "API_5XX_SPIKE"}
        result = _extract_body(event)
        self.assertEqual(result["category"], "API_5XX_SPIKE")

    def test_json_string_body(self):
        """body が JSON 文字列の場合パースされること"""
        event = {"body": json.dumps({"category": "POD_CRASHLOOP"})}
        result = _extract_body(event)
        self.assertEqual(result["category"], "POD_CRASHLOOP")

    def test_invalid_json_body_returns_empty_dict(self):
        """body が不正 JSON の場合空 dict を返すこと（fail-closed 前段）"""
        event = {"body": "not-json{{{"}
        result = _extract_body(event)
        self.assertEqual(result, {})

    def test_non_dict_event_returns_empty_dict(self):
        """event が dict でない場合空 dict を返すこと"""
        result = _extract_body("string-event")
        self.assertEqual(result, {})

    def test_nested_body_dict(self):
        """body が dict（API Gateway v2 形式）の場合そのまま返ること"""
        event = {"body": {"alert": {"title": "test"}}}
        result = _extract_body(event)
        self.assertIn("alert", result)


class TestClassifyCategory(unittest.TestCase):
    """_classify_category のユニットテスト"""

    def test_explicit_category_api_5xx(self):
        """明示的カテゴリ API_5XX_SPIKE が優先されること"""
        body = {"category": "API_5XX_SPIKE"}
        self.assertEqual(_classify_category(body), "API_5XX_SPIKE")

    def test_explicit_category_pod_crashloop(self):
        """明示的カテゴリ POD_CRASHLOOP が優先されること"""
        body = {"category": "POD_CRASHLOOP"}
        self.assertEqual(_classify_category(body), "POD_CRASHLOOP")

    def test_explicit_category_high_latency(self):
        """明示的カテゴリ HIGH_LATENCY が優先されること"""
        body = {"category": "HIGH_LATENCY"}
        self.assertEqual(_classify_category(body), "HIGH_LATENCY")

    def test_nested_alert_category(self):
        """alert オブジェクト内の category が使用されること"""
        body = {"alert": {"category": "HIGH_LATENCY", "title": "test"}}
        self.assertEqual(_classify_category(body), "HIGH_LATENCY")

    def test_title_inference_5xx(self):
        """タイトルに '5xx' を含む場合 API_5XX_SPIKE と推論されること"""
        body = {"alert": {"title": "High 5xx error rate on payment-service"}}
        self.assertEqual(_classify_category(body), "API_5XX_SPIKE")

    def test_title_inference_error_rate(self):
        """タイトルに 'error rate' を含む場合 API_5XX_SPIKE と推論されること"""
        body = {"alert": {"title": "Elevated error rate detected"}}
        self.assertEqual(_classify_category(body), "API_5XX_SPIKE")

    def test_title_inference_crashloop(self):
        """タイトルに 'crashloop' を含む場合 POD_CRASHLOOP と推論されること"""
        body = {"alert": {"title": "Pod crashloop detected in production"}}
        self.assertEqual(_classify_category(body), "POD_CRASHLOOP")

    def test_title_inference_oom(self):
        """タイトルに 'oom' を含む場合 POD_CRASHLOOP と推論されること"""
        body = {"alert": {"title": "OOM killed pod in namespace"}}
        self.assertEqual(_classify_category(body), "POD_CRASHLOOP")

    def test_title_inference_latency(self):
        """タイトルに 'latency' を含む場合 HIGH_LATENCY と推論されること"""
        body = {"alert": {"title": "P99 latency exceeds SLO threshold"}}
        self.assertEqual(_classify_category(body), "HIGH_LATENCY")

    def test_title_inference_slow(self):
        """タイトルに 'slow' を含む場合 HIGH_LATENCY と推論されること"""
        body = {"alert": {"title": "Slow response times on order-service"}}
        self.assertEqual(_classify_category(body), "HIGH_LATENCY")

    def test_unknown_fallback(self):
        """認識できないタイトルの場合 UNKNOWN が返ること"""
        body = {"alert": {"title": "Something unexpected happened"}}
        self.assertEqual(_classify_category(body), "UNKNOWN")

    def test_empty_body_returns_unknown(self):
        """空 body の場合 UNKNOWN が返ること"""
        self.assertEqual(_classify_category({}), "UNKNOWN")


class TestLambdaHandler(unittest.TestCase):
    """lambda_handler のインテグレーションテスト"""

    def test_known_category_returns_filtered_tools(self):
        """既知カテゴリで正しいツールフィルタが返ること"""
        event = {"category": "API_5XX_SPIKE"}
        response = lambda_handler(event, None)
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["category"], "API_5XX_SPIKE")
        self.assertEqual(body["allowed_tools"], TOOL_FILTERS["API_5XX_SPIKE"])
        self.assertEqual(body["tool_count"], len(TOOL_FILTERS["API_5XX_SPIKE"]))

    def test_pod_crashloop_tools(self):
        """POD_CRASHLOOP で正しいツールセットが返ること"""
        event = {"category": "POD_CRASHLOOP"}
        response = lambda_handler(event, None)
        body = json.loads(response["body"])
        self.assertEqual(body["category"], "POD_CRASHLOOP")
        self.assertIn("check_pod_health", body["allowed_tools"])
        self.assertIn("get_runbook", body["allowed_tools"])

    def test_high_latency_tools(self):
        """HIGH_LATENCY で正しいツールセットが返ること"""
        event = {"category": "HIGH_LATENCY"}
        response = lambda_handler(event, None)
        body = json.loads(response["body"])
        self.assertEqual(body["category"], "HIGH_LATENCY")
        self.assertIn("query_latency_metrics", body["allowed_tools"])
        self.assertIn("query_slow_queries", body["allowed_tools"])

    def test_unknown_category_returns_all_tools(self):
        """UNKNOWN カテゴリでは allowed_tools が None（全ツール通過）"""
        event = {"alert": {"title": "Random alert"}}
        response = lambda_handler(event, None)
        body = json.loads(response["body"])
        self.assertEqual(body["category"], "UNKNOWN")
        self.assertIsNone(body["allowed_tools"])
        self.assertEqual(body["tool_count"], "all")

    def test_fail_closed_on_exception(self):
        """例外発生時は MINIMUM_TOOLS のみ返ること（fail-closed）"""
        from unittest.mock import patch

        # _extract_body が例外を投げるケースをシミュレート
        with patch("gateway.interceptor.handler._extract_body", side_effect=RuntimeError("parse error")):
            response = lambda_handler({"body": "test"}, None)
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["category"], "UNKNOWN")
        self.assertEqual(body["allowed_tools"], MINIMUM_TOOLS)
        self.assertEqual(body.get("error"), "fail-closed")

    def test_json_string_body_event(self):
        """API Gateway v1 形式（body が JSON 文字列）でも動作すること"""
        event = {"body": json.dumps({"category": "HIGH_LATENCY"})}
        response = lambda_handler(event, None)
        body = json.loads(response["body"])
        self.assertEqual(body["category"], "HIGH_LATENCY")

    def test_response_headers(self):
        """レスポンスに X-Alert-Category ヘッダーが含まれること"""
        event = {"category": "API_5XX_SPIKE"}
        response = lambda_handler(event, None)
        self.assertEqual(response["headers"]["X-Alert-Category"], "API_5XX_SPIKE")
        self.assertEqual(response["headers"]["Content-Type"], "application/json")


if __name__ == "__main__":
    unittest.main()
