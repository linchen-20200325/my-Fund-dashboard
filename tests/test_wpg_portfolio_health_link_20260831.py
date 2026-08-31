"""WP-G：「④ 我的配置」的 💊 持倉健診改為**單行連結**（客戶 2026-08-31 直接指派：
「各頁不重複渲染相同功能 …… ④ 健診改單行連結」）。

## 這一批到底改了什麼（一句話）

④ 頁**不再渲染**健診 3 表（`ui.tab_fund_grp_health._render_health_3tables`），
改成一行灰字指路 → ② 組合健診；**但健診的「計算」原封不動保留**。

## ⚠️ 為什麼「只移除渲染、保留計算」——本檔最重要的一條

④ 那段健診區其實是**兩件事疊在一起**：

```
ThreadPool(process_one_fund) → _health_results → _ok_health → _funds_extra
                                                                  │
                    ┌─────────────────────────────────────────────┤
                    ↓                    ↓                        ↓
        _render_health_3tables   render_rotation_section   render_portfolio_performance
             （← 本次移除）        （🔄 輪動配對，留）        / render_efficient_frontier
                                                                （📊 績效 / 🎯 效率前緣，留）
```

`_funds_extra` 是**後面三個區塊的資料前置**，而那三個區塊**不在**本次授權範圍
（客戶只說健診）。**把整段拔掉 → 那三區會靜默變空**（比沒有數字更危險，`CLAUDE.md` §1）。
`test_health_precompute_and_downstream_sections_preserved` 就是這條的守衛。

## 為什麼「移除渲染」不會讓後面的區塊讀到舊值 / 缺值

因為健診的**渲染鏈路是純顯示** —— 實測（`test_health_render_chain_is_display_only`）：
`_render_health_3tables` / `_render_health_table` 全鏈路**零 `st.session_state[...] = ` 寫入**，
只有兩處 `.get("phase_info")` 讀進區域變數。**沒有「先寫後讀」的耦合可以被拔斷。**

這一條是本次最大的風險，所以它不是靠 review 講一句「我看過了」，而是寫成 fail-closed 斷言：
**日後有人在健診渲染鏈路裡加一個 `st.session_state[...] = `，本檔會轉紅**，
逼他回來重新想「④ 拔掉渲染之後，那個值誰來寫」。

## ⚠️ 為什麼全部用 AST，不用字串掃描

移除後的程式碼裡，**註解仍然寫著** `_render_health_tbl(...)`、
`from ui.tab_fund_grp_health import _render_health_3tables`
（刻意留著，說明「原本是什麼、為什麼拿掉」）。
一個 `grep "_render_health_3tables" ui/tab3_portfolio.py` 會**命中註解而誤判成沒改乾淨**；
反過來，`assert "_render_health_3tables" not in source` 這種寫法會**因為註解而永遠紅**，
逼下一個人把說明砍掉才能過測 —— 那是用測試逼人刪掉解釋，很糟。
**AST 只看真的會執行的東西，註解天生不在裡面。**

## ⚠️ 已知守不到的（不要讀成「重複渲染已經守死了」）

- **守不到**：有人用 `getattr(importlib.import_module("ui.tab_fund_grp_health"),
  "_render_health_3tables")` 這種動態寫法把健診表叫回來 —— AST 看不出那是什麼。
  第 1、2 條是**形態偵測**，不是語意證明。
- **守不到**：把健診 3 表的內容**複製一份**到 ④（不 import、自己重寫一遍）。
  本檔認的是「有沒有呼叫那個函式」，不是「畫面上有沒有出現健診表」。
- **守不到**：其他分頁（②以外）另外 embed 一次健診。本檔只看 `ui/tab3_portfolio.py`。
- **守不到**：單行連結被改成兩行、三行。第 3 條守的是「沒有標題、沒有卡片、
  沒有多出來的 `st.markdown` 區塊」，**不是**字數。

## 突變驗證（每條都實跑過，結果見各 test 的 docstring）

`CLAUDE.md` §-1.5 v3 §03-1「突變測試（拔掉修復邏輯必須轉為紅燈）」。
不能轉紅的斷言 = 沒有守到任何東西。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TAB3 = ROOT / "ui" / "tab3_portfolio.py"
HEALTH = ROOT / "ui" / "tab_fund_grp_health.py"

#: ② 健診端的渲染入口。④ 一旦再出現對它的呼叫，就是重複渲染回來了。
HEALTH_RENDER_FUNCS = frozenset({
    "_render_health_3tables",
    "_render_health_table",
})

#: 健診資料算完之後、**仍留在 ④** 的三個下游區塊。它們吃 `_funds_extra`。
#: 拔掉健診計算 = 這三個一起靜默變空 —— 那是本次最該防的退化。
DOWNSTREAM_SECTIONS = (
    "render_rotation_section",
    "render_portfolio_performance",
    "render_efficient_frontier",
)


# ══════════════════════════════════════════════════════════════════════════
# AST 小工具
# ══════════════════════════════════════════════════════════════════════════
def _parse(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _func(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(
        f"找不到函式 `{name}` —— 它被改名或刪掉了。這不是「測試過期」可以打發的："
        f"本檔所有斷言都掛在它身上，找不到它就等於整批守衛靜默失效。"
    )


def _call_name(call: ast.Call) -> str:
    """取呼叫端最末一段名字：`f()` → 'f'、`m.f()` → 'f'、其餘 → ''。"""
    fn = call.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return ""


def _dotted(node: ast.AST) -> str:
    """`st.caption` → 'st.caption'；非 Attribute/Name 鏈則回 ''。"""
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001 — 只是取名字，取不到就當空
        return ""


def _calls(node: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(node) if isinstance(n, ast.Call)]


def _health_block(tab3_tree: ast.Module) -> ast.If:
    """定位 ④ 的健診區塊 —— 即那個 `if _loaded_pf:`。

    **刻意不用行號、也不用「第幾個 If」定位**（兩者都會在下次重排時默默指到別處）：
    改用「這個 If 底下有呼叫 `render_rotation_section`」當識別特徵 ——
    那是健診算完之後緊接著的第一個下游區塊，跟健診計算綁在同一個 try 裡。
    """
    fn = _func(tab3_tree, "render_portfolio_tab")
    hits = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.If)
        and any(_call_name(c) == "render_rotation_section" for c in _calls(n))
    ]
    assert hits, (
        "在 `render_portfolio_tab` 裡找不到「含 render_rotation_section 的 if 區塊」。"
        "健診區塊被整段搬走或重寫了 —— 請先確認 ④ 的輪動配對 / 組合績效 / 效率前緣還在，"
        "再更新本檔的定位方式。"
    )
    # 巢狀時取**最內層**那一個（body 最小者），避免抓到外層包住半頁的 if。
    return min(hits, key=lambda n: (n.end_lineno or 0) - n.lineno)


# ══════════════════════════════════════════════════════════════════════════
# 1) ④ 不再 import 健診渲染（fail-closed：不是白名單，是「一個都不准有」）
# ══════════════════════════════════════════════════════════════════════════
def test_tab3_does_not_import_health_render():
    """④ 不得從 `ui.tab_fund_grp_health` import 任何健診渲染函式（**含改別名**）。

    為什麼守 import 而不只守呼叫：**沒有 import 就叫不到**（動態 import 除外，
    見檔頭「守不到」）。這是成本最低、最難繞過的那一道。

    突變實驗（實跑）：把 `from ui.tab_fund_grp_health import _render_health_3tables
    as _render_health_tbl` 加回 `ui/tab3_portfolio.py` → **本條轉紅**
    （`AssertionError: ④ 又 import 了健診渲染函式：[('_render_health_3tables',
    '_render_health_tbl')]`）。還原後轉綠。
    """
    tree = _parse(TAB3)
    offenders = [
        (alias.name, alias.asname)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name in HEALTH_RENDER_FUNCS
        # 別名不設限：改叫什麼都算（`as _foo` 一樣抓得到，因為比對的是 alias.name）
    ]
    assert offenders == [], (
        f"④ 又 import 了健診渲染函式：{offenders}。\n"
        f"WP-G 的要求是「④ 不重複渲染健診，只留一行連結指向 ②」。"
        f"若確定要讓 ④ 重新畫健診表，那是**版面變更**，依 `CLAUDE.md` §-1.5 v3 §03-2 ①"
        f"要先出線框草稿給客戶拍板，不能靠改測試放行。"
    )


# ══════════════════════════════════════════════════════════════════════════
# 2) ④ 不再呼叫健診渲染（守「用」，補上第 1 條守不到的既有別名路徑）
# ══════════════════════════════════════════════════════════════════════════
def test_tab3_does_not_call_health_render():
    """`render_portfolio_tab` 內不得出現健診渲染函式的呼叫。

    第 1 條守 import、本條守呼叫 —— 兩條都要，因為兩者各自有繞過方式：
    只守 import → 有人改用 `ui.tab_fund_grp_health._render_health_3tables(...)`
    的完整路徑呼叫（那不是 `ImportFrom`）；只守呼叫 → 有人 import 了先擺著。

    ⚠️ **註解不會誤觸本條**：移除處刻意留了一段說明，字面寫著
    `_render_health_tbl(_ok_health, ...)`。AST 不含註解，所以那段說明可以安心留著 ——
    這正是本檔不用字串掃描的理由（見檔頭）。

    突變實驗（實跑）：把 `_render_health_tbl(_ok_health, funds_extra=_funds_extra,
    source_tab="portfolio")` 這行**取消註解**放回去 → **本條轉紅**
    （`AssertionError: ④ 又呼叫了健診渲染：['_render_health_tbl']`）。還原後轉綠。
    """
    fn = _func(_parse(TAB3), "render_portfolio_tab")
    # 既有的別名 `_render_health_tbl` 也要認 —— 它是這次被移除的那個名字，
    # 最可能被原封不動貼回來。
    banned = HEALTH_RENDER_FUNCS | {"_render_health_tbl"}
    offenders = sorted({n for c in _calls(fn) if (n := _call_name(c)) in banned})
    assert offenders == [], (
        f"④ 又呼叫了健診渲染：{offenders}。理由同上一條。"
    )


# ══════════════════════════════════════════════════════════════════════════
# 3) 單行連結存在、走 SSOT、而且真的只有「一行」
# ══════════════════════════════════════════════════════════════════════════
def test_tab3_health_block_has_single_line_link_via_ssot():
    """健診區塊裡必須有**恰好一個** `st.caption`，其內容以 f-string 內嵌
    `tab_label('health')`（分頁名 SSOT）；且該區塊**不得**再有 `###` 標題。

    三件事一起守，因為它們是同一個要求的三面：
    - **有連結**：`tab_label('health')` 出現在 caption 裡（不是別的 key）；
    - **走 SSOT**：是**呼叫**取得，不是寫死字串（寫死由第 4 條再補一刀）；
    - **只有一行**：`###` 標題數 == 0 —— 客戶說「單行連結」，不是「換一張卡片」。

    ⚠️ 這裡只數**直接寫在該 If 底下**的 `st.markdown('###...')`；
    下游 `render_rotation_section` 等函式**自己**印的 `###` 標題不在本檔射程內
    （它們是各自區塊的標題，本來就該有，且本次未動）。

    突變實驗（實跑，三次）：
    1. 刪掉那個 `st.caption(...)` → 轉紅（`找不到指向 ② 的單行連結`）；
    2. 把 `_tab_label_t3('health')` 換成 `_tab_label_t3('portfolio')` → 轉紅（同上）；
    3. 把 `### 💊 持倉健診（共用 SSOT 3 表…）` 那行 `st.markdown` 加回去 → 轉紅
       （`健診區塊又多了 1 個 '###' 標題`）。三次還原後皆轉綠。
    """
    block = _health_block(_parse(TAB3))

    # (a) 找 caption：f-string 裡有 `<某某>('health')` 的呼叫。
    #     刻意用「呼叫 + 參數 'health'」認人，不認函式叫什麼名字 ——
    #     `tab_label` 在本檔是 `as _tab_label_t3` 匯入的，寫死名字反而會誤判。
    link_captions = []
    for call in _calls(block):
        if _dotted(call.func) != "st.caption":
            continue
        for arg in call.args:
            if not isinstance(arg, ast.JoinedStr):
                continue
            inner = [
                c for v in arg.values if isinstance(v, ast.FormattedValue)
                for c in _calls(v)
            ]
            if any(
                len(c.args) == 1
                and isinstance(c.args[0], ast.Constant)
                and c.args[0].value == "health"
                for c in inner
            ):
                link_captions.append(call)

    assert len(link_captions) == 1, (
        f"找不到指向 ② 的單行連結，或找到不只一個（實得 {len(link_captions)} 個）。\n"
        f"要求：健診區塊裡恰好一個 `st.caption(f\"…{{tab_label('health')}}…\")`。\n"
        f"分頁名**必須**取自 `ui/helpers/story_nav.tab_label`（SSOT）—— "
        f"寫死「💊 組合健診」的話，② 改名時這行會默默指向一個不存在的分頁"
        f"（2026-08-05 稽核 🔴 必修 2 的原始事故就是這個）。"
    )

    # (b) 灰色說明語意：不得用 st.error / st.warning 講「功能在別頁」。
    #     那不是系統故障（三態顏色分離）。
    #     判準：那三個 API 裡不得出現「內嵌 `<某某>('health')`」的 f-string ——
    #     也就是「指路句被畫成紅字 / 黃字」這個具體形態。
    #     ⚠️ 區塊裡既有的 `system_error(...)`（真的算爆了）不在此列，也不該被動到。
    miscolored = []
    for call in _calls(block):
        if _dotted(call.func) not in ("st.error", "st.warning", "st.info"):
            continue
        for arg in call.args:
            if not isinstance(arg, ast.JoinedStr):
                continue
            for v in arg.values:
                if not isinstance(v, ast.FormattedValue):
                    continue
                for c in _calls(v):
                    if (len(c.args) == 1 and isinstance(c.args[0], ast.Constant)
                            and c.args[0].value == "health"):
                        miscolored.append(f"{_dotted(call.func)}@L{call.lineno}")
    assert miscolored == [], (
        f"指路訊息被畫成非灰色狀態：{miscolored}。\n"
        f"「功能搬到別頁」是**灰色說明**（`st.caption`），不是系統故障 —— "
        f"三態顏色分離：未載入=灰／系統錯=紅／業務警示=業務色；"
        f"假紅字會讓真正的錯誤沒人看得見。"
    )

    # (c) 只有一行：該 If 底下不得再有 `###` 區塊標題。
    headings = [
        c for c in _calls(block)
        if _dotted(c.func) in ("st.markdown", "st.subheader", "st.header")
        and c.args
        and isinstance(c.args[0], ast.Constant)
        and isinstance(c.args[0].value, str)
        and "###" in c.args[0].value
    ]
    assert not headings, (
        f"健診區塊又多了 {len(headings)} 個 '###' 標題："
        f"{[c.args[0].value[:40] for c in headings]}。\n"
        f"客戶要的是**單行連結**，不是把健診換成另一個帶標題的區塊。"
    )


# ══════════════════════════════════════════════════════════════════════════
# 4) 分頁名不得寫死（SSOT，fail-closed；期望值本身由 SSOT 現場取得）
# ══════════════════════════════════════════════════════════════════════════
def test_tab3_does_not_hardcode_health_tab_label():
    """`ui/tab3_portfolio.py` 的任何字串常數都不得含 ② 的分頁名字面值。

    ⚠️ 本條**不寫死**「💊 組合健診」四個字 —— 期望值是 runtime 從
    `story_nav.tab_label('health')` 取的。② 改名時本條會跟著改對象，
    不會變成一條守著舊名字的殭屍斷言。

    突變實驗（實跑）：把單行連結改成寫死的
    `st.caption("💊 持倉健診請看「💊 組合健診」分頁")` → **本條轉紅**
    （`AssertionError: ④ 有 1 處寫死了 ② 的分頁名 '💊 組合健診'`）。還原後轉綠。
    """
    story_nav = pytest.importorskip(
        "ui.helpers.story_nav",
        reason="story_nav 匯入失敗時本條無法取得 SSOT 期望值；由既有 story_nav 測試把關",
    )
    label = story_nav.tab_label("health")
    assert label, "tab_label('health') 回空字串 —— SSOT 本身壞了，先修它。"

    hardcoded = [
        node.value
        for node in ast.walk(_parse(TAB3))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and label in node.value
    ]
    assert hardcoded == [], (
        f"④ 有 {len(hardcoded)} 處寫死了 ② 的分頁名 {label!r}："
        f"{[h[:50] for h in hardcoded]}\n"
        f"請改用 `ui.helpers.story_nav.tab_label('health')`。"
    )


# ══════════════════════════════════════════════════════════════════════════
# 5) ⭐ 耦合守衛：健診「計算」與三個下游區塊都必須還在
# ══════════════════════════════════════════════════════════════════════════
def test_health_precompute_and_downstream_sections_preserved():
    """移除的只有**渲染**；健診**計算**與吃它的三個下游區塊必須原封不動。

    **本檔最重要的一條。** 前面幾條紅了 = 重複渲染跑回來（看得見、不會算錯數字）；
    **本條紅了 = ④ 的輪動配對 / 組合績效 / 效率前緣可能已經靜默變空**——
    畫面上就是「那幾區不見了」，而沒有任何錯誤訊息（`CLAUDE.md` §1 點名最危險的那種）。

    守三樣東西，缺一不可：
    - `process_one_fund`（健診逐檔計算，`_health_results` 的來源）仍被 import；
    - `_funds_extra` 仍在健診區塊內被賦值（三個下游的唯一輸入）；
    - 三個下游區塊仍被呼叫。

    突變實驗（實跑，兩次）：
    1. 刪掉 `_funds_extra = [...]` 那段 list comprehension → 轉紅
       （`健診區塊內找不到 _funds_extra 的賦值`）；
    2. 刪掉 `render_portfolio_performance(_funds_extra)` 這行 → 轉紅
       （`④ 少了下游區塊：['render_portfolio_performance']`）。兩次還原後皆轉綠。
    """
    tree = _parse(TAB3)
    block = _health_block(tree)

    # (a) 逐檔健診計算仍在
    imported = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "process_one_fund" in {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }, (
        "④ 不再 import `services.fund_row.process_one_fund` —— 健診計算被拔掉了。\n"
        "WP-G 只授權移除**渲染**：`_funds_extra` 是輪動配對 / 組合績效 / 效率前緣的"
        "資料前置，計算一拔，那三區會靜默變空。"
    )
    assert imported, "ImportFrom 掃描結果為空，AST 解析可能出錯"

    # (b) `_funds_extra` 仍在健診區塊內被賦值
    assigned = {
        t.id
        for n in ast.walk(block) if isinstance(n, ast.Assign)
        for t in n.targets if isinstance(t, ast.Name)
    }
    assert "_funds_extra" in assigned, (
        "健診區塊內找不到 `_funds_extra` 的賦值。它是三個下游區塊的唯一輸入，"
        "沒有它 = 那三區拿不到資料。"
    )

    # (c) 三個下游區塊仍被呼叫
    called = {_call_name(c) for c in _calls(block)}
    missing = [s for s in DOWNSTREAM_SECTIONS if s not in called]
    assert not missing, (
        f"④ 少了下游區塊：{missing}。\n"
        f"這三個**不在** WP-G 的授權範圍（客戶只說健診），不得順手一起移除 ——"
        f"夾帶移除功能屬 `CLAUDE.md` §-1.5.3 C 明禁的行為。"
    )


# ══════════════════════════════════════════════════════════════════════════
# 6) ⭐「移除渲染是安全的」這個前提本身的守衛
# ══════════════════════════════════════════════════════════════════════════
def test_health_render_chain_is_display_only():
    """健診渲染鏈路必須**零 `st.session_state[...] = ` 寫入**（純顯示）。

    這條守的是**本次決策賴以成立的前提**，不是程式碼的某個行為。

    ④ 之所以敢「只拿掉渲染、留著計算」，靠的就是「渲染不寫任何 session_state」——
    若渲染其實會寫，而 ④ 後面的區塊讀它，拿掉渲染就會讓後面讀到**舊值或缺值**，
    而且**畫面完全看不出來**。實測（本條）目前為零寫入。

    日後有人在 `_render_health_3tables` / `_render_health_table` 裡加一個
    `st.session_state[...] = `，本條會轉紅 —— 那不是「測試擋路」，
    是在提醒他：**④ 已經沒有在跑這段渲染了，你寫的那個值在 ④ 不會被寫入。**

    ⚠️ 只涵蓋這兩個函式本體，**不遞迴進它們呼叫的其他模組**
    （`_render_low_base_screener` / `render_mutual_exclusion_section` / `columns` 等）。
    「整條鏈路零寫入」是更強的宣稱，本條**沒有**證明到那個程度。

    突變實驗（實跑）：在 `_render_health_3tables` 開頭插入
    `st.session_state["_wpg_probe"] = 1` → **本條轉紅**
    （`AssertionError: 健診渲染鏈路出現 session_state 寫入`）。還原後轉綠。
    """
    tree = _parse(HEALTH)
    writes: list[str] = []
    for name in HEALTH_RENDER_FUNCS:
        fn = _func(tree, name)
        for node in ast.walk(fn):
            targets: list[ast.AST] = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]
            for t in targets:
                # 只認 `<...>.session_state[...] = ...` 這種真寫入；
                # `x = st.session_state.get(...)` 是讀，target 是 Name，不會命中。
                if isinstance(t, ast.Subscript) and "session_state" in _dotted(t.value):
                    writes.append(f"{name}:{node.lineno}: {_dotted(t)}")

    assert writes == [], (
        f"健診渲染鏈路出現 session_state 寫入：{writes}\n"
        f"④（我的配置）自 WP-G 起**不再呼叫這段渲染** —— 你在這裡寫的值，"
        f"在 ④ 那一頁永遠不會被寫入。若 ④ 有東西要讀它，請把寫入移到"
        f"`ui/tab3_portfolio.py` 仍在執行的**計算**段，不要留在渲染裡。"
    )


# ══════════════════════════════════════════════════════════════════════════
# 7) ② 是健診唯一主場 —— 本批不得動到它
# ══════════════════════════════════════════════════════════════════════════
def test_health_tab_still_renders_3tables():
    """② 組合健診仍以 `source_tab="health"` 呼叫 `_render_health_3tables`。

    WP-G 是「④ 不重複渲染」，**不是**「健診整個下線」。
    ④ 的那一行連結指向 ②；② 若也不畫了，使用者會被指到一個空頁 ——
    那比原本的重複渲染更糟。

    突變實驗（實跑）：把 `render_fund_grp_health_tab` 裡的
    `_render_health_3tables(rows, …, source_tab="health")` 註解掉 → **本條轉紅**
    （`AssertionError: ② 不再呼叫健診 3 表渲染`）。還原後轉綠。
    """
    fn = _func(_parse(HEALTH), "render_fund_grp_health_tab")
    hits = [c for c in _calls(fn) if _call_name(c) == "_render_health_3tables"]
    assert hits, (
        "② 不再呼叫健診 3 表渲染 —— ④ 的單行連結會把使用者指到一個沒有健診的分頁。"
    )
    assert any(
        any(kw.arg == "source_tab"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value == "health"
            for kw in c.keywords)
        for c in hits
    ), (
        "② 呼叫健診 3 表時不再傳 `source_tab=\"health\"`。該參數決定「等權 → 去填金額」"
        "導引與 🧭 核心/衛星指路句要指向哪裡；④ 已不再是 caller，② 這一路不得跟著壞掉。"
    )
