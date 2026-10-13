# -*- coding: utf-8 -*-
"""A 鏈補收失敗原文（總管 2026-10-13 技術裁定第 3、4 條）：新增鍵以外，A 鏈行為零變化（fast lane；不打網路）。

證明方式：`tests/fixtures/a_chain_golden_before.json` 是**改動前**的程式碼對 `tests/_a_chain_stub.py::scenarios()`
七組 stub 輸入跑出來的結果（`auto_fetch_moneydj` 與 L1 `fetch_fund_from_moneydj_url` 兩條入口的回傳值，
加上各自依序呼叫了哪些來源）。改動後再跑一次，拿掉新增鍵後必須逐欄相同：
- 回傳 dict 的新增鍵：`nav_source_failures`（L1）、`nav_page_type_attempts`（`auto_fetch_moneydj`）；
- 淨值序列 attrs 的新增鍵：`nav_history_dates`／`nav_history_recorded_at`／`nav_history_source`／
  `nav_history_dates_error`（`_merge_nav_history_series`）。
每次跑都會變的兩個時間欄（`_moneydj_fetched_at`、`fetched_at`）兩邊都不比。

⚠️ 黃金檔的產生方式：改動前在乾淨的 `origin/main`（`1586a45`）＋本檔的 stub 工具上跑一次並存檔；
之後**不得**以改動後的程式重產（那會把要證明的東西變成循環論證）。
"""

from __future__ import annotations

import contextlib
import io
import json
import pathlib

import pytest

import _a_chain_stub as H

_GOLDEN = pathlib.Path(__file__).resolve().parent / "fixtures" / "a_chain_golden_before.json"
NEW_RESULT_KEYS = frozenset({"nav_source_failures", "nav_page_type_attempts"})
NEW_SERIES_ATTRS = frozenset({"nav_history_dates", "nav_history_recorded_at", "nav_history_source",
                              "nav_history_dates_error"})


def _run(monkeypatch, code, scenario):
    from repositories.fund.fund_orchestration import fetch_fund_from_moneydj_url
    from services.moneydj_fetcher import auto_fetch_moneydj

    calls = H.install(monkeypatch, scenario)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        res, page_type = auto_fetch_moneydj(code, return_page_type=True)
    auto_calls = list(calls)
    calls.clear()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        raw = fetch_fund_from_moneydj_url(code)
    return res, page_type, raw, auto_calls, list(calls)


_SCENARIOS = H.scenarios()


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_除新增鍵外_改動前後逐欄相同_呼叫順序相同(monkeypatch, name):
    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))[name]
    code, scenario = H.scenarios()[name]
    res, page_type, raw, auto_calls, l1_calls = _run(monkeypatch, code, scenario)
    drop = H.VOLATILE_TOP_KEYS | NEW_RESULT_KEYS | NEW_SERIES_ATTRS
    assert page_type == golden["page_type"]
    assert [list(c) for c in auto_calls] == golden["auto_calls"]
    assert [list(c) for c in l1_calls] == golden["l1_calls"]
    assert H.normalize(res, drop=drop) == golden["auto"]
    assert H.normalize(raw, drop=drop) == golden["l1"]


def test_黃金檔七個情境都在_防空掃():
    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    assert set(golden) == set(_SCENARIOS) and len(golden) == 7


# ═══════════════════════ 新增鍵的內容 ═══════════════════════

def test_全來源失敗_逐來源原文依嘗試順序記下_含fetch_nav自己的逐網址原文(monkeypatch):
    code, scenario = H.scenarios()["S3_all_fail"]
    res, page_type, raw, _a, _l = _run(monkeypatch, code, scenario)
    attempts = res["nav_page_type_attempts"]
    assert [a["page_type"] for a in attempts] == ["yp010000", "yp010001"]   # 兩個頁型都留
    for attempt in attempts:
        sources = [f["source"] for f in attempt["nav_source_failures"]]
        assert sources[:3] == ["FundClear", "cnyes", "tcb_moneydj"]          # 瀑布 2a→2b→2c 的順序
        assert "fetch_nav（legacy 最終備援）" in sources
        legacy = [f for f in attempt["nav_source_failures"] if f["source"].startswith("fetch_nav")][0]
        assert "kind=blocked" in legacy["error"] and "回傳 0 筆" in legacy["error"]
    # 多來源主路線那幾筆帶頁型；legacy 段（不分頁型）的那幾筆不帶
    assert all("page_type" in f for f in raw["nav_source_failures"] if not f["source"].startswith("fetch_nav"))
    assert any(f["source"].startswith("fetch_nav") and "page_type" not in f for f in raw["nav_source_failures"])


def test_來源成功_仍記下被略過的來源_但不影響採用結果(monkeypatch):
    code, scenario = H.scenarios()["S2_shortwindow_rescue"]
    res, _pt, _raw, _a, _l = _run(monkeypatch, code, scenario)
    fails = res["nav_source_failures"]
    assert fails[0] == {"source": "FundClear", "page_type": "yp010000",
                        "error": "回傳 8 筆，未達本步採用門檻 20 筆"}
    assert any("近30日短窗" in f["error"] for f in fails)
    assert res["data_source"] == "tcb_moneydj"   # 採用結果與黃金檔相同（上一條已逐欄比過）


def test_累積表併入點_記下日期與各自的recorded_at_缺的留空不補(monkeypatch):
    code, scenario = H.scenarios()["S1_complete_fundclear"]
    res, _pt, _raw, _a, _l = _run(monkeypatch, code, scenario)
    attrs = res["series"].attrs
    assert attrs["nav_history_dates"] == ["2025-11-03", "2025-11-04", "2025-11-05"]   # 重疊日 live 贏，不算
    assert attrs["nav_history_recorded_at"] == {"2025-11-03": "2025-11-03T09:00:00+00:00",
                                                "2025-11-04": "",
                                                "2025-11-05": "2025-11-05T09:00:00+00:00"}
    assert attrs["nav_history_source"] == "GoogleSheet:nav_history:ZZF001"


def test_shared_reads範圍內_整張表只讀一次_失敗照實重拋不重打(monkeypatch):
    import services.nav_history_gs as nh

    reads = []

    def fake_get_sheet(oauth_client=None):
        reads.append(1)

        class _WS:
            def get_all_values(self):
                return [["code", "date", "nav"], ["AAA", "2026-01-02", "10"], ["BBB", "2026-01-02", "20"]]

        class _SH:
            def worksheet(self, _name):
                return _WS()
        return _SH()

    monkeypatch.setattr(nh, "is_enabled", lambda: True)
    monkeypatch.setattr(nh, "_nav_backoff_ident", lambda oauth_client=None: ("", ""))
    monkeypatch.setattr(nh, "_get_sheet", fake_get_sheet)
    with nh.shared_reads():
        a = nh.load_points("AAA")
        b = nh.load_points("bbb ")
        c = nh.load_series("AAA")
    assert len(reads) == 1
    assert [p["nav"] for p in a] == [10.0] and [p["nav"] for p in b] == [20.0] and list(c) == [10.0]
    nh.load_points("AAA")          # 範圍外：照原路徑再讀
    assert len(reads) == 2

    def boom(oauth_client=None):
        reads.append(1)
        raise RuntimeError("APIError 429 quota")

    monkeypatch.setattr(nh, "_get_sheet", boom)
    reads.clear()
    with nh.shared_reads():
        for _ in range(3):
            with pytest.raises(nh.NavHistoryError, match="429"):
                nh.load_points("AAA")
    assert len(reads) == 1
