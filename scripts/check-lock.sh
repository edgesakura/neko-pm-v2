#!/bin/bash
# scripts/check-lock.sh
#
# ファイルロック確認スクリプト
# nawabari.md の「🔒 ファイルロック」セクションをパースして、
# 指定ファイルがロック中かどうかを判定する
#
# Usage: ./scripts/check-lock.sh <file_path>
# Example: ./scripts/check-lock.sh src/auth.ts
#
# Exit codes:
#   0: UNLOCKED
#   1: LOCKED or Error

TARGET_FILE="$1"

if [ -z "$TARGET_FILE" ]; then
  echo "Usage: $0 <file_path>"
  exit 1
fi

# nawabari.md の「🔒 ファイルロック」セクションを抽出
LOCK_SECTION=$(sed -n '/^## 🔒 ファイルロック/,/^## /p' nawabari.md | grep -v '^##')

# 対象ファイルがロック中か確認
if echo "$LOCK_SECTION" | grep -q "| $TARGET_FILE |"; then
  OWNER=$(echo "$LOCK_SECTION" | grep "| $TARGET_FILE |" | awk -F'|' '{print $3}' | xargs)
  echo "LOCKED by $OWNER"
  exit 1
else
  echo "UNLOCKED"
  exit 0
fi
