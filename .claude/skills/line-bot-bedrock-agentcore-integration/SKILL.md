# line-bot-bedrock-agentcore-integration

LINE Messaging API と Amazon Bedrock AgentCore Runtime を統合するパターン。Phase 3で実装したLambda Webhookをスキル化したにゃ。

## 使用タイミング
- LINE Bot を AgentCore と連携する時
- Webhook 処理を実装する時
- セッションID連携でMemory機能を有効化する時

## アーキテクチャ

```
LINE User → LINE Messaging API → Lambda Function URL → Bedrock AgentCore Runtime
                                  ↓
                             Secrets Manager
```

## 実装パターン

### 1. Lambda handler.py の基本構造

```python
import os
import json
import boto3
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# Secrets Manager から取得
CHANNEL_SECRET = get_secret("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = get_secret("LINE_CHANNEL_ACCESS_TOKEN")

# 環境変数から取得
AGENT_ID = os.environ["AGENT_ID"]
AGENT_ALIAS_ID = os.environ["AGENT_ALIAS_ID"]

bedrock_client = boto3.client("bedrock-agent-runtime", region_name="ap-northeast-1")
handler = WebhookHandler(CHANNEL_SECRET)

def lambda_handler(event, context):
    # LINE署名検証
    signature = event["headers"].get("X-Line-Signature", "")
    body = event["body"]

    try:
        handler.handle(body, signature)
        return {"statusCode": 200, "body": "OK"}
    except InvalidSignatureError:
        return {"statusCode": 403, "body": "Invalid signature"}
    except Exception as e:
        print(f"Error: {e}")
        return {"statusCode": 500, "body": "Internal server error"}

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    user_id = event.source.user_id
    user_message = event.message.text
    reply_token = event.reply_token

    # AgentCore Runtime 呼び出し（重要: sessionId=user_id）
    response = invoke_agentcore_runtime(user_id, user_message)

    # LINE返信
    send_line_reply(reply_token, response)
```

### 2. LINE署名検証（セキュリティ必須）

```python
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError

handler = WebhookHandler(CHANNEL_SECRET)

# 署名検証
try:
    handler.handle(body, signature)
except InvalidSignatureError:
    # 署名検証失敗 → 403 Forbidden
    return {"statusCode": 403, "body": "Invalid signature"}
```

### 3. AgentCore Runtime 呼び出し

```python
def invoke_agentcore_runtime(user_id: str, user_message: str) -> str:
    """
    Bedrock AgentCore Runtime を呼び出し

    重要: sessionId=user_id により会話継続が可能
    """
    response = bedrock_client.invoke_agent(
        agentId=AGENT_ID,
        agentAliasId=AGENT_ALIAS_ID,
        sessionId=user_id,  # ← LINE user_id を session_id として使用
        inputText=user_message,
    )

    # ストリーム形式のレスポンスを処理
    result = ""
    for event in response.get("completion", []):
        if "chunk" in event:
            chunk = event["chunk"]
            if "bytes" in chunk:
                result += chunk["bytes"].decode("utf-8")

    return result
```

### 4. セッションID連携（Memory機能有効化）

**最重要ポイント**: `sessionId=user_id` により、同一LINEユーザーの会話が同じセッションとして扱われる

```python
# LINE user_id を session_id として使用
user_id = event.source.user_id

# AgentCore Runtime に渡す
response = bedrock_client.invoke_agent(
    agentId=AGENT_ID,
    agentAliasId=AGENT_ALIAS_ID,
    sessionId=user_id,  # ← これが会話継続の鍵
    inputText=user_message,
)
```

これにより：
- 会話履歴の保持
- ユーザー好みの記憶
- 「さっきの2番目の店」などの指示代名詞を理解

### 5. LINE返信

```python
def send_line_reply(reply_token: str, message: str) -> None:
    """LINE返信メッセージ送信"""
    configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=message)]
            )
        )
```

### 6. Secrets Manager 連携

```python
def get_secret(secret_name: str) -> str:
    """Secrets Manager からシークレット取得"""
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name="ap-northeast-1")

    response = client.get_secret_value(SecretId=secret_name)
    return response["SecretString"]
```

## requirements.txt

```
line-bot-sdk>=3.0.0
boto3>=1.34.0
```

## チェックリスト

- [ ] LINE署名検証を実装
- [ ] sessionId=user_id でAgentCore呼び出し
- [ ] ストリーム形式レスポンスを処理
- [ ] Secrets Manager からシークレット取得
- [ ] エラーハンドリング実装
- [ ] CloudWatch Logs 出力実装
- [ ] Lambda Function URL 設定
- [ ] LINE Webhook URL 設定

## 参考資料

- LINE Bot SDK for Python v3: https://github.com/line/line-bot-sdk-python
- Bedrock AgentCore Runtime API: AWS公式ドキュメント
