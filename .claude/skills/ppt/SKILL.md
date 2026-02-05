---
name: ppt
description: PowerPointファイルの作成・編集・分析。新規作成、既存編集、テンプレート利用、SRE運用設計資料の自動作成に使用
allowed-tools: Read, Grep, Glob, Bash, Write
---

# PPT生成スキル

PowerPointファイルの作成・編集・分析をサポートするスキル。

## ナレッジ読み込み

このスキルが呼ばれたら、タスクに応じて以下を参照：

| タスク | 読むべきドキュメント |
|--------|---------------------|
| 新規作成 | `knowledge/ppt/html2pptx.md` + `knowledge/ppt/css.md` |
| 既存編集 | `knowledge/ppt/ooxml.md` |
| テンプレート利用 | `knowledge/ppt/SKILL.md` |

**重要**: ドキュメントは最後まで読んでからタスクを開始すること。

## 3つのワークフロー

### 1. 新規作成（html2pptx）
HTMLスライドからPPTXを生成。デザイン自由度が高い。

```bash
# ライブラリ展開
mkdir -p html2pptx && tar -xzf knowledge/ppt/html2pptx.tgz -C html2pptx

# HTML作成 → PPTX生成（Node.js）
NODE_PATH="$(npm root -g)" node your-script.js
```

### 2. 既存編集（ooxml）
既存PPTXをXML直接編集。

```bash
# 展開
python knowledge/ppt/ooxml_unpack.py input.pptx output_dir

# XML編集後、バリデーション
python knowledge/ppt/ooxml_validate.py output_dir --original input.pptx

# 再パック
python knowledge/ppt/ooxml_pack.py output_dir output.pptx
```

### 3. テンプレート利用
既存テンプレートのスライドを複製・並べ替え・テキスト置換。

```bash
# サムネイル作成
python knowledge/ppt/thumbnail.py template.pptx

# スライド並べ替え
python knowledge/ppt/rearrange.py template.pptx working.pptx 0,34,34,50,52

# テキスト抽出
python knowledge/ppt/inventory.py working.pptx text-inventory.json

# テキスト置換
python knowledge/ppt/replace.py working.pptx replacement-text.json output.pptx
```

## 簡易版（PptxGenJS）

シンプルなスライドはJSON定義から生成可能：

```bash
cd skills/ppt
npm install && npm run build
node dist/index.js input.json output.pptx
```

テンプレート: `skills/ppt/templates/sre-runbook.json`

## ナレッジ連携

- `/datadog` + `/ppt` → Datadog設計資料のPPT化
- `/aws` + `/ppt` → AWSアーキテクチャ資料のPPT化

プロンプトテンプレート:
- `prompts/datadog-multi-org-prompt.md` - マルチorg提案資料

## ビジュアル検証

作成したPPTXは必ず画像に変換して確認：

```bash
# PPTX → PDF → 画像
soffice --headless --convert-to pdf output.pptx
pdftoppm -jpeg -r 150 output.pdf slide
```

確認項目:
- テキスト切れ・重なり
- コントラスト・読みやすさ
- 位置・整列

## 依存関係

- markitdown: `pip install "markitdown[pptx]"`
- pptxgenjs: `npm install -g pptxgenjs`
- playwright: `npm install -g playwright`
- LibreOffice: PDF変換用
- Poppler: `pdftoppm`用
- defusedxml: `pip install defusedxml`
