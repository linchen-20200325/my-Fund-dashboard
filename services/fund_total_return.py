"""1Y 含息報酬率 SSOT(L2 純函式,zero-IO)。

從 `ui/helpers/macro_helpers.py` 搬入,理由:
- 函式無 streamlit 依賴,本就是純函式
- L2 service(`services/health/dividend.py`)需要呼叫它做吃本金燈號判定
  → §8.2 規定 L2 不得 import L3 → 搬到 L2 才能合法 SSOT 化

caller:
- `ui/helpers/macro_helpers.py` shim re-export 保持向後相容
- `services/health/dividend.check_eating_principal_1y_mk()` 直接呼叫
- `services/portfolio_service` / `services/ai_service` / `services/health/report` 讀值

precedence(2026-10-23 客戶裁示 1B 後**只有一層**):
  唯一算法 = 本地「配息還原淨值法」`metrics.ret_1y_total`
             (`fund_service.calc_metrics` 以 `calculate_fund_total_return` 產出)
  且窗口須 ≥ `RET_1Y_RESTORED_MIN_WINDOW_DAYS`(SSOT,350 天);
  配息型基金的還原窗口內若**一筆配息都沒有**,視為配息資料未備 → 不判。
  其餘情況一律回「⬜ 資料未備／無法判定」+ 白話原因,**不**外推年化、**不**退回
  純淨值報酬、**不**拿 MoneyDJ wb01 `perf["1Y"]` 當值(官方值只放 `official_1y_pct`
  供對帳,§4.3)。

舊的四層 fallback(perf["1Y"] → ret_1y_total → ret_1y → NAV 序列年化)已退役:
每一層的口徑都不一樣(官方複利 / 短窗累積 / 不含息 / 外推),同一檔基金在不同
分頁會因為走到不同層而出現不同數字與不同燈號(§2.1 SSOT)。
2026-08-14 稽核 E1 / v19.480 稽核 B1、B2 抓到的假 🔴 全部出自第 2~4 層。
"""
from __future__ import annotations

from typing import Any

# ── 「1Y 來源」欄 / Tab2 KPI 卡的顯示值(SSOT;呼叫端與測試一律 import)────────
# 2026-08-10 user 拍板:這些字串會**原樣印給使用者看**,不能是內部代號。
#
# 2026-10-23 裁示 1B 後,SSOT 只會產出下列兩種:
#   - `SRC_SELF_RESTORED`          有值(本地還原含息,窗口 ≥ 350 天)
#   - `SRC_UNAVAILABLE_PREFIX`(…)  無值(資料未備／無法判定 + 白話原因)
SRC_SELF_RESTORED = "自算（還原含息淨值）"          # 唯一有值的來源
SRC_UNAVAILABLE_PREFIX = "⬜ 資料未備／無法判定"     # 無值時的標籤前綴(括號補白話原因)
SRC_NONE = "—"                                      # resolve 結果 dict 的 `source` 欄(無值時)

# ── 以下常數 2026-10-23 裁示 1B 後**不再由 SSOT 產出**;只為相容保留(避免 import 斷)──
SRC_OFFICIAL = "MoneyDJ 官方"                      # 相容保留:官方值改放 official_1y_pct,不當主值
SRC_PERF_UNLABELED = "績效表（來源未標註）"         # 相容保留:perf 不再被讀成值
SRC_SELF_TOTAL = "自算含息"                        # 相容保留:短窗累積不再給值
SRC_SELF_NAV_ONLY = "自算（僅淨值，不含配息）"      # 相容保留:純淨值不再當含息報酬
SRC_SELF_ANNUALIZED = "自算（{days} 天資料外推年化）"   # 相容保留:外推年化已退役
SRC_TOO_SHORT = "—（僅 {days} 天資料，不足以推算一年）"  # 相容保留:短窗改走 window_short
# 值落在合理帶外時,**附加**在來源標籤後面(不改值、不丟值,只讓它自己講話)
SRC_IMPLAUSIBLE_SUFFIX = "　⚠️ 數值異常大，請先核對幣別與除息"

# unavailable 的白話原因(放進標籤括號;吃本金 / 健診表 / AI prompt 一律印這個)
UNAVAILABLE_REASON_TEXT = {
    "no_series": "無淨值序列",
    "no_restored_value": "淨值序列不足以還原一年含息報酬",
    "window_short": "淨值僅 {days} 天，不足一年",
    "dividend_data_missing": "配息基金但近一年窗口內無配息紀錄",
}


def is_implausible_1y(value) -> bool:
    """該 1Y 含息報酬是否落在合理帶外(§3.2 範圍檢查)。

    稽核 E1:大表出現 +201.65% / +190.64% 的**台幣**基金,在畫面上與正常數字
    長得一模一樣,還會因為數值大而排到最前面。這裡不改值也不丟值 —— 只回答
    「這格該不該打問號」,由呼叫端決定要在標籤 / 表格上怎麼標(§1 標記而非掩蓋)。

    門檻走 `shared.signal_thresholds` SSOT(§3.3 禁 inline magic)。
    """
    from shared.signal_thresholds import (
        RET_1Y_PLAUSIBLE_MAX_PCT,
        RET_1Y_PLAUSIBLE_MIN_PCT,
    )
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    if v != v:  # NaN
        return False
    return v > RET_1Y_PLAUSIBLE_MAX_PCT or v < RET_1Y_PLAUSIBLE_MIN_PCT


def _flag_if_implausible(value, source_label: str) -> tuple[float, str]:
    """統一出口:值離譜就把警語黏在來源標籤上。

    `float(value)` 對無法轉數字的值會拋 ValueError/TypeError;caller 須自行決定
    降級路徑。這裡先記一筆 stderr,讓「這個源給了垃圾」留得下痕跡(§3.3)。
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        import sys as _sys
        print(f"[fund_total_return] 來源 {source_label!r} 給出無法轉數字的值 "
              f"{value!r}", file=_sys.stderr)
        raise
    if is_implausible_1y(v):
        return v, f"{source_label}{SRC_IMPLAUSIBLE_SUFFIX}"
    return v, source_label

# Tab2 吃本金 KPI 卡用:命中任一片語 = 「這個 1Y 是本站算的,且可能不足一整年」,
# 該卡會把欄名從「1Y 含息報酬」改標成實際天數。保留既有字表(改文案不順手改行為);
# 裁示 1B 後 SSOT 只會產出「還原含息淨值」這一種,後兩個片語不會再出現。
LOCAL_WINDOW_SENSITIVE_HINTS = ("還原含息淨值", "自算含息", "外推年化")


def is_extrapolated_1y_source(source_label: str) -> bool:
    """該 tr1y 是否為『短窗淨值 ×最多12 外推年化』(`SRC_SELF_ANNUALIZED`)。

    2026-10-23 裁示 1B 後 SSOT **不再產出**此類來源(外推年化層已退役),
    對 SSOT 產出的標籤恆回 False;保留供舊標籤 / UI 既有分支相容。
    """
    return "外推年化" in str(source_label or "")


def is_too_short_1y_source(source_label: str) -> bool:
    """該 tr1y 之所以是 None,是不是「有淨值序列但不足一年」或「連序列都沒有」?

    2026-10-23 裁示 1B 後對應 `resolve_1y_total_return` 的 `window_short` / `no_series`
    兩種 unavailable 標籤回 True(供 `check_eating_principal_1y_mk` 既有分支與 UI 判讀);
    舊的 `SRC_TOO_SHORT` 字樣亦保留辨識。`no_restored_value` / `dividend_data_missing`
    不在此列 —— 那兩種不是「太短」,是「有長度但還原不出來 / 配息資料缺」。
    """
    _s = str(source_label or "")
    return ("不足以推算一年" in _s
            or UNAVAILABLE_REASON_TEXT["no_series"] in _s
            or "，不足一年" in _s)


def is_partial_window_1y_source(source_label: str) -> bool:
    """該 tr1y 是不是「自算含息、但只有 N 天窗口(< 一年)」的**累積**值?

    2026-10-23 裁示 1B 後 SSOT **不再產出**此類來源(窗口不足改回 unavailable
    `window_short`,不給值),對 SSOT 產出的標籤恆回 False;保留供相容。
    """
    _s = str(source_label or "")
    return "天窗口" in _s


def is_nav_only_1y_source(source_label: str) -> bool:
    """該 tr1y 是不是「純淨值變化、**不含配息**」(`SRC_SELF_NAV_ONLY`)?

    2026-10-23 裁示 1B 後 SSOT **不再產出**此類來源(純淨值層已退役),
    對 SSOT 產出的標籤恆回 False;保留供相容。
    """
    return "不含配息" in str(source_label or "")


def _normalize_shape(fund_obj: dict) -> dict:
    """flat fd(top-level 有 perf 但無 moneydj_raw)→ wrap 成 nested(v19.178 既有規則)。"""
    if not isinstance(fund_obj, dict):
        return {}
    if "moneydj_raw" not in fund_obj and "perf" in fund_obj:
        return {
            "moneydj_raw": fund_obj,
            "metrics": fund_obj.get("metrics") or {},
            "series": fund_obj.get("series"),
            "perf_source": fund_obj.get("perf_source"),
            "dividends": fund_obj.get("dividends"),
        }
    return fund_obj


def _safe_float_or_none(v: Any):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:
        return None
    return f


def is_dividend_fund(fund_obj: dict) -> bool:
    """這檔是不是配息型基金?**只用既有資料,不猜**。

    True 若任一成立:
      (a) `moneydj_div_yield`(wb05 官方年化配息率;nested / flat 皆支援)可轉 float 且 > 0;
      (b) `dividends` list(nested 或 flat)非空且含任一 amount > 0。
    其餘一律 False(含資料缺 → 無法證明它配息,就不把它當配息基金去擋)。
    """
    fund_obj = _normalize_shape(fund_obj)
    mj = fund_obj.get("moneydj_raw") or {}
    _dy = _safe_float_or_none(mj.get("moneydj_div_yield")
                              if mj.get("moneydj_div_yield") is not None
                              else fund_obj.get("moneydj_div_yield"))
    if _dy is not None and _dy > 0:
        return True
    _divs = fund_obj.get("dividends")
    if _divs is None:
        _divs = mj.get("dividends")
    if _divs:
        try:
            for _d in _divs:
                if isinstance(_d, dict):
                    _amt = _d.get("amount")
                    if _amt is None:
                        _amt = _d.get("div_per_unit")
                elif isinstance(_d, (tuple, list)) and len(_d) >= 2:
                    _amt = _d[1]
                else:
                    continue
                _f = _safe_float_or_none(_amt)
                if _f is not None and _f > 0:
                    return True
        except TypeError:
            return False
    return False


def _unavailable(reason: str, *, source_label_days=None, official=None,
                 window_days=None, div_count=None) -> dict:
    _txt = UNAVAILABLE_REASON_TEXT[reason]
    if reason == "window_short":
        _txt = _txt.format(days=source_label_days)
    return {
        "value_pct": None,
        "status": "unavailable",
        "reason": reason,
        "source": SRC_NONE,
        "window_days": window_days,
        "div_count_in_window": div_count,
        "official_1y_pct": official,
        "label": f"{SRC_UNAVAILABLE_PREFIX}（{_txt}）",
    }


def resolve_1y_total_return(fund_obj: dict) -> dict:
    """1Y 含息報酬 SSOT 解析(2026-10-23 裁示 1B,**唯一算法 = 本地還原淨值法**)。

    Returns
    -------
    {
      "value_pct": float | None,
      "status": "ok" | "unavailable",
      "reason": None | "no_series" | "no_restored_value" | "window_short"
                | "dividend_data_missing",
      "source": SRC_SELF_RESTORED(ok)或 SRC_NONE(unavailable),
      "window_days": int | None,            # 還原窗口實際天數
      "div_count_in_window": int | None,    # 窗內配息筆數(calc_metrics.ret_1y_div_count)
      "official_1y_pct": float | None,      # MoneyDJ wb01 perf["1Y"],僅 perf_source=="wb01";
                                            # **對帳用,不是主值**(§4.3)
      "label": str,                         # ok → SRC_SELF_RESTORED(離譜值附警語);
                                            # unavailable → "⬜ 資料未備／無法判定（白話原因）"
    }

    規則(依序):
      1. shape normalize(flat → nested)。
      2. v = metrics.ret_1y_total;wd = metrics.ret_1y_window_days。
      3. wd 有值且 < RET_1Y_RESTORED_MIN_WINDOW_DAYS → unavailable `window_short`。
      4. 配息閘門:`is_dividend_fund` 且 metrics.ret_1y_div_count == 0
         → unavailable `dividend_data_missing`(配息基金的還原序列一筆配息都沒加回,
           等於純淨值,拿去比年化配息率必然假 🔴,v19.480 稽核 B2)。
      5. v 缺:有 series → `no_restored_value`;無 series → `no_series`。
      6. 其餘 → ok;合理帶警語照舊黏在 label。
    **絕不**讀 perf["1Y"] 當值、**絕不**用 ret_1y(純淨值)、**絕不**外推年化。
    """
    from shared.signal_thresholds import RET_1Y_RESTORED_MIN_WINDOW_DAYS

    fund_obj = _normalize_shape(fund_obj)
    m = fund_obj.get("metrics") or {}
    mj = fund_obj.get("moneydj_raw") or {}

    # 官方值只做對帳,不進主值
    _ps = str(fund_obj.get("perf_source") or mj.get("perf_source") or "").lower()
    official = None
    if _ps == "wb01":
        official = _safe_float_or_none((mj.get("perf") or {}).get("1Y"))

    v = m.get("ret_1y_total")
    wd = m.get("ret_1y_window_days")
    try:
        wd_i = int(wd) if wd is not None else None
    except (TypeError, ValueError):
        wd_i = None
    div_count = m.get("ret_1y_div_count")

    if wd_i is not None and wd_i < RET_1Y_RESTORED_MIN_WINDOW_DAYS:
        return _unavailable("window_short", source_label_days=wd_i, official=official,
                            window_days=wd_i, div_count=div_count)

    if is_dividend_fund(fund_obj) and div_count == 0:
        return _unavailable("dividend_data_missing", official=official,
                            window_days=wd_i, div_count=div_count)

    if v is None:
        _s = fund_obj.get("series")
        if _s is None:
            _s = mj.get("series")
        # dict / list / pd.Series 皆算「有序列」(舊 mk_simple 路徑接受 dict),只看有無內容
        try:
            _has_series = _s is not None and len(_s) > 0
        except TypeError:
            _has_series = False
        return _unavailable("no_restored_value" if _has_series else "no_series",
                            official=official, window_days=wd_i, div_count=div_count)

    try:
        val, label = _flag_if_implausible(v, SRC_SELF_RESTORED)
    except (TypeError, ValueError):
        # 壞值不當成「有值」:誠實回無法還原(§1),stderr 已由 _flag_if_implausible 記錄
        return _unavailable("no_restored_value", official=official,
                            window_days=wd_i, div_count=div_count)
    return {
        "value_pct": val,
        "status": "ok",
        "reason": None,
        "source": SRC_SELF_RESTORED,
        "window_days": wd_i,
        "div_count_in_window": div_count,
        "official_1y_pct": official,
        "label": label,
    }


def compute_1y_total_return(fund_obj: dict) -> tuple[float | None, str]:
    """從 fund object 取「1Y 含息報酬率(%)」+ 來源標籤(`resolve_1y_total_return` 薄包裝)。

    簽名不變(多 caller):
        value        = resolve 的 value_pct(僅 status=="ok" 時有值)
        source_label = resolve 的 label(ok → SRC_SELF_RESTORED;unavailable → ⬜ 標籤)
    """
    r = resolve_1y_total_return(fund_obj)
    return (r["value_pct"] if r["status"] == "ok" else None), r["label"]
