# Report Templates

## v4 コンテキスト保護ルール（全 Teammate 必須）

### SendMessage ルール
完了報告の SendMessage は **1行サマリーのみ**。全文は output/logs/ に保存する。

```
【必須】完了時の SendMessage:
1. 全文は output/logs/{日時}_{agent}_{task-summary}.md に Write する
2. SendMessage の content は以下のフォーマットのみ:
   "✅ {タスク名} 完了。{1行サマリー}。詳細: output/logs/{ファイル名}"
3. 全文を SendMessage に含めてはいけない（コンテキスト爆発防止）
```

### output/logs/ ファイル命名規則
- フォーマット: `YYYY-MM-DD_HHMM_{agent}_{task-summary}.md`
- 例: `2026-02-19_1430_kitten-backend_api-impl.md`
- agent 名はハイフン区切り（kitten-backend, kitten-codex-bridge 等）
- task-summary は英語、ハイフン区切り、20文字以内

### 全文保存テンプレート（output/logs/ に保存する内容）
以下の「Teammate 完了報告フォーマット」をそのまま使用する。

## Lead 完了報告テンプレート

```markdown
## 作戦完了報告にゃ〜

### 結果サマリー
- 作戦: {作戦名}
- 状態: ✅ 完了 / ⚠️ 部分完了 / ❌ 失敗
- 成果物: {主な成果物}

### スキル化候補
| スキル名 | スコア | 推奨 |
|---------|--------|------|
| {名前} | {N}/20 | ✅/❌ |

### 改善提案（戦略レベル）
| タイプ | 提案 | 優先度 | 期待効果 |
|--------|------|--------|---------|
| {architecture/workflow/automation/cost} | {提案} | high/medium/low | {効果} |

### Teammate からの改善提案
- {集約した提案}

### 💡 ご主人への気づき（TAP レポート）
| 観点 | 発見 | 推奨アクション |
|------|------|---------------|
| 深掘り | {発見} | {アクション} |
| リスク | {発見} | {アクション} |
| 類推 | {発見} | {アクション} |
| スケール | {発見} | {アクション} |
```

## Teammate 完了報告フォーマット（必須項目）

```markdown
## 完了報告

### 実装内容
- {実装した内容}

### テスト結果
- passed: {N}, failed: {N}

### 修正ファイル
- {ファイルパスリスト}

### 🎯 skill_candidate（必須: F009）
- スキル名: {名前}【{スコア}/20点】{推奨判定}
  - 再利用性: {1-5}/5
  - 反復頻度: {1-5}/5
  - 複雑さ: {1-5}/5
  - 汎用性: {1-5}/5

### 💡 improvement_proposals（必須: F010）
| タイプ | 提案 | 優先度 |
|--------|------|--------|
| {security/code_quality/performance/docs/test} | {提案内容} | high/medium/low |
```
