# Memory MCP 導入手順書

## 概要

Memory MCP（知識グラフ記憶）を導入することで、セッションを跨いで以下の情報を記憶できるにゃ：

- ご主人の好み・傾向
- 重要な意思決定と理由
- プロジェクト横断の知見
- 解決した問題と解決方法

## 設定手順

### 1. ~/.claude/settings.json に追加

```json
{
  "mcpServers": {
    "memory": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    }
  }
}
```

### 2. 既存の設定がある場合

既存の `mcpServers` セクションに追加するにゃ：

```json
{
  "mcpServers": {
    "既存のサーバー": {
      // 既存の設定
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-memory"]
    }
  }
}
```

### 3. Claude Code を再起動

設定を反映するために Claude Code を再起動するにゃ。

## 使用方法

### セッション開始時（必須）

各エージェントはセッション開始時に必ず記憶を読み込むにゃ：

```bash
# まずツールをロード
ToolSearch("select:mcp__memory__read_graph")

# 記憶を読み込み
mcp__memory__read_graph()
```

### 記憶を保存するタイミング

| タイミング | 例 | アクション |
|------------|-----|-----------|
| ご主人が好みを表明 | 「シンプルがいい」「これ嫌い」 | add_observations |
| 重要な意思決定 | 「この方式採用」「この機能不要」 | create_entities |
| 問題が解決 | 「原因はこれだった」 | add_observations |
| ご主人が「覚えて」と言った | 明示的な指示 | create_entities |

### MCPツールの使い方

```bash
# ツールをロード（初回のみ）
ToolSearch("select:mcp__memory__read_graph")
ToolSearch("select:mcp__memory__create_entities")
ToolSearch("select:mcp__memory__add_observations")

# 読み込み
mcp__memory__read_graph()

# 新規エンティティ作成
mcp__memory__create_entities(entities=[
  {"name": "ご主人", "entityType": "user", "observations": ["シンプル好き"]}
])

# 既存エンティティに追加
mcp__memory__add_observations(observations=[
  {"entityName": "ご主人", "contents": ["新しい好み"]}
])
```

## 記憶すべきもの / しないもの

### ✅ 記憶すべき

| カテゴリ | 例 |
|----------|-----|
| ご主人の好み | 「シンプル好き」「過剰機能嫌い」等 |
| 重要な意思決定 | 「YAML Front Matter採用の理由」等 |
| プロジェクト横断の知見 | 「この手法がうまくいった」等 |
| 解決した問題 | 「このバグの原因と解決法」等 |

### ❌ 記憶しないもの

| カテゴリ | 理由 | 代替 |
|----------|------|------|
| 一時的なタスク詳細 | すぐに古くなる | YAML に書く |
| ファイルの中身 | 読めば分かる | 直接読む |
| 進行中タスクの詳細 | 状態が変わる | nawabari.md に書く |

## 保存先

Memory MCP は以下の場所にデータを保存するにゃ：

```
~/.claude/memory/  # デフォルト保存先
```

または、プロジェクト固有の記憶は：

```
{project}/memory/  # プロジェクト内保存
```

## 各エージェントへの指示書追記

### ボスねこ・番猫・子猫の指示書に追加

```markdown
## 起動時の振る舞い

1. Memory MCPから過去の記憶を読み込む：
   - プロジェクト固有の設定
   - 過去の失敗パターン
   - ご主人の好み・方針
2. 自己紹介（役割確認）
3. タスク待機状態に入る
```

### メモリ保存対象セクションを追加

```markdown
## メモリ保存対象

- ✅ ご主人の好み・方針（コーディングスタイル、技術選択等）
- ✅ 過去の失敗パターン（同じ失敗を繰り返さない）
- ✅ プロジェクト固有の設定（ディレクトリ構造、命名規則等）
- ✅ 各猫の役割・制約（誰が何を担当するか）
- ❌ 一時的な状態（現在のタスク進捗等）← nawabari.md に記録
```

## 注意事項

1. **初回起動時は記憶が空**: 最初は何も記憶されていないので、セッション中に徐々に蓄積されるにゃ

2. **コスト**: Memory MCP は追加のAPI呼び出しが発生するので、頻繁な保存は避けるにゃ

3. **プライバシー**: 機密情報は記憶に保存しないように注意するにゃ

4. **重複防止**: 同じ情報を何度も保存しないように、読み込んでから追加するにゃ〜
