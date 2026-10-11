# -*- coding: utf-8 -*-
"""級別三態 N1（客戶 2026-10-11）：「全部寫入」同代號多列級別的讀回快照閘門。

規則（`shared/tier_write_gate.py`）：
* 讀回後 Sheet 與「讀回快照」逐項相等 → 正常寫入（[核心, 衛星, 留白] 原樣通過，留白維持留白）。
* Sheet 已改、或沒有可靠快照（JSON 還原後）→ 同代號多列級別不完全一致（含「已設定＋留白」）
  → 整張保單不寫，只列衝突代號；其他保單照常寫入。
* 系統不認得的級別字串 → 一律擋，不因兩列相同放行。
* 比對 ≠ 配對：不依列序／金額把快照格子對到 session 列。

突變證據寫在各條 docstring 的「突變」一行（實跑結果見 commit 訊息／回報）。
"""
from __future__ import annotations

import ast
import json
import pathlib
import time

import pandas as pd
import pytest

from repositories.policy.v2 import ALL_COLS_V2, ZH_HEADERS_V2
from shared.policy_tier import resolve_tier
from shared.tier_write_gate import (
    SNAPSHOT_SESSION_KEY,
    capture_snapshot,
    code_key,
    invalidate_snapshot,
    needs_gate,
    snapshot_from_policies_df,
)

_MSG = "❌ 級別設定衝突：{}，未寫入此保單。"


# ── 假 gspread ─────────────────────────────────────────────────────
class _WS:
    def __init__(self, values):
        self.values = [list(r) for r in values]
        self.cleared = False
        self.updates: list = []

    def get_all_values(self):
        return [list(r) for r in self.values]

    def clear(self):
        self.cleared = True

    def update(self, rng, rows):
        self.updates.append((rng, rows))

    def format(self, *a, **k):
        pass


class _SH:
    def __init__(self, tabs):
        self.tabs = tabs

    def worksheet(self, title):
        return self.tabs[title]


class _Client:
    def __init__(self, tabs):
        self.sh = _SH(tabs)

    def open_by_key(self, sid):
        return self.sh


def _tab(pid: str, rows: list) -> _WS:
    """rows: [(代號, 級別, 本金), ...] → 中文表頭 v2 分頁。"""
    c = list(ALL_COLS_V2)
    out = [[ZH_HEADERS_V2[x] for x in c]]
    for code, tier, amt in rows:
        r = [""] * len(c)
        r[c.index("policy_id")], r[c.index("fund_code")] = pid, code
        r[c.index("tier")], r[c.index("invest_twd")] = tier, str(amt)
        out.append(r)
    return _WS(out)


def _written(ws: _WS) -> list:
    c = list(ALL_COLS_V2)
    _rng, rows = ws.updates[0]
    return [(r[c.index("fund_code")], r[c.index("tier")], r[c.index("invest_twd")]) for r in rows[1:]]


def _readback(monkeypatch, sheet: dict) -> dict:
    """Sheet {pid: rows} → 真的 `_load_all_from_sheet_v2` 讀回 → 與 policy_admin_section 相同地擷取快照。"""
    from ui.helpers import cloud_io
    recs = [{"policy_id": p, "fund_code": c, "tier": t, "invest_twd": a}
            for p, rows in sheet.items() for c, t, a in rows]
    df = pd.DataFrame(recs, columns=list(ALL_COLS_V2)).fillna("")
    monkeypatch.setattr(cloud_io, "load_all_policies_v2", lambda c, s: df)
    ss: dict = {"portfolio_funds": []}
    assert cloud_io._load_all_from_sheet_v2("c", "s", ss)["error"] is None
    capture_snapshot(ss)
    return ss


def _backup(funds: list) -> bytes:
    return json.dumps({"schema_version": "1.0", "portfolio_funds": [
        {"code": c, "name": c, "invest_twd": a, "policy_id": p, "policy_name": p,
         "policy_tier": t, "currency": "USD"} for p, c, a, t in funds],
        "t7_ledgers": {}}, ensure_ascii=False).encode("utf-8")


def _restore(ss: dict, funds: list) -> None:
    from ui.helpers.io.json_backup import restore_from_json_bytes
    assert restore_from_json_bytes(_backup(funds), ss)["ok"]
    invalidate_snapshot(ss)   # policy_admin_section 的 restore 呼叫端做的事


def _dump(monkeypatch, ss: dict, tabs: dict) -> dict:
    from ui.helpers import cloud_io
    monkeypatch.setattr(cloud_io, "detect_sheet_schema_version", lambda c, s: "v2")
    monkeypatch.setattr(time, "sleep", lambda s: None)
    return cloud_io.dump_all_to_sheet(_Client(tabs), "s", ss)


def _conflict_warning(out: dict, pid: str, codes: str) -> bool:
    return any(f"{pid}: {_MSG.format(codes)}" in w for w in out["warnings"])


# ══════════════════════════════════════════════════════════════════
# 快照可靠（Sheet 與讀回一致）→ 正常處理
# ══════════════════════════════════════════════════════════════════
def test_readback_then_dump_core_satellite_blank_passes_blank_stays_blank(monkeypatch):
    """讀回後原樣的 [核心, 衛星, 留白] 直接寫入 → 通過；留白維持留白（不填 core／satellite／0）。
    突變 M7（閘門放行後仍用 keep_sheet_tier=True）／M1（永不放行）→ 本條轉紅。"""
    rows = [("F1", "核心", 100), ("F1", "衛星", 200), ("F1", "", 300)]
    ss = _readback(monkeypatch, {"P1": rows})
    tab = _tab("P1", rows)
    out = _dump(monkeypatch, ss, {"P1": tab})
    assert out["ok"] and not out["warnings"], out
    assert _written(tab) == [("F1", "core", 100), ("F1", "satellite", 200), ("F1", "", 300)]


def test_readback_then_dump_unrecognized_in_single_row_code_is_preserved_in_same_policy(monkeypatch):
    """靠快照放行的保單裡，其他單列代號行為不退步：認不得的值原樣保留、已設定級別保留。
    突變 M8（放行時單列代號不走 merge_sheet_tier）→ 本條轉紅。"""
    rows = [("F1", "核心", 100), ("F1", "衛星", 200), ("F1", "", 300),
            ("F2", "foo", 1), ("F3", "satellite", 2)]
    ss = _readback(monkeypatch, {"P1": rows})
    # session 端 F3 因故未設定（例如 v1 殘留清掉）→ 單列代號仍保留 Sheet 原值
    for f in ss["portfolio_funds"]:
        if f["code"] == "F3":
            f["is_core"], f["policy_tier"] = None, ""
    tab = _tab("P1", rows)
    out = _dump(monkeypatch, ss, {"P1": tab})
    assert out["ok"] and not out["warnings"], out
    assert _written(tab) == [("F1", "core", 100), ("F1", "satellite", 200), ("F1", "", 300),
                             ("F2", "foo", 1), ("F3", "satellite", 2)]


def test_readback_identical_levels_multi_row_still_preserved(monkeypatch):
    """Sheet 同代號多列級別完全一致（拼法不同）→ 不需要快照，沿用既有保留（原拼法）。"""
    rows = [("F1", "核心", 100), ("F1", "Core", 200)]
    ss = _readback(monkeypatch, {"P1": rows})
    for f in ss["portfolio_funds"]:
        f["is_core"], f["policy_tier"] = None, ""      # 全部未設定
    tab = _tab("P1", rows)
    out = _dump(monkeypatch, ss, {"P1": tab})
    assert out["ok"] and not out["warnings"], out
    assert _written(tab) == [("F1", "核心", 100), ("F1", "Core", 200)]


def test_second_holding_added_without_tier_stays_blank(monkeypatch):
    """新增同基金第二筆持倉但未設級別 → 維持留白（不從第一筆搬級別過來）。"""
    rows = [("F1", "core", 100)]
    ss = _readback(monkeypatch, {"P1": rows})
    ss["portfolio_funds"].append({"code": "F1", "policy_id": "P1", "name": "F1", "currency": "USD",
                                  "invest_twd": 50, "is_core": None, "policy_tier": ""})
    tab = _tab("P1", rows)
    out = _dump(monkeypatch, ss, {"P1": tab})
    assert out["ok"] and not out["warnings"], out
    assert _written(tab) == [("F1", "core", 100), ("F1", "", 50)]


# ══════════════════════════════════════════════════════════════════
# Sheet 讀回後被改 → fail closed
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("changed", [
    [("F1", "衛星", 100), ("F1", "核心", 200), ("F1", "", 300)],   # 列序調換
    [("F1", "核心", 100), ("F1", "衛星", 200), ("F1", "衛星", 300)],  # 留白格被填
    [("F1", "核心", 100), ("F1", "", 200), ("F1", "", 300)],        # 衛星格被清
    [("F1", "核心", 100), ("F1", "衛星", 200)],                      # 少一列
])
def test_sheet_changed_after_readback_mixed_group_fails_closed(monkeypatch, changed):
    """突變 M2（沒有快照／快照不符也放行）→ 本條轉紅（P1 被清空重寫）。"""
    ss = _readback(monkeypatch, {"P1": [("F1", "核心", 100), ("F1", "衛星", 200), ("F1", "", 300)]})
    tab = _tab("P1", changed)
    out = _dump(monkeypatch, ss, {"P1": tab})
    assert tab.cleared is False and tab.updates == []
    assert _conflict_warning(out, "P1", "F1"), out["warnings"]


def test_sheet_changed_but_all_identical_levels_is_not_a_conflict(monkeypatch):
    """Sheet 被改成同代號多列級別『完全一致』→ 不是衝突（客戶只擋『不完全一致』）。"""
    ss = _readback(monkeypatch, {"P1": [("F1", "核心", 100), ("F1", "衛星", 200), ("F1", "", 300)]})
    for f in ss["portfolio_funds"]:
        f["is_core"], f["policy_tier"] = None, ""
    tab = _tab("P1", [("F1", "core", 100), ("F1", "core", 200), ("F1", "core", 300)])
    out = _dump(monkeypatch, ss, {"P1": tab})
    assert out["ok"] and not out["warnings"], out
    assert _written(tab) == [("F1", "core", 100), ("F1", "core", 200), ("F1", "core", 300)]


# ══════════════════════════════════════════════════════════════════
# 沒有可靠快照（JSON 還原）→ 多列級別不完全一致一律 fail closed
# ══════════════════════════════════════════════════════════════════
def test_n1_original_case_restore_then_dump_fails_closed_no_explicit_level_cleared(monkeypatch):
    """N1 原案例：備份 [core 100, 未設 200]、Sheet [留白 100, core 200]。
    舊行為無聲對調寫出 [(F1,core,100),(F1,'',200)]；現在整張不寫（Sheet 上的 core 一格都沒動）。
    突變 M6（閘門整段拿掉）→ 本條轉紅。"""
    ss: dict = {}
    _restore(ss, [("P1", "F1", 100, "core"), ("P1", "F1", 200, "")])
    sheet_rows = [("F1", "", 100), ("F1", "core", 200)]
    tab = _tab("P1", sheet_rows)
    before = [list(r) for r in tab.values]
    out = _dump(monkeypatch, ss, {"P1": tab})
    assert tab.cleared is False and tab.updates == [] and tab.values == before
    assert _conflict_warning(out, "P1", "F1"), out["warnings"]
    assert out["written"] == 0


def test_restore_after_readback_voids_old_snapshot_even_if_sheet_unchanged(monkeypatch):
    """先讀回（有快照）→ 再 JSON 還原 → 舊快照必須作廢：Sheet 與當初讀回完全一樣也不放行。
    突變 M3（restore 呼叫端拿掉 invalidate_snapshot）→ 靠 AST 守衛轉紅；M10（invalidate 不 pop）→ 本條轉紅。"""
    rows = [("F1", "核心", 100), ("F1", "衛星", 200), ("F1", "", 300)]
    ss = _readback(monkeypatch, {"P1": rows})
    assert SNAPSHOT_SESSION_KEY in ss
    _restore(ss, [("P1", "F1", 100, ""), ("P1", "F1", 200, ""), ("P1", "F1", 300, "")])
    assert SNAPSHOT_SESSION_KEY not in ss
    tab = _tab("P1", rows)
    out = _dump(monkeypatch, ss, {"P1": tab})
    assert tab.updates == [] and _conflict_warning(out, "P1", "F1"), out["warnings"]


def test_restore_invalidation_is_idempotent_and_only_a_full_readback_clears_it(monkeypatch):
    """重跑（上傳檔還在畫面上又還原一次）仍失效；下一次成功讀回才重新可靠。"""
    rows = [("F1", "核心", 100), ("F1", "衛星", 200), ("F1", "", 300)]
    ss = _readback(monkeypatch, {"P1": rows})
    for _ in range(3):
        _restore(ss, [("P1", "F1", 100, ""), ("P1", "F1", 200, ""), ("P1", "F1", 300, "")])
        assert SNAPSHOT_SESSION_KEY not in ss
    out = _dump(monkeypatch, ss, {"P1": _tab("P1", rows)})
    assert out["written"] == 0
    # 讀回才清除：重新讀回 → 再次可寫
    ss2 = _readback(monkeypatch, {"P1": rows})
    tab = _tab("P1", rows)
    assert _dump(monkeypatch, ss2, {"P1": tab})["written"] == 3


def test_no_snapshot_key_at_all_fails_closed(monkeypatch):
    """從未讀回（沒有快照鍵）：Sheet 多列混合 → 擋。"""
    ss: dict = {"portfolio_funds": [
        {"code": "F1", "policy_id": "P1", "name": "F1", "currency": "USD", "invest_twd": 1,
         "is_core": None, "policy_tier": ""},
        {"code": "F1", "policy_id": "P1", "name": "F1", "currency": "USD", "invest_twd": 2,
         "is_core": None, "policy_tier": ""}]}
    tab = _tab("P1", [("F1", "core", 1), ("F1", "", 2)])
    out = _dump(monkeypatch, ss, {"P1": tab})
    assert tab.updates == [] and _conflict_warning(out, "P1", "F1")


# ══════════════════════════════════════════════════════════════════
# 不認得的字串：一律擋
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("rows", [
    [("F1", "核心資產", 100), ("F1", "核心資產", 200)],     # 兩列相同但不認得（規則 5）
    [("F1", "核心資產", 100), ("F1", "衛星", 200)],         # 混合
])
def test_unrecognized_strings_always_fail_closed_even_with_reliable_snapshot(monkeypatch, rows):
    """即使剛讀回（快照可靠）也擋。突變 M5（拿掉認不得字串的判定）→ 本條轉紅。"""
    ss = _readback(monkeypatch, {"P1": rows})
    for f in ss["portfolio_funds"]:
        f["is_core"], f["policy_tier"] = None, ""
    tab = _tab("P1", rows)
    out = _dump(monkeypatch, ss, {"P1": tab})
    assert tab.updates == [] and _conflict_warning(out, "P1", "F1"), out["warnings"]


# ══════════════════════════════════════════════════════════════════
# 多保單／多代號
# ══════════════════════════════════════════════════════════════════
def test_one_conflict_one_normal_code_lists_only_conflicting_code_and_skips_whole_policy(monkeypatch):
    """同一張保單 F1 衝突、F2 正常 → 只列 F1，整張保單不寫；另一張保單 P2 照常寫入。"""
    ss: dict = {}
    _restore(ss, [("P1", "F1", 100, "core"), ("P1", "F1", 200, ""), ("P1", "F2", 5, ""),
                  ("P2", "G1", 7, "")])
    p1 = _tab("P1", [("F1", "", 100), ("F1", "core", 200), ("F2", "satellite", 5)])
    p2 = _tab("P2", [("G1", "core", 7)])
    out = _dump(monkeypatch, ss, {"P1": p1, "P2": p2})
    assert p1.cleared is False and p1.updates == []
    assert _written(p2) == [("G1", "core", 7)]
    assert out["written"] == 1 and len(out["warnings"]) == 1
    assert _conflict_warning(out, "P1", "F1") and "F2" not in out["warnings"][0]


def test_two_conflicting_codes_joined_with_enumeration_comma(monkeypatch):
    ss: dict = {}
    _restore(ss, [("P1", "F1", 1, ""), ("P1", "F1", 2, ""), ("P1", "F2", 3, ""), ("P1", "F2", 4, "")])
    tab = _tab("P1", [("F1", "core", 1), ("F1", "", 2), ("F2", "satellite", 3), ("F2", "", 4)])
    out = _dump(monkeypatch, ss, {"P1": tab})
    assert tab.updates == [] and _conflict_warning(out, "P1", "F1、F2"), out["warnings"]


def test_single_row_codes_unaffected_by_gate(monkeypatch):
    """沒有同代號多列 → 不讀 Sheet 做閘門、行為與改動前一樣（單列代號 merge_sheet_tier）。"""
    ss: dict = {}
    _restore(ss, [("P1", "F1", 1, ""), ("P1", "F2", 2, "satellite")])
    tab = _tab("P1", [("F1", "foo", 1), ("F2", "core", 2)])
    out = _dump(monkeypatch, ss, {"P1": tab})
    assert out["ok"] and not out["warnings"], out
    assert _written(tab) == [("F1", "foo", 1), ("F2", "satellite", 2)]


# ══════════════════════════════════════════════════════════════════
# 純函式／守衛
# ══════════════════════════════════════════════════════════════════
def test_code_key_makes_numericised_and_raw_codes_comparable():
    """gspread get_all_records 會把 "0050" 變 50；重讀 get_all_values 是 "0050"。
    突變 M9（拿掉純數字去前導零）→ 本條轉紅。"""
    assert code_key(50) == code_key("0050") == code_key(" 0050 ") == "50"
    assert code_key("a1b") == "A1B" and code_key(None) == ""


def test_snapshot_from_policies_df_semantic_levels_in_sheet_order():
    df = pd.DataFrame({"policy_id": ["P1"] * 4 + ["P2"],
                       "fund_code": ["F1", "F2", "F1", "F1", "F1"],
                       "tier": ["核心", "x", "衛星", float("nan"), " CORE "]})
    assert snapshot_from_policies_df(df) == {
        "P1": {"F1": ["core", "satellite", ""], "F2": ["?"]}, "P2": {"F1": ["core"]}}


@pytest.mark.parametrize("bad", [None, pd.DataFrame(), pd.DataFrame({"policy_tier": ["core"]}), 5])
def test_snapshot_from_unusable_input_is_empty_not_guessed(bad):
    assert snapshot_from_policies_df(bad) == {}


def test_needs_gate_only_for_repeated_code_with_unset_row():
    assert needs_gate(["F1", "F1"], ["core", ""])
    assert not needs_gate(["F1", "F1"], ["core", "satellite"])
    assert not needs_gate(["F1", "F2"], ["", ""])


# ── policy_admin_section 接線 ────────────────────────────────────
_SECTION = pathlib.Path(__file__).resolve().parents[1] / "ui" / "helpers" / "portfolio" / "policy_admin_section.py"


def _calls(node: ast.AST, name: str) -> list:
    return [n for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name]


def test_wiring_restore_invalidates_and_full_readbacks_capture_ast_guard():
    """restore 成功分支呼叫 invalidate_snapshot；兩處『全部讀回』成功後呼叫 capture_snapshot；
    refresh_only 區塊不得呼叫（它不重建 session 持倉，快照不能因此變可靠）。
    突變 M3（拿掉 invalidate）、M4（拿掉任一處 capture）、M11（refresh_only 也 capture）→ 本條轉紅。"""
    tree = ast.parse(_SECTION.read_text(encoding="utf-8"))
    ok_branches = [n for n in ast.walk(tree) if isinstance(n, ast.If)
                   and isinstance(n.test, ast.Subscript) and isinstance(n.test.value, ast.Name)
                   and n.test.value.id == "_result"]
    assert len(ok_branches) == 1
    assert len(_calls(ast.Module(body=ok_branches[0].body, type_ignores=[]), "invalidate_snapshot")) == 1
    assert len(_calls(tree, "invalidate_snapshot")) == 1
    assert len(_calls(tree, "capture_snapshot")) == 2
    for n in ast.walk(tree):
        if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == "_refresh_clicked":
            assert not _calls(ast.Module(body=n.body, type_ignores=[]), "capture_snapshot")


_LOAD_APP = """
import sys
sys.path.insert(0, {repo!r})
import pandas as pd
import streamlit as st
from ui.helpers import cloud_io

def _fake_load(client, sid, ss, **kw):
    ss["policies_df"] = pd.DataFrame({{"policy_id": ["P1", "P1"], "fund_code": ["F1", "F1"],
                                       "tier": ["核心", ""]}})
    return {{"ok": True, "added": [], "kept": [], "removed": [], "reused": [],
            "restored_ct": 0, "warnings": [], "error": None}}
_orig = cloud_io.load_all_from_sheet
cloud_io.load_all_from_sheet = _fake_load
ss = st.session_state
ss.setdefault("policy_sheet_id", "SID123")
ss.setdefault("gsheet_tokens", {{"x": 1}})
ss.setdefault("_last_loaded_sheet_id", "SID123")
ss.setdefault("_t3_cur_sheet_title", "帳本")
ss.setdefault("t3_io_panel", "load")
ss.setdefault("portfolio_funds", [])
from ui.helpers.portfolio.policy_admin_section import render_policy_admin_section
class _C:
    def __getattr__(self, n):
        raise RuntimeError("no net")
try:
    render_policy_admin_section(
        oauth_configured=True, resolve_oauth_cfg=lambda: None,
        get_oauth_client=lambda: _C(), gsa_secret=None, sheet_id_secret=None,
        get_login_state=lambda: {{}}, sheet_client=lambda: _C())
finally:
    cloud_io.load_all_from_sheet = _orig
"""


def test_wiring_load_button_captures_snapshot_behaviorally(tmp_path):
    """按「📥 立即全部讀回」成功後，session 內有讀回當下的逐列級別快照。
    突變 M4（拿掉按鈕分支的 capture_snapshot）→ 本條轉紅。"""
    from streamlit.testing.v1 import AppTest
    app = tmp_path / "load_panel_app.py"
    app.write_text(_LOAD_APP.format(repo=str(pathlib.Path(__file__).resolve().parents[1])),
                   encoding="utf-8")
    at = AppTest.from_file(str(app), default_timeout=60)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert SNAPSHOT_SESSION_KEY not in at.session_state
    at.button(key="t3_io_panel_load_run").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state[SNAPSHOT_SESSION_KEY] == {"P1": {"F1": ["core", ""]}}
