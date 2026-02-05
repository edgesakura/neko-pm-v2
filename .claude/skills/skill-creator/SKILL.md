---
name: skill-creator
description: 汎用的な作業パターンを発見した際に、再利用可能なClaude Codeスキルを自動生成するにゃ。繰り返し使えるワークフロー、ベストプラクティス、ドメイン知識をスキル化する時に使用にゃ。
---

# Skill Creator - スキル自動生成にゃ

## Overview

作業中に発見した汎用的なパターンを、再利用可能なClaude Codeスキルとして保存するにゃ。
これにより、同じ作業を繰り返す際の品質と効率が向上するにゃ〜。

## When to Create a Skill

以下の条件を満たす場合、スキル化を検討せよにゃ：

1. **再利用性**: 他のプロジェクトでも使えるパターン
2. **複雑性**: 単純すぎず、手順や知識が必要なもの
3. **安定性**: 頻繁に変わらない手順やルール
4. **価値**: スキル化することで明確なメリットがある

## Skill Structure

生成するスキルは以下の構造に従うにゃ：

```
skill-name/
├── SKILL.md          # 必須
├── scripts/          # オプション（実行スクリプト）
└── resources/        # オプション（参照ファイル）
```

## SKILL.md Template

```markdown
---
name: {skill-name}
description: {いつこのスキルを使うか、具体的なユースケースを明記}
---

# {Skill Name}

## Overview
{このスキルが何をするか}

## When to Use
{どういう状況で使うか、トリガーとなるキーワードや状況}

## Instructions
{具体的な手順}

## Examples
{入力と出力の例}

## Guidelines
{守るべきルール、注意点}
```

## Creation Process

1. パターンの特定
   - 何が汎用的か
   - どこで再利用できるか

2. スキル名の決定
   - kebab-case を使用（例: api-error-handler）
   - 動詞+名詞 or 名詞+名詞

3. description の記述（最重要）
   - Claude がいつこのスキルを使うか判断する材料にゃ
   - 具体的なユースケース、ファイルタイプ、アクション動詞を含める
   - 悪い例: "ドキュメント処理スキル"
   - 良い例: "PDFからテーブルを抽出しCSVに変換する。データ分析ワークフローで使用にゃ。"

4. Instructions の記述
   - 明確な手順にゃ
   - 判断基準にゃ
   - エッジケースの対処にゃ

5. 保存
   - パス: ~/.claude/skills/neko-{skill-name}/
   - 既存スキルと名前が被らないか確認にゃ

## 使用フロー（neko-pm 専用）

このスキルは番猫がボスねこからの指示を受けて使用するにゃ。

1. 子猫がスキル化候補を発見 → 報告YAMLの `skill_candidate` に記載
2. 番猫が子猫の報告をレビュー → nawabari.md の「🎯 スキル化候補」セクションに記録
3. 番猫がボスねこにエスカレ（send-keys + nawabari.md 更新）
4. **ボスねこが最新仕様をリサーチし、スキル設計を行う**
5. ボスねこがご主人に承認を依頼（nawabari.md経由）
6. ご主人が承認
7. ボスねこ → 番猫に作成を指示（設計書付き、queue/boss_to_guard.yaml）
8. **番猫 がこのskill-creatorを使用してスキルを作成**
9. 完了報告（queue/reports/）

※ ボスねこがリサーチした最新仕様に基づいて作成することにゃ。
※ ボスねこからの設計書に従うことにゃ。

## neko-pm 固有の要件

### 子猫の責務
- 全てのタスク報告YAMLに `skill_candidate` セクションを必須記入にゃ
- `found: true` の場合、スキル名・説明・理由・スコアを詳細に記載にゃ
- `found: false` の場合も、理由を記載にゃ

### 番猫の責務
- 子猫の報告から `skill_candidate: found: true` を発見したら、nawabari.md の「🎯 スキル化候補」セクションに記録にゃ
- スコア合計8点以上のものをボスねこにエスカレにゃ

### ボスねこの責務
- スキル化候補を受けたら、最新仕様をリサーチして設計書を作成にゃ
- ご主人に承認依頼（必要に応じて）にゃ
- 番猫にスキル作成を指示にゃ〜

## Examples of Good Skills

### Example 1: API Response Handler
```markdown
---
name: api-response-handler
description: REST APIのレスポンス処理パターンにゃ。エラーハンドリング、リトライロジック、レスポンス正規化を含むにゃ。API統合作業時に使用にゃ。
---
```

### Example 2: Meeting Notes Formatter
```markdown
---
name: meeting-notes-formatter
description: 議事録を標準フォーマットに変換するにゃ。参加者、決定事項、アクションアイテムを抽出・整理にゃ。会議後のドキュメント作成時に使用にゃ。
---
```

### Example 3: Data Validation Rules
```markdown
---
name: data-validation-rules
description: 入力データのバリデーションパターン集にゃ。メール、電話番号、日付、金額などの検証ルールにゃ。フォーム処理やデータインポート時に使用にゃ。
---
```

## Reporting Format

スキル生成時は以下の形式で報告するにゃ：

「にゃっ！新しいスキルを作ったにゃ〜
- スキル名: {name}
- 用途: {description}
- 保存先: {path}

ボスねこ、確認をお願いするにゃ！」
