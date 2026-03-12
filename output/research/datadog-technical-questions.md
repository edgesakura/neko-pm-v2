# Datadog 技術営業への質問ドラフト（v4）

> 作成日: 2026-03-08 / 更新: 2026-03-13
> 目的: Standard 3日 + Flex の tiering 設計にあたり、Flex 制約下での監視設計とサイジング根拠を確認
> 参考: Indexing Strategies Guide、Husky ブログ（Query Architecture / Flex Logs）

---

## 背景

弊社では Datadog の Log Management の Index 設計を見直しています。現在 Standard Index 30日保持で運用中ですが、コスト最適化のため **Standard 3日 + Flex 延長** への移行を検討しています。

御社の Indexing Strategies Guide で推奨されている tiering パターンに沿った構成です。設計を進める中で、以下の3点について御社の知見をいただきたくご相談します。

### 弊社の検討中の構成

| ログ種別 | Index 戦略 | 理由 |
|---------|-----------|------|
| 本番 Error/Warn | Standard 3日 | ログモニター（評価ウィンドウ最大48H）+ トラブルシュート |
| 本番 Info（高ボリューム） | Flex 直行 + logs-to-metrics | metrics 化で監視を分離 |
| CDN/WAF アクセスログ | Flex 直行 | セキュリティ調査時にオンデマンド検索 |
| CloudTrail 監査ログ | Flex 直行 | コンプライアンス用長期保持 |
| Debug ログ | 除外（Live Tail のみ） | 必要時に一時的に有効化 |

---

## Q1. Flex のモニター制約下での監視設計

Flex Logs ではログモニター・Watchdog モニター・Watchdog Insights が利用できないと理解しています。Standard 3日 + Flex の構成に移行した場合、**Flex 直行としたログ（Info 高ボリューム、CDN/WAF、CloudTrail）の異常検知をどう設計すべきか**が最大の懸念です。

弊社では以下のカバー策を検討していますが、御社としての推奨パターンがあれば教えてください。

### 弊社の検討中のカバー策

| Flex 制約 | カバー策（案） | 懸念 |
|----------|--------------|------|
| ログモニター使用不可 | logs-to-metrics でカスタムメトリクス化 → Metric Monitor で監視 | メトリクス変換時に情報が落ちる（ログの中身は見えない）。どこまで metrics 化すべきか判断基準がほしい |
| Watchdog モニター使用不可 | 上記 Metric Monitor + 手動閾値設定で代替 | Watchdog の自動異常検知（ベースライン学習）を手動閾値で再現するのは困難。代替手段はあるか |
| Watchdog Insights 使用不可 | インシデント時に手動で Flex 検索して調査 | 検索速度がインシデント対応 SLA（15分以内に初動完了）に影響しないか |

**特に聞きたい点**:
- Flex 直行ログに対して **logs-to-metrics 以外のモニタリング手法** はあるか（例: Pipeline 段階での振り分け、Cloud SIEM 連携等）
- 御社の他のお客様は Standard + Flex 構成で Watchdog 相当の異常検知をどう代替しているか

---

## Q2. Flex Compute サイジングの設計根拠

御社のドキュメント（Flex Logs > Determine the compute size that you need）では、クエリ性能に影響する要因として以下の4つが挙げられています:

1. **Volume** — Flex 層の累積データ量
2. **Time window** — クエリの時間範囲（15分 vs 1ヶ月）
3. **Complexity** — 集計の深さ、フィルタ数
4. **Concurrency** — 同時クエリユーザー数

一方で、サイジングの推奨テーブルは **累積イベント数（Volume）のみ** を基準にしています:

| Size | Volume |
|------|--------|
| Starter | < 10B events |
| XS | 10-50B |
| S | 50-200B |
| ... | ... |

**聞きたい点**:
- サイジングは**累積イベント数だけで決めて問題ないか**？ 残りの3要因（Time window / Complexity / Concurrency）が大きく影響するケースでは、テーブルの推奨よりワンサイズ上を選ぶべき等の指針はあるか
- 弊社の想定ワークロード（下記）の場合、テーブル上は XS〜S 相当だが、クエリパターンを踏まえて妥当か

```
想定ワークロード:
  累積イベント数: 約 15B events（90日保持 × 50GB/日 想定）
  → テーブル上は XS（10-50B）

  クエリパターン（Volume 以外の3要因）:
    Time window: インシデント時に 7-30日 範囲を検索（月1-2回）
    Complexity:  特定 IP/ユーザーID のフィルタ + status 集計
    Concurrency: 通常1-2名、インシデント時は最大 3-5名が同時検索
```

- また、Standard + Flex のまたがりクエリ（例: ダッシュボードで「過去7日間」を指定）の場合、直近3日（Standard）と4-7日前（Flex）で**体感としてどの程度の速度差**が出るか。ユーザーへの事前説明の参考にしたい

---

## Q3. ユースケース別の設計レビュー

上記の「弊社の検討中の構成」テーブルについて、御社の観点で見落としやリスクがあれば指摘いただきたいです。

**特に確認したい点**:

| ログ種別 | 確認したい点 |
|---------|-------------|
| 本番 Info → Flex 直行 | logs-to-metrics でメトリクス化 + Flex 保持。この2段構成は妥当か？ |
| CDN/WAF → Flex 直行 | セキュリティ調査時の検索速度は実用的か？ Cloud SIEM と組み合わせる方が良いか？ |
| CloudTrail → Flex 直行 | コンプライアンス要件（監査ログへの即時アクセス）との兼ね合いは問題ないか |
| Debug → 除外 | 本番で一時的に Debug を有効化した場合、動的に Standard Index に振り分ける Pipeline 設計は可能か |

---

## 補足: 弊社が事前に確認済みの情報

設計検討にあたり、以下の公開情報はすでに確認済みです。質問はこれらを踏まえた上での実運用判断に関するものです。

- Indexing Strategies Guide（tiering パターン）
- Husky ブログ（Query Architecture / Flex Logs）
- Flex Logs ドキュメント（direct-to-Flex、compute usage）
- Best Practices for Log Management

---

## Teams コピペ用

以下をそのまま Teams チャットに貼り付けてください。

---

### ここからコピペ ↓↓↓

お疲れさまです。Log Management の Index 設計見直しについてご相談させてください。

現在 Standard Index 30日保持で運用していますが、コスト最適化のため **Standard 3日 + Flex 延長** への移行を検討しています（Indexing Strategies Guide の tiering パターンに沿った構成です）。

設計を進める中で3点ご相談があります。

---

**【検討中の構成】**

- 本番 Error/Warn → Standard 3日（ログモニター + トラブルシュート用）
- 本番 Info（高ボリューム） → Flex 直行 + logs-to-metrics
- CDN/WAF アクセスログ → Flex 直行
- CloudTrail 監査ログ → Flex 直行
- Debug ログ → 除外（Live Tail のみ）

---

**Q1. Flex 制約下での監視設計**

Flex ではログモニター・Watchdog モニター・Watchdog Insights が使えないと理解しています。Flex 直行にしたログ（Info / CDN / CloudTrail）の異常検知をどう設計すべきかが一番の懸念です。

弊社案としては logs-to-metrics でメトリクス化 → Metric Monitor で代替を考えていますが、

- Watchdog の自動異常検知（ベースライン学習）を手動閾値で再現するのは難しそう。代替手段はありますか？
- logs-to-metrics 以外のモニタリング手法（Pipeline での振り分け、Cloud SIEM 連携等）はありますか？
- 他のお客様は Standard + Flex 構成で Watchdog 相当の監視をどう代替されていますか？

---

**Q2. Flex Compute サイジングの根拠**

ドキュメント（Flex Logs > Determine the compute size that you need）では、クエリ性能に影響する要因として Volume / Time window / Complexity / Concurrency の4つが挙げられています。

一方でサイジングの推奨テーブルは**累積イベント数（Volume）のみ**が基準になっています。

- 累積イベント数だけで決めて問題ないでしょうか？ 残りの3要因（Time window / Complexity / Concurrency）が大きく影響するケースでは、テーブルよりワンサイズ上を選ぶ等の指針はありますか？
- 弊社の想定: 累積 約15B events（90日保持 × 50GB/日）、テーブル上は XS。インシデント時に 7-30日範囲を 3-5名が同時検索する想定ですが、XS で問題ないでしょうか？
- Standard + Flex のまたがりクエリ（例: 過去7日間）の場合、直近3日（Standard）と4-7日前（Flex）で体感の速度差はどの程度出ますか？

---

**Q3. ユースケース別の設計レビュー**

上記の構成について、見落としやリスクがあれば教えてください。特に気になる点:

- 本番 Info → Flex 直行 + logs-to-metrics の2段構成は妥当か？
- CDN/WAF → Flex 直行で、セキュリティ調査時の検索速度は実用的か？（インシデント対応 SLA: 15分以内に初動完了）
- CloudTrail → Flex 直行で、コンプライアンス要件（監査ログの即時アクセス）は問題ないか？
- Debug → 除外で、本番で一時的に有効化した場合に動的に Standard に振り分ける Pipeline 設計は可能か？

---

なお、以下の公開情報は確認済みです:
Indexing Strategies Guide / Husky ブログ（Query Architecture / Flex Logs） / Flex Logs ドキュメント / Best Practices for Log Management

### ここまでコピペ ↑↑↑
