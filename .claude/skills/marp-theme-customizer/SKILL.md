# Marp Theme Customizer Skill

Marpカスタムテーマ（CSS）の作成・編集スキル。

## トリガーワード

このスキルは以下のキーワードで起動：
- `/marp-theme`
- "Marpテーマ作成"
- "スライドデザインカスタマイズ"
- "Marp CSSカスタマイズ"

## 概要

Marpスライドのカスタムテーマ（CSS）を作成・編集します。セクション区切りスライド、小文字クラス（参考文献用）、ハイライト、引用等のスタイルをカスタマイズできます。

## 主要機能

### 1. カスタムテーマ作成
- 新規テーマCSS作成
- 既存テーマのカスタマイズ
- borderテーマをベースにした派生テーマ

### 2. スタイル定義
- 背景・文字色のカスタマイズ
- フォント設定
- セクション区切りスライドのスタイル
- 小文字クラス（tinytext）
- ハイライト・引用のスタイル

### 3. レスポンシブデザイン
- スライドサイズ対応（16:9, 4:3）
- フォントサイズ調整
- レイアウト最適化

## 使用方法

### 基本的な使い方

```
/marp-theme borderテーマをベースに、青系の配色でカスタムテーマを作成してください
```

### 詳細指定

```
/marp-theme
ベーステーマ: border
配色: 青系（#2c3e50, #3498db）
フォント: Noto Sans JP
特殊クラス: tinytext, highlight, emphasis
```

## Marpテーマの基本構造

### テーマファイル（CSS）

```css
/* @theme custom-theme */

@import "default";

:root {
  font-family: 'Noto Sans JP', sans-serif;
  --border-color: #303030;
  --text-color: #0a0a0a;
  --bg-color-alt: #dadada;
  --mark-background: #ffef92;
}

section {
  background-image: linear-gradient(to bottom right, #f7f7f7 0%, #d3d3d3 100%);
  border: 1.3em solid var(--border-color);
  outline: 1em solid #ffffff;
  outline-offset: -0.5em;
}

h1, h2, h3, h4, h5, h6 {
  color: var(--text-color);
}

code {
  background-color: rgba(100, 100, 100, 0.2);
}

blockquote {
  background: var(--bg-color-alt);
  border-left: 10px solid var(--border-color);
  margin: 0.5em;
  padding: 0.5em;
}

mark {
  background-color: var(--mark-background);
  padding: 0 2px 2px;
  border-radius: 4px;
  margin: 0 2px;
}

/* 小文字クラス（参考文献用） */
section.tinytext > p,
section.tinytext > ul,
section.tinytext > blockquote {
  font-size: 0.65em;
}
```

## カスタマイズ可能な要素

### 1. 配色

**CSS変数で定義:**
```css
:root {
  --border-color: #303030;      /* ボーダー色 */
  --text-color: #0a0a0a;        /* テキスト色 */
  --bg-color-alt: #dadada;      /* 背景色（引用等） */
  --mark-background: #ffef92;   /* ハイライト背景色 */
}
```

**配色例:**
- **青系**: `--border-color: #2c3e50;`, `--mark-background: #3498db;`
- **緑系**: `--border-color: #27ae60;`, `--mark-background: #2ecc71;`
- **赤系**: `--border-color: #c0392b;`, `--mark-background: #e74c3c;`

### 2. フォント

```css
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap');

:root {
  font-family: 'Noto Sans JP', sans-serif;
}
```

**フォント例:**
- **Inter**: Google Fonts（英語向け、モダン）
- **Noto Sans JP**: Google Fonts（日本語対応）
- **Roboto**: Google Fonts（読みやすい）

### 3. 背景グラデーション

```css
section {
  background-image: linear-gradient(to bottom right, #f7f7f7 0%, #d3d3d3 100%);
}
```

**グラデーション例:**
- **青系**: `linear-gradient(to bottom right, #ebf5fb 0%, #aed6f1 100%);`
- **緑系**: `linear-gradient(to bottom right, #e8f8f5 0%, #a9dfbf 100%);`

### 4. ボーダースタイル

```css
section {
  border: 1.3em solid var(--border-color);
  outline: 1em solid #ffffff;
  outline-offset: -0.5em;
}
```

### 5. ページ番号

```css
section::after {
  font-size: 0.75em;
  content: attr(data-marpit-pagination) " / " attr(data-marpit-pagination-total);
}
```

### 6. 引用ブロック

```css
blockquote {
  background: var(--bg-color-alt);
  border-left: 10px solid var(--border-color);
  margin: 0.5em;
  padding: 0.5em;
}
```

### 7. ハイライト

```css
mark {
  background-color: var(--mark-background);
  padding: 0 2px 2px;
  border-radius: 4px;
  margin: 0 2px;
}
```

### 8. カスタムクラス

```css
/* 小文字クラス（参考文献用） */
section.tinytext > p,
section.tinytext > ul,
section.tinytext > blockquote {
  font-size: 0.65em;
}

/* 強調クラス */
section.emphasis {
  background-color: #fff3cd;
  border-color: #ffc107;
}

/* センタリングクラス */
section.center {
  display: flex;
  justify-content: center;
  align-items: center;
  text-align: center;
}
```

## 実装例

### borderテーマ（参考）

```css
/* @theme border */
/* Author: rnd195 https://github.com/rnd195/ */

@import "default";
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');

:root {
  font-family: Inter, Helvetica, Arial;
  --border-color: #303030;
  --text-color: #0a0a0a;
  --bg-color-alt: #dadada;
  --mark-background: #ffef92;
}

section {
  background-image: linear-gradient(to bottom right, #f7f7f7 0%, #d3d3d3 100%);
  border: 1.3em solid var(--border-color);
  outline: 1em solid #ffffff;
  outline-offset: -0.5em;
}

h1, h2, h3, h4, h5, h6 {
  color: var(--text-color);
}

code {
  background-color: rgba(100, 100, 100, 0.2);
}

section::after {
  font-size: 0.75em;
  content: attr(data-marpit-pagination) " / " attr(data-marpit-pagination-total);
}

/* 画像センタリング */
img[alt~="center"] {
  display: block;
  margin: 0 auto;
}

blockquote {
  background: var(--bg-color-alt);
  border-left: 10px solid var(--border-color);
  margin: 0.5em;
  padding: 0.5em;
}

mark {
  background-color: var(--mark-background);
  padding: 0 2px 2px;
  border-radius: 4px;
  margin: 0 2px;
}

section.tinytext > p,
section.tinytext > ul,
section.tinytext > blockquote {
  font-size: 0.65em;
}
```

### 青系カスタムテーマ

```css
/* @theme blue-modern */

@import "default";
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap');

:root {
  font-family: 'Noto Sans JP', sans-serif;
  --border-color: #2c3e50;
  --text-color: #2c3e50;
  --bg-color-alt: #ebf5fb;
  --mark-background: #3498db;
  --accent-color: #3498db;
}

section {
  background-image: linear-gradient(to bottom right, #ffffff 0%, #ebf5fb 100%);
  border: 1.3em solid var(--border-color);
  outline: 1em solid #ffffff;
  outline-offset: -0.5em;
}

h1, h2, h3, h4, h5, h6 {
  color: var(--border-color);
}

h1 {
  border-bottom: 3px solid var(--accent-color);
  padding-bottom: 0.3em;
}

code {
  background-color: rgba(52, 152, 219, 0.1);
  color: var(--accent-color);
  padding: 2px 6px;
  border-radius: 3px;
}

blockquote {
  background: var(--bg-color-alt);
  border-left: 10px solid var(--accent-color);
  margin: 0.5em;
  padding: 0.5em;
}

mark {
  background-color: var(--mark-background);
  color: #ffffff;
  padding: 2px 6px;
  border-radius: 4px;
  margin: 0 2px;
}

section.tinytext > p,
section.tinytext > ul,
section.tinytext > blockquote {
  font-size: 0.65em;
}
```

## テーマの使用方法

### Markdownでテーマを指定

```markdown
---
marp: true
theme: blue-modern
size: 16:9
paginate: true
---
```

### Marp CLIでテーマを適用

```bash
# カスタムテーマCSSを指定してPDF生成
marp slide.md --theme blue-modern.css --pdf -o slide.pdf
```

### プログラムからテーマを適用

```javascript
import { Marp } from '@marp-team/marp-core'
import fs from 'fs'

// カスタムテーマCSSを読み込み
const themeCSS = fs.readFileSync('blue-modern.css', 'utf8')

const marp = new Marp()
marp.themeSet.add(themeCSS)

const { html, css } = marp.render(`---
marp: true
theme: blue-modern
---

# Hello, Marp!
`)
```

## テーマ開発のベストプラクティス

### 1. CSS変数を活用

配色を変数で定義することで、簡単にテーマ変更が可能：

```css
:root {
  --primary-color: #3498db;
  --secondary-color: #2ecc71;
  --text-color: #2c3e50;
  --bg-color: #ffffff;
}

h1 {
  color: var(--primary-color);
}

blockquote {
  border-left-color: var(--secondary-color);
}
```

### 2. レスポンシブデザイン

異なるスライドサイズに対応：

```css
section {
  font-size: 1.5em; /* 16:9 */
}

section[data-size="4:3"] {
  font-size: 1.3em; /* 4:3 */
}
```

### 3. カスタムクラスの活用

用途別にクラスを定義：

```css
/* 参考文献用 */
section.tinytext { font-size: 0.65em; }

/* 強調用 */
section.emphasis { background-color: #fff3cd; }

/* センタリング用 */
section.center {
  display: flex;
  justify-content: center;
  align-items: center;
}
```

## トラブルシューティング

### テーマが適用されない

**問題:** カスタムテーマが反映されない

**解決策:**
1. `/* @theme テーマ名 */` がCSSファイルの先頭にあるか確認
2. Frontmatterの `theme` とテーマ名が一致しているか確認
3. `--theme` オプションでCSSファイルを指定

### 日本語フォントが表示されない

**問題:** 日本語が豆腐（□）になる

**解決策:**
1. Google Fontsから日本語フォントを読み込み（Noto Sans JP等）
2. PDF生成時に日本語フォントがインストールされているか確認

### ページ番号が表示されない

**問題:** ページ番号が表示されない

**解決策:**
```css
section::after {
  content: attr(data-marpit-pagination) " / " attr(data-marpit-pagination-total);
}
```

## 参考資料

- Marp公式テーマギャラリー: https://github.com/marp-team/marp-core/tree/main/themes
- borderテーマ: https://github.com/rnd195/my-marp-themes
- CSS変数: https://developer.mozilla.org/ja/docs/Web/CSS/Using_CSS_custom_properties

## 関連スキル

- `marp-slide-generator` - Marpスライド自動生成
- `bedrock-agentcore-integration` - Bedrock AgentCore統合

## バージョン情報

- Marp Core: 4.2.0+
- CSS: CSS3
