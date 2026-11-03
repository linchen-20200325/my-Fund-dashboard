# -*- coding: utf-8 -*-
"""Shell 資料狀態 adapter：既有 🌍 頁 view model 的各項資料狀態 → `ShellStatus`（BL-0536 Shell 批）。

- **只讀既有 health／provenance**：`MarketPageModel.statuses`（五條主要序列的取得狀態與取得時間，來源是 `market_view`），
  不自己取數、不 import services／infra、不計算任何領域值；本檔只做計數與取最晚的取得時間。
- 取得時間必須是帶時區的 ISO 字串才參與比較；不帶時區或無法解析的不猜、不參與（全部都不可用 → None）。
- 更新資料（refresh）：本批**沒有**安全可接的正式 refresh 流程（見 `docs/v2/80` 第 17.3 節盤點），一律 `refresh_available=False`
  並帶 `refresh_not_wired`；不自創 refresh pipeline。
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from ui_v3.adapters.market_page import REASON_NOT_CONFIGURED
from ui_v3.viewmodels.common import STATUS_FAILED, STATUS_OK
from ui_v3.viewmodels.market_page import MarketPageModel
from ui_v3.viewmodels.shell import LEVEL_NONE, LEVEL_OK, LEVEL_PARTIAL, REFRESH_NOT_WIRED, ShellStatus

__all__ = ("latest_fetched_at", "from_market_model")


def _aware(stamp: str) -> Optional[datetime]:
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return moment if moment.tzinfo is not None else None


def latest_fetched_at(stamps: Iterable[Optional[str]]) -> Optional[str]:
    """帶時區的取得時間中最晚的那一個（原字串）；沒有任何可比較的 → None。"""
    best, best_moment = None, None
    for stamp in stamps:
        if not stamp:
            continue
        moment = _aware(stamp)
        if moment is not None and (best_moment is None or moment > best_moment):
            best, best_moment = stamp, moment
    return best


def from_market_model(model: MarketPageModel) -> ShellStatus:
    rows = model.statuses
    ok = sum(1 for r in rows if r.status == STATUS_OK)
    # 「尚未設定」不是取數失敗（44 之十二其二第 1 條）：不計入取數失敗項數，只算沒取得。
    failed = sum(1 for r in rows if r.status == STATUS_FAILED and r.reason_code != REASON_NOT_CONFIGURED)
    level = LEVEL_OK if ok == len(rows) else LEVEL_NONE if ok == 0 else LEVEL_PARTIAL
    return ShellStatus(level, ok, len(rows), failed, latest_fetched_at(r.fetched_at for r in rows),
                       False, REFRESH_NOT_WIRED)
