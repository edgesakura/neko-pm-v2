#!/usr/bin/env python3
"""
market-watch.py - テクニカルレベル監視 & MT5連携 通知スクリプト

東大ぱふぇっと手法に基づくキーレベル到達時に通知する。
MT5のNekoBridge EAと連携してポジション監視・注文も可能。
設定: config/market-alerts.json

使い方:
  python3 scripts/market-watch.py              # デーモンモード（常駐）
  python3 scripts/market-watch.py --once        # 1回だけチェック
  python3 scripts/market-watch.py --status      # 現在の状況表示
  python3 scripts/market-watch.py --mt5         # MT5ポジション表示
  python3 scripts/market-watch.py --add NQ=F 24000 below "テスト" "テストアクション"
  python3 scripts/market-watch.py --order BUY_LIMIT NAS100 0.1 24155 23900 25500
"""

import json
import sys
import time
import os
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

# --- Config ---
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "market-alerts.json"
STATE_PATH = BASE_DIR / "output" / ".market-watch-state.json"

# MT5 NekoBridge ファイルパス
MT5_FILES_DIR = Path("/mnt/c/Users/alche/AppData/Roaming/MetaQuotes/Terminal/2FA8A7E69CED7DC259B1AD86A247F675/MQL5/Files")
MT5_POSITIONS = MT5_FILES_DIR / "neko_positions.json"
MT5_COMMANDS = MT5_FILES_DIR / "neko_commands.json"
MT5_RESULTS = MT5_FILES_DIR / "neko_results.json"

JST = timezone(timedelta(hours=9))


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, default=str)


def load_state():
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            return json.load(f)
    return {"fired": {}}


def fetch_price(ticker):
    """yfinance で最新価格を取得"""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        hist = t.history(period="1d", interval="1m")
        if hist.empty:
            hist = t.history(period="2d")
        if not hist.empty:
            row = hist.iloc[-1]
            return {
                "price": float(row["Close"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "time": hist.index[-1].strftime("%Y-%m-%d %H:%M"),
            }
    except Exception as e:
        print(f"  [WARN] {ticker} 取得失敗: {e}", file=sys.stderr)
    return None


def check_level(price, level):
    """価格がレベルを突破しているか判定"""
    direction = level["direction"]
    target = level["price"]
    # 近接判定（0.3%以内で approaching）
    proximity = abs(price - target) / target
    if direction == "below" and price <= target:
        return "triggered"
    elif direction == "above" and price >= target:
        return "triggered"
    elif proximity <= 0.003:
        return "approaching"
    return None


def format_alert(ticker_name, level, price, status):
    """アラートメッセージを生成"""
    priority_icon = {"critical": "🚨", "high": "⚠️", "medium": "📊", "low": "ℹ️"}
    icon = priority_icon.get(level.get("priority", "medium"), "📊")
    status_text = "到達!" if status == "triggered" else "接近中"

    return (
        f"{icon} [{ticker_name}] {level['label']} {status_text}\n"
        f"   現在値: {price:.2f} → ターゲット: {level['price']}\n"
        f"   アクション: {level['action']}"
    )


def notify(message, config, priority="medium"):
    """通知を送信"""
    nc = config["notification"]
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
    log_line = f"[{now}] {message}"

    # 1. ログファイル（常に）
    log_path = nc.get("log_file", "")
    if log_path:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a") as f:
            f.write(log_line + "\n\n")

    # 2. ターミナル出力 + ベル
    print(log_line)
    if nc.get("terminal_bell") and priority in ("critical", "high"):
        print("\a", end="", flush=True)

    # 3. tmux popup notification
    try:
        import subprocess
        # tmux display-message: active window に 8 秒間ポップアップ表示
        short_msg = message.split("\n")[0][:120]
        subprocess.run(
            ["tmux", "display-message", "-d", "8000", f" {short_msg}"],
            capture_output=True, timeout=3
        )
    except Exception:
        pass  # tmux 未使用時は無視

    # 4. Webhook (Discord / Slack / LINE 等)
    webhook_url = nc.get("webhook_url", "")
    if webhook_url:
        try:
            import urllib.request
            payload = json.dumps({"content": message}).encode()
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            print(f"  [WARN] Webhook送信失敗: {e}", file=sys.stderr)


def is_market_hours(config):
    """市場時間内か判定（US先物はほぼ24h だが設定で絞れる）"""
    if not config.get("market_hours_only", False):
        return True
    mh = config.get("market_hours", {})
    now_utc = datetime.now(timezone.utc).hour
    start = mh.get("start_utc", 13)
    end = mh.get("end_utc", 6)
    # 跨ぎ対応（13:00 UTC - 06:00 UTC = JST 22:00 - 15:00）
    if start > end:
        return now_utc >= start or now_utc < end
    else:
        return start <= now_utc < end


def get_mt5_symbols():
    """MT5 の保有ポジション+未決注文のシンボル一覧を返す"""
    mt5 = read_mt5_positions()
    if not mt5:
        return set()
    symbols = set()
    for pos in mt5.get("positions", []):
        symbols.add(pos.get("symbol", "").upper())
    for order in mt5.get("orders", []):
        symbols.add(order.get("symbol", "").upper())
    return symbols


# yfinance ticker → MT5 symbol の対応表
TICKER_TO_MT5 = {
    "NQ=F": ["US100", "NAS100"],
    "ES=F": ["US500", "SP500"],
    "GC=F": ["GOLD", "XAUUSD"],
    "SI=F": ["SILVER", "XAGUSD"],
    "USDJPY=X": ["USDJPY"],
    "AUDUSD=X": ["AUDUSD"],
    "NZDUSD=X": ["NZDUSD"],
    "GBPUSD=X": ["GBPUSD"],
    "EURUSD=X": ["EURUSD"],
}


def has_mt5_position(ticker, mt5_symbols):
    """yfinance ticker に対応する MT5 ポジション/注文があるか"""
    candidates = TICKER_TO_MT5.get(ticker, [])
    for candidate in candidates:
        for sym in mt5_symbols:
            if candidate in sym:
                return True
    return False


def run_check(config, state, quiet=False):
    """1回のチェックサイクル"""
    cooldown = config["notification"].get("cooldown_minutes", 60) * 60
    now = time.time()
    alerts_fired = 0
    mt5_symbols = get_mt5_symbols()

    for asset in config["alerts"]:
        ticker = asset["ticker"]
        name = asset["name"]
        data = fetch_price(ticker)
        if not data:
            continue

        price = data["price"]
        if not quiet:
            print(f"  {name}: {price:.2f} ({data['time']})")

        for level in asset["levels"]:
            status = check_level(price, level)
            if not status:
                continue

            # needs_position チェック: ポジション/注文がなければスキップ
            if level.get("needs_position") and not has_mt5_position(ticker, mt5_symbols):
                if not quiet:
                    print(f"    [{level['label']}] ポジションなし→スキップ")
                continue

            # クールダウン判定
            key = f"{ticker}_{level['price']}_{level['direction']}"
            last_fired = state["fired"].get(key, 0)
            if now - last_fired < cooldown:
                if not quiet:
                    print(f"    [{level['label']}] クールダウン中（残 {int((cooldown - (now - last_fired)) / 60)}分）")
                continue

            # アラート発火
            msg = format_alert(name, level, price, status)
            notify(msg, config, level.get("priority", "medium"))
            state["fired"][key] = now
            alerts_fired += 1

    save_state(state)
    return alerts_fired


def show_status(config):
    """現在の全銘柄ステータスを表示"""
    print("=" * 70)
    print(f"📈 Market Watch Status - {datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')}")
    print("=" * 70)

    for asset in config["alerts"]:
        ticker = asset["ticker"]
        name = asset["name"]
        data = fetch_price(ticker)
        if not data:
            print(f"\n{name} ({ticker}): データ取得失敗")
            continue

        price = data["price"]
        print(f"\n{name} ({ticker}): {price:.2f}")
        print("-" * 50)

        for level in sorted(asset["levels"], key=lambda x: x["price"], reverse=True):
            dist = price - level["price"]
            pct = (dist / level["price"]) * 100
            direction = "↓" if level["direction"] == "below" else "↑"

            status = check_level(price, level)
            if status == "triggered":
                marker = "🔴 到達!"
            elif status == "approaching":
                marker = "🟡 接近"
            else:
                marker = "⚪"

            icon = {"critical": "🚨", "high": "⚠️", "medium": "📊"}.get(level.get("priority"), "ℹ️")
            print(f"  {marker} {icon} {level['price']:>10,.0f} {direction} {level['label']}")
            print(f"       距離: {dist:+,.0f} ({pct:+.2f}%) | {level['action']}")

    print(f"\n{'=' * 70}")


def read_mt5_positions():
    """MT5 NekoBridge からポジション情報を読み取る"""
    if not MT5_POSITIONS.exists():
        return None
    try:
        with open(MT5_POSITIONS) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"  [WARN] MT5データ読み取り失敗: {e}", file=sys.stderr)
        return None


def send_mt5_command(command):
    """MT5 NekoBridge にコマンドを送信"""
    try:
        MT5_FILES_DIR.mkdir(parents=True, exist_ok=True)
        with open(MT5_COMMANDS, "w") as f:
            json.dump(command, f, indent=2)
        print(f"  コマンド送信: {command.get('action')} {command.get('type', '')} {command.get('symbol', '')}")

        # 結果を待つ（最大10秒）
        for _ in range(20):
            time.sleep(0.5)
            if MT5_RESULTS.exists():
                with open(MT5_RESULTS) as f:
                    result = json.load(f)
                MT5_RESULTS.unlink()
                return result
        return {"success": False, "error": "Timeout - EA未応答（MT5でNekoBridge EAが稼働中か確認してにゃ）"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def show_mt5_status():
    """MT5のポジション・口座情報を表示"""
    data = read_mt5_positions()
    if not data:
        print("MT5 データなし。NekoBridge EA が稼働中か確認してにゃ〜")
        print(f"  期待パス: {MT5_POSITIONS}")
        return

    acct = data.get("account", {})
    print("=" * 70)
    print(f"🐱 MT5 Status - {data.get('timestamp', '?')}")
    print("=" * 70)
    print(f"  サーバー: {acct.get('server', '?')}")
    print(f"  残高:     {acct.get('balance', 0):>12,.2f} {acct.get('currency', '')}")
    print(f"  有効証拠金: {acct.get('equity', 0):>10,.2f}")
    print(f"  含み損益:  {acct.get('profit', 0):>11,.2f}")
    print(f"  余剰証拠金: {acct.get('free_margin', 0):>10,.2f}")
    margin_level = acct.get('margin_level', 0)
    if margin_level > 0:
        ml_warn = " ⚠️ 低い!" if margin_level < 200 else ""
        print(f"  証拠金維持率: {margin_level:>8,.1f}%{ml_warn}")

    positions = data.get("positions", [])
    if positions:
        print(f"\n📊 ポジション ({len(positions)}件)")
        print("-" * 70)
        total_profit = 0
        for p in positions:
            pnl = p.get("profit", 0) + p.get("swap", 0)
            total_profit += pnl
            pnl_icon = "🟢" if pnl >= 0 else "🔴"
            sl_str = f"SL:{p['sl']:.1f}" if p.get("sl", 0) > 0 else "SL:なし"
            tp_str = f"TP:{p['tp']:.1f}" if p.get("tp", 0) > 0 else "TP:なし"
            print(f"  {pnl_icon} {p['symbol']:>10} {p['type']:>4} {p['volume']:.2f}lot"
                  f"  建値:{p['open_price']:.1f} → 現在:{p['current_price']:.1f}"
                  f"  損益:{pnl:+,.0f}  {sl_str} {tp_str}")
        print(f"  {'─' * 50}")
        total_icon = "🟢" if total_profit >= 0 else "🔴"
        print(f"  {total_icon} 合計損益: {total_profit:+,.0f}")
    else:
        print("\n  ポジションなし")

    orders = data.get("orders", [])
    if orders:
        print(f"\n📋 未決注文 ({len(orders)}件)")
        print("-" * 70)
        for o in orders:
            sl_str = f"SL:{o['sl']:.1f}" if o.get("sl", 0) > 0 else ""
            tp_str = f"TP:{o['tp']:.1f}" if o.get("tp", 0) > 0 else ""
            print(f"  📌 {o['symbol']:>10} {o['type']:>12} {o['volume']:.2f}lot"
                  f"  価格:{o['price']:.1f} {sl_str} {tp_str}")

    print(f"\n{'=' * 70}")


def main():
    args = sys.argv[1:]
    config = load_config()
    state = load_state()

    if "--mt5" in args:
        show_mt5_status()
        return

    if "--order" in args:
        # --order TYPE SYMBOL VOLUME PRICE SL TP
        idx = args.index("--order")
        parts = args[idx+1:]
        if len(parts) < 4:
            print("Usage: --order TYPE SYMBOL VOLUME PRICE [SL] [TP]")
            print("  TYPE: BUY, SELL, BUY_LIMIT, SELL_LIMIT, BUY_STOP, SELL_STOP")
            print("  例: --order BUY_LIMIT NAS100 0.1 24155 23900 25500")
            sys.exit(1)
        cmd = {
            "action": "order",
            "type": parts[0],
            "symbol": parts[1],
            "volume": float(parts[2]),
            "price": float(parts[3]),
            "sl": float(parts[4]) if len(parts) > 4 else 0,
            "tp": float(parts[5]) if len(parts) > 5 else 0,
        }
        print(f"🐱 注文送信: {cmd['type']} {cmd['symbol']} {cmd['volume']}lot @ {cmd['price']}")
        if cmd["sl"]: print(f"   SL: {cmd['sl']}")
        if cmd["tp"]: print(f"   TP: {cmd['tp']}")
        result = send_mt5_command(cmd)
        if result.get("success"):
            print(f"  ✅ 成功! ticket: {result.get('ticket')}")
        else:
            print(f"  ❌ 失敗: {result.get('error')}")
        return

    if "--close" in args:
        idx = args.index("--close")
        if len(args) <= idx + 1:
            print("Usage: --close TICKET")
            sys.exit(1)
        ticket = int(args[idx + 1])
        result = send_mt5_command({"action": "close", "ticket": ticket})
        if result.get("success"):
            print(f"  ✅ 決済成功! ticket: {ticket}")
        else:
            print(f"  ❌ 失敗: {result.get('error')}")
        return

    if "--cancel" in args:
        idx = args.index("--cancel")
        if len(args) <= idx + 1:
            print("Usage: --cancel TICKET")
            sys.exit(1)
        ticket = int(args[idx + 1])
        result = send_mt5_command({"action": "cancel", "ticket": ticket})
        if result.get("success"):
            print(f"  ✅ キャンセル成功! ticket: {ticket}")
        else:
            print(f"  ❌ 失敗: {result.get('error')}")
        return

    if "--status" in args or "-s" in args:
        show_status(config)
        # MT5データがあれば併せて表示
        if MT5_POSITIONS.exists():
            print()
            show_mt5_status()
        return

    if "--once" in args or "-1" in args:
        print(f"[{datetime.now(JST).strftime('%H:%M JST')}] 単発チェック...")
        run_check(config, state)
        return

    if "--add" in args:
        # --add TICKER PRICE DIRECTION LABEL ACTION
        idx = args.index("--add")
        if len(args) < idx + 6:
            print("Usage: --add TICKER PRICE DIRECTION LABEL ACTION")
            sys.exit(1)
        ticker, price, direction, label, action = args[idx+1:idx+6]
        # Find or create asset entry
        asset = next((a for a in config["alerts"] if a["ticker"] == ticker), None)
        if not asset:
            asset = {"ticker": ticker, "name": ticker, "levels": []}
            config["alerts"].append(asset)
        asset["levels"].append({
            "price": float(price),
            "direction": direction,
            "label": label,
            "action": action,
            "priority": "high",
        })
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"追加: {ticker} {price} {direction} '{label}'")
        return

    # デーモンモード
    interval = config.get("check_interval_seconds", 300)
    print(f"🐱 Market Watch 起動にゃ〜 (間隔: {interval}秒)")
    print(f"   ログ: {config['notification'].get('log_file', 'なし')}")
    print(f"   監視銘柄: {', '.join(a['ticker'] for a in config['alerts'])}")
    print(f"   Ctrl+C で停止\n")

    while True:
        try:
            now = datetime.now(JST)
            if is_market_hours(config):
                print(f"[{now.strftime('%H:%M JST')}] チェック中...")
                fired = run_check(config, state)
                if fired:
                    print(f"  → {fired}件のアラート発火!")
            else:
                # 市場外は30分おきにログだけ
                if now.minute < interval // 60:
                    print(f"[{now.strftime('%H:%M JST')}] 市場時間外 (次: JST 22:00)")
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n停止にゃ〜")
            break
        except Exception as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            time.sleep(60)


if __name__ == "__main__":
    main()
