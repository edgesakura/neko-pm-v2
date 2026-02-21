#!/bin/bash
# AgentCore Runtime デプロイ後の自動テスト
# agentcore invoke でツール動作確認を実施

set -e

echo "🧪 AgentCore Runtime デプロイ後テスト開始..."

# Change to agent directory (where .bedrock_agentcore.yaml exists)
cd "$(dirname "$0")/../agent" || exit 1

# Activate virtual environment
source .venv/bin/activate

# テストプロンプト
TEST_PROMPT='{"prompt": "渋谷でおすすめの居酒屋を教えて"}'

# agentcore invoke でテスト
echo "📡 agentcore invoke を実行中..."
RESPONSE=$(agentcore invoke "$TEST_PROMPT")

echo "📋 レスポンス受信:"
echo "$RESPONSE"

# レスポンスに居酒屋リストが含まれているか確認
if echo "$RESPONSE" | grep -q "居酒屋"; then
  echo ""
  echo "✅ デプロイ後テスト成功: 居酒屋リストが返された"
  exit 0
else
  echo ""
  echo "❌ デプロイ後テスト失敗: 居酒屋リストが返されなかった"
  echo "Response: $RESPONSE"
  exit 1
fi
