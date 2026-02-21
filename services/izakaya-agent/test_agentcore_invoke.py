#!/usr/bin/env python3
"""
AgentCore Runtime 直接テスト - ツール呼び出し確認
"""
import json
import boto3

RUNTIME_ARN = "arn:aws:bedrock-agentcore:ap-northeast-1:921563379197:runtime/izakaya_agent-9JGtN3Enat"
REGION = "ap-northeast-1"

def main():
    print("=" * 60)
    print("AgentCore Runtime 直接テスト")
    print("=" * 60)

    client = boto3.client('bedrock-agentcore', region_name=REGION)

    prompt = "渋谷でおすすめの居酒屋を教えて"
    print(f"\n📍 プロンプト: {prompt}")

    try:
        print("\n🔍 AgentCore Runtime 呼び出し中...")
        payload = json.dumps({"prompt": prompt})

        response = client.invoke_agent_runtime(
            agentRuntimeArn=RUNTIME_ARN,
            runtimeSessionId="test-session-001",
            payload=payload
        )

        # Read streaming response
        result_json = response['response'].read().decode('utf-8')
        response_data = json.loads(result_json)

        print("\n✅ レスポンス受信:")
        print(json.dumps(response_data, indent=2, ensure_ascii=False))

        # Extract result
        result = response_data.get("result", {})
        if isinstance(result, dict):
            content = result.get("content", [])
            if content and isinstance(content, list):
                response_text = content[0].get("text", "応答なし")
                print(f"\n💬 応答テキスト:")
                print(response_text)

        # Check if tools were used
        tool_use = response_data.get("toolUse", [])
        if tool_use:
            print(f"\n🛠️ ツール使用: {len(tool_use)}件")
            for i, tool in enumerate(tool_use, 1):
                print(f"  {i}. {tool.get('toolName', 'unknown')}")
        else:
            print("\n⚠️ ツールが使用されていません")

    except Exception as e:
        print(f"\n❌ エラー発生:")
        print(f"  - エラー型: {type(e).__name__}")
        print(f"  - エラーメッセージ: {e}")
        import traceback
        print(f"\n🔍 スタックトレース:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
