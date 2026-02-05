# Hybrid PPTX Generation Skill

PowerPoint生成の統合スキル。Markdown（Marp形式）と既存PPTXテンプレート、どちらからでも編集可能なPPTXを生成する。

## トリガーワード

このスキルは以下のキーワードで起動：
- `/hybrid-pptx`
- `/pptx`
- "PPTXを作成"
- "パワーポイント作成"
- "プレゼン資料作成"

## 概要

このスキルは、2つの異なる入力形式から最終的に**編集可能なPPTX**を生成します：

1. **Markdown入力モード**: Marp形式のMarkdownからPPTXを生成
2. **既存PPTX入力モード**: 既存PPTXをテンプレートとして流用

どちらのモードも、最終成果物は **Microsoft PowerPointで開いて編集できるPPTXファイル** です。

## 使用方法

### ユーザーからの依頼例

```
/hybrid-pptx Markdownから新規プレゼンを作成してください。テーマは「AIの未来」で10枚程度。
```

```
/pptx 既存のtemplate.pptxを使って、新しいプレゼンを作成してください。
```

---

# ワークフロー1: Markdown入力モード

Marp形式のMarkdownから、HTMLを経由してPPTXを生成します。

## 処理フロー

```
Marp Markdown作成
    ↓
HTML変換（marp-core）
    ↓
PPTX生成（html2pptx）
    ↓
編集可能なPPTX出力
```

## ステップバイステップ手順

### STEP 1: Marpスライド構成の考案

**使用スキル**: `marp-slide-generator`

marp-slide-generator スキルを参照して、プロフェッショナルなスライド構成を考案します：

- スライド枚数: 10-15枚（ユーザー指定に従う）
- 構成テクニック:
  - セクション区切りスライド（3-4枚ごと）
  - 箇条書き（1スライド3-5項目）
  - 表、引用、ハイライトを織り交ぜる
  - 参考文献スライド（最後）

**システムプロンプト**（marp-slide-generator/SKILL.mdから引用）：

```
あなたはプロフェッショナルなスライド作成AIアシスタントです。

## 役割
ユーザーの指示に基づいて、Marp形式のマークダウンでスライドを作成・編集します。

## スライド作成ルール
- フロントマターには以下を含める：
  ---
  marp: true
  theme: border  # またはdefault
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
```

### STEP 2: Marp Markdown作成

**出力例**:

```markdown
---
marp: true
theme: default
size: 16:9
paginate: true
---

<!-- _paginate: skip -->
# AIの未来
### 2026年の展望 — 発表者名

---
<!-- _backgroundColor: #2c3e50 -->
<!-- _color: white -->
## セクション1: 現状分析

---
## AI技術の進化

- 大規模言語モデルの急速な発展
- マルチモーダルAIの実用化
- エッジAIの普及
- 説明可能なAIへのシフト

---
## 主要技術の比較

| 技術 | 強み | 課題 |
|------|------|------|
| LLM | 汎用性 | コスト |
| CV | 精度 | データ要件 |
| RL | 最適化 | 学習時間 |

---
## 専門家の見解

> **重要なポイント**
>
> AIは単なるツールではなく、
> ビジネスモデルそのものを変革する。

---
<!-- _backgroundColor: #2c3e50 -->
<!-- _color: white -->
## セクション2: 将来展望

---
## 2026年のトレンド予測

- ==AGIへの道筋==が明確化
- 規制フレームワークの整備
- **産業別AIの特化**が進行
- *倫理的AI*の重要性増大

---
<!-- _class: tinytext -->
## 参考文献

- 出典1: AIトレンドレポート2026（https://example.com/1）
- 出典2: 技術動向調査（https://example.com/2）
```

**ファイル保存**: `workspace/slides.md`

### STEP 3: HTML変換（オプション）

Marp CoreでMarkdownをHTMLに変換する場合：

```javascript
// test-marp-html.js
const { Marp } = require('@marp-team/marp-core');
const fs = require('fs');

const marp = new Marp();
const markdown = fs.readFileSync('workspace/slides.md', 'utf8');
const { html, css } = marp.render(markdown);

const fullHtml = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Slides</title>
  <style>${css}</style>
</head>
<body>
${html}
</body>
</html>`;

fs.writeFileSync('workspace/slides.html', fullHtml, 'utf8');
console.log('HTML生成完了: workspace/slides.html');
```

```bash
node test-marp-html.js
```

### STEP 4: PPTX生成（html2pptx使用）

**使用ツール**: `knowledge/ppt/html2pptx.md`

HTMLスライドからPPTXを生成します。

**前提条件**:
```bash
# html2pptxライブラリを展開
mkdir -p html2pptx && tar -xzf knowledge/ppt/html2pptx.tgz -C html2pptx
```

**生成スクリプト例**:

```javascript
// generate-pptx.js
const pptxgen = require('pptxgenjs');
const { html2pptx } = require('./html2pptx');
const fs = require('fs');

async function createPresentation() {
  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';
  pptx.author = 'Your Name';
  pptx.title = 'AIの未来';

  // Marp HTMLをPPTXに変換
  // 注意: Marp HTMLは複数スライドが1ファイルに含まれているため、
  // スライドごとに分割したHTMLファイルを作成する必要があります

  // 代替案: Markdownを直接解析してスライドごとにHTMLを生成
  const markdown = fs.readFileSync('workspace/slides.md', 'utf8');
  const slides = markdown.split(/\n---\n/);

  for (let i = 0; i < slides.length; i++) {
    const slideMarkdown = slides[i];

    // 各スライドをHTML化してPPTXに追加
    // （簡易実装例 - 実際はMarpのレンダリング結果を使用）
    const slideHtml = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <style>
          body { width: 960px; height: 540px; }
          h1 { font-size: 40px; text-align: center; margin-top: 200px; }
          h2 { font-size: 32px; margin-top: 50px; }
          ul { font-size: 20px; line-height: 1.6; }
        </style>
      </head>
      <body>
        ${convertMarkdownToHtml(slideMarkdown)}
      </body>
      </html>
    `;

    fs.writeFileSync(`workspace/slide-${i}.html`, slideHtml);
    await html2pptx(`workspace/slide-${i}.html`, pptx);
  }

  await pptx.writeFile({ fileName: 'workspace/presentation.pptx' });
  console.log('PPTX生成完了: workspace/presentation.pptx');
}

// 簡易Markdown→HTML変換（実際はMarp Coreを使用推奨）
function convertMarkdownToHtml(markdown) {
  // タイトル変換
  let html = markdown.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');

  // 箇条書き変換
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

  return html;
}

createPresentation().catch(console.error);
```

**実行**:
```bash
NODE_PATH="$(npm root -g)" node generate-pptx.js 2>&1
```

### STEP 5: 視覚的検証

生成されたPPTXを画像化して確認します：

```bash
# PPTX → PDF
soffice --headless --convert-to pdf workspace/presentation.pptx

# PDF → 画像
pdftoppm -jpeg -r 150 workspace/presentation.pdf workspace/slide
```

**確認項目**:
- テキスト切れ・重なり
- コントラスト・読みやすさ
- 位置・整列

問題があれば、HTMLを修正して再生成します。

---

# ワークフロー2: 既存PPTX入力モード

既存のPPTXをテンプレートとして、スライドを複製・並べ替え・テキスト置換します。

## 処理フロー

```
既存PPTXテンプレート
    ↓
サムネイル作成（thumbnail.py）
    ↓
スライド選択・並べ替え（rearrange.py）
    ↓
テキスト抽出（inventory.py）
    ↓
テキスト置換（replace.py）
    ↓
編集可能なPPTX出力
```

## ステップバイステップ手順

### STEP 1: テンプレートの視覚的分析

**使用ツール**: `knowledge/ppt/thumbnail.py`

サムネイルグリッドを作成して、テンプレートの全体像を把握します：

```bash
python knowledge/ppt/thumbnail.py template.pptx workspace/thumbnails
```

**出力**: `workspace/thumbnails.jpg`（または `thumbnails-1.jpg`, `thumbnails-2.jpg` 等）

**確認項目**:
- スライドレイアウトのパターン
- タイトルスライド、コンテンツスライド、セクション区切り
- 画像プレースホルダーの位置
- デザインの一貫性

**テキスト抽出**:
```bash
python -m markitdown template.pptx > workspace/template-content.md
```

### STEP 2: テンプレート在庫分析

サムネイルとテキスト抽出結果を見て、テンプレート在庫を作成します：

**在庫ファイル例** (`workspace/template-inventory.md`):

```markdown
# Template Inventory Analysis

**Total Slides: 73**
**IMPORTANT: Slides are 0-indexed (first slide = 0, last slide = 72)**

## タイトル・カバースライド
- Slide 0: タイトル + サブタイトル（中央配置）

## 1カラムレイアウト
- Slide 34: B1 - タイトル + 本文（箇条書き対応）
- Slide 35: B2 - タイトル + 本文（段落テキスト）

## 2カラムレイアウト
- Slide 45: D1 - タイトル + 2カラム（左右テキスト）
- Slide 46: D2 - タイトル + 画像 + テキスト

## 引用・強調
- Slide 50: E1 - 大きな引用スライド（中央配置）

## クロージング
- Slide 52: F2 - クロージング + テキスト
```

### STEP 3: プレゼンテーション構成案の作成

在庫分析を基に、新しいプレゼンの構成を考えます：

**構成案** (`workspace/outline.md`):

```markdown
# 新規プレゼンテーション構成案

## スライド構成（6枚）

1. タイトルスライド
   - テンプレート: Slide 0
   - 内容: タイトル「AIの未来」、サブタイトル「2026年の展望」

2. 現状分析
   - テンプレート: Slide 34（B1: タイトル + 本文）
   - 内容: AI技術の進化（箇条書き4項目）

3. 技術比較
   - テンプレート: Slide 34（B1: 再利用）
   - 内容: 主要技術の比較（箇条書き）

4. 専門家の見解
   - テンプレート: Slide 50（E1: 引用）
   - 内容: 重要なポイントを引用形式で強調

5. 将来展望
   - テンプレート: Slide 34（B1: 再利用）
   - 内容: 2026年のトレンド予測

6. まとめ
   - テンプレート: Slide 52（F2: クロージング）
   - 内容: 結論とネクストステップ

## テンプレートマッピング
template_mapping = [0, 34, 34, 50, 34, 52]
```

### STEP 4: スライド並べ替え

**使用ツール**: `knowledge/ppt/rearrange.py`

テンプレートから必要なスライドを抽出し、並べ替えます：

```bash
python knowledge/ppt/rearrange.py template.pptx workspace/working.pptx 0,34,34,50,34,52
```

**結果**: `workspace/working.pptx`（6枚のスライド）

**注意**:
- スライド番号は0始まり（最初のスライドは0）
- 同じ番号を繰り返すとスライドが複製される
- 未使用のスライドは自動的に削除される

### STEP 5: テキスト抽出（inventory）

**使用ツール**: `knowledge/ppt/inventory.py`

並べ替え後のPPTXからすべてのテキストとプロパティを抽出します：

```bash
python knowledge/ppt/inventory.py workspace/working.pptx workspace/text-inventory.json
```

**出力**: `workspace/text-inventory.json`

**JSON構造例**:

```json
{
  "slide-0": {
    "shape-0": {
      "placeholder_type": "TITLE",
      "left": 1.5,
      "top": 2.0,
      "width": 7.5,
      "height": 1.2,
      "default_font_size": 40.0,
      "paragraphs": [
        {
          "text": "テンプレートのタイトル",
          "alignment": "CENTER",
          "bold": true,
          "font_size": 44.0
        }
      ]
    },
    "shape-1": {
      "placeholder_type": "SUBTITLE",
      "left": 1.5,
      "top": 3.5,
      "width": 7.5,
      "height": 0.8,
      "paragraphs": [
        {
          "text": "サブタイトル",
          "alignment": "CENTER"
        }
      ]
    }
  },
  "slide-1": {
    "shape-0": {
      "placeholder_type": "TITLE",
      "paragraphs": [
        {
          "text": "スライドタイトル",
          "bold": true
        }
      ]
    },
    "shape-1": {
      "placeholder_type": "BODY",
      "paragraphs": [
        {
          "text": "箇条書き項目1",
          "bullet": true,
          "level": 0
        },
        {
          "text": "箇条書き項目2",
          "bullet": true,
          "level": 0
        }
      ]
    }
  }
}
```

### STEP 6: 置換テキストの生成

在庫JSONを基に、置換テキストを作成します：

**置換JSON** (`workspace/replacement-text.json`):

```json
{
  "slide-0": {
    "shape-0": {
      "paragraphs": [
        {
          "text": "AIの未来",
          "alignment": "CENTER",
          "bold": true
        }
      ]
    },
    "shape-1": {
      "paragraphs": [
        {
          "text": "2026年の展望",
          "alignment": "CENTER"
        }
      ]
    }
  },
  "slide-1": {
    "shape-0": {
      "paragraphs": [
        {
          "text": "AI技術の進化",
          "bold": true
        }
      ]
    },
    "shape-1": {
      "paragraphs": [
        {
          "text": "大規模言語モデルの急速な発展",
          "bullet": true,
          "level": 0
        },
        {
          "text": "マルチモーダルAIの実用化",
          "bullet": true,
          "level": 0
        },
        {
          "text": "エッジAIの普及",
          "bullet": true,
          "level": 0
        },
        {
          "text": "説明可能なAIへのシフト",
          "bullet": true,
          "level": 0
        }
      ]
    }
  },
  "slide-2": {
    "shape-0": {
      "paragraphs": [
        {
          "text": "主要技術の比較",
          "bold": true
        }
      ]
    },
    "shape-1": {
      "paragraphs": [
        {
          "text": "LLM: 汎用性が高いが、コストが課題",
          "bullet": true,
          "level": 0
        },
        {
          "text": "CV: 精度向上したが、データ要件が厳しい",
          "bullet": true,
          "level": 0
        },
        {
          "text": "RL: 最適化能力は優秀だが学習時間が長い",
          "bullet": true,
          "level": 0
        }
      ]
    }
  },
  "slide-3": {
    "shape-0": {
      "paragraphs": [
        {
          "text": "専門家の見解",
          "bold": true
        }
      ]
    },
    "shape-1": {
      "paragraphs": [
        {
          "text": "AIは単なるツールではなく、ビジネスモデルそのものを変革する。",
          "alignment": "CENTER",
          "font_size": 28.0,
          "italic": true
        }
      ]
    }
  },
  "slide-4": {
    "shape-0": {
      "paragraphs": [
        {
          "text": "2026年のトレンド予測",
          "bold": true
        }
      ]
    },
    "shape-1": {
      "paragraphs": [
        {
          "text": "AGIへの道筋が明確化",
          "bullet": true,
          "level": 0
        },
        {
          "text": "規制フレームワークの整備",
          "bullet": true,
          "level": 0
        },
        {
          "text": "産業別AIの特化が進行",
          "bullet": true,
          "level": 0
        },
        {
          "text": "倫理的AIの重要性増大",
          "bullet": true,
          "level": 0
        }
      ]
    }
  },
  "slide-5": {
    "shape-0": {
      "paragraphs": [
        {
          "text": "まとめ",
          "bold": true
        }
      ]
    },
    "shape-1": {
      "paragraphs": [
        {
          "text": "AI技術は急速に進化し、2026年にはさらなる変革が期待される。",
          "alignment": "CENTER"
        },
        {
          "text": "Next Step: 戦略的投資と人材育成",
          "alignment": "CENTER",
          "bold": true,
          "color": "4472C4"
        }
      ]
    }
  }
}
```

**重要な注意点**:
- `"bullet": true` の場合、テキストに箇条書き記号（•, -, *）を含めない
- `"bullet": true` の時は `"level": 0` を必ず含める
- 置換JSONに含まれないshapeは自動的にクリアされる
- プロパティは在庫JSONから継承（bold, alignment等）

### STEP 7: テキスト置換の適用

**使用ツール**: `knowledge/ppt/replace.py`

置換テキストを適用してPPTXを生成します：

```bash
python knowledge/ppt/replace.py workspace/working.pptx workspace/replacement-text.json workspace/output.pptx
```

**結果**: `workspace/output.pptx`（編集可能なPPTX）

**検証**:
- スクリプトが在庫と置換JSONを自動検証
- 存在しないshapeを参照するとエラーが表示される
- オーバーフローが悪化した場合も警告が表示される

### STEP 8: 視覚的検証

生成されたPPTXを画像化して確認します：

```bash
# PPTX → PDF
soffice --headless --convert-to pdf workspace/output.pptx

# PDF → 画像
pdftoppm -jpeg -r 150 workspace/output.pdf workspace/slide
```

**確認項目**:
- テキスト切れ・重なり
- プレースホルダーの適切な使用
- レイアウトの一貫性

---

# 依存関係

## Pythonパッケージ

```bash
pip install "markitdown[pptx]"  # テキスト抽出
pip install defusedxml           # XML解析
```

## Node.jsパッケージ

```bash
# Marp Core/CLI
npm install @marp-team/marp-core
npm install -g @marp-team/marp-cli

# PPTX生成
npm install -g pptxgenjs
npm install -g playwright
npm install -g react-icons react react-dom
```

## システムツール

```bash
# LibreOffice（PDF変換）
sudo apt-get install libreoffice

# Poppler（PDF→画像変換）
sudo apt-get install poppler-utils
```

---

# 実装例

## 例1: Markdown入力モードの完全な流れ

```bash
# 1. Marp Markdownを作成（手動またはmarp-slide-generatorスキル使用）
# workspace/slides.md

# 2. html2pptxライブラリを展開
mkdir -p html2pptx && tar -xzf knowledge/ppt/html2pptx.tgz -C html2pptx

# 3. 生成スクリプトを実行
NODE_PATH="$(npm root -g)" node generate-pptx.js 2>&1

# 4. 視覚的検証
soffice --headless --convert-to pdf workspace/presentation.pptx
pdftoppm -jpeg -r 150 workspace/presentation.pdf workspace/slide
```

## 例2: 既存PPTX入力モードの完全な流れ

```bash
# 1. サムネイル作成
python knowledge/ppt/thumbnail.py template.pptx workspace/thumbnails

# 2. テキスト抽出
python -m markitdown template.pptx > workspace/template-content.md

# 3. スライド並べ替え
python knowledge/ppt/rearrange.py template.pptx workspace/working.pptx 0,34,34,50,34,52

# 4. テキスト抽出（inventory）
python knowledge/ppt/inventory.py workspace/working.pptx workspace/text-inventory.json

# 5. 置換テキスト作成（手動でJSONを編集）
# workspace/replacement-text.json

# 6. テキスト置換適用
python knowledge/ppt/replace.py workspace/working.pptx workspace/replacement-text.json workspace/output.pptx

# 7. 視覚的検証
soffice --headless --convert-to pdf workspace/output.pptx
pdftoppm -jpeg -r 150 workspace/output.pdf workspace/slide
```

---

# トラブルシューティング

## Markdown入力モード

**問題**: Marp HTMLが1ファイルに複数スライド含まれている

**解決策**: スライドごとにHTML分割するか、Markdownを直接解析してhtml2pptxに渡す

**問題**: テキストが切れる、重なる

**解決策**: HTMLのマージンを増やす、フォントサイズを減らす、レイアウトを見直す

## 既存PPTX入力モード

**問題**: スライド番号が範囲外

**解決策**: 0始まりで、最大は（総スライド数 - 1）。例: 73枚なら0-72

**問題**: 置換JSONのshapeが存在しない

**解決策**: text-inventory.jsonで利用可能なshapeを確認する

**問題**: テキストオーバーフロー

**解決策**: テキストを短くする、フォントサイズを小さくする、レイアウトを変更する

---

# 関連スキル

- `marp-slide-generator` - Marpスライド自動生成
- `marp-theme-customizer` - Marpカスタムテーマ作成
- `ppt` - PPT生成（3つのワークフロー）

---

# バージョン情報

- Marp Core: 4.2.0+
- Marp CLI: 最新版
- PptxGenJS: 最新版
- Python: 3.8+
- Node.js: 18+

---

# まとめ

このスキルは、Markdownと既存PPTXの両方から**編集可能なPPTX**を生成できます。

- **Markdown入力モード**: デザイン自由度が高く、プログラマブルな生成が可能
- **既存PPTX入力モード**: テンプレートデザインを保持しながら効率的に作成

どちらのモードも、最終的に**Microsoft PowerPointで開いて編集できる**PPTXファイルを出力します。
