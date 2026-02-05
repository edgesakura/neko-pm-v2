#!/bin/bash
# scripts/verify-checklist.sh
#
# チェックリスト自動検証ツール
# 指定ファイルのチェックリスト項目を抽出し、
# 未チェック項目があれば警告する
#
# Usage: ./scripts/verify-checklist.sh <file_path>
# Example: ./scripts/verify-checklist.sh instructions/kitten.md
#
# Exit codes:
#   0: All checked
#   1: Unchecked items found or Error

TARGET_FILE="$1"

if [ -z "$TARGET_FILE" ]; then
  echo "Usage: $0 <file_path>"
  exit 1
fi

if [ ! -f "$TARGET_FILE" ]; then
  echo "Error: File not found: $TARGET_FILE"
  exit 1
fi

# 未チェック項目を抽出（- [ ] で始まる行）
UNCHECKED=$(grep -E '^\s*- \[ \]' "$TARGET_FILE")

if [ -n "$UNCHECKED" ]; then
  echo "⚠️  未チェック項目が見つかりました:"
  echo "$UNCHECKED"
  exit 1
else
  echo "✅ 全てのチェックリスト項目が完了しています"
  exit 0
fi
