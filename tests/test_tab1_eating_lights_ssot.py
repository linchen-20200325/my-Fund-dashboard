"""2026-10-23 PR1b 獨立稽核回修(M1 / M2)守衛。

M1 ── `ui/tab_fund_grp_health.py` 多基金績效比較圖:年化基準下兩條柱**不得整排 None**。
      持有期年化欄 2026-10-23 改名「持有期配息率% (相對買入成本・年化)」「持有期含息% (相對
      買入成本・年化)」後,原 f"配息率% ({basis})" 字串拼鍵在 basis=="年化" 時組出舊鍵 →
      `r.get()` 全 None(v19.304「多檔比較全 0」的反向回歸)。鍵改走 `_comparison_keys_for_basis`。
M2 ── `ui/tab1_macro_inflection.py` 🚦 持倉紅綠燈、`ui/tab1_macro_longterm.py` 💰 資本防線:
      吃本金只走 `check_eating_principal_1y_mk`;**配息率缺 + 淨值小跌不得出 🔴**
      (舊寫法 `annual_div_rate or 0` + 純淨值 `ret_1y` + UI 自己 `tr < adr` = 假本金侵蝕)。
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# ══════════════════════════════════════════════════════════════════
# M1
# ══════════════════════════════════════════════════════════════════
def _row_from_fund_row_keys(**vals) -> dict:
    """用 `services/fund_row.py::process_one_fund` 實際輸出的鍵名組一列(不自己發明鍵)。"""
    base = {
        "持有期配息率% (相對買入成本・年化)": 9.09,
        "持有期含息% (相對買入成本・年化)": 10.8,
        "淨值% (年化)": 1.7,
        "配息率% (全期實際)": 4.6, "含息% (全期實際)": 6.3, "淨值% (全期實際)": 1.7,
    }
    base.update(vals)
    return base


def test_m1_comparison_keys_exist_in_fund_row_output():
    """對映表的三個鍵必須是 `process_one_fund` 真的會吐的鍵(源碼鎖),否則圖表又會整排 None。"""
    from ui.tab_fund_grp_health import _COMPARISON_KEYS_BY_BASIS
    src = (ROOT / "services" / "fund_row.py").read_text(encoding="utf-8")
    for _basis, _keys in _COMPARISON_KEYS_BY_BASIS.items():
        for _k in _keys:
            assert f'"{_k}":' in src, f"基準 {_basis!r} 的鍵 {_k!r} 不在 services/fund_row.py 輸出裡"


def test_m1_annual_basis_bars_are_not_all_none():
    """鎖的是 helper `_comparison_keys_for_basis` 回的鍵能在 fund_row 形狀的列上取到值
    (純函式層);圖表區真的有改走這支 helper、沒再用 f-string 拼鍵,由下面的源碼鎖
    `test_m1_chart_block_does_not_build_keys_by_string_formatting` 守,本條不渲染圖表。
    修正前的病(舊鍵 `r.get("配息率% (年化)")` 全 None)在本條末尾留一行反向對照。"""
    from ui.tab_fund_grp_health import _comparison_keys_for_basis, _pick_comparison_basis
    rows = [_row_from_fund_row_keys(), _row_from_fund_row_keys(**{
        "持有期配息率% (相對買入成本・年化)": 11.0, "持有期含息% (相對買入成本・年化)": 12.6})]
    basis = _pick_comparison_basis(rows)
    assert basis == "年化"
    div_key, ret_key, nav_key = _comparison_keys_for_basis(basis)
    div_r = [r.get(div_key) for r in rows]
    ret_r = [r.get(ret_key) for r in rows]
    assert not all(v is None for v in div_r), f"配息率柱整排 None(鍵 {div_key!r})"
    assert not all(v is None for v in ret_r), f"含息柱整排 None(鍵 {ret_key!r})"
    assert div_r == [9.09, 11.0] and ret_r == [10.8, 12.6]
    assert [r.get(nav_key) for r in rows] == [1.7, 1.7]
    # 舊鍵在新列上就是 None —— 這正是修正前的病,留一條反向對照
    assert all(r.get("配息率% (年化)") is None for r in rows)


def test_m1_quanqi_basis_keys_unchanged():
    from ui.tab_fund_grp_health import _comparison_keys_for_basis
    assert _comparison_keys_for_basis("全期實際") == (
        "配息率% (全期實際)", "含息% (全期實際)", "淨值% (全期實際)")
    with pytest.raises(KeyError):
        _comparison_keys_for_basis("不存在的基準")


def test_m1_chart_block_does_not_build_keys_by_string_formatting():
    """源碼鎖:圖表區不得再用 f"配息率% ({_basis})" 拼鍵。"""
    src = (ROOT / "ui" / "tab_fund_grp_health.py").read_text(encoding="utf-8")
    assert 'f"配息率% ({_basis})"' not in src
    assert 'f"含息% ({_basis})"' not in src
    assert "_comparison_keys_for_basis(_basis)" in src


# ══════════════════════════════════════════════════════════════════
# M2
# ══════════════════════════════════════════════════════════════════
def _fund(*, tr=None, adr=None, ret_1y=None, code="F"):
    """nested portfolio_funds 形狀。`adr=None` 代表 metrics.annual_div_rate 缺(鍵在、值 None)。"""
    m = {"ret_1y": ret_1y, "annual_div_rate": adr, "nav": 10.0}
    if tr is not None:
        m.update({"ret_1y_total": tr, "ret_1y_window_days": 365, "ret_1y_div_count": 12,
                  "annual_div_rate_div_count": 12})
    return {"code": code, "fund_name": f"{code} 基金", "loaded": True,
            "metrics": m, "moneydj_raw": {}, "series": None, "dividends": []}


@pytest.mark.parametrize("ret_1y", [-2.0, -20.0, 0.0])
def test_m2_inflection_missing_adr_and_small_nav_drop_is_not_red(ret_1y):
    """**修正前必紅**:配息率缺 → 舊寫法 `or 0`,純淨值 −2% < 0 → 🔴 假本金侵蝕。"""
    from ui.tab1_macro_inflection import _eating_light_parts
    out = _eating_light_parts(_fund(adr=None, ret_1y=ret_1y))
    assert out["red"] is False, out


def test_m2_inflection_pure_nav_is_not_total_return():
    """只有純淨值 `ret_1y`(沒有還原值)+ 配息率 5% → SSOT 無 1Y 含息 → 灰,不是 🔴。"""
    from ui.tab1_macro_inflection import _eating_light_parts
    out = _eating_light_parts(_fund(adr=5.0, ret_1y=-2.0))
    assert out["red"] is False and out["grey"] is True
    assert "⬜" in out["reason"], out


def test_m2_inflection_true_eating_is_red_and_green_is_neither():
    from ui.tab1_macro_inflection import _eating_light_parts
    red = _eating_light_parts(_fund(tr=2.0, adr=8.0))
    assert red["red"] is True and "吃本金警示" in red["reason"]
    green = _eating_light_parts(_fund(tr=12.0, adr=8.0))
    assert green == {"red": False, "grey": False, "reason": ""}
    nodiv = _eating_light_parts({"code": "N", "metrics": {"ret_1y_total": -3.0}, "moneydj_raw": {}})
    assert nodiv["red"] is False and nodiv["grey"] is False


def test_m2_longterm_missing_adr_is_neutral_not_eroded():
    """**修正前必紅**:`annual_div_rate or 0` + `ret_1y=-2` → 紅柱 + 🚨 本金侵蝕 + stash 計入。"""
    from ui.tab1_macro_longterm import _capital_line_rows
    rows = _capital_line_rows([_fund(adr=None, ret_1y=-2.0, code="A")])
    assert len(rows) == 1
    r = rows[0]
    assert r["eating"] is None and r["adr"] is None, r
    assert r["label"] != "🚨 本金侵蝕"
    assert r["tr1y"] is None, "純淨值 ret_1y 不得被當成 1Y 含息柱值"


def test_m2_longterm_rows_follow_ssot():
    from ui.tab1_macro_longterm import _capital_line_rows
    rows = _capital_line_rows([
        _fund(tr=2.0, adr=8.0, code="EAT"),
        _fund(tr=12.0, adr=8.0, code="OK"),
        _fund(adr=5.0, code="GREY"),
    ])
    by = {r["name"]: r for r in rows}
    assert by["EAT 基金"]["eating"] is True and by["EAT 基金"]["label"] == "🚨 本金侵蝕"
    assert by["EAT 基金"]["tr1y"] == 2.0 and by["EAT 基金"]["adr"] == 8.0
    assert by["OK 基金"]["eating"] is False and by["OK 基金"]["label"] == ""
    assert by["GREY 基金"]["eating"] is None and "⬜" in by["GREY 基金"]["label"]
    assert by["GREY 基金"]["tr1y"] is None and by["GREY 基金"]["adr"] == 5.0


def test_m2_source_no_longer_reads_pure_nav_or_or_zero():
    """源碼鎖:兩個區塊不得再用 `.get("ret_1y")` 當含息、不得 `annual_div_rate") or 0`。"""
    for rel in ("ui/tab1_macro_inflection.py", "ui/tab1_macro_longterm.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert 'annual_div_rate") or 0' not in src, rel
        assert 'get("ret_1y"))' not in src, rel
        assert "check_eating_principal_1y_mk" in src, rel


# ══════════════════════════════════════════════════════════════════
# N1(2026-10-23 delta 複核):Missing 不得變「全部配息有保障」
# ══════════════════════════════════════════════════════════════════
def _snapshot_with_capital_line(monkeypatch, cap: dict) -> str:
    import sys
    sys.path.insert(0, str(ROOT / "tests"))
    from test_tab1_macro import _mock_streamlit  # noqa: E402 — 沿用既有 session_state 替身
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro_ai import _build_macro_ai_snapshot
    _mock_streamlit(monkeypatch, {"_macro_capital_line": cap})
    snap, _, _ = _build_macro_ai_snapshot({}, {}, {}, {}, [])
    return snap


def test_n1_longterm_stash_carries_judged_grey_na_counts():
    """stash 必須把三種檔數帶出去,消費端才分得出「0 檔侵蝕」是全綠還是全灰。"""
    from ui.tab1_macro_longterm import _capital_line_rows
    rows = _capital_line_rows([
        _fund(tr=2.0, adr=8.0, code="EAT"), _fund(tr=12.0, adr=8.0, code="OK"),
        _fund(adr=5.0, code="GREY"),
        {"code": "N", "fund_name": "N 基金", "metrics": {"ret_1y_total": 1.0}, "moneydj_raw": {}},
    ])
    n_judged = sum(1 for r in rows if r["eating"] in (True, False))
    n_grey = sum(1 for r in rows if r["eating"] is None and r["label"] != "— 非配息基金")
    n_na = sum(1 for r in rows if r["label"] == "— 非配息基金")
    assert (n_judged, n_grey, n_na) == (2, 1, 1)
    # 源碼鎖:stash 真的寫了這三個鍵
    src = (ROOT / "ui" / "tab1_macro_longterm.py").read_text(encoding="utf-8")
    for _k in ('"n_judged"', '"n_grey"', '"n_na"'):
        assert _k in src, f"stash 缺 {_k}"


def test_n1_all_grey_portfolio_is_not_called_all_safe(monkeypatch):
    """**修正前必紅**:n_eroded==0 → 「5 檔基金全部 TR1Y ≥ 配息率（配息有保障）」。"""
    snap = _snapshot_with_capital_line(monkeypatch, {
        "n_funds": 5, "n_eroded": 0, "n_judged": 0, "n_grey": 5, "n_na": 0, "eroded_funds": []})
    assert "資本防線" in snap
    assert not ("全部" in snap and "配息有保障" in snap), snap
    assert "5 檔⬜ 未判定" in snap and "請勿推測" in snap, snap


def test_n1_all_non_dividend_portfolio_is_not_called_all_safe(monkeypatch):
    snap = _snapshot_with_capital_line(monkeypatch, {
        "n_funds": 3, "n_eroded": 0, "n_judged": 0, "n_grey": 0, "n_na": 3, "eroded_funds": []})
    assert not ("全部" in snap and "配息有保障" in snap), snap
    assert "3 檔非配息基金" in snap, snap


def test_n1_fully_judged_zero_eroded_still_says_all_safe(monkeypatch):
    """回歸鎖:每一檔都判得動且 0 侵蝕 → 原句保留。"""
    snap = _snapshot_with_capital_line(monkeypatch, {
        "n_funds": 4, "n_eroded": 0, "n_judged": 4, "n_grey": 0, "n_na": 0, "eroded_funds": []})
    assert "4 檔基金全部 TR1Y ≥ 配息率（配息有保障）" in snap, snap


def test_n1_mixed_counts_are_correct(monkeypatch):
    snap = _snapshot_with_capital_line(monkeypatch, {
        "n_funds": 6, "n_eroded": 1, "n_judged": 3, "n_grey": 2, "n_na": 1,
        "eroded_funds": [{"name": "高收益債 A", "tr1y": 2.0, "adr": 8.0}]})
    assert "⚠️ 1/6 檔本金侵蝕" in snap and "2 檔有保障" in snap, snap
    assert "2 檔⬜ 未判定" in snap and "1 檔非配息基金" in snap, snap
    assert "高收益債 A" in snap
    # 0 侵蝕但有未判定 → 講明有保障幾檔、未判定幾檔,不講「全部」
    snap2 = _snapshot_with_capital_line(monkeypatch, {
        "n_funds": 6, "n_eroded": 0, "n_judged": 3, "n_grey": 2, "n_na": 1, "eroded_funds": []})
    assert "3 檔 TR1Y ≥ 配息率（配息有保障）" in snap2 and "全部" not in snap2.split("資本防線")[1].split("\n")[0], snap2


def test_n1_old_stash_without_counts_is_not_called_all_safe(monkeypatch):
    """舊版 stash(沒有 n_judged)→ 當 0 檔判得動,不得說「全部」。"""
    snap = _snapshot_with_capital_line(monkeypatch, {"n_funds": 2, "n_eroded": 0, "eroded_funds": []})
    assert not ("全部" in snap and "配息有保障" in snap), snap
