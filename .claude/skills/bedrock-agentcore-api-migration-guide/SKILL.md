# bedrock-agentcore-api-migration-guide

AgentCore 旧API→新API移行パターン。緊急バグ修正で得た知見をまとめたスキルにゃ。

## 使用タイミング
- AgentCore プロジェクトで ModuleNotFoundError が発生した時
- 旧APIから新APIへ移行する時
- Memory API を使用する時

## 主な移行パターン

### 1. インポート修正

**旧API（間違い）**:
```python
from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore.context import RequestContext
```

**新API（正解）**:
```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
# RequestContext は存在しない（削除）
```

### 2. エントリーポイント関数

**旧API（間違い）**:
```python
@app.entrypoint
def main(payload, context: RequestContext):
    session_id = context.session_id
```

**新API（正解）**:
```python
@app.entrypoint
def invoke(payload, context):
    session_id = getattr(context, 'session_id', None) or payload.get("session_id", "default-session")
```

**重要**: 関数名を `main` → `invoke` に変更すること！

### 3. Memory API 移行

**旧API（間違い）**:
```python
from bedrock_agentcore.memory.session import MemorySessionManager
from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole
from bedrock_agentcore.memory import MemoryManager

# 会話履歴取得
session = get_session_manager(session_id)
turns = session.get_last_k_turns(k=3)

# 会話保存
messages = [ConversationalMessage(content, MessageRole.USER)]
session.add_turns(messages=messages)
```

**新API（正解）**:
```python
from bedrock_agentcore.memory import MemoryClient
import os

memory_client = MemoryClient(region_name='ap-northeast-1')
MEMORY_ID = os.getenv('MEMORY_ID')

# 会話履歴取得
turns = memory_client.get_last_k_turns(
    memory_id=MEMORY_ID,
    actor_id="user",
    session_id=session_id,
    k=3
)

# 会話保存
messages = [(user_message, "USER"), (agent_response, "ASSISTANT")]
memory_client.create_event(
    memory_id=MEMORY_ID,
    actor_id="user",
    session_id=session_id,
    messages=messages
)
```

### 4. メッセージ形式の変更

| 項目 | 旧API | 新API |
|------|-------|-------|
| 形式 | ConversationalMessage オブジェクト | タプル (content, role) |
| Role | MessageRole.USER / MessageRole.ASSISTANT | "USER" / "ASSISTANT" (文字列) |
| メソッド | session.add_turns() | memory_client.create_event() |
| 履歴取得 | session.get_last_k_turns() | memory_client.get_last_k_turns() |

### 5. 環境変数対応

**重要**: MEMORY_ID は環境変数で渡す必要がある

```bash
# デプロイ前に設定
export MEMORY_ID="<your_memory_id>"
agentcore launch
```

## チェックリスト

移行前に以下を確認せよ：

- [ ] インポートを `bedrock_agentcore.runtime` に修正
- [ ] RequestContext を削除
- [ ] 関数名を `main` → `invoke` に変更
- [ ] session_id 取得を `getattr()` に変更
- [ ] MemoryClient を使用
- [ ] メッセージ形式をタプルに変更
- [ ] Role を文字列に変更（"USER", "ASSISTANT"）
- [ ] MEMORY_ID を環境変数で渡す
- [ ] 公式ドキュメントで最新APIを確認

## 参考資料

- Bedrock AgentCore 公式ドキュメント
- Memory API リファレンス
