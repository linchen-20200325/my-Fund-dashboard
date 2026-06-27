"""v19.169 Multi-purpose macro threshold SSOT — F-GRAY-4 (SPEC §16.2).

問題:單一 stoplight dict (`MACRO_THRESHOLDS`) 無法表達同一指標在不同 site
的多種用途 (signal classification / score function / portfolio advisor /
beginner panic etc.) — 機械式 swap 會把 4 種語意不同的 path 強塞同一 schema。

設計:per-indicator multi sub-dict by use case，各 site 改 import 對應子
dict，**不**強制統一閾值,但所有閾值集中在本檔 SSOT。

優先順序 (per SPEC §16.2 ROI 表):HY_SPREAD (最少語意,最低風險) → CPI → PMI。

NOT meant to unify thresholds across sites — only to colocate them.
"""
from __future__ import annotations


# ── HY_SPREAD (BAMLH0A0HYM2) — High Yield OAS, % ─────────────────────────
HY_SPREAD_THRESHOLDS = {
    "stoplight": {
        # repositories/macro_repository.py:198 MACRO_THRESHOLDS
        # macro_service.py:1116 inline > 6 check
        # ui/tab1_macro.py:60 _HY_WARN_THRESHOLD
        # ui/tab6_manual.py:1246 教學表 (4, 6)
        "green_below": 4.0,
        "yellow_below": 6.0,
        "red_above": 6.0,
    },
    "score_function": {
        # services/macro_validation.py:78 SCORE_RULES lambda
        # services/macro_score_calibration.py:54 _s_hy_spread
        "tight_below": 4.0,    # v < 4 → +2 (信用利差收斂,利多)
        "wide_above": 6.0,     # v > 6 → -2 (信用利差走闊,利空)
    },
    "portfolio_advisor": {
        # services/portfolio_service.py:342,345 投組風險建議
        # 注意:warn 閾值與 stoplight (4.0) 不同 — 投組建議更寬容
        "warn_above": 4.5,     # > 4.5 → 🟡 信用風險升高
        "risk_above": 6.0,     # > 6.0 → 🔴 避險情緒高
    },
    "beginner_panic": {
        # ui/helpers/macro_beginner_view.py:52-53
        # 注意:閾值與 stoplight 不同 — 新手介面更保守 (避免過早警示)
        "warn_above": 5.0,
        "panic_above": 8.0,
    },
}


# ── CPI_YOY (CPIAUCSL YoY) — US Consumer Price Index, % ─────────────────
# v19.178 F-GRAY-4 CPI harmonize per SPEC §16.2 ROI 第 2 順位
#
# **NOT** a single threshold across sites — colocated SSOT for 4 use cases:
#
# 1. stoplight (UI 三燈) — repositories/macro_repository.py:198 MACRO_THRESHOLDS
# 2. score_function (0-10 連續分數) — services/macro_validation.py:101 SCORE_RULES
# 3. inflection_detection (拐點訊號) — services/macro_service.py:208-210,253
# 4. regime_classification (4 級景氣) — services/macro_service.py:1447-1449
# 5. beginner_panic (教學警示) — ui/helpers/macro_beginner_view.py:315
#
# **不**重收 regime 4 級 zone(`CPI_YOY_IDEAL_MAX_PCT` 等已在
# shared/signal_thresholds.py W5-4 SSOT 化,本檔不重複定義避免飄移)。
CPI_YOY_THRESHOLDS = {
    "stoplight": {
        # repositories/macro_repository.py:198 MACRO_THRESHOLDS["CPI"]
        # green_band [1.5, 2.5],yellow_at 3.5,red_above 4.0
        "green_low": 1.5,
        "green_high": 2.5,
        "yellow_above": 3.5,
        "red_above": 4.0,
    },
    "score_function": {
        # services/macro_validation.py:101 SCORE_RULES lambda
        # 1 < v < 2.5 → +1 (理想)/ v > 4 → -1 (過熱)
        "ideal_low": 1.0,      # v > 1.0 開始計入理想區
        "ideal_high": 2.5,     # v < 2.5 通膨健康
        "elevated_above": 4.0, # v > 4.0 過熱扣分
    },
    "inflection_detection": {
        # services/macro_service.py:208-210 高位未降警示 + 回落多頭
        # services/macro_service.py:253 MK 黃金拐點(CPI 見頂 + Fed 降息)
        "warn_above": 4.0,      # > 4.0% 高位未降 警告
        "bull_low": 1.5,        # 1.5 <= v <= 3.0 回落合理多頭
        "bull_high": 3.0,
        "mk_golden_below": 3.5, # < 3.5 + 下降 + Fed 見頂 = MK 黃金拐點
    },
    "regime_classification": {
        # services/macro_service.py:1447-1449
        # PMI >= 52 且 CPI < 3.5 → 成長期;CPI >= 3.5 → 過熱期
        "overheat_above": 3.5,
    },
    "beginner_panic": {
        # ui/helpers/macro_beginner_view.py:315
        "overheat_above": 4.0,
    },
}


# ── PMI (NAPM / ISM Manufacturing PMI) — US, % ─────────────────────────
# v19.179 F-GRAY-4 PMI harmonize per SPEC §16.2 ROI 第 3 順位
# v19.180 docstring 升級:加經濟學註解 + 教學區
#
# ╔══════════════════════════════════════════════════════════════════════╗
# ║ 📚 經濟學教學 — PMI 雙枯榮線(50 教科書 / 52 真正枯榮線)            ║
# ╚══════════════════════════════════════════════════════════════════════╝
#
# PMI(Purchasing Managers' Index)是擴散指數(diffusion index):
#   PMI = (上升% × 1.0) + (持平% × 0.5) + (下降% × 0.0)
#
# **教科書枯榮線 = 50%**:字面意義,>50 代表「多數受訪企業認為較上月擴張」。
# 本檔多數 sub-dict(stoplight / score_function / inflection / growth_signal /
# alert / beginner_panic)用 50,因為這是公開教科書共識,UI 觸發容易解釋。
#
# **真正枯榮線 = 52%**(US,1990-2020 歷史校準):
#   產出缺口(output gap)= 實際增速 − 潛在增速
#   美國潛在增速 ≈ 2.0% YoY,對應 PMI ≈ 52.0
#   - PMI > 52 → 實際 > 潛在 → 產出缺口為正 → 真擴張
#   - PMI 50~52 → 字面擴張但實質低於潛在 → 灰色帶(實際在收縮中)
#   - PMI < 50 → 字面收縮(且必然低於潛在)→ 真衰退
#
# 為什麼 regime_classification 用 52?
#   `macro_service.py:1457-1461` 4 象限要分「成長期 vs 衰退期」,需區分
#   「字面擴張」與「實質擴張」— 用 52 才能把 50-52 灰色帶正確歸到衰退。
#   else 兜底為衰退是 **feature 不是 bug**(灰色帶 = 字面看似擴張但已轉弱)。
#
# 為什麼 stoplight 不一併升 52?
#   UI 觸發以「易解釋」優先,50 教科書線使用者一看就懂;52 真正枯榮線需要
#   產出缺口知識才能理解。雙線並存即為本 multi-dict SSOT 設計動機。
#
# Sanity filter [30, 70] 在 shared/signal_thresholds.PMI_VALID_MIN/MAX
# (data-quality,非 business),本檔不重複定義。
PMI_THRESHOLDS = {
    "stoplight": {
        # UI 三燈(教科書枯榮線 50)— shared/macro_buckets.py:58-59
        # 字面意義:>50 擴張、<50 收縮、<46 深度收縮
        "green_above": 50.0,
        "yellow_below": 50.0,
        "red_below": 46.0,
    },
    "score_function": {
        # macro 分數函數(教科書枯榮線 50)
        # services/macro_validation.py:102 SCORE_RULES["PMI"] lambda
        # services/macro_score_calibration.py:58 _s_pmi
        # 3 段:>= 50 → +2(擴張), [45,50) → -1(略弱), < 45 → -2(衰退)
        # 45 為「深度收縮」門檻(歷史衰退期常見區間 42-48)
        "expansion_above": 50.0,
        "recession_below": 45.0,
    },
    "regime_classification": {
        # 4 象限景氣分類(**真正枯榮線 52**,產出缺口模型)
        # services/macro_service.py:1457-1461
        #
        # 52 = 實際增速 ≈ 潛在增速(產出缺口 = 0)的 PMI 對應值,
        # 學理:1990-2020 US 製造業 PMI 與 GDP YoY 回歸校準
        #
        # **灰色帶 [50, 52) 歸衰退是 feature**:
        #   字面擴張但實質低於潛在 = 經濟動能已開始轉弱,屬擴張末期 / 衰退初期
        #   else 兜底為衰退避免「字面擴張」誤導 UI
        "strong_growth_above": 52.0,
        "contraction_below": 50.0,
    },
    "inflection_detection": {
        # 拐點偵測(教科書枯榮線 50 + 過熱線 55)
        # services/macro_service.py:194-198
        # 55 = 歷史過熱區(連續 3 月 >55 常見於景氣末期前 6-12 月)
        # 50 同時作為擴張 / 反彈雙向參考
        "peak_warning_above": 55.0,
        "expansion_above": 50.0,
        "rebound_below": 50.0,
    },
    "growth_signal": {
        # 二元成長訊號(教科書枯榮線 50)
        # services/macro_service.py:986
        "expansion_above": 50.0,
    },
    "alert_generation": {
        # 警示文字觸發(教科書枯榮線 50)
        # services/macro_service.py:1145
        "contraction_below": 50.0,
    },
    "beginner_panic": {
        # 新手教學介面(教科書枯榮線 50)
        # ui/helpers/macro_beginner_view.py:314 _PMI_CONTRACTION_THRESHOLD
        # 用 50 而非 52:新手介面以「公開知識門檻」優先,避免引入產出缺口概念
        "contraction_below": 50.0,
    },
    "mk_tolerance": {
        # 美林時鐘 ±0.5 容忍區間(邊界震盪不算翻面)
        # ui/components/mk_clock.py:76-81,106-107
        # 美林時鐘在 50 ±0.5 內視為「過渡帶」,避免月度雜訊頻繁翻面誤判
        "expansion_above": 50.5,
        "contraction_below": 49.5,
    },
}


# ── M2(貨幣供給 YoY)— US, % ─────────────────────────────────────────
# v19.184 F-GRAY-4 M2 harmonize（dict 與 inline 語意完全一致，低風險）
#
# F-GRAY-4 audit:本指標 dict（macro_repository MACRO_THRESHOLDS["M2"]
# = {red_below: 0, green_above: 5}）與 inline score function **語意同源**：
#   services/macro_service.py:494-496（signal/color）
#   services/macro_score_calibration.py:67（_s_m2）
# 皆用「> 5% 寬鬆利多 / < 0% 緊縮壓力 / 中間中性」同一組閾值，故可安全 SSOT 化。
# 單一用途（流動性寬縮判讀，YoY %），無多 sub-dict 語意分化。
M2_THRESHOLDS = {
    "score_function": {
        # > 5% → 流動性寬鬆（利多，+1/🟢）；< 0% → 緊縮（壓力，-1/🔴）；中間 0/🟡
        "easing_above": 5.0,
        "tightening_below": 0.0,
    },
}


# ── Fed BS（聯準會資產負債表 YoY）— US, % ──────────────────────────────
# v19.184 F-GRAY-4 Fed BS harmonize（dict 與 inline 語意完全一致，低風險）
#
# F-GRAY-4 audit:dict（MACRO_THRESHOLDS["FED_BS"] = {red_below: -5, green_above: 5}）
# 與 inline score function **語意完全相同**：
#   services/macro_service.py:622-624（signal/color）
#   services/macro_score_calibration.py:70（_s_fed_bs）
# 皆用「擴表 > 5% 注入流動性利多 / 縮表 < -5% 抽走流動性壓力」同組閾值。
# 單一用途（流動性寬縮判讀，YoY %）。
FED_BS_THRESHOLDS = {
    "score_function": {
        # > 5% → 擴表（注入流動性，+1/🟢）；< -5% → 縮表（抽走流動性，-1/🔴）；中間 0/🟡
        "expansion_above": 5.0,
        "contraction_below": -5.0,
    },
}


# ── TW PMI(中華經濟研究院 PMI)— 5 級評分,獨立於 US PMI ─────────────
# v19.180 docstring 升級:加經濟學註解
#
# ╔══════════════════════════════════════════════════════════════════════╗
# ║ 📚 經濟學教學 — TW PMI 與 US PMI 為何**不**共用閾值                  ║
# ╚══════════════════════════════════════════════════════════════════════╝
#
# 1. **編製機構不同**:
#    - TW PMI:中華經濟研究院(CIER)編製,自 2012/07 起發布
#    - US PMI:ISM(Institute for Supply Management)編製,自 1948 起發布
#    - **非中國統計局 PMI**(中國 PMI 由國家統計局編製,本系統不採用)
#
# 2. **產業結構不同 → 真正枯榮線不同**:
#    - US 潛在 GDP 增速 ≈ 2.0% → 真正枯榮線 ≈ 52
#    - TW 潛在 GDP 增速 ≈ 2.5-3.0%(出口導向、半導體強週期)
#      → 真正枯榮線 ≈ 52-53(本系統取 52 作擴張上緣)
#    - 兩者**物理獨立**,不可機械式 swap
#
# 3. **5 級評分設計**(符合 TW 半導體景氣循環高波動特性):
#    - >=55 強擴張(+2):半導體擴產期典型值
#    - >=52 溫和擴張(+1):接近潛在增速
#    - >=50 中性(0):教科書枯榮線
#    - >=48 略弱(-1):接近收縮但未進入
#    - <48 收縮(-2):明確收縮
TW_PMI_THRESHOLDS = {
    "tw_pmi_score": {
        # services/macro_tw_local.py:205-214 (tpi_score_v2)
        # services/macro_tw_local.py:323-332 (tpi_score_v3)
        "strong_above": 55.0,      # 強擴張(半導體擴產典型值)
        "expansion_above": 52.0,   # 溫和擴張(接近 TW 潛在增速)
        "neutral_above": 50.0,     # 教科書枯榮線(中性)
        "weak_above": 48.0,        # 略弱(收縮邊緣)
    },
}
