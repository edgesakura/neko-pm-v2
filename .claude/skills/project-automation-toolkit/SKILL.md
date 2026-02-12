# project-automation-toolkit

プロジェクト固有の自動化スクリプト生成パターン。Phase Dで培った知見をまとめたスキルにゃ。

## 使用タイミング
- プロジェクト固有の自動化スクリプトを作成する時
- ロック機構やチェックリスト検証を実装する時
- Bash スクリプトのベストプラクティスを適用する時

## 設計原則

1. **単一責任の原則**: 1スクリプト = 1責務
2. **標準Exit code**: 0=成功, 1=失敗
3. **明確なエラーメッセージ**: ユーザーに何が起きたか伝える
4. **実行権限**: chmod +x で実行可能にする
5. **ドキュメント**: Usage コメントを必ず付ける

## パターン1: ファイルロック確認スクリプト

**ユースケース**: nawabari.md の「🔒 ファイルロック」セクションを解析し、指定ファイルがロック中かどうかを判定

**実装例**: scripts/check-lock.sh

```bash
#!/usr/bin/env bash
# Usage: ./check-lock.sh <file_path>
# Exit: 0=UNLOCKED, 1=LOCKED

set -euo pipefail

FILE_PATH="${1:-}"
NAWABARI="nawabari.md"

if [[ -z "$FILE_PATH" ]]; then
  echo "Error: File path required" >&2
  echo "Usage: $0 <file_path>" >&2
  exit 2
fi

if [[ ! -f "$NAWABARI" ]]; then
  echo "Error: nawabari.md not found" >&2
  exit 2
fi

# ロックセクションを抽出してパース
if grep -A 20 "^## 🔒 ファイルロック" "$NAWABARI" | grep -q "| $FILE_PATH |"; then
  LOCKER=$(grep -A 20 "^## 🔒 ファイルロック" "$NAWABARI" | grep "| $FILE_PATH |" | awk -F'|' '{print $3}' | xargs)
  echo "🔒 LOCKED by $LOCKER"
  exit 1
else
  echo "✅ UNLOCKED"
  exit 0
fi
```

**ポイント**:
- `set -euo pipefail` でエラー時即座に終了
- 引数チェックでUsageを表示
- Exit code で結果を返す（スクリプト連携しやすい）

## パターン2: チェックリスト検証スクリプト

**ユースケース**: Markdownファイル内のチェックリスト（- [ ]）を検証し、未チェック項目があれば警告

**実装例**: scripts/verify-checklist.sh

```bash
#!/usr/bin/env bash
# Usage: ./verify-checklist.sh <file_path>
# Exit: 0=All checked, 1=Unchecked items

set -euo pipefail

FILE_PATH="${1:-}"

if [[ -z "$FILE_PATH" ]]; then
  echo "Error: File path required" >&2
  echo "Usage: $0 <file_path>" >&2
  exit 2
fi

if [[ ! -f "$FILE_PATH" ]]; then
  echo "Error: File not found: $FILE_PATH" >&2
  exit 2
fi

# 未チェック項目を検索
UNCHECKED=$(grep -c "^- \[ \]" "$FILE_PATH" || true)

if [[ "$UNCHECKED" -gt 0 ]]; then
  echo "⚠️  $UNCHECKED unchecked items found in $FILE_PATH"
  grep -n "^- \[ \]" "$FILE_PATH" | head -5
  exit 1
else
  echo "✅ All items checked in $FILE_PATH"
  exit 0
fi
```

**ポイント**:
- `|| true` でgrepが見つからなくてもエラーにならない
- `-n` で行番号を表示（デバッグしやすい）
- Exit code で結果を返す

## パターン3: プロジェクト状態確認スクリプト

**ユースケース**: プロジェクト全体の状態を一括確認

```bash
#!/usr/bin/env bash
# Usage: ./check-project-status.sh

set -euo pipefail

echo "🔍 Checking project status..."

# Git status
echo ""
echo "📂 Git status:"
git status --short

# Pending tasks
echo ""
echo "📋 Pending tasks:"
grep -c "status: pending" queue/boss_to_guard.yaml || echo "0"

# File locks
echo ""
echo "🔒 File locks:"
if grep -A 20 "^## 🔒 ファイルロック" nawabari.md | grep -q "| - | - | - |"; then
  echo "No locks"
else
  grep -A 20 "^## 🔒 ファイルロック" nawabari.md | grep "|" | tail -n +3
fi

# Worker status
echo ""
echo "🐱 Worker status:"
grep -A 5 "^## 子猫状態" nawabari.md | grep "|" | tail -n +3

echo ""
echo "✅ Status check complete"
```

## パターン4: 自動クリーンアップスクリプト

**ユースケース**: 古いレポートファイルや一時ファイルを削除

```bash
#!/usr/bin/env bash
# Usage: ./cleanup-old-reports.sh [days]
# Default: 7 days

set -euo pipefail

DAYS="${1:-7}"
REPORTS_DIR="queue/reports"

echo "🧹 Cleaning up reports older than $DAYS days..."

# 7日以上古いファイルを削除
find "$REPORTS_DIR" -name "*.yaml" -type f -mtime +"$DAYS" -delete

echo "✅ Cleanup complete"
```

## Exit Code 規約

| Code | 意味 | 使用例 |
|------|------|--------|
| 0 | 成功 | チェックOK、処理成功 |
| 1 | 失敗（予期された） | チェックNG、ロック中 |
| 2 | 使用方法エラー | 引数不足、ファイル不存在 |

## エラーハンドリング

```bash
# 基本テンプレート
set -euo pipefail  # エラー時即座に終了

# 引数チェック
if [[ -z "${VAR:-}" ]]; then
  echo "Error: VAR is required" >&2
  exit 2
fi

# ファイル存在チェック
if [[ ! -f "$FILE" ]]; then
  echo "Error: File not found: $FILE" >&2
  exit 2
fi

# コマンド実行（失敗しても続行）
RESULT=$(command || true)
```

## チェックリスト

スクリプト作成時に以下を確認せよ：

- [ ] shebang（#!/usr/bin/env bash）を付与
- [ ] set -euo pipefail でエラーハンドリング
- [ ] Usage コメントを記載
- [ ] 引数チェック実装
- [ ] ファイル存在チェック実装
- [ ] 標準Exit code（0=成功, 1=失敗, 2=引数エラー）
- [ ] エラーメッセージは標準エラー出力（>&2）
- [ ] chmod +x で実行権限付与
- [ ] ドライラン機能実装（オプション）
- [ ] ログ出力（オプション）

## 参考資料

- Bash Best Practices
- ShellCheck（静的解析ツール）
