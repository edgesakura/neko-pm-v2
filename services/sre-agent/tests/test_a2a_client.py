"""
Unit tests for common/a2a_client.py
AgentCore Runtime 呼び出しクライアントのテスト。
"""
import io
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.a2a_client import (
    AGENT_CORE_CONFIG,
    AgentCoreClient,
    invoke_agent_runtime,
)


class TestAgentCoreConfig(unittest.TestCase):
    """AGENT_CORE_CONFIG の設定値テスト"""

    def test_retry_max_attempts(self):
        """retry max_attempts が 3 であること"""
        self.assertEqual(AGENT_CORE_CONFIG.retries["max_attempts"], 3)

    def test_retry_mode(self):
        """retry mode が adaptive であること"""
        self.assertEqual(AGENT_CORE_CONFIG.retries["mode"], "adaptive")

    def test_connect_timeout(self):
        """connect_timeout が 10 秒であること"""
        self.assertEqual(AGENT_CORE_CONFIG.connect_timeout, 10)

    def test_read_timeout(self):
        """read_timeout が 30 秒であること"""
        self.assertEqual(AGENT_CORE_CONFIG.read_timeout, 30)


class TestAgentCoreClientInit(unittest.TestCase):
    """AgentCoreClient の初期化テスト"""

    def test_default_region(self):
        """デフォルトリージョンが設定されること"""
        client = AgentCoreClient()
        self.assertIsNotNone(client.region)

    def test_custom_region(self):
        """カスタムリージョンが設定できること"""
        client = AgentCoreClient(region="ap-northeast-1")
        self.assertEqual(client.region, "ap-northeast-1")

    def test_lazy_initialization(self):
        """_client が None で初期化されること（lazy init）"""
        client = AgentCoreClient()
        self.assertIsNone(client._client)

    @patch("common.a2a_client.boto3.client")
    def test_client_property_creates_on_first_access(self, mock_boto3_client):
        """client プロパティ初回アクセスで boto3 client が作成されること"""
        mock_boto3_client.return_value = MagicMock()
        client = AgentCoreClient(region="us-east-1")

        # 初回アクセス
        _ = client.client
        mock_boto3_client.assert_called_once_with(
            "bedrock-agentcore",
            region_name="us-east-1",
            config=AGENT_CORE_CONFIG,
        )

    @patch("common.a2a_client.boto3.client")
    def test_client_property_reuses_on_second_access(self, mock_boto3_client):
        """client プロパティ2回目以降は同じインスタンスを返すこと"""
        mock_boto3_client.return_value = MagicMock()
        client = AgentCoreClient()

        first = client.client
        second = client.client
        self.assertIs(first, second)
        mock_boto3_client.assert_called_once()


class TestInvokeAgentRuntime(unittest.TestCase):
    """invoke_agent_runtime のリクエスト構築テスト"""

    @patch("common.a2a_client.boto3.client")
    def test_request_kwargs_basic(self, mock_boto3_client):
        """基本リクエストパラメータが正しく構築されること"""
        mock_response = {"body": json.dumps({"result": "ok"})}
        mock_client = MagicMock()
        mock_client.invoke_agent_runtime.return_value = mock_response
        mock_boto3_client.return_value = mock_client

        client = AgentCoreClient(region="us-west-2")
        result = client.invoke_agent_runtime(
            agent_arn="arn:aws:bedrock-agentcore:us-west-2:123456:agent/test",
            payload={"alert": "test"},
        )

        call_kwargs = mock_client.invoke_agent_runtime.call_args[1]
        self.assertEqual(call_kwargs["agentRuntimeArn"], "arn:aws:bedrock-agentcore:us-west-2:123456:agent/test")
        self.assertEqual(call_kwargs["qualifier"], "DEFAULT")
        self.assertNotIn("sessionId", call_kwargs)

        payload = json.loads(call_kwargs["payload"])
        self.assertEqual(payload["alert"], "test")

    @patch("common.a2a_client.boto3.client")
    def test_request_with_session_id(self, mock_boto3_client):
        """session_id 指定時にリクエストに含まれること"""
        mock_client = MagicMock()
        mock_client.invoke_agent_runtime.return_value = {"body": json.dumps({"ok": True})}
        mock_boto3_client.return_value = mock_client

        client = AgentCoreClient()
        client.invoke_agent_runtime(
            agent_arn="arn:aws:test",
            payload={"data": "value"},
            session_id="sess-123",
        )

        call_kwargs = mock_client.invoke_agent_runtime.call_args[1]
        self.assertEqual(call_kwargs["sessionId"], "sess-123")

    @patch("common.a2a_client.boto3.client")
    def test_streaming_response_body(self, mock_boto3_client):
        """streaming レスポンス（body.read()）が正しく処理されること"""
        body_content = json.dumps({"diagnosis": "CPU spike detected"})
        mock_body = io.BytesIO(body_content.encode("utf-8"))
        mock_client = MagicMock()
        mock_client.invoke_agent_runtime.return_value = {"body": mock_body}
        mock_boto3_client.return_value = mock_client

        client = AgentCoreClient()
        result = client.invoke_agent_runtime(
            agent_arn="arn:aws:test",
            payload={"query": "test"},
        )

        self.assertEqual(result["diagnosis"], "CPU spike detected")

    @patch("common.a2a_client.boto3.client")
    def test_dict_response_body(self, mock_boto3_client):
        """dict レスポンス（response key）が正しく処理されること"""
        mock_client = MagicMock()
        mock_client.invoke_agent_runtime.return_value = {
            "response": {"status": "completed", "data": "test"}
        }
        mock_boto3_client.return_value = mock_client

        client = AgentCoreClient()
        result = client.invoke_agent_runtime(
            agent_arn="arn:aws:test",
            payload={"test": True},
        )
        self.assertEqual(result["status"], "completed")

    @patch("common.a2a_client.boto3.client")
    def test_exception_is_raised(self, mock_boto3_client):
        """API エラー時に例外が re-raise されること"""
        mock_client = MagicMock()
        mock_client.invoke_agent_runtime.side_effect = Exception("API Error")
        mock_boto3_client.return_value = mock_client

        client = AgentCoreClient()
        with self.assertRaises(Exception) as ctx:
            client.invoke_agent_runtime(
                agent_arn="arn:aws:test",
                payload={"test": True},
            )
        self.assertIn("API Error", str(ctx.exception))


class TestStandaloneInvokeHelper(unittest.TestCase):
    """invoke_agent_runtime スタンドアロンヘルパーテスト"""

    @patch("common.a2a_client.boto3.client")
    def test_standalone_helper_delegates(self, mock_boto3_client):
        """スタンドアロンヘルパーが AgentCoreClient に委譲すること"""
        mock_client = MagicMock()
        mock_client.invoke_agent_runtime.return_value = {"body": json.dumps({"ok": True})}
        mock_boto3_client.return_value = mock_client

        result = invoke_agent_runtime(
            agent_arn="arn:aws:test",
            payload={"alert": "spike"},
            region="eu-west-1",
        )
        self.assertEqual(result["ok"], True)
        mock_boto3_client.assert_called_once_with(
            "bedrock-agentcore",
            region_name="eu-west-1",
            config=AGENT_CORE_CONFIG,
        )


if __name__ == "__main__":
    unittest.main()
