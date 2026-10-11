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
# 稽核 C（M-1）：同代號多列 —— 只保留單列代號；多列代號照寫 df 值，不得把別列的級別搬過來
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


def _sheet_round_trip(monkeypatch, sheet_rows: list, sheet_at_write: list | None = None,
                      expect_conflict: bool = False) -> list | None:
    """Sheet 分頁 → `_load_all_from_sheet_v2` → v2 全部寫入（真 write_policy_v2、假 gspread）。

    sheet_at_write：寫入當下 Sheet 的內容（模擬讀回之後客戶在 Sheet 上調過列序）；
    省略 ＝ 與讀回時相同。

    2026-10-11 N1：讀回成功後補 `capture_snapshot(ss)` —— 真實流程由 policy_admin_section 在
    「全部讀回」成功後擷取讀回快照；沒有快照時同代號多列級別不一致會 fail closed。
    expect_conflict=True：預期這張保單被擋（回傳 None；斷言分頁沒被清、沒被寫、警告含衝突字句）。
    """
    from repositories.policy.v2 import ALL_COLS_V2
    from shared.tier_write_gate import capture_snapshot
    from ui.helpers import cloud_io
    _c = list(ALL_COLS_V2)
    _df = pd.DataFrame([{"policy_id": "P1", "fund_code": c, "tier": t, "invest_twd": a}
                        for c, t, a in sheet_rows], columns=_c).fillna("")
    monkeypatch.setattr(cloud_io, "load_all_policies_v2", lambda c, s: _df)
    ss: dict = {"portfolio_funds": []}
    assert cloud_io._load_all_from_sheet_v2("c", "s", ss)["error"] is None
    capture_snapshot(ss)
    ws = _FakeWS(_v2_tab_rows(sheet_rows if sheet_at_write is None else sheet_at_write))
    monkeypatch.setattr(cloud_io, "detect_sheet_schema_version", lambda c, s: "v2")
    import time as _time
    monkeypatch.setattr(_time, "sleep", lambda s: None)
    out = cloud_io.dump_all_to_sheet(_FakeClient(ws), "s", ss)
    if expect_conflict:
        assert ws.cleared is False and ws.updates == []
        assert any("P1: ❌ 級別設定衝突：F1，未寫入此保單。" in w for w in out["warnings"]), out
        return None
    assert out["ok"] and not out["warnings"], out
    return _written_rows(ws)


@pytest.mark.parametrize("first_tier, expect_first", [
    ("core", "core"),   # session 本身就讀到 core → 照寫
    # ~~("foo", ""),  # 認不得 → session 未設定；多列代號不保留 → 空白（刻意取捨，同 e6b4702）~~
    # 2026-10-11 客戶裁示：不得把 Sheet 明示級別清成空白 → 「foo＋留白」改為衝突、整張不寫，
    # 移至 `test_round_trip_unrecognized_plus_blank_fails_closed`。
])
def test_v2_same_code_two_rows_tier_does_not_leak(monkeypatch, first_tier, expect_first):
    """稽核 C 重現：[F1 core 100] + [F1 '' 200] → 56f135c 寫出 ('F1','core',200)。
    第二列（未設定）一律不得拿到第一列的級別。"""
    assert _sheet_round_trip(monkeypatch, [("F1", first_tier, 100), ("F1", "", 200)]) == [
        ("F1", expect_first, 100), ("F1", "", 200)]


def test_v2_same_code_rows_reordered_in_sheet_before_write_does_not_fabricate(monkeypatch):
    """稽核 C 剩餘風險：讀回 [F1 '' 100, F1 core 200]，寫入前客戶在 Sheet 上把列序調成
    [F1 core 200, F1 '' 100] → 不得把 core 寫到 100 那一列（未設定）。
    突變：恢復「代號＋第 k 次出現」對齊 → 本條轉紅（寫出 ('F1','core',100)）。
    2026-10-11 N1：Sheet 讀回後已被改（列序與讀回快照不同）→ 同代號多列級別不完全一致一律 fail closed，
    整張不寫（不再照寫 session 值）；~~舊預期 [("F1","",100),("F1","core",200)]~~。"""
    assert _sheet_round_trip(
        monkeypatch,
        [("F1", "", 100), ("F1", "core", 200)],
        sheet_at_write=[("F1", "core", 200), ("F1", "", 100)],
        expect_conflict=True,
    ) is None


def test_v2_same_code_two_rows_blank_first(monkeypatch):
    """空白列在前、核心列在後：照寫各自的 session 值。"""
    assert _sheet_round_trip(monkeypatch, [("F1", "", 100), ("F1", "core", 200)]) == [
        ("F1", "", 100), ("F1", "core", 200)]


def test_v2_single_row_codes_still_preserved_when_rows_reordered():
    """單列代號照常保留，不受其他代號多列、或 df 與 Sheet 列序不同影響。
    ~~突變：保留條件放寬成「Sheet 有該代號就取第一列」→ 本條轉紅（F1 寫出 core）。~~
    2026-10-11：F1 原為 Sheet [core, 留白]＋session 全未設定 —— 客戶裁示後屬「對不上哪一列是
    留白」→ 整張不寫，無法再拿來測單列代號；F1 改為 [satellite, satellite]（同語意 → 保留），
    本條只守 F2／F3（單列）與 F1（多列同語意）。"""
    from repositories.policy.v2 import write_policy_v2
    ws = _FakeWS(_v2_tab_rows([("F1", "satellite", 1), ("F2", "foo", 2), ("F1", "satellite", 3),
                               ("F3", "satellite", 4)]))
    df = pd.DataFrame([{"policy_id": "P1", "fund_code": c, "tier": "", "invest_twd": a}
                       for c, a in (("F3", 4), ("F2", 2), ("F1", 3), ("F1", 1))])
    write_policy_v2(_FakeClient(ws), "s", "P1", df, keep_sheet_tier=True)
    # ~~[("F3","satellite",4), ("F2","foo",2), ("F1","",3), ("F1","",1)]~~（舊 F1 [core, 留白]）
    assert _written_rows(ws) == [("F3", "satellite", 4), ("F2", "foo", 2),
                                 ("F1", "satellite", 3), ("F1", "satellite", 1)]


# ~~expect 欄（b8aa0ec「多列代號不保留、照寫 df 值」的舊斷言，2026-10-11 客戶裁示推翻 ——~~
# ~~這五組舊斷言全都會把 Sheet 上的 core／foo 寫成空白）：~~
#   ~~0: [("F1", "", 1)]~~
#   ~~1: [("F1", "", 1), ("F1", "", 2)]~~
#   ~~2: [("F1", "", 1), ("F1", "", 2)]~~
#   ~~3: [("F1", "satellite", 1), ("F1", "", 2)]~~
#   ~~4: [("F1", "", 1), ("F1", "", 9), ("F2", "foo", 2)]~~
# 現行：五組都是「Sheet 能給未設定列的值不只一種」（core＋留白／core＋foo／df 明確列取代了
# 哪一格不可知）→ 整張分頁不寫（含第 4 組的單列代號 F2：裁示為整張保單不寫，不是只跳過 F1）。
@pytest.mark.parametrize("sheet_rows, df_rows", [
    # Sheet 2 列（core＋留白）、df 1 列未設定 → 對不上哪一列
    ([("F1", "core", 1), ("F1", "", 2)], [("F1", "", 1)]),
    # Sheet 1 列、df 2 列未設定 → 多出的那列 Sheet 上沒有 → 候選 core＋留白
    ([("F1", "core", 1)], [("F1", "", 1), ("F1", "", 2)]),
    # Sheet 2 列（core＋認不得）
    ([("F1", "core", 1), ("F1", "foo", 2)], [("F1", "", 1), ("F1", "", 2)]),
    # df 有一列明確 satellite（Sheet 沒有 satellite → 取代了哪一格不可知）＋一列未設定
    ([("F1", "core", 1)], [("F1", "satellite", 1), ("F1", "", 2)]),
    # 其他單列代號 F2 一樣不寫（整張保單）
    ([("F1", "core", 1), ("F2", "foo", 2)], [("F1", "", 1), ("F1", "", 9), ("F2", "", 2)]),
])
def test_v2_multi_row_code_skips_preservation(sheet_rows, df_rows):
    from repositories.policy.v2 import PolicyTierConflictError, write_policy_v2
    ws = _FakeWS(_v2_tab_rows(sheet_rows))
    df = pd.DataFrame([{"policy_id": "P1", "fund_code": c, "tier": t, "invest_twd": a}
                       for c, t, a in df_rows])
    with pytest.raises(PolicyTierConflictError) as ei:
        write_policy_v2(_FakeClient(ws), "s", "P1", df, keep_sheet_tier=True)
    assert str(ei.value) == "❌ 級別設定衝突：F1，未寫入此保單。"
    assert ws.cleared is False and ws.updates == []


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


# ══════════════════════════════════════════════════════════════════
# 客戶 2026-10-11 裁示：同代號多列 —— 同語意保留 Sheet 原值；互相衝突 → 整張保單不寫
# （獨立稽核重現：b8aa0ec 在 JSON 還原後「全部寫入」把 [F1 core, F1 satellite]、
#  [核心, 衛星]、[核心資產, 留白] 全寫成空白，且無任何提示）
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("df_tiers, sheet_raws, expect", [
    # 全部未設定、Sheet 同一語意 → 保留，拼法依剩餘 Sheet 格出現序（大小寫／中文／空白原樣）
    (["", ""], ["core", "Core"], ["core", "Core"]),
    (["", "", ""], ["核心", " CORE ", "core"], ["核心", " CORE ", "core"]),
    (["", ""], ["衛星", "satellite"], ["衛星", "satellite"]),
    (["", ""], ["", ""], ["", ""]),
    # Sheet 多、df 少（session 刪掉一列）→ 同語意照樣保留
    ([""], ["core", "核心"], ["core"]),
    # df 明確列用掉同語意那一格（保留拼法）→ 剩下的給未設定列
    (["core", ""], ["", "核心"], ["核心", ""]),
    # ~~(["", "satellite"], ["satellite", "core"], ["core", "satellite"]),~~
    # 2026-10-11 稽核必修 1：上列把「satellite 被明確列用掉、剩下 core」當成無衝突 → 把 core 寫進
    # 未設定列 ＝ 依列序配對＋捏造。Sheet 全部格子 core／satellite 並存 → 改為衝突（見下方衝突類）。
    (["", "satellite"], ["satellite", "core"], None),
    # df 明確列在 Sheet 找不到同語意格，但剩下全同語意 → 不論它取代哪一格，未設定列都是 core
    (["satellite", ""], ["core", "core"], ["satellite", "core"]),
    # df 全部明確 → 不需要 Sheet 值，不判衝突（session 明示優先，照舊）
    (["satellite", "core"], ["core", "satellite"], ["satellite", "core"]),
    (["core", "core"], ["核心資產", "foo"], ["core", "core"]),
    # 衝突 → None
    (["", ""], ["core", "satellite"], None),
    (["", ""], ["核心", "衛星"], None),
    (["", ""], ["核心資產", ""], None),          # 認不得 → 無法判定語意相同
    (["", ""], ["核心資產", "核心資產"], None),  # 同上（總管建議規則；見回報）
    (["", ""], ["core", ""], None),              # 有設有留白 → 對不上哪一列是留白
    (["", ""], ["core"], None),                  # session 多一列：候選 core＋留白
    (["satellite", ""], ["core", ""], None),     # 明確列取代了哪一格不可知 → 候選 core＋留白
])
def test_multi_row_tier_out_table(df_tiers, sheet_raws, expect):
    """突變 A：拿掉「同語意保留」（未設定列一律寫空白）→ 保留非空白值的各列轉紅（實跑 6 列；必修 1 後該類剩 5 列，實跑 5 列）。
    突變 B2：拿掉 `len(kinds) > 1 → None` → 衝突類中「留白混合」的 3 列轉紅（必修 1 後實跑；core／satellite 互衝改由「全部格子」判定擋下）。
    突變 C：拿掉「全部格子」判定（必修 1）→ `(["", "satellite"], ["satellite", "core"])` 轉紅。"""
    from repositories.policy.v2 import _multi_row_tier_out
    assert _multi_row_tier_out(df_tiers, sheet_raws) == expect


class _MultiSH:
    def __init__(self, tabs: dict):
        self.tabs = tabs

    def worksheet(self, title):
        return self.tabs[title]


class _MultiClient:
    def __init__(self, tabs: dict):
        self.sh = _MultiSH(tabs)

    def open_by_key(self, sid):
        return self.sh


def _backup_funds(funds: list) -> bytes:
    """funds: [(policy_id, code, invest_twd), ...] → 舊備份（級別一律還原成未設定）。"""
    return json.dumps({
        "schema_version": "1.0",
        "portfolio_funds": [{"code": c, "name": c, "invest_twd": a, "policy_id": p,
                             "policy_name": p, "policy_tier": "", "currency": "USD",
                             "is_core": True} for p, c, a in funds],
        "t7_ledgers": {},
    }, ensure_ascii=False).encode("utf-8")


def _restore_and_dump(monkeypatch, funds: list, tabs: dict) -> dict:
    from ui.helpers import cloud_io
    from ui.helpers.io.json_backup import restore_from_json_bytes
    ss: dict = {}
    assert restore_from_json_bytes(_backup_funds(funds), ss)["ok"]
    assert all(resolve_tier(f) is None for f in ss["portfolio_funds"])
    monkeypatch.setattr(cloud_io, "detect_sheet_schema_version", lambda c, s: "v2")
    import time as _time
    monkeypatch.setattr(_time, "sleep", lambda s: None)
    return cloud_io.dump_all_to_sheet(_MultiClient(tabs), "s", ss)


@pytest.mark.parametrize("sheet_rows", [
    [("F1", "core", 100), ("F1", "satellite", 200)],   # 稽核重現 1
    [("F1", "核心", 100), ("F1", "衛星", 200)],         # 稽核重現 2
    [("F1", "核心資產", 100), ("F1", "", 200)],         # 稽核重現 3
])
def test_restore_then_dump_conflict_fails_closed_other_policy_written(monkeypatch, sheet_rows):
    """JSON 還原 → 全部寫入：衝突保單整張不動、提示含代號；其他保單照常寫入（含保留級別）。
    突變 B（拿掉衝突中止）→ 本條轉紅（P1 被清空重寫）。"""
    p1 = _FakeWS(_v2_tab_rows(sheet_rows))
    p2 = _FakeWS(_v2_tab_rows([("F9", "核心", 300)]))
    out = _restore_and_dump(
        monkeypatch, [("P1", "F1", 100), ("P1", "F1", 200), ("P2", "F9", 300)],
        {"P1": p1, "P2": p2})
    assert out["ok"] and out["error"] is None, out
    assert p1.cleared is False and p1.updates == []
    assert _written_rows(p2) == [("F9", "核心", 300)]
    assert out["written"] == 1
    assert len(out["warnings"]) == 1
    assert "P1: ❌ 級別設定衝突：F1，未寫入此保單。" in out["warnings"][0]


def test_restore_then_dump_same_semantic_multi_row_keeps_sheet_spelling(monkeypatch):
    """同代號多列同語意（大小寫／中文／原拼法）→ 保留每列 Sheet 原值，不清成空白。
    突變 A（拿掉同語意保留）→ 本條轉紅（寫出空白，即 b8aa0ec 的行為）。"""
    p1 = _FakeWS(_v2_tab_rows([("F1", "核心", 100), ("F1", "Core", 200),
                               ("F2", "衛星", 50), ("F2", "satellite", 60)]))
    out = _restore_and_dump(
        monkeypatch, [("P1", "F1", 100), ("P1", "F1", 200), ("P1", "F2", 50), ("P1", "F2", 60)],
        {"P1": p1})
    assert out["ok"] and not out["warnings"], out
    assert _written_rows(p1) == [("F1", "核心", 100), ("F1", "Core", 200),
                                 ("F2", "衛星", 50), ("F2", "satellite", 60)]


def test_conflict_message_lists_all_codes_untruncated(monkeypatch):
    """多個衝突代號以「、」連接；cloud_io 不截斷（通用分支會截 80 字）。"""
    codes = [f"ABCDEFGH{i:02d}" for i in range(10)]
    rows = []
    for c in codes:
        rows += [(c, "core", 1), (c, "satellite", 2)]
    p1 = _FakeWS(_v2_tab_rows(rows))
    out = _restore_and_dump(monkeypatch, [("P1", c, a) for c, _t, a in rows], {"P1": p1})
    _msg = f"❌ 級別設定衝突：{'、'.join(codes)}，未寫入此保單。"
    assert len(_msg) > 80
    assert f"P1: {_msg}" in out["warnings"][0]
    assert p1.updates == []


def test_normal_round_trip_multi_row_different_tiers_not_blocked(monkeypatch):
    """一般流程（讀回後 session 每列都有明確級別）→ session 明示優先，不判衝突、照常寫入。"""
    assert _sheet_round_trip(monkeypatch, [("F1", "core", 1), ("F1", "satellite", 2)]) == [
        ("F1", "core", 1), ("F1", "satellite", 2)]
    # 2026-10-11 N1：混合群組靠『讀回快照一致』放行時，級別欄由閘門定案、以 session 值為準，
    # 「核心」寫成語意等價的 `core`（客戶核准的正規化）；~~舊預期保留原拼法「核心」~~。留白仍是留白。
    assert _sheet_round_trip(monkeypatch, [("F1", "核心", 1), ("F1", "", 2)]) == [
        ("F1", "core", 1), ("F1", "", 2)]


def test_single_row_and_session_explicit_unchanged_under_conflict_rule():
    """單列代號仍走 merge_sheet_tier（認不得的值原樣保留，不判衝突）；session 明示值優先。"""
    from repositories.policy.v2 import write_policy_v2
    ws = _FakeWS(_v2_tab_rows([("F1", "核心資產", 1), ("F2", "core", 2), ("F2", "core", 3)]))
    df = pd.DataFrame([{"policy_id": "P1", "fund_code": c, "tier": t, "invest_twd": a}
                       for c, t, a in (("F1", "", 1), ("F2", "satellite", 2), ("F2", "", 3))])
    write_policy_v2(_FakeClient(ws), "s", "P1", df, keep_sheet_tier=True)
    assert _written_rows(ws) == [("F1", "核心資產", 1), ("F2", "satellite", 2), ("F2", "core", 3)]


def test_round_trip_unrecognized_plus_blank_fails_closed(monkeypatch):
    """（原 `test_v2_same_code_two_rows_tier_does_not_leak` 的 ("foo", "") 那組）一般讀回 →
    全部寫入：[F1 foo, F1 留白] 兩列 session 皆未設定 → 不得把 foo 清成空白 → 整張不寫。"""
    from repositories.policy.v2 import ALL_COLS_V2
    from ui.helpers import cloud_io
    rows = [("F1", "foo", 100), ("F1", "", 200)]
    _df = pd.DataFrame([{"policy_id": "P1", "fund_code": c, "tier": t, "invest_twd": a}
                        for c, t, a in rows], columns=list(ALL_COLS_V2)).fillna("")
    monkeypatch.setattr(cloud_io, "load_all_policies_v2", lambda c, s: _df)
    ss: dict = {"portfolio_funds": []}
    assert cloud_io._load_all_from_sheet_v2("c", "s", ss)["error"] is None
    ws = _FakeWS(_v2_tab_rows(rows))
    monkeypatch.setattr(cloud_io, "detect_sheet_schema_version", lambda c, s: "v2")
    import time as _time
    monkeypatch.setattr(_time, "sleep", lambda s: None)
    out = cloud_io.dump_all_to_sheet(_FakeClient(ws), "s", ss)
    assert ws.cleared is False and ws.updates == []
    assert "P1: ❌ 級別設定衝突：F1，未寫入此保單。" in out["warnings"][0]


# ══════════════════════════════════════════════════════════════════
# 2026-10-11 稽核必修 1：Sheet 全部格子 core／satellite 並存 → 不得因明確列「用掉」一種就判無衝突
# ══════════════════════════════════════════════════════════════════
def test_round_trip_then_customer_edits_sheet_conflict_fails_closed(monkeypatch):
    """重現 A：讀回 [F1 satellite 100, F1 留白 200]，寫入前客戶在 Sheet 改成
    [F1 core 100, F1 satellite 200] → 4e0845e 寫出 [satellite 100, core 200]（捏造）。
    突變 C（拿掉「全部格子」判定）→ 本條轉紅。"""
    from repositories.policy.v2 import ALL_COLS_V2
    from ui.helpers import cloud_io
    read_rows = [("F1", "satellite", 100), ("F1", "", 200)]
    _df = pd.DataFrame([{"policy_id": "P1", "fund_code": c, "tier": t, "invest_twd": a}
                        for c, t, a in read_rows], columns=list(ALL_COLS_V2)).fillna("")
    monkeypatch.setattr(cloud_io, "load_all_policies_v2", lambda c, s: _df)
    ss: dict = {"portfolio_funds": []}
    assert cloud_io._load_all_from_sheet_v2("c", "s", ss)["error"] is None
    ws = _FakeWS(_v2_tab_rows([("F1", "core", 100), ("F1", "satellite", 200)]))
    monkeypatch.setattr(cloud_io, "detect_sheet_schema_version", lambda c, s: "v2")
    import time as _time
    monkeypatch.setattr(_time, "sleep", lambda s: None)
    out = cloud_io.dump_all_to_sheet(_FakeClient(ws), "s", ss)
    assert ws.cleared is False and ws.updates == []
    assert "P1: ❌ 級別設定衝突：F1，未寫入此保單。" in out["warnings"][0]


def _backup_with_tiers(funds: list) -> bytes:
    """funds: [(policy_id, code, invest_twd, policy_tier), ...]（備份裡的 policy_tier 會被採用）。"""
    return json.dumps({
        "schema_version": "1.0",
        "portfolio_funds": [{"code": c, "name": c, "invest_twd": a, "policy_id": p,
                             "policy_name": p, "policy_tier": t, "currency": "USD"}
                            for p, c, a, t in funds],
        "t7_ledgers": {},
    }, ensure_ascii=False).encode("utf-8")


@pytest.mark.parametrize("backup, sheet_rows", [
    # CE3：備份 [satellite 100, 未設定 200]、Sheet [core 100, satellite 200] → 舊版寫出 [satellite, core]
    ([("P1", "F1", 100, "satellite"), ("P1", "F1", 200, "")],
     [("F1", "core", 100), ("F1", "satellite", 200)]),
    # CE1：備份 [core 100, 未設定 200]、Sheet [satellite 100, core 200] → 舊版寫出 [core, satellite]
    ([("P1", "F1", 100, "core"), ("P1", "F1", 200, "")],
     [("F1", "satellite", 100), ("F1", "core", 200)]),
])
def test_restore_partial_explicit_with_sheet_conflict_fails_closed(monkeypatch, backup, sheet_rows):
    """突變 C（拿掉「全部格子」判定）→ 兩組皆轉紅。"""
    from ui.helpers import cloud_io
    from ui.helpers.io.json_backup import restore_from_json_bytes
    ss: dict = {}
    assert restore_from_json_bytes(_backup_with_tiers(backup), ss)["ok"]
    assert [resolve_tier(f) for f in ss["portfolio_funds"]][1] is None
    ws = _FakeWS(_v2_tab_rows(sheet_rows))
    monkeypatch.setattr(cloud_io, "detect_sheet_schema_version", lambda c, s: "v2")
    import time as _time
    monkeypatch.setattr(_time, "sleep", lambda s: None)
    out = cloud_io.dump_all_to_sheet(_FakeClient(ws), "s", ss)
    assert ws.cleared is False and ws.updates == []
    assert "P1: ❌ 級別設定衝突：F1，未寫入此保單。" in out["warnings"][0]


# ══════════════════════════════════════════════════════════════════
# 2026-10-11 稽核必修 2：「全部寫入」的警告不得被緊接的 st.rerun() 清掉
# ══════════════════════════════════════════════════════════════════
_SAVE_PANEL_APP = """
import sys
sys.path.insert(0, {repo!r})
import streamlit as st
from ui.helpers import cloud_io

_MSG = "⚠️ 1 個保單分頁寫入失敗：P1: ❌ 級別設定衝突：F1，未寫入此保單。"
# AppTest 與 pytest 同一個 process：替身只在本輪 render 期間生效，finally 一律還原（不得洩漏到其他測試）
_orig_dump = cloud_io.dump_all_to_sheet
_fake_dump = lambda client, sid, ss: {{
    "ok": True, "written": 1, "skipped_no_pid": 0, "n_state": 0, "n_overview": 0,
    "warnings": [_MSG] if ss.get("_with_warning", True) else [], "error": None}}
ss = st.session_state
ss.setdefault("policy_sheet_id", "SID123")
ss.setdefault("gsheet_tokens", {{"x": 1}})
ss.setdefault("_last_loaded_sheet_id", "SID123")
ss.setdefault("_t3_cur_sheet_title", "帳本")
ss.setdefault("t3_io_panel", "save")
ss.setdefault("portfolio_funds", [{{"code": "F1", "policy_id": "P1", "name": "x"}}])
ss["_runs"] = ss.get("_runs", 0) + 1
_orig_warning = st.warning
def _rec(body, *a, **k):
    ss.setdefault("_warn_log", []).append((ss["_runs"], str(body)))
    return _orig_warning(body, *a, **k)
from ui.helpers.portfolio.policy_admin_section import render_policy_admin_section
class _C:
    def __getattr__(self, n):
        raise RuntimeError("no net")
st.warning = _rec
cloud_io.dump_all_to_sheet = _fake_dump
try:
    render_policy_admin_section(
        oauth_configured=True, resolve_oauth_cfg=lambda: None,
        get_oauth_client=lambda: _C(), gsa_secret=None, sheet_id_secret=None,
        get_login_state=lambda: {{}}, sheet_client=lambda: _C())
finally:
    st.warning = _orig_warning
    cloud_io.dump_all_to_sheet = _orig_dump
"""


def _save_panel_click(tmp_path, with_warning: bool):
    import pathlib as _pl
    from streamlit.testing.v1 import AppTest
    _app = tmp_path / "save_panel_app.py"
    _app.write_text(_SAVE_PANEL_APP.format(repo=str(_pl.Path(__file__).resolve().parents[1])),
                    encoding="utf-8")
    at = AppTest.from_file(str(_app), default_timeout=60)
    at.session_state["_with_warning"] = with_warning
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    at.button(key="t3_io_panel_save_run").click().run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_save_warning_survives_rerun(tmp_path):
    """按「📦 立即全部寫入」→ st.rerun() 之後的那一輪（最後一輪）仍以 st.warning 顯示衝突字句，
    顯示後即清除。突變 D（恢復無條件 rerun、不暫存）→ 本條轉紅（最後一輪沒有任何警告）。"""
    at = _save_panel_click(tmp_path, True)
    _runs = at.session_state["_runs"]
    assert _runs >= 3   # 初次 → 點擊 → rerun
    _last = [b for r, b in at.session_state["_warn_log"] if r == _runs]
    assert _last == ["⚠️ ⚠️ 1 個保單分頁寫入失敗：P1: ❌ 級別設定衝突：F1，未寫入此保單。"]
    assert "_t3_io_panel_save_warnings" not in at.session_state
    at.run()   # 再一輪：已清除，不重複顯示
    assert [b for r, b in at.session_state["_warn_log"]
            if r == at.session_state["_runs"]] == []


def test_save_without_warning_behaviour_unchanged(tmp_path):
    """無警告：仍 rerun（上次寫入更新），不暫存、不顯示警告。"""
    at = _save_panel_click(tmp_path, False)
    assert at.session_state["_runs"] >= 3
    assert "_warn_log" not in at.session_state
    assert "_t3_io_panel_save_warnings" not in at.session_state
