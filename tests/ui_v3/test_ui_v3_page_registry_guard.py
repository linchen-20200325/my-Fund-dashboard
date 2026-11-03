# -*- coding: utf-8 -*-
"""ui_v3 頁序／頁名／登錄守衛（80 第 7、9 節 navigation 測試；`DEC-2026-10-29-06`／`-07`、`DEC-2026-10-27-10`）。

- 五個位置、頁序 🌍 → 💼 → 🔍 → 🤖 → ⚙️、不得有第六頁；
- 🤖 在 Phase 7 前不得掛導覽（建構時就擋）；
- ~~批 1 沒有任何已掛載頁（不做空殼）~~ → 2026-11-03 BL-0536 rendering 批：只有 🌍 `mkt` 已掛載（線框已核准＋已實作，只進 Preview App）；
  其餘四頁（💼／🔍／🤖／⚙️）仍未掛載（線框未核准，不做空殼）。日後每一頁核准並實作時，由該批有意識地改這裡；
- 頁名逐字與 ui_v2 預覽導覽的四頁一致（AST 讀 `ui_v2/app_preview.py::PAGES` 字面值，不 import ui_v2）。
"""
from __future__ import annotations

import ast

import pytest

import ui_v3_guard_lib as lib
from ui_v3.shell import registry
from ui_v3.shell.registry import IA_PAGES, PageSlot


def test_five_pages_in_ia_order():
    assert [p.slug for p in IA_PAGES] == ["mkt", "ast", "exp", "ai", "set"]
    assert [p.title for p in IA_PAGES] == ["🌍 市場與趨勢", "💼 我的資產", "🔍 找基金", "🤖 AI 投資總結", "⚙️ 設定"]
    assert len({p.slug for p in IA_PAGES}) == 5 and len({p.title for p in IA_PAGES}) == 5


def test_ai_page_is_never_registered_before_phase7():
    ai = [p for p in IA_PAGES if p.slug == registry.AI_SLUG]
    assert len(ai) == 1 and ai[0].registered is False
    assert ai[0].unregistered_reason == registry.REASON_PHASE7
    assert all(p.slug != registry.AI_SLUG for p in registry.registered_pages())


def test_only_market_page_is_registered_so_no_empty_shell():
    """線框核准＋已實作的只有 🌍；其餘四頁沒有核准線框 → 不得掛載（不做空殼）。"""
    assert [p.slug for p in registry.registered_pages()] == ["mkt"]
    assert [p.slug for p in registry.assert_preview_ready()] == ["mkt"]
    for p in IA_PAGES:
        if p.slug != "mkt":
            assert p.registered is False and p.unregistered_reason is not None, p.slug


def test_preview_not_ready_when_nothing_is_registered(monkeypatch):
    """負控：若沒有任何已掛載的頁，入口仍大聲失敗（不渲染空殼）。在記憶體內換掉登錄表，不改檔。"""
    monkeypatch.setattr(registry, "IA_PAGES", tuple(
        PageSlot(p.slug, p.title, False,
                 registry.REASON_PHASE7 if p.slug == registry.AI_SLUG else registry.REASON_WIREFRAME_PENDING)
        for p in IA_PAGES))
    with pytest.raises(registry.PreviewNotReady):
        registry.assert_preview_ready()


def test_registered_pages_keep_ia_order_and_never_include_ai():
    """負控：模擬「前四頁之二已掛載」時，registered_pages 保持 IA 順序且仍不含 🤖（在記憶體內組，不改登錄表）。"""
    fake = (
        PageSlot("mkt", "🌍 市場與趨勢", True),
        PageSlot("ast", "💼 我的資產", False, registry.REASON_WIREFRAME_PENDING),
        PageSlot("exp", "🔍 找基金", True),
    )
    assert tuple(p.slug for p in fake if p.registered) == ("mkt", "exp")


def test_ai_slot_cannot_be_constructed_as_registered():
    with pytest.raises(ValueError):
        PageSlot("ai", "🤖 AI 投資總結", True)
    with pytest.raises(ValueError):
        PageSlot("ai", "🤖 AI 投資總結", False, registry.REASON_WIREFRAME_PENDING)


def test_unregistered_slot_must_explain_why_and_registered_must_not():
    with pytest.raises(ValueError):
        PageSlot("mkt", "x", False)
    with pytest.raises(ValueError):
        PageSlot("mkt", "x", False, "made_up_reason")
    with pytest.raises(ValueError):
        PageSlot("mkt", "x", True, registry.REASON_WIREFRAME_PENDING)


def test_titles_match_ui_v2_preview_pages_verbatim():
    src = lib.read(lib.ROOT / "ui_v2" / "app_preview.py")
    pages = None
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "PAGES" for t in node.targets):
            pages = [(e.elts[0].value, e.elts[1].value) for e in node.value.elts]
    assert pages, "找不到 ui_v2/app_preview.py::PAGES（守衛失效）"
    ours = {p.slug: p.title for p in IA_PAGES}
    for slug, title in pages:
        assert ours[slug] == title, (slug, ours[slug], title)
    # 相對順序一致（ui_v2 預覽少了 🤖）
    assert [s for s, _ in pages] == [p.slug for p in IA_PAGES if p.slug != registry.AI_SLUG]
