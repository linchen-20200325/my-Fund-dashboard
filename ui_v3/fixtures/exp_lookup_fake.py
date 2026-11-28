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
    # ── NAV／輔助判定 sibling（NAV-ADMISSION-CASES v1.0.1-draft 的合成案；A-EXP-NAV-SIBLING-FAKE-1）──
    "FAKE-ZZC1": "ZZ-C1 日期衝突：淨值扣下、兩判定無法判定",
    "FAKE-ZZC1B": "ZZ-C1b 衝突＋權利未核證",
    "FAKE-ZZ10A": "ZZ-1-0a 日期已修但級別未核證：仍扣下",
    "FAKE-ZZ10B": "ZZ-1-0b 級別已核證：顯示淨值、判定通過",
    "FAKE-ZZC2": "ZZ-C2 月配但配息缺失：兩判定無法判定",
    "FAKE-ZZC2B": "ZZ-C2b 成立 2.0 年：❌ 有證據的未通過",
    "FAKE-ZZC3A": "ZZ-C3a 已證實無配息：❌＋無配息（事實）",
    "FAKE-ZZC3B": "ZZ-C3b 序列不足：3-3-3 無法判定、無配息事實仍成立",
    "FAKE-ZZC3D": "ZZ-C3d 無配息證據只有一半：退回未取得",
    "FAKE-ZZR4": "ZZ-R4 只有 AI 使用權未核證：主畫面不變",
    "FAKE-ZZR3": "ZZ-R3 衍生計算權利未核證：淨值照常、判定無法判定",
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


#: ZZ 案例的基本資料（名稱／配息方式／成立日；全部 FAKE）。成立 2.0 年的 2b 用 2024-11-24。
_ZZ_PROFILE = {
    "FAKE-ZZC1": ("dist", "2020-02-03"), "FAKE-ZZC1B": ("dist", "2020-02-03"), "FAKE-ZZ10A": ("dist", "2020-02-03"),
    "FAKE-ZZ10B": ("dist", "2020-02-03"), "FAKE-ZZC2": ("dist", "2020-02-03"), "FAKE-ZZC2B": ("dist", "2024-11-24"),
    "FAKE-ZZC3A": ("accum", "2020-02-03"), "FAKE-ZZC3B": ("accum", "2020-02-03"), "FAKE-ZZC3D": ("accum", "2020-02-03"),
    "FAKE-ZZR4": ("dist", "2020-02-03"), "FAKE-ZZR3": ("dist", "2020-02-03"),
}


def _shape(query: str, code: str) -> dict:
    if code in _ZZ_PROFILE:
        policy, inception = _ZZ_PROFILE[code]
        return _result(query, policy=("ok", policy), inception=("ok", inception), name=("ok", "FAKE 合成基金"))
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


# ───────────────────────── NAV／輔助判定 sibling 的假資料（來源層：判定與格式化在這裡完成；renderer 不算）─────────────────────────

#: 已核證的原始供應者擷取時間（含時分；與快取更新時間不同日，用來證明原值被保留、沒被截成日期或以快取時間代填）。
_SUPPLIER_STAMP = "2026-11-20T09:30Z"
_SRC = "GitHubActions:cache/nav/{code}.json（合成）"


def _metric(kind, reason=None, evidence=()):
    return {"kind": kind, "reason_code": reason, "evidence": list(evidence)}


def _nav_verified(code: str, *, supplier=None) -> dict:
    return {"display": "verified", "nav_value": "12.3456", "ccy": "美元", "nav_date": "2026-11-20", "source_label": _SRC.format(code=code),
            "cache_updated_at": "2026-11-21", "supplier_fetched_at": supplier, "ccy_declared_at": "2026-11-20", "ccy_declared": "美元",
            "time_sources_differ": True}


def _nav_withheld(code: str, display: str, reasons, conflicts=()) -> dict:
    return {"display": display, "reason_codes": list(reasons), "source_label": _SRC.format(code=code), "cache_updated_at": "2026-07-22",
            "supplier_fetched_at": None, "ccy_declared_at": "2026-10-14", "ccy_declared": "美元", "time_sources_differ": True,
            "conflicts": list(conflicts)}


def _blocked_judgement(reason: str) -> dict:
    return {"three_three_three": _metric("undetermined", reason), "eating_principal": _metric("undetermined", reason), "dividend_status": "present"}


_CONFLICT = {"code": "nav_before_inception", "a_date": "2011-11-18", "b_date": "2020-02-03"}


def _nav_case(code: str):
    """回傳 `{"nav", "judgement", "ai_usable"}`；不是 NAV 案例 → None。"""
    if code == "FAKE-ZZC1":
        return {"nav": _nav_withheld(code, "withheld_conflict", ["input_conflict"], [_CONFLICT]), "judgement": _blocked_judgement("input_conflict"), "ai_usable": False}
    if code == "FAKE-ZZC1B":
        return {"nav": _nav_withheld(code, "withheld_conflict", ["input_conflict", "rights_unverified"], [_CONFLICT]),
                "judgement": _blocked_judgement("input_conflict"), "ai_usable": False}
    if code == "FAKE-ZZ10A":
        return {"nav": _nav_withheld(code, "withheld_not_admitted", ["identity_unverified", "class_unverified"]),
                "judgement": _blocked_judgement("identity_unverified"), "ai_usable": False}
    if code in ("FAKE-ZZ10B", "FAKE-ZZR4"):
        judgement = {"three_three_three": _metric("pass_evidenced", None, [("成立年數", "6.8 年"), ("3 年平均年化", "9.00%")]),
                     "eating_principal": _metric("pass_evidenced", None, [("1 年含息報酬", "5.00%"), ("年化配息率", "4.20%")]),
                     "dividend_status": "present"}
        return {"nav": _nav_verified(code), "judgement": judgement, "ai_usable": code == "FAKE-ZZ10B"}
    if code == "FAKE-ZZR3":
        return {"nav": _nav_verified(code), "judgement": _blocked_judgement("rights_unverified"), "ai_usable": False}
    if code == "FAKE-ZZC2":
        judgement = {"three_three_three": _metric("undetermined", "dividend_not_obtained", [("成立年數", "6.8 年")]),
                     "eating_principal": _metric("undetermined", "dividend_not_obtained"), "dividend_status": "missing"}
        return {"nav": _nav_verified(code), "judgement": judgement, "ai_usable": True}
    if code == "FAKE-ZZC2B":
        judgement = {"three_three_three": _metric("fail_evidenced", None, [("成立年數", "2.0 年"), ("門檻", "3 年")]),
                     "eating_principal": _metric("undetermined", "dividend_not_obtained"), "dividend_status": "missing"}
        return {"nav": _nav_verified(code), "judgement": judgement, "ai_usable": True}
    if code == "FAKE-ZZC3A":
        judgement = {"three_three_three": _metric("fail_evidenced", None, [("3 年平均年化", "6.00%"), ("門檻", "7%")]),
                     "eating_principal": _metric("fact_no_dividend"), "dividend_status": "confirmed_none"}
        return {"nav": _nav_verified(code, supplier=_SUPPLIER_STAMP), "judgement": judgement, "ai_usable": True}
    if code == "FAKE-ZZC3B":
        judgement = {"three_three_three": _metric("undetermined", "history_short", [("序列", "300 點，不足 756 點")]),
                     "eating_principal": _metric("fact_no_dividend"), "dividend_status": "confirmed_none"}
        return {"nav": _nav_verified(code, supplier=_SUPPLIER_STAMP), "judgement": judgement, "ai_usable": True}
    if code == "FAKE-ZZC3D":
        judgement = {"three_three_three": _metric("undetermined", "dividend_not_obtained"),
                     "eating_principal": _metric("undetermined", "dividend_not_obtained"), "dividend_status": "missing"}
        return {"nav": _nav_verified(code, supplier=_SUPPLIER_STAMP), "judgement": judgement, "ai_usable": True}
    return None


class FakeNavLoader:
    """假 NAV loader：`loader(query_text) -> dict | None`。只認 `FAKE-ZZ*`；其他代碼 → None（結果卡維持原樣）。記錄呼叫參數。"""

    def __init__(self) -> None:
        self.calls: List[str] = []

    def __call__(self, query_text: str):
        self.calls.append(query_text)
        return _nav_case(query_text.upper())


def make_nav_loader() -> Callable[[str], object]:
    return FakeNavLoader()
