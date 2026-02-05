# Datadog OOTBルールスクレイピングスキル

Datadog Security Detection Rules (OOTB) をスクレイピングしてJSON/CSV化するスキル。

## ナレッジ読み込み

このスキルが呼ばれたら、まず以下を参照：
- `knowledge/scrape-dd-rules/index.md` - 使い方、スクリプト一覧
- `knowledge/scrape-dd-rules/page-structures.md` - ページ構造の違い
- `tools/` - 既存スクリプト

## できること

### 1. OOTBルール一覧取得
- https://docs.datadoghq.com/ja/security/default_rules/ からルールリンク取得
- 全ルールの title, url を収集

### 2. ルール詳細取得
- 各ルールページから Goal, Description, Strategy を抽出
- H2/H3 両方のヘッディング構造に対応
- 並列処理（5ワーカー）で高速化

### 3. ASMルール専用取得
- ASM ルールは特殊な H3 構造
- 7フィールド: goal, required_events, event_tagging, strategy, triage, response, remediation

### 4. カテゴリ分類
- 80+ カテゴリに自動分類
- AWS, Azure, GCP, Kubernetes, Linux, Windows, Authentication など

### 5. 出力形式
- JSON (グループ化/フラット)
- CSV (翻訳用に最適)

## 既存スクリプト

| スクリプト | 用途 |
|-----------|------|
| `scrape-ootb-rules.js` | ルールリンク一覧取得 |
| `scrape-rule-details.js` | Goal/Strategy 詳細取得 |
| `fetch-descriptions.js` | Description セクション取得 |
| `group-rules.js` | カテゴリ分類 |
| `scrape-asm-rules.js` | ASM ルール全セクション取得 |
| `merge-descriptions.js` | データマージ |

## ページ構造

### 通常ルール (H2)
```
H2: Goal
H2: Strategy
H2: Triage and response
```

### ASMルール (H3)
```
H3: Goal
H3: Required business logic events
H3: Strategy
H3: Triage and response
```

### 特殊ケース
- `Rationale` → Goal として扱う
- `Description` → description フィールドに格納
- `Response` + `Remediation` → triage の代替

## 使い方例

```
/scrape-dd-rules 全ルールを取得したい
/scrape-dd-rules ASMルールだけ取得したい
/scrape-dd-rules 特定カテゴリのルールを抽出したい
/scrape-dd-rules 新しいルールが追加されたか確認したい
```

## 出力ファイル

```
tools/
├── ootb-rules-grouped.json    # カテゴリ別全ルール
├── ootb-rules-grouped.csv     # CSV版
├── asm-rules.json             # ASMルール専用
├── asm-rules.csv              # ASM CSV版
└── empty-rules.json           # 未取得ルールリスト
```

## 注意事項

- Playwright (headless Chromium) が必要
- 動的コンテンツのため waitForTimeout が必要
- 大量リクエスト時は並列数を制限（5推奨）
- 全ルール取得は数十分かかる
