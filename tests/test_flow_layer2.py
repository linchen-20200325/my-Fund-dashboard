"""Layer 2「基金核心分析」稽核修正的回歸鎖(2026-08-14)。

本檔只鎖 Layer 2 這一輪動到的四件事,每一條都必須**改回舊行為就紅**
(PROCESS §4:紅得起來才算測試,不然只是把現況抄一遍當綠燈)。

涵蓋:
  A1  批次部分失敗不得標「✅ 成功」        `ui/helpers/fund_grp_health/unified.py`
                                          `ui/tab_batch_analysis.split_status_counts`
  C4  吃本金 `_adr_pct` 回傳 → 換標建議消費  `services/health/{dividend,replacement}.py`
  E1  1Y 含息報酬合理性閘 + 停止短窗外推     `services/fund_total_return.py`
  F12 大表揭露「這列用幾筆淨值算的」         `services/health/report._nav_sample_label`

⚠️ 本檔刻意**不**碰網路 —— 全部以 monkeypatch 注入假的 fetch 結果,
   讓測試在沒有 secrets / 沒有外網的環境也能跑真行為(不是 skip 掉變假綠)。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parent.parent


# ── 共用 fixture helper ────────────────────────────────────────────────
def _series(n_points: int, span_days: int, start: float = 10.0,
            end: float | None = None) -> pd.Series:
    """等距 n 點、跨 span_days 天的 NAV 序列(線性由 start 走到 end)。

    ⚠️ 刻意用**小數天**當間距而不是四捨五入到整天:整天會在
    `n_points > span_days` 時產生重複索引,而 `compute_1y_total_return`
    的 `index.get_indexer(..., method="nearest")` 遇到非唯一索引會直接拋
    `InvalidIndexError` —— 測試會炸在 fixture 上,而不是炸在要驗的邏輯上。
    跨度以 `.days` 取整後仍等於 `span_days`。
    """
    end = start if end is None else end
    _t0 = pd.Timestamp("2026-01-01")
    _den = max(n_points - 1, 1)
    idx = pd.DatetimeIndex(
        [_t0 + pd.Timedelta(days=span_days * i / _den) for i in range(n_points)])
    assert idx.is_unique and idx.is_monotonic_increasing, "fixture 索引須唯一且升序"
    vals = [start + (end - start) * i / _den for i in range(n_points)]
    return pd.Series(vals, index=idx)


# ══════════════════════════════════════════════════════════════════════
# A1 — 批次「部分成功」三態
# ══════════════════════════════════════════════════════════════════════
def _fake_base(code: str) -> dict:
    """process_one_fund 的最小可用回傳(ok=True,足以走完 build_batch_unified_row)。"""
    return {
        "code": code, "ok": True, "基金名": "測試基金",
        "ccy": "USD", "fx_spot": 32.0,
        "_nav_date": "2026-08-13", "_fund_raw": {}, "_principal_twd": 1_000_000.0,
    }


def _patch_batch_all_ok(monkeypatch):
    """把 `build_batch_unified_row` 會碰到的**所有外部依賴**換成成功的假貨。

    刻意逐一列出而不是攏統 mock:這幾支裡有真的會打網路的
    (`capture_by_code` 走大盤基準、`fx_regime_by_ccy` 抓 USDTWD)。
    不釘死的話,測試在無外網環境會因為「真的抓失敗」而變成部分成功 ——
    看起來是綠的(斷言剛好通過),實際上根本沒測到我們要測的邏輯(PROCESS §4)。
    """
    import services.fund_row as _fr
    # 2026-08-14 Layer 3-C:匯率快取下沉 L2,production 從這裡讀 → 靶點跟著改
    import services.fx_regime_service as _fxr
    import services.health.report as _rep
    from ui.helpers.fund_grp_health import _utils as _u
    from ui.helpers.fund_grp_health import unified as U

    monkeypatch.setattr(_fr, "process_one_fund",
                        lambda code, principal_twd=1_000_000.0, **kw: _fake_base(code))
    monkeypatch.setattr(_u, "_build_fund_dict",
                        lambda fd, code, principal_twd=None, **kw: {"code": code})
    monkeypatch.setattr(_rep, "build_health_analysis_row", lambda fd, code, **kw: {})
    monkeypatch.setattr(_rep, "build_dividend_summary_row", lambda fd, code, **kw: {})
    monkeypatch.setattr(U, "build_merged_extra_columns",
                        lambda funds, phase="", score=None: ([], {}))
    monkeypatch.setattr(U, "compute_switch_columns", lambda row: {})
    monkeypatch.setattr(U, "compute_regime_fit_column", lambda row, phase: {})
    monkeypatch.setattr(U, "compute_nav_fx_column", lambda row, fxmap: {})
    monkeypatch.setattr(_fxr, "fx_regime_by_ccy", lambda *a, **kw: {})
    return U


def test_batch_all_ok_still_plain_success(monkeypatch):
    """反向護欄:沒有任何欄組失敗時,不得誤標「部分成功」(避免過度告警)。

    這條同時是上面三條的**前提檢查** —— 它若紅了,代表 `_patch_batch_all_ok`
    沒有真的把所有依賴釘住,下面那三條的綠燈就不可信。
    """
    U = _patch_batch_all_ok(monkeypatch)
    row = U.build_batch_unified_row("TESTCODE")
    assert row["狀態"] == "✅ 成功"
    assert row["備註"] is None


def test_batch_partial_failure_is_not_marked_success(monkeypatch):
    """**改回舊行為必紅** —— ① 健康分析算爆時,那一列不得標「✅ 成功」。

    舊碼三段 `except` 各自把欄組設成 `{}`,然後**無條件**寫
    `out["狀態"] = "✅ 成功"` / `out["備註"] = None`。於是 13 個欄位留白的列
    在 400 列裡與正常列完全同形,使用者只會讀成「這檔沒有這些資料」。
    """
    import services.health.report as _rep

    U = _patch_batch_all_ok(monkeypatch)

    def _boom(*a, **kw):
        raise RuntimeError("① 故意炸掉")

    monkeypatch.setattr(_rep, "build_health_analysis_row", _boom)

    row = U.build_batch_unified_row("TESTCODE")
    assert "部分成功" in str(row["狀態"]), (
        f"① 欄組失敗卻標成 {row['狀態']!r} —— 部分失敗被當成完全成功(稽核 A1)")
    assert row["備註"], "部分成功必須在備註寫出缺了哪一組,否則使用者無從得知"
    assert "①" in str(row["備註"])


def test_batch_post_merge_failure_is_caught(monkeypatch):
    """**改回舊行為必紅** —— post-merge 三組欄原本不在任何 try 內。

    舊碼一旦 `compute_switch_columns` 拋例外,會一路穿透到 `app.py` 的
    `with tab_batch:`,**整個 App 從批次分頁往下全白**,而且 400 檔跑到一半的
    結果會一起消失。現在應收成「④ 部分成功」而不是外拋。
    """
    U = _patch_batch_all_ok(monkeypatch)

    def _boom(*a, **kw):
        raise RuntimeError("④ 故意炸掉")

    monkeypatch.setattr(U, "compute_switch_columns", _boom)

    row = U.build_batch_unified_row("TESTCODE")   # 不得外拋
    assert "部分成功" in str(row["狀態"])
    assert "④" in str(row["備註"])


def test_split_status_counts_does_not_fold_partial_into_ok():
    """**改回舊行為必紅** —— 「部分成功」字面含「成功」。

    舊摘要用 `df["狀態"].str.contains("成功").sum()` 當 n_ok,
    會把部分成功算進全綠計數。三態必須各歸各的,且加總 = 總列數。
    """
    from ui.tab_batch_analysis import split_status_counts

    statuses = ["✅ 成功", "✅ 成功", "⚠️ 部分成功", "❌ 抓取失敗", "⚠️ 無效代號"]
    n_ok, n_partial, n_fail = split_status_counts(statuses)
    assert (n_ok, n_partial, n_fail) == (2, 1, 2)
    assert n_ok + n_partial + n_fail == len(statuses)


def test_status_column_help_documents_partial_state():
    """0-consumer 條款:新狀態必須在使用者 hover 得到的地方寫清楚。"""
    from ui.helpers.fund_grp_health.columns import batch_column_config

    _cfg = batch_column_config()
    for _col in ("狀態", "備註"):
        _help = str(getattr(_cfg[_col], "help", "") or _cfg[_col])
        assert "部分成功" in _help or "欄組" in _help, (
            f"「{_col}」欄 help 未說明部分成功,新狀態等於沒揭露")


def test_partial_success_is_retryable_but_not_counted_as_failure():
    """**稽核 🟠-7** —— 部分成功不算失敗,但必須進得了重試名單。

    分類與後果是兩件事:`_is_fail` 判 False 是對的(淨值抓到了),
    但如果重試也放不進來,使用者就看到一個自己無法處理的狀態 ——
    唯一出路變成整批清除重跑(400 檔 2~5 小時)。
    """
    from ui.tab_batch_analysis import _is_fail, _is_retryable

    _partial = {"狀態": "⚠️ 部分成功"}
    assert _is_fail(_partial) is False, "部分成功不該被計為失敗(統計會失真)"
    assert _is_retryable(_partial) is True, "部分成功進不了重試名單 = 使用者無路可走"
    assert _is_retryable({"狀態": "❌ 抓取失敗"}) is True
    assert _is_retryable({"狀態": "⚠️ 無效代號"}) is True
    assert _is_retryable({"狀態": "✅ 成功"}) is False, "完全成功的檔不該被重跑"


def test_late_added_columns_are_all_covered_by_stale_notice():
    """**稽核 🟠-8** —— 每個後來才加的欄都要進舊存檔提示,否則空白會冒充「沒資料」。

    舊 checkpoint 讀得回來(相容性檢查只驗「狀態」),`_build_df` 以固定欄骨架
    建表 → 缺鍵補空白。而新欄的 help 教使用者把空白讀成「連序列都沒拿到」。
    """
    from ui.helpers.fund_grp_health.unified import BATCH_UNIFIED_COLUMNS
    from ui.tab_batch_analysis import _LATE_ADDED_COLUMNS, _rows_missing_late_columns

    assert "淨值樣本" in _LATE_ADDED_COLUMNS, "新欄未登記 → 舊存檔會靜靜留白"
    for _c in _LATE_ADDED_COLUMNS:
        assert _c in BATCH_UNIFIED_COLUMNS, f"{_c} 已登記但不在批次欄骨架裡(登記過期)"

    # 模擬一份舊存檔:成功列缺兩個新欄
    _old = {"AAA": {"狀態": "✅ 成功"}, "BBB": {"狀態": "❌ 抓取失敗"}}
    _missing = _rows_missing_late_columns(_old)
    assert _missing.get("淨值樣本") == 1, "缺新欄的成功列沒被數到"
    assert "BBB" not in str(_missing), "失敗列本來就整列留白,不該混進提示"


# ══════════════════════════════════════════════════════════════════════
# C4 — 吃本金 `_adr_pct` → 換標建議(舊碼撈的 key 根本不存在)
# ══════════════════════════════════════════════════════════════════════
def _eating_fixture(nav_span_days: int = 400) -> dict:
    """會判出「吃本金」的基金:配息率 9%,含息報酬只有 ~2%。"""
    return {
        "series": _series(max(nav_span_days // 2, 3), nav_span_days, 10.0, 10.2),
        "dividends": [{"date": "2026-03-15", "amount": 0.075}],
        "metrics": {"annual_div_rate": 9.0},
        "moneydj_raw": {},
    }


def test_eating_principal_exposes_adr_pct():
    """**改回舊行為必紅** —— `check_eating_principal_1y_mk` 必須回傳 `_adr_pct`。

    `replacement.py` 規則 (b) 原本撈 `annual_div_rate_pct`,那個 key
    從來沒被產出過 → adr 恆 None → 4D 少一維 → 換標建議用的 grade
    與大表顯示的 grade **不同源**。

    ⚠️ 這裡跑**真實行為**而不是掃原始碼:前一輪稽核指出
    「assert 某字串在 / 不在 source」屬 PROCESS §4 明文禁止的寫法
    (把解釋寫進 docstring 就會誤紅 / 誤綠)。
    """
    from services.health.dividend import check_eating_principal_1y_mk

    res = check_eating_principal_1y_mk(_eating_fixture())
    assert res is not None
    assert res.get("_adr_pct") == pytest.approx(9.0), (
        f"未回傳 _adr_pct(實際 {res.get('_adr_pct')!r})—— 換標建議的配息維度會恆缺")


def test_replacement_rule_b_actually_uses_the_adr():
    """**改回舊行為必紅** —— 換標建議的 4D 必須真的吃到 adr(接線驗證,非字串比對)。

    驗法:同一檔基金,一次照常呼叫、一次把 `_adr_pct` 從結果裡拿掉,
    比較 `compute_4d_health` 收到的 `adr_pct` 參數。舊碼撈的是不存在的
    `annual_div_rate_pct`,兩次都會是 None → 斷言紅。
    """
    from services.health import replacement as R

    _seen: list = []
    _orig = None

    import services.health.grade as _G

    def _spy(**kw):
        _seen.append(kw.get("adr_pct"))
        return _orig(**kw)

    _orig = _G.compute_4d_health
    try:
        _G.compute_4d_health = _spy
        R.check_replacement_recommendation(_eating_fixture(), holding_years=2.0)
    finally:
        _G.compute_4d_health = _orig

    assert _seen, "compute_4d_health 沒被呼叫 —— 規則 (b) 整條沒跑到"
    assert _seen[0] is not None, (
        "規則 (b) 傳給 4D 的 adr_pct 是 None —— 消費端沒接上 _adr_pct")


def test_too_short_series_still_carries_adr(monkeypatch):
    """**稽核 🟠-3 的紅線** —— E1 把短窗改道之後,adr 不可以跟著蒸發。

    E1 前:短窗 → 外推有值 → 走「外推拒判」分支 → 回 grey dict(帶 adr)。
    E1 後若不處理:短窗 → tr1y=None → 舊的 `return None` → adr 一起消失
    → 換標建議規則 (b) 對這批基金**恆失效**,且燈號從 🟢 保留掉成 ⬜ 資料不足。
    """
    from services.health.dividend import check_eating_principal_1y_mk

    res = check_eating_principal_1y_mk(_eating_fixture(nav_span_days=60))
    assert res is not None, "有淨值序列、只是太短 —— 不可與『完全沒資料』一樣回 None"
    assert res["alert_level"] == "grey"
    assert res.get("_adr_pct") == pytest.approx(9.0)


def test_no_series_at_all_still_returns_none():
    """反向護欄:連序列都沒有時,必須維持既有契約回 None(不可被上一條帶壞)。"""
    from services.health.dividend import check_eating_principal_1y_mk

    assert check_eating_principal_1y_mk({"moneydj_div_yield": 5.0}) is None
    assert check_eating_principal_1y_mk({}) is None


# ══════════════════════════════════════════════════════════════════════
# E1 — 1Y 含息報酬:停止短窗外推 + 合理性閘
# ══════════════════════════════════════════════════════════════════════
def test_short_window_no_longer_extrapolated():
    """**改回舊行為必紅** —— 60 天資料不得再 ×6 外推成「一年報酬」。

    舊碼:跨度 ≥ 30 天就用 `min(365/d, 12)` 外推。一檔 30 天漲 17% 的基金
    會在大表印出「1Y 含息報酬 +201%」,而且因為數值大而排到最前面。
    現在跨度未達半年 → 誠實回 None,並在來源欄寫出只有幾天資料。
    """
    from services.fund_total_return import compute_1y_total_return

    fd = {"metrics": {}, "moneydj_raw": {}, "series": _series(40, 60, 10.0, 11.7)}
    val, src = compute_1y_total_return(fd)
    assert val is None, f"60 天資料仍被外推成 {val} —— 那不是量出來的一年報酬(稽核 E1)"
    assert "60" in src and "不足以推算一年" in src, f"來源欄未說明為什麼留白:{src!r}"


def test_long_window_still_annualized_but_capped():
    """跨度夠長仍要給值,且放大倍數受 SSOT 上限約束(不可回到 ×12)。"""
    from shared.signal_thresholds import RET_1Y_EXTRAPOLATE_MAX_SCALE
    from services.fund_total_return import compute_1y_total_return

    fd = {"metrics": {}, "moneydj_raw": {}, "series": _series(200, 200, 10.0, 11.0)}
    val, src = compute_1y_total_return(fd)
    assert val is not None, "跨度 200 天(> 半年)不該留白"
    _raw = (11.0 / 10.0 - 1.0) * 100.0
    # 精確驗算(不只驗「沒超過上限」—— 那條由建構保證,是恆真斷言)
    _expect = _raw * min(365.0 / 200.0, RET_1Y_EXTRAPOLATE_MAX_SCALE)
    assert val == pytest.approx(_expect, rel=1e-6), (
        f"外推公式漂移:raw={_raw:.4f} 期望 {_expect:.4f} 實得 {val:.4f}")
    assert "外推年化" in src and "200" in src


def test_extrapolation_floor_comes_from_ssot():
    """門檻不得寫死在函式裡(§3.3 反捏造:常數一律從 shared 引入)。"""
    from shared.signal_thresholds import (
        RET_1Y_EXTRAPOLATE_MAX_SCALE,
        RET_1Y_EXTRAPOLATE_MIN_DAYS,
        RET_1Y_PLAUSIBLE_MAX_PCT,
        RET_1Y_PLAUSIBLE_MIN_PCT,
    )
    assert RET_1Y_EXTRAPOLATE_MIN_DAYS >= 180
    # cap 必須與門檻自洽:跨度剛好達標時 365/d 不得超過 cap,否則 cap 形同虛設
    assert RET_1Y_EXTRAPOLATE_MAX_SCALE <= 365.0 / RET_1Y_EXTRAPOLATE_MIN_DAYS + 1e-9
    assert RET_1Y_PLAUSIBLE_MIN_PCT < 0 < RET_1Y_PLAUSIBLE_MAX_PCT


@pytest.mark.parametrize("bad", [201.65, 190.64, -99.0])
def test_implausible_1y_is_flagged_in_source_label(bad):
    """**改回舊行為必紅** —— 離譜的 1Y 必須自己在來源欄講話。

    201.65 / 190.64 是實測時大表上兩檔**台幣**基金印出來的數字,
    在畫面上與正常數字長得一模一樣,排序時還會衝到最前面。
    """
    from services.fund_total_return import (
        SRC_IMPLAUSIBLE_SUFFIX,
        compute_1y_total_return,
        is_implausible_1y,
    )

    assert is_implausible_1y(bad)
    fd = {"metrics": {}, "perf": {"1Y": bad}, "perf_source": "wb01"}
    val, src = compute_1y_total_return(fd)
    assert val == pytest.approx(bad), "閘只做標記,不得偷改值或丟值"
    assert SRC_IMPLAUSIBLE_SUFFIX in src, f"離譜值未被標記:{src!r}"


@pytest.mark.parametrize("good", [12.3, -30.0, 0.0, 149.0])
def test_plausible_1y_is_not_flagged(good):
    """反向護欄:正常值不得被貼警語(否則警語會被使用者當雜訊忽略)。"""
    from services.fund_total_return import (
        SRC_IMPLAUSIBLE_SUFFIX,
        compute_1y_total_return,
        is_implausible_1y,
    )

    assert not is_implausible_1y(good)
    _val, src = compute_1y_total_return(
        {"metrics": {}, "perf": {"1Y": good}, "perf_source": "wb01"})
    assert SRC_IMPLAUSIBLE_SUFFIX not in src


def test_is_implausible_1y_handles_none_and_nan():
    """缺值不是「離譜」—— 不可把 None / NaN 誤標成異常(§1 兩種狀態要分得開)。"""
    from services.fund_total_return import is_implausible_1y

    assert not is_implausible_1y(None)
    assert not is_implausible_1y(float("nan"))
    assert not is_implausible_1y("—")


# ══════════════════════════════════════════════════════════════════════
# F12 — 大表揭露「這一列是用幾筆淨值算的」
# ══════════════════════════════════════════════════════════════════════
def test_nav_sample_label_marks_short_span():
    """**改回舊行為必紅** —— 只抓到「近30日淨值表」的列必須帶 ⚠️。

    實測 ACCP138:`nav=30 筆`、跨度 42 天 → Sharpe / σ / Max DD / 3Y 5Y 年化
    全數留白,4D Score 照樣給分。沒有這一欄,使用者分不出
    「這檔沒有波動風險」與「我們沒有足夠淨值去算它的波動」。
    """
    from services.health.report import _nav_sample_label

    lbl = _nav_sample_label({"series": _series(30, 42)})
    assert lbl.startswith("⚠️"), f"短窗未標警示:{lbl!r}"
    assert "30 筆" in lbl and "42 天" in lbl


def test_nav_sample_label_long_history_has_no_warning():
    """反向護欄:正常長歷史不得被貼 ⚠️。"""
    from services.health.report import _nav_sample_label

    lbl = _nav_sample_label({"series": _series(400, 700)})
    assert not lbl.startswith("⚠️")
    assert "400 筆" in lbl


def test_nav_sample_label_single_point_is_not_safer_looking():
    """**稽核 🟠-6** —— 1 筆是最極端的短窗,不可回一個沒有 ⚠️ 的字串。

    否則它在表上看起來比「⚠️ 30 筆 · 42 天」還安全,嚴重度與標示反向。
    """
    from services.health.report import _nav_sample_label

    lbl = _nav_sample_label({"series": _series(1, 0)})
    assert lbl.startswith("⚠️"), f"單點序列未標警示:{lbl!r}"


def test_nav_sample_label_survives_non_series_shape():
    """list / dict 形狀不可炸(舊 cache 與部分 fixture 就是這種),且不得謊稱正常。"""
    from services.health.report import _nav_sample_label

    for _bad in ([10.0, 10.1, 10.2], {"2026-01-01": 10.0, "2026-01-02": 10.1}):
        lbl = _nav_sample_label({"series": _bad})
        assert lbl.startswith("⚠️") or lbl.startswith("⬜"), (
            f"非 Series 形狀回了看起來正常的標籤:{lbl!r}")


def test_nav_sample_label_missing_series_is_honest():
    """連序列都沒有 → ⬜,不可回空字串或 0 筆(§1 缺資料要講出來)。"""
    from services.health.report import _nav_sample_label

    assert _nav_sample_label({}) == "⬜ 無淨值序列"
    assert _nav_sample_label({"series": pd.Series(dtype=float)}) == "⬜ 無淨值序列"


def test_nav_sample_label_reads_nested_shape():
    """巢狀 fd(Tab2 / Tab3 shape)也要抓得到 series,否則那兩處恆顯示 ⬜。"""
    from services.health.report import _nav_sample_label

    lbl = _nav_sample_label({"moneydj_raw": {"series": _series(300, 500)}})
    assert "300 筆" in lbl


def test_nav_sample_threshold_is_ssot():
    """⚠️ 切點必須與大表「短窗」判定同源,不得各寫一個數字。

    走 AST 而不是字串比對:`_nav_sample_label` 的 **docstring 裡就寫著**
    `NAV_SHORT_WINDOW_MAX_DAYS`,用 `in source` 檢查的話,把 import 整行刪掉
    改寫死 90,這條測試照樣綠(PROCESS §4 恆真型假綠)。
    """
    import ast
    import inspect
    import textwrap

    from services.health import report as _rep

    _tree = ast.parse(textwrap.dedent(inspect.getsource(_rep._nav_sample_label)))
    _imported = {
        _a.name
        for _n in ast.walk(_tree) if isinstance(_n, ast.ImportFrom)
        for _a in _n.names
        if (_n.module or "").startswith("shared.signal_thresholds")
    }
    assert "NAV_SHORT_WINDOW_MAX_DAYS" in _imported, (
        "_nav_sample_label 未從 shared/signal_thresholds import 切點,"
        "改成 inline 數字就會與大表分歧(§3.3)")
    # 反向:函式體內不得出現裸的門檻數字
    _nums = {_n.value for _n in ast.walk(_tree)
             if isinstance(_n, ast.Constant) and isinstance(_n.value, (int, float))
             and not isinstance(_n.value, bool)}
    from shared.signal_thresholds import NAV_SHORT_WINDOW_MAX_DAYS
    assert NAV_SHORT_WINDOW_MAX_DAYS not in _nums, (
        f"函式體內出現裸數字 {NAV_SHORT_WINDOW_MAX_DAYS} —— 常數被抄了第二份")


def test_nav_sample_column_is_wired_everywhere():
    """0-consumer 條款:新欄必須同時進 row、進欄序、進 column_config help。"""
    from services.health.report import HEALTH_COLUMNS
    from ui.helpers.fund_grp_health.columns import health_column_config
    from ui.helpers.fund_grp_health.unified import (
        BATCH_UNIFIED_COLUMNS,
        _UNIFIED_FRONT,
    )

    assert "淨值樣本" in HEALTH_COLUMNS
    _front = [c for c, _ in _UNIFIED_FRONT]
    assert "淨值樣本" in _front
    assert "淨值樣本" in BATCH_UNIFIED_COLUMNS
    _spec = health_column_config()["淨值樣本"]
    _help = str(getattr(_spec, "help", "") or _spec)
    assert "筆" in _help and "留白" in _help, "新欄沒有 help = 使用者看不懂那串數字"


def test_nav_sample_sits_before_the_columns_it_qualifies():
    """欄序不是美觀問題:它是右邊那排數字的可信度前提,必須先被看到。"""
    from ui.helpers.fund_grp_health.unified import _UNIFIED_FRONT

    _front = [c for c, _ in _UNIFIED_FRONT]
    for _later in ("4D Grade", "4D Score", "Sharpe 1Y", "Max DD %"):
        assert _front.index("淨值樣本") < _front.index(_later), (
            f"「淨值樣本」排在 {_later} 後面 —— 使用者會先讀到數字才讀到樣本量")


# ══════════════════════════════════════════════════════════════════════
# D1 — 個基深掘手動匯率不得預填 32(前一步已改,這裡上鎖)
# ══════════════════════════════════════════════════════════════════════
def test_manual_fx_input_has_no_prefilled_number():
    """**改回舊行為必紅** —— 手動匯率欄不得預設 32.0(走 AST,不掃字串)。

    舊碼 `value=32.0`:日圓(≈0.21)/ 南非幣(≈1.7)基金一進來就帶著美元匯率,
    而下方換匯算式只印 `÷ 32.0000` 這個裸數字,完全看不出是預設值 ——
    差一個數量級,下面所有金額全錯。
    """
    import ast

    _tree = ast.parse((_ROOT / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8"))
    _found = False
    for _n in ast.walk(_tree):
        if not isinstance(_n, ast.Call):
            continue
        _kw = {k.arg: k.value for k in _n.keywords if k.arg}
        _key = _kw.get("key")
        if not (isinstance(_key, ast.JoinedStr)
                and any(isinstance(v, ast.Constant) and "_calc_fx_" in str(v.value)
                        for v in _key.values)):
            continue
        _found = True
        _val = _kw.get("value")
        assert isinstance(_val, ast.Constant) and _val.value is None, (
            f"手動匯率輸入框仍有預設值 {getattr(_val, 'value', _val)!r}(稽核 D1)")
    assert _found, "找不到手動匯率輸入框 —— 測試已與實作脫節,請更新選取條件"


def test_calc_block_is_gated_on_having_an_fx():
    """**🔴 稽核駁回項的紅線** —— 非台幣基金沒有匯率時,試算區必須整塊不算。

    改成 `value=None` 只解決了一半:舊的 gate 只看 `_nav_calc > 0`,
    非台幣基金在匯率留空時會掉進 `else: _amt_local = 台幣金額` —— 等於把
    100 萬台幣當成 100 萬日圓,三個 metric 照樣印出來(差約 4.8 倍),
    而畫面上那句 st.info 明明寫著「暫不計算……寧可不算也不給你一個錯的數字」。
    這裡鎖住:計算區的條件式必須同時檢查匯率是否備妥。
    """
    import ast

    _src = (_ROOT / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert "_fx_ready" in _src, "計算區未加入匯率備妥判斷(承諾與行為不符)"
    _tree = ast.parse(_src)
    _gated = [
        _n for _n in ast.walk(_tree)
        if isinstance(_n, ast.If)
        and any(isinstance(_x, ast.Name) and _x.id == "_fx_ready"
                for _x in ast.walk(_n.test))
        and any(isinstance(_x, ast.Name) and _x.id == "_nav_calc"
                for _x in ast.walk(_n.test))
    ]
    assert _gated, (
        "找不到同時檢查 `_nav_calc` 與 `_fx_ready` 的條件式 —— "
        "非台幣基金在匯率留空時仍會用 fx=1.0 算出金額")
