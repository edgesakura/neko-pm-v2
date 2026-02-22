# Delegation Rule（委譲ルール）

## いつ Agent Teams を使うか

| 条件 | 判定 |
|------|------|
| 独立した並列タスクが **3つ以上** | → Teams |
| 異なる専門領域を同時に触る（front + back + infra 等） | → Teams |
| 1ファイル集中の変更（+200行程度） | → Lead 直接 OK |
| config / docs / 設定値の変更 | → Lead 直接 OK |

## Teams を使うときの必須事項

```
model: "sonnet"  ← 省略すると Opus 継承で高コスト
subagent_type: 対応する kitten ロール
team_name: チーム名
```

1. TeamCreate でチーム作成
2. TaskCreate でタスク分解
3. Task tool で子猫 spawn（team_name 指定）
4. 子猫の完了報告を受けて統合レビュー

## Lead が直接実装するとき

Agent Teams を使わない場合でも:

- **たぬきレビューは必須**（code-review.md 参照）
- 実装前にご主人に「直接やるにゃ」と宣言する
- 理由: 並列化の恩恵がない / 1ファイル集中 / タスク粒度が小さい 等
