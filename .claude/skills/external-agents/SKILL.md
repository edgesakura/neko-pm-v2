# 外部エージェント呼び出しスキル

neko-pm v3 で Claude 以外のモデル（Codex CLI, Gemini CLI）を呼び出すパターン。
Lead または Teammate が Bash 経由で外部エージェントを利用する。

**重要**: `--cd /home/edgesakura` を指定することで、各 CLI のホームディレクトリに
配置されたスキル（`.codex/skills/`, `.gemini/skills/`）が自動で読み込まれる。

---

## 利用可能な外部エージェント

### 🦊 賢者キツネ（sage-fox）

**ツール**: Gemini CLI
**モデル**: Gemini 3 Pro
**スキル**: `~/.gemini/skills/sage-fox/`
**用途**: リサーチ、トレンド調査、概要把握
**特徴**: 高速、情報収集特化

```bash
# リサーチ依頼（ホームディレクトリのスキルが自動読み込み）
gemini --approval-mode full "{依頼内容}"

# 例: 技術調査
gemini --approval-mode full "Next.js 15 の App Router と Pages Router の違いを整理して"
```

### 🦝 研究狸（research-tanuki）

**ツール**: Codex CLI
**モデル**: gpt-5.3-codex
**スキル**: `~/.codex/skills/research-tanuki/`
**用途**: 深掘り調査、アーキテクチャ分析、Lead の相談相手
**特徴**: コードベース分析に強い、仮説→検証プロセス

```bash
# 調査依頼（--cd でホームを指定→スキル読み込み）
codex exec --full-auto --sandbox read-only --cd /home/edgesakura "{依頼内容}"

# 特定プロジェクトを調査する場合もホームを指定
codex exec --full-auto --sandbox read-only --cd /home/edgesakura \
  "~/git/project/ のアーキテクチャを分析して、改善点を提案して"
```

### 🦉 目利きフクロウ（owl-reviewer）

**ツール**: Codex CLI
**モデル**: gpt-5.3-codex
**スキル**: `~/.codex/skills/owl-reviewer/`
**用途**: コードレビュー、セキュリティ監査
**特徴**: OWASP Top 10 チェック、重要度別レポート

```bash
# コードレビュー
codex exec --full-auto --sandbox read-only --cd /home/edgesakura "{レビュー依頼}"

# 例: セキュリティレビュー
codex exec --full-auto --sandbox read-only --cd /home/edgesakura \
  "~/neko-pm/scripts/ のセキュリティレビュー。OWASP Top 10 の観点でチェック"
```

---

## スキル配置

```
/home/edgesakura/
├── .codex/
│   ├── skills/
│   │   ├── research-tanuki/   # 研究狸スキル
│   │   ├── owl-reviewer/      # フクロウスキル
│   │   └── izakaya-backend-ops/
│   └── rules/
│       └── default.rules
└── .gemini/
    └── skills/
        └── sage-fox/          # キツネスキル
```

## リサーチ Teammate パターン

複雑なタスクでは、Teammate の 1 つをリサーチ専任として割り当てる。

```
Lead が Teammate を spawn
    ├─ Teammate A: 実装担当
    ├─ Teammate B: 実装担当
    └─ Teammate C: リサーチ担当
         └─ Bash 経由で codex/gemini を呼び出し
         └─ --cd /home/edgesakura でスキル自動読み込み
         └─ 調査結果を Lead に報告
```

### いつリサーチ Teammate を使うか

- 技術選定が必要な場合（フレームワーク比較、ライブラリ選定）
- 既存コードベースの深い分析が必要な場合
- バグの根本原因調査が必要な場合
- セキュリティレビューが必要な場合

---

## コスト意識

| エージェント | コスト | 使い分け |
|-------------|--------|---------|
| Gemini CLI | 低 | 概要把握、トレンド調査 |
| Codex CLI (gpt-5.3-codex) | 中 | 深い調査・分析・コードレビュー |
| Opus (Task tool) | 高 | 重大な設計判断のみ |

**原則**: 安い方から試す。Gemini → Codex → Opus の順。
