# Codex

OpenAI Codex CLIを使用してコードレビュー・分析を実行するスキル。

## トリガー

"codex", "コードレビュー", "レビューして", "分析して", "/codex"

## 実行コマンド

```bash
codex exec --full-auto --sandbox read-only --cd <project_directory> "<request>"
```

## パラメータ

| パラメータ | 説明 |
|-----------|------|
| `--full-auto` | 完全自動モードで実行 |
| `--sandbox read-only` | 読み取り専用サンドボックス（安全な分析用） |
| `--cd <dir>` | 対象プロジェクトのディレクトリ |
| `"<request>"` | 依頼内容（日本語可） |

## 使用例

### コードレビュー
```bash
codex exec --full-auto --sandbox read-only --cd /path/to/project "このプロジェクトのコードをレビューして、改善点を指摘してください"
```

### バグ調査
```bash
codex exec --full-auto --sandbox read-only --cd /path/to/project "認証処理でエラーが発生する原因を調査してください"
```

### リファクタリング提案
```bash
codex exec --full-auto --sandbox read-only --cd /path/to/project "このコードのリファクタリング案を提示してください"
```

### アーキテクチャ分析
```bash
codex exec --full-auto --sandbox read-only --cd /path/to/project "プロジェクト全体のアーキテクチャを分析してください"
```

## 実行手順

1. ユーザーから依頼内容を受け取る
2. 対象プロジェクトのディレクトリを特定（デフォルト: カレントディレクトリ）
3. 上記コマンド形式でCodexを実行
4. 結果をユーザーに報告

## 使用場面

- コードレビュー依頼時
- コードベース全体の分析
- 実装に関する質問
- バグの調査
- リファクタリング提案
- 解消が難しい問題の調査
