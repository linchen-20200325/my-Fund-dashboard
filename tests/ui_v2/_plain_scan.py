# -*- coding: utf-8 -*-
"""一般畫面去工程化（Phase 3 P0-①）畫面測試的共用件：五頁正式模式 × 情境的 AppTest 腳本，與畫面抽字器。

腳本只用各頁 fixtures／替身當 `load_live` 的回傳（同 `tests/ui_v2/test_live_390_page.py` 的做法），
不呼叫任何 `source.load_live`（設定與診斷頁走真 L2 ＋ 真 L1 ＋ 假 gspread），不打網路。

抽字器讀 AppTest 的元素樹：Markdown（去 HTML 標籤後的文字，另保留原 HTML 給定位用）、Caption、
各種輸入元件的標籤／說明／提示／選項、按鈕標籤與說明、展開區標題。
"""

from __future__ import annotations

import html
import pathlib
import re

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
_TESTS = _ROOT / "tests"

_HEAD = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
sys.path.insert(0, {str(_HERE)!r})
sys.path.insert(0, {str(_TESTS)!r})
"""

# ───────────────────────── 市場總覽 ─────────────────────────

_MKT_NOTES = """
_notes = {"pending": {"leading_index": "ndc_no_release_date", "coincident_index": "ndc_no_release_date",
                      "fx_twd_per_usd": "fx_obs_date_rule"},
          "masked_keys": [], "cooldowns": [],
          "available_keys": ["vol_index", "credit_spread_pct", "term_spread_pct", "policy_rate_pct"],
          "settings": SETTINGS, "settings_error": SETTINGS_ERROR}
"""


def _mkt(dataset_expr: str, *, settings="None", settings_error="None") -> str:
    return _HEAD + f"""
from ui_v2.mkt import fixtures, page
SETTINGS = {settings}
SETTINGS_ERROR = {settings_error}
if SETTINGS is None:
    SETTINGS = {{"window_days": None, "baseline_date": None, "indicator_keys": None, "pair_consistent": None}}
_dataset = {dataset_expr}
""" + _MKT_NOTES + """
page.render(load_live=lambda: {"dataset": _dataset, "notes": _notes}, save_live=lambda *_a: {"status": "saved"})
"""


_MKT_SAVED = ('{"window_days": 30, "baseline_date": "2026-08-01", '
              '"indicator_keys": ["vol_index", "credit_spread_pct"], "pair_consistent": True}')
_MKT_UNCONF = """{"rows": [], "errors": {
    "vol_index": "fetch_url returned None: ^VIX (kind=unreachable)",
    "credit_spread_pct": "未設定 FRED_API_KEY",
    "term_spread_pct": "未設定 FRED_API_KEY",
    "policy_rate_pct": "未設定 FRED_API_KEY"}}"""

MKT = {
    "正常": _mkt("fixtures.dataset_all_ok()", settings=_MKT_SAVED),
    "未設定": _mkt(_MKT_UNCONF, settings_error='"未設定試算表 ID，暫停寫入"'),
    "取數失敗": _mkt("fixtures.dataset_mkt1_fetch_failed()"),
    "局部失敗": _mkt("fixtures.dataset_mkt1_one_key_missing()", settings=_MKT_SAVED),
    "stale": _mkt("fixtures.dataset_mkt2_only_five_rows()", settings=_MKT_SAVED),
}

# ───────────────────────── 持倉體檢 ─────────────────────────

_HLD_BODY = """
import datetime
from ui_v2.hld import fixtures, logic, page

def _scrub(node):
    if isinstance(node, str):
        return node.replace(logic.HINT, "")
    if isinstance(node, dict):
        return {k: _scrub(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_scrub(v) for v in node]
    return node

_dataset = _scrub(fixtures.scenario(SCENARIO)["dataset"])
for _h in _dataset.get("holding") or ():
    if _h["policy_id"] == "DIRECT":
        _h["policy_id"] = "P-001"
for _table, _message in REPLACE_ERRORS.items():
    _dataset.setdefault("errors", {})[_table] = _message
    if _table in ("holding", "user_setting"):
        _dataset[_table] = []
_navs = {r["fund_code"] for r in _dataset.get("nav") or ()}
_prov = {c: {"cache_fallback": c in STALE, "stale": None} for c in _navs}
_live_args = {"direct_policy_id": "DIRECT", "today": datetime.date(*TODAY), "nav_provenance": _prov}

def _load():
    if RAISE:
        raise RuntimeError(RAISE)
    return {"dataset": _dataset, "live_args": _live_args}

page.render(load_live=_load, mask_error=str, save_live=lambda *_a: {"status": "saved"})
"""


def _hld(scenario: str, *, replace_errors=None, stale=(), raise_message=None, today=(2026, 9, 28)) -> str:
    return _HEAD + (
        f"SCENARIO = {scenario!r}\nREPLACE_ERRORS = {dict(replace_errors or {})!r}\n"
        f"STALE = {set(stale)!r}\nRAISE = {raise_message!r}\nTODAY = {tuple(today)!r}\n"
    ) + _HLD_BODY


HLD = {
    "正常": _hld("full"),
    "未設定": _hld("holdfail", replace_errors={"holding": "未設定保單試算表 ID（POLICY_SHEET_ID），不讀取",
                                              "user_setting": "未設定試算表 ID，暫停寫入"}),
    "取數失敗": _hld("fetchfail"),
    "局部失敗": _hld("twofail"),
    "stale": _hld("full", stale={"AAAA", "BBBB"}),
    "超過10日": _hld("full", stale={"AAAA"}, today=(2026, 10, 9)),
    "整頁失敗": _hld("full", raise_message="ConnectionError: fetch_url returned None (kind=unreachable)"),
}

# ───────────────────────── 標的探索 ─────────────────────────

_EXP_BODY = """
import json
import _exp_live_stub as STUB
from ui_v2.exp import logic, page
STUB.reset()
if WIRED:
    STUB.WIRED.append(True)
STUB.STORE["exp_filter_rules"] = json.dumps(RULES, ensure_ascii=False)
STUB.STORE["exp_visible_columns"] = json.dumps(list(logic.COLUMN_ORDER))
STUB.STORE["exp_sort_column"] = json.dumps(SORT)
STUB.STORE["exp_watchlist"] = json.dumps(WATCH)
if READ_ERROR:
    STUB.READ_ERROR.append(READ_ERROR)
_pool_saved = dict(STUB.POOL)   # AppTest 與 pytest 同一個行程：替身的選股池用完原樣放回，不汙染之後的測試
try:
    if POOL:
        STUB.POOL.update(POOL)
    page.render(load_live=STUB.load_live, save_live=STUB.save_setting)
finally:
    STUB.POOL.clear()
    STUB.POOL.update(_pool_saved)
    STUB.reset()
"""


def _exp(*, wired=True, rules=None, sort=(), watch=(), read_error=None, pool=None) -> str:
    if rules is None:
        rules = [{"field": "fund_code", "op": "不等於", "value": "ZZZ"}]
    return _HEAD + (
        f"WIRED = {wired!r}\nRULES = {rules!r}\nSORT = {list(sort)!r}\nWATCH = {list(watch)!r}\n"
        f"READ_ERROR = {read_error!r}\nPOOL = {pool!r}\n"
    ) + _EXP_BODY


EXP = {
    "正常": _exp(sort=["ccy"]),
    "未設定": _exp(read_error="未設定試算表 ID，暫停寫入",
                   pool={"status": "not_configured", "codes": [], "message": "選股池未設定雲端來源（沒有服務帳戶憑證），不讀本機暫存檔當母體"}),
    "取數失敗": _exp(read_error="HTTPSConnectionPool(host='sheets.example'): Max retries exceeded (kind=unreachable)"),
    "局部失敗": _exp(wired=False),
    "stale": _exp(rules=[{"field": "mgmt_fee_rate_pct", "op": "大於", "value": "1"}]),
}

# ───────────────────────── 資產配置 ─────────────────────────

_ALO_BODY = """
from ui_v2.alo import fixtures, page
_dataset = fixtures.scenario(SCENARIO)
for _table, _message in REPLACE_ERRORS.items():
    _dataset.setdefault("errors", {})[_table] = _message
if NOT_READY:
    _codes = [h["fund_code"] for h in _dataset["holding"]][:1]
    _dataset["nav_not_ready"] = {"codes": _codes, "days": 10, "last": {c: "2026-09-01" for c in _codes}}
if CONFLICT:   # 同鍵兩列而類別不同 → 組模型那一步 raise ValueError（整頁錯誤畫面；同 test_alo_r3_conflict_page）
    _first = _dataset["holding"][0]
    _dataset["holding"].append(dict(_first, holding_id=_first["holding_id"] + "X", bucket=_first["bucket"] + "X"))

page.render(load_live=lambda: {"dataset": _dataset, "notes": {}}, mask_error=str)
"""


def _alo(scenario: str, *, replace_errors=None, conflict=False, not_ready=False) -> str:
    return _HEAD + (
        f"SCENARIO = {scenario!r}\nREPLACE_ERRORS = {dict(replace_errors or {})!r}\nCONFLICT = {conflict!r}\n"
        f"NOT_READY = {not_ready!r}\n"
    ) + _ALO_BODY


ALO = {
    "正常": _alo("full"),
    "未設定": _alo("settingfail", replace_errors={"user_setting": "未設定試算表 ID，暫停寫入"}),
    "未設定保單": _alo("holdfail", replace_errors={"holding": "未設定保單試算表 ID（POLICY_SHEET_ID），不讀取"}),
    "取數失敗": _alo("holdfail", replace_errors={"holding": "RuntimeError：fetch_url returned None (kind=unreachable)"}),
    "局部失敗": _alo("fxfail"),
    "stale": _alo("full", not_ready=True),
    "整頁失敗": _alo("full", conflict=True),
}

# ───────────────────────── 設定與診斷 ─────────────────────────

_SET_BODY = """
import types
from _fake_settings_sheet import FakeClient, FakeSpreadsheet
from infra import gspread_retry as GR
from repositories import settings_sheet_repository as R
from ui_v2.set import page, source
from ui_v2 import plain
import streamlit as st

class _Book(FakeSpreadsheet):
    title = "測試用設定本"

_book = _Book()
_cfg = dict(CFG)
_mi = source.market_indicator
# AppTest 與 pytest 同一個行程：換掉的東西一律在 finally 換回來，不汙染之後的測試。
_saved = (R.get_secret, R._make_client, dict(R._TITLES), GR.time, source.st, _mi.source_cooldowns,
          _mi.fetch_yf_close_with_error)
try:
    R.get_secret = lambda key, default=None: _cfg.get(key, default)
    R._make_client = lambda creds: FakeClient(_book)
    R._TITLES = {}
    R.clear_cache()
    GR.time = types.SimpleNamespace(sleep=lambda _s: None)
    source.st = types.SimpleNamespace(secrets=_cfg, session_state={})
    _mi.source_cooldowns = lambda: []
    _mi.fetch_yf_close_with_error = lambda ticker, *a, **k: (None, FETCH_ERROR)
    if STALE:   # 新鮮度上限設 0 日 ⇒ 取回的每一列都在上限外（44 SET-1 判準）
        import pandas as pd
        _s = pd.Series([17.0, 18.5], index=pd.to_datetime(["2026-09-22", "2026-09-23"]), dtype=float, name="^VIX")
        _s.attrs["fetched_at"] = "2026-09-25T06:00:00+00:00"
        _s.attrs["exchange_tz"] = "Etc/UTC"
        _mi.fetch_yf_close_with_error = lambda ticker, *a, **k: (_s, None)
        source.save_setting("set_max_age_days", "0", "int")
    if REFETCH or STALE:
        source.refetch("市場指標")
    for _slug, _entries in PRESET.items():
        plain.record_raw(st.session_state, _slug, _entries, "2026-10-17T00:00:00+00:00")
    page.render(load_live=source.load_live, save_live=source.save_setting, refetch_live=source.refetch)
finally:
    (R.get_secret, R._make_client, R._TITLES, GR.time, source.st, _mi.source_cooldowns,
     _mi.fetch_yf_close_with_error) = _saved
    R.clear_cache()
"""

_SET_CFG = {"SETTINGS_SHEET_ID": "sheet-for-plain-scan",
            "google_service_account": {"client_email": "sa@example.iam.gserviceaccount.com"}}


_SET_FETCH_ERROR = "HTTPSConnectionPool(host='127.0.0.1'): Max retries exceeded (kind=unreachable)"


def _set(*, cfg=None, preset=None, refetch=False, stale=False) -> str:
    return _HEAD + (
        f"CFG = {dict(_SET_CFG if cfg is None else cfg)!r}\nPRESET = {dict(preset or {})!r}\n"
        f"REFETCH = {refetch!r}\nSTALE = {stale!r}\nFETCH_ERROR = {_SET_FETCH_ERROR!r}\n"
    ) + _SET_BODY


SET_PRESET_RAW = "⛔ 取數失敗：fetch_url returned None: ^VIX (kind=unreachable)"
SET = {
    "正常": _set(),
    "未設定": _set(cfg={}),
    "取數失敗": _set(cfg={"SETTINGS_SHEET_ID": "sheet-for-plain-scan"}),
    "局部失敗": _set(preset={"mkt": [{"where": "MKT-1 風險情緒卡", "text": SET_PRESET_RAW}]}),
    "取數紀錄": _set(refetch=True),
    "stale": _set(stale=True),
}

SCRIPTS = {"mkt": MKT, "hld": HLD, "exp": EXP, "alo": ALO, "set": SET}

# ───────────────────────── 抽字器 ─────────────────────────

_TAG = re.compile(r"<[^>]+>")
_STYLE = re.compile(r"<style>.*?</style>", re.S)
_TITLE_ATTR = re.compile(r'\stitle="([^"]*)"')


def markdown_text(value: str) -> str:
    """Markdown 元素去 `<style>` 區塊與 HTML 標籤（含屬性，所以 `data-block` 不算畫面字）後的可見文字；
    滑過去會看到的 `title` 屬性（值旁的來源提示）另收在後面。"""
    value = _STYLE.sub(" ", value or "")
    tips = " ".join(_TITLE_ATTR.findall(value))
    return html.unescape(_TAG.sub(" ", value) + (" " + tips if tips else ""))


def _element_texts(node) -> list:
    kind = type(node).__name__
    out = []
    if kind in ("Markdown", "Caption"):
        out.append(markdown_text(node.value))
    for attr in ("label", "help", "placeholder"):
        if kind in ("Markdown", "Caption") and attr != "help":
            continue
        value = getattr(node, attr, None)
        if isinstance(value, str) and value:
            out.append(value)
    options = getattr(node, "options", None)
    if kind in ("Selectbox", "Radio", "Multiselect") and options:
        out.extend(str(option) for option in options)
    return out


def screen_texts(at, *, skip_expanders=(), skip_columns_with=()) -> list:
    """畫面上看得到的字（一般畫面）。`skip_expanders`：標題以這些字開頭的展開區整枚不收；
    `skip_columns_with`：欄（`st.columns` 的一格）內任一 Markdown 原 HTML 含這些字 → 整欄不收。"""
    out = []

    def walk(node):
        kind = type(node).__name__
        if kind == "Expander" and any(str(node.label).startswith(p) for p in skip_expanders):
            return
        if kind == "Column" and skip_columns_with:
            raw = []

            def collect(n):
                if type(n).__name__ == "Markdown":
                    raw.append(n.value)
                for ch in getattr(n, "children", {}).values():
                    collect(ch)

            collect(node)
            if any(marker in value for marker in skip_columns_with for value in raw):
                return
        out.extend(_element_texts(node))
        if kind == "Expander":
            out.append(str(node.label))
        for child in getattr(node, "children", {}).values():
            walk(child)

    walk(at._tree)
    return out


def expander_texts(at, title_prefix: str) -> list:
    """標題以 `title_prefix` 開頭的那一枚展開區裡的字（含標題）。"""
    out = []

    def walk(node, inside):
        kind = type(node).__name__
        here = inside or (kind == "Expander" and str(node.label).startswith(title_prefix))
        if here:
            out.extend(_element_texts(node))
            if kind == "Expander":
                out.append(str(node.label))
        for child in getattr(node, "children", {}).values():
            walk(child, here)

    walk(at._tree, False)
    return out
