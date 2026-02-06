# Checkpoints Directory

このディレクトリには、長時間タスクの中間状態を保存するにゃ。

## ファイル命名規則
- `checkpoint-{task_id}-{timestamp}.yaml`
- 例: `checkpoint-task-2026-02-05T16:00:00-kitten1-20260205T163000.yaml`

## 保存内容
- completed_steps: 完了したステップのリスト
- next_action: 次にやるべきこと
- context: 関連情報（ファイルパス、変数等）
- issues: 未解決の問題点

## 運用ルール
- タスク完了後は削除してOK
- 中断時は必ず保持
- 1週間以上経過したファイルは定期的にクリーンアップ
