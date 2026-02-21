#!/bin/bash
# tmux-send.sh - tmux ペインに確実にプロンプトを送信するヘルパー
#
# 問題: tmux send-keys でテキスト送信後に Enter が飲み込まれることがある
# 原因: Codex CLI / Gemini CLI が raw terminal モードで動作しており、
#       テキスト送信直後の Enter がアプリに到達する前に消失する
# 解決: テキスト送信後に短いディレイを入れてから Enter を送信
#
# 使い方:
#   ./scripts/tmux-send.sh <target> <text>
#   ./scripts/tmux-send.sh neko-pm:tanuki "プロンプト内容"
#   ./scripts/tmux-send.sh neko-pm:scouts.0 "質問内容"
#
# Enter のみ送信:
#   ./scripts/tmux-send.sh <target>
#   ./scripts/tmux-send.sh neko-pm:tanuki

set -e

TARGET="${1:?Usage: tmux-send.sh <target> [text]}"
TEXT="${2:-}"

if [ -n "$TEXT" ]; then
    # テキスト送信
    tmux send-keys -t "$TARGET" "$TEXT"
    # ディレイ（raw terminal モードのアプリがテキストを処理する時間を確保）
    sleep 0.3
fi

# Enter 送信
tmux send-keys -t "$TARGET" Enter
