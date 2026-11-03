# -*- coding: utf-8 -*-
"""依據卡 MKT-1～MKT-3 對照正式規格守衛（BL-0536；規格＝44 第三節 3.1 各塊「來源／規則」欄，72 第 3 節表同）。

對照什麼：每張卡有哪幾個鍵、順序、畫面名稱、小數位數、單位；沒有正式資料的鍵一律 Missing（不補欄位、不補值）。
規格的機器可讀來源：`ui_v2/mkt/logic.py::_CARD_SPECS`（以 AST 讀字面值，不 import ui_v2；ui_v2 已逐字引 44）。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import market_stubs as ms
import ui_v3_guard_lib as lib
from shared.ui_semantics import rules
from ui_v3.adapters import market_page as adapter
from ui_v3.pages import mkt
from ui_v3.viewmodels import preview_wording as W

ROOT = lib.ROOT


def _spec():
    tree = ast.parse((ROOT / "ui_v2" / "mkt" / "logic.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_CARD_SPECS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("_CARD_SPECS not found")


# 44 3.1 的 `indicator_key` → ui_v3 依據卡 label_key
_KEY_TO_LABEL = {"vol_index": "fact_vix", "credit_spread_pct": "fact_credit_spread", "leading_index": "fact_leading",
                 "coincident_index": "fact_coincident", "policy_rate_pct": "fact_policy_rate",
                 "fx_twd_per_usd": "fact_fx"}


def _model():
    return adapter.build_market_page(ms.view(), ms.table(), period="1Y")


def test_each_card_has_the_formal_keys_in_the_formal_order_with_the_formal_names():
    spec = _spec()
    assert set(spec) == {"MKT-1", "MKT-2", "MKT-3"}
    model = _model()
    assert [c.code for c in model.evidence_cards] == ["MKT-1", "MKT-2", "MKT-3"]
    for card in model.evidence_cards:
        expected = spec[card.code]
        assert [f.label_key for f in card.facts] == [_KEY_TO_LABEL[row[0]] for row in expected], card.code
        assert [W.text(f.label_key) for f in card.facts] == [row[1] for row in expected], card.code


def test_formal_names_are_cited_from_44_and_card_titles_name_the_44_blocks():
    doc44 = (ROOT / "docs" / "v2" / "44_fund_ui_ssot.md").read_text(encoding="utf-8")
    for key in ("fact_vix", "fact_credit_spread", "fact_leading", "fact_coincident", "fact_policy_rate", "fact_fx"):
        assert rules.approved(key).text in doc44, key
    assert [W.text(k) for k in ("evidence_card_1", "evidence_card_2", "evidence_card_3")] == [
        "MKT-1 風險情緒", "MKT-2 景氣位置", "MKT-3 資金與匯率"]   # 與 81 線框／72 第 3 節同寫法


def test_keys_without_formal_data_are_missing_not_filled():
    """MKT-2 兩鍵（國發會不給公布日 → pending）與 MKT-3 匯率（閘門未開 → pending）：◇ 資料未備，沒有值、沒有補。"""
    model = _model()
    facts = {f.label_key: f for c in model.evidence_cards for f in c.facts}
    for key in ("fact_leading", "fact_coincident", "fact_fx"):
        assert facts[key].status == "missing" and facts[key].value is None and facts[key].as_of is None, key
        assert facts[key].reason_code in ("ndc_no_release_date", "fx_obs_date_rule"), key
    for key in ("fact_vix", "fact_credit_spread", "fact_policy_rate"):
        assert facts[key].status == "ok" and isinstance(facts[key].value, float), key


def test_a_failed_key_is_fetch_failed_and_never_looks_like_missing():
    table = ms.table(errors={"credit_spread_pct": "HTTP 500"}, drop=("credit_spread_pct",))
    model = adapter.build_market_page(ms.view(), table, period="1Y")
    fact = next(f for c in model.evidence_cards for f in c.facts if f.label_key == "fact_credit_spread")
    assert fact.status == "failed" and fact.reason_code == "fetch_failed"


@pytest.mark.parametrize("label_key, pattern", [
    ("fact_vix", r"^\d+\.\d$"),                 # 小數 1 位、無單位
    ("fact_credit_spread", r"^\d+\.\d{2}pp$"),  # 小數 2 位、單位 pp
    ("fact_policy_rate", r"^\d+\.\d{2}%$"),     # 小數 2 位、單位 %
])
def test_values_use_the_formal_decimals_and_units(label_key, pattern):
    model = _model()
    fact = next(f for c in model.evidence_cards for f in c.facts if f.label_key == label_key)
    shown = mkt.fmt_value(fact.value, fact.unit, mkt._FACT_DECIMALS.get(fact.label_key, 2))
    assert re.match(pattern, shown), (label_key, shown)
    assert re.search(re.escape(W.text(label_key)) + r"\s+" + re.escape(shown), re.sub(r"<[^>]+>", " ", mkt.fact_html(fact)))


def test_fx_formal_decimals_are_three_but_the_key_is_not_reachable_today():
    """匯率 3 位小數與單位「新臺幣／美元」是 44 的規則；閘門關閉時 `fx_twd_per_usd` 不取數 → 這條只鎖位數常數。
    ⚠️ 單位不符時 44 要 `業務例外`，ui_v3 狀態詞彙沒有這一態（尚未判定；見 81 第 10 節 MKT 對照），開閘前須另行處置。"""
    assert mkt._FACT_DECIMALS["fact_fx"] == 3
