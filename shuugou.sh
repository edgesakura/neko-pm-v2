#!/bin/bash
# neko-pm 集合スクリプト（にゃ〜）
#
# 使い方:
#   ./shuugou.sh          # デフォルト: 子猫2匹
#   ./shuugou.sh -w 5     # 子猫5匹で起動
#   ./shuugou.sh --help   # ヘルプ表示
#
# ウィンドウ構成（3ウィンドウ）:
#   ウィンドウ "boss":        ボスねこ専用（Sonnet・作戦指揮）
#   ウィンドウ "workers":     番猫 + 子猫たち + フクロウ（Sonnet・実装作業）
#   ウィンドウ "specialists": キツネ + 研究狸（常駐）
#
# 長老猫（Opus）はオンデマンド召喚（Task tool）- ペインなし

set -e

# デフォルト設定
WORKERS=2
SESSION_NAME="neko"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER_DIR="${SCRIPT_DIR}/.launchers"
HISTORY_DIR="${SCRIPT_DIR}/history"

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
    echo "  -w, --workers N   子猫の数を指定（デフォルト: 2）"
    echo "  -h, --help        このヘルプを表示"
    echo ""
    echo "ウィンドウ構成:"
    echo "  'boss':        ボスねこ（Sonnet・作戦指揮）"
    echo "  'workers':     番猫 + 子猫たち + フクロウ（Sonnet・実装作業）"
    echo "  'specialists': キツネ + 研究狸（常駐）"
    echo ""
    echo "長老猫（Opus）はオンデマンド召喚（Task tool）"
    echo ""
    echo "例:"
    echo "  $0              # 子猫2匹で起動"
    echo "  $0 -w 5         # 子猫5匹で起動"
    echo ""
    echo "再開する場合:"
    echo "  ./resume.sh     # 前回のセッションから再開"
    echo "  ./resume.sh -l  # 過去のセッション一覧"
}

# 引数解析
while [[ $# -gt 0 ]]; do
    case $1 in
        -w|--workers)
            # 引数の存在チェック
            if [ -z "$2" ]; then
                echo -e "${RED}エラー: -w/--workers オプションには引数が必要にゃ${NC}" >&2
                echo "使用方法: $0 -w <数値>" >&2
                exit 1
            fi

            WORKERS="$2"

            # 整数チェック（正規表現）
            if ! [[ "$WORKERS" =~ ^[0-9]+$ ]]; then
                echo -e "${RED}エラー: WORKERS は正の整数である必要があるにゃ${NC}" >&2
                echo "指定された値: '$WORKERS'" >&2
                exit 1
            fi

            # 範囲チェック（1〜10）
            if [ "$WORKERS" -lt 1 ] || [ "$WORKERS" -gt 10 ]; then
                echo -e "${RED}エラー: WORKERS は 1 から 10 の範囲で指定するにゃ${NC}" >&2
                echo "指定された値: $WORKERS" >&2
                exit 1
            fi

            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}不明なオプション: $1${NC}" >&2
            show_help
            exit 1
            ;;
    esac
done

echo -e "${CYAN}🐱 neko-pm 起動中にゃ〜${NC}"
echo -e "   子猫の数: ${WORKERS}"

# 前回セッションの確認
if [ -L "${HISTORY_DIR}/latest" ]; then
    LATEST_SESSION=$(readlink "${HISTORY_DIR}/latest")
    echo ""
    echo -e "${YELLOW}💡 前回のセッションが見つかったにゃ: ${LATEST_SESSION}${NC}"
    echo -e "   再開するには: ${CYAN}./resume.sh${NC}"
    echo ""
fi

# 既存セッションの確認
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
    echo -e "${YELLOW}⚠️  既存の ${SESSION_NAME} セッションを検出したにゃ。${NC}"
    echo -e "${YELLOW}   先に ./neru.sh を実行するにゃ〜${NC}"
    exit 1
fi

# ランチャーディレクトリ作成
mkdir -p "${LAUNCHER_DIR}"

# ===========================================
# Memory MCP セットアップ
# ===========================================
echo -e "${CYAN}🧠 Memory MCP 確認中にゃ...${NC}"

MEMORY_FILE="${SCRIPT_DIR}/memory/neko_memory.jsonl"
mkdir -p "${SCRIPT_DIR}/memory"

# Memory MCP が既に設定済みか確認
if command -v claude &> /dev/null; then
    if claude mcp list 2>/dev/null | grep -q "memory"; then
        echo -e "${GREEN}✅ Memory MCP は既に設定済みにゃ${NC}"
    else
        echo -e "${YELLOW}📝 Memory MCP を設定中にゃ...${NC}"
        if claude mcp add memory \
            -e MEMORY_FILE_PATH="${MEMORY_FILE}" \
            -- npx -y @modelcontextprotocol/server-memory 2>/dev/null; then
            echo -e "${GREEN}✅ Memory MCP 設定完了にゃ〜${NC}"
        else
            echo -e "${YELLOW}⚠️  Memory MCP の自動設定に失敗したにゃ（手動で設定可能）${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  claude コマンドが見つからないにゃ${NC}"
fi

# グローバルコンテキストファイルの作成（存在しない場合）
if [ ! -f "${SCRIPT_DIR}/memory/global_context.md" ]; then
    cat > "${SCRIPT_DIR}/memory/global_context.md" << 'CONTEXT_EOF'
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

## 解決済み問題

| 問題 | 原因 | 解決方法 |
|------|------|----------|
| - | - | - |

## 注意事項

- Memory MCP で永続化される情報は `memory/neko_memory.jsonl` に保存されるにゃ
- コンパクション後もセッション跨ぎで記憶が保持されるにゃ〜
CONTEXT_EOF
    echo -e "${GREEN}📝 global_context.md を作成したにゃ${NC}"
fi

# キューディレクトリの初期化
mkdir -p "${SCRIPT_DIR}/queue/tasks"
mkdir -p "${SCRIPT_DIR}/queue/reports"

# 状況板の初期化
cat > "${SCRIPT_DIR}/nawabari.md" << 'EOF'
# 🐱 作戦状況板

> 最終更新: 起動時
> 更新者: システム
> **作戦状態: 待機中**

## 🚨 要対応 - ご主人のご判断をお待ちしておりますにゃ

なし

## 🔄 進行中

なし

## 作戦概要

まだ作戦は開始されていないにゃ。

## 子猫状態

| 子猫 | 状態 | 現在のタスク | 進捗 |
|------|------|-------------|------|
| - | 待機中 | - | - |

## ✅ 完了タスク

なし

## 🎯 スキル化候補

なし

## 振り返りサマリー

なし
EOF

# ボスねこランチャー生成（opus）
cat > "${LAUNCHER_DIR}/boss-launcher.sh" << 'LAUNCHER_EOF'
#!/bin/bash
cd "$(dirname "$0")/.."
INSTRUCTIONS=$(cat instructions/boss-cat.md)
claude --permission-mode acceptEdits --model opus --system-prompt "$INSTRUCTIONS"
LAUNCHER_EOF
chmod +x "${LAUNCHER_DIR}/boss-launcher.sh"

# 番猫ランチャー生成（sonnet）
cat > "${LAUNCHER_DIR}/guard-launcher.sh" << 'LAUNCHER_EOF'
#!/bin/bash
cd "$(dirname "$0")/.."
INSTRUCTIONS=$(cat instructions/guard-cat.md)
claude --permission-mode acceptEdits --model sonnet --system-prompt "$INSTRUCTIONS"
LAUNCHER_EOF
chmod +x "${LAUNCHER_DIR}/guard-launcher.sh"

# 長老猫はオンデマンド召喚（Task tool）のためランチャーなし

# 子猫ランチャー生成（sonnet・動的）
for i in $(seq 1 $WORKERS); do
    cat > "${LAUNCHER_DIR}/kitten${i}-launcher.sh" << 'LAUNCHER_EOF'
#!/bin/bash
cd "$(dirname "$0")/.."
INSTRUCTIONS=$(cat instructions/kitten.md)
claude --permission-mode acceptEdits --model sonnet --system-prompt "$INSTRUCTIONS"
LAUNCHER_EOF
    chmod +x "${LAUNCHER_DIR}/kitten${i}-launcher.sh"
done

# 目利きフクロウランチャー生成（codex-cli監視）
cat > "${LAUNCHER_DIR}/owl-launcher.sh" << 'LAUNCHER_EOF'
#!/bin/bash
cd "$(dirname "$0")/.."
echo "🦉 目利きフクロウ起動ホー！"
echo "   承認ゲートとして監視を開始するホー"
echo ""
./owl-watcher.sh
LAUNCHER_EOF
chmod +x "${LAUNCHER_DIR}/owl-launcher.sh"

# 賢者キツネランチャー生成（Gemini CLI リサーチ専用）
cat > "${LAUNCHER_DIR}/fox-launcher.sh" << 'LAUNCHER_EOF'
#!/bin/bash
cd "$(dirname "$0")/.."
echo "🦊 賢者キツネ起動コン！"
echo "   リサーチ専用モード（読み取りのみ）で常駐するコン"
echo ""
# full モード = 通常モード
gemini --approval-mode full
LAUNCHER_EOF
chmod +x "${LAUNCHER_DIR}/fox-launcher.sh"

# 研究狸ランチャー生成（Codex CLI 深い調査）
cat > "${LAUNCHER_DIR}/tanuki-launcher.sh" << 'LAUNCHER_EOF'
#!/bin/bash
cd "$(dirname "$0")/.."
echo "🦝 研究狸起動ポン！"
echo "   深い調査モードで常駐するポン"
echo ""
# 対話モードで起動（読み取り専用サンドボックス）
codex --sandbox read-only
LAUNCHER_EOF
chmod +x "${LAUNCHER_DIR}/tanuki-launcher.sh"

# ===========================================
# tmuxセッション作成（3ウィンドウ構成）
# ===========================================
echo -e "${GREEN}📦 tmuxセッション作成中にゃ...${NC}"

# ウィンドウ1: boss（ボスねこ専用）
tmux new-session -d -s $SESSION_NAME -n boss
tmux send-keys -t ${SESSION_NAME}:boss "echo '🐱 ボスねこ起動にゃ〜'; ${LAUNCHER_DIR}/boss-launcher.sh" Enter

# ウィンドウ2: workers（番猫 + 子猫たち + フクロウ）
tmux new-window -t ${SESSION_NAME} -n workers

# 番猫（ペイン0）
tmux send-keys -t ${SESSION_NAME}:workers "echo '🐱 番猫起動にゃ〜'; ${LAUNCHER_DIR}/guard-launcher.sh" Enter

# 子猫たち（ペイン1〜N）- 右に分割して追加
for i in $(seq 1 $WORKERS); do
    tmux split-window -t ${SESSION_NAME}:workers -h
    tmux send-keys -t ${SESSION_NAME}:workers "echo '🐱 子猫${i}起動にゃ〜'; ${LAUNCHER_DIR}/kitten${i}-launcher.sh" Enter
done

# 目利きフクロウ（ペインN+1）- workersウィンドウ内でコードレビュー
OWL_PANE=$((1 + WORKERS))
tmux split-window -t ${SESSION_NAME}:workers -h
tmux send-keys -t ${SESSION_NAME}:workers.${OWL_PANE} "echo '🦉 目利きフクロウ起動ホー'; ${LAUNCHER_DIR}/owl-launcher.sh" Enter

# レイアウト調整（タイル状に並べる）
tmux select-layout -t ${SESSION_NAME}:workers tiled

# ウィンドウ3: specialists（キツネ + 研究狸）
# 常駐するスペシャリストたち（長老猫はオンデマンド）
tmux new-window -t ${SESSION_NAME} -n specialists

# 賢者キツネ（ペイン0）- リサーチ
tmux send-keys -t ${SESSION_NAME}:specialists "echo '🦊 賢者キツネ起動コン'; ${LAUNCHER_DIR}/fox-launcher.sh" Enter

# 研究狸（ペイン1）- 深い調査・ボスねこの相談相手
tmux split-window -t ${SESSION_NAME}:specialists -h
tmux send-keys -t ${SESSION_NAME}:specialists.1 "echo '🦝 研究狸起動ポン'; ${LAUNCHER_DIR}/tanuki-launcher.sh" Enter

# レイアウト調整（左右に並べる）
tmux select-layout -t ${SESSION_NAME}:specialists even-horizontal

# ===========================================
# @agent_id 設定（コンパクション復帰時の自己同定用）
# ===========================================
echo -e "${CYAN}🏷️  @agent_id 設定中にゃ...${NC}"

# bossウィンドウ
tmux set-option -p -t ${SESSION_NAME}:boss @agent_id "boss-cat"

# workersウィンドウ
tmux set-option -p -t ${SESSION_NAME}:workers.0 @agent_id "guard-cat"
for i in $(seq 1 $WORKERS); do
    tmux set-option -p -t ${SESSION_NAME}:workers.${i} @agent_id "kitten${i}"
done
OWL_PANE=$((1 + WORKERS))
tmux set-option -p -t ${SESSION_NAME}:workers.${OWL_PANE} @agent_id "owl-reviewer"

# specialistsウィンドウ
tmux set-option -p -t ${SESSION_NAME}:specialists.0 @agent_id "sage-fox"
tmux set-option -p -t ${SESSION_NAME}:specialists.1 @agent_id "research-tanuki"

echo -e "${GREEN}✅ @agent_id 設定完了にゃ〜${NC}"

# ワークスペース信頼の自動承認（5秒待ってからEnter送信）
echo -e "${YELLOW}⏳ ワークスペース承認中にゃ...${NC}"
sleep 5

# bossウィンドウ
tmux send-keys -t ${SESSION_NAME}:boss Enter 2>/dev/null || true

# workersウィンドウ（番猫 + 子猫たち + フクロウ）
WORKER_PANES=$((1 + WORKERS + 1))  # 番猫 + 子猫 + フクロウ
for i in $(seq 0 $((WORKER_PANES - 1))); do
    tmux send-keys -t ${SESSION_NAME}:workers.${i} Enter 2>/dev/null || true
done

# specialistsウィンドウ（キツネ + 研究狸）
for i in $(seq 0 1); do
    tmux send-keys -t ${SESSION_NAME}:specialists.${i} Enter 2>/dev/null || true
done
sleep 2

# ===========================================
# chat-app をバックグラウンドで起動
# ===========================================
echo -e "${CYAN}📱 chat-app 起動中にゃ...${NC}"
mkdir -p logs
(cd output/chat-app && npm start > ../../logs/chat-app.log 2>&1 &)
echo -e "${GREEN}✅ chat-app をバックグラウンドで起動したにゃ（ログ: logs/chat-app.log）${NC}"
sleep 2

# 最初のウィンドウ（boss）を選択
tmux select-window -t ${SESSION_NAME}:boss

echo ""
echo -e "${GREEN}✅ neko-pm 起動完了にゃ〜${NC}"
echo ""
echo "セッション: ${CYAN}${SESSION_NAME}${NC}"
echo ""
echo -e "${YELLOW}【ウィンドウ構成】${NC}"
echo ""
echo -e "📌 ウィンドウ ${CYAN}boss${NC} (Ctrl+b 0):"
echo -e "  └─ ボスねこ（Sonnet）- 作戦指揮・ユーザー相談"
echo ""
echo -e "📌 ウィンドウ ${CYAN}workers${NC} (Ctrl+b 1):"
echo -e "  ├─ ペイン0: 番猫（Sonnet）- タスク管理"
for i in $(seq 1 $WORKERS); do
    echo -e "  ├─ ペイン${i}: 子猫${i}（Sonnet）- 実装作業"
done
OWL_PANE=$((1 + WORKERS))
echo -e "  └─ ペイン${OWL_PANE}: 🦉目利きフクロウ（Codex）- コードレビュー"
echo ""
echo -e "📌 ウィンドウ ${CYAN}specialists${NC} (Ctrl+b 2):"
echo -e "  ├─ ペイン0: 🦊賢者キツネ（Gemini CLI）- リサーチ"
echo -e "  └─ ペイン1: 🦝研究狸（Codex CLI）- 深い調査"
echo ""
echo -e "📌 ${YELLOW}長老猫（Opus）${NC}: オンデマンド召喚（Task tool）"
echo ""
echo "接続コマンド:"
echo -e "  ${YELLOW}tmux attach -t ${SESSION_NAME}${NC}"
echo ""
echo "ウィンドウ切り替え:"
echo -e "  ${CYAN}Ctrl+b 0${NC}(boss) / ${CYAN}Ctrl+b 1${NC}(workers) / ${CYAN}Ctrl+b 2${NC}(specialists)"
echo "ペイン移動: ${CYAN}Ctrl+b → 矢印キー${NC}"
echo ""
