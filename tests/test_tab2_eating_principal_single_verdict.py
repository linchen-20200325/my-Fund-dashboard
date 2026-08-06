# -*- coding: utf-8 -*-
"""2026-08-06 稽核 🔴 必修 4 — Tab④ 的「吃本金」結論同頁只能印一次。

同一頁原本有兩個結論框，輸入**逐字同源**：
  * 上方主 KPI 列旁的「吃本金檢查 — {status}」橫幅（`_kpi_adr` / `_kpi_tr1y`）
  * 下方配息區的「🚨 吃本金警示」框（`_adr` / `_tr1y`）
`_kpi_adr` 與 `_adr` 都來自同一個 `_resolve_adr_with_fallback`；`_kpi_tr1y` 與
`_tr1y` 都來自同一個 `compute_1y_total_return` 且 payload 相同 → `div_safety_check`
的回傳必然一模一樣。下方那份的註解自己就寫著「與同頁『吃本金檢查』橫幅完全同源」。

留哪一份（本輪決定：留上方 KPI 橫幅）
------------------------------------
1. 下方那份被關在 `if divs and len(divs) >= 1:` 內 —— 累積型 / MoneyDJ 沒配息頁的
   基金根本看不到，結構上當不了單一出口。
2. 上方橫幅另外處理「⬜ 不適用（無配息率）」「⬜ 資料不足（無 1Y 含息）」兩種缺值
   狀態，並附「1Y 來源」provenance，資訊量嚴格較多。
3. 它就在主 KPI 列旁，是使用者第一眼的位置。

去重不得順手刪掉揭露
--------------------
警示框獨有的 `nav_warning`（1Y 淨值跌破門檻的獨立早期警訊）必須上移到 KPI 橫幅，
否則就是「去重把揭露一起刪掉」—— 本檔 `TestDisclosureNotLost` 專門守這一條。

配息覆蓋率講義卡**保留**：它印的是公式與門檻（教學），不是再講一次結論；
色 / 標籤仍讀同一個 `_ds`，與上方橫幅永遠一致。

測試手法：一律 AST。`ui/tab2_single_fund.py` 的說明註解裡就寫著
`div_safety_check`、「吃本金」等字樣，字串掃描會被自己的註解騙過去。

修正前紅的類型
--------------
- `test_lower_verdict_box_is_gone` → **行為衝突紅**（`_ds['status']` /
  `_ds['message']` / `_ds['nav_warning']` 當時都被渲染）
- `TestDisclosureNotLost` 兩條 → **行為衝突紅**（當時 KPI 橫幅沒有 nav_warning）
- `test_kpi_banner_still_prints_the_verdict` → 修正前**綠**，回歸鎖：
  防「兩份都砍掉」這種過度去重。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
TAB2 = ROOT / "ui" / "tab2_single_fund.py"


@pytest.fixture(scope="module")
def tree() -> ast.AST:
    return ast.parse(TAB2.read_text(encoding="utf-8"), filename=str(TAB2))


def _gets_on(tree: ast.AST, var: str) -> set[str]:
    """`<var>.get("<key>")` → {key}（只認 Name 上的 .get，註解不會誤觸）。"""
    out: set[str] = set()
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "get"
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == var
                and n.args and isinstance(n.args[0], ast.Constant)):
            out.add(n.args[0].value)
    return out


def _subscripts_on(tree: ast.AST, var: str) -> dict[str, int]:
    """`<var>["<key>"]` → {key: lineno}。"""
    out: dict[str, int] = {}
    for n in ast.walk(tree):
        if (isinstance(n, ast.Subscript)
                and isinstance(n.value, ast.Name) and n.value.id == var
                and isinstance(n.slice, ast.Constant)
                and isinstance(n.slice.value, str)):
            out.setdefault(n.slice.value, n.lineno)
    return out


def _loaded_names(tree: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


# ══════════════════════════════════════════════════════════════
# 1. 下方那份結論框已移除
# ══════════════════════════════════════════════════════════════
_VERDICT_FIELDS = ("status", "message", "nav_warning")


def test_lower_verdict_box_is_gone(tree: ast.AST) -> None:
    """**修正前必紅（行為衝突）**。

    配息區那份 `dividend_safety` 結果（`_ds`）只允許被拿去算**講義卡的色與
    Coverage 數字**；一旦又讀 status / message / nav_warning，就是把同一個結論
    在同一頁再印一次。
    """
    _used = _gets_on(tree, "_ds") | set(_subscripts_on(tree, "_ds"))
    offenders = sorted(_used & set(_VERDICT_FIELDS))
    assert not offenders, (
        f"配息區的 `_ds` 又讀了 {offenders} —— 這幾個欄位就是「吃本金結論」本身，"
        "同頁上方 KPI 橫幅已經印過一次（兩者輸入逐字同源，結果必然相同）。")


def test_lower_block_still_computes_coverage_for_the_teaching_card(tree: ast.AST) -> None:
    """回歸鎖（修正前綠）：講義卡要留著，別把整段連公式一起刪了。"""
    _used = _gets_on(tree, "_ds")
    assert "coverage" in _used, "講義卡的 Coverage 數字沒了"
    assert "alert_level" in _used, "講義卡的色碼沒有跟 SSOT 對齊"


# ══════════════════════════════════════════════════════════════
# 2. 上方 KPI 橫幅仍是那唯一的結論出口
# ══════════════════════════════════════════════════════════════
def test_kpi_banner_still_prints_the_verdict(tree: ast.AST) -> None:
    """回歸鎖（修正前綠）：去重不是「兩邊都砍」。"""
    _used = _gets_on(tree, "_kpi_ds")
    for _f in ("status", "message"):
        assert _f in _used, f"KPI 橫幅沒讀 {_f}，畫面上就沒有吃本金結論了"


# ══════════════════════════════════════════════════════════════
# 3. 去重不得順手刪掉揭露
# ══════════════════════════════════════════════════════════════
class TestDisclosureNotLost:
    def test_nav_warning_moved_to_the_kpi_banner(self, tree: ast.AST) -> None:
        """**修正前必紅（行為衝突）** —— 當時 nav_warning 只存在於被刪掉的那個框。"""
        assert "nav_warning" in _gets_on(tree, "_kpi_ds"), (
            "`nav_warning` 是警示框獨有的揭露（1Y 淨值跌破門檻 → 配息源頭值得確認），"
            "刪掉那個框就必須把它接到留下來的橫幅上，否則是去重把揭露一起刪掉。")

    def test_nav_warning_is_actually_rendered(self, tree: ast.AST) -> None:
        """**修正前必紅（AST 找不到 `_kpi_nav_warn` 被讀取）** —— 接線驗證。

        只算出來不印出來，等於 `PROCESS.md §4` 的「算對了但沒接出去」。
        """
        assert "_kpi_nav_warn" in _loaded_names(tree), (
            "`_kpi_nav_warn` 只被賦值、沒有任何地方讀它 → 畫面上看不到")
