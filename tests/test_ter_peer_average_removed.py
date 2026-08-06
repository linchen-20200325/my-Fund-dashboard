# -*- coding: utf-8 -*-
"""2026-08-06 稽核 🔴 必修 1 — TER「同類均值」憑印象填的對照表必須全站消失。

背景
====
`ui/tab2_single_fund.py` 上一輪已移除一份 11 筆的「基金類別 → 費率」寫死表
（無來源、無抓取時間、無樣本數、無定義），但**逐字相同的表還有兩份活著**，
而且上一輪剛好把兩個顯示點都改成預設展開：

  * `ui/helpers/fund_grp_health/investment.py`（💊 健診 Tab 逐檔卡）
  * `ui/helpers/fund/checkup.py`（健診 Tab + Tab⑤ 持倉健診卡，兩處都 expanded=True）

使用者因此會在 Tab④ 看到「本站沒有同類均值資料，誠實留白」，切到健診 Tab 卻看到
「TER 1.85% ｜ 同類均值 1.50% ｜ 高於均值 +0.35%」的紅字 —— 有數字有顏色的那個
比較像真的，他會據此判定「這檔太貴要換」。§1「自行估一個合理值當常數」、§3.3 反捏造。

測試手法
========
一律走 **AST**，不掃字串字面值：解釋「為什麼移除」的註解、以及誠實留白的說明文案
本身就含「同類均值」四個字，字串掃描會被自己的文案騙過去（本 repo 踩過的坑）。

- 結構特徵：key 全為字串常數、value 全為數字常數且 ≥ 4 筆的 dict 字面量 = 這類表。
- 識別名：`_ter_avg` / `_ter_diff` / `_TER_AVG_MAP` 這組變數只為了同類比較而存在。
- 出口契約：`_compute_fund_health_kpis` 不得再吐 `ter_avg` / `ter_diff` 鍵。

修正前紅的類型
--------------
- `test_no_fabricated_string_to_number_lookup_table[...investment.py]`
  / `[...checkup.py]` → **行為衝突紅**（兩份表當時都在）
- `test_no_peer_average_identifiers[...]` 同上 → **行為衝突紅**
- `test_kpi_payload_has_no_peer_average_fields` → **行為衝突紅**（當時回傳含兩鍵）
- `test_compounding_copy_uses_the_verifiable_number` → **行為衝突紅**
  （investment.py 當時寫 ~25%；1.01²⁰ = 1.2202 → 正解 22%）
- `test_tab2_stays_clean` → 修正前**綠**，是回歸鎖：防第三份表再長回來。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]

# 三個曾經（或現在）印 TER 卡的檔案 —— 新增顯示點請往這裡加，不要另開測試。
_TER_RENDER_FILES = [
    "ui/tab2_single_fund.py",
    "ui/helpers/fund/checkup.py",
    "ui/helpers/fund_grp_health/investment.py",
]

# 4 筆以上的「名稱 → 數值」字面表，通常就是憑印象填的基準值
# （沿用 tests/test_tab2_single_fund_ui.py 的同一個結構判準）。
_LOOKUP_TABLE_MIN_ENTRIES = 4

_PEER_AVG_IDENTIFIER_MARKERS = ("ter_avg", "ter_diff", "TER_AVG")


def _tree(rel: str) -> ast.AST:
    _p = ROOT / rel
    return ast.parse(_p.read_text(encoding="utf-8"), filename=str(_p))


def _all_str_constants(tree: ast.AST) -> str:
    """把模組內所有字串常數串起來（含 docstring，但**不含註解** —— AST 已剝掉）。"""
    return "\n".join(
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    )


@pytest.mark.parametrize("rel", _TER_RENDER_FILES)
def test_no_fabricated_string_to_number_lookup_table(rel: str) -> None:
    offenders = []
    for node in ast.walk(_tree(rel)):
        if not isinstance(node, ast.Dict):
            continue
        if len(node.keys) < _LOOKUP_TABLE_MIN_ENTRIES:
            continue
        if any(k is None for k in node.keys):
            continue  # 有 **unpack，不是單純字面表
        keys_ok = all(isinstance(k, ast.Constant) and isinstance(k.value, str)
                      for k in node.keys)
        vals_ok = all(isinstance(v, ast.Constant)
                      and isinstance(v.value, (int, float))
                      and not isinstance(v.value, bool)
                      for v in node.values)
        if keys_ok and vals_ok:
            offenders.append(node.lineno)
    assert not offenders, (
        f"{rel} 行 {offenders}：偵測到寫死在 UI 層的「名稱 → 數值」對照表。"
        "畫面上它與真實抓取值無法區分，使用者會據此做汰換決策。"
        "若確實有來源，請放進 shared/ 的 SSOT 模組並附出處與 as_of。"
    )


@pytest.mark.parametrize("rel", _TER_RENDER_FILES)
def test_no_peer_average_identifiers(rel: str) -> None:
    """同類均值只有一個用途 —— 相關識別名整組不該存在。

    走 AST 的 Name / Attribute / 關鍵字，註解與說明文案不會誤觸。
    """
    offenders = set()
    for node in ast.walk(_tree(rel)):
        _name = None
        if isinstance(node, ast.Name):
            _name = node.id
        elif isinstance(node, ast.Attribute):
            _name = node.attr
        elif isinstance(node, ast.keyword) and node.arg:
            _name = node.arg
        if _name and any(m in _name for m in _PEER_AVG_IDENTIFIER_MARKERS):
            offenders.add(_name)
    assert not offenders, (
        f"{rel} 仍有同類均值相關識別名 {sorted(offenders)} —— "
        "整組比較（表 + 差值 + 色碼）應移除，只留本檔實際費率。"
    )


def test_kpi_payload_has_no_peer_average_fields() -> None:
    """出口契約：健診 KPI 不得再帶同類均值 / 差值（渲染端就拿不到，也就印不出來）。"""
    from ui.helpers.fund.checkup import _compute_fund_health_kpis
    _k = _compute_fund_health_kpis({
        "code": "TEST1",
        "moneydj_raw": {"mgmt_fee": "1.85", "category": "全球股票型"},
        "metrics": {},
    })
    assert "ter_val" in _k and "ter_cat" in _k, "本檔真實費率仍須提供"
    assert _k["ter_val"] == pytest.approx(1.85)
    for _banned in ("ter_avg", "ter_diff"):
        assert _banned not in _k, (
            f"KPI 仍回傳 {_banned} —— 只要它還在，渲染端就隨時會把它印回畫面")


@pytest.mark.parametrize("rel", _TER_RENDER_FILES)
def test_compounding_copy_uses_the_verifiable_number(rel: str) -> None:
    """1.01²⁰ = 1.2202 → 每降 1% 費用、20 年多約 **22%**，不是 25%。

    只比對字串常數（AST），所以本檔與各原始碼的說明性註解不會影響判定。
    """
    _text = _all_str_constants(_tree(rel))
    # 刻意用 assert 而非 skip（PROCESS.md §4「測試自身的可執行性」）：
    # 文案被整段刪掉時本條應該紅，讓人回來確認是有意移除，而不是靜靜變成 skip。
    assert "20 年後終值多" in _text, f"{rel} 的 TER 複利說明不見了"
    assert "~25%" not in _text, f"{rel} 仍留無依據的 ~25%"
    assert "~22%" in _text, f"{rel} 複利說明應寫可自行驗算的 ~22%"


@pytest.mark.parametrize(
    "rel", ["ui/helpers/fund/checkup.py",
            "ui/helpers/fund_grp_health/investment.py"])
def test_states_why_there_is_no_peer_comparison(rel: str) -> None:
    """§1 誠實留白：拿掉比較之後要說「為什麼沒有」，不是靜靜少一欄。"""
    _text = _all_str_constants(_tree(rel))
    assert "沒有同類均值可對照" in _text, (
        f"{rel} 移除比較後未向使用者說明原因（三個資料源都沒有這個欄位）")


def test_tab2_stays_clean() -> None:
    """回歸鎖（修正前綠）：Tab④ 上一輪已收乾淨，別讓第三份表長回來。"""
    _text = _all_str_constants(_tree("ui/tab2_single_fund.py"))
    assert "為什麼這裡沒有「同類均值」比較" in _text
