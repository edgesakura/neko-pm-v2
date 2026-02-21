"""
Izakaya Agent - Restaurant Search AI Agent (v2: A2A Multi-Perspective)
"""
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from strands import Agent
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from utils.memory import (
    save_conversation,
    get_conversation_history,
    search_semantic_memory,
)
from utils.secrets import validate_secrets

logger = logging.getLogger(__name__)

# Ensure logs reach CloudWatch (AgentCore captures stdout)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger().addHandler(_handler)
logging.getLogger().setLevel(logging.INFO)

# Worker Runtime ARN（環境変数で上書き可能、デフォルトはデプロイ済み ARN）
WORKER_RUNTIME_ARN = os.environ.get(
    "WORKER_RUNTIME_ARN",
    "arn:aws:bedrock-agentcore:ap-northeast-1:921563379197:runtime/izakayaperspectiveworker_Agent-lzpXHR7q3i",
)

SYSTEM_PROMPT = """あなたは「のんべいエージェント」、東京を中心とした日本各地の居酒屋・飲食店を探すAIアシスタントです。

## 基本方針
- ユーザーの「飲みたい」「食べたい」を叶える最適な店を提案する
- 曖昧な要望（「渋谷で軽く飲みたい」）でも積極的に検索し、具体的な店を提示する
- 検索結果がない場合は、条件を緩和して再検索を試みる

## ツール使用ルール
1. エリア名が出たら必ず resolve_area で座標を取得してから search_restaurants を呼ぶ
2. search_restaurants の keyword パラメータを積極的に活用する
   - 「個室」「飲み放題」「デート」等のキーワードをユーザー発話から抽出
3. 検索結果が少ない（3件未満）場合は、radius を広げるか genre を変えて再検索
4. 予算の表現を適切に変換する（「安い」→3000、「ちょっといい店」→5000-7000）

## 応答フォーマット
- 検索結果は番号付きリストで簡潔に紹介（店名・特徴・予算）
- 各店の特徴を1-2文で説明（個室の有無、雰囲気、おすすめポイント）
- 最後に「他の条件で探しますか？」等のフォローアップを添える

## 会話スタイル
- フレンドリーで親しみやすいトーン
- 「〜ですね！」「いいですね！」等の共感表現を使う
- 専門用語は避け、わかりやすく説明する

## 深堀りモード
ユーザーが「N番目」「もっと詳しく」「予約したい」等と言った場合:
1. 直前の検索結果から該当する店を特定
2. check_availability で営業時間を確認
3. 詳細情報（住所、電話、URL、個室情報、コース）を整理して返す
4. 「別の店も見る？条件変える？」のフォローアップを添える
"""

# Initialize AgentCore App
app = BedrockAgentCoreApp()

# Validate secrets at startup (fail fast if API keys are not configured)
validate_secrets()

# 深堀りパターン（STM コンテキストを参照して特定の店の詳細を返す）
_DRILL_DOWN_PATTERN = re.compile(
    r"(?:"
    r"\d+番目|[①②③④⑤]|[1-5]つ目"
    r"|もっと詳しく|詳細|詳しく教えて"
    r"|予約したい|行ってみたい|行きたい"
    r")",
    re.UNICODE,
)


def _log_json(level: str, event: str, **kwargs):
    """Emit a structured JSON log line for CloudWatch Insights."""
    record = {"event": event, "level": level.upper(), **kwargs}
    # Use print to guarantee CloudWatch visibility in AgentCore runtime
    print(json.dumps(record, ensure_ascii=False, default=str))


def _extract_text(response) -> str:
    """Safely extract plain text from a Strands Agent response."""
    msg = response.message if hasattr(response, "message") else response

    if isinstance(msg, str):
        return msg

    # Strands returns {'role': 'assistant', 'content': [{'text': '...'}]}
    if isinstance(msg, dict):
        content = msg.get("content", [])
        if isinstance(content, list):
            texts = [c.get("text", "") for c in content if isinstance(c, dict) and "text" in c]
            if texts:
                return "\n".join(texts)
        if isinstance(msg.get("text"), str):
            return msg["text"]

    return str(msg)


def _stringify_content(value: Any) -> str:
    """Best-effort conversion for heterogeneous Memory API payloads."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = [_stringify_content(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str):
            return text
        if "content" in value:
            nested = _stringify_content(value.get("content"))
            if nested:
                return nested
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _is_drill_down(user_message: str) -> bool:
    """深堀りモードかどうかを判定する。"""
    return bool(_DRILL_DOWN_PATTERN.search(user_message))


def _call_perspective_worker(
    perspective: str,
    restaurants: List[Dict[str, Any]],
    user_context: str,
    session_id: str,
) -> Dict[str, Any]:
    """
    単一視点の Perspective Worker を A2A で呼び出す。
    失敗時は空 picks を返す（フォールバック）。
    """
    from common.a2a_client import AgentCoreClient, WORKER_CONFIG

    client = AgentCoreClient(config=WORKER_CONFIG)
    try:
        result = client.invoke_agent_runtime(
            agent_arn=WORKER_RUNTIME_ARN,
            payload={
                "perspective": perspective,
                "restaurants": restaurants,
                "user_context": user_context,
            },
            session_id=session_id,
        )
        _log_json("info", "perspective_called",
                  perspective=perspective,
                  picks_count=len(result.get("picks", [])))
        return result
    except Exception as e:
        _log_json("warning", "perspective_failed",
                  perspective=perspective,
                  error=str(e))
        return {"perspective": perspective, "picks": []}


def _call_perspectives_parallel(
    restaurants: List[Dict[str, Any]],
    user_context: str,
    session_id: str,
) -> Dict[str, Dict[str, Any]]:
    """
    3 視点の Perspective Worker を並列 A2A で呼び出す。
    ThreadPoolExecutor で並列実行し、全結果を返す。
    """
    perspectives = ["cospa", "atmosphere", "reviews"]

    with ThreadPoolExecutor(max_workers=3) as pool:
        future_to_perspective = {
            pool.submit(
                _call_perspective_worker,
                p,
                restaurants,
                user_context,
                session_id,
            ): p
            for p in perspectives
        }

        results: Dict[str, Dict[str, Any]] = {}
        for future in as_completed(future_to_perspective):
            p = future_to_perspective[future]
            try:
                results[p] = future.result()
            except Exception as e:
                _log_json("warning", "perspective_future_error", perspective=p, error=str(e))
                results[p] = {"perspective": p, "picks": []}

    return results


def _format_multi_perspective(
    perspective_results: Dict[str, Dict[str, Any]],
) -> str:
    """
    3 視点の結果を統合して、ユーザー向けの提案文を生成する。
    重複する restaurant_index は最初の視点の pick を優先する。
    """
    from common.constants import PERSPECTIVE_LABELS

    lines = ["3つの視点で見つけたにゃ！\n"]
    seen_indices: set = set()

    for perspective_key, (emoji, label) in PERSPECTIVE_LABELS.items():
        result = perspective_results.get(perspective_key, {})
        picks = result.get("picks", [])

        if not picks:
            lines.append(f"{emoji} {label}: 該当店舗なし")
            continue

        # 重複排除: 他の視点ですでに紹介した店は 2 位以降にフォールバック
        top_pick = None
        for pick in picks:
            idx = pick.get("restaurant_index", -1)
            if idx not in seen_indices:
                top_pick = pick
                seen_indices.add(idx)
                break

        if top_pick is None:
            top_pick = picks[0]  # 全て重複でも表示する

        name = top_pick.get("name", "不明")
        highlight = top_pick.get("highlight", "")
        lines.append(f"{emoji} {label}: {name}（{highlight}）")

    lines.append("\n気になる店があれば番号で詳しく聞いてね！")
    return "\n".join(lines)


@app.entrypoint
def invoke(payload, context):
    """
    AgentCore entrypoint for Izakaya Agent v2 with A2A Multi-Perspective support.

    Args:
        payload: Request payload containing user message
        context: AgentCore execution context

    Returns:
        Agent response with optional multi-perspective restaurant picks
    """
    t_start = time.time()

    try:
        # Extract session ID and user ID
        session_id = getattr(context, "session_id", None) or payload.get("session_id", "default-session")
        actor_id = payload.get("user_id", session_id)

        # Extract user message
        user_message = payload.get("user_message", "") or payload.get("prompt", "こんにちは")

        _log_json("info", "invoke_start",
                  actor_id=actor_id, session_id=session_id,
                  message_length=len(user_message),
                  v2_enabled=bool(WORKER_RUNTIME_ARN))

        # Retrieve conversation history (STM)
        t0 = time.time()
        conversation_history = get_conversation_history(actor_id, session_id, k=3)
        _log_json("info", "stm_retrieved",
                  actor_id=actor_id, turns=len(conversation_history),
                  duration_ms=round((time.time() - t0) * 1000))

        # Search user preferences in long-term memory (LTM)
        t0 = time.time()
        user_preferences = search_semantic_memory(
            actor_id=actor_id,
            session_id=session_id,
            query="ユーザーの好み ジャンル 予算 エリア 雰囲気",
        )
        _log_json("info", "ltm_retrieved",
                  actor_id=actor_id, preferences_count=len(user_preferences),
                  duration_ms=round((time.time() - t0) * 1000))

        # Import tools
        from tools.search_restaurants import search_restaurants, get_last_results, clear_last_results
        from tools.resolve_area import resolve_area
        from tools.check_availability import check_availability

        # Clear stale results from previous requests to prevent data leakage
        clear_last_results()

        # 深堀りモード判定（STM の直前検索結果を参照する前にフラグ立て）
        drill_down = _is_drill_down(user_message)

        # Build context-aware prompt with conversation history and preferences
        context_prompt = f"""
【重要】過去の会話履歴:
{format_conversation_history(conversation_history)}

【重要】ユーザーの好み:
{format_user_preferences(user_preferences)}

【利用可能なジャンル】
search_restaurants ツールの genre パラメータで指定できます:
- G001: 居酒屋（デフォルト）
- G002: ダイニングバー・バル
- G003: 創作料理
- G004: 和食
- G005: 洋食
- G006: イタリアン・フレンチ
- G007: 中華
- G008: 焼肉・ホルモン
- G009: 韓国料理
- G010: 各国料理
- G011: カラオケ・パーティ
- G012: バー・カクテル
- G013: ラーメン
- G014: カフェ・スイーツ
- G016: お好み焼き・もんじゃ
- G017: アジア・エスニック料理

【キーワード検索】
search_restaurants ツールの keyword パラメータでフリーワード検索ができます:
- 個室、飲み放題、食べ放題、デート、接待、宴会 等
- ユーザーの要望から適切なキーワードを抽出して指定してください

【予算の目安】
search_restaurants ツールの budget_max パラメータで指定できます:
ユーザーの「安い」「高い」などの表現から適切な予算上限（円）を推定してください。
- 安い: 3000円程度
- 普通: 4000-5000円程度
- 高い: 7000円以上

【例】「安い焼肉を探して」→ genre="G008", budget_max=3000

ユーザーからの質問: {user_message}
        """.strip()

        # Initialize Strands Agent with tools
        agent = Agent(system_prompt=SYSTEM_PROMPT, tools=[search_restaurants, resolve_area, check_availability])

        # Run agent (Strands Agent is called directly)
        t0 = time.time()
        response = agent(context_prompt)
        agent_duration_ms = round((time.time() - t0) * 1000)

        # Extract message from Strands Agent response (fix: ensure plain text)
        agent_message = _extract_text(response)

        _log_json("info", "agent_completed",
                  actor_id=actor_id,
                  response_length=len(agent_message),
                  agent_duration_ms=agent_duration_ms)

        # Capture structured restaurant data from last tool call
        restaurants = get_last_results()

        # ─── A2A マルチパースペクティブ処理 ───────────────────────────────
        perspective_message: Optional[str] = None
        perspective_results: Optional[Dict[str, Any]] = None

        # 深堀りモードでなく、レストランが3件以上ある場合に A2A を起動
        if WORKER_RUNTIME_ARN and restaurants and not drill_down and len(restaurants) >= 3:
            _log_json("info", "a2a_start",
                      actor_id=actor_id, restaurant_count=len(restaurants))
            t0 = time.time()
            try:
                # レストランを Worker に渡せる形式にシリアライズ
                restaurants_for_worker = [
                    {
                        "name": r.get("name", ""),
                        "rating": r.get("rating", 0),
                        "review_count": r.get("user_ratings_total", 0),
                        "budget": r.get("budget", ""),
                        "genre": r.get("genre", "居酒屋"),
                        "catch": r.get("catch", ""),
                        "access": r.get("access", ""),
                        "features": r.get("features", {}),
                    }
                    for r in restaurants
                ]

                perspective_results = _call_perspectives_parallel(
                    restaurants=restaurants_for_worker,
                    user_context=user_message,
                    session_id=session_id,
                )
                success_count = sum(1 for r in perspective_results.values() if r.get("picks"))
                if success_count == 0:
                    perspective_message = None
                else:
                    perspective_message = _format_multi_perspective(perspective_results)

                _log_json("info", "a2a_complete",
                          actor_id=actor_id,
                          duration_ms=round((time.time() - t0) * 1000))

            except Exception as e:
                _log_json("warning", "a2a_fallback",
                          actor_id=actor_id, error=str(e))
                # フォールバック: v1 の単一エージェントレスポンスをそのまま使う
                perspective_message = None
                perspective_results = None

        # 最終レスポンス: A2A 結果があれば統合、なければ v1 レスポンス
        final_message = (
            f"{agent_message}\n\n{perspective_message}"
            if perspective_message
            else agent_message
        )

        # Save conversation to Memory (triggers LTM extraction)
        t0 = time.time()
        save_ok = save_conversation(
            actor_id=actor_id,
            session_id=session_id,
            user_message=user_message,
            agent_response=final_message,
        )
        _log_json("info", "memory_saved",
                  actor_id=actor_id, success=save_ok,
                  duration_ms=round((time.time() - t0) * 1000))

        result: Dict[str, Any] = {"result": final_message, "session_id": session_id}
        if restaurants:
            # Serialize for JSON transport (remove internal fields)
            result["restaurants"] = [
                {
                    "name": r.get("name", ""),
                    "rating": r.get("rating", 0),
                    "review_count": r.get("user_ratings_total", 0),
                    "score": r.get("score", 0),
                    "budget": r.get("budget", ""),
                    "genre": r.get("genre", "居酒屋"),
                    "address": r.get("address", ""),
                    "phone": r.get("phone", ""),
                    "url": r.get("url", ""),
                    "google_maps_url": r.get("google_maps_url", ""),
                    "photo_url": r.get("photo_url", ""),
                    "open_now": r.get("open_now"),
                    "features": r.get("features", {}),
                    "catch": r.get("catch", ""),
                    "access": r.get("access", ""),
                }
                for r in restaurants
            ]
        if perspective_results:
            result["perspectives"] = perspective_results

        total_ms = round((time.time() - t_start) * 1000)
        _log_json("info", "invoke_complete",
                  actor_id=actor_id, total_ms=total_ms,
                  restaurant_count=len(restaurants),
                  has_perspectives=perspective_results is not None)

        return result

    except Exception as e:
        total_ms = round((time.time() - t_start) * 1000)
        _log_json("error", "invoke_error",
                  error_type=type(e).__name__,
                  error_message=str(e),
                  total_ms=total_ms)
        return {"error": "エージェント処理中にエラーが発生しました。しばらくしてからお試しください。"}


def format_conversation_history(turns: List[Dict[str, Any]]) -> str:
    """
    Format conversation history for agent instructions

    Args:
        turns: List of conversation turns from Memory API

    Returns:
        Formatted conversation history string
    """
    if not turns:
        return "（初回の会話です）"

    formatted = []
    for turn in turns[-5:]:  # Last 5 turns
        if isinstance(turn, str):
            formatted.append(f"会話: {turn}")
            continue

        if not isinstance(turn, dict):
            content = _stringify_content(turn)
            if content:
                formatted.append(f"会話: {content}")
            continue

        # New Memory API structure: turn has 'messages' array
        messages = turn.get("messages", [])
        if isinstance(messages, list) and messages:
            for msg in messages:
                if isinstance(msg, dict):
                    role = str(msg.get("role", "unknown")).upper()
                    content = _stringify_content(msg.get("content", ""))
                    if not content:
                        continue
                    if role == "USER":
                        formatted.append(f"ユーザー: {content}")
                    elif role == "ASSISTANT":
                        formatted.append(f"エージェント: {content}")
                    else:
                        formatted.append(content)
                else:
                    content = _stringify_content(msg)
                    if content:
                        formatted.append(content)
            continue

        # Legacy/unknown shape fallback
        role = str(turn.get("role", "unknown")).upper()
        content = _stringify_content(
            turn.get("content") or turn.get("message") or turn.get("text")
        )
        if not content:
            continue
        if role == "USER":
            formatted.append(f"ユーザー: {content}")
        elif role == "ASSISTANT":
            formatted.append(f"エージェント: {content}")
        else:
            formatted.append(content)

    return "\n".join(formatted) if formatted else "（初回の会話です）"


def format_user_preferences(preferences: List[Dict[str, Any]]) -> str:
    """
    Format user preferences for agent instructions

    Args:
        preferences: List of user preference records

    Returns:
        Formatted user preferences string
    """
    if not preferences:
        return "（好みは未登録です）"

    formatted = []
    for pref in preferences:
        if isinstance(pref, dict):
            content = _stringify_content(
                pref.get("content")
                or pref.get("text")
                or pref.get("memory")
                or pref.get("summary")
                or pref.get("value")
            )
            if not content:
                content = _stringify_content(pref.get("messages"))
        else:
            content = _stringify_content(pref)

        if content:
            formatted.append(f"- {content}")

    return "\n".join(formatted) if formatted else "（好みは未登録です）"


if __name__ == "__main__":
    # Run the app locally for testing
    app.run()
