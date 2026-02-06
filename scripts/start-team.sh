#!/bin/bash
# neko-pm v3 - Agent Teams 起動スクリプト
#
# 使い方:
#   ./scripts/start-team.sh          # デフォルト起動
#   ./scripts/start-team.sh --help   # ヘルプ
#
# Agent Teams は CLAUDE.md をプロジェクトルートとして読み込む。
# Lead（ボスねこ）が delegate mode で Teammates を spawn する。

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 色定義
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

show_help() {
    echo "🐱 neko-pm v3 - Agent Teams 起動スクリプト"
    echo ""
    echo "使い方: $0 [オプション]"
    echo ""
    echo "オプション:"
    echo "  -h, --help    ヘルプ表示"
    echo ""
    echo "構成:"
    echo "  Lead (ボスねこ) = タスク指揮 + 分解（delegate mode）"
    echo "  Teammates (子猫) = 実装担当（Lead が spawn）"
    echo "  外部エージェント = Codex CLI / Gemini CLI（Bash 経由）"
    echo "  長老猫 = Opus（Task tool でオンデマンド召喚）"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help) show_help; exit 0 ;;
        *) echo "不明なオプション: $1" >&2; show_help; exit 1 ;;
    esac
done

echo -e "${CYAN}🐱 neko-pm v3 起動中にゃ〜${NC}"

# Memory MCP 確認
echo -e "${CYAN}🧠 Memory MCP 確認中にゃ...${NC}"
MEMORY_FILE="${PROJECT_DIR}/memory/neko_memory.jsonl"
mkdir -p "${PROJECT_DIR}/memory"

if command -v claude &> /dev/null; then
    if claude mcp list 2>/dev/null | grep -q "memory"; then
        echo -e "${GREEN}✅ Memory MCP は既に設定済みにゃ${NC}"
    else
        echo -e "${YELLOW}📝 Memory MCP を設定中にゃ...${NC}"
        claude mcp add memory \
            -e MEMORY_FILE_PATH="${MEMORY_FILE}" \
            -- npx -y @modelcontextprotocol/server-memory 2>/dev/null \
            && echo -e "${GREEN}✅ Memory MCP 設定完了にゃ〜${NC}" \
            || echo -e "${YELLOW}⚠️  Memory MCP の自動設定に失敗したにゃ${NC}"
    fi
fi

# グローバルコンテキストファイルの作成（存在しない場合）
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

echo ""
echo -e "${GREEN}✅ neko-pm v3 準備完了にゃ〜${NC}"
echo ""
echo -e "プロジェクトルート: ${CYAN}${PROJECT_DIR}${NC}"
echo ""
echo -e "${YELLOW}【v3 構成】${NC}"
echo -e "  🐱 Lead（ボスねこ）: delegate mode でタスク指揮"
echo -e "  🐱 Teammates（子猫）: Lead が必要に応じて spawn"
echo -e "  🦊 賢者キツネ: gemini CLI（Bash 経由）"
echo -e "  🦝 研究狸: codex CLI（Bash 経由）"
echo -e "  🦉 目利きフクロウ: codex CLI（Bash 経由）"
echo -e "  👴 長老猫: Opus（Task tool でオンデマンド）"
echo ""
echo -e "起動: ${CYAN}claude --model opus${NC}"
echo -e "（CLAUDE.md を自動読み込み → Lead として動作）"
echo ""
