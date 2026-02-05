# Bedrock AgentCore Integration Skill

AWS Bedrock AgentCoreとの統合方法を提供するスキル。

## トリガーワード

このスキルは以下のキーワードで起動：
- `/agentcore`
- "Bedrock AgentCore統合"
- "AgentCore実装"
- "Strands Agents SDK"

## 概要

AWS Bedrock AgentCoreを使用したAIエージェントの実装方法を提供します。CDKでのRuntime定義、Pythonでのエージェント実装、セッション管理、ストリーミングレスポンス等を包括的にカバーします。

## 主要機能

### 1. AgentCore Runtime定義（CDK）
- AWS CDKでRuntimeリソースを定義
- 認証設定（JWT / Cognito）
- 環境変数設定
- IAMポリシー設定

### 2. Pythonエージェント実装
- Strands Agents SDKの使用
- ツール定義（@toolデコレータ）
- システムプロンプト設定
- Bedrockモデル設定（Claude Sonnet 4.5）

### 3. セッション管理
- 会話履歴の保持
- セッションIDベースの管理
- Agentインスタンスの再利用

### 4. ストリーミングレスポンス
- リアルタイムレスポンス
- イベントベースの通信
- ツール使用中の通知

### 5. コンテナイメージ構築
- Dockerfile定義
- ARM64対応
- 依存パッケージインストール

## アーキテクチャ

```
┌─────────────────────────────────────────────────────┐
│ Frontend (React + Amplify UI)                       │
│  - Cognito認証                                       │
│  - AgentCore Runtime呼び出し                        │
│  - ストリーミングレスポンス表示                      │
└─────────────────────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────┐
│ AWS Bedrock AgentCore Runtime                       │
│  - JWT認証（Cognito User Pool）                     │
│  - Dockerコンテナ実行（Python + Strands Agents）   │
│  - OpenTelemetry監視                                │
└─────────────────────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────┐
│ Python Agent (agent.py)                             │
│  - Strands Agents SDK                               │
│  - Claude Sonnet 4.5（Bedrock）                     │
│  - ツール定義（@tool）                              │
│  - セッション管理                                    │
│  - ストリーミングレスポンス                          │
└─────────────────────────────────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────┐
│ External Services                                   │
│  - Tavily API（Web検索）                            │
│  - Marp CLI（PDF生成）                              │
└─────────────────────────────────────────────────────┘
```

## 実装手順

### 1. CDKでAgentCore Runtimeを定義

**ファイル:** `amplify/agent/resource.ts`

```typescript
import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as agentcore from '@aws-cdk/aws-bedrock-agentcore-alpha';
import { ContainerImageBuild } from 'deploy-time-build';
import { Platform } from 'aws-cdk-lib/aws-ecr-assets';
import type { IUserPool, IUserPoolClient } from 'aws-cdk-lib/aws-cognito';

interface MarpAgentProps {
  stack: cdk.Stack;
  userPool?: IUserPool;
  userPoolClient?: IUserPoolClient;
  nameSuffix?: string;
}

export function createMarpAgent({ stack, userPool, userPoolClient, nameSuffix }: MarpAgentProps) {
  // 環境判定: sandbox（ローカル）vs 本番（Amplify Console）
  const isSandbox = !process.env.AWS_BRANCH;

  let agentRuntimeArtifact: agentcore.AgentRuntimeArtifact;
  let containerImageBuild: ContainerImageBuild | undefined;

  if (isSandbox) {
    // sandbox: ローカルでARM64ビルド
    agentRuntimeArtifact = agentcore.AgentRuntimeArtifact.fromAsset(
      path.join(__dirname, 'runtime')
    );
  } else {
    // 本番: CodeBuildでARM64ビルド（deploy-time-build）
    containerImageBuild = new ContainerImageBuild(stack, 'MarpAgentImageBuild', {
      directory: path.join(__dirname, 'runtime'),
      platform: Platform.LINUX_ARM64,
      tag: 'latest',
    });
    agentRuntimeArtifact = agentcore.AgentRuntimeArtifact.fromEcrRepository(
      containerImageBuild.repository,
      'latest'
    );
  }

  // 認証設定（JWT認証）
  const discoveryUrl = userPool
    ? `https://cognito-idp.${stack.region}.amazonaws.com/${userPool.userPoolId}/.well-known/openid-configuration`
    : undefined;

  const authConfig = discoveryUrl && userPoolClient
    ? agentcore.RuntimeAuthorizerConfiguration.usingJWT(
        discoveryUrl,
        [userPoolClient.userPoolClientId],
      )
    : undefined;

  // 環境ごとのランタイム名
  const runtimeName = nameSuffix ? `marp_agent_${nameSuffix}` : 'marp_agent';

  // AgentCore Runtime作成
  const runtime = new agentcore.Runtime(stack, 'MarpAgentRuntime', {
    runtimeName,
    agentRuntimeArtifact,
    authorizerConfiguration: authConfig,
    environmentVariables: {
      TAVILY_API_KEY: process.env.TAVILY_API_KEY || '',
      // Observability（OTEL）設定
      AGENT_OBSERVABILITY_ENABLED: 'true',
      OTEL_PYTHON_DISTRO: 'aws_distro',
      OTEL_PYTHON_CONFIGURATOR: 'aws_configurator',
      OTEL_EXPORTER_OTLP_PROTOCOL: 'http/protobuf',
    },
  });

  // 本番環境: ContainerImageBuild完了後にRuntimeを作成
  if (containerImageBuild) {
    runtime.node.addDependency(containerImageBuild);
  }

  // Bedrockモデル呼び出し権限を付与
  runtime.addToRolePolicy(new iam.PolicyStatement({
    actions: [
      'bedrock:InvokeModel',
      'bedrock:InvokeModelWithResponseStream',
    ],
    resources: [
      'arn:aws:bedrock:*::foundation-model/*',
      'arn:aws:bedrock:*:*:inference-profile/*',
    ],
  }));

  // 出力
  new cdk.CfnOutput(stack, 'MarpAgentRuntimeArn', {
    value: runtime.agentRuntimeArn,
    description: 'Marp Agent Runtime ARN',
  });

  return { runtime };
}
```

### 2. Pythonエージェントを実装

**ファイル:** `amplify/agent/runtime/agent.py`

```python
import os
from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
from tavily import TavilyClient

# Tavily クライアント初期化
tavily_client = TavilyClient(api_key=os.environ.get('TAVILY_API_KEY', ''))


@tool
def web_search(query: str) -> str:
    """Web検索を実行して最新情報を取得します。

    Args:
        query: 検索クエリ（日本語または英語）

    Returns:
        検索結果のテキスト
    """
    if not tavily_client.api_key:
        return "Web検索機能は現在利用できません（APIキー未設定）"

    try:
        results = tavily_client.search(
            query=query,
            max_results=5,
            search_depth="advanced",
        )
        # 検索結果をテキストに整形
        formatted_results = []
        for result in results.get("results", []):
            title = result.get("title", "")
            content = result.get("content", "")
            url = result.get("url", "")
            formatted_results.append(f"**{title}**\n{content}\nURL: {url}")
        return "\n\n---\n\n".join(formatted_results) if formatted_results else "検索結果がありませんでした"
    except Exception as e:
        return f"検索エラー: {str(e)}"


@tool
def output_slide(markdown: str) -> str:
    """生成したスライドのマークダウンを出力します。

    Args:
        markdown: Marp形式のマークダウン全文（フロントマターを含む）

    Returns:
        出力完了メッセージ
    """
    global _generated_markdown
    _generated_markdown = markdown
    return "スライドを出力しました。"


SYSTEM_PROMPT = """あなたはプロフェッショナルなスライド作成AIアシスタントです。

## 役割
ユーザーの指示に基づいて、Marp形式のマークダウンでスライドを作成・編集します。

## スライド作成ルール
- フロントマターには以下を含める：
  ---
  marp: true
  theme: border
  size: 16:9
  paginate: true
  ---
- スライド区切りは `---` を使用
- 1枚目はタイトルスライド（タイトル + サブタイトル）
- 箇条書きは1スライドあたり3〜5項目に抑える
- 絵文字は使用しない（シンプルでビジネスライクに）
"""

app = BedrockAgentCoreApp()

# セッションごとのAgentインスタンスを管理（会話履歴保持用）
_agent_sessions: dict[str, Agent] = {}
_generated_markdown: str | None = None


def get_or_create_agent(session_id: str | None) -> Agent:
    """セッションIDに対応するAgentを取得または作成"""
    # セッションIDがない場合は新規Agentを作成（履歴なし）
    if not session_id:
        return Agent(
            model=BedrockModel(
                model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                cache_prompt="default",
                cache_tools="default",
            ),
            system_prompt=SYSTEM_PROMPT,
            tools=[web_search, output_slide],
        )

    # 既存のセッションがあればそのAgentを返す
    if session_id in _agent_sessions:
        return _agent_sessions[session_id]

    # 新規セッションの場合はAgentを作成して保存
    agent = Agent(
        model=BedrockModel(
            model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            cache_prompt="default",
            cache_tools="default",
        ),
        system_prompt=SYSTEM_PROMPT,
        tools=[web_search, output_slide],
    )
    _agent_sessions[session_id] = agent
    return agent


@app.entrypoint
async def invoke(payload):
    """エージェント実行（ストリーミング対応）"""
    global _generated_markdown
    _generated_markdown = None  # リセット

    user_message = payload.get("prompt", "")
    session_id = payload.get("session_id")  # セッションID（会話履歴保持用）

    # セッションIDに対応するAgentを取得（会話履歴が保持される）
    agent = get_or_create_agent(session_id)
    stream = agent.stream_async(user_message)

    async for event in stream:
        if "data" in event:
            chunk = event["data"]
            yield {"type": "text", "data": chunk}
        elif "current_tool_use" in event:
            # ツール使用中イベントを送信
            tool_info = event["current_tool_use"]
            tool_name = tool_info.get("name", "unknown")
            yield {"type": "tool_use", "data": tool_name}
        elif "result" in event:
            # 最終結果からテキストを抽出
            result = event["result"]
            if hasattr(result, 'message') and result.message:
                for content in getattr(result.message, 'content', []):
                    if hasattr(content, 'text') and content.text:
                        yield {"type": "text", "data": content.text}

    # output_slideツールで生成されたマークダウンを送信
    if _generated_markdown:
        yield {"type": "markdown", "data": _generated_markdown}

    yield {"type": "done"}


if __name__ == "__main__":
    app.run()
```

### 3. Dockerfileを作成

**ファイル:** `amplify/agent/runtime/Dockerfile`

```dockerfile
FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.13-slim-bookworm

WORKDIR /app

# Node.js、Chromium、日本語フォントをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    npm \
    chromium \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -fv

# Marp CLI をインストール
RUN npm install -g @marp-team/marp-cli

# Puppeteer の Chromium パス設定
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true

# Python 依存関係をインストール
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# エージェントコードとテーマをコピー
COPY agent.py ./
COPY border.css ./

EXPOSE 8080

# OTELの自動計装を有効にして起動
CMD ["opentelemetry-instrument", "python", "agent.py"]
```

### 4. requirements.txt を作成

**ファイル:** `amplify/agent/runtime/requirements.txt`

```
bedrock-agentcore
strands-agents[otel]
aws-opentelemetry-distro
tavily-python
```

## セッション管理の実装

### セッションIDベースの会話履歴保持

```python
# グローバル辞書でAgentインスタンスを管理
_agent_sessions: dict[str, Agent] = {}

def get_or_create_agent(session_id: str | None) -> Agent:
    """セッションIDに対応するAgentを取得または作成"""
    # セッションIDがない場合は新規Agent（履歴なし）
    if not session_id:
        return Agent(...)

    # 既存のセッションがあればそのAgentを返す（履歴保持）
    if session_id in _agent_sessions:
        return _agent_sessions[session_id]

    # 新規セッションの場合はAgentを作成して保存
    agent = Agent(...)
    _agent_sessions[session_id] = agent
    return agent
```

### フロントエンドからのセッションID送信

```typescript
// React + Amplify UI
const sessionId = useRef(crypto.randomUUID())

const sendMessage = async (message: string) => {
  const response = await agentCoreRuntime.invoke({
    prompt: message,
    session_id: sessionId.current
  })

  // ストリーミングレスポンス処理
  for await (const event of response) {
    if (event.type === 'text') {
      console.log(event.data)
    }
  }
}
```

## ストリーミングレスポンスの実装

### イベントタイプ

| イベントタイプ | 説明 | データ |
|---------------|------|--------|
| `text` | テキストチャンク | `data: string` |
| `tool_use` | ツール使用中 | `data: tool_name` |
| `markdown` | 生成マークダウン | `data: markdown` |
| `error` | エラー | `message: error_message` |
| `done` | 完了 | - |

### Pythonでストリーミング送信

```python
@app.entrypoint
async def invoke(payload):
    agent = get_or_create_agent(payload.get("session_id"))
    stream = agent.stream_async(payload.get("prompt", ""))

    async for event in stream:
        if "data" in event:
            yield {"type": "text", "data": event["data"]}
        elif "current_tool_use" in event:
            yield {"type": "tool_use", "data": event["current_tool_use"]["name"]}

    yield {"type": "done"}
```

### フロントエンドで受信

```typescript
for await (const event of response) {
  switch (event.type) {
    case 'text':
      appendText(event.data)
      break
    case 'tool_use':
      showToolUse(event.data)
      break
    case 'markdown':
      renderMarkdown(event.data)
      break
    case 'done':
      hideLoading()
      break
  }
}
```

## 監視・トレース（OpenTelemetry）

### 環境変数設定

```typescript
environmentVariables: {
  AGENT_OBSERVABILITY_ENABLED: 'true',
  OTEL_PYTHON_DISTRO: 'aws_distro',
  OTEL_PYTHON_CONFIGURATOR: 'aws_configurator',
  OTEL_EXPORTER_OTLP_PROTOCOL: 'http/protobuf',
}
```

### 自動計装

```dockerfile
CMD ["opentelemetry-instrument", "python", "agent.py"]
```

### CloudWatch Logsで確認

- ロググループ: `/aws/bedrock-agentcore/runtimes/{runtime_name}-{id}-DEFAULT`
- トレース: X-Ray（OpenTelemetry経由）

## デプロイ

### ローカル（sandbox）

```bash
npx ampx sandbox
```

### 本番（Amplify Console）

```bash
git push origin main
```

Amplify Consoleが自動的に：
1. CodeBuildでDockerイメージビルド
2. ECRにプッシュ
3. AgentCore Runtimeデプロイ

## トラブルシューティング

### Runtime作成でエラー

**問題:** AgentCore Runtime作成時にエラー

**解決策:**
1. リージョンが us-east-1 か確認（2026-01時点でus-east-1のみ）
2. IAMポリシーが正しく設定されているか確認
3. Dockerイメージが正しくビルドされているか確認

### ストリーミングレスポンスが届かない

**問題:** イベントが受信できない

**解決策:**
1. `yield` で正しくイベントを送信しているか確認
2. フロントエンドで `for await` を使用しているか確認
3. CloudWatch Logsでエラーログを確認

### セッション履歴が保持されない

**問題:** 会話履歴が消える

**解決策:**
1. session_idが正しく送信されているか確認
2. `_agent_sessions` 辞書が正しく管理されているか確認
3. Lambdaコールドスタートで辞書が初期化されていないか確認

## 参考資料

- AWS Bedrock AgentCore: https://docs.aws.amazon.com/bedrock/latest/userguide/agents-agentcore.html
- Strands Agents SDK: https://github.com/anthropics/strands
- AWS CDK: https://docs.aws.amazon.com/cdk/
- OpenTelemetry: https://opentelemetry.io/

## 関連スキル

- `marp-slide-generator` - Marpスライド自動生成
- `marp-theme-customizer` - Marpテーマカスタマイズ

## バージョン情報

- AWS CDK: 2.234.1+
- Bedrock AgentCore: Alpha (2.236.0-alpha.0+)
- Strands Agents SDK: 最新版
- Python: 3.13+
