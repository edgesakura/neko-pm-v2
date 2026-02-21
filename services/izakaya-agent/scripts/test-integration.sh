#!/bin/bash
# Lambda 統合テスト
# Lambda 直接 invoke でE2Eテストを実施

set -e

echo "🧪 Lambda 統合テスト開始..."

# Lambda関数名を取得
echo "📡 Lambda 関数名を取得中..."
FUNCTION_NAME=$(aws cloudformation describe-stack-resources \
  --stack-name IzakayaAgentStack \
  --region ap-northeast-1 \
  --query "StackResources[?ResourceType=='AWS::Lambda::Function'].PhysicalResourceId" \
  --output text)

echo "📡 Lambda 関数: $FUNCTION_NAME"

# テストペイロード作成（LINE webhook形式）
# Note: LINE署名検証があるため、Invalid signatureエラーは正常
cat > /tmp/lambda-test-payload.json << 'EOF'
{
  "headers": {
    "x-line-signature": "test-signature"
  },
  "body": "{\"events\":[{\"type\":\"message\",\"message\":{\"type\":\"text\",\"text\":\"test\"},\"source\":{\"userId\":\"test-user-123\"},\"replyToken\":\"test-token-456\"}]}"
}
EOF

# Lambda invoke
echo "📡 Lambda invoke を実行中..."
aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --cli-binary-format raw-in-base64-out \
  --payload file:///tmp/lambda-test-payload.json \
  --region ap-northeast-1 \
  --log-type Tail \
  /tmp/lambda-response.json > /tmp/lambda-invoke-log.json

# レスポンス確認
echo "📋 レスポンス受信:"
cat /tmp/lambda-response.json
echo ""

# ステータスコード確認
# Lambda Function URL 経由の場合は statusCode が含まれる
# 直接invokeの場合は errorMessage の有無で判定
if grep -q "errorMessage" /tmp/lambda-response.json; then
  echo "❌ Lambda 統合テスト失敗: エラーが発生"
  cat /tmp/lambda-response.json
  exit 1
elif grep -q "Invalid signature" /tmp/lambda-response.json; then
  echo "✅ Lambda 統合テスト成功: Lambda が正常起動（署名検証まで到達）"
  echo "   Note: Invalid signature は正常（テスト用署名のため）"
  exit 0
else
  echo "✅ Lambda 統合テスト成功: Lambda が正常応答"
  exit 0
fi
