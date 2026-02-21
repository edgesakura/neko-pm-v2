#!/home/edgesakura/venvs/webull/bin/python3
"""
webull-portfolio.py - Webull OpenAPI REST ポートフォリオ表示スクリプト

公式 SDK (webull-python-sdk) は grpcio ビルド不可のため、REST API を直接叩く。
認証: HMAC-SHA1 署名方式（SDK の default_signature_composer.py を忠実に再現）
ドキュメント: https://developer.webull.com/apis/docs/about

使い方:
  python3 scripts/webull-portfolio.py              # ポートフォリオ一覧
  python3 scripts/webull-portfolio.py --summary    # 損益サマリー（セクター別）
  python3 scripts/webull-portfolio.py --json       # JSON出力（他ツール連携用）
  python3 scripts/webull-portfolio.py --debug      # API疎通デバッグ

API エンドポイント (V1, US region):
  Host: api.webull.com
  サブスクリプション一覧: GET /app/subscriptions/list
  ポジション:            GET /account/positions?account_id=xxx&page_size=10
  残高:                  GET /account/balance?account_id=xxx
  プロフィール:          GET /account/profile?account_id=xxx
"""

import argparse
import hashlib
import hmac
import json
import os
import re
import socket
import subprocess
import sys
import uuid
from base64 import b64encode
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, quote

import requests

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
CACHE_PATH = OUTPUT_DIR / "webull-portfolio.json"

# Webull OpenAPI ベースURL（developer.webull.com に登録したアプリが使う）
WEBULL_API_HOST = "api.webull.com"
WEBULL_API_BASE = f"https://{WEBULL_API_HOST}"

JST = timezone(timedelta(hours=9))

# デバッグ用: 接続確認候補エンドポイント
_DEBUG_PATHS = [
    "/app/subscriptions/list",
    "/account/profile",
    "/account/positions",
    "/account/balance",
]
_DEBUG_HOSTS = [
    "api.webull.com",
]


# ---------------------------------------------------------------------------
# 環境変数取得（.bashrc から読み取り）
# ---------------------------------------------------------------------------
def get_env_from_bashrc(var_name: str) -> Optional[str]:
    """
    現在のプロセスに環境変数がない場合、~/.bashrc をファイルパースして取得する。

    取得優先順位:
      1. os.environ（現在のプロセス環境変数）
      2. ~/.bashrc をファイルとして直接パース
      3. subprocess 経由で bash -c 'source ~/.bashrc && printf $VAR'（フォールバック）
    """
    # 1. まず現在の環境に存在するか確認
    val = os.environ.get(var_name)
    if val:
        return val

    # 2. ~/.bashrc をファイルとして直接パース
    #    対応形式: export VAR="value" / export VAR='value' / export VAR=value
    bashrc = Path.home() / ".bashrc"
    if bashrc.exists():
        try:
            content = bashrc.read_text(encoding="utf-8")
            # export VAR_NAME="..." or 'value' or unquoted
            pattern = re.compile(
                r'^\s*export\s+' + re.escape(var_name) + r'\s*=\s*["\']?([^"\';\n\r]+)["\']?\s*$',
                re.MULTILINE,
            )
            m = pattern.search(content)
            if m:
                return m.group(1).strip().strip('"').strip("'")
        except OSError:
            pass

    # 3. subprocess フォールバック（bash -c source 方式）
    try:
        result = subprocess.run(
            "source ~/.bashrc 2>/dev/null && printf '%s' \"$" + var_name + "\"",
            shell=True,
            executable="/bin/bash",
            capture_output=True,
            text=True,
            timeout=5,
        )
        val = result.stdout.strip()
        if val:
            return val
    except (subprocess.TimeoutExpired, OSError):
        pass

    return None


def load_credentials() -> tuple[str, str]:
    """APP_KEY と APP_SECRET を取得する。失敗時は終了。"""
    app_key = get_env_from_bashrc("WEBULL_APP_KEY")
    app_secret = get_env_from_bashrc("WEBULL_APP_SECRET")

    if not app_key:
        print("ERROR: WEBULL_APP_KEY が取得できません。", file=sys.stderr)
        print("  ~/.bashrc に以下を設定してください:", file=sys.stderr)
        print("    export WEBULL_APP_KEY=\"your_app_key\"", file=sys.stderr)
        sys.exit(1)
    if not app_secret:
        print("ERROR: WEBULL_APP_SECRET が取得できません。", file=sys.stderr)
        print("  ~/.bashrc に以下を設定してください:", file=sys.stderr)
        print("    export WEBULL_APP_SECRET=\"your_app_secret\"", file=sys.stderr)
        sys.exit(1)

    return app_key, app_secret


# ---------------------------------------------------------------------------
# HMAC-SHA1 署名計算（SDK の default_signature_composer.py を忠実に再現）
# ---------------------------------------------------------------------------
def _get_nonce() -> str:
    """SDK 互換の nonce 生成（uuid5）。"""
    name = socket.gethostname() + str(uuid.uuid1())
    return str(uuid.uuid5(uuid.NAMESPACE_URL, name))


def _get_timestamp() -> str:
    """SDK 互換の ISO 8601 タイムスタンプ（ミリ秒なし）。"""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _md5_hex_upper(body_str: str) -> str:
    """ボディ文字列の MD5 ハッシュ（大文字 hex）。SDK の _get_body_string 互換。"""
    return hashlib.md5(body_str.encode("utf-8")).hexdigest().upper()


def _compact_json(obj: dict) -> str:
    """SDK 互換のコンパクト JSON シリアライズ。"""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def build_signature(
    *,
    host: str,
    uri: str,
    query_params: dict,
    body_params: Optional[dict],
    app_key: str,
    app_secret: str,
    timestamp: str,
    nonce: str,
) -> str:
    """
    Webull OpenAPI の HMAC-SHA1 署名を計算する。
    SDK の default_signature_composer.py:calc_signature() を忠実に再現。

    署名文字列の構成:
      1. URI を先頭に配置（パラメータではなく直接）
      2. 署名ヘッダー（小文字キー） + クエリパラメータをアルファベット順ソート
      3. ボディがある場合は MD5(大文字hex) を末尾に追加
      4. 全体を URL エンコード
      5. HMAC-SHA1(app_secret + "&", encoded_string) → Base64

    署名パラメータ:
      - host          : リクエストホスト（api.webull.com）
      - x-app-key
      - x-signature-algorithm
      - x-signature-nonce
      - x-signature-version
      - x-timestamp
      - (クエリパラメータ各キー)
    """
    # 署名ヘッダー（小文字キー）
    sign_params: dict[str, str] = {
        "host": host,
        "x-app-key": app_key,
        "x-signature-algorithm": "HMAC-SHA1",
        "x-signature-nonce": nonce,
        "x-signature-version": "1.0",
        "x-timestamp": timestamp,
    }

    # クエリパラメータを追加
    for k, v in query_params.items():
        existing = sign_params.get(str(k))
        if existing is not None:
            sign_params[str(k)] = str(existing) + "&" + str(v)
        else:
            sign_params[str(k)] = str(v)

    # ボディの MD5（大文字 hex）
    body_string: Optional[str] = None
    if body_params is not None:
        raw_str = _compact_json(body_params)
        body_string = _md5_hex_upper(raw_str)

    # 署名文字列を構築: URI&sorted_params&body_md5
    string_to_sign = uri
    sorted_items = sorted(sign_params.items(), key=lambda item: item[0])
    sorted_array = [f"{k}={v}" for k, v in sorted_items]
    if string_to_sign:
        string_to_sign = string_to_sign + "&" + "&".join(sorted_array)
    else:
        string_to_sign = "=".join(sorted_array)
    if body_string:
        string_to_sign = string_to_sign + "&" + body_string

    # URL エンコード（safe='' で / も含めて全てエンコード）
    encoded = quote(string_to_sign, safe="")

    if os.environ.get("WEBULL_DEBUG_SIGN"):
        print(f"  [SIGN] raw string_to_sign: {string_to_sign[:200]}", file=sys.stderr)
        print(f"  [SIGN] encoded: {encoded[:200]}", file=sys.stderr)

    # HMAC-SHA1: キーは app_secret + "&"
    key = (app_secret + "&").encode("utf-8")
    sig = hmac.new(key, encoded.encode("utf-8"), hashlib.sha1)
    return b64encode(sig.digest()).decode("utf-8").strip()


def build_headers(
    *,
    host: str,
    app_key: str,
    app_secret: str,
    method: str,
    path: str,
    query_params: dict,
    body_params: Optional[dict] = None,
) -> dict[str, str]:
    """署名付きリクエストヘッダーを生成する。"""
    timestamp = _get_timestamp()
    nonce = _get_nonce()

    signature = build_signature(
        host=host,
        uri=path,
        query_params=query_params,
        body_params=body_params,
        app_key=app_key,
        app_secret=app_secret,
        timestamp=timestamp,
        nonce=nonce,
    )

    headers = {
        "x-app-key": app_key,
        "x-timestamp": timestamp,
        "x-signature-nonce": nonce,
        "x-signature-algorithm": "HMAC-SHA1",
        "x-signature-version": "1.0",
        "x-signature": signature,
        "x-version": "v1",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    return headers


# ---------------------------------------------------------------------------
# API クライアント
# ---------------------------------------------------------------------------
class WebullClient:
    def __init__(self, app_key: str, app_secret: str, host: str = WEBULL_API_HOST):
        self._app_key = app_key
        self._app_secret = app_secret
        self._host = host
        self._base_url = f"https://{host}"
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "webull-portfolio-viewer/1.0"})

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        body_params: Optional[dict] = None,
        debug: bool = False,
    ) -> dict:
        """署名付きリクエストを送信し、レスポンスの JSON を返す。"""
        query_params = params or {}

        headers = build_headers(
            host=self._host,
            app_key=self._app_key,
            app_secret=self._app_secret,
            method=method.upper(),
            path=path,
            query_params=query_params,
            body_params=body_params,
        )

        # URL 構築: SDK 互換（クエリパラメータは URL に付与）
        url = self._base_url + path

        # ボディ（POST 用）
        body_str = _compact_json(body_params) if body_params else None

        if debug:
            print(f"  [DEBUG] {method} {url}", file=sys.stderr)
            if query_params:
                print(f"  [DEBUG] query_params: {query_params}", file=sys.stderr)
            print(f"  [DEBUG] headers: x-app-key={self._app_key[:8]}..., x-timestamp={headers['x-timestamp']}", file=sys.stderr)

        try:
            resp = self._session.request(
                method=method,
                url=url,
                params=query_params if query_params else None,
                data=body_str,
                headers=headers,
                timeout=15,
            )
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(
                f"Webull API に接続できません ({url})。\n"
                f"  ネットワーク接続またはホスト名を確認してください。\n"
                f"  詳細: {e}"
            )
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Webull API がタイムアウトしました ({url})。")

        if debug:
            print(f"  [DEBUG] status={resp.status_code}, body={resp.text[:300]}", file=sys.stderr)

        if resp.status_code == 401:
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            raise RuntimeError(
                f"認証エラー (401)。APP_KEY / APP_SECRET を確認してください。\n"
                f"  詳細: {err}"
            )
        if resp.status_code == 403:
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            raise RuntimeError(
                f"アクセス拒否 (403)。API の利用権限を確認してください。\n"
                f"  developer.webull.com でアプリ審査が完了しているか確認してください。\n"
                f"  詳細: {err}"
            )
        if resp.status_code == 404:
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            raise RuntimeError(
                f"エンドポイントが見つかりません (404): {url}\n"
                f"  アプリが Sandbox / Production のどちらの環境か確認してください。\n"
                f"  詳細: {err}"
            )
        if resp.status_code >= 400:
            try:
                err_body = resp.json()
            except Exception:
                err_body = resp.text
            raise RuntimeError(
                f"API エラー (HTTP {resp.status_code}): {err_body}"
            )

        try:
            return resp.json()
        except Exception:
            raise RuntimeError(
                f"API レスポンスのパースに失敗しました: {resp.text[:200]}"
            )

    def get_app_subscriptions(self, debug: bool = False) -> list[dict]:
        """アプリサブスクリプション（アカウント）一覧を取得する（V1）。"""
        data = self._request("GET", "/app/subscriptions/list", debug=debug)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data", data.get("list", [data]))
        return []

    def get_account_profile(self, account_id: str, debug: bool = False) -> dict:
        """アカウントプロフィールを取得する。"""
        return self._request(
            "GET", "/account/profile",
            params={"account_id": account_id},
            debug=debug,
        )

    def get_positions(self, account_id: str, page_size: int = 100, debug: bool = False) -> list[dict]:
        """指定アカウントのポジション一覧を取得する。"""
        data = self._request(
            "GET", "/account/positions",
            params={"account_id": account_id, "page_size": str(page_size)},
            debug=debug,
        )
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data", data.get("list", data.get("positions", [])))
        return []

    def get_balance(self, account_id: str, currency: str = "USD", debug: bool = False) -> dict:
        """アカウント残高を取得する。"""
        return self._request(
            "GET", "/account/balance",
            params={"account_id": account_id, "total_asset_currency": currency},
            debug=debug,
        )


# ---------------------------------------------------------------------------
# データ整形ヘルパー
# ---------------------------------------------------------------------------
def _safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def parse_position(pos: dict) -> dict:
    """
    API レスポンスのポジション dict を正規化する。
    複数のキー名パターンに対応（Webull OpenAPI のバージョン差異を吸収）。
    """
    ticker = (
        pos.get("symbol")
        or pos.get("ticker", {}).get("symbol")
        or pos.get("instrumentId", "N/A")
    )
    quantity = _safe_float(
        pos.get("position") or pos.get("quantity") or pos.get("qty")
    )
    avg_cost = _safe_float(
        pos.get("costPrice") or pos.get("avgCost") or pos.get("cost")
    )
    last_price = _safe_float(
        pos.get("lastPrice") or pos.get("price") or pos.get("last")
    )
    market_value = _safe_float(
        pos.get("marketValue") or pos.get("mktValue")
    )
    unrealized_pnl = _safe_float(
        pos.get("unrealizedProfitLoss")
        or pos.get("unrealizedPL")
        or pos.get("pnl")
    )

    # market_value が 0 なら quantity * last_price で計算
    if market_value == 0.0 and quantity and last_price:
        market_value = quantity * last_price

    # unrealized_pnl が 0 なら (last - avg) * qty で計算
    if unrealized_pnl == 0.0 and quantity and avg_cost and last_price:
        unrealized_pnl = (last_price - avg_cost) * quantity

    pnl_pct = (unrealized_pnl / (avg_cost * quantity) * 100) if avg_cost and quantity else 0.0

    # セクター情報（存在すれば）
    sector = (
        pos.get("sector")
        or pos.get("ticker", {}).get("industryCategoryId")
        or "N/A"
    )

    return {
        "symbol": str(ticker),
        "quantity": quantity,
        "avg_cost": avg_cost,
        "last_price": last_price,
        "market_value": market_value,
        "unrealized_pnl": unrealized_pnl,
        "pnl_pct": pnl_pct,
        "sector": str(sector),
    }


# ---------------------------------------------------------------------------
# 表示
# ---------------------------------------------------------------------------
def fmt_usd(val: float, sign: bool = False) -> str:
    """USD 金額を整形する。負数は '-$58.10' 形式（'$-58.10' ではない）。"""
    if val < 0:
        return f"-${abs(val):,.2f}"
    prefix = "+" if (sign and val > 0) else ""
    return f"{prefix}${val:,.2f}"


def fmt_pct(val: float) -> str:
    """パーセント値を整形する。"""
    prefix = "+" if val > 0 else ""
    return f"{prefix}{val:.1f}%"


def print_portfolio(positions: list[dict], account_name: str = "US Stock Account") -> None:
    """ポートフォリオをテーブル形式で表示する。"""
    now_jst = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    sep = "=" * 70

    print(sep)
    print(f"  Webull Portfolio - {now_jst}")
    print(sep)
    print(f"  口座: {account_name}")
    print()

    if not positions:
        print("  ポジションがありません。")
    else:
        header = f"  {'銘柄':<10} {'数量':>6}  {'平均取得':>10}  {'現在値':>10}  {'損益':>12}  {'損益率':>8}"
        print(header)
        print("  " + "-" * 66)

        for p in positions:
            sym = p["symbol"]
            qty_val = p["quantity"]
            qty = f"{qty_val:.0f}" if qty_val == int(qty_val) else f"{qty_val:.4f}"
            avg = f"${p['avg_cost']:.2f}"
            last = f"${p['last_price']:.2f}"
            pnl = fmt_usd(p["unrealized_pnl"], sign=True)
            pct = fmt_pct(p["pnl_pct"])
            print(f"  {sym:<10} {qty:>6}  {avg:>10}  {last:>10}  {pnl:>12}  {pct:>8}")

    print()
    print("  " + "-" * 66)

    total_value = sum(p["market_value"] for p in positions)
    total_pnl = sum(p["unrealized_pnl"] for p in positions)
    total_cost = sum(p["avg_cost"] * p["quantity"] for p in positions)
    total_pct = (total_pnl / total_cost * 100) if total_cost else 0.0

    print(f"  合計評価額: {fmt_usd(total_value)}")
    print(f"  合計損益:   {fmt_usd(total_pnl, sign=True)} ({fmt_pct(total_pct)})")
    print(sep)


def print_summary(positions: list[dict]) -> None:
    """セクター別損益サマリーを表示する。"""
    now_jst = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    sep = "=" * 70

    print(sep)
    print(f"  Webull Portfolio Summary - {now_jst}")
    print(sep)

    # セクター別集計
    sectors: dict[str, dict] = {}
    for p in positions:
        s = str(p.get("sector", "N/A"))
        if s not in sectors:
            sectors[s] = {"market_value": 0.0, "unrealized_pnl": 0.0, "cost": 0.0, "count": 0}
        sectors[s]["market_value"] += p["market_value"]
        sectors[s]["unrealized_pnl"] += p["unrealized_pnl"]
        sectors[s]["cost"] += p["avg_cost"] * p["quantity"]
        sectors[s]["count"] += 1

    total_value = sum(p["market_value"] for p in positions)
    total_pnl = sum(p["unrealized_pnl"] for p in positions)

    print()
    print(f"  {'セクター':<20} {'銘柄数':>6}  {'評価額':>12}  {'損益':>12}  {'比率':>7}")
    print("  " + "-" * 62)

    for sector, data in sorted(sectors.items(), key=lambda x: -x[1]["market_value"]):
        alloc = (data["market_value"] / total_value * 100) if total_value else 0
        pnl_str = fmt_usd(data["unrealized_pnl"], sign=True)
        val_str = fmt_usd(data["market_value"])
        print(
            f"  {sector:<20} {data['count']:>6}  {val_str:>12}  {pnl_str:>12}  {alloc:>6.1f}%"
        )

    print()
    print("  " + "-" * 62)
    print(f"  合計評価額:  {fmt_usd(total_value)}")
    total_cost = sum(p["avg_cost"] * p["quantity"] for p in positions)
    total_pct = (total_pnl / total_cost * 100) if total_cost else 0.0
    print(f"  合計損益:    {fmt_usd(total_pnl, sign=True)} ({fmt_pct(total_pct)})")
    print(sep)

    # 上位/下位 5 銘柄
    if positions:
        print()
        print("  ---- 含み益 TOP 5 ----")
        top5 = sorted(positions, key=lambda x: -x["unrealized_pnl"])[:5]
        for p in top5:
            print(f"  {p['symbol']:<8}  {fmt_usd(p['unrealized_pnl'], sign=True):>12}  ({fmt_pct(p['pnl_pct'])})")

        print()
        print("  ---- 含み損 TOP 5 ----")
        bot5 = sorted(positions, key=lambda x: x["unrealized_pnl"])[:5]
        for p in bot5:
            print(f"  {p['symbol']:<8}  {fmt_usd(p['unrealized_pnl'], sign=True):>12}  ({fmt_pct(p['pnl_pct'])})")
        print()


# ---------------------------------------------------------------------------
# デバッグモード（API 疎通確認）
# ---------------------------------------------------------------------------
def run_debug(app_key: str, app_secret: str) -> None:
    """API エンドポイントの疎通確認を行う。"""
    sep = "=" * 70
    print(sep)
    print("  Webull API デバッグモード")
    print(sep)
    print(f"  App Key: {app_key[:8]}...{app_key[-4:]} (長さ={len(app_key)})")
    print(f"  App Secret: ***...*** (長さ={len(app_secret)})")
    print()

    for host in _DEBUG_HOSTS:
        print(f"  ホスト: {host}")
        for path in _DEBUG_PATHS:
            headers = build_headers(
                host=host,
                app_key=app_key,
                app_secret=app_secret,
                method="GET",
                path=path,
                query_params={},
            )
            try:
                url = f"https://{host}{path}"
                resp = requests.get(url, headers=headers, timeout=10)
                status = resp.status_code
                body_preview = resp.text[:150].replace("\n", " ")
                status_str = {
                    200: "OK (200) - 接続成功",
                    401: "UNAUTHORIZED (401) - 認証エラー（エンドポイントは存在する）",
                    403: "FORBIDDEN (403) - 権限なし（エンドポイントは存在する）",
                    404: "NOT FOUND (404) - エンドポイントが存在しない",
                }.get(status, f"HTTP {status}")
                print(f"    {path}: {status_str}")
                if status not in (404,):
                    print(f"      レスポンス: {body_preview}")
            except requests.exceptions.ConnectionError:
                print(f"    {path}: 接続エラー（ホストに到達できません）")
            except requests.exceptions.Timeout:
                print(f"    {path}: タイムアウト")
        print()

    print("  ---- トラブルシューティングのヒント ----")
    print("  404 が続く場合:")
    print("    1. developer.webull.com でアプリのステータスを確認してください。")
    print("       (Sandbox / Production の違い)")
    print("    2. アプリに Trade API の権限が付与されているか確認してください。")
    print("    3. 本番環境への昇格申請が必要な場合があります。")
    print()
    print("  401 の場合:")
    print("    1. APP_KEY と APP_SECRET が正しいか確認してください。")
    print("    2. 署名アルゴリズムに問題がある可能性があります。")
    print()
    print("  200 の場合:")
    print("    1. API 接続成功。--verbose で詳細確認できます。")
    print(sep)


# ---------------------------------------------------------------------------
# JSON キャッシュ書き出し
# ---------------------------------------------------------------------------
def save_cache(data: dict) -> None:
    """output/webull-portfolio.json にキャッシュを書き出す。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"WARNING: キャッシュ書き出し失敗: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Webull ポートフォリオ表示スクリプト",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使い方の例:
  %(prog)s                # ポートフォリオ一覧（デフォルト）
  %(prog)s --summary      # セクター別損益サマリー
  %(prog)s --json         # JSON 出力（他ツール連携用）
  %(prog)s --debug        # API 疎通デバッグ（接続問題の診断）
        """,
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="損益サマリー（セクター別）を表示",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="JSON 形式で出力（他ツール連携用）",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="API 疎通デバッグ（接続確認・エラー診断）",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="詳細ログを表示（リクエスト/レスポンスの内容）",
    )
    args = parser.parse_args()

    # 認証情報取得
    app_key, app_secret = load_credentials()

    # デバッグモード
    if args.debug:
        run_debug(app_key, app_secret)
        return

    client = WebullClient(app_key, app_secret)

    # サブスクリプション（アカウント）一覧取得
    try:
        subscriptions = client.get_app_subscriptions(debug=args.verbose)
    except RuntimeError as e:
        print(f"ERROR: サブスクリプション一覧の取得に失敗しました。", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        print(f"\n  ヒント: python3 {Path(__file__).name} --debug で疎通確認できます。", file=sys.stderr)
        sys.exit(1)

    if not subscriptions:
        print("ERROR: アカウントが見つかりません。", file=sys.stderr)
        print("  アプリに Trade API の権限があるか確認してください。", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"  [DEBUG] subscriptions response: {json.dumps(subscriptions, indent=2)[:500]}", file=sys.stderr)

    # 最初のアカウントを使用（レスポンス構造に応じて account_id を探す）
    account = subscriptions[0] if isinstance(subscriptions, list) else subscriptions
    account_id = (
        account.get("account_id")
        or account.get("accountId")
        or account.get("id")
        or str(account)
    )
    account_name = (
        account.get("account_type")
        or account.get("accountType")
        or account.get("name")
        or "US Stock Account"
    )

    # ポジション取得
    try:
        raw_positions = client.get_positions(account_id, debug=args.verbose)
    except RuntimeError as e:
        print(f"ERROR: ポジションの取得に失敗しました。", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    positions = [parse_position(p) for p in raw_positions]

    # キャッシュ書き出し（market-watch.py 参照用）
    cache_data = {
        "fetched_at": datetime.now(JST).isoformat(),
        "account_id": account_id,
        "account_name": account_name,
        "positions": positions,
        "total_market_value": sum(p["market_value"] for p in positions),
        "total_unrealized_pnl": sum(p["unrealized_pnl"] for p in positions),
    }
    save_cache(cache_data)

    # 出力
    if args.output_json:
        print(json.dumps(cache_data, ensure_ascii=False, indent=2))
    elif args.summary:
        print_summary(positions)
    else:
        print_portfolio(positions, account_name=account_name)


if __name__ == "__main__":
    main()
