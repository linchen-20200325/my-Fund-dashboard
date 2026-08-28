"""顏色五態 SSOT —— 「系統真紅燈」與「業務紅燈」嚴格分離。

客戶 2026-08-28 拍板（線框 `fund-empty-state-wireframe.html` §03「顏色：三態統一規則」）：

> 嚴格分離「業務紅燈」與「系統真紅燈」，未載入／未設定一律改灰色說明，
> 把用灰字印的真失敗改回系統紅燈。

為什麼一定要分（線框原文，本模組存在的唯一理由）
------------------------------------------------
**系統紅燈的意思是「這個數字不可信」；業務紅燈的意思是「這個數字可信，而且它很難看」。**
兩者要使用者做的事完全相反 —— 前者要他別採信、去修；後者要他採信、去換基金。
用同一個紅色，等於把「不要相信這個畫面」和「相信這個畫面並據以行動」畫成同一件事。

反方向同樣是 bug：真正的失敗（抓取／渲染／模組載入）如果用灰字印，
畫面看起來只是「還沒載入」—— 使用者會以為按一下就好，實際按幾次都一樣。
這與 `CLAUDE.md §1`「錯誤的數字比沒有數字更危險」同源。

五態對照
--------
| 狀態         | 視覺                       | 本模組入口              |
|--------------|----------------------------|-------------------------|
| 未載入／未設定 | ⬜ 灰色說明（`st.caption`） | `not_ready()`           |
| 不適用       | ➖ 或不顯示                 | `NOT_APPLICABLE_MARK`（現況已分對，**不要**併進 ⬜） |
| 業務警訊     | 🔴 紅字，但用卡片／表格列    | `business_alert()`      |
| 系統真出錯   | 🔴 紅色錯誤框 + 可展開技術細節 | `system_error()`      |
| 破壞性操作提醒 | 🟠 常駐橘框                | `st.warning()`（無例外處理，不需 helper） |

⚠️ **🟠 這件衣服，同一頁上現在有三種意思**（2026-08-28 第二輪稽核 A6 補登；
本模組自稱是顏色 SSOT，表就必須跟得上實況，否則它自己變成新的模糊來源）：

| 🟠 的來源 | 意思 | 怎麼分辨 |
|---|---|---|
| `st.warning()` 常駐橘框 | **破壞性操作提醒** —— 永遠有效的警語，沒有任何事情出錯 | 不帶錯誤內容、每次都在 |
| `system_error(degraded=True)` | **系統失敗，但數字全在且全對** —— 掉的只有一張圖 | 帶例外類型與技術細節 |
| `st.warning(_res["caveat"])`（既有，如 `backtest_section`） | **§1 業務 caveat** —— 結果正確，但方法論有限制（樣本少／回測非未來） | 不帶錯誤內容、跟在結果旁邊 |

⚠️ **這是已知的、尚未收斂的模糊**，據實登記而不是假裝沒有：本批把「紅色」拆乾淨了
（業務紅 vs 系統紅），**橘色沒有拆**。要拆需要新增視覺語彙或改版面，
屬 §-1.5 v3 §03-2 ① 的**客戶 gate**，不在「只做顏色」這一批的範圍內。
現況唯一可靠的辨識點是**內容**：**只有第二種帶技術細節**（`🔧 技術細節` 區塊）。

⚠️ 這一句原本後面還有半句「三者不會同時出現在同一個區塊裡」——
**已刪除，因為它是假的**：`backtest_section.render_allocation_backtest_section()`
**同一個函式、同一個「🔁 配置回測」區塊**內就同時有 `st.warning(_res["caveat"])`（§1 業務 caveat）
與 `system_error(..., degraded=True)`（淨值疊圖失敗）兩種橘色。
（查證指令：`python -c "import ast,pathlib; t=ast.parse(pathlib.Path('ui/helpers/fund_grp_health/backtest_section.py').read_text()); print([(ast.unparse(n.func), n.lineno) for n in ast.walk(t) if isinstance(n, ast.Call)])"`
→ 同一函式內同時命中 `st.warning` 與帶 `degraded=True` 的 `system_error`。）

⭐ **一條給後人（含我自己）的規則 —— 這是三輪稽核連續抓到的同一種病**：
> **任何「X 不會發生／三者不會同時／已經全部／繞不過去」形式的句子，
> 必須就地附上證明它的那條 `grep`／AST 指令；附不出來就不要寫。**

病史（體積逐輪縮小，但習慣沒改，所以要用規則治而不是靠自律）：
第一輪 commit message 的「順帶修掉」（那段其實是死碼）→
第二輪測試註解的「那已經不是回歸，是改設計」（實測改兩行就繞過）→
第三輪本行的「三者不會同時出現」（實測同一個函式裡就有兩種）。
**三次都是「誠實揭露之後，順手接一句沒查證的安撫話」** ——
揭露本身是對的，壞在那句多出來的保證。

⚠️ **五態表有一個沒有格子的狀態：「持久化失敗」**（2026-08-28 顏色批次二之一登記）
------------------------------------------------------------------------
`nav_history` 寫入失敗、批次分析的磁碟 checkpoint 失敗、CSV 匯入後雲端同步失敗 ——
這一族的形狀是：**畫面上每一個數字都還在、也都是對的，壞掉的是「留得住」**。
- 它不符合 `degraded=True` 的通過條件（掉的**不是**一張圖，而且使用者**會**因此
  在幾週後做出錯誤判斷 —— 以為序列在累積、其實沒有）。
- 它也不是 ⬜（那不是「還沒設定」，是**真的寫失敗了**，按幾次都一樣）。

**本批的處置：一律 🔴 `degraded=False`，並在 `hint` 裡明講「本次數字不受影響、
壞的是保存」。** ⚠️ **這是判斷，不是事實** —— 「系統紅燈＝這個數字不可信」照字面
只涵蓋畫面上的數字，這裡的紅指的是「**未來的序列**不可信」。
若客戶認為這一族該用 🟠 或別的視覺，推翻這一段即可，三處會一起改
（查證這三處，量測日 2026-08-28 各 1 命中，共 3：
  `grep -rnE 'system_error[(]"(NAV 累積寫入失敗|磁碟續存失敗|雲端 nav_history 同步失敗)' ui/ --include=*.py`
  → 恰好 3 行,分別在 nav_history_hook.py / tab_manage.py / tab_batch_analysis.py）。

⚠️ `not_ready()` 不吃 Exception —— 這是刻意的型別層防呆：
「還沒載入」永遠不會有 exception 可報；一旦手上有 exception，就是 `system_error()`。
`tests/test_render_state_color_separation.py` 以 AST 守住這條分界（守形狀，不守字面）。
"""
from __future__ import annotations

import streamlit as st

from shared.colors import BG_DARK_RED_1, GH_FG_PRIMARY, MATERIAL_RED

# ⬜ 在 ui/ 全層已是家規（量測日 2026-08-28：299 處）——沿用，不引進新符號。
NOT_READY_MARK: str = "⬜"
# ➖「結構上不適用」（台幣基金沒有匯率位階、不配息基金沒有配息欄）。
# 與 ⬜ 語意不同：⬜ 是「現在沒有、之後會有」，➖ 是「這件事對它本來就不存在」。
NOT_APPLICABLE_MARK: str = "➖"


def not_ready(message: str, *, where: str = "") -> None:
    """⬜ 灰色說明：還沒載入／還沒執行／還沒設定。**不是**故障。

    Parameters
    ----------
    message : 缺什麼（寫具體的東西，不要只寫「無資料」）。
    where   : 去哪裡補（例：「🌐 市場定調 → 📡 載入總經資料」）。
              線框 §02：這是最容易省掉、也最有價值的一項 ——
              沒有它，占位只是把「消失」換成「灰色的消失」。
    """
    if isinstance(message, BaseException):
        # 型別層防呆:「還沒載入」永遠不會有 exception 可報。手上有 exception
        # 卻走到這裡,代表把「系統真出錯」畫成了「還沒載入」—— 那正是本模組要擋的 bug。
        raise TypeError(
            "not_ready() 不接受 Exception —— 手上有例外就是 system_error()，"
            f"收到的是 {type(message).__name__}: {message}")
    _msg = f"{NOT_READY_MARK} {message}"
    if where:
        _msg += f"（請先到：{where}）"
    st.caption(_msg)


def system_error(what: str, exc: BaseException, *, hint: str = "",
                 degraded: bool = False) -> None:
    """🔴 系統真出錯：紅色錯誤框 + 可展開技術細節 + stderr 鏡射。

    用在：抓取失敗、渲染失敗、模組載入失敗 —— 也就是**畫面上少了或錯了一個數字**。

    走 `ui.helpers.session.friendly_error(level="error")`（全站錯誤呈現 SSOT，
    §2.1），本函式只負責把「這是系統紅燈」這個語意具名化，讓稽核與測試找得到。

    Parameters
    ----------
    degraded : 降為 🟠 橘框（`level="warning"`）。
        **通過條件只有一個，不得放寬**：這次失敗之後，畫面上**每一個數字都還在、
        而且都還是對的**，掉的只有非數值的呈現物（一張圖）。使用者**不可能**因為
        這次失敗而做出錯誤決定 —— 他只是少看到一張圖。

        ⚠️ 只要有任何一個數字消失、被排除、或改變（例：匯率抓不到 → 美元計價基金
        被排除在回測之外），**一律 `degraded=False`**：那正是客戶 2026-08-28 要
        建立的分辨力（「這個數字不可信」vs「這個數字可信」）。把兩者穿同一件紅衣服
        會把它抹平；把前者穿成橘衣服更糟。
        （2026-08-28 稽核 M3：本檔同一區塊內就有一組正反例，見 backtest_section。）
    """
    from ui.helpers.session import friendly_error  # lazy：避免 import 迴圈

    friendly_error(
        what, exc,
        hint=hint or "此區塊已隔離，其他區塊與分頁不受影響；"
                     "請展開下方「🔧 技術細節」把 traceback 截圖回報。",
        level="warning" if degraded else "error",
    )


def business_alert(title: str, lines: list[str], *, footer: str = "") -> None:
    """🔴 業務警訊：紅字卡片，**不是**紅色錯誤框。

    用在：淘汰候選、嚴重吃本金、系統性風險暫緩換標 —— 分析**成功了**，
    答案是「這幾檔該換」。那是成果，不是故障，所以不能用 `st.error`
    （會和系統崩潰共用同一個視覺語彙）。
    """
    _body = "".join(f"<div style='margin:2px 0'>{ln}</div>" for ln in lines)
    _foot = (f"<div style='color:{GH_FG_PRIMARY};opacity:.7;font-size:11px;"
             f"margin-top:6px'>{footer}</div>") if footer else ""
    st.markdown(
        f"<div style='background:{BG_DARK_RED_1};border-left:4px solid {MATERIAL_RED};"
        f"border-radius:6px;padding:10px 12px;margin:6px 0'>"
        f"<div style='color:{MATERIAL_RED};font-weight:700;font-size:15px;"
        f"margin-bottom:4px'>{title}</div>"
        f"<div style='color:{GH_FG_PRIMARY};font-size:13px'>{_body}</div>"
        f"{_foot}</div>",
        unsafe_allow_html=True,
    )
