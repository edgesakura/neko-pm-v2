#!/usr/bin/env python3
"""
trigger-alert.py - SRE Agent アラートトリガー CLI

ローカルテスト用: mock/alerts/ の JSON を Orchestrator に送信して動作確認する。

使用例:
  python scripts/trigger-alert.py --scenario api_5xx_spike
  python scripts/trigger-alert.py --scenario pod_crashloop --local
  python scripts/trigger-alert.py --scenario high_latency --agent-arn arn:aws:bedrock-agentcore:...
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# プロジェクトルートを PYTHONPATH に追加
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SCENARIO_FILES = {
    "api_5xx_spike": "mock/alerts/api_5xx_spike.json",
    "pod_crashloop": "mock/alerts/pod_crashloop.json",
    "high_latency": "mock/alerts/high_latency.json",
}


def load_alert(scenario: str) -> dict:
    """mock/alerts/ からアラート JSON を読み込む"""
    if scenario not in SCENARIO_FILES:
        print(f"Error: Unknown scenario '{scenario}'")
        print(f"Available: {', '.join(SCENARIO_FILES.keys())}")
        sys.exit(1)

    alert_file = PROJECT_ROOT / SCENARIO_FILES[scenario]
    if not alert_file.exists():
        print(f"Error: Alert file not found: {alert_file}")
        sys.exit(1)

    with open(alert_file) as f:
        return json.load(f)


def run_local(alert: dict) -> None:
    """ローカルモード: Orchestrator を直接 import して実行"""
    try:
        from agents.orchestrator.main import handle_alert
        print("\n=== Local Mode: Direct Orchestrator Call ===")
        t0 = time.time()
        result = handle_alert(alert)
        elapsed = round((time.time() - t0) * 1000)
        print(f"\n=== Result (elapsed: {elapsed}ms) ===")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except ImportError as e:
        print(f"Error: Could not import orchestrator: {e}")
        print("Hint: Run from project root or ensure agents/orchestrator/ exists")
        sys.exit(1)


def run_remote(alert: dict, agent_arn: str, session_id: str, region: str) -> None:
    """リモートモード: AgentCore Runtime に送信"""
    from common.a2a_client import invoke_agent_runtime

    print(f"\n=== Remote Mode: AgentCore Runtime ===")
    print(f"Agent ARN: {agent_arn}")
    print(f"Session ID: {session_id}")

    payload = {
        "alert": alert,
        "session_id": session_id,
    }

    t0 = time.time()
    result = invoke_agent_runtime(
        agent_arn=agent_arn,
        payload=payload,
        session_id=session_id,
        region=region,
    )
    elapsed = round((time.time() - t0) * 1000)

    print(f"\n=== Result (elapsed: {elapsed}ms) ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="SRE Agent アラートトリガー CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIO_FILES.keys()),
        required=True,
        help="テストシナリオを選択",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        default=False,
        help="ローカルモード: AgentCore を呼ばずに直接実行",
    )
    parser.add_argument(
        "--agent-arn",
        default=os.environ.get("ORCHESTRATOR_AGENT_ARN", ""),
        help="Orchestrator Agent ARN (env: ORCHESTRATOR_AGENT_ARN)",
    )
    parser.add_argument(
        "--session-id",
        default=f"test-session-{int(time.time())}",
        help="セッション ID（デフォルト: タイムスタンプ）",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-west-2"),
        help="AWS リージョン（デフォルト: us-west-2）",
    )
    args = parser.parse_args()

    # アラート読み込み
    alert = load_alert(args.scenario)
    print(f"\n=== Alert Loaded: {args.scenario} ===")
    print(json.dumps(alert, ensure_ascii=False, indent=2))

    # 実行モード選択
    if args.local:
        run_local(alert)
    elif args.agent_arn:
        run_remote(alert, args.agent_arn, args.session_id, args.region)
    else:
        # ARN 未指定の場合はローカルモードを試みる
        print("\nNo --agent-arn specified. Falling back to --local mode.")
        run_local(alert)


if __name__ == "__main__":
    main()
