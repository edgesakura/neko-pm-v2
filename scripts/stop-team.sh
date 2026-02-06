#!/bin/bash
# neko-pm v3 - Agent Teams 停止スクリプト
#
# v3 では tmux セッション管理が不要。
# Memory MCP が状態を永続化するため、/exit するだけ。

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
HISTORY_DIR="${PROJECT_DIR}/history"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}🐱 neko-pm v3 終了処理にゃ〜${NC}"

# 履歴保存
mkdir -p "$HISTORY_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
SESSION_DIR="${HISTORY_DIR}/session_${TIMESTAMP}"
mkdir -p "$SESSION_DIR"

# メタデータ作成
cat > "${SESSION_DIR}/session_meta.yaml" << EOF
session_id: "session_${TIMESTAMP}"
ended_at: "$(date -Iseconds)"
version: "v3"
notes: |
  neko-pm v3 セッション。Agent Teams ベース。
  Memory MCP で記憶は永続化済み。
EOF

# latest リンク更新
rm -f "${HISTORY_DIR}/latest"
ln -s "session_${TIMESTAMP}" "${HISTORY_DIR}/latest"

echo -e "${GREEN}✅ セッション履歴を保存したにゃ${NC}"
echo -e "  保存先: ${CYAN}${SESSION_DIR}${NC}"
echo ""
echo "おやすみにゃ〜 🐱💤"
