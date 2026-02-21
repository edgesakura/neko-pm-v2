"""
A2A (Agent-to-Agent) Client
invoke_agent_runtime ヘルパー。AgentCore Runtime を呼び出す。
izakaya-agent の invoke_agentcore_runtime パターン参考。
"""
import json
import logging
import os
from typing import Any, Dict, Optional

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)

# デフォルトリージョン
DEFAULT_REGION = os.environ.get("AWS_REGION", "us-west-2")

# AgentCore 呼び出し用 boto3 Config（retry + timeout）
AGENT_CORE_CONFIG = Config(
    retries={"max_attempts": 3, "mode": "adaptive"},
    connect_timeout=10,
    read_timeout=30,
)


class AgentCoreClient:
    """
    AgentCore Runtime 呼び出しクライアント。
    Orchestrator から Worker エージェントを呼び出す際に使用。
    """

    def __init__(self, region: str = DEFAULT_REGION):
        self.region = region
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client(
                "bedrock-agentcore",
                region_name=self.region,
                config=AGENT_CORE_CONFIG,
            )
        return self._client

    def invoke_agent_runtime(
        self,
        agent_arn: str,
        payload: Dict[str, Any],
        session_id: Optional[str] = None,
        qualifier: str = "DEFAULT",
    ) -> Dict[str, Any]:
        """
        AgentCore Runtime にリクエストを送信する。

        Args:
            agent_arn: AgentCore Runtime の ARN
            payload: 送信するペイロード（dict）
            session_id: セッション ID（省略時は None）
            qualifier: バージョン/エイリアス修飾子

        Returns:
            エージェントからのレスポンス dict
        """
        request_kwargs: Dict[str, Any] = {
            "agentRuntimeArn": agent_arn,
            "qualifier": qualifier,
            "payload": json.dumps(payload, default=str),
        }
        if session_id:
            request_kwargs["sessionId"] = session_id

        logger.info(
            json.dumps({
                "event": "agent_invoke",
                "agent_arn": agent_arn,
                "session_id": session_id,
                "payload_keys": list(payload.keys()),
            })
        )

        try:
            response = self.client.invoke_agent_runtime(**request_kwargs)

            # レスポンスボディを読み取る（streaming or direct）
            body = response.get("body") or response.get("response", {})
            if hasattr(body, "read"):
                body = json.loads(body.read().decode("utf-8"))
            elif isinstance(body, str):
                body = json.loads(body)

            logger.info(
                json.dumps({
                    "event": "agent_invoke_success",
                    "agent_arn": agent_arn,
                    "response_keys": list(body.keys()) if isinstance(body, dict) else [],
                })
            )
            return body

        except Exception as e:
            logger.error(
                json.dumps({
                    "event": "agent_invoke_error",
                    "agent_arn": agent_arn,
                    "error": str(e),
                })
            )
            raise


def invoke_agent_runtime(
    agent_arn: str,
    payload: Dict[str, Any],
    session_id: Optional[str] = None,
    region: str = DEFAULT_REGION,
) -> Dict[str, Any]:
    """
    AgentCore Runtime 呼び出しのスタンドアロンヘルパー。

    Args:
        agent_arn: AgentCore Runtime の ARN
        payload: 送信するペイロード
        session_id: セッション ID
        region: AWS リージョン

    Returns:
        エージェントからのレスポンス
    """
    client = AgentCoreClient(region=region)
    return client.invoke_agent_runtime(
        agent_arn=agent_arn,
        payload=payload,
        session_id=session_id,
    )
