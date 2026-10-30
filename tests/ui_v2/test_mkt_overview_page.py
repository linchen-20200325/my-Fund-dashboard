# -*- coding: utf-8 -*-
"""🌍 市場與趨勢頁新視覺層級的執行期測試（slow lane；Streamlit AppTest；BL-0525 Batch C，`DEC-2026-10-30-01`）。

驗的是 D1～D7 與額外 UI Guardrail 裡「渲染結果」能自動量測的部分（版面像素層級由 `tests/visual_fidelity` 的 CI fixture screenshot 驗）：
順序、Secondary ≤3、無頁級日期、結論燈改一行 chip 且文案不變、依據卡內容不刪、Missing／error 語意不變、利率與信用的資料來自 B 線列。
"""

import pathlib
import re
import sys

import pytest

pytestmark = pytest.mark.slow

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "tests" / "ui_v2"))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

import test_mkt_market_section_page as _T9  # noqa: E402
from ui_v2.mkt import overview  # noqa: E402

_OK = _T9._OK


def _run(script):
    at = AppTest.from_string(script, default_timeout=90)
    at.run()
    return at


def _leaves(node):
    """依畫面順序走訪元素樹（深度優先）。"""
    children = getattr(node, "children", None)
    if not children:
        yield node
        return
    for child in children.values():
        yield from _leaves(child)


def _ordered_markdown(at):
    return [leaf.value for leaf in _leaves(at.main) if type(leaf).__name__ == "Markdown"]


def _index(blobs, needle):
    hits = [i for i, b in enumerate(blobs) if needle in b]
    assert hits, needle
    return hits[0]


def test_順序_status_chip_一句主判讀_Primary_Secondary_依據卡_尚未取得():
    blobs = _ordered_markdown(_run(_OK))
    order = [_index(blobs, n) for n in ('class="mkt-light mkt-light--chip"', 'class="mkt-hero"', 'data-section="primary"',
                                        'data-section="secondary"', 'data-block="MKT-1"', 'data-section="trend-eps_pe_scenario"',
                                        'data-section="trend-conclusion"')]
    assert order == sorted(order) and len(set(order)) == len(order), order


def test_Primary圖在一句主判讀之後_Secondary是行內迷你圖不是vega圖():
    at = _run(_OK)
    assert len(at.get("vega_lite_chart")) == 1
    secondary = [b for b in _ordered_markdown(at) if 'data-section="secondary"' in b]
    assert len(secondary) == 3 <= overview.MAX_SECONDARY          # 風險、國際、利率與信用
    # 合成資料只有 VIX／S&P 500 有足夠 1Y 點；fixtures 的利率三鍵只有幾筆列 → 誠實說資料不足、不畫圖（豐富資料見下一條）
    assert ["<svg" in b for b in secondary] == [True, True, False]
    assert "資料不足以呈現此期間" in secondary[2]
    titles = [re.search(r'pc-card-title">([^<]+)<', b).group(1) for b in secondary]
    assert titles == ["風險｜VIX", "國際｜S&amp;P 500", "利率與信用｜期限利差"]


def test_豐富資料_三張Secondary都有迷你折線_圖表仍只有Primary一張():
    import test_live_390_page as live390
    at = _run(live390._SCRIPTS["mkt"])
    assert not at.exception, [e.value for e in at.exception]
    secondary = [b for b in _ordered_markdown(at) if 'data-section="secondary"' in b]
    assert len(secondary) == 3 and all("<svg" in b and "mkt-sec-body" in b for b in secondary)
    assert len(at.get("vega_lite_chart")) == 1
    for b in secondary:                                           # 每張只有現在值、期間變動（或單位）、資料日三枚 chip
        assert b.count('class="pc-chip"') == 3


def test_結論燈是一行chip_沿用既有狀態字樣_不新增n項資料未備():
    at = _run(_OK.replace("_dataset = fixtures.dataset_all_ok()", "_dataset = fixtures.dataset_mkt2_both_keys_missing()"))
    assert not at.exception, [e.value for e in at.exception]
    chip = [b for b in _ordered_markdown(at) if 'class="mkt-light mkt-light--chip"' in b]
    assert len(chip) == 1 and 'data-block="MKT-0"' in chip[0] and "mkt-light-dot" in chip[0]
    text = re.sub(r"<[^>]+>", "", chip[0])
    assert "資料未備" in text and not re.search(r"\d+ 項資料未備", text)
    assert "mkt-light-code" not in chip[0]                        # 塊名移進「▸ 各項資料狀態」
    assert re.search(r"[◇⬜⛔]|資料未備|不適用|取數失敗", text)


def test_沒有頁級日期_頁首不畫主要原因與資料截至():
    at = _run(_OK)
    everything = "\n".join(_ordered_markdown(at) + [c.value for c in at.caption])
    assert "資料截至" not in everything and 'class="v2-status-line"' not in everything
    assert re.search(r"一句|class=\"mkt-hero\"", everything)
    hero = [b for b in _ordered_markdown(at) if 'class="mkt-hero"' in b][0]
    assert not re.search(r"\d{4}-\d{2}-\d{2}", hero) and "暫無完整市場綜合判定" in hero


def test_依據卡_三張仍在_內容沒刪():
    blobs = _ordered_markdown(_run(_OK))
    for code in ("MKT-1", "MKT-2", "MKT-3"):
        card = [b for b in blobs if f'data-block="{code}"' in b and "mkt-card" in b]
        assert len(card) == 1 and "mkt-mv" in card[0], code


def test_各項資料狀態_收著原結論燈的說明_市場結論卡_與完整的暫無完整判定():
    at = _run(_OK)
    expander = [e for e in at.expander if e.label == overview.STATUS_DETAIL_TITLE]
    assert len(expander) == 1 and not expander[0].proto.expanded
    text = "\n".join(_ordered_markdown(at))
    assert "暫無完整市場綜合判定（缺正式 aggregation rule）" in text
    assert "我今天在這一頁看到的東西，可不可以照著讀" in text      # 原結論燈下的 answers，搬進群組而不是刪掉


def test_利率與信用_三個子序列都可切換_資料來自B線列_切換後chips變():
    at = _run(_OK)
    seen = []
    for key in overview.RATES_KEYS:
        next(r for r in at.radio if r.key == "mkt_rates_series").set_value(key).run()
        assert not at.exception, [e.value for e in at.exception]
        card = [b for b in _ordered_markdown(at) if 'data-section="secondary"' in b and "利率與信用" in b]
        assert len(card) == 1
        seen.append(re.search(r'pc-card-title">([^<]+)<', card[0]).group(1))
    assert seen == [f"利率與信用｜{overview.RATES_OPTION_LABELS[k]}" for k in overview.RATES_KEYS]
    # 同一時間只顯示一個子序列：卡裡不會同時出現另外兩個子序列的名稱
    assert "期限利差" not in seen[1] and "信用利差" not in seen[2]


def test_利率與信用_B線沒有列_維持Missing_不新增來源_不畫圖():
    script = _OK.replace("_dataset = fixtures.dataset_all_ok()",
                         "_dataset = fixtures.dataset_all_ok(); _dataset = {**_dataset, 'rows': [r for r in _dataset['rows'] if r['indicator_key'] not in ('credit_spread_pct','term_spread_pct','policy_rate_pct')]}")
    at = _run(script)
    assert not at.exception, [e.value for e in at.exception]
    card = [b for b in _ordered_markdown(at) if 'data-section="secondary"' in b and "利率與信用" in b][0]
    assert "<svg" not in card and "資料未備" in card


def test_Secondary使用的資料列只有B線既有三鍵_page沒有新的取數():
    import ast
    tree = ast.parse((_ROOT / "ui_v2/mkt/overview.py").read_text(encoding="utf-8"))
    keys = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and n.value.endswith("_pct")}
    assert keys == {"term_spread_pct", "credit_spread_pct", "policy_rate_pct"}
