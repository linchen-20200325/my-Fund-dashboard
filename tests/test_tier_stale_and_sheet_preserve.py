# -*- coding: utf-8 -*-
"""級別三態（四）：過期 `is_core` 不得存活並寫回 Sheet；寫回不得洗掉客戶在 Sheet 上的級別。

守的是三件事（兩組獨立稽核 2026-10-10 指出）：
1. **過期 `is_core`**：v1 讀回（`sync_policies_to_portfolio_funds`）與 JSON 還原
   （`restore_from_json_bytes`）都只讓 Sheet 的級別決定 `is_core` —— 舊備份裡的 `is_core`
   可能是名稱猜測、也可能是 Sheet 設定，無法分辨，一律不採；不得被 `resolve_tier` 撿回去、
   再由「全部寫入」寫回。
2. **寫回保留 Sheet 原值**：session 沒有客戶級別（例如剛還原備份）時，v1 的
   `upsert_fund_in_policy` 與 v2「全部寫入」（`write_policy_v2(keep_sheet_tier=True)`）
   保留該格 Sheet 現值，不寫空白。
3. **保資料**：中文「核心／衛星」辨識為 core／satellite；其他認不得的值原樣寫回、不清空，
   計算上仍當未設定。

突變驗證（實跑，結果寫在各條 docstring 的「突變」一行）。
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

from shared.policy_tier import (
    fund_tier_sheet_value,
    merge_sheet_tier,
    normalize_tier,
    resolve_tier,
)

# 改動前的批次載入一律用名稱猜 is_core；台灣基金名稱幾乎都帶這段字樣，舊關鍵字表含「配息」⇒ 猜成核心。
_GUESSED_CORE_NAME = "貝萊德世界科技基金A6穩定配息(美元)(基金之配息來源可能為本金)"


# ══════════════════════════════════════════════════════════════════
# shared.policy_tier：中文同義詞 + 寫回合併
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("raw, expect", [
    ("核心", "core"), (" 衛星 ", "satellite"), ("core", "core"), ("Satellite", "satellite"),
    ("foo", None), ("核心資產", None), ("卫星", None), ("", None), (None, None),
])
def test_normalize_tier_recognizes_only_the_two_chinese_synonyms(raw, expect):
    """突變：拿掉 `_ZH_SYNONYMS` → 「核心」「衛星」兩列轉紅。"""
    assert normalize_tier(raw) == expect


@pytest.mark.parametrize("tier, sheet_raw, expect", [
    (None, "core", "core"),          # 未設定 → 保留 Sheet 原值
    ("", "satellite", "satellite"),
    (None, "foo", "foo"),            # 認不得的值原樣保留
    (None, "", ""),
    (None, None, ""),
    ("core", "核心", "核心"),         # 語意相同 → 保留客戶拼法
    ("core", "", "core"),            # 明確級別 → 寫入
    ("satellite", "core", "satellite"),
    ("core", "foo", "core"),
])
def test_merge_sheet_tier(tier, sheet_raw, expect):
    assert merge_sheet_tier(tier, sheet_raw) == expect


# ══════════════════════════════════════════════════════════════════
# 1. 過期 is_core：v1 讀回
# ══════════════════════════════════════════════════════════════════
def _v1_policies_df(tier: str = "") -> pd.DataFrame:
    return pd.DataFrame([{
        "policy_id": "P1", "policy_name": "保單一", "fund_url": "F1",
        "invest_twd": 100000, "invest_date": "", "currency": "USD",
        "fx_at_buy": 0.0, "notes": "", "policy_tier": tier,
    }])


def test_v1_read_drops_stale_is_core_from_session():
    """既存 (policy_id, code) 走 `base.update(...)`：session 殘留的 `is_core=True`
    不得留下來。突變：拿掉 v1.py aggregated 的 `"is_core"` 鍵 → 本條轉紅（tier == "core"）。"""
    from repositories.policy.v1 import sync_policies_to_portfolio_funds
    stale = [{"code": "F1", "policy_id": "P1", "name": _GUESSED_CORE_NAME,
              "is_core": True, "policy_tier": "", "loaded": True}]
    merged, rep = sync_policies_to_portfolio_funds(_v1_policies_df(""), stale)
    assert rep["kept"] == ["P1::F1"]
    assert resolve_tier(merged[0]) is None
    assert fund_tier_sheet_value(merged[0]) == ""


@pytest.mark.parametrize("sheet_tier, expect", [
    ("core", "core"), ("satellite", "satellite"), ("核心", "core"), ("衛星", "satellite"),
    ("foo", None), ("", None),
])
def test_v1_read_tier_follows_sheet_only(sheet_tier, expect):
    """Sheet 明示的級別（含中文）照讀；與 session 殘留的 is_core 方向相反時以 Sheet 為準。"""
    from repositories.policy.v1 import sync_policies_to_portfolio_funds
    stale = [{"code": "F1", "policy_id": "P1", "is_core": (expect != "core")}]
    merged, _ = sync_policies_to_portfolio_funds(_v1_policies_df(sheet_tier), stale)
    assert resolve_tier(merged[0]) == expect
    assert merged[0]["is_core"] is {"core": True, "satellite": False}.get(expect)


def test_v2_session_switching_to_v1_does_not_carry_tier(monkeypatch):
    """v2 session（級別住在 is_core）切到 v1 Sheet（該檔未設定）→ 不帶入 v2 的級別。
    突變：拿掉 v1.py aggregated 的 `"is_core"` 鍵 → 本條轉紅。"""
    from ui.helpers import cloud_io
    v2_session = [{"code": "F1", "policy_id": "P1", "is_core": True, "policy_tier": "",
                   "loaded": True}]
    ss = {"portfolio_funds": v2_session, "t7_ledgers": {}}
    monkeypatch.setattr(cloud_io, "load_policies", lambda c, s: _v1_policies_df(""))
    monkeypatch.setattr(cloud_io, "load_all_ledgers_snapshot", lambda *a, **k: {})
    out = cloud_io.load_all_from_sheet("c", "s", ss, oauth_mode=False)
    assert out["error"] is None, out["error"]
    _f = [f for f in ss["portfolio_funds"] if f["code"] == "F1"][0]
    assert resolve_tier(_f) is None


# ══════════════════════════════════════════════════════════════════
# 1. 過期 is_core：JSON 還原
# ══════════════════════════════════════════════════════════════════
def _old_backup(policy_tier: str = "", is_core=True) -> bytes:
    """改動前匯出的備份；本 fixture 模擬 is_core 是名稱猜測的那一種（無法與 Sheet 設定分辨）。"""
    return json.dumps({
        "schema_version": "1.0",
        "portfolio_funds": [{
            "code": "F1", "name": _GUESSED_CORE_NAME, "invest_twd": 100000,
            "policy_id": "P1", "policy_name": "P1", "policy_tier": policy_tier,
            "currency": "USD", "is_core": is_core,
        }],
        "t7_ledgers": {},
    }, ensure_ascii=False).encode("utf-8")


def test_restore_ignores_backup_is_core():
    """突變：拿掉 json_backup.restore 的兩行級別重算 → 本條轉紅（tier == "core"）。"""
    from ui.helpers.io.json_backup import restore_from_json_bytes
    ss: dict = {}
    assert restore_from_json_bytes(_old_backup("", True), ss)["ok"]
    assert resolve_tier(ss["portfolio_funds"][0]) is None
    assert ss["portfolio_funds"][0]["is_core"] is None


@pytest.mark.parametrize("backup_tier, expect", [
    ("satellite", "satellite"), ("core", "core"), ("核心", "core"), ("bogus", None),
])
def test_restore_tier_comes_from_backup_policy_tier_only(backup_tier, expect):
    """備份的 policy_tier（從 Sheet 讀來的客戶設定）照用；is_core 與它相反也不採。"""
    from ui.helpers.io.json_backup import restore_from_json_bytes
    ss: dict = {}
    restore_from_json_bytes(_old_backup(backup_tier, expect != "core"), ss)
    assert resolve_tier(ss["portfolio_funds"][0]) == expect


def test_old_backup_restore_then_v2_dump_does_not_write_guessed_core(monkeypatch):
    """稽核實證的重現：還原舊 v2 備份 → `_dump_all_to_sheet_v2` 原本寫出 tier `core`。
    突變：拿掉 json_backup.restore 的級別重算 → 本條轉紅（寫出 "core"）。"""
    from ui.helpers import cloud_io
    from ui.helpers.io.json_backup import restore_from_json_bytes
    ss: dict = {}
    restore_from_json_bytes(_old_backup("", True), ss)
    _seen: list = []
    monkeypatch.setattr(cloud_io, "write_policy_v2",
                        lambda c, s, pid, df, **k: (_seen.append((df, k)), len(df))[1])
    out = cloud_io._dump_all_to_sheet_v2("c", "s", ss)
    assert out["error"] is None, out["error"]
    _df, _kw = _seen[0]
    assert _df["tier"].tolist() == [""]
    assert _kw.get("keep_sheet_tier") is True


def test_old_backup_restore_then_v1_read_then_dump_writes_no_guess(monkeypatch):
    """舊備份還原 → v1 讀回 → 全部寫入：寫出的級別不得是名稱猜測。
    突變：同時拿掉 restore 與 v1 aggregated 的修正 → 本條轉紅。"""
    from ui.helpers import cloud_io
    from ui.helpers.io.json_backup import restore_from_json_bytes
    ss: dict = {}
    restore_from_json_bytes(_old_backup("", True), ss)
    monkeypatch.setattr(cloud_io, "load_policies", lambda c, s: _v1_policies_df(""))
    monkeypatch.setattr(cloud_io, "load_all_ledgers_snapshot", lambda *a, **k: {})
    assert cloud_io.load_all_from_sheet("c", "s", ss, oauth_mode=False)["error"] is None
    _rows: list = []
    monkeypatch.setattr(cloud_io, "detect_sheet_schema_version", lambda c, s: "v1")
    monkeypatch.setattr(cloud_io, "upsert_fund_in_policy",
                        lambda c, s, pid, row: _rows.append(row))
    assert cloud_io.dump_all_to_sheet("c", "s", ss)["ok"]
    assert [r["policy_tier"] for r in _rows] == [""]


def test_export_carries_v2_tier_in_policy_tier():
    """匯出：v2 session 的級別（is_core）收進 policy_tier，否則新備份還原後級別會消失。"""
    from ui.helpers.io.json_backup import build_export_payload, restore_from_json_bytes
    ss = {"portfolio_funds": [
        {"code": "F1", "policy_id": "P1", "is_core": True, "policy_tier": ""},
        {"code": "F2", "policy_id": "P1", "is_core": None, "policy_tier": ""},
        {"code": "F3", "policy_id": "P1", "policy_tier": "satellite"},
    ]}
    _p = build_export_payload(ss)
    assert [f["policy_tier"] for f in _p["portfolio_funds"]] == ["core", "", "satellite"]
    assert [f["is_core"] for f in _p["portfolio_funds"]] == [True, None, False]
    ss2: dict = {}
    restore_from_json_bytes(json.dumps(_p).encode("utf-8"), ss2)
    assert [resolve_tier(f) for f in ss2["portfolio_funds"]] == ["core", None, "satellite"]


# ══════════════════════════════════════════════════════════════════
# 2. 寫回保留 Sheet 原值 —— 假 gspread
# ══════════════════════════════════════════════════════════════════
class _FakeWS:
    def __init__(self, values, fail_read: bool = False):
        self.values = [list(r) for r in values]
        self.fail_read = fail_read
        self.cleared = False
        self.updates: list = []
        self.appended: list = []

    def get_all_values(self):
        if self.fail_read:
            raise RuntimeError("read boom")
        return [list(r) for r in self.values]

    def get_all_records(self):
        hdr = self.values[0]
        return [dict(zip(hdr, r)) for r in self.values[1:]]

    def row_values(self, i):
        return list(self.values[i - 1]) if len(self.values) >= i else []

    def update(self, rng, rows):
        self.updates.append((rng, rows))

    def append_row(self, values):
        self.appended.append(values)

    def clear(self):
        self.cleared = True

    def format(self, *a, **k):
        pass


class _FakeSH:
    def __init__(self, ws):
        self.ws = ws

    def worksheet(self, title):
        return self.ws


class _FakeClient:
    def __init__(self, ws):
        self.sh = _FakeSH(ws)

    def open_by_key(self, sid):
        return self.sh


def _v1_tab_values(tier_cells: dict) -> list:
    from repositories.policy._helpers import ALL_COLS
    hdr = list(ALL_COLS)
    rows = [hdr]
    for code, tier in tier_cells.items():
        r = [""] * len(hdr)
        r[hdr.index("policy_id")] = "P1"
        r[hdr.index("fund_url")] = code
        r[hdr.index("policy_tier")] = tier
        rows.append(r)
    return rows


@pytest.mark.parametrize("sheet_tier, session_tier, expect", [
    ("core", "", "core"),            # 還原後未設定 → 不清空 Sheet
    ("foo", "", "foo"),              # 認不得的值原樣寫回
    ("核心", "core", "核心"),         # 語意相同保留拼法
    ("core", "satellite", "satellite"),
    ("", "core", "core"),
])
def test_v1_upsert_keeps_sheet_tier_when_session_unset(monkeypatch, sheet_tier, session_tier, expect):
    """突變：upsert_fund_in_policy 不走 merge_sheet_tier（直接寫 row 值）→ 前三列轉紅。"""
    from repositories.policy import v2 as V2
    from repositories.policy._helpers import ALL_COLS
    ws = _FakeWS(_v1_tab_values({"F1": sheet_tier}))
    monkeypatch.setattr(V2, "ensure_policy_worksheet", lambda c, s, p: ws)
    assert V2.upsert_fund_in_policy("c", "s", "P1", {
        "fund_url": "F1", "policy_name": "P1", "policy_tier": session_tier}) == "updated"
    _rng, _rows = ws.updates[-1]
    assert _rows[0][list(ALL_COLS).index("policy_tier")] == expect


def test_v1_upsert_without_tier_key_keeps_sheet(monkeypatch):
    from repositories.policy import v2 as V2
    from repositories.policy._helpers import ALL_COLS
    ws = _FakeWS(_v1_tab_values({"F1": "satellite"}))
    monkeypatch.setattr(V2, "ensure_policy_worksheet", lambda c, s, p: ws)
    V2.upsert_fund_in_policy("c", "s", "P1", {"fund_url": "F1", "policy_name": "P1"})
    assert ws.updates[-1][1][0][list(ALL_COLS).index("policy_tier")] == "satellite"


def _v2_tab_values(tier_cells: dict, zh: bool = True) -> list:
    from repositories.policy.v2 import ALL_COLS_V2, ZH_HEADERS_V2
    hdr = [ZH_HEADERS_V2[c] if zh else c for c in ALL_COLS_V2]
    rows = [hdr]
    for code, tier in tier_cells.items():
        r = [""] * len(hdr)
        r[list(ALL_COLS_V2).index("policy_id")] = "P1"
        r[list(ALL_COLS_V2).index("fund_code")] = code
        r[list(ALL_COLS_V2).index("tier")] = tier
        rows.append(r)
    return rows


def _df_v2(tiers: dict) -> pd.DataFrame:
    from repositories.policy.v2 import ALL_COLS_V2
    return pd.DataFrame([{"policy_id": "P1", "fund_code": c, "tier": t, "invest_twd": 100}
                         for c, t in tiers.items()], columns=list(ALL_COLS_V2))


def _written_rows(ws) -> list:
    """寫出的 (代號, 級別, 本金) 依列序。"""
    from repositories.policy.v2 import ALL_COLS_V2
    _c = list(ALL_COLS_V2)
    _rng, rows = ws.updates[0]
    return [(r[_c.index("fund_code")], r[_c.index("tier")], r[_c.index("invest_twd")])
            for r in rows[1:]]


def _written_tiers(ws) -> dict:
    from repositories.policy.v2 import ALL_COLS_V2
    _rng, rows = ws.updates[0]
    _ci, _ti = list(ALL_COLS_V2).index("fund_code"), list(ALL_COLS_V2).index("tier")
    return {r[_ci]: r[_ti] for r in rows[1:]}


@pytest.mark.parametrize("zh", [True, False])
def test_v2_write_keep_sheet_tier(zh):
    """突變：write_policy_v2 的 tier 欄不走 merge_sheet_tier → F1/F2/F3 轉紅（寫成空白）。"""
    from repositories.policy.v2 import write_policy_v2
    ws = _FakeWS(_v2_tab_values({"F1": "core", "F2": "核心", "F3": "foo", "F5": "satellite"}, zh))
    write_policy_v2(_FakeClient(ws), "s", "P1",
                    _df_v2({"F1": "", "F2": "core", "F3": "", "F4": "satellite", "F5": "core"}),
                    keep_sheet_tier=True)
    assert _written_tiers(ws) == {"F1": "core", "F2": "核心", "F3": "foo",
                                  "F4": "satellite", "F5": "core"}


def test_v2_write_default_unchanged_writes_df_as_is():
    """預設 keep_sheet_tier=False：編輯器等「df 就是整張表」的路徑行為不變、也不多讀一次。"""
    from repositories.policy.v2 import write_policy_v2
    ws = _FakeWS(_v2_tab_values({"F1": "core"}), fail_read=True)
    write_policy_v2(_FakeClient(ws), "s", "P1", _df_v2({"F1": ""}))
    assert _written_tiers(ws) == {"F1": ""}


def test_v2_write_read_failure_does_not_clear_tab():
    from repositories.policy._helpers import PolicySheetError
    from repositories.policy.v2 import write_policy_v2
    ws = _FakeWS(_v2_tab_values({"F1": "core"}), fail_read=True)
    with pytest.raises(PolicySheetError):
        write_policy_v2(_FakeClient(ws), "s", "P1", _df_v2({"F1": ""}), keep_sheet_tier=True)
    assert ws.cleared is False and ws.updates == []


def test_v2_write_v1_headers_in_v2_sheet():
    """混合 Sheet：v1 英文分頁（fund_url／policy_tier）也能定位既有級別。"""
    from repositories.policy.v2 import _tier_by_code_from_values
    assert _tier_by_code_from_values(_v1_tab_values({"F1": "core", "F2": "x"})) == {
        "F1": ["core"], "F2": ["x"]}
    assert _tier_by_code_from_values([]) == {}
    assert _tier_by_code_from_values([["a", "b"], ["1", "2"]]) == {}


def test_restore_then_full_v2_dump_keeps_sheet_tier(monkeypatch):
    """端到端：還原舊備份（級別 → 未設定）→ v2「全部寫入」→ Sheet 上既有的 core 不被清空。
    突變：cloud_io 拿掉 `keep_sheet_tier=True` → 本條轉紅（寫成空白）。"""
    from ui.helpers import cloud_io
    from ui.helpers.io.json_backup import restore_from_json_bytes
    ss: dict = {}
    restore_from_json_bytes(_old_backup("", True), ss)
    ws = _FakeWS(_v2_tab_values({"F1": "core"}))
    monkeypatch.setattr(cloud_io, "detect_sheet_schema_version", lambda c, s: "v2")
    import time as _time
    monkeypatch.setattr(_time, "sleep", lambda s: None)
    out = cloud_io.dump_all_to_sheet(_FakeClient(ws), "s", ss)
    assert out["ok"] and not out["warnings"], out
    assert _written_tiers(ws) == {"F1": "core"}


# ══════════════════════════════════════════════════════════════════
# 3. 保資料：讀端辨識中文、認不得的值不進計算
# ══════════════════════════════════════════════════════════════════
def test_v1_loader_recognizes_chinese_and_blanks_unknown_in_session():
    from repositories.policy.v2 import _records_to_policy_df
    df = _records_to_policy_df([
        {"policy_id": "P1", "policy_name": "", "fund_url": c, "invest_twd": 1,
         "invest_date": "", "currency": "USD", "fx_at_buy": 0, "notes": "", "policy_tier": t}
        for c, t in (("F1", "核心"), ("F2", "衛星"), ("F3", "foo"), ("F4", "CORE"))])
    assert df["policy_tier"].tolist() == ["core", "satellite", "", "core"]


@pytest.mark.parametrize("sheet_tier, expect", [
    ("核心", "core"), ("衛星", "satellite"), ("foo", None), ("Core", "core"),
])
def test_v2_read_recognizes_chinese(monkeypatch, sheet_tier, expect):
    from repositories.policy.v2 import ALL_COLS_V2
    from ui.helpers import cloud_io
    _df = pd.DataFrame([{"policy_id": "P1", "fund_code": "F1", "tier": sheet_tier,
                         "invest_twd": 1}], columns=list(ALL_COLS_V2)).fillna("")
    monkeypatch.setattr(cloud_io, "load_all_policies_v2", lambda c, s: _df)
    ss: dict = {"portfolio_funds": []}
    assert cloud_io._load_all_from_sheet_v2("c", "s", ss)["error"] is None
    assert resolve_tier(ss["portfolio_funds"][0]) == expect


# ══════════════════════════════════════════════════════════════════
# 小修：全部未設定時檔數格不只顯示「—」
# ══════════════════════════════════════════════════════════════════
def test_health_ratio_label_all_unset_shows_count():
    """突變：拿掉 health.py 的 `elif n_unset` 分支 → 本條轉紅（"—"）。"""
    from ui.helpers.portfolio.health import compute_health_kpis
    funds = [{"code": c, "loaded": True} for c in ("F1", "F2")]
    mk = pd.DataFrame({"MK_Class": ["Unset", "Unset"], "Price_Zone": ["", ""],
                       "Health_Check": ["", ""]})
    k = compute_health_kpis(funds, mk)
    assert k["ratio_label"] == "⬜ 未設定 2 檔"
    assert k["n_classed"] == 0 and k["pct_core"] == 0


def test_health_ratio_label_mixed_unchanged():
    from ui.helpers.portfolio.health import compute_health_kpis
    funds = [{"code": c, "loaded": True} for c in ("F1", "F2")]
    mk = pd.DataFrame({"MK_Class": ["Core", "Unset"], "Price_Zone": ["", ""],
                       "Health_Check": ["", ""]})
    assert compute_health_kpis(funds, mk)["ratio_label"] == "核心 1 檔 / 衛星 0 檔 / ⬜ 未設定 1 檔"


def test_manual_has_no_unapproved_parenthetical():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "ui" / "tab6_manual.py").read_text(
        encoding="utf-8")
    assert "仍以基金名稱判斷" not in src
    assert "組合的核心／衛星級別不再用基金名稱推定。" in src


# ══════════════════════════════════════════════════════════════════
# 稽核 C（M-1）：同代號多列 —— 以 (代號, 第 k 次出現) 對齊，不得把 A 列的級別滲到 B 列
# ══════════════════════════════════════════════════════════════════
def _v2_tab_rows(rows: list) -> list:
    """rows: [(代號, 級別, 本金), ...] → 中文表頭 v2 分頁的 get_all_values。"""
    from repositories.policy.v2 import ALL_COLS_V2, ZH_HEADERS_V2
    _c = list(ALL_COLS_V2)
    out = [[ZH_HEADERS_V2[c] for c in _c]]
    for code, tier, amt in rows:
        r = [""] * len(_c)
        r[_c.index("policy_id")] = "P1"
        r[_c.index("fund_code")] = code
        r[_c.index("tier")] = tier
        r[_c.index("invest_twd")] = str(amt)
        out.append(r)
    return out


def _sheet_round_trip(monkeypatch, sheet_rows: list) -> list:
    """Sheet 分頁 → `_load_all_from_sheet_v2` → v2 全部寫入（真 write_policy_v2、假 gspread）。"""
    from repositories.policy.v2 import ALL_COLS_V2
    from ui.helpers import cloud_io
    _c = list(ALL_COLS_V2)
    _df = pd.DataFrame([{"policy_id": "P1", "fund_code": c, "tier": t, "invest_twd": a}
                        for c, t, a in sheet_rows], columns=_c).fillna("")
    monkeypatch.setattr(cloud_io, "load_all_policies_v2", lambda c, s: _df)
    ss: dict = {"portfolio_funds": []}
    assert cloud_io._load_all_from_sheet_v2("c", "s", ss)["error"] is None
    ws = _FakeWS(_v2_tab_rows(sheet_rows))
    monkeypatch.setattr(cloud_io, "detect_sheet_schema_version", lambda c, s: "v2")
    import time as _time
    monkeypatch.setattr(_time, "sleep", lambda s: None)
    out = cloud_io.dump_all_to_sheet(_FakeClient(ws), "s", ss)
    assert out["ok"] and not out["warnings"], out
    return _written_rows(ws)


@pytest.mark.parametrize("first_tier", ["core", "foo"])
def test_v2_same_code_two_rows_tier_does_not_leak(monkeypatch, first_tier):
    """稽核 C 重現：[F1 core 100] + [F1 '' 200] → 56f135c 寫出 ('F1','core',200)。
    突變：對齊改成「最後一列優先」或「只取第一列」→ 本條轉紅。"""
    assert _sheet_round_trip(monkeypatch, [("F1", first_tier, 100), ("F1", "", 200)]) == [
        ("F1", first_tier, 100), ("F1", "", 200)]


def test_v2_same_code_two_rows_reverse_order(monkeypatch):
    """空白列在前、核心列在後：各自保留自己的值。"""
    assert _sheet_round_trip(monkeypatch, [("F1", "", 100), ("F1", "core", 200)]) == [
        ("F1", "", 100), ("F1", "core", 200)]


def test_v2_rows_reordered_across_codes_align_per_code():
    """列序改變（不同代號交錯、df 順序與 Sheet 不同）：每個代號各自依出現次序對齊。"""
    from repositories.policy.v2 import write_policy_v2
    ws = _FakeWS(_v2_tab_rows([("F1", "core", 1), ("F2", "foo", 2), ("F1", "", 3),
                               ("F2", "satellite", 4)]))
    df = pd.DataFrame([{"policy_id": "P1", "fund_code": c, "tier": "", "invest_twd": a}
                       for c, a in (("F2", 2), ("F2", 4), ("F1", 1), ("F1", 3))])
    write_policy_v2(_FakeClient(ws), "s", "P1", df, keep_sheet_tier=True)
    assert _written_rows(ws) == [("F2", "foo", 2), ("F2", "satellite", 4),
                                 ("F1", "core", 1), ("F1", "", 3)]


@pytest.mark.parametrize("sheet_rows, df_rows, expect", [
    # Sheet 2 列、df 1 列 → 出現次數不同 → 不保留、照寫 df 值（空 → 空白，刻意取捨）
    ([("F1", "core", 1), ("F1", "", 2)], [("F1", "", 1)], [("F1", "", 1)]),
    # Sheet 1 列、df 2 列 → 同上
    ([("F1", "core", 1)], [("F1", "", 1), ("F1", "", 2)], [("F1", "", 1), ("F1", "", 2)]),
    # 次數不同但 df 有明確級別 → 照寫 df 值
    ([("F1", "core", 1)], [("F1", "satellite", 1), ("F1", "", 2)],
     [("F1", "satellite", 1), ("F1", "", 2)]),
    # 其他代號次數一致 → 不受影響、照常保留
    ([("F1", "core", 1), ("F2", "foo", 2)], [("F1", "", 1), ("F1", "", 9), ("F2", "", 2)],
     [("F1", "", 1), ("F1", "", 9), ("F2", "foo", 2)]),
])
def test_v2_occurrence_count_mismatch_skips_preservation(sheet_rows, df_rows, expect):
    from repositories.policy.v2 import write_policy_v2
    ws = _FakeWS(_v2_tab_rows(sheet_rows))
    df = pd.DataFrame([{"policy_id": "P1", "fund_code": c, "tier": t, "invest_twd": a}
                       for c, t, a in df_rows])
    write_policy_v2(_FakeClient(ws), "s", "P1", df, keep_sheet_tier=True)
    assert _written_rows(ws) == expect


def test_tier_by_code_keeps_all_occurrences_in_order():
    from repositories.policy.v2 import _tier_by_code_from_values
    assert _tier_by_code_from_values(_v2_tab_rows([("f1", "core", 1), ("F2", "x", 2),
                                                   ("F1", "", 3)])) == {
        "F1": ["core", ""], "F2": ["x"]}


@pytest.mark.parametrize("cells, expect_first, expect_second", [
    (["core", ""], "core", ""),
    (["", "core"], "", "core"),
])
def test_v1_upsert_same_url_two_rows_no_leak(monkeypatch, cells, expect_first, expect_second):
    """v1 分頁同 fund_url 兩列：upsert 只改第一列、級別取自第一列本身；第二列不被動到。"""
    from repositories.policy import v2 as V2
    from repositories.policy._helpers import ALL_COLS
    vals = _v1_tab_values({"F1": cells[0]})
    second = list(vals[1])
    second[list(ALL_COLS).index("policy_tier")] = cells[1]
    vals.append(second)
    ws = _FakeWS(vals)
    monkeypatch.setattr(V2, "ensure_policy_worksheet", lambda c, s, p: ws)
    V2.upsert_fund_in_policy("c", "s", "P1", {"fund_url": "F1", "policy_tier": ""})
    assert len(ws.updates) == 1
    _rng, _rows = ws.updates[0]
    assert _rng.startswith("A2:")
    assert _rows[0][list(ALL_COLS).index("policy_tier")] == expect_first
    assert ws.values[2][list(ALL_COLS).index("policy_tier")] == expect_second


# ══════════════════════════════════════════════════════════════════
# 稽核 C：直接打 v1.load_policies 的中文辨識
# ══════════════════════════════════════════════════════════════════
def test_v1_load_policies_recognizes_chinese(monkeypatch):
    """突變：load_policies 改回 `.str.lower().where(isin(["core","satellite"]))` → 本條轉紅。"""
    from repositories.policy import v1 as V1
    ws = _FakeWS(_v1_tab_values({"F1": "核心", "F2": "衛星", "F3": "foo", "F4": "Core"}))
    monkeypatch.setattr(V1, "_open_worksheet", lambda c, s, w="Policies": ws)
    df = V1.load_policies("c", "s")
    assert df["policy_tier"].tolist() == ["core", "satellite", "", "core"]


# ══════════════════════════════════════════════════════════════════
# 稽核 C：舊 SA 表單（upsert_policy_row）更新既有列不清空級別
# ══════════════════════════════════════════════════════════════════
def _sa_form_row(code: str = "F1") -> dict:
    """舊 SA 表單送出的列：沒有 policy_tier 鍵（ui/helpers/portfolio/policy_admin_section.py）。"""
    return {"policy_id": "P1", "policy_name": "新名稱", "fund_url": code,
            "invest_twd": 500, "invest_date": "", "currency": "USD",
            "fx_at_buy": 0.0, "notes": "改"}


@pytest.mark.parametrize("sheet_tier", ["core", "foo", "核心", ""])
def test_legacy_upsert_policy_row_keeps_sheet_tier(monkeypatch, sheet_tier):
    """突變：upsert_policy_row 拿掉 merge 段 → core／foo／核心三列轉紅（寫成空白）。"""
    from repositories.policy import v1 as V1
    from repositories.policy._helpers import ALL_COLS
    ws = _FakeWS(_v1_tab_values({"F1": sheet_tier}))
    monkeypatch.setattr(V1, "_open_worksheet", lambda c, s, w="Policies": ws)
    assert V1.upsert_policy_row("c", "s", _sa_form_row()) == "updated"
    _rng, _rows = ws.updates[-1]
    _c = list(ALL_COLS)
    assert _rows[0][_c.index("policy_tier")] == sheet_tier
    # 其他欄照舊整列覆寫（語意不變）
    assert _rows[0][_c.index("policy_name")] == "新名稱"
    assert _rows[0][_c.index("invest_twd")] == 500


def test_legacy_upsert_policy_row_explicit_tier_and_insert(monkeypatch):
    from repositories.policy import v1 as V1
    from repositories.policy._helpers import ALL_COLS
    _c = list(ALL_COLS)
    ws = _FakeWS(_v1_tab_values({"F1": "core"}))
    monkeypatch.setattr(V1, "_open_worksheet", lambda c, s, w="Policies": ws)
    V1.upsert_policy_row("c", "s", {**_sa_form_row(), "policy_tier": "satellite"})
    assert ws.updates[-1][1][0][_c.index("policy_tier")] == "satellite"
    assert V1.upsert_policy_row("c", "s", _sa_form_row("F9")) == "inserted"
    assert ws.appended[-1][_c.index("policy_tier")] == ""


def test_legacy_upsert_policy_row_header_without_tier_column(monkeypatch):
    """舊 8 欄表頭（沒有 policy_tier 欄）→ 寫入寬度不變、不碰級別。"""
    from repositories.policy import v1 as V1
    from repositories.policy._helpers import REQUIRED_COLS
    ws = _FakeWS([list(REQUIRED_COLS),
                  ["P1", "", "F1", "1", "", "USD", "0", ""]])
    monkeypatch.setattr(V1, "_open_worksheet", lambda c, s, w="Policies": ws)
    V1.upsert_policy_row("c", "s", _sa_form_row())
    assert len(ws.updates[-1][1][0]) == len(REQUIRED_COLS)
