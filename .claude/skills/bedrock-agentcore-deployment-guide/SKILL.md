# bedrock-agentcore-deployment-guide

Amazon Bedrock AgentCore エージェントのデプロイ手順テンプレート。Phase 4で作成した完全手順をスキル化したにゃ。

## 使用タイミング
- AgentCore プロジェクトをデプロイする時
- Lambda + AgentCore Runtime を統合する時
- LINE Bot と AgentCore を連携する時

## 前提条件

- AWS CLI 設定済み
- Node.js 18+ インストール済み
- Python 3.11+ インストール済み
- AWS CDK CLI インストール済み

## デプロイ手順（全10ステップ）

### ステップ1: Lambda Layer 作成

```bash
cd output/{project-name}
mkdir -p lambda-layer/python
pip install -r lambda/requirements.txt -t lambda-layer/python
```

**重要**: Lambda Layer は手動で作成する必要がある

### ステップ2: AgentCore CLI インストール

```bash
pip install bedrock-agentcore-starter-toolkit
```

### ステップ3: Memory リソース作成

```bash
cd agent
agentcore memory create {ProjectName}Memory \
  --strategies '[{"semanticMemoryStrategy": {"name": "UserPreferences"}}]' \
  --region ap-northeast-1 \
  --wait
```

### ステップ4: エージェント設定

```bash
agentcore configure \
  --entrypoint main.py \
  --name {project-name} \
  --runtime PYTHON_3_11 \
  --region ap-northeast-1 \
  --non-interactive
```

### ステップ5: エージェントデプロイ

```bash
agentcore launch
```

### ステップ6: エージェントID取得

```bash
agentcore status
# AGENT_ID と AGENT_ALIAS_ID をメモ
```

### ステップ7: CDKスタックデプロイ

```bash
cd ../infra
export AGENT_ID="<取得したAGENT_ID>"
export AGENT_ALIAS_ID="<取得したAGENT_ALIAS_ID>"
npm install
npx cdk deploy
```

### ステップ8: Lambda Function URL 取得

CDKデプロイ後、Outputs から Function URL をメモ：
```
{ProjectName}Stack.LineWebhookFunctionUrl = https://xxxxx.lambda-url.ap-northeast-1.on.aws/
```

### ステップ9: LINE Developers で Webhook URL 設定

1. LINE Developers Console にログイン
2. チャネルを選択
3. Messaging API 設定 > Webhook URL に Lambda Function URL を設定
4. 「Webhookの利用」をONにする
5. 「検証」をクリックして疎通確認

### ステップ10: 動作テスト

1. LINE公式アカウントを友だち追加
2. メッセージを送信
3. CloudWatch Logs で動作確認
   ```bash
   aws logs tail /aws/lambda/{ProjectName}Stack-LineWebhookFunction --follow
   ```

## CDKスタック例

```typescript
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as path from 'path';

// Lambda Layer for Python dependencies
const pythonDepsLayer = new lambda.LayerVersion(this, 'PythonDepsLayer', {
  code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda-layer')),
  compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
  description: 'Python dependencies (line-bot-sdk, boto3)',
});

// Lambda Function
const webhookFunction = new lambda.Function(this, 'LineWebhookFunction', {
  runtime: lambda.Runtime.PYTHON_3_11,
  handler: 'handler.lambda_handler',
  code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda')),
  timeout: Duration.seconds(60),
  role: lambdaRole,
  layers: [pythonDepsLayer],
  environment: {
    AGENT_ID: process.env.AGENT_ID || 'PLACEHOLDER_AGENT_ID',
    AGENT_ALIAS_ID: process.env.AGENT_ALIAS_ID || 'PLACEHOLDER_AGENT_ALIAS_ID',
  },
  description: 'LINE Webhook to Bedrock AgentCore',
});
```

## トラブルシューティング

### Lambda タイムアウト
- CloudWatch Logs で実行時間を確認
- AgentCore の応答が遅い場合は timeout を延長

### LINE署名検証エラー
- Secrets Manager に正しいチャネルシークレットが登録されているか確認
- `X-Line-Signature` ヘッダーが正しく渡されているか確認

### AgentCore Runtime エラー
- AGENT_ID, AGENT_ALIAS_ID が正しく設定されているか確認
- AgentCore のステータスを確認: `agentcore status`
- Memory リソースが作成されているか確認

### Memory機能が動作しない
- Memory リソースが作成されているか確認
- session_id（LINE user_id）が正しく渡されているか確認
- CloudWatch Logs でMemory関連エラーを確認

## チェックリスト

- [ ] Lambda Layer 作成完了
- [ ] AgentCore CLI インストール完了
- [ ] Memory リソース作成完了
- [ ] agentcore configure 実行完了
- [ ] agentcore launch 実行完了
- [ ] AGENT_ID, AGENT_ALIAS_ID 取得完了
- [ ] CDKスタックデプロイ完了
- [ ] Lambda Function URL 取得完了
- [ ] LINE Webhook URL 設定完了
- [ ] 動作テスト成功
