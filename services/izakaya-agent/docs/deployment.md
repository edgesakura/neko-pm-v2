# AgentCore Runtime デプロイ手順

このドキュメントでは、LINE Bot「イザカヤくん」（AgentCore Runtime使用）のデプロイ手順を説明します。今回の開発で発覚した7つのハマりポイントを全て記載し、同じ問題を繰り返さないようにします。

## 概要

### デプロイの全体フロー

```
┌─────────────────────────────────────────────────────┐
│ 1. 依存パッケージのインストール                      │
│    └─ Python venv作成、requirements.txtインストール  │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ 2. Lambda Layerのビルド                              │
│    └─ manylinux wheel でバイナリ互換性を確保         │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ 3. CDK デプロイ（Lambda + Layer）                    │
│    └─ AWS CloudFormationスタック作成/更新            │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ 4. AgentCore Runtime デプロイ                        │
│    └─ エージェントコードをRuntimeにアップロード      │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ 5. IAM権限の確認・追加                               │
│    ├─ Lambda → AgentCore Runtime                    │
│    └─ AgentCore Runtime → Secrets Manager           │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ 6. 動作確認                                          │
│    ├─ agentcore invoke でツール動作確認             │
│    └─ LINE Bot 実機テスト                           │
└─────────────────────────────────────────────────────┘
```

### 必要な権限

デプロイを実行するユーザー/ロールには、以下のIAM権限が必要です：

| サービス | 必要な権限 | 用途 |
|---------|-----------|------|
| Lambda | `lambda:CreateFunction`, `lambda:UpdateFunctionCode`, `lambda:UpdateFunctionConfiguration` | Lambda関数の作成・更新 |
| IAM | `iam:CreateRole`, `iam:PutRolePolicy`, `iam:PassRole` | 実行ロールの作成 |
| CloudFormation | `cloudformation:CreateStack`, `cloudformation:UpdateStack` | CDKデプロイ |
| Bedrock AgentCore | `bedrock-agentcore:CreateAgentRuntime`, `bedrock-agentcore:UpdateAgentRuntime` | Runtimeのデプロイ |
| Secrets Manager | `secretsmanager:GetSecretValue` | シークレット取得（動作確認用） |

## 前提条件チェックリスト

デプロイを開始する前に、以下の項目をすべて確認してください：

- [ ] **AWS CLI設定済み**
  ```bash
  aws sts get-caller-identity  # 認証情報の確認
  ```

- [ ] **IAM権限確認**
  - Lambda、AgentCore、Secrets Managerへのアクセス権限
  - CloudFormationスタックの作成権限

- [ ] **Secrets ManagerにAPIキー設定済み**
  ```bash
  # 4つのシークレットが存在することを確認
  aws secretsmanager list-secrets \
    --region ap-northeast-1 \
    --query 'SecretList[?contains(Name, `izakaya-agent`)].Name'
  ```
  詳細は [secrets-setup.md](./secrets-setup.md) を参照してください。

- [ ] **Python 3.11環境**
  ```bash
  python3 --version  # Python 3.11.x であること
  ```

- [ ] **Node.js 18以上（CDK用）**
  ```bash
  node --version  # v18.x 以上であること
  npm --version
  ```

- [ ] **AgentCore CLI インストール済み**
  ```bash
  agentcore --version
  ```

## デプロイ手順（ステップバイステップ）

### Step 1: 依存パッケージのインストール

エージェント開発用の依存パッケージをインストールします。

```bash
# プロジェクトルートに移動
cd output/izakaya-agent

# agent/ ディレクトリに移動
cd agent

# Python仮想環境を作成
python3 -m venv .venv

# 仮想環境を有効化
source .venv/bin/activate

# 依存パッケージをインストール
pip install -r requirements.txt
```

**確認**:
```bash
# strands-agents がインストールされているか確認
pip list | grep strands-agents
# 出力例: strands-agents 1.25.0
```

### Step 2: Lambda Layer のビルド（manylinux wheel）

Lambda Layer用の依存パッケージを、Amazon Linux 2023と互換性のある形でビルドします。

**⚠️ 重要**: Ubuntu/WSLで直接 `pip install` すると、Amazon Linux 2023と互換性がないバイナリがビルドされます。必ず `--platform manylinux2014_x86_64` を指定してください。

```bash
# プロジェクトルートに戻る
cd ..

# Lambda Layerディレクトリを削除（既存の場合）
rm -rf lambda-layer/python

# manylinux wheel でLambda Layerをビルド
pip install --platform manylinux2014_x86_64 --python-version 3.11 \
  --only-binary=:all: --target lambda-layer/python \
  -r lambda/requirements.txt
```

**重要なオプション**:
- `--platform manylinux2014_x86_64`: Amazon Linux 2023互換のバイナリを取得
- `--python-version 3.11`: Lambda実行環境のPythonバージョンに合わせる
- `--only-binary=:all:`: ソースからビルドせず、ビルド済みwheelのみ使用
- `--target lambda-layer/python`: Lambda Layerの標準ディレクトリ構造

**確認**:
```bash
# pydantic_core（バイナリパッケージ）が正しくインストールされているか確認
ls -la lambda-layer/python/pydantic_core/_pydantic_core.*.so
# .so ファイルが存在すればOK
```

### Step 3: CDK デプロイ（Lambda + Layer）

AWS CDKを使って、Lambda関数とLayerをデプロイします。

```bash
# infra/ ディレクトリに移動
cd infra

# Node.js依存パッケージをインストール（初回のみ）
npm install

# CDKをブートストラップ（初回のみ）
# npx cdk bootstrap

# CDKデプロイ
npx cdk deploy --require-approval never
```

**デプロイ内容**:
- Lambda関数: `IzakayaAgentFunction`
- Lambda Layer: `PythonDepsLayer` (strands-agents, pydantic等を含む)
- IAM実行ロール: Lambda → AgentCore Runtime の呼び出し権限

**確認**:
```bash
# Lambda関数がデプロイされたか確認
aws lambda get-function \
  --function-name IzakayaAgentFunction \
  --region ap-northeast-1 \
  --query 'Configuration.FunctionName'

# Lambda Layerのバージョンを確認
aws lambda list-layer-versions \
  --layer-name IzakayaStack-PythonDepsLayer \
  --region ap-northeast-1 \
  --query 'LayerVersions[0].Version'
```

### Step 4: AgentCore Runtime デプロイ

エージェントコード（`agent/main.py`, `agent/tools/*.py`）をAgentCore Runtimeにデプロイします。

**⚠️ 重要**: エージェントコードを変更したら、必ず `agentcore deploy` を実行してください。CDKデプロイだけではAgentCore Runtimeに反映されません。

```bash
# agent/ ディレクトリに移動
cd ../agent

# 仮想環境を有効化（未有効化の場合）
source .venv/bin/activate

# AgentCore Runtimeにデプロイ
agentcore deploy
```

**デプロイ内容**:
- エージェントコード（`main.py`, `tools/`）
- 依存パッケージ（`requirements.txt`）
- 設定ファイル（`.bedrock_agentcore.yaml`）

**確認**:
```bash
# デプロイされたAgentCore Runtimeの情報を確認
agentcore describe

# 出力例:
# Agent ARN: arn:aws:bedrock-agentcore:ap-northeast-1:XXXX:runtime/izakaya_agent-9JGtN3Enat
# Memory ID: izakaya_agent_mem-ZOMh0R8tfz
# Deployment Type: direct_code_deploy
```

### Step 5: IAM権限の確認・追加

Lambda関数とAgentCore Runtimeが必要なリソースにアクセスできるよう、IAM権限を設定します。

#### 5.1 Lambda IAM権限

Lambda関数がAgentCore Runtimeを呼び出すために必要な権限：

**必要なアクション**: `bedrock-agentcore:InvokeAgentRuntime`（`InvokeRuntime` ではない！）

**CDKでの設定**:

`infra/lib/izakaya-stack.ts` の53行目付近で、以下のように設定されているか確認：

```typescript
lambdaFunction.addToRolePolicy(new iam.PolicyStatement({
  actions: ['bedrock-agentcore:InvokeAgentRuntime'],  // ← InvokeAgentRuntime
  resources: [process.env.AGENT_RUNTIME_ARN || '*']
}));
```

**誤った設定例**（動作しない）:
```typescript
// ❌ 間違い: InvokeRuntime では403エラーになる
actions: ['bedrock-agentcore:InvokeRuntime']
```

#### 5.2 AgentCore Runtime IAM権限

AgentCore RuntimeがSecrets ManagerからAPIキーを取得するために必要な権限：

**必要なアクション**: `secretsmanager:GetSecretValue`

**権限の追加手順**:

1. **IAMポリシーJSONを作成**

```bash
cat > /tmp/agentcore-secrets-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "IzakayaAgentSecretsAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:ap-northeast-1:*:secret:izakaya-agent/*"
      ]
    }
  ]
}
EOF
```

2. **AgentCore RuntimeのIAMロール名を確認**

```bash
# AgentCore RuntimeのARNを確認
agentcore describe --query runtime_arn

# IAMロール一覧からAgentCore Runtime用のロールを検索
aws iam list-roles \
  --query 'Roles[?contains(RoleName, `AmazonBedrockAgentCoreSDKRuntime`)].RoleName'

# 出力例:
# AmazonBedrockAgentCoreSDKRuntime-ap-northeast-1-1fcb41dc28
```

3. **IAMロールにインラインポリシーを追加**

```bash
# ロール名を変数に格納（上記で確認したロール名を使用）
ROLE_NAME="AmazonBedrockAgentCoreSDKRuntime-ap-northeast-1-XXXXXXXX"

# インラインポリシーを追加
aws iam put-role-policy \
  --role-name $ROLE_NAME \
  --policy-name IzakayaAgentSecretsAccess \
  --policy-document file:///tmp/agentcore-secrets-policy.json
```

**確認**:
```bash
# ポリシーが追加されたか確認
aws iam get-role-policy \
  --role-name $ROLE_NAME \
  --policy-name IzakayaAgentSecretsAccess
```

### Step 6: 動作確認

#### 6.1 AgentCore invoke でツール動作確認

AgentCore CLIを使って、エージェントが正常に動作するか確認します。

```bash
# agent/ ディレクトリで実行
cd agent
source .venv/bin/activate

# テストプロンプトでツール動作を確認
agentcore invoke '{"prompt": "渋谷でおすすめの居酒屋を教えて"}'
```

**期待される出力**:
```json
{
  "response": "渋谷エリアでおすすめの居酒屋をご紹介いたします！\n\n## 🍻 渋谷のおすすめ居酒屋トップ10\n\n1. **TOMBOY INDIAN LOUNGE DINING** ⭐4.7 (2,361件)\n...",
  "tool_calls": [
    {
      "tool": "search_restaurants",
      "input": {"query": "渋谷 居酒屋", "location": "渋谷"}
    }
  ]
}
```

✅ 居酒屋リスト（星評価・レビュー数付き）が返ってくれば成功です。

#### 6.2 Lambda 直接invokeでテスト（オプション）

Lambda関数を直接呼び出して、AgentCore Runtimeとの連携を確認します。

```bash
# テストペイロード（LINE Webhook形式）を作成
cat > /tmp/test-payload.json <<EOF
{
  "events": [
    {
      "type": "message",
      "message": {
        "type": "text",
        "text": "渋谷でおすすめの居酒屋を教えて"
      },
      "replyToken": "test-reply-token"
    }
  ]
}
EOF

# Lambda関数を直接invoke
aws lambda invoke \
  --function-name IzakayaAgentFunction \
  --region ap-northeast-1 \
  --payload file:///tmp/test-payload.json \
  /tmp/lambda-response.json

# レスポンスを確認
cat /tmp/lambda-response.json
```

#### 6.3 LINE Bot 実機テスト

LINE Developersコンソールで、実際のLINEメッセージを送信してテストします。

1. LINEアプリで、Botをトークに追加
2. 「渋谷でおすすめの居酒屋を教えて」とメッセージを送信
3. Botから居酒屋リスト（星評価・レビュー数付き）が返ってくることを確認

**確認**:
```bash
# CloudWatch Logsで実行ログを確認
aws logs tail /aws/lambda/IzakayaAgentFunction \
  --region ap-northeast-1 \
  --follow
```

## ハマりポイント7つ（今回の教訓）

今回の開発で遭遇した7つのハマりポイントと、その対策を記載します。

### 1. Lambda Layer のバイナリ互換性問題

**問題**: Ubuntu/WSLでビルドしたLambda Layerが、Amazon Linux 2023で動作しない

**症状**:
```
Runtime.ImportModuleError: Unable to import module 'handler': No module named 'pydantic_core._pydantic_core'
```

**根本原因**:
- `pydantic_core` 等のバイナリパッケージが、Ubuntu/WSL環境でビルドされていた
- Amazon Linux 2023とのバイナリ互換性がなかった

**対策**:
```bash
# ❌ 間違い: ローカル環境で直接インストール
pip install -t lambda-layer/python -r lambda/requirements.txt

# ✅ 正解: manylinux wheel を使用
pip install --platform manylinux2014_x86_64 --python-version 3.11 \
  --only-binary=:all: --target lambda-layer/python -r lambda/requirements.txt
```

**教訓**: Lambda Layerは必ず manylinux wheel でビルドせよ

---

### 2. Lambda → AgentCore の 403 Forbidden

**問題**: Lambda関数からAgentCore Runtimeを呼び出すと、403 Forbiddenエラーが発生

**症状**:
```
AgentCore Runtime HTTP error: 403 Client Error: Forbidden for url: https://bedrock-agentcore.ap-northeast-1.amazonaws.com/...
```

**根本原因**:
- 手動でHTTP POSTリクエスト + SigV4署名を実装していた
- 署名の実装が誤っていた

**対策**:
```python
# ❌ 間違い: 手動のHTTP POST + SigV4
import requests
from botocore.auth import SigV4Auth
response = requests.post(url, data=payload, auth=SigV4Auth(...))

# ✅ 正解: boto3 クライアントを使用
import boto3
client = boto3.client('bedrock-agentcore', region_name='ap-northeast-1')
response = client.invoke_agent_runtime(
    agentRuntimeArn=runtime_arn,
    payload={'prompt': prompt}
)
```

**教訓**: AgentCore Runtime呼び出しには boto3 クライアントを使え

---

### 3. Lambda Layer に strands-agents なし

**問題**: Lambda Layerにエージェント用パッケージ（strands-agents）がインストールされていない

**症状**:
```
ModuleNotFoundError: No module named 'strands'
```

**根本原因**:
- `lambda/requirements.txt` に `strands-agents` が記載されていなかった
- `agent/requirements.txt` には記載があったが、Lambda Layerは `lambda/requirements.txt` からビルドされる

**対策**:
```bash
# lambda/requirements.txt に追加
echo "strands-agents>=0.1.0" >> lambda/requirements.txt
echo "bedrock-agentcore-starter-toolkit>=0.1.0" >> lambda/requirements.txt

# Lambda Layerを再ビルド
pip install --platform manylinux2014_x86_64 --python-version 3.11 \
  --only-binary=:all: --target lambda-layer/python -r lambda/requirements.txt

# CDK再デプロイ
cd infra && npx cdk deploy --require-approval never
```

**教訓**: Lambda と AgentCore の requirements.txt を統合すべき

---

### 4. Lambda IAM 権限のアクション名誤り

**問題**: Lambda IAM権限で `InvokeRuntime` を指定していたが、正しくは `InvokeAgentRuntime`

**症状**:
```
AccessDeniedException: User is not authorized to perform: bedrock-agentcore:InvokeAgentRuntime
```

**根本原因**:
- IAMポリシーで `bedrock-agentcore:InvokeRuntime` を指定していた
- 正しいアクション名は `bedrock-agentcore:InvokeAgentRuntime`（ドキュメント不足）

**対策**:
```typescript
// infra/lib/izakaya-stack.ts
lambdaFunction.addToRolePolicy(new iam.PolicyStatement({
  actions: ['bedrock-agentcore:InvokeAgentRuntime'],  // ← AgentRuntimeを追加
  resources: [process.env.AGENT_RUNTIME_ARN || '*']
}));
```

**教訓**: IAMアクション名は公式ドキュメントで確認せよ

---

### 5. AgentCore Runtime 未デプロイ

**問題**: エージェントコードを修正したが、AgentCore Runtimeにデプロイしていなかった

**症状**:
- `agentcore invoke` では古いコードが実行される
- ツールが正常に動作しない

**根本原因**:
- `.bedrock_agentcore.yaml` で `deployment_type: direct_code_deploy` を指定している場合、`agentcore deploy` を実行しないと反映されない
- CDKデプロイだけではAgentCore Runtimeには反映されない

**対策**:
```bash
# エージェントコードを変更したら必ず実行
cd agent
source .venv/bin/activate
agentcore deploy
```

**教訓**: エージェントコード変更時は必ず `agentcore deploy` を実行せよ

---

### 6. AgentCore IAM に Secrets Manager 権限なし

**問題**: AgentCore RuntimeのIAMロールに、Secrets Managerへのアクセス権限がなかった

**症状**:
- ツール内で `boto3.client('secretsmanager').get_secret_value()` を呼ぶと、`AccessDeniedException` が発生
- API呼び出しが失敗

**根本原因**:
- AgentCore RuntimeのIAMロールには、デフォルトで `bedrock-agentcore-identity!default/*` への権限のみ
- `izakaya-agent/*` への `secretsmanager:GetSecretValue` 権限がなかった

**対策**:
```bash
# IAMポリシーを追加
aws iam put-role-policy \
  --role-name AmazonBedrockAgentCoreSDKRuntime-ap-northeast-1-XXXXXXXX \
  --policy-name IzakayaAgentSecretsAccess \
  --policy-document file:///tmp/agentcore-secrets-policy.json
```

**教訓**: AgentCore Runtime IAMロールに必要な権限を追加せよ

---

### 7. Secrets Manager の値が空

**問題**: Secrets Managerにシークレットは作成されているが、値が空（`""`）だった

**症状**:
- API呼び出しが `401 Unauthorized` または `403 Forbidden` で失敗
- CloudWatch Logsに「APIキーが無効」というエラーが記録される

**根本原因**:
- `aws secretsmanager create-secret` で `--secret-string` を指定せずに作成していた
- または、テスト用に空文字列 `""` を設定していた

**対策**:
```bash
# シークレット作成時に必ず値を指定
aws secretsmanager create-secret \
  --name izakaya-agent/hotpepper-api-key \
  --secret-string "YOUR_ACTUAL_API_KEY" \
  --region ap-northeast-1

# 既存のシークレットを更新
aws secretsmanager put-secret-value \
  --secret-id izakaya-agent/hotpepper-api-key \
  --secret-string "YOUR_ACTUAL_API_KEY" \
  --region ap-northeast-1
```

**検証ロジックを追加**:
```python
# ツール内で値が空でないことを確認
secret_value = client.get_secret_value(SecretId=secret_name)['SecretString']
if not secret_value or secret_value.strip() == '':
    raise ValueError(f"Secret '{secret_name}' is empty")
```

**教訓**: Secrets Managerの値が空でないことを検証せよ

---

## トラブルシューティング

### CloudWatch Logs の確認方法

Lambda関数のログを確認して、エラーの詳細を調査します。

```bash
# Lambda関数のログをリアルタイムで表示
aws logs tail /aws/lambda/IzakayaAgentFunction \
  --region ap-northeast-1 \
  --follow

# 過去1時間のエラーログを検索
aws logs filter-log-events \
  --log-group-name /aws/lambda/IzakayaAgentFunction \
  --region ap-northeast-1 \
  --start-time $(date -u -d '1 hour ago' +%s)000 \
  --filter-pattern "ERROR"
```

### Lambda 直接 invoke でのテスト

LINE Webhookを経由せず、Lambda関数を直接呼び出してデバッグします。

```bash
# テストペイロードを作成
cat > /tmp/test-event.json <<EOF
{
  "events": [
    {
      "type": "message",
      "message": {
        "type": "text",
        "text": "テストメッセージ"
      },
      "replyToken": "test-token"
    }
  ]
}
EOF

# Lambda関数をinvoke
aws lambda invoke \
  --function-name IzakayaAgentFunction \
  --region ap-northeast-1 \
  --payload file:///tmp/test-event.json \
  --log-type Tail \
  /tmp/response.json

# レスポンスとログを確認
cat /tmp/response.json
```

### IAM権限のデバッグ方法

IAM権限の問題をデバッグするためのステップ：

#### 1. Lambda実行ロールの確認

```bash
# Lambda関数の実行ロール名を取得
ROLE_ARN=$(aws lambda get-function \
  --function-name IzakayaAgentFunction \
  --region ap-northeast-1 \
  --query 'Configuration.Role' \
  --output text)

ROLE_NAME=$(echo $ROLE_ARN | awk -F'/' '{print $2}')

# ロールにアタッチされたポリシーを確認
aws iam list-attached-role-policies \
  --role-name $ROLE_NAME

# インラインポリシーを確認
aws iam list-role-policies \
  --role-name $ROLE_NAME

# 特定のポリシーの内容を確認
aws iam get-role-policy \
  --role-name $ROLE_NAME \
  --policy-name DefaultPolicy
```

#### 2. AgentCore Runtime IAMロールの確認

```bash
# AgentCore RuntimeのIAMロール名を取得
AGENTCORE_ROLE=$(aws iam list-roles \
  --query 'Roles[?contains(RoleName, `AmazonBedrockAgentCoreSDKRuntime`)].RoleName' \
  --output text)

# ロールの権限を確認
aws iam list-role-policies \
  --role-name $AGENTCORE_ROLE

# Secrets Manager権限が追加されているか確認
aws iam get-role-policy \
  --role-name $AGENTCORE_ROLE \
  --policy-name IzakayaAgentSecretsAccess
```

#### 3. IAM Policy Simulator でテスト

```bash
# Lambda実行ロールが AgentCore Runtime を呼び出せるかシミュレート
aws iam simulate-principal-policy \
  --policy-source-arn $ROLE_ARN \
  --action-names bedrock-agentcore:InvokeAgentRuntime \
  --resource-arns "arn:aws:bedrock-agentcore:ap-northeast-1:*:runtime/*"
```

### よくあるエラーと対処法

| エラーメッセージ | 原因 | 対処法 |
|----------------|------|--------|
| `No module named 'pydantic_core._pydantic_core'` | Lambda Layerのバイナリ互換性 | manylinux wheel で再ビルド |
| `403 Forbidden` | Lambda IAM権限不足 | `InvokeAgentRuntime` 権限を追加 |
| `AccessDeniedException: secretsmanager:GetSecretValue` | AgentCore IAM権限不足 | Secrets Manager権限を追加 |
| `401 Unauthorized (API)` | Secrets Managerの値が空 | `put-secret-value` で値を設定 |
| `ModuleNotFoundError: No module named 'strands'` | Lambda Layerに strands-agents なし | requirements.txt に追加して再ビルド |

## CI/CD パイプラインへの組み込み（推奨）

以下のステップを自動化することで、デプロイの信頼性を向上させます：

```yaml
# .github/workflows/deploy.yml の例
name: Deploy Izakaya Agent

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Build Lambda Layer (manylinux)
        run: |
          pip install --platform manylinux2014_x86_64 --python-version 3.11 \
            --only-binary=:all: --target lambda-layer/python \
            -r lambda/requirements.txt

      - name: Deploy CDK Stack
        run: |
          cd infra
          npm install
          npx cdk deploy --require-approval never

      - name: Deploy AgentCore Runtime
        run: |
          cd agent
          python -m venv .venv
          source .venv/bin/activate
          pip install -r requirements.txt
          agentcore deploy

      - name: Run Integration Tests
        run: |
          cd agent
          source .venv/bin/activate
          pytest tests/integration/
```

## 参考リンク

- [AWS Lambda Layers Documentation](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/latest/guide/home.html)
- [Bedrock AgentCore SDK Documentation](https://docs.aws.amazon.com/bedrock/latest/agentcore/)
- [Python Packaging - manylinux](https://github.com/pypa/manylinux)
- [IAM Policy Simulator](https://policysim.aws.amazon.com/)

## まとめ

このドキュメントで記載した7つのハマりポイントを回避することで、AgentCore Runtimeを使用したLINE Botのデプロイをスムーズに行うことができます。特に以下の点に注意してください：

1. **Lambda Layerは manylinux wheel でビルド**
2. **boto3 クライアントで AgentCore Runtime を呼び出す**
3. **requirements.txt を統合して依存関係の不一致を防ぐ**
4. **IAMアクション名は公式ドキュメントで確認**
5. **エージェントコード変更時は agentcore deploy を実行**
6. **AgentCore Runtime IAMロールに必要な権限を追加**
7. **Secrets Managerの値が空でないことを検証**

これらのポイントを押さえることで、同じ問題を繰り返すことなく、効率的にデプロイできます。
