# -*- coding: utf-8 -*-
"""單檔基金查詢呈現元件｜隔離式 FAKE Preview 的演示輸入（全部 FAKE；不用真實基金代碼或身分，不宣稱已確認任何來源的基金身分）。

- `FakeLoader` 是**注入給 adapter 的假取數函式**：回傳形狀對照 L2 `build_profiles`（只含 adapter 會讀的鍵），不 import 真實 L1／L2、不連網、不讀憑證。
  ViewModel 一律由 `ui_v3.adapters.fund_lookup.lookup_fund(FakeLoader(), 輸入)` 產生，**不自行偽造繞過 adapter**。
- 唯一例外：`CONFLICT` 欄位狀態在現行真實 L2 對這四欄**不可達**（L2 只對幣別用 inconsistent），但 adapter 對 inconsistent 格會映為 CONFLICT；
  為了演示呈現語意，`conflict_view()` **直接建構 ViewModel**（harness 明示這是直接建構、非 adapter 結果）。
- 未列於下表的任何合法代碼格式 → 一律 `not_found`（頁面無法確認），**不推論基金存在與否**。
"""
from __future__ import annotations

from typing import Callable, Dict, Tuple

from ui_v3.viewmodels.fund_lookup import (
    FieldStatus,
    FieldView,
    FundLookupView,
    LookupSourceError,
    LookupState,
    ProfileFields,
)

FAKE_NAME = "FAKE 範例基金甲"
FAKE_INCEPTION = "2000-01-02"     # FAKE 日期（不對應任何真實基金）
CONFLICT_CODE = "FAKE-CNFL1"

# 代碼 → (說明, 預期狀態/原因，僅供 harness 提示與測試對照)
FAKE_CODES: Dict[str, Tuple[str, str]] = {
    "FAKE-OK01": ("有結果：配息型、成立日期有值", "RESULT"),
    "FAKE-OK02": ("有結果：累積型、成立日期缺值", "RESULT"),
    "FAKE-OK03": ("有結果：配息方式與成立日期皆缺值", "RESULT"),
    "FAKE-FAIL1": ("來源回報取數失敗", "SOURCE_FAILED/source_failed"),
    "FAKE-COOL1": ("來源冷卻中", "SOURCE_FAILED/source_cooling"),
    "FAKE-IOERR": ("取數連線例外（LookupSourceError）", "SOURCE_FAILED/loader_io_error"),
    "FAKE-PAGE1": ("頁面格式無法辨識", "PAGE_UNMATCHED/unrecognized_page"),
    "FAKE-PAGE2": ("找不到對應頁面", "PAGE_UNMATCHED/no_page"),
    "FAKE-PAGE3": ("來源沒有列出這一檔", "PAGE_UNMATCHED/source_not_listed"),
    "FAKE-NAME1": ("頁面可辨識但基金名稱無法確認", "PAGE_UNMATCHED/name_unconfirmed"),
    "FAKE-REJ1": ("取數鍵被 L2 拒絕", "BLOCKED/key_rejected"),
}
HARNESS_CODES_HINT = "FAKE 示範代碼：" + "、".join(FAKE_CODES) + "；其他合法格式的代碼＝找不到對應頁面；ISIN 形、網址形、空白等會在入口被攔截"


def _cell(status: str, value=None) -> dict:
    return {"status": status, "value": value}


def _source(status: str, *, cooling: bool = False) -> dict:
    return {"MoneyDJ": {"status": status, "cooling": cooling}}


_FIELDS = ("fund_name", "dividend_policy", "inception_on", "mgmt_fee_rate_pct")


def _result(query: str, *, policy=("ok", "dist"), inception=("ok", FAKE_INCEPTION), name=("ok", FAKE_NAME)) -> dict:
    cells = {"fund_name": _cell(*name), "dividend_policy": _cell(*policy), "inception_on": _cell(*inception),
             "mgmt_fee_rate_pct": _cell("not_ready")}
    return {"cells": {query: cells}, "source_status": {query: _source("ok")}}


def _no_cells(query: str, source: dict) -> dict:
    return {"cells": {query: {f: _cell("not_ready") for f in _FIELDS}}, "source_status": {query: source}}


def _shape(query: str, code: str):
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
    """注入給 adapter 的假取數函式：`loader(query_text) -> L2 形狀 dict`。記錄呼叫次數與參數（供測試驗證攔截案例不呼叫 loader）。"""

    def __init__(self) -> None:
        self.calls: list = []

    def __call__(self, query_text: str) -> dict:
        self.calls.append(query_text)
        code = query_text.upper()
        if code == "FAKE-IOERR":
            raise LookupSourceError("fake io error")
        return _shape(query_text, code)


def make_loader() -> Callable[[str], dict]:
    return FakeLoader()


def conflict_view() -> FundLookupView:
    """**直接建構**的 ViewModel：配息方式與成立日期為 CONFLICT（現行真實 L2 對這四欄不可達；只演示呈現語意，不是 adapter 的輸出）。"""
    fields = ProfileFields(
        fund_name=FieldView(FieldStatus.VALUE, FAKE_NAME),
        dividend_policy=FieldView(FieldStatus.CONFLICT),
        inception_on=FieldView(FieldStatus.CONFLICT),
        mgmt_fee_rate_pct=FieldView(FieldStatus.MISSING),
    )
    return FundLookupView(LookupState.RESULT, CONFLICT_CODE, None, fields)
