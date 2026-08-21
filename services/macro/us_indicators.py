"""services/macro/us_indicators.py — v19.199 P1-7 美國指標 + Phase + Regime + Systemic Risk。

從 macro_service 主檔抽出(原 line 211-1758)。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor as _TPE_macro
from typing import Optional

import pandas as pd

from repositories.macro_repository import (
    fetch_ism_pmi, fetch_fred_batch,
)
from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED, MD_AMBER_300, MD_BLUE_300, MD_BLUE_500, MD_DEEP_ORANGE_400, MD_GREEN_A200, MD_RED_A100, TRAFFIC_NEUTRAL
# v19.245 R13 F-GRAY-4 Phase A HY_SPREAD inflection 收口 SSOT
from shared.macro_thresholds_v2 import HY_SPREAD_THRESHOLDS as _HY_THR_V2
# v19.404 CFNAI 官方非對稱門檻(衰退 -0.70 / 擴張 +0.20,皆 MA3 基準)。
# 直接自 L0 shared 引(`services.macro._helpers` 只 re-export 了 RECESSION 那顆)。
from shared.signal_thresholds import (
    CFNAI_MA3_EXPANSION_THRESHOLD,
    CFNAI_TREND_GROWTH,
    macro_score_v2_enabled as _score_v2_on,
)
# 2026-08-05 稽核:`detect_systemic_risk` 的 HIGH/MEDIUM 門檻原為 inline 10/5
# (§3.3 magic number),收進新聞桶門檻族 SSOT `shared/macro_buckets.py`。
from shared.macro_buckets import (
    NEWS_RISK_HIGH_SCORE as _NEWS_RISK_HIGH,
    NEWS_RISK_MEDIUM_SCORE as _NEWS_RISK_MED,
)
# 2026-08-05 稽核:PMI / HY / CPI 評分函式與歷史 replay 收單一實作(消除兩份拷貝漂移)。
# 方向 L2(services.macro)→ L2(services.calibration),同層不違 §8.2;
# `macro_score` module-level 只 import shared.* + numpy/pandas,無回頭 import,無循環。
from services.calibration.macro_score import (
    score_cpi as _score_cpi,
    score_hy_spread as _score_hy_spread,
    score_pmi as _score_pmi,
)

from services.macro._helpers import (  # noqa: F401
    ENGINE_VERSION,
    _CPI_WARN_ABOVE, _CPI_BULL_LOW, _CPI_BULL_HIGH, _CPI_MK_GOLDEN_BELOW,
    _CPI_REGIME_OVERHEAT,
    _PMI_INFL_REBOUND, _PMI_INFL_EXPANSION, _PMI_INFL_PEAK_WARN,
    _PMI_GROWTH_EXPANSION, _PMI_ALERT_CONTRACT,
    _PMI_REGIME_STRONG, _PMI_REGIME_CONTRACT,
    _M2_EASING, _M2_TIGHTENING, _FEDBS_EXPANSION, _FEDBS_CONTRACTION,
    _HY_YELLOW, _MB_VIX_RED, _MB_VIX_YELLOW,
    SAHM_RECESSION_THRESHOLD, CFNAI_RECESSION_THRESHOLD,
    RECESSION_LOGIT_COEF_SPREAD, RECESSION_LOGIT_COEF_INTERCEPT,
    _fred, _yf_s, _trend, _safe_last, _spread_series, recession_probability,
)
from services.macro._helpers import (  # noqa: F401
    FRED_AMTMNO, FRED_CCSA, FRED_CFNAI, FRED_CHF_USD, FRED_CPI,
    FRED_DGS10, FRED_DGS2, FRED_DGS3MO, FRED_DRTSCILM, FRED_DXY,
    FRED_FED_BS, FRED_FED_FUNDS, FRED_HSN1F, FRED_HY_SPREAD, FRED_ICSA,
    FRED_ISM_PMI, FRED_JPY_USD, FRED_M2, FRED_M2_WEEKLY, FRED_MNFCTRIRSA,
    FRED_PAYEMS, FRED_PERMIT, FRED_PPI, FRED_RRP, FRED_SAHM,
    FRED_T10Y2Y, FRED_T5YIE, FRED_TGA, FRED_UMCSENT, FRED_UNRATE,
)
# v19.405:指標聚合的「去重事實」契約 SSOT(`superseded_by`)。
# v19.425:`_` 前綴 meta 述詞一併收 SSOT(原本 4 個 aggregator 各自 inline
#          `str(key).startswith("_")`,其中兩個漏寫 → 見 composite_score 頂部契約 3)。
# composite_score.py 只 import shared.colors(L0),同層 L2 互 import 無循環。
from services.macro.composite_score import is_meta_key as _is_meta_key
from services.macro.composite_score import is_superseded as _is_superseded

# ════════════════════════════════════════════════════════════════════════
# `fetch_all_indicators` 的**產出契約** —— 診斷頁靠它辨認「缺席」
# ════════════════════════════════════════════════════════════════════════
# 2026-08-20 稽核發現的結構缺陷:`fetch_all_indicators` 對每個指標都是
# 「抓到才寫 key」(例:`if pmi.get("value") is not None: R["PMI"] = ...`),
# 抓失敗時 **key 直接不存在**。而 `ui/helpers/io/data_registry` 是
# **列舉既有 stash**、不是比對應有清單 ⇒ 抓失敗的指標不會產生任何一列 ⇒
# 「異常清單」印出「✅ 已登錄的 N 個資料源狀態全數正常」。
#
#   ⇒ **失敗越多、N 越小、畫面越綠。** 這是「缺資料偽裝成正常」的最上游形態,
#     且它會系統性放大所有其他監控缺口(§1)。
#
# 本常數把「應該有哪些」從隱性(散在 28 個 `R[...] = ` 賦值裡)變成顯性契約,
# 讓消費端能算出差集。**這是給診斷用的清單,不是給計分用的** ——
# 缺席代表「這次沒抓到」,不代表「本系統沒有這個指標」。
#
# ⚠️ 新增/刪除指標時**必須**同步本元組,否則 `tests/test_indicator_inventory.py`
#    的 AST 漂移鎖會紅燈(它直接掃本檔的 `R[...]` 賦值比對)。
EXPECTED_INDICATOR_KEYS: tuple[str, ...] = (
    # 領先 / 循環
    "PMI", "LEI", "NFP", "PERMIT_HOUSING", "NEW_HOME", "CONSUMER_CONF",
    # 通膨
    "CPI", "PPI", "INFL_EXP_5Y",
    # 就業
    "UNEMPLOYMENT", "JOBLESS", "CONT_CLAIMS", "SAHM",
    # 貨幣 / 流動性
    "M2", "M2_WEEKLY", "FED_BS", "FED_RATE", "SLOOS",
    # 利率 / 信用
    "YIELD_10Y2Y", "YIELD_10Y3M", "HY_SPREAD",
    # 市場 / 匯率 / 商品
    "VIX", "DXY", "ADL", "COPPER", "EURUSD", "USDJPY", "USDCNH",
)
"""`fetch_all_indicators` 承諾**嘗試**產出的 28 個 key(不含 `_` 前綴 meta 鍵)。

用途:讓 `data_registry` 能做 `EXPECTED - present` 的差集,把「應該有但沒來」
的指標顯式列成 🔴,而不是靜靜地不存在。

**不是**「一定會有」的保證 —— 外部來源失敗時該 key 就是不會出現,
這正是本常數要讓它可見的東西。
"""

_INDICATOR_SNAPSHOT: dict = {}

# v19.384(user 2026-07-23 拍板回退 v19.383):VIX 快照卡「平靜」綠界**刻意保持 18**,
# 嚴於全站 cross-site SSOT yellow=22(`_MB_VIX_RED` 紅界仍走 SSOT 30)。此為 snapshot 層
# 獨立校準,**非** F-GRAY-4「全站 yellow 統一 22」的漏網 —— 稽核時勿逕改為 `_MB_VIX_YELLOW`。
# 具名常數化以免 §3.3 inline magic + 防未來重複改動。
_VIX_SNAPSHOT_CALM = 18.0

# ── PMI 補救/防呆常數(v19.404 稽核)──────────────────────────────
# 歷史補救序列的時效上限:沿用主路徑 `repositories.macro.alternate.fetch_ism_pmi`
# 的 `max_age_days=90` 契約 —— value 端已被 90 天時效檢查擋掉的死 series,
# 沒有理由當作 series 端的「歷史結構」餵給 Z-Score / lag-correlation。
_PMI_HIST_MAX_AGE_DAYS = 90
# PMI 刻度值域(CLAUDE.md §3.2 合理範圍表 + `fetch_ism_pmi` 各段自帶的
# `30 <= v <= 70` 防呆,同一契約)。落在此區間外者**必非 PMI 刻度**
# (例:OECD US BCI ~98–102),不可用 50 榮枯線判讀。
# ⚠️ 本區間僅作「刻度辨識」,不是「ISM 歷史實務區間」—— 收緊到實務區間需官方
# 統計佐證,尚未取得,依 §1 維持現狀不臆測(見交付報告任務 4)。
_PMI_SCALE_MIN = 30.0
_PMI_SCALE_MAX = 70.0


def _detect_inflection(indicators):
    signals = []; score = 0
    def _chk(key, attr="value"): return indicators.get(key,{}).get(attr)

    pmi_v = _chk("PMI"); pmi_p = _chk("PMI","prev")
    if pmi_v and pmi_p:
        if pmi_v < _PMI_INFL_REBOUND and pmi_v > pmi_p:
            signals.append({"type":"buy","text":f"PMI {pmi_v:.1f} 收縮區但止跌反彈（+{pmi_v-pmi_p:.1f}）— 復甦訊號"}); score += 2
        elif pmi_v >= _PMI_INFL_EXPANSION and pmi_v > pmi_p:
            signals.append({"type":"bull","text":f"PMI {pmi_v:.1f} 擴張且上升"}); score += 1
        elif pmi_v >= _PMI_INFL_PEAK_WARN and pmi_v < pmi_p:
            signals.append({"type":"warn","text":f"PMI {pmi_v:.1f} 高位回落，景氣可能見頂"}); score -= 1

    y22 = indicators.get("YIELD_10Y2Y",{})
    v22 = y22.get("value"); p22 = y22.get("prev")
    if v22 is not None:
        if v22 < 0: signals.append({"type":"warn","text":f"10Y-2Y 倒掛 {v22:.3f}%，衰退信號"}); score -= 2
        elif v22 >= 0 and p22 is not None and p22 < 0:
            signals.append({"type":"buy","text":f"⚡ 10Y-2Y 由負翻正（{v22:.3f}%）— 策略3 最強黃金買點！"}); score += 4
        elif v22 > 0.5: signals.append({"type":"bull","text":f"10Y-2Y 正斜率 {v22:.3f}%"}); score += 1

    y3m = indicators.get("YIELD_10Y3M",{})
    v3m = y3m.get("value"); p3m = y3m.get("prev")
    if v3m is not None:
        if v3m < 0: signals.append({"type":"warn","text":f"10Y-3M 倒掛 {v3m:.3f}%"}); score -= 2
        elif v3m >= 0 and p3m is not None and p3m < 0:
            signals.append({"type":"buy","text":f"⚡ 10Y-3M 翻正（{v3m:.3f}%）— 降息確認"}); score += 3

    cpi_v = _chk("CPI"); cpi_t = indicators.get("CPI",{}).get("trend","")
    if cpi_v:
        if cpi_v > _CPI_WARN_ABOVE and "下降" in cpi_t: signals.append({"type":"buy","text":f"⚡ CPI {cpi_v:.1f}% 高位但回落 — 落後指標見頂"}); score += 3
        elif cpi_v > _CPI_WARN_ABOVE: signals.append({"type":"warn","text":f"CPI {cpi_v:.1f}% 高位未降，緊縮壓力"}); score -= 2
        elif _CPI_BULL_LOW <= cpi_v <= _CPI_BULL_HIGH: signals.append({"type":"bull","text":f"CPI {cpi_v:.1f}% 回落至合理區間"}); score += 2

    fed_v = _chk("FED_RATE"); fed_p = _chk("FED_RATE","prev")
    if fed_v is not None and fed_p is not None:
        if fed_v < fed_p: signals.append({"type":"buy","text":f"⚡ 降息（{fed_p:.2f}%→{fed_v:.2f}%）— 資金行情"}); score += 3
        elif fed_v > fed_p: signals.append({"type":"warn","text":f"升息（{fed_p:.2f}%→{fed_v:.2f}%）"}); score -= 2

    vix_v = _chk("VIX")
    if vix_v:
        if vix_v > _MB_VIX_RED: signals.append({"type":"buy","text":f"VIX {vix_v:.1f} 恐慌高位 — 逢低加碼時機"}); score += 2
        elif vix_v < 15: signals.append({"type":"warn","text":f"VIX {vix_v:.1f} 過低，市場過樂觀"}); score -= 1  # 15=過樂觀地板,與 yellow/red SSOT 不同語意,保留

    jb_v = _chk("JOBLESS"); jb_p = _chk("JOBLESS","prev")
    if jb_v and jb_p:
        # 單位：萬人（macro_engine 已統一在 fetch_all_indicators 將 ICSA/10000）
        if jb_v < jb_p and jb_v < 25: signals.append({"type":"bull","text":f"初領失業金 {jb_v:.1f} 萬 改善"}); score += 1
        elif jb_v > 30: signals.append({"type":"warn","text":f"初領失業金 {jb_v:.1f} 萬 高位"}); score -= 1

    # v18.250 新增：HY Spread 由高位回落（信用拐點）— v19.245 R13 收口 SSOT
    hy_v = _chk("HY_SPREAD"); hy_p = _chk("HY_SPREAD","prev")
    if hy_v is not None and hy_p is not None:
        _HY_INFL = _HY_THR_V2["inflection_detection"]
        if hy_p >= _HY_INFL["high_position"] and hy_v < hy_p:
            signals.append({"type":"buy","text":f"⚡ HY 利差 {hy_p:.2f}%→{hy_v:.2f}% 高位首度回落 — 信用拐點"}); score += 3
        elif hy_p >= _HY_INFL["moderate_position"] and hy_v < hy_p - _HY_INFL["moderate_drop_pp"]:
            signals.append({"type":"buy","text":f"HY 利差 {hy_v:.2f}% 明顯收斂（-{hy_p-hy_v:.2f}pp）— risk-on 醞釀"}); score += 1

    # v18.250 新增：薩姆規則由觸發→解除（衰退結束拐點）
    sahm_v = _chk("SAHM"); sahm_p = _chk("SAHM","prev")
    if sahm_v is not None:
        if sahm_p is not None and sahm_p >= SAHM_RECESSION_THRESHOLD and sahm_v < SAHM_RECESSION_THRESHOLD:
            signals.append({"type":"buy","text":f"⚡ 薩姆規則 {sahm_p:.2f}→{sahm_v:.2f} 跌破 {SAHM_RECESSION_THRESHOLD} — 衰退警報解除拐點"}); score += 4
        elif sahm_v >= SAHM_RECESSION_THRESHOLD:
            signals.append({"type":"warn","text":f"薩姆規則 {sahm_v:.2f} ≥{SAHM_RECESSION_THRESHOLD} 衰退警報中"}); score -= 2

    # v18.250 新增：CFNAI 領先指標由負轉正（領先翻揚拐點）
    # v19.404 稽核修正：改吃 **CFNAI-MA3**（`ma3`/`ma3_prev`）—— 官方 ±門檻是為 MA3 校準的，
    #   拿月度值判「由負轉正」會被 √3 倍的噪音頻繁誤觸。缺 ma3 欄（舊 cache / 測試 fixture）
    #   時退回月度 value/prev，行為與 v19.403 相同（不 raise，§1 降級可辨識）。
    # 同時補上官方遲滯的另一半：MA3 由 ≤ -0.70 回升越過 +0.20 = 官方「衰退結束」訊號，
    #   原本只有單邊衰退門檻，復甦期永遠發不出解除警報（對齊同檔 SAHM 的解除拐點寫法）。
    # v19.405 稽核修正(§4.1 量綱一致):降級必須 **all-or-nothing**。
    #   原碼兩個 fallback 各自獨立 —— `ma3` 有值但 `ma3_prev` 為 None
    #   (上方 :866 `len(_ma3_valid) < 2`,即 CFNAI 只夠算 1 期 MA3)時,
    #   lei_v = **三月均值**、lei_p = **單月值**,拿兩個不同基準比「由負轉正」,
    #   月度值波動度約 MA3 的 √3 倍 → 假拐點。改為兩欄同時具備才用 MA3,
    #   否則整組退回月度 value/prev(同基準,行為與 v19.403 相同)。
    lei_v = _chk("LEI","ma3"); lei_p = _chk("LEI","ma3_prev")
    if lei_v is None or lei_p is None:
        lei_v, lei_p = _chk("LEI"), _chk("LEI","prev")
    if lei_v is not None and lei_p is not None:
        if lei_p <= CFNAI_RECESSION_THRESHOLD and lei_v > CFNAI_MA3_EXPANSION_THRESHOLD:
            signals.append({"type":"buy","text":f"⚡ CFNAI-MA3 {lei_p:+.2f}→{lei_v:+.2f} 突破官方擴張門檻 +{CFNAI_MA3_EXPANSION_THRESHOLD:.2f} — 衰退結束確認"}); score += 4
        elif lei_v > CFNAI_TREND_GROWTH and lei_p <= CFNAI_TREND_GROWTH:
            signals.append({"type":"buy","text":f"⚡ CFNAI-MA3 {lei_p:+.2f}→{lei_v:+.2f} 由負轉正 — 景氣翻揚拐點"}); score += 3
        elif lei_v < CFNAI_RECESSION_THRESHOLD:
            signals.append({"type":"warn","text":f"CFNAI-MA3 {lei_v:+.2f} < {CFNAI_RECESSION_THRESHOLD} 強烈衰退"}); score -= 2

    if fed_v is not None and fed_p is not None and fed_v <= fed_p and fed_p > 0 and \
       cpi_v and cpi_v < _CPI_MK_GOLDEN_BELOW and "下降" in cpi_t:
        signals.append({"type":"buy","text":"⭐ 黃金拐點：CPI+Fed Rate 雙雙見頂回落，勝率最高！"}); score += 5

    if score >= 8:   infl = {"label":"🚀 強力買進拐點","color":MATERIAL_GREEN,"desc":"多項指標同時確認，景氣最佳買點"}
    elif score >= 4: infl = {"label":"✅ 買進拐點形成","color":MD_GREEN_A200,"desc":"落後見頂 + 領先反彈，建議逢低布局"}
    elif score >= 1: infl = {"label":"👀 觀察（偏多）","color":MATERIAL_ORANGE,"desc":"部分訊號出現，持續觀察"}
    elif score >= -2:infl = {"label":"⚖️ 中性整理","color":TRAFFIC_NEUTRAL,"desc":"指標分歧，維持資產配置"}
    elif score >= -5:infl = {"label":"⚠️ 謹慎偏空","color":MD_DEEP_ORANGE_400,"desc":"落後指標未見頂，降低股票型比重"}
    else:            infl = {"label":"🔴 空頭拐點","color":MATERIAL_RED,"desc":"確認衰退，優先貨幣型與投資等級債"}
    return {"inflection":infl,"signals":signals,"infl_score":score}


def _fred_iso(sid, key, n=250):
    """v19.331 review:per-series 隔離(把 v19.171 五條並行 pool 的 per-future 容錯
    慣例擴及本檔其餘 16 處 sequential `_fred()` 呼叫)。

    單一 series 例外(pandera SchemaError / 上游 IO error)原本會炸掉整個
    fetch_all_indicators → 該指標**之後的所有指標格全滅**(UI 大面積空白)。
    改為失敗回空 DataFrame + stderr log — 只犧牲該格(下游各區塊已有
    `len(df)>=N` 防線),repository 層 fail-loud 驗證不動(§1 分層:來源炸、編排格局部降級)。
    """
    try:
        return _fred(sid, key, n)
    except Exception as _e_iso:
        print(f"[macro_service/fetch_all] FRED {sid} 失敗,以空 DataFrame 替代: "
              f"{type(_e_iso).__name__}: {_e_iso}")
        return pd.DataFrame()


def _yf_iso(ticker, period="2y"):
    """v19.331 review:同 _fred_iso,Yahoo 收盤序列 per-ticker 隔離(VIX / 銅博士)。"""
    try:
        return _yf_s(ticker, period)
    except Exception as _e_iso:
        print(f"[macro_service/fetch_all] Yahoo {ticker} 失敗,以空 Series 替代: "
              f"{type(_e_iso).__name__}: {_e_iso}")
        return pd.Series(dtype=float)


# ── NFP 月變動 → (score, signal, color) ────────────────────────────────
# v19.404 稽核修正:**符號整組反向**。原碼 `cur_d < 0 → score = +1.5 / 🔴`、
# `cur_d >= 500 → score = -1.0 / 🟢` —— 非農就業月增為負(衰退訊號、紅燈)卻給正分,
# 就業成長(綠燈)卻給負分,是全站唯一符號相反的指標。
#
# 全站 sign convention(§4.1):**正分 = 偏多 / 風險下降**,與 emoji 同向。
#   evidence: `services/macro/explain.py` interpretation 7 級(v19.352 「正分 = 偏多」)、
#             同檔 `YIELD_10Y3M score = 2 if v > 0.5 else -2`(好 = 正分)、
#             聚合式 `norm = (earned_w + total_w) / (2 * total_w) * 10`(分數越高位階越高)。
#
# 幅度另同步修正:原「衰退」給 ±1.5 但 `weight=1.0` —— `calc_macro_phase` 會 clamp 到
# ±weight,`services/macro/composite_score.calculate_composite_score` **不 clamp**,
# 同一分數在兩條路徑不一致。現在全部 tier 的 |score| ≤ weight(1.0),兩路徑等價。
#
# 上檔為倒 U:250–500k 強勁(+1.0 滿分)、>500k 過熱反而打折(+0.5)——
# 過熱會推升 Fed 緊縮預期,對風險資產不是線性利多(對齊同檔 CPI/PPI 的「區間最佳」寫法)。
#
# ── 門檻出處(v19.405 稽核補標;沿用 `shared/macro_buckets.py:23-26` 的標註慣例)──
# 同一 PR 內 CFNAI 的 -0.70 / +0.20 附了 Chicago Fed 官方逐字引文 + URL;
# 本組三個切點**沒有**同等級的來源,不得比照辦理假裝有,故據實標 DESIGN:
#   * BLS 發布 NFP 月變動本身,**不發布**任何「冷 / 中性 / 強勁 / 過熱」分級表;
#   * 100k 一般被市場當「損益兩平就業成長」(吸納勞動力自然增長所需)的概念值,
#     但該值隨勞動參與率 / 移民淨流入變動,各家(Fed 官員談話、投行研究)估計並不一致,
#     本專案**未取得**可引用的單一官方定義 → 不掛任何機構名背書;
#   * 250k / 500k 為本專案 tier 切點,無外部來源。
# ⚠️ 因此本組**只保證方向與幅度**(符號 = 全站 sign convention、|score| ≤ weight),
#    **不宣稱數值權威**。要調數值需 user 指派 + 附得起的出處(§-1 不主動推)。
# ⚠️ 禁止把本常數改標成 "SSOT:<某處>" 除非真的接上該處常數(§3.3 反捏造)。
_NFP_TIER_SOURCE: str = "DESIGN"   # 見上方說明;非官方門檻,本專案自訂分級
_NFP_COLD_K = 100.0     # 千人;< 100k 偏冷        (DESIGN)
_NFP_NEUTRAL_K = 250.0  # 千人;100–250k 中性      (DESIGN)
_NFP_STRONG_K = 500.0   # 千人;250–500k 強勁 / > 500k 過熱  (DESIGN)


def _nfp_tier(cur_d: float) -> tuple[float, str, str]:
    """非農新增就業月變動(千人)→ (score, signal_emoji, color)。

    純函式,無 I/O。獨立出來讓 `tests/test_macro_indicator_signs.py` 能直接釘死符號。
    """
    if cur_d < 0:
        return -1.0, "🔴", MATERIAL_RED            # 就業淨減 = 衰退訊號
    if cur_d < _NFP_COLD_K:
        # v19.405:原 inline hex,已具名收 SSOT(§3.3 色票 shared/colors.py)
        return -0.5, "🟠", MD_RED_A100             # 偏冷
    if cur_d < _NFP_NEUTRAL_K:
        return 0.0, "🟡", MD_AMBER_300             # 中性
    if cur_d < _NFP_STRONG_K:
        return 1.0, "🟢", MD_GREEN_A200            # 強勁
    return 0.5, "🟡", MD_AMBER_300                 # 過熱 — 強但引發 Fed 緊縮,上檔打折


# ── 淨流動性 YoY 的「誰在抽水」分解(2026-08-05 稽核)────────────────────
# 單位(§4.1 陷阱):WALCL / TGA = 百萬美元、RRP = 十億美元 → 換算係數**不同**。
# 統一輸出「億美元」(1 億 = 100 百萬 = 0.1 十億),對齊 user 讀報用語。
_MN_TO_100M = 100.0     # 百萬美元 → 億美元
_BN_TO_100M = 0.1       # 十億美元 → 億美元
_YOY_LOOKBACK_DAYS = 365   # 以「日曆日」回看,對週頻 WALCL/TGA 與日頻 RRP 都成立


def _asof_year_ago(s) -> Optional[float]:
    """回傳「最新觀測日往回 365 日曆日」當下**已公布**的值;不足回 None。

    用 `s.loc[:target]` 取截止日以前的最後一筆 —— backward as-of,**不吃未來**
    (§2.3 防 lookahead)。頻率無關:週頻 52 筆、日頻 ~252 筆都適用,不必假設列距。
    §1:資料不足回 None,由呼叫端決定降級,不填 0 / 不 ffill。
    """
    try:
        if s is None or len(s) < 2:
            return None
        _target = s.index[-1] - pd.Timedelta(days=_YOY_LOOKBACK_DAYS)
        _prior = s.loc[:_target]
        if len(_prior) == 0:
            return None
        return float(_prior.iloc[-1])
    except Exception as _e:
        print(f"[net_liq/decomp] as-of 回看失敗:{type(_e).__name__}: {_e}")
        return None


def _net_liq_decomposition(df_walcl, df_rrp, df_tga) -> str:
    """淨流動性 YoY 的組成分解字串(億美元);任一組件缺 → 回 ""(§1 不編數字)。

    **為什麼需要這段**(2026-08-05 稽核 🔴 必修 2):v19.193 起評分格的輸入已從
    毛額 WALCL 換成淨流動性(WALCL − RRP − TGA),但**卡片文案沒跟著換**。實測
    2026-07-29 淨流動性 YoY = −4.77%,畫面敘述成「急速縮表」—— 事實是 Fed 資產
    (WALCL 毛額)YoY **+1.44%(增加約 956 億美元)**,跌幅幾乎全部來自 TGA 由
    3,705 億重建到 9,108 億(+5,403 億)。那是財政部發債補庫存造成的**機械性、
    暫時性抽水**,不是 QT。把「是誰在抽水」寫進 desc,讓卡片不能再被讀成縮表。

    只回字串、不回 dict:唯一消費端就是 `R["FED_BS"]["desc"]`(UI 直接渲染),
    多包一層 side-car dict 沒有第二個 consumer = `CLAUDE.md §8.1 step 6` 的
    「用不到的抽象」,且會踩 `PROCESS.md §4` 的 0-consumer 陷阱。
    """
    try:
        if df_walcl is None or df_rrp is None or df_tga is None:
            return ""
        if getattr(df_walcl, "empty", True) or getattr(df_rrp, "empty", True) \
                or getattr(df_tga, "empty", True):
            return ""
        _parts = []

        def _series(_df):
            _s = _df[["date", "value"]].dropna().copy()
            _s["date"] = pd.to_datetime(_s["date"])
            _s = _s.sort_values("date").set_index("date")["value"]
            return _s

        _w = _series(df_walcl)
        _w_prev = _asof_year_ago(_w)
        if _w_prev is not None and abs(_w_prev) > 0:
            _w_now = float(_w.iloc[-1])
            _w_yoy = (_w_now / _w_prev - 1.0) * 100.0
            _w_d = (_w_now - _w_prev) / _MN_TO_100M
            _parts.append(f"Fed資產 {_w_yoy:+.2f}%({_w_d:+,.0f} 億)")

        _t = _series(df_tga)
        _t_prev = _asof_year_ago(_t)
        if _t_prev is not None:
            _t_d = (float(_t.iloc[-1]) - _t_prev) / _MN_TO_100M
            # 淨流動性 = W − R − T ⇒ TGA 增加 = 抽水
            _parts.append(f"TGA {_t_d:+,.0f} 億({'抽水' if _t_d > 0 else '釋水'})")

        _r = _series(df_rrp)
        _r_prev = _asof_year_ago(_r)
        if _r_prev is not None:
            _r_d = (float(_r.iloc[-1]) - _r_prev) / _BN_TO_100M
            _parts.append(f"RRP {_r_d:+,.0f} 億({'抽水' if _r_d > 0 else '釋水'})")

        if not _parts:
            return ""
        return "近1年分解:" + " / ".join(_parts)
    except Exception as _e:
        print(f"[net_liq/decomp] 分解失敗,desc 不附分解:{type(_e).__name__}: {_e}")
        return ""


def fetch_all_indicators(fred_api_key):
    R = {}

    # ── v19.65 P1-F1：21 條 FRED 批次預熱（並行 8 worker）──
    # v19.67 P1-F2：擴展 3 條 liquidity_engine.py 用 FRED（DTWEXBGS/DEXJPUS/DEXSZUS）
    # 原本 16 條 sequential `_fred()` 呼叫各 0.2~0.5s（首次 cache miss）→ 一次 batch
    # 並行 + 共享既有 @_ttl_cache(30min)，後續呼叫點自然 hit cache、邏輯 0 改動。
    # 估 Fund 首頁總經 tab 載入 -3~6s（v19.67 額外覆蓋深水區流動性兩 builder 冷啟動）。
    if fred_api_key:
        fetch_fred_batch([
            (FRED_DGS10, 2600), (FRED_DGS2, 2600), (FRED_DGS3MO, 2600),
            (FRED_HY_SPREAD, 2500), (FRED_M2, 144),
            (FRED_ISM_PMI, 144), (FRED_FED_BS, 312), (FRED_CPI, 144),
            (FRED_FED_FUNDS, 144), (FRED_UNRATE, 144), (FRED_PPI, 144),
            (FRED_UMCSENT, 144), (FRED_ICSA, 312), (FRED_HSN1F, 144),
            (FRED_SAHM, 144), (FRED_DRTSCILM, 80), (FRED_CFNAI, 144),
            (FRED_CCSA, 312), (FRED_M2_WEEKLY, 520), (FRED_T5YIE, 2500),
            (FRED_PERMIT, 144), (FRED_PAYEMS, 144),
            # v19.67 P1-F2：liquidity_engine.py 用
            (FRED_DXY, 800), (FRED_JPY_USD, 400), (FRED_CHF_USD, 400),
            # v19.331 review:淨流動性路徑補進 batch(原 sequential 冷啟動 2 次串行往返;
            # n 與下方呼叫點一致 → 同 cache key 直接命中)
            (FRED_RRP, 2000), (FRED_TGA, 312),
        ], fred_api_key, max_workers=8)

    # ── PMI（v2.1 改用共用函式 fetch_ism_pmi 6 段備援 + 90 天時效檢查）──
    #   舊版直接拿 FRED NAPM 末筆值，會誤用 2016-08 停更後的死值欺騙 UI；
    #   改呼叫 macro_core.fetch_ism_pmi()，備援順序：
    #   NAPM/ISPMANPMI（時效檢查）→ MacroMicro → ISM World → DBnomics →
    #   Phil Fed Diffusion（轉 PMI 刻度，**代理值非本尊**）→ OECD US BCI（最後手段）
    #   ⚠️ 舊註解寫「相關性 0.85」為過度宣稱，已刪：Phil Fed 是單一聯準區約 250 家
    #      廠商的月變化擴散指數，ISM 是全國 16 大產業複合指數。實證反例 2026-07：
    #      Phil Fed 10.3→41.4（+31.1），ISM 53.3→55.6（+2.3）。命中此段時
    #      `is_proxy=True`，UI/AI prompt 必須顯示代理標記（§1）。
    #      同一句宣稱已於 repositories/macro/alternate.py 一併更正。
    pmi = fetch_ism_pmi(fred_api_key)
    if pmi.get("value") is not None:
        v = float(pmi["value"])
        vals_list = pmi.get("values") or [v]
        prev = float(vals_list[-2]) if len(vals_list) >= 2 else None
        s = None
        if pmi.get("dates") and pmi.get("values"):
            s = pd.Series(
                [float(x) for x in pmi["values"]],
                index=pd.to_datetime(pmi["dates"]),
            ).tail(120)
        # v18.118/119 issue 3 補救：HTML 來源或舊 tail(24) 限制導致 series 缺失或過短
        # → 補抓 FRED ISPMANPMI 144 期當 series（即使源 value 已過時，歷史結構對
        #   Phase 4 lag-correlation / Phase 3-B 燈號回測仍可用 — 都看相對變化）
        # v18.119: 條件放寬「s is None or len(s) < 60」— 上游 fetch_ism_pmi 雖已改 tail(120)
        # 但 MacroMicro / ISM World 等 HTML 源仍可能回 0 期，雙保險。
        # v19.404 稽核修正（§1 Fail Loud）：本補救路徑抓的 `ISPMANPMI` 與 `NAPM` 兩條
        #   FRED series 都在 2016-08 ISM 收回授權後停更/下架 —— 主路徑 `fetch_ism_pmi`
        #   有 90 天時效檢查會跳過它們，這裡卻**無時效檢查也無空值 log**：
        #     (a) df_hist 為空（series 已下架）→ 原碼靜默什麼都不做，看不出補救失敗；
        #     (b) df_hist 非空但末筆停在 2016 → 把一段十年前的死序列裝進 `series`，
        #         而 `value` 是當期值 → `calc_macro_phase_zpct` 的
        #         `z = (value - mean(series.tail(60))) / std` 與 Phase 4 lag-corr 全被污染。
        #   改為：空 → 明確 log；過期（沿用 `fetch_ism_pmi(max_age_days=90)` 同一時效契約）
        #   → 明確 log 並**拒絕採用**，寧可留 series=None 讓下游 `len(s)>=N` 防線跳過該格。
        if (s is None or len(s) < 60) and fred_api_key:
            try:
                df_hist = _fred(FRED_ISM_PMI, fred_api_key, 144)
                if df_hist.empty:
                    print(f"[PMI] ⚠️ series 補救失敗：FRED {FRED_ISM_PMI} 回空 "
                          f"(2016-08 ISM 收回授權後停更/下架)，本次不補歷史")
                else:
                    _hist_last = pd.to_datetime(df_hist["date"].iloc[-1])
                    _hist_age = (pd.Timestamp.today().normalize() - _hist_last.normalize()).days
                    if _hist_age > _PMI_HIST_MAX_AGE_DAYS:
                        print(f"[PMI] ⚠️ series 補救**拒絕採用**：FRED {FRED_ISM_PMI} 末筆="
                              f"{_hist_last.date()} 已停更 {_hist_age} 天 > "
                              f"{_PMI_HIST_MAX_AGE_DAYS} 天；與當期 value 混用會污染 "
                              f"Z-Score / lag-correlation（§1 不以死值假裝有歷史）")
                    else:
                        s = df_hist.set_index("date")["value"].tail(120)
                        print(f"[PMI] series 補救：FRED {FRED_ISM_PMI} 歷史 {len(s)} 期"
                              f"（末筆 {_hist_last.date()}，age={_hist_age}d）")
            except Exception as _e_pmi_hist:
                print(f"[PMI] ⚠️ series 補救失敗：{type(_e_pmi_hist).__name__}: {_e_pmi_hist}")
        is_proxy = bool(pmi.get("is_proxy"))
        src_label = pmi.get("source", "?")
        # v19.404 稽核修正：原判斷式 `src_label == "OECD-Proxy"` **永遠不成立** ——
        #   `repositories/macro/alternate.fetch_ism_pmi` 方案 7 回傳的 `source` 實際是
        #   `"FRED:BSCICP02USM460S:proxy"`（"OECD-Proxy" 只出現在該段的 print log 裡）。
        #   後果：OECD 商業信心（值域 ~98–102，100 為長期平均）會掉進 else 分支，被拿
        #   50 榮枯線判讀 → 98 > 50 → 恆給 🟢 + score=2（該指標的最高正分），且卡名被
        #   誤標成「Phil Fed 替代」。改以 series_id / source 子字串比對（來源契約），
        #   並加值域防呆：is_proxy 且值落在 PMI 刻度 [30,70] 之外 = 必非 PMI 刻度。
        _pmi_sid = str(pmi.get("series_id", ""))
        _off_pmi_scale = not (_PMI_SCALE_MIN <= v <= _PMI_SCALE_MAX)
        _is_index100 = is_proxy and (
            "BSCICP02" in _pmi_sid or "BSCICP02" in str(src_label)
            or "OECD" in str(src_label).upper()
            or _off_pmi_scale
        )
        # v19.404:命中來源攤在 log,方便現場對帳「顯示值到底出自哪一段備援」
        print(f"[PMI] 採用 value={v} date={pmi.get('date', '?')} "
              f"source={src_label} label={pmi.get('label', '')} "
              f"series_id={_pmi_sid or '-'} is_proxy={is_proxy} "
              f"scale={'index100' if _is_index100 else 'pmi50'}")
        if _is_index100 and _off_pmi_scale and not (
                "BSCICP02" in _pmi_sid or "BSCICP02" in str(src_label)
                or "OECD" in str(src_label).upper()):
            # §1:值不在 PMI 刻度、來源又認不出是 OECD → 刻度不明,只能保守走 index-100
            print(f"[PMI] ⚠️ 值 {v} 不在 PMI 刻度 [{_PMI_SCALE_MIN:.0f},{_PMI_SCALE_MAX:.0f}] "
                  f"且來源無法辨識({src_label}) — 以 index-100 刻度保守判讀,請人工確認來源")
        if _is_index100:
            # OECD BCI 概念替代：100 為長期平均，>100 擴張、<100 收縮
            signal_g = v > 100
            signal_r = v < 99
            score = 1 if signal_g else (-1 if signal_r else 0)
            desc = (f"⚠️ 替代指標（非 PMI 刻度）：{pmi.get('label', 'OECD US BCI')} | "
                    "100 為長期平均，>100 擴張 | "
                    f"資料源：{src_label}")
            name = "ISM PMI（替代：OECD US BCI）"
        else:
            # 包括 Phil Fed 已轉換為 PMI 刻度，與真 ISM PMI 同 50 榮枯線
            signal_g = v > 50
            signal_r = v < 45
            # 2026-08-05 稽核:原 inline `2 if v>=50 else (-2 if v<45 else -1)` 收
            # `services.calibration.macro_score.score_pmi`(與歷史 replay 同一實作)。
            # 旗標 OFF → 逐點等值;ON → 連續 tanh(見該函式 docstring 的參數論證)。
            # signal/color 維持階梯(stoplight 與 score 語意分離,F-GRAY-4 既有裁決)。
            score = _score_pmi(v, max_abs=2.0)
            desc = (f"50 為榮枯線，>50 擴張，<50 收縮 | 最核心領先指標 | "
                    f"資料源：{pmi.get('label', src_label)}")
            name = ("ISM 製造業 PMI（Phil Fed 替代）" if is_proxy
                    else "ISM 製造業 PMI")
        R["PMI"] = dict(
            name=name, value=v, prev=prev, unit="", type="領先",
            date=str(pmi.get("date", ""))[:7],
            desc=desc,
            trend=_trend([float(x) for x in vals_list[-6:]]),
            signal="🟢" if signal_g else ("🔴" if signal_r else "🟡"),
            color=MATERIAL_GREEN if signal_g else (MATERIAL_RED if signal_r else MATERIAL_ORANGE),
            score=score, weight=2, series=s,
            source=src_label,
            is_proxy=is_proxy,
            label=pmi.get("label", ""),
            proxy_note=pmi.get("proxy_note", ""),
        )

    # ── 殖利率利差 ──────────────────────────────────────────────────
    # n=2600 (≈10y daily) 才能 resample("ME") 後保留 120 月頻 spread → 餵 Phase 4/3-B
    # v19.49 perf: DGS10/DGS2/DGS3MO + HY (BAMLH0A0HYM2) + M2 (M2SL) 五條 FRED 並行
    #   原序列 3-5s → max(t)。HY/M2 series 留待下方原本位置繼續算指標（不動邏輯）。
    # 必須用 DGS3MO（日頻 3M Treasury Constant Maturity）而非 TB3MS（月頻 T-Bill 平均），
    # 否則 spread 被 inner-join 降頻成月頻，daily threshold 會誤判 🔴 過舊。
    with _TPE_macro(max_workers=5) as _pool_dgs:
        _f_d10 = _pool_dgs.submit(_fred, "DGS10",  fred_api_key, 2600)
        _f_d2  = _pool_dgs.submit(_fred, "DGS2",   fred_api_key, 2600)
        _f_d3m = _pool_dgs.submit(_fred, "DGS3MO", fred_api_key, 2600)
        _f_hy  = _pool_dgs.submit(_fred, "BAMLH0A0HYM2", fred_api_key, 2500)
        _f_m2  = _pool_dgs.submit(_fred, "M2SL",   fred_api_key, 144)
        # v19.171:per-future 容錯(對齊 fetch_fred_batch 慣例)。
        # 原本任一 series 觸發 pandera SchemaError / 上游 IO error 都會炸掉整個
        # fetch_all_indicators 路徑 → UI 顯示「0 個指標」。改為 per-series 失敗回
        # 空 DataFrame + 印 stderr,下游已有 df.empty 防線(本檔多處 `if df.empty:`)。
        def _safe_fred_result(_fut, _label):
            try:
                return _fut.result()
            except Exception as _e_fr:
                print(f"[macro_service/fetch_all] FRED {_label} 失敗,以空 DataFrame 替代: "
                      f"{type(_e_fr).__name__}: {_e_fr}")
                return pd.DataFrame()
        df10 = _safe_fred_result(_f_d10, "DGS10")
        df2  = _safe_fred_result(_f_d2,  "DGS2")
        df3m = _safe_fred_result(_f_d3m, "DGS3MO")
        _df_hy_pre = _safe_fred_result(_f_hy, "BAMLH0A0HYM2")
        _df_m2_pre = _safe_fred_result(_f_m2, "M2SL")

    # v19.56 B2: 5 條 FRED 個別命中狀態（series_id → success/last_date/rows）
    # v19.60 D1：補上 realtime_start（BLS/FED 真實發布日）+ publish_lag_days
    _fred_srcs: dict = {}
    for _sid, _dfp in (("DGS10", df10), ("DGS2", df2), ("DGS3MO", df3m),
                       ("BAMLH0A0HYM2", _df_hy_pre), ("M2SL", _df_m2_pre)):
        try:
            if _dfp is not None and not _dfp.empty:
                _last_row = _dfp.iloc[-1]
                _obs_date = str(_last_row["date"])[:10]
                _rt = _last_row.get("realtime_start")
                _rt_str = ""
                _lag = None
                try:
                    if _rt is not None and pd.notna(_rt):
                        _rt_str = str(_rt)[:10]
                        _lag = int((pd.to_datetime(_rt_str)
                                    - pd.to_datetime(_obs_date)).days)
                except Exception:
                    _rt_str = ""
                    _lag = None
                _fred_srcs[_sid] = {
                    "success": True,
                    "last_date": _obs_date,
                    "realtime_start": _rt_str,
                    "publish_lag_days": _lag,
                    "rows": int(len(_dfp)),
                }
            else:
                _fred_srcs[_sid] = {
                    "success": False, "last_date": "",
                    "realtime_start": "", "publish_lag_days": None, "rows": 0,
                }
        except Exception:
            _fred_srcs[_sid] = {
                "success": False, "last_date": "",
                "realtime_start": "", "publish_lag_days": None, "rows": 0,
            }
    R["_fred_sources"] = _fred_srcs

    if not df10.empty and not df2.empty:
        sp22 = _spread_series(df10, df2, 120)
        if len(sp22) >= 2:
            v = float(sp22.iloc[-1]); p = float(sp22.iloc[-2])
            R["YIELD_10Y2Y"] = dict(name="殖利率利差 10Y-2Y", value=round(v,3), prev=round(p,3),
                unit="%", type="領先", date=str(sp22.index[-1])[:7],
                desc="倒掛(<0)=衰退 | 由負翻正=黃金買點",
                trend=_trend(sp22.tolist()[-6:]),
                signal="🟢" if v>0.5 else ("🔴" if v<0 else "🟡"),
                color=MATERIAL_GREEN if v>0.5 else (MATERIAL_RED if v<0 else MATERIAL_ORANGE),
                score=2 if v>0.5 else (-2 if v<0 else 0),
                weight=2, series=sp22)

    if not df10.empty and not df3m.empty:
        sp3m = _spread_series(df10, df3m, 120)
        if len(sp3m) >= 2:
            v = float(sp3m.iloc[-1]); p = float(sp3m.iloc[-2])
            R["YIELD_10Y3M"] = dict(name="殖利率利差 10Y-3M", value=round(v,3), prev=round(p,3),
                unit="%", type="領先", date=str(sp3m.index[-1])[:7],
                desc="倒掛解除=降息確認 | 最強衰退預測指標",
                trend=_trend(sp3m.tolist()[-6:]),
                signal="🟢" if v>0.5 else ("🔴" if v<0 else "🟡"),
                color=MATERIAL_GREEN if v>0.5 else (MATERIAL_RED if v<0 else MATERIAL_ORANGE),
                # v19.195 A2:score 對齊同卡的 signal/color 門檻(0.5/0)+ 對齊 10Y-2Y 與
                # 台股危險線。原 `2 if v>0 else -2` 把曲線轉平(0~0.5)當滿分多頭、與燈號
                # 矛盾(燈黃卻給滿分),過度樂觀;改三段:>0.5 多頭 / 0~0.5 中性 / <0 倒掛。
                score=2 if v>0.5 else (-2 if v<0 else 0),
                weight=2, series=sp3m)

    # ── HY 信用利差 ──────────────────────────────────────────────────
    # n=2500 + tail(2500) 確保 Phase 3-B 燈號回測有 ≥60 樣本（10y 日頻）
    # v19.49：已於上方 DGS pool 並行抓取（_df_hy_pre），免重複 IO
    df = _df_hy_pre
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(2500)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        # 2026-08-05 稽核:score 收 `score_hy_spread` SSOT。旗標 OFF → 與原
        # `2 if v<4 else (-2 if v>6 else 0)` 逐點等值;ON → 追加「極緊=自滿」上緣罰則
        # (原評分只有下緣、下不封底,2.78% 這種循環極緊水位會拿最強多頭分)。
        _hy_compl_on = _score_v2_on("hy_complacency")
        _hy_compl_lo = float(_HY_THR_V2["complacency"]["complacency_below"])
        R["HY_SPREAD"] = dict(
            name="HY 信用利差 (OAS)", value=round(v,2), prev=round(p,2),
            unit="%", type="金融壓力", date=str(df.iloc[-1]["date"])[:7],
            desc=(f"≤{_hy_compl_lo:.0f}%極緊(自滿→降半檔) | <4%樂觀 | 4~6%中性 | "
                  ">6%風險 | 擴大=逃離高風險資產"
                  if _hy_compl_on else
                  "<4%樂觀 | 4~6%中性 | >6%風險 | 擴大=逃離高風險資產"),
            trend=_trend(s.tolist()[-6:]),
            signal="🟢" if v<4 else ("🔴" if v>6 else "🟡"),
            color=MATERIAL_GREEN if v<4 else (MATERIAL_RED if v>6 else MATERIAL_ORANGE),
            score=_score_hy_spread(v, max_abs=2.0),
            weight=2, series=s)

    # ── M2 ───────────────────────────────────────────────────────────
    # v19.49：已於上方 DGS pool 並行抓取（_df_m2_pre），免重複 IO
    df = _df_m2_pre
    if len(df) >= 13:
        s = df.set_index("date")["value"]
        yoy = (s / s.shift(12) - 1) * 100
        s24 = yoy.dropna().tail(120)
        v = float(s24.iloc[-1]); p = float(s24.iloc[-2]) if len(s24)>=2 else v
        R["M2"] = dict(
            name="M2 貨幣供給 (YoY)", value=round(v,2), prev=round(p,2),
            unit="%", type="流動性", date=str(df.iloc[-1]["date"])[:7],
            desc=">5%流動性寬鬆→利多 | <0%緊縮→壓力",
            trend=_trend(s24.tolist()[-6:]),
            # F-GRAY-4 v19.184: M2 score_function SSOT（easing>5 / tightening<0）
            signal="🟢" if v>_M2_EASING else ("🔴" if v<_M2_TIGHTENING else "🟡"),
            color=MATERIAL_GREEN if v>_M2_EASING else (MATERIAL_RED if v<_M2_TIGHTENING else MATERIAL_ORANGE),
            score=1 if v>_M2_EASING else (-1 if v<_M2_TIGHTENING else 0),
            # v19.404:月頻為 M2 因子的主源;週頻 WM2NS 命中時會自我降為 weight=0
            # (見下方 M2_WEEKLY 區塊),避免同因子重複計數。
            # v19.425:原有 `is_scored=True` 已刪 —— 全 repo **0 production reader**,
            #   且主源恆為 True(= 零資訊)。去重事實一律以 `superseded_by` 揭露
            #   (3 個真 reader:composite_score 兩條路徑 + daily_key_alerts),
            #   兩欄併存等於同一事實兩份編碼,會漂移(§2.1 SSOT / §8.1 step 6)。
            weight=1, series=s24)

    # v19.49 perf: SPY / RSP / DXY 三條 yfinance 並行（原 3× 序列 → max(t)）
    _yf_pre: dict = {}
    with _TPE_macro(max_workers=3) as _pool_yf:
        for _tk_pre in ("SPY", "RSP", "DX-Y.NYB"):
            _yf_pre[_tk_pre] = _pool_yf.submit(_yf_s, _tk_pre, "5y")
    # 即時 resolve（pool 結束時 future 已 done，.result() 直接拿）
    try:
        _yf_pre = {k: v.result() for k, v in _yf_pre.items()}
    except Exception as _e_yf_pre:
        print(f"[fetch_all_indicators yfinance pool] {_e_yf_pre}")
        _yf_pre = {"SPY": pd.Series(dtype=float),
                   "RSP": pd.Series(dtype=float),
                   "DX-Y.NYB": pd.Series(dtype=float)}

    # ── 市場廣度 RSP/SPY ─────────────────────────────────────────────
    try:
        s_spy = _yf_pre.get("SPY", pd.Series(dtype=float))
        s_rsp = _yf_pre.get("RSP", pd.Series(dtype=float))
        if len(s_spy)>=22 and len(s_rsp)>=22:
            ratio = (s_rsp / s_spy).dropna()
            # W5-6 §1: reindex+ffill 把 ratio 對齊 SPY 日索引(填 RSP 缺日),log 補幾筆
            _before_ratio = len(ratio)
            ratio = ratio.reindex(s_spy.index, method="ffill").dropna()
            if len(ratio) != _before_ratio:
                print(f"[macro_service ADL] ratio reindex ffill: {_before_ratio} → {len(ratio)}")
            v = round(float(ratio.iloc[-1]),4); m1 = round(float(ratio.iloc[-22]),4)
            chg = round((v-m1)/m1*100,2)
            s_w = ratio.resample("W").last().tail(260)
            R["ADL"] = dict(
                name="市場廣度 RSP/SPY", value=round(v,4), prev=round(chg,2),
                unit="", type="市場廣度",
                date=ratio.index[-1].strftime("%Y-%m-%d"),
                desc=f"等/市值比率月變{chg:+.2f}% | 上升=多頭健康 | 下降=僅七巨頭撐盤",
                trend="up" if chg>0.5 else ("down" if chg<-0.5 else "flat"),
                signal="🟢" if chg>0.5 else ("🔴" if chg<-1 else "🟡"),
                color=MATERIAL_GREEN if chg>0.5 else (MATERIAL_RED if chg<-1 else MATERIAL_ORANGE),
                score=1 if chg>0.5 else (-1 if chg<-1 else 0),
                weight=1, series=s_w)
    except Exception as e:
        print(f"[ADL] {e}")

    # ── DXY ──────────────────────────────────────────────────────────
    # v19.49：已於上方 yf pool 並行抓取
    s_dxy = _yf_pre.get("DX-Y.NYB", pd.Series(dtype=float))
    if len(s_dxy) >= 22:
        v = round(float(s_dxy.iloc[-1]),2); m1 = round(float(s_dxy.iloc[-22]),2)
        # v19.339(第五份 review Bug 3):m1=0(病態源資料)原直接 ZeroDivisionError,
        # 本區塊無 try → 炸掉後面所有指標。補守衛,對齊同檔 COPPER/cross-rate pattern。
        chg_m = round((v-m1)/m1*100, 2) if m1 else 0.0
        s_w = s_dxy.resample("W").last().tail(260)
        R["DXY"] = dict(
            name="美元指數 DXY", value=v, prev=round(chg_m,2),
            unit="", type="資金流向",
            date=s_dxy.index[-1].strftime("%Y-%m-%d"),
            desc=f"月漲跌 {chg_m:+.2f}% | 弱美元→新興市場利多 | 強美元→壓縮",
            trend="up" if chg_m>1 else ("down" if chg_m<-1 else "flat"),
            signal="🟡" if abs(chg_m)<1 else ("🟢" if chg_m<-1 else "🔴"),
            color=MATERIAL_ORANGE if abs(chg_m)<1 else (MATERIAL_GREEN if chg_m<-1 else MATERIAL_RED),
            score=1 if chg_m<-1 else (-1 if chg_m>2 else 0),
            weight=1, series=s_w)

    # ── v18.107 跨幣別 cross-rate（歐元 / 日圓 / 離岸人民幣）─────────
    # 用 yfinance forex pair（已經接 NAS proxy 中繼，不直連）
    _CROSS_RATES = [
        # (yf_ticker, snapshot_key, name, desc_low, desc_high, low_thr, high_thr)
        ("EURUSD=X", "EURUSD", "歐元/美元 EUR/USD",
         "歐元走弱→歐洲資產壓力", "歐元走強→歐美息差縮",   1.05, 1.15),
        ("JPY=X",    "USDJPY", "美元/日圓 USD/JPY",
         "日圓走強→避險升溫", "日圓貶值→carry trade", 140.0, 155.0),
        ("CNH=X",    "USDCNH", "美元/離岸人民幣 USD/CNH",
         "人民幣走強→新興市場利多", "人民幣貶值→中國壓力", 7.0, 7.3),
    ]
    # v19.46 perf: 3 個 forex pair 並行抓取（原 3× 序列 → max(t)）
    _fx_cache: dict = {}
    with _TPE_macro(max_workers=3) as _pool_fx:
        _fx_futs = {_pool_fx.submit(_yf_s, _c[0], "5y"): _c[0] for _c in _CROSS_RATES}
        for _f_x in _fx_futs:
            try:
                _fx_cache[_fx_futs[_f_x]] = _f_x.result()
            except Exception as _e_fx:
                print(f"[FX/{_fx_futs[_f_x]}] {_e_fx}")
                _fx_cache[_fx_futs[_f_x]] = pd.Series(dtype=float)
    for _tk, _key, _nm, _d_lo, _d_hi, _lo, _hi in _CROSS_RATES:
        try:
            s_fx = _fx_cache.get(_tk, pd.Series(dtype=float))
            if len(s_fx) >= 22:
                v = round(float(s_fx.iloc[-1]), 4)
                m1 = float(s_fx.iloc[-22])
                chg_m = round((v - m1) / m1 * 100, 2) if m1 else 0.0
                s_w = s_fx.resample("W").last().tail(260)
                # 強弱判斷：USDxxx pair 高=USD 強 / EURUSD 高=EUR 強
                if _key == "EURUSD":
                    sig = "🟢" if v > _hi else ("🔴" if v < _lo else "🟡")
                    score = 1 if v > _hi else (-1 if v < _lo else 0)
                else:
                    # USDJPY / USDCNH：偏高代表 USD 太強（對新興市場壓力）
                    sig = "🔴" if v > _hi else ("🟢" if v < _lo else "🟡")
                    score = -1 if v > _hi else (1 if v < _lo else 0)
                color = (MATERIAL_GREEN if sig == "🟢"
                         else (MATERIAL_RED if sig == "🔴" else MATERIAL_ORANGE))
                R[_key] = dict(
                    name=_nm, value=v, prev=round(chg_m, 2),
                    unit="", type="跨幣別",
                    date=s_fx.index[-1].strftime("%Y-%m-%d"),
                    desc=f"月漲跌 {chg_m:+.2f}% | {_d_lo} | {_d_hi}",
                    trend="up" if chg_m > 0.5 else ("down" if chg_m < -0.5 else "flat"),
                    signal=sig, color=color, score=score,
                    weight=1, series=s_w,
                )
        except Exception as _e:
            print(f"[{_key}] {_e}")

    # ── Fed 資產負債表 → v19.193 升級為「淨流動性」(WALCL − RRP − TGA) ──
    # user 2026-06-27:評分這格從「原始 Fed 資產」升級成「淨流動性」(扣掉停在 RRP /
    #   政府帳戶 TGA 的死錢),更貼近「真正進股市的錢」。算法/門檻/權重全不動(YoY% →
    #   ±5% → score),只換輸入序列。淨流動性序列走 us_liquidity_engine.net_liquidity_series
    #   SSOT(與顯示卡同源,user 要求資料 SSOT)。
    #   §1 降級:淨流動性 series 不足 53 週(TGA/RRP 史太短/缺)→ fallback 原始 WALCL YoY,
    #   指標永不消失。n=312 (6y weekly) + tail(260) = Phase 3-B 燈號回測需 ≥60 樣本。
    df = _fred_iso(FRED_FED_BS, fred_api_key, 312)
    _fedbs_name = "Fed 資產負債表 (YoY)"
    _fedbs_desc = "擴表=注入流動性→利多 | 縮表=抽走流動性→壓力"
    _s_lvl = None
    try:
        from services.us_liquidity_engine import net_liquidity_series as _nl_series
        _df_rrp = _fred(FRED_RRP, fred_api_key, 2000)   # 日頻,多抓供 52 週 YoY + 260 tail 對齊
        _df_tga = _fred(FRED_TGA, fred_api_key, 312)    # 週頻(同 WALCL 6y)
        _nl = _nl_series(df, _df_rrp, _df_tga)           # 淨流動性週序列(兆美元 T,DatetimeIndex)
        if len(_nl) >= 53:                               # YoY 需 shift(52)+1
            _s_lvl = _nl
            _fedbs_name = "淨流動性 (YoY)"
            # 2026-08-05 稽核 🔴 必修 2:desc 必須寫清楚「跌的是誰」——
            # 淨流動性轉負常常來自 TGA 重建(財政部發債補庫存,機械性/暫時性),
            # 與 Fed 主動 QT 是兩回事,不附分解就會被讀成「急速縮表」(實測誤讀)。
            _fedbs_desc = ("Fed資產−RRP−TGA=真正進股市的錢；增=利多 | 減=壓力"
                           "（升級自 Fed 資產；⚠️ 本格已非毛額 WALCL，"
                           "數字轉負≠Fed 縮表，須看下方分解）")
            _fedbs_decomp = _net_liq_decomposition(df, _df_rrp, _df_tga)
            if _fedbs_decomp:
                _fedbs_desc = f"{_fedbs_desc}｜{_fedbs_decomp}"
    except Exception as _e_nl:
        print(f"[fetch_all_indicators/net_liq] fallback gross WALCL: {type(_e_nl).__name__}: {_e_nl}")
    if _s_lvl is None and len(df) >= 53:
        _s_lvl = df.set_index("date")["value"]           # fallback：原始 WALCL level
    if _s_lvl is not None and len(_s_lvl) >= 53:
        yoy = (_s_lvl / _s_lvl.shift(52) - 1) * 100
        s24 = yoy.dropna().tail(260)
        if len(s24) >= 1:
            v = float(s24.iloc[-1]); p = float(s24.iloc[-2]) if len(s24)>=2 else v
            R["FED_BS"] = dict(
                name=_fedbs_name, value=round(v,2), prev=round(p,2),
                unit="%", type="流動性", date=str(df.iloc[-1]["date"])[:7],
                desc=_fedbs_desc,
                trend=_trend(s24.tolist()[-6:]),
                # F-GRAY-4 v19.184: Fed BS score_function SSOT（expansion>5 / contraction<-5）
                signal="🟢" if v>_FEDBS_EXPANSION else ("🔴" if v<_FEDBS_CONTRACTION else "🟡"),
                color=MATERIAL_GREEN if v>_FEDBS_EXPANSION else (MATERIAL_RED if v<_FEDBS_CONTRACTION else MATERIAL_ORANGE),
                score=1 if v>_FEDBS_EXPANSION else (-1 if v<_FEDBS_CONTRACTION else 0),
                weight=1, series=s24)

    # ── VIX ──────────────────────────────────────────────────────────
    # period=5y + tail(260) 確保 Phase 4 lag-corr 與 Phase 3-B 燈號回測樣本足
    s_vix = _yf_iso("^VIX","5y")
    if len(s_vix) >= 6:
        v = round(float(s_vix.iloc[-1]),2); p = round(float(s_vix.iloc[-6]),2)
        s_m = s_vix.resample("W").last().tail(260)
        R["VIX"] = dict(name="VIX 恐慌指數", value=v, prev=p, unit="", type="同時",
            date=s_vix.index[-1].strftime("%Y-%m-%d"),
            # v19.384:綠界回退 22→18(user 拍板),用具名 `_VIX_SNAPSHOT_CALM`(snapshot 層獨立校準,
            # 見上方常數註解);紅界維持 SSOT `_MB_VIX_RED`。
            desc=f"<{_VIX_SNAPSHOT_CALM:.0f}平靜 | >{_MB_VIX_RED:.0f}恐慌=逢低加碼時機",
            signal="🟢" if v<_VIX_SNAPSHOT_CALM else ("🔴" if v>_MB_VIX_RED else "🟡"),
            color=MATERIAL_GREEN if v<_VIX_SNAPSHOT_CALM else (MATERIAL_RED if v>_MB_VIX_RED else MATERIAL_ORANGE),
            score=1 if v<_VIX_SNAPSHOT_CALM else (-1 if v>_MB_VIX_RED else 0),
            weight=1, series=s_m)

    # ── CPI ──────────────────────────────────────────────────────────
    df = _fred_iso(FRED_CPI, fred_api_key, 144)
    if len(df) >= 14:
        s = df.set_index("date")["value"]
        yoy = (s / s.shift(12) - 1) * 100
        s24 = yoy.dropna().tail(120)
        # v19.331 review 修正:守衛檢查的是**原始 df** 長度,但 shift(12)+dropna 後
        # s24 可能只剩 <2 筆(序列短且含缺漏)→ 原 `s24.iloc[-2]` 直接 IndexError
        # 且中斷其後所有指標。對齊同檔 PPI(len>=1/len>=2 雙守衛)既有模式。
        if len(s24) >= 1:
            v = float(s24.iloc[-1])
            p = float(s24.iloc[-2]) if len(s24) >= 2 else None
            t = _trend(s24.tolist()[-6:])
            # 2026-08-05 稽核:score 收 `score_cpi` SSOT。旗標 OFF → 與原
            # `1 if 1<v<2.5 else (-1 if v>4 else 0)` 逐點等值(max_abs 保持 1.0,
            # 避免動到 causal_sankey / composite_score / explain 等**讀原始 score**
            # 的消費者);ON → 中間帶 [2.5, 4.0] 線性遞減罰則(原為完全免罰走廊)。
            _cpi_graded_on = _score_v2_on("cpi_graded")
            R["CPI"] = dict(name="CPI 通膨率 (YoY)", value=round(v,2),
                prev=round(p,2) if p is not None else None,
                unit="%", type="落後", date=str(df.iloc[-1]["date"])[:7],
                desc=("目標2% | 2.5~4% 高於目標(遞減扣分) | 高位回落=利多拐點"
                      if _cpi_graded_on else "目標2% | 高位回落=利多拐點"), trend=t,
                signal="🟢" if 1<v<2.5 else ("🔴" if v>4 else "🟡"),
                color=MATERIAL_GREEN if 1<v<2.5 else (MATERIAL_RED if v>4 else MATERIAL_ORANGE),
                score=_score_cpi(v, max_abs=1.0),
                weight=0.5, series=s24)

    # ── Fed Rate ──────────────────────────────────────────────────────
    df = _fred_iso(FRED_FED_FUNDS, fred_api_key, 144)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(120)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        R["FED_RATE"] = dict(name="聯準會利率", value=v, prev=p, unit="%", type="落後",
            date=str(df.iloc[-1]["date"])[:7], desc="降息=利多 | 升息=緊縮",
            trend=_trend(df["value"].tolist()[-8:]),
            signal="🟢" if v<p else ("🔴" if v>5 else "🟡"),
            color=MATERIAL_GREEN if v<p else (MATERIAL_RED if v>5 else MATERIAL_ORANGE),
            score=1 if v<p else (-1 if v>5 else 0),
            weight=0.5, series=s)

    # ── 失業率 ───────────────────────────────────────────────────────
    df = _fred_iso(FRED_UNRATE, fred_api_key, 144)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(120)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        R["UNEMPLOYMENT"] = dict(name="失業率", value=v, prev=p, unit="%", type="落後",
            date=str(df.iloc[-1]["date"])[:7], desc="<4.5%健康 | 上升=景氣轉差",
            trend=_trend(df["value"].tolist()[-6:]),
            signal="🟢" if v<4.5 else ("🔴" if v>6 else "🟡"),
            color=MATERIAL_GREEN if v<4.5 else (MATERIAL_RED if v>6 else MATERIAL_ORANGE),
            # v19.449 稽核 M4:score 須滿足 |score|≤weight(否則 composite 用 score×weight 未 clamp,
            # 比 calc_macro_phase 的 clamp 版多算一倍力道)。weight=0.5 → 封頂 ±0.5(對齊 NFP/LEI 修法)。
            score=0.5 if v<4.5 else (-0.5 if v>6 else 0),
            weight=0.5, series=s)

    # ── PPI ──────────────────────────────────────────────────────────
    df = _fred_iso(FRED_PPI, fred_api_key, 144)
    if len(df) >= 13:
        s = df.set_index("date")["value"]
        yoy = (s / s.shift(12) - 1) * 100
        s24 = yoy.dropna().tail(120)
        v = float(s24.iloc[-1]) if len(s24) >= 1 else 0
        p = float(s24.iloc[-2]) if len(s24) >= 2 else None
        R["PPI"] = dict(name="PPI 生產者物價 (YoY)", value=round(v,2),
            prev=round(p,2) if p else None,
            unit="%", type="領先", date=str(df.iloc[-1]["date"])[:7],
            desc="領先CPI，0~3%溫和，>5%過熱",
            trend=_trend(s24.tolist()[-6:]),
            signal="🟢" if 0<v<3 else ("🔴" if v>5 or v<-1 else "🟡"),
            color=MATERIAL_GREEN if 0<v<3 else (MATERIAL_RED if v>5 or v<-1 else MATERIAL_ORANGE),
            score=0.5 if 0<v<3 else (-0.5 if v>5 else 0),
            weight=0.5, series=s24)

    # ── 銅博士 ────────────────────────────────────────────────────────
    s_cu = _yf_iso("HG=F","5y")
    if len(s_cu) >= 22:
        now = float(s_cu.iloc[-1]); prev = float(s_cu.iloc[-22])
        chg = round((now-prev)/prev*100, 2) if prev else 0
        monthly = s_cu.resample("ME").last().pct_change(fill_method=None)*100  # §1 不補值
        R["COPPER"] = dict(name="銅博士（月漲跌）", value=chg, prev=None,
            unit="% MoM", type="領先",
            date=s_cu.index[-1].strftime("%Y-%m-%d"),
            desc=f"現價 {now:.3f} USD/lb | 漲=工業需求增",
            signal="🟢" if chg>2 else ("🔴" if chg<-5 else "🟡"),
            color=MATERIAL_GREEN if chg>2 else (MATERIAL_RED if chg<-5 else MATERIAL_ORANGE),
            score=0.5 if chg>2 else (-0.5 if chg<-5 else 0),
            weight=0.5, series=monthly.dropna().tail(60))

    # ── 消費者信心 ────────────────────────────────────────────────────
    df = _fred_iso(FRED_UMCSENT, fred_api_key, 144)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(120)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        R["CONSUMER_CONF"] = dict(name="消費者信心 (Michigan)", value=v, prev=p,
            unit="", type="領先", date=str(df.iloc[-1]["date"])[:7],
            desc="上升=消費回升，>85樂觀，<60悲觀",
            trend=_trend(df["value"].tolist()[-6:]),
            signal="🟢" if v>80 else ("🔴" if v<60 else "🟡"),
            color=MATERIAL_GREEN if v>80 else (MATERIAL_RED if v<60 else MATERIAL_ORANGE),
            score=0.5 if v>80 else (-0.5 if v<60 else 0),
            weight=0.5, series=s)

    # ── 初領失業金 ────────────────────────────────────────────────────
    # n=312 (6y weekly) + tail(260) = Phase 3-B 燈號回測 ≥60 樣本
    df = _fred_iso(FRED_ICSA, fred_api_key, 312)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(260)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        # value/prev 統一以「萬人」為單位（與 series 一致），避免 Z-Score 與 AI Prompt 單位錯位
        R["JOBLESS"] = dict(name="初領失業金 (週)", value=round(v/10000, 1), prev=round(p/10000, 1),
            unit="萬人", type="領先", date=str(df.iloc[-1]["date"])[:10],
            desc="下降=就業好轉，<23萬健康，>30萬警戒",
            trend=_trend(df["value"].tolist()[-8:]),
            signal="🟢" if v<230000 else ("🔴" if v>300000 else "🟡"),
            color=MATERIAL_GREEN if v<230000 else (MATERIAL_RED if v>300000 else MATERIAL_ORANGE),
            score=0.5 if v<230000 else (-0.5 if v>300000 else 0),
            weight=0.5, series=s/10000)

    # ── 新屋銷售 ──────────────────────────────────────────────────────
    df = _fred_iso(FRED_HSN1F, fred_api_key, 144)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(120)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        R["NEW_HOME"] = dict(name="新屋銷售", value=v, prev=p, unit="千戶", type="領先",
            date=str(df.iloc[-1]["date"])[:7], desc=f"月增{v-p:+.0f}k | 增加=房市回升",
            trend=_trend(df["value"].tolist()[-6:]),
            signal="🟢" if v>p else "🔴", color=MATERIAL_GREEN if v>p else MATERIAL_RED,
            score=0.5 if v>p else -0.5,
            weight=0.5, series=s)

    # ── 薩姆規則（Sahm Rule Recession Indicator）──────────────────────
    df = _fred_iso(FRED_SAHM, fred_api_key, 144)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(120)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        R["SAHM"] = dict(name="薩姆規則", value=v, prev=p, unit="pp", type="領先",
            date=str(df.iloc[-1]["date"])[:7],
            desc="≥0.5 觸發衰退警報 | <0.3 安全 | 3月失業率均值-12月最低",
            trend=_trend(df["value"].tolist()[-6:]),
            signal="🔴" if v >= 0.5 else ("🟡" if v >= 0.3 else "🟢"),
            color=MATERIAL_RED if v >= 0.5 else (MATERIAL_ORANGE if v >= 0.3 else MATERIAL_GREEN),
            score=-1.5 if v >= 0.5 else (-0.5 if v >= 0.3 else 1),  # v19.449 M4:−2→−1.5 (|score|≤weight)
            weight=1.5, series=s)

    # ── SLOOS 銀行放貸標準（Senior Loan Officer Survey）──────────────
    # 季頻 (quarterly)：n=80 (20y)、tail(60) (15y) → Phase 3-B ≥60 樣本
    df = _fred_iso(FRED_DRTSCILM, fred_api_key, 80)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(60)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        # 正值=銀行收緊放貸(壞)，負值=放寬(好)
        R["SLOOS"] = dict(name="SLOOS 放貸標準", value=v, prev=p, unit="%", type="領先",
            date=str(df.iloc[-1]["date"])[:7],
            desc=">20% 銀行大幅緊縮信貸（衰退前兆）| <0% 信貸寬鬆",
            trend=_trend(df["value"].tolist()[-4:]),
            signal="🔴" if v > 20 else ("🟡" if v > 0 else "🟢"),
            color=MATERIAL_RED if v > 20 else (MATERIAL_ORANGE if v > 0 else MATERIAL_GREEN),
            score=-1.5 if v > 30 else (-1 if v > 20 else (0.5 if v < 0 else -0.5)),  # v19.449 M4:−2→−1.5
            weight=1.5, series=s)

    # ════════════════════════════════════════════════════════════════
    # v16.1 高頻替代資料源（A+B 路線：補位月度資料延遲）
    # 設計：以下指標是「主源延遲時的高頻補位」，皆與既有指標平行存在
    # ════════════════════════════════════════════════════════════════

    # ── LEI 領先指標（CFNAI 芝加哥聯儲全國活動指數）────────────────
    # ⚠️ USSLIND（Philadelphia Fed Leading Index）已於 2020 COVID 期間因方法論
    #    失效永久停更（最後資料 2020-02），改用 CFNAI 作為等價替代：
    #    CFNAI 月頻活躍發布，匯總 85 個月度經濟指標，z-score 標準化後
    #    平均值=0，標準差=1。三月均值 < -0.7 強烈衰退訊號。
    # 注意：CFNAI 數值意涵與 USSLIND 不同，閾值與描述已對應調整。
    # v19.404 稽核修正（三重錯誤，全部依 Chicago Fed 官方 background PDF 校正）：
    #   1. 門檻基準錯：-0.70 是為 **CFNAI-MA3** 校準的，原碼卻拿去砍月度 `v`。月度序列
    #      波動度約為 MA3 的 √3 ≈ 1.7 倍 → 假衰退訊號大量增加。改以 `v_ma3` 判讀。
    #   2. 擴張門檻缺席：官方是「衰退 -0.70 / 擴張 +0.20」的**非對稱含遲滯**設計，
    #      原碼只有單邊（且綠界用腦補的 0.0 / desc 寫「> +0.7 強勁擴張」查無官方出處）。
    #   3. 幅度超出 weight：原 score 可到 -2 但 weight=1 → `calc_macro_phase` 會 clamp、
    #      `composite_score.calculate_composite_score` 不 clamp，同分數兩路徑不一致。
    #      現在全 tier |score| ≤ weight(1.0)。
    # 官方原文：
    #   "an increasing likelihood of a recession has historically been associated with a
    #    CFNAI-MA3 value below -0.70 ... a significant likelihood of an expansion has
    #    historically been associated with a CFNAI-MA3 value above +0.20."
    #   零點語意："A zero value for the index indicates that the national economy is
    #    expanding at its historical trend rate of growth."
    #   https://www.chicagofed.org/-/media/publications/cfnai/background/cfnai-background-pdf.pdf
    #   現值(2026-06)：CFNAI = -0.02 / CFNAI-MA3 = -0.05
    #   https://www.chicagofed.org/research/data/cfnai/current-data
    # ⚠️ 常見誤用：-0.35 是 **CFNAI Diffusion Index**（另一條擴散序列）的擴張門檻，
    #    與 CFNAI 水準值無關 —— 已於 `shared/macro_buckets.py` 一併移除。
    # 【為何不改抓 FRED CFNAIMA3】下方 `s.rolling(3).mean()` 逐式等於 CFNAI-MA3 的定義
    #   （MA3 = 月度 CFNAI 的 3 期移動平均），多抓一條 series 只是多一次 IO 與一個
    #   新 fallback 面，對當前需求是「用不到的抽象」(§8.1 step 6)。同時 `value`/`series`
    #   維持月度基準才與 Z-Score 矩陣（value vs series 同尺度，見
    #   tests/test_indicator_scale_consistency.py）一致；MA3 以獨立欄位 `ma3`/`ma3_prev` 揭露。
    df = _fred_iso(FRED_CFNAI, fred_api_key, 144)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(120)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        # CFNAI 三月均值（CFNAI-MA3 = 官方衰退/擴張門檻的正確基準）
        _ma3_valid = s.rolling(3).mean().dropna()
        v_ma3 = float(_ma3_valid.iloc[-1]) if len(_ma3_valid) >= 1 else v
        v_ma3_prev = float(_ma3_valid.iloc[-2]) if len(_ma3_valid) >= 2 else None
        # 下方 inline 的 -0.7 / 0.0 為 SSOT `CFNAI_RECESSION_THRESHOLD` /
        # `CFNAI_TREND_GROWTH` 的字面鏡像 —— `tests/test_card_threshold_drift.py`
        # 要求 MACRO_THRESHOLDS["LEI"] 門檻須以字面值出現在本區塊（同 SAHM 既有慣例）；
        # 字面值與 SSOT 的相等性由 `tests/test_macro_indicator_signs.py` 釘死。
        R["LEI"] = dict(name="CFNAI 領先指標", value=round(v,2), prev=round(p,2),
            ma3=round(v_ma3, 2),
            ma3_prev=(round(v_ma3_prev, 2) if v_ma3_prev is not None else None),
            unit="", type="領先", date=str(df.iloc[-1]["date"])[:7],
            desc=f"芝加哥聯儲全國活動指數（85 指標 z-score）| 燈號/評分以 3M均值"
                 f"={v_ma3:+.2f} 判讀（官方 CFNAI-MA3 基準）"
                 f"| > +{CFNAI_MA3_EXPANSION_THRESHOLD:.2f} 擴張確認 | 0 = 歷史趨勢成長 "
                 f"| < -0.7 衰退預警 | PMI 替代源",
            trend=_trend(df["value"].tolist()[-6:]),
            signal=("🟢" if v_ma3 > CFNAI_MA3_EXPANSION_THRESHOLD
                    else ("🔴" if v_ma3 < -0.7 else "🟡")),
            color=(MATERIAL_GREEN if v_ma3 > CFNAI_MA3_EXPANSION_THRESHOLD
                   else (MATERIAL_RED if v_ma3 < -0.7 else MATERIAL_ORANGE)),
            # +1.0 官方擴張 / +0.5 高於趨勢未達擴張 / -0.5 低於趨勢 / -1.0 官方衰退
            score=(1.0 if v_ma3 > CFNAI_MA3_EXPANSION_THRESHOLD
                   else (-1.0 if v_ma3 < -0.7
                         else (0.5 if v_ma3 > 0.0 else -0.5))),
            weight=1, series=s)

    # ── CONT_CLAIMS 持續失業金（CCSA，週頻）──────────────────────
    # UNEMPLOYMENT 月度延遲時的高頻替代；與 ICSA(初領)互補：CCSA=尚未找到工作的人數
    df = _fred_iso(FRED_CCSA, fred_api_key, 312)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(260)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        # value/prev 統一以「萬人」為單位（與 series=s/10000 一致），避免 Z-Score 與 AI Prompt
        # 單位錯位（對齊上方 ICSA/JOBLESS 既有正確寫法）。原本 value=int(v) 為原始人數
        # （~1,821,000）但 series 已 /10000（~182 萬人）→ Z=(1.82M-182)/std≈+57000 爆量,
        # Z-Score 矩陣顯示「值 1821000 萬、Z=+57324」假極端,並汙染「就業」子循環評分。
        # signal/color/score 維持用原始 v（門檻 1.7M/1.9M 人數）不受影響。
        R["CONT_CLAIMS"] = dict(name="持續失業金 (週)", value=round(v/10000, 1), prev=round(p/10000, 1),
            unit="萬人", type="領先", date=str(df.iloc[-1]["date"])[:10],
            desc="尚在領失業金人數 | <170 萬健康 | >190 萬警戒 | 失業率月延遲時看這顆",
            trend=_trend(df["value"].tolist()[-8:]),
            signal="🟢" if v < 1700000 else ("🔴" if v > 1900000 else "🟡"),
            color=MATERIAL_GREEN if v < 1700000 else (MATERIAL_RED if v > 1900000 else MATERIAL_ORANGE),
            score=0.5 if v < 1700000 else (-0.5 if v > 1900000 else 0),
            weight=0.5, series=s/10000)

    # ── M2_WEEKLY 週頻 M2（WM2NS）─────────────────────────────────
    # M2 月度延遲時的補位；YoY 計算用 52 週前的數據對比
    #
    # v19.404 稽核修正（重複計數）：WM2NS 與 M2SL 是**同一個經濟因子**的兩種取樣，
    #   原碼兩者各自 `weight=1` 且平行進入所有加權路徑
    #   （`calc_macro_phase` 分子分母 / `composite_score.calculate_composite_score` /
    #    `ui/helpers/macro/helpers._CATEGORY_MAP["💧 流動性"]` 同時列 M2 與 M2_WEEKLY），
    #   等於同一因子被計兩次；又因 SA/NSA 與月/週取樣差異，兩者 Z 值可反向
    #   （線上實測 M2_WEEKLY Z=+0.55 vs M2 Z=-0.11）→ 互相抵銷，流動性訊號被稀釋。
    #   本模組 docstring 早已言明「高頻**替代**源」——「替代」的語意就是取代而非疊加。
    #
    #   修法（對齊 §2.1「第一命中即用、禁止平均」）：月頻 M2 命中 → 週頻降為
    #   **顯示專用**（`weight=0` → 不進任何加權分母/分子），月頻缺漏才由週頻遞補計分。
    #   選 weight=0 而非「不輸出」，是因為 Z-Score 矩陣 / 資料看板 / 教學卡都直接讀
    #   `indicators["M2_WEEKLY"]`（`ui/tab1_macro_midcycle.py:95` 等），拔掉會讓那些
    #   面板整格消失；weight=0 只切斷評分、不動顯示。
    #   實際採用哪一個以 `superseded_by` 揭露（§2.2 provenance；機器可讀，3 個
    #   production reader：composite_score 的加權/投票兩條 + daily_key_alerts）
    #   ＋ `desc` 尾綴的中文說明（人可讀，直接顯示在教學卡 / Z-Score 矩陣上）。
    #   v19.425：原併存的 `is_scored` 已刪 —— 全 repo 0 production reader，
    #   且恆等於 `superseded_by is None`（同一事實兩份編碼，必然漂移）。
    #   §2.1 SSOT ＋ §8.1 step 6「用不到的抽象先不做」。
    df = _fred_iso(FRED_M2_WEEKLY, fred_api_key, 520)
    if len(df) >= 53:
        s_full = df.set_index("date")["value"]
        yoy = (s_full / s_full.shift(52) - 1) * 100
        s24 = yoy.dropna().tail(260)
        if len(s24) >= 2:
            v = float(s24.iloc[-1]); p = float(s24.iloc[-2])
            _m2_monthly_hit = isinstance(R.get("M2"), dict)
            if _m2_monthly_hit:
                print("[M2] 月頻 M2SL 已命中 → M2_WEEKLY(WM2NS) 降為顯示專用 "
                      "weight=0（同因子不重複計分）")
            R["M2_WEEKLY"] = dict(name="M2 週頻 (YoY)", value=round(v,2), prev=round(p,2),
                unit="%", type="流動性", date=str(df.iloc[-1]["date"])[:10],
                desc=("WM2NS 週頻 | M2 月版延遲時的最即時替代 | 同樣 >5%寬鬆 / <0%緊縮 | "
                      + ("⚠️ 月頻 M2 已命中，本格僅供顯示、不計入加權分"
                         if _m2_monthly_hit else "✅ 月頻 M2 缺漏，本格遞補計分")),
                trend=_trend(s24.tolist()[-6:]),
                signal="🟢" if v > 5 else ("🔴" if v < 0 else "🟡"),
                color=MATERIAL_GREEN if v > 5 else (MATERIAL_RED if v < 0 else MATERIAL_ORANGE),
                score=1 if v > 5 else (-1 if v < 0 else 0),
                # 月頻命中 → weight=0（顯示保留、評分歸零）；否則遞補為 1
                weight=(0 if _m2_monthly_hit else 1),
                superseded_by=("M2" if _m2_monthly_hit else None),
                series=s24)
        # 週頻缺漏時，月頻 M2 本來就在評分內，無須額外處理（§1 不補假值）

    # ── INFL_EXP_5Y 5Y 通膨預期（T5YIE，日頻）─────────────────────
    # CPI 月度延遲時的高頻補位；債市每日交易計算的 5 年期 breakeven
    df = _fred_iso(FRED_T5YIE, fred_api_key, 2500)
    if len(df) >= 22:
        s = df.set_index("date")["value"].tail(2500)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-22]["value"])
        R["INFL_EXP_5Y"] = dict(name="5Y 通膨預期 (日)", value=round(v,2), prev=round(p,2),
            unit="%", type="領先", date=str(df.iloc[-1]["date"])[:10],
            desc="債市每日交易計算 | Fed 目標 2-2.5% | >3% 通膨失控擔憂 | CPI 月延遲時看這顆",
            trend=_trend(df["value"].tolist()[-22:][::4]),
            signal="🟢" if 1.5 < v < 2.8 else ("🔴" if v > 3.5 else "🟡"),
            color=MATERIAL_GREEN if 1.5 < v < 2.8 else (MATERIAL_RED if v > 3.5 else MATERIAL_ORANGE),
            score=1 if 1.5 < v < 2.8 else (-1 if v > 3.5 else 0),
            weight=1, series=s)

    # ── PERMIT_HOUSING 建照核發（PERMIT）──────────────────────────
    # NEW_HOME（新屋銷售）的領先指標：建商先拿建照才開工再銷售，PERMIT 早 1-2 個月反映
    df = _fred_iso(FRED_PERMIT, fred_api_key, 144)
    if len(df) >= 2:
        s = df.set_index("date")["value"].tail(120)
        v = float(df.iloc[-1]["value"]); p = float(df.iloc[-2]["value"])
        R["PERMIT_HOUSING"] = dict(name="建照核發", value=v, prev=p, unit="千戶",
            type="領先", date=str(df.iloc[-1]["date"])[:7],
            desc=f"月增{v-p:+.0f}k | 領先新屋銷售 1-2 個月 | >150 萬健康 | <120 萬房市疲弱",
            trend=_trend(df["value"].tolist()[-6:]),
            signal="🟢" if v > 1500 else ("🔴" if v < 1200 else "🟡"),
            color=MATERIAL_GREEN if v > 1500 else (MATERIAL_RED if v < 1200 else MATERIAL_ORANGE),
            score=0.5 if v > 1500 else (-0.5 if v < 1200 else 0),
            weight=0.5, series=s)

    # ── NFP 非農新增就業 v19.17（v19.404 符號修正）──────────────────
    # PAYEMS 是「就業人口總數」，市場關注的「非農新增」是月變動量（千人）
    df = _fred_iso(FRED_PAYEMS, fred_api_key, 144)
    if len(df) >= 3:
        s_full = df.set_index("date")["value"]
        # 月變動（單位：千人，PAYEMS 原始單位就是千人）
        s_delta = s_full.diff().dropna().tail(120)
        cur_d = float(s_delta.iloc[-1])
        prev_d = float(s_delta.iloc[-2])
        score_nfp, sig_nfp, col_nfp = _nfp_tier(cur_d)
        R["NFP"] = dict(
            name="非農新增就業（月變動）", value=round(cur_d, 0), prev=round(prev_d, 0),
            unit="千人", type="同時", date=str(df.iloc[-1]["date"])[:7],
            desc=(f"本月 {cur_d:+.0f}k | 上月 {prev_d:+.0f}k | "
                  f"<0 衰退🔴 / <{_NFP_COLD_K:.0f}k 偏冷🟠 / "
                  f"{_NFP_COLD_K:.0f}-{_NFP_NEUTRAL_K:.0f}k 中性🟡 / "
                  f"{_NFP_NEUTRAL_K:.0f}-{_NFP_STRONG_K:.0f}k 強勁🟢 / "
                  f">{_NFP_STRONG_K:.0f}k 過熱🟡(Fed 緊縮風險)"),
            trend=_trend(s_delta.tolist()[-6:]),
            signal=sig_nfp, color=col_nfp,
            score=score_nfp, weight=1.0,
            series=s_delta,
        )

    return R
def get_market_phase(indicators: dict) -> dict:
    """
    二維景氣位階判定（說明書 §3）：Z-Score 位階 × 線性斜率方向
    ─────────────────────────────────────────────────────────────
    以 PMI 為主要代表指標（最高權重領先指標），結合 Z-Score 與 trend_slope：

      復甦 (Recovery) : Z 低位(< -0.5) + Slope 轉正(> +0.05)
      擴張 (Expansion): Z 中位         + Slope 為正(> 0)
      減速 (Slowdown) : Z 高位(> +0.5) + Slope 轉負(< -0.05) ← 關鍵拐點
      衰退 (Recession): Z 低位         + Slope 為負(< 0)

    回傳字典可直接補充至 calc_macro_phase() 輸出，作為第二層確認。
    """
    def _get(key, attr): return (indicators.get(key) or {}).get(attr)

    # ── 以 PMI + YIELD_10Y2Y + HY_SPREAD 三個領先指標投票
    _phases = []
    for _key in ("PMI", "YIELD_10Y2Y", "HY_SPREAD"):
        _z  = _get(_key, "z_score")
        _sl = _get(_key, "trend_slope")
        if _z is None or _sl is None:
            continue
        # 反向指標（HY 利差越大越壞）
        _inv = -1 if _key == "HY_SPREAD" else 1
        _z_adj  = _z  * _inv
        _sl_adj = _sl * _inv

        if _z_adj < -0.5 and _sl_adj > 0.05:
            _phases.append("復甦")
        elif _z_adj > 0.5 and _sl_adj < -0.05:
            _phases.append("減速")   # 最重要的高位轉負訊號
        elif _sl_adj > 0:
            _phases.append("擴張")
        else:
            _phases.append("衰退")

    if not _phases:
        return {"phase2d": "未知", "phase2d_color": TRAFFIC_NEUTRAL, "phase2d_desc": "資料不足"}

    # 多數決
    from collections import Counter
    _winner = Counter(_phases).most_common(1)[0][0]
    _vote_ratio = Counter(_phases).most_common(1)[0][1] / len(_phases)

    _map = {
        "復甦": (MD_BLUE_300, "Z 低位 + 斜率翻正，景氣底部確認，逢低布局機會"),
        "擴張": (MATERIAL_GREEN, "Z 中位 + 斜率向上，成長動能充足，持有風險資產"),
        "減速": (MATERIAL_ORANGE, "Z 高位 + 斜率轉負，擴張減速拐點！考慮調降衛星比重"),
        "衰退": (MATERIAL_RED, "Z 低位 + 斜率向下，景氣收縮，轉向防禦配置"),
    }
    _color, _desc = _map.get(_winner, (TRAFFIC_NEUTRAL, ""))
    return {
        "phase2d":        _winner,
        "phase2d_color":  _color,
        "phase2d_desc":   _desc,
        "phase2d_votes":  dict(Counter(_phases)),
        "phase2d_conf":   round(_vote_ratio * 100),
    }


def calc_growth_inflation_axis(indicators: dict) -> dict:
    """
    成長/通膨雙軸分析（文件建議 §1：二象限循環判定）
    ─────────────────────────────────────────────────
    Growth Axis  : PMI, 殖利率曲線, M2, 市場廣度, 消費者信心, 初領失業金, 銅博士
    Inflation Axis: CPI, PPI, Fed Rate
    ─────────────────────────────────────────────────
    四象限:
      復甦/擴張 (Goldilocks): 成長↑ 通膨↓
      過熱 (Overheat)       : 成長↑ 通膨↑
      滯脹 (Stagflation)    : 成長↓ 通膨↑
      衰退 (Recession)      : 成長↓ 通膨↓
    """
    def _get(key, attr="value"):
        return (indicators.get(key) or {}).get(attr)

    # ── Growth signals（正=成長向上，負=成長向下）
    growth_signals = []
    pmi_v = _get("PMI")
    if pmi_v is not None:
        growth_signals.append(1 if pmi_v >= _PMI_GROWTH_EXPANSION else -1)

    y22 = _get("YIELD_10Y2Y")
    if y22 is not None:
        growth_signals.append(1 if y22 >= 0 else -1)

    m2_v = _get("M2")
    if m2_v is not None:
        growth_signals.append(1 if m2_v >= 3 else -1)

    adl_chg = _get("ADL", "prev")  # prev = monthly change %
    if adl_chg is not None:
        growth_signals.append(1 if adl_chg >= 0 else -1)

    conf_v = _get("CONSUMER_CONF")
    if conf_v is not None:
        growth_signals.append(1 if conf_v >= 70 else -1)

    jobless_v = _get("JOBLESS")
    if jobless_v is not None:
        # JOBLESS 已統一單位為「萬人」（28 萬 = 過去的 280000）
        growth_signals.append(1 if jobless_v < 28 else -1)

    copper_v = _get("COPPER")  # monthly change %
    if copper_v is not None:
        growth_signals.append(1 if copper_v >= 0 else -1)

    # ── Inflation signals（正=通膨偏高，負=通膨受控）
    inflation_signals = []
    cpi_v = _get("CPI")
    if cpi_v is not None:
        inflation_signals.append(1 if cpi_v >= 3.0 else -1)

    ppi_v = _get("PPI")
    if ppi_v is not None:
        inflation_signals.append(1 if ppi_v >= 3.0 else -1)

    fed_v = _get("FED_RATE")
    if fed_v is not None:
        inflation_signals.append(1 if fed_v >= 4.0 else -1)

    # ── 計算平均訊號分數（-1 ~ +1）
    growth_score    = sum(growth_signals)    / max(len(growth_signals), 1)
    inflation_score = sum(inflation_signals) / max(len(inflation_signals), 1)
    growth_up    = growth_score > 0
    inflation_up = inflation_score > 0

    # ── 四象限映射
    if growth_up and not inflation_up:
        quadrant    = "復甦/擴張"; quadrant_en = "Goldilocks"
        quad_color  = MATERIAL_GREEN;   quad_icon   = "🌱"
        quad_desc   = "成長↑ 通膨↓ — 黃金期，積極持有風險資產"
        quad_alloc  = "衛星成長型↑  核心配息↑  現金↓"
    elif growth_up and inflation_up:
        quadrant    = "過熱";      quadrant_en = "Overheat"
        quad_color  = MATERIAL_ORANGE;   quad_icon   = "🔥"
        quad_desc   = "成長↑ 通膨↑ — 景氣高峰，注意泡沫與緊縮風險"
        quad_alloc  = "實物資產↑  高息防禦↑  成長型↓"
    elif not growth_up and inflation_up:
        quadrant    = "滯脹";      quadrant_en = "Stagflation"
        quad_color  = MATERIAL_RED;   quad_icon   = "⚠️"
        quad_desc   = "成長↓ 通膨↑ — 最惡劣環境，降低股票，持有商品與短債"
        quad_alloc  = "商品/黃金↑  短天期債↑  成長股↓↓"
    else:
        quadrant    = "衰退";      quadrant_en = "Recession"
        quad_color  = MATERIAL_ORANGE;   quad_icon   = "🌧️"
        quad_desc   = "成長↓ 通膨↓ — 景氣收縮，轉向長債與防禦型配置"
        quad_alloc  = "長天期債↑↑  防禦股息↑  現金↑  成長股↓"

    return {
        "growth_score":     round(growth_score, 2),
        "inflation_score":  round(inflation_score, 2),
        "growth_up":        growth_up,
        "inflation_up":     inflation_up,
        "quadrant":         quadrant,
        "quadrant_en":      quadrant_en,
        "quad_color":       quad_color,
        "quad_icon":        quad_icon,
        "quad_desc":        quad_desc,
        "quad_alloc":       quad_alloc,
        "n_growth":         len(growth_signals),
        "n_inflation":      len(inflation_signals),
    }


def calc_macro_phase(indicators: dict) -> dict:
    """
    AI Macro Score 加權評分（機構級 v7）
    ─────────────────────────────────────────────────
    指標                    weight    分值
    殖利率曲線 10Y-2Y          2      ±2
    殖利率曲線 10Y-3M          2      ±2
    PMI                       2      ±2
    HY 信用利差                2      ±2
    M2 流動性                  1      ±1
    市場廣度 RSP/SPY           1      ±1
    Fed 資產負債表             1      ±1
    DXY 美元指數               1      ±1
    VIX 恐慌指數               1      ±1
    CPI 通膨                  0.5     ±0.5
    Fed Rate                 0.5     ±0.5
    失業率                    0.5     ±0.5
    ─────────────────────────────────────────────────
    最大可能 ≈ 14 → 正規化到 0~10
    景氣判斷：0~2衰退 | 3~4復甦 | 5~7擴張 | 8~10高峰

    ⚠️ **`_` 前綴 key 為 meta,不參與計算**(v19.404 稽核修正)
    `fetch_all_indicators` 除了指標外還會塞 provenance meta(目前只有 `_fred_sources`,
    5 條 FRED series 的命中狀態 dict)。這類 meta **沒有 `weight` / `score` 欄**,
    舊寫法 `ind.get("weight", 1)` 會給它預設 w=1 → 被當成一個「w=1 / s=0 的指標」
    計入 `total_w` 分母,而 `earned_w` 分子拿 0 → 正規化式
    `(earned_w + total_w) / (2*total_w)` 的分母被灌水,**所有分數被系統性拉向中性 5.0**
    (權重總和 ~19 時,單一 meta 就讓極端分往 5.0 收斂約 0.13 分;若未來 meta 變多會更嚴重)。
    另同時排除非 dict 值(防呆),避免 `.get` AttributeError。
    新增 meta 一律用 `_` 前綴,自動被本迴圈與 `_build_phase_provenance` 排除。
    """
    # 加權加總
    total_w = 0; earned_w = 0
    for key, ind in indicators.items():
        # v19.425:述詞收 SSOT(composite_score.is_meta_key),行為與原 inline 相同
        if _is_meta_key(key) or not isinstance(ind, dict):
            continue   # v19.404:meta(如 _fred_sources)不是指標,禁止污染權重分母
        w = ind.get("weight", 1)
        s = ind.get("score", 0)
        # 確保 score 不超過 weight
        s = max(-w, min(w, s))
        total_w += w
        earned_w += s

    # 正規化：把 [-total_w, +total_w] 映射到 [0, 10]
    if total_w > 0:
        norm = (earned_w + total_w) / (2 * total_w) * 10
    else:
        norm = 5
    score = round(max(0, min(10, norm)), 1)

    # ─── 修正後的景氣門檻 ───
    if score >= 8:
        phase = "高峰"; phase_en = "Peak"; phase_color = MATERIAL_RED
        alloc = dict(股票=35, 債券=45, 現金=20)
        advice = "高峰期：適度獲利了結，轉向防禦型資產"
        strategy = "逐步減碼高估值成長股，增加投資等級債與黃金"
    elif score >= 5:
        phase = "擴張"; phase_en = "Expansion"; phase_color = MATERIAL_GREEN
        alloc = dict(股票=60, 債券=30, 現金=10)
        advice = "股優於債：核心高股息ETF + 衛星AI/半導體，設嚴格停利點"
        strategy = "持有核心配息資產，衛星資產設15%停利出場"
    elif score >= 3:
        phase = "復甦"; phase_en = "Recovery"; phase_color = MD_BLUE_300
        alloc = dict(股票=40, 債券=40, 現金=20)
        advice = "復甦期：最高勝率買點！逐步加碼，優先佈局高股息與平衡型"
        strategy = "積極佈局中小型成長股、非必需消費、金融股底部"
    else:
        phase = "衰退"; phase_en = "Recession"; phase_color = MATERIAL_ORANGE
        alloc = dict(股票=20, 債券=50, 現金=30)
        advice = "衰退期：保守為主，等待落後指標見頂為進場訊號"
        strategy = "保留現金，等待PMI落底與殖利率曲線翻正"

    # 衰退機率
    sp3m = indicators.get("YIELD_10Y3M", {}).get("value")
    rec_prob = None
    if sp3m is not None:
        import math
        logit = RECESSION_LOGIT_COEF_SPREAD * sp3m + RECESSION_LOGIT_COEF_INTERCEPT
        rec_prob = round(1 / (1 + math.exp(-logit)) * 100, 1)

    # 風險警報
    alerts = []
    if indicators.get("YIELD_10Y2Y",{}).get("value", 1) < 0:
        alerts.append("⚠️ 殖利率曲線倒掛（衰退前兆）")
    if indicators.get("HY_SPREAD",{}).get("value", 4) > _HY_YELLOW:
        alerts.append(f"⚠️ 信用利差>{_HY_YELLOW:.0f}% — 市場恐慌升溫")
    if indicators.get("PMI",{}).get("value", _PMI_ALERT_CONTRACT) < _PMI_ALERT_CONTRACT:
        alerts.append(f"⚠️ PMI 跌破 {_PMI_ALERT_CONTRACT:.0f} — 製造業收縮")
    if indicators.get("VIX",{}).get("value", 18) > _MB_VIX_YELLOW:
        alerts.append(f"⚠️ VIX>{_MB_VIX_YELLOW:.0f} — 市場恐慌升溫,注意波動")
    if indicators.get("CPI",{}).get("value", 2) > 4:
        alerts.append("⚠️ 通膨偏高 — Fed 緊縮壓力")
    if indicators.get("M2",{}).get("value", 3) < 0:
        alerts.append("⚠️ M2 負成長 — 流動性緊縮")
    if indicators.get("ADL",{}).get("prev", 0) < -1:
        alerts.append("⚠️ 市場廣度惡化 — 僅少數股支撐指數")
    if rec_prob and rec_prob > 60:
        alerts.append(f"🔴 衰退機率 {rec_prob:.0f}% — 高度警戒")

    # 拐點偵測
    mk_signals = _detect_inflection(indicators)

    # ── 拐點轉向判斷 ─────────────────────────────────────
    PHASE_ORDER = ["衰退", "復甦", "擴張", "高峰"]
    infl_score = mk_signals.get("infl_score", 0)
    ph_idx = PHASE_ORDER.index(phase)

    if infl_score >= 5:         # 多項買進訊號齊發 → 向上轉
        next_phase = PHASE_ORDER[(ph_idx + 1) % 4]
        trend_arrow = "↗"
        trend_label = "向上轉折（加速）"
        trend_color = MATERIAL_GREEN
    elif infl_score >= 2:       # 偏多觀察 → 偏向上
        next_phase = PHASE_ORDER[(ph_idx + 1) % 4]
        trend_arrow = "→↗"
        trend_label = "偏向上（觀察中）"
        trend_color = MD_GREEN_A200
    elif infl_score <= -5:      # 多項空頭訊號 → 向下轉
        next_phase = PHASE_ORDER[(ph_idx - 1) % 4]
        trend_arrow = "↘"
        trend_label = "向下轉折（警示）"
        trend_color = MATERIAL_RED
    elif infl_score <= -2:      # 偏空謹慎 → 偏向下
        next_phase = PHASE_ORDER[(ph_idx - 1) % 4]
        trend_arrow = "→↘"
        trend_label = "偏向下（謹慎）"
        trend_color = MD_DEEP_ORANGE_400
    else:                       # 中性整理
        next_phase = phase
        trend_arrow = "→"
        trend_label = "持穩整理"
        trend_color = TRAFFIC_NEUTRAL

    # ── 各景氣位階配置 Map（供拐點轉換顯示）────────────────
    ALLOC_MAP = {
        "復甦": dict(股票=40, 債券=40, 現金=20),
        "擴張": dict(股票=60, 債券=30, 現金=10),
        "高峰": dict(股票=35, 債券=45, 現金=20),
        "衰退": dict(股票=20, 債券=50, 現金=30),
    }
    cur_idx  = ph_idx  # 複用已計算的 ph_idx，消除重複定義
    next_p   = PHASE_ORDER[(cur_idx + 1) % 4]
    next_alloc = ALLOC_MAP[next_p]
    cur_alloc  = ALLOC_MAP[phase] if phase in ALLOC_MAP else alloc

    # 拐點發生時的配置變更說明
    alloc_transition = {
        k: {"from": cur_alloc.get(k,0), "to": next_alloc.get(k,0)}
        for k in ["股票","債券","現金"]
    }

    # v15: Weather metaphor (before return dict)
    _weather_tup = (
        ("☀️", "晴天", MD_AMBER_300,
         "股 {}% / 債 {}% / 現金 {}%".format(alloc.get("股票",60),alloc.get("債券",30),alloc.get("現金",10)))
        if score >= 7 else
        ("⛅", "多雲", "#90caf9",
         "股 {}% / 債 {}% / 現金 {}%".format(alloc.get("股票",50),alloc.get("債券",40),alloc.get("現金",10)))
        if score >= 4 else
        ("⛈️", "暴雨", "#ef9a9a",
         "股 {}% / 債 {}% / 現金 {}%".format(alloc.get("股票",30),alloc.get("債券",50),alloc.get("現金",20)))
    )
    _w_icon, _w_label, _w_color, _w_alloc_str = _weather_tup

    # 成長/通膨雙軸分析（文件建議 §1 二象限循環判定）
    growth_inflation = calc_growth_inflation_axis(indicators)
    # Z-Score × Slope 二維景氣位階（說明書 §3）
    market_phase_2d  = get_market_phase(indicators)

    return dict(
        score=score, phase=phase, phase_en=phase_en,
        phase_color=phase_color, alloc=alloc,
        weather_icon=_w_icon, weather_label=_w_label,
        weather_color=_w_color, weather_alloc_str=_w_alloc_str,
        advice=advice, strategy=strategy,
        alerts=alerts, mk_signals=mk_signals,
        rec_prob=rec_prob,
        # 拐點轉向
        next_phase=next_phase,
        next_phase_name=next_p,
        trend_arrow=trend_arrow,
        trend_label=trend_label,
        trend_color=trend_color,
        alloc_transition=alloc_transition,
        # 雙軸分析
        growth_inflation=growth_inflation,
        market_phase_2d=market_phase_2d,
        # 保留舊 key 供 AI engine 使用
        inflection=mk_signals.get("inflection",{}),
        signals=mk_signals.get("signals",[]),
        allocation=alloc,
        # F-PROV-1 phase 21 v19.107 — 12 指標融合處 provenance(schema-additive)
        # 把每個參與融合的指標來源串起來,讓 caller 能追溯 single composite score 的血緣
        _provenance=_build_phase_provenance(indicators, total_w, earned_w),
    )


def _build_phase_provenance(indicators: dict, total_w: float, earned_w: float) -> dict:
    """F-PROV-1 phase 21 — calc_macro_phase 融合後 provenance builder.

    把 fetch_all_indicators 各指標 dict 的 `source` 欄串成 sources map,
    讓 caller 可追溯「composite score 由哪幾個 indicator + 哪些來源組成」。

    Args:
        indicators: fetch_all_indicators 回傳的 dict({key: {value, source, score, weight, ...}})
        total_w / earned_w: 加權前 / 後總和(供 caller 驗算)

    Returns:
        dict with:
          - sources: {indicator_key: source_label}(僅含有 source 的指標)
          - contributing: 實際參與融合的指標數
          - total_weight / earned_weight: 加權統計
          - fetched_at: UTC ISO timestamp
          - aggregator: "macro_service.calc_macro_phase"
    """
    import pandas as _pd
    sources = {}
    for k, ind in indicators.items():
        # v19.404:`_` 前綴為 meta(如 _fred_sources),與 calc_macro_phase 同步排除
        # v19.425:述詞收 SSOT(composite_score.is_meta_key)
        if _is_meta_key(k):
            continue
        if isinstance(ind, dict) and ind.get("source"):
            sources[k] = str(ind["source"])
    return {
        "sources": sources,
        "contributing": len([1 for _k, ind in indicators.items()
                             if not _is_meta_key(_k)
                             and isinstance(ind, dict) and ind.get("score") is not None]),
        "total_weight": float(total_w),
        "earned_weight": float(earned_w),
        "fetched_at": _pd.Timestamp.now('UTC').isoformat(),
        "aggregator": "macro_service.calc_macro_phase",
    }


# ══════════════════════════════════════════════════════════════
# F-RECON-1 macro_health 雙演算法 — Z-score 百分位排名平均(v19.108)
# ══════════════════════════════════════════════════════════════
# 設計動機:CLAUDE.md §4.3「macro health score 缺對照演算法」收結。
# 主路徑 calc_macro_phase 用「weighted sum + 絕對閾值」,本對照走「Z-score → 百分位
# → 平均」,與主路徑邏輯正交,可揪出單一指標權重壓制 / regime-change 訊號。
#
# 數學式:
#   for each indicator with series:
#     z = (value - mean(series.tail(60))) / std(series.tail(60))
#     if 反向指標(HY_SPREAD/VIX/ICSA/DXY/CPI/FED_RATE): z = -z
#     pct = Φ(z)  = 0.5 * (1 + erf(z / sqrt(2)))    # 標準常態 CDF
#   score = mean(all pct) * 10
#   phase 用主路徑相同門檻(0~3 衰退 / 3~5 復甦 / 5~8 擴張 / >=8 高峰)
#
# 不變量:
#   * series < 60 期 → 該指標跳過(不偽造)
#   * 全部缺資料 → score = None 並設 status="insufficient_data"
#   * 不引入 scipy 依賴(用 math.erf 等價實作)

# 反向指標:值越高越壞(對風險偏好的 sign 要倒過來)
# v19.449 稽核 HIGH:原本寫 FRED series ID "ICSA"/"UNRATE",但 fetch_all_indicators
# 實際以 dict key "JOBLESS"/"UNEMPLOYMENT" 輸出 → key 永遠對不上、z 從未翻轉 →
# 失業率/初領失業金飆高(衰退)在 z-pct 對帳分被當**最偏多**訊號。改用真正的 indicator
# key,並補齊同屬「高=壞」卻漏掉的 CONT_CLAIMS/SAHM/SLOOS/INFL_EXP_5Y(與 CPI/PPI 同理)。
_ZPCT_REVERSE_KEYS = frozenset({
    "HY_SPREAD",       # 信用利差越大越壞
    "VIX",             # 恐慌指數越高越壞
    "JOBLESS",         # 初領失業金越多越壞(FRED ICSA;實際 key 名)
    "DXY",             # 強美元壓抑風險資產
    "CPI",             # 通膨高 = 緊縮壓力
    "FED_RATE",        # 利率高 = 緊縮
    "UNEMPLOYMENT",    # 失業率高 = 衰退(FRED UNRATE;實際 key 名)
    "PPI",             # PPI 高 = 上游成本壓力
    "CONT_CLAIMS",     # 續領失業金越多越壞
    "SAHM",            # Sahm ≥0.5 = 衰退
    "SLOOS",           # 銀行放貸收緊越多越壞
    "INFL_EXP_5Y",     # 通膨預期高 = 緊縮壓力(同 CPI 理)
})

# Z-pct 採樣窗口(月);<60 視為樣本不足
_ZPCT_MIN_SAMPLES = 60


def _zpct_norm_cdf(z: float) -> float:
    """標準常態累積分佈函數 Φ(z),不依賴 scipy。

    Φ(z) = 0.5 * (1 + erf(z / sqrt(2)))    (math.erf 為 Python 標準庫)
    """
    import math
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def calc_macro_phase_zpct(indicators: dict) -> dict:
    """F-RECON-1 對照演算法:Z-score 百分位排名平均(v19.108)。

    與 calc_macro_phase 邏輯正交:
    - 主路徑:weighted_sum(score, weight) → 0..10
    - 本路徑:mean(Φ(zscore vs 5y rolling)) × 10 → 0..10

    Args
    ----
    indicators : dict
        fetch_all_indicators 輸出格式;各 ind 須有 'value' + 'series'(pd.Series)
        否則該指標跳過。

    Returns
    -------
    dict
        score / phase / phase_color(沿用主路徑 SSOT 配色)
        sub_pcts / contributing(各指標百分位 + 計入數)
        status: 'ok' | 'insufficient_data'
        _provenance: schema-additive(aggregator + fetched_at)
    """
    import math
    import pandas as _pd
    sub_pcts: dict[str, float] = {}
    skipped: list[str] = []
    for key, ind in (indicators or {}).items():
        if not isinstance(ind, dict):
            continue
        # v19.404:`_` 前綴為 meta(如 _fred_sources),與主路徑同步排除。
        # (原本靠「無 value/series」被動跳過,但會污染 skipped 清單讓 audit 誤判。)
        # v19.425:述詞收 SSOT(composite_score.is_meta_key)。
        if _is_meta_key(key):
            continue
        # v19.405 稽核修正(§2.1「第一命中即用、禁止平均」):同因子的備源不得再進來。
        #   本演算法**刻意不讀 weight**(不加權的百分位平均才與主路徑正交,F-RECON-1),
        #   所以 v19.404 給 M2_WEEKLY 的 `weight=0` 對這條路徑完全無效 ——
        #   M2 與 M2_WEEKLY 兩格都有 series 且 ≥60 期 → 各佔 1/n 平均,
        #   且兩者 Z 常反向(線上實測 M2_WEEKLY Z=+0.55 vs M2 Z=-0.11)→ 互相抵銷。
        #   改讀**去重事實** `superseded_by`(§2.2 provenance,生產端 R["M2_WEEKLY"]
        #   在月頻命中時才會標)。刻意不用靜態 key 名單:supersede 是**執行期條件**
        #   (月頻缺漏時週頻要遞補計分),寫死名單會連遞補場景一起砍掉 = §1 丟資料。
        #   跳過原因寫進 skipped,audit 看得到不是靜默。
        _sup = _is_superseded(ind, indicators)
        if _sup:
            skipped.append(f"{key}:superseded_by={_sup}")
            continue
        v = ind.get("value")
        s = ind.get("series")
        if v is None or s is None:
            skipped.append(f"{key}:missing_value_or_series")
            continue
        try:
            s_tail = s.dropna().tail(_ZPCT_MIN_SAMPLES)
        except Exception:
            skipped.append(f"{key}:series_invalid")
            continue
        if len(s_tail) < _ZPCT_MIN_SAMPLES:
            skipped.append(f"{key}:samples={len(s_tail)}<{_ZPCT_MIN_SAMPLES}")
            continue
        mu = float(s_tail.mean())
        sd = float(s_tail.std())
        if sd <= 0 or math.isnan(sd):
            skipped.append(f"{key}:std=0_or_nan")  # §1 Fail Loud:不偽造 z
            continue
        z = (float(v) - mu) / sd
        if key in _ZPCT_REVERSE_KEYS:
            z = -z
        sub_pcts[key] = _zpct_norm_cdf(z)

    if not sub_pcts:
        return {
            "score": None,
            "phase": None,
            "phase_color": TRAFFIC_NEUTRAL,
            "sub_pcts": {},
            "contributing": 0,
            "skipped": skipped,
            "status": "insufficient_data",
            "_provenance": {
                "aggregator": "macro_service.calc_macro_phase_zpct",
                "fetched_at": _pd.Timestamp.now('UTC').isoformat(),
                "method": "Z-score percentile mean (Φ(z) average × 10)",
                "min_samples": _ZPCT_MIN_SAMPLES,
            },
        }

    avg_pct = sum(sub_pcts.values()) / len(sub_pcts)
    score = round(avg_pct * 10, 1)
    # 與主路徑同門檻
    if score >= 8:
        phase = "高峰"; phase_color = MATERIAL_RED
    elif score >= 5:
        phase = "擴張"; phase_color = MATERIAL_GREEN
    elif score >= 3:
        phase = "復甦"; phase_color = MD_BLUE_300
    else:
        phase = "衰退"; phase_color = MATERIAL_ORANGE
    return {
        "score": score,
        "phase": phase,
        "phase_color": phase_color,
        "sub_pcts": sub_pcts,
        "contributing": len(sub_pcts),
        "skipped": skipped,
        "status": "ok",
        "_provenance": {
            "aggregator": "macro_service.calc_macro_phase_zpct",
            "fetched_at": _pd.Timestamp.now('UTC').isoformat(),
            "method": "Z-score percentile mean (Φ(z) average × 10)",
            "min_samples": _ZPCT_MIN_SAMPLES,
            "reverse_keys": sorted(_ZPCT_REVERSE_KEYS),
        },
    }


# ══════════════════════════════════════════════════════════════
# v13 新增：Z-Score 工具 & 景氣循環辨識模型（Regime Model）
# ══════════════════════════════════════════════════════════════

# W5-5+ §1 + DRY:zscore SSOT 在 repositories/macro_repository.py,本檔僅 re-export
# 以維持既有 caller 介面;新 caller 應直接 from repositories.macro_repository import zscore
from repositories.macro_repository import zscore  # noqa: F401, E402


def identify_regime(indicators: dict) -> dict:
    """
    景氣循環辨識模型（v13）
    依 PMI、CPI、FED_RATE 四象限判斷：
      復甦 / 成長 / 過熱 / 衰退
    額外輸出 Z-Score 估值與配置建議
    """
    pmi_v   = (indicators.get("PMI")      or {}).get("value")
    cpi_v   = (indicators.get("CPI")      or {}).get("value")
    fed_v   = (indicators.get("FED_RATE") or {}).get("value")
    fed_p   = (indicators.get("FED_RATE") or {}).get("prev")
    hy_v    = (indicators.get("HY_SPREAD") or {}).get("value")

    # ── 四象限判斷 ────────────────────────────────────────
    if pmi_v is None:
        regime = "未知"; regime_color = TRAFFIC_NEUTRAL
    elif pmi_v >= _PMI_REGIME_STRONG and (cpi_v or 0) < _CPI_REGIME_OVERHEAT:
        regime = "🟢 成長期"; regime_color = MATERIAL_GREEN
    elif pmi_v >= _PMI_REGIME_STRONG and (cpi_v or 0) >= _CPI_REGIME_OVERHEAT:
        regime = "🟡 過熱期"; regime_color = MATERIAL_ORANGE
    elif pmi_v < _PMI_REGIME_CONTRACT and (fed_v or 5) <= (fed_p or 5):
        regime = "🔵 復甦期"; regime_color = MD_BLUE_500
    else:
        regime = "🔴 衰退期"; regime_color = MATERIAL_RED

    # ── Z-Score 估值判斷（PMI / HY_SPREAD）──────────────
    pmi_series = (indicators.get("PMI") or {}).get("series")
    zscore_pmi = None
    if pmi_series is not None and len(pmi_series) >= 12:
        z = float(zscore(pmi_series).iloc[-1])
        # W5-5 §1:std=0 退化時 zscore 回 NaN,caller 須跳過 zscore_pmi 輸出(不可填中性)
        if z != z:  # NaN
            zscore_pmi = None
        elif z < -1.5:   zscore_pmi = {"label": "PMI 低估（買進訊號）", "z": round(z,2), "signal": "🟢"}
        elif z > 1.5:    zscore_pmi = {"label": "PMI 高估（過熱警告）", "z": round(z,2), "signal": "🔴"}
        else:            zscore_pmi = {"label": "PMI 中性",             "z": round(z,2), "signal": "🟡"}

    # ── 配置建議（依循環調整）────────────────────────────
    alloc_by_regime = {
        "🟢 成長期": {"股票型": 50, "核心債券": 30, "衛星主題": 20},
        "🟡 過熱期": {"股票型": 30, "核心債券": 40, "實物資產": 20, "現金": 10},
        "🔵 復甦期": {"股票型": 45, "核心債券": 35, "衛星主題": 15, "現金": 5},
        "🔴 衰退期": {"投資等級債": 50, "貨幣型": 30, "防禦股息": 20},
        "未知":      {"核心債券": 40, "股票型": 40, "現金": 20},
    }
    alloc = alloc_by_regime.get(regime, alloc_by_regime["未知"])

    return {
        "regime":        regime,
        "regime_color":  regime_color,
        "zscore_pmi":    zscore_pmi,
        "hy_spread":     hy_v,
        "alloc_suggest": alloc,
        "note": f"PMI:{pmi_v} CPI:{cpi_v} FedRate:{fed_v}",
    }


# ══════════════════════════════════════════════════════════════════
# v18.1 新聞系統性風險偵測（關鍵字加權評分）
# ══════════════════════════════════════════════════════════════════
_RISK_KEYWORDS = {
    # ── 流動性危機（最高風險）
    "default":       4, "debt crisis":   4, "bank run":       4,
    "bankruptcy":    4, "contagion":      4, "lehman":         4,
    "systemic":      3, "liquidity":      3, "credit crunch":  3,
    "違約":          4, "崩盤":           4, "擠兌":           4,
    "金融危機":      4, "系統性風險":     4, "破產":           3,
    # ── 衰退 / 停滯
    "recession":     3, "stagflation":    3, "depression":     3,
    "slowdown":      2, "contraction":    2, "gdp decline":    2,
    "衰退":          3, "滯脹":           3, "蕭條":           3,
    "負成長":        2, "景氣惡化":       2,
    # ── 央行緊急行動
    "emergency cut": 3, "rate hike":      2, "tightening":     2,
    "暴力升息":      3, "緊急降息":       3, "意外升息":       3,
    # ── 地緣政治 / 貿易
    "war":           2, "sanction":       2, "tariff":         2,
    "trade war":     2, "escalation":     2,
    "戰爭":          2, "制裁":           2, "關稅":           2,
    "脫鉤":          2, "升級":           1,
}

def detect_systemic_risk(news_items: list) -> dict:
    """
    對新聞列表做關鍵字加權掃描，回傳系統性風險評估。

    回傳格式：
    {
      "risk_level":  "HIGH" | "MEDIUM" | "LOW",
      "risk_score":  int,
      "risk_color":  str (hex),
      "risk_icon":   str,
      "triggered":   [{"keyword": str, "count": int, "weight": int, "sub_score": int}],
      "headlines":   [str],  ← 命中關鍵字的新聞標題
      "advice":      str,
    }
    算法：
      sub_score_i = keyword_weight_i × min(hit_count_i, 3)
      total_score = Σ sub_score_i
      HIGH   : score ≥ NEWS_RISK_HIGH_SCORE   （多重高危信號，建議立即降低風險暴露）
      MEDIUM : score ≥ NEWS_RISK_MEDIUM_SCORE（警示狀態，密切追蹤）
      LOW    : 其餘                            （暫無系統性異常）
      ↑ 門檻 SSOT = `shared/macro_buckets.py`（2026-08-05 稽核由 inline 10/5 收編）

    ⚠️ 與 `repositories.news_repository.classify_systemic()` 的分工（2026-08-05 稽核釐清）
    ─────────────────────────────────────────────────────────────────────────
    本函式 = **加權風險分**（44 個詞、權重 1~4），輸出 HIGH/MEDIUM/LOW 供「風險告警」。
    news_repository 的 `is_systemic` = **旗標**，原始用途是排序（命中者永遠排前）。
    兩者**不是同一件事**，也不共用詞表；歷史上曾有 UI 直接把旗標命中「則數」渲染成
    「🔴 系統性警報」，同畫面與本函式的 ✅ LOW 自相矛盾（2026-08-04/05 實測 6 則假警報）。
    若要做風險告警，優先吃本函式的 `risk_level`；旗標只回答「這則該不該排前面」。
    """
    import re as _re

    all_text   = []
    title_map  = {}   # keyword → list of matching titles

    for item in (news_items or []):
        title   = str(item.get("title",   ""))
        summary = str(item.get("summary", ""))
        combined = (title + " " + summary).lower()
        all_text.append(combined)
        # 建立 keyword → title 映射（供展示用）
        for kw in _RISK_KEYWORDS:
            if kw in combined:
                title_map.setdefault(kw, []).append(title[:80])

    full_corpus = " ".join(all_text)
    triggered   = []
    total_score = 0

    for kw, weight in sorted(_RISK_KEYWORDS.items(), key=lambda x: -x[1]):
        # 使用 word boundary 避免誤判（e.g. "war" in "forward"）
        count = len(_re.findall(r'\b' + _re.escape(kw) + r'\b', full_corpus))
        if count > 0:
            sub = weight * min(count, 3)   # 同一關鍵字最多計 3 次，避免單篇洗版
            total_score += sub
            triggered.append({
                "keyword":   kw,
                "count":     count,
                "weight":    weight,
                "sub_score": sub,
            })

    # 命中關鍵字對應的標題（最多 5 則）
    hit_titles = []
    for kw in [t["keyword"] for t in triggered[:5]]:
        for title in title_map.get(kw, []):
            if title not in hit_titles:
                hit_titles.append(title)
    hit_titles = hit_titles[:5]

    # 風險等級判定
    # 2026-08-05 稽核:原 inline `>= 10` / `>= 5`(§3.3 magic number)收 SSOT
    # `shared.macro_buckets.NEWS_RISK_HIGH_SCORE / NEWS_RISK_MEDIUM_SCORE`,
    # 與同族的 `NEWS_SYSTEMIC_*_COUNT` 並列(門檻取法論證見該檔註解)。
    if total_score >= _NEWS_RISK_HIGH:
        level  = "HIGH"
        color  = MATERIAL_RED
        icon   = "🚨"
        advice = "偵測到多重高危信號，建議立即提高現金比重，核心部位 ≥80%，衛星部位設停損"
    elif total_score >= _NEWS_RISK_MED:
        level  = "MEDIUM"
        color  = MATERIAL_ORANGE
        icon   = "⚠️"
        advice = "市場存在潛在壓力訊號，密切追蹤 VIX 與 HY 利差，衛星部位設停利"
    else:
        level  = "LOW"
        color  = MATERIAL_GREEN
        icon   = "✅"
        advice = "新聞面暫無系統性異常，維持既有配置策略"

    return {
        "risk_level":  level,
        "risk_score":  total_score,
        "risk_color":  color,
        "risk_icon":   icon,
        "triggered":   triggered[:10],
        "headlines":   hit_titles,
        "advice":      advice,
    }
