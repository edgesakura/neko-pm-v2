"""
Unit tests for agent entrypoints (orchestrator/diagnostic/knowledge)
不正 payload の処理、エラーレスポンスの安全性をテストする。
"""
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../agents/diagnostic"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../agents/knowledge"))


def _make_mock_context(session_id="test-session"):
    """テスト用の AgentCore context モック"""
    ctx = MagicMock()
    ctx.session_id = session_id
    return ctx


class TestOrchestratorEntrypoint(unittest.TestCase):
    """Orchestrator invoke エントリポイントの異常系テスト"""

    def _get_handle_alert(self):
        """handle_alert を mock 環境でインポートする"""
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock()
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {
            "strands": MagicMock(tool=MagicMock(side_effect=lambda fn: fn), Agent=MagicMock),
            "bedrock_agentcore": MagicMock(),
            "bedrock_agentcore.runtime": MagicMock(),
        }):
            with patch("common.telemetry.setup_telemetry", return_value=mock_tracer):
                # リロード不要: handle_alert を直接テスト
                from agents.orchestrator.main import handle_alert
                return handle_alert

    @patch.dict("sys.modules", {
        "strands": MagicMock(tool=MagicMock(side_effect=lambda fn: fn), Agent=MagicMock),
        "bedrock_agentcore": MagicMock(),
        "bedrock_agentcore.runtime": MagicMock(),
    })
    @patch("common.telemetry.setup_telemetry")
    def test_empty_dict_payload(self, mock_telemetry):
        """空 dict payload でもクラッシュしないこと"""
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock()
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_telemetry.return_value = mock_tracer

        # Agent() が例外を投げる場合のテスト
        with patch("strands.Agent") as mock_agent_cls:
            mock_agent_cls.side_effect = Exception("Agent init failed")
            from agents.orchestrator.main import handle_alert
            result = handle_alert({})
            self.assertEqual(result["status"], "error")
            self.assertIn("alert_id", result)
            self.assertNotIn("traceback", json.dumps(result))

    @patch.dict("sys.modules", {
        "strands": MagicMock(tool=MagicMock(side_effect=lambda fn: fn), Agent=MagicMock),
        "bedrock_agentcore": MagicMock(),
        "bedrock_agentcore.runtime": MagicMock(),
    })
    @patch("common.telemetry.setup_telemetry")
    def test_error_response_no_internal_details(self, mock_telemetry):
        """エラーレスポンスに内部詳細（スタックトレース等）が含まれないこと"""
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock()
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_telemetry.return_value = mock_tracer

        with patch("strands.Agent") as mock_agent_cls:
            mock_agent_cls.side_effect = RuntimeError("SECRET_DB_PASSWORD=abc123")
            from agents.orchestrator.main import handle_alert
            result = handle_alert({"id": "alert-1", "title": "test"})
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error"], "An internal error occurred")
            self.assertNotIn("SECRET_DB_PASSWORD", json.dumps(result))

    @patch.dict("sys.modules", {
        "strands": MagicMock(tool=MagicMock(side_effect=lambda fn: fn), Agent=MagicMock),
        "bedrock_agentcore": MagicMock(),
        "bedrock_agentcore.runtime": MagicMock(),
    })
    @patch("common.telemetry.setup_telemetry")
    def test_elapsed_ms_always_present(self, mock_telemetry):
        """レスポンスに常に elapsed_ms が含まれること"""
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock()
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        mock_telemetry.return_value = mock_tracer

        with patch("strands.Agent") as mock_agent_cls:
            mock_agent_cls.side_effect = Exception("fail")
            from agents.orchestrator.main import handle_alert
            result = handle_alert({"id": "test"})
            self.assertIn("elapsed_ms", result)
            self.assertIsInstance(result["elapsed_ms"], int)


class TestDiagnosticEntrypoint(unittest.TestCase):
    """Diagnostic invoke エントリポイントの異常系テスト"""

    _diag_tool_modules = [
        "tools.query_metrics", "tools.query_logs", "tools.check_health",
        "tools.check_db", "tools.check_eks",
    ]

    def setUp(self):
        """テスト前にモジュールキャッシュを保存"""
        self._saved_modules = {k: sys.modules.get(k) for k in self._diag_tool_modules}
        if "agents.diagnostic.main" in sys.modules:
            self._saved_diag_main = sys.modules["agents.diagnostic.main"]
        else:
            self._saved_diag_main = None

    def tearDown(self):
        """テスト後にモジュールキャッシュを復元"""
        for k, v in self._saved_modules.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        if self._saved_diag_main is None:
            sys.modules.pop("agents.diagnostic.main", None)
        else:
            sys.modules["agents.diagnostic.main"] = self._saved_diag_main

    def _setup_diagnostic_mocks(self):
        """diagnostic モジュールのインポートに必要な mock を設定"""
        mock_app = MagicMock()
        mock_app.entrypoint = lambda fn: fn
        mock_runtime = MagicMock()
        mock_runtime.BedrockAgentCoreApp.return_value = mock_app

        for mod_name in self._diag_tool_modules:
            sys.modules[mod_name] = MagicMock()

        return mock_runtime

    def test_empty_payload_returns_error(self):
        """空 payload で Agent 初期化失敗時にエラーレスポンスを返すこと"""
        mock_runtime = self._setup_diagnostic_mocks()

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {
            "strands": MagicMock(tool=MagicMock(side_effect=lambda fn: fn), Agent=MagicMock(side_effect=Exception("fail"))),
            "bedrock_agentcore": MagicMock(),
            "bedrock_agentcore.runtime": mock_runtime,
        }):
            with patch("common.telemetry.setup_telemetry", return_value=mock_tracer):
                if "agents.diagnostic.main" in sys.modules:
                    del sys.modules["agents.diagnostic.main"]
                from agents.diagnostic.main import invoke
                ctx = _make_mock_context()
                result = invoke({}, ctx)
                self.assertIsInstance(result, dict)
                self.assertIn("error", result)
                self.assertEqual(result["error"], "An internal error occurred")

    def test_error_response_no_secrets(self):
        """エラーレスポンスに内部情報が含まれないこと"""
        mock_runtime = self._setup_diagnostic_mocks()

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {
            "strands": MagicMock(tool=MagicMock(side_effect=lambda fn: fn), Agent=MagicMock(side_effect=RuntimeError("aws_secret_key=AKIAXXX"))),
            "bedrock_agentcore": MagicMock(),
            "bedrock_agentcore.runtime": mock_runtime,
        }):
            with patch("common.telemetry.setup_telemetry", return_value=mock_tracer):
                if "agents.diagnostic.main" in sys.modules:
                    del sys.modules["agents.diagnostic.main"]
                from agents.diagnostic.main import invoke
                ctx = _make_mock_context()
                result = invoke({"alert_title": "test"}, ctx)
                result_str = json.dumps(result)
                self.assertNotIn("AKIAXXX", result_str)
                self.assertNotIn("aws_secret_key", result_str)


class TestKnowledgeEntrypoint(unittest.TestCase):
    """Knowledge invoke エントリポイントの異常系テスト"""

    _knowledge_tool_modules = ["tools.search_incidents", "tools.get_runbook"]

    def setUp(self):
        """テスト前にモジュールキャッシュを保存"""
        self._saved_modules = {k: sys.modules.get(k) for k in self._knowledge_tool_modules}
        if "agents.knowledge.main" in sys.modules:
            self._saved_know_main = sys.modules["agents.knowledge.main"]
        else:
            self._saved_know_main = None

    def tearDown(self):
        """テスト後にモジュールキャッシュを復元"""
        for k, v in self._saved_modules.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        if self._saved_know_main is None:
            sys.modules.pop("agents.knowledge.main", None)
        else:
            sys.modules["agents.knowledge.main"] = self._saved_know_main

    def _setup_knowledge_mocks(self):
        """knowledge モジュールのインポートに必要な mock を設定"""
        mock_app = MagicMock()
        mock_app.entrypoint = lambda fn: fn
        mock_runtime = MagicMock()
        mock_runtime.BedrockAgentCoreApp.return_value = mock_app

        for mod_name in self._knowledge_tool_modules:
            sys.modules[mod_name] = MagicMock()

        return mock_runtime

    def test_empty_payload_returns_error(self):
        """空 payload でエラーレスポンスを返すこと"""
        mock_runtime = self._setup_knowledge_mocks()

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict("sys.modules", {
            "strands": MagicMock(tool=MagicMock(side_effect=lambda fn: fn), Agent=MagicMock(side_effect=Exception("fail"))),
            "bedrock_agentcore": MagicMock(),
            "bedrock_agentcore.runtime": mock_runtime,
        }):
            with patch("common.telemetry.setup_telemetry", return_value=mock_tracer):
                if "agents.knowledge.main" in sys.modules:
                    del sys.modules["agents.knowledge.main"]
                from agents.knowledge.main import invoke
                ctx = _make_mock_context()
                result = invoke({}, ctx)
                self.assertIsInstance(result, dict)
                self.assertIn("error", result)
                self.assertEqual(result["error"], "An internal error occurred")

    def test_missing_alert_description(self):
        """alert_description 欠落でもクラッシュしないこと"""
        mock_runtime = self._setup_knowledge_mocks()

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)

        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = MagicMock(message="test result")

        with patch.dict("sys.modules", {
            "strands": MagicMock(tool=MagicMock(side_effect=lambda fn: fn), Agent=MagicMock(return_value=mock_agent_instance)),
            "bedrock_agentcore": MagicMock(),
            "bedrock_agentcore.runtime": mock_runtime,
        }):
            with patch("common.telemetry.setup_telemetry", return_value=mock_tracer):
                if "agents.knowledge.main" in sys.modules:
                    del sys.modules["agents.knowledge.main"]
                from agents.knowledge.main import invoke
                ctx = _make_mock_context()
                result = invoke({"alert_category": "API_5XX_SPIKE"}, ctx)
                self.assertIsInstance(result, dict)
                self.assertNotIn("error", result)


if __name__ == "__main__":
    unittest.main()
