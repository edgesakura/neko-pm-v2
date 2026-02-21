# Memory MCP アーカイブ（2026-02-19）

リファインメント時に Memory MCP のナレッジグラフをダンプ。
古い v3 時代のデータが大量に残っていたため、掃除前にアーカイブ。

## Entities

### ご主人 (user)
- Memory MCP統合を優先したい
- shutsujin_departure.shの仕組みに興味がある
- neko-pmの機能強化に積極的
- スキル化判断をボスねこに委任OK
- スキル化基準: 12点以上→自動承認、8-11点→検討、7点以下→見送り
- 検討時の判断フレームワーク: (1)論点に対する選択肢を出す (2)論理構成を持つ評価項目を作る (3)目指す方向性を基準に評価する
- 自律開発には自己改善機能が大事と考えている
- 能動的に改善点を見つける機能を重視
- 子猫が直接ご主人に報告・質問するのは絶対禁止。必ず番猫にエスカレすること。指揮系統を守れ（※v3ルール、v4で廃止）
- 大規模実装前に番猫・子猫は必ず/clearすること（※v3ルール）

### neko-pm (project)
- 猫型マルチエージェントシステム
- ボスねこ・番猫・子猫の階層構造（※v3。v4では番猫廃止）
- 2026-01-31: Memory MCP統合を実装
- 2026-01-31: 通信ロスト対策（リトライ+全報告スキャン）を実装
- 2026-01-31: スキル化候補のスコア化システムを実装
- 2026-01-31: エスカレ階層の設計変更 - 番猫→ボスねこ→ご主人
- 2026-01-31: 階層化承認フロー導入
- 2026-01-31: 自己改善機能の検討開始
- 2026-01-31: chat-app実装済み（output/chat-app/）
- 2026-01-31: acceptEditsだけでは番猫・子猫の承認問題解決せず
- 2026-01-31: フクロウに全ペイン監視・承認自動化機能を追加予定
- 2026-02-01: フクロウ承認監視システム完成（owl-watcher.sh 547行）（※v4で廃止）
- 2026-02-01: chat-app改修完成
- 2026-02-01: スキル化承認 - websocket-chat-enhancement (15点)
- 2026-02-01: スキル化承認 - tmux-approval-watcher (19点)
- 2026-02-05: brand-theme-generator スキル化承認（スコア13/20）
- 2026-02-05: Datadogカラーテーマ作成完了
- 2026-02-05: owl-watcher新形式プロンプト対応修正
- 2026-02-05: スキル化承認 - cross-project-pattern-migration (17/20)
- 2026-02-05: スキル化承認 - docs-integration-guide (15/20)
- 2026-02-05: スキル化承認 - project-automation-toolkit (19/20)
- 2026-02-05: Phase A〜D 完了
- ルール追加: 子猫→ご主人への直接報告禁止（※v3ルール）
- /clear運用ルール（※v3ルール）

### multi-agent-shogun (reference_project)
- neko-pmの参考元
- 将軍・家老・足軽の階層構造
- Memory MCP、8足軽並列、スキル化候補検出などの機能あり

### イザカヤくん開発 (project)
- LINE Bot + AgentCore Runtime の居酒屋検索AI
- 2026-02-06: 全バグ修正完了、動作確認済み
- のみべろ v2 Phase 1完了（Next.js+Amplify Gen2+Cognito）
- CRITICALセキュリティ修正完了

### LINE Bot エラー調査 (issue)
- 解決済み: Lambda Layer互換性問題、403 Forbidden（boto3修正）

### market-watch-v2-2026-02-17 (session_progress)
- MT5 watchlist 拡張、yfinance祝日問題解決、変動率アラート実装等
- 全変更は未コミット

## Relations
- ご主人 → owns → neko-pm
- neko-pm → references → multi-agent-shogun
