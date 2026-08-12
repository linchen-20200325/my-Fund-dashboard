"""test_fix_and_shrink_v2.py — v19.436 一鍵修正基金名稱 + 精簡 Sheet(10 欄)。

鎖住:
- `_row_needs_name_fix`:fund_name 空 / 被灌成 policy_id → 需重抓(純函式)
- `fix_and_shrink_v2_sheets`:逐張讀→修名(注入 fetcher)→重寫;計數正確、好名不重抓、
  修正的 df 真的被寫回。
"""
from __future__ import annotations

import pandas as pd

import ui.helpers.cloud_io as C
import repositories.policy_repository as PR


def test_row_needs_name_fix_pure():
    assert C._row_needs_name_fix("", "P1") is True             # 空 → 修
    assert C._row_needs_name_fix("   ", "P1") is True          # 全空白 → 修
    assert C._row_needs_name_fix("P1", "P1") is True           # 被灌成 policy_id → 修
    assert C._row_needs_name_fix("聯博-全球高收益債", "P1") is False   # 真名 → 不動
    assert C._row_needs_name_fix("31611267318", "31611267318") is True  # 截圖實例 → 修


def test_fix_and_shrink_fixes_corrupt_names_and_rewrites(monkeypatch):
    # 兩張保單:P_A 名稱被灌成保單號(要修)、P_B 名稱正常(不動)
    _sheets = {
        "P_A": pd.DataFrame([{
            "policy_id": "P_A", "fund_code": "ACTI71", "fund_name": "P_A",
            "currency": "", "tier": "", "invest_twd": 100, "div_cash_pct": 100,
            "units": 0, "avg_nav": 0, "avg_fx": 0,
        }]),
        "P_B": pd.DataFrame([{
            "policy_id": "P_B", "fund_code": "TLZF9", "fund_name": "聯博全球",
            "currency": "USD", "tier": "core", "invest_twd": 200, "div_cash_pct": 100,
            "units": 0, "avg_nav": 0, "avg_fx": 0,
        }]),
    }
    _written: dict = {}

    monkeypatch.setattr(PR, "list_policy_worksheets", lambda c, s: ["P_A", "P_B"])
    monkeypatch.setattr(PR, "load_policy_v2", lambda c, s, pid: _sheets[pid].copy())

    def _fake_write(c, s, pid, df):
        _written[pid] = df.copy()
        return len(df)
    monkeypatch.setattr(C, "write_policy_v2", _fake_write)

    # 注入 fetcher:代號 → (名稱, 幣別, 級別)
    _fetch_calls = []

    def _fetcher(code):
        _fetch_calls.append(code)
        return ("聯博-全球高收益債券", "USD", "satellite")

    res = C.fix_and_shrink_v2_sheets(object(), "sid", info_fetcher=_fetcher,
                                     progress_cb=None, with_backup=False)

    assert res["policies"] == 2
    assert res["funds"] == 2
    assert res["names_fixed"] == 1               # 只有 P_A 需要修
    assert res["errors"] == []
    assert _fetch_calls == ["ACTI71"]            # P_B 名字正常 → 不呼叫 fetcher

    # P_A 被修:名稱換真名、空的 currency/tier 補上
    _pa = _written["P_A"].iloc[0]
    assert _pa["fund_name"] == "聯博-全球高收益債券"
    assert _pa["currency"] == "USD"
    assert _pa["tier"] == "satellite"
    # P_B 原樣重寫(名字不動),但仍被寫回(達到 10 欄物理精簡)
    assert _written["P_B"].iloc[0]["fund_name"] == "聯博全球"


def test_fix_and_shrink_survives_per_policy_error(monkeypatch):
    """單張讀取失敗不中斷整批,收集錯誤。"""
    monkeypatch.setattr(PR, "list_policy_worksheets", lambda c, s: ["BAD", "OK"])

    def _load(c, s, pid):
        if pid == "BAD":
            raise RuntimeError("boom")
        return pd.DataFrame([{
            "policy_id": "OK", "fund_code": "X", "fund_name": "好名",
            "currency": "USD", "tier": "core", "invest_twd": 1, "div_cash_pct": 100,
            "units": 0, "avg_nav": 0, "avg_fx": 0,
        }])
    monkeypatch.setattr(PR, "load_policy_v2", _load)
    monkeypatch.setattr(C, "write_policy_v2", lambda c, s, pid, df: len(df))

    res = C.fix_and_shrink_v2_sheets(object(), "sid",
                                     info_fetcher=lambda code: ("", "", ""),
                                     with_backup=False)
    assert res["policies"] == 1                  # 只有 OK 成功計入
    assert any("BAD" in e for e in res["errors"])


def test_fix_and_shrink_backs_up_before_touching(monkeypatch):
    """§1:with_backup=True → 先 copy_sheet_as_backup,backup_url 回填。"""
    _order = []
    monkeypatch.setattr(PR, "copy_sheet_as_backup",
                        lambda c, s: _order.append("backup") or ("BAK", "http://bak"))
    monkeypatch.setattr(PR, "list_policy_worksheets",
                        lambda c, s: _order.append("list") or [])
    res = C.fix_and_shrink_v2_sheets(object(), "sid",
                                     info_fetcher=lambda code: ("", "", ""))
    assert res["backup_url"] == "http://bak"
    assert _order == ["backup", "list"]          # 備份必在列分頁之前


def test_fix_and_shrink_aborts_when_backup_fails(monkeypatch):
    """§1:備份失敗 → 中止,不動原本(不呼叫 list/load/write)。"""
    _touched = []
    monkeypatch.setattr(PR, "copy_sheet_as_backup",
                        lambda c, s: (_ for _ in ()).throw(RuntimeError("drive down")))
    monkeypatch.setattr(PR, "list_policy_worksheets",
                        lambda c, s: _touched.append("list") or [])
    monkeypatch.setattr(C, "write_policy_v2",
                        lambda c, s, pid, df: _touched.append("write"))
    res = C.fix_and_shrink_v2_sheets(object(), "sid",
                                     info_fetcher=lambda code: ("", "", ""))
    assert res["policies"] == 0
    assert _touched == []                         # 未動原本
    assert any("備份失敗" in e for e in res["errors"])
