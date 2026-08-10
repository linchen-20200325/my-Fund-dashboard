"""tests/test_compare_inception_years.py — MK 3-3-3 成立年數對照器（唯讀診斷工具）。

守三件事：
1. **轉錄等價鎖**：`scripts/compare_inception_years.py` 裡 B 版是
   `services/fund_row.py::process_one_fund` 內嵌 3-3-3 區塊的手抄本（該區塊沒被抽成
   函式，無法 import）。本組拿同一批 fixture 餵**真的** `process_one_fund`，比對手抄本
   的輸出必須逐字相同 —— 內嵌邏輯一改而手抄本沒跟上，本組立刻紅。
   （fixture 幣別用 TWD → `process_one_fund` 走 fx=1.0 短路，全程零網路。）
2. **A 端零轉錄**：對照器 A 版必須直接呼 production 函式，不得自己重寫一份。走 AST。
3. **「成立日只在 metrics」是空集合**：這是本次不收斂兩份演算法的查證基礎 ——
   `finalize_fund_metrics` 只有在頂層 `inception_date` 已有值時才會往 metrics 複製，
   所以「只有 metrics 帶成立日」的基金不存在。若日後有人加了獨立 writer，本組會紅，
   查證結論就要重跑。

修正前紅不紅
============
1/2/4/5 條：**ImportError 紅**（`scripts/compare_inception_years.py` 本次才新增）。
3 條（finalize 不變量）：本次前**綠** —— 它鎖的是既有行為，不是新行為；
它的價值在「日後有人破壞查證前提時會紅」，不在「證明本次改對了」。
"""
from __future__ import annotations

import ast
import datetime as _dt
import sys
from pathlib import Path

import pandas as pd
import pytest

# scripts/ 不在 default sys.path —— 顯式加 repo root（同 tests/test_update_macro_history.py）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# prime 匯入順序:services.fund_service ↔ fund_fetcher 為既有 latent 互相 import
# （同 tests/test_nav_history_consume.py 的處置）
import fund_fetcher  # noqa: F401,E402

from scripts.compare_inception_years import (  # noqa: E402
    diagnose,
    variant_b_nav_dict,
    variant_b_status,
    variant_b_years,
)

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "scripts" / "compare_inception_years.py"


def _today_naive() -> pd.Timestamp:
    """本機當日（tz-naive）—— fixture 一律相對今天生成，避免寫死日期日後過期。"""
    return pd.Timestamp.today().normalize()


def _fd_twd(*, inception=None, n=900, start="2018-01-01", recent=False,
            ret_3y_ann=9.0, index=None, drop_perf_3y=False):
    """TWD 計價 fd —— `process_one_fund` 對 TWD 走 fx=1.0，不打 FX API。

    recent=True → 序列尾端貼齊今天（用來製造「短歷史」情境，不寫死年份）。
    """
    if index is not None:
        idx = index
    elif recent:
        idx = pd.date_range(end=_today_naive(), periods=n, freq="D")
    else:
        idx = pd.date_range(start, periods=n, freq="D")
    s = pd.Series([10.0 + (i % 50) * 0.02 for i in range(len(idx))], index=idx)
    fd = {
        "series": s,
        "dividends": [],
        "currency": "TWD",
        "fund_name": "對照測試基金",
        "metrics": {"nav": 11.0, "ret_3y_ann": ret_3y_ann, "div_freq_n": 12},
        "perf": {"1Y": 5.0} if drop_perf_3y else {"1Y": 5.0, "3Y": 20.0},
    }
    if inception is not None:
        fd["inception_date"] = inception
    return fd


# ══════════════════════════════════════════════════════════════════════
# 1. 轉錄等價鎖 —— 手抄本 vs 真的 process_one_fund
# ══════════════════════════════════════════════════════════════════════
_CASES = {
    # 成立日齊全、年化達標 → 應為通過
    "inception_pass": dict(inception="2008-03-01", ret_3y_ann=9.0),
    # 成立日齊全、年化不足 → 應為明確未通過
    "inception_fail_return": dict(inception="2008-03-01", ret_3y_ann=3.0),
    # 成立日齊全但未滿 3 年 → 明確未通過
    "inception_too_young": dict(
        inception=(_dt.date.today() - _dt.timedelta(days=400)).isoformat()),
    # 成立日格式壞掉 → 兩版都該退回 NAV 首日推算
    "inception_garbage": dict(inception="民國97年3月1日"),
    # 沒有成立日、長序列 → NAV 首日推算
    "no_inception_long": dict(inception=None),
    # 沒有成立日、短序列 → 兩版都該誠實回資料不足（不可硬報 0.x 年）
    "no_inception_short": dict(inception=None, n=30, recent=True),
    # 沒有成立日、3 年年化整個抓不到 → 三態應停在「資料不足」
    "no_ann_3y": dict(inception="2008-03-01", ret_3y_ann=None, drop_perf_3y=True),
}


@pytest.mark.parametrize("case", sorted(_CASES))
def test_variant_b_matches_real_process_one_fund(case):
    """手抄本輸出必須等於 production 內嵌邏輯的輸出（逐字）。

    這條是本工具唯一的 SSOT 保護：拿掉 `fund_row.py` 3-3-3 區塊的任何一個分支、
    或改動門檻，本條就會紅。
    """
    from services.fund_row import process_one_fund

    fd = _fd_twd(**_CASES[case])
    row = process_one_fund(case, 1_000_000.0, fd=fd)
    assert row.get("ok") is True, f"fixture 本身跑不起來：{row.get('error')}"
    assert row["MK 3-3-3 篩"] == variant_b_status(fd)


def test_variant_b_short_series_is_data_insufficient_not_zero_years():
    """§1：無成立日 + 序列過短 → 誠實回 None，不得硬報 0.x 年然後判 ❌。"""
    fd = _fd_twd(inception=None, n=30, recent=True)
    assert variant_b_years(fd, variant_b_nav_dict(fd)) is None


# ══════════════════════════════════════════════════════════════════════
# 2. A 端零轉錄（AST）
# ══════════════════════════════════════════════════════════════════════
def _script_tree() -> ast.Module:
    return ast.parse(_SCRIPT.read_text(encoding="utf-8"), filename=str(_SCRIPT))


def test_comparator_calls_production_for_variant_a():
    """A 版必須 import production 函式，不能自己重寫一份成立年演算法。

    若對照器自己抄一份 A，量出來的差異就是「兩份手抄本」的差異，結論不可信。
    """
    imported: set = set()
    for node in ast.walk(_script_tree()):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imported.add(f"{node.module}.{alias.name}")
    assert "services.health.report._compute_holding_years" in imported
    assert "services.health.report.build_health_analysis_row" in imported
    assert "services.health.dividend.check_333_principle" in imported


def test_comparator_does_not_import_streamlit():
    """腳本層不得依賴 streamlit（無 runtime session，且會拖慢啟動）。"""
    mods: set = set()
    for node in ast.walk(_script_tree()):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert "streamlit" not in mods


# ══════════════════════════════════════════════════════════════════════
# 3. 查證前提鎖：metrics 的成立日永遠只是頂層的副本
# ══════════════════════════════════════════════════════════════════════
def _noisy(idx):
    import numpy as np
    rng = np.random.default_rng(7)
    return pd.Series(10 * np.cumprod(1 + rng.normal(0.0003, 0.01, len(idx))),
                     index=idx, dtype=float)


def test_metrics_inception_never_written_without_toplevel(monkeypatch):
    """頂層沒有成立日 → metrics 也不會憑空長出一個。

    這是「A 多讀 metrics 那條分支在 production 不可達」的執行時證據。
    """
    from services import nav_history_gs as GS
    from services.fund_service import finalize_fund_metrics
    monkeypatch.setattr(GS, "load_series", lambda code: pd.Series(dtype=float))

    result = {"series": _noisy(pd.bdate_range("2020-01-01", periods=400)),
              "dividends": [], "fund_code": "X"}
    finalize_fund_metrics(result)
    assert (result.get("metrics") or {}).get("inception_date") is None


def test_metrics_inception_is_a_copy_of_toplevel(monkeypatch):
    """頂層有成立日 → metrics 拿到的是**同一個值**（副本，非獨立來源）。"""
    from services import nav_history_gs as GS
    from services.fund_service import finalize_fund_metrics
    monkeypatch.setattr(GS, "load_series", lambda code: pd.Series(dtype=float))

    result = {"series": _noisy(pd.bdate_range("2020-01-01", periods=400)),
              "dividends": [], "fund_code": "X",
              "inception_date": "2011-09-30"}
    finalize_fund_metrics(result)
    assert result["metrics"]["inception_date"] == result["inception_date"]


# ══════════════════════════════════════════════════════════════════════
# 4. diagnose：有成立日 → 兩版必然一致；無成立日 → 才可能分歧
# ══════════════════════════════════════════════════════════════════════
def test_diagnose_reports_no_diff_when_inception_present():
    fd = _fd_twd(inception="2008-03-01")
    r = diagnose(fd, "SAME")
    assert r["differs"] is False
    assert r["years_a"] == pytest.approx(r["years_b"], abs=1e-9)
    assert not r["reasons"]


def test_diagnose_flags_today_basis_gap_when_no_inception():
    """無成立日時，A 用 UTC 當日、B 用本機當日 → 差 N 天必須被抓出來並歸因。

    這裡把 B 的「今日」往後推 2 天來確定性重現該分支（推 2 天而非 1 天，
    避開跨 UTC 午夜跑測試時多算/少算一天的競態）。
    """
    fd = _fd_twd(inception=None, n=900, start="2018-01-01")
    _b_today = _dt.datetime.now(_dt.timezone.utc).date() + _dt.timedelta(days=2)
    r = diagnose(fd, "TZGAP", today_local=_b_today)
    assert r["differs"] is True
    assert r["reasons"], "有差異就必須說得出來源，不可只報一個 True"
    # 只斷言「B 比 A 多算了至少半天、至多四天」——不寫死天數，避開跨 UTC 午夜競態
    _gap = r["years_b"] - r["years_a"]
    assert 0.5 / 365.25 < _gap < 4.0 / 365.25


def test_diagnose_flags_sample_count_gap_on_duplicate_dates():
    """同日重複：A 數列長度、B 數不重複日期 → 90 筆門檻兩邊踩在不同時機。

    這是「A 會硬報 0.x 年 ❌、B 誠實回資料不足 ⬜」的唯一已知真實觸發路徑
    （方向與稽核表的假設相反 —— 誠實的是 B 不是 A）。
    """
    base = pd.date_range(end=_today_naive(), periods=50, freq="D")
    idx = pd.DatetimeIndex(sorted(list(base) + list(base)))   # 100 筆 / 50 個日期
    fd = _fd_twd(inception=None, index=idx)
    r = diagnose(fd, "DUPDATE")
    assert r["n_series"] == 100 and r["n_nav_dict"] == 50
    assert r["years_a"] is not None      # A：len(series)=100 ≥ 90 → 照報約 0.x 年
    assert r["years_b"] is None          # B：不重複日期 50 < 90 且 < 0.5 年 → 資料不足
    assert r["differs"] is True and r["reasons"]


# ══════════════════════════════════════════════════════════════════════
# 5. 快照 round-trip：離線重跑不得把差異來源抹掉
# ══════════════════════════════════════════════════════════════════════
def test_snapshot_roundtrip_preserves_duplicate_dates():
    """快照若把 NAV 壓成 date→value dict，同日重複會消失 → 量出假的零差異。"""
    from scripts.compare_inception_years import fd_to_snapshot, snapshot_to_fd

    base = pd.date_range(end=_today_naive(), periods=50, freq="D")
    idx = pd.DatetimeIndex(sorted(list(base) + list(base)))
    fd = _fd_twd(inception=None, index=idx)
    fd2 = snapshot_to_fd(fd_to_snapshot(fd))
    assert len(fd2["series"]) == len(fd["series"])
    assert diagnose(fd2, "RT")["n_nav_dict"] == diagnose(fd, "RT")["n_nav_dict"]
