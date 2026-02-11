#!/bin/bash

# thinking-log.sh - AIP 思考ログヘルパー
# Usage: ./thinking-log.sh <agent_name> <phase> <message> [level]

set -euo pipefail

if [ $# -lt 3 ] || [ $# -gt 4 ]; then
  echo "Usage: $0 <agent_name> <phase> <message> [level]" >&2
  exit 1
fi

AGENT_NAME="$1"
PHASE="$2"
MESSAGE="$3"
LEVEL="${4:-info}"

LOG_DIR="/home/edgesakura/neko-pm/.claude/teams/neko-pm"
LOG_FILE="${LOG_DIR}/thinking.log"
MAX_LINES=200

# ディレクトリが無ければ作成
mkdir -p "${LOG_DIR}"

# ログローテーション（200行を超えたら）
if [ -f "${LOG_FILE}" ]; then
  LINE_COUNT=$(wc -l < "${LOG_FILE}" 2>/dev/null || echo 0)
  if [ "${LINE_COUNT}" -ge "${MAX_LINES}" ]; then
    # .old に現在のログを保存（上書き）
    cp "${LOG_FILE}" "${LOG_FILE}.old"
    # 最新50行だけ残す
    tail -n 50 "${LOG_FILE}" > "${LOG_FILE}.tmp"
    mv "${LOG_FILE}.tmp" "${LOG_FILE}"
  fi
fi

# タイムスタンプ付きログ出力
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "[${TIMESTAMP}] [${AGENT_NAME}] [${PHASE}] [${LEVEL}] ${MESSAGE}" >> "${LOG_FILE}"
