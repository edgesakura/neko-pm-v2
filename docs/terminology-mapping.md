# 用語マッピング: multi-agent-shogun ↔ neko-pm

複数プロジェクト間でパターン移植する際の用語対応表にゃ。

## エージェント

| multi-agent-shogun | neko-pm | 役割 |
|--------------------|---------|------|
| Shogun | ボスねこ | 統括・作戦指揮 |
| Karo | 番猫 | タスク分配・管理 |
| Ashigaru | 子猫 | 実装作業 |
| Elder | 長老猫 | 技術アドバイザー（オンデマンド） |

## ファイル

| multi-agent-shogun | neko-pm | 用途 |
|--------------------|---------|------|
| dashboard.md | nawabari.md | 状況板 |
| queue/shogun_to_karo.yaml | queue/boss_to_guard.yaml | 指示キュー |
| queue/tasks/ashigaru{N}.yaml | queue/tasks/task-*-kitten{N}.yaml | タスク定義 |
| queue/reports/ | queue/reports/ | 報告キュー（同じ） |
| instructions/shogun.md | instructions/boss-cat.md | ボスねこ指示書 |
| instructions/karo.md | instructions/guard-cat.md | 番猫指示書 |
| instructions/ashigaru.md | instructions/kitten.md | 子猫指示書 |

## ディレクトリ

| multi-agent-shogun | neko-pm | 用途 |
|--------------------|---------|------|
| context/ | context/ | プロジェクト固有情報（同じ） |
| memory/ | memory/ | Memory MCP保存先（同じ） |
| config/ | config/ | プロジェクト設定（同じ） |
| output/ | output/ | 成果物（同じ） |
| queue/ | queue/ | 通信キュー（同じ） |

## その他

| multi-agent-shogun | neko-pm | 意味 |
|--------------------|---------|------|
| Human / The Lord | ご主人 | ユーザー |
| Session | セッション | tmuxセッション名 |
| Pane | ペイン | tmuxペイン |

## 用語の特徴

### multi-agent-shogun（戦国時代テーマ）
- 将軍（Shogun）: 最高権力者
- 家老（Karo）: 側近・参謀
- 足軽（Ashigaru）: 歩兵・実働部隊
- 殿（The Lord）: 主君
- 格式ある語尾: 「はっ！」「申し上げます」

### neko-pm（猫テーマ）
- ボスねこ: リーダー
- 番猫: 現場監督
- 子猫: 実行部隊
- ご主人: 飼い主
- かわいい語尾: 「にゃ」「にゃ〜」

## 使用例

multi-agent-shogun のパターンを neko-pm に移植する際:

### ステップ1: このテーブルを参照
用語対応表を確認し、変換対象を特定にゃ。

### ステップ2: 用語を一括置換
```bash
# 例: ファイル内の用語を一括置換
sed -i 's/Shogun/ボスねこ/g' target-file.md
sed -i 's/Karo/番猫/g' target-file.md
sed -i 's/Ashigaru/子猫/g' target-file.md
sed -i 's/dashboard.md/nawabari.md/g' target-file.md
```

### ステップ3: プロジェクト固有の調整
- 語尾を調整（「はっ！」→「にゃ！」）
- ファイルパスを調整（必要に応じて）
- プロジェクト固有の要件を追加にゃ〜

## 注意事項

- 用語置換後は必ず文脈を確認にゃ
- 機械的な置換だけでなく、プロジェクトの文化・ノリに合わせて調整にゃ
- ファイルパスやコマンドは特に注意して確認にゃ〜

## 応用: 他プロジェクトへの展開

この用語マッピングの考え方は、他のマルチエージェントプロジェクトにも応用できるにゃ：

1. プロジェクトのテーマを決定（例: 海賊団、宇宙船クルー、etc）
2. 階層構造に合わせた用語を定義
3. 用語マッピングテーブルを作成
4. 既存パターンを移植にゃ〜
