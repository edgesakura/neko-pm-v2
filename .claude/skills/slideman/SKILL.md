---
name: slideman
description: コンサルタント向けAIスライド生成スキル。テーマ・要件から自動でPowerPointを生成
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Slideman スキル

コンサルタント向けに、テーマや要件を入力するだけで、Web検索とLLMを活用してプロフェッショナルなPowerPointスライドを自動生成するスキル。

## このスキルが呼ばれたら読むべきドキュメント

| タスク | 読むべきドキュメント |
|--------|---------------------|
| システム設計理解 | `shogun/output/slideman-design.md` |
| 型定義確認 | `projects/consul-slideman/src/types/index.ts` |
| PPTX生成実装 | `projects/consul-slideman/src/modules/pptx.ts` |
| Web検索連携 | `projects/consul-slideman/src/modules/search.ts` |
| LLM連携 | `projects/consul-slideman/src/modules/llm.ts` |

**重要**: ドキュメントは最後まで読んでからタスクを開始すること。

## 主要機能

### 1. テーマ入力
ユーザーがスライドのテーマや要件を入力

### 2. Web検索
Tavily APIを使用して最新情報を収集

### 3. LLM生成
Claude Sonnet 4.5で構成・内容を生成

### 4. PPTX出力
編集可能なPowerPoint形式で出力

## コマンド構文

### ローカル版CLI

```bash
# 基本使用法
consul-slideman generate \
  --theme "DX推進戦略" \
  --requirements "製造業向け" "ROI重視" \
  --slides 12 \
  --output "./output/dx-strategy.pptx"

# オプション一覧
Options:
  --theme <string>              スライドテーマ（必須）
  --requirements <string...>    追加要件（複数可）
  --slides <number>             スライド枚数（デフォルト: 10-15）
  --style <style>               スタイル（simple | visual | data-heavy）
  --target <string>             ターゲット層（例: 経営層、IT部門）
  --language <lang>             言語（ja | en）
  --output <path>               出力先パス
  --no-search                   Web検索を無効化
  --verbose                     詳細ログ出力
  --help                        ヘルプ表示
```

### 使用例

#### 例1: 基本的な使い方
```bash
consul-slideman generate \
  --theme "クラウド移行戦略" \
  --slides 10 \
  --output ./cloud-migration.pptx
```

#### 例2: 詳細な要件指定
```bash
consul-slideman generate \
  --theme "SaaS事業の成長戦略" \
  --requirements "サブスクリプションモデル" "ARR拡大" "チャーン率改善" \
  --slides 15 \
  --style data-heavy \
  --target "経営層・投資家" \
  --language ja \
  --output ./saas-growth-strategy.pptx
```

#### 例3: Web検索なし（オフライン）
```bash
consul-slideman generate \
  --theme "アジャイル開発導入" \
  --slides 8 \
  --no-search \
  --output ./agile-introduction.pptx
```

#### 例4: 英語プレゼンテーション
```bash
consul-slideman generate \
  --theme "Digital Transformation Strategy" \
  --requirements "Enterprise" "ROI-focused" \
  --slides 12 \
  --language en \
  --output ./dx-strategy-en.pptx
```

## スライドタイプ

consul-slidemanは以下の4種類のスライドタイプを自動生成します：

### 1. タイトルスライド
- プレゼンテーションの最初のスライド
- タイトル（大きく中央配置）
- サブタイトル（小さく中央配置）

### 2. 箇条書きスライド
- 一般的なコンテンツスライド
- タイトル
- 箇条書き（最大3階層のインデント対応）
- 3-5項目推奨

### 3. セクション区切りスライド
- 章の区切りを明示
- 背景色変更（デフォルト: ブルー）
- セクションタイトル（大きく中央配置、白文字）
- 視覚的インパクト

### 4. クロージングスライド
- プレゼンテーションの最後
- 締めのメッセージ
- 「まとめ」「ご清聴ありがとうございました」などを自動判定

## テーマ設定

### デフォルトテーマ
```bash
--theme default  # または省略
```
- プライマリカラー: ブルー (#0066CC)
- セカンダリカラー: オレンジ (#FF6B35)
- テキスト: ダークグレー (#333333)
- 背景: ホワイト (#FFFFFF)

### ミニマルテーマ
```bash
--theme minimal
```
- プライマリカラー: ブラック (#000000)
- セカンダリカラー: グレー (#666666)
- テキスト: ダークグレー (#333333)
- 背景: ホワイト (#FFFFFF)

## アスペクト比

### 16:9（デフォルト）
```bash
# 明示的に指定する場合
--aspect-ratio 16:9
```
- 現代的なワイド画面
- オンラインプレゼンテーションに最適

### 4:3（クラシック）
```bash
--aspect-ratio 4:3
```
- 従来型プロジェクター向け
- 印刷資料に適している

## スタイル設定

### simple（デフォルト）
```bash
--style simple
```
- シンプルでクリーンなデザイン
- 箇条書き中心
- 経営層向けに最適

### visual
```bash
--style visual
```
- ビジュアル重視
- 図表・グラフを多用（Phase 2で実装予定）
- マーケティング資料に最適

### data-heavy
```bash
--style data-heavy
```
- データ駆動型
- テーブル・グラフ中心（Phase 2で実装予定）
- アナリスト・技術者向け

## 開発ワークフロー

### ローカル開発環境セットアップ

```bash
cd projects/consul-slideman
npm install
```

### ビルド

```bash
npm run build
```

### 開発モード（ホットリロード）

```bash
npm run dev -- generate --theme "テストテーマ"
```

### テスト実行

```bash
# 全テスト実行
npm test

# PPTX生成モジュールのみ
npm test -- src/modules/__tests__/pptx.test.ts

# カバレッジ確認
npm run test:coverage

# ウォッチモード（開発中）
npm run test:watch
```

### テストカバレッジ要件

- **目標**: 80%以上
- **現在**: 100%（pptx.ts）

## プロジェクト構造

```
projects/consul-slideman/
├── src/
│   ├── index.ts              # CLIエントリーポイント
│   ├── types/
│   │   └── index.ts          # TypeScript型定義
│   └── modules/
│       ├── input.ts          # 入力処理モジュール
│       ├── llm.ts            # LLM連携モジュール
│       ├── search.ts         # Web検索モジュール
│       ├── pptx.ts           # PPTX生成モジュール
│       ├── output.ts         # 出力処理モジュール
│       └── __tests__/
│           ├── input.test.ts
│           └── pptx.test.ts
├── package.json
├── tsconfig.json
└── README.md
```

## モジュール連携

```
CLI入力
  ↓
入力処理モジュール（input.ts）
  ↓
LLM連携モジュール（llm.ts）
  ├── Web検索モジュール（search.ts） ← Tavily API
  │   └── 最新情報収集
  └── スライド構成・内容生成
      └── Claude Sonnet 4.5
  ↓
PPTX生成モジュール（pptx.ts）
  ├── タイトルスライド作成
  ├── 箇条書きスライド作成
  ├── セクション区切りスライド作成
  └── クロージングスライド作成
  ↓
出力処理モジュール（output.ts）
  └── ファイル保存（ローカル / S3）
```

## 技術スタック

| レイヤー | 技術 | 理由 |
|---------|------|------|
| PPTX生成 | PptxGenJS | ゼロ依存・軽量・AWS Lambda最適 |
| LLM | Claude Sonnet 4.5 | 長文生成・日本語精度・Function Calling |
| Web検索 | Tavily API | LLM最適化・検索深度オプション |
| 言語 | TypeScript | 型安全・自動補完・開発効率 |
| テスト | Vitest | 高速・ES Modules対応 |
| ビルド | tsc | TypeScript公式 |
| ランタイム | Node.js 22.x | 最新LTS・ES2024サポート |

## トラブルシューティング

### Q1: PPTX生成でエラーが出る

```bash
# PptxGenJSのインストール確認
npm list pptxgenjs

# 再インストール
npm install pptxgenjs --save
```

### Q2: テストが失敗する

```bash
# node_modulesを削除して再インストール
rm -rf node_modules package-lock.json
npm install

# TypeScriptビルド
npm run build

# テスト実行
npm test
```

### Q3: Claude API キーエラー

```bash
# 環境変数設定
export ANTHROPIC_API_KEY="sk-ant-..."

# または .env ファイル作成
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

### Q4: Tavily API キーエラー

```bash
# 環境変数設定
export TAVILY_API_KEY="tvly-..."

# Web検索を無効化して実行
consul-slideman generate --theme "テーマ" --no-search
```

## ベストプラクティス

### 1. テーマ設定
- **明確に**: 「DX推進」より「製造業向けDX推進戦略」
- **具体的に**: 「マーケティング」より「SaaSスタートアップのGrowth Marketing」

### 2. 要件指定
- **箇条書き形式**: `--requirements "ROI重視" "3年計画" "中小企業向け"`
- **優先順位**: 重要な要件を先に記述
- **3-5個が最適**: 多すぎると焦点がぼける

### 3. スライド枚数
- **経営層向け**: 10-12枚（簡潔に）
- **技術者向け**: 15-20枚（詳細に）
- **営業資料**: 8-10枚（インパクト重視）

### 4. ターゲット層
- 明示的に指定することで、トーン・内容・詳細度が最適化される
- 例: `--target "経営層"`, `--target "エンジニア"`, `--target "投資家"`

### 5. Web検索
- **最新情報が必要**: デフォルトで有効
- **過去の知識で十分**: `--no-search` で高速化
- **コスト削減**: Web検索を無効化するとTavily API料金が不要

## Phase 2 予定機能

現在Phase 1（MVP）完了。Phase 2で以下を実装予定：

- **テーブル生成**: LLMが構造化データ出力、PptxGenJSで描画
- **グラフ生成**: 棒グラフ、折れ線グラフ、円グラフ
- **テンプレート機能**: 企業テンプレートPPTXの読み込み（pptx-automizer統合）
- **画像生成**: DALL-E連携でスライド用画像自動生成
- **AWSサーバーレス版**: Lambda + API Gateway + S3でクラウド運用

## 参考資料

### 設計書
- `shogun/output/slideman-design.md` - システム設計書
- `shogun/output/marp-agent-analysis.md` - 参考実装分析
- `shogun/output/pptx-tech-research.md` - 技術調査レポート

### 実装ファイル
- `projects/consul-slideman/src/types/index.ts` - 型定義
- `projects/consul-slideman/src/modules/pptx.ts` - PPTX生成実装
- `projects/consul-slideman/src/modules/__tests__/pptx.test.ts` - テスト

### 既存PPTスキル
- `.claude/skills/ppt/SKILL.md` - 既存PPT生成スキル
- `knowledge/ppt/` - PPT関連ナレッジベース

## ライセンス

MIT License

---

**重要**: このスキルはPhase 1（MVP）が完了した段階です。テーブル・グラフ・画像生成はPhase 2で実装予定です。
