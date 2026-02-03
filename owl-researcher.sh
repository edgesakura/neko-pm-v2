#!/bin/bash
# ============================================================
# 調査フクロウスクリプト (owl-researcher.sh)
# ============================================================
#
# 役割: Codexを活用した技術調査の実行
# ツール: Codex CLI (OpenAI)
#
# 機能:
#   1. 調査テーマに基づいてCodexに調査依頼
#   2. 調査タイプ別のプロンプト生成
#   3. 結果をMarkdownファイルとして保存
#   4. 調査ログの記録
#
# 使い方:
#   ./owl-researcher.sh "調査テーマ" [対象ディレクトリ]
#   ./owl-researcher.sh --type analyze [対象ディレクトリ]
#   ./owl-researcher.sh --type debug "バグ内容" [対象ディレクトリ]
#   ./owl-researcher.sh --type security [対象ディレクトリ]
#
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESEARCH_DIR="${SCRIPT_DIR}/reports/research"
LOG_FILE="${SCRIPT_DIR}/logs/owl-researcher.log"

# 色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# ログディレクトリと調査ディレクトリ作成
mkdir -p "${SCRIPT_DIR}/logs"
mkdir -p "${RESEARCH_DIR}"

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
    echo -e "${MAGENTA}🦉 調査フクロウ${NC}"
    echo ""
    echo "使い方: $0 [オプション] <調査テーマ> [対象ディレクトリ]"
    echo ""
    echo "引数:"
    echo "  <調査テーマ>        調査したいテーマ（必須、--type が analyze/security の場合は不要）"
    echo "  [対象ディレクトリ]  調査対象のプロジェクトディレクトリ（デフォルト: カレントディレクトリ）"
    echo ""
    echo "オプション:"
    echo "  --type <type>       調査タイプを指定"
    echo "                        research  - 技術的調査（デフォルト）"
    echo "                        analyze   - アーキテクチャ分析"
    echo "                        debug     - バグ原因調査"
    echo "                        security  - セキュリティ監査"
    echo "  -h, --help          このヘルプを表示"
    echo ""
    echo "例:"
    echo "  $0 \"neko-pmの構造調査\" /home/edgesakura/git/neko-pm"
    echo "  $0 --type analyze /home/edgesakura/git/neko-pm"
    echo "  $0 --type debug \"写真アップロードでフリーズする\" /path/to/project"
    echo "  $0 --type security /path/to/project"
    echo ""
    echo "結果保存先: ${RESEARCH_DIR}/research_<timestamp>_<topic>.md"
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

# 調査タイプ別プロンプト生成
generate_prompt() {
    local type="$1"
    local topic="$2"

    case "$type" in
        research)
            echo "以下のテーマについて技術的な調査を実施して: ${topic}"
            ;;
        analyze)
            echo "プロジェクト全体のアーキテクチャ分析を実施して"
            ;;
        debug)
            echo "以下のバグの原因を調査して: ${topic}"
            ;;
        security)
            echo "セキュリティ監査を実施して、脆弱性を検出して"
            ;;
        *)
            log_error "不明な調査タイプ: ${type}"
            echo "research, analyze, debug, security のいずれかを指定してください"
            exit 1
            ;;
    esac
}

# トピック名をファイル名用にサニタイズ
sanitize_topic() {
    local topic="$1"
    # スペースをアンダースコアに、特殊文字を削除
    echo "$topic" | tr ' ' '_' | tr -cd '[:alnum:]_-' | cut -c1-50
}

# Codexで調査実行
run_research() {
    local type="$1"
    local topic="$2"
    local project_dir="$3"

    log_owl "調査開始: タイプ=${type}, テーマ=${topic}, ディレクトリ=${project_dir}"

    # プロンプト生成
    local prompt=$(generate_prompt "$type" "$topic")
    log_info "プロンプト: ${prompt}"

    # 結果保存ファイル名生成
    local timestamp=$(date "+%Y%m%d-%H%M%S")
    local sanitized_topic=$(sanitize_topic "$topic")
    local output_file="${RESEARCH_DIR}/research_${timestamp}_${sanitized_topic}.md"

    log_info "結果保存先: ${output_file}"

    # ヘッダー書き込み
    cat > "$output_file" << EOF
# 🦉 調査フクロウ調査レポート

## 調査情報

- **調査タイプ**: ${type}
- **調査テーマ**: ${topic}
- **対象ディレクトリ**: ${project_dir}
- **調査日時**: $(date "+%Y-%m-%d %H:%M:%S")
- **実行コマンド**: codex exec --full-auto --sandbox read-only --cd "${project_dir}" "${prompt}"

---

## 調査結果

EOF

    # Codex実行
    echo -e "${CYAN}🦉 Codexに調査を依頼中...${NC}"
    local research_result
    if research_result=$(timeout 180 codex exec --full-auto --sandbox read-only --cd "$project_dir" "$prompt" 2>&1); then
        log_owl "調査完了"
        echo "$research_result" >> "$output_file"

        # フッター追記
        cat >> "$output_file" << EOF

---

## 調査完了

調査は正常に完了しましたホー。

EOF

        echo -e "${GREEN}✅ 調査完了ホー！${NC}"
        echo -e "   結果: ${CYAN}${output_file}${NC}"

    else
        log_error "Codex実行エラー"
        echo "## ⚠️ 調査エラー" >> "$output_file"
        echo "" >> "$output_file"
        echo "調査実行エラー: タイムアウトまたは実行失敗ホー" >> "$output_file"
        echo "" >> "$output_file"
        echo '```' >> "$output_file"
        echo "$research_result" >> "$output_file"
        echo '```' >> "$output_file"

        echo -e "${RED}❌ 調査失敗ホー${NC}"
        echo -e "   詳細: ${output_file}"
        exit 1
    fi

    log_owl "調査ログ記録完了: ${output_file}"
}

# 引数パース
parse_args() {
    local type="research"
    local topic=""
    local project_dir="$(pwd)"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --type)
                type="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                if [ -z "$topic" ]; then
                    topic="$1"
                elif [ -z "$project_dir" ] || [ "$project_dir" = "$(pwd)" ]; then
                    project_dir="$1"
                else
                    log_error "不明な引数: $1"
                    show_help
                    exit 1
                fi
                shift
                ;;
        esac
    done

    # analyze と security はトピック不要
    if [ "$type" != "analyze" ] && [ "$type" != "security" ]; then
        if [ -z "$topic" ]; then
            log_error "調査テーマが指定されていません"
            show_help
            exit 1
        fi
    else
        # analyze/security の場合、topicが空ならデフォルト値
        if [ -z "$topic" ]; then
            if [ "$type" = "analyze" ]; then
                topic="architecture_analysis"
            else
                topic="security_audit"
            fi
        fi
    fi

    # ディレクトリ存在チェック
    if [ ! -d "$project_dir" ]; then
        log_error "ディレクトリが存在しません: ${project_dir}"
        exit 1
    fi

    echo "$type|$topic|$project_dir"
}

# メイン処理
main() {
    # 引数が何もなければヘルプ表示
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi

    # --help オプションを先にチェック
    for arg in "$@"; do
        if [ "$arg" = "-h" ] || [ "$arg" = "--help" ]; then
            show_help
            exit 0
        fi
    done

    # Codex確認
    check_codex

    # 引数パース
    local args=$(parse_args "$@")
    IFS='|' read -r type topic project_dir <<< "$args"

    # 調査実行
    run_research "$type" "$topic" "$project_dir"
}

main "$@"
