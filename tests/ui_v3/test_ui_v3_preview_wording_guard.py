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


def test_no_pending_text_equals_or_embeds_an_approved_registry_wording():
    """暫時字樣不得與規則表任一已核准字樣相同（否則等於把它當成已核准）；已核准的符號字首（◆◇⬜⛔◷）也不得出現在暫時字樣內。"""
    approved = {e.wording for e in rules.ENTRIES.values() if e.wording and not e.is_pending}
    symbols = {e.symbol for e in rules.ENTRIES.values() if e.symbol}
    for key, item in W.PREVIEW_PENDING_WORDING.items():
        assert item.text not in approved, key
        assert not any(sym in item.text for sym in symbols), (key, item.text)


def test_registry_is_untouched_pending_entries_stay_pending_and_not_filled_in():
    """規則表只放已核准字樣：`chart_empty` 仍是 PENDING；本批不得替它補字（暫時字樣在別處、且標 pending）。"""
    pending = {e.key for e in rules.pending_entries()}
    assert pending == {"chart_empty"}
    assert rules.ENTRIES["chart_empty"].wording == rules.PENDING_WORDING
    with pytest.raises(LookupError):
        rules.entry("chart_empty")
    for item in W.PREVIEW_PENDING_WORDING.values():
        assert item.text != rules.ENTRIES["chart_empty"].gap


def test_registry_module_does_not_import_preview_wording():
    import ast
    from pathlib import Path
    tree = ast.parse(Path(rules.__file__).read_text(encoding="utf-8"))
    mods = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | \
           {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m.split(".")[0] == "ui_v3" for m in mods), mods


def test_pending_span_is_machine_identifiable_and_escaped():
    html = W.pending_span("base_chip", date="2026-01-02", base=100)
    assert 'data-pending-wording="base_chip"' in html and "基準日 2026-01-02＝100" in html
    assert 'class="uv3-pending"' in html
    assert "&lt;" in W.pending_span("single_chart_note", reason="<x>")


def test_text_formatting_fails_loud_on_unknown_key_or_missing_field():
    with pytest.raises(KeyError):
        W.text("nope")
    with pytest.raises(KeyError):
        W.text("base_chip", date="2026-01-02")   # 缺 base
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
    assert not any(re.match(r"(streamlit|services|shared|ui_v2|ui)\b", m) for m in mods), mods
