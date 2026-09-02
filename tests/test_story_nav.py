"""test_story_nav — 決策動線敘事導覽列（純函式）

沿革：v19.405 Phase 4 對齊 6→5；**2026-08-31 客戶拍板線框 7→5** 之後，
第 3 站由「🔍 個基深掘」改為合併頁「🔍 基金研究」、第 4 站改名「📊 我的配置」。
⚠️ 2026-09-01 五分頁動線重構（客戶拍板線框 `ia-wireframe.html`）四個分頁**再次改名**：
   市場定調→**市場總覽** ／ 組合健診→**持倉體檢** ／ 基金研究→**標的探索** ／
   我的配置→**資產配置**（⑤ 設定與診斷未改）。下方逐字斷言已同步；
   **它們轉紅正是本檔的作用** —— 改名必須是一次有意識的動作，不能靜默漂移。

只測內容層 `story_nav_markdown`（不涉 streamlit）；`render_story_nav` 走 st.caption，
由 app smoke / AppTest 覆蓋。

⚠️ 本檔**刻意不寫死**「④ 📊 資產配置」以外的中文字面值去對 `_TAB_LABELS`：
   凡是能從 SSOT 導出的，一律導出。少數保留字面值的地方（第 1 站 / 第 4 站的
   highlight 形狀）是為了讓「markdown 長相」本身有一條鎖 —— 那是這個模組的產出，
   不是它的輸入。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from ui.helpers.story_nav import (
    _SECTION_LABELS,
    _STEPS,
    _TAB_LABELS,
    section_label,
    story_nav_markdown,
    tab_label,
    where_to_find,
)

_ROOT = Path(__file__).resolve().parents[1]


def test_story_nav_highlights_current_step():
    md = story_nav_markdown("portfolio")
    assert "**:blue[④ 📊 資產配置]**" in md    # 目前站：藍色粗體
    assert ":gray[① 🌐 市場總覽]" in md          # 其餘站：灰色
    assert "記帳 + 再平衡" in md                  # 目前站提示


def test_story_nav_all_steps_present():
    md = story_nav_markdown("macro")
    for _key, _label, _hint in _STEPS:
        assert _label in md
    assert "**:blue[① 🌐 市場總覽]**" in md


def test_story_nav_health_step_valid():
    """v19.405 Phase 4 新增第 2 站（2026-09-01 起名「持倉體檢」）→ health 為合法 current key。"""
    md = story_nav_markdown("health")
    assert "**:blue[② 💊 持倉體檢]**" in md
    assert "吃本金" in md


def test_story_nav_invalid_current_no_highlight():
    md = story_nav_markdown("nope")
    assert ":blue[" not in md          # 沒有任何站被 highlight
    assert ":gray[" in md              # 四站都灰


def test_story_nav_order_decision_flow():
    """順序必須是 市場總覽 → 持倉體檢 → 標的探索 → 資產配置（決策動線）。

    2026-08-31 七→五：第 3 站的 key 由 `fund` 改為 `research`
    （個基深掘 + 批次分析合併成 ③；③ 2026-09-01 起名「標的探索」）。
    """
    keys = [s[0] for s in _STEPS]
    assert keys == ["macro", "health", "research", "portfolio"]


# ══════════════════════════════════════════════════════════════
# 2026-08-31 七→五：分頁 / 分區兩張表 + 指路函式
# ══════════════════════════════════════════════════════════════
def test_tab_labels_are_exactly_the_five_top_level_tabs():
    """`_TAB_LABELS` 只准放**分頁列上真的看得到**的那 5 個。

    這是本次改動的核心不變量：`tab_label()` 的全部價值就是「它回的字串一定
    在分頁列上找得到」。多放一個舊 key 進來，它就退化成一個會說謊的 SSOT。
    """
    assert list(_TAB_LABELS) == [
        "macro", "health", "research", "portfolio", "settings",
    ], "頂層分頁 SSOT 的內容或**順序**變了 —— 順序即站號 ①②③④⑤，不是裝飾"


def test_old_top_level_keys_now_fail_loud():
    """**突變自證點**：七→五之後，舊分頁 key 不得再從 `tab_label()` 拿到東西。

    `fund` / `batch` / `manage` / `ref` 現在是**頁內分區或已拆解**，
    回一個分頁名 = 指到分頁列上不存在的地方（本 repo 同型 bug 已發作兩次：
    2026-08-05 必修 2、2026-08-14 sidebar 三處死指路）。
    """
    for _dead in ("fund", "batch", "manage", "ref"):
        with pytest.raises(KeyError):
            tab_label(_dead)


def test_tab_label_error_message_points_at_the_replacement():
    """Fail loud 不只是炸掉 —— 訊息要告訴 caller 該改用什麼，否則只是換個地方卡住。"""
    with pytest.raises(KeyError) as _ei:
        tab_label("batch")
    _msg = str(_ei.value)
    assert "where_to_find" in _msg, "錯誤訊息沒有指名替代 API"
    assert "標的探索" in _msg, "錯誤訊息沒有直接把正確答案算給 caller 看"


def test_section_label_and_tab_label_are_disjoint_namespaces():
    """兩張表不得有交集 —— 有交集就代表同一個字既是分頁又是分區，指路必然歧義。"""
    assert not (set(_TAB_LABELS) & set(_SECTION_LABELS))
    with pytest.raises(KeyError):
        section_label("macro")      # 分頁 key 不該從分區表拿到東西
    with pytest.raises(KeyError):
        section_label("nope")


def test_where_to_find_carries_the_owning_tab_and_ordinal():
    """指路字串必須**自動帶上頂層分頁名**（線框要求），站號由順序推導、不寫死。"""
    assert where_to_find("batch") == "③ 🔍 標的探索 → 📦 批次掃描"
    assert where_to_find("fund") == "③ 🔍 標的探索 → 🔍 單檔深掘"
    assert where_to_find("manual") == "⑤ ⚙️ 設定與診斷 → 📖 說明書"
    # 分頁 key 也吃得下（沒有下一層可指）
    assert where_to_find("macro") == "① 🌐 市場總覽"
    with pytest.raises(KeyError):
        where_to_find("nope")


def test_where_to_find_ordinal_is_derived_not_hardcoded():
    """站號必須是**推導**出來的：把分頁順序換掉，站號要跟著換。

    這條鎖的是線框點名的那顆地雷 ——「Tab2＝個基深掘（實際第 4）」
    正是有人把站號寫死、分頁增刪後沒人跟著改。
    """
    import ui.helpers.story_nav as _sn

    _orig = _sn._TAB_LABELS
    try:
        # 把 research 從第 3 個搬到第 1 個 → 站號必須從 ③ 變成 ①
        _sn._TAB_LABELS = {
            "research": _orig["research"],
            **{k: v for k, v in _orig.items() if k != "research"},
        }
        assert _sn.where_to_find("batch").startswith("① "), (
            "站號沒有跟著分頁順序走 —— 它一定是寫死的")
    finally:
        _sn._TAB_LABELS = _orig
    assert where_to_find("batch").startswith("③ "), "還原失敗，後續測試會被污染"


def test_section_keys_resolve_to_the_owning_tab_in_story_nav():
    """子頁仍傳舊 key（`render_story_nav("fund")`）時，必須高亮它**所屬的分頁**。

    這是「邊界外 caller 一個字都不用改」的那條路：若不解析，`_VALID` 檢查會讓
    整條導覽**靜默不畫** —— 無聲的功能退化比報錯更難發現。
    """
    md = story_nav_markdown("fund")
    assert "**:blue[③ 🔍 標的探索]**" in md, "分區 key 沒有解析成所屬分頁"
    assert story_nav_markdown("batch") == md, "同一頁的兩個模式應指向同一站"


# ══════════════════════════════════════════════════════════════
# 分區名 SSOT ↔ 合併頁實際畫出來的字（漂移鎖）
# ══════════════════════════════════════════════════════════════
@pytest.mark.parametrize("key,relpath", [
    ("fund",   "ui/tab_fund_research.py"),
    ("batch",  "ui/tab_fund_research.py"),
    ("manage", "ui/tab_settings_diag.py"),
    ("diag",   "ui/tab_settings_diag.py"),
    ("manual", "ui/tab_settings_diag.py"),
    # 2026-09-02：⑤ 的 NAV 兩塊（線框 `ia-wireframe.html` Tab 05）。字面值住在
    # `ui/helpers/settings_diag/nav_history_section.py`（合併頁把該區塊委派給它），
    # 所以漂移鎖錨到那一檔而不是 `tab_settings_diag.py`。
    ("nav_status", "ui/helpers/settings_diag/nav_history_section.py"),
    ("nav_manual", "ui/helpers/settings_diag/nav_history_section.py"),
])
def test_section_labels_match_merged_pages(key: str, relpath: str):
    """`_SECTION_LABELS` 的字必須真的出現在該合併頁的原始碼裡。

    ⚠️ 為什麼是「字串出現在檔案裡」這種弱形式的鎖：兩個合併頁**不在本批的
    檔案邊界內**（另有批次在改），還沒改吃這張表，各自持有自己的字面值。
    這條鎖不能證明它們**用的是同一份**，但它能在任一邊改字時**當場轉紅** ——
    也就是把「兩份標籤悄悄漂移」變成「CI 紅燈」。
    等合併頁改吃 `section_label()` 之後，本條應升級為 AST 接線驗證
    （已列入 PR 描述的待辦）。
    """
    _src = (_ROOT / relpath).read_text(encoding="utf-8")
    _want = _SECTION_LABELS[key]
    assert _want in _src, (
        f"{relpath} 找不到分區名「{_want}」—— story_nav 的分區 SSOT 與合併頁"
        f"實際畫出來的字已經漂移，指路文案會指到使用者找不到的地方。")


def test_section_label_for_batch_is_the_wireframe_wording():
    """線框把 ③ 的第二個模式定名為「📦 批次掃描」（不是舊分頁名「📦 批次分析」）。

    直接對 `ui/tab_fund_research.py::MODE_BATCH` 比，不比字面值 —— 比字面值
    等於在測試裡再抄第三份。
    """
    from ui.tab_fund_research import MODE_BATCH, MODE_SINGLE

    assert section_label("batch") == MODE_BATCH
    assert section_label("fund") == MODE_SINGLE


def test_no_leftover_seven_tab_labels_in_story_nav_source():
    """story_nav 檔內不得再有舊分頁名的**活字串**（註解與 docstring 可以講歷史）。

    ⚠️ 用 AST 排除 docstring，不是用「行首是不是 #」—— 本檔第一版就是那樣寫的，
    結果被自己 docstring 裡「直接寫『📦 批次分析』這種句子」那句說明文字絆倒。
    **字串比對式的守衛會被檔案自己的說明文字騙**，這是本 repo 已實證過的形狀，
    所以這裡改成只看「真的會被求值的字串常數」。
    """
    import ast as _ast

    _tree = _ast.parse(
        (_ROOT / "ui" / "helpers" / "story_nav.py").read_text(encoding="utf-8"))
    # 收集所有 docstring 節點（模組 / 函式 / 類別的第一個 Expr-Constant-str）
    _docstrings = set()
    for _n in _ast.walk(_tree):
        if isinstance(_n, (_ast.Module, _ast.FunctionDef,
                           _ast.AsyncFunctionDef, _ast.ClassDef)):
            _b = getattr(_n, "body", None)
            if (_b and isinstance(_b[0], _ast.Expr)
                    and isinstance(_b[0].value, _ast.Constant)
                    and isinstance(_b[0].value.value, str)):
                _docstrings.add(id(_b[0].value))

    # ⚠️ 2026-08-31 新增一個**具名的例外**（**有意識的政策變更，不是漏改** ·
    # 決策者：AI 總管）：`RETIRED_TAB_LABELS` / `MISWRITTEN_TAB_NAMES` 兩個常數
    # **就是**「已失效分頁名」的字表本身，它們的元素**必須**是那些字串。
    # ~~本條原本禁止 story_nav.py 出現任何舊分頁名的活字串。~~
    # **舊條文的理由仍然成立**：它要防的是「SSOT 自己還留著一份舊值」——
    # 例如有人把 `batch` 留在 `_TAB_LABELS` 裡，`tab_label('batch')` 就會回一個
    # 分頁列上不存在的名字（本模組 docstring 講的就是這件事）。**這個防線一字未鬆**。
    # **被權衡掉的只是它的涵蓋方式**：它原本假設「舊名字出現在本檔 ＝ 一定是殘留」，
    # 而 2026-08-31 之後多了一個**正當**的出現位置 —— 黑名單守衛的字表 SSOT
    # （`tests/test_wpf_five_tab_wiring.py::test_no_live_string_hardcodes_a_tab_name`
    # 拿它去掃全 repo）。字表不寫出那些字，就無從比對。
    # ⚠️ 例外**只給這兩個常數的元素**，本檔其餘任何位置照樣禁止 ——
    # 也就是「`_TAB_LABELS` 裡殘留舊值」這個原本要抓的東西，依然會被抓到。
    _WHITELIST_ASSIGN = {"RETIRED_TAB_LABELS", "MISWRITTEN_TAB_NAMES"}
    _in_name_table: set = set()
    for _n in _ast.walk(_tree):
        if isinstance(_n, (_ast.Assign, _ast.AnnAssign)):
            _tgts = (_n.targets if isinstance(_n, _ast.Assign) else [_n.target])
            if any(getattr(_t, "id", None) in _WHITELIST_ASSIGN for _t in _tgts):
                _in_name_table |= {id(_c) for _c in _ast.walk(_n)
                                   if isinstance(_c, _ast.Constant)}

    _live = [_n.value for _n in _ast.walk(_tree)
             if isinstance(_n, _ast.Constant) and isinstance(_n.value, str)
             and id(_n) not in _docstrings and id(_n) not in _in_name_table]

    for _dead in ("📦 批次分析", "📋 我的管理室", "📖 參考 / 診斷", "🔍 個基深掘",
                  "📊 配置 & 帳本"):
        _hits = [_s for _s in _live if _dead in _s]
        assert not _hits, f"story_nav.py 仍有舊分頁名 {_dead} 的活字串：{_hits}"

    # 例外不得被擴大成「整個檔案豁免」：這兩個常數本身必須真的存在且非空，
    # 否則上面那段排除等於白寫（有人把常數刪掉、字表沒了，守衛也不會叫）。
    from ui.helpers.story_nav import MISWRITTEN_TAB_NAMES, RETIRED_TAB_LABELS
    assert RETIRED_TAB_LABELS and MISWRITTEN_TAB_NAMES, (
        "退役 / 錯名字表是空的 —— 黑名單守衛會退化成只擋現行分頁名")


def test_steps_labels_are_ordinal_plus_tab_label():
    """`_STEPS` 的顯示字必須是「站號 + tab_label」，不得另寫一份。"""
    for _key, _label, _hint in _STEPS:
        assert re.fullmatch(r"[①②③④⑤] .+", _label), f"站號格式壞了：{_label}"
        assert _label.endswith(tab_label(_key)), (
            f"_STEPS 的『{_label}』與 tab_label('{_key}') 對不上 → 又出現第二份標籤")


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
