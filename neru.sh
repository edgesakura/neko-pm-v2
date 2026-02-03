#!/bin/bash
# neko-pm おやすみスクリプト（にゃ〜）
#
# 使い方:
#   ./neru.sh          # セッション終了＆コンテキスト保存
#   ./neru.sh --force  # 保存せずに強制終了

set -e

SESSION_NAME="neko"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER_DIR="${SCRIPT_DIR}/.launchers"
HISTORY_DIR="${SCRIPT_DIR}/history"
QUEUE_DIR="${SCRIPT_DIR}/queue"

# 色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 引数解析
FORCE_EXIT=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--force)
            FORCE_EXIT=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

echo -e "${CYAN}🐱 neko-pm 終了中にゃ〜${NC}"

# ===========================================
# コンテキスト保存（--force でない場合）
# ===========================================
if [ "$FORCE_EXIT" = false ]; then
    # historyディレクトリ作成
    mkdir -p "$HISTORY_DIR"

    # タイムスタンプ生成
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    SESSION_DIR="${HISTORY_DIR}/session_${TIMESTAMP}"
    mkdir -p "$SESSION_DIR"

    echo -e "  ${CYAN}📦 コンテキストを保存中にゃ...${NC}"

    # nawabari.md を保存
    if [ -f "${SCRIPT_DIR}/nawabari.md" ]; then
        cp "${SCRIPT_DIR}/nawabari.md" "${SESSION_DIR}/nawabari.md"
        echo -e "  ${GREEN}✓ nawabari.md を保存したにゃ${NC}"
    fi

    # queue/ を保存（空でない場合）
    if [ -d "$QUEUE_DIR" ] && [ "$(ls -A $QUEUE_DIR 2>/dev/null)" ]; then
        cp -r "$QUEUE_DIR" "${SESSION_DIR}/queue"
        echo -e "  ${GREEN}✓ queue/ を保存したにゃ${NC}"

        # 振り返りレポートの存在確認
        RETRO_COUNT=$(find "$QUEUE_DIR/reports" -name "retrospective_*.md" 2>/dev/null | wc -l)
        if [ "$RETRO_COUNT" -gt 0 ]; then
            echo -e "  ${GREEN}✓ 振り返りレポート ${RETRO_COUNT}件 を保存したにゃ${NC}"
        else
            echo -e "  ${YELLOW}⚠️  振り返りレポートがないにゃ（作戦完了後は振り返りを忘れずに！）${NC}"
        fi
    fi

    # セッションメタデータ作成
    cat > "${SESSION_DIR}/session_meta.yaml" << EOF
session_id: "session_${TIMESTAMP}"
ended_at: "$(date -Iseconds)"
nawabari_status: "$(grep -m1 '作戦状態' ${SCRIPT_DIR}/nawabari.md 2>/dev/null | sed 's/.*: //' || echo '不明')"
notes: |
  このセッションは ${TIMESTAMP} に終了しました。
  再開するには ./resume.sh を実行してください。
EOF
    echo -e "  ${GREEN}✓ セッションメタデータを作成したにゃ${NC}"

    # 最新セッションへのシンボリックリンク更新
    rm -f "${HISTORY_DIR}/latest"
    ln -s "session_${TIMESTAMP}" "${HISTORY_DIR}/latest"
    echo -e "  ${GREEN}✓ latest リンクを更新したにゃ${NC}"

    echo ""
    echo -e "  ${YELLOW}💾 保存先: ${SESSION_DIR}${NC}"
fi

# ===========================================
# セッション終了
# ===========================================
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
    tmux kill-session -t $SESSION_NAME
    echo -e "  ${GREEN}✓ セッション ${SESSION_NAME} を終了したにゃ${NC}"
else
    echo -e "${YELLOW}⚠️  終了するセッションがなかったにゃ${NC}"
fi

# ランチャーのクリーンアップ
if [ -d "$LAUNCHER_DIR" ]; then
    rm -rf "$LAUNCHER_DIR"
    echo -e "  ${GREEN}✓ ランチャーをクリーンアップしたにゃ${NC}"
fi

echo ""
if [ "$FORCE_EXIT" = false ]; then
    echo -e "再開するには: ${CYAN}./resume.sh${NC}"
fi
echo "おやすみにゃ〜 🐱💤"
