# -*- coding: utf-8 -*-
"""路徑 B（單檔基本資料查詢）離線測試共用輔助（`DEC-2026-11-18-02`，待核）：假 L2 回傳字典、假 loader、網路守衛、CI 嚴格度。

⚠️ 全部是**純資料／假函式**：不 import 真實 L1／L2（services、repositories、infra）、不連網、不讀 secrets、不寫持久層。
假 L2 回傳字典的形狀對照 `services/v2_tables/exp_profile.py::build_profiles` 的 docstring 與原始碼（形狀字面由 adapter 測試以 AST 讀碼鎖死），
範例代碼取自 `tests/fixtures/moneydj_basic/manifest.json` 的真實代碼樣本。
本檔被同目錄測試以裸名 import（tests/ 沒有 `__init__.py`），故檔名取唯一的 `fund_lookup_support`。
負控字串一律在測試中現編（隨機），不寫死在任何檔案裡。
"""
from __future__ import annotations

import os
import secrets
import socket
import sys
from typing import Callable, List

import pytest

SAMPLE_CODE = "ACTI71"
SAMPLE_NAME = "範例全球股票基金"
SAMPLE_INCEPTION = "2010-05-03"


# ───────────────────────── CI 嚴格度 ─────────────────────────

def ci_is_true() -> bool:
    """環境變數 CI 非空且不是 0／false（大小寫不分）→ 視為 CI。"""
    return os.environ.get("CI", "").strip().lower() not in ("", "0", "false")


def unavailable(reason: str) -> None:
    """依賴載不起來：CI 內 **fail**（不得靜默跳過）；非 CI 本機才 skip 並印出明確原因。"""
    if ci_is_true():
        pytest.fail("[CI] " + reason + "（CI 環境必須有完整依賴；此處不得跳過）")
    print("[SKIP-LOCAL] " + reason, file=sys.stderr)
    pytest.skip(reason)


# ───────────────────────── 現編的隨機毒字串（每次執行不同，不寫死） ─────────────────────────

def poisons() -> List[str]:
    token = secrets.token_hex(6)
    return [f"poison-{token}", f"https://host-{token}.example/path?k={token}", f"KeyError: 'key_{token}'", f"Traceback {token} api_key={token}"]


# ───────────────────────── 假 L2 回傳字典（形狀對照 build_profiles；不 import 它） ─────────────────────────

def cell(status: str = "ok", value=None, *, reason=None, raw=None) -> dict:
    """L2 `_cell` 的形狀（adapter 只該讀 status／value，其餘鍵故意可塞毒字串）。"""
    return {"value": value, "status": status, "sources": ("MoneyDJ",), "failed_sources": (), "raw": dict(raw or {}),
            "fetched_at": {"MoneyDJ": "2026-11-18T01:02:03+00:00"}, "observed_at": {}, "reason": reason}


def source_entry(status: str = "ok", *, cooling: bool = False, error=None) -> dict:
    return {"status": status, "error": error, "cooling": cooling, "cooling_remaining_sec": 120 if cooling else None}


def good_cells() -> dict:
    return {"fund_name": cell("ok", SAMPLE_NAME), "ccy": cell("ok", "USD"), "inception_on": cell("ok", SAMPLE_INCEPTION),
            "dividend_policy": cell("ok", "dist"), "mgmt_fee_rate_pct": cell("not_ready", None, reason="no source")}


def profile(code: str = SAMPLE_CODE, *, cells: dict = None, moneydj: str = "ok", cooling: bool = False, tdcc: str = "ok",
            fundclear: str = "ok", table_wide_failed: bool = False, **cell_over) -> dict:
    """`build_profiles` 回傳形狀。`cell_over` 以欄名覆蓋單一格（例 `fund_name=cell('not_ready')`）。"""
    cmap = dict(good_cells() if cells is None else cells)
    cmap.update(cell_over)
    return {
        "rows": [{"fund_code": code, "fund_name": SAMPLE_NAME, "ccy": "USD", "fetched_at": "2026-11-18T01:02:03+00:00"}],
        "cells": {code: cmap},
        "declared": {code: ("USD", "meta:MoneyDJ+TDCC+FundClear")},
        "source_status": {code: {"MoneyDJ": source_entry(moneydj, cooling=cooling), "TDCC": source_entry(tdcc),
                                 "FundClear": source_entry(fundclear)}},
        "table_wide_failed": table_wide_failed,
    }


def failed_profile(code: str = SAMPLE_CODE, *, cooling: bool = False) -> dict:
    """MoneyDJ 取不到：L2 的三個 MoneyDJ 格是 fetch_failed（adapter 不得去讀它們）。"""
    cells = {"fund_name": cell("fetch_failed", None, reason="MoneyDJ 取數失敗"), "ccy": cell("fetch_failed"),
             "inception_on": cell("fetch_failed"), "dividend_policy": cell("fetch_failed"), "mgmt_fee_rate_pct": cell("not_ready")}
    return profile(code, cells=cells, moneydj="failed", cooling=cooling)


def unmatched_profile(source_status: str, code: str = SAMPLE_CODE) -> dict:
    cells = {f: cell("not_ready", None, reason="頁面無法確認") for f in ("fund_name", "ccy", "inception_on", "dividend_policy", "mgmt_fee_rate_pct")}
    return profile(code, cells=cells, moneydj=source_status)


def rejected_profile(code: str = SAMPLE_CODE) -> dict:
    """L2 拒絕該鍵：source_status[code] 為 {}，各格 not_ready。"""
    cells = {f: cell("not_ready", None, reason="代碼無法對照") for f in ("fund_name", "ccy", "inception_on", "dividend_policy", "mgmt_fee_rate_pct")}
    result = profile(code, cells=cells)
    result["source_status"] = {code: {}}
    return result


# ───────────────────────── 假 loader ─────────────────────────

class CountingLoader:
    """記錄呼叫次數與參數；`result` 可為 dict（原樣回傳）、callable（以參數呼叫）或要拋的例外實例。"""

    def __init__(self, result=None):
        self.result = result
        self.calls: List[str] = []

    def __call__(self, query_text):
        self.calls.append(query_text)
        if isinstance(self.result, BaseException):
            raise self.result
        if callable(self.result):
            return self.result(query_text)
        return self.result


def sentinel_loader() -> Callable[[str], object]:
    """被呼叫即失敗的哨兵（攔截案例的 loader）。"""
    def loader(_query_text):
        raise AssertionError("loader must not be called for a blocked input")
    return loader


# ───────────────────────── 真實網路請求次數為 0：把所有入口換成會 raise 的守衛 ─────────────────────────

class NetworkAttempt(AssertionError):
    pass


def install_network_guard(monkeypatch, attempts: list) -> None:
    def blocker(name):
        def _blocked(*args, **kwargs):
            attempts.append(name)
            raise NetworkAttempt(f"network access attempted via {name}")
        return _blocked

    monkeypatch.setattr(socket.socket, "connect", blocker("socket.connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", blocker("socket.connect_ex"))
    monkeypatch.setattr(socket, "create_connection", blocker("socket.create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", blocker("socket.getaddrinfo"))
    import urllib.request
    import http.client
    monkeypatch.setattr(urllib.request, "urlopen", blocker("urllib.request.urlopen"))
    monkeypatch.setattr(http.client.HTTPConnection, "connect", blocker("http.client.HTTPConnection.connect"))
    monkeypatch.setattr(http.client.HTTPSConnection, "connect", blocker("http.client.HTTPSConnection.connect"))
    try:  # requests 不是本批依賴；有裝就一併守住，沒裝就沒有可守的入口
        import requests.adapters
        import requests.sessions
    except ImportError:
        return
    monkeypatch.setattr(requests.sessions.Session, "request", blocker("requests.Session.request"))
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", blocker("requests.HTTPAdapter.send"))


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    """所有 fund_lookup 測試都在此守衛下執行；任何網路入口被碰到 → 測試失敗（即使被測碼吞掉例外，結尾也會斷言嘗試次數為 0）。"""
    attempts: list = []
    install_network_guard(monkeypatch, attempts)
    yield attempts
    assert attempts == [], f"real network access attempted: {attempts}"
