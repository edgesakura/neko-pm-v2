#!/bin/bash
# ============================================================
# 目利きフクロウ監視スクリプト (owl-watcher.sh)
# ============================================================
#
# 役割: queue/reports/ を監視し、新規報告を自動レビュー
# ツール: Codex CLI (OpenAI)
#
# 機能:
#   1. 新規報告YAMLを検知
#   2. Codexでコードレビュー実行
#   3. レビュー結果をYAMLに追記
#   4. HIGH以上の問題があれば番猫に警告
#
# 使い方:
#   ./owl-watcher.sh              # フォアグラウンドで実行
#   ./owl-watcher.sh --daemon     # バックグラウンドで実行
#   ./owl-watcher.sh --stop       # デーモン停止
#
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPORTS_DIR="${SCRIPT_DIR}/queue/reports"
LOG_FILE="${SCRIPT_DIR}/logs/owl-watcher.log"
APPROVAL_LOG="${SCRIPT_DIR}/logs/approval.log"
PID_FILE="${SCRIPT_DIR}/.owl-watcher.pid"

# 設定値（環境変数からオーバーライド可能）
POLL_INTERVAL="${OWL_POLL_INTERVAL:-15}"  # 秒（レポート監視）
APPROVAL_POLL_INTERVAL="${OWL_APPROVAL_POLL_INTERVAL:-5}"  # 秒（承認監視）

# レビュー範囲: 環境変数 OWL_REVIEW_RANGE で指定可能
# デフォルト: HEAD~1（直近1コミットの変更）
# 例: OWL_REVIEW_RANGE="main..HEAD" で複数コミットをまとめてレビュー
REVIEW_RANGE="${OWL_REVIEW_RANGE:-HEAD~1}"

# 入力バリデーション: 整数チェック
validate_integer() {
    local var_name="$1"
    local var_value="$2"
    if ! [[ "$var_value" =~ ^[0-9]+$ ]]; then
        echo "Error: ${var_name} must be a positive integer, got: '${var_value}'" >&2
        exit 1
    fi
    if [ "$var_value" -lt 1 ] || [ "$var_value" -gt 3600 ]; then
        echo "Error: ${var_name} must be between 1 and 3600, got: '${var_value}'" >&2
        exit 1
    fi
}

# 設定値の検証
validate_integer "POLL_INTERVAL" "$POLL_INTERVAL"
validate_integer "APPROVAL_POLL_INTERVAL" "$APPROVAL_POLL_INTERVAL"

# 承認監視設定
# 全子猫ペインを監視対象に（workers.0=番猫、1-3=子猫）
PANES_TO_MONITOR=("neko:workers.0" "neko:workers.1" "neko:workers.2" "neko:workers.3")
SKIP_PANE=""  # スキップなし（全ペイン監視）
WEBSOCKET_URL="ws://localhost:3000"

# 色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# ログディレクトリ作成
mkdir -p "${SCRIPT_DIR}/logs"

# ログ出力関数
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    echo -e "${timestamp} [${level}] ${message}" | tee -a "${LOG_FILE}"
}

log_info() { log "INFO" "$1"; }
log_warn() { log "WARN" "$1"; }
log_error() { log "ERROR" "$1"; }
log_owl() { log "🦉OWL" "$1"; }

# ヘルプ表示
show_help() {
    echo -e "${MAGENTA}🦉 目利きフクロウ監視スクリプト${NC}"
    echo ""
    echo "使い方: $0 [オプション]"
    echo ""
    echo "オプション:"
    echo "  --daemon    バックグラウンドで実行"
    echo "  --stop      デーモン停止"
    echo "  --status    デーモン状態確認"
    echo "  -h, --help  このヘルプを表示"
    echo ""
    echo "監視対象: queue/reports/*.yaml"
    echo "レビュー結果: 各YAMLに owl_review セクションを追記"
}

# デーモン停止
stop_daemon() {
    if [ -f "${PID_FILE}" ]; then
        PID=$(cat "${PID_FILE}")
        if kill -0 "${PID}" 2>/dev/null; then
            log_info "フクロウ停止中... (PID: ${PID})"
            kill "${PID}"
            rm -f "${PID_FILE}"
            echo -e "${GREEN}🦉 フクロウは眠りについたホー${NC}"
        else
            log_warn "PIDファイルはあるが、プロセスが存在しない"
            rm -f "${PID_FILE}"
        fi
    else
        echo -e "${YELLOW}フクロウは動いていないホー${NC}"
    fi
}

# デーモン状態確認
check_status() {
    if [ -f "${PID_FILE}" ]; then
        PID=$(cat "${PID_FILE}")
        if kill -0 "${PID}" 2>/dev/null; then
            echo -e "${GREEN}🦉 フクロウは監視中ホー (PID: ${PID})${NC}"
            return 0
        else
            echo -e "${YELLOW}🦉 フクロウは眠っているホー（PIDファイル残存）${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}🦉 フクロウは眠っているホー${NC}"
        return 1
    fi
}

# Codexが利用可能か確認
check_codex() {
    if ! command -v codex &> /dev/null; then
        log_error "codex コマンドが見つからないホー"
        echo -e "${RED}❌ codex CLI がインストールされていないホー${NC}"
        echo "   インストール: npm install -g @openai/codex"
        exit 1
    fi
    log_info "codex CLI 確認OK"
}

# 成果物パスを報告YAMLから抽出
extract_artifact_path() {
    local report_file="$1"

    # 成果物パスを探す（複数のパターンに対応）
    local artifact_path=""

    # パターン1: artifact_path フィールド
    artifact_path=$(grep -E "^artifact_path:|^  artifact_path:" "$report_file" 2>/dev/null | head -1 | sed 's/.*: *//' | tr -d '"' | tr -d "'")

    # パターン2: 成果物リスト内のパス
    if [ -z "$artifact_path" ]; then
        artifact_path=$(grep -E "^\s*- .*\.(js|ts|py|go|rs|java|css|html)$" "$report_file" 2>/dev/null | head -1 | sed 's/.*- *//' | tr -d '"')
    fi

    # パターン3: output/ 配下のパス
    if [ -z "$artifact_path" ]; then
        artifact_path=$(grep -oE "/home/edgesakura/git/[^[:space:]\"']+/(output|src|lib)/[^[:space:]\"']*" "$report_file" 2>/dev/null | head -1)
    fi

    # パスが見つからない場合はディレクトリを推測
    if [ -z "$artifact_path" ]; then
        # タスクIDからプロジェクトを推測
        if grep -q "chat-app" "$report_file" 2>/dev/null; then
            artifact_path="/home/edgesakura/neko-pm/output/chat-app"
        elif grep -q "marp-agent" "$report_file" 2>/dev/null; then
            artifact_path="/home/edgesakura/git/marp-agent"
        else
            artifact_path="/home/edgesakura/neko-pm"
        fi
    fi

    # ファイルの場合はディレクトリを取得
    if [ -f "$artifact_path" ]; then
        artifact_path=$(dirname "$artifact_path")
    fi

    echo "$artifact_path"
}

# タスク種別を判定（レビュー必要かどうか）
should_review() {
    local report_file="$1"

    # 既にレビュー済みならスキップ
    if grep -q "^owl_review:" "$report_file" 2>/dev/null; then
        return 1
    fi

    # ドキュメント作成タスクはスキップ
    if grep -qE "type:.*documentation|type:.*docs" "$report_file" 2>/dev/null; then
        log_info "ドキュメントタスクはスキップするホー: $(basename "$report_file")"
        return 1
    fi

    # コード変更を含むタスクはレビュー
    if grep -qE "\.(js|ts|py|go|rs|java|jsx|tsx)$" "$report_file" 2>/dev/null; then
        return 0
    fi

    # feature-development, bugfix タイプはレビュー
    if grep -qE "type:.*(feature|bugfix|enhancement|refactor)" "$report_file" 2>/dev/null; then
        return 0
    fi

    # デフォルトはレビュー
    return 0
}

# Codexでレビュー実行
run_codex_review() {
    local artifact_path="$1"
    local report_file="$2"

    log_owl "レビュー開始: ${artifact_path}"

    # レビュープロンプト
    local prompt="git diff ${REVIEW_RANGE} の変更について、以下の観点でコードレビューを実施してホー：
1. セキュリティ（入力バリデーション、認証、機密情報）
2. コード品質（重複、複雑さ、命名）
3. エラーハンドリング
4. パフォーマンス

問題があれば重要度（HIGH/MEDIUM/LOW）と具体的な箇所を指摘してホー。
問題がなければ「問題なしホー」と報告してホー。"

    # Codex実行（タイムアウト60秒）
    local review_result
    if review_result=$(timeout 120 codex exec --full-auto --sandbox read-only --cd "$artifact_path" "$prompt" 2>&1); then
        log_owl "レビュー完了"
        echo "$review_result"
    else
        log_error "Codex実行エラー"
        echo "レビュー実行エラー: タイムアウトまたは実行失敗ホー"
    fi
}

# レビュー結果をYAMLに追記
append_review_result() {
    local report_file="$1"
    local review_result="$2"

    # HIGH問題の数をカウント
    local high_count=$(echo "$review_result" | grep -ci "HIGH" | tr -d '\n' || echo "0")
    local medium_count=$(echo "$review_result" | grep -ci "MEDIUM" | tr -d '\n' || echo "0")
    local low_count=$(echo "$review_result" | grep -ci "LOW" | tr -d '\n' || echo "0")

    # ステータス判定
    local status="passed"
    local gate_result="✅ APPROVED"
    if [ "$high_count" -gt 0 ]; then
        status="blocked"
        gate_result="❌ BLOCKED (HIGH issues found)"
    elif [ "$medium_count" -gt 0 ]; then
        status="warning"
        gate_result="⚠️ WARNING (MEDIUM issues found)"
    fi

    # YAMLに追記
    cat >> "$report_file" << EOF

# ============================================================
# 🦉 目利きフクロウ自動レビュー結果
# ============================================================
owl_review:
  timestamp: "$(date '+%Y-%m-%dT%H:%M:%S')"
  status: "${status}"
  gate_result: "${gate_result}"
  issues:
    high: ${high_count}
    medium: ${medium_count}
    low: ${low_count}
  review_result: |
$(echo "$review_result" | sed 's/^/    /')
EOF

    log_owl "レビュー結果追記完了: ${status} (H:${high_count}/M:${medium_count}/L:${low_count})"

    # HIGH問題があれば番猫に警告
    if [ "$high_count" -gt 0 ]; then
        notify_guard_cat "$report_file" "$high_count"
    fi
}

# 番猫に警告通知
notify_guard_cat() {
    local report_file="$1"
    local high_count="$2"

    log_warn "HIGH問題検出！番猫に通知するホー"

    # send-keys で番猫に通知（2回ルール）
    if tmux has-session -t neko:workers 2>/dev/null; then
        local message="🦉 フクロウ警告ホー！$(basename "$report_file") にHIGH問題が${high_count}件あるホー！確認してホー！"
        tmux send-keys -t neko:workers.0 "$message" ""
        sleep 1
        tmux send-keys -t neko:workers.0 Enter
        log_info "番猫に通知送信完了"
    else
        log_warn "番猫ペインが見つからない - 通知スキップ"
    fi
}

# ============================================================
# 承認監視機能
# ============================================================

# 承認プロンプトを検出
check_approval_prompt() {
    local pane="$1"
    local capture_output="$2"

    # 承認プロンプトのパターン
    if echo "$capture_output" | grep -qE "(Allow (Bash|Read|Edit|Write|Glob|Grep|Task|WebFetch|WebSearch).*\?|\? \(y/n\)|\[y/n\]|Do you want to proceed\?)"; then
        return 0  # 承認プロンプトあり
    else
        return 1  # 承認プロンプトなし
    fi
}

# シェルメタ文字を含むかチェック（コマンド注入防止）
contains_shell_metachar() {
    local input="$1"
    # セミコロン、&&、||、バッククォート、$()、パイプ を検出
    if [[ "$input" =~ [\;\&\|\`] ]] || [[ "$input" =~ \$\( ]]; then
        return 0  # メタ文字あり
    fi
    return 1  # メタ文字なし
}

# コマンドが自動承認すべきか判断
should_auto_approve() {
    local capture_output="$1"

    # ============================================================
    # STEP 1: シェルメタ文字チェック（コマンド注入防止）
    # ============================================================
    # 連結コマンド（; && || ` $()）を含む場合は即拒否
    if contains_shell_metachar "$capture_output"; then
        log_warn "シェルメタ文字検出！拒否ホー"
        return 1  # 拒否
    fi

    # ============================================================
    # STEP 2: 明確な危険パターン拒否
    # ============================================================
    # 削除系・破壊的コマンドは絶対拒否
    if echo "$capture_output" | grep -qE "(rm -rf|rm -r|rmdir|delete|DELETE|DROP|TRUNCATE|git push|git reset --hard|--force|sudo|curl.*\|.*bash|wget.*\|.*sh|eval|exec)"; then
        return 1  # 拒否
    fi

    # ============================================================
    # STEP 3: Claude Code ツール別判定（旧形式: "Allow XXX"）
    # ============================================================
    # 安全なツール（Read, Edit, Write, etc）は自動承認
    if echo "$capture_output" | grep -qE "Allow (Read|Edit|Write|Glob|Grep|Task|WebFetch|WebSearch)"; then
        return 0  # 承認
    fi

    # ============================================================
    # STEP 3b: Claude Code ツール別判定（新形式: "Do you want to proceed?"）
    # ============================================================
    # 新形式: "XXX file" や "XXX command" でツールを検出
    if echo "$capture_output" | grep -q "Do you want to proceed?"; then
        # Read/Edit/Write/Glob/Grep 等の安全なツールは自動承認
        if echo "$capture_output" | grep -qE "(Read|Edit|Write|Glob|Grep) (file|1 file|[0-9]+ files)"; then
            log_owl "新形式: 安全なファイル操作を検出 → 承認"
            return 0  # 承認
        fi
        # Reading X files 形式
        if echo "$capture_output" | grep -qE "Reading [0-9]+ files"; then
            log_owl "新形式: ファイル読み取りを検出 → 承認"
            return 0  # 承認
        fi
    fi

    # ============================================================
    # STEP 4: Bash コマンドの厳密な検証（旧形式）
    # ============================================================
    if echo "$capture_output" | grep -q "Allow Bash"; then
        # コマンド部分を抽出（Allow Bash: の後の部分）
        local cmd=$(echo "$capture_output" | grep -oE "Allow Bash.*" | sed 's/Allow Bash[^:]*: *//' | head -1)

        # 安全なコマンドパターン（正規表現で厳密にマッチ）
        # npm: install, run, test, build, ci のみ許可
        if [[ "$cmd" =~ ^npm\ (install|run|test|build|ci|start|audit)($|\ ) ]]; then
            return 0  # 承認
        fi

        # node: ファイル実行のみ許可
        if [[ "$cmd" =~ ^node\ [a-zA-Z0-9_./-]+\.m?js($|\ ) ]]; then
            return 0  # 承認
        fi

        # git: 安全なサブコマンドのみ許可
        if [[ "$cmd" =~ ^git\ (status|diff|log|branch|add|commit|fetch|pull|stash|show|ls-files)($|\ ) ]]; then
            return 0  # 承認
        fi

        # ファイル操作: 読み取り系のみ許可
        if [[ "$cmd" =~ ^(cat|ls|head|tail|grep|find|pwd|date|wc)($|\ ) ]]; then
            return 0  # 承認
        fi

        # ディレクトリ作成: mkdir のみ許可
        if [[ "$cmd" =~ ^mkdir($|\ ) ]]; then
            return 0  # 承認
        fi

        # tmux: send-keys, list-panes, capture-pane のみ許可
        if [[ "$cmd" =~ ^tmux\ (send-keys|list-panes|capture-pane|list-sessions|has-session)($|\ ) ]]; then
            return 0  # 承認
        fi

        # codex/gemini: CLIツール許可
        if [[ "$cmd" =~ ^(codex|gemini)\ (exec|review|skills)(\ |$) ]]; then
            return 0  # 承認
        fi

        # shellcheck: 静的解析は許可
        if [[ "$cmd" =~ ^shellcheck($|\ ) ]]; then
            return 0  # 承認
        fi

        # 上記に該当しないBashコマンドは拒否
        log_warn "未許可のBashコマンド: ${cmd}"
        return 1  # 拒否
    fi

    # ============================================================
    # STEP 4b: Bash コマンドの厳密な検証（新形式: "Bash command"）
    # ============================================================
    if echo "$capture_output" | grep -q "Bash command"; then
        # コマンド部分を抽出（Bash command の次の行）
        local cmd=$(echo "$capture_output" | grep -A1 "Bash command" | tail -1 | sed 's/^[[:space:]]*//')
        log_owl "新形式Bash検出: ${cmd}"

        # 安全なコマンドパターン（STEP 4と同じロジック）
        # npm: install, run, test, build, ci のみ許可
        if [[ "$cmd" =~ ^npm\ (install|run|test|build|ci|start|audit)($|\ ) ]]; then
            return 0  # 承認
        fi

        # node: ファイル実行のみ許可
        if [[ "$cmd" =~ ^node\ [a-zA-Z0-9_./-]+\.m?js($|\ ) ]]; then
            return 0  # 承認
        fi

        # git: 安全なサブコマンドのみ許可
        if [[ "$cmd" =~ ^git\ (status|diff|log|branch|add|commit|fetch|pull|stash|show|ls-files)($|\ ) ]]; then
            return 0  # 承認
        fi

        # ファイル操作: 読み取り系のみ許可
        if [[ "$cmd" =~ ^(cat|ls|head|tail|grep|find|pwd|date|wc|echo)($|\ ) ]]; then
            return 0  # 承認
        fi

        # ディレクトリ作成: mkdir のみ許可
        if [[ "$cmd" =~ ^mkdir($|\ ) ]]; then
            return 0  # 承認
        fi

        # pip: install のみ許可
        if [[ "$cmd" =~ ^pip3?\ install($|\ ) ]]; then
            return 0  # 承認
        fi

        # python: スクリプト実行許可
        if [[ "$cmd" =~ ^python3?\ [a-zA-Z0-9_./-]+\.py($|\ ) ]]; then
            return 0  # 承認
        fi

        # tmux: send-keys, list-panes, capture-pane のみ許可
        if [[ "$cmd" =~ ^tmux\ (send-keys|list-panes|capture-pane|list-sessions|has-session)($|\ ) ]]; then
            return 0  # 承認
        fi

        # codex/gemini: CLIツール許可
        if [[ "$cmd" =~ ^(codex|gemini)\ (exec|review|skills)(\ |$) ]]; then
            return 0  # 承認
        fi

        # shellcheck: 静的解析は許可
        if [[ "$cmd" =~ ^shellcheck($|\ ) ]]; then
            return 0  # 承認
        fi

        # 上記に該当しないBashコマンドは拒否
        log_warn "新形式: 未許可のBashコマンド: ${cmd}"
        return 1  # 拒否
    fi

    return 1  # デフォルトは拒否
}

# 承認ログに記録
log_approval() {
    local pane="$1"
    local decision="$2"
    local command="$3"
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")

    echo "[${timestamp}] [${pane}] [${decision}] ${command}" >> "${APPROVAL_LOG}"
}

# WebSocket経由で通知
notify_websocket() {
    local pane="$1"
    local command="$2"
    local timestamp="$3"

    # wscatが利用可能かチェック
    if command -v wscat &> /dev/null; then
        local payload="{\"type\":\"approval_alert\",\"pane\":\"${pane}\",\"command\":\"${command}\",\"timestamp\":\"${timestamp}\"}"
        echo "$payload" | wscat -c "${WEBSOCKET_URL}" --no-color 2>/dev/null &
    else
        log_warn "wscat not found - WebSocket notification skipped"
    fi
}

# 承認/拒否を送信（2回ルール厳守）
send_approval() {
    local pane="$1"
    local decision="$2"  # "y" or "n"
    local command="$3"

    log_owl "承認送信: ${pane} -> ${decision}"

    # 数字選択式の場合は "1" を送信
    local response="$decision"
    local capture_output=$(tmux capture-pane -t "$pane" -p | tail -20)
    if echo "$capture_output" | grep -q "❯ 1. Yes"; then
        response="1"
        log_owl "数字選択式検出: 1 を送信"
    fi

    # 1回目: y/n または 1 を送信（Enter なし）
    tmux send-keys -t "$pane" "$response"
    sleep 1

    # 2回目: Enter を送信
    tmux send-keys -t "$pane" Enter

    # ログに記録
    local decision_text
    if [ "$decision" = "y" ]; then
        decision_text="APPROVED"
    else
        decision_text="REJECTED"
        # 拒否した場合は番猫に通知
        if [ "$pane" != "neko:workers.0" ]; then
            tmux send-keys -t neko:workers.0 "🦉 警告ホー！${pane}で危険なコマンドを検出して拒否したホー：${command}"
            sleep 1
            tmux send-keys -t neko:workers.0 Enter
        fi
        # WebSocket通知
        notify_websocket "$pane" "$command" "$(date '+%Y-%m-%dT%H:%M:%S')"
    fi

    log_approval "$pane" "$decision_text" "$command"
}

# 承認監視ループ
watch_approvals() {
    log_owl "承認監視開始ホー！"
    echo -e "${GREEN}🦉 承認監視開始ホー！${NC}"
    echo -e "   監視対象ペイン: ${CYAN}${PANES_TO_MONITOR[@]}${NC}"
    echo -e "   ポーリング間隔: ${APPROVAL_POLL_INTERVAL}秒"
    echo ""

    while true; do
        for pane in "${PANES_TO_MONITOR[@]}"; do
            # ペインが存在するかチェック
            if ! tmux list-panes -t "$pane" &>/dev/null; then
                continue
            fi

            # ペインの出力をキャプチャ
            local capture_output=$(tmux capture-pane -t "$pane" -p | tail -10)

            # 承認プロンプトを検出
            if check_approval_prompt "$pane" "$capture_output"; then
                log_owl "承認プロンプト検出: ${pane}"

                # コマンド内容を抽出
                local command=$(echo "$capture_output" | grep -oE "Allow (Bash|Read|Edit|Write|Glob|Grep|Task|WebFetch|WebSearch).*" | head -1)

                # コマンドが取得できなかった場合は capture_output の最後の行を使う
                if [ -z "$command" ]; then
                    command=$(echo "$capture_output" | tail -3 | tr '\n' ' ' | head -c 150)
                    log_owl "コマンド抽出失敗、プロンプト内容を記録: ${command}"
                fi

                # 自動承認すべきか判断
                if should_auto_approve "$capture_output"; then
                    log_owl "自動承認: ${command}"
                    send_approval "$pane" "y" "$command"
                else
                    log_warn "危険なコマンド検出！拒否: ${command}"
                    send_approval "$pane" "n" "$command"
                fi

                # 連続検出を防ぐため少し待機
                sleep 2
            fi
        done

        sleep "${APPROVAL_POLL_INTERVAL}"
    done
}

# メイン監視ループ
watch_reports() {
    log_owl "監視開始ホー！ディレクトリ: ${REPORTS_DIR}"
    echo -e "${GREEN}🦉 目利きフクロウ、監視開始ホー！${NC}"
    echo -e "   監視対象: ${CYAN}${REPORTS_DIR}${NC}"
    echo -e "   ポーリング間隔: ${POLL_INTERVAL}秒"
    echo ""

    while true; do
        # reports ディレクトリが存在しなければ作成
        mkdir -p "${REPORTS_DIR}"

        # 新規報告ファイルをチェック
        for report_file in "${REPORTS_DIR}"/*.yaml "${REPORTS_DIR}"/*.yml; do
            # ファイルが存在しない場合はスキップ
            [ -f "$report_file" ] || continue

            # レビュー対象かチェック
            if should_review "$report_file"; then
                log_info "新規報告検出: $(basename "$report_file")"

                # 成果物パスを抽出
                artifact_path=$(extract_artifact_path "$report_file")

                if [ -d "$artifact_path" ] || [ -f "$artifact_path" ]; then
                    # Codexでレビュー実行
                    review_result=$(run_codex_review "$artifact_path" "$report_file")

                    # 結果をYAMLに追記
                    append_review_result "$report_file" "$review_result"
                else
                    log_warn "成果物パスが見つからない: ${artifact_path}"
                    # スキップマーカーを追記
                    echo "" >> "$report_file"
                    echo "owl_review:" >> "$report_file"
                    echo "  status: skipped" >> "$report_file"
                    echo "  reason: 成果物パスが見つからないホー" >> "$report_file"
                fi
            fi
        done

        sleep "${POLL_INTERVAL}"
    done
}

# 並列監視実行
run_parallel_watch() {
    log_owl "並列監視モード起動ホー！"

    # レポート監視をバックグラウンド起動
    watch_reports &
    local reports_pid=$!

    # 承認監視をバックグラウンド起動
    watch_approvals &
    local approvals_pid=$!

    log_info "レポート監視PID: ${reports_pid}"
    log_info "承認監視PID: ${approvals_pid}"

    # 両方の監視を待機
    wait $reports_pid $approvals_pid
}

# デーモンモードで実行
run_daemon() {
    if [ -f "${PID_FILE}" ]; then
        PID=$(cat "${PID_FILE}")
        if kill -0 "${PID}" 2>/dev/null; then
            echo -e "${YELLOW}🦉 フクロウは既に監視中ホー (PID: ${PID})${NC}"
            exit 1
        fi
    fi

    log_info "デーモンモードで起動"
    nohup "$0" > "${LOG_FILE}" 2>&1 &
    echo $! > "${PID_FILE}"
    echo -e "${GREEN}🦉 フクロウ、バックグラウンドで監視開始ホー (PID: $!)${NC}"
    echo -e "   ログ: ${LOG_FILE}"
    echo -e "   承認ログ: ${APPROVAL_LOG}"
}

# メイン処理
main() {
    case "${1:-}" in
        --daemon)
            check_codex
            run_daemon
            ;;
        --stop)
            stop_daemon
            ;;
        --status)
            check_status
            ;;
        -h|--help)
            show_help
            ;;
        --reports-only)
            # レポート監視のみ
            check_codex
            watch_reports
            ;;
        --approvals-only)
            # 承認監視のみ
            watch_approvals
            ;;
        *)
            # デフォルトは並列監視
            check_codex
            run_parallel_watch
            ;;
    esac
}

main "$@"
