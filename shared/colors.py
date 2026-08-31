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
BG_DARK_GREEN_GAUGE: str = "#0a2a0a"  # success mid(gauge safe zone tuple,3 處同檔)
BG_DARK_PURPLE_1: str = "#1a0a2a"  # purple dark(大跌大買訊號 bg,1 處 single-use)

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
# v19.405 稽核收口:淡紅 accent(Material Red A100)。原以 inline hex 散落 4 處
# (services/macro/composite_score.composite_verdict「悲觀」/ services/macro/explain.py
#  同名函式 / services/macro/us_indicators._nfp_tier「偏冷」/ ui/tab1_macro_midcycle
#  警示 chip 前景色)。語意 = 「負面但未到最嚴重」的第二層紅,比 MATERIAL_RED 淡。
MD_RED_A100: str = "#ff8a80"       # Material Red A100(次級警示 / 悲觀 / 偏冷)

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
# v19.274 Phase 2 收尾:策略3 訊號 chip 近黑底(3 處跨 tab2/tab3,原 inline "#111")
CHIP_BG_NEAR_BLACK: str = "#111"   # near-black chip bg(phase-signal chip / alloc fallback)

# ── 三態顏色語意角色 SSOT（2026-08-31，客戶四大鐵律第 3 條「三態顏色分離」）──────
# 客戶拍板的三態：
#   未載入／沒點過 ＝ 灰色說明 ／ 系統真出錯 ＝ 紅色警示 ／ 業務上的壞消息 ＝ **業務色**。
# 2026-08-31 前，業務警訊卡（`ui/helpers/render_state.business_alert`）用的是
# `MATERIAL_RED`，與系統紅同屬「一眼看去就是那個紅」，**只靠形狀（卡片 vs 錯誤框）分辨** ——
# 本組拆的就是這一點。`MATERIAL_RED` 其餘用途（吃本金／z-score／sparkline，34 檔）**未動**。
#
# ⚠️ 下面兩個值是**一組、依底色擇一**，不是「深色版／淺色版隨便挑」。
#    實測 WCAG 對比（`scripts` 無此工具，數字由本次 PR 就地計算，公式 WCAG 2.x relative luminance）：
#      #96124a on #ffffff = 8.46:1 ✅ ／ on 業務卡底 #2a0a0a = 2.17:1 ❌（幾乎看不見）
#      #f294b6 on #2a0a0a = 8.45:1 ✅ ／ on #ffffff        = 2.17:1 ❌（幾乎看不見）
#    **用錯邊的代價不是「不夠好看」，是字直接讀不到。**
#    `tests/test_tricolor_colour_provenance.py::test_r1_*` 以對比公式把這件事機器化，
#    不靠這段註解自律。
BUSINESS_ALERT_ON_LIGHT: str = "#96124a"   # 深莓紅：**淺**色底上的業務警訊前景
BUSINESS_ALERT_ON_DARK: str = "#f294b6"    # 亮莓紅：**深**色底上的業務警訊前景

# ⚠️⚠️ **`BUSINESS_ALERT_ON_LIGHT` 今天沒有 production 消費者 —— 這是刻意保留，不是漏刪。**
#    **總管 2026-08-31 拍板：留在 SSOT，不刪；但必須就地標明現況。** 以下即該標明。
#
#    **現況（實測）**：`.streamlit/config.toml` 釘死 `base = "dark"` → App 只有深色底，
#    因此只有 `ON_DARK` 會被畫出來。
#
#    ⚠️ **引用清單更正（2026-08-31，有意識的更正，不是漏刪；決策者：本實作組，稽核指出）**
#    舊表述寫 ~~「全 repo 對 `ON_LIGHT` 的引用**只有**本檔的定義與
#    `tests/test_tricolor_colour_provenance.py` 的守衛」~~ —— **漏了第三處。**
#    **實測**（`grep -rn 'BUSINESS_ALERT_ON_LIGHT' --include='*.py' --include='*.md' .`）
#    命中 **3 個檔**：
#      1. **本檔** —— 定義（`BUSINESS_ALERT_ON_LIGHT: str = "#96124a"`）＋本段註解；
#      2. `tests/test_tricolor_colour_provenance.py` —— 守衛（`BUSINESS_TOKEN_NAMES`、
#         `test_r0_*`、`test_r1_the_light_surface_pair_is_kept_usable_for_a_light_surface`）；
#      3. **`ui/helpers/render_state.py`** —— **模組 docstring 內的散文**
#         （「淺色底的配對值 `BUSINESS_ALERT_ON_LIGHT`（`#96124a`）已進 SSOT 但 production 用不到」）。
#
#    ⚠️ **第三處是散文，不是功能引用** —— 它不是 `import`、不是 `from ... import`、
#    也不會被求值成任何輸出，**刪掉本常數不會讓那一行報錯**。
#    **兩邊理由並陳**：舊表述想講的事**仍然成立** ——「本常數沒有 production 消費者」
#    這個結論**不受第三處影響**（散文不是消費者）；**被權衡掉的是它的措辭**：
#    「引用**只有**兩處」是一句**可被一條 grep 推翻的全稱句**，而它偏偏是錯的。
#    **新表述勝出的理由**：後人若拿舊句去 grep 覆核，會發現對不上，
#    進而懷疑整段保留裁決的可信度 —— **一個錯的計數會拖垮它旁邊所有正確的結論。**
#    （對照本檔既有的 `115 條 / 4 條` 那則自我更正：同一個病，同一份檔案內第二次。）
#
#    **為什麼留（兩個理由，缺一不可）**：
#      1. **它是「一組兩個值」的另一半，不是獨立常數。** 上面那張對比表就是它存在的意義 ——
#         `#f294b6` 在白底只有 2.17:1、`#96124a` 在業務卡底也只有 2.17:1。**留著配對值
#         ＋ 用對比測試釘住**，是防止有人把 `ON_DARK` 畫到淺底上的最直接手段；
#         **只留一半，SSOT 會變成一個會誤導人的半套。**
#      2. 客戶是把兩個值**一起**給的，刪一半等於片面改掉客戶給的規格。
#
#    ⛔ **給未來的 Garbage Collection（`CLAUDE.md §-1.5.1c` v3 §01-2「用不到即清理」）**：
#    本常數**符合「無 production caller」的表面特徵，但不是孤兒**，理由如上。
#    **刪它之前必須先確認「本 repo 已確定不需要主題感知」** —— 那是一個尚未成立的前提
#    （主題感知機制已另立待辦，本批不做：`base="dark"` 現況下沒有需求觸發）。
#    ✅ **實際護欄不靠這段註解**：刪掉本常數會讓
#    `tests/test_tricolor_colour_provenance.py` 的 **4 條**測試當場轉紅，第一條是
#    `test_r0_both_role_tokens_exist_even_the_one_with_no_caller`，它的失敗訊息
#    直接把上面這些理由印出來 ——**GC 刪不掉它而不出聲，而且會被告知為什麼。**
#    （2026-08-31 實測，見該批 PR 突變表 M5。⚠️ 初稿在此寫「3 條」是**沒查證就寫的**，
#     實跑是 4 條；且在補 `test_r0` 之前實際會噴 **115 條**——其中 112 條是 R2 對每個
#     UI 檔各報一次同樣的 AttributeError，**那種級聯會把真正的原因埋掉**，
#     故一併把 R2 改為容錯查值、由 `test_r0` 專責報這件事。）
#
#    ⛔ **`@media (prefers-color-scheme: light)` 這條路已評估並否決，不要再試**：
#    那個 media query 反映的是**作業系統偏好**，**不是** Streamlit 主題。
#    使用者 OS 設淺色、App 仍是深色底 → 會挑到 `ON_LIGHT` 畫在 `#2a0a0a` 上
#    ＝ **2.17:1，比現況更糟**。本 repo 唯一的深淺切換在
#    `ui/helpers/dividend_calendar_render.py`，那是**獨立匯出 HTML**（供 PNG 匯出）的私有
#    `:root{--…}` CSS，讀不到本模組，也套不進 `st.markdown` 片段 —— **不是可用的機制。**

# 同義對應
TRAFFIC_EMOJI: tuple[str, str, str, str] = ("🟢", "🟡", "🔴", "⬜")
TRAFFIC_HEX: tuple[str, str, str, str] = (
    TRAFFIC_GREEN, TRAFFIC_YELLOW, TRAFFIC_RED, TRAFFIC_NEUTRAL,
)
