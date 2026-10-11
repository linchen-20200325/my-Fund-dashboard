# -*- coding: utf-8 -*-
"""「資產屬性」改「基金屬性」、停用依基金名稱推定核心／衛星（客戶 2026-10-11 裁示）。

背景：`ui/helpers/macro/helpers.py::mk_fund_signal` 原以基金名稱／`基金種類` 的關鍵字猜
核心資產／衛星資產／混合型，並據此輸出買進／賣出類操作句。目前 production 上它之所以不會顯示，
只因 `st.session_state.macro_done`／`phase_info` 只有舊 tab1 會寫入 ⇒ **一旦總經景氣位階重新接回，
名稱推定就會復活**。本檔守的是「接回之後也不會復活」：

1. 行為：不論名稱、`基金種類`、景氣位階為何，基金屬性與操作訊號恆為「—」；`auto_alloc` 與名稱無關。
2. 接回情境：把 `macro_done`／`phase_info` 注入後，單檔頁卡片、② 健診／③ 批次大表的
   「基金屬性」「操作訊號」仍為「—」。
3. 結構（AST，不用字串 grep）：`mk_fund_signal` 本體不讀基金名稱／種類、不含舊的屬性字樣；
   四個相關檔案的字串常數裡沒有舊標籤「資產屬性」與舊的屬性值。

語意：
- 客戶設定的「核心／衛星級別」只來自 Google Sheet 的 `policy_tier`（`shared/policy_tier.py::resolve_tier`）。
- 「基金屬性」只有取得 MoneyDJ／FundClear 等可追溯的原始分類資料時才可顯示；目前沒有 ⇒ 一律「—」。

突變驗證（實跑，見各條 docstring）：把舊的名稱關鍵字判斷貼回 `mk_fund_signal` ⇒ 1、2、3 的多條轉紅。
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

_HELPERS = "ui/helpers/macro/helpers.py"
_TAB2 = "ui/tab2_single_fund.py"
_SIGNALS = "ui/helpers/fund_grp_health/signals.py"
_UNIFIED = "ui/helpers/fund_grp_health/unified.py"

# 舊的屬性值與動作句（只在此處作為「不得出現」的判準；不是掃描用的假符號）。
_OLD_ATTR_VALUES = ("核心資產 🛡️", "衛星資產 ⚡", "混合型 ⚖️")
_OLD_ACTION_LABELS = ("🟢 買進加碼", "🟢 積極買進", "⚪ 持有核心", "🟡 持有設停利",
                      "🟡 持有減碼", "🔴 賣出獲利", "🟢 逢低買進", "⏸️ 觀望等待")

_NAMES_LOOK_CORE = ("摩根多重收益債券基金", "Global Income Bond Fund", "某某高股息均衡基金")
_NAMES_LOOK_SATELLITE = ("全球科技基金", "AI 半導體成長基金", "Emerging Tech Growth Equity Fund")
_NAMES_NEUTRAL = ("某某全球基金", "XYZ Fund", "")
_PHASES = ("復甦", "擴張", "高峰", "衰退")
_ALL_NAMES = _NAMES_LOOK_CORE + _NAMES_LOOK_SATELLITE + _NAMES_NEUTRAL


def _tree(rel: str) -> ast.Module:
    return ast.parse((ROOT / rel).read_text(encoding="utf-8"), filename=rel)


def _func(rel: str, name: str) -> ast.FunctionDef:
    for n in ast.walk(_tree(rel)):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    raise AssertionError(f"{rel} 找不到 {name}")


def _str_constants(node: ast.AST) -> list:
    return [n.value for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


@pytest.fixture
def _indicators():
    """隔離 `st.session_state['indicators']`（auto_alloc 會讀它），測完還原。"""
    import streamlit as st
    _had = "indicators" in st.session_state
    _old = st.session_state.get("indicators")
    yield st.session_state
    if _had:
        st.session_state["indicators"] = _old
    else:
        st.session_state.pop("indicators", None)


# ══════════════════════════════════════════════════════════════════
# 1. 行為：mk_fund_signal 不依名稱／種類／景氣位階推定
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("phase", _PHASES)
@pytest.mark.parametrize("name", _ALL_NAMES)
@pytest.mark.parametrize("key", ("基金名稱", "name", "fund_name"))
def test_name_never_decides_attribute_or_signal(name, phase, key):
    """核心像／衛星像／中性 × 四個景氣位階 × 三種名稱鍵 → 一律「—」、sig_type none、reason 空。

    突變：把舊的 core_kw／sat_kw 判斷與 RECS 貼回 `mk_fund_signal` → 本條大量轉紅。
    """
    from ui.helpers.macro.helpers import mk_fund_signal
    sig = mk_fund_signal({key: name}, phase, 6.5)
    assert sig["asset_class"] == "—", sig
    assert sig["label"] == "—", sig
    assert sig["sig_type"] == "none", sig
    assert sig["reason"] == "", sig


@pytest.mark.parametrize("phase", _PHASES)
@pytest.mark.parametrize("kind", ("核心型收益債券", "衛星型科技成長", "core income bond", "satellite tech equity"))
def test_fund_kind_field_never_decides_attribute_or_signal(kind, phase):
    """`基金種類`（全 repo 無人產生，但舊程式會讀）帶核心／衛星字樣也不得影響結果。"""
    from ui.helpers.macro.helpers import mk_fund_signal
    sig = mk_fund_signal({"基金名稱": "全球科技基金", "基金種類": kind}, phase, 6.5)
    assert (sig["asset_class"], sig["label"], sig["sig_type"], sig["reason"]) == ("—", "—", "none", "")


def test_return_keys_unchanged_so_callers_need_no_change():
    from ui.helpers.macro.helpers import mk_fund_signal
    sig = mk_fund_signal({}, "擴張", 5.0)
    assert set(sig) == {"asset_class", "label", "sig_type", "sig_style", "reason", "auto_alloc"}
    assert isinstance(sig["sig_style"], str) and sig["sig_style"]


def test_auto_alloc_is_independent_of_fund_name(_indicators):
    """`auto_alloc`（PMI／VIX／失業率／CPI 的股債配比）與名稱無關：同指標下不同名稱得到相同結果，且仍有值。"""
    from ui.helpers.macro.helpers import mk_fund_signal
    _indicators["indicators"] = {
        "PMI": {"value": 52.0}, "VIX": {"value": 18.0},
        "UNEMPLOYMENT": {"value": 3.8}, "CPI": {"value": 2.5, "prev": 2.6},
    }
    _ref = mk_fund_signal({}, "復甦", 6.5)["auto_alloc"]
    assert _ref is not None and _ref[:3] == (70, 30, "復甦/擴張—積極"), _ref
    for _name in _ALL_NAMES:
        for _ph in _PHASES:
            assert mk_fund_signal({"基金名稱": _name}, _ph, 6.5)["auto_alloc"] == _ref, (_name, _ph)


# ══════════════════════════════════════════════════════════════════
# 2. 接回情境：② 健診／③ 批次大表（mk_signal_by_code）
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("phase", _PHASES)
def test_grp_health_tables_show_dash_when_phase_is_wired(phase):
    """帶景氣位階時，「基金屬性」「操作訊號」仍為「—」；買賣價位與現價位階不受影響。"""
    from ui.helpers.fund_grp_health.signals import mk_signal_by_code
    funds = [
        {"code": "C1", "name": "摩根多重收益債券基金",
         "metrics": {"nav": 94.0, "buy1": 95.0, "buy3": 85.0, "sell1": 105.0, "sell3": 115.0}},
        {"code": "S1", "name": "全球科技成長基金",
         "metrics": {"nav": 120.0, "buy1": 95.0, "buy3": 85.0, "sell1": 105.0, "sell3": 115.0}},
        {"code": "N1", "name": "某某全球基金", "metrics": {}},
    ]
    out = mk_signal_by_code(funds, phase, 6.5)
    for code in ("C1", "S1", "N1"):
        assert out[code]["基金屬性"] == "—", (code, out[code])
        assert out[code]["操作訊號"] == "—", (code, out[code])
        assert "資產屬性" not in out[code], "舊欄名不得殘留"
    # 價位與位階與景氣／名稱無關，照常計算（確認沒有把整列一併停掉）
    assert out["C1"]["買 1 (小跌)"] == "95.00" and "買1" in out["C1"]["現價位階"]
    assert "賣3" in out["S1"]["現價位階"]


def test_unified_column_name_and_help_are_renamed():
    from ui.helpers.fund_grp_health.columns import unified_column_config
    from ui.helpers.fund_grp_health.unified import _UNIFIED_FRONT

    _names = [c for c, _ in _UNIFIED_FRONT]
    assert "基金屬性" in _names and "資產屬性" not in _names
    # 欄位位置不變：仍緊接在「淨值×匯率」之後、「操作訊號」之前（只改字、不改版面）
    assert _names.index("基金屬性") == _names.index("淨值×匯率") + 1
    assert _names.index("操作訊號") == _names.index("基金屬性") + 1

    cfg = unified_column_config()
    assert "基金屬性" in cfg and "資產屬性" not in cfg
    _help = cfg["基金屬性"]["help"]
    for _must in ("可追溯", "—", "不是", "核心", "衛星", "不會依基金名稱推測"):
        assert _must in _help, f"基金屬性 help 少了 {_must!r}"
    assert "股票 / 債券 / 平衡" not in _help, "舊 help 與實際行為不符的敘述不得殘留"
    _sig_help = cfg["操作訊號"]["help"]
    assert "已停用" in _sig_help and "—" in _sig_help
    assert "景氣位階" not in _sig_help, "操作訊號 help 不得帶裁示外的新語意（全表沒有叫「景氣位階」的欄）"


# ══════════════════════════════════════════════════════════════════
# 3. 結構（AST）：mk_fund_signal 本體與四個相關檔案
# ══════════════════════════════════════════════════════════════════
def test_mk_fund_signal_body_does_not_read_fund_identity():
    """`mk_fund_signal` 本體不得引用 `fund_info`（名稱／種類的唯一入口），也不得出現名稱鍵或舊屬性字樣。

    ⚠️ 只擋字面寫法；`getattr`／動態組鍵之類的繞法擋不住 —— 行為面由第 1 組守。
    突變：貼回 `name = (fund_info.get("基金名稱", ...` → 本條紅。
    """
    fn = _func(_HELPERS, "mk_fund_signal")
    _used = [n.lineno for n in ast.walk(fn)
             if isinstance(n, ast.Name) and n.id == "fund_info"
             and n is not fn]
    assert not _used, f"mk_fund_signal 行 {_used} 引用 fund_info（名稱／種類不得參與判斷）"
    _banned_keys = {"基金名稱", "name", "fund_name", "基金種類"}
    _consts = set(_str_constants(fn))
    assert not (_consts & _banned_keys), f"讀了名稱／種類鍵：{sorted(_consts & _banned_keys)}"
    for _v in _OLD_ATTR_VALUES + _OLD_ACTION_LABELS:
        assert _v not in _consts, f"mk_fund_signal 仍帶舊字樣 {_v!r}"


@pytest.mark.parametrize("rel", (_HELPERS, _TAB2, _SIGNALS, _UNIFIED))
def test_no_old_attribute_values_or_actions_in_string_constants(rel):
    """四個檔案的字串常數（AST，註解不算）不得有舊的屬性值、舊動作句。"""
    _consts = _str_constants(_tree(rel))
    for _v in _OLD_ATTR_VALUES + _OLD_ACTION_LABELS:
        assert not any(_v in c for c in _consts), f"{rel} 仍有字串常數含 {_v!r}"


@pytest.mark.parametrize("rel", (_TAB2, _SIGNALS, _UNIFIED))
def test_old_label_is_renamed_in_visible_strings(rel):
    """使用者可見標籤已由「資產屬性」改為「基金屬性」（卡片標題、大表欄名）。"""
    _consts = _str_constants(_tree(rel))
    assert not any("資產屬性" in c for c in _consts), f"{rel} 仍有字串常數含「資產屬性」"


def test_tab2_card_title_is_fund_attribute():
    assert any("基金屬性</div>" in c for c in _str_constants(_tree(_TAB2))), "單檔頁卡片標題未改為「基金屬性」"


# ══════════════════════════════════════════════════════════════════
# 2'. 接回情境：單檔頁（AppTest，注入 macro_done／phase_info）
# ══════════════════════════════════════════════════════════════════
@pytest.fixture
def _no_hot_money_auto_refresh():
    """AppTest 不外連（同 tests/test_app_apptest.py 的作法）。"""
    import ui.hot_money as _hm
    _orig = _hm.refresh_hot_money_data
    _hm.refresh_hot_money_data = lambda *a, **k: (False, "skipped in AppTest")
    yield
    _hm.refresh_hot_money_data = _orig


@pytest.mark.slow
@pytest.mark.parametrize("fund_name, phase", [
    ("Test Fund 收益債券基金", "復甦"),      # 名稱像核心
    ("Test Fund 科技成長基金", "高峰"),      # 名稱像衛星
])
def test_tab2_card_stays_dash_when_macro_phase_is_wired(
    monkeypatch: pytest.MonkeyPatch, _no_hot_money_auto_refresh, fund_name: str, phase: str,
) -> None:
    """注入 `macro_done=True` + `phase_info` 後，單檔頁卡片的「基金屬性」值為「—」，
    卡片內沒有舊屬性值與舊動作句；同頁「總經自動配比建議」（auto_alloc）仍照常渲染。

    突變：把舊的名稱推定貼回 `mk_fund_signal` → 本條紅（卡片會出現核心資產／衛星資產與動作句）。
    """
    import pandas as pd
    from streamlit.testing.v1 import AppTest

    for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.setenv(_pv, "http://127.0.0.1:9")     # 不外連（同 test_app_apptest）
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.setenv("FRED_API_KEY", "test-fred-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    app = AppTest.from_file("app.py", default_timeout=180)
    app.secrets["FRED_API_KEY"] = "test-fred-key"
    app.secrets["GEMINI_API_KEY"] = "test-gemini-key"

    _idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=400, freq="B")
    _nav = pd.Series([100.0 * (1 + 0.0003 * i) for i in range(400)], index=_idx, name="TEST001")

    app.session_state["macro_done"] = True
    app.session_state["indicators"] = {
        "PMI": {"score": 1.0, "weight": 1.0, "value": 52.0, "date": "2026-05-15"},
        "VIX": {"score": 1.0, "weight": 1.0, "value": 18.0, "date": "2026-05-15"},
        "UNEMPLOYMENT": {"score": 0.0, "weight": 1.0, "value": 3.8, "date": "2026-05-15"},
        "CPI": {"score": 0.0, "weight": 1.0, "value": 2.5, "prev": 2.6, "date": "2026-05-15"},
    }
    app.session_state["phase_info"] = {
        "score": 6.5, "phase": phase, "phase_color": "#90EE90",
        "alloc": {"股票": 50, "債券": 30, "現金": 20}, "advice": "test", "rec_prob": 0.10,
    }
    app.session_state["fund_data"] = {
        "status": "ok", "full_key": "TEST001", "fund_name": fund_name,
        "series": _nav, "dividends": [],
        "metrics": {"nav_latest": 112.0, "ret_1y": 8.5, "ret_3y": 25.0, "annual_div_rate": 4.2,
                    "sharpe": 1.1, "std_1y": 12.0, "bb_upper": 115.0, "bb_lower": 105.0, "ma60": 110.0},
        "moneydj_raw": {}, "page_type": "yp010000", "error": "", "warning": "",
    }
    app.run()
    assert not app.exception, [str(e) for e in app.exception]

    _blobs = [m.value for m in app.markdown if isinstance(m.value, str)]
    _cards = [b for b in _blobs if "基金屬性" in b and "策略3 操作訊號" in b]
    assert len(_cards) == 1, f"找不到單檔頁訊號卡片（含「基金屬性」與「策略3 操作訊號」）：{len(_cards)} 個"
    _card = _cards[0]
    assert re.search(r"基金屬性</div><div[^>]*>—</div>", _card), f"基金屬性值不是「—」：{_card[:400]!r}"
    assert re.search(r"策略3 操作訊號</div><span[^>]*>—</span>", _card), f"操作訊號不是「—」：{_card[:600]!r}"
    for _v in _OLD_ATTR_VALUES + _OLD_ACTION_LABELS:
        assert _v not in _card, f"卡片仍出現舊字樣 {_v!r}"
    assert "資產屬性" not in _card
    assert any("總經自動配比建議" in b for b in _blobs), "auto_alloc 配比卡應照常渲染（與名稱無關）"


# ══════════════════════════════════════════════════════════════════
# 4. 合併點（② 健診／③ 批次共用）：景氣位階非空時仍為「—」
# ══════════════════════════════════════════════════════════════════
@pytest.fixture
def _seed_benchmark(monkeypatch):
    """種入基準快取 → capture_by_code 不連網（同 tests/test_grp_health_unified_merge.py）。"""
    import time as _t

    import numpy as np
    import pandas as pd

    import ui.helpers.fund_grp_health.capture as _cap
    _d = pd.date_range("2020-01-31", periods=60, freq="ME")
    _b = pd.Series(100 * np.cumprod([1.0] + [1.005] * 59), index=_d)
    _now = _t.monotonic()
    monkeypatch.setitem(_cap._BENCH_CACHE, "SPX", (_now, _b))
    monkeypatch.setitem(_cap._BENCH_CACHE, "TWII", (_now, _b))


@pytest.mark.parametrize("phase", _PHASES)
def test_merged_extra_columns_keep_attribute_and_signal_dash(_seed_benchmark, phase):
    """`build_merged_extra_columns(funds, phase, score)`：名稱像核心／像衛星／中性、景氣位階非空 →
    「基金屬性」「操作訊號」皆「—」，且欄名是「基金屬性」、沒有「資產屬性」。

    突變：在 `unified.build_merged_extra_columns` 合併後依名稱覆寫「基金屬性」→ 本條紅。
    """
    from ui.helpers.fund_grp_health.unified import build_merged_extra_columns
    funds = [
        {"code": "C1", "name": "摩根多重收益債券基金", "series": None, "metrics": {},
         "risk_metrics": {}, "moneydj_raw": {}},
        {"code": "S1", "name": "全球科技成長基金", "series": None, "metrics": {},
         "risk_metrics": {}, "moneydj_raw": {}},
        {"code": "N1", "name": "某某全球基金", "series": None, "metrics": {},
         "risk_metrics": {}, "moneydj_raw": {}},
    ]
    cols, combined = build_merged_extra_columns(funds, phase, 6.5)
    assert "基金屬性" in cols and "資產屬性" not in cols
    for code in ("C1", "S1", "N1"):
        assert combined[code]["基金屬性"] == "—", (code, combined[code])
        assert combined[code]["操作訊號"] == "—", (code, combined[code])
        assert "資產屬性" not in combined[code]


def test_batch_row_skeleton_uses_new_column_name():
    """批次建列的欄骨架（`build_batch_unified_row` 輸出的鍵集合）用「基金屬性」，不含「資產屬性」。
    （`build_batch_unified_row` 本體需連網取基金資料，故這裡只守欄骨架 SSOT；合併點行為由上一條守。）"""
    from ui.helpers.fund_grp_health.unified import BATCH_UNIFIED_COLUMNS
    assert "基金屬性" in BATCH_UNIFIED_COLUMNS and "資產屬性" not in BATCH_UNIFIED_COLUMNS
