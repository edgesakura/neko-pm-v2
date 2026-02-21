# neko-pm Memory

## v3.5 進捗（2026-02-17）
- コミット `730ea9c`（未 push）。前回 push は `eeb4c6b`
- **今セッションの未コミット変更**: market-watch.py（MT5優先化+前方一致+桁数自動+5mスコア表示+変動率アラート）、config/market-alerts.json（volatility_alert追加+GC=F/SI=F削除+GOLD/SILVER統合）
- **TAP**（思考増幅）/ **AIP**（自律改善）/ **BMP**（バックログ管理）導入
- **AIP Phase 0（前提検証）導入済み**: Teammate が Lead の指示に対し「ご主人の本当の目的は？この手段は最適か？」と異議を唱える仕組み
- **tmux 5 Window**: lead(+Teammate自動分割) / tanuki / scouts / chat / market
  - teammates Window 廃止（`--teammate-mode tmux` で lead に自動分割）
  - thinking Window 廃止（サマリーログは思考可視化にならない）
- **thinking-log.sh**: 全7 kitten に AIP フェーズごとのログ記録を組み込み済み
- **AIP 試運転**: 完了。Phase 0/1/2 が正常動作
- **学び**: Lead が TAP（Why×3）をサボると方向を間違える。Teammate が異議を唱える Phase 0 で補完
- **学び**: Task tool サブエージェントは実装委譲に不適切（ファイル編集が保存されずに消滅する）。実装は必ず Agent Teams で → F002 ルール化済み
- **コスト方針**: 週間制限にかからない範囲ならトークン多少多くてOK。品質優先
- **Codex CLI（研究狸/フクロウ）**: OpenAI Plus プランが遊んでいるので積極活用。調査・レビュー・設計相談に遠慮なく投げてよい
- **ネコ×狸 連携**: ネコ(Claude)は0→1(新規作成)に強い、狸(Codex)は1→100(レビュー・エラー修正)に強い。実装後は必ず狸レビューを挟むフローを標準化
- **次のステップ**: 仕事用 PC 展開

## Qiita 記事シリーズ（2026-02-17）
- **第1弾**: v2 猫型PM作った → **公開済み** https://qiita.com/alphaedgesakura/items/0a00554d7607f8b2be4a
- **第2弾**: マルチベンダー実践（Claude×Codex×Gemini）→ `output/qiita-article-v37.md` にドラフトあり
  - 実例①: のんべろエージェント（個人開発。社内ハッカソンではない）+ 狸が7つのハマりポイント解析
  - 実例②: SRE/Datadogスキルで汎用AI→専門家化
  - Datadog ログコスト算出の実例は**ウソになるので削除済み**（実際にやってない話は書かない）
  - v36（旧ドラフト `output/qiita-article-v36.md`）は v37 にマージ済みで不要
- **第3弾（予定）**: TAP/AIP 思考増幅の設計と実運用
- **第4弾（予定）**: 運用ノウハウ集（Agent Teams vs Task tool、CLAUDE.md分割、合意即セーブ等）

## market-watch.py（2026-02-17 更新）
- **MT5 優先化**: EA WatchSymbols に GOLD,SILVER,US100-MAR26,USDJPY,AUDUSD を設定
- **yfinance 祝日問題**: Presidents' Day 等で先物データが止まる → MT5 優先で解決
- **前方一致マッチ**: fetch_price_mt5 で US100 → US100-MAR26 にヒット（限月対応）
- **price_fmt()**: 価格帯で自動桁数（<10: 5桁FX, <1000: 3桁, >=1000: 2桁）
- **5m足スコア詳細**: アラート本文に format_score_detail() で表示。FSM.last_score_detail で保持
- **変動率アラート**: config `volatility_alert`（window:30min, threshold:1.0%）。deque リングバッファ
- **銘柄統合**: GC=F/SI=F(yfinance) 削除 → GOLD/SILVER(MT5直結) に統合。監視 8→6 銘柄
- GOLD レベル: 5300(売り)/4600(買い)、SILVER: 92/80(売り)/70(買い) — XM 価格帯
- スコア制: 7条件（ゾーン反発2, RSI1, MACD1, ピンバー1, 包み足1, BB1, 出来高1）
- 必須ゲート: zone_reject AND momentum>=1 AND price_action>=1
- 売り5点/買い4点（非対称）。FX は vol:SKIP
- デーモン稼働中（neko-pm:market Window）

## finance-tanuki スキル（2026-02-17 追加）
- `~/.codex/skills/finance-tanuki/` — Codex CLI 用の金融ドメイン専門家スキル
- SKILL.md + agents/openai.yaml + references/trading-context.md

## プロジェクト構成
- `~/neko-pm/` — **本体（稼働版）**。すべての作業はここで行う
- `~/git/neko-pm/` — **アーカイブ**。更新予定なし。コピペミスの可能性もあるので参照程度に留める
- PPT スキルは別リポジトリ `edgesakura/claude-ppt-skill` (private) に分離済み → submodule で参照

## 外部エージェント運用ルール（2026-02-16 追加）
- **E001**: `codex exec` 直接実行禁止 → tanuki ペインに `tmux send-keys` で送る（F011）
- **E002**: tanuki コンテキストオーバー → `/new` で新規セッション（`tmux send-keys -t neko-pm:tanuki '/new'` + Enter）
- **E003**: scouts も同様（Gemini: `:reset`、Codex: `/new`）
- **start-team.sh に Window 4 "market" 追加済み**（market-watch.py デーモン自動起動）

## tmux send-keys ルール（重要）
- **Enter は必ず別コマンドで送る**: `tmux send-keys -t <target> 'コマンド' Enter` の Enter が効かないケースがある
- 正しいパターン: `tmux send-keys -t neko-pm:tanuki 'コマンド内容'` → `tmux send-keys -t neko-pm:tanuki Enter`
- **常にこの2ステップで送る**。コマンドなしの素の Enter 送信も同じ: `tmux send-keys -t <target> Enter`
- **改行を含む長文は送らない**: Codex/Gemini CLI が複数行入力モードに入り送信されない。**必ず1行に収める**こと

## サブプロジェクト
- **chat-app** (`output/chat-app/`): Node.js + WebSocket + xterm.js のターミナルWeb UI (port 3000)
- **nomibero-web** (`output/nomibero-web/`): Next.js + Amplify + Cognito の居酒屋検索チャットUI
- **izakaya-agent** (`output/izakaya-agent/`): Lambda + API Gateway + Bedrock AgentCore のバックエンド
  - API: `https://ok1y8ns08b.execute-api.ap-northeast-1.amazonaws.com/prod/chat`
  - Streaming: `https://w2jp72dlbkx4caczxsvxuplvra0cxvud.lambda-url.ap-northeast-1.on.aws/`
  - Lambda: `izakaya-agent-line-webhook` (python3.11) + `izakaya-agent-streaming` (Docker/FastAPI)
  - CDK Stack: `IzakayaAgentStack` (infra/ ディレクトリ)

## awssap-quiz (`output/awssap-quiz/`)
- Next.js 16 + Amplify Gen 2 + Cognito（nomibero-web と User Pool 共有）
- 529問の AWS SAP-C02 クイズアプリ（PWA）
- デプロイ済: `https://main.d2f8qm6i4rra4.amplifyapp.com`
- GitHub: `edgesakura/awssap-quiz`（main ブランチ auto-build）
- Amplify App ID: `d2f8qm6i4rra4`
- Cognito: `ap-northeast-1_VwL7teKWl`（nomibero-web 共有）
- テスト: 10 suites, 63 tests passing

## Agent Teams 設定
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 有効化済み
- v3.5 アーキテクチャ: TAP/AIP/BMP プロトコル導入済み
- Codex MCP (`codex mcp-server` v0.98.0) 設定済み
- **ご主人の要望**: 自律的改善、思考可視化、発想を超える提案、Backlog 管理
- **仕事用 PC**: IP 制限あり、Backlog MCP あり → `setup.sh --work` で展開予定

## デプロイ知見
- Lambda Web Adapter イメージ: `public.ecr.aws/awsguru/aws-lambda-adapter`（`web-adapter` ではない）
- Function URL CORS: `OPTIONS` は CloudFormation 非サポート → POST のみ指定
- WSL2 Docker: `~/.docker/config.json` の `credsStore: desktop.exe` 削除必要
- **Function URL + FastAPI で CORS 二重付与に注意**: Function URL の CORS 設定と FastAPI CORSMiddleware を両方有効にすると `Access-Control-Allow-Origin` が2回出力されブラウザが拒否する → FastAPI 側は削除して Function URL に任せる

## ファイナンス機能（2026-02-16 追加）
- `/finance` スキル: ファイナンスボスネコペルソナ（東大ぱふぇっと手法ベース）
- `scripts/market-watch.py`: yfinance + MT5 NekoBridge 連携の市場監視デーモン
  - tmux chat Window の下ペインで常駐（`tmux split-window -t neko-pm:chat`）
  - `needs_position` フラグ: MT5 にポジションがない銘柄の利確通知をスキップ
- `config/market-alerts.json`: 監視銘柄とキーレベル設定
- `output/finance/YYYY-MM-DD.md`: 日付付き分析レポート（.gitignore で除外）
- **NekoBridge EA**: `GetFillingMode()` で filling mode 自動判定（XMTrading 対応）
  - EA ファイル: `/mnt/c/Users/alche/AppData/Roaming/MetaQuotes/Terminal/2FA8A7E69CED7DC259B1AD86A247F675/MQL5/Experts/NekoBridge.mq5`
  - US100 最小ロット: 0.1（0.01 は Invalid volume）

## トラブルシュート知見
- 詳細: [troubleshooting.md](troubleshooting.md)

## モバイル対応知見
- 詳細: [mobile-patterns.md](mobile-patterns.md)
