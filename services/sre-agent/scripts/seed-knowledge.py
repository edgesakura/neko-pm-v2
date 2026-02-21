#!/usr/bin/env python3
"""
seed-knowledge.py - インシデントナレッジの Memory API 投入

mock/incidents/seed.json を AgentCore Memory に投入する。
フォールバック: Memory API 未設定時はローカルファイル参照のみ確認。

使用例:
  python scripts/seed-knowledge.py
  python scripts/seed-knowledge.py --dry-run
  python scripts/seed-knowledge.py --memory-id <MEMORY_ID>
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# プロジェクトルートを PYTHONPATH に追加
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SEED_FILE = PROJECT_ROOT / "mock" / "incidents" / "seed.json"


def load_seed_data() -> list:
    """mock/incidents/seed.json を読み込む"""
    if not SEED_FILE.exists():
        logger.error("Seed file not found: %s", SEED_FILE)
        sys.exit(1)

    with open(SEED_FILE) as f:
        incidents = json.load(f)

    logger.info("Loaded %d incidents from %s", len(incidents), SEED_FILE)
    return incidents


def seed_to_memory(incidents: list, memory_id: str, region: str, dry_run: bool) -> None:
    """
    インシデントデータを AgentCore Memory に投入する。

    Args:
        incidents: インシデントリスト
        memory_id: AgentCore Memory ID
        region: AWS リージョン
        dry_run: True の場合は実際には投入しない
    """
    if dry_run:
        logger.info("=== DRY RUN MODE: No data will be written ===")
        for i, incident in enumerate(incidents, 1):
            logger.info(
                "[%d/%d] Would seed: %s (%s)",
                i, len(incidents),
                incident.get("title", "unknown"),
                incident.get("category", "UNKNOWN"),
            )
        return

    try:
        from bedrock_agentcore.memory import MemoryClient
        client = MemoryClient(region_name=region)
    except ImportError:
        logger.warning("bedrock-agentcore not installed. Using local-only mode.")
        _local_fallback(incidents)
        return
    except Exception as e:
        logger.warning("Failed to initialize Memory client: %s. Using local fallback.", e)
        _local_fallback(incidents)
        return

    success_count = 0
    fail_count = 0

    for i, incident in enumerate(incidents, 1):
        content = _format_incident_for_memory(incident)
        try:
            client.ingest_conversation_history(
                memory_id=memory_id,
                actor_id="knowledge-seed",
                session_id=f"seed-{incident['id']}",
                messages=[
                    {
                        "role": "user",
                        "content": f"Incident: {incident['title']}",
                    },
                    {
                        "role": "assistant",
                        "content": content,
                    },
                ],
            )
            success_count += 1
            logger.info(
                "[%d/%d] Seeded: %s",
                i, len(incidents), incident.get("title", "unknown"),
            )
        except Exception as e:
            fail_count += 1
            logger.warning(
                "[%d/%d] Failed to seed '%s': %s",
                i, len(incidents), incident.get("title", "unknown"), e,
            )

    logger.info(
        "Seeding complete: %d succeeded, %d failed",
        success_count, fail_count,
    )


def _format_incident_for_memory(incident: dict) -> str:
    """インシデントを Memory API 用のテキストに変換する"""
    lines = [
        f"Category: {incident.get('category', 'UNKNOWN')}",
        f"Severity: {incident.get('severity', 'unknown')}",
        f"Title: {incident.get('title', '')}",
        f"Description: {incident.get('description', '')}",
        f"Root Cause: {incident.get('root_cause', '')}",
        f"Resolution: {incident.get('resolution', '')}",
        f"Duration: {incident.get('duration_minutes', 0)} minutes",
        f"Tags: {', '.join(incident.get('tags', []))}",
    ]
    if incident.get("lessons_learned"):
        lines.append(f"Lessons Learned: {incident['lessons_learned']}")
    return "\n".join(lines)


def _local_fallback(incidents: list) -> None:
    """Memory API が使えない場合のローカルファイル確認"""
    logger.info("=== LOCAL FALLBACK: Verifying seed data structure ===")
    categories = {}
    for incident in incidents:
        cat = incident.get("category", "UNKNOWN")
        categories[cat] = categories.get(cat, 0) + 1

    for cat, count in categories.items():
        logger.info("  %s: %d incidents", cat, count)

    logger.info(
        "Local verification complete. %d incidents ready for seeding.",
        len(incidents),
    )
    logger.info(
        "To seed to Memory API, set MEMORY_ID env var and ensure AWS credentials."
    )


def main():
    parser = argparse.ArgumentParser(
        description="インシデントナレッジを AgentCore Memory に投入",
    )
    parser.add_argument(
        "--memory-id",
        default=os.environ.get("MEMORY_ID", ""),
        help="AgentCore Memory ID (env: MEMORY_ID)",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-west-2"),
        help="AWS リージョン",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="実際には投入せず、内容を確認のみ",
    )
    args = parser.parse_args()

    incidents = load_seed_data()

    if not args.memory_id and not args.dry_run:
        logger.warning("MEMORY_ID not set. Running in local-only mode.")
        logger.warning("Set --memory-id or MEMORY_ID env var to seed to Memory API.")
        _local_fallback(incidents)
        return

    seed_to_memory(incidents, args.memory_id, args.region, args.dry_run)


if __name__ == "__main__":
    main()
