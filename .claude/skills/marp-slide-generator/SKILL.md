# Marp Slide Generator Skill

Marp形式のMarkdownでプロフェッショナルなスライドを自動生成するスキル。

## トリガーワード

このスキルは以下のキーワードで起動：
- `/marp`
- "スライド作って"
- "プレゼン作成"
- "Marpスライド生成"
- "スライド資料作成"

## 概要

ユーザーが指定したテーマや題材を基に、Marp形式のMarkdownでスライドを自動生成します。Web検索機能（Tavily API）で最新情報を取得し、高品質なビジネスライクなスライドを作成します。

## 主要機能

### 1. スライド自動生成
- テーマ・題材指定でスライド生成
- ビジネスライクなデザイン（絵文字なし）
- プロフェッショナルな構成

### 2. Web検索機能（オプション）
- Tavily APIで最新情報を取得
- 検索結果をスライドに反映
- 参考文献スライドを自動追加

### 3. 多様なコンテンツ形式
- 箇条書き（1スライド3-5項目）
- 表（比較・一覧）
- 引用ブロック（重要ポイント）
- ハイライト（キーワード強調）

### 4. PDF出力（オプション）
- Marp CLIでPDF生成
- Chromiumベースのレンダリング
- カスタムテーマ適用

## 使用方法

### 基本的な使い方

```
/marp AIについてのプレゼンテーションを10枚程度で作成してください
```

### Web検索を含む場合

```
/marp 最新のAI技術動向についてスライドを作成してください。Web検索で最新情報を取得してください。
```

### 詳細指定

```
/marp
テーマ: クラウドネイティブアーキテクチャ
スライド枚数: 15枚
内容: マイクロサービス、コンテナ、Kubernetesの概要と実例
Web検索: 最新のKubernetes動向を含める
```

## 入力パラメータ

| パラメータ | 説明 | 必須 | デフォルト |
|-----------|------|------|-----------|
| テーマ | スライドのテーマ | ✅ | - |
| 題材 | 具体的な内容・URL | ❌ | テーマから推測 |
| スライド枚数 | 生成するスライド数 | ❌ | 10-15枚 |
| Web検索 | 最新情報取得の要否 | ❌ | 不要 |

## 出力フォーマット

### Marp形式Markdown

```markdown
---
marp: true
theme: border
size: 16:9
paginate: true
---

<!-- _paginate: skip -->
# プレゼンタイトル
### サブタイトル — 発表者名

---
<!-- _backgroundColor: #303030 -->
<!-- _color: white -->
## セクション1

---
## スライドタイトル

- 箇条書き項目1
- 箇条書き項目2
- 箇条書き項目3

---
<!-- _class: tinytext -->
## 参考文献

- 出典1: タイトル（URL）
- 出典2: タイトル（URL）
```

## スライド作成ルール

### Frontmatter（必須）

```yaml
---
marp: true
theme: border
size: 16:9
paginate: true
---
```

### スライド構成

1. **タイトルスライド（1枚目）**
   - タイトル（大見出し `#`）
   - サブタイトル（中見出し `###`）
   - ページ番号スキップ（`<!-- _paginate: skip -->`）

2. **セクション区切りスライド（3-4枚ごと）**
   - 背景色変更（`<!-- _backgroundColor: #303030 -->`）
   - 白文字（`<!-- _color: white -->`）
   - セクション名（`##`）

3. **コンテンツスライド**
   - 箇条書き: 1スライド3-5項目
   - 表: 比較・一覧に使用
   - 引用: 重要ポイントの強調（`> テキスト`）
   - ハイライト: キーワード強調（`==キーワード==`）

4. **参考文献スライド（最後）**
   - 小文字クラス（`<!-- _class: tinytext -->`）
   - 出典リスト

### デザインガイドライン

- ✅ **ビジネスライク**: シンプルで洗練されたデザイン
- ✅ **絵文字禁止**: 絵文字は使用しない
- ✅ **適切な情報量**: 1スライド3-5項目
- ✅ **セクション区切り**: 3-4枚ごとに区切りスライド
- ✅ **多様なコンテンツ**: 箇条書きだけでなく表・引用も使用

## システムプロンプト

以下のシステムプロンプトを使用してスライドを生成：

```
あなたはプロフェッショナルなスライド作成AIアシスタントです。

## 役割
ユーザーの指示に基づいて、Marp形式のマークダウンでスライドを作成・編集します。
デザインや構成についてのアドバイスも積極的に行います。

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

## スライド構成テクニック（必ず従うこと！）
単調な箇条書きの連続を避け、以下のテクニックを織り交ぜてプロフェッショナルなスライドを作成してください。

### セクション区切りスライド【必須】
3〜4枚ごとに、背景色を変えた中タイトルスライドを挟んでセクションを区切る：
```
---
<!-- _backgroundColor: #303030 -->
<!-- _color: white -->
## セクション名
```

### 多様なコンテンツ形式
箇条書きだけでなく、以下を積極的に使い分ける：
- **表（テーブル）**: 比較・一覧に最適
- **引用ブロック**: 重要なポイントや定義の強調に `> テキスト`
- **==ハイライト==**: キーワードの強調に
- **太字・斜体**: `**重要**` や `*補足*`

### 参考文献・出典スライド
Web検索した場合は最後に出典スライドを追加し、文字を小さくする：
```
---
<!-- _class: tinytext -->
## 参考文献
- 出典1: タイトル（URL）
- 出典2: タイトル（URL）
```

## Web検索
最新の情報が必要な場合や、リクエストに不明点がある場合は、web_searchツールを使って調べてからスライドを作成してください。
ユーザーが「〇〇について調べて」「最新の〇〇」などと言った場合は積極的に検索を活用します。
```

## 技術情報

### 依存パッケージ

**Node.js:**
- `@marp-team/marp-core` - Markdown→HTMLスライド変換
- `@marp-team/marp-cli` - PDF生成（オプション）

**インストール:**
```bash
npm install @marp-team/marp-core
npm install -g @marp-team/marp-cli  # PDF生成用
```

### Marp CLIでPDF生成

```bash
marp slide.md --pdf --allow-local-files -o slide.pdf
```

**カスタムテーマ適用:**
```bash
marp slide.md --pdf --theme border.css -o slide.pdf
```

### Markdown → HTML変換

```javascript
import { Marp } from '@marp-team/marp-core'

const marp = new Marp()
const { html, css } = marp.render('# Hello, Marp!')

console.log(html)
```

## 実装例

### スライド生成の基本フロー

```javascript
import { Marp } from '@marp-team/marp-core'
import fs from 'fs'

// Marpインスタンス作成
const marp = new Marp({
  html: true,
  emoji: {
    shortcode: false,
    unicode: true
  }
})

// Markdownを作成
const markdown = `---
marp: true
theme: border
size: 16:9
paginate: true
---

<!-- _paginate: skip -->
# プレゼンタイトル
### サブタイトル — 発表者名

---
<!-- _backgroundColor: #303030 -->
<!-- _color: white -->
## セクション1

---
## スライドタイトル

- 箇条書き項目1
- 箇条書き項目2
- 箇条書き項目3
`

// HTML生成
const { html, css } = marp.render(markdown)

// ファイル出力
fs.writeFileSync('slide.html', html)
console.log('スライドを生成しました: slide.html')
```

### Web検索機能の統合（Tavily API）

```javascript
import { TavilyClient } from 'tavily-python'

async function webSearch(query) {
  const client = new TavilyClient(process.env.TAVILY_API_KEY)

  const results = await client.search({
    query: query,
    max_results: 5,
    search_depth: 'advanced'
  })

  // 検索結果を整形
  const formatted = results.results.map(result => ({
    title: result.title,
    content: result.content,
    url: result.url
  }))

  return formatted
}

// スライドに検索結果を含める
async function generateSlideWithSearch(theme) {
  const searchResults = await webSearch(`${theme} 最新動向`)

  // 検索結果からスライドコンテンツを生成
  let slideContent = `...`

  // 参考文献スライド追加
  slideContent += `
---
<!-- _class: tinytext -->
## 参考文献

${searchResults.map(r => `- ${r.title}（${r.url}）`).join('\n')}
  `

  return slideContent
}
```

## 注意事項

### ビジネスライクなデザイン

- ❌ **絵文字禁止**: ビジネス資料として不適切
- ✅ **シンプル**: 洗練されたデザイン
- ✅ **読みやすさ**: 適切な情報量

### Web検索エラー時の対応

Web検索ツールがエラーを返した場合：
1. エラー原因をユーザーに伝える
2. 一般的な知識や推測でスライド作成せず、検索APIの復旧を待つ
3. スライド作成は行わず、エラー報告のみで終了

### PDF生成の制約

- Chromiumが必要（Marp CLI内部で使用）
- 日本語フォントが必要（`fonts-noto-cjk`等）
- ローカル環境では `--allow-local-files` が必要

## トラブルシューティング

### PDF生成でエラーが出る

**問題:** `marp --pdf` でエラーが発生

**解決策:**
1. Chromiumがインストールされているか確認
2. 日本語フォントがインストールされているか確認
3. `--allow-local-files` オプションを追加

### テーマが適用されない

**問題:** カスタムテーマ（border）が適用されない

**解決策:**
1. Frontmatterに `theme: border` を記載
2. `--theme border.css` オプションでCSSを指定
3. CSSファイルの `/* @theme border */` を確認

## 参考資料

- Marp公式: https://marp.app/
- Marp Core: https://github.com/marp-team/marp-core
- Marp CLI: https://github.com/marp-team/marp-cli
- borderテーマ: https://github.com/rnd195/my-marp-themes

## 関連スキル

- `marp-theme-customizer` - Marpカスタムテーマ作成
- `bedrock-agentcore-integration` - Bedrock AgentCore統合

## バージョン情報

- Marp Core: 4.2.0+
- Marp CLI: 最新版
- Node.js: 18+
