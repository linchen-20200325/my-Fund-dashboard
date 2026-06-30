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

# v19.254 Phase 4-B1: GitHub-style dark theme palette(UI component CSS 跨檔重複 226+ 處)
GH_BG_PRIMARY: str = "#0d1117"     # GitHub bg primary(主背景)
GH_BG_CARD: str = "#161b22"        # GitHub card bg(卡片底)
GH_BG_HOVER: str = "#21262d"       # GitHub bg hover(滑鼠 hover)
GH_BORDER: str = "#30363d"         # GitHub border(1px solid)
GH_FG_PRIMARY: str = "#e6edf3"     # GitHub fg primary(主文字白)
GH_FG_SECONDARY: str = "#c9d1d9"   # GitHub fg secondary(次文字)
GH_FG_MUTED: str = "#8b949e"       # GitHub fg muted(注意:跟 TRAFFIC_NEUTRAL #888888 不同色)
STREAMLIT_BG: str = "#0e1117"      # Streamlit default body bg(1 hex off from GH_BG_PRIMARY)

# v19.255 Phase 4-B5: Dark accent BG palette(semi-transparent danger / warning / success panel bg)
BG_DARK_NAVY_1: str = "#0d1b2a"    # navy dark(最常用,~11 處)
BG_DARK_NAVY_2: str = "#1a2845"    # navy mid
BG_DARK_NAVY_3: str = "#1e2a3a"    # navy deep
BG_DARK_NAVY_4: str = "#1a1f2e"    # navy alt
BG_DARK_RED_1: str = "#2a0a0a"     # danger dark
BG_DARK_RED_2: str = "#1a0606"     # danger deep
BG_DARK_RED_3: str = "#3a0a0a"     # danger bright(σ+布林雙確認賣 badge bg,2 處)
BG_DARK_AMBER_1: str = "#2a1f00"   # warning dark
BG_DARK_AMBER_2: str = "#1a1200"   # warning deep
BG_DARK_AMBER_3: str = "#1a1500"   # warning alert(σ 小跌小買 alert bg,2 處)
BG_DARK_GREEN_1: str = "#0a1a0a"   # success dark
BG_DARK_GREEN_2: str = "#061a06"   # success deep(持倉紅綠燈/momentum/gradient,3 處)
BG_DARK_GREEN_3: str = "#0a3a1a"   # success bright(σ+布林雙確認買 badge bg,2 處)

# v19.256 Phase 4-B4: Material extended palette(component accent colors)
MD_BLUE_300: str = "#64b5f6"       # Material Blue 300(info accent,最常用)
MD_BLUE_500: str = "#2196f3"       # Material Blue 500
MD_GREEN_A200: str = "#69f0ae"     # Material Green A200(success accent)
MD_GREEN_A400: str = "#00e676"     # Material Green A400
MD_DEEP_ORANGE_400: str = "#ff7043" # Material Deep Orange 400(warning accent)
MD_AMBER_300: str = "#ffd54f"      # Material Amber 300
MD_ORANGE_300: str = "#ffb74d"     # Material Orange 300
MD_ORANGE_A200: str = "#ffab40"    # Material Orange A200(Z-Score 警示 |Z|≥1.5,3 處跨 2 檔)
MD_PURPLE_500: str = "#9c27b0"     # Material Purple 500

# v19.259 Item 2 long-tail 高頻收口(各 ≥8 處跨多檔)
INFO_BLUE: str = "#58a6ff"         # GitHub-style info blue(hold signal / link / border,17 處)
WARN_AMBER: str = "#ffa726"        # 賣訊號 amber(sell1 / 接近警示,8 處)
CAUTION_YELLOW: str = "#ffeb3b"    # C 評等 / 中性偏好 caution(8 處)

# v19.257 Phase 4-B3: 灰調漸層 SSOT(short hex,by intensity 命名避免 false semantic 分群)
GRAY_44: str = "#444"              # very dark gray
GRAY_55: str = "#555"              # dark gray
GRAY_66: str = "#666"              # medium dark gray
GRAY_AA: str = "#aaa"              # medium gray
GRAY_BB: str = "#bbb"              # medium light gray
GRAY_CC: str = "#ccc"              # light gray
WHITE: str = "#fff"                # pure white

# 同義對應
TRAFFIC_EMOJI: tuple[str, str, str, str] = ("🟢", "🟡", "🔴", "⬜")
TRAFFIC_HEX: tuple[str, str, str, str] = (
    TRAFFIC_GREEN, TRAFFIC_YELLOW, TRAFFIC_RED, TRAFFIC_NEUTRAL,
)
