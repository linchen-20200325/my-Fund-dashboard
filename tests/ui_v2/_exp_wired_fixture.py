# -*- coding: utf-8 -*-
"""exp 頁 C2 接線的測試用 L2 形狀假資料（純 dict；不 import services、不打網路）。

`profiles()` 與 `exp_profile.build_profiles` 的回傳同形；`nav_out()` 與 `exp_nav.load_nav_dividend` 的回傳同形。
形狀是否真的一致，由 tests/ui_v2/test_exp_live_wiring_logic.py 的契約測試（走真的 L2、注入 L1 替身）另外釘住。

情境（`TODAY` ＝ 2026-10-14，台灣日期）：
- A01 全齊：淨值 4 天前、近 12 個月月配 12 筆 → 配息比算得出來。
- B02 淨值剛好 10 天前（不算舊）；配息已確認、一筆都沒有 → ⬜ 不適用：近 12 個月無配息。
- C03 淨值 11 天前（規則 11）→ 三格「⬜ 資料未備：最近一筆淨值 2026-10-03，已超過 10 日」。
- D04 幣別部分來源失敗（規則 12）：USD 由 MoneyDJ＋TDCC 一致，FundClear 失敗；成立日期 ⬜；配息未確認完整。
- E05 淨值資料幣別與基本資料幣別衝突（規則 14）。
- F06 計價幣別未確定 → 資料層隔離 `ccy_undetermined`。
- G07 MoneyDJ 取數失敗（名稱 ⛔）、淨值取數失敗（原因含秘密值，驗遮蔽）。
- H08 名稱與來源字串含 `<script>`、引號（驗 escape）。
"""

from __future__ import annotations

from datetime import date

TODAY = date(2026, 10, 14)
SECRET = "sk-test-0123456789abcdef"
META = "meta:MoneyDJ+TDCC"
XSS_NAME = '<script>alert("x")</script>基金'
XSS_SOURCE = 'Evil"Src<b>'

TEXT_MGMT_FEE = "來源未提供經理費率（不以「最高經理費」代替）"
TEXT_CCY_UNDETERMINED = "計價幣別未確定（declared_ccy_source 為 None），本檔不取數、不寫列"
CONFLICT_LINE = "淨值序列宣告的幣別與來源自報（MoneyDJ+TDCC）的幣別不同（即時序列:'EUR'；來源自報（MoneyDJ+TDCC） USD）；淨值 30 筆全部不寫"

CODES = ("A01", "B02", "C03", "D04", "E05", "F06", "G07", "H08")


def cell(value=None, status="ok", *, sources=("MoneyDJ",), failed=(), reason=None) -> dict:
    return {"value": value, "status": status, "sources": tuple(sources) if status == "ok" else (),
            "failed_sources": tuple(failed), "raw": {}, "fetched_at": {}, "observed_at": {}, "reason": reason}


def default_cells(code) -> dict:
    return {
        "fund_name": cell(f"測試基金 {code}"),
        "ccy": cell("USD", sources=("MoneyDJ", "TDCC")),
        "inception_on": cell("2010-01-15"),
        "dividend_policy": cell("dist"),
        "mgmt_fee_rate_pct": cell(None, "not_ready", reason=TEXT_MGMT_FEE),
    }


def profiles(overrides=None, codes=CODES) -> dict:
    """`exp_profile.build_profiles` 同形。`overrides`：`{代碼: {欄: Cell}}`。"""
    overrides = overrides if overrides is not None else default_overrides()
    out = {"rows": [], "cells": {}, "declared": {}, "source_status": {}, "table_wide_failed": False}
    for code in codes:
        cells = default_cells(code)
        cells.update(overrides.get(code, {}))
        row = {"fund_code": code}
        for column in ("fund_name", "ccy", "inception_on", "dividend_policy", "mgmt_fee_rate_pct"):
            row[column] = cells[column]["value"] if cells[column]["status"] == "ok" else None
        row["fetched_at"] = "2026-10-14T01:00:00+00:00"
        out["rows"].append(row)
        out["cells"][code] = cells
        ccy = cells["ccy"]
        out["declared"][code] = ((ccy["value"], "meta:" + "+".join(ccy["sources"])) if ccy["status"] == "ok"
                                 else (None, None))
        out["source_status"][code] = {}
    return out


def default_overrides() -> dict:
    return {
        "D04": {
            "ccy": cell("USD", sources=("MoneyDJ", "TDCC"), failed=("FundClear",),
                        reason="部分來源取數失敗，以其餘一致的來源為準（FundClear：HTTP 503；完整原文見 source_status）"),
            "inception_on": cell(None, "not_ready", reason="成立日期字樣無法辨識：民國99年"),
        },
        "F06": {"ccy": cell(None, "inconsistent", reason="各來源幣別不一致（MoneyDJ:'美元'→USD、TDCC:'歐元'→EUR、FundClear:沒提供）")},
        "G07": {"fund_name": cell(None, "fetch_failed", failed=("MoneyDJ",), reason="MoneyDJ 取數失敗"),
                "inception_on": cell(None, "fetch_failed", failed=("MoneyDJ",), reason="MoneyDJ 取數失敗"),
                "dividend_policy": cell(None, "fetch_failed", failed=("MoneyDJ",), reason="MoneyDJ 取數失敗"),
                "ccy": cell("USD", sources=("TDCC",), failed=("MoneyDJ",),
                            reason="部分來源取數失敗，以其餘一致的來源為準（MoneyDJ：timeout；完整原文見 source_status）")},
        "H08": {"fund_name": cell(XSS_NAME)},
    }


def _nav_row(code, day, value, ccy="USD"):
    return {"fund_code": code, "nav_date": day, "nav_orig_ccy": value, "ccy": ccy, "source_tier": "淨值",
            "is_estimated": False, "fetched_at": "2026-10-14T01:00:00Z"}


def _div_row(code, day, amount, ccy="USD"):
    return {"fund_code": code, "ex_date": day, "pay_date": None, "div_per_unit_orig_ccy": amount, "ccy": ccy,
            "div_kind": "unknown", "fetched_at": "2026-10-14T01:00:00Z"}


def _prov(source="FundClear:GetFundNAV"):
    return {"source": source, "fetched_at": "2026-10-14T01:00:00Z", "ccy_source": "source_reported",
            "cache_fallback": False, "stale": None, "live_error": None}


def nav_out(codes=CODES) -> dict:
    """`exp_nav.load_nav_dividend` 同形（只含 `codes` 裡、而且是本情境要取淨值的檔）。"""
    nav = {"rows": [], "errors": {}, "withheld": {}, "skipped": {}, "fetched": {}, "skipped_rows": {},
           "provenance": {}}
    div = {"rows": [], "errors": {}, "pending": {}, "withheld": {}, "skipped": {}, "fetched": {},
           "skipped_rows": {}, "provenance": {}, "settled": {}}
    memo, not_fetched = {}, {}

    def ok_nav(code, last, value, ccy="USD", source="FundClear:GetFundNAV"):
        nav["rows"].append(_nav_row(code, date(last.year, last.month, last.day - 1) if last.day > 1 else last,
                                    value * 0.99, ccy))
        nav["rows"].append(_nav_row(code, last, value, ccy))
        nav["provenance"][code] = _prov(source)

    def div_settled(code, rows, coverage):
        div["rows"].extend(rows)
        div["settled"][code] = True
        div["provenance"][code] = {"source": ["moneydj_wb05"], "fetched_at": "2026-10-14T01:00:00Z",
                                   "ccy_source": f"{META}_matches_source", "settled": True,
                                   "coverage_start": coverage}

    for code in codes:
        memo[code] = {"hit": False, "cooling": False, "cooling_remaining_sec": None}
        if code == "A01":
            ok_nav(code, date(2026, 10, 10), 10.0)
            # 2025-11-05 … 2026-10-05：12 筆都在窗口 (2025-10-10, 2026-10-10] 內 → 0.6 ÷ 10 × 100 ＝ 6.00%
            rows = [_div_row(code, date(2025 if m >= 11 else 2026, m, 5), 0.05) for m in range(1, 13)]
            rows.append(_div_row(code, date(2024, 12, 15), 0.05))     # 窗口外，不算
            div_settled(code, rows, date(2024, 12, 15))
        elif code == "B02":
            ok_nav(code, date(2026, 10, 4), 20.0)                       # 剛好 10 天：不算舊
            div_settled(code, [], None)                                 # 確認沒有任何配息
        elif code == "C03":
            ok_nav(code, date(2026, 10, 3), 30.0)                       # 11 天：資料未備
            div_settled(code, [_div_row(code, date(2026, 9, 1), 0.1)], date(2020, 1, 1))
        elif code == "D04":
            ok_nav(code, date(2026, 10, 13), 12.5)
            div["rows"].append(_div_row(code, date(2026, 9, 1), 0.1))
            div["settled"][code] = False
            div["skipped"][code] = ["供列的來源回報有列沒有交出來（moneydj_wb05：{'rows': 3}）；寫出的列不是全部，不算已確定"]
            div["provenance"][code] = {"source": ["moneydj_wb05"], "fetched_at": None, "settled": False,
                                       "coverage_start": date(2026, 9, 1)}
        elif code == "E05":
            nav["withheld"][code] = "ccy_conflict"
            nav["skipped"][code] = [CONFLICT_LINE]
            nav["provenance"][code] = {"source": "MoneyDJ:wb01", "fetched_at": None, "ccy_source": None,
                                       "cache_fallback": False, "stale": None, "live_error": None}
            div["withheld"][code] = "ccy_conflict"
            div["settled"][code] = False
        elif code == "F06":
            for part in (nav, div):
                part["withheld"][code] = "ccy_undetermined"
                part["skipped"][code] = [TEXT_CCY_UNDETERMINED]
            div["settled"][code] = False
            not_fetched[code] = TEXT_CCY_UNDETERMINED
        elif code == "G07":
            nav["errors"][code] = f"A 鏈（auto_fetch_moneydj('G07')）沒有取得淨值序列；token={SECRET}"
            div["errors"][code] = f"A 鏈配息取數失敗（每一個來源都失敗）：\ntoken={SECRET}"
            div["settled"][code] = False
        elif code == "H08":
            ok_nav(code, date(2026, 10, 12), 8.0, source=XSS_SOURCE)
            div_settled(code, [_div_row(code, date(2026, 6, 30), 0.2)], date(2019, 1, 1))
    return {"nav": nav, "dividend": div, "memo": memo, "not_fetched": not_fetched}


def mask(text: str) -> str:
    """測試用遮蔽：與 `masking.mask_message(text, [SECRET])` 同效果（把秘密值換成記號）。"""
    return text.replace(SECRET, "‹已遮蔽›")


WITHHELD_TEXTS = {"ccy_missing": None, "ccy_conflict": None, "fetched_at_missing": None,
                  "fetched_at_in_future": None, "ccy_undetermined": TEXT_CCY_UNDETERMINED}
INPUT_CONFLICT = "input_conflict"
