"""
Unit tests for agents/orchestrator/tools/classify_alert.py
classify_alert ツールのカテゴリ分類・重要度判定をテストする。
"""
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# strands の @tool デコレータを mock してからインポート
# (strands がインストールされていない環境でもテスト可能にする)
_mock_tool = MagicMock(side_effect=lambda fn: fn)
with patch.dict("sys.modules", {"strands": MagicMock(tool=_mock_tool)}):
    from agents.orchestrator.tools.classify_alert import (
        classify_alert,
        _keyword_classify,
        _classify_severity,
    )
    from common.models import AlertCategory, AlertSeverity


class TestClassifyAlertExplicitCategory(unittest.TestCase):
    """明示的カテゴリの優先テスト"""

    def test_explicit_api_5xx_spike(self):
        """明示的 API_5XX_SPIKE カテゴリが最優先されること"""
        alert = json.dumps({"category": "API_5XX_SPIKE", "title": "test", "severity": "high"})
        result = classify_alert(alert)
        self.assertEqual(result["category"], "API_5XX_SPIKE")
        self.assertEqual(result["confidence"], "high")
        self.assertIn("Explicit category", result["reasoning"])

    def test_explicit_pod_crashloop(self):
        """明示的 POD_CRASHLOOP カテゴリが最優先されること"""
        alert = json.dumps({"category": "POD_CRASHLOOP", "title": "test", "severity": "critical"})
        result = classify_alert(alert)
        self.assertEqual(result["category"], "POD_CRASHLOOP")
        self.assertEqual(result["confidence"], "high")

    def test_explicit_high_latency(self):
        """明示的 HIGH_LATENCY カテゴリが最優先されること"""
        alert = json.dumps({"category": "HIGH_LATENCY", "title": "test"})
        result = classify_alert(alert)
        self.assertEqual(result["category"], "HIGH_LATENCY")

    def test_explicit_unknown(self):
        """明示的 UNKNOWN カテゴリが最優先されること"""
        alert = json.dumps({"category": "UNKNOWN", "title": "test"})
        result = classify_alert(alert)
        self.assertEqual(result["category"], "UNKNOWN")


class TestClassifyAlertKeywordMatch(unittest.TestCase):
    """キーワードマッチによる分類テスト"""

    def test_5xx_in_title(self):
        """タイトルに '5xx' を含む場合 API_5XX_SPIKE になること"""
        alert = json.dumps({"title": "5xx errors on payment-service", "severity": "high"})
        result = classify_alert(alert)
        self.assertEqual(result["category"], "API_5XX_SPIKE")

    def test_error_rate_in_description(self):
        """description に 'error rate' を含む場合 API_5XX_SPIKE になること"""
        alert = json.dumps({"title": "alert", "description": "High error rate detected", "severity": "medium"})
        result = classify_alert(alert)
        self.assertEqual(result["category"], "API_5XX_SPIKE")

    def test_502_keyword(self):
        """'502' キーワードで API_5XX_SPIKE になること"""
        alert = json.dumps({"title": "502 Bad Gateway errors", "severity": "high"})
        result = classify_alert(alert)
        self.assertEqual(result["category"], "API_5XX_SPIKE")

    def test_503_keyword(self):
        """'503' キーワードで API_5XX_SPIKE になること"""
        alert = json.dumps({"title": "503 Service Unavailable", "severity": "high"})
        result = classify_alert(alert)
        self.assertEqual(result["category"], "API_5XX_SPIKE")

    def test_crashloop_keyword(self):
        """'crashloop' キーワードで POD_CRASHLOOP になること"""
        alert = json.dumps({"title": "CrashLoop detected", "severity": "critical"})
        result = classify_alert(alert)
        self.assertEqual(result["category"], "POD_CRASHLOOP")

    def test_oomkill_keyword(self):
        """'oomkill' キーワードで POD_CRASHLOOP になること"""
        alert = json.dumps({"title": "Container oomkill event", "severity": "high"})
        result = classify_alert(alert)
        self.assertEqual(result["category"], "POD_CRASHLOOP")

    def test_restart_loop_keyword(self):
        """'restart loop' キーワードで POD_CRASHLOOP になること"""
        alert = json.dumps({"title": "Pod in restart loop", "severity": "high"})
        result = classify_alert(alert)
        self.assertEqual(result["category"], "POD_CRASHLOOP")

    def test_latency_keyword(self):
        """'latency' キーワードで HIGH_LATENCY になること"""
        alert = json.dumps({"title": "High latency on API", "severity": "medium"})
        result = classify_alert(alert)
        self.assertEqual(result["category"], "HIGH_LATENCY")

    def test_p99_keyword(self):
        """'p99' キーワードで HIGH_LATENCY になること"""
        alert = json.dumps({"title": "P99 SLO breach", "severity": "high"})
        result = classify_alert(alert)
        self.assertEqual(result["category"], "HIGH_LATENCY")

    def test_timeout_keyword(self):
        """'timeout' キーワードで HIGH_LATENCY になること"""
        alert = json.dumps({"title": "Request timeout on checkout", "severity": "medium"})
        result = classify_alert(alert)
        self.assertEqual(result["category"], "HIGH_LATENCY")

    def test_unknown_fallback(self):
        """どのキーワードにも一致しない場合 UNKNOWN になること"""
        alert = json.dumps({"title": "Something happened", "description": "No matching keywords"})
        result = classify_alert(alert)
        self.assertEqual(result["category"], "UNKNOWN")
        self.assertEqual(result["confidence"], "low")


class TestClassifySeverity(unittest.TestCase):
    """severity 判定テスト"""

    def test_critical_severity(self):
        """critical が正しく判定されること"""
        result = _classify_severity({"severity": "critical"})
        self.assertEqual(result, AlertSeverity.CRITICAL)

    def test_high_severity(self):
        """high が正しく判定されること"""
        result = _classify_severity({"severity": "high"})
        self.assertEqual(result, AlertSeverity.HIGH)

    def test_medium_severity(self):
        """medium が正しく判定されること"""
        result = _classify_severity({"severity": "medium"})
        self.assertEqual(result, AlertSeverity.MEDIUM)

    def test_low_severity(self):
        """low が正しく判定されること"""
        result = _classify_severity({"severity": "low"})
        self.assertEqual(result, AlertSeverity.LOW)

    def test_unknown_severity_defaults_to_medium(self):
        """不明な severity は MEDIUM にフォールバックすること"""
        result = _classify_severity({"severity": "unknown_level"})
        self.assertEqual(result, AlertSeverity.MEDIUM)

    def test_missing_severity_defaults_to_medium(self):
        """severity 未指定は MEDIUM にフォールバックすること"""
        result = _classify_severity({})
        self.assertEqual(result, AlertSeverity.MEDIUM)

    def test_uppercase_severity(self):
        """大文字 severity も処理されること（lower() で変換）"""
        result = _classify_severity({"severity": "HIGH"})
        self.assertEqual(result, AlertSeverity.HIGH)


class TestClassifyAlertJsonParseError(unittest.TestCase):
    """JSON parse エラー時の処理テスト"""

    def test_invalid_json_returns_unknown(self):
        """不正 JSON でも UNKNOWN + MEDIUM が返ること"""
        result = classify_alert("not-valid-json{{{")
        self.assertEqual(result["category"], "UNKNOWN")
        self.assertEqual(result["severity"], "medium")
        self.assertEqual(result["confidence"], "low")
        self.assertIn("JSON parse error", result["reasoning"])

    def test_dict_input_accepted(self):
        """dict が直接渡された場合もパースなしで処理されること"""
        alert = {"title": "5xx on api", "severity": "high"}
        result = classify_alert(alert)
        self.assertEqual(result["category"], "API_5XX_SPIKE")

    def test_severity_in_result(self):
        """結果に常に severity フィールドが含まれること"""
        result = classify_alert(json.dumps({"title": "test"}))
        self.assertIn("severity", result)
        self.assertIn(result["severity"], ["critical", "high", "medium", "low"])


class TestKeywordClassify(unittest.TestCase):
    """_keyword_classify の直接テスト"""

    def test_http_5_keyword(self):
        """'http 5' で API_5XX_SPIKE に分類されること"""
        cat, conf, _ = _keyword_classify("http 500 internal server error")
        self.assertEqual(cat, AlertCategory.API_5XX_SPIKE)
        self.assertEqual(conf, "high")

    def test_504_keyword(self):
        """'504' で API_5XX_SPIKE に分類されること"""
        cat, _, _ = _keyword_classify("504 gateway timeout")
        self.assertEqual(cat, AlertCategory.API_5XX_SPIKE)

    def test_crashloopbackoff_keyword(self):
        """'crashloopbackoff' で POD_CRASHLOOP に分類されること"""
        cat, _, _ = _keyword_classify("pod in crashloopbackoff state")
        self.assertEqual(cat, AlertCategory.POD_CRASHLOOP)

    def test_response_time_keyword(self):
        """'response time' で HIGH_LATENCY に分類されること"""
        cat, _, _ = _keyword_classify("high response time on service")
        self.assertEqual(cat, AlertCategory.HIGH_LATENCY)

    def test_no_match_returns_unknown(self):
        """一致なしで UNKNOWN + low confidence"""
        cat, conf, _ = _keyword_classify("disk usage warning")
        self.assertEqual(cat, AlertCategory.UNKNOWN)
        self.assertEqual(conf, "low")


if __name__ == "__main__":
    unittest.main()
