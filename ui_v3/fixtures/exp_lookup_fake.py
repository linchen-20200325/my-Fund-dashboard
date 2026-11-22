# -*- coding: utf-8 -*-
"""【FAKE】🔍 找基金的離線假取數函式（Gate-M 方案 2a；總管裁示 #1296 comment 7073385776）。

- 全部**虛構**：代碼一律以 `FAKE-` 起頭、名稱以 `FAKE` 起頭、日期是明顯的示意值，不代表任何真實基金或來源。
- `make_loader()` 回傳的是**注入給 adapter 的假取數函式**：形狀對照 L2 `build_profiles`（只含 adapter 會讀的鍵），
  不 import 真實 L1／L2、不連線、不讀環境變數或憑證、不寫任何東西；ViewModel 一律經 `ui_v3.adapters.fund_lookup.lookup_fund` 產生。
- 未列於 `DEMO_CODES` 的任何合法格式代碼 → 一律「找不到對應頁面」（頁面無法確認），**不推論基金存在與否**。
- 唯一允許的使用者：`ui_v3/app_preview.py::_render_exp`（函式內 import；其他檔案、其他函式、模組層 import 都由守衛攔截）。
"""
from __future__ import annotations

from typing import Callable, Dict, List

from ui_v3.viewmodels.fund_lookup import LookupSourceError

FAKE_FIXTURE = True
FAKE_NAME = "FAKE 範例基金甲"
FAKE_INCEPTION = "2000-01-02"     # FAKE 日期（不對應任何真實基金）

#: 代碼 → 說明（僅供畫面提示與測試對照；預期狀態由測試自己持有，不放在這裡）
DEMO_CODES: Dict[str, str] = {
    "FAKE-OK01": "有結果：配息型、成立日期有值",
    "FAKE-OK02": "有結果：累積型、成立日期缺值",
    "FAKE-OK03": "有結果：配息方式與成立日期皆缺值",
    "FAKE-FAIL1": "來源回報取數失敗",
    "FAKE-COOL1": "來源冷卻中",
    "FAKE-IOERR": "取數連線例外",
    "FAKE-PAGE1": "頁面格式無法辨識",
    "FAKE-PAGE2": "找不到對應頁面",
    "FAKE-PAGE3": "來源沒有列出這一檔",
    "FAKE-NAME1": "頁面可辨識但基金名稱無法確認",
    "FAKE-REJ1": "取數鍵被 L2 拒絕",
}

_FIELDS = ("fund_name", "dividend_policy", "inception_on", "mgmt_fee_rate_pct")


def _cell(status: str, value=None) -> dict:
    return {"status": status, "value": value}


def _source(status: str, *, cooling: bool = False) -> dict:
    return {"MoneyDJ": {"status": status, "cooling": cooling}}


def _result(query: str, *, policy=("ok", "dist"), inception=("ok", FAKE_INCEPTION), name=("ok", FAKE_NAME)) -> dict:
    cells = {"fund_name": _cell(*name), "dividend_policy": _cell(*policy), "inception_on": _cell(*inception),
             "mgmt_fee_rate_pct": _cell("not_ready")}
    return {"cells": {query: cells}, "source_status": {query: _source("ok")}}


def _no_cells(query: str, source: dict) -> dict:
    return {"cells": {query: {f: _cell("not_ready") for f in _FIELDS}}, "source_status": {query: source}}


def _shape(query: str, code: str) -> dict:
    if code == "FAKE-OK01":
        return _result(query)
    if code == "FAKE-OK02":
        return _result(query, policy=("ok", "accum"), inception=("not_ready", None))
    if code == "FAKE-OK03":
        return _result(query, policy=("not_ready", None), inception=("not_ready", None))
    if code == "FAKE-NAME1":
        return _result(query, name=("not_ready", None))
    if code == "FAKE-FAIL1":
        return _no_cells(query, _source("failed"))
    if code == "FAKE-COOL1":
        return _no_cells(query, _source("failed", cooling=True))
    if code == "FAKE-PAGE1":
        return _no_cells(query, _source("unrecognized_page"))
    if code == "FAKE-PAGE3":
        return _no_cells(query, _source("not_listed"))
    if code == "FAKE-REJ1":
        return {"cells": {query: {f: _cell("not_ready") for f in _FIELDS}}, "source_status": {query: {}}}
    return _no_cells(query, _source("not_found"))      # FAKE-PAGE2 與所有未列出的合法格式代碼


class FakeLoader:
    """假取數函式：`loader(query_text) -> L2 形狀 dict`。記錄呼叫參數（供測試驗證攔截案例不呼叫 loader）。"""

    def __init__(self) -> None:
        self.calls: List[str] = []

    def __call__(self, query_text: str) -> dict:
        self.calls.append(query_text)
        code = query_text.upper()
        if code == "FAKE-IOERR":
            raise LookupSourceError("fake io error")
        return _shape(query_text, code)


def make_loader() -> Callable[[str], dict]:
    return FakeLoader()


def demo_codes_hint() -> str:
    """畫面提示用：FAKE 示範代碼清單（純字串，全部 FAKE-）。"""
    return "、".join(DEMO_CODES)
