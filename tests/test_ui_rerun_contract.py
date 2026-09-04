"""鐵律 2：`st.form` 防重繪 —— 既有的 form 不准退化，多輸入區塊不准裸奔。

## 為什麼非有這個檔不可（實測，不是推測）

2026-08-28 稽核組突變實測：把 `ui/helpers/fund_grp_health/switch_advisor_section.py`
的 `with st.form(...)` 改成 `with st.container()`、`st.form_submit_button` 改成
`st.button` —— **fast lane 與 slow lane 全綠**。同一輪一共注入 5 個違反四大鐵律的
改動，全 suite 結果與基線**逐項相同**（`14 failed / 5347 passed`）。

`st.form` 在 Streamlit 是「這一整組輸入按下送出前不要 rerun」的唯一機制。
拆掉它，使用者每敲一個字、每選一次下拉，整個 script 就從頭跑一次
（本 repo 的 Tab 動輒抓 NAV / 打 Google Sheets）。**畫面看起來一樣，體驗完全不同**
—— 這正是一種「肉眼 review 抓不到、測試也沒在看」的退化。

## 五條規則與它們各自的方向

| # | 規則 | 方向 | 現況（量測日 2026-09-04） |
|---|---|---|---|
| 1 | 既有 `st.form` 站點不准消失 | 資產登記（`==`） | 7 處 / 5 檔 |
| 2 | 每個 `with st.form(...)` 內必須有 `form_submit_button` | fail-closed，無額度 | 0 違規 |
| 3 | 同一區塊 ≥2 個輸入 + 其後的 `st.button` → 必須包 form | fail-closed + ratchet | 5 處 / 4 函式 |
| 4 | 既有的 checkbox / button 延遲載入 gate 不准被刪 | 資產登記（子集） | 22 函式 |
| 5 | 控制項的值不得餵進**沒有送出鈕保護**的取數／重算呼叫 | fail-closed + ratchet | 2 處 / 2 檔 |

⚠️ **規則 1 與 4 是資產登記簿：它們擋回歸，但發現不了新違規。**
真正 fail-closed、會抓到「新寫的裸奔區塊」的只有規則 3 與規則 5。
**2026-09-04 之前只有規則 3**，而它對「一個滑桿直接餵進一個取數呼叫、中間沒有按鈕」
這個形狀是**完全瞎的**（它要求同一區塊 ≥2 個輸入**且**其後有 `st.button`）——
本 repo 最貴的兩處（輪動配對三支滑桿 → `suggest_rotation_pairs`、
熱錢四支滑桿 → `fetch_hot_money_frames` 打 FinMind ＋ Yahoo）正好都長這樣。
規則 5 補的就是這個洞；它與 `_INPUT_WIDGETS` 漏收 `slider` 是**兩個獨立的洞**，
兩個都補完，下一批「把裸滑桿包進 Form」的修復才有一條會轉紅的規則守著。

⚠️ **規則 4 的方向是本檔唯一一條「不對稱」的 ratchet，理由寫在這裡供覆核**：
規則 1~3 守的是**違規存量**（壞東西），依 `CLAUDE.md` 既有慣例用**雙向 `==`**，
因為單向額度會被「還一筆借一筆」的淨零置換繞過
（見 `test_a_caught_exception_backlog_only_shrinks` 的 X-4b 否證紀錄）。
規則 4 守的是**資產存量**（gate 是好東西），淨零置換的攻擊面不存在
—— 「多一個 gate」不是借，是還。若也用 `==`，等於**每加一個按鈕就把 CI 弄紅**，
而且會與正在新增 `ui/components/` 元件的另一組正面衝突。
故規則 4 採**子集斷言**：登記過的函式必須**至少還有一個 gate**；新增 gate 不罰。
📌 **這是實作組的判斷，不是規格明文** —— 派工規格寫的是「記錄現況站點、只准減不准增」，
而「只准減」對一個好東西是反向的。**已就地揭露，請總管裁決**（`CLAUDE.md §-2` 規則 6）。

## receiver 剝殼

`st.form` / `col1.form` / `_s.form`（`import streamlit as _s`）都要認得。
**直接復用** `test_render_state_color_separation` 的 `_receiver_root` /
`_st_container_names`，不另寫一份（§2.1 SSOT）。

## ⚠️ 已知會誤紅 / 守不到的情形（不要事後才發現）

- **錨點失效（規則 1）**：把一個 form 從 `render_t7_section()` 搬進新的
  `_render_t7_form()`，**form 還在、寫法完全正確**，但鍵從
  `…::render_t7_section()×3` 變成兩個鍵 → **會紅**。
  這是刻意的：拆函式是版面/結構改動，值得在 diff 裡被看到；正解是更新 `FORM_SITES`。
- **守不到（規則 3）**：輸入與按鈕被拆進**不同函式**（`_inputs()` + `_actions()`），
  本檔只在**同一個語句區塊**內配對，跨函式的資料流不追。
- **守不到（規則 3）**：輸入與按鈕跨了 form 邊界以外的任何抽象（helper 回傳 widget 值等）。
- ~~**守不到（規則 3）**：`st.data_editor` / `st.chat_input` / `st.file_uploader` 等~~
  → **2026-09-04 部分補上**：`data_editor` / `file_uploader` / `slider` / `radio` /
  `checkbox` / `toggle` / `select_slider` / `time_input` / `color_picker` / `text_area`
  **已收進 `_INPUT_WIDGETS`**（見該常數上方的實測數字）。
  ⚠️ **仍未收** `chat_input` / `pills` / `segmented_control` / `feedback` / `camera_input`
  —— **集合漏一個，規則在那個方向上就是瞎的**，這句話今天依然成立，
  **不要讀成「已經涵蓋所有輸入」**。
- **守不到（規則 5）**：經 `st.session_state` 中轉的值、跨函式傳遞的值、
  不經變數直接內嵌的值（`fetch(st.slider(...))`）、動態呼叫。逐項理由與實測見
  `_ungated_widget_io_keys` 的 docstring —— 那裡是這條規則的**規格**，改規則前先讀它。
- **守不到（規則 5）**：「昂貴」是靠 I/O 可達性推導的，所以**純算但很貴**的重算入口
  只能靠 `_DECLARED_RECOMPUTE` 手寫宣告。**現在只有 1 列**（`suggest_rotation_pairs`），
  也就是說其他純算的重算入口對本規則是隱形的。
- **守不到（規則 4）**：把 gate 的條件改成恆真（`if st.button(...) or True:`）——
  gate 還在、形狀還在，但已經不 gate 了。
- **守不到（全檔）**：`getattr(st, "form")` 這種動態取屬性；
  跨函式傳進來的容器、存進 dict / list 的容器（`_st_container_names` 的既有邊界）。
"""
from __future__ import annotations

import ast
import functools
import pathlib

import pytest
from test_render_state_color_separation import (
    ROOT,
    UI_SOURCES,
    _receiver_root,
    _st_container_names,
)

#: 會讓「每敲一下就整頁重跑」的輸入元件。
#: ⚠️ **2026-09-04 擴射程（有意識的政策變更，不是漏刪）**：上一版只有下面第一行那五個，
#: 於是 `slider` / `radio` / `checkbox` / `toggle` / `file_uploader` / `data_editor` …
#: 全部**對規則 3 與規則 5 隱形**。實測（量測日 2026-09-04，`ui/**` ＋ `app.py`）：
#: 舊集合涵蓋 **82** 次呼叫，射程外還有 **43** 次 —— 也就是本檔上一版在**三分之一**的
#: 輸入元件上是瞎的。舊註解自己寫著「集合漏一個，規則在那個方向上就是瞎的」，
#: 本批就是把那句話兌現。
#: **舊表述的理由仍然成立**（`data_editor` / `file_uploader` 的送出語意確實與純輸入不同），
#: **被權衡掉的是它的結論** —— 「語意不同」是**誤紅風險**，而「完全不掃」是**必然漏抓**；
#: 誤紅會被 diff 看到並登記，漏抓不會被任何人看到。實測本次擴射程只讓規則 3 多出 **1** 處
#: （`radio`，見 `NAKED_MULTI_INPUT_SITES`），其餘九個元件**一處都沒多**——
#: 也就是說「會製造誤紅」這個顧慮在本 repo 的現況下**沒有發生**。
#: ⚠️ 仍**不含** `chat_input`（它自帶送出語意、按 Enter 才送，不是每敲一下就 rerun）
#: 與 `pills` / `segmented_control` / `feedback` / `camera_input`
#: （實測 `ui/**` 內 `segmented_control` 1 次、其餘 0 次；**不是「已涵蓋所有輸入」**）。
_INPUT_WIDGETS = frozenset({
    "text_input", "number_input", "selectbox", "date_input", "multiselect",
    # 2026-09-04 新增：實測會觸發整頁重繪、而上一版看不見的九個。
    "slider", "radio", "checkbox", "toggle", "select_slider",
    "time_input", "color_picker", "file_uploader", "data_editor",
    "text_area",
})

#: **動作型**元件：按下之後回 True，**下一次 rerun 就回 False**。
#: 規則 5 只認這一組當「保護閘門」，理由見該節 `_ungated_widget_io_keys` 的 docstring。
#: ⚠️ 刻意**不含** `checkbox` / `toggle` —— 它們是**黏著**的（勾了就一直是 True），
#: 擋得住「首屏無條件跑」，擋**不住**「拖一下滑桿就重打一次」。
_ACTION_WIDGETS = frozenset({"button", "form_submit_button", "download_button"})

#: 延遲載入 gate：用它包住重運算，讓首屏不要無條件跑。
_GATE_WIDGETS = frozenset({"checkbox", "button", "toggle"})


def _parents(tree: ast.AST) -> dict[int, ast.AST]:
    out: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            out[id(child)] = node
    return out


def _enclosing_function(node: ast.AST, parents: dict[int, ast.AST]) -> str:
    cur = node
    while id(cur) in parents:
        cur = parents[id(cur)]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur.name
    return "<module>"


def _is_st_call(node: ast.AST, containers: frozenset[str], attr: str) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == attr
            and _receiver_root(node.func.value) in containers)


def _form_with_nodes(tree: ast.AST, containers: frozenset[str]) -> list[ast.With]:
    """所有 `with st.form(...):` 的 With 節點。"""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.With, ast.AsyncWith)) and any(
                _is_st_call(item.context_expr, containers, "form") for item in node.items):
            out.append(node)
    return out


def _form_site_counts(paths) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        containers = _st_container_names(tree)
        parents = _parents(tree)
        for node in _form_with_nodes(tree, containers):
            key = f"{path.relative_to(ROOT)}::{_enclosing_function(node, parents)}()"
            counts[key] = counts.get(key, 0) + 1
    return counts


def _as_table(counts: dict[str, int]) -> frozenset[str]:
    return frozenset(f"{k}×{v}" for k, v in counts.items())


# ── 規則 3 用：把每個呼叫歸給「它最近的那個語句區塊」──────────────────
def _block_index(tree: ast.AST):
    """`id(stmt) -> (區塊 id, 在區塊內的序號)`。

    刻意以**語句區塊**（statement list）為單位，而不是 `ast.walk` 整棵子樹：
    後者會讓外層區塊把內層的輸入一起算進來，同一批輸入被重複歸屬到每一層祖先
    （初稿實測：28 個重複命中 vs 實際 4 處）。
    """
    out: dict[int, tuple[int, int]] = {}
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
                for i, stmt in enumerate(block):
                    out[id(stmt)] = (id(block), i)
    return out


def _naked_multi_input_keys(path: pathlib.Path) -> list[str]:
    """同一區塊出現 ≥2 個輸入、其後又有 `st.button`，而且**沒有**被 form 包住。

    這是鐵律 2 的**反向**規則：規則 1 守「既有 form 不要不見」，
    本規則守「該包 form 的地方不要一直不包」。少了它，只要不去動既有那 5 處，
    新寫的多輸入區塊可以永遠裸奔。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    containers = _st_container_names(tree)
    parents = _parents(tree)
    blocks = _block_index(tree)

    inside_form: set[int] = set()
    for node in _form_with_nodes(tree, containers):
        for sub in ast.walk(node):
            inside_form.add(id(sub))

    per_block: dict[int, list[tuple[int, ast.Call]]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in _INPUT_WIDGETS | {"button"}:
            continue
        if _receiver_root(node.func.value) not in containers:
            continue
        if id(node) in inside_form:
            continue                                   # 已經在 form 裡 → 合規
        cur: ast.AST = node                            # 找它所屬的那一個語句
        while id(cur) in parents and id(cur) not in blocks:
            cur = parents[id(cur)]
        if id(cur) not in blocks:
            continue
        block_id, idx = blocks[id(cur)]
        per_block.setdefault(block_id, []).append((idx, node))

    out: list[str] = []
    for items in per_block.values():
        inputs = [(i, c) for i, c in items if c.func.attr in _INPUT_WIDGETS]
        buttons = [(i, c) for i, c in items if c.func.attr == "button"]
        if len(inputs) < 2 or not buttons:
            continue
        last_input = max(i for i, _ in inputs)
        after = [c for i, c in buttons if i >= last_input]   # 「緊接其後」的送出鈕
        if not after:
            continue
        out.append(f"{path.relative_to(ROOT)}::"
                   f"{_enclosing_function(after[0], parents)}()")
    return out


def _gate_function_keys(path: pathlib.Path) -> list[str]:
    """`if st.checkbox(...) / st.button(...) / st.toggle(...):` 這種延遲載入 gate。

    2026-09-02 增收 **`applied_form(...)`**（IA kit 鐵則 02，`ui/helpers/ia/gated_form.py`）。

    ⚠️ **本分支看得到什麼、看不到什麼 —— 據實寫明，不要照抄成「等價」**
    ---------------------------------------------------------------------
    新分支只看「這個函式裡**有沒有出現 `applied_form(...)` 這個 Call**」，
    **不看它回傳的 gate 有沒有被拿去 gate 任何東西**。兩種形態的差別在這裡：

    - `if st.button(...):` —— **call 與 guard 不可分離**，看到 call 就等於看到 guard。
    - `with applied_form(...) as gate:` —— **兩者可以分離**：`applied_form` 照樣被呼叫，
      而 `if gate:` 那一行可以被改成 `if False:`、或整個拿掉。**本分支偵測不到。**

    2026-09-02 實測（本組自行重跑，非轉述）：保留 `applied_form(...)`、把
    `ui/tab_manage.py::_sec_nav_backfill_auto` 的 `if not _bf_gate: return` 改成
    `if False: return` → **本條仍為綠**（`1 passed`）。
    當時另有 5 條紅，但那是**附帶抓到的** —— gate 失效後真的打了外網把渲染搞爛，
    不是設計來抓這件事的。**對「重運算很便宜、不打外網」的未來使用者，沒有任何東西守得住。**

    → **所以本次是「換一種偵測形態」，不是「等價地擴大」。** 之所以仍然收它：
    不收的話，任何把 button gate **升級**成 form gate 的改動都會被誤判成「gate 不見了」，
    逼後人為了消紅**把 gate 拆回去**，方向比現在更糟。

    📌 **待補的機器規則（已登記，本批未做）**：AST 驗「`applied_form(...)` 回傳的
    gate 必須被消費」（出現在某個 `if` 的判斷式裡，或被傳出去）。
    ⚠️ `ui/helpers/ia/gated_form.py` 的 docstring 已經寫著這個病
    （「submit 的回傳值要被接住並用來 gate 運算……否則就會**很明顯地看出**沒 gate」）——
    但「很明顯地看出」是**人眼規則，不是機器規則**；`tests/test_ia_kit.py` 27 條裡
    **沒有一條**在驗呼叫端有沒有用 gate。這條補起來之前，本分支只是形態偵測。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    containers = _st_container_names(tree)
    parents = _parents(tree)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "applied_form":
            out.append(f"{path.relative_to(ROOT)}::{_enclosing_function(node, parents)}()")
            continue
        if not isinstance(node, ast.If):
            continue
        if any(_is_st_call(sub, containers, sub.func.attr)
               and sub.func.attr in _GATE_WIDGETS
               for sub in ast.walk(node.test) if isinstance(sub, ast.Call)
               and isinstance(sub.func, ast.Attribute)):
            out.append(f"{path.relative_to(ROOT)}::{_enclosing_function(node, parents)}()")
    return out


# ══════════════════════════════════════════════════════════════════
# 規則 1：既有的 `st.form` 站點（資產登記）
# ══════════════════════════════════════════════════════════════════
# 量測日 2026-08-31、基準 commit `5f798ee`：`ui/**` + `app.py` 共 **6 個**
# `with st.form(...)`，分佈 4 檔。（`tests/test_app_smoke.py` 內另有 1 個，
#  不在 `UI_SOURCES` 範圍內，本表不含 —— 測試檔不是產品程式碼。）
# ⚠️ 本表由本組**自行重掃**產出，不是照抄派工單。
# 沿革：量測日 2026-08-28（commit `a28e6a3`）為 5 個 / 3 檔；2026-08-31 新增元件 B 一處。
FORM_SITES = frozenset({
    # 2026-09-01 五分頁動線重構：`st.form` 封裝的**共用入口**（IA kit 鐵則 02）。
    # **這是新增一處 form（好事），不是搬家** —— 本批沒有移動或刪除任何既有 form 站點。
    # 它與本表其他列的差別：其他列是「某個畫面包了 form」，這一列是「**給所有畫面用的
    # form 包裝器**」。它現在**沒有 production caller**（本批只做元件，不改分頁），
    # 各分頁改用它是下一批的事。
    # ⚠️ **屆時會發生的事，先寫在這裡**：分頁改用 `applied_form()` 之後，
    #    它們原本各自的 `st.form(` 站點會從本表消失、收斂到這一列 ——
    #    到時候 `FORM_SITE_TOTAL` 會**變少**，那**不是**有人把 form 拆掉，
    #    是站點被收斂了。**請連同呼叫端一起看，不要只看總數下降就放行。**
    # ✅ 這個包裝器自己的行為由 `tests/test_ia_kit.py` 五條斷言守（皆已突變驗證）：
    #    送出鈕必須排在所有 widget 之後（M6）、送出結果必須寫回 gate（M7）、
    #    未送出時 gate 為 False、預設送出字是「套用」、區塊內拋例外不吞。
    "ui/helpers/ia/gated_form.py::applied_form()×1",
    "ui/helpers/fund_grp_health/switch_advisor_section.py::_render_pool_editor()×1",
    # 2026-08-31：③ 批次「🧩 互補配對探索」的 3 支門檻滑桿包進 form + 「套用門檻」submit。
    # **這是新增一處 form（好事），不是搬家** —— #738 建元件 B 時就該包，當時因本檔正由
    # #736 佔用（File Boundary 防撞）而具名延後，阻擋解除後於本批補上。
    # 客戶已拍板線框（`docs/wireframes/rotation-components-wireframe.html` §03 區塊 1
    # 「3 欄滑桿 ＋『套用門檻』鈕」）即長這樣，故屬「實作補齊既有規格」而非新設計。
    "ui/helpers/fund_grp_health/rotation.py::render_complementary_explorer_from_df()×1",
    # WP-D 2026-08-28：下面這組原本掛在 `ui/tab3_portfolio.py::render_portfolio_tab()`，
    # 因「📋 保單管理（Google Sheets）」整段（790 行）抽成 `policy_admin_section.py`
    # 而改掛新函式。**違規呼叫數一個沒有增減**（見該批 PR 的守恆對照），
    # 這是本檔 docstring 寫的「錨點失效（拆函式）→ 更新表」那一種，不是新增豁免。
    "ui/helpers/portfolio/policy_admin_section.py::render_policy_admin_section()×1",
    "ui/tab3_t7_ledger.py::render_t7_section()×3",
})
FORM_SITE_TOTAL = 7   # 2026-08-31：5 → 6（元件 B 門檻列包 form）；
                      # 2026-09-01：6 → 7（IA kit `applied_form()` 共用包裝器，**新增**非搬家）


def test_existing_forms_must_not_degrade():
    """既有的 `st.form` 不准被換成 `st.container` —— 這正是稽核組突變過、全綠的那一招。

    雙向 `==`：拆掉 form 會紅；**新增** form 也會紅（提醒你把表一起加上去）。
    新增 form 是好事，紅燈只是要你留一筆紀錄，不是叫你別加。
    """
    found = _as_table(_form_site_counts(UI_SOURCES))
    lost = sorted(FORM_SITES - found)
    added = sorted(found - FORM_SITES)
    assert not lost, (
        "以下 `st.form` 站點不見了（或函式改名 / form 數量變了）。\n"
        "`st.form` 是「送出前不要 rerun」的唯一機制，拆掉它畫面看起來一樣、"
        "但使用者每敲一個字整個 Tab 就重抓一次資料：\n  "
        + "\n  ".join(lost)
        + "\n⚠️ 若你是**刻意搬家 / 拆函式**：form 還在就把 `FORM_SITES` 一起更新。")
    assert not added, (
        "新增了 `st.form` 站點（這是好事）—— 請把它加進 `FORM_SITES`，"
        "讓下一個人也不能把它拆掉：\n  " + "\n  ".join(added))


def test_form_site_total_matches_the_table():
    """總數也要對得上 —— 擋「拆掉一處、別處補一處」的淨零置換。"""
    total = sum(_form_site_counts(UI_SOURCES).values())
    assert total == FORM_SITE_TOTAL, (
        f"`st.form` 站點總數從 {FORM_SITE_TOTAL} 變成 {total} —— "
        f"請連同 `FORM_SITES` 一起更新（並確認不是把某處拆掉換來的）。")


@pytest.mark.parametrize("path", UI_SOURCES, ids=lambda p: str(p.name))
def test_every_form_has_a_submit_button(path: pathlib.Path):
    """`with st.form(...)` 內必須至少有一個 `form_submit_button`。

    fail-closed，沒有豁免額度（量測日 2026-08-28 現況 0 違規）。
    一個沒有 `form_submit_button` 的 form 在 Streamlit 執行期會直接丟
    `StreamlitAPIException` —— 但那是**跑到那一頁才會炸**，而本 repo 的
    slow lane 只跑 AppTest smoke，不保證每個 form 都被走到。
    把它變成靜態規則，才是「跑不到也守得住」。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    containers = _st_container_names(tree)
    parents = _parents(tree)
    bad = []
    for node in _form_with_nodes(tree, containers):
        has_submit = any(
            isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
            and sub.func.attr == "form_submit_button"
            for sub in ast.walk(node))
        if not has_submit:
            bad.append(f"{path.relative_to(ROOT)}::"
                       f"{_enclosing_function(node, parents)}()（第 {node.lineno} 行）")
    assert not bad, (
        "以下 `st.form` 區塊內沒有 `form_submit_button`，使用者按不出去：\n  "
        + "\n  ".join(bad))


# ══════════════════════════════════════════════════════════════════
# 規則 3：多輸入區塊必須進 form（fail-closed + ratchet）
# ══════════════════════════════════════════════════════════════════
# 量測日 2026-08-28、基準 commit `a28e6a3`：**4 處 / 3 個函式**。
# ⚠️ 這不是「批准這樣寫」，是**待辦的可見化**。四處都是真的（人工複核過）：
#   - `_render_pool_editor()` 的「改型態 / 移除」兩個 selectbox + 兩顆按鈕；
#     以及進階區的 3 個輸入（基金 / secId / 幣別）+「存晨星代碼」按鈕。
#   - `render_first_use_wizard()` / `render_portfolio_tab()` 同型態。
# 每一處都會讓使用者**還沒填完就整頁重跑**。
NAKED_MULTI_INPUT_SITES = frozenset({
    "ui/helpers/fund_grp_health/switch_advisor_section.py::_render_pool_editor()×2",
    "ui/helpers/v2_editor.py::render_first_use_wizard()×1",
    # WP-D 2026-08-28：下面這組原本掛在 `ui/tab3_portfolio.py::render_portfolio_tab()`，
    # 因「📋 保單管理（Google Sheets）」整段（790 行）抽成 `policy_admin_section.py`
    # 而改掛新函式。**違規呼叫數一個沒有增減**（見該批 PR 的守恆對照），
    # 這是本檔 docstring 寫的「錨點失效（拆函式）→ 更新表」那一種，不是新增豁免。
    "ui/helpers/portfolio/policy_admin_section.py::render_policy_admin_section()×1",
    # 2026-09-04 `_INPUT_WIDGETS` 擴射程後**才看得見**的一處 —— 它一直都在，
    # 只是上一版的集合沒收 `radio`，所以規則對它是瞎的。**這不是新寫的違規。**
    # 實體：T7 「C. 複合轉換」的落帳目標 `st.radio` ＋ 方案名稱 `st.text_input`
    # ＋「🔁 試算 M→N 複合轉換」`st.button`（`key="t7c_submit_btn"`），三者同一區塊、沒有 form。
    # ⚠️ 這是**待修**，不是合理豁免 —— 依派工邊界由 **Lane B** 承接。
    # 📌 **修的時候要先確認一件事**：同檔 `_a_mode` 那一組 radio 的就地註解寫著
    #    「policy + multiselect **必須在 form 外**，否則 form 內無法即時 reactive」。
    #    C 段這一組**未經查證是否同理**（本組沒有讀完 C 段的 reactive 相依）——
    #    若確實需要即時反應，正解是**只把不需要 reactive 的欄位包進 form**，
    #    而不是整段塞進去然後發現壞掉再拆回來。
    "ui/tab3_t7_ledger.py::render_t7_section()×1",
})
# 2026-09-04：4 → 5。**變多的原因是規則看得更廣，不是有人新寫了一個違規**
# （本批一行 production 程式碼都沒有改）。
NAKED_MULTI_INPUT_TOTAL = 5


def test_multi_input_blocks_must_be_wrapped_in_a_form():
    """≥2 個輸入 + 其後的按鈕 → 必須包 `st.form`，否則進 ratchet 具名登記。

    ⚠️ **fail-closed**：規則不是「命中某個已知壞檔才檢查」，而是掃全部
    `ui/**` + `app.py`，不在表上就紅。新寫的多輸入區塊不包 form → 當場紅。
    ⚠️ 雙向 `==`：修好一處（包進 form）→ 本條轉紅 → 逼你把表一起降。
    **紅燈在這裡是提醒不是責備。**
    """
    counts: dict[str, int] = {}
    for path in UI_SOURCES:
        for key in _naked_multi_input_keys(path):
            counts[key] = counts.get(key, 0) + 1
    found = _as_table(counts)
    new = sorted(found - NAKED_MULTI_INPUT_SITES)
    fixed = sorted(NAKED_MULTI_INPUT_SITES - found)
    assert not new, (
        "以下區塊有 2 個以上輸入元件、後面接著一顆 `st.button`，卻沒有包在 `st.form` 裡 ——\n"
        "使用者每改一個欄位，整個 Tab 就從頭重跑一次（本 repo 的 Tab 會重抓 NAV / 打 Sheets）。\n"
        "請用 `with st.form(...)` 包起來、按鈕改 `st.form_submit_button`：\n  "
        + "\n  ".join(new))
    assert not fixed, (
        "以下站點已經修好（或改名），請把 `NAKED_MULTI_INPUT_SITES` 與 "
        "`NAKED_MULTI_INPUT_TOTAL` 一起降下來。**這條紅燈是提醒不是責備。**\n"
        "⚠️ 若你是**把輸入欄位整個刪掉**才讓它消失：那不算修好，請確認功能沒有默默少一塊。\n  "
        + "\n  ".join(fixed))
    total = sum(counts.values())
    assert total == NAKED_MULTI_INPUT_TOTAL, (
        f"裸奔的多輸入區塊從 {NAKED_MULTI_INPUT_TOTAL} 變成 {total} —— 請一起更新常數。")


# ══════════════════════════════════════════════════════════════════
# 規則 4：既有的延遲載入 gate（資產登記，子集斷言 —— 方向理由見檔頭）
# ══════════════════════════════════════════════════════════════════
# 量測日 2026-08-28、基準 commit `a28e6a3`：22 個函式、共 64 處 `if st.<gate>(...)`。
# 本表只記「**哪些函式有 gate**」，**刻意不記次數** —— 次數（×17 / ×11）每加一顆
# 按鈕就變動，會把 CI 變成噪音來源，且會與正在新增 `ui/components/` 的另一組衝突。
GATE_FUNCTIONS = frozenset({
    "ui/helpers/fund_grp_health/switch_advisor_section.py::_render_pool_editor()",
    "ui/helpers/fund_grp_health/switch_advisor_section.py::render_switch_advisor_section()",
    "ui/helpers/io/freshness.py::_render_data_health_ai()",
    "ui/helpers/portfolio/linkage.py::render_fund_portfolio_membership()",
    "ui/helpers/v2_editor.py::_render_new_policy_section()",
    "ui/helpers/v2_editor.py::_render_policy_block()",
    "ui/helpers/v2_editor.py::render_first_use_wizard()",
    "ui/helpers/v2_editor.py::render_v2_section()",
    "ui/hot_money.py::render_hot_money_section()",
    "ui/sidebar.py::render_sidebar()",
    "ui/tab1_macro_longterm.py::render_long_term_section()",
    "ui/tab1_macro_radar.py::render_short_radar_section()",
    "ui/tab2_single_fund.py::render_single_fund_tab()",
    "ui/tab3_portfolio.py::render_portfolio_tab()",
    "ui/tab3_t7_ledger.py::render_t7_section()",
    "ui/tab5_data_guard.py::render_data_guard_tab()",
    "ui/tab_batch_analysis.py::_render_recent_checkpoints()",
    "ui/tab_fund_grp_health.py::render_fund_grp_health_tab()",
    "ui/tab_manage.py::_sec_dividend_calendar()",
    # 2026-09-02：`_sec_nav_backfill()` 的 CSV 段抽成
    # `render_nav_csv_manage_section()`（線框 `ia-wireframe.html` Tab 05 拆兩塊），
    # gate 跟著搬到新函式 —— **錨點更新，不是拿掉 gate**。
    "ui/tab_manage.py::render_nav_csv_manage_section()",
    # 同批：本函式的 `if not st.button(...)` 升級成 `applied_form(...)` 送出閘門
    # （鐵則 02「寫入類動作全部 Form 封裝」）。函式名未變，gate 形態變了。
    "ui/tab_manage.py::_sec_nav_backfill_auto()",
    "ui/tab_manage.py::_sec_notify()",
})

#: 量測日 2026-08-28 的 gate 總處數。錨點用（防「規則對空氣生效」），不是上限。
GATE_ANCHOR_MIN_SITES = 55


def test_existing_lazy_load_gates_must_not_disappear():
    """登記過的函式必須**至少還有一個** gate —— 刪掉 gate ＝ 首屏無條件跑重運算。

    ⚠️ **子集斷言，不是 `==`**（本檔唯一一條不對稱的 ratchet，理由見檔頭）：
    新增 gate 是好事，不該讓 CI 紅。這條只擋「把既有的 gate 拿掉」。
    📌 派工規格原本寫的是「只准減不准增」；本組判定那對一個**好東西**是反向的，
    改為子集斷言並就地揭露 —— **請總管裁決**（`CLAUDE.md §-2` 規則 6）。
    """
    found = {k for p in UI_SOURCES for k in _gate_function_keys(p)}
    lost = sorted(GATE_FUNCTIONS - found)
    assert not lost, (
        "以下函式原本用 checkbox / button gate 擋住重運算，現在 gate 不見了 ——\n"
        "使用者一進分頁就會無條件觸發抓取（鐵律 2 / 鐵律 4）：\n  "
        + "\n  ".join(lost)
        + "\n⚠️ 若你是**刻意搬家 / 改名**：gate 還在就把 `GATE_FUNCTIONS` 一起更新。")


def test_gate_anchor_still_detectable():
    """錨點：gate 還掃得到嗎？

    不加這條，有人把 `if st.button(...)` 換成別的寫法時，上一條會**對空氣生效**。
    """
    n = sum(len(_gate_function_keys(p)) for p in UI_SOURCES)
    assert n >= GATE_ANCHOR_MIN_SITES, (
        f"只掃到 {n} 處延遲載入 gate（量測日 2026-08-28 為 64，錨點下限 "
        f"{GATE_ANCHOR_MIN_SITES}）—— gate 規則可能正在對空氣生效。")


# ══════════════════════════════════════════════════════════════════
# 規則 5：控制項的值不得直接餵進「沒有送出鈕保護」的取數／重算呼叫
# ══════════════════════════════════════════════════════════════════
# ## 為什麼規則 3 抓不到這一類（本規則存在的唯一理由）
#
# 規則 3 要**同一區塊 ≥2 個輸入 ＋ 其後一顆 `st.button`**。於是下面這個形狀
# ——本 repo 最貴的那一種——**永遠不會 match**：
#
#     _sell = c1.slider(...)                      # 1 個控制項就夠了
#     _buy  = c2.slider(...)                      # 沒有 button
#     _pairs = suggest_rotation_pairs(rows, ...)  # 值直接餵進重算
#
# 沒有 button ⇒ `buttons` 為空 ⇒ `continue`。**這與 `_INPUT_WIDGETS` 漏收 `slider`
# 是兩個獨立的洞**：就算把 `slider` 加進去（本批已加），規則 3 對這個形狀依然是瞎的。
# 兩個洞都補完，才有下一批「把裸滑桿包進 Form」的紅燈可言。
#
# ## 判定準則（機器可判定、fail-closed；**這一段是本規則的規格，改規則前先改這裡**）
#
# 一處算違規，**四個條件必須同時成立**：
#
#   (a) **有一個輸入元件的回傳值被綁進一個區域變數**
#       （`x = st.slider(...)`；`_INPUT_WIDGETS` 全員）。
#   (b) **同一個函式裡**，那個變數被當成引數傳進某個呼叫。
#       ⚠️ 綁定與消費**都以函式為作用域**，不是整個檔案 —— 初稿用檔案作用域，
#       結果 `_render_pairs_ui` 的 `_sell` 洩漏到 `render_complementary_explorer_from_df`
#       （後者其實是從 `st.session_state` 讀值、而且已經包了 form），**憑空多一筆假違規**。
#   (c) **那個呼叫是「昂貴」的**（定義見下）。
#   (d) **這條路徑上沒有任何保護**：輸入與呼叫都不在 `st.form` / `applied_form` 區塊內，
#       且該呼叫不在任何**動作型閘門**（`_ACTION_WIDGETS`）的 `if` **正分支**裡。
#
# ### 「昂貴」怎麼定義 —— **用 AST 推導，不手抄清單**
#
# **昂貴 ＝ 這個呼叫會（傳遞地）走到真正的 I/O**。理由：重繪的代價不是 CPU，
# 是**每動一下就多一次對外往返**（`CLAUDE.md` 檔頭原話：「本 repo 的 Tab 動輒抓 NAV /
# 打 Google Sheets」）。作法是在 `repositories/` ＋ `services/` ＋ `infra/` 上建一張
# 呼叫圖，用 I/O 原語當種子往上傳遞取不動點（實測 1015 個函式、4 輪收斂、0.9 秒）。
#
# ⚠️ **為什麼不用「住在 `repositories/` 就算昂貴」這個更簡單的定義** —— 實測會誤判：
# `repositories/policy/v2.py::compute_units`（`invest_twd / (avg_nav × avg_fx)`）與
# 同檔 `estimate_dividend_split` 都是**純算術**，住 L1 但一次 I/O 都沒有。
# 拿它們當違規登記，就是 `CLAUDE.md §8.2.A.0 規則 5` 點名的「理由倒置」。
#
# ⚠️ **種子刻意只收「幾乎不可能撞名」的原語**：`get` / `post` / `parse` / `update`
# 這種通名**一律不收**。初稿收了 `get`，於是 `rows.get(...)` 這種 dict 存取讓
# `suggest_rotation_pairs` 被誤標成 I/O —— **答案碰巧對了，機制是錯的**。
# HTTP 改用「receiver 是 I/O 模組別名」來認（`requests.get` 認得，`d.get` 不會）。
#
# ⚠️ **傳遞是用「裸函式名」做的，不是完整 qualname** —— 同名函式會互相汙染。
# 這是**過近似**：多標成昂貴 ⇒ 多紅，是 fail-closed 的方向，不是漏抓的方向。
_IO_MODULES = frozenset({
    "requests", "httpx", "urllib", "yfinance", "gspread",
    "feedparser", "socket", "subprocess",
})
_IO_CALL_PRIMITIVES = frozenset({
    "fetch_url", "fetch_url_with_retry", "urlopen", "urlretrieve",
    "read_csv", "read_html", "read_parquet", "read_excel", "to_parquet",
    "open_by_key", "open_by_url", "get_all_records", "get_all_values",
    "append_row", "append_rows", "service_account", "from_service_account_info",
    "Ticker", "post_gemini", "generate_content", "read_text", "write_text",
})
#: 掃哪幾個套件建呼叫圖。UI 自己不掃 —— 規則問的是「值有沒有跨出 UI 層」。
_IO_SOURCE_PACKAGES = ("repositories", "services", "infra")

#: **純算但很貴**的重算入口：走不到 I/O，所以上面那張圖抓不到，只能具名宣告。
#: 每一列**必須寫為什麼**，而且要寫「為什麼這個位置該被保護」，不是「它長得像什麼」
#: （`CLAUDE.md §8.2.A.0` 規則 5）。**這是本規則唯一手寫的部分，刻意壓到最小。**
#: ⚠️ 名字寫錯不會靜默失效 —— `test_declared_recompute_entries_still_exist` 會紅。
_DECLARED_RECOMPUTE = {
    "suggest_rotation_pairs":
        "O(賣方×買方) 全配對 ＋ 每對取 σ / 健康度 / 操盤評分；它是輪動配對整段畫面的"
        "唯一計算入口。客戶已為它的**另一個**呼叫點拍板包 form"
        "（`FORM_SITES` 的 `render_complementary_explorer_from_df()×1`，"
        "線框 `docs/wireframes/rotation-components-wireframe.html` §03 區塊 1），"
        "本 repo 因此已經認定這個呼叫值得一道送出閘門 —— 只是另一個呼叫點還沒補。",
}


@functools.lru_cache(maxsize=1)
def _io_reaching_names() -> frozenset[str]:
    """會（傳遞地）走到 I/O 的函式**裸名**集合。

    種子：函式體內出現 `<io模組別名>.<any>(...)`，或呼叫 `_IO_CALL_PRIMITIVES` 之一。
    傳遞：呼叫了任何一個已標記名字的函式，自己也算。取不動點。
    """
    funcs: dict[str, tuple[set[str], bool]] = {}
    by_name: dict[str, set[str]] = {}
    for pkg in _IO_SOURCE_PACKAGES:
        pkg_dir = ROOT / pkg
        if not pkg_dir.is_dir():
            continue
        for path in sorted(pkg_dir.rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:                      # 壞檔不該讓守衛整條啞掉
                continue
            mod_alias = _io_module_aliases(tree.body)
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                alias = mod_alias | _io_module_aliases(ast.walk(node))
                called: set[str] = set()
                seed = False
                for sub in ast.walk(node):
                    if not isinstance(sub, ast.Call):
                        continue
                    fn = sub.func
                    if isinstance(fn, ast.Name):
                        called.add(fn.id)
                        seed = seed or fn.id in _IO_CALL_PRIMITIVES or fn.id in alias
                    elif isinstance(fn, ast.Attribute):
                        called.add(fn.attr)
                        seed = (seed or fn.attr in _IO_CALL_PRIMITIVES
                                or _receiver_root(fn.value) in alias)
                key = f"{path.relative_to(ROOT)}::{node.name}"
                funcs[key] = (called, seed)
                by_name.setdefault(node.name, set()).add(key)

    hot = {k for k, (_, seed) in funcs.items() if seed}
    changed = True
    while changed:                                   # 不動點；實測 4 輪收斂
        changed = False
        for key, (called, _) in funcs.items():
            if key in hot:
                continue
            if any(q in hot for c in called for q in by_name.get(c, ())):
                hot.add(key)
                changed = True
    return frozenset(funcs_name for k in hot
                     for funcs_name in (k.rsplit("::", 1)[1],))


def _io_module_aliases(nodes) -> frozenset[str]:
    """`import requests as _req` / `from gspread import x` → 綁出來的名字。"""
    out: set[str] = set()
    for node in nodes:
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in _IO_MODULES:
                    out.add(a.asname or a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in _IO_MODULES:
                for a in node.names:
                    out.add(a.asname or a.name)
    return frozenset(out)


def _expensive_callees() -> frozenset[str]:
    return _io_reaching_names() | frozenset(_DECLARED_RECOMPUTE)


def _enclosing_function_node(node: ast.AST, parents: dict[int, ast.AST]):
    cur = node
    while id(cur) in parents:
        cur = parents[id(cur)]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur
    return None


def _ungated_widget_io_keys(path: pathlib.Path) -> list[str]:
    """控制項的值直接餵進未受保護的昂貴呼叫 → 每命中一處回一個鍵。

    ## 三種「保護」，以及為什麼 checkbox 不算
    - `st.form(...)` / `applied_form(...)`：送出前不 rerun。**這是正解。**
    - `if <button>:` 的**正分支**：`st.button` 下一次 rerun 就回 False，
      所以拖滑桿不會再打一次。**這是可接受的替代解。**
    - ⛔ `if st.checkbox(...):` / `if st.toggle(...)`：**不算保護**。它們是**黏著**的
      —— 勾起來之後每一次 rerun 都還是 True，滑桿一動照樣重打。
      ⚠️ **據實說明**：本 repo 現況下這個區分**一次都沒有被觸發**
      （量測日 2026-09-04：把 checkbox/toggle 也當閘門，命中數同樣是 2）。
      也就是說**這條分界目前沒有被實測驗證過**，它是照語意選的嚴格側。

    ## 只看 `if` 的 body，不看 `orelse`
    `elif` 在 AST 裡是掛在 `orelse` 的巢狀 `If`。若整棵 `ast.walk(if節點)` 都算「受保護」，
    `else:` 分支——**按鈕沒被按時才跑的那一段**——會被誤判成受保護。故只收 `node.body`。

    ## 這條規則**看不到**什麼（不要讀成「已經涵蓋」）
    - **經由 `st.session_state` 中轉的值**：`st.session_state.x = st.slider(...)`，
      別處再 `st.session_state.get("x")` 讀回來。目標是 `Attribute` 不是 `Name`，
      本規則的綁定表收不到。實測 `ui/tab3_portfolio.py` 的 `slider_core_pct` 正是這一種
      （不過它的下游 `_core_tgt_fp` 只做百分比偏差顯示，走不到 I/O，**本來也不該紅**）。
    - **跨函式的資料流**：`_search(keyword)` 把值當參數傳進另一個函式再打 TDCC，
      本規則只在同一個函式內配對。
    - **值不經過變數**：`fetch(st.slider(...))` 直接內嵌。實測本 repo 目前 0 處，
      但規則確實看不到 —— 綁定表只收 `ast.Assign`。
    - **動態呼叫**：`getattr(mod, name)(...)`、存進 dict 再叫出來。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    containers = _st_container_names(tree)
    parents = _parents(tree)
    expensive = _expensive_callees()

    shielded: set[int] = set()                       # form / applied_form 區塊內
    for node in ast.walk(tree):
        if not isinstance(node, (ast.With, ast.AsyncWith)):
            continue
        if any(_is_st_call(i.context_expr, containers, "form")
               or (isinstance(i.context_expr, ast.Call)
                   and isinstance(i.context_expr.func, ast.Name)
                   and i.context_expr.func.id == "applied_form")
               for i in node.items):
            for sub in ast.walk(node):
                shielded.add(id(sub))

    action_names: set[str] = set()                   # `do_load = st.button(...)`
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            fn = node.value.func
            if (isinstance(fn, ast.Attribute) and fn.attr in _ACTION_WIDGETS
                    and _receiver_root(fn.value) in containers):
                for tgt in node.targets:
                    for x in ast.walk(tgt):
                        if isinstance(x, ast.Name):
                            action_names.add(x.id)
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:                  # `with applied_form(...) as gate:`
                if (isinstance(item.context_expr, ast.Call)
                        and isinstance(item.context_expr.func, ast.Name)
                        and item.context_expr.func.id == "applied_form"
                        and item.optional_vars is not None):
                    for x in ast.walk(item.optional_vars):
                        if isinstance(x, ast.Name):
                            action_names.add(x.id)

    gated: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test_hit = any(
            isinstance(s, ast.Call) and isinstance(s.func, ast.Attribute)
            and s.func.attr in _ACTION_WIDGETS
            and _receiver_root(s.func.value) in containers
            for s in ast.walk(node.test))
        test_hit = test_hit or any(isinstance(s, ast.Name) and s.id in action_names
                                   for s in ast.walk(node.test))
        if test_hit:
            for stmt in node.body:                   # 刻意不含 orelse，理由見 docstring
                for sub in ast.walk(stmt):
                    gated.add(id(sub))

    bound: dict[tuple[int, str], str] = {}           # (函式 id, 變數名) -> widget
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr in _INPUT_WIDGETS
                and _receiver_root(node.value.func.value) in containers):
            continue
        if id(node.value) in shielded:               # 已在 form 內 → 合規
            continue
        fn = _enclosing_function_node(node, parents)
        scope = id(fn) if fn is not None else 0
        for tgt in node.targets:
            for x in ast.walk(tgt):
                if isinstance(x, ast.Name):
                    bound[(scope, x.id)] = node.value.func.attr

    out: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in expensive):
            continue
        if id(node) in shielded or id(node) in gated:
            continue
        fn = _enclosing_function_node(node, parents)
        scope = id(fn) if fn is not None else 0
        fed = sorted({x.id for arg in list(node.args) + [k.value for k in node.keywords]
                      for x in ast.walk(arg)
                      if isinstance(x, ast.Name) and (scope, x.id) in bound})
        if fed:
            name = fn.name if fn is not None else "<module>"
            out.append(f"{path.relative_to(ROOT)}::{name}() → {node.func.id}()")
    return out


# 量測日 2026-09-04、基準 commit `6d18b88`：**2 處 / 2 檔**。
# ⚠️ 這不是「批准這樣寫」，是**待辦的可見化** —— 兩列都是「待修」，不是「合理豁免」。
# 依派工邊界，修這兩處是 **Lane B** 的事；本批只負責把規則立起來、把債登記清楚。
UNGATED_WIDGET_IO_SITES = frozenset({
    # 待修（Lane B 承接）。3 支門檻滑桿 → `suggest_rotation_pairs(rows, ...)`，中間無鈕。
    # **它活在兩個分頁**：② 組合健診（`fund_grp_health/__init__.py` → `render_rotation_section`）
    # 與 ④ 投資組合（`ui/tab3_portfolio.py`，`key_prefix="pf_rot_"`），所以拖一下滑桿的代價
    # 兩邊都付。**同一個 `_render_pairs_ui` 只登記一列** —— 鍵是「哪個函式打哪個呼叫」，
    # 不是「幾個分頁用到它」；分頁數變動不該讓本表變動。
    # ✅ 正解已經存在、而且客戶已拍板：同檔的 `render_complementary_explorer_from_df`
    #    就是把同一組滑桿包進 `st.form` ＋「套用門檻」submit（見 `FORM_SITES`）。
    #    這一列要做的是把**同樣的形狀**補到 `_render_pairs_ui`。
    "ui/helpers/fund_grp_health/rotation.py::_render_pairs_ui() → suggest_rotation_pairs()×1",
    # 待修（Lane B 承接）。4 支滑桿（回看天數 / 觀察窗格 / 外資門檻 / 台幣門檻）
    # → `fetch_hot_money_frames(days, token)`，中間無鈕。
    # ⚠️ 這是本表**代價最高**的一列：該 facade 會打 **FinMind ＋ Yahoo** 兩個外部來源
    #    （`services/hot_money_service.py` → `repositories/hot_money_repository.py`）。
    #    也就是**每拖一格滑桿就是一次對外往返**，而其中三支滑桿
    #    （`window` / `flow_thr` / `fx_thr`）**根本沒有被傳進取數**，純粹是畫面門檻 ——
    #    動它們不需要重抓，現在卻照抓。
    "ui/hot_money.py::render_hot_money_section() → fetch_hot_money_frames()×1",
})
#: 違規**呼叫數**（不是鍵數）。與上表一起降 —— 修好一處就要把兩個都改小。
UNGATED_WIDGET_IO_TOTAL = 2


def test_widget_values_must_not_feed_ungated_expensive_calls():
    """控制項的值直接餵進未受保護的取數／重算 → 具名登記，否則紅。

    ⚠️ **fail-closed**：掃全部 `ui/**` ＋ `app.py`，不在表上就紅。
    ⚠️ **雙向 `==`**：修好一處（包進 form 或加送出鈕）→ 本條轉紅 → 逼你把表一起降。
    **紅燈在這裡是提醒不是責備**（形狀沿用本檔規則 3 與 `test_ui_grid_contract.py`）。
    """
    counts: dict[str, int] = {}
    for path in UI_SOURCES:
        for key in _ungated_widget_io_keys(path):
            counts[key] = counts.get(key, 0) + 1
    found = _as_table(counts)
    new = sorted(found - UNGATED_WIDGET_IO_SITES)
    fixed = sorted(UNGATED_WIDGET_IO_SITES - found)
    assert not new, (
        "以下位置：一個輸入元件的值**直接**被餵進會走到 I/O（或已具名宣告為重算入口）"
        "的呼叫，中間沒有 `st.form` / `applied_form`，也沒有任何送出鈕擋著 ——\n"
        "使用者每拖一下滑桿 / 每換一個選項，就多打一次外部來源：\n  "
        + "\n  ".join(new)
        + "\n\n正解二選一："
        "\n  (1) `with applied_form(...) as gate:` 包住那組控制項（本 repo 現行做法，"
        "見 `ui/helpers/ia/gated_form.py`）；"
        "\n  (2) 或在控制項與呼叫之間加一顆 `st.button` 並把呼叫移進它的 `if` 正分支。"
        "\n⚠️ `if st.checkbox(...)` **不算**：它是黏著的，勾起來之後照樣每動必打。")
    assert not fixed, (
        "以下站點已經修好（或改名 / 改變資料流），請把 `UNGATED_WIDGET_IO_SITES` 與 "
        "`UNGATED_WIDGET_IO_TOTAL` 一起降下來。**這條紅燈是提醒不是責備。**\n"
        "⚠️ 若你是**把控制項或整段功能刪掉**才讓它消失：那不算修好，"
        "請確認功能沒有默默少一塊。\n  " + "\n  ".join(fixed))
    total = sum(counts.values())
    assert total == UNGATED_WIDGET_IO_TOTAL, (
        f"未受保護的「控制項 → 昂貴呼叫」從 {UNGATED_WIDGET_IO_TOTAL} 變成 {total}。\n"
        f"⚠️ 變**少**是好事，請把 `UNGATED_WIDGET_IO_TOTAL` 一起改成 {total}；\n"
        f"⚠️ 變**多**請包 form，或連同 `UNGATED_WIDGET_IO_SITES` 一起登記並附理由。")


def test_expensive_callee_whitelist_still_derivable():
    """錨點：昂貴呼叫的白名單還推導得出來嗎？

    不加這條，`repositories/` 改名、`_IO_CALL_PRIMITIVES` 被清空、或呼叫圖建壞掉時，
    上一條會**對空氣生效** —— 白名單變空集合 ⇒ 一處都掃不到 ⇒ 綠燈，
    而錯誤訊息還會說「站點已經修好」，把讀者導向完全相反的方向。

    ⚠️ **總數下限單獨守不住「部分退化」—— 這是實測出來的，不是推測**（2026-09-04）：
    種子有兩條路（`_IO_MODULES` 的別名、`_IO_CALL_PRIMITIVES` 的原語），
    **清空任一條，另一條仍能撐到 209 / 240 個名字，總數下限照樣過關**；
    只有兩條同時清空才會紅。所以下面**每條路徑各釘一個專屬探針**：

    - `fetch_nav`（`repositories/fund/nav_metrics.py`）**只**靠 `_IO_CALL_PRIMITIVES`
      進得來 —— 清空原語它就掉出來（實測：68 個名字只走這條路）。
    - `fetch_market_news`（`repositories/news_repository.py`）**只**靠 `_IO_MODULES`
      的別名進得來 —— 清空模組它就掉出來（實測：37 個名字只走這條路）。
    - 其餘四個（`fetch_hot_money_frames` L2 facade→L1、`tdcc_search_fund` L1 直打 HTTP、
      `import_csv_text` 走 gspread、`diagnose_fx_sources`）**兩條路都到得了**，
      屬冗餘取樣，守的是「整張圖垮掉」。

    ⚠️ 這六個是**取樣，不是窮舉** —— 本測試綠不代表白名單是對的，
    只代表這六條路徑還通。
    """
    names = _io_reaching_names()
    assert len(names) >= 200, (
        f"只推導出 {len(names)} 個會走到 I/O 的函式名（量測日 2026-09-04 為 277）——"
        "呼叫圖可能建壞了，規則 5 正在對空氣生效。")
    assert "fetch_nav" in names, (
        "`fetch_nav` 不再被判定為會走到 I/O —— `_IO_CALL_PRIMITIVES` 那條種子路徑斷了"
        "（它只靠原語進得來，見本測試 docstring）。")
    assert "fetch_market_news" in names, (
        "`fetch_market_news` 不再被判定為會走到 I/O —— `_IO_MODULES` 那條種子路徑斷了"
        "（它只靠模組別名進得來，見本測試 docstring）。")
    for probe in ("fetch_hot_money_frames", "tdcc_search_fund", "import_csv_text",
                  "diagnose_fx_sources"):
        assert probe in names, (
            f"`{probe}` 不再被判定為會走到 I/O —— 推導路徑斷了，"
            "規則 5 在那個方向上已經瞎掉。")
    # 反向：純算術不該被誤判成昂貴，否則整張表會被噪音淹掉（§8.2.A.0 規則 5 理由倒置）。
    for pure in ("compute_units", "estimate_dividend_split"):
        assert pure not in names, (
            f"`{pure}` 被誤判成會走到 I/O —— 它是純算術（`repositories/policy/v2.py`）。"
            "請檢查 `_IO_CALL_PRIMITIVES` 是不是收了會撞名的通名（如 `get` / `parse`）。")


def test_declared_recompute_entries_still_exist():
    """`_DECLARED_RECOMPUTE` 是本規則唯一手寫的部分 —— 名字寫錯不准靜默失效。"""
    found: set[str] = set()
    for pkg in _IO_SOURCE_PACKAGES:
        pkg_dir = ROOT / pkg
        if not pkg_dir.is_dir():
            continue
        for path in pkg_dir.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            found |= {n.name for n in ast.walk(tree)
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    missing = sorted(set(_DECLARED_RECOMPUTE) - found)
    assert not missing, (
        f"`_DECLARED_RECOMPUTE` 宣告的重算入口已不存在：{missing} —— "
        "改名或刪除時請一起更新，否則規則 5 對它就是瞎的。")
    assert all(_DECLARED_RECOMPUTE.values()), (
        "`_DECLARED_RECOMPUTE` 每一列都必須寫理由（為什麼這個位置該被保護）。")


def test_declared_ungated_io_paths_still_exist():
    """`UNGATED_WIDGET_IO_SITES` 寫死了路徑 —— 檔案改名要出聲。"""
    declared = {k.split("::")[0] for k in UNGATED_WIDGET_IO_SITES}
    missing = sorted(p for p in declared if not (ROOT / p).is_file())
    assert not missing, f"下列路徑已不存在，規則 5 的登記正在對空氣生效：{missing}"


#: `form_submit_button` 的數量下限 —— **等於當下實測值,刻意不留容忍度**。
#: ⚠️ 2026-08-31 稽核指出:本條原本寫死 `>= 5`,而實測自 2026-08-28 起就是 6、
#: 本批之後是 7 —— 也就是**容忍度從 1 悄悄變成 2**:可以無聲拆掉兩個 form 而本條不紅。
#: 「下限沒跟著實測值走」本身就是一種靜默弱化,所以現在把它綁死在實測值上。
#: **這是「會漂移的量測值」**:每次有意增減 form 都要一起改這個數字(改它是正常維護,
#: 不是繞過守衛)—— 相對地,**沒改它就退化,一定會紅**,那正是本條要的效果。
_FORM_SUBMIT_FLOOR = 7


def test_form_anchor_still_detectable():
    """錨點：`st.form` 與 `form_submit_button` 還掃得到嗎？

    ⚠️ 這條與 `test_existing_forms_must_not_degrade` **不重複**：那條比對的是
    「是哪幾處」，本條守的是「偵測邏輯本身還活著」。若 `_st_container_names`
    哪天壞掉、`_form_with_nodes` 一律回空集合，那條會因為 `found` 是空集合而紅 ——
    但錯誤訊息會說「form 不見了」，把讀者導向錯誤方向。本條讓真正的原因先現形。
    """
    submits = 0
    for path in UI_SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        submits += sum(1 for n in ast.walk(tree)
                       if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                       and n.func.attr == "form_submit_button")
    assert submits >= _FORM_SUBMIT_FLOOR, (
        f"只掃到 {submits} 個 `form_submit_button`，少於下限 {_FORM_SUBMIT_FLOOR}"
        "（量測日 2026-08-31 為 7；2026-08-28 為 6，差額為元件 B 的「套用門檻」）"
        " —— form 偵測可能已經對空氣生效。"
        "\n若這是**有意**移除某個 form，請同步下修 `_FORM_SUBMIT_FLOOR` 並在 commit 說明；"
        "本條刻意不留容忍度,理由見該常數上方註解。")


def test_declared_form_paths_still_exist():
    """`FORM_SITES` / `GATE_FUNCTIONS` 寫死了路徑 —— 檔案改名要出聲。"""
    declared = {k.split("::")[0] for k in
                {s.rsplit("×", 1)[0] for s in FORM_SITES} | GATE_FUNCTIONS}
    missing = sorted(p for p in declared if not (ROOT / p).is_file())
    assert not missing, f"下列路徑已不存在，本檔規則正在對空氣生效：{missing}"
