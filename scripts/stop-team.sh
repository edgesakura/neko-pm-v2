#!/bin/bash
# neko-pm v4 - Agent Teams 停止スクリプト
#
# tmux セッション 'neko-pm' を終了し、セッション履歴を保存する。
# Memory MCP が状態を永続化するため、コンテキストは次回引き継がれる。

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
HISTORY_DIR="${PROJECT_DIR}/history"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SESSION_NAME="neko-pm"

echo -e "${CYAN}🐱 neko-pm v4 終了処理にゃ〜${NC}"

# 履歴保存
mkdir -p "$HISTORY_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
SESSION_DIR="${HISTORY_DIR}/session_${TIMESTAMP}"
mkdir -p "$SESSION_DIR"

# メタデータ作成
cat > "${SESSION_DIR}/session_meta.yaml" << EOF
session_id: "session_${TIMESTAMP}"
ended_at: "$(date -Iseconds)"
version: "v4"
notes: |
  neko-pm v4 セッション。Agent Teams ベース。
  Memory MCP で記憶は永続化済み。
EOF

# latest リンク更新
rm -f "${HISTORY_DIR}/latest"
ln -s "session_${TIMESTAMP}" "${HISTORY_DIR}/latest"

echo -e "${GREEN}✅ セッション履歴を保存したにゃ${NC}"
echo -e "  保存先: ${CYAN}${SESSION_DIR}${NC}"

# chat-app バックグラウンドプロセス停止
CHAT_PID_FILE="${PROJECT_DIR}/.chat-app.pid"
if [ -f "$CHAT_PID_FILE" ]; then
    CHAT_PID=$(cat "$CHAT_PID_FILE")
    if kill -0 "$CHAT_PID" 2>/dev/null; then
        echo -e "${YELLOW}💬 Chat App (PID: ${CHAT_PID}) を停止中にゃ...${NC}"
        kill "$CHAT_PID" 2>/dev/null
        sleep 1
        # まだ生きてたら強制終了
        if kill -0 "$CHAT_PID" 2>/dev/null; then
            kill -9 "$CHAT_PID" 2>/dev/null
        fi
        echo -e "${GREEN}✅ Chat App を停止したにゃ${NC}"
    fi
    rm -f "$CHAT_PID_FILE"
else
    # PID ファイルがない場合、ポートで探して停止
    CHAT_PID=$(lsof -ti:3000 2>/dev/null || true)
    if [ -n "$CHAT_PID" ]; then
        echo -e "${YELLOW}💬 Chat App (PID: ${CHAT_PID}) を停止中にゃ...${NC}"
        kill "$CHAT_PID" 2>/dev/null || true
        echo -e "${GREEN}✅ Chat App を停止したにゃ${NC}"
    fi
fi

# Discord Bot バックグラウンドプロセス停止
DISCORD_PID_FILE="${PROJECT_DIR}/.discord-bot.pid"
if [ -f "$DISCORD_PID_FILE" ]; then
    DISCORD_PID=$(cat "$DISCORD_PID_FILE")
    if kill -0 "$DISCORD_PID" 2>/dev/null; then
        echo -e "${YELLOW}🤖 Discord Bot (PID: ${DISCORD_PID}) を停止中にゃ...${NC}"
        kill "$DISCORD_PID" 2>/dev/null
        sleep 1
        if kill -0 "$DISCORD_PID" 2>/dev/null; then
            kill -9 "$DISCORD_PID" 2>/dev/null
        fi
        echo -e "${GREEN}✅ Discord Bot を停止したにゃ${NC}"
    fi
    rm -f "$DISCORD_PID_FILE"
fi

# tmux セッション終了
if command -v tmux &> /dev/null && tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo -e "${YELLOW}🖥️  tmux セッション '${SESSION_NAME}' を終了するにゃ...${NC}"
    tmux kill-session -t "$SESSION_NAME"
    echo -e "${GREEN}✅ tmux セッションを終了したにゃ${NC}"
else
    echo -e "${YELLOW}ℹ️  tmux セッション '${SESSION_NAME}' は見つからなかったにゃ${NC}"
fi

echo ""
echo "おやすみにゃ〜 🐱💤"
