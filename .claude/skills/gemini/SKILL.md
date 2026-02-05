# Gemini（賢者キツネ）

---
name: gemini
description: Google Gemini 3 Proを使用してリサーチ・トレンド調査・概要把握を実行するスキル
allowed-tools:
  - Bash
triggers:
  - gemini
  - リサーチ
  - 調査して
  - トレンド
  - 概要把握
  - /gemini
---

Google Gemini 3 Proを使用して、リサーチ・トレンド調査・概要把握を実行するスキル。

## トリガー

"gemini", "リサーチ", "調査して", "トレンド", "概要把握", "/gemini"

## 実行コマンド

```bash
gemini -p "<request>" -y
```

## パラメータ

| パラメータ | 説明 | デフォルト |
|-----------|------|-----------|
| `-p, --prompt` | プロンプト（非対話モード） | - |
| `-i, --prompt-interactive` | プロンプト実行後に対話モードを継続 | - |
| `-y, --yolo` | 全アクション自動承認（YOLO mode） | false |
| `--approval-mode` | 承認モード: default, auto_edit, yolo, plan | default |
| `-m, --model` | 使用するモデル | - |
| `-s, --sandbox` | サンドボックスモードで実行 | - |
| `-r, --resume` | セッション再開（"latest"で最新） | - |
| `--allowed-tools` | 確認なしで実行可能なツール | - |
| `-o, --output-format` | 出力フォーマット: text, json, stream-json | text |

## 承認モード

| モード | 説明 | 用途 |
|--------|------|------|
| `default` | 各アクションでプロンプト表示 | 通常使用 |
| `auto_edit` | 編集ツールを自動承認 | ファイル編集が多い場合 |
| `yolo` | 全ツールを自動承認 | 完全自動実行 |
| `plan` | 読み取り専用モード | リサーチ専用 |

## 使用例

### 技術トレンド調査
```bash
gemini -p "2026年のフロントエンド開発トレンドを調査して、主要な技術スタックをまとめてください" --approval-mode plan
```

### 新技術の概要把握
```bash
gemini -p "React 19の新機能について概要をまとめてください。特にServer Componentsの変更点を中心に" --approval-mode plan
```

### ライブラリ比較調査
```bash
gemini -p "Next.js 15とRemixを比較して、それぞれの強みと弱みをまとめてください" --approval-mode plan
```

### プロジェクト技術選定のリサーチ
```bash
cd /path/to/project
gemini -p "このプロジェクトで使用すべき状態管理ライブラリを調査し、Redux、Zustand、Jotaiを比較してください" --approval-mode plan
```

### APIサービスの調査
```bash
gemini -p "Datadog、New Relic、Grafanaの監視ツールを比較し、それぞれの特徴と価格帯をまとめてください" -y
```

### アーキテクチャパターンの調査
```bash
gemini -p "マイクロサービスアーキテクチャとモノリシックアーキテクチャのトレードオフをまとめてください" --approval-mode plan
```

### 対話的なリサーチ（継続質問）
```bash
gemini -i "Tailscaleについて教えてください"
# 対話モードで追加質問が可能
```

## 使用場面

### 1. 技術選定前のリサーチ
新しいプロジェクトで技術スタックを決める前に、選択肢を調査する。
- **推奨**: `--approval-mode plan`（読み取り専用）

### 2. 最新トレンドの把握
業界のトレンドや新技術の動向を短時間で概要把握する。
- **推奨**: `-y` または `--approval-mode plan`

### 3. ライブラリ・ツールの比較
複数の選択肢がある場合に、それぞれの特徴を比較する。
- **推奨**: `--approval-mode plan`

### 4. ベストプラクティスの調査
特定の技術領域における推奨パターンやベストプラクティスを調べる。
- **推奨**: `--approval-mode plan`

### 5. 概要の素早い理解
新しい概念や技術について、詳細な実装前に全体像を掴む。
- **推奨**: `-p "<質問>" -y`

### 6. 市場調査・競合分析
類似サービスやプロダクトの調査、市場動向の把握。
- **推奨**: `--approval-mode plan`

### 7. 対話的な深掘り調査
複数回の質問で段階的に理解を深める。
- **推奨**: `-i "<最初の質問>"`

## 賢者キツネとの連携方法

### ボスねこからの召喚
```yaml
# queue/boss_to_guard.yamlに記載
commands:
  - command_id: "cmd-{timestamp}"
    type: research
    description: |
      賢者キツネを召喚して、{調査対象}をリサーチせよ
    external_agent: sage_fox
    expected_outputs:
      - "調査レポート（マークダウン）"
```

### 番猫からの召喚（tmux send-keys）

#### ワンショット調査（読み取り専用）
```bash
# 1回目: コマンド送信
tmux send-keys -t neko:specialists.2 "gemini -p '技術トレンド調査の依頼内容' --approval-mode plan"

# 間を空ける
sleep 1

# 2回目: Enter送信
tmux send-keys -t neko:specialists.2 Enter
```

#### 完全自動モード（YOLO）
```bash
# 1回目
tmux send-keys -t neko:specialists.2 "gemini -p '調査依頼内容' -y"

# 間を空ける
sleep 1

# 2回目
tmux send-keys -t neko:specialists.2 Enter
```

### 子猫からの利用
子猫は直接呼ばず、番猫にエスカレーションして依頼する。

## Codex（目利きフクロウ）との使い分け

| エージェント | 用途 | 強み | 推奨承認モード |
|-------------|------|------|---------------|
| **賢者キツネ（Gemini）** | リサーチ、トレンド調査、概要把握 | 幅広い知識、最新情報、短時間での概要把握 | `plan` (読み取り専用) |
| **目利きフクロウ（Codex）** | コードレビュー、セキュリティ監査 | コード理解、静的解析、脆弱性検出 | `read-only` |
| **研究狸（o3-deep-research）** | 深い調査、詳細分析 | 深い推論、複雑な問題の分析 | - |
| **長老猫（Opus）** | 重大な設計判断 | 深い推論、アーキテクチャ設計 | - |

## 判断フロー（ボスねこの視点）

```
判断に迷う
    ↓
まず賢者キツネで概要把握（数分）
  gemini -p "..." --approval-mode plan
    ↓
詳細必要なら研究狸で深掘り（5〜30分）
    ↓
それでも難しい → 長老猫（Opus）召喚
```

## 出力フォーマット

賢者キツネからの出力は通常、以下のような形式になります：

```markdown
# {調査タイトル}

## 概要
{対象の概要を2-3文で}

## 調査結果

### {観点1}
- {ポイント1}
- {ポイント2}

### {観点2}
- {ポイント1}
- {ポイント2}

## 比較表（該当する場合）

| 項目 | 選択肢A | 選択肢B | 選択肢C |
|------|---------|---------|---------|
| 特徴 | ... | ... | ... |
| 価格 | ... | ... | ... |
| 強み | ... | ... | ... |
| 弱み | ... | ... | ... |

## 推奨

{調査結果を踏まえた推奨事項}

## 参考情報

- [リンク1](URL)
- [リンク2](URL)
```

## 実行手順（召喚側の視点）

### 1. タスクの受け取り
番猫または子猫が「リサーチが必要」と判断した場合、ボスねこにエスカレーション。

### 2. ボスねこが召喚判断
- 単純な情報検索 → 賢者キツネ（Gemini）
- 深い調査が必要 → 研究狸（o3-deep-research）
- 設計判断が必要 → 長老猫（Opus）

### 3. 賢者キツネを召喚
tmux send-keysで賢者キツネのペイン（neko:specialists.2）に依頼を送信。

```bash
# 読み取り専用モード（リサーチに最適）
tmux send-keys -t neko:specialists.2 "gemini -p '調査依頼' --approval-mode plan"
sleep 1
tmux send-keys -t neko:specialists.2 Enter
```

### 4. 結果の受け取り
賢者キツネが調査レポートを出力。これを元にボスねこが判断、または番猫に指示。

### 5. 報告
調査結果を元に作戦を進める。必要に応じてご主人に報告。

## CLI設定

賢者キツネのCLI設定は `~/.gemini/settings.json` に保存されます：

```json
{
  "security": {
    "auth": {
      "selectedType": "oauth-personal"
    }
  }
}
```

認証方式は OAuth（個人用）が設定されています。

## セッション管理

```bash
# セッション一覧
gemini --list-sessions

# 最新セッションを再開
gemini -r latest

# 特定セッションを再開（番号指定）
gemini -r 5

# セッション削除
gemini --delete-session 3
```

## 注意事項

### 承認モードの選択
- **リサーチ専用**: `--approval-mode plan`（読み取り専用、最も安全）
- **編集含む**: `--approval-mode auto_edit`（編集ツール自動承認）
- **完全自動**: `-y` または `--approval-mode yolo`（全ツール承認、注意して使用）

### Opus節約のため
- まず賢者キツネで概要把握してから深掘りを判断すること
- リアルタイム情報が必要な場合は、賢者キツネが有利
- コード関連の調査は目利きフクロウ（Codex）の方が適切な場合がある
- 深い推論が必要な場合は研究狸を先に検討すること

### 役割の明確化
- 賢者キツネはリサーチ専門であり、実装やレビューは行わない
- コードの修正・実装が必要な場合は、別のエージェントに委譲
- 複数回の対話が必要な場合は `-i` オプションを使用

### パフォーマンス
- ワンショット調査: `-p` オプション（高速）
- 対話的調査: `-i` オプション（柔軟性）
- 出力形式: `--output-format json` でプログラム処理可能
