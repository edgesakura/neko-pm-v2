# SRE Agent on AgentCore + A2A

**コンテキストエンジニアリング + 可観測性** を最重視した SRE マルチエージェントシステム。

## アーキテクチャ

```
  Mock Alert (CLI trigger)
         |
  +----- Gateway (MCP, Semantic Search ON) -----+
  |  Interceptor Lambda: アラート種別でフィルタ    |
  +----------------------------------------------+
         |
  +==============================+
  |  SRE Orchestrator (Sonnet)   |  <- 薄いコンテキスト: classify_alert のみ
  |  Tools: classify_alert       |
  +==============================+
       |                    |
       v                    v
+-------------+    +---------------+
| Knowledge   |    | Diagnostic    |
| Agent       |    | Agent         |
| (Haiku)     |    | (Sonnet)      |
| Memory: LTM |    | 15 mock tools |
+-------------+    +---------------+
```

### コンテキスト比較

| 構成 | トークン概算 |
|------|-------------|
| モノリシック（17ツール全直接） | ~8,000 |
| A2A のみ（Gateway なし） | ~1,500 |
| **A2A + Gateway（本構成）** | **~900** |

## クイックスタート

```bash
# ローカルテスト（AWS 不要）
cd output/sre-agent
python scripts/trigger-alert.py --scenario api_5xx_spike --local

# シナリオ一覧
python scripts/trigger-alert.py --scenario pod_crashloop --local
python scripts/trigger-alert.py --scenario high_latency --local
```

## プロジェクト構成

```
output/sre-agent/
├── agents/
│   ├── orchestrator/          # 薄い Orchestrator (Sonnet)
│   │   ├── main.py
│   │   ├── tools/classify_alert.py
│   │   ├── prompts/system.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── diagnostic/            # メトリクス/ログ/ヘルス診断 (Sonnet)
│   │   ├── main.py
│   │   ├── tools/             # 15 mock tools
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── knowledge/             # インシデント検索 + Runbook (Haiku)
│       ├── main.py
│       ├── tools/
│       ├── Dockerfile
│       └── requirements.txt
├── gateway/
│   ├── interceptor/handler.py # Gateway Interceptor Lambda
│   └── setup-gateway.sh
├── common/
│   ├── models.py              # Alert, Diagnosis, Incident dataclass
│   ├── mock_data.py           # リアルな時系列データ生成
│   ├── telemetry.py           # OTel -> Langfuse + FilteringSpanProcessor
│   └── a2a_client.py          # invoke_agent_runtime ヘルパー
├── mock/
│   ├── alerts/                # 3 シナリオ (Datadog webhook 形式)
│   ├── incidents/seed.json    # 10 件の過去インシデント
│   └── runbooks/              # 3 Runbook (markdown)
├── scripts/
│   ├── trigger-alert.py       # CLI アラートトリガー
│   ├── seed-knowledge.py      # Memory API シードデータ投入
│   └── deploy-all.sh          # 全体デプロイ
├── infra/                     # CDK (TypeScript)
│   ├── lib/sre-agent-stack.ts # ECR x3, IAM, Lambda, CloudWatch
│   └── lib/config.ts          # enableVpc: false (Phase 3 で ON)
├── tests/
└── requirements-base.txt
```

## 可観測性 (OTel + Langfuse)

```
Layer 1: OTel 計装（全エージェント共通）
Layer 2: FilteringSpanProcessor（A2A 内部スパン除外）
Layer 3: Langfuse Exporter（Phase 1）→ Datadog LLM Obs（Phase 3）
Layer 4: Knowledge 品質メトリクス（Relevance Score トレース）
```

### Phase 3 移行（Datadog LLM Obs）

環境変数を変えるだけ:
```bash
# Phase 1 (Langfuse)
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx

# Phase 3 (Datadog)
OTEL_EXPORTER_ENDPOINT=http://datadog-agent:4317
```

## デプロイ

```bash
# CDK
cd infra && npm install && npx cdk deploy

# 全体デプロイ
./scripts/deploy-all.sh
```

## フェーズロードマップ

| Phase | 内容 |
|-------|------|
| **1 (本実装)** | A2A 骨格 + Gateway + OTel/Langfuse + コンテキスト設計 |
| 2 | Mock Datadog API + Slack 通知 + AI-as-a-Judge |
| 3 | VPC + 実 Datadog 接続 + Langfuse -> Datadog 移行 |
| 4 | EKS Remediation Agent + 承認ワークフロー |

## 技術スタック

- **Strands Agents** + BedrockAgentCoreApp
- **Gateway Semantic Search** + Interceptor Lambda
- **OpenTelemetry** + Langfuse Cloud
- **AWS CDK** (TypeScript)
- **Docker** + Lambda Web Adapter
