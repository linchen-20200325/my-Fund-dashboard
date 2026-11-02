# -*- coding: utf-8 -*-
"""Design token 命名守衛（批 2b；80 第 5 節；NG-4 A）。純讀檔，不依賴 conftest fixture。

1. 80 第 5 節表格點名的 token 名字全部存在（`state.empty.*` 以前綴對）；名字格式為點分隔小寫；不重複。
2. **值一律 None**（token 數值屬內部決定、視覺待重建）；80 第 5 節的建議尺度只記在 `proposed`，且逐字對得上 80。
3. chip token 與 `StatusChip.kind` 一致；`color.tone.*` 與規則表 tone 鍵一致；`color.status.*` 涵蓋規則表每一列已核准者、
   指向正確的 tone，且不是色碼。
"""
from __future__ import annotations

import re

import ui_v3_guard_lib as lib
from shared.ui_semantics import rules
from ui_v3.design import tokens
from ui_v3.viewmodels import components

DOC_80 = (lib.ROOT / rules.DOC_80).read_text(encoding="utf-8")
SECTION_5 = DOC_80[DOC_80.index("## 5. Design Contract"):DOC_80.index("## 6. View Model Contract")]


def test_token_names_are_dotted_lowercase_and_unique():
    assert len(tokens.TOKEN_NAMES) == len(set(tokens.TOKEN_NAMES))
    for name in tokens.TOKEN_NAMES:
        assert re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z0-9_]+)+", name), name


def test_every_token_named_in_80_section_5_exists():
    named = set(re.findall(r"`([a-z]+(?:\.[a-z0-9*]+)+)`", SECTION_5))
    assert {"space.1", "type.metric", "chip.attention", "nav.bottom", "state.empty.*"} <= named
    for name in named:
        if name.endswith(".*"):
            assert any(t.startswith(name[:-1]) for t in tokens.TOKEN_NAMES), name
        else:
            assert name in tokens.TOKENS, name


def test_no_token_has_a_value_yet():
    assert all(t.value is None for t in tokens.TOKENS.values())


def test_proposed_scales_are_verbatim_from_80_and_not_applied():
    for name in ("space.1", "space.2", "space.3", "space.4", "space.6", "space.8", "gutter.mobile"):
        assert f"`{name}`＝{tokens.TOKENS[name].proposed}" in SECTION_5, name
    sizes = "／".join(tokens.TOKENS[f"type.{n}"].proposed for n in ("page", "section", "metric", "body", "caption"))
    assert f"（建議 {sizes}）" in SECTION_5
    assert "建議尺度，屬提案" in SECTION_5


def test_every_token_carries_a_source():
    assert all(t.source.strip() for t in tokens.TOKENS.values())


def test_chip_tokens_match_status_chip_kinds():
    assert tokens.CHIP_TOKEN_KINDS == components.CHIP_KINDS
    assert {f"chip.{k}" for k in components.CHIP_KINDS} <= set(tokens.TOKENS)


def test_color_tokens_follow_rules_table_tones():
    assert tokens.TONE_KEYS == tuple(rules.TONES)
    approved = {e.key: e.tone for e in rules.ENTRIES.values() if not e.is_pending}
    assert tokens.STATUS_TONES == approved
    for key, tone in approved.items():
        token = tokens.TOKENS[f"color.status.{key}"]
        assert token.refers_to == f"color.tone.{tone}" and token.refers_to in tokens.TOKENS
    for e in rules.pending_entries():
        assert f"color.status.{e.key}" not in tokens.TOKENS  # 字樣未核准的列不配色
