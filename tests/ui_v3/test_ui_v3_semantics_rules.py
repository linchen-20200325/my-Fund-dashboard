# -*- coding: utf-8 -*-
"""呈現規則資料表守衛（批 2b；80 第 3.3 節 (c)、第 6 節；NG-4 A）。純讀檔＋AST，不依賴 conftest fixture。

本機執行：
    /root/.local/bin/pytest tests/ui_v3 -q --noconftest -p no:cacheprovider

守什麼：
1. **字樣逐字**：規則表每一列的字樣，必須逐字出現在它自己列出的每一份出處文件（`doc_refs`）裡；
   符號只准 44／80 已落字的 ◆ ◇ ⬜ ⛔ ◷；tone 的中文色名必須是 44 已用的名字。
2. **β precedence**：順序逐字等於 `DEC-2026-10-30-04` 客戶原話，且與 `ui_v2/status_class.py` 的嚴重度順序同序（AST 讀，不 import ui_v2）。
3. **行動詞不新增**：`ACTION_WORDS` 逐字、依序等於 67 第 2.1～2.6 節標題；ui_v3 的 `ACTION_VOCABULARY` 就是同一份。
4. **tone 是名字不是色碼**；非中性 tone 必有符號＋字樣（顏色不是唯一訊息）。
5. **單一來源**：ui_v3 的 `MISSING_TEXT`、chip kind、status、freshness 與規則表一致。
6. **純度**：`shared/ui_semantics/` 只用標準函式庫、不 import 任何專案層、無動態 import、import 零副作用（負控在記憶體內）。
"""
from __future__ import annotations

import ast
import re

import pytest

import ui_v3_guard_lib as lib
from shared.ui_semantics import rules
from ui_v3.viewmodels import action_slot, common, components

ROOT = lib.ROOT
SEMANTICS_DIR = ROOT / "shared" / "ui_semantics"
APPROVED_SYMBOLS = {"◆", "◇", "⬜", "⛔", "◷"}


def _doc(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _section(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i:text.index(end, i + len(start))]


APPROVED = [e for e in rules.ENTRIES.values() if not e.is_pending and e.wording is not None]


# ─────────────── 1. 字樣逐字 ───────────────
@pytest.mark.parametrize("entry", APPROVED, ids=lambda e: e.key)
def test_every_wording_appears_verbatim_in_each_cited_doc(entry):
    assert entry.doc_refs, entry.key
    for rel in entry.doc_refs:
        assert entry.wording in _doc(rel), f"{entry.key}: {entry.wording!r} 不在 {rel}"


def test_symbols_are_only_the_approved_five():
    line = next(l for l in _doc(rules.DOC_80).splitlines() if l.startswith("| 符號 |"))
    assert set(re.findall("[◆◇⬜⛔◷]", line)) == APPROVED_SYMBOLS  # 80 §0：只用 44 已落字的五個
    used = {e.symbol for e in rules.ENTRIES.values() if e.symbol is not None}
    assert used <= APPROVED_SYMBOLS
    doc44 = _doc(rules.DOC_44)
    assert all(s in doc44 for s in used)


def test_approved_symbol_meanings_match_79_missing_contract_table():
    """79 §11 表格：五個符號各自對應的字樣（逐字）。"""
    table = _section(_doc(rules.DOC_79), "## 11. Missing Contract", "## 12.")
    for key, wording in (("missing", "◇ 資料未備"), ("undetermined", "⬜ 無法判定"), ("fetch_failed", "⛔ 取數失敗"),
                         ("stale", "◷ 不是最新"), ("attention", "◆ 需要注意")):
        assert rules.entry(key).wording == wording
        assert f"| `{wording}" in table, wording


def test_tone_names_are_the_ones_44_uses():
    card_table = _section(_doc(rules.DOC_44), "### 5.1 卡片 `Card`", "### 5.2")
    for zh in rules.TONES.values():
        assert zh in card_table, zh


def test_tone_by_state_follows_44_and_67():
    assert rules.entry("ok").tone == rules.TONE_NEUTRAL            # 44 §5.1 ok：中性文字色
    assert rules.entry("attention").tone == rules.TONE_NEUTRAL     # 44 之七其三：◆ 不著色
    assert rules.entry("missing").tone == rules.TONE_GREY          # 44 §5.1 資料未備：灰
    assert rules.entry("not_applicable").tone == rules.TONE_GREY   # 44 §5.1 業務例外：黃→灰
    assert rules.entry("fetch_failed").tone == rules.TONE_RED      # 44 §5.1 系統錯誤：紅
    assert rules.entry("stale").tone == rules.TONE_YELLOW          # 44 之七其四：◷ 顏色照舊（黃）
    assert rules.entry("not_configured").tone == rules.TONE_RED    # 44 之十二其二第 1 條：⛔、紅色照舊
    for key in ("undetermined", "threshold_pending", "user_param_unset"):  # 67 §2.6／44 之七其四：⬜ 族為灰
        assert rules.entry(key).tone == rules.TONE_GREY
    for key in ("threshold_pending", "user_param_unset"):          # 這兩列的灰是推論，必須明標
        assert "推論" in rules.entry(key).note and "推論" in rules.entry(key).source


def test_not_configured_and_user_param_unset_are_44_concepts():
    """44 之十二其二第 1 條：設定沒設（沒有取數）→ `⛔ 尚未設定：<哪一項>`；使用者自己的參數沒填 → `⬜ 未設定`（字面照舊）。"""
    doc44 = _doc(rules.DOC_44)
    clause = next(l for l in doc44.splitlines() if l.startswith("1. **規則**：成因是某個設定沒設"))
    assert rules.NOT_CONFIGURED_FORM in clause and "⛔ 取數失敗" in clause and "「⬜ 未設定」" in clause
    assert rules.entry("not_configured").wording == "⛔ 尚未設定"
    assert rules.NOT_CONFIGURED_FORM.startswith(rules.entry("not_configured").wording + "：")
    set3 = next(l for l in doc44.splitlines() if l.startswith("| **空狀態** | 全表為空 → 逐鍵列出且目前值欄皆"))
    assert rules.entry("user_param_unset").wording in set3
    # DEC-2026-10-20-01：使用者參數留空不是資料狀態 → 不進 β、不被任何 status／chip 對照叫出
    note = rules.entry("user_param_unset").note
    assert "DEC-2026-10-20-01" in note and "β" in note
    assert "DEC-2026-10-20-01" in _doc(rules.DOC_DECISIONS)
    assert all(lvl.entry_key != "user_param_unset" for lvl in rules.BETA_LEVELS)
    assert "user_param_unset" not in set(rules.STATUS_TO_KEY.values()) | set(rules.CHIP_KIND_TO_KEY.values())


def test_fetch_failed_composite_forms_are_verbatim_in_44():
    doc44 = _doc(rules.DOC_44)
    for form in (rules.FETCH_FAILED_SCREEN_FORM, rules.FETCH_FAILED_SAME_SOURCE_TEXT, rules.NOT_CONFIGURED_FORM):
        assert form in doc44, form
        assert form.startswith("⛔ ")
    assert "44 §5.5" in rules.COMPOSITE_FORMS_SOURCE


def test_failed_with_not_configured_reason_never_renders_fetch_failed():
    assert rules.entry_for_status("failed").key == "fetch_failed"
    assert rules.entry_for_status("failed", reason_code="source_timeout").key == "fetch_failed"
    found = rules.entry_for_status("failed", reason_code=rules.REASON_NOT_CONFIGURED)
    assert found.key == "not_configured" and "取數失敗" not in found.wording
    for status in ("ok", "missing", "stale", "undetermined"):
        with pytest.raises(ValueError):
            rules.entry_for_status(status, reason_code=rules.REASON_NOT_CONFIGURED)


def test_every_entry_level_and_constant_carries_a_source_citation():
    cite = re.compile(r"(\d\d\s*§|§\d|第.+節|DEC-\d{4}-\d{2}-\d{2}-\d{2}|BL-\d{4})")
    for e in rules.ENTRIES.values():
        assert cite.search(e.source), e.key
    for level in rules.BETA_LEVELS:
        assert cite.search(level.source), level.key
    for text in (rules.TONES_SOURCE, rules.ACTION_WORDS_SOURCE, rules.ACTION_UNDETERMINED_FORM_SOURCE, rules.BETA_SOURCE,
                 rules.COMPOSITE_FORMS_SOURCE):
        assert cite.search(text), text


def test_pending_mechanism_still_blocks_unapproved_wording_and_beta_gaps_stay_explicit():
    """狀態列已無 PENDING（`chart_empty` 於 2026-11-03 客戶裁示後移進 `APPROVED_WORDING`）；
    但 PENDING 機制本身仍要擋住日後的未核准字樣，且 β 頁級字樣缺口仍明列。"""
    assert rules.pending_entries() == ()
    pending = rules.SemanticEntry("x", None, rules.PENDING_WORDING, None, "79 §11", gap="缺口出處")   # 機制仍可用
    assert pending.is_pending
    unworded = [lvl for lvl in rules.BETA_LEVELS if lvl.entry_key is None]
    assert {lvl.key for lvl in unworded} == {"no_holding", "partial", "normal"}
    assert all("wireframe Gate" in lvl.wording_gap for lvl in unworded)
    with pytest.raises(ValueError):
        rules.PrecedenceLevel("x", "x", None)
    reachable = set(rules.STATUS_TO_KEY.values()) | set(rules.CHIP_KIND_TO_KEY.values()) | {
        k for k in rules.FRESHNESS_TO_KEY.values() if k}
    assert reachable <= set(rules.ENTRIES)
    assert "整張圖沒有資料時改用空狀態元件的模板" in _doc(rules.DOC_44)   # 之前 gap 所引的 44 原文仍在（不得被誤讀為已被 44 取代）


# ─────────────── 1b. 純文字正式字樣（客戶 2026-11-03；DEC-2026-11-03-07） ───────────────
@pytest.mark.parametrize("item", list(rules.APPROVED_WORDING.values()), ids=lambda a: a.key)
def test_every_approved_plain_wording_appears_verbatim_in_each_cited_doc(item):
    assert item.doc_refs and item.source.strip()
    for rel in item.doc_refs:
        assert item.ruling_text in _doc(rel), f"{item.key}: {item.ruling_text!r} 不在 {rel}"


def test_customer_ruling_wording_is_in_decisions_and_evidence_and_44_wording_is_in_44():
    from_44 = {k for k, a in rules.APPROVED_WORDING.items() if a.doc_refs == (rules.DOC_44,)}
    assert from_44 == {"fact_vix", "fact_credit_spread", "fact_leading", "fact_coincident", "fact_policy_rate", "fact_fx"}
    for key, item in rules.APPROVED_WORDING.items():
        if key in from_44:
            continue
        evidence = rules.EVIDENCE_SHELL_RULING if key.startswith("shell_") else rules.EVIDENCE_WORDING_RULING   # Shell 字樣出自 DEC-2026-11-03-11 的裁示檔
        assert evidence in item.doc_refs and rules.DOC_DECISIONS in item.doc_refs, key


def test_approved_plain_wording_view_labels_and_first_screen_fields_match_the_ruling_lines():
    evidence = _doc(rules.EVIDENCE_WORDING_RULING)
    views = "／".join(rules.approved(k).text for k in ("view_compare", "view_vix", "view_us10y", "view_us2y"))
    fields = "／".join(rules.approved(k).text for k in ("field_market_state", "field_attention", "evidence_label",
                                                       "freshness_label"))
    assert f"| 檢視標籤 | {views} |" in evidence and views == "比較／VIX／美10Y／美2Y"   # 無空格
    assert f"| 首屏欄位 | {fields} |" in evidence
    full = f"{rules.approved('base_chip').ruling_text}；{rules.approved('frequency_line').text}"
    assert f"「{full}」" in evidence   # 歸一化揭露整句＝兩段以「；」相連
    assert "頻率：日" in rules.approved("frequency_line").text and "頻率 日" not in rules.approved("frequency_line").text


def test_approved_plain_wording_has_no_engineering_terms_and_no_symbols():
    for item in rules.APPROVED_WORDING.values():
        assert not re.search(r"aggregation rule|[A-Z]+_[A-Z_]+|Traceback|Exception", item.text), item.key
        assert not any(sym in item.text for sym in APPROVED_SYMBOLS), item.key   # 符號只屬狀態列
    assert "aggregation rule" not in rules.approved("hero_sentence").text


def test_approved_wording_keys_do_not_collide_with_state_entry_keys_and_table_is_read_only():
    assert not set(rules.APPROVED_WORDING) & set(rules.ENTRIES)
    with pytest.raises(TypeError):
        rules.APPROVED_WORDING["x"] = None
    with pytest.raises(KeyError):
        rules.approved("nope")
    with pytest.raises(ValueError):
        rules.ApprovedWording("x", " ", "y")
    with pytest.raises(ValueError):
        rules.ApprovedWording("x", "t", "t", doc_refs=())


def test_rules_table_is_read_only_at_runtime():
    for mapping in (rules.ENTRIES, rules.TONES, rules.STATUS_TO_KEY, rules.FRESHNESS_TO_KEY, rules.CHIP_KIND_TO_KEY,
                    rules.BETA_RANK):
        with pytest.raises(TypeError):
            mapping["x"] = None
    with pytest.raises(Exception):
        rules.entry("missing").wording = "x"  # frozen dataclass


def test_entry_rejects_invented_or_inconsistent_rows():
    with pytest.raises(ValueError):  # 非中性 tone 卻沒符號（只靠顏色）
        rules.SemanticEntry("x", None, None, rules.TONE_RED, "79 §11")
    with pytest.raises(ValueError):  # 色碼當 tone
        rules.SemanticEntry("x", "◇", "◇ 資料未備", "#9e9e9e", "79 §11", doc_refs=(rules.DOC_79,))
    with pytest.raises(ValueError):  # 字樣不以符號開頭
        rules.SemanticEntry("x", "◇", "資料未備", rules.TONE_GREY, "79 §11", doc_refs=(rules.DOC_79,))
    with pytest.raises(ValueError):  # 有字樣卻沒有出處文件
        rules.SemanticEntry("x", "◇", "◇ 資料未備", rules.TONE_GREY, "79 §11")
    with pytest.raises(ValueError):  # PENDING 沒寫缺口
        rules.SemanticEntry("x", None, rules.PENDING_WORDING, None, "79 §11")
    with pytest.raises(ValueError):  # 沒有 source
        rules.SemanticEntry("x", None, None, rules.TONE_NEUTRAL, " ")


# ─────────────── 2. β precedence ───────────────
def test_beta_order_is_the_client_quote_verbatim():
    assert " > ".join(level.beta_label for level in rules.BETA_LEVELS) == rules.BETA_QUOTE
    assert rules.BETA_QUOTE in _doc(rules.DOC_DECISIONS)
    assert [lvl.key for lvl in rules.BETA_LEVELS] == [
        "fetch_failed", "no_holding", "attention", "missing", "undetermined", "partial", "normal"]
    for level in rules.BETA_LEVELS:
        if level.entry_key is not None:
            assert rules.entry(level.entry_key).symbol in level.beta_label or level.beta_label in rules.entry(
                level.entry_key).wording


def test_beta_order_matches_ui_v2_status_class_severity_order():
    tree = ast.parse((ROOT / "ui_v2" / "status_class.py").read_text(encoding="utf-8"))
    order = next(n.value for n in tree.body if isinstance(n, ast.Assign)
                 and any(getattr(t, "id", "") == "SEVERITY_ORDER" for t in n.targets))
    assert [e.id for e in order.elts] == ["ERROR", "NO_HOLDING", "ATTENTION", "MISSING", "UNSET", "PARTIAL", "NORMAL"]
    assert len(order.elts) == len(rules.BETA_LEVELS)


def test_resolve_precedence_takes_the_heaviest_pairwise():
    keys = [lvl.key for lvl in rules.BETA_LEVELS]
    for i, heavy in enumerate(keys):
        for light in keys[i:]:
            assert rules.resolve_precedence([light, heavy]) == heavy
            assert rules.resolve_precedence([heavy, light]) == heavy
    assert rules.resolve_precedence(["normal", "missing", "normal"]) == "missing"
    assert rules.resolve_precedence(["normal", "partial"]) == "partial"   # 只評估一部分不得被正常遮蔽


def test_resolve_precedence_never_infers_normal_from_nothing_or_unknown():
    with pytest.raises(ValueError):
        rules.resolve_precedence([])
    with pytest.raises(KeyError):
        rules.resolve_precedence(["normal", "safe"])


def test_resolve_precedence_documents_the_bl0411_production_gate():
    doc = rules.resolve_precedence.__doc__
    assert "BL-0411" in doc and "不得" in doc
    assert "先修 BL-0411，再允許 P3 production 上線" in _doc(rules.DOC_DECISIONS)


# ─────────────── 3. 行動詞不新增 ───────────────
def test_action_words_equal_67_section_2_headings():
    text = _doc(rules.DOC_67)
    headings = re.findall(r"^### 2\.([1-6]) (\S+)$", text, flags=re.M)
    assert [n for n, _ in headings] == ["1", "2", "3", "4", "5", "6"]
    assert tuple(w for _, w in headings) == rules.ACTION_WORDS
    assert rules.ACTION_UNDETERMINED_FORM in text
    assert rules.ACTION_UNDETERMINED_FORM.startswith(rules.entry("undetermined").wording)


def test_ui_v3_action_vocabulary_is_the_rules_table_tuple():
    assert action_slot.ACTION_VOCABULARY is rules.ACTION_WORDS
    assert action_slot.ACTION_UNDETERMINED == "無法判定"
    assert len(set(rules.ACTION_WORDS)) == 6


# ─────────────── 4. tone 是名字、顏色不是唯一訊息 ───────────────
def test_tone_keys_are_names_not_hex():
    """規則表（`rules.py`）的 tone 永遠只是名字，沒有色碼。

    G3 批（客戶核准候選 B 色票）改前：本測試連 `ui_v3/design/tokens.py` 也要求無色碼（因為 token 值一律 None）。
    現在核准色值住在 token 表（`tokens.py`；唯一真相源），所以該檔改為「語意層仍只指向名字」：`color.status.*` 一律只有
    `refers_to`（指向 tone 鍵）、自己沒有值、不是色碼；色碼只准出現在核准的 PALETTE／TONE_VALUES（由 `test_ui_v3_design_tokens.py` 逐值鎖）。"""
    assert all(re.fullmatch(r"[a-z]+", k) for k in rules.TONES)
    src = (SEMANTICS_DIR / "rules.py").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b|rgba?\(|hsla?\(", src)
    from ui_v3.design import tokens
    for name, token in tokens.TOKENS.items():
        if name.startswith("color.status."):
            assert token.value is None and token.refers_to and token.refers_to.startswith("color.tone."), name


def test_non_neutral_tone_always_has_symbol_and_wording():
    for e in rules.ENTRIES.values():
        if not e.is_pending and e.tone != rules.TONE_NEUTRAL:
            assert e.symbol and e.wording and e.wording.startswith(e.symbol + " "), e.key
    for kind in components.CHIP_KINDS:
        if kind != "neutral":
            found = rules.entry_for_chip_kind(kind)
            assert found.symbol and found.wording, kind


# ─────────────── 5. 單一來源／一致性 ───────────────
def test_missing_text_single_source_and_value_unchanged():
    assert common.MISSING_TEXT == "◇ 資料未備"
    assert common.MISSING_TEXT is rules.MISSING_TEXT
    assert rules.MISSING_TEXT == rules.entry("missing").wording
    assert components.MissingItem.PRESENTATION == rules.MISSING_TEXT


def test_chip_kinds_map_onto_rules_keys():
    assert tuple(rules.CHIP_KIND_TO_KEY) == components.CHIP_KINDS
    for kind in components.CHIP_KINDS:
        assert rules.entry_for_chip_kind(kind).key == rules.CHIP_KIND_TO_KEY[kind]


def test_status_and_freshness_keys_match_view_model_contract():
    assert set(rules.STATUS_TO_KEY) == set(common.STATUSES)
    assert set(rules.FRESHNESS_TO_KEY) == set(common.FRESHNESS_STATES)
    assert rules.entry_for_status("missing").wording == common.MISSING_TEXT
    assert rules.entry_for_status("failed").key == "fetch_failed"
    assert rules.entry_for_freshness("fresh") is None
    assert rules.entry_for_freshness("undetermined").wording == "⬜ 門檻待裁示"
    for bad in (lambda: rules.entry_for_status("safe"), lambda: rules.entry_for_freshness("ok"),
                lambda: rules.entry_for_chip_kind("good"), lambda: rules.entry("hold")):
        with pytest.raises(KeyError):
            bad()


# ─────────────── 6. 純度（shared/ui_semantics） ───────────────
def semantics_violations(rel: str, source: str) -> list:
    tree = ast.parse(source)
    bad = []
    for module in lib.imports_of(tree, "shared.ui_semantics"):
        root = module.split(".")[0]
        if module.startswith("__future__"):
            continue
        if module == "shared.ui_semantics" or module.startswith("shared.ui_semantics."):
            continue
        if root not in lib.STDLIB:
            bad.append(f"非標準函式庫 {module}")
        elif root in lib.NET_ROOTS or root in lib.DYNAMIC_IMPORT_MODULES or root in lib.BACKDOOR_MODULES or root == "os":
            bad.append(f"I/O／動態 import 模組 {module}")
    bad += [f"動態 import／eval 寫法 {u}" for u in lib.dynamic_import_uses(tree)]
    bad += [f"模組層副作用 {v}" for v in lib.module_level_side_effects(source)]
    return bad


def test_semantics_population_is_not_empty():
    files = sorted(p.name for p in SEMANTICS_DIR.glob("*.py"))
    assert files == ["__init__.py", "rules.py"]


def test_semantics_package_is_pure_stdlib_and_side_effect_free():
    hits = []
    for path in sorted(SEMANTICS_DIR.rglob("*.py")):
        hits += [f"{lib.rel_of(path)}: {v}" for v in semantics_violations(lib.rel_of(path), lib.read(path))]
    assert not hits, "\n".join(hits)


@pytest.mark.parametrize("source", [
    "import streamlit as st",
    "from services.v2_tables import contract",
    "from ui_v3.viewmodels import MISSING_TEXT",
    "import ui_v2.symbols",
    "from ui.helpers import x",
    "from repositories.macro import yf",
    "from shared import colors",
    "import pandas",
    "import requests",
    "import os",
    "import importlib",
    "x = __import__('os')",
    "print('side effect')",
])
def test_negative_control_semantics_purity_turns_red(source):
    assert semantics_violations("shared/ui_semantics/x.py", source)


def test_semantics_purity_accepts_stdlib_and_own_package():
    src = ('"""doc"""\nfrom __future__ import annotations\nfrom dataclasses import dataclass\n'
           'from typing import Dict\nfrom shared.ui_semantics.rules import ENTRIES\nX = 1\n')
    assert semantics_violations("shared/ui_semantics/x.py", src) == []
