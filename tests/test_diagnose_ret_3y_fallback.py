"""tests/test_diagnose_ret_3y_fallback.py — MK 3-3-3 C2 取值鏈診斷器的回歸網。

守六件事
========
1. **歸因對帳鎖**:診斷器自己算的「命中第幾步」必須與 production 等價鏈值
   (`scripts/compare_inception_years.variant_b_ann_3y`,已被該檔測試釘住 =
   `services/fund_row.py` 內嵌區塊)完全一致。fixture 刻意讓三步帶**互相衝突**
   的數字 —— 順序一寫錯,對帳立刻不成立。
2. **描述 = 現實**:診斷器印的「現況判定」必須逐字等於**真的** `process_one_fund`
   產出的那一欄。這條是 PROCESS §4 的接線驗證:診斷器算得再漂亮,只要跟大表
   對不上就是廢的。
3. **零行為改動**:跑完診斷後,`fd` / `fd["metrics"]` 一個字都不能變,
   production 判定前後必須完全相同。把試算值偷偷回灌進 metrics 這條測試會紅。
4. **口徑揭露**:命中步驟 3(MoneyDJ 含息)與時間軸試算(純 NAV)必須標成
   **不同**口徑,而且吃步驟 3 的基金要掛翻面警告(§4.1)。
5. **零轉錄 + 無 inline magic**(AST):值一律呼 production;
   點數門檻不得以字面值出現,必須從 `shared/signal_thresholds` 推得(§3.3)。
6. **快照 round-trip**:離線重跑不得把診斷結論弄丟;且必須吃得下舊格式快照
   (`compare_inception_years` 那版),否則既有 snapshot 立刻報廢。

Test Liveness(PROCESS §4)
=========================
本組**全離線、零 skip、零外部工具**:fixture 全部是就地生成的 pandas Series,
幣別一律 TWD → `process_one_fund` 走 fx=1.0 短路,不打任何網路。
沒有任何一條測試會因「環境缺件」變 skip —— 缺件的話是紅的。

修正前會不會紅
==============
全部條目在本次之前都是 **ImportError 紅**(`scripts/diagnose_ret_3y_fallback.py`
本次才新增)。其中第 1、2、3 條即使在檔案存在後,也會在「取值順序寫錯 / 診斷器
偷改 fd / 顯示字串與大表不同源」時各自變紅,不是只驗 import 得起來。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# prime 匯入順序:services.fund_service ↔ fund_fetcher 為既有 latent 互相 import
import fund_fetcher  # noqa: F401,E402

from scripts.compare_inception_years import (  # noqa: E402
    fd_to_snapshot as base_fd_to_snapshot,
    variant_b_ann_3y,
)
from scripts.diagnose_ret_3y_fallback import (  # noqa: E402
    BASIS_NAV_ONLY,
    BASIS_TOTAL_RETURN,
    chain_steps,
    diagnose_3y,
    fd_to_snapshot,
    freq_label,
    points_required_for_metrics_3y,
    render_report,
    series_facts,
    snapshot_to_fd,
    time_axis_probe,
)

_REPO = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO / "scripts" / "diagnose_ret_3y_fallback.py"


# ══════════════════════════════════════════════════════════════════════
# fixture — 一律相對「今天」生成,不寫死年份(避免日後過期)
# ══════════════════════════════════════════════════════════════════════
def _today() -> pd.Timestamp:
    return pd.Timestamp.today().normalize()


def _nav(periods: int, freq: str, step_growth: float = 0.0,
         start_nav: float = 10.0) -> pd.Series:
    idx = pd.date_range(end=_today(), periods=periods, freq=freq)
    vals = [start_nav * ((1.0 + step_growth) ** i) for i in range(len(idx))]
    return pd.Series(vals, index=idx, dtype=float)


def _fd(series, *, metrics=None, perf=None, nested_perf=None,
        inception="2018-09-26", name="診斷測試基金") -> dict:
    fd = {
        "series": series,
        "dividends": [],
        "currency": "TWD",                       # → process_one_fund 走 fx=1.0
        "fund_name": name,
        "inception_date": inception,
        "metrics": {"nav": float(series.iloc[-1]), "div_freq_n": 12,
                    **(metrics or {})},
        "perf": dict(perf or {}),
    }
    if nested_perf is not None:
        fd["moneydj_raw"] = {"perf": dict(nested_perf)}
    return fd


def _fd_short_window():
    """實測症狀重現:日更 NAV 但只抓回短窗、MoneyDJ 績效表整包是空的。

    (= user 那 5 檔 AC* 的形狀:成立很久、序列只有一小段、perf = {})
    """
    return _fd(_nav(30, "B"), perf={})


def _fd_wb01_rescue():
    """對照組:序列一樣短,但 MoneyDJ 績效表有 3Y → 靠步驟 3 撐起判定。"""
    return _fd(_nav(30, "B"), perf={"1Y": 12.66, "3Y": 35.44})


def _fd_weekly_history():
    """第四層真的救得到的形狀:週更淨值、4 年歷史 → 點數永遠不夠但時間夠。"""
    return _fd(_nav(209, "W", step_growth=0.0015), perf={})


def _fd_step1():
    """步驟 1 就有值 → 第四層永遠輪不到。"""
    return _fd(_nav(30, "B"), metrics={"ret_3y_ann": 9.0}, perf={"3Y": 35.44})


# ══════════════════════════════════════════════════════════════════════
# 1. 歸因對帳鎖 —— 三步帶衝突數字,順序寫錯立刻紅
# ══════════════════════════════════════════════════════════════════════
_ATTRIB_CASES = {
    # (metrics 覆蓋, perf, 預期命中步驟)
    "all_three_conflict": ({"ret_3y_ann": 9.0, "ret_3y_cum": 20.0,
                            "ret_3y": 44.0}, {"3Y": 90.0}, 1),
    "step1_missing":      ({"ret_3y_cum": 20.0}, {"3Y": 90.0}, 2),
    "only_ret_3y_legacy": ({"ret_3y": 20.0}, {"3Y": 90.0}, 2),
    "step12_missing":     ({}, {"3Y": 90.0}, 3),
    "nothing_anywhere":   ({}, {}, None),
    "perf_without_3y":    ({}, {"1Y": 12.0, "5Y": 60.0}, None),
}


@pytest.mark.parametrize("case", sorted(_ATTRIB_CASES))
def test_attribution_matches_locked_production_chain(case):
    """命中步驟的歸因 → 值必須等於 production 等價鏈值。

    三步的數字刻意互不相同(9 / 20 / 90),取值順序一寫反,`attribution_ok`
    就會是 False,而且 `hit_step` 也會對不上預期。
    """
    _m, _p, _expect_step = _ATTRIB_CASES[case]
    fd = _fd(_nav(30, "B"), metrics=_m, perf=_p)
    row = diagnose_3y(fd, case)

    assert row["hit_step"] == _expect_step
    assert row["attribution_ok"] is True, (
        f"歸因 {row['hit_value_pct']} vs production 鏈值 {row['chain_value_pct']}")
    _chain = variant_b_ann_3y(fd)
    if _chain is None:
        assert row["chain_value_pct"] is None
    else:
        assert row["chain_value_pct"] == pytest.approx(float(_chain), abs=1e-9)


def test_step2_reads_both_legacy_keys():
    """步驟 2 的兩個 key 都要吃到(ret_3y_cum 缺 → 退 ret_3y)。"""
    fd = _fd(_nav(30, "B"), metrics={"ret_3y": 20.0})
    assert chain_steps(fd)["raw_step2"] == pytest.approx(20.0)


# ══════════════════════════════════════════════════════════════════════
# 2. 描述 = 現實(接線驗證,PROCESS §4)
# ══════════════════════════════════════════════════════════════════════
_REALITY_CASES = {
    "short_window": _fd_short_window,
    "wb01_rescue": _fd_wb01_rescue,
    "weekly_history": _fd_weekly_history,
    "step1_hit": _fd_step1,
}


@pytest.mark.parametrize("case", sorted(_REALITY_CASES))
def test_current_status_equals_real_process_one_fund(case):
    """診斷器印的「現況判定」必須逐字等於健診大表那一欄。"""
    from services.fund_row import process_one_fund

    fd = _REALITY_CASES[case]()
    real = process_one_fund(case, 1_000_000.0, fd=fd)
    assert real.get("ok") is True, f"fixture 跑不起來:{real.get('error')}"
    assert diagnose_3y(fd, case)["current_status"] == real["MK 3-3-3 篩"]


def test_short_window_case_is_really_blocked_and_not_fixable_by_layer4():
    """實測症狀那一組:三步全空 → ⬜;而且第四層**救不了**(序列根本沒 3 年)。"""
    fd = _fd_short_window()
    row = diagnose_3y(fd, "SHORT")

    assert row["hit_step"] is None                     # 三步全空
    assert row["perf_origin"] is None                  # perf = {} → 步驟 3 沒得取
    assert row["n_points"] < row["points_required"]    # 點數卡在門檻下
    assert row["span_years"] < 3.0                     # 跨度也不足 3 年
    assert row["freq_label"] == freq_label(1.0)        # 是日更,不是月配淨值
    assert row["hypo_ann_pct"] is None                 # 時間軸切法一樣切不出來
    assert row["would_apply"] is False
    assert row["would_change"] is False
    assert row["current_status"].startswith("⬜")


def test_weekly_history_case_is_the_one_layer4_would_fix():
    """週更 + 4 年歷史 = 點數不夠但時間夠 → 這才是第四層救得到的形狀。"""
    fd = _fd_weekly_history()
    row = diagnose_3y(fd, "WEEKLY")

    assert row["hit_step"] is None
    assert row["n_points"] < row["points_required"]
    assert row["span_years"] > 3.0                     # 時間是夠的
    assert row["freq_label"] == freq_label(7.0)        # 病灶是頻率不是歷史
    assert row["hypo_ann_pct"] is not None
    assert row["would_apply"] is True
    assert row["would_change"] is True
    assert row["current_status"].startswith("⬜")
    assert row["would_status"].startswith("✅")


# ══════════════════════════════════════════════════════════════════════
# 3. 零行為改動 —— 診斷器不得回灌任何值
# ══════════════════════════════════════════════════════════════════════
def test_diagnose_never_writes_back_into_fd():
    """跑完診斷後 production 判定必須完全不變,metrics 也不得長出新欄位。

    把時間軸試算值偷偷寫回 `fd["metrics"]["ret_3y_ann"]`(最容易犯的錯)
    會讓 `after` 從 ⬜ 變 ✅ → 本條紅。
    """
    from services.fund_row import process_one_fund

    fd = _fd_weekly_history()
    before = process_one_fund("W", 1_000_000.0, fd=fd)["MK 3-3-3 篩"]
    metrics_before = dict(fd["metrics"])
    perf_before = dict(fd["perf"])

    row = diagnose_3y(fd, "W")
    assert row["hypo_ann_pct"] is not None      # 確定這條路徑真的算出東西了

    after = process_one_fund("W", 1_000_000.0, fd=fd)["MK 3-3-3 篩"]
    assert after == before
    assert dict(fd["metrics"]) == metrics_before
    assert dict(fd["perf"]) == perf_before
    assert "ret_3y_ann" not in fd["metrics"]


def test_time_axis_probe_does_not_mutate_metrics():
    """試算會複製 metrics 再挖空 —— 原 dict 不得被挖。"""
    fd = _fd(_nav(209, "W", step_growth=0.0015),
             metrics={"ret_3y_ann": 9.0, "ret_3y_cum": 20.0})
    probe = time_axis_probe(fd)
    assert probe["ann_pct"] is not None          # 有被強迫走 NAV 分支
    assert fd["metrics"]["ret_3y_ann"] == pytest.approx(9.0)
    assert fd["metrics"]["ret_3y_cum"] == pytest.approx(20.0)


# ══════════════════════════════════════════════════════════════════════
# 4. 口徑揭露(§4.1)
# ══════════════════════════════════════════════════════════════════════
def test_step3_is_labelled_total_return_and_flagged_for_flip():
    fd = _fd_wb01_rescue()
    row = diagnose_3y(fd, "WB01")
    assert row["hit_step"] == 3
    assert row["hit_basis"] == BASIS_TOTAL_RETURN
    assert row["basis_downgrade_risk"] is True
    assert row["perf_origin"] == "fd.perf"


def test_step1_is_labelled_nav_only_and_not_flagged():
    row = diagnose_3y(_fd_step1(), "S1")
    assert row["hit_step"] == 1
    assert row["hit_basis"] == BASIS_NAV_ONLY
    assert row["basis_downgrade_risk"] is False
    assert row["would_apply"] is False          # 前面有值 → 第四層輪不到


def test_layer4_basis_differs_from_step3_basis():
    """第四層是純 NAV、步驟 3 是含息 —— 兩者若標成同一個口徑,警示就失效了。"""
    assert BASIS_NAV_ONLY != BASIS_TOTAL_RETURN
    row = diagnose_3y(_fd_weekly_history(), "W")
    assert row["hypo_basis"] == BASIS_NAV_ONLY
    assert row["hypo_basis"] != BASIS_TOTAL_RETURN


def test_nested_perf_origin_is_reported():
    """perf 掛在 moneydj_raw 底下時,來源要標成 nested 而不是 top-level。"""
    fd = _fd(_nav(30, "B"), perf={}, nested_perf={"3Y": 35.44})
    row = diagnose_3y(fd, "NESTED")
    assert row["perf_origin"] == "fd.moneydj_raw.perf"
    assert row["hit_step"] == 3


# ══════════════════════════════════════════════════════════════════════
# 5. 序列事實 —— 頻率診斷欄
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("freq,periods", [("B", 60), ("W", 60), ("ME", 60)])
def test_freq_label_distinguishes_update_cadence(freq, periods):
    """日 / 週 / 月三種更新頻率必須落在三個不同的標籤,否則這欄沒有診斷力。"""
    facts = series_facts(_fd(_nav(periods, freq)))
    assert facts["n_points"] == periods
    assert facts["median_gap_days"] is not None
    assert facts["freq_label"] == freq_label(facts["median_gap_days"])


def test_freq_labels_are_actually_three_different_values():
    labels = {
        series_facts(_fd(_nav(60, f)))["freq_label"] for f in ("B", "W", "ME")
    }
    assert len(labels) == 3


def test_series_facts_on_missing_series_is_honest():
    """無序列 → 誠實回 0 點 + 說明,不得偽造任何跨度(§1)。"""
    facts = series_facts({"metrics": {}})
    assert facts["n_points"] == 0
    assert facts["span_years"] is None
    assert facts["series_note"]


def test_points_required_comes_from_ssot():
    from shared.signal_thresholds import TRADING_DAYS_PER_YEAR
    assert points_required_for_metrics_3y() == 3 * TRADING_DAYS_PER_YEAR


# ══════════════════════════════════════════════════════════════════════
# 6. AST — 零轉錄 / 無 inline magic / 不碰 streamlit
# ══════════════════════════════════════════════════════════════════════
def _script_tree() -> ast.Module:
    return ast.parse(_SCRIPT.read_text(encoding="utf-8"), filename=str(_SCRIPT))


def _imported_symbols() -> set:
    out: set = set()
    for node in ast.walk(_script_tree()):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                out.add(f"{node.module}.{alias.name}")
    return out


def test_values_all_come_from_production():
    """診斷器不得自己重寫任何演算法 —— 值一律呼 production / 已上鎖的手抄本。"""
    imported = _imported_symbols()
    for _sym in (
        "services.fund_screening.check_333_fund",          # 時間軸切法
        "services.fund_service.assess_series_coverage",    # 覆蓋率
        "services.health.dividend.check_333_principle",    # 三態判定
        "scripts.compare_inception_years.variant_b_ann_3y",   # 取值鏈等價值
        "scripts.compare_inception_years.variant_b_status",   # 顯示字串
        "scripts.compare_inception_years.variant_b_years",    # 成立年數
        "shared.signal_thresholds.TRADING_DAYS_PER_YEAR",  # 點數門檻
    ):
        assert _sym in imported, f"{_sym} 沒有被 import —— 是不是自己抄了一份?"


def test_no_inline_window_constants():
    """§3.3:點數門檻不得以字面值出現,必須由 SSOT 常數推得。"""
    from shared.signal_thresholds import TRADING_DAYS_PER_YEAR

    banned = {TRADING_DAYS_PER_YEAR, 3 * TRADING_DAYS_PER_YEAR}
    hits = [
        n.value for n in ast.walk(_script_tree())
        if isinstance(n, ast.Constant) and isinstance(n.value, int)
        and not isinstance(n.value, bool) and n.value in banned
    ]
    assert not hits, f"發現寫死的門檻字面值:{hits}"


def test_script_does_not_import_streamlit():
    mods: set = set()
    for node in ast.walk(_script_tree()):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert "streamlit" not in mods


# ══════════════════════════════════════════════════════════════════════
# 7. 快照 round-trip + 舊格式相容
# ══════════════════════════════════════════════════════════════════════
_ROUNDTRIP_KEYS = ("n_points", "hit_step", "would_apply", "perf_origin",
                   "freq_label", "attribution_ok")


def test_snapshot_roundtrip_preserves_diagnosis():
    fd = _fd_weekly_history()
    fd2 = snapshot_to_fd(fd_to_snapshot(fd))
    a, b = diagnose_3y(fd, "RT"), diagnose_3y(fd2, "RT")
    for k in _ROUNDTRIP_KEYS:
        assert a[k] == b[k], f"欄位 {k} 在快照 round-trip 後改變了"
    assert a["span_years"] == pytest.approx(b["span_years"], abs=1e-9)
    assert a["hypo_ann_pct"] == pytest.approx(b["hypo_ann_pct"], abs=1e-9)


def test_snapshot_keeps_perf_and_step3_value():
    fd = _fd_wb01_rescue()
    fd2 = snapshot_to_fd(fd_to_snapshot(fd))
    assert diagnose_3y(fd2, "RT")["hit_step"] == 3


def test_old_format_snapshot_still_loads():
    """既有 `compare_inception_years` 快照(無 metrics_extra / perf_nested)必須照吃。

    否則 user 手上已經 dump 出來的快照會在本工具上直接報廢。
    """
    fd = _fd_wb01_rescue()
    fd2 = snapshot_to_fd(base_fd_to_snapshot(fd))
    a, b = diagnose_3y(fd, "OLD"), diagnose_3y(fd2, "OLD")
    for k in _ROUNDTRIP_KEYS:
        assert a[k] == b[k]


# ══════════════════════════════════════════════════════════════════════
# 8. 報告本身 — 讀得懂、不炸
# ══════════════════════════════════════════════════════════════════════
def test_report_renders_and_names_the_blocked_funds():
    rows = [
        diagnose_3y(_fd_short_window(), "SHORT"),
        diagnose_3y(_fd_wb01_rescue(), "WB01"),
        diagnose_3y(_fd_weekly_history(), "WEEKLY"),
    ]
    text = render_report(rows)
    for _code in ("SHORT", "WB01", "WEEKLY"):
        assert _code in text
    # 每一檔都要有「為什麼」,不能只丟一個 True/False
    for r in rows:
        assert r["explain"]
        assert r["explain"] in text


def test_report_on_empty_input_does_not_crash():
    assert render_report([])
