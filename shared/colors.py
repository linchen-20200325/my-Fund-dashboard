"""K4b-4b：traffic-light + Material 顏色 SSOT（跨 repo 共用）。

鏡像 Stock 端 shared/colors.py 8 hex 常數（5 TRAFFIC + 3 MATERIAL），
透過 scripts/sync_to_stock.sh 單向同步至 my-stock-dashboard/shared/colors.py，
確保兩 repo 配色一致。

設計：純常數模組，零 import 依賴；caller 用 `from shared.colors import MATERIAL_*`。

對外 API：
- TRAFFIC_GREEN / TRAFFIC_YELLOW / TRAFFIC_ORANGE / TRAFFIC_RED：Tailwind-style 五色
- TRAFFIC_NEUTRAL：⬜ 灰（unknown / disabled）
- MATERIAL_GREEN / RED / ORANGE：Material Design colors（macro_card sparkline 用）
- TRAFFIC_EMOJI / TRAFFIC_HEX：emoji 與 hex 對應元組
"""
from __future__ import annotations

# Tailwind-style traffic light（v19.68 統一升級，原 GitHub-style #3fb950/#d29922/#f85149/#6e7681）
TRAFFIC_GREEN: str = "#22c55e"
TRAFFIC_YELLOW: str = "#eab308"
TRAFFIC_ORANGE: str = "#fb923c"  # 中間色（services 估值/事件曆 4 級色階用）
TRAFFIC_RED: str = "#ef4444"
TRAFFIC_NEUTRAL: str = "#888888"  # 灰，未知/disabled

# Material Design colors（macro_card.py sparkline / z-score 用）
MATERIAL_GREEN: str = "#00c853"   # 健康成長
MATERIAL_RED: str = "#f44336"     # 吃本金
MATERIAL_ORANGE: str = "#ff9800"  # 邊緣健康

# 同義對應
TRAFFIC_EMOJI: tuple[str, str, str, str] = ("🟢", "🟡", "🔴", "⬜")
TRAFFIC_HEX: tuple[str, str, str, str] = (
    TRAFFIC_GREEN, TRAFFIC_YELLOW, TRAFFIC_RED, TRAFFIC_NEUTRAL,
)


