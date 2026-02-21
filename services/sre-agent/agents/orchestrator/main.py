"""
Orchestrator Agent - SRE マルチエージェントの指揮官
Strands Agent + BedrockAgentCoreApp

コンテキスト最適化:
  - ローカルツールは classify_alert のみ（薄いコンテキスト）
  - Worker ツールは Gateway Interceptor 経由で動的フィルタリング
  - 三菱電機パターン: 15 → 5 ツールに絞り込んでから Worker に委譲
"""
import json
import logging
import time
from typing import Any, Dict

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent

from agents.orchestrator.prompts.system import SYSTEM_PROMPT
from agents.orchestrator.tools.classify_alert import classify_alert
from common.telemetry import setup_telemetry

logger = logging.getLogger(__name__)

# 構造化ログのセットアップ（CloudWatch Insights 対応）
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger().addHandler(_handler)
logging.getLogger().setLevel(logging.INFO)

# テレメトリ初期化（OTel → Langfuse）
tracer = setup_telemetry(agent_name="orchestrator", agent_role="orchestrator")

# AgentCore App 初期化
app = BedrockAgentCoreApp()

# Orchestrator が使用するモデル
MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"


def _log_json(level: str, event: str, **kwargs) -> None:
    """CloudWatch Logs Insights 用の構造化 JSON ログ出力"""
    record = {"event": event, "level": level.upper(), "agent": "orchestrator", **kwargs}
    print(json.dumps(record, ensure_ascii=False, default=str))


def handle_alert(alert: Dict[str, Any]) -> Dict[str, Any]:
    """
    アラートを受け取り、調査・報告を行う。

    1. classify_alert でカテゴリ判定
    2. Gateway Interceptor がツールをフィルタリング
    3. Worker エージェントに調査を委譲
    4. 結果を統合してレポートを返す

    Args:
        alert: アラート dict（models.Alert に対応）

    Returns:
        インシデントレポート dict
    """
    t_start = time.time()
    alert_id = alert.get("id", "unknown")

    _log_json("info", "orchestrator_start", alert_id=alert_id, title=alert.get("title"))

    try:
        # ローカルツール: classify_alert のみ（コンテキスト最小化）
        # Gateway 経由のツールは動的フィルタリング後に利用可能になる
        agent = Agent(
            model=MODEL_ID,
            system_prompt=SYSTEM_PROMPT,
            tools=[classify_alert],
        )

        # アラート情報をプロンプトとして構築
        user_message = (
            f"Incoming alert requires immediate investigation:\n\n"
            f"{json.dumps(alert, ensure_ascii=False, indent=2)}\n\n"
            f"Please classify this alert, investigate the incident, "
            f"and provide a structured incident report with recommended actions."
        )

        with tracer.start_as_current_span("agent.orchestrator.handle"):
            response = agent(user_message)

        # レスポンスからテキストを抽出
        result_text = _extract_text(response)

        elapsed_ms = round((time.time() - t_start) * 1000)
        _log_json(
            "info", "orchestrator_complete",
            alert_id=alert_id,
            elapsed_ms=elapsed_ms,
            response_length=len(result_text),
        )

        return {
            "alert_id": alert_id,
            "status": "completed",
            "report": result_text,
            "elapsed_ms": elapsed_ms,
        }

    except Exception as e:
        elapsed_ms = round((time.time() - t_start) * 1000)
        logger.error("Orchestrator error: %s", str(e), exc_info=True)
        _log_json(
            "error", "orchestrator_error",
            alert_id=alert_id,
            elapsed_ms=elapsed_ms,
        )
        return {
            "alert_id": alert_id,
            "status": "error",
            "error": "An internal error occurred",
            "elapsed_ms": elapsed_ms,
        }


def _extract_text(response) -> str:
    """Strands Agent レスポンスからテキストを抽出する（izakaya-agent パターン準拠）"""
    msg = response.message if hasattr(response, "message") else response

    if isinstance(msg, str):
        return msg

    if isinstance(msg, dict):
        content = msg.get("content", [])
        if isinstance(content, list):
            texts = [c.get("text", "") for c in content if isinstance(c, dict) and "text" in c]
            if texts:
                return "\n".join(texts)
        if isinstance(msg.get("text"), str):
            return msg["text"]

    return str(msg)


@app.entrypoint
def invoke(payload: Dict[str, Any], context) -> Dict[str, Any]:
    """
    AgentCore Runtime エントリポイント

    Args:
        payload: リクエストペイロード
          - alert (dict): アラートデータ
          - session_id (str, optional): セッション ID
        context: AgentCore 実行コンテキスト

    Returns:
        インシデントレポート
    """
    session_id = getattr(context, "session_id", None) or payload.get("session_id", "default")
    alert = payload.get("alert", payload)

    _log_json("info", "invoke_start", session_id=session_id, alert_id=alert.get("id"))

    return handle_alert(alert)


if __name__ == "__main__":
    app.run()
