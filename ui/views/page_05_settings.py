"""⑤ 設定與診斷 —— **(A) 路線的委派殼**：只做版面與編排，功能一律呼叫既有舊模組。

客戶方針（2026-09-06，(A) 路線拍板）
------------------------------------
新五頁**只做版面呈現與互動排版**，寫入邏輯**原封不動呼叫既有舊模組**。

⚠️ **⑤ 是五頁裡唯一一頁在 (A) 拍板之前就寫成獨立重寫的**，所以本檔 2026-09-06
由「骨架 + 灰態 + 自寫 Form」改寫成**委派殼**。
**舊實作不是被刪掉，是被換成呼叫舊模組的 public 入口** —— 逐塊對照見下表。

===== ====================== =====================================================
順序   線框區塊（`<h4>` 逐字）  本檔怎麼實現
===== ====================== =====================================================
1      資料來源健康度          **委派** `ui.tab5_data_guard.render_data_guard_tab()`
                              （前置 `_update_data_registry()`；整塊在 gate 之後）
2      NAV 累積狀態            **保留本檔實作**（總管裁決 2，理由見下方 (D-4)）
3      連線與金鑰              **委派** `render_policy_admin_bridge(sheet_client=None)`
                              ＋ `render_fetch_diag_from_session()`
4      手動補資料              **委派** `render_nav_manual_section()`（三條寫入路徑）
（4.5） 🗄️ 資料維護與通報      **委派** `ui.tab_manage.render_manage_tab()`
                              ⚠️ **線框沒有給它位置**，見下方 (D-5) 的登記
5      使用手冊                **委派** `ui.tab6_manual.render_manual_tab()`
===== ====================== =====================================================

線框同時釘死了本頁的**職責邊界**：

> 回答一個問題：**資料本身可不可信、要不要我補？** 平常不用進來；出事時第一個進來。

⛔ **因此本頁不放**（線框「這裡不放什麼」逐字）：
   「**快取與退避狀態不做成畫面**」「任何投資判斷 → **01 ~ 04**」。
   → 本檔**沒有任何快取／退避狀態的區塊**，由
   `tests/test_wf05_settings_skeleton.py::test_the_page_does_not_render_cache_or_backoff_state` 釘住。
   ⚠️ **這條只管本檔自己畫的東西** —— 被委派的 `render_data_guard_tab()` 內部有沒有
   快取相關的顯示，本檔管不到，也不該管（(A) 路線：舊模組原封不動）。

⭐ 五則總管裁決 —— 理由寫在這裡，是為了讓後人**能推翻它**
==========================================================

(D-1) 「使用手冊」那張卡的 `dim` **不是灰態**
---------------------------------------------
**實測依據**（`grep -n 'dim' docs/wireframes/ia-wireframe.html`，全檔僅 5 個命中）：
`:193/:198` 是 CSS 兩行；`:379`／`:552` 各配著一個 `灰態` chip；
**`:706`（使用手冊那一處）`card span3 dim` 沒有 `灰態` chip**，內文「**純文字**」。
→ `dim` 在這份線框裡承擔**兩種**意思：配 chip ＝「還沒接上」，沒配 chip ＝**視覺降權**。

⛔ **因此使用手冊不得畫成灰態佔位。** 自 (A) 路線起這一條**更沒有藉口** ——
   說明書的真內容（`ui/tab6_manual.py`，十章）**一直都在**，只是舊版沒有委派過去。

(D-2) 本頁**沒有頁面層級的空狀態**；空狀態只可能出現在單一區塊
--------------------------------------------------------------
**線框事實**：Tab 05 **沒有畫任何空狀態區塊**（實測全檔 `class="empty"` 唯一一處在
`:486`，落在 Tab 02 的 panel）。

**以下是總管的判斷，不是線框寫的 —— 寫在這裡讓後人能推翻**：
本頁**只有「NAV 累積狀態」可能真的空**；其餘四塊委派給舊模組，
**舊模組自己會處理它們的空／未設定狀態**（本檔不替它們判斷，那會變成第二份真相源）。

空狀態**只在「gate 勾了 → 後端已啟用 → 真的讀到、而且一筆都沒有」時出現**。
⛔ **不得**把它綁在 `portfolio_funds` 上：`coverage_status()` 讀的是**整張雲端 sheet**，
與那個 session 鍵毫無關係 —— 一個雲端已經累積三年的人會被告知「還沒列入任何基金」。
→ 守衛：:func:`~tests.test_wf05_settings_skeleton.test_the_empty_state_only_appears_after_a_successful_read`。

(D-3) 線框裡的示意值**一個都不准畫**
------------------------------------
`18 源 · 2 異常`／`42 檔 · 最長 6.2 年`／`正常` **全是線框示範版面用的假數字**。
NAV 那一塊現在會印**真的**「N 檔 · 共 M 筆」—— 那不是示意值，它有出處
（:func:`services.nav_history_gs.coverage_status` 回傳的逐檔點數）。
⛔ **但「最長 X 年」永遠不會回來**：不是因為它是線框的假數字，
而是因為 `span_days = last - first` **單獨出現就會說謊**（見 :func:`coverage_line`）。
⚠️ **黑名單的已知代價**：`_PINNED_FAKE_VALUES` 收了字面值 `"42 檔"`，
而本頁會印真的「N 檔」—— **若哪天 fixture 剛好是 42 檔，那條守衛會誤紅**。
它是**潛在風險，不是現行風險**（現行 fixture 檔數為 1 / 2 / 0）。

(D-4) ⭐ **區塊 2 不委派回舊模組 —— 舊的那一塊會印假數字**（總管裁決 2）
----------------------------------------------------------------------
舊的 NAV 累積狀態是 `ui.helpers.settings_diag.nav_history_section.render_nav_status_section()`
→ `ui.tab5_data_guard.render_nav_accumulation_status()`，它把 `coverage_status()` 回傳的
`span_days` **原封放進一張 DataFrame 的兩個欄位**：「涵蓋天數」與「≈年」。

**問題出在上游**：`services/nav_history_gs.py::coverage_status` 在日期 parse 失敗時
`_span = 0`（它自己那一行的註解就寫著「**跨度未知**，點數仍誠實回報」），
而 `norm_date_key()` **刻意讓壞日期的原字串通過**（「不靜默丟資料（§1：不猜）」）
—— 所以壞日期真的會走到畫面上。

**本組端到端實測（注入假 worksheet，非推論；指令與逐字輸出見 PR）**：

======================================  ==================  ==================
上游回傳                                  舊塊畫出來            真相
======================================  ==================  ==================
`BBB first=113/01/02 last=2025-06-01`   涵蓋天數 **0** · ≈年 **0.0**   **約 1.4 年**
`DDD first=last=2024-05-05`             涵蓋天數 **0** · ≈年 **0.0**   **真的 0 天**
======================================  ==================  ==================

**兩者在畫面上長得一模一樣。** 委派回舊的 ＝ 把一個**已知的假數字**重新放回線上，
直接違反客戶常設紅線與 `CLAUDE.md §1`（錯誤的數字比沒有數字更危險）。
→ 故本塊**保留本檔實作**：:func:`span_days_or_unknown` 用兩端自己重算並與上游對帳，
對不上就誠實回「算不出天數」。

⚠️ **這一塊是 (A) 路線的唯一例外，而且是刻意的** —— 它**不是**「順手重寫比較好看」，
   是「委派過去會說謊」。**任何其他塊都不得引用本例外來自行重寫。**
✅ **旗標粒度夠細，兩份 NAV 不會同時出現（本組實測，不是推論）**：
   `merge_context.NAV_HISTORY` 由本檔在委派 `render_manage_tab()` 與
   `render_data_guard_tab()` 時持有，而那兩支各自**只跳過自己那一塊 NAV**
   （`ui/tab_manage.py` 跳 `_sec_nav_backfill()`；`ui/tab5_data_guard.py` 跳
   `render_nav_accumulation_status()` ＋ `render_nav_statement_csv_import()`），
   **其餘照畫**。舊的 `render_nav_status_section()` 本檔**根本不呼叫**，
   所以那份假數字連渲染的機會都沒有。
   → 守衛：:func:`~tests.test_wf05_settings_skeleton.test_the_page_renders_exactly_one_nav_status_block`。

(D-5) ⚠️ **「🗄️ 資料維護與通報」在線框裡沒有位置 —— 登記，不吞掉**
------------------------------------------------------------------
線框 Tab 05 的「從哪裡搬來」**逐字列了 `ui/tab_manage.py`**，但五個 `<h4>` 裡
**沒有任何一塊叫得出「選股池」「除息行事曆」「換股通報」**。三種可能的處置：

(a) 塞進「手動補資料」那一塊 → **畫面會說謊**：選股池 CRUD 不是「補資料」；
(b) 整個不畫 → **等於刪功能**（線框自己說要從那個檔搬來）；
(c) **另立一個區塊、就地登記線框沒有給它位置**。

**本檔選 (c)**，理由是 (a) 違 §1、(b) 違線框自己的「從哪裡搬來」。
⛔ **這是總管級的裁決，不是實作細節** —— 它在客戶拍板的版面上**多了一塊**，
   已具名回報，**在客戶／總管裁決落下之前，本區塊的存在本身是登記在案的待驗事項**。
   ⚠️ **不得**把本段讀成「⑤ 可以隨意加區塊」。

⚠️ **本頁沒有 `render_story_nav()`，這是刻意的，不是漏做**
===========================================================
`story_nav.render_story_nav()` 的第一行是
``if _as_tab_key(current) not in _VALID: return`` —— 而決策動線只有**四站**
（`macro` / `health` / `research` / `portfolio`），`render_flow_nav` 的 docstring
自己就寫著「**⑤ 設定與診斷不在其中**」。照抄 ①②③④ 那一行進來，會得到一個
**看起來有做、實際是 no-op** 的呼叫。**本檔不放那一行。**

⚠️ **本批尚未接進 `app.py`**（客戶明令舊分頁不動、不接線、不下架），
所以本檔現在**沒有 production caller** —— 這是**刻意的中間狀態**，不是漏接。

⚠️ **接線批次必讀：`FETCH_DIAG` 要由 `app.py` 持有，不是本檔**
---------------------------------------------------------------
`merge_context.FETCH_DIAG` 的作用是「⑤ 持有 → **個基頁**那份抓取診斷不畫」。
Streamlit 的 `st.tabs` 是**同一次 script run 渲染全部分頁**，所以要壓住個基頁那份，
持有範圍必須**涵蓋整個分頁列的渲染**（現行 `app.py` 就是這樣包住五個分頁本體的）。
⛔ 在本檔內部包一層 `settings_page_owns(FETCH_DIAG)` **對個基頁毫無作用** ——
   那會變成一個「看起來有做、實際 no-op」的呼叫，正是本檔對 `render_story_nav`
   拒絕照抄的同一個病。**故本檔刻意不包。**
"""
from __future__ import annotations

import datetime as _dt
from typing import Any

import streamlit as st

from services.nav_history_gs import (
    coverage_status as fetch_nav_coverage,
    status as fetch_nav_backend_status,
)
from ui.helpers.ia.empty_state import empty_state
from ui.helpers.render_state import not_ready, safe_section
from ui.helpers.settings_diag.merge_context import (
    DATA_GUARD_HEADER,
    MANAGE_HEADER,
    MANUAL_HEADER,
    NAV_HISTORY,
    settings_page_owns,
)
from ui.helpers.settings_diag.fetch_diag_section import render_fetch_diag_from_session
from ui.helpers.settings_diag.policy_admin_bridge import render_policy_admin_bridge
from ui.helpers.story_nav import section_label, tab_label, where_to_find

# ── session 鍵名（本檔自己的命名空間）────────────────────────────────────────
#: 使用者的持股來源。既有 session 契約，由 ④ 的加入基金流程／`ui/helpers/cloud_io.py` 寫入。
#: ⚠️ 這個字串是**別人定義**的鍵名，本檔只讀不寫 —— 不要在這裡「順手改個好名字」。
_SK_PORTFOLIO: str = "portfolio_funds"

#: 「資料來源健康度」整塊的 Checkbox Gate 鍵。
#:
#: ⚠️ **刻意不沿用舊 ⑤ 的 `sd_diag_gate`**（`ui/tab_settings_diag.py::_render_diag_section`）。
#:    舊 ⑤ **仍然接在 `app.py`**（本批不接線、不下架），兩頁共用同一個 widget key
#:    在「兩頁同時被渲染」的那一刻會直接拋 `StreamlitDuplicateElementKey`。
#:    **gate 這件事一格未鬆**（總管裁決 3）：擋的東西、預設值、灰態文案全部照舊，
#:    換掉的只有 key 的命名空間。
_SK_DIAG_GATE: str = "v05_diag_gate"

# ── 區塊名 ────────────────────────────────────────────────────────────────
#: 線框 Tab 05 `<h4>` 逐字。**SSOT `_SECTION_LABELS` 沒有這個 key**，
#: 本批**刻意不新增 key**（不在檔案邊界內，同 `page_04_portfolio.py::BLOCK_POLICY`）。
BLOCK_HEALTH: str = "資料來源健康度"
#: 線框 Tab 05 `<h4>` 逐字。**SSOT 沒有這個 key**（理由同上）。
BLOCK_KEYS: str = "連線與金鑰"
#: 線框 Tab 05 `<h4>` 逐字。⚠️ **與 `section_label("manual")`（「📖 說明書」）並存的
#: 第二份真相源，尚未裁決** —— 兩個名字很可能指同一塊東西
#: （`manual` 的所屬分頁在 `_SECTION_TO_TAB` 裡正是 `settings`）。
#: 本檔取**線框字面**：線框是客戶看過並拍板的那份視覺，
#: 用 `section_label("manual")` 會在畫面上印出「📖 說明書」——那與客戶拍板的字不一樣。
#: ⛔ **但這一條沒有被裁決過，本檔不宣稱它是對的**（已具名回報總管）。
BLOCK_MANUAL: str = "使用手冊"

#: gate 的標籤。**與舊 ⑤ 逐字相同**（總管裁決 3：gate 一格未鬆）。
DIAG_GATE_LABEL: str = "🔭 載入資料診斷"

#: 逐檔明細的展開器標題（線框：「雲端歷史涵蓋度，**逐檔可展開**」）。
#: ⚠️ **刻意是固定字串、不帶檔數** —— 它在守衛的 `_units()` 裡是一個**單位名**，
#:    帶了檔數就會隨資料變動，單位邊界會跟著漂。
NAV_DETAIL_LABEL: str = "逐檔明細"

#: 讀雲端 NAV 累積狀態的 **Checkbox Gate**。勾起來才會去讀一次。
#:
#: ⚠️ **為什麼是 gate 而不是 `@st.cache_data`（總管裁決，理由寫在這裡讓後人能推翻）**：
#:    (a) 在 `ui/**` 自建 `@st.cache_data` 會替憲法例外 `EX-UICACHE-1` 新增一個成員，
#:        而那個例外的成立**繫於一個尚未裁決的問題**（`CLAUDE.md §8.3.P` 的 `P-UIGSPREAD-1`）；
#:    (b) `coverage_status()` 內部走 `load_points(None)` —— **一次讀完整張 sheet**，
#:        而 L2 那層**沒有**任何快取，UI 再疊一層就會變成 `P-NDCCACHE-1` 的同型。
#:    → gate 同時解掉這兩件事：**沒勾就一次都不讀**，勾了才讀，而且讀的責任留在 L2。
NAV_GATE_LABEL: str = "讀取雲端 NAV 累積狀態"

#: 「跨度」在畫面上的**唯一措辭**。具名是為了讓守衛認得出「哪一行在講跨度」。
#: ⚠️ 用「首末相距」而不是「跨度 N 年」：`span_days = last - first`，
#:    它**不代表中間連續** —— 兩個點相距六年也會是六年。措辭本身要說出這件事。
SPAN_PHRASE: str = "首末相距"
#: 點數的單位字。**跨度出現的地方一定要有它**（見 :func:`coverage_line`）。
POINTS_UNIT: str = "筆"

#: gate 沒勾時的灰態本文。**不講任何數量**，因為我們一次都還沒讀。
_NOT_LOADED_NOTE: str = (
    "尚未讀取雲端 NAV 累積狀態 —— 這是一次會往返 Google Sheets 的讀取，"
    "所以預設不做；勾上面那個選項才會讀一次。")

#: 「資料來源健康度」gate 沒勾時的灰態本文。**逐字沿用舊 ⑤ 的理由**。
_DIAG_NOT_LOADED_NOTE: str = (
    "資料來源健康度尚未載入（避免每次互動都重跑註冊表更新與匯率抓取）")

#: 後端未啟用時的灰態本文開頭。⚠️ **這不是「沒有資料」，是「我們沒辦法去看」**（§1）。
_BACKEND_UNAVAILABLE_NOTE: str = (
    "讀不到雲端 NAV 歷史 —— 累積功能所需的設定不完整，"
    "所以**這一格不知道你累積了多少**（不是「你沒有累積」）。缺少：")

#: 真的讀到了、但一筆都沒有時的空狀態三要素。
_EMPTY_TITLE: str = "雲端 NAV 歷史目前一筆都沒有"
_EMPTY_MISSING: str = (
    "已經讀到雲端了，但 nav_history 裡沒有任何一筆紀錄 —— "
    "可能是還沒開始累積，也可能是那張工作表還沒建立")
_EMPTY_FOOTER: str = "開始累積之後，這裡會逐檔列出點數與首末日期。"


def nav_status_label() -> str:
    """「NAV 累積狀態」—— **走 SSOT，不抄線框字面**（`_SECTION_LABELS["nav_status"]`）。

    ⚠️ 做成函式而不是 module 層常數，是為了讓 `section_label()` 的
    §1 Fail Loud（未知 key 直接 `KeyError`）發生在**渲染當下**而不是 import 期 ——
    import 期炸掉會讓整個 `ui.views` 套件無法載入，連帶打死其他四頁。
    """
    return section_label("nav_status")


def nav_manual_label() -> str:
    """「手動補資料」—— **走 SSOT，不抄線框字面**（`_SECTION_LABELS["nav_manual"]`）。"""
    return section_label("nav_manual")


def maintain_label() -> str:
    """「🗄️ 資料維護與通報」—— **走 SSOT**（`_SECTION_LABELS["manage"]`）。

    ⚠️ 這一塊在線框 Tab 05 裡**沒有位置**，見模組 docstring 的 (D-5)。
    名字仍然走 SSOT，是因為它**確實有一個 key**（不像 `BLOCK_HEALTH` 那三個）——
    有 key 卻手抄字面，是本 repo 已經發作過三次的那個病。
    """
    return section_label("manage")


def _where(block: str) -> str:
    """本頁內的指路。**回傳的必須是一個「地方」。**

    `render_state.not_ready()` 會把它包成「（請先到：…）」——
    也就是說回傳值會變成一句**祈使句的受詞**。塞一句狀態陳述進去
    （「目前只有 X 是完整的」）會產生一句**不可執行的指令**：那是 ③
    `ui/views/page_03_research.py` 2026-09-05 被獨立紅隊實測抓到的錯。

    ⚠️ 分頁名走 `where_to_find()`，**不手抄**；區塊名由呼叫端傳進來，
    不在這裡再抄一份（手抄的指路在本 repo 已經指錯三次）。
    ⚠️ **刻意不用「」把 `block` 括起來**：`tests/test_batch2_top_card_grid.py::`
    `test_every_where_names_something_that_exists_on_screen` 只對 ``「」`` 內的
    **字面值**比對「畫面上有沒有這個字」，而它的字表不收 `st.caption`。
    """
    return f"{where_to_find('settings')} → {block}"


def _holdings() -> list[dict[str, Any]]:
    """使用者**目前持有**的基金。讀既有 session 契約，**不自己取數**。

    ⚠️ **這裡刻意`不`做 `loaded` 過濾**，與 `page_02_health.py` / `page_04_portfolio.py`
    的同名函式**故意不同** —— ②④ 問的是「**拿這幾檔去算**」，沒載入的算進去會生出
    一個不完整的結論（§1）；⑤ 的 NAV 累積狀態問的是「**雲端歷史涵蓋了哪幾檔**」，
    而「已列入但還沒抓回來」正是這一頁最該顯示的那一種。
    """
    _cur = st.session_state.get(_SK_PORTFOLIO)
    return [_f for _f in _cur if isinstance(_f, dict)] if isinstance(_cur, list) else []


def _as_int(value: Any) -> int | None:
    """能算出整數就回它，**算不出來回 `None`，不回 `0`**。

    ⛔ **`0` 是一個宣稱（「一筆都沒有」），`None` 是「我不知道」** —— §1 的分界就在這裡。
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_day(value: Any) -> "_dt.date | None":
    """把一端的日期字串 parse 成 `date`；**parse 不出來回 `None`，不猜**。"""
    try:
        return _dt.date.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        return None


def span_days_or_unknown(first: Any, last: Any, reported: Any) -> int | None:
    """跨度**可不可信** —— 不可信回 `None`。**全檔唯一決定「要不要印跨度」的地方。**

    ⛔ **為什麼不能直接用上游的 `span_days`（＝總管裁決 2 的全部理由）**
    ----------------------------------------------------------------
    `services/nav_history_gs.py::coverage_status` 在日期 parse 失敗時
    **把「未知」編成 `0`** —— 它自己那一行的註解就寫著「**跨度未知**，點數仍誠實回報」。
    而 `norm_date_key()` **刻意讓壞日期的原字串通過**（「不靜默丟資料（§1：不猜）」），
    所以壞日期真的會走到這裡。

    **本組端到端重現（`coverage_status(_sheet=…)` 注入假 worksheet，非推論）**：

    ====================================================  =====================
    上游回傳                                                真實跨度
    ====================================================  =====================
    `BBB {'first': '113/01/02', 'last': '2025-06-01', 'span_days': 0}`   **約 1.4 年**
    `DDD {'first': '2024-05-05', 'last': '2024-05-05', 'span_days': 0}`  **真的 0 天**
    ====================================================  =====================

    **兩者在舊塊的畫面上長得一模一樣**（涵蓋天數 0 · ≈年 0.0）。

    做法：**用兩端自己重算一次**（同一條算式，所以上游算得出來時兩者必然相等）
    ---------------------------------------------------------------------
    1. **任一端 parse 不出來 → 回 `None`。** 上游的 `0` 在這種情況下是「放棄」不是「零」。
    2. **兩端都 parse 得出來，但與上游回報的值不一致 → 也回 `None`。**
       兩邊用的是同一條算式，不一致代表**至少有一個前提不成立**。
       ⚠️ 這個分支在今天的 L2 下不會發生，它是**兩層之間的契約檢查**。
    3. 兩端都 parse 得出來且一致 → 回那個數字。

    ⛔ **不要改成「`first != last` 而 `span_days == 0` 就當作未知」那種啟發式。**
    它有一個**真的偽陽性**：`date.fromisoformat` 在 3.11+ 接受 `2024-1-1` 這種變體，
    所以 `"2024-01-01"` 與 `"2024-1-1"` **字串不同、都 parse 得出來、而且是同一天**。

    ⚠️ **本函式仍然守不到的（照實列）**：上游 `first`/`last` 取的是**字串排序**的頭尾
    （`sorted(_ds)`），混入非 ISO 字串時**頭尾可能不是時序上的頭尾**。
    「兩個都 parse 得出來、順序卻是錯的、而且差值剛好為正」這種情況**抓不到**。
    ⛔ **這一段不在本批的射程內**（要修得動 L2 的排序），**登記，不是沒看到**。
    """
    _a, _b = _parse_day(first), _parse_day(last)
    if _a is None or _b is None:
        return None
    _computed = (_b - _a).days
    if _computed < 0 or _computed != _as_int(reported):
        return None
    return _computed


def coverage_headline(coverage: dict[str, Any]) -> str:
    """涵蓋度的一句話總結 —— **只講數量，不講跨度**。

    ⛔ **這裡刻意不放「最長 N 年」**（線框的示意值正是「42 檔 · 最長 6.2 年」）。
    理由不是「線框的數字是假的」（那由 D-3 管），而是**跨度單獨出現會說謊**。
    跨度只在 :func:`coverage_line` 裡出現，而且**永遠與點數同行**。

    ⚠️ 純函式、無 I/O —— 這樣「這句話怎麼算出來的」可以被單獨測。
    """
    _readable = 0
    _points = 0
    _unknown = 0
    for _e in coverage.values():
        # ⛔ **兩種「讀不出來」都要算進 `_unknown`，不能只防一種**：
        #    `{'AAA': None, 'BBB': 'x', 'CCC': [1]}` 若無聲丟棄會印成
        #    「**0 檔 · 共 0 筆**」，那是一句**斷言**（你什麼都沒累積），
        #    而事實是我們收到了三筆讀不懂的東西（§1）。
        if not isinstance(_e, dict) or (_n := _as_int(_e.get("points"))) is None:
            _unknown += 1
            continue
        _readable += 1
        _points += _n
    # ⚠️ **「可讀取」三個字是承重的**：沒有它，「0 檔」會被讀成「你一檔都沒累積」。
    _head = f"可讀取 {_readable} 檔 · 共 {_points} {POINTS_UNIT}"
    if _unknown:
        _head += f"（另有 {_unknown} 檔讀不出來，未計入）"
    return _head


def coverage_line(code: str, entry: dict[str, Any], *, held: bool = False) -> str:
    """一檔的明細行。**全檔唯一被允許讀 `span_days` 的地方。**

    ⛔ **跨度永遠與點數同行，這是本函式存在的唯一理由**：
    `span_days` 是 `last - first`，**中間有沒有斷掉它一個字都沒說**。
    單獨印一個「6.2 年」會被讀成「我有六年的完整歷史」，而真相可能是兩個點。

    ⚠️ **守衛靠的是「機制」不是「這一行長怎樣」**：
    (a) AST 驗 `"span_days"` 這個鍵**只在本函式內被讀**；
    (b) 對任意輸入驗「輸出裡只要有 :data:`SPAN_PHRASE`，就一定有點數」。

    Parameters
    ----------
    held : 這一檔是不是**這個 session 已列入**的持倉。
           ⚠️ 只是一個標記；**沒列入不代表使用者沒有它**（`portfolio_funds`
           開站不自動載入），所以沒有標記的那些**不寫任何否定的話**。
    """
    _points = _as_int(entry.get("points"))
    # ⛔ **不准直接用上游的 `span_days`** —— 它把「未知」編成 `0`。
    _span = span_days_or_unknown(entry.get("first"), entry.get("last"),
                                 entry.get("span_days"))
    _first = str(entry.get("first") or "").strip() or "?"
    _last = str(entry.get("last") or "").strip() or "?"
    _mark = " ・本 session 已列入" if held else ""
    if _points is None:
        # ⛔ **點數算不出來 → 這一行連跨度都不印。**
        return f"- `{code}`{_mark}：這一筆的點數讀不出來（原始值 {entry.get('points')!r}）"
    if _span is None:
        return (f"- `{code}`{_mark}：**{_points} {POINTS_UNIT}**"
                f"（{_first} → {_last}，首末日期算不出天數）")
    return (f"- `{code}`{_mark}：**{_points} {POINTS_UNIT}**"
            f"（{_first} → {_last}，{SPAN_PHRASE} {_span} 天）")


def coverage_lines(coverage: dict[str, Any], held_codes_: set[str]) -> list[str]:
    """逐檔明細的全部行，**依代碼排序**（穩定順序，不隨 dict 插入序漂移）。

    ⛔ **讀不懂的條目也要有一行**：整個濾掉的話，「收到三筆讀不懂的東西」與
    「什麼都沒有」在畫面上一模一樣，而且會畫出一個**空的**展開器（違鐵則 04）。
    ⚠️ **排序 key 走 `str(...)`**：代碼理論上可能不是字串，混型別直接 `sorted()` 會炸。
    """
    _out: list[str] = []
    for _c, _e in sorted(coverage.items(), key=lambda _kv: str(_kv[0])):
        if not isinstance(_e, dict):
            # ⚠️ 只印**型別**不印值：一個壞掉的條目可能是很大的東西。
            _out.append(f"- `{_c}`：這一筆讀不出來"
                        f"（收到 {type(_e).__name__}，不是預期的欄位表）")
            continue
        _out.append(coverage_line(_c, _e, held=str(_c).upper() in held_codes_))
    return _out


def held_codes() -> set[str]:
    """這個 session 已列入的基金代碼（大寫）。**只用來加標記，不用來過濾。**

    ⛔ **不得**拿它去縮小 `coverage_status()` 的範圍：雲端累積的是**整張表**，
    用一個「開站不會自動載入」的 session 鍵去過濾，等於把使用者真的有、
    但這個 session 還沒載入的那些**藏起來**（§1：不知道 ≠ 沒有）。
    """
    return {str(_f.get("code", "")).strip().upper()
            for _f in _holdings() if str(_f.get("code", "")).strip()}


# ══════════════════════════════════════════════════════════════════════════
# 五個線框區塊（＋ 一個線框沒有給位置的，見 (D-5)）
# ══════════════════════════════════════════════════════════════════════════

def _render_source_health() -> None:
    """區塊 1｜資料來源健康度 —— **委派** `render_data_guard_tab()`，整塊在 gate 之後。

    線框：「每源最後成功時間與資料日期。」chip：「三態」。

    ⭐ **gate 的理由（本檔最重要的一條，總管裁決 3）**：
    `render_data_guard_tab()` 的開頭有一次**無條件的匯率抓取**（線框已點名），
    ＋ caller 契約要求先跑 `_update_data_registry()`。在單頁的 ⑤ 裡，這些會跟著
    本頁**每一次互動**重跑 —— gate 讓重運算留在使用者的一次點擊之後。
    ⛔ **拿掉這個 checkbox ＝ 打開 ⑤ 就對外取數。**

    ⚠️ **本檔不畫「18 源 · 2 異常」** —— 那是線框的示意值（D-3）。在這一頁上尤其毒：
       使用者進來就是要問「我的資料可不可信」，一個假的「2 異常」會直接被當成答案。
       ⛔ 而且 (A) 路線之下**根本沒有理由畫它**：真的來源清單由被委派的舊模組畫。
    ⚠️ **`NAV_HISTORY` 在這裡也要持有，而且這一項最容易漏** —— 所有權是
       thread-local ＋ context manager 作用域，別的區塊那個 `with` 一離開就還原了。
       漏掉它的後果不是報錯，是「🗂️ NAV 歷史匯入與累積狀態」**又在這裡畫一次**，
       而且沒有任何東西會叫。
    """
    _open = st.checkbox(
        DIAG_GATE_LABEL,
        key=_SK_DIAG_GATE,
        help="診斷區載入時會更新資料註冊表並抓取匯率等即時狀態。"
             "沒遇到問題時可以完全略過（診斷頁自己的說明原文）。",
    )
    if not _open:
        # ⚠️ 指路指的是**上方那個 checkbox**，不是本區塊自己 —— 這一則是
        #    本頁少數「去了真的有用」的指路：勾起來就會載入。
        #    字面吃 :data:`DIAG_GATE_LABEL`，**不手抄**（手抄的那一刻它就開始漂移）。
        not_ready(_DIAG_NOT_LOADED_NOTE, where=f"上方「{DIAG_GATE_LABEL}」")
        return

    # caller 契約（`ui/tab5_data_guard.py` 的 docstring）：呼叫前先更新 data_registry。
    from ui.helpers.data_registry import _update_data_registry
    from ui.tab5_data_guard import render_data_guard_tab

    _update_data_registry()
    # ⑤ 已畫區塊標題 → 診斷頁不再畫自己的 `##` 頁面大標（其餘一行不動）。
    with settings_page_owns(DATA_GUARD_HEADER, NAV_HISTORY):
        render_data_guard_tab()


def _render_nav_status() -> None:
    """區塊 2｜NAV 累積狀態 —— **本檔實作，刻意不委派**（總管裁決 2，理由見 (D-4)）。

    線框逐字：「雲端歷史涵蓋度，逐檔可展開。」

    四種狀態，**一次只顯示一種**（順序不可顛倒）
    ---------------------------------------------

    ===========================  ==================================================
    狀態                          畫面
    ===========================  ==================================================
    gate 沒勾（**預設**）           ⬜ 尚未讀取（:data:`_NOT_LOADED_NOTE`）
    後端未啟用                     ⬜ 讀不到 ＋ **缺哪幾把 secret**
    讀到了、但一筆都沒有             空狀態（:func:`empty_state`）
    讀到了、有資料                   總結一句 ＋ 逐檔明細（展開器）
    ===========================  ==================================================

    ⛔ **「後端未啟用」必須排在「一筆都沒有」前面，這是總管裁決也是 §1。**
    `coverage_status()` 在**未啟用**與**工作表不存在**時**都回 `{}`** ——
    它自己的 docstring 逐字寫著「呼叫端須據此顯示『未啟用』而非『0 點』」。
    **本組已實測那條路徑**：`load_points()` 開頭
    ``if _sheet is None and not is_enabled() and oauth_client is None: return []``
    → `coverage_status()` 的 ``if not _pts: return {}``。**兩條路真的會匯流成同一個 `{}`。**

    ⚠️ **本塊不自己接 `try/except`**：`coverage_status()` 在來源冷卻期／真 I/O 失敗時
       **會拋 `NavHistoryError`**（那是 L2 刻意的 §1 行為，不是 bug）。
       由 :func:`render_settings_and_diagnostics` 幫本塊單獨包一層 `safe_section()`。
       自己 `except` 會變成吞例外（§1 違憲）。
    """
    _open = st.checkbox(
        NAV_GATE_LABEL,
        value=False,
        help="讀一次 Google Sheets 的 nav_history；沒勾就完全不連線。",
    )
    if not _open:
        # ⚠️ 同上：指的是上方那個 checkbox，字面吃 :data:`NAV_GATE_LABEL`。
        not_ready(_NOT_LOADED_NOTE, where=f"上方「{NAV_GATE_LABEL}」")
        return

    # ⛔ 先問「能不能看」，再問「看到什麼」—— 順序顛倒就會把「未啟用」講成「0 點」。
    _backend = fetch_nav_backend_status()
    if not _backend.get("enabled"):
        _missing = ", ".join(str(_m) for _m in (_backend.get("missing") or [])) or "（未回報）"
        not_ready(
            f"{_BACKEND_UNAVAILABLE_NOTE}{_missing}。"
            # ⚠️ **刻意不寫「這兩把」** —— `status()` 的 `missing` 可能只有一項。
            "這些是部署環境的 secret，畫面上改不了。",
            where=_where(BLOCK_KEYS))
        return

    _coverage = fetch_nav_coverage()
    # ⚠️ **展開器開不開，看的是「有沒有可渲染的行」，不是「dict 空不空」**：
    #    `{'AAA': None}` 這種**非空但整包讀不懂**的回傳，若照 dict 判斷會畫一個
    #    **空的**展開器（違鐵則 04）。現在每一個條目都會產出一行，
    #    所以 `_lines` 空 ⟺ `_coverage` 空 —— **這條性質是結構保證的，不是巧合。**
    _lines = coverage_lines(_coverage, held_codes())
    if not _lines:
        empty_state(_EMPTY_TITLE, _EMPTY_MISSING,
                    where=_where(nav_manual_label()),
                    footer=_EMPTY_FOOTER)
        return

    st.markdown(f"##### {coverage_headline(_coverage)}")
    with st.expander(NAV_DETAIL_LABEL, expanded=False):
        st.caption(
            f"「{SPAN_PHRASE}」量的是**第一筆到最後一筆**的日曆天數，"
            "**不代表中間每天都有**；能不能算長期指標看的是點數。")
        for _line in _lines:
            st.markdown(_line)


def _render_keys() -> None:
    """區塊 3｜連線與金鑰 —— **委派**保單管理橋接 ＋ 抓取診斷細節。

    線框：「Google 授權、Proxy、API 金鑰。」

    ⛔ **不畫「正常」** —— 線框示意值（D-3），而且是三個之中**最危險**的一個：
       它是一句**系統對自己健康狀態的斷言**。使用者會據此排除掉
       「是不是我金鑰過期」這個真正的原因。

    ⛔ **本檔不切換 `POLICY_ADMIN` 旗標**（總管指示，且有硬前置未解）：
       今天 `app.py` 一次都沒有持有它 → `render_policy_admin_bridge()` 只畫一句灰色指路，
       它掛的那一整支 Google Sheets 寫入是**死碼**。順手打開它會讓一整批寫入路徑活過來，
       而 `policy_admin_bridge` 的 docstring 明列了**三條尚未處置的硬前置**
       （session_state 先寫後讀耦合 / `sheet_client` 無 SSOT / oauth snapshot 紀律）。
       → 守衛：:func:`~tests.test_wf05_settings_skeleton.test_the_page_never_opens_the_policy_admin_flag`。

    ⚠️ **「API 金鑰狀態 / NAS Proxy 測試」仍住在 `render_data_guard_tab()` 深處**
       （舊 ⑤ 的模組 docstring 早已登記這一點）—— 抽出屬 tab5 的拆分批次，
       **(A) 路線明令不得改舊模組**，故本塊只承接兩個已可承接的對象。
       **這是已知缺口，不是漏做。**
    """
    render_policy_admin_bridge(sheet_client=None)
    # ⚠️ 個基頁那份由 `FETCH_DIAG` 旗標控制，而那個旗標**必須由 `app.py` 持有**
    #    才壓得住它（理由見模組 docstring 最後一段）。本檔刻意不在這裡包。
    render_fetch_diag_from_session()


def _render_backfill() -> None:
    """區塊 4｜手動補資料 —— **委派** `render_nav_manual_section()`（三條寫入路徑）。

    線框逐字：「CSV 匯入淨值歷史、一鍵補抓、逐檔結果。**寫入類動作，全部 Form 封裝。**」

    ⚠️ **三條路徑實測不等價，一條都不能砍**（`nav_history_section` 的模組 docstring
       有逐條對照表）：① 一鍵自動補全（連外抓 → 本地 cache ＋ 雲端）、
       ② 對帳單 CSV（單檔、代碼手填、**只寫雲端**、吃兩欄 CSV）、
       ③ 本地基底 CSV（多檔、代號讀自 CSV、寫本機 cache ＋ 雲端）。

    ⚠️ **一個 Form 封裝上的硬限制，據實寫明**：③ 底下的「📤 下載當前 cache 為 CSV」
       用的是 `st.download_button`，Streamlit **在原始碼層面無條件禁止它出現在
       `st.form` 內**。那是平台限制，不是選擇 —— 完整說明在被委派函式的 docstring。

    ⛔ **本檔不再自己畫一個「按了不會寫」的假 Form。** 改寫前的版本按下送出鍵只把
       選擇寫進 session、**沒有任何 I/O**，並靠一行灰態自陳「實際補抓功能尚未接上」。
       (A) 路線之下那個取捨消失了：**真的寫入功能一直都在舊模組裡**，委派過去即可。
    """
    from ui.helpers.settings_diag.nav_history_section import render_nav_manual_section

    # ⚠️ 這裡**不需要**持有 `NAV_HISTORY`：`render_nav_manual_section()` 是直接呼叫
    #    三個 helper，它們自己不查旗標（本組 AST 實測：三支函式體內 0 個旗標呼叫）。
    #    旗標要持有的地方是**委派整頁的那兩處**（區塊 1 與 4.5）。
    render_nav_manual_section()


def _render_maintain() -> None:
    """（4.5）｜🗄️ 資料維護與通報 —— **委派** `render_manage_tab()`。

    ⚠️ **線框 Tab 05 沒有這一塊，這是登記在案的偏離**（見模組 docstring 的 (D-5)）。
    線框的「從哪裡搬來」逐字列了 `ui/tab_manage.py`，但五個 `<h4>` 裡沒有任何一塊
    叫得出「選股池」「除息行事曆」「換股通報」。塞進「手動補資料」會讓畫面說謊；
    整個不畫等於刪功能。**故另立一塊並就地登記。**

    ⚠️ **持有 `MANAGE_HEADER` ＋ `NAV_HISTORY` 兩支**：
    - `MANAGE_HEADER` → 管理室不再畫它自己的 `##` 頁面大標（⑤ 已畫區塊標題）；
    - `NAV_HISTORY`  → 管理室**跳過** `_sec_nav_backfill()`（那一塊已由區塊 4 畫）。
      ⛔ 漏掉它的後果是「🗄️ 補歷史淨值」在同一頁**畫第二次**，而且不報錯。
      ✅ **粒度實測**：`render_manage_tab()` 只跳過那一段，選股池／除息行事曆／
      換股通報**照畫** —— 這正是總管裁決 2 能成立的前提。

    📌 **一個已知的副作用寫入，登記在此，但不由本檔處置**（總管 2026-09-06 裁決）：
    `render_manage_tab()` → `_sec_pool()` → `repositories/pool_repository.py::list_pool()`
    第一行呼叫的 `_ws()` 會在讀取路徑上 `add_worksheet` / `ws.update("A1", …)` 補 header
    —— **讀一下就寫回去**。客戶 2026-09-06【永久授權】原則一明令「查詢/搜尋一律唯讀」，
    該處已由 **P0-B 組（PR #796，branch `claude/fund-readonly-sn42bh`）** 在切。
    ⛔ **本檔不得為了避開它而改寫、包一層或改成不呼叫舊模組** —— 那是繞道，不是修好；
       也**不得**去動 `repositories/pool_repository.py`：那是 P0-B 的檔案邊界
       （§-1.5 v1 第一條第 2 點 File Boundary ＋ `PROCESS.md §3` 寫入端序列化）。
    """
    from ui.tab_manage import render_manage_tab

    with settings_page_owns(MANAGE_HEADER, NAV_HISTORY):
        render_manage_tab()


def _render_manual() -> None:
    """區塊 5｜使用手冊 —— **委派** `render_manual_tab()`。**靜態文字，不是灰態**（D-1）。

    線框逐字：「指標定義、門檻由來、常見誤讀。**純文字，不佔首屏**。」

    ⛔ **這一塊不准畫成灰態**（依據見 (D-1)）。改寫前的版本只放了三行**目錄**，
       而真內容（`ui/tab6_manual.py`，十章 + 錨點目錄）一直都在 —— (A) 路線委派過去。
    ⚠️ **「不佔首屏」怎麼落地**：本塊排在最後、且**收在 `st.expander` 裡預設不展開**。
       線框的 `dim`（虛線框 + 灰標題）是 HTML 的視覺降權手法，在 Streamlit 沒有等價物；
       「預設收合」是本 repo 拿得到、且**語意相同**（在，但不搶版面）的那一個。
       ⚠️ **這是本組挑的落地方式，不是線框指定的** —— 線框只說「不佔首屏」。
    """
    from ui.tab6_manual import render_manual_tab

    with st.expander(BLOCK_MANUAL, expanded=False):
        # ⑤ 已畫區塊標題 → 說明書不再畫自己的 `##` 頁面大標（其餘一行不動）。
        with settings_page_owns(MANUAL_HEADER):
            render_manual_tab()


def render_settings_and_diagnostics() -> None:
    """渲染「⑤ 設定與診斷」整頁 —— 五塊照線框順序，功能全部委派舊模組。

    ⚠️ **每個區塊各自走 `safe_section()`，這是本頁最重要的一條紀律。**
    合併成一頁之後六個區塊共用同一次 script run：管理室當掉會一併帶走
    🔭 資料診斷與 📖 說明書，而那兩塊正是使用者出事時要去的地方
    （本頁一句話職責：「出事時第一個進來」）——
    **把診斷跟故障綁在同一條命上，等於在最需要它的時候把它拿走。**
    `safe_section` **不吞例外**（§1）：它走 `system_error()` 顯式紅框 ＋ traceback。

    ⚠️ **沒有 `render_story_nav("settings")`** —— 它會靜默 no-op，理由見模組 docstring。
    ⚠️ **沒有頁面層級的空狀態**（D-2）—— 與 ④ 刻意不同。
    ⚠️ **本批尚未接進 `app.py`**，所以現在**沒有 production caller**。
    """
    st.markdown(f"## {tab_label('settings')}")
    # 線框 Tab 05 的職責宣告 ＋「這裡不放什麼」。
    # ⚠️ 指路的顆粒度**跟著線框走**：線框寫「任何投資判斷 → 01 ~ 04」（整個分頁）。
    st.caption(
        "回答一個問題：**資料本身可不可信、要不要我補？** 平常不用進來；"
        f"出事時第一個進來 —— 任何投資判斷在 {where_to_find('macro')} "
        f"到 {where_to_find('portfolio')} 之間。")

    # ── 線框 Tab 05 的五塊，順序逐字照線框 ────────────────────────────────
    # ⚠️ **區塊標題一律 `### `，理由是它要跟被委派模組的頂層標題同一級**：
    #    `render_data_guard_tab()` / `render_manage_tab()` / `render_nav_manual_section()`
    #    的頂層區塊全部用 `### `。用 `#### ` 會讓**我的區塊標題比它裝的東西還小**，
    #    用 `## ` 會與頁面大標同級。這個階層是被委派模組決定的，(A) 路線不改它們。
    st.markdown(f"### {BLOCK_HEALTH}")
    safe_section(BLOCK_HEALTH, _render_source_health)

    st.markdown(f"### {nav_status_label()}")
    safe_section(nav_status_label(), _render_nav_status)

    st.markdown(f"### {BLOCK_KEYS}")
    safe_section(BLOCK_KEYS, _render_keys)

    # ⚠️ **區塊 4 刻意不由本檔畫標題** —— `render_nav_manual_section()` 自己會畫
    #    `### {section_label("nav_manual")}`（`nav_history_section.NAV_MANUAL_HEADING`），
    #    **與本檔會畫的那一行同一份 SSOT、同一級、逐字相同**。本檔再畫一次的結果是
    #    畫面上連著出現兩個一模一樣的「手動補資料」。
    #    ⛔ **另一條路（改成直接呼叫底下三個 helper）本檔不走**：那會把「這一塊裝哪三條
    #       寫入路徑」複製成第二份真相源（§2.1），而它正是 `nav_history_section`
    #       模組 docstring 花了一整張表在守的東西。
    #    → 守衛：`test_each_block_heading_is_drawn_exactly_once`（六個區塊逐一驗，
    #       0 次 ＝ 那一塊不見了、2 次 ＝ 畫重複了，**兩個方向都紅**）。
    safe_section(nav_manual_label(), _render_backfill)

    # ⚠️ 線框沒有給這一塊位置，見模組 docstring 的 (D-5)。**登記在案的偏離。**
    st.markdown(f"### {maintain_label()}")
    safe_section(maintain_label(), _render_maintain)

    st.markdown(f"### {BLOCK_MANUAL}")
    safe_section(BLOCK_MANUAL, _render_manual)
