"""tests/test_ssot_3a_333.py — 2026-10-23 客戶裁示 3A:3-3-3 唯一 SSOT。

釘住五件事(派工單 §3):
  (a) `calc_metrics.ret_3y_ann_tr` = 還原序列(Adj_NAV)最近 3×252 筆窗端點年化
      `(Adj_end/Adj_start)^(252/n) − 1`,且 = meta `ret_3y_ann_tr_pct`(Calmar 分子)同一值;
      `ret_3y_div_count` = 窗內被還原的配息筆數;`ret_3y_window_days` = 窗實際日曆天數。
  (b) wb01 `perf["3Y"]` 存在但無 `ret_3y_ann_tr` → derive 回 (None, ⬜…),
      `check_333_principle` → passed None(不是 False)。
  (c) 配息型且 `ret_3y_div_count == 0` → ⬜ 配息資料未備。
  (d) 年化恰 7.0 → passed False(「> 7%」規則);9.14 → True。
  (e) `batch_333_funds` 輸出無 C3 / 同儕欄,且每列與逐檔 SSOT 一致;
      `check_333_fund` 在 ui/** 與 services/** 只剩定義與註解(AST,不靠 grep 字串)。

突變驗證(2026-10-23 實跑,改後跑、再還原):
  1. 把 `derive_ann_3y_for_333` 改回「無 ret_3y_ann_tr 時退 `ret_3y_ann` 純淨值」
     → (b) / 短歷史 / `test_batch_rows_equal_per_fund_ssot` 的 ⬜ 列轉紅。
  2. 把 `batch_333_funds` 改回呼叫 `check_333_fund`
     → (e) 的欄位斷言與 AST 守衛轉紅。
全部離線、零網路:fixture 為就地生成的 pandas Series。
"""
from __future__ import annotations

import ast
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import fund_fetcher  # noqa: F401  — prime services.fund_service ↔ fund_fetcher 既有 latent 互相 import

from services.fund_service import calc_metrics, calculate_fund_total_return
from services.health.dividend import (
    ANN3Y_BASIS_RESTORED,
    ANN3Y_LABEL_DIV_MISSING,
    ANN3Y_LABEL_HISTORY_SHORT,
    ANN3Y_LABEL_NONE,
    THREE_THREE_THREE_MIN_ANN_RETURN_PCT,
    THREE_THREE_THREE_MIN_YEARS,
    check_333_principle,
    derive_ann_3y_for_333,
    derive_years_for_333,
    resolve_ann_3y_for_333_detail,
)
from services.fund_screening import batch_333_funds
from shared.signal_thresholds import TRADING_DAYS_PER_YEAR

_REPO = Path(__file__).resolve().parents[1]
_WINDOW_3Y = 3 * TRADING_DAYS_PER_YEAR


# ══════════════════════════════════════════════════════════════════════
# fixture:4 年日頻 NAV + 每 21 個交易日配一次息(≈ 月配),固定日期避免 flaky
# ══════════════════════════════════════════════════════════════════════
def _nav_4y(daily_growth: float = 0.0003, start: float = 10.0) -> pd.Series:
    idx = pd.bdate_range(end="2026-10-20", periods=4 * TRADING_DAYS_PER_YEAR)
    return pd.Series(start * np.cumprod(np.full(len(idx), 1.0 + daily_growth)), index=idx)


def _monthly_divs(idx: pd.DatetimeIndex, amount: float = 0.05) -> list[dict]:
    return [{"date": str(d.date()), "amount": amount} for d in idx[::21]]


def _hand_3y_tr(nav: pd.Series, divs: list[dict]) -> tuple[float, int, int]:
    """手算:(年化 %, 窗內配息筆數, 窗實際天數)。公式照派工單 §3(a) 逐字寫,不呼 production。"""
    tr = calculate_fund_total_return(
        pd.DataFrame({"Date": nav.index, "NAV": nav.values}),
        pd.DataFrame([{"Date": pd.to_datetime(d["date"]), "Dividend": d["amount"]} for d in divs]),
    )
    adj = tr["Adj_NAV"].to_numpy()
    n = _WINDOW_3Y
    ann = ((adj[-1] / adj[-n]) ** (TRADING_DAYS_PER_YEAR / n) - 1.0) * 100.0
    div_cnt = int((tr["Dividend"].to_numpy()[-n:] > 0).sum())
    days = int((nav.index[-1] - nav.index[-n]).days)
    return ann, div_cnt, days


# ══════════════════════════════════════════════════════════════════════
# (a) ret_3y_ann_tr = 還原序列 3Y 窗端點年化,= Calmar 分子
# ══════════════════════════════════════════════════════════════════════
def test_a_ret_3y_ann_tr_matches_hand_calculation_and_calmar_numerator():
    nav = _nav_4y()
    divs = _monthly_divs(nav.index)
    m = calc_metrics(nav, divs)
    hand_ann, hand_cnt, hand_days = _hand_3y_tr(nav, divs)

    assert m["ret_3y_ann_tr"] is not None
    # 一級鍵與 meta(Calmar 分子)是**同一個值**(2dp),不是第二個公式
    assert m["ret_3y_ann_tr"] == m["risk_metric_meta"]["calmar"]["ret_3y_ann_tr_pct"]
    # 與手算一致:production 存 2dp,故對 round(hand, 2) 取 ±1e-6;對原值差距不得超過半個 0.01
    assert math.isclose(m["ret_3y_ann_tr"], round(hand_ann, 2), abs_tol=1e-6)
    assert abs(m["ret_3y_ann_tr"] - hand_ann) <= 0.005 + 1e-9
    assert m["ret_3y_div_count"] == hand_cnt and hand_cnt > 0
    assert m["ret_3y_window_days"] == hand_days
    # 含息 > 純淨值(配息被還原進序列),且純淨值鍵名與值照舊存在
    assert m["ret_3y_ann"] is not None and m["ret_3y_ann_tr"] > m["ret_3y_ann"]


def test_a_no_dividend_fund_tr_equals_price_annualized():
    """無配息基金 s_tr ≡ s → 含息年化與純淨值年化同值(僅少一次中間 round,容差 0.01)。"""
    nav = _nav_4y()
    m = calc_metrics(nav, [])
    assert m["ret_3y_ann_tr"] is not None and m["ret_3y_div_count"] == 0
    assert abs(m["ret_3y_ann_tr"] - m["ret_3y_ann"]) <= 0.01 + 1e-9


def test_a_short_series_gives_none_not_short_window():
    """< 756 筆 → 三個鍵皆 None(§1 不以短窗充數),不是 0。"""
    nav = _nav_4y().tail(_WINDOW_3Y - 1)
    m = calc_metrics(nav, _monthly_divs(nav.index))
    assert m["ret_3y_ann_tr"] is None
    assert m["ret_3y_window_days"] is None
    assert m["ret_3y_div_count"] is None


# ══════════════════════════════════════════════════════════════════════
# (b) wb01 perf 有、ret_3y_ann_tr 無 → ⬜,passed None
# ══════════════════════════════════════════════════════════════════════
def test_b_wb01_perf_without_restored_value_is_grey():
    fd = {"perf": {"3Y": 35.44}, "perf_source": "wb01",
          "metrics": {"ret_3y_ann": 9.0, "ret_3y_cum": 29.5}}      # 純淨值也在,一樣不准頂上
    ann, basis = derive_ann_3y_for_333(fd)
    assert ann is None and basis == ANN3Y_LABEL_NONE
    r = check_333_principle(5.0, ann)
    assert r["passed"] is None and r["return_ok"] is None and r["years_ok"] is True
    d = resolve_ann_3y_for_333_detail(fd)
    assert d["status"] == "unavailable" and d["reason"] == "no_series"
    assert d["official_3y_ann_pct"] == pytest.approx(round(((1.3544) ** (1 / 3) - 1) * 100, 2))


def test_b_short_history_label_when_series_present():
    nav = _nav_4y().tail(300)
    fd = {"perf": {"3Y": 35.44}, "metrics": {"ret_3y_ann": 9.0}, "series": nav}
    assert derive_ann_3y_for_333(fd) == (None, ANN3Y_LABEL_HISTORY_SHORT)
    assert check_333_principle(5.0, None)["passed"] is None


# ══════════════════════════════════════════════════════════════════════
# (c) 配息型且窗內 0 筆 → ⬜ 配息資料未備
# ══════════════════════════════════════════════════════════════════════
def test_c_dividend_fund_with_zero_restored_dividends_is_grey():
    fd = {"moneydj_raw": {"moneydj_div_yield": 6.5},
          "metrics": {"ret_3y_ann_tr": 9.0, "ret_3y_div_count": 0, "ret_3y_window_days": 1090}}
    ann, basis = derive_ann_3y_for_333(fd)
    assert ann is None and basis == ANN3Y_LABEL_DIV_MISSING
    assert check_333_principle(5.0, ann)["passed"] is None
    # 同一檔若配息真的有被還原(count > 0)→ 正常給值
    fd["metrics"]["ret_3y_div_count"] = 12
    assert derive_ann_3y_for_333(fd) == (9.0, ANN3Y_BASIS_RESTORED)


def test_c_non_dividend_fund_zero_count_passes_gate():
    # 無任何配息跡象 → 不是配息基金 → count 0 不擋(無法證明它配息,不猜)
    fd = {"metrics": {"ret_3y_ann_tr": 9.0, "ret_3y_div_count": 0}}
    assert derive_ann_3y_for_333(fd) == (9.0, ANN3Y_BASIS_RESTORED)


# ══════════════════════════════════════════════════════════════════════
# (d) 門檻:恰 7.0 → False(> 7 規則);9.14 → True;門檻值走 SSOT 常數
# ══════════════════════════════════════════════════════════════════════
def test_d_threshold_strict_greater_than_seven():
    assert THREE_THREE_THREE_MIN_ANN_RETURN_PCT == 7.0 and THREE_THREE_THREE_MIN_YEARS == 3
    assert check_333_principle(5.0, 7.0)["passed"] is False
    assert check_333_principle(5.0, 9.14)["passed"] is True
    assert check_333_principle(2.9, 9.14)["passed"] is False      # 成立年數不足 = 明確反證
    assert check_333_principle(None, 9.14)["passed"] is None      # 缺成立年數 → ⬜


# ══════════════════════════════════════════════════════════════════════
# (e) batch_333_funds:無 C3 欄、與逐檔 SSOT 一致;check_333_fund 退役守衛
# ══════════════════════════════════════════════════════════════════════
def _batch_input():
    nav = _nav_4y()
    divs = _monthly_divs(nav.index)
    m_ok = calc_metrics(nav, divs)
    m_ok["inception_date"] = "2015-01-01"
    short = nav.tail(300)
    m_short = calc_metrics(short, _monthly_divs(short.index))
    return [
        {"code": "OK1", "name": "通過", "series": nav, "metrics": m_ok, "dividends": divs},
        # 配息型(wb05 > 0)但窗內 0 筆被還原 → ⬜ 配息資料未備
        {"code": "DIV0", "name": "配息未備", "series": nav,
         "metrics": {**m_ok, "ret_3y_div_count": 0}, "moneydj_raw": {"moneydj_div_yield": 6.0}},
        # 短歷史 + 成立日 → 成立年數有、3Y 無 → ⬜
        {"code": "SHORT", "name": "歷史不足", "series": short,
         "metrics": {**m_short, "inception_date": "2015-01-01"}},
        # 完全沒資料
        {"code": "NONE", "name": "無資料", "series": None, "metrics": {}},
        # 重複 code(去重契約照舊)
        {"code": "OK1", "name": "通過(重複)", "series": nav, "metrics": m_ok, "dividends": divs},
    ]


def test_e_batch_has_no_peer_columns_and_uses_tri_state():
    df = batch_333_funds(_batch_input())
    assert list(df.columns) == ["代碼", "名稱", "成立年數", "3Y 含息年化", "基準", "整體", "說明"]
    for col in df.columns:
        assert "③" not in col and "同儕" not in col and "C3" not in col
    assert df["代碼"].tolist() == ["OK1", "DIV0", "SHORT", "NONE"]
    assert df.set_index("代碼")["整體"].to_dict() == {"OK1": "✅", "DIV0": "⬜", "SHORT": "⬜", "NONE": "⬜"}
    assert set(df["整體"]) <= {"✅", "❌", "⬜"}           # 沒有 ❓,缺資料不是 ❌
    assert df.set_index("代碼")["基準"]["DIV0"] == ANN3Y_LABEL_DIV_MISSING
    assert df.set_index("代碼")["基準"]["SHORT"] == ANN3Y_LABEL_HISTORY_SHORT


def test_e_batch_rows_equal_per_fund_ssot():
    """每一列 = 逐檔呼叫 derive_years_for_333 + derive_ann_3y_for_333 + check_333_principle。"""
    items = _batch_input()
    df = batch_333_funds(items).set_index("代碼")
    seen = set()
    for f in items:
        if f["code"] in seen:
            continue
        seen.add(f["code"])
        s = f.get("series")
        first = str(pd.Timestamp(s.index[0]).date()) if s is not None and len(s) else None
        years, _ = derive_years_for_333((f.get("metrics") or {}).get("inception_date"), first)
        fd = {"moneydj_raw": f.get("moneydj_raw") or {}, "metrics": f.get("metrics") or {},
              "series": s, "dividends": f.get("dividends")}
        ann, basis = derive_ann_3y_for_333(fd, f.get("metrics") or {})
        r = check_333_principle(years, ann)
        row = df.loc[f["code"]]
        assert row["基準"] == basis
        assert row["說明"] == r["message"]
        assert row["整體"] == {True: "✅", False: "❌", None: "⬜"}[r["passed"]]
        assert row["3Y 含息年化"] == (f"{ann:.1f}%" if ann is not None else "—")
        assert row["成立年數"] == (f"{years:.1f}年" if years is not None else "—")


def _calls_and_imports_of(path: Path, name: str) -> tuple[list[int], list[int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    calls, imports = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if (isinstance(fn, ast.Name) and fn.id == name) or \
               (isinstance(fn, ast.Attribute) and fn.attr == name):
                calls.append(node.lineno)
        elif isinstance(node, ast.ImportFrom) and any(a.name == name for a in node.names):
            imports.append(node.lineno)
    return calls, imports


def test_e_check_333_fund_has_no_callers_in_ui_or_services():
    """退役守衛(AST,不靠 grep 字串):ui/** 與 services/** 不得呼叫或 import `check_333_fund`;
    `services/fund_screening.py` 只准剩它的 def(本體保留,待 legacy deletion gate)。"""
    offenders = []
    for p in list((_REPO / "ui").rglob("*.py")) + list((_REPO / "services").rglob("*.py")):
        calls, imports = _calls_and_imports_of(p, "check_333_fund")
        if calls or imports:
            offenders.append((str(p.relative_to(_REPO)), calls, imports))
    assert not offenders, f"check_333_fund 仍被呼叫 / import:{offenders}"
    tree = ast.parse((_REPO / "services" / "fund_screening.py").read_text(encoding="utf-8"))
    defs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "check_333_fund"]
    assert len(defs) == 1, "check_333_fund 本體應保留(不實體刪除)"
    assert "RETIRED" in ast.get_docstring(defs[0]), "docstring 須標示 retired"


def _string_constants(path: Path) -> list[str]:
    """檔內所有**字串常數**(含 f-string 的字面片段)。刻意不掃原始碼全文 —— 註解為了說明
    「移除了什麼」必然會引用被移除的字樣,掃全文會被自己的註解餵成恆紅(本 repo 已踩過的
    「註解錨點」陷阱,見 tests/test_domestic_perf_frozen.py)。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def test_e_tab2_and_tab3_wire_to_ssot():
    """Tab2 expander 與 Tab3 批次區改走 SSOT:Tab2 import check_333_principle;兩處渲染字串
    不再出現同儕 / 晨星 / ❓ 三態字樣(只看字串常數,不看註解)。"""
    tab2 = _REPO / "ui" / "tab2_single_fund.py"
    _, imp = _calls_and_imports_of(tab2, "check_333_principle")
    assert imp, "Tab2 _render_333_fund_expander 須 import check_333_principle"
    consts2 = _string_constants(tab2)
    for banned in ("同儕前1/3", "③晨星", "③ 晨星評級", "c2_return_3y", "overall_pass", "c1_pass"):
        hits = [c for c in consts2 if banned in c]
        assert not hits, f"Tab2 渲染字串仍殘留退役鏈字樣:{banned} → {hits[:2]}"
    tab3 = _REPO / "ui" / "tab3_portfolio.py"
    consts3 = _string_constants(tab3)
    for banned in ("③同儕排名", "②來源空", "③晨星評級", "晨星3星"):
        hits = [c for c in consts3 if banned in c]
        assert not hits, f"Tab3 渲染字串仍殘留退役鏈字樣:{banned} → {hits[:2]}"
    # 整體統計的三態符號:⬜ 在、❓ 不在(與 SSOT passed=None 對齊)
    src3 = tab3.read_text(encoding="utf-8")
    assert '_df_333["整體"] == "⬜"' in src3
    assert '_df_333["整體"] == "❓"' not in src3
