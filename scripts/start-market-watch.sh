#!/bin/bash
# market-watch を tmux ペインまたはバックグラウンドで起動
# 使い方:
#   ./scripts/start-market-watch.sh          # フォアグラウンド
#   ./scripts/start-market-watch.sh --bg     # バックグラウンド (nohup)
#   ./scripts/start-market-watch.sh --tmux   # tmux chat Window に追加

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
WATCH_SCRIPT="$BASE_DIR/scripts/market-watch.py"
LOG_FILE="$BASE_DIR/output/market-watch.log"
PID_FILE="$BASE_DIR/output/.market-watch.pid"

case "${1:-}" in
  --bg)
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      echo "既に起動中 (PID: $(cat "$PID_FILE"))"
      exit 1
    fi
    nohup python3 "$WATCH_SCRIPT" >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "🐱 Market Watch 起動 (PID: $!, ログ: $LOG_FILE)"
    ;;
  --tmux)
    if tmux has-session -t neko-pm 2>/dev/null; then
      # chat Window (3) に水平分割で追加
      tmux split-window -t neko-pm:chat -v "python3 $WATCH_SCRIPT"
      echo "🐱 Market Watch を tmux neko-pm:chat に追加"
    else
      echo "tmux session 'neko-pm' が見つからない。--bg で起動してね"
      exit 1
    fi
    ;;
  --stop)
    if [ -f "$PID_FILE" ]; then
      PID=$(cat "$PID_FILE")
      if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "停止 (PID: $PID)"
      else
        echo "既に停止済み"
      fi
      rm -f "$PID_FILE"
    else
      echo "PIDファイルなし"
    fi
    ;;
  --status)
    python3 "$WATCH_SCRIPT" --status
    ;;
  *)
    python3 "$WATCH_SCRIPT"
    ;;
esac
