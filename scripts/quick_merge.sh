#!/usr/bin/env bash
# scripts/quick_merge.sh — 跳過 PR 直接 squash-merge 進 main
#
# 用途（CLAUDE.md §4 例外）：
#   - 文件 / 註解 / typo
#   - STATE.md 同步
#   - 版本字串 bump
#   - 不需 CI gate 的小改
#
# 用法：
#   ./scripts/quick_merge.sh "commit message"
#       → squash 當前分支進 main、push、刪本地+遠端分支
#
# 大功能變更仍走 PR：gh pr create + gh pr merge --squash --delete-branch

set -euo pipefail

MSG="${1:-}"
if [[ -z "$MSG" ]]; then
    echo "❌ 用法：$0 \"commit message\"" >&2
    exit 1
fi

BRANCH="$(git branch --show-current)"
if [[ "$BRANCH" == "main" || "$BRANCH" == "master" ]]; then
    echo "❌ 已在 $BRANCH，不需要 merge" >&2
    exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
    echo "❌ working tree 不乾淨，先 commit 或 stash" >&2
    git status --short
    exit 1
fi

echo "🔍 當前分支：$BRANCH → 將 squash 進 main"
echo

git fetch origin main
git checkout main
git pull --ff-only origin main
git merge --squash "$BRANCH"
git commit -m "$MSG"
git push origin main

echo
echo "🧹 清理分支 $BRANCH"
git branch -D "$BRANCH" || true
git push origin --delete "$BRANCH" 2>/dev/null || echo "  (遠端分支不存在，略過)"

echo
echo "✅ 完成：$MSG → main"
git log --oneline -3
