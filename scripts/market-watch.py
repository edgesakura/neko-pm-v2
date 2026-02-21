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
import math
import sys
import time
import os
import subprocess
from collections import deque
from datetime import datetime, timezone, timedelta
from pathlib import Path

# --- Config ---
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "market-alerts.json"
STATE_PATH = BASE_DIR / "output" / ".market-watch-state.json"
MARKET_STATUS_PATH = BASE_DIR / "output" / "market-status.json"

# MT5 NekoBridge ファイルパス
MT5_FILES_DIR = Path("/mnt/c/Users/alche/AppData/Roaming/MetaQuotes/Terminal/2FA8A7E69CED7DC259B1AD86A247F675/MQL5/Files")
MT5_POSITIONS = MT5_FILES_DIR / "neko_positions.json"
MT5_COMMANDS = MT5_FILES_DIR / "neko_commands.json"
MT5_RESULTS = MT5_FILES_DIR / "neko_results.json"

JST = timezone(timedelta(hours=9))

# --- テクニカル分析キャッシュ（同一チェックサイクル内の再取得防止）---
_ta_cache = {}


# --- FSM (Finite State Machine) for Level Trading ---
class LevelFSM:
    """各レベルの自動売買状態を管理する FSM"""

    STATES = ["idle", "approaching", "armed", "confirmed", "ordered", "cooldown"]

    def __init__(self, ticker, level, state_dict=None):
        self.ticker = ticker
        self.level = level
        self.level_key = f"{ticker}_{level['price']}_{level['direction']}"

        # 状態復元 or 初期化
        if state_dict:
            self.state = state_dict.get("state", "idle")
            self.entered_at = state_dict.get("entered_at")
            self.prev_price = state_dict.get("prev_price")
            self.armed_at = state_dict.get("armed_at")
            self.last_5m_check = state_dict.get("last_5m_check")
            self.last_5m_bar_time = state_dict.get("last_5m_bar_time")
            self.ordered_at = state_dict.get("ordered_at")
            self.last_score_detail = None
        else:
            self.state = "idle"
            self.entered_at = None
            self.prev_price = None
            self.armed_at = None
            self.last_5m_check = None
            self.last_5m_bar_time = None
            self.ordered_at = None
            self.last_score_detail = None

    def to_dict(self):
        """FSM 状態を辞書化（永続化用）"""
        return {
            "state": self.state,
            "entered_at": self.entered_at,
            "prev_price": self.prev_price,
            "armed_at": self.armed_at,
            "last_5m_check": self.last_5m_check,
            "last_5m_bar_time": self.last_5m_bar_time,
            "ordered_at": self.ordered_at,
        }

    def get_zone_width(self):
        """ゾーン幅を取得（未指定時は price * 0.003 でフォールバック）"""
        return self.level.get("zone_width", self.level["price"] * 0.003)

    def is_in_zone(self, price):
        """価格がゾーン内か判定"""
        zone_width = self.get_zone_width()
        target = self.level["price"]
        return abs(price - target) <= zone_width

    def is_in_approach_buffer(self, price):
        """価格が approach バッファ（zone_width * 1.5）内か判定"""
        zone_width = self.get_zone_width()
        target = self.level["price"]
        return abs(price - target) <= zone_width * 1.5

    def update(self, current_price, config, mt5_data, now, warmup=False):
        """FSM 状態を更新（1サイクルごとに呼ばれる）"""
        auto_trade = config.get("auto_trade", {})
        if not auto_trade.get("enabled", False):
            # auto_trade 無効時は FSM を動かさない
            return None

        # ウォームアップ中は価格記録のみ（誤クロス防止）
        if warmup:
            self.prev_price = current_price
            return None

        zone_width = self.get_zone_width()
        target = self.level["price"]
        direction = self.level["direction"]

        # 状態遷移ロジック
        if self.state == "idle":
            # idle → armed（価格がゾーン内に直接突入した場合、approaching をスキップ）
            if self.is_in_zone(current_price):
                self.state = "armed"
                self.armed_at = now
                self.last_5m_check = None
                self.last_5m_bar_time = None
                self.prev_price = current_price
                return {"transition": "armed", "message": f"[FSM] {self.level_key} → armed (ゾーン直接突入: {price_fmt(current_price)})"}
            # idle → approaching
            elif self.is_in_approach_buffer(current_price):
                self.state = "approaching"
                self.entered_at = now
                self.prev_price = current_price
                return {"transition": "approaching", "message": f"[FSM] {self.level_key} → approaching (価格: {price_fmt(current_price)})"}

        elif self.state == "approaching":
            # approaching → armed (ヒステリシス: 前回値がゾーン外 かつ 今回値がゾーン内)
            if self.prev_price is not None and not self.is_in_zone(self.prev_price) and self.is_in_zone(current_price):
                self.state = "armed"
                self.armed_at = now
                self.last_5m_check = None
                self.last_5m_bar_time = None
                return {"transition": "armed", "message": f"[FSM] {self.level_key} → armed (ゾーン内突入: {price_fmt(current_price)})"}

            # approaching → idle (バッファ外に出た)
            if not self.is_in_approach_buffer(current_price):
                self.state = "idle"
                self.entered_at = None
                self.prev_price = None
                return {"transition": "idle", "message": f"[FSM] {self.level_key} → idle (バッファ外: {price_fmt(current_price)})"}

            self.prev_price = current_price

        elif self.state == "armed":
            # armed 状態では 5m 足で反転パターンを確認
            # アプローチバッファ外まで出たら idle に戻る（ゾーン境界のチャタリング防止）
            if not self.is_in_approach_buffer(current_price):
                self.state = "idle"
                self.entered_at = None
                self.prev_price = None
                self.armed_at = None
                return {"transition": "idle", "message": f"[FSM] {self.level_key} → idle (バッファ外脱出: {price_fmt(current_price)})"}

            # 5m 足確認（前回から 60秒以上経過した場合のみ）
            if self.last_5m_check is None or (now - self.last_5m_check) >= 60:
                confirmed = self._check_5m_confirmation(config)
                self.last_5m_check = now
                if confirmed:
                    self.state = "confirmed"
                    return {"transition": "confirmed", "message": f"[FSM] {self.level_key} → confirmed (反転パターン確認!)"}

        elif self.state == "confirmed":
            # confirmed → ordered (MT5 注文送信)
            # リスクチェック前に mt5_data を再取得（同サイクル内の古いスナップショット問題を回避）
            fresh_mt5_data = read_mt5_positions()
            if self._check_trading_conditions(config, fresh_mt5_data or mt5_data, now):
                order_result = self._send_order(fresh_mt5_data or mt5_data)
                if order_result.get("success"):
                    self.state = "ordered"
                    self.ordered_at = now
                    return {"transition": "ordered", "message": f"[FSM] {self.level_key} → ordered (注文送信成功: ticket={order_result.get('ticket')})"}
                else:
                    # 注文失敗 → armed に戻る（再試行可能に）
                    self.state = "armed"
                    return {"transition": "armed", "message": f"[FSM] {self.level_key} → armed (注文失敗: {order_result.get('error')})"}
            else:
                # リスクチェック失敗 → armed に戻る
                self.state = "armed"
                return {"transition": "armed", "message": f"[FSM] {self.level_key} → armed (リスクチェック NG)"}

        elif self.state == "ordered":
            # ordered → cooldown (即座に移行)
            cooldown_minutes = auto_trade.get("cooldown_after_order_minutes", 120)
            if (now - self.ordered_at) >= cooldown_minutes * 60:
                self.state = "cooldown"
                return {"transition": "cooldown", "message": f"[FSM] {self.level_key} → cooldown"}

        elif self.state == "cooldown":
            # cooldown → idle (クールダウン完了 + 価格が rearm_distance_pct 以上離れた)
            rearm_dist_pct = auto_trade.get("rearm_distance_pct", 0.5)
            rearm_dist = zone_width * rearm_dist_pct
            if abs(current_price - target) >= rearm_dist:
                self.state = "idle"
                self.entered_at = None
                self.prev_price = None
                self.armed_at = None
                self.ordered_at = None
                return {"transition": "idle", "message": f"[FSM] {self.level_key} → idle (rearm 完了)"}

        return None

    def _is_pin_bar(self, open_price, high, low, close, direction, conf):
        """ピンバー判定（売りなら上ヒゲ、買いなら下ヒゲが長い）"""
        body = abs(close - open_price)
        if body == 0:
            return False

        if direction == "above":  # 売り: 上ヒゲが長い
            wick = high - max(open_price, close)
        else:  # 買い: 下ヒゲが長い
            wick = min(open_price, close) - low

        range_size = high - low
        if range_size == 0:
            return False

        wick_body_ratio = wick / body
        wick_range_ratio = wick / range_size

        return (wick_body_ratio >= conf["pin_bar_wick_body_ratio"] and
                wick_range_ratio >= conf["pin_bar_wick_range_ratio"])

    def _is_engulfing(self, prev_bar, curr_bar, direction, conf):
        """包み足判定（現バーの実体が前バーの実体を包む）"""
        prev_body = abs(prev_bar["Close"] - prev_bar["Open"])
        curr_body = abs(curr_bar["Close"] - curr_bar["Open"])

        if prev_body == 0:
            return False

        body_ratio = curr_body / prev_body
        if body_ratio < conf["engulfing_body_ratio"]:
            return False

        # 実体の包含チェック
        prev_top = max(prev_bar["Open"], prev_bar["Close"])
        prev_bottom = min(prev_bar["Open"], prev_bar["Close"])
        curr_top = max(curr_bar["Open"], curr_bar["Close"])
        curr_bottom = min(curr_bar["Open"], curr_bar["Close"])

        if direction == "above":  # 売り: 現バーが陰線で前バーを包む
            return (curr_bar["Close"] < curr_bar["Open"] and
                    curr_top >= prev_top and curr_bottom <= prev_bottom)
        else:  # 買い: 現バーが陽線で前バーを包む
            return (curr_bar["Close"] > curr_bar["Open"] and
                    curr_top >= prev_top and curr_bottom <= prev_bottom)

    def _relative_volume(self, volume, volume_sma20, conf):
        """相対出来高判定（Volume > 0 の場合のみ）"""
        # NaN チェック: NaN != NaN
        if volume == 0 or volume_sma20 == 0 or volume_sma20 != volume_sma20:
            return False

        ratio = volume / volume_sma20
        return ratio >= conf["relative_volume_threshold"]

    def _zone_reject_depth(self, high, low, close, price, zone_width, direction, conf):
        """ゾーン反発判定（zone_width の 25% 以上タッチしてから戻した）"""
        zone_depth_threshold = zone_width * conf["zone_reject_depth_pct"]

        if direction == "above":  # 売り: price 付近まで上昇してから下落
            touch_depth = high - price
            reject = price - close
            return touch_depth >= zone_depth_threshold and reject > 0
        else:  # 買い: price 付近まで下落してから上昇
            touch_depth = price - low
            reject = close - price
            return touch_depth >= zone_depth_threshold and reject > 0

    def _check_5m_confirmation(self, config):
        """5m 足で反転パターンを確認"""
        try:
            # MT5 専用シンボルは先物データで代用
            ta_ticker = MT5_TA_PROXY.get(self.ticker, self.ticker)
            # 5m 足取得（キャッシュ: 1分ごとに更新）
            df_5m = fetch_ohlcv(ta_ticker, "5m", "1d")
            if df_5m is None or len(df_5m) < 3:
                return False

            # 最後の確定バー（iloc[-2]）を使用
            if len(df_5m) < 2:
                return False

            last_bar = df_5m.iloc[-2]
            bar_time = df_5m.index[-2].timestamp()

            # 新バー確定の検知（前回と timestamp が変わったか）
            if self.last_5m_bar_time is not None and bar_time == self.last_5m_bar_time:
                # まだ同じバー → 確認不要
                return False

            self.last_5m_bar_time = bar_time

            # RSI 計算
            df_5m = calc_technicals(df_5m.copy())
            if len(df_5m) < 2:
                return False

            last = df_5m.iloc[-2]
            prev = df_5m.iloc[-3] if len(df_5m) >= 3 else last
            prev2 = df_5m.iloc[-4] if len(df_5m) >= 4 else prev

            # === スコア制確認 ===
            conf = config.get("auto_trade", {}).get("confirmation", {})
            if not conf:
                # confirmation 設定がない場合は旧ロジックにフォールバック
                rsi = last.get("RSI_14", 50)
                rsi_prev = prev.get("RSI_14", 50)
                close = last["Close"]
                open_price = last["Open"]
                direction = self.level["direction"]
                if direction == "above":
                    if rsi > 60 and rsi < rsi_prev and close < open_price:
                        return True
                elif direction == "below":
                    if rsi < 40 and rsi > rsi_prev and close > open_price:
                        return True
                return False

            # データ取得
            direction = self.level["direction"]
            price = self.level["price"]
            zone_width = self.level.get("zone_width", 100)

            high = last["High"]
            low = last["Low"]
            close = last["Close"]
            open_price = last["Open"]
            volume = last.get("Volume", 0)
            volume_sma20 = last.get("Volume_SMA20", 0)

            rsi = last.get("RSI_14", 50)
            rsi_prev = prev.get("RSI_14", 50)
            macd_hist = last.get("MACD_Hist", 0)
            macd_hist_prev = prev.get("MACD_Hist", 0)
            macd_hist_2nd_prev = prev2.get("MACD_Hist", 0)
            bb_upper = last.get("BB_Upper", float("inf"))
            bb_lower = last.get("BB_Lower", 0)

            # スコア初期化
            score_zone = 0
            score_momentum = 0
            score_price_action = 0
            score_context = 0

            # 1. ゾーン反発（必須）
            if self._zone_reject_depth(high, low, close, price, zone_width, direction, conf):
                score_zone = 2

            # 2. モメンタム: RSI ターン
            score_rsi = 0
            if direction == "above":  # 売り
                threshold = conf.get("rsi_sell_threshold", 62)
                if rsi > threshold and abs(rsi - rsi_prev) >= conf.get("rsi_min_delta", 1.0) and rsi < rsi_prev:
                    score_rsi = 1
            else:  # 買い
                threshold = conf.get("rsi_buy_threshold", 38)
                if rsi < threshold and abs(rsi - rsi_prev) >= conf.get("rsi_min_delta", 1.0) and rsi > rsi_prev:
                    score_rsi = 1

            # 3. モメンタム: MACD ヒストグラム2本連続縮小
            score_macd = 0
            macd_hist_bars = conf.get("macd_hist_bars", 2)
            if macd_hist_bars == 2:
                # 2本連続縮小を確認
                if direction == "above":  # 売り: ヒストグラムが2本連続で減少
                    if macd_hist < macd_hist_prev < macd_hist_2nd_prev:
                        score_macd = 1
                else:  # 買い: ヒストグラムが2本連続で増加
                    if macd_hist > macd_hist_prev > macd_hist_2nd_prev:
                        score_macd = 1
            else:
                # 1本比較にフォールバック（macd_hist_bars != 2 の場合）
                if direction == "above":
                    if macd_hist < macd_hist_prev:
                        score_macd = 1
                else:
                    if macd_hist > macd_hist_prev:
                        score_macd = 1

            score_momentum = score_rsi + score_macd

            # 4. プライスアクション: ピンバー
            score_pin = 0
            if self._is_pin_bar(open_price, high, low, close, direction, conf):
                score_pin = 1

            # 5. プライスアクション: 包み足
            score_engulf = 0
            if self._is_engulfing(prev, last, direction, conf):
                score_engulf = 1

            score_price_action = score_pin + score_engulf

            # 6. コンテキスト: BB 再侵入
            score_bb = 0
            prev_close = prev["Close"]
            prev_bb_upper = prev.get("BB_Upper", float("inf"))
            prev_bb_lower = prev.get("BB_Lower", 0)
            if direction == "above":  # 売り: 前バー BB 上抜け → 現バー BB 内
                if prev_close > prev_bb_upper and close <= bb_upper:
                    score_bb = 1
            else:  # 買い: 前バー BB 下抜け → 現バー BB 内
                if prev_close < prev_bb_lower and close >= bb_lower:
                    score_bb = 1

            # 7. コンテキスト: 相対出来高
            score_vol = 0
            if self._relative_volume(volume, volume_sma20, conf):
                score_vol = 1

            score_context = score_bb + score_vol

            # 総合スコア
            total_score = score_zone + score_momentum + score_price_action + score_context

            # 閾値
            if direction == "above":
                threshold = conf.get("score_threshold_sell", 5)
            else:
                threshold = conf.get("score_threshold_buy", 4)

            # 必須ゲート
            zone_ok = score_zone > 0
            momentum_ok = score_momentum >= 1
            price_action_ok = score_price_action >= 1
            score_ok = total_score >= threshold

            confirmed = zone_ok and momentum_ok and price_action_ok and score_ok

            # ログ出力
            vol_str = str(score_vol) if volume > 0 else "SKIP"
            result_str = "CONFIRMED" if confirmed else "REJECTED"
            score_detail = {
                "total": total_score,
                "threshold": threshold,
                "zone": score_zone,
                "rsi": score_rsi,
                "macd": score_macd,
                "pin": score_pin,
                "engulf": score_engulf,
                "bb": score_bb,
                "vol": vol_str,
                "confirmed": confirmed,
                "rsi_value": round(rsi, 1),
                "macd_hist": round(macd_hist, 2),
                "timeframe": "5m",
            }
            print(f"[FSM] {self.level_key} 確認スコア: {total_score}/{threshold} "
                  f"(zone:{score_zone} rsi:{score_rsi} macd:{score_macd} pin:{score_pin} "
                  f"engulf:{score_engulf} bb:{score_bb} vol:{vol_str}) → {result_str}",
                  file=sys.stderr)

            # 詳細を FSM に保存（アラート表示用）
            self.last_score_detail = score_detail
            return confirmed
        except Exception as e:
            print(f"  [WARN] FSM 5m確認失敗 ({self.level_key}): {e}", file=sys.stderr)
            return False

    def _check_trading_conditions(self, config, mt5_data, now):
        """注文前のリスクチェック"""
        auto_trade = config.get("auto_trade", {})

        # 0. MT5 データが取得できない場合は注文拒否（安全側）
        if not mt5_data:
            print(f"  [FSM] {self.level_key} リスクチェック: MT5データ取得不可→注文拒否", file=sys.stderr)
            return False

        # 1. 同一シンボルのポジション数チェック
        max_positions = auto_trade.get("max_positions_per_symbol", 1)
        if mt5_data:
            positions = mt5_data.get("positions", [])
            mt5_symbols = TICKER_TO_MT5.get(self.ticker, [])
            position_count = sum(1 for p in positions if any(sym in p.get("symbol", "").upper() for sym in mt5_symbols))
            if position_count >= max_positions:
                print(f"  [FSM] {self.level_key} リスクチェック: ポジション数上限 ({position_count}/{max_positions})", file=sys.stderr)
                return False

            # 2. 同一シンボルの未決注文チェック
            orders = mt5_data.get("orders", [])
            order_count = sum(1 for o in orders if any(sym in o.get("symbol", "").upper() for sym in mt5_symbols))
            if order_count > 0:
                print(f"  [FSM] {self.level_key} リスクチェック: 未決注文あり ({order_count}件)", file=sys.stderr)
                return False

        # 3. allowed_sessions チェック（JST 固定）
        now_jst = datetime.fromtimestamp(now, JST)
        now_time = now_jst.strftime("%H:%M")

        allowed_sessions = auto_trade.get("allowed_sessions", [])
        in_session = False
        for session in allowed_sessions:
            start_jst = session.get("start_jst", "00:00")
            end_jst = session.get("end_jst", "23:59")
            # 跨ぎ対応（22:00 - 06:00 など）
            if start_jst > end_jst:
                if now_time >= start_jst or now_time < end_jst:
                    in_session = True
                    break
            else:
                if start_jst <= now_time < end_jst:
                    in_session = True
                    break

        if not in_session:
            print(f"  [FSM] {self.level_key} リスクチェック: セッション時間外 ({now_time})", file=sys.stderr)
            return False

        # 4. blackout_periods チェック
        blackout_periods = auto_trade.get("blackout_periods", [])
        for period in blackout_periods:
            start_jst = period.get("start_jst", "00:00")
            end_jst = period.get("end_jst", "00:00")
            if start_jst > end_jst:
                if now_time >= start_jst or now_time < end_jst:
                    print(f"  [FSM] {self.level_key} リスクチェック: ブラックアウト期間 ({now_time})", file=sys.stderr)
                    return False
            else:
                if start_jst <= now_time < end_jst:
                    print(f"  [FSM] {self.level_key} リスクチェック: ブラックアウト期間 ({now_time})", file=sys.stderr)
                    return False

        return True

    def _send_order(self, mt5_data):
        """MT5 に指値注文を送信"""
        try:
            # MT5 シンボル取得
            mt5_symbols = TICKER_TO_MT5.get(self.ticker, [])
            if not mt5_symbols:
                return {"success": False, "error": f"MT5 シンボルマッピングなし: {self.ticker}"}

            symbol = mt5_symbols[0]  # 最初の候補を使用

            # 注文タイプ決定
            direction = self.level["direction"]
            if direction == "above":
                order_type = "SELL_LIMIT"  # 上値抵抗帯で売り
            else:
                order_type = "BUY_LIMIT"   # 下値サポートで買い

            # 価格・SL・TP
            price = self.level["price"]

            # SL/TP が level に指定されていればそれを使用、なければ 0（なし）
            sl = self.level.get("sl", 0)
            tp = self.level.get("tp", 0)

            # ロット数（level に指定があればそれを使用、なければデフォルト 0.1）
            volume = self.level.get("volume", 0.1)

            # MT5 コマンド送信
            cmd = {
                "action": "order",
                "type": order_type,
                "symbol": symbol,
                "volume": volume,
                "price": price,
                "sl": sl,
                "tp": tp,
            }

            result = send_mt5_command(cmd)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}


def _cache_key(ticker, interval, period=""):
    """キャッシュキーを生成（5m足は60秒キャッシュ、それ以外は5分キャッシュ）"""
    if interval == "5m":
        # 5m 足は60秒キャッシュ（新バー確定検知のため）
        cache_window = int(time.time() // 60)
    else:
        # それ以外は5分キャッシュ
        cache_window = int(time.time() // 300)
    return f"{ticker}_{interval}_{period}_{cache_window}"


def calc_technicals(df):
    """DataFrame にテクニカル指標カラムを追加して返す（pandas のみ使用）"""
    import numpy as np
    c = df["Close"]

    # RSI(14) — loss=0→RSI=100, gain=0→RSI=0 を明示処理
    delta = c.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(loss != 0, 100.0)   # 上昇一辺倒 → RSI=100
    rsi = rsi.where(gain != 0, 0.0)     # 下落一辺倒 → RSI=0
    df["RSI_14"] = rsi

    # MACD(12,26,9) — adjust=False で TV/MT5 と整合
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    # ボリンジャーバンド(20,2)
    df["BB_Mid"] = c.rolling(20).mean()
    bb_std = c.rolling(20).std()
    df["BB_Upper"] = df["BB_Mid"] + 2 * bb_std
    df["BB_Lower"] = df["BB_Mid"] - 2 * bb_std

    # EMA — adjust=False で TV/MT5 と整合
    df["EMA_20"] = c.ewm(span=20, adjust=False).mean()
    df["EMA_50"] = c.ewm(span=50, adjust=False).mean()
    df["EMA_200"] = c.ewm(span=200, adjust=False).mean()

    # Volume SMA(20) — 相対出来高判定用
    if "Volume" in df.columns:
        df["Volume_SMA20"] = df["Volume"].rolling(20).mean()

    return df


def fetch_ohlcv(ticker, interval="1h", period="30d"):
    """yfinance で OHLCV データを取得（キャッシュ付き）"""
    key = _cache_key(ticker, interval, period)
    if key in _ta_cache:
        return _ta_cache[key]
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        df = t.history(period=period, interval=interval)
        if not df.empty:
            _ta_cache[key] = df
            return df
    except Exception as e:
        print(f"  [WARN] {ticker} {interval} 取得失敗: {e}", file=sys.stderr)
    return None


def resample_to_4h(df_1h):
    """1h足を4h足にリサンプル（未確定足を除外）"""
    try:
        agg = df_1h.resample("4h").agg({
            "Open": "first", "High": "max", "Low": "min",
            "Close": "last", "Volume": "sum"
        }).dropna()
        # 最後のバケットが4本未満（未確定足）なら除外
        if len(agg) > 1:
            count = df_1h.resample("4h")["Close"].count()
            if count.iloc[-1] < 4:
                agg = agg.iloc[:-1]
        return agg if len(agg) > 0 else None
    except Exception:
        return None


def analyze_timeframe(df):
    """単一時間足のテクニカルサマリーを返す"""
    if df is None or len(df) < 30:
        return None
    df = calc_technicals(df.copy())
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last

    rsi = last.get("RSI_14", 50)
    macd_h = last.get("MACD_Hist", 0)
    macd_h_prev = prev.get("MACD_Hist", 0)
    close = last["Close"]
    ema20 = last.get("EMA_20", close)
    ema50 = last.get("EMA_50", close)
    ema200 = last.get("EMA_200", close)
    bbu = last.get("BB_Upper", close)
    bbl = last.get("BB_Lower", close)
    bb_mid = last.get("BB_Mid", close)

    # BB 幅に対する位置（0=下限, 1=上限）
    bb_width = bbu - bbl if bbu != bbl else 1
    bb_pos = (close - bbl) / bb_width

    return {
        "rsi": round(rsi, 1),
        "macd_hist": round(macd_h, 2),
        "macd_hist_prev": round(macd_h_prev, 2),
        "macd_expanding": abs(macd_h) > abs(macd_h_prev),
        "macd_turning_up": macd_h > macd_h_prev,    # ヒストグラム上向き（反転兆候）
        "macd_turning_down": macd_h < macd_h_prev,  # ヒストグラム下向き（失速兆候）
        "close": round(close, 2),
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "ema200": round(ema200, 2),
        "ema_trend": "up" if ema20 > ema50 else "down",
        "ema_long_trend": "up" if ema50 > ema200 else "down",
        "bb_upper": round(bbu, 2),
        "bb_lower": round(bbl, 2),
        "bb_pos": round(bb_pos, 2),
    }


# MT5 専用シンボル → テクニカル分析用の yfinance 先物ティッカー
MT5_TA_PROXY = {
    "GOLD": "GC=F",     # ゴールド現物 → 先物でテクニカル代用
    "SILVER": "SI=F",   # シルバー現物 → 先物でテクニカル代用
}


def analyze_multi_timeframe(ticker):
    """マルチタイムフレーム テクニカル分析"""
    result = {"1h": None, "4h": None, "1d": None,
              "signal": "neutral", "confidence": "low", "reasons": []}

    # MT5 専用シンボルは先物データでテクニカル分析を代用
    ta_ticker = MT5_TA_PROXY.get(ticker, ticker)

    # 1h足
    df_1h = fetch_ohlcv(ta_ticker, "1h", "30d")
    if df_1h is not None and len(df_1h) > 30:
        result["1h"] = analyze_timeframe(df_1h)

        # 4h足（1hからリサンプル）
        df_4h = resample_to_4h(df_1h)
        if df_4h is not None and len(df_4h) > 30:
            result["4h"] = analyze_timeframe(df_4h)

    # 日足
    df_1d = fetch_ohlcv(ta_ticker, "1d", "1y")
    if df_1d is not None and len(df_1d) > 30:
        result["1d"] = analyze_timeframe(df_1d)

    # 複合シグナル判定
    _evaluate_signal(result)
    return result


def _evaluate_signal(result):
    """マルチタイムフレーム結果から売買シグナルを判定"""
    sell_score = 0
    buy_score = 0
    reasons = []

    tf_sell_count = 0  # 売り方向の時間足数
    tf_buy_count = 0   # 買い方向の時間足数

    for tf_name in ("1h", "4h", "1d"):
        tf = result.get(tf_name)
        if not tf:
            continue

        tf_sell = 0
        tf_buy = 0

        # 売りシグナル条件
        if tf["rsi"] > 70:
            sell_score += 2; tf_sell += 1
            reasons.append(f"{tf_name} RSI {tf['rsi']} 買われすぎ")
        elif tf["rsi"] > 65:
            sell_score += 1; tf_sell += 1
            reasons.append(f"{tf_name} RSI {tf['rsi']} 高め")

        if tf["macd_hist"] > 0 and tf["macd_turning_down"]:
            sell_score += 1; tf_sell += 1
            reasons.append(f"{tf_name} MACD勢い減速")

        if tf["bb_pos"] > 0.9:
            sell_score += 1; tf_sell += 1
            reasons.append(f"{tf_name} BB上限タッチ")

        # 買いシグナル条件
        if tf["rsi"] < 30:
            buy_score += 2; tf_buy += 1
            reasons.append(f"{tf_name} RSI {tf['rsi']} 売られすぎ")
        elif tf["rsi"] < 35:
            buy_score += 1; tf_buy += 1
            reasons.append(f"{tf_name} RSI {tf['rsi']} 低め")

        if tf["macd_hist"] < 0 and tf["macd_turning_up"]:
            buy_score += 1; tf_buy += 1
            reasons.append(f"{tf_name} MACD反転兆候")

        if tf["bb_pos"] < 0.1:
            buy_score += 1; tf_buy += 1
            reasons.append(f"{tf_name} BB下限タッチ")

        if tf_sell > 0:
            tf_sell_count += 1
        if tf_buy > 0:
            tf_buy_count += 1

    # シグナル判定（売り/買い衝突時は差分で判定、2TF以上の合意を重視）
    net = sell_score - buy_score
    if abs(net) < 2:
        pass  # 衝突 → neutral
    elif sell_score >= 4 and tf_sell_count >= 2:
        result["signal"] = "sell"
        result["confidence"] = "high" if sell_score >= 6 else "medium"
    elif buy_score >= 4 and tf_buy_count >= 2:
        result["signal"] = "buy"
        result["confidence"] = "high" if buy_score >= 6 else "medium"
    elif sell_score >= 4:
        result["signal"] = "sell"
        result["confidence"] = "low"
    elif buy_score >= 4:
        result["signal"] = "buy"
        result["confidence"] = "low"
    elif sell_score >= 2:
        result["signal"] = "sell"
        result["confidence"] = "low"
    elif buy_score >= 2:
        result["signal"] = "buy"
        result["confidence"] = "low"

    result["reasons"] = reasons


def format_ta_summary(ta, tf_name):
    """単一時間足のテクニカルを1行にフォーマット"""
    if not ta:
        return f"  [{tf_name}] データ不足"

    rsi_icon = "⚠️" if ta["rsi"] > 70 or ta["rsi"] < 30 else ""
    macd_dir = "📈拡大" if ta["macd_expanding"] else "📉縮小"
    trend = "📈上昇" if ta["ema_trend"] == "up" else "📉下落"

    bb_label = "上限" if ta["bb_pos"] > 0.8 else "下限" if ta["bb_pos"] < 0.2 else "中間"

    return f"  [{tf_name}] RSI:{ta['rsi']}{rsi_icon} | MACD:{macd_dir} | {trend} | BB:{bb_label}"


def format_signal(analysis):
    """シグナル判定結果をフォーマット"""
    sig = analysis["signal"]
    conf = analysis["confidence"]
    reasons = analysis["reasons"]

    if sig == "sell":
        icon = "🔴"
        label = "戻り売りシグナル"
    elif sig == "buy":
        icon = "🟢"
        label = "押し目買いシグナル"
    else:
        icon = "⚪"
        label = "明確なシグナルなし"

    conf_str = {"high": "高", "medium": "中", "low": "低"}.get(conf, "?")
    lines = [f"  {icon} {label} (確度: {conf_str})"]
    if reasons:
        lines.append(f"  理由: {' + '.join(reasons[:5])}")
    return "\n".join(lines)


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
    return {"fired": {}, "fsm": {}, "prev_prices": {}}


def get_mt5_watchlist():
    """MT5 NekoBridge の watchlist 価格を取得"""
    data = read_mt5_positions()
    if not data:
        return {}
    watchlist = {}
    for item in data.get("watchlist", []):
        sym = item.get("symbol", "").upper()
        if sym:
            watchlist[sym] = item
    return watchlist


def fetch_price_mt5(ticker, mt5_watchlist):
    """MT5 watchlist から価格を取得（前方一致で限月付きシンボルにも対応）"""
    candidates = TICKER_TO_MT5.get(ticker, [])
    for candidate in candidates:
        # 完全一致を先に試す
        item = mt5_watchlist.get(candidate)
        if item and item.get("bid", 0) > 0:
            return {
                "price": float(item["bid"]),
                "high": float(item.get("high", 0)),
                "low": float(item.get("low", 0)),
                "time": "MT5 live",
                "source": "mt5",
            }
        # 前方一致で探す（US100 → US100-MAR26 等）
        for sym, data in mt5_watchlist.items():
            if sym.startswith(candidate) and data.get("bid", 0) > 0:
                return {
                    "price": float(data["bid"]),
                    "high": float(data.get("high", 0)),
                    "low": float(data.get("low", 0)),
                    "time": "MT5 live",
                    "source": "mt5",
                }
    return None


def price_fmt(price):
    """価格帯に応じた表示桁数を返す"""
    if price < 10:
        return f"{price:.5f}"   # FX (AUDUSD 0.70561)
    elif price < 1000:
        return f"{price:.3f}"   # USDJPY 153.175, SILVER 75.408
    else:
        return f"{price:.2f}"   # GOLD 4951.71, NQ 24618.18


def fetch_price(ticker, mt5_watchlist=None):
    """価格を取得（MT5 優先、なければ yfinance）"""
    # MT5 watchlist から取得を試みる
    if mt5_watchlist:
        mt5_data = fetch_price_mt5(ticker, mt5_watchlist)
        if mt5_data:
            return mt5_data

    # MT5 専用シンボルは yfinance フォールバックなし
    if ticker in MT5_ONLY_TICKERS:
        return None

    # yfinance フォールバック
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
                "source": "yfinance",
            }
    except Exception as e:
        print(f"  [WARN] {ticker} 取得失敗: {e}", file=sys.stderr)
    return None


def check_level(price, level, zone_width=None):
    """価格がレベルを突破しているか判定（ゾーン対応）"""
    direction = level["direction"]
    target = level["price"]

    # ゾーン幅取得（未指定時は level から取得、それもなければ price * 0.003）
    if zone_width is None:
        zone_width = level.get("zone_width", target * 0.003)

    # ゾーン判定（中心±zone_width）
    in_zone = abs(price - target) <= zone_width
    in_approach_buffer = abs(price - target) <= zone_width * 1.5

    if in_zone:
        return "triggered"
    elif in_approach_buffer:
        return "approaching"
    return None


def format_score_detail(score):
    """5m足スコア詳細を表示用文字列にする"""
    if not score:
        return ""
    marks = []
    for key, label in [("zone", "ゾーン反発"), ("rsi", "RSI"), ("macd", "MACD"),
                        ("pin", "ピンバー"), ("engulf", "包み足"), ("bb", "BB再侵入"), ("vol", "出来高")]:
        val = score.get(key, 0)
        if val == "SKIP":
            marks.append(f"{label}:SKIP")
        elif val > 0:
            marks.append(f"{label}:✅")
        else:
            marks.append(f"{label}:−")
    result = "✅ CONFIRMED" if score.get("confirmed") else "❌ REJECTED"
    return (
        f"   🔍 5m足確認スコア: {score['total']}/{score['threshold']} {result}\n"
        f"      {' | '.join(marks)}\n"
        f"      RSI={score.get('rsi_value', '?')} MACD_Hist={score.get('macd_hist', '?')}"
    )


def format_alert(ticker_name, level, price, status, analysis=None, score_detail=None):
    """アラートメッセージを生成（テクニカル分析付き）"""
    priority_icon = {"critical": "🚨", "high": "⚠️", "medium": "📊", "low": "ℹ️"}
    icon = priority_icon.get(level.get("priority", "medium"), "📊")
    status_text = "到達!" if status == "triggered" else "接近中"

    msg = (
        f"{icon} [{ticker_name}] {level['label']} {status_text}\n"
        f"   現在値: {price_fmt(price)} → ターゲット: {level['price']}\n"
        f"   アクション: {level['action']}"
    )

    if analysis and analysis.get("1h"):
        msg += "\n   📊 テクニカル分析:"
        for tf in ("1h", "4h", "1d"):
            if analysis.get(tf):
                msg += "\n  " + format_ta_summary(analysis[tf], tf)
        msg += "\n" + format_signal(analysis)

    if score_detail:
        msg += "\n" + format_score_detail(score_detail)

    return msg


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
# MT5 専用シンボル（yfinance にないもの）はティッカー=MT5シンボルとして扱う
TICKER_TO_MT5 = {
    "NQ=F": ["US100", "NAS100"],  # US100-MAR26 等の限月付きも前方一致でヒット
    "ES=F": ["US500", "SP500"],
    "GC=F": ["GOLD", "XAUUSD"],
    "SI=F": ["SILVER", "XAGUSD"],
    "GOLD": ["GOLD"],       # ゴールド現物（MT5専用・XMTrading）
    "SILVER": ["SILVER"],   # シルバー現物（MT5専用・XMTrading）
    "USDJPY=X": ["USDJPY"],
    "AUDUSD=X": ["AUDUSD"],
    "NZDUSD=X": ["NZDUSD"],
    "GBPUSD=X": ["GBPUSD"],
    "EURUSD=X": ["EURUSD"],
}

# MT5 専用シンボル（yfinance フォールバックなし）
MT5_ONLY_TICKERS = {"GOLD", "SILVER"}

# --- 変動率アラート用の価格履歴バッファ ---
# ticker → deque of (timestamp, price)
_price_history = {}


def record_price(ticker, price, now):
    """価格を履歴バッファに記録"""
    if ticker not in _price_history:
        _price_history[ticker] = deque(maxlen=120)  # 最大120分分（1分間隔）
    _price_history[ticker].append((now, price))


def check_volatility(ticker, name, price, now, config):
    """変動率アラートをチェック。アラート文字列を返す or None"""
    vol_cfg = config.get("volatility_alert", {})
    if not vol_cfg.get("enabled", False):
        return None

    # 銘柄ごとの上書き設定
    asset_override = None
    for asset in config.get("alerts", []):
        if asset["ticker"] == ticker:
            asset_override = asset.get("volatility_override", {})
            break

    window = (asset_override or {}).get("window_minutes", vol_cfg.get("window_minutes", 30))
    threshold = (asset_override or {}).get("threshold_pct", vol_cfg.get("threshold_pct", 1.0))
    cooldown = vol_cfg.get("cooldown_minutes", 30) * 60

    history = _price_history.get(ticker)
    if not history or len(history) < 2:
        return None

    # window 分前の価格を探す
    cutoff = now - window * 60
    old_price = None
    for ts, p in history:
        if ts >= cutoff:
            old_price = p
            break
    if old_price is None or old_price == 0:
        return None

    change_pct = (price - old_price) / old_price * 100

    if abs(change_pct) >= threshold:
        direction = "📈 急騰" if change_pct > 0 else "📉 急落"
        return (
            f"🔔 [{name}] {direction} {change_pct:+.2f}%（{window}分間）\n"
            f"   {price_fmt(old_price)} → {price_fmt(price)}"
        )
    return None


# 変動率アラートのクールダウン管理
_vol_alert_fired = {}


def has_mt5_position(ticker, mt5_symbols):
    """yfinance ticker に対応する MT5 ポジション/注文があるか"""
    candidates = TICKER_TO_MT5.get(ticker, [])
    for candidate in candidates:
        for sym in mt5_symbols:
            if candidate in sym:
                return True
    return False


def run_check(config, state, quiet=False, warmup=False):
    """1回のチェックサイクル（FSM 統合版）"""
    cooldown = config["notification"].get("cooldown_minutes", 60) * 60
    now = time.time()
    alerts_fired = 0
    mt5_symbols = get_mt5_symbols()
    mt5_watchlist = get_mt5_watchlist()
    mt5_data = read_mt5_positions()
    analysis_cache = {}  # 同一銘柄の分析を再利用

    # FSM 辞書（既存状態から復元）
    fsm_states = state.get("fsm", {})
    prev_prices = state.get("prev_prices", {})

    for asset in config["alerts"]:
        ticker = asset["ticker"]
        name = asset["name"]
        data = fetch_price(ticker, mt5_watchlist)
        if not data:
            continue

        price = data["price"]
        if not quiet:
            print(f"  {name}: {price_fmt(price)} ({data['time']})")

        # 前回価格を保存
        prev_prices[ticker] = price

        # 価格履歴に記録 + 変動率チェック
        record_price(ticker, price, now)
        if not warmup:
            vol_cooldown = config.get("volatility_alert", {}).get("cooldown_minutes", 30) * 60
            vol_key = f"vol_{ticker}"
            last_vol_fired = _vol_alert_fired.get(vol_key, 0)
            if now - last_vol_fired >= vol_cooldown:
                vol_msg = check_volatility(ticker, name, price, now, config)
                if vol_msg:
                    notify(vol_msg, config, "high")
                    _vol_alert_fired[vol_key] = now
                    alerts_fired += 1

        for level in asset["levels"]:
            # --- 既存の通知ロジック（approaching/triggered） ---
            status = check_level(price, level)
            if status:
                # needs_position チェック: ポジション/注文がなければスキップ
                if level.get("needs_position") and not has_mt5_position(ticker, mt5_symbols):
                    if not quiet:
                        print(f"    [{level['label']}] ポジションなし→スキップ")
                else:
                    # クールダウン判定
                    key = f"{ticker}_{level['price']}_{level['direction']}"
                    last_fired = state["fired"].get(key, 0)
                    if now - last_fired < cooldown:
                        if not quiet:
                            print(f"    [{level['label']}] クールダウン中（残 {int((cooldown - (now - last_fired)) / 60)}分）")
                    else:
                        # テクニカル分析（レベル到達時のみ実行、同一銘柄はキャッシュ）
                        if ticker not in analysis_cache:
                            try:
                                analysis_cache[ticker] = analyze_multi_timeframe(ticker)
                            except Exception as e:
                                print(f"    [WARN] テクニカル分析失敗: {e}", file=sys.stderr)
                                analysis_cache[ticker] = None
                        analysis = analysis_cache[ticker]

                        # アラート発火（FSM スコア詳細があれば付加）
                        level_key = f"{ticker}_{level['price']}_{level['direction']}"
                        fsm_score = None
                        if level_key in fsm_states:
                            fsm_obj = fsm_states[level_key]
                            if isinstance(fsm_obj, LevelFSM):
                                fsm_score = fsm_obj.last_score_detail
                        msg = format_alert(name, level, price, status, analysis, fsm_score)
                        notify(msg, config, level.get("priority", "medium"))
                        state["fired"][key] = now
                        alerts_fired += 1

            # --- FSM ロジック（auto_trade 有効時のみ） ---
            auto_trade = config.get("auto_trade", {})
            if auto_trade.get("enabled", False):
                level_key = f"{ticker}_{level['price']}_{level['direction']}"

                # FSM インスタンス取得 or 作成
                if level_key not in fsm_states:
                    fsm = LevelFSM(ticker, level)
                    fsm_states[level_key] = fsm
                else:
                    # 既存状態から復元
                    fsm_dict = fsm_states[level_key]
                    if isinstance(fsm_dict, dict):
                        fsm = LevelFSM(ticker, level, fsm_dict)
                    else:
                        fsm = fsm_dict  # 既に LevelFSM インスタンス
                    fsm_states[level_key] = fsm

                # FSM 更新
                try:
                    transition = fsm.update(price, config, mt5_data, now, warmup=warmup)
                    if transition:
                        # 状態遷移があった → 通知
                        msg = transition["message"]
                        # スコア詳細があればアラートに付加
                        if fsm.last_score_detail:
                            msg += "\n" + format_score_detail(fsm.last_score_detail)
                        notify(msg, config, level.get("priority", "medium"))
                        alerts_fired += 1

                        if not quiet:
                            print(f"    [FSM] {transition['transition']}: {level['label']}")
                except Exception as e:
                    print(f"  [WARN] FSM更新失敗 ({level_key}): {e}", file=sys.stderr)

    # FSM 状態を辞書化して保存
    fsm_states_dict = {}
    for level_key, fsm in fsm_states.items():
        if isinstance(fsm, LevelFSM):
            fsm_states_dict[level_key] = fsm.to_dict()
        else:
            fsm_states_dict[level_key] = fsm

    state["fsm"] = fsm_states_dict
    state["prev_prices"] = prev_prices
    save_state(state)

    try:
        status_data = build_status_data(config, mt5_watchlist, analysis_cache, fsm_states)
        write_status_file(status_data)
    except Exception as e:
        print(f"  [WARN] Status file write failed: {e}", file=sys.stderr)

    return alerts_fired


def build_status_data(config, mt5_watchlist, analysis_cache, fsm_states=None):
    """全銘柄の状態を辞書にまとめて返す（JSON export 用、FSM 状態含む）"""
    mt5_data = read_mt5_positions()
    account = mt5_data.get("account", {}) if mt5_data else {}
    positions = mt5_data.get("positions", []) if mt5_data else []
    orders = mt5_data.get("orders", []) if mt5_data else []

    if fsm_states is None:
        fsm_states = {}

    assets = []
    for asset in config["alerts"]:
        ticker = asset["ticker"]
        name = asset["name"]
        data = fetch_price(ticker, mt5_watchlist)
        if not data:
            continue

        price = data["price"]
        source = data.get("source", "unknown")

        # テクニカル分析（キャッシュ再利用）
        if ticker not in analysis_cache:
            try:
                analysis_cache[ticker] = analyze_multi_timeframe(ticker)
            except Exception:
                analysis_cache[ticker] = None
        ta = analysis_cache[ticker]

        # levels の距離%を計算 + FSM 状態追加
        levels = []
        for level in asset["levels"]:
            level_price = level["price"]
            if not level_price or not isinstance(level_price, (int, float)):
                continue
            distance_pct = ((price - level_price) / level_price) * 100
            if not math.isfinite(distance_pct):
                distance_pct = 0.0
            status = check_level(price, level)

            # FSM 状態取得
            level_key = f"{ticker}_{level['price']}_{level['direction']}"
            fsm = fsm_states.get(level_key)
            fsm_state = None
            if fsm:
                if isinstance(fsm, LevelFSM):
                    fsm_state = fsm.state
                elif isinstance(fsm, dict):
                    fsm_state = fsm.get("state")

            level_data = {
                "price": level["price"],
                "direction": level["direction"],
                "label": level["label"],
                "action": level["action"],
                "priority": level.get("priority", "medium"),
                "distance_pct": round(distance_pct, 2),
                "status": status,
            }

            # FSM 状態があれば追加
            if fsm_state:
                level_data["fsm_state"] = fsm_state

            levels.append(level_data)

        assets.append({
            "ticker": ticker,
            "name": name,
            "price": price,
            "source": source,
            "ta": ta,
            "levels": levels,
        })

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checkIntervalSeconds": config.get("check_interval_seconds", 60),
        "account": account,
        "assets": assets,
        "positions": positions,
        "orders": orders,
    }


def write_status_file(status_data):
    """market-status.json をアトミックに書き出す"""
    tmp_path = MARKET_STATUS_PATH.with_suffix('.tmp')
    try:
        os.makedirs(MARKET_STATUS_PATH.parent, exist_ok=True)
        with open(tmp_path, "w") as f:
            json.dump(status_data, f, default=str, ensure_ascii=False, allow_nan=False)
        os.replace(tmp_path, MARKET_STATUS_PATH)
    except Exception as e:
        print(f"  [WARN] Status file write failed: {e}", file=sys.stderr)


def show_status(config):
    """現在の全銘柄ステータスを表示"""
    mt5_watchlist = get_mt5_watchlist()
    print("=" * 70)
    print(f"📈 Market Watch Status - {datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')}")
    if mt5_watchlist:
        print(f"   MT5 watchlist: {', '.join(mt5_watchlist.keys())}")
    print("=" * 70)

    for asset in config["alerts"]:
        ticker = asset["ticker"]
        name = asset["name"]
        data = fetch_price(ticker, mt5_watchlist)
        if not data:
            print(f"\n{name} ({ticker}): データ取得失敗")
            continue

        price = data["price"]
        src = data.get("source", "?")
        print(f"\n{name} ({ticker}): {price_fmt(price)}  [{src}]")

        # テクニカル概要（1h足のみ、軽量）
        try:
            ta_ticker = MT5_TA_PROXY.get(ticker, ticker)
            df_1h = fetch_ohlcv(ta_ticker, "1h", "30d")
            if df_1h is not None and len(df_1h) > 30:
                ta = analyze_timeframe(df_1h)
                if ta:
                    rsi_icon = "⚠️" if ta["rsi"] > 70 or ta["rsi"] < 30 else ""
                    macd_dir = "📈" if ta["macd_expanding"] else "📉"
                    trend = "📈" if ta["ema_trend"] == "up" else "📉"
                    print(f"  [TA] RSI:{ta['rsi']}{rsi_icon} MACD:{macd_dir} トレンド:{trend}(EMA20{'>'if ta['ema_trend']=='up' else '<'}50)")
        except Exception:
            pass

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

    # --status 実行時にも status file を更新
    try:
        analysis_cache = {}
        status_data = build_status_data(config, mt5_watchlist, analysis_cache, {})
        write_status_file(status_data)
    except Exception as e:
        print(f"  [WARN] Status file write failed: {e}", file=sys.stderr)


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

    if "--analyze" in args or "-a" in args:
        idx = args.index("--analyze") if "--analyze" in args else args.index("-a")
        ticker = args[idx + 1] if len(args) > idx + 1 else None
        if not ticker:
            # 全銘柄を分析
            tickers = [(a["ticker"], a["name"]) for a in config["alerts"]]
        else:
            name = next((a["name"] for a in config["alerts"] if a["ticker"] == ticker), ticker)
            tickers = [(ticker, name)]

        print("=" * 70)
        print(f"📊 テクニカル分析 - {datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')}")
        print("=" * 70)

        for tk, nm in tickers:
            print(f"\n{'─' * 60}")
            print(f"  {nm} ({tk})")
            print(f"{'─' * 60}")
            analysis = analyze_multi_timeframe(tk)
            for tf in ("1h", "4h", "1d"):
                ta = analysis.get(tf)
                if ta:
                    print(format_ta_summary(ta, tf))
                    print(f"       Close:{ta['close']} EMA20:{ta['ema20']} EMA50:{ta['ema50']} EMA200:{ta['ema200']}")
                    print(f"       BB:[{ta['bb_lower']} - {ta['bb_upper']}] MACD_H:{ta['macd_hist']}")
                else:
                    print(f"  [{tf}] データ不足")
            print()
            print(format_signal(analysis))

        print(f"\n{'=' * 70}")
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
    auto_trade = config.get("auto_trade", {})
    print(f"🐱 Market Watch 起動にゃ〜 (間隔: {interval}秒)")
    print(f"   ログ: {config['notification'].get('log_file', 'なし')}")
    print(f"   監視銘柄: {', '.join(a['ticker'] for a in config['alerts'])}")
    if auto_trade.get("enabled"):
        print(f"   🤖 自動売買: ON (セッション: {auto_trade.get('allowed_sessions', [])})")
    else:
        print(f"   🤖 自動売買: OFF")
    print(f"   Ctrl+C で停止\n")

    is_warmup = True  # 起動直後1サイクルはウォームアップ（価格記録のみ、FSM 発火なし）

    while True:
        try:
            now = datetime.now(JST)
            if is_market_hours(config):
                _ta_cache.clear()
                if is_warmup:
                    print(f"[{now.strftime('%H:%M JST')}] ウォームアップ中（価格記録のみ）...")
                else:
                    print(f"[{now.strftime('%H:%M JST')}] チェック中...")
                fired = run_check(config, state, warmup=is_warmup)
                is_warmup = False  # 2サイクル目以降は通常モード
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
