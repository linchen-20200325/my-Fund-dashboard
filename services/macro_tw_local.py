"""台股本地總經視角純函式 — Phase v19.23（2026-06-07）。

鏡像 stock dashboard `macro_helpers.py` 之 3 個核心函式：
- detect_mk_golden_inflection  : MK 黃金拐點偵測（CPI YoY × Fed Funds 雙頂回落）
- classify_long_term_regime    : 12M 視角，景氣大循環位階
- classify_short_term_regime   : 1Q 視角，對齊台股財報季偏向

設計原則：
- 零 Streamlit / Plotly 依賴，純資料計算
- pure function：相同輸入恆等輸出
- 防呆：所有 helper 對 None / NaN / 字串皆有 fallback
- 對應 tests/test_macro_tw_local.py 完整 coverage

⚠️ 此檔故意與 services/macro_service.py::identify_regime() 並存：
   - identify_regime  : 全球視角（PMI=US ISM, 無 TW PMI/NDC/Export）
   - 本檔 long/short  : 台股本地視角（含 NDC/TW PMI/Export/外資連續日數/MK）
   兩者互補，由 UI 端決定何時呼叫哪個。
"""
from __future__ import annotations

from typing import Any, Optional


def _safe_float(x: Any) -> Optional[float]:
    """容錯轉浮點：None / 字串 / NaN → None。"""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN guard
        return None
    return f


def detect_mk_golden_inflection(
    cpi_yoy: Optional[float],
    cpi_prev_yoy: Optional[float],
    fed_rate: Optional[float],
    fed_prev_rate: Optional[float],
) -> Optional[dict]:
    """MK 黃金拐點偵測 — CPI YoY × Fed Funds Rate 雙頂回落判讀。

    參數
    ----
    cpi_yoy        : 最新月度美國核心 CPI 年增率（%）
    cpi_prev_yoy   : 上月度美國核心 CPI 年增率（%）
    fed_rate       : 最新月度 Fed Funds Rate（%，月均有效利率）
    fed_prev_rate  : 上月度 Fed Funds Rate（%）

    回傳
    ----
    None  — 資料不足（任一參數為 None / 非數值）或無 MK 訊號
    dict  — {'label', 'icon', 'color', 'detail', 'strength'}
            strength: 'strong'（雙明確回落）/ 'weak'（CPI 弱降+Fed 持平）

    判讀規則（防雜訊：±0.05ppt 視為持平）
    --------
    - CPI 月降 ≥ 0.2ppt AND Fed 持平或月降      → ⭐ 強訊號（MK 黃金拐點 ＝ 多頭最佳買點）
    - CPI 月降 ∈ [0.05, 0.2)ppt AND Fed 持平或月降 → ✅ 弱訊號（MK 拐點觀察中）
    - 任一上升 (> 0.05ppt) 或 CPI 未降          → None（無訊號）
    """
    if cpi_yoy is None or cpi_prev_yoy is None:
        return None
    if fed_rate is None or fed_prev_rate is None:
        return None

    try:
        cpi_delta = float(cpi_yoy) - float(cpi_prev_yoy)
        fed_delta = float(fed_rate) - float(fed_prev_rate)
    except (TypeError, ValueError):
        return None

    if cpi_delta > 0.05 or fed_delta > 0.05:
        return None
    if cpi_delta > -0.05:
        return None

    _fed_desc = '持平' if abs(fed_delta) < 0.05 else f'月降 {abs(fed_delta):.2f}ppt'

    if cpi_delta <= -0.2:
        return {
            'label': 'MK 黃金拐點 ⭐',
            'icon': '⭐',
            'color': '#3fb950',
            'detail': (
                f'核心 CPI {cpi_prev_yoy:+.2f}% → {cpi_yoy:+.2f}% '
                f'（月降 {abs(cpi_delta):.2f}ppt） + Fed Funds '
                f'{fed_prev_rate:.2f}% → {fed_rate:.2f}% （{_fed_desc}） '
                f'→ ⭐ 通膨+利率雙頂回落，景氣多頭最佳買點（歷史勝率最高）'
            ),
            'strength': 'strong',
        }
    return {
        'label': 'MK 拐點觀察中',
        'icon': '✅',
        'color': '#d29922',
        'detail': (
            f'核心 CPI {cpi_prev_yoy:+.2f}% → {cpi_yoy:+.2f}% + '
            f'Fed Funds {fed_prev_rate:.2f}% → {fed_rate:.2f}% '
            f'→ 通膨初步降溫，待 CPI 加速回落或 Fed 確認暫停升息'
        ),
        'strength': 'weak',
    }


def classify_long_term_regime(
    cpi_yoy: Any,
    fed_rate: Any,
    fed_prev_rate: Any,
    ndc_score: Any,
    pmi: Any,
    mk_signal: Optional[dict] = None,
) -> dict:
    """長期總經位階判讀（12M 視角，景氣大循環）。

    參數
    ----
    cpi_yoy        : 美國核心 CPI YoY（%）
    fed_rate       : 最新 Fed Funds Rate（%）
    fed_prev_rate  : 上月 Fed Funds Rate（%）
    ndc_score      : 台灣景氣對策信號分數（9-45）
    pmi            : 台灣製造業 PMI 指數（CIER）
    mk_signal      : detect_mk_golden_inflection() 回傳值（None 或 dict）

    回傳
    ----
    dict 含 regime / score / color / detail / suggest_pct / components

    評分（每項 ∈ [-2, +2]，加權加總）
    --------
    - CPI YoY (25%)：≤2%+2 / 2-3%+1 / 3-4% 0 / 4-5%-1 / ≥5%-2
    - Fed 方向 (20%)：月降+2 / 持平+1 / 月升-2
    - NDC (20%)：紅(≥38)+2 / 黃紅(32-37)+1 / 綠(23-31) 0 / 黃藍(17-22)-1 / 藍(<17)-2
    - PMI (20%)：≥55+2 / 52-55+1 / 50-52 0 / 48-50-1 / <48-2
    - MK 拐點 (15%)：⭐強+2 / ✅弱+1 / None 0
    """
    cpi_v = _safe_float(cpi_yoy)
    fed_v = _safe_float(fed_rate)
    fed_p = _safe_float(fed_prev_rate)
    ndc_v = _safe_float(ndc_score)
    pmi_v = _safe_float(pmi)

    components: list = []
    weighted_sum = 0.0
    weight_total = 0.0

    if cpi_v is not None:
        if cpi_v <= 2.0:
            cpi_pts = 2
        elif cpi_v <= 3.0:
            cpi_pts = 1
        elif cpi_v <= 4.0:
            cpi_pts = 0
        elif cpi_v <= 5.0:
            cpi_pts = -1
        else:
            cpi_pts = -2
        components.append(('美 CPI YoY', cpi_pts, 25))
        weighted_sum += cpi_pts * 25
        weight_total += 25

    if fed_v is not None and fed_p is not None:
        fed_delta = fed_v - fed_p
        if fed_delta < -0.05:
            fed_pts = 2
        elif fed_delta <= 0.05:
            fed_pts = 1
        else:
            fed_pts = -2
        components.append(('Fed 方向', fed_pts, 20))
        weighted_sum += fed_pts * 20
        weight_total += 20

    if ndc_v is not None:
        if ndc_v >= 38:
            ndc_pts = 2
        elif ndc_v >= 32:
            ndc_pts = 1
        elif ndc_v >= 23:
            ndc_pts = 0
        elif ndc_v >= 17:
            ndc_pts = -1
        else:
            ndc_pts = -2
        components.append(('NDC 景氣燈號', ndc_pts, 20))
        weighted_sum += ndc_pts * 20
        weight_total += 20

    if pmi_v is not None:
        if pmi_v >= 55:
            pmi_pts = 2
        elif pmi_v >= 52:
            pmi_pts = 1
        elif pmi_v >= 50:
            pmi_pts = 0
        elif pmi_v >= 48:
            pmi_pts = -1
        else:
            pmi_pts = -2
        components.append(('台 PMI', pmi_pts, 20))
        weighted_sum += pmi_pts * 20
        weight_total += 20

    # MK 訊號：只當至少一個主指標存在時才計入，避免 MK 獨自驅動 regime
    if weight_total > 0:
        if mk_signal is not None and isinstance(mk_signal, dict):
            _s = mk_signal.get('strength')
            mk_pts = 2 if _s == 'strong' else (1 if _s == 'weak' else 0)
        else:
            mk_pts = 0
        components.append(('MK 拐點', mk_pts, 15))
        weighted_sum += mk_pts * 15
        weight_total += 15

    if weight_total == 0:
        return {
            'regime': '⚪ 資料不足',
            'score': 0.0,
            'color': '#8b949e',
            'detail': '所有長期指標皆缺失，無法判讀',
            'suggest_pct': 'N/A',
            'components': components,
        }

    score = weighted_sum / weight_total

    if score >= 1.0:
        regime, color, suggest = '🟢 成長期', '#3fb950', '80%+'
        detail = '景氣擴張+通膨溫和+資金寬鬆 → 多頭主升段，可積極做多'
    elif score >= 0.0:
        regime, color, suggest = '🔵 復甦期', '#58a6ff', '60-80%'
        detail = '景氣由谷底回升 → 加碼基本面好的標的，留意通膨變化'
    elif score >= -1.0:
        regime, color, suggest = '🟡 過熱/震盪期', '#d29922', '40-60%'
        detail = '景氣高檔震盪或通膨壓力 → 謹慎觀望，等待方向確認'
    else:
        regime, color, suggest = '🔴 衰退期', '#f85149', '<30%'
        detail = '景氣下行+通膨壓力或政策緊縮 → 保守減倉，現金為王'

    return {
        'regime': regime,
        'score': round(score, 2),
        'color': color,
        'detail': detail,
        'suggest_pct': suggest,
        'components': components,
    }


def classify_short_term_regime(
    export_yoy: Any,
    pmi: Any,
    vix_current: Any,
    fi_streak_days: Any,
    cpi_yoy: Any,
    cpi_prev_yoy: Any,
) -> dict:
    """短期總經偏向判讀（1Q 視角，對齊台股財報季 Q1/Q2/Q3/Q4）。

    參數
    ----
    export_yoy      : 台灣出口 YoY（%）
    pmi             : 台灣製造業 PMI（CIER 指數）
    vix_current     : VIX 收盤
    fi_streak_days  : 外資連續買賣超天數（+正=連買，負=連賣）
    cpi_yoy         : 美 CPI YoY（%）
    cpi_prev_yoy    : 上月 CPI YoY（%）

    回傳
    ----
    dict 含 regime / score / color / detail / action / components

    評分（每項 ∈ [-2, +2]，加權加總）
    --------
    - 出口 YoY (25%)：≥15%+2 / 5-15%+1 / 0-5% 0 / -5-0%-1 / <-5%-2
    - PMI 水準 (25%)：≥55+2 / 52-55+1 / 50-52 0 / 48-50-1 / <48-2
    - VIX 水準 (15%)：<15+2 / 15-20+1 / 20-25 0 / 25-30-1 / ≥30-2
    - 外資連續 (20%)：連買≥5+2 / 1-4+1 / 0 0 / 連賣1-4-1 / 連賣≥5-2
    - CPI 月降 (15%)：降≥0.3+2 / 0.1-0.3+1 / ±0.1 0 / 升0.1-0.3-1 / 升≥0.3-2
    """
    exp_v = _safe_float(export_yoy)
    pmi_v = _safe_float(pmi)
    vix_v = _safe_float(vix_current)
    fi_v  = _safe_float(fi_streak_days)
    cpi_v = _safe_float(cpi_yoy)
    cpi_p = _safe_float(cpi_prev_yoy)

    components: list = []
    weighted_sum = 0.0
    weight_total = 0.0

    if exp_v is not None:
        if exp_v >= 15:
            exp_pts = 2
        elif exp_v >= 5:
            exp_pts = 1
        elif exp_v >= 0:
            exp_pts = 0
        elif exp_v >= -5:
            exp_pts = -1
        else:
            exp_pts = -2
        components.append(('出口 YoY', exp_pts, 25))
        weighted_sum += exp_pts * 25
        weight_total += 25

    if pmi_v is not None:
        if pmi_v >= 55:
            pmi_pts = 2
        elif pmi_v >= 52:
            pmi_pts = 1
        elif pmi_v >= 50:
            pmi_pts = 0
        elif pmi_v >= 48:
            pmi_pts = -1
        else:
            pmi_pts = -2
        components.append(('台 PMI', pmi_pts, 25))
        weighted_sum += pmi_pts * 25
        weight_total += 25

    if vix_v is not None:
        if vix_v < 15:
            vix_pts = 2
        elif vix_v < 20:
            vix_pts = 1
        elif vix_v < 25:
            vix_pts = 0
        elif vix_v < 30:
            vix_pts = -1
        else:
            vix_pts = -2
        components.append(('VIX 波動', vix_pts, 15))
        weighted_sum += vix_pts * 15
        weight_total += 15

    if fi_v is not None:
        if fi_v >= 5:
            fi_pts = 2
        elif fi_v >= 1:
            fi_pts = 1
        elif fi_v > -1:
            fi_pts = 0
        elif fi_v > -5:
            fi_pts = -1
        else:
            fi_pts = -2
        components.append(('外資籌碼', fi_pts, 20))
        weighted_sum += fi_pts * 20
        weight_total += 20

    if cpi_v is not None and cpi_p is not None:
        cpi_delta = cpi_v - cpi_p
        if cpi_delta <= -0.3:
            cpi_pts = 2
        elif cpi_delta <= -0.1:
            cpi_pts = 1
        elif cpi_delta <= 0.1:
            cpi_pts = 0
        elif cpi_delta <= 0.3:
            cpi_pts = -1
        else:
            cpi_pts = -2
        components.append(('CPI 月降', cpi_pts, 15))
        weighted_sum += cpi_pts * 15
        weight_total += 15

    if weight_total == 0:
        return {
            'regime': '⚪ 資料不足',
            'score': 0.0,
            'color': '#8b949e',
            'detail': '所有短期指標皆缺失，無法判讀',
            'action': 'N/A',
            'components': components,
        }

    score = weighted_sum / weight_total

    if score >= 0.8:
        regime, color = '⚡ 偏多', '#3fb950'
        detail = '下個財報季正向動能 → 加碼績優股、波段佈局好時機'
        action = '建議：擇強做多、留意外資連續買超的個股'
    elif score >= -0.3:
        regime, color = '⚖️ 中性', '#d29922'
        detail = '訊號分歧或多空交織 → 觀望為主、留意個股輪動'
        action = '建議：區間操作、避免追高殺低、續抱長期持股'
    else:
        regime, color = '⚠️ 偏空', '#f85149'
        detail = '下個財報季承壓 → 防守為主、現金為王'
        action = '建議：減碼高估值、停利出場、留意外資連續賣超'

    return {
        'regime': regime,
        'score': round(score, 2),
        'color': color,
        'detail': detail,
        'action': action,
        'components': components,
    }
