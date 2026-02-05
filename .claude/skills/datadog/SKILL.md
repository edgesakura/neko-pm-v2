---
name: datadog
description: Datadog監視設計・ダッシュボード構築・アラート設定。ダッシュボード設計、メトリクスクエリ、モニター設定に使用
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Datadog開発モード

Datadog関連の開発・設計をサポートするスキル。

## ナレッジ読み込み

このスキルが呼ばれたら、まず以下を参照：
- `knowledge/datadog/index.md` - クエリ例、色分けルール、環境情報
- `knowledge/datadog/dashboards/` - 既存ダッシュボード定義

## できること

### 1. ダッシュボード設計
- ウィジェット構成の提案
- クエリの作成・最適化
- JSON定義ファイルの生成

### 2. アラート設計
- モニター設定の提案
- 閾値設計
- 通知チャネル設計（Slack、PagerDuty）

### 3. クエリ作成
- メトリクスクエリ
- ログクエリ
- APMトレースクエリ

### 4. 提案資料作成
- マルチorg導入提案（`prompts/datadog-multi-org-prompt.md` 参照）
- ダッシュボード設計書

## 環境情報

5つのDatadogアカウント：
- 東商用（NTT東日本本番）
- 西商用（NTT西日本本番）
- ST（ステージング）
- dev（開発）
- cmm（AWS連携管理）

## 監視対象システム

```
Mule → Pega(EKS) → Java
```

## 使い方例

```
/datadog ダッシュボードにCPU使用率のウィジェットを追加したい
/datadog エラー率が5%を超えたらアラートを出したい
/datadog マルチorg導入の提案資料を作りたい
```
