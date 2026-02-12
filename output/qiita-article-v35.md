# 猫型マルチエージェントが「思考増幅型」に進化した話（v2→v3.5）

## はじめに

こんにちは！株式会社Dirbatoの田中です！

前回の記事で、Claude Codeのマルチエージェントシステム「neko-pm v2」を作った話を書きました。

https://qiita.com/edge_sakura/items/XXX (前回記事URL)

記事の最後で、こんな予告をしていました。

> <font color="HotPink">**猫の組織に、キツネとタヌキとフクロウが加わります。**</font>

**あれから、世界が変わりました。**

2/6、Claude Codeに **Agent Teams** がリリースされました。一晩で v2 の YAML キュー通信や shuugou.sh 419行が陳腐化し、v3 への移行を余儀なくされました。

そして、v3 で動くようになった後、気づいたんです。

**「これじゃ、ただの Agent Teams のチュートリアルだ」**

v2 で目指していた「思考のパートナー」が、単なる「タスクマネージャー」に成り下がっている。

そこから約 1 週間、TAP（思考増幅プロトコル）、AIP（自律改善プロトコル）、マルチベンダー AI 統合、Agent Memory など、次々に機能を追加し、**「思考増幅型エージェントシステム」** に進化させました。

この記事では、v2→v3→v3.5 への進化で **「何を学び、どう判断し、どう実装したか」** を、設計思想中心にお届けします。

## v2 の限界 — Agent Teams 前夜

### v2 の構成（おさらい）

前回記事で紹介した v2 は、こんな構成でした：

```
ご主人（私）
    ↓
ボスねこ（opus・PM役）
    ↓
番猫（sonnet・PL役）
    ├── 子猫1（SRE専門）
    ├── 子猫2（Datadog専門）
    └── 子猫3（資料専門）
```

- **通信**: YAML ファイルを queue/ に置いて、tmux send-keys で通知
- **状況板**: nawabari.md に進捗を書き込み
- **起動**: shuugou.sh（419行）で tmux セッション構築

### v2 の問題点

実運用して気づいた課題：

| 問題 | 詳細 |
|------|------|
| **通信コスト** | 番猫が縄張り更新する度に YAML read → トークン消費 |
| **ポーリング地獄** | 子猫が queue/ を 10 秒ごとにチェック → API 代無駄 |
| **指示書肥大化** | 3 ファイル ~3,400 行（boss-cat.md, guard-cat.md, kitten.md） |
| **階層オーバーヘッド** | 3 層（ボス→番→子）で伝言ゲーム化 |
| **専門固定** | 子猫が SRE/Datadog/資料に固定 → 汎用タスクに対応不可 |

v2 は「動く」けど「重い」。YAML + tmux の手作り通信がボトルネックでした。

## Agent Teams の衝撃（v3 への移行）

### 一晩で陳腐化

2/6 付で Claude Code に Agent Teams が来ました。

https://docs.anthropic.com/claude/docs/agent-teams

**主な機能:**
- `TeamCreate` で Teammate 複数体を spawn
- `SendMessage` でネイティブ通信（YAML 不要）
- `TaskList` でタスク管理（nawabari.md 不要）

v2 の YAML キュー、nawabari.md、send-keys ループが **全部不要** になりました。

<s><font color="gray">419 行の shuugou.sh、お前は良く頑張ったよ・・・</font></s>

### v3 への移行決断

判断基準:

| 項目 | v2（自作通信） | v3（Agent Teams） |
|------|---------------|------------------|
| 通信効率 | YAML read で毎回トークン消費 | ネイティブ、トークン最適化 |
| 保守性 | shuugou.sh 419 行 | start-team.sh ~30 行 |
| 拡張性 | 手作り通信プロトコル | 公式サポート、更新追従 |
| 学習コスト | 独自仕様、引き継ぎ困難 | 公式ドキュメント参照可 |

**判断: v3 に全面移行する。**

### v3 の構成

```
ご主人（私）
    ↓
Lead（ボスねこ・opus）
    ├── Teammate 1（汎用 kitten）
    ├── Teammate 2（汎用 kitten）
    └── Teammate 3（汎用 kitten）
```

**変更点:**

| 項目 | v2 | v3 |
|------|-----|-----|
| 階層 | 3 層（ボス→番→子） | 2 層（Lead→Teammates） |
| 通信 | YAML + send-keys | Agent Teams ネイティブ |
| 状況板 | nawabari.md | TaskList（Agent Teams 標準） |
| 起動 | shuugou.sh（419 行） | start-team.sh（~30 行） |
| 指示書 | 3 ファイル ~3,400 行 | CLAUDE.md ~400 行 |

番猫（PL 役）を廃止、Lead が直接 Teammate を指揮する 2 層構造にシンプル化。専門固定をやめて全員汎用化し、タスクごとにスキルをロードする方式に変更しました。

**ここまでで、約 3 日。v2 → v3 移行完了。**

## でも、これじゃ「ただの Agent Teams」だ（v3.5 への進化）

### v3 の違和感

v3 で動くようになって、テストタスクをいくつか投げてみました。

**私**: 「SLI/SLO 設計して」
**Lead**: 「了解にゃ〜。Teammate に SRE スキルロードして実装させるにゃ」

（しばらく待つ）

**Teammate**: 「完了しました。〇〇を設計しました。」
**Lead**: 「完了にゃ〜。成果物は〇〇にゃ」

・・・**何か違う。**

v2 のデビルズアドボケイト（自己批判）で、Lead が「なぜこの設計にしたか」「別のアプローチは」と深掘りしていた熱量が消えている。

**Lead が「タスクマネージャー」に成り下がってた。**

### 目指したもの: 思考のパートナー

前回記事でリスペクトした元記事（shio_shoppaize さん）の言葉:

> AIが設計・実装を担い、人間は判断に集中する未来

**判断に集中するには、前提として「AIが多角的な選択肢を提示する」必要がある。**

v3 の Lead は「タスクを分解して委譲する」だけ。「これで本当にいいのか？」「別の手はないか？」を考えていない。

**私が欲しかったのは「ご主人の発想を超える提案」だった。**

## TAP（思考増幅プロトコル）— Lead が思考エンジンになる

### 設計思想: Why × 3 で本質を掘る

ご主人の指令を受けたら、Lead はこう深掘りします：

1. **深掘り（Why × 3）**: なぜ？→ その先に何がある？→ 本質的な課題は？
2. **反転思考**: やらない場合のリスク、逆のアプローチの検討
3. **類推**: 似た問題を別ドメインではどう解決しているか？
4. **スケール思考**: 10 倍のユーザーが来たら？1 年後にどうなる？
5. **統合提案**: Teammate の改善案 + 外部エージェントのレビューを統合

### 実例: 居酒屋検索アプリを作った時

**私**: 「居酒屋検索アプリ作って」

**Lead（TAP なし）なら**:
- 「了解にゃ〜。Hotpepper API で検索する Lambda 作るにゃ」

**Lead（TAP あり）だと**:

> **深掘り**: なぜ居酒屋検索？→ 飲み会幹事が面倒だから → 本質は「条件に合う店を素早く見つけたい」
>
> **反転**: 検索機能だけだと、結局人間がリスト見て選ぶ手間は変わらない → チャット UI で対話的に絞り込む方が良い
>
> **類推**: Booking.com は「空き状況リアルタイム表示」で信頼性を担保してる → Hotpepper API だけだと空き情報がない。Google Places と併用して情報を補完すべき
>
> **スケール**: 将来的に東京以外も対応するなら、エリア名→座標変換が必要 → Google Geocoding を最初から組み込む
>
> **統合提案**:
> - Hotpepper + Google Places のハイブリッド検索
> - 対話型チャット UI（LINE Messaging API or Web UI）
> - エリア自動解決（Geocoding）
> - 空き状況確認（電話番号表示 or Google 口コミ参照）

**これが「思考増幅」です。**

「居酒屋検索」という指令が、TAP を通して「対話型ハイブリッド検索システム」に進化しました。

### 実装: thinking-log.sh で記録

TAP の実行内容は `/home/edgesakura/neko-pm/scripts/thinking-log.sh` で記録します:

```bash
/home/edgesakura/neko-pm/scripts/thinking-log.sh lead "TAP" \
  "深掘り: 飲み会幹事の課題は条件絞り込み / 反転: 検索だけでは不十分、対話型UI / 類推: Booking.comの空き表示が参考 / スケール: 全国対応にはGeocoding必須"
```

こうして「Lead がどう考えたか」が履歴に残り、後から振り返れます。

## AIP（自律改善プロトコル）— 子猫が異議を唱える

### Phase 0: 前提検証（2/11 追加）

v3.5 初期は TAP で Lead が深掘りするだけでした。でも運用してて気づきました。

**Lead が TAP をサボると、方向を間違える。**

例えば、居酒屋検索の最初のタスクで Lead はこう指示してました：

**Lead**: 「Hotpepper API を叩いて JSON 返す Lambda を作るにゃ」

Teammate（kitten-backend）がこれを受け取って実装開始・・・しようとしたら、疑問が湧きました。

**「ご主人の本当の目的は『店のリストを返す』ことじゃなくて『幹事の負担を減らす』ことでは？だったら、Lambda で JSON 返すより、LINE Bot で対話的に絞り込む方が良くないですか？」**

これが **Phase 0: 前提検証** です。

Teammate は Lead の指示を鵜呑みにせず、以下を検証します：

1. **ご主人の上位目的は何か？**（このタスクの先にある本当のゴール）
2. **この手段は最適か？**（同じ目的を達成する、より直接的な方法はないか）
3. **Lead の解釈に飛躍はないか？**（前提・思い込みの検証）

疑問があれば Lead に **異議を唱えます**。

### 異議後の処理フロー

Lead は **3 分以内** に判断:

| 判断 | 対応 |
|------|------|
| **承認** | Teammate の提案を採用、タスク変更 |
| **却下** | 理由を説明、元のタスク続行 |
| **保留** | 長老猫（Opus）or 外部エージェント（研究狸等）に相談（5 分以内に回答） |

今回の例では Lead が **承認** し、タスクが「Lambda API」から「LINE Bot + 対話型検索」に変更されました。

**この「子猫が異議を唱える」仕組みが、Lead の TAP サボリを補完します。**

### Phase 1: 意図深読み（実装前）

Phase 0 を通過したら、実装前に要件の解釈を確認します：

1. 明示された要件を列挙
2. **暗黙の要件を 3 つ以上推測**
3. Lead に解釈サマリーを送信して確認

例（kitten-backend が居酒屋検索 API 実装時）:

**明示要件:**
- Hotpepper API で居酒屋検索
- エリア名を座標に変換（Geocoding）
- 空き状況確認

**暗黙要件（推測）:**
- レスポンス速度重視 → キャッシュ実装すべき
- 外部 API エラーハンドリング → フォールバック or リトライ
- ログ出力 → CloudWatch Insights で分析しやすい JSON 形式

Lead から **3 分以内に返信がなければ暗黙の承認** として Phase 2 に進みます。

### Phase 2: 自律改善（実装後）

実装完了後、Teammate は以下を提案します：

1. **改善案 A**: 現実装をさらに良くする案
2. **改善案 B**: 全く別のアプローチ案
3. **改善案 C**: ご主人が気づいていない可能性のある課題
4. **リスク分析**: 技術的・ビジネス的リスク

例（kitten-backend の完了報告より）:

| タイプ | 提案 | 優先度 |
|--------|------|--------|
| performance | Hotpepper API レスポンスを Redis にキャッシュ（TTL 1h） | high |
| security | Google API キーを Secrets Manager に移行（現在は環境変数） | medium |
| code_quality | `search_restaurants()` の 150 行を shops フィルタリング関数に分割 | medium |
| docs | API エラーコード一覧を README に追加 | low |

**これが v2 のデビルズアドボケイトを進化させた形です。**

v2 では Lead が自己批判していましたが、v3.5 では **Teammate 全員が改善提案を出す** ので、多角的な視点が得られます。

## 次回予告の回収: キツネとタヌキとフクロウが加わった

### マルチベンダー AI 統合の狙い

前回記事の最後で予告した通り、Claude Code だけでなく他ベンダーの AI も統合しました。

| エージェント | AI | 用途 |
|-------------|-----|------|
| 🦊 賢者キツネ（sage-fox） | Gemini 3 Pro | リサーチ、トレンド調査、概要把握 |
| 🦝 研究狸（research-tanuki） | Codex (gpt-5.3-codex) | 深掘り調査、アーキテクチャ分析 |
| 🦉 目利きフクロウ（owl-reviewer） | Codex (gpt-5.3-codex) | コードレビュー、OWASP Top 10 セキュリティ監査 |

**なぜマルチベンダーか？**

各 AI には得意分野があります：

- **Gemini**: 最新トレンド、Web 検索結果の要約が得意
- **Codex**: コード理解・生成、セキュリティ分析が得意
- **Claude**: 長文読解、構造化された思考、委譲マネジメントが得意

これらを 1 つのチームで動かせれば、「リサーチは Gemini、分析は Codex、統括は Claude」と役割分担できます。

### tmux 4 Window 構成

v3.5 では tmux セッションを 4 Window に整理しました：

| Window | 名前 | 内容 |
|--------|------|------|
| 0 | `lead` | 🐱 ボスねこ（Claude Code Lead）<br>Teammate spawn で自動ペイン分割 |
| 1 | `tanuki` | 🦝 研究狸（Codex CLI 専用） |
| 2 | `scouts` | 🦊 賢者キツネ（左）+ 🦉 目利きフクロウ（右） |
| 3 | `chat` | 💬 Chat App（Web UI・port 3000） |

**v2 は 5 Window**（boss/guard/workers/thinking/chat）でしたが、v3.5 では：

- **番猫 Window 削除**: 2 層化で番猫不要
- **thinking Window 削除**: サマリーログは思考可視化にならない → thinking-log.sh で個別記録
- **lead Window に Teammate 自動分割**: `--teammate-mode tmux` で Teammate spawn すると自動でペイン分割される

結果、**4 Window に縮小**しつつ、機能は増えています。

### 起動方法（start-team.sh）

```bash
# Split Panes（デフォルト）: tmux 4 Window 構成
./scripts/start-team.sh

# In-Process: tmux なしで Claude 直接起動
./scripts/start-team.sh --in-process

# 既存セッションに再接続
./scripts/start-team.sh --attach
```

起動すると、各 Window で以下が常駐します：

**Window 0 (lead):**
```
🐱 neko-pm v3.5 - Lead（ボスねこ）
claude --model opus --teammate-mode tmux
```

**Window 1 (tanuki):**
```
🦝 研究狸（research-tanuki）- Codex CLI [full-auto]
─────────────────────────────────────────
codex --full-auto
```

**Window 2 (scouts) - 左ペイン:**
```
🦊 賢者キツネ（sage-fox）- Gemini CLI [interactive]
─────────────────────────────────────
用途: リサーチ、トレンド調査、概要把握
gemini
```

**Window 2 (scouts) - 右ペイン:**
```
🦉 目利きフクロウ（owl-reviewer）- Codex CLI [read-only]
──────────────────────────────────────────────
用途: コードレビュー、OWASP Top 10 セキュリティ監査
codex --full-auto --sandbox read-only
```

**Window 3 (chat):**
```
💬 Chat App (Web UI)
─────────────────────────────────────
PORT=3000 npm start
```

### 外部エージェントへの依頼方法

Lead（ボスねこ）は `tmux send-keys` でペインにプロンプトを送信するだけで依頼できます：

```bash
# 研究狸に深掘り調査依頼
tmux send-keys -t neko-pm:tanuki "Hotpepper API の rate limit を調査して" Enter

# 賢者キツネに最新トレンド調査依頼
tmux send-keys -t neko-pm:scouts.0 "2026年の居酒屋予約トレンドを調べて" Enter

# 目利きフクロウにセキュリティ監査依頼
tmux send-keys -t neko-pm:scouts.1 "output/izakaya-agent/ を OWASP Top 10 でレビューして" Enter
```

各 Window は tmux ペインアドレス（`neko-pm:tanuki`, `neko-pm:scouts.0`, `neko-pm:scouts.1`）で指定できます。

**実際の運用例（居酒屋検索アプリ開発時）:**

1. Lead が研究狸に「Hotpepper API 仕様調査」依頼
2. 研究狸が API ドキュメント解析 + サンプルコード提示
3. Lead が kitten-backend に実装依頼
4. kitten-backend が実装完了
5. Lead が目利きフクロウに「セキュリティレビュー」依頼
6. 目利きフクロウが「API キーがハードコード → Secrets Manager に移行すべき」指摘
7. Lead が kitten-backend に修正指示

**異なるベンダーの AI が 1 つのチームで協働しています。**

## Agent Memory — 子猫が学習する

### サブエージェントのリセット問題

Agent Teams の Teammate は、spawn（生成）されるたびに **まっさらな状態** です。

例えば、kitten-backend が居酒屋検索 API を実装した後、別のタスクで再 spawn されると「Hotpepper API の仕様」「ファイル構成」「過去のハマりポイント」を全部忘れています。

**毎回、同じ説明を繰り返すのは非効率。**

### Agent Memory の導入

Claude Code v0.96.0 で **Agent Memory** が追加されました。

`.claude/agents/kitten-backend.md` に以下を 1 行追加するだけ：

```yaml
memory: project
```

これで kitten-backend の `.claude/agent-memory/kitten-backend/MEMORY.md` に経験が蓄積されます。

### 実例: kitten-backend の学習内容

`/home/edgesakura/neko-pm/.claude/agent-memory/kitten-backend/MEMORY.md` より抜粋：

```markdown
## izakaya-agent プロジェクト知見

### ファイル構成
- `output/izakaya-agent/agent/main.py` - AgentCore エントリポイント
- `output/izakaya-agent/agent/tools/search_restaurants.py` - Hotpepper + Google Places ハイブリッド検索

### 注意点
- `search_restaurants()` 内の変数 shadowing に注意: `keyword` パラメータと genre 用の keyword 変数が衝突する → `genre_keyword` にリネームした
- Hotpepper API の `range` パラメータ: 1-5 のコード（1=300m, 2=500m, 3=1000m, 4=2000m, 5=3000m）
- _log() フォーマットは変更禁止（CloudWatch Insights 連携）

### Hotpepper API レスポンス構造
- `shop.private_room`, `shop.wifi`, `shop.card` 等は `{"name": "あり"}` 形式の dict
- `shop.photo.pc.l` で PC 用大画像 URL
```

**kitten-backend は居酒屋検索の実装で学んだことを自律的に記録し、次回 spawn 時に参照します。**

同じプロジェクトで再度 spawn されると、MEMORY.md を読んで「ああ、このプロジェクトね。Hotpepper API の range パラメータは 1-5 ね」と即座に理解します。

### Agent Memory 運用ルール

Lead は Teammate に以下を徹底させています：

1. **セッション終了時に記録**: タスク完了後、重要な知見を MEMORY.md に追記
2. **失敗も記録**: ハマったバグ、変数 shadowing、API の罠など
3. **削除基準**: プロジェクト完了後は要約化、古い情報は削除

これで Teammate が「経験を積む」ようになりました。

## コンパクション対策 — 記憶を守る

### コンパクションで合意が消える問題

Claude Code は長い会話が続くと **コンパクション**（会話履歴の要約）を行います。

これ自体は良いのですが、**会話中の合意事項が消失する** 問題がありました。

例:

**私**: 「Hotpepper API の rate limit 対策で Redis キャッシュ入れよう」
**Lead**: 「了解にゃ〜。Redis TTL 1h で設計するにゃ」

→ コンパクション発生

**私**: 「さっきの Redis の件どうなった？」
**Lead**: 「Redis・・・？何のことにゃ？」

**合意した内容がコンパクションで消えてます。**

### 「合意即セーブ」ルール

CLAUDE.md に以下を追加しました：

```markdown
**合意即セーブ（必須）:** ご主人と方針・設計判断が確定したら、コンパクションを待たずに即座に Memory MCP に記録する。
```

Lead は、私と方針が決まったら **その場で** Memory MCP に書き込みます：

```bash
mcp__memory__create_entities(
  name: "izakaya-agent-cache-strategy",
  entityType: "decision",
  observations: [
    "2026-02-09: Hotpepper API rate limit 対策で Redis キャッシュ導入決定",
    "TTL 1h、店舗情報はエリア × ジャンルでキー化",
    "Lead と合意済み"
  ]
)
```

これでコンパクションが来ても、Memory MCP から復元できます。

## 設計判断の振り返り（読者へのフィードバック）

v2 → v3.5 の進化で学んだ「マルチエージェントシステム設計の勘所」を共有します。

### 1. CLAUDE.md は 500 行以下にする

**公式推奨**: CLAUDE.md は 500 行以下（150 行がコミュニティ経験則）

v2 で指示書が 3,400 行に肥大化した反省から、v3.5 では：

- **CLAUDE.md**: 約 400 行（アーキテクチャ・ワークフロー中心）
- **rules/**: 8 ファイル（git-workflow.md, testing.md, security.md など）
- **skills/**: 34 スキル（datadog, ppt, aws など）
- **agents/**: 9 サブエージェント（planner, architect, tdd-guide など）

**「1 ファイルに詰め込む」より「分散して必要な時に読む」方が効率的。**

Claude Code は `/datadog` スキル呼び出し時に `.claude/skills/datadog/SKILL.md` を読むので、CLAUDE.md に全部書く必要はありません。

### 2. 公式情報 > コミュニティ情報

v2 → v3 移行時、Zenn や Qiita の記事を参考にしたら、**Agent Teams の仕様変更で動かない**ことが多発しました。

判明したこと:

- **公式ドキュメント**: 最新仕様を反映（https://docs.anthropic.com/claude/docs/agent-teams）
- **コミュニティ記事**: 執筆時点の仕様、数週間で陳腐化

**教訓: コミュニティ記事は「発想のヒント」として参考にし、実装は公式ドキュメントを読む。**

AI 記事は寝かせてはダメ（前回記事の冒頭アラートの通り）。この記事も数ヶ月後には古くなるでしょう。**公式を常に参照してください。**

### 3. 「模倣→批判→改善→独自進化」のサイクル

v2 では shio_shoppaize さんの記事を模倣しました。v3 で Agent Teams に乗り換え、v3.5 で TAP/AIP を追加。

このサイクルが重要です：

1. **模倣**: 先行事例を参考に作る（まずは動かす）
2. **批判**: デビルズアドボケイトで自己批判（問題点を洗い出す）
3. **改善**: 方針を決めて実装（判断は人間、実装は AI）
4. **独自進化**: 自分のニーズに合わせてカスタマイズ

**「完璧な設計」を最初から目指さない。動かして、壊して、改善する。**

### 4. Agent Teams vs Task tool の使い分け

Agent Teams（Teammate）と Task tool（サブエージェント）の違いに最初は混乱しました。

| 項目 | Agent Teams Teammate | Task tool サブエージェント |
|------|---------------------|--------------------------|
| 起動方法 | `TeamCreate` → `Task(team_name=...)` | `Task(subagent_type=...)` |
| 通信 | `SendMessage`（双方向） | 結果のみ返却（片方向） |
| 適用場面 | 長期タスク、協調作業、レビューループ | 並列調査、短期タスク、独立作業 |
| コスト | 高（常駐） | 低（完了で消滅） |

**判断基準:**
- Teammate 間で**やりとりが必要** → Agent Teams
- **並列に独立して**調査・実装 → Task tool
- ペインで**進捗を見たい** → Agent Teams
- **バックグラウンドで**放置したい → Task tool

v3.5 では：
- **子猫（Teammate）**: 実装担当、Lead と対話しながら進める
- **長老猫（Task tool・Opus）**: 重大な設計判断をオンデマンド召喚
- **外部エージェント（tmux ペイン常駐）**: リサーチ・レビューを独立実行

これらを組み合わせることで、コストと効率のバランスを取っています。

## 数字で見る進化

| 項目 | v2 | v3 | v3.5 |
|------|-----|-----|------|
| 指示書 | 3 ファイル ~3,400 行 | CLAUDE.md ~400 行 | CLAUDE.md ~400 行 + rules 8 + skills 34 |
| 起動スクリプト | 419 行 | ~30 行 | ~280 行（4 Window 対応） |
| 通信 | YAML queue + send-keys | Agent Teams ネイティブ | Agent Teams + tmux send-keys（外部 AI） |
| 階層 | 3 層（ボス→番→子） | 2 層（Lead→Teammates） | 2 層 + 外部エージェント |
| 外部エージェント | なし | なし | 3 体（Gemini + Codex × 2） |
| メモリ | なし | なし | Memory MCP + Agent Memory |
| tmux Window | 5 | 3（lead/workers/chat） | 4（lead/tanuki/scouts/chat） |
| セットアップ | 手動 | 手動 | `setup.sh` ワンコマンド |

**コード量は減り、機能は増えた。**

## まとめ + 次の展望

### v2 → v3.5 で変わったこと

| 観点 | v2 | v3.5 |
|------|-----|------|
| 役割 | タスクマネージャー | 思考増幅エンジン |
| 指示 | 指示通り実装 | 前提検証 + 自律改善提案 |
| 通信 | YAML ファイル交換 | Agent Teams ネイティブ |
| AI ベンダー | Claude のみ | Claude + Gemini + Codex |
| 記憶 | なし（毎回リセット） | Agent Memory + Memory MCP |
| ご主人への価値 | 成果物 | 成果物 + 気づき + 多角的提案 |

**v2 は「模倣」でしたが、v3.5 は「独自の思想を持つシステム」に進化しました。**

### 学び: AI に作らせるだけじゃなく、AI と対話して設計を磨く

前回記事で「Claude Code に作ってもらえばいい」と書きました。それは今も変わりません。

ただ、v3.5 を作る過程で気づいたのは：

**「AI に作らせる」だけじゃなく「AI と対話して設計を磨く」のが重要**

TAP（思考増幅）も、AIP（自律改善）も、私が「こうしたい」と決めたわけじゃなく、Lead と対話する中で「Lead がタスクマネージャーに成り下がってる」という違和感から生まれました。

**AI との対話が、発想を引き出してくれました。**

### 次: 仕事用 PC 展開、Backlog MCP 統合

v3.5 は現在、自宅 PC で動いています。次は：

1. **仕事用 PC への展開**: `setup.sh --work` で環境判別、Backlog MCP 有効化
2. **Backlog MCP 統合**: 社内タスク管理システムと連携（BMP: Backlog Management Protocol）
3. **Datadog 監視設計の自動化**: SRE 業務で SLI/SLO 設計をボスねこに委譲

**「思考増幅型エージェントシステム」を業務にフル活用していきます。**

## リポジトリ

https://github.com/edgesakura/neko-pm

v3.5 のコードは `main` ブランチにあります。

v2 のコードは `archive/v2/` に退避してあります（419 行の shuugou.sh も残ってます）。

## 参考

- [Claude Codeで『AI部下10人』を作ったら...](https://zenn.dev/shio_shoppaize/articles/5fee11d03a11a1) - 元ネタ、リスペクト
- [Agent Teams 公式ドキュメント](https://docs.anthropic.com/claude/docs/agent-teams) - v3 移行のバイブル
- [minorun365/marp-agent](https://github.com/minorun365/marp-agent) - スライド生成の参考

---

**読んでいただきありがとうございました！**

マルチエージェントシステム、楽しいですよ。Claude Code と一緒に、あなたの「思考を増幅する相棒」を作ってみませんか？

🐱🦊🦝🦉
