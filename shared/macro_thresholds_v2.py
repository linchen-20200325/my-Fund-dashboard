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
#
# Sanity filter [30, 70] 在 shared/signal_thresholds.PMI_VALID_MIN/MAX
# (data-quality,非 business),本檔不重複定義。
PMI_THRESHOLDS = {
    "stoplight": {
        # shared/macro_buckets.py:58-59
        "green_above": 50.0,
        "yellow_below": 50.0,
        "red_below": 46.0,
    },
    "score_function": {
        # services/macro_validation.py:102 SCORE_RULES["PMI"] lambda
        # services/macro_score_calibration.py:58 _s_pmi
        # 3 段:>= 50 → +2(擴張), [45,50) → -1(略弱), < 45 → -2(衰退)
        "expansion_above": 50.0,
        "recession_below": 45.0,
    },
    "regime_classification": {
        # services/macro_service.py:1457-1461 4 象限
        # 52 為「真正枯榮線」(新觀念,對應實際增速=潛在增速,產出缺口=0);
        # 50-52 灰色帶字面擴張但實質收縮,故 else 兜底為衰退是 feature
        "strong_growth_above": 52.0,
        "contraction_below": 50.0,
    },
    "inflection_detection": {
        # services/macro_service.py:194-198 拐點偵測
        "peak_warning_above": 55.0,
        "expansion_above": 50.0,
        "rebound_below": 50.0,
    },
    "growth_signal": {
        # services/macro_service.py:986 二元成長訊號
        "expansion_above": 50.0,
    },
    "alert_generation": {
        # services/macro_service.py:1145 警示文字觸發
        "contraction_below": 50.0,
    },
    "beginner_panic": {
        # ui/helpers/macro_beginner_view.py:314 _PMI_CONTRACTION_THRESHOLD
        "contraction_below": 50.0,
    },
    "mk_tolerance": {
        # ui/components/mk_clock.py:76-81,106-107 美林時鐘 ±0.5 容忍區間
        # (邊界震盪不算翻面)
        "expansion_above": 50.5,
        "contraction_below": 49.5,
    },
}


# ── TW PMI(中華經濟研究院 PMI)— 5 級評分,獨立於 US PMI ─────────────
# 注意:台灣 PMI 為中經院編製,非中國統計局 PMI;閾值與 US 物理獨立。
TW_PMI_THRESHOLDS = {
    "tw_pmi_score": {
        # services/macro_tw_local.py:205-214 (tpi_score_v2)
        # services/macro_tw_local.py:323-332 (tpi_score_v3)
        # 5 級:>=55(+2) / >=52(+1) / >=50(0) / >=48(-1) / <48(-2)
        "strong_above": 55.0,
        "expansion_above": 52.0,
        "neutral_above": 50.0,
        "weak_above": 48.0,
    },
}
