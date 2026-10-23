"""2026-10-23 裁示 2C ＋ Stop Gate「選項 1」(BL-0426):HWM σ 基金位置唯一 SSOT 守衛。

鎖住的事:
  1. σ 位置一律在**配息還原(Total Return)序列**上計算;無配息時 ≡ 原始 NAV。
  2. Fail closed:歷史不足 / 配息資料未備 / 貨幣市場型 / σ≈0 / 還原失敗 → ⬜,
     sigma_rank=None、position=None,**不退回原始 NAV、不補 0、不當中性**。
  3. 中性三態經 `services.rotation.classify_base`(同切點 −0.5 / −1.5),`calibrated=False`。
  4. 全站 consumer 不得繞過 SSOT 直接呼叫 `calc_hwm_sigma_levels`(AST 守衛)。
  5. SSOT 輸出 / HWM label 不得出現行動用字(禁字守衛)。
"""
from __future__ import annotations

import ast
import pathlib

import numpy as np
import pandas as pd
import pytest

from services.fund_position import compute_fund_position
from services.precision_service import (
    calc_hwm_sigma_levels,
    hwm_position_from_rank,
    hwm_position_labels,
)
from services.rotation import classify_base
from services.total_return_series import restore_total_return_series

ROOT = pathlib.Path(__file__).resolve().parents[1]

FORBIDDEN = ("加碼", "減碼", "超跌", "買點", "賣點", "可買", "可賣", "抄底", "接刀",
             "觀察", "承接", "停利", "進場", "出場", "過熱")


# ── 合成序列 ──────────────────────────────────────────────────────────────

def _noisy(n=300, seed=7, base=10.0, sd=0.01, start="2023-01-02"):
    idx = pd.bdate_range(start, periods=n)
    rng = np.random.default_rng(seed)
    return pd.Series(base + rng.normal(0, sd, n), index=idx)


def _monthly_div_fund(n=300, seed=7, amount=0.08, date_fmt="%Y/%m/%d"):
    """NAV ≈ 10 + 小雜訊,每月第一個交易日除息 `amount`(除息日起淨值整段下移)。"""
    s = _noisy(n=n, seed=seed)
    idx = s.index
    vals = s.to_numpy().copy()
    divs = []
    months = sorted({(d.year, d.month) for d in idx})
    for (y, mo) in months[1:]:
        exd = idx[(idx.year == y) & (idx.month == mo)][0]
        divs.append({"date": exd.strftime(date_fmt), "amount": amount})
        vals[idx >= exd] -= amount
    return pd.Series(vals, index=idx), divs


# ═══ 1. 正常非配息:TR ≡ raw ═══════════════════════════════════════════════

def test_non_dividend_fund_equals_raw_calc():
    s = _noisy()
    r = compute_fund_position({"series": s})
    raw = calc_hwm_sigma_levels(s)
    assert r["status"] == "ok"
    assert r["sigma_rank"] == pytest.approx(raw["sigma_rank"])
    assert r["series_basis"] == "total_return"
    assert r["thresholds"] == {"near_high": -0.5, "far_from_high": -1.5, "calibrated": False}
    assert "error" not in r
    # 錨定:還原基準的「現價」= 原始最新淨值(以最新淨值為錨換回原幣單位)
    assert r["current_nav_tr"] == pytest.approx(r["current_nav"], abs=1e-3)
    assert r["div_count_in_window"] == 0


# ═══ 2. 正常配息:還原後非平線,ok ════════════════════════════════════════

def test_monthly_dividend_fund_ok_and_restored():
    s, divs = _monthly_div_fund()
    s_tr, meta = restore_total_return_series(s, divs)
    assert s_tr is not None and meta["reason"] is None
    assert len(meta["restored_div_dates"]) == len(divs)
    assert s_tr.std() > 0
    r = compute_fund_position({"series": s, "dividends": divs,
                               "moneydj_raw": {"moneydj_div_yield": 9.6}})
    assert r["status"] == "ok"
    assert r["div_count_in_window"] > 0
    assert r["position"] in ("near_high", "mid", "far_from_high")


def test_restore_core_is_the_existing_factor_method():
    """沒有另寫公式:乾淨升冪輸入時,與 `_total_return_nav`(同一支 Factor 核心)逐點相等。"""
    from services.fund_service import _total_return_nav
    s, divs = _monthly_div_fund(date_fmt="%Y-%m-%d")
    s_tr, _ = restore_total_return_series(s, divs)
    legacy = _total_return_nav(s, divs)
    np.testing.assert_allclose(s_tr.to_numpy(), legacy.to_numpy(), rtol=1e-12)


# ═══ 3. 除息造成的假低基期:舊路徑 far_from_high,新 SSOT 不是 ═══════════════

def test_ex_dividend_drop_no_longer_reads_far_from_high():
    s, divs = _monthly_div_fund()
    raw = calc_hwm_sigma_levels(s)           # 舊路徑:原始 NAV
    assert raw["position"] == "far_from_high"
    assert raw["sigma_rank"] < -1.5           # 實測 -2.485(本合成序列,seed=7)
    r = compute_fund_position({"series": s, "dividends": divs,
                               "moneydj_raw": {"moneydj_div_yield": 9.6}})
    assert r["status"] == "ok"
    assert r["position"] != "far_from_high"
    assert r["sigma_rank"] > -1.5             # 實測 -0.098


# ═══ 4. 配息缺漏 → dividend_data_missing ════════════════════════════════

def test_dividend_fund_without_dividend_records():
    s, _ = _monthly_div_fund()
    r = compute_fund_position({"series": s, "dividends": [],
                               "moneydj_raw": {"moneydj_div_yield": 9.6}})
    assert r["status"] == "unavailable" and r["reason"] == "dividend_data_missing"
    assert r["sigma_rank"] is None and r["position"] is None


def test_dividend_dates_never_on_nav_dates():
    """全部落在週六(bdate 序列沒有週六)→ 一筆都沒被還原 → 對不上(2026-10-23 稽核必修 C)。
    ~~reason == "dividend_data_missing"~~:窗口內**有**配息紀錄,只是對不上淨值日 →
    `dividend_data_unreliable`(更精確的 ⬜ 原因);兩者都是 fail closed。"""
    s, _ = _monthly_div_fund()
    sats = [d for d in pd.date_range(s.index[0], s.index[-1], freq="W-SAT")]
    divs = [{"date": d.strftime("%Y-%m-%d"), "amount": 0.05} for d in sats[::4]]
    r = compute_fund_position({"series": s, "dividends": divs})
    assert r["reason"] == "dividend_data_unreliable"
    assert r["div_count_in_window"] == 0 and r["sigma_rank"] is None


def test_partial_dividend_misalignment_fails_closed():
    """必修 C:一筆在淨值日、一筆在週六 → 部分沒被還原 → ⬜(不自行挪到下一個淨值日)。"""
    s, _ = _monthly_div_fund()
    on_nav = s.index[200]
    sat = next(d for d in pd.date_range(s.index[210], s.index[-1]) if d.dayofweek == 5)
    divs = [{"date": on_nav.strftime("%Y-%m-%d"), "amount": 0.05},
            {"date": sat.strftime("%Y-%m-%d"), "amount": 0.05}]
    r = compute_fund_position({"series": s, "dividends": divs})
    assert r["status"] == "unavailable" and r["reason"] == "dividend_data_unreliable"
    assert r["label"].startswith("⬜") and "對不上" in r["label"]
    assert r["div_count_in_window"] == 1
    # 對照:兩筆都在淨值日 → 可判(證明擋下來的是「對不上」,不是配息本身)
    ok = compute_fund_position({"series": s, "dividends": [
        {"date": on_nav.strftime("%Y-%m-%d"), "amount": 0.05},
        {"date": s.index[230].strftime("%Y-%m-%d"), "amount": 0.05}]})
    assert ok["status"] == "ok" and ok["div_count_in_window"] == 2


def test_misaligned_dividend_outside_window_is_ignored():
    """窗口(最後 252 筆)之外的對不上的配息不影響本窗口的判定。"""
    s = _noisy(n=400)
    sat = next(d for d in pd.date_range(s.index[10], s.index[60]) if d.dayofweek == 5)
    r = compute_fund_position({"series": s, "dividends": [
        {"date": sat.strftime("%Y-%m-%d"), "amount": 0.05}]})
    # 是配息基金、窗口內沒有任何配息 → 走 dividend_data_missing(不是 unreliable)
    assert r["reason"] == "dividend_data_missing"


# ═══ 5 / 6. 歷史不足、貨幣市場、σ≈0 ═══════════════════════════════════════

def test_history_short():
    r = compute_fund_position({"series": _noisy(n=20)})
    assert r["reason"] == "history_short" and r["sigma_rank"] is None


def test_no_series():
    assert compute_fund_position({"series": None})["reason"] == "no_series"
    assert compute_fund_position({})["reason"] == "no_series"


def test_money_market_not_applicable():
    r = compute_fund_position({"series": _noisy(), "moneydj_raw": {"category": "貨幣市場型"}})
    assert r["reason"] == "money_market" and r["position"] is None


def test_flat_nav_low_volatility():
    idx = pd.bdate_range("2023-01-02", periods=120)
    r = compute_fund_position({"series": pd.Series(10.0, index=idx)})
    assert r["reason"] == "low_volatility" and r["sigma_rank"] is None


# ═══ 7. 還原失敗(配息 ≥ NAV / 同日重複 / 降冪輸入先排序)════════════════════

def test_dividend_ge_nav_restore_failed():
    s, divs = _monthly_div_fund()
    bad = list(divs) + [{"date": s.index[50].strftime("%Y-%m-%d"), "amount": 99.0}]
    assert restore_total_return_series(s, bad)[0] is None
    r = compute_fund_position({"series": s, "dividends": bad})
    assert r["reason"] == "restore_failed" and r["sigma_rank"] is None


def test_duplicate_ex_date_restore_failed():
    s, divs = _monthly_div_fund()
    dup = list(divs) + [dict(divs[3])]
    s_tr, meta = restore_total_return_series(s, dup)
    assert s_tr is None and meta["reason"] == "restore_failed"
    assert meta["detail"] == "duplicate_ex_date"


def test_descending_input_is_sorted_not_inverted():
    s, divs = _monthly_div_fund()
    a, _ = restore_total_return_series(s, divs)
    b, _ = restore_total_return_series(s.iloc[::-1], divs)
    assert b.index.is_monotonic_increasing
    pd.testing.assert_series_equal(a, b)
    ra = compute_fund_position({"series": s, "dividends": divs})
    rb = compute_fund_position({"series": s.iloc[::-1], "dividends": divs})
    assert ra["sigma_rank"] == rb["sigma_rank"]


def test_unparsable_dividend_date_restore_failed():
    s, divs = _monthly_div_fund()
    bad = list(divs) + [{"date": "not-a-date", "amount": 0.08}]
    assert restore_total_return_series(s, bad)[0] is None


def test_restore_meta_counts_only_restored_in_window():
    """restore 的 meta:`div_count_in_window` 只數「真的被還原」且 ≥ window_start 的;
    對不上淨值日的那筆算在 div_count_total、不算在 restored / window 計數。"""
    s, divs = _monthly_div_fund(date_fmt="%Y-%m-%d")
    sat = next(d for d in pd.date_range(s.index[200], s.index[-1]) if d.dayofweek == 5)
    ws = s.index[150]
    s_tr, meta = restore_total_return_series(
        s, list(divs) + [{"date": sat.strftime("%Y-%m-%d"), "amount": 0.05}], window_start=ws)
    assert s_tr is not None
    assert meta["div_count_total"] == len(divs) + 1
    assert len(meta["restored_div_dates"]) == len(divs)
    assert meta["div_count_in_window"] == sum(
        1 for d in divs if pd.Timestamp(d["date"]) >= ws)


def test_no_dividend_events_explicit():
    s = _noisy()
    s_tr, meta = restore_total_return_series(s, [])
    assert meta["reason"] == "no_dividend_events"
    pd.testing.assert_series_equal(s_tr, s)


def test_dividend_format_parity_with_is_dividend_fund():
    """dict(amount / div_per_unit)與 tuple 兩種格式都被還原,與 is_dividend_fund 同一份解析。"""
    from services.fund_total_return import is_dividend_fund
    s, divs = _monthly_div_fund(date_fmt="%Y-%m-%d")
    as_dpu = [{"date": d["date"], "div_per_unit": d["amount"]} for d in divs]
    as_tuple = [(d["date"], d["amount"]) for d in divs]
    base, _ = restore_total_return_series(s, divs)
    for fmt in (as_dpu, as_tuple):
        assert is_dividend_fund({"dividends": fmt}) is True
        got, meta = restore_total_return_series(s, fmt)
        assert len(meta["restored_div_dates"]) == len(divs)
        pd.testing.assert_series_equal(got, base)


# ═══ as_of:截斷序列與還原用的配息(「是否配息基金」用現在資訊,見上一條)═════════════════════════════════════════════

def test_as_of_known_limitation_dividend_status_uses_current_info():
    """必修 B:據實鎖住已知行為 —— as_of 截掉的是序列與還原用的配息,但「是不是配息基金」
    用的是**現在的資訊**。t 之後才開始配息的基金,在 t 時點被判 dividend_data_missing(⬜),
    方向是 fail closed(本來可判 → 變 unknown;不會反向把配息基金當非配息基金判)。"""
    rng = np.random.default_rng(9)
    idx = pd.bdate_range("2020-01-02", periods=1000)
    s = pd.Series(10 * np.exp(np.cumsum(rng.normal(0, 0.007, 1000))), index=idx)
    t = idx[500]
    late = [{"date": idx[900].strftime("%Y-%m-%d"), "amount": 0.05}]
    assert compute_fund_position({"series": s, "dividends": late},
                                 as_of=t)["reason"] == "dividend_data_missing"
    assert compute_fund_position({"series": s, "moneydj_raw": {"moneydj_div_yield": 4.0}},
                                 as_of=t)["reason"] == "dividend_data_missing"
    # 截至 t 已知的資訊(沒有任何配息)本來可判
    assert compute_fund_position({"series": s, "dividends": []}, as_of=t)["status"] == "ok"


def test_as_of_truncates_series_and_restore_dividends():
    s, divs = _monthly_div_fund()
    t = s.index[220]
    fund = {"series": s, "dividends": divs, "moneydj_raw": {"moneydj_div_yield": 9.6}}
    cut = {"series": s.loc[:t],
           "dividends": [d for d in divs if pd.Timestamp(d["date"].replace("/", "-")) <= t],
           "moneydj_raw": {"moneydj_div_yield": 9.6}}
    a = compute_fund_position(fund, as_of=t)
    b = compute_fund_position(cut)
    assert a["sigma_rank"] == b["sigma_rank"] and a["current_nav"] == b["current_nav"]


# ═══ 8. 三態邊界與 classify_base 一致 ═════════════════════════════════════

@pytest.mark.parametrize("rank,expected", [
    (-0.5, "near_high"), (-0.4999, "near_high"), (-0.5001, "mid"),
    (-1.5, "far_from_high"), (-1.4999, "mid"), (-1.5001, "far_from_high"),
])
def test_three_state_boundaries_match_classify_base(rank, expected):
    pos, label, color = hwm_position_from_rank(rank)
    assert pos == expected
    assert {"high": "near_high", "mid": "mid", "low": "far_from_high"}[classify_base(rank)] == pos
    assert label and color


# ═══ 9. Missing 不得變成 0 / 中性 / 買賣 —— 一路追到下游 ═══════════════════════

def _unavailable_fund(code="X1"):
    return {"code": code, "name": "Short", "series": _noisy(n=20), "dividends": []}


def test_unavailable_is_none_not_zero():
    r = compute_fund_position(_unavailable_fund())
    assert r["status"] == "unavailable"
    assert r["sigma_rank"] is None and r["position"] is None and r["sigma_abs"] is None
    assert r["error"] == r["label"] and r["label"].startswith("⬜")


def test_downstream_by_code_shows_dash():
    from services.fund_grp_health.risk import hwm_sigma_by_code
    out = hwm_sigma_by_code([_unavailable_fund()])["X1"]
    assert out["σ rank"] == "—" and out["HWM"] == "—" and out["距 HWM %"] == "—"
    assert out["HWM 位階"].startswith("⬜")
    assert classify_base(out["σ rank"]) == "unknown"


def test_downstream_rotation_excludes_unknown():
    from services.rotation import insufficient_sigma_names, suggest_rotation_pairs
    rows = [
        {"code": "S", "name": "Sell", "基金類別": "股票", "σ rank": "-0.10σ",
         "4D Grade": "A", "吃本金燈號": "🟢", "操盤評分": 90, "距 HWM %": "-1%"},
        {"code": "U", "name": "Unknown", "基金類別": "債券", "σ rank": "—",
         "4D Grade": "A", "吃本金燈號": "🟢", "操盤評分": 90, "距 HWM %": "—"},
    ]
    pairs = suggest_rotation_pairs(rows)
    assert all(p["buy_code"] != "U" and p["sell_code"] != "U" for p in pairs)
    assert insufficient_sigma_names(rows) == ["Unknown"]


def test_downstream_advisor_takes_insufficient_branch():
    from services.policy_advisor_service import (
        INSUFFICIENT_DATA,
        advise_fund,
        recommend_policy,
    )
    r = compute_fund_position(_unavailable_fund())
    assert advise_fund(r, None, None, 99.0)["code"] == INSUFFICIENT_DATA
    rec = recommend_policy([{"invest_twd": 100, "is_core": True, "sigma_info": r}
                            for _ in range(3)], target_core_pct=100.0)
    assert "深度" not in rec["text"]          # unavailable 不計入 P3 深跌計數
    # 2026-10-23 BL-0428 DG-1 A:~~只斷言不含「深度」(全 ⬜ 時綠燈「配置健康」照樣通過)~~
    # → 全 ⬜ 不得亮綠燈,走既有 INSUFFICIENT_DATA 灰色並列出 ⬜ 檔數。
    assert rec["color"] != "green" and "配置健康" not in rec["text"]
    assert rec["code"] == INSUFFICIENT_DATA and rec["color"] == "grey"
    assert "3 檔基金位置無法判定" in rec["text"]


def test_downstream_decision_matrix_skips_sigma_override():
    from services.decision_matrix import verdict_to_actions
    r = compute_fund_position(_unavailable_fund())
    out = verdict_to_actions("樂觀", 5.0, [{"code": "X1", "policy_tier": "satellite",
                                             "sigma_info": r}])
    assert "σ" not in out[0]["reason"]


def test_downstream_screening_and_backtest_unknown():
    from services.allocation_backtest import _sigma_rank_at
    from services.fund_screening import compute_base_state
    f = _unavailable_fund()
    lb = compute_base_state(f)
    assert lb["base"] == "unknown" and lb["sigma_rank"] is None and lb["is_low_base"] is None
    assert _sigma_rank_at(f, f["series"].index[-1]) is None
    # 配息基金缺配息資料 → 同樣 unknown(不退回原始 NAV)
    s, _ = _monthly_div_fund()
    g = {"series": s, "dividends": [], "moneydj_raw": {"moneydj_div_yield": 9.6}}
    assert compute_base_state(g)["base"] == "unknown"
    assert _sigma_rank_at(g, s.index[-1]) is None


def test_screening_buy_threshold_comparable_with_raw_price():
    """還原基準以最新原始淨值為錨 → buy_threshold_nav 仍可直接和原始現價比較。"""
    from services.fund_screening import compute_base_state
    s, divs = _monthly_div_fund()
    lb = compute_base_state({"series": s, "dividends": divs,
                             "moneydj_raw": {"moneydj_div_yield": 9.6}})
    assert lb["base"] != "unknown"
    assert lb["current"] == pytest.approx(float(s.iloc[-1]), abs=1e-3)
    assert lb["buy_threshold_nav"] < lb["hwm"]
    # 現價 ≥ 門檻價 ⇔ 不在低基期(本序列 near_high)
    assert (lb["current"] > lb["buy_threshold_nav"]) == (lb["base"] != "low")


# ═══ 10. AST 守衛:只有 SSOT 可以直接呼叫 calc_hwm_sigma_levels ═════════════

_WHITELIST = {"services/fund_position.py", "services/precision_service.py"}


def _direct_calc_uses(src: str) -> list:
    """回傳違規節點描述:import calc_hwm_sigma_levels、或 `.calc_hwm_sigma_levels` 屬性存取。

    ⚠️ 射程外(刻意不擋,據實寫明):`getattr(mod, "calc_hwm" + "_sigma_levels")` 這類動態
    取名、exec / eval、經別名 dict 間接呼叫 —— AST 看不到字面名稱。另一個繞過方式
    「傳 SSOT 一個只有 series 的 dict」也不是本守衛的射程,由下方 consumer 層行為測試擋。
    """
    hits = []
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == "calc_hwm_sigma_levels":
                    hits.append(f"import@{node.lineno}")
        elif isinstance(node, ast.Attribute) and node.attr == "calc_hwm_sigma_levels":
            hits.append(f"attr@{node.lineno}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "calc_hwm_sigma_levels":
            hits.append(f"call@{node.lineno}")
    return hits


def test_guard_detector_self_check():
    """守衛自身先驗:直呼 / 別名 import / 屬性存取 三種寫法都抓得到。"""
    assert _direct_calc_uses(
        "from services.precision_service import calc_hwm_sigma_levels as f\nf(s)")
    assert _direct_calc_uses("import services.precision_service as p\np.calc_hwm_sigma_levels(s)")
    assert _direct_calc_uses("calc_hwm_sigma_levels(s)")
    assert not _direct_calc_uses("from services.fund_position import compute_fund_position")


def test_no_consumer_bypasses_ssot():
    offenders = {}
    for top in ("ui", "services", "scripts"):
        for p in (ROOT / top).rglob("*.py"):
            rel = p.relative_to(ROOT).as_posix()
            if rel in _WHITELIST:
                continue
            hits = _direct_calc_uses(p.read_text(encoding="utf-8"))
            if hits:
                offenders[rel] = hits
    for p in ROOT.glob("*.py"):
        hits = _direct_calc_uses(p.read_text(encoding="utf-8"))
        if hits:
            offenders[p.name] = hits
    assert not offenders, f"HWM σ 必須經 compute_fund_position(2C SSOT):{offenders}"


# ═══ 11. 禁字守衛 ═══════════════════════════════════════════════════════════

def _all_outputs():
    s, divs = _monthly_div_fund()
    idx = pd.bdate_range("2023-01-02", periods=120)
    cases = [
        {"series": _noisy()},
        {"series": s, "dividends": divs},
        {"series": s, "dividends": [], "moneydj_raw": {"moneydj_div_yield": 5.0}},
        {"series": _noisy(n=20)},
        {"series": None},
        {"series": _noisy(), "moneydj_raw": {"category": "貨幣市場型"}},
        {"series": pd.Series(10.0, index=idx)},
        {"series": s, "dividends": list(divs) + [dict(divs[2])]},
        {"series": s, "dividends": [{"date": "2023-12-02", "amount": 0.05}]},   # 週六 → unreliable
    ]
    return [compute_fund_position(c) for c in cases]


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _strings(v)


def test_no_action_words_in_ssot_outputs():
    from services.fund_position import UNAVAILABLE_REASON_TEXT
    texts = list(_strings(_all_outputs()))
    texts += [lbl for lbl, _ in hwm_position_labels().values()]
    texts += list(UNAVAILABLE_REASON_TEXT.values())
    for r in (-0.1, -1.0, -2.5):
        texts.append(hwm_position_from_rank(r)[1])
    bad = [(t, w) for t in texts for w in FORBIDDEN if w in t]
    assert not bad, bad


def test_no_action_words_in_ssot_source_files():
    for rel in ("services/fund_position.py", "services/total_return_series.py"):
        txt = (ROOT / rel).read_text(encoding="utf-8")
        bad = [w for w in FORBIDDEN if w in txt]
        assert not bad, (rel, bad)
    # precision_service:HWM 位置相關函式內的字串常數(含 calc_hwm_sigma_levels 的 label)
    tree = ast.parse((ROOT / "services/precision_service.py").read_text(encoding="utf-8"))
    names = {"hwm_position_labels", "hwm_position_from_rank", "calc_hwm_sigma_levels",
             "_fmt_sigma_cut"}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    bad = [w for w in FORBIDDEN if w in sub.value]
                    assert not bad, (node.name, sub.value, bad)


# ═══ 批次版(回測用)與逐 t 呼叫逐位元相同 ═══════════════════════════════════

def _rand_fund(seed, kind):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2019-01-02", periods=700)
    s = pd.Series(10 * np.exp(np.cumsum(rng.normal(0.0002, 0.009, 700))), index=idx)
    divs = []
    if kind in ("div", "late_bad", "sat"):
        for d in idx[30::21]:
            divs.append({"date": d.strftime("%Y/%m/%d"), "amount": round(float(rng.uniform(0.02, 0.06)), 4)})
            s[idx >= d] -= divs[-1]["amount"]
    if kind == "late_bad":           # 全段還原會失敗(配息 ≥ NAV 在 t 之後)→ 批次必須退回逐 t
        divs.append({"date": idx[650].strftime("%Y-%m-%d"), "amount": 999.0})
    if kind == "sat":                # 一筆對不上淨值日(週六)
        sat = next(d for d in pd.date_range(idx[400], idx[-1]) if d.dayofweek == 5)
        divs.append({"date": sat.strftime("%Y-%m-%d"), "amount": 0.03})
    return {"series": s, "dividends": divs,
            "moneydj_raw": {"moneydj_div_yield": 5.0 if divs else None}}


@pytest.mark.parametrize("seed,kind", [(1, "div"), (2, "nodiv"), (3, "late_bad"), (4, "sat")])
def test_batch_positions_equal_per_t(seed, kind):
    from services.fund_position import compute_fund_positions_at
    fund = _rand_fund(seed, kind)
    idx = fund["series"].index
    dates = [idx[i] for i in (5, 29, 30, 100, 260, 399, 400, 500, 649, 650, 699)]
    batch = compute_fund_positions_at(fund, dates)
    for t in dates:
        single = compute_fund_position(fund, as_of=t)
        assert batch[t] == single, (kind, t)


def test_backtest_prefilled_sigma_equals_per_t_calls():
    """回測預算(每檔還原一次)的 σ 與逐 t 呼叫 `_sigma_rank_at` 完全相同。"""
    from services.allocation_backtest import (
        _fund_at, _preparse_meta, _sigma_rank_at, rebalance_dates,
    )
    from services.fund_position import compute_fund_positions_at
    from services.allocation_backtest import _sigma_from_position
    funds = {f"F{i}": _rand_fund(10 + i, k) for i, k in enumerate(("div", "nodiv", "sat"))}
    orig = {c: f["series"] for c, f in funds.items()}
    meta = _preparse_meta({c: {"dividends": f["dividends"], "moneydj_raw": f["moneydj_raw"]}
                           for c, f in funds.items()})
    rd = rebalance_dates(orig["F0"].index)
    for c in orig:
        fund = _fund_at(c, orig, meta)
        pre = {t: _sigma_from_position(p) for t, p in compute_fund_positions_at(fund, rd).items()}
        for t in rd:
            assert pre[t] == _sigma_rank_at(fund, t), (c, t)


# ═══ 必修 A:consumer 層 —— 配息基金但完全沒有配息紀錄 → raw 會 ok,SSOT 必須 ⬜ ═══

def _div_fund_no_records(code="DX"):
    s, _ = _monthly_div_fund()
    return {"code": code, "name": "DivNoRecords", "series": s, "dividends": [],
            "moneydj_raw": {"moneydj_div_yield": 9.6, "category": "債券型"},
            "metrics": {}, "risk_metrics": {}}


def test_case_premise_raw_would_be_ok():
    """前提:同一序列拿原始 NAV 算會 ok(而且是遠離高點)—— 所以下列 consumer 若偷用 raw 必露餡。"""
    raw = calc_hwm_sigma_levels(_div_fund_no_records()["series"])
    assert "error" not in raw and raw["position"] == "far_from_high"
    assert compute_fund_position(_div_fund_no_records())["reason"] == "dividend_data_missing"


def test_consumer_hwm_sigma_by_code():
    from services.fund_grp_health.risk import hwm_sigma_by_code
    out = hwm_sigma_by_code([_div_fund_no_records()])["DX"]
    assert out["σ rank"] == "—" and out["HWM"] == "—" and out["距 HWM %"] == "—"
    assert out["HWM 位階"].startswith("⬜")
    # 現價是已知事實 → 照實顯示原始最新淨值(不是 '—')
    assert out["現價"] == f"{float(_div_fund_no_records()['series'].iloc[-1]):.2f}"


def test_consumer_screen_funds():
    from services.fund_screening import screen_funds
    it = dict(_div_fund_no_records(), currency="USD", category="債券型", eats_principal=False)
    assert screen_funds([it]) == []
    rows = screen_funds([it], only_low_base=False)
    assert rows and rows[0]["base"] == "unknown" and rows[0]["sigma_rank"] is None


def test_consumer_allocation_backtest_with_and_without_meta():
    from services.allocation_backtest import backtest_allocations, strategy_weights_at
    f = _div_fund_no_records()
    s = f["series"]
    t = s.index[-1]
    twd_df = pd.DataFrame({"DX": s})
    meta = {"DX": {"dividends": f["dividends"], "moneydj_raw": f["moneydj_raw"]}}
    for m in (meta, None):
        _, sig = strategy_weights_at("S3", t, {"DX": s}, twd_df, None, meta_by_code=m)
        assert sig["DX"]["nav_level"] == "unknown" and sig["DX"]["sigma_rank"] is None
    res = backtest_allocations({"DX": s}, {"DX": "TWD"}, None, meta_by_code=meta)
    assert res["ok"]
    assert all(v["nav_level"] == "unknown" for v in res["results"]["S3"]["final_signals"].values())
    res2 = backtest_allocations({"DX": s}, {"DX": "TWD"}, None)
    assert all(v["sigma_rank"] is None for v in res2["results"]["S1"]["final_signals"].values())


class _FakeSt:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def _rec(*a, **k):
            self.calls.append((name, a))
        return _rec


def test_consumer_far_from_high_list(monkeypatch):
    import ui.helpers.fund_grp_health.risk as R
    fake = _FakeSt()
    monkeypatch.setattr(R, "st", fake)
    R._render_oversold_badges([_div_fund_no_records()])
    names = [n for n, _ in fake.calls]
    # 2026-10-23 BL-0428 DG-1 A:~~全 ⬜ 時綠色 success「目前無基金位於遠離高點區」~~
    # → 灰色 caption 揭露 ⬜ 檔數,不得用綠色成功框
    assert "success" not in names
    assert any(n == "caption" and "位置無法判定" in str(a) for n, a in fake.calls)
    assert not any("DivNoRecords" in str(a) for n, a in fake.calls if n == "markdown")


def test_consumer_tab2_card_and_ai_line():
    from ui.tab2_single_fund import _tab2_hwm_ai_line, _tab2_hwm_position
    r = _tab2_hwm_position(_div_fund_no_records())
    assert r["status"] == "unavailable" and r["sigma_rank"] is None
    line = _tab2_hwm_ai_line(_div_fund_no_records())
    assert line.startswith("- σ絕對位階：⬜") and "σ_rank" not in line


def test_consumer_tab3_advisor():
    from services.policy_advisor_service import INSUFFICIENT_DATA, advise_fund
    from ui.tab3_portfolio import _hwm_sigma_info_for
    si = _hwm_sigma_info_for(_div_fund_no_records())
    assert "error" in si and si["sigma_rank"] is None
    assert advise_fund(si, {"alert_level": "green", "coverage": 1.2}, "up", 35.0)["code"] \
        == INSUFFICIENT_DATA


def test_consumer_tab1_enrich():
    from ui.tab1_macro import _enrich_fund_for_decision
    si = _enrich_fund_for_decision(_div_fund_no_records())["sigma_info"]
    assert si["status"] == "unavailable" and si["sigma_rank"] is None and "error" in si


def test_consumer_ai_cross_fund_snapshot():
    from ui.helpers.fund_grp_health.ai import _build_cross_fund_snapshot
    snap, _ = _build_cross_fund_snapshot([_div_fund_no_records()])
    # 2026-10-23 BL-0428 DG-1 A:~~「0 檔 / 1」(分母含 ⬜)~~ → 分母只算可判定,⬜ 另列
    assert "遠離高點(σ rank ≤ −1.5,研究候選門檻、未校準):0 檔 / 0 檔可判定" in snap
    assert "⬜ 位置無法判定(資料不足／無法判定):1 檔" in snap
    assert "σ 位置:⬜" in snap
    assert "平均 σ rank" not in snap


def test_tab3_has_single_ssot_call_site():
    """tab3 三處都經 `_hwm_sigma_info_for`(唯一一處把 fund dict 交給 SSOT 的地方)。"""
    src = (ROOT / "ui/tab3_portfolio.py").read_text(encoding="utf-8")
    assert src.count("import compute_fund_position") == 1   # 只有 helper 內那一處 import
    assert src.count("_hwm_sigma_info_for(") == 4      # 定義 1 + 呼叫 3
