#!/bin/bash
# neko-pm 集合スクリプト（にゃ〜）
#
# 使い方:
#   ./shuugou.sh          # デフォルト: 子猫3匹
#   ./shuugou.sh -w 5     # 子猫5匹で起動
#   ./shuugou.sh --help   # ヘルプ表示

set -e

# デフォルト設定
WORKERS=3
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER_DIR="${SCRIPT_DIR}/.launchers"

# 色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ヘルプ表示
show_help() {
    echo "🐱 neko-pm - 猫型マルチエージェントシステム"
    echo ""
    echo "使い方: $0 [オプション]"
    echo ""
    echo "オプション:"
    echo "  -w, --workers N   子猫の数を指定（デフォルト: 3）"
    echo "  -h, --help        このヘルプを表示"
    echo ""
    echo "例:"
    echo "  $0              # 子猫3匹で起動"
    echo "  $0 -w 5         # 子猫5匹で起動"
}

# 引数解析
while [[ $# -gt 0 ]]; do
    case $1 in
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

echo -e "${CYAN}🐱 neko-pm 起動中にゃ〜${NC}"
echo -e "   子猫の数: ${WORKERS}"

# 既存セッションの確認
for session in boss team worker; do
    if tmux has-session -t $session 2>/dev/null; then
        echo -e "${YELLOW}⚠️  既存の ${session} セッションを検出したにゃ。${NC}"
        echo -e "${YELLOW}   先に ./neru.sh を実行するにゃ〜${NC}"
        exit 1
    fi
done

# ランチャーディレクトリ作成
mkdir -p "${LAUNCHER_DIR}"

# キューディレクトリの初期化
mkdir -p "${SCRIPT_DIR}/queue/tasks"
mkdir -p "${SCRIPT_DIR}/queue/reports"

# 状況板の初期化
cat > "${SCRIPT_DIR}/nawabari.md" << 'EOF'
# 作戦状況板

> 最終更新: 起動時
> 更新者: システム
> **作戦状態: 待機中**

## 作戦概要

まだ作戦は開始されていないにゃ。

## 子猫状態

| 子猫 | 状態 | 現在のタスク | 進捗 |
|------|------|-------------|------|
| - | 待機中 | - | - |

## 完了タスク

なし

## 要対応事項

なし
EOF

# ボスねこランチャー生成
cat > "${LAUNCHER_DIR}/boss-launcher.sh" << EOF
#!/bin/bash
cd "${SCRIPT_DIR}"
claude --instructions "${SCRIPT_DIR}/instructions/boss-cat.md"
EOF
chmod +x "${LAUNCHER_DIR}/boss-launcher.sh"

# 番猫ランチャー生成
cat > "${LAUNCHER_DIR}/guard-launcher.sh" << EOF
#!/bin/bash
cd "${SCRIPT_DIR}"
claude --instructions "${SCRIPT_DIR}/instructions/guard-cat.md"
EOF
chmod +x "${LAUNCHER_DIR}/guard-launcher.sh"

# 子猫ランチャー生成（動的）
for i in $(seq 1 $WORKERS); do
    cat > "${LAUNCHER_DIR}/kitten${i}-launcher.sh" << EOF
#!/bin/bash
cd "${SCRIPT_DIR}"
# 子猫${i}として起動
export KITTEN_ID=${i}
claude --instructions "${SCRIPT_DIR}/instructions/kitten.md"
EOF
    chmod +x "${LAUNCHER_DIR}/kitten${i}-launcher.sh"
done

# tmuxセッション作成
echo -e "${GREEN}📦 tmuxセッション作成中にゃ...${NC}"

# ボスねこセッション（opus）
tmux new-session -d -s boss -n main
tmux send-keys -t boss:main "echo '🐱 ボスねこセッション起動にゃ〜'; ${LAUNCHER_DIR}/boss-launcher.sh" Enter

# 番猫セッション（sonnet）
tmux new-session -d -s team -n main
tmux send-keys -t team:main "echo '🐱 番猫セッション起動にゃ〜'; ${LAUNCHER_DIR}/guard-launcher.sh" Enter

# 子猫セッション（sonnet × N）
tmux new-session -d -s worker -n main

# 最初の子猫
tmux send-keys -t worker:main "echo '🐱 子猫1セッション起動にゃ〜'; ${LAUNCHER_DIR}/kitten1-launcher.sh" Enter

# 追加の子猫（ペイン分割）
for i in $(seq 2 $WORKERS); do
    tmux split-window -t worker -h
    tmux select-layout -t worker tiled
    tmux send-keys -t worker "echo '🐱 子猫${i}セッション起動にゃ〜'; ${LAUNCHER_DIR}/kitten${i}-launcher.sh" Enter
done

# レイアウト調整
tmux select-layout -t worker tiled

echo ""
echo -e "${GREEN}✅ neko-pm 起動完了にゃ〜${NC}"
echo ""
echo "セッション一覧:"
echo -e "  ${CYAN}boss${NC}   - ボスねこ（Opus）: tmux attach -t boss"
echo -e "  ${CYAN}team${NC}   - 番猫（Sonnet）: tmux attach -t team"
echo -e "  ${CYAN}worker${NC} - 子猫×${WORKERS}（Sonnet）: tmux attach -t worker"
echo ""
echo "ご主人は boss セッションに接続して指令を出すにゃ〜"
echo -e "  ${YELLOW}tmux attach -t boss${NC}"
