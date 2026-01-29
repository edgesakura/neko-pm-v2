#!/bin/bash
# neko-pm おやすみスクリプト（にゃ〜）

set -e

# 色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}🐱 neko-pm 終了中にゃ〜${NC}"

# セッション終了
sessions=("boss" "team" "worker")
killed=0

for session in "${sessions[@]}"; do
    if tmux has-session -t $session 2>/dev/null; then
        echo -e "  ${YELLOW}終了: ${session}${NC}"
        tmux kill-session -t $session
        ((killed++))
    fi
done

if [ $killed -eq 0 ]; then
    echo -e "${YELLOW}⚠️  終了するセッションがなかったにゃ${NC}"
else
    echo ""
    echo -e "${GREEN}✅ ${killed}個のセッションを終了したにゃ〜${NC}"
fi

# ランチャーのクリーンアップ（オプション）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER_DIR="${SCRIPT_DIR}/.launchers"

if [ -d "$LAUNCHER_DIR" ]; then
    rm -rf "$LAUNCHER_DIR"
    echo -e "  ${GREEN}ランチャーをクリーンアップしたにゃ${NC}"
fi

echo ""
echo "おやすみにゃ〜 🐱💤"
