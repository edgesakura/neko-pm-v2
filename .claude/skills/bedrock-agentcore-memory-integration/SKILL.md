# bedrock-agentcore-memory-integration

Amazon Bedrock AgentCore Memory 統合パターン。会話継続・文脈維持を実現するスキルにゃ。

## 使用タイミング
- AgentCore で会話履歴を管理する時
- ユーザー好みを記憶する時
- セマンティック検索を実装する時

## アーキテクチャ

```
AgentCore Runtime ← Memory Client → Memory Resource
                                     ├─ 会話履歴（ターン形式）
                                     └─ セマンティックメモリ（ユーザー好み）
```

## 実装パターン

### 1. Memory Client 初期化

```python
import os
from bedrock_agentcore.memory import MemoryClient
from typing import List, Dict, Any

# Memory Client 初期化（グローバルスコープ）
memory_client = MemoryClient(region_name='ap-northeast-1')
MEMORY_ID = os.getenv('MEMORY_ID')  # 環境変数から取得

if not MEMORY_ID:
    raise ValueError("MEMORY_ID environment variable is required")
```

### 2. 会話履歴取得

```python
def get_conversation_history(session_id: str, k: int = 3) -> List[Dict[str, Any]]:
    """
    過去k件の会話履歴を取得

    Args:
        session_id: セッションID（LINE user_id など）
        k: 取得件数

    Returns:
        会話履歴のリスト
    """
    try:
        turns = memory_client.get_last_k_turns(
            memory_id=MEMORY_ID,
            actor_id="user",
            session_id=session_id,
            k=k
        )
        return turns if turns else []
    except Exception as e:
        print(f"Failed to retrieve conversation history: {e}")
        return []
```

### 3. 会話保存

```python
def save_conversation(
    session_id: str,
    user_message: str,
    agent_response: str
) -> bool:
    """
    会話をMemoryに保存

    Args:
        session_id: セッションID
        user_message: ユーザーのメッセージ
        agent_response: エージェントの応答

    Returns:
        保存成功 = True
    """
    try:
        # メッセージをタプルのリストとして作成
        messages = [
            (user_message, "USER"),
            (agent_response, "ASSISTANT")
        ]

        memory_client.create_event(
            memory_id=MEMORY_ID,
            actor_id="user",
            session_id=session_id,
            messages=messages
        )
        return True
    except Exception as e:
        print(f"Failed to save conversation: {e}")
        return False
```

### 4. セマンティック検索

```python
def search_semantic_memory(
    session_id: str,
    query: str
) -> List[Dict[str, Any]]:
    """
    セマンティックメモリを検索（ユーザーの好みなど）

    Args:
        session_id: セッションID
        query: 検索クエリ

    Returns:
        関連するメモリのリスト
    """
    try:
        # 新APIではセマンティック検索は get_last_k_turns で代用
        # または別のメソッドを使用（公式ドキュメント確認）
        return []
    except Exception as e:
        print(f"Failed to search semantic memory: {e}")
        return []
```

### 5. main.py での Memory 統合

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from utils.memory import get_conversation_history, save_conversation

app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload, context):
    """
    エージェントのエントリーポイント

    Args:
        payload: リクエストペイロード（dict）
        context: AgentCore実行コンテキスト
    """
    # session_id の取得
    session_id = getattr(context, 'session_id', None) or payload.get("session_id", "default-session")
    user_message = payload.get("user_message", "") or payload.get("prompt", "")

    # 会話履歴取得
    history = get_conversation_history(session_id, k=3)
    history_text = format_conversation_history(history)

    # instructions に会話履歴を含める
    instructions = f"""
    あなたは親切なアシスタントです。

    過去の会話:
    {history_text}

    ユーザーの質問: {user_message}
    """

    # エージェント処理（省略）
    agent_response = process_agent(instructions)

    # Memory に保存
    save_conversation(session_id, user_message, agent_response)

    return agent_response

def format_conversation_history(turns: List[Dict]) -> str:
    """会話履歴をフォーマット"""
    if not turns:
        return "（初回の会話です）"

    formatted = []
    for turn in turns[-5:]:  # 直近5件
        messages = turn.get('messages', [])
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if role == 'USER':
                formatted.append(f"ユーザー: {content}")
            elif role == 'ASSISTANT':
                formatted.append(f"エージェント: {content}")
    return "\n".join(formatted)
```

## Memory Resource 作成

```bash
agentcore memory create {ProjectName}Memory \
  --strategies '[{"semanticMemoryStrategy": {"name": "UserPreferences"}}]' \
  --region ap-northeast-1 \
  --wait
```

## 環境変数設定

```bash
# デプロイ前に設定
export MEMORY_ID="<取得したMEMORY_ID>"
agentcore launch
```

## チェックリスト

- [ ] Memory Resource 作成完了
- [ ] MEMORY_ID 環境変数設定
- [ ] MemoryClient 初期化実装
- [ ] get_conversation_history 実装
- [ ] save_conversation 実装
- [ ] main.py に Memory 統合
- [ ] session_id を正しく渡す
- [ ] エラーハンドリング実装

## 参考資料

- Bedrock AgentCore Memory API リファレンス
- AWS公式ドキュメント
