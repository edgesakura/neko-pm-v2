# kitten-backend Memory

## izakaya-agent プロジェクト知見

### ファイル構成
- `output/izakaya-agent/agent/main.py` - AgentCore エントリポイント、Strands Agent 初期化
- `output/izakaya-agent/agent/tools/search_restaurants.py` - Hotpepper + Google Places ハイブリッド検索
- `output/izakaya-agent/agent/tools/resolve_area.py` - Google Geocoding でエリア→座標変換
- `output/izakaya-agent/agent/tools/check_availability.py` - 空き状況確認
- `output/izakaya-agent/agent/utils/secrets.py` - API キー管理
- `output/izakaya-agent/agent/utils/memory.py` - 会話履歴・LTM 管理

### 注意点
- `search_restaurants()` 内の変数 shadowing に注意: `keyword` パラメータと genre 用の keyword 変数が衝突する → `genre_keyword` にリネームした
- Hotpepper API の `range` パラメータ: 1-5 のコード（1=300m, 2=500m, 3=1000m, 4=2000m, 5=3000m）
- _log() フォーマットは変更禁止（CloudWatch Insights 連携）
- Strands Agent の `@tool` デコレータで関数をツール化

### Hotpepper API レスポンス構造
- `shop.private_room`, `shop.wifi`, `shop.card` 等は `{"name": "あり"}` 形式の dict
- `shop.photo.pc.l` で PC 用大画像 URL
- `shop.catch` でキャッチフレーズ
- `shop.access` でアクセス情報

### Google Geocoding viewport
- `geometry.viewport.northeast/southwest` から半径推定可能
- `dlat * 111 km`, `dlon * 111 * cos(avg_lat) km` で距離変換
- 300m〜3000m にクランプ
