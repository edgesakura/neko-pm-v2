#!/bin/bash
# neko-pm - Agent Teams 起動スクリプト
#
# tmux セッション 'neko-pm' を作成し、4 Window 構成で起動:
#   Window 0 "lead"      : ボスねこ（Claude Code Lead + Teammate 自動分割）
#   Window 1 "tanuki"    : 研究狸（Codex CLI 専用）
#   Window 2 "kitsune"   : 賢者キツネ（Gemini CLI）
#   Window 3 "market"    : Market Watch（テクニカル分析付き銘柄監視）
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
neko-pm - Agent Teams 起動スクリプト

使い方: start-team.sh [オプション]

オプション:
  --in-process    In-Process モード（tmux なし、Claude 直接起動）
  --attach        既存の neko-pm tmux セッションに接続
  -h, --help      ヘルプ表示

デフォルト（Split Panes）:
  tmux セッション 'neko-pm' を 4 Window 構成で起動:

  Window 0 "lead"    - ボスねこ（+ Teammate 自動分割）
  Window 1 "tanuki"  - 研究狸（Codex CLI）
  Window 2 "kitsune" - 賢者キツネ（Gemini CLI）
  Window 3 "market"  - Market Watch

操作:
  Ctrl+B → 0      : Lead（ボスねこ + Teammates）
  Ctrl+B → 1      : 研究狸
  Ctrl+B → 2      : 賢者キツネ
  Ctrl+B → 3      : Market Watch
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

# --- nawabari アーカイブ + 新規作成 ---

archive_nawabari() {
    local nawabari="${PROJECT_DIR}/nawabari.md"
    local history_dir="${PROJECT_DIR}/history"
    mkdir -p "$history_dir"

    if [ -f "$nawabari" ]; then
        cp "$nawabari" "${history_dir}/nawabari-$(date +%Y%m%d-%H%M%S).md"
        echo -e "${CYAN}📋 前回の nawabari を history/ にアーカイブしたにゃ${NC}"
    fi

    cat > "$nawabari" << 'NAWABARI_EOF'
# nawabari

最終更新: (セッション開始)

## 要対応
（ご主人の判断が必要なこと）

## 進行中
| 担当 | タスク | 状態 |
|------|--------|------|

## 完了（最新5件）
（リンクのみ: → output/logs/xxx.md）

## メモ
（チーム共有の気づき・発見）
NAWABARI_EOF
    echo -e "${GREEN}📝 nawabari.md を新規作成したにゃ${NC}"
}

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
# neko-pm グローバルコンテキスト

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

echo -e "${CYAN}🐱 neko-pm 起動中にゃ〜${NC}"
echo ""

archive_nawabari
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
        # Window 0 "lead": ボスねこ（Claude Code Lead）
        # =============================================
        tmux new-session -d -s "$SESSION_NAME" -n "lead" -c "$PROJECT_DIR"
        tmux send-keys -t "${SESSION_NAME}:lead" \
            "echo -e '${GREEN}🐱 neko-pm - Lead（ボスねこ）${NC}' && echo '' && claude --model opus --teammate-mode tmux" Enter

        # =============================================
        # Window 1 "tanuki": 研究狸（Codex CLI 専用）
        # =============================================
        tmux new-window -t "${SESSION_NAME}" -n "tanuki" -c "$PROJECT_DIR"
        tmux send-keys -t "${SESSION_NAME}:tanuki" \
            "echo -e '${CYAN}🦝 研究狸（research-tanuki）- Codex CLI [full-auto]${NC}'; echo '─────────────────────────────────────────'; echo ''; codex --full-auto" Enter

        # =============================================
        # Window 2 "kitsune": 賢者キツネ（Gemini CLI）
        # =============================================
        tmux new-window -t "${SESSION_NAME}" -n "kitsune" -c "$PROJECT_DIR"
        if command -v gemini &> /dev/null; then
            tmux send-keys -t "${SESSION_NAME}:kitsune" \
                "echo -e '${CYAN}🦊 賢者キツネ（sage-fox）- Gemini CLI [interactive]${NC}'; echo '─────────────────────────────────────'; echo ''; gemini" Enter
        else
            tmux send-keys -t "${SESSION_NAME}:kitsune" \
                "echo -e '${YELLOW}🦊 賢者キツネ - gemini CLI 未インストール${NC}'; echo '  npm install -g @anthropic-ai/gemini-cli'; exec bash" Enter
        fi

        # =============================================
        # chat-app: バックグラウンド起動（port 3000）
        # =============================================
        CHAT_APP_DIR="${PROJECT_DIR}/output/chat-app"
        if [ -d "$CHAT_APP_DIR" ] && [ -f "${CHAT_APP_DIR}/package.json" ]; then
            echo -e "${CYAN}💬 Chat App をバックグラウンド起動中にゃ...${NC}"
            cd "$CHAT_APP_DIR"
            BOSS_PANE=neko-pm:lead WORKERS_SESSION=neko-pm:lead PORT=3000 \
                nohup npm start > "${PROJECT_DIR}/output/logs/chat-app.log" 2>&1 &
            echo $! > "${PROJECT_DIR}/.chat-app.pid"
            cd "$PROJECT_DIR"
            echo -e "${GREEN}✅ Chat App 起動完了（http://0.0.0.0:3000）${NC}"
        fi

        # =============================================
        # Discord Bot: バックグラウンド起動
        # =============================================
        DISCORD_BOT_DIR="${PROJECT_DIR}/output/discord-bot"
        if [ -d "$DISCORD_BOT_DIR" ] && [ -f "${DISCORD_BOT_DIR}/.env" ]; then
            echo -e "${CYAN}🤖 Discord Bot をバックグラウンド起動中にゃ...${NC}"
            cd "$DISCORD_BOT_DIR"
            nohup node bot.js > "${PROJECT_DIR}/output/logs/discord-bot.log" 2>&1 &
            echo $! > "${PROJECT_DIR}/.discord-bot.pid"
            cd "$PROJECT_DIR"
            echo -e "${GREEN}✅ Discord Bot 起動完了${NC}"
        fi

        # =============================================
        # Window 3 "market": Market Watch
        # =============================================
        tmux new-window -t "${SESSION_NAME}" -n "market" -c "$PROJECT_DIR"
        tmux send-keys -t "${SESSION_NAME}:market" \
            "echo -e '${CYAN}📈 Market Watch（テクニカル分析付き銘柄監視）${NC}'; echo '─────────────────────────────────────'; echo ''; python3 ${PROJECT_DIR}/scripts/market-watch.py" Enter

        # Window 0（lead）をアクティブに
        tmux select-window -t "${SESSION_NAME}:lead"

        echo ""
        echo -e "${GREEN}✅ neko-pm 準備完了にゃ〜${NC}"
        echo ""
        echo -e "${YELLOW}【tmux レイアウト】${NC}"
        echo -e "  Window 0 ${CYAN}\"lead\"${NC}      : 🐱 ボスねこ（+ Teammate 自動分割）"
        echo -e "  Window 1 ${CYAN}\"tanuki\"${NC}    : 🦝 研究狸（Codex CLI）"
        echo -e "  Window 2 ${CYAN}\"kitsune\"${NC}   : 🦊 賢者キツネ（Gemini CLI）"
        echo -e "  💬 Chat App: http://0.0.0.0:3000（バックグラウンド）"
        echo -e "  🤖 Discord Bot: バックグラウンド（output/discord-bot/.env が必要）"
        echo -e "  Window 3 ${CYAN}\"market\"${NC}    : 📈 Market Watch"
        echo ""
        echo -e "${YELLOW}【操作】${NC}"
        echo -e "  Ctrl+B → 0  : Lead（ボスねこ + Teammates）"
        echo -e "  Ctrl+B → 1  : 研究狸"
        echo -e "  Ctrl+B → 2  : 賢者キツネ"
        echo -e "  Ctrl+B → 3  : Market Watch"
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
        echo -e "${GREEN}✅ neko-pm 準備完了にゃ〜${NC}"
        echo ""
        echo -e "Teammate Mode: ${CYAN}In-Process${NC}"
        echo ""
        echo -e "${YELLOW}【構成】${NC}"
        echo -e "  🐱 Lead（ボスねこ）: delegate mode でタスク指揮"
        echo -e "  🐱 Teammates（子猫）: In-Process（Shift+Up/Down で切替）"
        echo -e "  🦊 賢者キツネ: gemini CLI（Bash 経由・同一ターミナル）"
        echo -e "  🦝 研究狸: codex CLI（Bash 経由・同一ターミナル）"
        echo ""

        cd "$PROJECT_DIR"
        exec claude --model opus --teammate-mode in-process
        ;;
esac
