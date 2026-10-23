"""tests/test_ssot_3a_333.py — 2026-10-23 客戶裁示 3A:3-3-3 唯一 SSOT。

釘住五件事(派工單 §3):
  (a) `calc_metrics.ret_3y_ann_tr` = 還原序列(Adj_NAV)最近 3×252 筆窗端點年化
      `(Adj_end/Adj_start)^(252/n) − 1`,且 = meta `ret_3y_ann_tr_pct`(Calmar 分子)同一值;
      `ret_3y_div_count` = 窗內被還原的配息筆數;`ret_3y_window_days` = 窗實際日曆天數。
  (b) wb01 `perf["3Y"]` 存在但無 `ret_3y_ann_tr` → derive 回 (None, ⬜…),
      `check_333_principle` → passed None(不是 False)。
  (c) 配息型且 `ret_3y_div_count == 0` → ⬜ 配息資料未備。
  (d) 年化恰 7.0 → passed False(「> 7%」規則);9.14 → True。
  (e) `batch_333_funds` 欄數 / 欄序與 3A 之前相同(客戶 UI/Layout Gate `DEC-2026-10-23-04`:
      ③ 兩欄保留、只改名加註「參考，不計入 3-3-3 判定」、值恆「—」),且每列與逐檔 SSOT 一致;
      `check_333_fund` 在 ui/** 與 services/** 只剩定義與註解(AST,不靠 grep 字串)。
  (g) ③ 有值 / 無值兩種輸入 → 整體與 ①② 逐列相同(③ 不參與判定)。
  (h) Missing → ⬜ 不是 ❌(批次表、Tab2 判定卡;Tab2 ③ 列原位保留且無 ✅/❌)。

突變驗證(2026-10-23 實跑,改後跑、再還原):
  1. 把 `derive_ann_3y_for_333` 改回「無 ret_3y_ann_tr 時退 `ret_3y_ann` 純淨值」
     → (b) / 短歷史 / `test_batch_rows_equal_per_fund_ssot` 的 ⬜ 列轉紅。
  2. 把 `batch_333_funds` 改回呼叫 `check_333_fund`
     → (e) 的欄位斷言與 AST 守衛轉紅。
  3. 把「整體」改成受 ③ 影響(③ 為「—」→ 整體 ⬜)
     → (e)(g)(h) 的整體斷言轉紅。
  4. Tab2 `_icon(None)` 改 ❌ → (M4) 轉紅;計數改數原始配息清單 → (M5) 轉紅;
     mk_dashboard 換回 3A 前版本 → mk 同源 / AST 守衛轉紅;mk 候選加 ③ 波動篩選 → ③ 參考測試轉紅。
  (各突變的實跑結果見 commit message。)
  (M4) Tab2 判定卡 ② 缺值列圖示為 ⬜ 不是 ❌;(M5) 配息落在非淨值日不計數 → ⬜ 配息資料未備;
  mk_dashboard「3-3-3 篩選器」與 batch / check_333_principle 逐檔同源,⬜ 不進候選但計數;
  AST 守衛:ui/ 與 services/ 不得自寫「年資 >= 3」「報酬 > 7」字面門檻比較。
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
    ANN3Y_LABEL_NO_VALUE,
    ANN3Y_LABEL_NONE,
    THREE_THREE_THREE_MIN_ANN_RETURN_PCT,
    THREE_THREE_THREE_MIN_YEARS,
    check_333_principle,
    derive_ann_3y_for_333,
    derive_years_for_333,
    resolve_ann_3y_for_333_detail,
)
from services.fund_screening import COL_333_PEER_PASS, COL_333_PEER_RANK, batch_333_funds
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


# 3A 之前 `batch_333_funds` 的欄序(2026-10-23 以 main `2c11a2b` 實跑取得)。客戶 UI/Layout
# Decision Gate(`DEC-2026-10-23-04`):欄位增減屬版面變更 → 欄數與位置不得變,只准 ③ 兩欄改名加註。
_PRE_3A_COLUMNS = ["代碼", "名稱", "①成立年", "①通過", "②3年年化", "②通過",
                   "③同儕排名", "③通過", "整體"]
_ICON = {True: "✅", False: "❌", None: "⬜"}


def test_e_batch_keeps_layout_and_peer_columns_are_reference_only():
    df = batch_333_funds(_batch_input())
    assert list(df.columns) == ["代碼", "名稱", "①成立年", "①通過", "②3年年化", "②通過",
                                COL_333_PEER_RANK, COL_333_PEER_PASS, "整體"]
    assert len(df.columns) == len(_PRE_3A_COLUMNS)              # 欄數不變(不增不減)
    for _old, _new in zip(_PRE_3A_COLUMNS, df.columns):       # 每欄原位:同名,或只在 ③ 加註
        assert _new == _old or (_old.startswith("③") and _new.startswith(_old)
                                and "參考，不計入 3-3-3 判定" in _new)
    # ③ 不判定:兩欄只有「—」,絕無 ✅ / ❌(也沒有舊的 ❓)
    for _c in (COL_333_PEER_RANK, COL_333_PEER_PASS):
        assert set(df[_c]) == {"—"}
    assert df["代碼"].tolist() == ["OK1", "DIV0", "SHORT", "NONE"]
    assert df.set_index("代碼")["整體"].to_dict() == {"OK1": "✅", "DIV0": "⬜", "SHORT": "⬜", "NONE": "⬜"}
    for _c in ("①通過", "②通過", "整體"):
        assert set(df[_c]) <= {"✅", "❌", "⬜"}               # 沒有 ❓,缺資料不是 ❌
    _by = df.set_index("代碼")
    assert _by["②3年年化"]["DIV0"] == ANN3Y_LABEL_DIV_MISSING       # 缺值格寫原因
    assert _by["②3年年化"]["SHORT"] == ANN3Y_LABEL_HISTORY_SHORT


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
        assert row["整體"] == _ICON[r["passed"]]
        assert row["①通過"] == _ICON[r["years_ok"]]
        assert row["②通過"] == _ICON[r["return_ok"]]
        assert row["②3年年化"] == (f"{ann:.1f}%" if ann is not None else basis)
        assert row["①成立年"] == (f"{years:.1f}年" if years is not None else "—")


# ══════════════════════════════════════════════════════════════════════
# (g) ③ 有值 / 無值 → 整體相同(③ 不參與判定)
# ══════════════════════════════════════════════════════════════════════
def test_g_peer_data_present_or_absent_does_not_change_verdict():
    """同一批基金,一份帶上各種「同儕 / 晨星」資料(peer_series_map、同類排名、晨星星等),
    一份完全不帶 → 整體 / ①② 必須逐列相同,③ 兩欄仍只是「—」(不新增資料來源、不判定)。"""
    plain = _batch_input()
    with_peer = []
    for f in _batch_input():
        g = dict(f)
        g["peer_series_map"] = {"P1": f.get("series"), "P2": f.get("series")}
        g["metrics"] = {**(f.get("metrics") or {}), "c3_peer_rank_pct": 0.05, "c3_pass": True,
                        "peer_rank_pct": 0.95, "morningstar_rating": 1}
        g["moneydj_raw"] = {**(f.get("moneydj_raw") or {}),
                            "peer_compare": {"一年": {"同類排名": "40/45"}}}
        with_peer.append(g)
    a = batch_333_funds(plain).set_index("代碼")
    b = batch_333_funds(with_peer).set_index("代碼")
    for _c in ("整體", "①通過", "②通過", "②3年年化", "①成立年"):
        assert a[_c].to_dict() == b[_c].to_dict(), f"③ 資料改變了「{_c}」"
    for _c in (COL_333_PEER_RANK, COL_333_PEER_PASS):
        assert set(b[_c]) == {"—"}


def test_g_verdict_column_is_only_function_of_rules_1_and_2():
    """整體 ⇔ check_333_principle(①,②) 的 passed;① ② 都 ✅ 時整體必為 ✅(③ 恆「—」不擋)。"""
    df = batch_333_funds(_batch_input())
    both_ok = df[(df["①通過"] == "✅") & (df["②通過"] == "✅")]
    assert len(both_ok) >= 1 and set(both_ok["整體"]) == {"✅"}


# ══════════════════════════════════════════════════════════════════════
# (h) Missing → ⬜,不是 ❌(批次表 + Tab2 判定卡)
# ══════════════════════════════════════════════════════════════════════
def test_h_missing_3y_is_grey_not_red_in_batch():
    df = batch_333_funds(_batch_input()).set_index("代碼")
    for code in ("DIV0", "SHORT"):          # 成立年數 ≥ 3(成立日 2015)、3Y 含息缺
        assert df.loc[code, "①通過"] == "✅"
        assert df.loc[code, "②通過"] == "⬜" and df.loc[code, "整體"] == "⬜"
    assert df.loc["NONE", "整體"] == "⬜" and df.loc["NONE", "①通過"] == "⬜"
    assert "❌" not in set(df["整體"])


def test_h_label_no_value_is_grey():
    """序列 ≥ 756 筆但含息值缺(還原端點壞)→ label「⬜ 3 年含息年化不可得」,passed None。"""
    nav = _nav_4y()
    d = resolve_ann_3y_for_333_detail({"series": nav, "metrics": {}})
    assert d["status"] == "unavailable" and d["reason"] == "no_restored_value"
    assert d["label"] == ANN3Y_LABEL_NO_VALUE and d["value_pct"] is None
    assert check_333_principle(5.0, d["value_pct"])["passed"] is None


class _StRecorder:
    """最小 streamlit 替身:收集 markdown / caption 文字,不起 server。"""

    def __init__(self):
        self.texts: list[str] = []

    def markdown(self, body, *a, **k):
        self.texts.append(str(body))

    def caption(self, body, *a, **k):
        self.texts.append(str(body))

    def container(self, *a, **k):
        import contextlib
        return contextlib.nullcontext()


def _render_tab2(monkeypatch, nav, metrics, fd=None) -> str:
    import ui.tab2_single_fund as t2
    rec = _StRecorder()
    monkeypatch.setattr(t2, "st", rec)
    t2._render_333_fund_expander(nav, metrics, "測試基金", fd=fd)
    return "\n".join(rec.texts)


def _peer_row(html: str) -> str:
    i = html.index("③ 晨星評級 / 同儕前 1/3")
    return html[i:html.index("</tr>", i)]


def test_h_tab2_card_keeps_peer_row_reference_only_and_missing_is_grey(monkeypatch):
    nav = _nav_4y().tail(300)                      # 3Y 含息缺(歷史不足)
    out = _render_tab2(monkeypatch, nav, {"inception_date": "2015-01-01"})
    assert "⬜ 無法判定" in out and "未達標" not in out          # Missing → ⬜ 不是 ❌
    assert ANN3Y_LABEL_HISTORY_SHORT in out
    row3 = _peer_row(out)                                      # ③ 列仍在、原位
    assert "參考，不計入 3-3-3 判定" in row3 and "Morningstar" in row3
    assert not any(sym in row3 for sym in ("✅", "❌", "❓", "⬜"))
    # 列序:① → ② → ③(原位)
    assert out.index("① 成立時間") < out.index("② 3 年含息年化報酬") < out.index("③ 晨星評級")


def test_h_tab2_verdict_ignores_peer_row(monkeypatch):
    nav = _nav_4y()
    divs = _monthly_divs(nav.index)
    m = calc_metrics(nav, divs)
    m["inception_date"] = "2015-01-01"
    fd = {"moneydj_raw": {}, "metrics": m, "series": nav, "dividends": divs}
    out = _render_tab2(monkeypatch, nav, m, fd=fd)
    ann, _ = derive_ann_3y_for_333(fd, m)
    expect = check_333_principle(derive_years_for_333("2015-01-01", None)[0], ann)["passed"]
    assert expect is True
    assert "🏆 通過 3-3-3" in out                              # ③ 恆「—」,不擋 ✅
    assert not any(sym in _peer_row(out) for sym in ("✅", "❌"))


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
    """Tab2 expander 與 Tab3 批次區改走 SSOT:Tab2 import check_333_principle;退役鏈字樣
    (c2_return_3y / overall_pass / c1_pass / ②來源 / ❓ 三態)不得殘留在渲染字串(只看字串常數,
    不看註解)。③ 依客戶 UI/Layout Gate 保留 → 須帶「參考，不計入 3-3-3 判定」加註。"""
    tab2 = _REPO / "ui" / "tab2_single_fund.py"
    _, imp = _calls_and_imports_of(tab2, "check_333_principle")
    assert imp, "Tab2 _render_333_fund_expander 須 import check_333_principle"
    consts2 = _string_constants(tab2)
    for banned in ("c2_return_3y", "overall_pass", "c1_pass", "三項全過"):
        hits = [c for c in consts2 if banned in c]
        assert not hits, f"Tab2 渲染字串仍殘留退役鏈字樣:{banned} → {hits[:2]}"
    assert any("③ 晨星評級 / 同儕前 1/3" in c for c in consts2), "Tab2 ③ 列被移除(違反 UI/Layout Gate)"
    assert any("參考，不計入 3-3-3 判定" in c for c in consts2)
    tab3 = _REPO / "ui" / "tab3_portfolio.py"
    consts3 = _string_constants(tab3)
    for banned in ("②來源空", "②來源*", "❓ 資料不足"):
        hits = [c for c in consts3 if banned in c]
        assert not hits, f"Tab3 渲染字串仍殘留退役鏈字樣:{banned} → {hits[:2]}"
    assert any("③同儕排名僅供參考、不計入 3-3-3 判定" in c for c in consts3)
    # 整體統計的三態符號:⬜ 在、❓ 不在(與 SSOT passed=None 對齊)
    src3 = tab3.read_text(encoding="utf-8")
    assert '_df_333["整體"] == "⬜"' in src3
    assert '_df_333["整體"] == "❓"' not in src3


# ══════════════════════════════════════════════════════════════════════
# (M4) Tab2 判定卡:② 缺值那一列圖示是 ⬜,不是 ❌
# ══════════════════════════════════════════════════════════════════════
def _row_of(html: str, label: str) -> str:
    i = html.index(label)
    return html[i:html.index("</tr>", i)]


def test_m4_tab2_missing_return_row_icon_is_grey_not_red(monkeypatch):
    nav = _nav_4y().tail(300)                      # 3Y 含息缺(歷史不足)、成立日 ≥ 3 年
    out = _render_tab2(monkeypatch, nav, {"inception_date": "2015-01-01"})
    row2 = _row_of(out, "② 3 年含息年化報酬")
    assert "⬜" in row2 and "❌" not in row2 and "✅" not in row2
    row1 = _row_of(out, "① 成立時間")
    assert "✅" in row1                              # ① 有值仍照判(對照組,確認不是整卡灰掉)


# ══════════════════════════════════════════════════════════════════════
# (M5) 配息日落在非淨值日 → 不算「被還原的配息」→ 配息型 ⬜ 配息資料未備
# ══════════════════════════════════════════════════════════════════════
def test_m5_dividends_on_non_nav_dates_are_not_counted():
    nav = _nav_4y()                                 # bdate_range → 只有平日
    sats = [d for d in pd.date_range(nav.index[-_WINDOW_3Y], nav.index[-1], freq="W-SAT")][::4]
    assert sats and all(d.weekday() == 5 for d in sats) and not any(d in nav.index for d in sats)
    divs = [{"date": str(d.date()), "amount": 0.05} for d in sats]
    m = calc_metrics(nav, divs)
    assert m["ret_3y_ann_tr"] is not None
    assert m["ret_3y_div_count"] == 0, "落在非淨值日、沒被還原進序列的配息不得計數"
    fd = {"moneydj_raw": {}, "metrics": m, "series": nav, "dividends": divs}
    ann, basis = derive_ann_3y_for_333(fd, m)
    assert ann is None and basis == ANN3Y_LABEL_DIV_MISSING
    assert check_333_principle(5.0, ann)["passed"] is None


# ══════════════════════════════════════════════════════════════════════
# mk_dashboard(Tab3 戰情室「3-3-3 篩選器」)與 batch / check_333_principle 同源
# ══════════════════════════════════════════════════════════════════════
def _mk_funds():
    out = []
    for f in _batch_input():
        g = dict(f)
        g["loaded"] = True
        out.append(g)
    return out[:-1]                                  # 去掉重複 code 那一列(mk 不去重)


def test_mk_dashboard_333_equals_batch_and_principle():
    from ui.components.mk_dashboard import build_mk_dataframe
    funds = _mk_funds()
    mk = build_mk_dataframe(funds).set_index("代碼")
    batch = batch_333_funds(funds).set_index("代碼")
    for f in funds:
        s = f.get("series")
        first = str(pd.Timestamp(s.index[0]).date()) if s is not None and len(s) else None
        years, _ = derive_years_for_333((f.get("metrics") or {}).get("inception_date"), first)
        fd = {"moneydj_raw": f.get("moneydj_raw") or {}, "metrics": f.get("metrics") or {},
              "series": s, "dividends": f.get("dividends")}
        ann, _ = derive_ann_3y_for_333(fd, f.get("metrics") or {})
        r = check_333_principle(years, ann)
        row = mk.loc[f["code"]]
        _p = row["_333_passed"]
        _p = None if _p is None or (isinstance(_p, float) and _p != _p) else bool(_p)
        assert _p is r["passed"], f["code"]
        assert _ICON[_p] == batch.loc[f["code"], "整體"]
    for c in mk.columns:
        if c.startswith("_333_"):
            from ui.components.mk_dashboard import _333_COLS
            assert c not in _333_COLS


class _MkSt:
    """mk_dashboard 用到的最小 streamlit 替身。"""

    def __init__(self):
        self.texts, self.metrics, self.frames = [], [], []
        _self = self

        class _Col:
            def metric(self, label, value, *a, **k):
                _self.metrics.append((label, value))
        self._col = _Col

    def expander(self, *a, **k):
        import contextlib
        return contextlib.nullcontext()

    def markdown(self, body, *a, **k):
        self.texts.append(str(body))

    def warning(self, body, *a, **k):
        self.texts.append(str(body))

    def info(self, body, *a, **k):
        self.texts.append(str(body))

    def columns(self, n, *a, **k):
        return [self._col() for _ in range(n if isinstance(n, int) else len(n))]

    def dataframe(self, df, *a, **k):
        self.frames.append(df)


def _render_mk_333(monkeypatch, df):
    import ui.components.mk_dashboard as mk
    rec = _MkSt()
    monkeypatch.setattr(mk, "st", rec)
    mk._render_333_tab(df)
    return rec


def test_mk_render_candidates_are_passed_true_and_grey_counted(monkeypatch):
    from ui.components.mk_dashboard import build_mk_dataframe
    df = build_mk_dataframe(_mk_funds())
    rec = _render_mk_333(monkeypatch, df)
    cand_codes = list(rec.frames[0]["代碼"]) if rec.frames else []
    assert cand_codes == ["OK1"]                     # 只有 passed=True
    labels = [m[0] for m in rec.metrics]
    assert labels == ["① 成立 ≥ 3 年", "② ① + 3 年含息年化 > 7%",
                      "③ 波動優於中位（參考，不計入 3-3-3 判定）"]
    vals = dict(rec.metrics)
    assert vals["② ① + 3 年含息年化 > 7%"] == "1 檔"
    txt = "\n".join(rec.texts)
    assert "⬜ 資料未備 3 檔" in txt                  # DIV0 / SHORT / NONE:計入 ⬜,不進候選


def test_mk_render_peer_reference_does_not_change_candidates(monkeypatch):
    """③(波動)只當參考:把 OK1 的波動調成全組最高 / 最低,候選清單不變。"""
    from ui.components.mk_dashboard import build_mk_dataframe
    base = build_mk_dataframe(_mk_funds())
    outs = []
    for v in (1e-6, 1e6):
        df = base.copy()
        df.loc[df["代碼"] == "OK1", "_std_1y"] = v
        rec = _render_mk_333(monkeypatch, df)
        outs.append(list(rec.frames[0]["代碼"]) if rec.frames else [])
    assert outs[0] == outs[1] == ["OK1"]


# ══════════════════════════════════════════════════════════════════════
# AST 守衛:ui/ 與 services/ 不得自寫 3-3-3 門檻比較(年資 >= 3 / 報酬 > 7 字面值)
# ══════════════════════════════════════════════════════════════════════
_YEAR_HINTS = ("age", "year", "成立", "inception")
_RET_HINTS = ("ret", "報酬", "年化", "ann")


def _self_written_333_compares(src: str) -> list:
    hits = []
    for n in ast.walk(ast.parse(src)):
        if not isinstance(n, ast.Compare):
            continue
        left = ast.unparse(n.left).lower()
        for op, c in zip(n.ops, n.comparators):
            if not (isinstance(c, ast.Constant) and isinstance(c.value, (int, float))
                    and not isinstance(c.value, bool)):
                continue
            if isinstance(op, ast.GtE) and c.value == 3 and any(h in left for h in _YEAR_HINTS):
                hits.append((n.lineno, ast.unparse(n)))
            if isinstance(op, ast.Gt) and c.value == 7 and any(h in left for h in _RET_HINTS):
                hits.append((n.lineno, ast.unparse(n)))
    return hits


def test_guard_detects_old_mk_dashboard_code():
    """守衛自我驗證(突變等價):3A 前 mk_dashboard 的兩行判定必須被抓到。"""
    old = ('age_pass = df["_age_years"].fillna(0) >= 3.0\n'
           'ret_pass = df["含息總報酬(1Y%)"].fillna(-999) > 7.0\n')
    assert len(_self_written_333_compares(old)) == 2


def test_no_self_written_333_threshold_compares_in_ui_or_services():
    offenders = []
    for p in list((_REPO / "ui").rglob("*.py")) + list((_REPO / "services").rglob("*.py")):
        for ln, code in _self_written_333_compares(p.read_text(encoding="utf-8")):
            offenders.append(f"{p.relative_to(_REPO)}:{ln}  {code}")
    assert not offenders, ("3-3-3 判定只能走 check_333_principle(門檻住 SSOT 常數),"
                           "發現自寫比較:\n  " + "\n  ".join(offenders))
