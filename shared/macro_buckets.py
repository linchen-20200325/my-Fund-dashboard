"""shared/macro_buckets.py — 總經五桶 × 危險門檻 SSOT 註冊表 (v19.144)

CLAUDE.md §3.3 反捏造 / §8.2 L0 Shared:
本模組是「Fund 總經五桶」(長期/中期/短線/拐點/新聞)危險門檻系統的**單一真相**,
同時被三個 surface 消費,避免閾值散落、漂移:

    compute_*_summary (L2 services / ui helpers)  ← 桶燈號 / 四時域 bar
    chart add_danger_hlines (L3 UI helpers)       ← 圖表標準線(Phase B)
    SPEC.md §16 危險門檻表 (docs)                  ← 參考文件

【為何是 L0】純常數 + 純 classify 函式,零 I/O、零 L1+ 依賴(§8.2 硬規則)。
`repositories.macro_repository.MACRO_THRESHOLDS` 位於 L1,L0 不得 import → 重疊值
在此鏡像並由 `test_macro_buckets.py` 斷言相等(drift-safe,CI 擋漂移),非腦補。

【與既有 4-horizon bar 的關係】
- `ui/helpers/macro_beginner_view.py::compute_four_horizon_summary` 仍是 4 桶,
  不破壞既有 production 體驗。本檔提供**第 5 桶(新聞)+ SSOT 危險門檻表 + 圖表
  標準線**所需的 schema,Phase B/C 漸進擴充。
- F-GRAY-4 v19.80 audit 釐清:`MACRO_THRESHOLDS` 與 inline scoring **語意不同源**。
  本 registry 為「stoplight 紅黃綠燈」schema(單一視覺判讀),**不**取代既有 SCORE_RULES /
  四時域 scoring,只負責顯示用 danger level 分類。

【門檻來源透明度】每條 DangerSpec.source 標註:
    "SSOT:<位置>"  → 有官方 / 既有常數背書(鏡像或 import)
    "DESIGN"       → 本桶系統設計之警示線(無單一官方源,為 UI 判讀方便而訂,
                     §1 不適用:此為 UI 門檻 config 非偽造資料輸出,已具名 + 文件化)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ── 既有 L0 SSOT 常數(直接 import,不重複宣告)──
from shared.signal_thresholds import (
    SAHM_RECESSION_THRESHOLD,         # 0.5 — 失業率 3MA - 過去 12M 最低 ≥ 0.5pp
    CFNAI_RECESSION_THRESHOLD,        # -0.7 — Chicago Fed 領先指標衰退門檻
)
from shared.colors import (
    MATERIAL_GREEN as _C_GREEN,
    MATERIAL_ORANGE as _C_YELLOW,
    MATERIAL_RED as _C_RED,
)

# ── 燈號 → 色 / emoji / 嚴重度排序(bar + chart + SPEC 共用)──
LEVEL_COLOR = {"green": _C_GREEN, "yellow": _C_YELLOW,
               "red": _C_RED, "gray": "#6e7681"}
LEVEL_EMOJI = {"green": "🟢", "yellow": "🟡", "red": "🔴", "gray": "⬜"}
LEVEL_RANK = {"green": 1, "yellow": 2, "red": 3}   # gray 不參與 worst 計算

# ════════════════════════════════════════════════════════════════
# 鏡像 macro_repository.MACRO_THRESHOLDS(L1,L0 不可 import)— drift test 守護
#   test_macro_buckets.py::test_mirror_matches_macro_repository 斷言下列 == 源
# ════════════════════════════════════════════════════════════════
_VIX_YELLOW = 22.0   # 對齊 MACRO_THRESHOLDS['VIX']['yellow_above']
_VIX_RED    = 30.0   # 對齊 MACRO_THRESHOLDS['VIX']['red_above']
_CPI_YELLOW = 3.5    # 對齊 MACRO_THRESHOLDS['CPI']['yellow_above']
_CPI_RED    = 4.0    # 對齊 MACRO_THRESHOLDS['CPI']['red_above']
# F-GRAY-4 v19.179 PR-3: PMI stoplight SSOT(shared/macro_thresholds_v2.PMI_THRESHOLDS)
from shared.macro_thresholds_v2 import PMI_THRESHOLDS as _PMI_THR_V2
_PMI_YELLOW = _PMI_THR_V2["stoplight"]["yellow_below"]  # 50.0(<50 收縮)
_PMI_RED    = _PMI_THR_V2["stoplight"]["red_below"]     # 46.0(<46 嚴重)
_HY_YELLOW  = 4.0    # 對齊 MACRO_THRESHOLDS['HY_SPREAD']['yellow_below']
_HY_RED     = 6.0    # 對齊 MACRO_THRESHOLDS['HY_SPREAD']['red_above']
_US10Y_YELLOW = 4.5  # 對齊 MACRO_THRESHOLDS['US10Y']['yellow_above']
_US10Y_RED  = 5.0    # 對齊 MACRO_THRESHOLDS['US10Y']['red_above']
_M2_RED     = 0.0    # 對齊 MACRO_THRESHOLDS['M2_YOY']['red_below']
_M2_GREEN   = 5.0    # 對齊 MACRO_THRESHOLDS['M2_YOY']['green_above']

# ════════════════════════════════════════════════════════════════
# 桶 meta:5 桶順序鎖定(對齊 Fund 既有 4-horizon + 新增 📰 新聞為第 5 桶)
# ════════════════════════════════════════════════════════════════
BUCKET_ORDER = ["long", "mid", "short", "inflection", "news"]
BUCKET_META = {
    "long":       {"emoji": "🌳", "title": "長期",     "sub": "結構 / 景氣位階"},
    "mid":        {"emoji": "📈", "title": "中期",     "sub": "景氣循環 3-12 月"},
    "short":      {"emoji": "🎯", "title": "短線",     "sub": "即時 risk-off"},
    "inflection": {"emoji": "⚠️", "title": "拐點",     "sub": "領先警報"},
    "news":       {"emoji": "📰", "title": "新聞",     "sub": "系統性風險掃描"},
}

# 各桶 × 燈號 → 狀態短語(bar 上的 1 句 label)
BUCKET_LEVEL_LABEL = {
    "long":       {"green": "結構健康", "yellow": "結構轉折", "red": "結構防禦",   "gray": "未載入"},
    "mid":        {"green": "循環健康", "yellow": "局部走弱", "red": "循環惡化",   "gray": "未載入"},
    "short":      {"green": "短線平靜", "yellow": "短線警戒", "red": "急殺風險",   "gray": "未載入"},
    "inflection": {"green": "拐點未現", "yellow": "拐點臨近", "red": "拐點鎖定",   "gray": "未載入"},
    "news":       {"green": "無系統風險", "yellow": "風險新聞", "red": "系統性警報", "gray": "未掃描"},
}

# 新聞桶:系統性風險命中「則數」→ 燈號(對齊 Stock v18.284)
NEWS_SYSTEMIC_YELLOW_COUNT = 1   # ≥1 則系統性新聞 → 🟡
NEWS_SYSTEMIC_RED_COUNT    = 2   # ≥2 則系統性新聞 → 🔴

# Macro 健康評分(0-10,services.macro_validation.aggregate_score 規範)
_MACRO_SCORE_HEALTHY_MIN = 6.0   # ≥6 結構健康
_MACRO_SCORE_DANGER_MAX  = 3.0   # <3 結構防禦


@dataclass(frozen=True)
class DangerSpec:
    """單一指標的危險門檻規格。chart hline / 桶燈號 / SPEC 表共用。"""
    key: str               # 取值 key
    label: str             # 顯示名
    bucket: str            # long / mid / short / inflection / news
    unit: str              # "", "%", "分", "則", "倍"
    direction: str         # high_bad | low_bad | band
    yellow: float          # 黃線(high_bad=上緣 / low_bad=下緣 / band=高側)
    red: float             # 紅線(同上)
    decimals: int = 1
    yellow_lo: Optional[float] = None   # band 低側黃線
    red_lo: Optional[float] = None      # band 低側紅線
    note: str = ""         # 業務語意
    source: str = ""       # 門檻來源(SSOT:... 或 DESIGN)


# ════════════════════════════════════════════════════════════════
# 危險門檻註冊表 — 五桶 × 指標
#   Fund 視角:基金投資判讀,以 US macro + global risk 為主(無 TW 籌碼桶,
#   既有 macro_beginner_view._PCR_PANIC_THRESHOLD 等保留作既有 4-horizon 用)。
# ════════════════════════════════════════════════════════════════
BUCKET_DANGER_SPECS: list[DangerSpec] = [
    # ── 🌳 長期:結構 / 景氣位階 ──
    DangerSpec("macro_score", "總經健康評分", "long", "/10", "low_bad",
               yellow=_MACRO_SCORE_HEALTHY_MIN, red=_MACRO_SCORE_DANGER_MAX, decimals=1,
               note="≥6 結構健康 / <3 結構防禦",
               source="SSOT:macro_validation.aggregate_score 分級慣例"),
    DangerSpec("m2_yoy", "M2 貨幣供給 YoY", "long", "%", "low_bad",
               yellow=_M2_GREEN, red=_M2_RED, decimals=1,
               note=">5% 寬鬆 / <0% 緊縮", source="SSOT:MACRO_THRESHOLDS.M2_YOY"),
    DangerSpec("fed_bs_yoy", "Fed 資產負債表 YoY", "long", "%", "low_bad",
               yellow=5.0, red=-5.0, decimals=1,
               note=">5% 擴表 / <-5% 縮表",
               source="SSOT:MACRO_THRESHOLDS.FED_BS_YOY"),

    # ── 📈 中期:景氣循環 ──
    DangerSpec("pmi", "ISM 製造業 PMI", "mid", "", "low_bad",
               yellow=_PMI_YELLOW, red=_PMI_RED, decimals=1,
               note="<50 收縮 / <46 嚴重", source="SSOT:MACRO_THRESHOLDS.PMI"),
    DangerSpec("cpi_yoy", "CPI YoY", "mid", "%", "high_bad",
               yellow=_CPI_YELLOW, red=_CPI_RED, decimals=1,
               note=">3.5% 通膨升溫 / >4% 嚴峻", source="SSOT:MACRO_THRESHOLDS.CPI"),
    DangerSpec("unemployment", "失業率", "mid", "%", "high_bad",
               yellow=4.5, red=6.0, decimals=1,
               note=">4.5% 警戒 / >6% 衰退",
               source="SSOT:macro_validation.SCORE_RULES.UNEMPLOYMENT"),
    DangerSpec("us10y", "US10Y 殖利率", "mid", "%", "high_bad",
               yellow=_US10Y_YELLOW, red=_US10Y_RED, decimals=2,
               note=">4.5% 警戒 / >5% 緊縮",
               source="SSOT:MACRO_THRESHOLDS.US10Y"),
    DangerSpec("forward_pe", "Forward P/E (S&P 500)", "mid", "倍", "high_bad",
               yellow=19.5, red=22.5, decimals=1,  # PE_MEAN(16.5) + 1σ / +2σ
               note=">+1σ 偏貴 / >+2σ 過熱",
               source="SSOT:valuation.FORWARD_PE_MEAN(16.5)+σ(3.0)"),

    # ── 🎯 短線急殺:即時 risk-off ──
    DangerSpec("vix", "VIX 恐慌指數", "short", "", "high_bad",
               yellow=_VIX_YELLOW, red=_VIX_RED, decimals=1,
               note="≥22 警戒 / ≥30 危機",
               source="SSOT:MACRO_THRESHOLDS.VIX + macro_validation 預設"),
    DangerSpec("hy_spread", "HY 信用利差 OAS", "short", "%", "high_bad",
               yellow=_HY_YELLOW, red=_HY_RED, decimals=2,
               note="≥4% 警戒 / ≥6% 信用裂",
               source="SSOT:MACRO_THRESHOLDS.HY_SPREAD"),
    DangerSpec("move", "MOVE 債市波動", "short", "", "high_bad",
               yellow=100.0, red=120.0, decimals=0,
               note=">100 警戒 / >120 stress",
               source="DESIGN:對齊 macro_beginner_view._MOVE_WARNING"),
    DangerSpec("pcr", "Put/Call 比率", "short", "", "high_bad",
               yellow=1.0, red=1.5, decimals=2,
               note=">1.0 警戒 / >1.5 散戶恐慌",
               source="DESIGN:對齊 macro_beginner_view._PCR_PANIC"),

    # ── ⚠️ 拐點:領先警報 ──
    DangerSpec("sahm", "Sahm Rule", "inflection", "", "high_bad",
               yellow=0.3, red=float(SAHM_RECESSION_THRESHOLD), decimals=2,
               note=">0.3 接近觸發 / ≥0.5 衰退觸發",
               source="SSOT:SAHM_RECESSION_THRESHOLD(0.5)+DESIGN(0.3 警戒)"),
    DangerSpec("yield_10y2y", "10Y-2Y 殖利率差", "inflection", "%", "low_bad",
               yellow=0.5, red=0.0, decimals=2,
               note="<0.5 接近倒掛 / <0 倒掛",
               source="SSOT:MACRO_THRESHOLDS.YIELD_10Y2Y"),
    DangerSpec("yield_10y3m", "10Y-3M 殖利率差", "inflection", "%", "low_bad",
               yellow=0.5, red=0.0, decimals=2,
               note="<0.5 接近倒掛 / <0 倒掛",
               source="SSOT:MACRO_THRESHOLDS.YIELD_10Y3M"),
    DangerSpec("cfnai", "CFNAI 領先指標", "inflection", "", "low_bad",
               yellow=-0.35, red=float(CFNAI_RECESSION_THRESHOLD), decimals=2,
               note="<-0.35 走弱 / ≤-0.7 衰退",
               source="SSOT:CFNAI_RECESSION_THRESHOLD(-0.7)+DESIGN(-0.35 警戒)"),
    DangerSpec("sloos", "SLOOS 銀行收緊", "inflection", "%", "high_bad",
               yellow=30.0, red=50.0, decimals=1,
               note=">30% 信用條件收緊 / >50% 衰退級緊縮",
               source="DESIGN:對齊 macro_beginner_view._SLOOS_TIGHTENING(50)"),

    # ── 📰 新聞:系統性風險掃描 ──
    DangerSpec("news_systemic", "系統性風險新聞數", "news", "則", "high_bad",
               yellow=float(NEWS_SYSTEMIC_YELLOW_COUNT),
               red=float(NEWS_SYSTEMIC_RED_COUNT), decimals=0,
               note="≥1 則警戒 / ≥2 則紅(戰爭/倒閉/崩盤關鍵字命中)",
               source="DESIGN:命中則數規則(對齊 news_repository 既有 SYSTEMIC_RISK_KEYWORDS)"),
]

# 快速查表
SPECS_BY_KEY: dict[str, DangerSpec] = {s.key: s for s in BUCKET_DANGER_SPECS}
