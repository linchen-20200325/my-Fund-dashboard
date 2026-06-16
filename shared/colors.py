"""K4b-4b：traffic-light + Material 顏色 SSOT（跨 repo 共用）。

鏡像 Stock 端 shared/colors.py 7 hex 常數（4 TRAFFIC + 3 MATERIAL），
透過 scripts/sync_to_stock.sh 單向同步至 my-stock-dashboard/shared/colors.py，
確保兩 repo 配色一致。

設計：純常數模組，零 import 依賴；caller 用 `from shared.colors import MATERIAL_*`。

對外 API：
- TRAFFIC_GREEN / TRAFFIC_YELLOW / TRAFFIC_RED：GitHub-style 主用三色
- TRAFFIC_NEUTRAL：⬜ 灰（unknown / disabled）
- MATERIAL_GREEN / RED / ORANGE：Material Design colors（macro_card sparkline 用）
- TRAFFIC_EMOJI / TRAFFIC_HEX：emoji 與 hex 對應元組
"""
from __future__ import annotations

# GitHub-style traffic light
TRAFFIC_GREEN: str = "#3fb950"
TRAFFIC_YELLOW: str = "#d29922"
TRAFFIC_RED: str = "#f85149"
TRAFFIC_NEUTRAL: str = "#6e7681"  # 灰，未知/disabled

# Material Design colors（macro_card.py sparkline / z-score 用）
MATERIAL_GREEN: str = "#00c853"   # 健康成長
MATERIAL_RED: str = "#f44336"     # 吃本金
MATERIAL_ORANGE: str = "#ff9800"  # 邊緣健康

# 同義對應
TRAFFIC_EMOJI: tuple[str, str, str, str] = ("🟢", "🟡", "🔴", "⬜")
TRAFFIC_HEX: tuple[str, str, str, str] = (
    TRAFFIC_GREEN, TRAFFIC_YELLOW, TRAFFIC_RED, TRAFFIC_NEUTRAL,
)


def emoji_to_hex(emoji: str) -> str:
    """🟢/🟡/🔴/⬜ → traffic-light hex；未知 emoji → TRAFFIC_NEUTRAL。"""
    _m = {"🟢": TRAFFIC_GREEN, "🟡": TRAFFIC_YELLOW,
          "🔴": TRAFFIC_RED, "⬜": TRAFFIC_NEUTRAL}
    return _m.get(emoji, TRAFFIC_NEUTRAL)
