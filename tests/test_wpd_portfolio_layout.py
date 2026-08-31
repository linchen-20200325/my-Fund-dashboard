"""WP-D：「④ 我的配置」版面重整的守衛（線框 `docs/wireframes/fund-wireframe-final.html` §03）。

本檔守四件事，每一條都經過**突變驗證**（把被守的東西拿掉，該條必須轉紅；
實驗與結果寫在各 test 的 docstring 裡）：

| # | 守什麼 | 方向 |
|---|---|---|
| 1 | container slot 真的能把「顯示順序」與「執行順序」分開 | 前提驗證（釘住整個做法的地基） |
| 2 | slot 的**建立順序** == 線框指定的版面順序 | 雙向 `==`，順序敏感 |
| 3 | slot 的 **`with` 進入順序** == 搬遷前的執行順序 | 雙向 `==`，順序敏感 |
| 4 | 頁內區塊標題**不帶圈號**、指路文案不寫死站號 | fail-closed（不是白名單） |

## 為什麼第 1 條要用真的 Streamlit 跑（不是讀 code）

整個 WP-D 的做法建立在一個**外部框架的行為**上：
「`st.container()` 先建立的先顯示，`with` 先進入的先執行」。
這件事**不是本 repo 能保證的**，它是 streamlit 的實作細節；
釘版 `requirements.txt` 放寬 / streamlit 改行為，整頁順序會默默倒回去
而**沒有任何測試會紅**。第 1 條就是那個地基的守衛。

## 為什麼第 3 條（執行順序）比第 2 條（顯示順序）更要緊

第 2 條紅了 = 版面排錯，肉眼看得到。
**第 3 條紅了 = 數字可能已經變了，而且肉眼看不出來。**
搬遷時實測到~~三處~~**至少四處**「同一次 run 內先寫後讀 / 先讀後寫」的耦合
（`portfolio_core_pct` / `policy_sheet_id` / `gsheet_tokens`，
2026-08-31 獨立稽核補第 4 處 `_schema_ver` —— 保單管理段寫、保單分組視圖讀，
與 `_sheet_id` 同一個顯示條件；原「三處」是單組 AST 掃描漏算了
「寫在抽出的模組、讀在 tab3」的跨檔耦合。**四處是已知清單，不是窮舉**），
只要有人「順手把 `with` 也照版面順序排一排」，那幾處就會翻面 ——
畫面看起來一模一樣，KPI 卡的核心% 卻吃到不同 run 的 slider 值。
這正是 `CLAUDE.md §-2` 說的「肉眼 review 抓不到」的那一種退化。

## ⚠️ 已知守不到的（不要讀成「版面已經守死了」）

- **守不到**：slot 之間的**內容**被搬來搬去（例如把「淨值成長模擬曲線」
  從配置總覽挪進帳本）。本檔只認 slot 的名字與順序，不認每個 slot 裝了什麼。
- **守不到**：把兩個 slot 合併成一個、或改名之後同步改本檔常數 ——
  那會是合法的更新，但也可能是偷偷改版面。**它會出現在 diff 裡**，靠 review。
- **守不到**：`st.markdown` 字串裡手刻 HTML 造出視覺上的另一種順序。
- **守不到（第 4 條）**：用全形數字 `１２３` 或 `(1)(2)(3)` 另起一套頁內編號。
  字表只涵蓋圈號 `①`~`⑩` 與 `⓪`。集合漏一個，規則在那個方向上就是瞎的。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TAB3 = ROOT / "ui" / "tab3_portfolio.py"
T7 = ROOT / "ui" / "tab3_t7_ledger.py"
POLICY_ADMIN = ROOT / "ui" / "helpers" / "portfolio" / "policy_admin_section.py"

#: 圈號字表。⚠️ 只涵蓋這 11 個字元（見檔頭「守不到」）。
CIRCLED = "⓪①②③④⑤⑥⑦⑧⑨⑩"

#: 線框 §03「④ 我的配置」由上到下的版面順序 —— slot 的**建立**順序必須等於這個。
#: 線框原文：「照你實際的操作順序 —— 先加標的 → 看現在長怎樣 → 檢查重疊 → 記帳與再平衡。」
WIREFRAME_DISPLAY_ORDER = (
    "_sec_add",       # 加入與管理基金（沒有標的就沒有配置，這是第一步）
    "_sec_policy",    # 保單管理（Google Sheets）—— WP-E 會把「連線／授權」搬去 ⑤
    "_sec_overview",  # 配置總覽（內含三個子 slot，見 OVERVIEW_SUB_ORDER）
    "_sec_overlap",   # 持股重疊度診斷
    "_sec_ledger",    # 帳本（T7）+ 費用與扣款
    "_sec_ai",        # AI 摘要
    "_sec_raw",       # Raw data（核對數字來源，留最後、不擋路）
)

#: 「配置總覽」段內的子 slot 建立順序（線框：配置總覽本體 + 收進來的三塊）。
OVERVIEW_SUB_ORDER = ("_ov_core", "_ov_warroom", "_ov_group")

#: 搬遷前 `render_portfolio_tab()` 的**執行**順序（= 各區塊在原始檔的行號先後）。
#: ⚠️ 這個順序**刻意與版面順序不同**，理由見檔頭「為什麼第 3 條更要緊」。
PRE_MIGRATION_EXECUTION_ORDER = (
    "_ov_warroom",    # 原 :242-463  智能戰情室 / FX 曝險摘要
    "_sec_overlap",   # 原 :464-603  持股重疊度診斷
    "_sec_raw",       # 原 :605-630  Raw data
    "_sec_policy",    # 原 :637-1426 保單管理（本批抽成獨立模組）
    "_ov_group",      # 原 :1428-1700 保單分組視圖
    "_ov_core",       # 原 :1702-2073 配置總覽 + KPI 卡 + 淨值成長曲線
    "_sec_add",       # 原 :2075-2793 加入與管理基金（含載入 / 清單 / 矩陣 / 健診）
    "_sec_ledger",    # 原 :2795-2822 帳本 + 費用與扣款
    "_sec_ai",        # 原 :2824-2827 AI 摘要
)


def _docstring_ids(tree: ast.AST) -> frozenset[int]:
    """module / class / def 的 docstring 節點 id —— 掃使用者文案時要跳過它們。

    ⚠️ **只跳 docstring，不跳「不是直接餵給 `st.*` 的字串」** —— 這是本檔踩過的坑：
    第一版只掃 `st.*(...)` 的引數，結果突變實驗把 `Tab①` 放進
    `_msg = "…Tab①…"`（之後才 `st.caption(_msg)`）→ **測試全綠**。
    字串先進變數再渲染是本 repo 到處都是的寫法，只認直接引數等於規則是瞎的。
    註解（`#`）本來就不是字串節點，自然不在掃描範圍。
    """
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                out.add(id(first.value))
    return frozenset(out)


def _portfolio_fn() -> ast.FunctionDef:
    tree = ast.parse(TAB3.read_text(encoding="utf-8"))
    return next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "render_portfolio_tab")


def _slot_creation_order(scope: list[ast.stmt]) -> list[str]:
    """`<name> = st.container()` 在這一層 body 出現的先後（= 顯示順序）。"""
    out: list[str] = []
    for stmt in scope:
        if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Attribute)
                and stmt.value.func.attr == "container"):
            out.append(stmt.targets[0].id)
    return out


def _is_slot_declaration_only(stmt: ast.With) -> bool:
    """這個 `with` 只是用來**宣告子 slot**（body 全是 `x = st.container()`），不是執行區塊。"""
    return bool(stmt.body) and len(_slot_creation_order(stmt.body)) == len(stmt.body)


def _with_entry_order(fn: ast.FunctionDef) -> list[str]:
    """`with <slot>:` 在函式 body 出現的先後（= 執行順序）。

    只認**函式頂層**的 `with`，且 context 必須是裸名字 —— `with st.expander(...)`
    之類不會被誤收。⚠️ 同時排除「只用來宣告子 slot」的那個 `with`
    （`with _sec_overview:` 裡面只有三行 `st.container()`）—— 它不執行任何渲染，
    把它算進執行順序會讓本檔第 3 條在守一個不存在的東西。
    """
    out: list[str] = []
    for stmt in fn.body:
        if isinstance(stmt, ast.With) and len(stmt.items) == 1:
            ctx = stmt.items[0].context_expr
            if isinstance(ctx, ast.Name) and not _is_slot_declaration_only(stmt):
                out.append(ctx.id)
    return out


def test_container_slots_decouple_display_from_execution() -> None:
    """地基：`st.container()` 的顯示順序 = 建立順序，與 `with` 執行順序無關。

    整個 WP-D 的版面重整建立在這個 streamlit 行為上。它**不是本 repo 保證的**，
    所以要用真的 streamlit 跑一次，而不是相信註解。

    突變驗證（2026-08-28 實跑）
    --------------------------
    把示範腳本改成「先 `with slot_a` 再 `with slot_b`」（也就是讓執行順序與建立
    順序一致）→ 本條**轉紅**，因為 `exec_order` 會變成 `["A", "B"]`、
    與斷言要求的 `["B", "A"]` 不符。也就是這條測試確實在讀真實行為，不是恆真。
    """
    from streamlit.testing.v1 import AppTest

    script = (
        "import streamlit as st\n"
        "slot_a = st.container()\n"          # 先建立 → 應該先顯示
        "slot_b = st.container()\n"
        "with slot_b:\n"                     # 先執行 → 但應該後顯示
        "    st.markdown('B')\n"
        "    st.session_state['exec'] = st.session_state.get('exec', []) + ['B']\n"
        "with slot_a:\n"
        "    st.markdown('A')\n"
        "    st.session_state['exec'] = st.session_state.get('exec', []) + ['A']\n"
    )
    tmp = pathlib.Path(__file__).parent / "_wpd_slot_probe.py"
    tmp.write_text(script, encoding="utf-8")
    try:
        at = AppTest.from_file(str(tmp))
        at.run()
        display = [m.value for m in at.markdown]
        execution = at.session_state["exec"]
    finally:
        tmp.unlink(missing_ok=True)

    assert display == ["A", "B"], (
        "streamlit 的顯示順序不再等於 container 建立順序 —— "
        "WP-D 的版面重整整個建立在這個行為上。\n"
        f"實測顯示順序 = {display}（預期 ['A', 'B']）。\n"
        "若這是 streamlit 升版造成的，`ui/tab3_portfolio.py` 的版面會默默倒回舊順序，"
        "必須改成真的搬動程式碼（並處理該檔註解列出的三處 session_state 耦合）。")
    assert execution == ["B", "A"], (
        f"執行順序不是 `with` 的進入順序（實測 {execution}）—— "
        "本檔第 3 條（執行順序不准被改）賴以成立的前提消失了。")


def test_slot_creation_order_matches_the_approved_wireframe() -> None:
    """版面：slot 建立順序 == 線框 §03「④ 我的配置」由上到下的順序。

    ⚠️ 雙向 `==` 且**順序敏感** —— 少一個、多一個、換位置都紅。
    客戶已拍板的是這個順序；要改順序就是**改設計**，依 `CLAUDE.md §-1.5.4`
    必須先出線框給客戶拍板，不是改這張表。

    突變驗證（2026-08-28 實跑）
    --------------------------
    把 `ui/tab3_portfolio.py` 的 `_sec_add` 與 `_sec_overview` 兩行建立順序對調
    （＝把「加入基金」排回「配置總覽」之後，也就是線框點名要修的舊毛病）
    → 本條**轉紅**：`['_sec_policy', '_sec_overview', '_sec_add', ...]` != 預期。
    """
    fn = _portfolio_fn()
    assert _slot_creation_order(fn.body) == list(WIREFRAME_DISPLAY_ORDER), (
        "「④ 我的配置」的版面順序與客戶已拍板的線框不符。\n"
        f"實測：{_slot_creation_order(fn.body)}\n"
        f"線框：{list(WIREFRAME_DISPLAY_ORDER)}\n"
        "⚠️ 改版面順序 = 改設計（`CLAUDE.md §-1.5.4` / 線框 §03 ④），"
        "要先出線框給客戶拍板，不是改這張表。")


def test_overview_sub_slot_order_matches_the_wireframe() -> None:
    """版面：「配置總覽」段內三個子 slot 的建立順序。

    線框 §2：「把現在散在頁面上下兩端、其實都在講『現況長怎樣』的三塊收在這裡：
    FX 曝險摘要／智能戰情室、保單分組視圖、淨值成長模擬曲線。」

    突變驗證（2026-08-28 實跑）：把 `_ov_core` 與 `_ov_group` 兩行對調 → 轉紅。
    """
    fn = _portfolio_fn()
    subs = [s for stmt in fn.body if isinstance(stmt, ast.With)
            for s in _slot_creation_order(stmt.body)]
    assert subs == list(OVERVIEW_SUB_ORDER), (
        f"「配置總覽」段內的子區塊順序不符線框。實測 {subs}，"
        f"預期 {list(OVERVIEW_SUB_ORDER)}。")


def test_execution_order_must_stay_exactly_as_before_the_migration() -> None:
    """**最要緊的一條**：`with` 的進入順序 == 搬遷前的執行順序，一步都不准換。

    WP-D 是**版面重整，不是計算改動**（派工規格：「不得改變任何數字的算法」）。
    搬遷時實測到**至少四處**同一次 run 內的 session_state 耦合
    （原文寫「三處」；第 4 處為 2026-08-31 獨立稽核補，非窮舉）：
      1. `portfolio_core_pct` —— slider 在「加入與管理基金」段尾寫，
         「配置總覽」透過 `ui/helpers/portfolio/allocation.py` 讀。
         搬遷前是**先讀後寫**；一旦調換就變**先寫後讀**，KPI 卡的核心%
         會吃到不同 run 的 slider 值。
      2. `policy_sheet_id` —— 保單管理段寫、加入基金段讀。
      3. `gsheet_tokens` —— 加入基金段寫、保單管理段讀。
      4. `_schema_ver` —— 保單管理段（`policy_admin_section.py`）寫、
         「保單分組視圖」讀（「🔗 綁到保單」顯示條件，與 `_sheet_id` 同一個 `if`）。
         搬遷前是**先寫後讀**；調換會讓下拉吃到上一次 run 的 schema 判定。
    這幾處都會**改變畫面上的數字或顯示條件**，而且**畫面排版看起來完全一樣**。

    突變驗證（2026-08-28 實跑）
    --------------------------
    把 `with _sec_add:` 整段移到 `with _ov_core:` 之前（＝「順手讓執行順序也照
    版面走」，這正是最可能發生的那種好意改動）→ 本條**轉紅**，
    而 `test_slot_creation_order_matches_the_approved_wireframe` 仍然綠 ——
    證明少了本條就真的沒有人在看執行順序。
    """
    fn = _portfolio_fn()
    assert _with_entry_order(fn) == list(PRE_MIGRATION_EXECUTION_ORDER), (
        "`render_portfolio_tab()` 的區塊執行順序變了。\n"
        f"實測：{_with_entry_order(fn)}\n"
        f"搬遷前：{list(PRE_MIGRATION_EXECUTION_ORDER)}\n"
        "⚠️ 版面順序由 container **建立**順序決定（見上一條），"
        "**不需要**也**不可以**靠調換 `with` 來排版 —— "
        "調換 `with` 會改到 `portfolio_core_pct` / `policy_sheet_id` / `gsheet_tokens` / "
        "`_schema_ver`（至少四處，已知非窮舉）同一次 run 內的先寫後讀關係，"
        "畫面一樣、數字會變。\n"
        "真要改執行順序，請先**重掃**所有跨段 / 跨模組耦合（不要只處理被點名的），"
        "並在 PR 說明改了哪個數字。")


def test_display_and_execution_orders_are_actually_different() -> None:
    """錨點：兩張表若哪天變成一樣，上面兩條就在對空氣生效。

    不加這條，有人把 `PRE_MIGRATION_EXECUTION_ORDER` 直接複製成
    `WIREFRAME_DISPLAY_ORDER` 的內容、再把 code 一起改成同序 —— 兩條都綠，
    但「顯示 / 執行分離」這個保護已經沒了。

    突變驗證（2026-08-28 實跑）
    --------------------------
    把 `PRE_MIGRATION_EXECUTION_ORDER = WIREFRAME_DISPLAY_ORDER` → 本條**轉紅**。
    ⚠️ 據實記錄：本條的第一版突變（在執行順序表**前面插入**版面順序表）
    得到 **GREEN** —— 那是**突變設計錯了**（插入後長度變了、過濾出重複元素，
    自然不相等），不是規則有洞。重新設計成「整個抄過去」才是這條要防的形狀。
    """
    assert list(WIREFRAME_DISPLAY_ORDER) != [
        s for s in PRE_MIGRATION_EXECUTION_ORDER if s in WIREFRAME_DISPLAY_ORDER
    ], ("版面順序與執行順序已經一致 —— 那代表要嘛真的搬了程式碼（那就要處理三處"
        "session_state 耦合並更新本檔），要嘛有人把表抄成一樣。兩種都要在 PR 講清楚。")


@pytest.mark.parametrize("path", [TAB3, T7, POLICY_ADMIN], ids=lambda p: p.name)
def test_no_in_page_section_numbering_in_headings(path: pathlib.Path) -> None:
    """頁內標題不得帶圈號 —— 線框 §04「頁內：純標題階層，不編號」。

    ⚠️ 2026-08-31 獨立稽核補 `POLICY_ADMIN` 進掃描範圍：這 790 行是**同一頁**的
    內容，WP-D 把它抽成模組的同時也把它抽出了本規則的射程 —— 第一版只掃
    TAB3 / T7，等於規則誕生當天就有 1/3 的頁面在規則外（實測現況 0 違規，
    加入後仍綠；docstring 內的 ④⑤ 是跨分頁站號文件，不是渲染標題，掃不到是對的）。

    盤點認定本頁的病是「畫面順序 ④→①→②→③」：同一頁用圈號同時表達
    **區塊站號**、**表格準則序號**、**跨分頁站號**三種不同語意。
    收斂方式是把**區塊站號**整組拿掉（頂層 ①~⑤ 只留在分頁列，由
    `ui/helpers/story_nav.py` 這個既有 SSOT 產生）。

    ⚠️ 本條只管 **`st.markdown("### …")` / `st.subheader(…)` 這類標題**，
    **不管**內文與 caption 裡的內容清單標記 —— 例如 3-3-3 表格底下的
    「②來源…」對應的是該表**真實存在的欄名** `②3年年化` / `②通過`
    （`services/fund_screening.py::batch_333_funds`），持倉健診的
    「① 健康分析 / ② 配息相關 / ③ 實際購買結果」對應的是它真的渲染的三張表。
    那些是**內容標記**不是**區塊編號**，拿掉會讓文案指不到東西。

    突變驗證（2026-08-28 實跑）
    --------------------------
    把 `st.markdown("### 📊 配置總覽 — 你的組合現況")` 改回
    `st.markdown("### 📊 ① 配置總覽 — 你的組合現況")` → 本條**轉紅**，
    訊息指名該行。四個標題逐一試過，四次都紅。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in ("markdown", "subheader", "header", "title"):
            continue
        if not node.args:
            continue
        first = node.args[0]
        text = first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else (
            "".join(v.value for v in first.values
                    if isinstance(v, ast.Constant) and isinstance(v.value, str))
            if isinstance(first, ast.JoinedStr) else "")
        if not text.lstrip().startswith("#"):
            continue                      # 不是標題（`st.markdown` 也拿來畫 HTML 卡片）
        if any(c in text for c in CIRCLED):
            bad.append(f"{path.name}:{node.lineno}  {text.strip()[:70]}")
    assert not bad, (
        "頁內標題出現圈號 —— 線框 §04 拍板「頁內：純標題階層，不編號；"
        "頂層 ①~⑤ 決策站號只用在分頁列」。\n"
        "頁內編號正是盤點點名的「6 套互相衝突」的來源（同一頁同時有區塊站號、"
        "表格準則序號、跨分頁站號三種語意共用同一批字元）。\n  " + "\n  ".join(bad))


def test_tab_station_numbers_are_not_hardcoded_in_user_facing_text() -> None:
    """指路文案不得寫死「Tab①」這種站號 —— 分頁名／站號的 SSOT 是 `story_nav`。

    2026-08-05 稽核 🔴 必修 2 的根因就是「標籤沒有 SSOT」，三處文案指向不存在的
    分頁名。站號同理：分頁順序一改，寫死的「Tab①」就開始說謊，
    而且**沒有任何東西會報錯**。

    突變驗證（2026-08-28 實跑，**第一版沒過，據實記錄**）
    ------------------------------------------------
    把 `ui/tab3_portfolio.py` 的 VIX 缺值提示改回
    `"想補上：先到 🌐 Tab① 按「📡 載入總經資料」，再回本頁。"`：
    - **第一版規則（只掃 `st.*(...)` 的直接引數）→ 全綠，沒抓到。**
      因為那句話是先寫進 `_msg` 變數、之後才 `st.caption(_msg)` ——
      規則看不到。**這正是「規則對空氣生效」的實例，不是理論風險。**
    - 改成「掃所有字串常數、只跳 docstring」之後 → **轉紅**，訊息指名該行。
    """
    import re
    pat = re.compile(r"Tab\s*[" + CIRCLED + r"]")
    bad: list[str] = []
    for path in (TAB3, T7, POLICY_ADMIN):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and id(node) not in _docstring_ids(tree):
                for m in pat.finditer(node.value):
                    bad.append(f"{path.name}:{node.lineno}  …{m.group(0)}…")
    assert not bad, (
        "文案寫死了分頁站號（`Tab①` 之類）。分頁名與站號的唯一真相源是 "
        "`ui/helpers/story_nav.py::tab_label`；寫死一份 = 第二個真相源，"
        "分頁順序一改它就開始說謊而且不會報錯。\n  " + "\n  ".join(bad))


def test_policy_admin_block_is_extracted_and_still_wired() -> None:
    """保單管理區塊已抽成獨立模組，且 `tab3_portfolio` 仍然呼叫它、仍然收回 `_sheet_id`。

    這條同時守兩個相反方向：
    - **抽出去了嗎**：`tab3_portfolio` 不該再自己畫那個 expander。
    - **還接著嗎**：抽出去但忘了接 → 整段畫面消失，而 import 測試不會紅。
    - **`_sheet_id` 有交還嗎**：它原本是同一個函式的區域變數，「保單分組視圖」
      的「🔗 綁到保單」要讀它。忘了接回來 → `NameError` 只在**已登入 OAuth 且
      Sheet 已升 v2** 的使用者身上炸，測試環境完全踩不到。

    突變驗證（2026-08-28 實跑，三個方向各一次）
    -------------------------------------------
    1. 把 `_sheet_id = _render_policy_admin(...)` 改成不接回傳值
       （`_render_policy_admin(...)`）→ 本條**轉紅**（第 3 個斷言）。
    2. 把整個 `with _sec_policy:` 區塊刪掉 → 本條**轉紅**（第 2 個斷言）。
    3. 在 `tab3_portfolio` 貼回一行 `st.expander("📋 保單管理（Google Sheets）…")`
       → 本條**轉紅**（第 1 個斷言）。
    """
    # ⚠️ 認的是**實作**（畫出那個 expander 的呼叫），不是「檔案裡有沒有提到這幾個字」——
    # `tab3_portfolio` 有一句合法的指路文案「展開上方「📋 保單管理（Google Sheets）」→
    # 按「📥 雲端讀取」」，那是**指路**不是**重複實作**，不該被判違規。
    def _renders_policy_expander(tree: ast.AST) -> bool:
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "expander" and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and "保單管理（Google Sheets）" in str(node.args[0].value)):
                return True
        return False

    assert not _renders_policy_expander(ast.parse(TAB3.read_text(encoding="utf-8"))), (
        "「保單管理（Google Sheets）」的實作又出現在 `ui/tab3_portfolio.py` —— "
        "它已於 WP-D 抽到 `ui/helpers/portfolio/policy_admin_section.py`，"
        "WP-E 要把「連線／授權」那半搬去 ⑤。兩份實作 = "
        "`CLAUDE.md §-1.5.1c v3 §01-2` 明禁的重複視圖。")
    assert _renders_policy_expander(ast.parse(POLICY_ADMIN.read_text(encoding="utf-8"))), (
        "`policy_admin_section.py` 裡找不到保單管理區塊 —— 抽出的內容不見了。")

    fn = _portfolio_fn()
    calls = [n for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_render_policy_admin"]
    assert len(calls) == 1, (
        f"`render_portfolio_tab()` 對 `_render_policy_admin` 的呼叫有 {len(calls)} 處"
        "（預期 1）—— 抽出去之後忘了接，畫面上整段保單管理會直接消失，"
        "而 import / smoke 測試都不會紅。")

    assigned = [n for n in ast.walk(fn)
                if isinstance(n, ast.Assign) and n.value in calls
                and any(isinstance(t, ast.Name) and t.id == "_sheet_id" for t in n.targets)]
    assert assigned, (
        "`_render_policy_admin(...)` 的回傳值沒有接進 `_sheet_id`。\n"
        "`_sheet_id` 原本是 `render_portfolio_tab()` 的區域變數，"
        "下方「🗂️ 保單分組視圖」的「🔗 綁到保單」條件要讀它。\n"
        "⚠️ 不接會是 `NameError`，而且只在**已登入 OAuth + Sheet 已升 v2** 的"
        "使用者身上炸 —— 測試環境踩不到。")
