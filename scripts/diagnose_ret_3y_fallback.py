#!/usr/bin/env python3
"""scripts/diagnose_ret_3y_fallback.py —  3-3-3 的「3 年年化」為什麼拿不到(唯讀診斷)。

要回答的問題
============
user 的 8 檔持倉裡有 5 檔(ACCP138 / ACDD01 / ACDD19 / ACTI71 / ACTI94)的
「 3-3-3 篩」停在 ⬜ 資料不足,但這 5 檔的成立年數是 7.87 / 26.34 / 18.30 /
8.57 / 5.54 年,全部遠超 3 年 —— 卡住的不是 C1(成立年數)而是 C2(3 年平均
年化報酬)。本檔把 C2 的取值鏈**逐步拆開印給人看**:每一檔停在哪一步、為什麼
停、以及「如果補上一層用時間軸切的 fallback,這一檔會不會有救」。

**本檔零行為改動**:不改任何判定門檻,所有數值一律來自 production 函式;
「補一層會怎樣」只印出來,不回灌任何 dict、不寫回 fd。

production 的取值鏈(`services/fund_row.py` 內嵌 3-3-3 區塊)
==========================================================
  步驟 1  metrics["ret_3y_ann"]                        直接當年化 %
  步驟 2  metrics["ret_3y_cum"] / metrics["ret_3y"]    累計 % → 開三次方年化
  步驟 3  fd["perf"]["3Y"](或 fd["moneydj_raw"]["perf"]["3Y"])累計 % → 年化
  三步全 None → `check_333_principle` 回 passed=None → ⬜ 資料不足(§1 三態)

步驟 1/2 同源:兩者都由 `services/fund_service.calc_metrics` 內的 `_ret(n)` 產出,
而 `_ret(n)` 的可用條件是「**序列點數** len(s) >= n」,n = 3 × 每年交易日數。
注意這是**點數**不是**時間跨度**(§4.1 量綱陷阱):NAV 序列若因來源只回傳短窗
而被截斷,26 年歷史的老基金一樣拿不到 —— 所以本檔把「NAV 點數 / 起訖 / 跨度 /
相鄰兩點中位數間隔」四欄並排,一眼分辨三種完全不同的病:
  (a) 真的沒有 3 年歷史(新基金)
  (b) 有 3 年歷史但**更新頻率稀疏**(週更 / 月更淨值)→ 點數永遠湊不到門檻
  (c) 有 3 年歷史、也是日更,但**這次只抓回一小段**(短窗 fallback / 子網域被擋)
只有 (b) 是「補時間軸 fallback 就能救」的;(a)(c) 補了也沒用,本檔會直接說出來。

口徑(第二個重點,§4.1)
=====================
步驟 1/2 走的是**原始 NAV**(`calc_metrics` docstring 明列為不含息);
步驟 3 走的是 MoneyDJ 官方績效表(該頁為含息總報酬)。也就是說**同一條鏈的
不同層本來就不同口徑**,而且比較寬鬆的那個(含息)排在**後面** —— 一旦某檔
基金的 NAV 歷史補齊、步驟 1 開始有值,它會**從含息掉回純 NAV**,對月配息基金
等於少掉三年份的配息。本檔逐列標出實際命中的步驟與其口徑,並對「目前吃步驟 3」
的基金掛出口徑翻面警告。

零轉錄(本檔不自己重寫任何演算法)
================================
- 取值鏈最終值:呼 `scripts/compare_inception_years.variant_b_ann_3y` —— 那是
  `fund_row.py` 內嵌區塊的手抄本,已被 `tests/test_compare_inception_years.py`
  的等價鎖釘住(手抄本一旦與 production 分歧,那組測試會紅)。
- 成立年數 / 現況顯示字串:同檔的 `variant_b_years` / `variant_b_status`。
- 序列覆蓋率 / 最大缺口:`services/fund_service.assess_series_coverage`。
- 「時間軸切法」試算:`services/fund_screening.check_333_fund` —— 把 metrics 裡
  三個 3 年欄位拿掉,強迫它走 NAV 序列那條分支,值由 production 算。
- 本檔自己做的只有「命中哪一步」的歸因,而且**每一列都跟上面那個 production
  鏈值對帳**(`attribution_ok`):對不上就把兩個值一起印出來,不偷偷用自己的。

輸入來源 / CLI
==============
沿用 `scripts/compare_inception_years.py` 的兩段式(理由見該檔檔頭:repo 內沒有
任何現成快照同時帶 series + metrics + perf):

    python scripts/diagnose_ret_3y_fallback.py --live --dump snap_3y.json
    python scripts/diagnose_ret_3y_fallback.py --snapshot snap_3y.json
    python scripts/diagnose_ret_3y_fallback.py --live --codes ACCP138,TLZF9
    python scripts/diagnose_ret_3y_fallback.py --snapshot snap.json --out out.txt

代號清單預設讀 `config/preset_funds.json`,或用 `--codes A,B,C`。
本檔的快照是 compare_inception_years 快照的**超集**(多存年化配息率等欄位),
反過來也吃得下舊快照 —— 舊快照缺的欄位一律印「—」,不猜(§1)。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from scripts.compare_inception_years import (  # noqa: E402
    fd_to_snapshot as _base_fd_to_snapshot,
    load_codes,
    snapshot_to_fd as _base_snapshot_to_fd,
    variant_b_ann_3y,
    variant_b_nav_dict,
    variant_b_status,
    variant_b_years,
)

# 「3 年報酬」的年數 —— 這是欄位語意(ret_3y 的那個 3),不是可調門檻,
# 故不進 shared/signal_thresholds;真正會變的「每年幾個交易日」走 SSOT(見下)。
RET_3Y_YEARS = 3

# 口徑標籤(顯示用)。§4.1:這兩種 3 年報酬**不可互相比較**,更不可混排排序。
BASIS_NAV_ONLY = "純 NAV(不含配息)"
BASIS_TOTAL_RETURN = "含息(MoneyDJ 官方績效表)"

# v19.485 PR-2:取值順序改**含息(wb01 perf)優先**,與 SSOT `derive_ann_3y_for_333` 一致
#   (原純NAV優先=偏低口徑)。step1 含息 → step2/3 純NAV fallback(偏低,配息型會被低估)。
STEP_LABELS = {
    1: 'perf["3Y"](MoneyDJ 績效表・含息)',
    2: 'metrics["ret_3y_ann"]',
    3: 'metrics["ret_3y_cum"] / metrics["ret_3y"]',
}
STEP_BASIS = {1: BASIS_TOTAL_RETURN, 2: BASIS_NAV_ONLY, 3: BASIS_NAV_ONLY}

# perf dict 裡的 provenance 欄(F-PROV-1 加的),列 key 時要濾掉,不然報告會很吵。
_PERF_META_KEYS = frozenset({"source", "fetched_at", "_source", "_fetched_at"})

# 相鄰兩點中位數間隔(日曆日)→ 更新頻率白話。用中位數不用平均:少數長假 /
# 停牌缺口會把平均拉歪,中位數才反映「常態多久一筆」。
_FREQ_BANDS = (
    (1.5, "每交易日一筆"),
    (4.0, "接近每交易日(含週末與連假缺口)"),
    (10.0, "約每週一筆"),
    (45.0, "約每月一筆"),
)


def points_required_for_metrics_3y() -> int:
    """步驟 1/2 需要的 NAV **點數**門檻 = 3 × 年交易日數(SSOT,§3.3 不寫死字面值)。"""
    from shared.signal_thresholds import TRADING_DAYS_PER_YEAR
    return RET_3Y_YEARS * TRADING_DAYS_PER_YEAR


def freq_label(median_gap_days) -> str:
    """中位數間隔(天)→ 更新頻率白話標籤。None → 「—」(不猜)。"""
    if median_gap_days is None:
        return "—"
    for _hi, _label in _FREQ_BANDS:
        if median_gap_days <= _hi:
            return _label
    return "比月更稀疏 / 不規則"


def _num(v):
    """寬鬆轉 float;轉不動或非有限值回 None(診斷腳本不因單欄髒資料中斷)。"""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _close(a, b) -> bool:
    """浮點比較走容差(§4.3 禁 `==`);兩邊都 None 視為相同。"""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=1e-9)


def annualize_cum_pct(cum_pct, years: int = RET_3Y_YEARS):
    """累計 % → 年化 %。算不出來回 None(§1,不硬湊)。

    負到 -100% 以下時 `(1+r)**(1/3)` 在 Python 會變複數 —— 那不是報酬率,
    一律當「算不出來」處理。
    """
    v = _num(cum_pct)
    if v is None or years <= 0:
        return None
    try:
        out = ((1.0 + v / 100.0) ** (1.0 / years) - 1.0) * 100.0
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None
    if isinstance(out, complex) or not math.isfinite(out):
        return None
    return out


# ════════════════════════════════════════════════════════════════════════
# NAV 序列事實(點數 / 起訖 / 跨度 / 頻率 / 覆蓋率)
# ════════════════════════════════════════════════════════════════════════
def series_facts(fd: dict) -> dict:
    """只描述序列本身,不做任何判定。覆蓋率走 production `assess_series_coverage`。"""
    out = {
        "n_points": 0, "first_iso": None, "last_iso": None, "span_years": None,
        "median_gap_days": None, "freq_label": "—",
        "coverage": None, "max_gap_days": None, "sparse": None, "series_note": "",
    }
    s = fd.get("series")
    if s is None or not hasattr(s, "dropna"):
        out["series_note"] = "無 NAV 序列"
        return out
    s2 = s.dropna().sort_index()
    out["n_points"] = int(len(s2))
    if len(s2) == 0:
        out["series_note"] = "NAV 序列全空"
        return out
    try:
        idx = pd.DatetimeIndex(pd.to_datetime(s2.index))
    except Exception as e:  # noqa: BLE001 — 診斷腳本:解析不了就標明,不猜
        out["series_note"] = f"index 無法解析為日期:{type(e).__name__}: {e}"
        return out
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    out["first_iso"] = str(idx[0])[:10]
    out["last_iso"] = str(idx[-1])[:10]
    out["span_years"] = round((idx[-1] - idx[0]).days / 365.25, 2)
    if len(idx) >= 2:
        _gaps = pd.Series(idx).diff().dt.days.dropna()
        if len(_gaps):
            out["median_gap_days"] = float(_gaps.median())
            out["freq_label"] = freq_label(out["median_gap_days"])
    try:
        from services.fund_service import assess_series_coverage
        _cov = assess_series_coverage(
            pd.Series(s2.to_numpy(dtype=float), index=idx))
        out["coverage"] = _cov.get("coverage")
        out["max_gap_days"] = _cov.get("max_gap_days")
        out["sparse"] = _cov.get("sparse")
    except Exception as e:  # noqa: BLE001
        out["series_note"] = f"覆蓋率算不出:{type(e).__name__}: {e}"
    return out


# ════════════════════════════════════════════════════════════════════════
# 取值鏈逐步拆解 + 歸因
# ════════════════════════════════════════════════════════════════════════
def chain_steps(fd: dict) -> dict:
    """把三個步驟各自的原始值 / 換算後年化 / 命中者拆開。

    取值順序與 `fund_row.py` 內嵌區塊一致;正確性由 `attribution_ok`(與
    `variant_b_ann_3y` 對帳)守住,不靠人工比對。
    """
    m = fd.get("metrics") or {}
    mj = fd.get("moneydj_raw") or fd
    _perf_top = fd.get("perf") or {}
    _perf_nested = mj.get("perf") or {}
    perf = _perf_top or _perf_nested or {}
    perf_origin = ("fd.perf" if _perf_top
                   else "fd.moneydj_raw.perf" if _perf_nested else None)

    # v19.485 PR-2:新順序 step1 含息(perf 3Y)→ step2 純NAV 直取 → step3 純NAV 累積換算,
    # 與 SSOT `derive_ann_3y_for_333` literal 同源;年化 + round(2) 全走 SSOT `_annualize_cum_pct`
    # 保證 `attribution_ok`(對 variant_b_ann_3y=SSOT)恆成立。
    from services.health.dividend import _annualize_cum_pct as _ann_ssot
    raw1 = perf.get("3Y")                              # step1 含息(wb01)
    raw2 = m.get("ret_3y_ann")                         # step2 純NAV(直取)
    # production 用的是 `or`(不是 `is None`)—— 忠實照抄,見報告「潛在 falsy 回退」。
    raw3 = m.get("ret_3y_cum") or m.get("ret_3y")      # step3 純NAV(累積換算)

    _v1 = _ann_ssot(_num(raw1), 3)
    val1 = None if _v1 is None else round(_v1, 2)
    _v2 = _num(raw2)
    val2 = None if _v2 is None else round(_v2, 2)
    _v3 = _ann_ssot(_num(raw3), 3)
    val3 = None if _v3 is None else round(_v3, 2)

    hit_step, hit_value = None, None
    for _step, _v in ((1, val1), (2, val2), (3, val3)):
        if _v is not None:
            hit_step, hit_value = _step, _v
            break

    return {
        "raw_step1": raw1, "raw_step2": raw2, "raw_step3": raw3,
        "ann_step1_pct": val1, "ann_step2_pct": val2, "ann_step3_pct": val3,
        "hit_step": hit_step,
        "hit_value_pct": hit_value,
        "hit_basis": STEP_BASIS.get(hit_step, "—"),
        "perf_origin": perf_origin,
        "perf_keys": sorted(k for k in perf if k not in _PERF_META_KEYS),
    }


# ════════════════════════════════════════════════════════════════════════
# 「假設補上時間軸 fallback」試算 —— 只算不套用
# ════════════════════════════════════════════════════════════════════════
def time_axis_probe(fd: dict) -> dict:
    """用 production `check_333_fund` 的 NAV 時間切分支試算 3 年年化(零轉錄)。

    做法:複製一份 metrics、把三個 3 年欄位拿掉,`check_333_fund` 就會落到
    「從 NAV 序列自算」那條分支(以 `searchsorted` 依**時間**回推起點,而非
    數點數)。**只讀不寫**:原 fd / 原 metrics 一個字都不動。

    回傳 {"ann_pct": float|None, "source": str, "basis": str, "reason": str}。
    單位:`check_333_fund` 回的是**小數**,本函式一律換成 **%**(§4.1)。
    """
    out = {"ann_pct": None, "source": "", "basis": BASIS_NAV_ONLY, "reason": ""}
    s = fd.get("series")
    if s is None or not hasattr(s, "dropna"):
        out["reason"] = "無 NAV 序列,時間軸切法同樣無從算起"
        return out
    m = dict(fd.get("metrics") or {})
    for _k in ("ret_3y_ann", "ret_3y_cum", "ret_3y"):
        m.pop(_k, None)
    try:
        from services.fund_screening import check_333_fund
        r = check_333_fund(s, m)
    except Exception as e:  # noqa: BLE001 — 診斷腳本:試算炸掉要說出來,不吞
        out["reason"] = f"production 試算丟例外:{type(e).__name__}: {e}"
        return out
    v = _num(r.get("c2_return_3y"))
    if v is None:
        out["reason"] = ("production 的時間軸分支沒給值 —— 它對「切出來的窗口"
                         "實際涵蓋幾年」有下限,序列不夠長就誠實不給(§1)")
        return out
    out["ann_pct"] = round(v * 100.0, 2)
    out["source"] = str(r.get("c2_source") or "")
    return out


# ════════════════════════════════════════════════════════════════════════
# 單檔診斷
# ════════════════════════════════════════════════════════════════════════
def _verdict_string(years, ann_pct) -> str:
    """把 (成立年數, 3 年年化%) 換成大表那一欄的顯示字串(emoji + 訊息)。"""
    from services.health.dividend import check_333_principle
    r = check_333_principle(years, ann_pct)
    _passed = r.get("passed")
    _emoji = "✅" if _passed is True else ("❌" if _passed is False else "⬜")
    _msg = r.get("message", "")
    return f"{_emoji} {_msg[:32]}" if _msg else _emoji


def diagnose_3y(fd: dict, code: str, today=None) -> dict:
    """單檔:序列事實 + 三步拆解 + 現況判定 + 「補第四層會怎樣」。純函式、零網路。"""
    facts = series_facts(fd)
    steps = chain_steps(fd)
    need = points_required_for_metrics_3y()

    chain_value = _num(variant_b_ann_3y(fd))          # production 等價鏈值(已上鎖)
    attribution_ok = _close(chain_value, steps["hit_value_pct"])

    nav_dict = variant_b_nav_dict(fd)
    years = variant_b_years(fd, nav_dict, today=today)
    current_status = variant_b_status(fd, today=today)

    hypo = time_axis_probe(fd)
    # 第四層只有在前三步全空時才會輪到它 —— 前面有值就永遠輪不到,誠實反映。
    would_apply = (steps["hit_step"] is None) and (hypo["ann_pct"] is not None)
    would_status = (_verdict_string(years, hypo["ann_pct"]) if would_apply
                    else current_status)

    row = {
        "code": code,
        "fund_name": str(fd.get("fund_name") or "")[:28],
        "points_required": need,
        "years_since_inception": years,
        "current_status": current_status,
        "chain_value_pct": chain_value,
        "attribution_ok": attribution_ok,
        "hypo_ann_pct": hypo["ann_pct"],
        "hypo_source": hypo["source"],
        "hypo_basis": hypo["basis"],
        "hypo_reason": hypo["reason"],
        "would_apply": would_apply,
        "would_status": would_status,
        "would_change": (would_status or "")[:1] != (current_status or "")[:1],
        # v19.485:口徑偏低風險 —— 命中**純 NAV**(步驟 2/3)代表「> 7%」用的是不含配息的
        #   偏低數字,配息型會被低估;含息(步驟 1・wb01)命中則無此虞。
        "basis_downgrade_risk": steps["hit_step"] in (2, 3),
        **facts,
        **steps,
    }
    row["explain"] = _explain(row)
    return row


def _explain(row: dict) -> str:
    """一句話講清楚「這檔為什麼是現在這個結果」。給人看,不是給程式 parse。"""
    need, n = row["points_required"], row["n_points"]
    hit = row["hit_step"]
    if hit is not None:
        _s = (f"步驟 {hit}({STEP_LABELS[hit]})命中 → 3 年年化 "
              f"{row['hit_value_pct']:.2f}%,口徑 = {row['hit_basis']}")
        if hit in (2, 3):
            _s += (f";含息(步驟 1・wb01 perf)是空的(NAV {n} 點 vs 門檻 {need} 點)"
                   "—— 用的是不含配息的純 NAV 數字,配息型會被低估;"
                   "哪天 MoneyDJ 績效表補上 3Y,會改吃較高的含息數字")
        return _s

    parts = []
    if n < need:
        parts.append(f"NAV 只有 {n} 點 < {need} 點門檻 → 步驟 1、2 必為 None")
    else:
        parts.append(f"NAV 有 {n} 點(已過 {need} 點門檻),步驟 1、2 卻仍為 None"
                     "(這包 fd 沒跑過 calc_metrics,或三年前那一點 NAV ≤ 0)")
    _span = row["span_years"]
    _gap = row["median_gap_days"]
    # 分辨三種完全不同的病(見檔頭 a/b/c):沒歷史 / 頻率太稀 / 抓取窗被截斷。
    if _span is not None and _span < RET_3Y_YEARS:
        parts.append(f"而且序列只涵蓋 {_span} 年({row['first_iso']}→"
                     f"{row['last_iso']}),連 3 年窗都切不出來 —— 這是「沒有歷史」")
    elif _span is not None and _gap is not None and _gap > _FREQ_BANDS[1][0]:
        parts.append(f"序列涵蓋 {_span} 年、但每 {_gap:.0f} 天才一筆"
                     f"({row['freq_label']})→ 點數永遠湊不到門檻,"
                     "這是「更新頻率」問題不是歷史長度問題")
    elif _span is not None:
        parts.append(f"序列涵蓋 {_span} 年、更新頻率是 {row['freq_label']},"
                     f"卻只抓回 {n} 點 → 這是「抓取窗口被截斷」,不是沒有歷史")
    if row["perf_origin"] is None:
        parts.append("MoneyDJ 績效表整包是空的(perf = {}) → 步驟 3 也沒得取")
    elif row["raw_step3"] is None:
        parts.append(f"MoneyDJ 績效表有抓到({row['perf_origin']},欄位 "
                     f"{row['perf_keys']}),但沒有 3Y 這一欄 → 步驟 3 空")
    return ";".join(parts) + f" ⇒ {row['current_status']}"


# ════════════════════════════════════════════════════════════════════════
# 快照 I/O(compare_inception_years 快照的超集;舊快照也讀得進來)
# ════════════════════════════════════════════════════════════════════════
# 本檔多存的 metrics 欄位:年化配息率讓讀者自己看得出「純 NAV vs 含息」差幾個
# 百分點的量級(§1:只給實測欄位,不在報告裡算任何估計值冒充數據)。
_EXTRA_METRIC_KEYS = ("annual_div_rate", "div_freq_n", "ret_1y", "ret_1y_total")


def fd_to_snapshot(fd: dict) -> dict:
    snap = _base_fd_to_snapshot(fd)
    _m = fd.get("metrics") or {}
    snap["metrics_extra"] = {k: _m.get(k) for k in _EXTRA_METRIC_KEYS}
    snap["perf_nested"] = dict((fd.get("moneydj_raw") or {}).get("perf") or {})
    snap["n_dividends"] = len(fd.get("dividends") or [])
    return snap


def snapshot_to_fd(snap: dict) -> dict:
    fd = _base_snapshot_to_fd(snap)
    _extra = snap.get("metrics_extra") or {}
    if _extra:
        fd["metrics"].update({k: v for k, v in _extra.items() if v is not None})
    _nested = snap.get("perf_nested") or {}
    if _nested:
        fd["moneydj_raw"] = {"perf": dict(_nested)}
    fd["n_dividends"] = snap.get("n_dividends")
    return fd


# ════════════════════════════════════════════════════════════════════════
# 報告
# ════════════════════════════════════════════════════════════════════════
def _fmt_pct(v) -> str:
    return "—" if v is None else f"{float(v):.2f}%"


def _dash(v) -> str:
    """None → 「—」;其餘原樣印(值在計算端已 round 過,這裡不再動它)。"""
    return "—" if v is None else str(v)


def _fmt_step(raw, ann_pct, unit_note: str) -> str:
    if raw is None:
        return "—(沒有這個值)"
    if ann_pct is None:
        return f"{raw!r} → 換算不出年化(值不合理)"
    return f"{raw}{unit_note} → 年化 {ann_pct:.2f}%"


def render_report(rows: list) -> str:
    out: list = []
    need = rows[0]["points_required"] if rows else points_required_for_metrics_3y()
    out.append("=" * 78)
    out.append(" 3-3-3 C2「3 年年化」取值鏈診斷(唯讀,零行為改動)")
    out.append(f"跑的時間:本機 {_dt.datetime.now():%Y-%m-%d %H:%M}")
    out.append(f"步驟 1/2 的 NAV 點數門檻:{need} 點(= 3 × 每年交易日數)")
    out.append("=" * 78)

    _blocked = [r for r in rows if r["hit_step"] is None]
    _fixable = [r for r in rows if r["would_change"]]
    _basis_risk = [r for r in rows if r["basis_downgrade_risk"]]
    _bad_attr = [r for r in rows if not r["attribution_ok"]]

    out.append("")
    out.append(f"共診斷 {len(rows)} 檔;三步全空(⬜)的有 **{len(_blocked)} 檔**;"
               f"補上時間軸 fallback 後判定會改變的有 **{len(_fixable)} 檔**。")
    if _bad_attr:
        out.append(f"⚠️ 有 {len(_bad_attr)} 檔的「命中步驟」歸因與 production 鏈值對不上,"
                   "詳見各列(這代表本工具的歸因需要修,不是 production 出錯)。")
    out.append("")

    for r in rows:
        out.append("─" * 78)
        out.append(f"● {r['code']}  {r['fund_name']}")
        out.append(f"    現況判定    {r['current_status'] or '—'}")
        out.append(f"    成立年數    {_fmt_years(r['years_since_inception'])}"
                   f"(3-3-3 要求 ≥ 3 年)")
        out.append(f"    NAV 序列    {r['n_points']} 點｜"
                   f"{r['first_iso'] or '—'} → {r['last_iso'] or '—'}｜"
                   f"跨度 {_dash(r['span_years'])} 年")
        out.append(f"                中位數間隔 {_dash(r['median_gap_days'])} 天"
                   f" → {r['freq_label']}"
                   f"｜覆蓋率 {_dash(r['coverage'])}"
                   f"｜最大缺口 {_dash(r['max_gap_days'])} 天")
        if r["series_note"]:
            out.append(f"                ⚠️ {r['series_note']}")
        out.append(f"    步驟 1  {STEP_LABELS[1]:<38} "
                   f"{_fmt_step(r['raw_step1'], r['ann_step1_pct'], '%(已是年化)')}")
        out.append(f"    步驟 2  {STEP_LABELS[2]:<38} "
                   f"{_fmt_step(r['raw_step2'], r['ann_step2_pct'], '%(累計)')}")
        out.append(f"    步驟 3  {STEP_LABELS[3]:<38} "
                   f"{_fmt_step(r['raw_step3'], r['ann_step3_pct'], '%(累計)')}")
        out.append(f"            └ perf 來自 {r['perf_origin'] or '（沒有 perf）'}"
                   f"，有的欄位:{r['perf_keys'] or '（無）'}")
        out.append(f"    ⇒ {r['explain']}")
        if not r["attribution_ok"]:
            out.append(f"    ⚠️ 歸因對帳失敗:本工具算 {_fmt_pct(r['hit_value_pct'])}、"
                       f"production 鏈值 {_fmt_pct(r['chain_value_pct'])}")
        out.append(f"    補時間軸 fallback 會怎樣？  "
                   f"{_fmt_pct(r['hypo_ann_pct'])}"
                   f"{'（' + r['hypo_source'] + '）' if r['hypo_source'] else ''}"
                   f"｜口徑 {r['hypo_basis']}")
        if r["hypo_reason"]:
            out.append(f"                                {r['hypo_reason']}")
        if r["would_apply"]:
            out.append(f"                                判定 {r['current_status']}"
                       f"  →  {r['would_status']}")
        elif r["hit_step"] is not None:
            out.append("                                前面已經有值,第四層永遠輪不到"
                       " → 判定不變")
        else:
            out.append("                                → 判定不變,這檔不是第四層能救的")
        if r["basis_downgrade_risk"]:
            out.append("    ⚠️ 口徑偏低:目前用的是**純 NAV**(不含配息,步驟 2/3);含息(步驟 1・"
                       "wb01 perf 3Y)缺 → 月配息基金三年份配息沒算進去,> 7% 門檻會被低估")
    out.append("─" * 78)
    out.append("")

    out.append("── 總結 ───────────────────────────────────────────────")
    out.append(f"  三步全空(⬜):{len(_blocked)} 檔"
               f"{'  ' + ', '.join(r['code'] for r in _blocked) if _blocked else ''}")
    out.append(f"  補第四層後會改判:{len(_fixable)} 檔"
               f"{'  ' + ', '.join(r['code'] for r in _fixable) if _fixable else ''}")
    out.append(f"  目前吃純 NAV 偏低口徑(步驟 2/3・含息缺):{len(_basis_risk)} 檔"
               f"{'  ' + ', '.join(r['code'] for r in _basis_risk) if _basis_risk else ''}")
    out.append("")
    out.append("── 怎麼讀 ─────────────────────────────────────────────")
    out.append("  ✅ 通過 3-3-3 ／ ❌ 明確未通過 ／ ⬜ 資料不足 ／ ⚠️ 計算失敗")
    out.append("  「NAV 點數」是步驟 1、2 唯一的門檻 —— 它數的是**點數不是時間**,")
    out.append("  所以週更 / 月更淨值的基金,就算有 20 年歷史也永遠過不了這關。")
    out.append("  「跨度」才是時間;跨度不足 3 年 = 真的沒歷史,補幾層 fallback 都沒用。")
    out.append(f"  口徑:步驟 1 = {BASIS_TOTAL_RETURN};步驟 2、3 = {BASIS_NAV_ONLY};")
    out.append(f"        時間軸 fallback = {BASIS_NAV_ONLY}。")
    out.append("  同一張表裡混用這兩種口徑,月配息基金會被系統性低估三年份的配息 —")
    out.append("  所以真要補第四層,值必須連同口徑一起標出來(比照「1Y 來源」欄的做法)。")
    return "\n".join(out)


def _fmt_years(v) -> str:
    return "—" if v is None else f"{float(v):.2f} 年"


# ════════════════════════════════════════════════════════════════════════
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=" 3-3-3 C2「3 年年化」取值鏈診斷(唯讀,不改任何判定)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--live", action="store_true",
                     help="上線抓(走 production auto_fetch_moneydj)")
    src.add_argument("--snapshot", metavar="FILE",
                     help="離線:讀先前 --dump 出來的快照(也吃 compare_inception_years 的)")
    ap.add_argument("--codes", help="逗號分隔代號;省略則讀 config/preset_funds.json")
    ap.add_argument("--dump", metavar="FILE", help="--live 時同時存快照供離線重跑")
    ap.add_argument("--out", metavar="FILE", help="報告另存純文字檔")
    args = ap.parse_args(argv)

    fds: dict = {}
    if args.snapshot:
        raw = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        for code, snap in (raw.get("funds") or {}).items():
            fds[code] = snapshot_to_fd(snap)
        if not fds:
            raise SystemExit(f"{args.snapshot} 沒有任何基金資料")
    else:
        from services.moneydj_fetcher import auto_fetch_moneydj
        for code in load_codes(args):
            print(f"[live] 抓 {code} …")
            try:
                fd = auto_fetch_moneydj(code)
            except Exception as e:  # noqa: BLE001 — 單檔炸掉不擋整批,但要說出來
                print(f"[live] ❌ {code} 抓取失敗:{type(e).__name__}: {e}")
                continue
            if not isinstance(fd, dict):
                print(f"[live] ❌ {code} 回傳型別非 dict,跳過")
                continue
            fds[code] = fd
        if args.dump:
            Path(args.dump).write_text(json.dumps(
                {"dumped_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                 "funds": {c: fd_to_snapshot(f) for c, f in fds.items()}},
                ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"[dump] 快照已存 → {args.dump}")

    rows = [diagnose_3y(fd, code) for code, fd in sorted(fds.items())]
    report = render_report(rows)
    print(report)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"\n[out] 報告已存 → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
