#!/bin/bash
# neko-pm 再開スクリプト（にゃ〜）
#
# 使い方:
#   ./resume.sh              # 最新セッションから再開
#   ./resume.sh -l           # 過去のセッション一覧表示
#   ./resume.sh -s SESSION   # 特定のセッションから再開
#   ./resume.sh -w N         # 子猫の数を指定して再開
#
# 動作:
#   1. 前回のnawabari.mdとqueueを復元
#   2. 猫たちに「前回の続きから」というコンテキストを渡して起動

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HISTORY_DIR="${SCRIPT_DIR}/history"
SESSION_NAME="neko"

# デフォルト設定
WORKERS=2
TARGET_SESSION="latest"
LIST_MODE=false

# 色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ヘルプ表示
show_help() {
    echo "🐱 neko-pm - 再開スクリプト"
    echo ""
    echo "使い方: $0 [オプション]"
    echo ""
    echo "オプション:"
    echo "  -l, --list          過去のセッション一覧を表示"
    echo "  -s, --session NAME  特定のセッションから再開（例: session_20250130_120000）"
    echo "  -w, --workers N     子猫の数を指定（デフォルト: 2）"
    echo "  -h, --help          このヘルプを表示"
    echo ""
    echo "例:"
    echo "  $0                  # 最新セッションから再開"
    echo "  $0 -l               # 過去のセッション一覧"
    echo "  $0 -s session_20250130_120000"
}

# 引数解析
while [[ $# -gt 0 ]]; do
    case $1 in
        -l|--list)
            LIST_MODE=true
            shift
            ;;
        -s|--session)
            TARGET_SESSION="$2"
            shift 2
            ;;
        -w|--workers)
            WORKERS="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}不明なオプション: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# historyディレクトリの確認
if [ ! -d "$HISTORY_DIR" ]; then
    echo -e "${YELLOW}⚠️  過去のセッションが見つからないにゃ${NC}"
    echo "通常起動するには: ./shuugou.sh"
    exit 1
fi

# 一覧表示モード
if [ "$LIST_MODE" = true ]; then
    echo -e "${CYAN}🐱 過去のセッション一覧にゃ〜${NC}"
    echo ""

    for session_dir in $(ls -1d ${HISTORY_DIR}/session_* 2>/dev/null | sort -r); do
        session_name=$(basename "$session_dir")

        # メタデータから情報取得
        if [ -f "${session_dir}/session_meta.yaml" ]; then
            ended_at=$(grep "ended_at:" "${session_dir}/session_meta.yaml" | sed 's/.*: "//' | sed 's/"//')
            status=$(grep "nawabari_status:" "${session_dir}/session_meta.yaml" | sed 's/.*: "//' | sed 's/"//')
        else
            ended_at="不明"
            status="不明"
        fi

        # latestかどうか
        if [ -L "${HISTORY_DIR}/latest" ] && [ "$(readlink ${HISTORY_DIR}/latest)" = "$session_name" ]; then
            echo -e "  ${GREEN}★ ${session_name}${NC} (latest)"
        else
            echo -e "  ・ ${session_name}"
        fi
        echo -e "      終了: ${ended_at}"
        echo -e "      状態: ${status}"
        echo ""
    done

    exit 0
fi

# 復元元セッションの確認
if [ "$TARGET_SESSION" = "latest" ]; then
    if [ ! -L "${HISTORY_DIR}/latest" ]; then
        echo -e "${RED}❌ 最新セッションのリンクが見つからないにゃ${NC}"
        echo "一覧を確認: ./resume.sh -l"
        exit 1
    fi
    SESSION_PATH="${HISTORY_DIR}/$(readlink ${HISTORY_DIR}/latest)"
else
    SESSION_PATH="${HISTORY_DIR}/${TARGET_SESSION}"
fi

if [ ! -d "$SESSION_PATH" ]; then
    echo -e "${RED}❌ セッションが見つからないにゃ: ${TARGET_SESSION}${NC}"
    echo "一覧を確認: ./resume.sh -l"
    exit 1
fi

echo -e "${CYAN}🐱 neko-pm 再開中にゃ〜${NC}"
echo -e "   復元元: ${YELLOW}$(basename $SESSION_PATH)${NC}"
echo -e "   子猫数: ${WORKERS}"
echo ""

# ===========================================
# コンテキスト復元
# ===========================================
echo -e "${GREEN}📦 コンテキスト復元中にゃ...${NC}"

# nawabari.md 復元
if [ -f "${SESSION_PATH}/nawabari.md" ]; then
    cp "${SESSION_PATH}/nawabari.md" "${SCRIPT_DIR}/nawabari.md"
    echo -e "  ${GREEN}✓ nawabari.md を復元したにゃ${NC}"
else
    echo -e "  ${YELLOW}⚠️  nawabari.md がなかったにゃ（新規作成される）${NC}"
fi

# queue/ 復元
if [ -d "${SESSION_PATH}/queue" ]; then
    rm -rf "${SCRIPT_DIR}/queue"
    cp -r "${SESSION_PATH}/queue" "${SCRIPT_DIR}/queue"
    echo -e "  ${GREEN}✓ queue/ を復元したにゃ${NC}"
else
    echo -e "  ${YELLOW}⚠️  queue/ がなかったにゃ（新規作成される）${NC}"
fi

# 前回のコンテキスト情報を読み込み
PREV_CONTEXT=""
if [ -f "${SESSION_PATH}/nawabari.md" ]; then
    PREV_CONTEXT=$(cat "${SESSION_PATH}/nawabari.md")
fi

# ===========================================
# 再開用ランチャー生成
# ===========================================
LAUNCHER_DIR="${SCRIPT_DIR}/.launchers"
mkdir -p "$LAUNCHER_DIR"

# ボスねこランチャー（再開コンテキスト付き）
cat > "${LAUNCHER_DIR}/boss-launcher.sh" << 'LAUNCHER_EOF'
#!/bin/bash
cd "$(dirname "$0")/.."
INSTRUCTIONS=$(cat instructions/boss-cat.md)

# 前回のコンテキストを読み込み
PREV_NAWABARI=""
if [ -f "nawabari.md" ]; then
    PREV_NAWABARI=$(cat nawabari.md)
fi

# 再開コンテキストを追加
RESUME_CONTEXT="

## 【再開モード】前回のセッションから続行にゃ

前回の縄張り状況:
\`\`\`
${PREV_NAWABARI}
\`\`\`

**ご主人に前回の続きから進めるか確認するにゃ！**
"

FULL_INSTRUCTIONS="${INSTRUCTIONS}${RESUME_CONTEXT}"

claude --permission-mode acceptEdits --model opus --system-prompt "$FULL_INSTRUCTIONS"
LAUNCHER_EOF
chmod +x "${LAUNCHER_DIR}/boss-launcher.sh"

# 番猫ランチャー生成（通常と同じ）
cat > "${LAUNCHER_DIR}/guard-launcher.sh" << 'LAUNCHER_EOF'
#!/bin/bash
cd "$(dirname "$0")/.."
INSTRUCTIONS=$(cat instructions/guard-cat.md)
claude --permission-mode acceptEdits --model sonnet --system-prompt "$INSTRUCTIONS"
LAUNCHER_EOF
chmod +x "${LAUNCHER_DIR}/guard-launcher.sh"

# 長老猫ランチャー生成（通常と同じ）
cat > "${LAUNCHER_DIR}/elder-launcher.sh" << 'LAUNCHER_EOF'
#!/bin/bash
cd "$(dirname "$0")/.."
INSTRUCTIONS=$(cat instructions/elder-cat.md)
claude --permission-mode acceptEdits --model opus --system-prompt "$INSTRUCTIONS"
LAUNCHER_EOF
chmod +x "${LAUNCHER_DIR}/elder-launcher.sh"

# 子猫ランチャー生成
for i in $(seq 1 $WORKERS); do
    cat > "${LAUNCHER_DIR}/kitten${i}-launcher.sh" << 'LAUNCHER_EOF'
#!/bin/bash
cd "$(dirname "$0")/.."
INSTRUCTIONS=$(cat instructions/kitten.md)
claude --permission-mode acceptEdits --model sonnet --system-prompt "$INSTRUCTIONS"
LAUNCHER_EOF
    chmod +x "${LAUNCHER_DIR}/kitten${i}-launcher.sh"
done

echo -e "  ${GREEN}✓ ランチャーを生成したにゃ${NC}"

# ===========================================
# tmuxセッション作成（shuugou.shと同じ構成）
# ===========================================
echo -e "${GREEN}📦 tmuxセッション作成中にゃ...${NC}"

# 既存セッションの確認
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
    echo -e "${YELLOW}⚠️  既存の ${SESSION_NAME} セッションを検出したにゃ。${NC}"
    echo -e "${YELLOW}   先に ./neru.sh を実行するにゃ〜${NC}"
    exit 1
fi

# キューディレクトリ確認（復元されていなければ作成）
mkdir -p "${SCRIPT_DIR}/queue/tasks"
mkdir -p "${SCRIPT_DIR}/queue/reports"

# ウィンドウ1: boss（ボスねこ専用）
tmux new-session -d -s $SESSION_NAME -n boss
tmux send-keys -t ${SESSION_NAME}:boss "echo '🐱 ボスねこ再開にゃ〜'; ${LAUNCHER_DIR}/boss-launcher.sh" Enter

# ウィンドウ2: workers（番猫 + 長老猫 + 子猫）
tmux new-window -t ${SESSION_NAME} -n workers

# 番猫（ペイン0）
tmux send-keys -t ${SESSION_NAME}:workers "echo '🐱 番猫起動にゃ〜'; ${LAUNCHER_DIR}/guard-launcher.sh" Enter

# 長老猫（ペイン1）- 右に分割
tmux split-window -t ${SESSION_NAME}:workers -h
tmux send-keys -t ${SESSION_NAME}:workers.1 "echo '🐱 長老猫起動にゃ〜'; ${LAUNCHER_DIR}/elder-launcher.sh" Enter

# 子猫たち（ペイン2〜）- 下に追加
for i in $(seq 1 $WORKERS); do
    tmux split-window -t ${SESSION_NAME}:workers -v
    tmux send-keys -t ${SESSION_NAME}:workers "echo '🐱 子猫${i}起動にゃ〜'; ${LAUNCHER_DIR}/kitten${i}-launcher.sh" Enter
done

# レイアウト調整
tmux select-layout -t ${SESSION_NAME}:workers tiled

# ワークスペース信頼の自動承認
echo -e "${YELLOW}⏳ ワークスペース承認中にゃ...${NC}"
sleep 5

# bossウィンドウ
tmux send-keys -t ${SESSION_NAME}:boss Enter 2>/dev/null || true

# workersウィンドウ
WORKER_PANES=$((2 + WORKERS))
for i in $(seq 0 $((WORKER_PANES - 1))); do
    tmux send-keys -t ${SESSION_NAME}:workers.${i} Enter 2>/dev/null || true
done
sleep 2

# bossウィンドウを選択
tmux select-window -t ${SESSION_NAME}:boss

echo ""
echo -e "${GREEN}✅ neko-pm 再開完了にゃ〜${NC}"
echo ""
echo "セッション: ${CYAN}${SESSION_NAME}${NC}"
echo ""
echo -e "${YELLOW}【復元されたコンテキスト】${NC}"
echo -e "  nawabari.md: $(basename $SESSION_PATH) から復元済み"
echo ""
echo "接続コマンド:"
echo -e "  ${YELLOW}tmux attach -t ${SESSION_NAME}${NC}"
echo ""
echo "ウィンドウ切り替え: ${CYAN}Ctrl+b 0${NC}(boss) / ${CYAN}Ctrl+b 1${NC}(workers)"
echo ""
