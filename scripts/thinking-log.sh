#!/bin/bash

# thinking-log.sh - AIP 思考ログヘルパー
# Usage: ./thinking-log.sh <agent_name> <phase> <message>

set -euo pipefail

if [ $# -ne 3 ]; then
  echo "Usage: $0 <agent_name> <phase> <message>" >&2
  exit 1
fi

AGENT_NAME="$1"
PHASE="$2"
MESSAGE="$3"

LOG_DIR="/home/edgesakura/neko-pm/.claude/teams/neko-pm"
LOG_FILE="${LOG_DIR}/thinking.log"

# ディレクトリが無ければ作成
mkdir -p "${LOG_DIR}"

# タイムスタンプ付きログ出力
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "[${TIMESTAMP}] [${AGENT_NAME}] [${PHASE}] ${MESSAGE}" >> "${LOG_FILE}"
