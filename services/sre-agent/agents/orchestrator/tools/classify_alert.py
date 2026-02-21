"""
classify_alert ツール - アラート分類

アラート JSON を受け取り、カテゴリと重要度を判定する。
Orchestrator の唯一のローカルツール（コンテキスト最小化のため）。
"""
import json
import logging
from typing import Dict

from strands import tool

from common.models import AlertCategory, AlertSeverity

logger = logging.getLogger(__name__)


@tool
def classify_alert(alert_json: str) -> Dict:
    """
    Classify an incoming alert into category and severity.

    Parses the alert JSON and determines the appropriate response category
    to enable focused tool selection via the Gateway Interceptor.

    Categories:
      - API_5XX_SPIKE: API error rate exceeds threshold
      - POD_CRASHLOOP: Kubernetes pod restart loop
      - HIGH_LATENCY: P95/P99 latency exceeds SLO
      - UNKNOWN: Unrecognized alert type

    Args:
        alert_json: JSON string containing alert data with fields:
          - title (str): Alert title
          - description (str): Alert description
          - severity (str): Alert severity (critical/high/medium/low)
          - category (str, optional): Pre-classified category

    Returns:
        dict with keys:
          - category (str): Alert category name
          - severity (str): Alert severity name
          - confidence (str): Classification confidence (high/medium/low)
          - reasoning (str): Brief explanation of classification
    """
    try:
        alert = json.loads(alert_json) if isinstance(alert_json, str) else alert_json
    except json.JSONDecodeError as e:
        logger.error("Failed to parse alert JSON: %s", e)
        return {
            "category": AlertCategory.UNKNOWN.value,
            "severity": AlertSeverity.MEDIUM.value,
            "confidence": "low",
            "reasoning": f"JSON parse error: {e}",
        }

    # 明示的なカテゴリが設定されている場合は優先
    explicit_category = alert.get("category", "")
    if explicit_category in [c.value for c in AlertCategory]:
        severity = _classify_severity(alert)
        return {
            "category": explicit_category,
            "severity": severity.value,
            "confidence": "high",
            "reasoning": f"Explicit category from alert: {explicit_category}",
        }

    # タイトル + 説明文からキーワードマッチで分類
    title = alert.get("title", "").lower()
    description = alert.get("description", "").lower()
    combined = f"{title} {description}"

    category, confidence, reasoning = _keyword_classify(combined)
    severity = _classify_severity(alert)

    logger.info(
        "Alert classified: category=%s, severity=%s, confidence=%s",
        category.value, severity.value, confidence,
    )

    return {
        "category": category.value,
        "severity": severity.value,
        "confidence": confidence,
        "reasoning": reasoning,
    }


def _keyword_classify(text: str):
    """キーワードマッチでアラートカテゴリを分類する"""
    # API 5xx スパイク
    if any(kw in text for kw in ["5xx", "error rate", "http 5", "502", "503", "504"]):
        return (
            AlertCategory.API_5XX_SPIKE,
            "high",
            "Detected 5xx error rate keywords",
        )

    # Pod CrashLoop
    if any(kw in text for kw in ["crashloop", "crashloopbackoff", "oomkill", "oom", "restart loop"]):
        return (
            AlertCategory.POD_CRASHLOOP,
            "high",
            "Detected pod crash/restart keywords",
        )

    # 高レイテンシ
    if any(kw in text for kw in ["latency", "p95", "p99", "slow", "timeout", "response time"]):
        return (
            AlertCategory.HIGH_LATENCY,
            "high",
            "Detected latency/timeout keywords",
        )

    return (
        AlertCategory.UNKNOWN,
        "low",
        "No matching keywords found",
    )


def _classify_severity(alert: dict) -> AlertSeverity:
    """アラートの重要度を判定する"""
    severity_str = alert.get("severity", "medium").lower()
    try:
        return AlertSeverity(severity_str)
    except ValueError:
        return AlertSeverity.MEDIUM
