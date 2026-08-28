"""鐵律 4：首屏無冗餘占位 —— fail-closed 的允許表，不是關鍵字白名單。

## 為什麼非有這個檔不可（實測，不是推測）

2026-08-28 稽核組突變實測：在 `app.py` 的 `st.tabs(...)` **之前**插入
`st.info(...)` + `st.caption(...)` + 空的 `st.markdown("&nbsp;")` ——
**fast lane 與 slow lane 全綠**。同一輪一共注入 5 個違反四大鐵律的改動，
全 suite 結果與基線**逐項相同**（`14 failed / 5347 passed`）。

現有的守衛只有 `test_render_state_color_separation.py::
test_q3_home_page_no_longer_prints_a_key_notice`，而它認的是
`FRED_KEY` / `GEMINI_KEY` 這類**憑證字樣** —— 換一句話就繞過去了。
它守的是「金鑰提示不要回來」這個**更窄、更精準**的語意，本檔**不取代它**，
兩條並存取嚴（`CLAUDE.md` 既有慣例：舊條文保留不刪）。

## 為什麼首屏特別要緊

`app.py` 的 module top-level 在**每一次 rerun** 都無條件執行，而 `st.tabs` 的
七個分頁是**同一次 run 全部渲染**的。所以 `st.tabs` 之前的任何一句話，
**七個分頁的最上方都看得到**，而且是使用者第一眼看到的東西。
在那裡放一句可有可無的說明 ＝ 把最貴的版面拿去印廢話。

## 判定方向：fail-closed 的**允許表**（本檔最重要的設計決定）

⚠️ **刻意不用關鍵字白名單** —— 換個文案就繞過去，那正是既有 Q3 規則的邊界。
本檔的規則是：首屏範圍內**每一個渲染呼叫**，只要不在 `FIRST_SCREEN_ALLOWED`
的具名允許表內就紅。

⚠️ **`st.markdown` 不整個放行**（本規格最容易做錯的一點）：
首屏那一大塊 CSS 就是 `st.markdown(f"<style>…")`，若為了讓它過而把
`st.markdown` 整個列進允許表，`st.markdown("&nbsp;")` 這種空占位就會混過去 ——
而那正是 M5 突變的第三招。故允許條件收成**參數必須是以 `<style` 開頭的字串字面**
（`ast.Constant` 或 `ast.JoinedStr` 的第一段），f-string 的變數插值不影響開頭判定。

## 首屏的邊界怎麼定

`app.py` 的 module body 中，**第一個包含 `st.tabs(...)` 的頂層語句之前**的所有語句。
邊界本身（`tab_a, tab_b, … = st.tabs([...])`）不算首屏內容。

## ⚠️ 已知會誤紅 / 守不到的情形（不要事後才發現）

- **守不到（跨檔）**：把占位搬進別的模組再由 `app.py` import 呼叫。
  首屏那段確實呼叫了 `render_sidebar(...)` 與 `_oauth_callback()` ——
  本檔**不追進去**（跨檔呼叫圖，同 Q3 規則的既有邊界）。
  ⚠️ 這是真的洞：`render_sidebar` 畫的是側邊欄（不佔首屏正文），
  但 `_oauth_callback()` 會印 flash 訊息。**不要讀成「首屏已經守死了」。**
- **守不到**：CSS 本身塞進視覺內容（`st.markdown("<style>…</style><div>公告</div>")`）——
  本檔只看開頭是不是 `<style`，不解析整段 HTML。
- **誤紅（設計如此）**：首屏若真的需要新增一句話（例如全域停機公告），
  會紅 —— 正解是**登記進 `FIRST_SCREEN_ALLOWED` 並在 PR 寫理由**，
  而登記會出現在 diff 裡被客戶看到。那正是這條規則存在的目的。
- **守不到**：`getattr(st, "info")(...)` 這種動態取屬性
  （同 `test_render_state_color_separation` 檔頭列的既有盲點 (e)）。
"""
from __future__ import annotations

import ast

from test_render_state_color_separation import (
    ROOT,
    _receiver_root,
    _st_container_names,
)

APP = ROOT / "app.py"

#: 「會在首屏放東西」的 st API。
#: 刻意**比顏色規則檔的 `_ST_RENDER_ATTRS` 更寬** —— 這裡連「占位」都要抓，
#: 所以把 `divider` / `container` / `empty` / `expander` / `progress` 等
#: 純版面元素也算進來（空的 `st.container()` 也是占位）。
#: ⚠️ 集合漏一個，規則在那個方向上就是瞎的；已知仍未涵蓋 `st.badge` 等新 API。
FIRST_SCREEN_RENDER_ATTRS = frozenset({
    "markdown", "write", "text", "caption", "info", "warning", "error", "success",
    "exception", "code", "latex", "json", "table", "dataframe", "metric",
    "title", "header", "subheader", "divider", "image", "video", "audio",
    "progress", "spinner", "status", "toast", "balloons", "snow",
    "container", "empty", "expander", "popover", "columns", "chat_message",
    "button", "download_button", "checkbox", "toggle", "radio", "selectbox",
    "multiselect", "text_input", "number_input", "date_input", "text_area",
    "slider", "file_uploader", "data_editor", "form",
    "plotly_chart", "altair_chart", "pyplot", "line_chart", "bar_chart",
    "area_chart", "map", "graphviz_chart",
})


def _first_screen_boundary(tree: ast.Module, containers: frozenset[str]) -> int | None:
    """回傳「第一個含 `st.tabs(...)` 的頂層語句」在 `tree.body` 的索引。

    找不到就回 None —— 那代表首屏的邊界消失了（`st.tabs` 被搬走 / 改名），
    本檔所有規則會對空氣生效，故由 `test_first_screen_boundary_exists` 直接擋下。
    """
    for i, stmt in enumerate(tree.body):
        for node in ast.walk(stmt):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "tabs"
                    and _receiver_root(node.func.value) in containers):
                return i
    return None


def _first_screen_render_calls():
    """首屏（`st.tabs` 之前的 module 層語句）內所有渲染呼叫。"""
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    containers = _st_container_names(tree)
    idx = _first_screen_boundary(tree, containers)
    out: list[ast.Call] = []
    if idx is None:
        return out, tree
    for stmt in tree.body[:idx]:
        for node in ast.walk(stmt):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if node.func.attr not in FIRST_SCREEN_RENDER_ATTRS:
                continue
            if _receiver_root(node.func.value) not in containers:
                continue
            out.append(node)
    return out, tree


def _leading_literal(node: ast.AST) -> str | None:
    """取一個字串字面（含 f-string）的**開頭文字**；不是字串字面就回 None。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr) and node.values:
        head = node.values[0]
        if isinstance(head, ast.Constant) and isinstance(head.value, str):
            return head.value
    return None


def _is_css_only_markdown(call: ast.Call) -> bool:
    """`st.markdown(f"<style>…")` —— 只放行「開頭就是 `<style` 的字串字面」。

    ⚠️ 這是本檔的關鍵收緊處：整個放行 `st.markdown` 會讓
    `st.markdown("&nbsp;")` 這種空占位混過去（M5 突變的第三招）。
    非字串字面（變數 / 函式回傳）一律不放行 —— 靜態證不出來 ＝ 不放行（fail-closed）。
    """
    if call.func.attr != "markdown" or not call.args:
        return False
    head = _leading_literal(call.args[0])
    return head is not None and head.lstrip().lower().startswith("<style")


#: 首屏**唯一**允許的渲染：全域 CSS 注入。
#: 鍵是「呼叫名 + 為什麼放行」，判定由 `_ALLOW_PREDICATES` 給，不是靠關鍵字比對。
FIRST_SCREEN_ALLOWED = {
    "st.markdown(<style …)": _is_css_only_markdown,
}
#: 量測日 2026-08-28、基準 commit `a28e6a3`：首屏渲染呼叫共 **1 個**（就是那塊 CSS）。
FIRST_SCREEN_RENDER_TOTAL = 1


def test_first_screen_boundary_exists():
    """錨點：`app.py` 的 module 層還找得到 `st.tabs(...)` 嗎？

    找不到就代表首屏的邊界沒了，本檔其餘規則會**掃 0 個語句、天天綠**。
    ratchet 擋得住「數字變大」，擋不住「規則整條蒸發」。
    """
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    containers = _st_container_names(tree)
    idx = _first_screen_boundary(tree, containers)
    assert idx is not None, (
        "`app.py` 的 module 層找不到 `st.tabs(...)` —— 首屏的邊界不見了，"
        "本檔所有規則正在對空氣生效。若分頁機制真的換掉了，請重新定義首屏邊界。")
    assert idx >= 5, (
        f"`st.tabs` 出現在 module body 的第 {idx} 個語句 —— 首屏範圍幾乎是空的，"
        "請確認不是把整段搬走讓規則掃不到東西。")


def test_first_screen_has_no_redundant_placeholder():
    """首屏只准有「具名允許」的渲染 —— 其餘一律紅（fail-closed）。

    ⚠️ 這條**不是**關鍵字白名單。它不問「這句話在講什麼」，只問
    「這個渲染呼叫有沒有被具名允許」。換個文案繞不過去，換個 widget 也繞不過去。
    ⚠️ 它與 `test_q3_home_page_no_longer_prints_a_key_notice` **不重複也不取代**：
    那條守的是「來源端不要再有金鑰提示」（語意更窄更精準），
    本條守的是「首屏不要有任何冗餘占位」（範圍更寬）。**兩條並存取嚴。**
    """
    calls, _ = _first_screen_render_calls()
    bad = []
    for call in calls:
        if any(pred(call) for pred in FIRST_SCREEN_ALLOWED.values()):
            continue
        bad.append(f"app.py:{call.lineno}  {ast.unparse(call.func)}(…)")
    assert not bad, (
        "首屏（`app.py` module 層、`st.tabs` 之前）多了渲染呼叫。\n"
        "那段在**每一次 rerun 都無條件執行**，而且**七個分頁的最上方都看得到** ——\n"
        "客戶 2026-08-28 拍板的鐵律 4 是「首屏無冗餘占位」。\n"
        f"目前唯一允許的是：{sorted(FIRST_SCREEN_ALLOWED)}\n"
        "若這句話真的必須放在首屏（例如全域停機公告），請登記進 "
        "`FIRST_SCREEN_ALLOWED` 並在 PR 描述寫理由：\n  "
        + "\n  ".join(bad))


def test_first_screen_render_total_is_pinned():
    """首屏渲染呼叫的**總數**也要對得上 —— 擋「刪一句補一句」的淨零置換。

    上一條只問「每一個是否被允許」；若哪天允許表被放寬成「所有 `st.markdown`」，
    多塞十個 `st.markdown` 也不會紅。本條讓數量本身也留一道痕跡。
    """
    calls, _ = _first_screen_render_calls()
    assert len(calls) == FIRST_SCREEN_RENDER_TOTAL, (
        f"首屏渲染呼叫從 {FIRST_SCREEN_RENDER_TOTAL} 個變成 {len(calls)} 個：\n  "
        + "\n  ".join(f"app.py:{c.lineno}  {ast.unparse(c.func)}(…)" for c in calls)
        + f"\n⚠️ 變**少**是好事，請把 `FIRST_SCREEN_RENDER_TOTAL` 改成 {len(calls)}；"
          "\n⚠️ 變**多**請先問「這句話非放在七個分頁最上方不可嗎？」")


def test_css_markdown_predicate_rejects_a_bare_placeholder():
    """允許表的判定式本身也要有測試 —— 否則它壞掉時上面兩條會靜靜放行。

    ⚠️ 這是本檔的**自我防護**：`_is_css_only_markdown` 若哪天被改成
    「只要是 markdown 就 True」，`test_first_screen_has_no_redundant_placeholder`
    會照樣全綠，而且沒有任何人會發現。本條把那個判定式釘死。
    """
    def _call(src: str) -> ast.Call:
        return ast.parse(src, mode="eval").body

    assert _is_css_only_markdown(_call('st.markdown("<style>a{}</style>")'))
    assert _is_css_only_markdown(_call('st.markdown(f"<style>{X}</style>")'))
    assert not _is_css_only_markdown(_call('st.markdown("&nbsp;")')), \
        "空占位不得被當成 CSS 放行 —— 那正是 M5 突變的第三招。"
    assert not _is_css_only_markdown(_call('st.markdown("### 公告")'))
    assert not _is_css_only_markdown(_call('st.markdown(_css)')), \
        "非字串字面一律不放行（fail-closed：靜態證不出來就是不放行）。"
    assert not _is_css_only_markdown(_call('st.markdown(f"{X}<style>a{{}}</style>")')), \
        "f-string 開頭是插值時無法證明它是 CSS，不放行。"
    assert not _is_css_only_markdown(_call('st.info("<style>")')), \
        "允許的是 markdown 這個 widget，不是任何帶 <style> 字樣的呼叫。"


def test_first_screen_render_attrs_cover_the_common_placeholders():
    """錨點：允許表的偵測集合還認得那三個突變用的 widget 嗎？

    M5 突變注入的是 `st.info` / `st.caption` / `st.markdown` —— 若哪天有人
    「精簡」`FIRST_SCREEN_RENDER_ATTRS` 把它們拿掉，主規則會對那三招失明。
    """
    for attr in ("info", "caption", "markdown", "write", "container", "empty", "divider"):
        assert attr in FIRST_SCREEN_RENDER_ATTRS, (
            f"`{attr}` 不在 `FIRST_SCREEN_RENDER_ATTRS` 裡 —— 首屏規則對它是瞎的。")
