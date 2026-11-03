# -*- coding: utf-8 -*-
"""一般 UI 不得外漏工程內部資訊守衛（客戶 2026-11-03，`DEC-2026-11-03-07` 第 (3) 項；BL-0536）。

禁止出現在**使用者看得到的字**：環境變數名／常數名、exception 類別與訊息、Python symbol（snake_case 識別字）、
內部原因代碼、模組路徑、traceback、英文 aggregation rule 這類工程詞。技術細節只留在 log／diagnostics／evidence。

兩條獨立路徑（任一條單獨都會漏，所以都要）：
1. **靜態**：`ui_v3/` 非測試原始碼的字串常數（排除 docstring）與兩張字樣表（正式＋暫時）裡，不得有「環境變數形」字串；
   字樣表文字本身要通過同一個偵測器。
2. **渲染**：以 AppTest 實際渲染 🌍 頁（多個情境 × 四個檢視），收集**看得見的字**（markdown 去標籤＋aria／title 屬性、
   標題、expander 標籤、radio 標籤與選項），逐一過偵測器。

⚠️ 偵測器與負控都只在記憶體／monkeypatch 內現編；掃描對象是渲染結果與 `ui_v3/` 非測試原始碼，**不含本檔與文件**
（本檔含負控字串，掃它會自我命中；CLAUDE.md §-2.A 第 8 款）。

未涵蓋（據實）：偵測器是形狀比對（大寫底線識別字、snake_case、已知工程詞、模組路徑、traceback 字樣），不是語意判斷；
一般英文單字（例：來源名 Yahoo Finance、FRED）與來源標示裡的代號（例：`^TWII`）不在禁字內——來源標示屬 44 之十九要求的來源層，不是工程資訊。
"""
from __future__ import annotations

import ast
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

import ui_v3_guard_lib as lib
from shared.ui_semantics import rules
from ui_v3.viewmodels import preview_wording as W

streamlit_testing = pytest.importorskip("streamlit.testing.v1")

import market_stubs as ms
from ui_v3.adapters import market_page as adapter
from ui_v3.pages import mkt

APP = str(Path(__file__).resolve().parents[2] / "ui_v3" / "app_preview.py")

# ───────────────────────────── 偵測器（純函式） ─────────────────────────────

_ENV_SHAPE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")            # 環境變數／常數名
_SNAKE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")                 # Python symbol／內部原因代碼
_ENGINEERING_WORDS = re.compile(
    r"aggregation rule|Traceback|\w*Exception\b|\w*Error\b|Errno|\bNone\b|\bNaN\b|HTTP \d{3}|st\.secrets|os\.environ|\.py\b"
    r"|\b(?:services|repositories|infra|shared|ui_v2|ui_v3)[./]", re.IGNORECASE)


def leaks(text: str) -> list:
    """看得見的字 → 命中的工程資訊清單（空＝乾淨）。"""
    return [m.group(0) for rx in (_ENV_SHAPE, _SNAKE, _ENGINEERING_WORDS) for m in rx.finditer(text)]


class _Visible(HTMLParser):
    """HTML → 看得見的字：去標籤、略過 style／script，另收 aria-label／title／alt 屬性（螢幕閱讀器看得到）。"""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self._skip += 1
        self.parts += [v for k, v in attrs if k in ("aria-label", "title", "alt") and v]

    def handle_endtag(self, tag):
        if tag in ("style", "script") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def visible_text(html: str) -> str:
    parser = _Visible()
    parser.feed(html)
    return " ".join(parser.parts)


# ───────────────────────────── 負控（記憶體內現編） ─────────────────────────────

@pytest.mark.parametrize("bad", [
    "⛔ 尚未設定：" + "FRED" + "_API_" + "KEY",
    "暫無完整市場綜合判定（缺正式 " + "aggregation" + " rule）",
    "Trace" + "back (most recent call last)",
    "原因代碼：" + "no" + "_source",
    "services" + ".v2_tables.market_view",
    "Value" + "Error: bad",
    "ui_v3" + "/pages/mkt.py",
])
def test_negative_control_detector_flags_engineering_text(bad):
    assert leaks(visible_text(f"<div>{bad}</div>")), bad


def test_negative_control_detector_reads_attribute_text_and_ignores_style():
    assert leaks(visible_text('<svg aria-label="no' + '_source"></svg>'))
    assert leaks(visible_text("<style>.a_b-c{x:1}</style><p>只有中文</p>")) == []
    assert leaks("台股 資料日 2026-11-02（經過 1 日） Yahoo Finance (^TWII) FRED ◇ 資料未備 S&P 500") == []


# ───────────────────────────── 1. 靜態 ─────────────────────────────

# 比對鍵（不是畫面字）：adapter 用它辨認下層「未設定金鑰」的原因，從不顯示；畫面端由渲染路徑守衛證明不會出現。
_STATIC_ALLOWLIST = {("ui_v3/adapters/market_page.py", "未設定 " + "FRED" + "_API_" + "KEY")}


def _string_constants(source: str):
    """畫面可能用到的字串常數：排除 docstring、`__all__` 匯出名、`raise` 裡的內部錯誤訊息（不上畫面；渲染路徑守衛另證）。"""
    tree = ast.parse(source)
    skip = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) or (isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)):
            skip |= {id(n) for n in ast.walk(node) if isinstance(n, ast.Constant)}
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip]


def env_shaped_literals(rel: str, source: str) -> list:
    return [s for s in _string_constants(source) if _ENV_SHAPE.search(s) and (rel, s) not in _STATIC_ALLOWLIST]


def test_ui_v3_source_has_no_env_var_shaped_string_literal():
    hits = []
    for path in sorted(lib.UI_V3.rglob("*.py")):
        rel = lib.rel_of(path)
        hits += [f"{rel}: {s!r}" for s in env_shaped_literals(rel, lib.read(path))]
    assert hits == []


def test_static_scan_negative_control_turns_red():
    bad = 'NAME = "' + "FRED" + "_API_" + 'KEY"\ndef f():\n    """FRED_API_KEY 在 docstring 不算"""\n    return 1\n'
    assert env_shaped_literals("ui_v3/pages/x.py", bad) == ["FRED" + "_API_" + "KEY"]
    assert env_shaped_literals("ui_v3/pages/x.py", 'def f():\n    """TOKEN_X"""\n    return "中文"\n') == []


def test_every_wording_table_text_passes_the_detector_and_the_approved_texts_say_no_aggregation_rule():
    texts = [a.text for a in rules.APPROVED_WORDING.values()] + [w.text for w in W.PREVIEW_PENDING_WORDING.values()]
    # 佔位欄位名（{date}／{label}…）是模板語法、不是畫面字：去掉大括號再比對
    assert {t: leaks(t.replace("{", "").replace("}", "")) for t in texts if leaks(t.replace("{", "").replace("}", ""))} == {}
    assert not any("aggregation" in t.lower() for t in texts)
    assert rules.approved("hero_sentence").text == "暫無完整市場綜合判定（尚未建立正式綜合判定規則）"


# ───────────────────────────── 2. 渲染（多情境 × 四個檢視） ─────────────────────────────

def _run(monkeypatch, view, table=None, *, state=None):
    monkeypatch.setattr(adapter, "load", lambda sources: (view, table if table is not None else ms.table()))
    at = streamlit_testing.AppTest.from_file(APP, default_timeout=60)
    for key, value in (state or {}).items():
        at.session_state[key] = value
    return at.run()


def _page_visible(at) -> str:
    parts = [visible_text(m.value) for m in at.markdown] + [t.value for t in at.title]
    parts += [e.label for e in at.expander]
    for radio in at.radio:
        parts.append(radio.label)
        parts += [str(o) for o in radio.options]
    return " ".join(parts)


_SHORT = ms.weekdays("2026-09-01", ms.LAST_US)

SCENARIOS = {
    "complete": lambda: (ms.view(), ms.table(), {}),
    "partial_history": lambda: (ms.view(us_dates=ms.weekdays("2024-11-01", ms.LAST_US)), ms.table(),
                                {mkt.KEY_PERIOD: "3Y"}),
    "both_too_short": lambda: (ms.view(tw_dates=_SHORT, us_dates=_SHORT), ms.table(), {mkt.KEY_PERIOD: "3Y"}),
    "fetch_failure": lambda: (ms.view(tw="error", us="error", vx="error"), ms.table(), {}),
    "stale_series": lambda: (ms.view(us_dates=ms.weekdays("2021-06-01", "2026-10-30")), ms.table(), {}),
    "all_missing": lambda: (ms.view(tw="missing", us="missing", vx="missing"), ms.table(drop=("vol_index", "credit_spread_pct",
                            "term_spread_pct", "policy_rate_pct")), {}),
    "no_fred_key": lambda: (ms.view(key=""), ms.table(errors={k: "未設定 " + "FRED" + "_API_" + "KEY"
                                                              for k in ("credit_spread_pct", "term_spread_pct", "policy_rate_pct")},
                                                     drop=("credit_spread_pct", "term_spread_pct", "policy_rate_pct")), {}),
}


@pytest.mark.parametrize("view_key", ["compare", "vix", "us10y", "us2y"])
@pytest.mark.parametrize("name", list(SCENARIOS))
def test_rendered_page_never_shows_engineering_information(monkeypatch, name, view_key):
    view, table, state = SCENARIOS[name]()
    state = {**state, mkt.KEY_VIEW: view_key}
    at = _run(monkeypatch, view, table, state=state)
    assert not at.exception
    found = leaks(_page_visible(at))
    assert found == [], (name, view_key, found)


def test_rendered_page_does_not_show_raw_failure_text_from_the_source(monkeypatch):
    """L1／L2 回來的失敗原文（含金鑰樣態、HTTP 狀態）不得上一般畫面。"""
    at = _run(monkeypatch, ms.view(us="error"))
    shown = _page_visible(at)
    assert "secret-token-abc123" not in shown and "HTTP 429" not in shown


def test_render_path_negative_control_turns_red_when_a_leak_is_injected(monkeypatch):
    """負控：把「尚未設定」的『哪一項』改成設定名稱 → 渲染路徑偵測必須轉紅（證明渲染守衛不是空掃）。"""
    view, table, state = SCENARIOS["no_fred_key"]()
    clean = leaks(_page_visible(_run(monkeypatch, view, table, state={**state, mkt.KEY_RATES: "credit_spread_pct"})))
    assert clean == []
    monkeypatch.setattr(mkt, "not_configured_html", lambda: "⛔ 尚未設定：" + "FRED" + "_API_" + "KEY")
    at = _run(monkeypatch, view, table, state={**state, mkt.KEY_VIEW: "us10y", mkt.KEY_RATES: "credit_spread_pct"})
    assert any("FRED" in hit for hit in leaks(_page_visible(at)))


def test_not_configured_item_is_a_human_readable_data_class_not_a_setting_name():
    item = W.text("not_configured_item")
    assert item == "利率資料來源" and leaks(item) == []
    html = mkt.not_configured_html()
    assert visible_text(html).replace(" ", "") == "⛔尚未設定：利率資料來源"
