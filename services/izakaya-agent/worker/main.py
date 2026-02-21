"""
Perspective Worker — A2A マルチパースペクティブ推薦 Worker（独立デプロイ版）
同一 Runtime を perspective パラメータで 3 視点（cospa/atmosphere/reviews）に切り替える。
ツールなし、LLM 分析のみ。
"""
import json
import logging
import os

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from prompts import PERSPECTIVE_SYSTEM_PROMPTS

logger = logging.getLogger(__name__)

# Ensure logs reach CloudWatch
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger().addHandler(_handler)
logging.getLogger().setLevel(logging.INFO)

# モデル ID（環境変数で上書き可能）
MODEL_ID = os.environ.get(
    "PERSPECTIVE_WORKER_MODEL_ID",
    "anthropic.claude-haiku-4-5-20251001-v1:0",
)

app = BedrockAgentCoreApp()

# boto3 クライアントのシングルトン（コールドスタート時のみ初期化）
_bedrock_client = boto3.client(
    "bedrock-runtime",
    region_name=os.environ.get("AWS_REGION", "ap-northeast-1"),
)


def _log_json(level: str, event: str, **kwargs):
    """CloudWatch Insights 向け構造化ログ（_log_json パターン）。"""
    record = {"event": event, "level": level.upper(), **kwargs}
    print(json.dumps(record, ensure_ascii=False, default=str))


def _call_bedrock(system_prompt: str, user_content: str) -> str:
    """Bedrock converse API を直接呼び出して LLM レスポンスを取得する。"""
    response = _bedrock_client.converse(
        modelId=MODEL_ID,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_content}]}],
        inferenceConfig={"maxTokens": 1024, "temperature": 0.3},
    )
    return response["output"]["message"]["content"][0]["text"]


def _parse_picks(raw: str, perspective: str, restaurant_count: int) -> dict:
    """
    LLM レスポンスから JSON picks を抽出する。

    スキーマ検証:
    - picks が list であること
    - 各 pick が dict であること
    - restaurant_index が int かつ [0, restaurant_count) の範囲内であること
    パース失敗・検証失敗時は空 picks を返す。
    """
    try:
        # JSON ブロックを抽出（```json ... ``` 形式にも対応）
        text = raw.strip()
        if "```" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            text = text[start:end]
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        _log_json("warning", "parse_picks_failed", perspective=perspective, raw_length=len(raw))
        return {"perspective": perspective, "picks": []}

    # picks が list であることを検証
    picks_raw = parsed.get("picks", [])
    if not isinstance(picks_raw, list):
        _log_json("warning", "parse_picks_invalid_type",
                  perspective=perspective, picks_type=type(picks_raw).__name__)
        return {"perspective": perspective, "picks": []}

    # 各 pick のスキーマ検証（不正な pick は除外）
    valid_picks = []
    for pick in picks_raw:
        if not isinstance(pick, dict):
            _log_json("warning", "parse_picks_invalid_pick",
                      perspective=perspective, pick_type=type(pick).__name__)
            continue
        idx = pick.get("restaurant_index")
        if not isinstance(idx, int) or not (0 <= idx < restaurant_count):
            _log_json("warning", "parse_picks_invalid_index",
                      perspective=perspective, restaurant_index=idx,
                      restaurant_count=restaurant_count)
            continue
        valid_picks.append(pick)

    return {"perspective": parsed.get("perspective", perspective), "picks": valid_picks}


@app.entrypoint
def invoke(payload, context):
    """
    Perspective Worker エントリポイント。

    Args:
        payload: {
            "perspective": "cospa" | "atmosphere" | "reviews",
            "restaurants": [...],  # search_restaurants の結果
            "user_context": str,   # ユーザーの要望（任意）
        }
        context: AgentCore execution context

    Returns:
        {
            "perspective": str,
            "picks": [{"rank", "name", "reason", "highlight", "restaurant_index"}]
        }
    """
    perspective = payload.get("perspective", "cospa")
    restaurants = payload.get("restaurants", [])
    user_context = payload.get("user_context", "")

    _log_json("info", "perspective_worker_start",
              perspective=perspective,
              restaurant_count=len(restaurants),
              has_user_context=bool(user_context))

    # 視点に対応するシステムプロンプトを取得（不明な視点は cospa にフォールバック）
    system_prompt = PERSPECTIVE_SYSTEM_PROMPTS.get(perspective, PERSPECTIVE_SYSTEM_PROMPTS["cospa"])

    # レストランリストを LLM に渡すフォーマットに変換
    restaurant_lines = []
    for i, r in enumerate(restaurants):
        features = r.get("features", {})
        private_room = features.get("private_room", "")
        all_you_can_drink = features.get("all_you_can_drink", "")
        line_parts = [
            f"[{i}] {r.get('name', '不明')}",
            f"評価: {r.get('rating', 'N/A')}★ ({r.get('review_count', 0)}件)",
            f"予算: {r.get('budget', '不明')}",
            f"ジャンル: {r.get('genre', '居酒屋')}",
            f"キャッチ: {r.get('catch', '')}",
            f"アクセス: {r.get('access', '')}",
        ]
        if private_room:
            line_parts.append(f"個室: {private_room}")
        if all_you_can_drink:
            line_parts.append(f"飲み放題: {all_you_can_drink}")
        restaurant_lines.append(" / ".join(p for p in line_parts if p.split(": ", 1)[-1]))

    restaurant_text = "\n".join(restaurant_lines) if restaurant_lines else "（レストランデータなし）"

    user_content_parts = [f"レストランリスト:\n{restaurant_text}"]
    if user_context:
        user_content_parts.append(f"\nユーザーの要望: {user_context}")
    user_content = "\n".join(user_content_parts)

    try:
        raw_response = _call_bedrock(system_prompt, user_content)
        result = _parse_picks(raw_response, perspective, restaurant_count=len(restaurants))

        _log_json("info", "perspective_worker_done",
                  perspective=perspective,
                  picks_count=len(result.get("picks", [])))

        return result

    except Exception as e:
        _log_json("error", "perspective_worker_error",
                  perspective=perspective,
                  error=str(e))
        return {"perspective": perspective, "picks": []}


if __name__ == "__main__":
    app.run()
