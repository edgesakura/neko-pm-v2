# 居酒屋検索AIエージェント「イザカヤくん」

LINE Botで複数エリアの居酒屋を検索できるAIエージェント

## プロジェクト概要

**イザカヤくん**は、LINE Bot + Webアプリで動作する居酒屋検索AIエージェントです。
ユーザーがエリア名を送ると、そのエリアの居酒屋情報を検索して返信します。

### 主な機能

- **全国対応**: Google Geocoding API統合により、全国のエリアを検索可能
- **AI対話**: Bedrock AgentCore + Claude Sonnet 4 による自然な対話
- **LINE連携**: LINE Messaging API経由で誰でも利用可能
- **Webアプリ対応**: API Gateway + Cognito認証でWebフロントエンドにも対応

## 技術スタック

| カテゴリ | 技術 |
|---------|------|
| AIエージェント | Strands Agents + Amazon Bedrock AgentCore |
| LLM | Claude Sonnet 4 (ap-northeast-1) |
| Memory | AgentCore Memory (会話履歴・セマンティック検索) |
| インフラ | AWS CDK v2 (TypeScript) |
| ランタイム | AWS Lambda (Python 3.11) |
| メッセージング | LINE Messaging API |
| Web API | API Gateway (REST API) + Cognito Authorizer |
| 外部API | Google Geocoding API, Google Places API |

## アーキテクチャ

### LINE Bot経由
```
LINE User
    ↓ メッセージ送信
LINE Messaging API
    ↓ Webhook
AWS Lambda (Function URL)
    ├─ LINE署名検証
    ├─ Secrets Manager（API Key取得）
    └─ Bedrock AgentCore呼び出し
        └─ Strands Agent実行
            ├─ Google Geocoding API（エリア解決）
            └─ Google Places API（居酒屋検索）
    ↓ レスポンス
LINE User（居酒屋情報を受信）
```

### Webアプリ経由
```
Web User (React/Next.js)
    ↓ メッセージ送信
API Gateway (/chat)
    ├─ Cognito Authorizer（認証）
    └─ AWS Lambda
        ├─ Secrets Manager（API Key取得）
        └─ Bedrock AgentCore呼び出し
            └─ Strands Agent実行
                ├─ Google Geocoding API（エリア解決）
                └─ Google Places API（居酒屋検索）
    ↓ JSON レスポンス
Web User（居酒屋情報を表示）
```

## プロジェクト構成

```
izakaya-agent/
├── infra/           # AWS CDKインフラ定義（Phase 1 ✅）
│   ├── bin/app.ts
│   ├── lib/izakaya-stack.ts
│   ├── package.json
│   └── cdk.json
├── agent/           # Strands Agent実装（Phase 2, 2.5 ✅）
│   ├── main.py      # AgentCoreエントリーポイント
│   ├── tools/       # 検索ツール（resolve_area, search_restaurants, check_availability）
│   ├── utils/       # ユーティリティ（memory.py, secrets.py）
│   └── requirements.txt
├── lambda/          # LINE Webhook実装（Phase 3 ✅）
│   ├── handler.py   # LINE Webhook処理
│   └── requirements.txt
└── README.md        # このファイル
```

## Phase 1: CDKインフラ構築 ✅

### デプロイ手順

#### 1. 依存関係のインストール

```bash
cd infra
npm install
```

#### 2. AWS CDKブートストラップ（初回のみ）

```bash
npx cdk bootstrap aws://{ACCOUNT_ID}/ap-northeast-1
```

#### 3. CDKデプロイ

```bash
npx cdk deploy
```

デプロイ後、以下の情報が出力されます：
- **LineWebhookUrl**: LINE Developers Consoleに設定するWebhook URL
- **ApiGatewayUrl**: Web APIのベースURL
- **ChatEndpoint**: Webアプリから呼び出すエンドポイント（`/chat`）
- **UserPoolId**: Cognito User Pool ID
- **UserPoolClientId**: Cognito User Pool Client ID
- **LambdaFunctionName**: Lambda関数名

**最新デプロイ情報（2026-02-06）**:
- API Gateway URL: `https://ok1y8ns08b.execute-api.ap-northeast-1.amazonaws.com/prod/`
- Chat Endpoint: `https://ok1y8ns08b.execute-api.ap-northeast-1.amazonaws.com/prod/chat`
- Cognito User Pool ID: `ap-northeast-1_7ctUrtWE6`
- Cognito User Pool Client ID: `mjcc196hqickudbha8ecfa4nn`

#### 4. Secrets Manager にAPIキーを設定（手動）

以下のコマンドでAPIキーを設定します：

```bash
# ホットペッパーグルメAPI キー
aws secretsmanager put-secret-value \
  --secret-id izakaya-agent/hotpepper-api-key \
  --secret-string "YOUR_HOTPEPPER_API_KEY" \
  --region ap-northeast-1

# Google Places API キー
aws secretsmanager put-secret-value \
  --secret-id izakaya-agent/google-places-api-key \
  --secret-string "YOUR_GOOGLE_PLACES_API_KEY" \
  --region ap-northeast-1

# LINE チャネルシークレット
aws secretsmanager put-secret-value \
  --secret-id izakaya-agent/line-channel-secret \
  --secret-string "YOUR_LINE_CHANNEL_SECRET" \
  --region ap-northeast-1

# LINE チャネルアクセストークン
aws secretsmanager put-secret-value \
  --secret-id izakaya-agent/line-channel-access-token \
  --secret-string "YOUR_LINE_CHANNEL_ACCESS_TOKEN" \
  --region ap-northeast-1
```

#### 5. CDKスタックの確認

```bash
# リソース一覧確認
npx cdk ls

# 差分確認
npx cdk diff

# 合成済みCloudFormationテンプレート確認
npx cdk synth
```

### デプロイされるリソース

| リソース | 説明 |
|---------|------|
| Secrets Manager (4つ) | API認証情報を安全に保存 |
| IAM Role | Lambda実行ロール（Bedrock, SecretsManager権限） |
| Lambda Function | LINE Webhook処理（Python 3.12） |
| Lambda Function URL | 公開エンドポイント（LINE署名検証で保護） |
| CloudWatch Logs | Lambda実行ログ（7日間保持） |

## Phase 2: エージェント実装 ✅

**ステータス**: 完了

### 実装内容

1. **main.py**: Strands Agent + BedrockAgentCoreApp エントリーポイント
2. **tools/resolve_area.py**: エリア名→座標変換（10エリア対応）
3. **tools/search_restaurants.py**: ハイブリッド検索（Hotpepper + Google Places）
4. **tools/check_availability.py**: 営業時間確認（Google Places API）
5. **utils/secrets.py**: Secrets Manager統合（lru_cache付き）

### 主な機能

- **ハイブリッド検索**: Hotpepper + Google Places APIでスコアリング
- **スコアリングロジック**: 評価×20 + レビュー数/100×10 + 両方掲載+10
- **複数エリア対応**: 新橋、渋谷、新宿、池袋、六本木、銀座、品川、上野、恵比寿、中目黒

## Phase 2.5: Memory機能追加 ✅

**ステータス**: 完了

### 実装内容

1. **utils/memory.py**: AgentCore Memory統合
   - `save_conversation()`: 会話保存
   - `get_conversation_history()`: 会話履歴取得
   - `search_semantic_memory()`: セマンティック検索
   - `save_user_preference()`: ユーザー好み保存

2. **main.py修正**: Memory統合
   - RequestContext から session_id 取得（LINE user_id）
   - 会話履歴を instructions に注入
   - セマンティック検索でユーザー好みを取得

### 主な機能

- **会話継続**: 「さっきの2番目の店」などの指示代名詞を理解
- **セマンティックメモリ**: ユーザーの好み（エリア、雰囲気、予算）を記憶
- **セッションID連携**: LINE user_id = session_id で個別の会話履歴を保持

## Phase 3: LINE Bot連携 ✅

**ステータス**: 完了

### 実装内容

1. **lambda/handler.py**: LINE Webhook処理（222行）
   - LINE署名検証（WebhookHandler）
   - Webhook イベント処理
   - Bedrock AgentCore Runtime 呼び出し（session_id = LINE user_id）
   - LINE返信メッセージ送信
   - エラーハンドリング

### 主な機能

- **LINE署名検証**: セキュリティ必須（InvalidSignatureError → 400）
- **セッションID連携**: LINE user_id をそのまま session_id として使用
- **ストリーム処理**: AgentCore レスポンスを順次読み取り
- **エラーハンドリング**: 署名検証失敗、Runtime エラー、返信エラー全て対応

## Phase 4: デプロイ・テスト 🚀

### 前提条件

- AWS CLI 設定済み
- Node.js 18+ インストール済み
- Python 3.11+ インストール済み

### 手順

#### 1. Lambda Layer 作成

Lambda Functionで使用するPythonパッケージをLayerとして準備します：

```bash
cd output/izakaya-agent
mkdir -p lambda-layer/python
pip install -r lambda/requirements.txt -t lambda-layer/python
```

#### 2. AgentCore CLI インストール

```bash
pip install bedrock-agentcore-starter-toolkit
```

#### 3. Memory リソース作成

AgentCore Memory リソースを作成します（会話履歴・セマンティック検索用）：

```bash
cd agent
agentcore memory create IzakayaAgentMemory \
  --strategies '[{"semanticMemoryStrategy": {"name": "UserPreferences"}}]' \
  --region ap-northeast-1 \
  --wait
```

#### 4. エージェント設定

```bash
agentcore configure \
  --entrypoint main.py \
  --name izakaya-agent \
  --runtime PYTHON_3_11 \
  --region ap-northeast-1 \
  --non-interactive
```

#### 5. エージェントデプロイ

```bash
agentcore launch
```

#### 6. エージェントID取得

デプロイ完了後、AGENT_ID と AGENT_ALIAS_ID を取得します：

```bash
agentcore status
# AGENT_ID と AGENT_ALIAS_ID をメモ
```

#### 7. CDKスタックデプロイ

取得したエージェントIDを環境変数として渡してCDKデプロイします：

```bash
cd ../infra
export AGENT_ID="<取得したAGENT_ID>"
export AGENT_ALIAS_ID="<取得したAGENT_ALIAS_ID>"
npm install
npx cdk deploy
```

#### 8. Lambda Function URL 取得

CDKデプロイ後、Outputs から Function URL をメモします：

```
IzakayaStack.LineWebhookUrl = https://xxxxx.lambda-url.ap-northeast-1.on.aws/
```

#### 9. LINE Developers で Webhook URL 設定

1. LINE Developers Console にログイン
2. チャネルを選択
3. Messaging API 設定 > Webhook URL に Lambda Function URL を設定
4. 「Webhookの利用」をONにする
5. 「検証」をクリックして疎通確認

#### 10. 動作テスト

1. LINE公式アカウントを友だち追加
2. メッセージを送信（例: "渋谷で飲みたい"）
3. CloudWatch Logs で動作確認

```bash
aws logs tail /aws/lambda/izakaya-agent-line-webhook --follow
```

### トラブルシューティング

#### Lambda タイムアウト

- CloudWatch Logs で実行時間を確認
- AgentCore の応答が遅い場合は timeout を延長

#### LINE署名検証エラー

- Secrets Manager に正しいチャネルシークレットが登録されているか確認
- `X-Line-Signature` ヘッダーが正しく渡されているか確認

#### AgentCore Runtime エラー

- AGENT_ID, AGENT_ALIAS_ID が正しく設定されているか確認
- AgentCore のステータスを確認: `agentcore status`
- Memory リソースが作成されているか確認

#### Memory機能が動作しない

- Memory リソースが作成されているか確認: `agentcore memory list`
- session_id（LINE user_id）が正しく渡されているか確認
- CloudWatch Logs でMemory関連エラーを確認

#### ModuleNotFoundError: bedrock_agentcore.context

**問題**: `agentcore invoke` 実行時に以下のエラーが発生:
```
ModuleNotFoundError: No module named 'bedrock_agentcore.context'
```

**原因**: AgentCore の旧API（Phase 2, 2.5で使用）が公式ドキュメントと異なる

**解決方法**:

1. **main.py のインポート修正**

修正前（間違い）:
```python
from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore.context import RequestContext
```

修正後（正解）:
```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
# RequestContext は存在しない（削除）
```

2. **エントリーポイント関数の修正**

修正前（間違い）:
```python
@app.entrypoint
def main(payload, context: RequestContext):
    session_id = context.session_id
```

修正後（正解）:
```python
@app.entrypoint
def invoke(payload, context):
    session_id = getattr(context, 'session_id', None) or payload.get("session_id", "default-session")
```

**重要**: 関数名を `main` → `invoke` に変更すること！

3. **utils/memory.py の新API対応**

修正前（旧API）:
```python
from bedrock_agentcore.memory.session import MemorySessionManager
from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole
```

修正後（新API）:
```python
from bedrock_agentcore.memory import MemoryClient
import os

memory_client = MemoryClient(region_name='ap-northeast-1')
MEMORY_ID = os.getenv('MEMORY_ID')
```

**API変更点**:

| 項目 | 旧API | 新API |
|------|-------|-------|
| インポート | `MemorySessionManager` | `MemoryClient` |
| メッセージ形式 | `ConversationalMessage` | タプル `(content, role)` |
| Role | `MessageRole.USER` | `"USER"` (文字列) |
| 履歴取得 | `session.get_last_k_turns(k=3)` | `memory_client.get_last_k_turns(memory_id, actor_id, session_id, k=3)` |
| 会話保存 | `session.add_turns(messages=[...])` | `memory_client.create_event(memory_id, actor_id, session_id, messages=[...])` |

4. **環境変数設定**

```bash
cd agent
export MEMORY_ID="izakaya_agent_mem-ZOMh0R8tfz"
agentcore launch
agentcore invoke '{"prompt": "こんにちは"}'
```

**参考**: 新API移行の詳細は緊急バグ修正レポート（queue/reports/report-task-20260206-022203-kitten1.yaml）を参照

## トラブルシューティング

### CDK デプロイエラー

**エラー**: `cdk: command not found`

```bash
# グローバルインストール
npm install -g aws-cdk

# または npx経由で実行
npx cdk deploy
```

**エラー**: `Requires bootstrap stack version 'X', found 'Y'`

```bash
npx cdk bootstrap --force
```

### Lambda 実行エラー

CloudWatch Logsで確認：

```bash
aws logs tail /aws/lambda/izakaya-agent-line-webhook --follow
```

## 開発メモ

### 重要な設計判断

1. **AgentCore本体のデプロイ**: CDKではなく `agentcore CLI` を使用
2. **Lambda Function URL**: API Gatewayを使わずシンプルに構成
3. **タイムアウト**: 60秒（LINE Bot化記事に従う）
4. **シークレット管理**: 値は手動設定（CDKでは箱だけ作成）

### 参考記事

- [新橋くん（元記事）](https://dev.classmethod.jp/articles/shoma-struggling-with-after-party-venue-search-built-shimbashi-izakaya-search-ai-agent-shimbashi-kun-with-bedrock-agentcore/)
- [LINE Bot化記事](https://dev.classmethod.jp/articles/shoma-bedrock-agentcore-izakaya-search-ai-agent-shinbashi-kun-line-official-account-messaging-api-bot/)

## ライセンス

MIT

## 作成者

neko-pm / 子猫1
