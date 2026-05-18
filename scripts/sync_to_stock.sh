#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# sync_to_stock.sh — 把 fund 端的 shared 模組同步到 stock 端
# ──────────────────────────────────────────────────────────────────────
# 設計原則：
#   - 單向同步：canonical source = fund/shared/，stock 端為唯讀副本
#   - 只同步「render 共用模組」：macro_card.py + __init__.py
#   - 不同步 macro_card_edu.py（EDU 內容是 fund-side keys，stock 用自己的 EDU_GUIDE）
#   - 同步前先 SHA256 比對；不同才複製，避免無謂的 git 噪音
#   - 同步後在 stock 端的副本檔頭加上「DO NOT EDIT」警告
# ──────────────────────────────────────────────────────────────────────
# 使用：
#   cd my-fund-dashboard
#   bash scripts/sync_to_stock.sh
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)/shared"
DST_DIR="$(cd "$(dirname "$0")/../../my-stock-dashboard" && pwd)/shared"

# 要同步的檔案清單（fund-side EDU 不同步）
SYNC_FILES=("__init__.py" "macro_card.py")

# 0. 健康檢查
if [[ ! -d "$SRC_DIR" ]]; then
  echo "❌ Source not found: $SRC_DIR"; exit 1
fi
if [[ ! -d "$(dirname "$DST_DIR")" ]]; then
  echo "❌ Stock repo not found at $(dirname "$DST_DIR")"; exit 1
fi
mkdir -p "$DST_DIR"

# 1. 逐檔比對 + 複製
CHANGED=0
for f in "${SYNC_FILES[@]}"; do
  src="$SRC_DIR/$f"
  dst="$DST_DIR/$f"
  if [[ ! -f "$src" ]]; then
    echo "⚠️  Missing in source: $f (skipped)"; continue
  fi
  src_hash=$(sha256sum "$src" | awk '{print $1}')
  dst_hash=""
  if [[ -f "$dst" ]]; then
    dst_hash=$(sha256sum "$dst" | awk '{print $1}')
  fi
  if [[ "$src_hash" == "$dst_hash" ]]; then
    echo "✓  $f (already in sync)"
  else
    cp "$src" "$dst"
    echo "→  $f  ($(wc -l < "$dst") lines copied)"
    CHANGED=$((CHANGED + 1))
  fi
done

# 2. 在 stock 端加 DO NOT EDIT 警告（只在第一次或檔頭沒有警告時）
WARN_LINE='# ⚠️  AUTO-SYNCED FROM my-fund-dashboard/shared/ — DO NOT EDIT HERE.'
for f in "${SYNC_FILES[@]}"; do
  dst="$DST_DIR/$f"
  if [[ -f "$dst" ]] && ! head -1 "$dst" | grep -q "AUTO-SYNCED"; then
    tmp=$(mktemp)
    {
      echo "$WARN_LINE"
      echo "#    Edit fund repo's shared/$f, then run scripts/sync_to_stock.sh."
      echo
      cat "$dst"
    } > "$tmp"
    mv "$tmp" "$dst"
    echo "🛡  prepended DO NOT EDIT warning to $f"
  fi
done

# 3. 摘要
echo ""
if [[ "$CHANGED" -eq 0 ]]; then
  echo "✅ Sync complete (no changes)."
else
  echo "✅ Sync complete ($CHANGED file(s) updated). Now in stock repo:"
  echo "   git add shared/  &&  git commit -m 'sync: pull shared/macro_card from fund'"
fi
