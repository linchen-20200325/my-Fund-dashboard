# -*- coding: utf-8 -*-
"""Preview 暫時字樣守衛（BL-0536 rendering 批）：暫時字樣不得冒充已核准字樣、不得進規則表、畫面輸出要能被機器辨識。"""
from __future__ import annotations

import re

import pytest

from shared.ui_semantics import rules
from ui_v3.viewmodels import preview_wording as W


def test_pending_wording_is_nonempty_unique_and_all_pending():
    assert len(W.PREVIEW_PENDING_WORDING) > 30
    for key, item in W.PREVIEW_PENDING_WORDING.items():
        assert item.key == key and item.text.strip() and item.source.strip()
        assert item.status == W.STATUS_PENDING


# 序列名稱「VIX」（沿用 ui_v2，未核准）與檢視標籤「VIX」（客戶 2026-11-03 已核准）是兩個角色、字面剛好相同。
_SAME_LITERAL_DIFFERENT_ROLE = frozenset({"series_vix", "fact_vix"})


def test_approved_and_pending_wording_never_share_a_key():
    """已核准的鍵只在規則表；暫時字樣表不得留同鍵（單一來源，不得兩處各寫一份）。"""
    assert not set(rules.APPROVED_WORDING) & set(W.PREVIEW_PENDING_WORDING)
    assert len(rules._APPROVED_LIST) == len(rules.APPROVED_WORDING)   # 無重複鍵


def test_no_pending_text_equals_or_embeds_an_approved_registry_wording():
    """暫時字樣不得與規則表任一已核准字樣相同（否則等於把它當成已核准）；已核准的符號字首（◆◇⬜⛔◷）也不得出現在暫時字樣內。"""
    approved = {e.wording for e in rules.ENTRIES.values() if e.wording and not e.is_pending}
    approved |= {a.text for a in rules.APPROVED_WORDING.values()}
    symbols = {e.symbol for e in rules.ENTRIES.values() if e.symbol}
    for key, item in W.PREVIEW_PENDING_WORDING.items():
        if key in _SAME_LITERAL_DIFFERENT_ROLE:   # 文字巧合相同、角色不同（見下）；不是把暫時字樣冒充已核准
            continue
        assert item.text not in approved, key
        assert not any(sym in item.text for sym in symbols), (key, item.text)


def test_registry_has_no_pending_state_entry_left_and_chart_empty_is_approved_plain_wording():
    """客戶 2026-11-03 裁示後：規則表狀態列已無 PENDING；整張圖無資料字樣是正式純文字字樣（不再標 pending）。"""
    assert rules.pending_entries() == ()
    assert "chart_empty" not in rules.ENTRIES and "chart_empty" not in W.PREVIEW_PENDING_WORDING
    assert rules.approved("chart_empty").text == "此圖目前沒有可畫的資料"
    html = W.span("chart_empty")
    assert "data-pending-wording" not in html and "uv3-pending" not in html and "此圖目前沒有可畫的資料" in html


def test_registry_module_does_not_import_preview_wording():
    import ast
    from pathlib import Path
    tree = ast.parse(Path(rules.__file__).read_text(encoding="utf-8"))
    mods = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | \
           {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m.split(".")[0] == "ui_v3" for m in mods), mods


def test_pending_span_is_machine_identifiable_and_escaped():
    html = W.pending_span("period_label")
    assert 'data-pending-wording="period_label"' in html and 'class="uv3-pending"' in html
    approved = W.span("base_chip", date="2026-01-02")   # 正式字樣：純文字、不標 pending
    assert approved == "基準日 2026-01-02＝100" and "pending" not in approved
    with pytest.raises(KeyError):
        W.pending_span("base_chip", date="2026-01-02")   # 已核准的鍵不得再走 pending 路徑
    assert "&lt;" in W.pending_span("secondary_latest", value="<x>", unit="")
    assert "&lt;" in W.span("data_date_line", label="<x>", date="2026-01-02", days=1)   # 正式字樣的欄位值同樣跳脫
    assert "<b>" not in W.span_html("single_fallback", reason="&lt;b&gt;") and "&lt;b&gt;" in W.span_html("single_fallback", reason="&lt;b&gt;")


def test_text_formatting_fails_loud_on_unknown_key_or_missing_field():
    with pytest.raises(KeyError):
        W.text("nope")
    with pytest.raises(KeyError):
        W.text("data_date_line", label="台股", date="2026-01-02")   # 缺 days
    with pytest.raises(ValueError):
        W.PendingWording("x", "t", "s", status="approved")


def test_duplicate_keys_are_rejected():
    item = W.PendingWording("k", "t", "s")
    with pytest.raises(ValueError):
        W._index((item, item))


def test_pending_wording_module_is_pure_data_no_streamlit_no_services():
    import ast
    from pathlib import Path
    tree = ast.parse(Path(W.__file__).read_text(encoding="utf-8"))
    mods = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | \
           {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    bad = [m for m in mods if re.match(r"(streamlit|services|shared|ui_v2|ui)\b", m) and m != "shared.ui_semantics"]
    assert not bad, bad   # 只准讀規則表（已核准字樣的單一來源）


# ───────── mkt.py 不得硬寫畫面中文字樣（BL-0536 稽核 non-blocker 2/3） ─────────

_CJK = re.compile(r"[　-鿿＀-￯]")
# 明確白名單：規則表的代入佔位符（取代用）與一則內部 raise 訊息（不上畫面）。
_CJK_LITERAL_WHITELIST = frozenset({"<中文資料類>", "<哪一項>", "status_html 只處理非 ok 狀態："})


def _hardcoded_cjk_literals(source: str) -> list:
    import ast
    tree = ast.parse(source)
    docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                  and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant)}
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings
            and _CJK.search(n.value) and n.value not in _CJK_LITERAL_WHITELIST]


def test_mkt_page_has_no_hardcoded_cjk_screen_wording():
    from pathlib import Path
    src = Path(__file__).resolve().parents[2].joinpath("ui_v3", "pages", "mkt.py").read_text(encoding="utf-8")
    assert _hardcoded_cjk_literals(src) == []


def test_hardcoded_cjk_scan_negative_control_turns_red():
    """負控：造一段含硬寫中文的副本，掃描必須抓到（證明守衛不是空掃）。"""
    bad = 'def f(x):\n    """文件字串不算"""\n    return f"{x}：取得 ｜ 來源"\n'
    assert _hardcoded_cjk_literals(bad) != []
    assert _hardcoded_cjk_literals('def f():\n    """只有文件字串"""\n    return 1  # 註解中文\n') == []


def test_reason_span_unknown_code_never_leaks_raw_code():
    from ui_v3.pages import mkt
    for code in ("no_source_zzz", "some_internal_code", None, ""):
        html = mkt.reason_span(code)
        assert "<code>" not in html and "some_internal_code" not in html and "no_source_zzz" not in html
        assert html == "原因未明" and "pending" not in html   # 正式字樣（客戶 2026-11-03）：純文字、不標 pending


def test_reason_span_known_codes_have_own_pending_wording():
    from ui_v3.pages import mkt
    for code, key in mkt._REASON_WORDING.items():
        assert key in W.PREVIEW_PENDING_WORDING or key in rules.APPROVED_WORDING
        html = mkt.reason_span(code)
        visible = re.sub(r"<[^>]+>", "", html)   # 只看看得見的字（屬性裡的字樣鍵不算）
        assert "<code>" not in html and code not in visible
        if key in W.PREVIEW_PENDING_WORDING:
            assert f'data-pending-wording="{key}"' in html
        else:
            assert "data-pending-wording" not in html and html == rules.APPROVED_WORDING[key].text
    assert {"no_source", "no_observation"} <= set(mkt._REASON_WORDING)
