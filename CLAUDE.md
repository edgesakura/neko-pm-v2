# neko-pm プロジェクト

猫型マルチエージェントシステム。ボスねこ・番猫・子猫の階層構造でタスクを実行する。

## 親プロジェクトの継承

@/home/edgesakura/git/CLAUDE.md

---

## 利用可能なスキル（親プロジェクトから継承）

| コマンド | 用途 | 定義 |
|---------|------|------|
| `/datadog` | Datadog監視設計 | @/home/edgesakura/git/.claude/skills/datadog/SKILL.md |
| `/ppt` | PowerPoint作成 | @/home/edgesakura/git/.claude/skills/ppt/SKILL.md |
| `/aws` | AWSインフラ設計 | @/home/edgesakura/git/.claude/skills/aws/SKILL.md |
| `/codex` | コードレビュー | @/home/edgesakura/git/.claude/skills/codex/SKILL.md |
| `/tdd` | テスト駆動開発 | @/home/edgesakura/git/.claude/commands/tdd.md |
| `/plan` | 実装計画作成 | @/home/edgesakura/git/.claude/commands/plan.md |
| `/code-review` | コードレビュー | @/home/edgesakura/git/.claude/commands/code-review.md |
| `/verify` | ビルド・テスト検証 | @/home/edgesakura/git/.claude/commands/verify.md |
| `/e2e` | E2Eテスト | @/home/edgesakura/git/.claude/commands/e2e.md |

## 利用可能なサブエージェント（親プロジェクトから継承）

| エージェント | 役割 | 定義 |
|-------------|------|------|
| planner | 実装計画作成 | @/home/edgesakura/git/.claude/agents/planner.md |
| architect | アーキテクチャ設計 | @/home/edgesakura/git/.claude/agents/architect.md |
| tdd-guide | TDDワークフロー支援 | @/home/edgesakura/git/.claude/agents/tdd-guide.md |
| code-reviewer | コードレビュー | @/home/edgesakura/git/.claude/agents/code-reviewer.md |
| security-reviewer | セキュリティレビュー | @/home/edgesakura/git/.claude/agents/security-reviewer.md |
| build-error-resolver | ビルドエラー解決 | @/home/edgesakura/git/.claude/agents/build-error-resolver.md |
| datadog-agent | 監視設計 | @/home/edgesakura/git/.claude/agents/datadog-agent.md |
| ppt-agent | プレゼン作成 | @/home/edgesakura/git/.claude/agents/ppt-agent.md |
| sre-agent | SRE運用設計 | @/home/edgesakura/git/.claude/agents/sre-agent.md |

---

## neko-pm固有の設定

### ディレクトリ構成

```
neko-pm/
├── instructions/     # エージェント指示書
│   ├── boss-cat.md   # ボスねこ（Opus・統括）
│   ├── guard-cat.md  # 番猫（Sonnet・タスク分配）
│   └── kitten.md     # 子猫（Sonnet・実行）
├── queue/            # 通信キュー
│   ├── boss_to_guard.yaml
│   ├── tasks/
│   └── reports/
├── nawabari.md       # 縄張り（状況板）
├── config/           # 設定
└── output/           # 成果物
```

### 猫型階層構造

```
ご主人（ユーザー）
    ↓ 指令
ボスねこ（neko:boss）
    ↓ YAML作戦命令 + tmux send-keys
番猫（neko:workers.0）
    ↓ タスクYAML + tmux send-keys
子猫1,2,3...（neko:workers.1,2,3...）
```

### 通信ルール

- **2回ルール**: tmux send-keysはコマンドとEnterを分けて送信
- **ポーリング禁止**: イベント駆動で通知
- **YAML永続化**: 通信失敗対策

### neko-pm固有スキル

| コマンド | 用途 | 定義 |
|---------|------|------|
| `/retrospective` | 振り返り | .claude/skills/retrospective/SKILL.md |

---

## 開発時の注意

- 本番環境への変更は必ず確認
- git pushは承認必要
- テストは自由に実行OK
