#!/bin/bash
# neko-pm v3.5 - セットアップスクリプト
# 別 PC への neko-pm 環境構築を自動化するにゃ
#
# 使い方:
#   git clone <neko-pm-repo>
#   cd neko-pm
#   ./scripts/setup.sh
#   ./scripts/setup.sh --work  # 仕事用 PC モード

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

WORK_MODE=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --work) WORK_MODE=true; shift ;;
        -h|--help)
            echo "🐱 neko-pm v3.5 セットアップ"
            echo ""
            echo "使い方: setup.sh [オプション]"
            echo "  --work    仕事用 PC モード（Backlog MCP 設定を追加）"
            echo "  -h        ヘルプ"
            exit 0
            ;;
        *) echo "不明なオプション: $1"; exit 1 ;;
    esac
done

echo -e "${CYAN}🐱 neko-pm v3.5 セットアップにゃ〜${NC}"
echo ""

# --- 必須ツールチェック ---
echo -e "${YELLOW}📋 必須ツール確認中...${NC}"
MISSING=()
for cmd in tmux node npm uv; do
    if command -v "$cmd" &> /dev/null; then
        echo -e "  ${GREEN}✅ $cmd${NC} $(command -v "$cmd")"
    else
        echo -e "  ${RED}❌ $cmd が見つからないにゃ${NC}"
        MISSING+=("$cmd")
    fi
done

# Claude Code
if command -v claude &> /dev/null; then
    echo -e "  ${GREEN}✅ claude${NC} $(claude --version 2>/dev/null | head -1)"
else
    echo -e "  ${RED}❌ claude が見つからないにゃ${NC}"
    echo -e "     ${YELLOW}npm install -g @anthropic-ai/claude-code${NC}"
    MISSING+=("claude")
fi

# Codex CLI（推奨）
if command -v codex &> /dev/null; then
    echo -e "  ${GREEN}✅ codex${NC} $(codex --version 2>/dev/null | head -1)"
else
    echo -e "  ${YELLOW}⚠️  codex CLI（推奨）が見つからないにゃ${NC}"
    echo -e "     ${YELLOW}npm install -g @openai/codex${NC}"
fi

# Gemini CLI（推奨）
if command -v gemini &> /dev/null; then
    echo -e "  ${GREEN}✅ gemini${NC}"
else
    echo -e "  ${YELLOW}⚠️  gemini CLI（推奨）が見つからないにゃ${NC}"
    echo -e "     ${YELLOW}npm install -g @anthropic-ai/gemini-cli${NC}"
fi

if [ ${#MISSING[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}❌ 必須ツールが不足しているにゃ: ${MISSING[*]}${NC}"
    echo -e "  インストール後に再実行してにゃ"
    exit 1
fi

echo ""

# --- MCP サーバーセットアップ ---
echo -e "${YELLOW}🔌 MCP サーバーセットアップ...${NC}"

# npx 系: 初回起動時に自動 fetch されるが、プリキャッシュで高速化
echo -e "  npx 系パッケージをプリキャッシュ中..."
NPX_PACKAGES=(
  "@modelcontextprotocol/server-memory"
  "@playwright/mcp@latest"
  "chrome-devtools-mcp@latest"
  "@drawio/mcp"
)
for pkg in "${NPX_PACKAGES[@]}"; do
  echo -n "    $pkg ... "
  npx -y "$pkg" --help >/dev/null 2>&1 && echo -e "${GREEN}✅${NC}" || echo -e "${YELLOW}⚠️ (初回接続時に fetch)${NC}"
done

# uvx 系: 初回起動時に自動 fetch されるが、プリキャッシュで高速化
echo -e "  uvx 系パッケージをプリキャッシュ中..."
UVX_PACKAGES=(
  "awslabs.aws-api-mcp-server@latest"
  "awslabs.cdk-mcp-server@latest"
  "awslabs.amazon-bedrock-agentcore-mcp-server@latest"
  "strands-agents-mcp-server"
)
for pkg in "${UVX_PACKAGES[@]}"; do
  echo -n "    $pkg ... "
  uvx "$pkg" --help >/dev/null 2>&1 && echo -e "${GREEN}✅${NC}" || echo -e "${YELLOW}⚠️ (初回接続時に fetch)${NC}"
done

# HTTP 系: インストール不要、到達確認のみ
echo -e "  HTTP 系 MCP の接続確認..."
HTTP_MCPS=(
  "https://knowledge-mcp.global.api.aws|aws-knowledge"
  "https://context7.liam.sh/mcp|context7"
  "https://api.githubcopilot.com/mcp/|github"
)
for entry in "${HTTP_MCPS[@]}"; do
  url="${entry%%|*}"
  name="${entry##*|}"
  echo -n "    $name ($url) ... "
  curl -s --max-time 5 -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -qE "^[234]" \
    && echo -e "${GREEN}✅${NC}" \
    || echo -e "${YELLOW}⚠️ (接続不可 - ネットワーク確認)${NC}"
done

echo ""

# --- ディレクトリ作成 ---
echo -e "${YELLOW}📁 ディレクトリ構造作成中...${NC}"
mkdir -p "${PROJECT_DIR}/memory"
mkdir -p "${PROJECT_DIR}/config"
mkdir -p "${PROJECT_DIR}/context"
mkdir -p "${PROJECT_DIR}/output"
mkdir -p "${PROJECT_DIR}/history"
mkdir -p "${PROJECT_DIR}/.claude/teams/neko-pm"
echo -e "  ${GREEN}✅ 完了${NC}"

# --- Memory MCP ---
echo -e "${YELLOW}🧠 Memory MCP 確認中...${NC}"
if claude mcp list 2>/dev/null | grep -q "memory"; then
    echo -e "  ${GREEN}✅ Memory MCP 設定済み${NC}"
else
    echo -e "  ${YELLOW}📝 Memory MCP を設定中...${NC}"
    claude mcp add memory \
        -e MEMORY_FILE_PATH="${PROJECT_DIR}/memory/neko_memory.jsonl" \
        -- npx -y @modelcontextprotocol/server-memory 2>/dev/null \
        && echo -e "  ${GREEN}✅ Memory MCP 設定完了${NC}" \
        || echo -e "  ${YELLOW}⚠️  手動設定が必要にゃ${NC}"
fi

echo ""

# --- settings.json MCP 設定 ---
echo -e "${YELLOW}⚙️  settings.json 確認中...${NC}"
SETTINGS_FILE="$HOME/.claude/settings.json"
if [ -f "$SETTINGS_FILE" ]; then
  # mcpServers キーが存在するか確認
  if grep -q '"mcpServers"' "$SETTINGS_FILE"; then
    echo -e "  ${GREEN}✅ settings.json に mcpServers 設定済み${NC}"
    # MCP サーバー数を表示
    MCP_COUNT=$(grep -c '"type"' "$SETTINGS_FILE" 2>/dev/null || echo 0)
    echo -e "  設定済み MCP サーバー: ${MCP_COUNT} 個"
  else
    echo -e "  ${YELLOW}⚠️  mcpServers が未設定。テンプレートを参照:${NC}"
    echo -e "  ${CYAN}cat ${PROJECT_DIR}/config/settings.json.template${NC}"
  fi
else
  echo -e "  ${YELLOW}⚠️  ~/.claude/settings.json が存在しない${NC}"
  echo -e "  テンプレートからコピー:"
  echo -e "  ${CYAN}mkdir -p ~/.claude && cp ${PROJECT_DIR}/config/settings.json.template ~/.claude/settings.json${NC}"
fi

echo ""

# --- 環境変数チェック ---
echo -e "${YELLOW}🔑 環境変数チェック...${NC}"
ENV_VARS=(
  "GITHUB_TOKEN|GitHub MCP 認証|必須"
  "ANTHROPIC_API_KEY|Claude Code API|必須"
  "OPENAI_API_KEY|Codex CLI|推奨"
  "AWS_PROFILE|AWS MCP 群|推奨"
)
for entry in "${ENV_VARS[@]}"; do
  IFS='|' read -r var desc importance <<< "$entry"
  if [ -n "${!var:-}" ]; then
    echo -e "  ${GREEN}✅ $var${NC} ($desc)"
  else
    if [ "$importance" = "必須" ]; then
      echo -e "  ${RED}❌ $var${NC} ($desc) - $importance"
    else
      echo -e "  ${YELLOW}⚠️  $var${NC} ($desc) - $importance"
    fi
  fi
done

echo ""

# --- 環境変数設定 ---
echo -e "${YELLOW}🔧 環境設定...${NC}"
if [ "$WORK_MODE" = true ]; then
    echo -e "  ${CYAN}📋 仕事用 PC モード${NC}"
    echo -e "  ${YELLOW}Backlog MCP の設定が必要にゃ:${NC}"
    echo -e "    claude mcp add backlog -- <backlog-mcp-server-command>"
    echo ""
    echo -e "  ${YELLOW}~/.claude/settings.json に以下を確認:${NC}"
    echo -e "    NEKO_PM_ENV=work を env に追加"
else
    echo -e "  ${CYAN}🏠 個人開発モード${NC}"
fi

# --- global_context.md ---
if [ ! -f "${PROJECT_DIR}/memory/global_context.md" ]; then
    cat > "${PROJECT_DIR}/memory/global_context.md" << 'EOF'
# neko-pm グローバルコンテキスト

> 最終更新: (未設定)

## ご主人の好み
- (ここにご主人の好みを記録するにゃ)

## 重要な意思決定
| 日付 | 決定事項 | 理由 |
|------|----------|------|
| - | - | - |

## プロジェクト横断の知見
- (複数プロジェクトに役立つ知見)
EOF
    echo -e "  ${GREEN}📝 global_context.md 作成${NC}"
fi

# --- Agent Teams 環境変数 ---
echo ""
echo -e "${YELLOW}🔧 ~/.claude/settings.json の確認事項:${NC}"
echo -e '  "env": {'
echo -e '    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"'
if [ "$WORK_MODE" = true ]; then
    echo -e '    "NEKO_PM_ENV": "work"'
fi
echo -e '  }'

echo ""
echo -e "${GREEN}✅ neko-pm v3.5 セットアップ完了にゃ〜${NC}"
echo ""
echo -e "MCP: ${CYAN}12 サーバー構成（npx/uvx 自動 fetch 対応）${NC}"
echo -e "起動: ${CYAN}./scripts/start-team.sh${NC}"
echo -e "停止: ${CYAN}./scripts/stop-team.sh${NC}"
echo ""
echo -e "${YELLOW}📝 次のステップ:${NC}"
echo -e "  1. 環境変数を設定（GITHUB_TOKEN, ANTHROPIC_API_KEY）"
echo -e "  2. settings.json を確認・配置"
echo -e "  3. ${CYAN}./scripts/start-team.sh${NC} で起動"
