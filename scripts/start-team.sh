#!/bin/bash
# neko-pm v3.5 - Agent Teams 起動スクリプト
#
# tmux セッション 'neko-pm' を作成し、4 Window 構成で起動:
#   Window 0 "lead"      : 🐱 ボスねこ（Claude Code Lead + Teammate 自動分割）
#   Window 1 "tanuki"    : 🦝 研究狸（Codex CLI 専用）
#   Window 2 "scouts"    : 🦊 賢者キツネ + 🦉 目利きフクロウ
#   Window 3 "chat"      : 💬 Chat App (Web UI)
#
# 使い方:
#   ./scripts/start-team.sh                # Split Panes（デフォルト）
#   ./scripts/start-team.sh --in-process   # In-Process（tmux なし）
#   ./scripts/start-team.sh --attach       # 既存セッションに接続
#   ./scripts/start-team.sh --help         # ヘルプ

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 色定義
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SESSION_NAME="neko-pm"
MODE="split-panes"

show_help() {
    cat << 'HELP'
🐱 neko-pm v3.5 - Agent Teams 起動スクリプト

使い方: start-team.sh [オプション]

オプション:
  --in-process    In-Process モード（tmux なし、Claude 直接起動）
  --attach        既存の neko-pm tmux セッションに接続
  -h, --help      ヘルプ表示

デフォルト（Split Panes）:
  tmux セッション 'neko-pm' を 4 Window 構成で起動:

  Window 0 "lead" ─ ボスねこ（+ Teammate 自動分割）
  ┌──────────────────────────────────┐
  │   🐱 Lead（ボスねこ）             │
  │   claude --teammate-mode tmux    │
  │   Teammate spawn で自動ペイン分割 │
  └──────────────────────────────────┘

  Window 1 "tanuki" ─ 研究狸
  ┌──────────────────────────────────┐
  │   🦝 研究狸（Codex CLI）          │
  └──────────────────────────────────┘

  Window 2 "scouts" ─ 偵察隊
  ┌───────────────┬──────────────────┐
  │ 🦊 賢者キツネ  │ 🦉 目利きフクロウ │
  │   (gemini)    │   (codex)       │
  └───────────────┴──────────────────┘

  Window 3 "chat" ─ Chat App (Web UI)
  ┌──────────────────────────────────┐
  │   💬 Chat App (port 3000)        │
  └──────────────────────────────────┘

操作:
  Ctrl+B → 0      : Lead（ボスねこ + Teammates）
  Ctrl+B → 1      : 研究狸
  Ctrl+B → 2      : 偵察隊（キツネ+フクロウ）
  Ctrl+B → 3      : Chat App (Web UI)
  Ctrl+B → 矢印   : ペイン間移動
  Ctrl+B → n/p    : Window 切替
HELP
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --in-process) MODE="in-process"; shift ;;
        --attach) MODE="attach"; shift ;;
        -h|--help) show_help; exit 0 ;;
        *) echo "不明なオプション: $1" >&2; show_help; exit 1 ;;
    esac
done

# --- 共通: 前提チェック ---

if ! command -v claude &> /dev/null; then
    echo -e "${RED}❌ claude CLI が見つからないにゃ！${NC}"
    echo -e "${YELLOW}   npm install -g @anthropic-ai/claude-code でインストールするにゃ${NC}"
    exit 1
fi

# --- Memory MCP セットアップ ---

setup_memory_mcp() {
    echo -e "${CYAN}🧠 Memory MCP 確認中にゃ...${NC}"
    local memory_file="${PROJECT_DIR}/memory/neko_memory.jsonl"
    mkdir -p "${PROJECT_DIR}/memory"

    if claude mcp list 2>/dev/null | grep -q "memory"; then
        echo -e "${GREEN}✅ Memory MCP は既に設定済みにゃ${NC}"
    else
        echo -e "${YELLOW}📝 Memory MCP を設定中にゃ...${NC}"
        claude mcp add memory \
            -e MEMORY_FILE_PATH="${memory_file}" \
            -- npx -y @modelcontextprotocol/server-memory 2>/dev/null \
            && echo -e "${GREEN}✅ Memory MCP 設定完了にゃ〜${NC}" \
            || echo -e "${YELLOW}⚠️  Memory MCP の自動設定に失敗したにゃ${NC}"
    fi
}

# --- グローバルコンテキスト作成 ---

setup_global_context() {
    if [ ! -f "${PROJECT_DIR}/memory/global_context.md" ]; then
        cat > "${PROJECT_DIR}/memory/global_context.md" << 'CONTEXT_EOF'
# 🐱 neko-pm グローバルコンテキスト

> 最終更新: (未設定)
> このファイルはシステム全体で共有する情報を記録するにゃ

## ご主人の好み

- (ここにご主人の好みを記録するにゃ)

## 重要な意思決定

| 日付 | 決定事項 | 理由 |
|------|----------|------|
| - | - | - |

## プロジェクト横断の知見

- (複数プロジェクトに役立つ知見をここに記録するにゃ)
CONTEXT_EOF
        echo -e "${GREEN}📝 global_context.md を作成したにゃ${NC}"
    fi
}

# --- モード別起動 ---

echo -e "${CYAN}🐱 neko-pm v3.5 起動中にゃ〜${NC}"
echo ""

setup_memory_mcp
setup_global_context

case "$MODE" in
    # --------------------------------------------------
    # Split Panes: tmux 4 Window 構成
    # --------------------------------------------------
    split-panes)
        if ! command -v tmux &> /dev/null; then
            echo -e "${RED}❌ tmux がインストールされていないにゃ！${NC}"
            echo -e "${YELLOW}   sudo apt install tmux でインストールするにゃ${NC}"
            echo -e "${YELLOW}   または --in-process で tmux なし起動できるにゃ${NC}"
            exit 1
        fi

        # 既存セッションの確認
        if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
            echo -e "${YELLOW}⚠️  既存セッション '${SESSION_NAME}' が見つかったにゃ${NC}"
            echo -e "  接続:     ${CYAN}./scripts/start-team.sh --attach${NC}"
            echo -e "  再作成:   ${CYAN}./scripts/stop-team.sh && ./scripts/start-team.sh${NC}"
            exit 1
        fi

        # 既に tmux 内にいる場合
        if [ -n "$TMUX" ]; then
            echo -e "${YELLOW}⚠️  既に tmux セッション内にゃ${NC}"
            echo -e "  このまま Claude を起動するにゃ..."
            echo ""
            cd "$PROJECT_DIR"
            exec claude --model opus --teammate-mode tmux
        fi

        echo -e "${GREEN}🖥️  tmux セッション '${SESSION_NAME}' を作成するにゃ${NC}"

        # =============================================
        # Window 0 "lead": 🐱 ボスねこ（Claude Code Lead）
        # =============================================
        tmux new-session -d -s "$SESSION_NAME" -n "lead" -c "$PROJECT_DIR"
        tmux send-keys -t "${SESSION_NAME}:lead" \
            "echo -e '${GREEN}🐱 neko-pm v3.5 - Lead（ボスねこ）${NC}' && echo '' && claude --model opus --teammate-mode tmux" Enter

        # =============================================
        # Window 1 "tanuki": 🦝 研究狸（Codex CLI 専用）
        # =============================================
        tmux new-window -t "${SESSION_NAME}" -n "tanuki" -c "$PROJECT_DIR"
        tmux send-keys -t "${SESSION_NAME}:tanuki" \
            "echo -e '${CYAN}🦝 研究狸（research-tanuki）- Codex CLI [full-auto]${NC}'; echo '─────────────────────────────────────────'; echo ''; codex --full-auto" Enter

        # =============================================
        # Window 2 "scouts": 🦊 賢者キツネ + 🦉 目利きフクロウ
        # =============================================
        tmux new-window -t "${SESSION_NAME}" -n "scouts" -c "$PROJECT_DIR"

        # ペイン 0: 🦊 賢者キツネ（左半分）
        if command -v gemini &> /dev/null; then
            tmux send-keys -t "${SESSION_NAME}:scouts" \
                "echo -e '${CYAN}🦊 賢者キツネ（sage-fox）- Gemini CLI [interactive]${NC}'; echo '─────────────────────────────────────'; echo '用途: リサーチ、トレンド調査、概要把握'; echo ''; gemini" Enter
        else
            tmux send-keys -t "${SESSION_NAME}:scouts" \
                "echo -e '${YELLOW}🦊 賢者キツネ - gemini CLI 未インストール${NC}'; echo '  npm install -g @anthropic-ai/gemini-cli'; exec bash" Enter
        fi

        # ペイン 1: 🦉 目利きフクロウ（右半分）
        tmux split-window -t "${SESSION_NAME}:scouts" -h -c "$PROJECT_DIR"
        if command -v codex &> /dev/null; then
            tmux send-keys -t "${SESSION_NAME}:scouts.1" \
                "echo -e '${CYAN}🦉 目利きフクロウ（owl-reviewer）- Codex CLI [read-only]${NC}'; echo '──────────────────────────────────────────────'; echo '用途: コードレビュー、OWASP Top 10 セキュリティ監査'; echo ''; codex --full-auto --sandbox read-only" Enter
        else
            tmux send-keys -t "${SESSION_NAME}:scouts.1" \
                "echo -e '${YELLOW}🦉 目利きフクロウ - codex CLI 未インストール${NC}'; echo '  npm install -g @openai/codex'; exec bash" Enter
        fi

        # =============================================
        # Window 3 "chat": 💬 Chat App (Web UI)
        # =============================================
        CHAT_APP_DIR="${PROJECT_DIR}/output/chat-app"
        tmux new-window -t "${SESSION_NAME}" -n "chat" -c "$CHAT_APP_DIR"
        tmux send-keys -t "${SESSION_NAME}:chat" \
            "echo -e '${CYAN}💬 Chat App (Web UI)${NC}'; echo '─────────────────────────────────────'; echo ''; BOSS_PANE=neko-pm:lead WORKERS_SESSION=neko-pm:lead PORT=3000 npm start" Enter

        # Window 0（lead）をアクティブに
        tmux select-window -t "${SESSION_NAME}:lead"

        echo ""
        echo -e "${GREEN}✅ neko-pm v3.5 準備完了にゃ〜${NC}"
        echo ""
        echo -e "${YELLOW}【tmux レイアウト】${NC}"
        echo -e "  Window 0 ${CYAN}\"lead\"${NC}      : 🐱 ボスねこ（+ Teammate 自動分割）"
        echo -e "  Window 1 ${CYAN}\"tanuki\"${NC}    : 🦝 研究狸（Codex CLI）"
        echo -e "  Window 2 ${CYAN}\"scouts\"${NC}    : 🦊 賢者キツネ + 🦉 目利きフクロウ"
        echo -e "  Window 3 ${CYAN}\"chat\"${NC}      : 💬 Chat App (http://0.0.0.0:3000)"
        echo ""
        echo -e "${YELLOW}【操作】${NC}"
        echo -e "  Ctrl+B → 0  : Lead（ボスねこ + Teammates）"
        echo -e "  Ctrl+B → 1  : 研究狸"
        echo -e "  Ctrl+B → 2  : 偵察隊（キツネ+フクロウ）"
        echo -e "  Ctrl+B → 3  : Chat App (Web UI)"
        echo -e "  Ctrl+B → 矢印 : ペイン間移動"
        echo ""

        # tmux セッションに接続
        exec tmux attach -t "$SESSION_NAME"
        ;;

    # --------------------------------------------------
    # Attach: 既存セッションに接続
    # --------------------------------------------------
    attach)
        if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
            echo -e "${RED}❌ セッション '${SESSION_NAME}' が見つからないにゃ${NC}"
            echo -e "  新規作成: ${CYAN}./scripts/start-team.sh${NC}"
            exit 1
        fi
        echo -e "${GREEN}🐱 セッション '${SESSION_NAME}' に接続するにゃ〜${NC}"
        exec tmux attach -t "$SESSION_NAME"
        ;;

    # --------------------------------------------------
    # In-Process: tmux なしで Claude を直接起動
    # --------------------------------------------------
    in-process)
        echo ""
        echo -e "${GREEN}✅ neko-pm v3.5 準備完了にゃ〜${NC}"
        echo ""
        echo -e "Teammate Mode: ${CYAN}In-Process${NC}"
        echo ""
        echo -e "${YELLOW}【v3.5 構成】${NC}"
        echo -e "  🐱 Lead（ボスねこ）: delegate mode でタスク指揮"
        echo -e "  🐱 Teammates（子猫）: In-Process（Shift+Up/Down で切替）"
        echo -e "  🦊 賢者キツネ: gemini CLI（Bash 経由・同一ターミナル）"
        echo -e "  🦝 研究狸: codex CLI（Bash 経由・同一ターミナル）"
        echo -e "  🦉 目利きフクロウ: codex CLI（Bash 経由・同一ターミナル）"
        echo ""

        cd "$PROJECT_DIR"
        exec claude --model opus --teammate-mode in-process
        ;;
esac
