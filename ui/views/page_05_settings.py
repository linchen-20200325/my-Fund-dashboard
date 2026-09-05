"""⑤ 設定與診斷 —— 五分頁動線重構的**最後一頁**（全新撰寫，非舊 `tab*.py` 的搬運）。

客戶方針（2026-09-04）第 1 條：UI 渲染層打掉重練，不改舊 `tab*.py`，從零撰寫全新 View。
客戶方針（2026-09-05）：本頁**只做骨架 + 灰態**；每一塊的真內容**分批填**。

整頁骨架 —— 取自已核准線框 `docs/wireframes/ia-wireframe.html` 的 **Tab 05**
------------------------------------------------------------------------------

===== ====================== ==================================================
順序   區塊                    版面（線框 class 逐字）
===== ====================== ==================================================
1      資料來源健康度          `grid3` 第 1 欄（線框 chip：「三態」）
2      NAV 累積狀態            `grid3` 第 2 欄
3      連線與金鑰              `grid3` 第 3 欄
4      手動補資料              `card span3`（**全寬**；chip：「Form 封裝」「寫入類」）
5      使用手冊                `card span3 dim`（**全寬**；線框：「純文字，不佔首屏」）
===== ====================== ==================================================

線框同時釘死了本頁的**職責邊界**：

> 回答一個問題：**資料本身可不可信、要不要我補？** 平常不用進來；出事時第一個進來。

⛔ **因此本頁不放**（線框「這裡不放什麼」逐字）：
   「**快取與退避狀態不做成畫面** ─ 沿用先前已拍板的裁示：那批不必改任何畫面，
   本次不推翻」「任何投資判斷 → **01 ~ 04**」。
   → 本檔**沒有任何快取／退避狀態的區塊**，由
   `tests/test_wf05_settings_skeleton.py::test_the_page_does_not_render_cache_or_backoff_state` 釘住。

三則總管裁決（2026-09-05）—— 理由寫在這裡，是為了讓後人**能推翻它**
==================================================================

(D-1) 「使用手冊」那張卡的 `dim` **不是灰態**
---------------------------------------------
**實測依據**（`grep -n 'dim' docs/wireframes/ia-wireframe.html`，全檔僅 5 個命中）：

===========  =========================================================
命中          它是什麼
===========  =========================================================
`:193/:198`  CSS 兩行（`.card.dim{border-style:dashed;...}`）
`:379`       `card dim` ＋ **`灰態` chip**，內文「未載入。點上方…」
`:552`       `card dim` ＋ **`灰態` chip**，內文「幣別未知…」
`:706`       `card span3 dim`，**沒有 `灰態` chip**，內文「**純文字**」
===========  =========================================================

→ `dim` 在這份線框裡承擔**兩種**意思。前兩處配著 `灰態` chip ＝「還沒接上」；
**使用手冊那一處沒有那個 chip** ＝ **視覺降權**（不佔首屏），不是「還沒接上」。

⛔ **因此使用手冊不得畫成灰態佔位。** 它是**現在就能出的靜態文字**（指標定義、
門檻由來、常見誤讀），把它畫成「未載入」是對使用者說一句**假話**（`CLAUDE.md §1`）——
而且是這一頁最不該說謊的地方：本頁的職責就是回答「資料可不可信」。
→ 守衛：:func:`~tests.test_wf05_settings_skeleton.test_the_manual_is_static_text_not_a_grey_placeholder`。

(D-2) 本頁**沒有頁面層級的空狀態**；空狀態只可能出現在單一區塊
--------------------------------------------------------------
**線框事實**：Tab 05 **沒有畫任何空狀態區塊**（②③④ 都有）。

**以下是總管的判斷，不是線框寫的 —— 寫在這裡讓後人能推翻**：

- 「資料來源健康度」「連線與金鑰」**永遠有狀態可說** —— 沒設定金鑰**本身就是一個
  真答案**，不是「空」。把「你沒設金鑰」畫成空狀態，等於把一個已知事實
  講成「查不到」。→ 兩者用**灰態**（本批未接線）。
- 「手動補資料」是 Form、「使用手冊」是靜態文字 → **都不會空**。
- **只有「NAV 累積狀態」可能真的空**（一檔基金都沒有 → 沒有涵蓋度可談）
  → **那一塊**走 :func:`ui.helpers.ia.empty_state.empty_state`，指路指向 ④。

⛔ **不得**因為 ②③④ 都有頁面層級空狀態就照抄一個到 ⑤。
⚠️ 對照 `page_04_portfolio.py`：④ 的空狀態是**頁面層級**的（沒持倉 ⇒ 四塊全都無意義），
   ⑤ **不是**（沒持倉時，來源健康度與金鑰狀態照樣有話可說）。**兩者不要互相抄。**

(D-3) 線框裡的示意值**一個都不准畫**
------------------------------------
`18 源 · 2 異常`／`42 檔 · 最長 6.2 年`／`正常` **全是線框示範版面用的假數字**。

使用者**看不出它是假的**，而且會拿它判斷「我的資料到底可不可信」——
**這一頁的職責就是回答那個問題，在這裡放假數字是最壞的一種**（§1：錯誤的數字比
沒有數字更危險）。→ 守衛：
:func:`~tests.test_wf05_settings_skeleton.test_the_page_never_prints_the_illustrative_values_from_the_wireframe`
（比照 ④ 的同名守衛，黑名單同樣**只擋名單內的字面寫法**，見該處的射程聲明）。

區塊名怎麼來的 —— 兩個走 SSOT、三個照線框字面
==============================================

`ui/helpers/story_nav.py::_SECTION_LABELS` 目前**只收了 ⑤ 五塊裡的兩塊**
（`nav_status` = 「NAV 累積狀態」、`nav_manual` = 「手動補資料」，2026-09-02 加入，
該處註解自陳是逐字照線框、刻意不加 emoji）。

===================  ==================================  ==============================
線框 `<h4>`           本檔怎麼取名                          理由
===================  ==================================  ==============================
資料來源健康度         :data:`BLOCK_HEALTH`（線框字面）      **SSOT 沒有這個 key**
NAV 累積狀態          :func:`nav_status_label` → SSOT      `nav_status`
連線與金鑰            :data:`BLOCK_KEYS`（線框字面）         **SSOT 沒有這個 key**
手動補資料            :func:`nav_manual_label` → SSOT      `nav_manual`
使用手冊              :data:`BLOCK_MANUAL`（線框字面）       見下方 ⚠️ 張力
===================  ==================================  ==============================

⚠️ **本批刻意不新增 `_SECTION_LABELS` 的 key**（不在本批檔案邊界內）——
同 `page_04_portfolio.py::BLOCK_POLICY` 的處置：**沒有 key 就照線框字面寫，
並就地註明理由**，不要順手改別人的 SSOT。

⚠️ **一處尚未裁決的張力，請務必讀完（不要略過）**：`_SECTION_LABELS` **有**一個
`manual` key，值是 **「📖 說明書」**，而線框 Tab 05 的 `<h4>` 寫的是 **「使用手冊」**
—— **兩個名字指的很可能是同一塊東西**（`manual` 的所屬分頁在 `_SECTION_TO_TAB`
裡正是 `settings`）。

本檔取**線框字面**（「使用手冊」），理由兩條：
  (a) 線框是**客戶看過並拍板的那份視覺**，`_SECTION_LABELS` 的 `manual`
      是七→五之前就有的舊分區名，**沒有經過這份線框的確認**；
  (b) 用 `section_label("manual")` 會在畫面上印出「📖 說明書」——
      那與客戶拍板的字**不一樣**，屬於拿樣式覆蓋客戶拍板的字
      （正是 `_SECTION_LABELS` 自己那段註解在防的事）。

⛔ **但這一條沒有被裁決過，本檔不宣稱它是對的。** 若「使用手冊」與「📖 說明書」
確實是同一塊，正解是**把 SSOT 那一格改成線框字面**（一處改，全站跟著對），
而不是像現在這樣**同一塊東西在兩個地方各有一個名字**。
→ 已具名回報總管；在裁決落下之前，本檔的
:data:`BLOCK_MANUAL` 就是那個**登記在案的第二份真相源**。

⚠️ **本頁沒有 `render_story_nav()`，這是刻意的，不是漏做**
===========================================================
`story_nav.render_story_nav()` 的第一行是
``if _as_tab_key(current) not in _VALID: return`` —— 而決策動線只有**四站**
（`macro` / `health` / `research` / `portfolio`）。`render_flow_nav` 的 docstring
自己就寫著「**⑤ 設定與診斷不在其中**」。

→ 也就是說 `render_story_nav("settings")` 會**靜默什麼都不畫**。
照抄 ①②③④ 那一行進來，會得到一個**看起來有做、實際是 no-op** 的呼叫，
下一個人得自己去讀 `_VALID` 才知道它從來沒生效過。**本檔不放那一行。**
→ 守衛：:func:`~tests.test_wf05_settings_skeleton.test_the_page_does_not_call_a_no_op_story_nav`。

⚠️ **本批尚未接進 `app.py`**（客戶明令舊分頁不動、不接線、不下架），
所以本檔現在**沒有 production caller** —— 這是**刻意的中間狀態**，不是漏接。
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from ui.helpers.ia import (
    STATE_NOT_READY,
    applied_form,
    card_row,
    state_card,
)
from ui.helpers.ia.empty_state import empty_state
from ui.helpers.render_state import not_ready, safe_section
from ui.helpers.story_nav import section_label, tab_label, where_to_find

# ── session 鍵名（本檔自己的命名空間）────────────────────────────────────────
# ⚠️ 刻意**不**沿用舊 ⑤（`ui/tab5_data_guard.py` / `ui/tab_manage.py` /
#    `ui/tab_settings_diag.py` / `ui/tab6_manual.py`）的鍵：那四個舊頁依方針第 3 條
#    仍在磁碟上、且仍接在 `app.py`，共用鍵會讓兩套 View 互相覆寫對方的狀態。
_FORM_KEY: str = "v05_settings_backfill_form"
#: **已送出**的補資料請求（不是 widget 當下值）。下游只准讀這個 —— 理由見 :func:`_applied_request`。
#: `None`／不存在 ＝ 還沒送出過（或送出時沒有勾任何一種來源）。
_SK_APPLIED: str = "v05_settings_applied_backfill"

#: 使用者的持股來源。既有 session 契約，由 ④ 的加入基金流程／`ui/helpers/cloud_io.py` 寫入。
#: ⚠️ 這個字串是**別人定義**的鍵名，本檔只讀不寫 —— 不要在這裡「順手改個好名字」。
_SK_PORTFOLIO: str = "portfolio_funds"

# ── Form 的欄位（線框 Tab 05：「CSV 匯入淨值歷史、一鍵補抓、逐檔結果」）────────
#: 線框沒有指定送出鈕的字（④ 的「試算」是線框寫的，這裡沒有）。
#: 取 `ia.APPLY_LABEL` 的預設會是「套用」—— 對一個**寫入類**動作而言太輕，
#: 故具名為「開始補抓」，讓「這是一個會動到資料的動作」在鈕上就看得見。
#: ⚠️ **這是本組挑的字，不是線框給的** —— 具名而不 inline，是為了讓它可被推翻。
SUBMIT_LABEL: str = "開始補抓"
_LABEL_SOURCE_CSV: str = "CSV 匯入淨值歷史"
_LABEL_SOURCE_REFETCH: str = "一鍵補抓"
_LABEL_ONLY_MISSING: str = "只補有缺口的檔"

#: 兩個來源的預設。⚠️ **兩個都預設不勾**，這是刻意的：
#: 這是**寫入類**動作，預設勾好等於使用者一按鈕就寫了他沒想寫的東西。
#: 對照 ④ `_DEFAULT_BUDGET_TWD = 0`（同樣刻意不照線框的示意值）——
#: **會動到使用者資料的欄位，預設值一律取「不做事」的那一邊。**
_DEFAULT_SOURCE_CSV: bool = False
_DEFAULT_SOURCE_REFETCH: bool = False
#: 「只補有缺口的檔」預設**勾選** —— 它是**縮小**寫入範圍的開關，
#: 預設縮小同樣是「不做事的那一邊」，與上面兩行同一個原則、不是不一致。
_DEFAULT_ONLY_MISSING: bool = True

# ── 區塊名 ────────────────────────────────────────────────────────────────
#: 線框 Tab 05 `<h4>` 逐字。**SSOT 沒有這個 key**（見模組 docstring 的對照表）。
#: 線框 chip：「三態」—— 那是**下一批的取數約束**（每源要能分出正常／異常／未知），
#: 本批沒有取數，故只登記不實作。
BLOCK_HEALTH: str = "資料來源健康度"
#: 線框 Tab 05 `<h4>` 逐字。**SSOT 沒有這個 key**（見模組 docstring 的對照表）。
BLOCK_KEYS: str = "連線與金鑰"
#: 線框 Tab 05 `<h4>` 逐字。⚠️ **與 `section_label("manual")`（「📖 說明書」）並存的
#: 第二份真相源，尚未裁決** —— 完整理由與正解見模組 docstring。
BLOCK_MANUAL: str = "使用手冊"


def nav_status_label() -> str:
    """「NAV 累積狀態」—— **走 SSOT，不抄線框字面**（`_SECTION_LABELS["nav_status"]`）。

    ⚠️ 做成函式而不是 module 層常數，是為了讓 `section_label()` 的
    §1 Fail Loud（未知 key 直接 `KeyError`）發生在**渲染當下**而不是 import 期 ——
    import 期炸掉會讓整個 `ui.views` 套件無法載入，連帶打死其他四頁。
    （同 `page_04_portfolio.py::switch_block_label` 的處置。）
    """
    return section_label("nav_status")


def nav_manual_label() -> str:
    """「手動補資料」—— **走 SSOT，不抄線框字面**（`_SECTION_LABELS["nav_manual"]`）。

    做成函式的理由同 :func:`nav_status_label`。
    """
    return section_label("nav_manual")


#: 本批共用的灰態理由。**只有一句話**，因為它會出現在多個地方，
#: 各寫一句就是多份會各自漂移的真相源（§2.1）。
_PENDING_NOTE: str = "本頁分批上線，這一塊的內容還沒接上"


def _pending_where(block: str) -> str:
    """「內容還沒填」這種灰態的指路。**回傳的必須是一個「地方」。**

    `render_state.not_ready()` 會把它包成「（請先到：…）」——
    也就是說回傳值會變成一句**祈使句的受詞**。塞一句狀態陳述進去
    （「目前只有 X 是完整的」）會產生一句**不可執行的指令**：那是 ③
    `ui/views/page_03_research.py` 2026-09-05 被獨立紅隊實測抓到的錯。**本檔從第一版就避開它。**

    ⛔ **「是一個地方」不等於「去了有用」，這兩件事本檔分開講**：
    這一塊沒接上，去任何地方都不會讓它出現 —— 能指的最誠實的地方就是本頁上
    唯一真的做完的那一塊（＝手動補資料的 Form），而灰態本文
    （:data:`_PENDING_NOTE`）已經先講了「這一塊的內容還沒接上」。
    ✅ **對照**：NAV 累積狀態的**空狀態**（:func:`_render_nav_status`）那一則指路是
    **真的有效**的，而且是 AppTest 實跑驗過的。**兩者不要混為一談。**

    ⚠️ 分頁名走 `where_to_find()`，**不手抄**；區塊名由呼叫端傳進來，
    不在這裡再抄一份（手抄的指路在本 repo 已經指錯三次）。
    ⚠️ **刻意不用「」把 `block` 括起來**：`tests/test_batch2_top_card_grid.py::`
    `test_every_where_names_something_that_exists_on_screen` 只對 ``「」`` 內的
    **字面值**比對「畫面上有沒有這個字」，而它的字表不收 `st.caption` ——
    加了括號會產生一條**必然失敗**的比對，不是多一層保護（③ 的既有登記）。
    """
    return f"{where_to_find('settings')} → {block}"


def _holdings() -> list[dict[str, Any]]:
    """使用者**目前持有**的基金。讀既有 session 契約，**不自己取數**。

    ⚠️ **這裡刻意`不`做 `loaded` 過濾**，與 `page_02_health.py` / `page_04_portfolio.py`
    的同名函式**故意不同** —— 理由是本頁的問題不一樣：
    ②④ 問的是「**拿這幾檔去算**」，沒載入的算進去會生出一個不完整的結論（§1）；
    ⑤ 的 NAV 累積狀態問的是「**雲端歷史涵蓋了哪幾檔**」，而
    **「已列入但還沒抓回來」正是這一頁最該顯示的那一種** ——
    把它濾掉，等於讓「該補的那幾檔」從一個專門用來看「要不要我補」的畫面上消失。
    ⛔ 因此本頁的空狀態門檻是「**一檔都沒列**」，不是「一檔都沒載入成功」。
    """
    _cur = st.session_state.get(_SK_PORTFOLIO)
    return [_f for _f in _cur if isinstance(_f, dict)] if isinstance(_cur, list) else []


def _normalise_request(csv_import: Any, refetch: Any, only_missing: Any) -> dict[str, Any]:
    """把三個 widget 值收成一份**已送出**的補資料請求。"""
    return {
        "csv_import": bool(csv_import),
        "refetch": bool(refetch),
        "only_missing": bool(only_missing),
    }


def _applied_request() -> dict[str, Any] | None:
    """**已送出**的補資料請求；沒送出過回 `None`。

    ⚠️ 下游只准讀這個，**不准讀 widget 當下值** —— 那正是鐵則 02（Form 封裝防重繪）
    要買的東西：勾一下 checkbox 不該觸發任何寫入。
    """
    _cur = st.session_state.get(_SK_APPLIED)
    return _cur if isinstance(_cur, dict) else None


def _render_source_health() -> None:
    """區塊 1｜資料來源健康度（`grid3` 第 1 欄）。本批灰態。

    線框：「每源最後成功時間與資料日期。」chip：「三態」。

    ⛔ **不畫「18 源 · 2 異常」** —— 那是線框的示意值（D-3）。在這一頁上尤其毒：
       使用者進來就是要問「我的資料可不可信」，一個假的「2 異常」會直接被當成答案。
    ⚠️ chip「三態」講的是**下一批的取數約束**（每源要能分出正常／異常／未知，
       且未知不得被畫成正常），本批沒有取數，故只登記不實作。
    ⚠️ **這一塊沒有空狀態**（D-2）：來源清單是**系統自己的**，不是使用者填的 ——
       它永遠有話可說。「一個來源都沒有」不是使用者的處境，是系統壞了
       （那要走 `system_error()`，不是 `empty_state()`）。
    """
    state_card(BLOCK_HEALTH, state=STATE_NOT_READY,
               note=f"{_PENDING_NOTE}（每個來源的最後成功時間與資料日期）。",
               where=_pending_where(nav_manual_label()))


def _render_nav_status() -> None:
    """區塊 2｜NAV 累積狀態（`grid3` 第 2 欄）。**本頁唯一可能真的空的一塊**（D-2）。

    線框：「雲端歷史涵蓋度，逐檔可展開。」

    ⛔ **不畫「42 檔 · 最長 6.2 年」** —— 線框示意值（D-3）。
    ⚠️ **一檔都沒列 → 走空狀態**，指路指向 ④ 的「➕ 加入與管理基金」。
       ✅ **這一則的「去哪補」照著做真的有效**，而且是 AppTest 實跑驗過的：
       `portfolio_funds` 一有項目，本塊當場離開空狀態、改印灰態
       （`test_the_empty_state_pointer_actually_works`）。
    ⛔ **不得**在空狀態裡順便說「加完就會看到涵蓋度」：加完看到的是**灰態**
       （本塊還沒接線）。**兩種灰的下一步不同，一次只給一個**
       （`page_02_health.py` / `page_04_portfolio.py` 同型）。
    ⚠️ **「逐檔可展開」本批不畫**：沒有真資料就沒有「逐檔」可展開，
       先畫一個空的展開器就是鐵則 04 的冗餘占位。
    """
    if not _holdings():
        empty_state(
            "還沒有任何基金可以談涵蓋度",
            "雲端 NAV 歷史是逐檔累積的 —— 一檔都還沒列入，就沒有涵蓋度可看",
            where=where_to_find("pf_add"),
            footer="列入之後，這一塊才會開始累積。",
        )
        return
    state_card(nav_status_label(), state=STATE_NOT_READY,
               note=f"{_PENDING_NOTE}（雲端歷史涵蓋度與逐檔明細）。",
               where=_pending_where(nav_manual_label()))


def _render_keys() -> None:
    """區塊 3｜連線與金鑰（`grid3` 第 3 欄）。本批灰態。

    線框：「Google 授權、Proxy、API 金鑰。」

    ⛔ **不畫「正常」** —— 線框示意值（D-3），而且是三個之中**最危險**的一個：
       它是一句**系統對自己健康狀態的斷言**。在還沒接線的情況下印「正常」，
       使用者會據此排除掉「是不是我金鑰過期」這個真正的原因。
    ⚠️ **這一塊沒有空狀態**（D-2）：「**沒設定金鑰**」本身就是一個**真答案**，不是「空」——
       接線後它該是一張帶狀態的卡（未設定 ⇒ 灰、設了但驗不過 ⇒ 紅），
       不是一個「查無資料」的空畫面。**把已知事實講成「查不到」是造假的一種。**
    """
    state_card(BLOCK_KEYS, state=STATE_NOT_READY,
               note=f"{_PENDING_NOTE}（Google 授權、Proxy 與 API 金鑰的連線狀態）。",
               where=_pending_where(nav_manual_label()))


def _render_grid() -> None:
    """把區塊 1~3 排成 3 欄自適應網格（鐵則 01，線框 class `grid3`）。

    ⚠️ **走 `card_row()` 而不是自己 `st.columns(3)`** —— 本檔不得有自己的網格
    （`tests/test_wf05_settings_skeleton.py::test_the_page_draws_no_grid_form_or_tabs_of_its_own`
    ＋ 全域 `tests/test_ui_grid_contract.py` 兩條一起釘）。

    ⚠️ **走 `card_row()` 而不是 `render_cards()`，這是刻意的**：
       `render_cards()` 收的是一串**卡片定義 dict**，每張卡只能是 `state_card` 的一種狀態；
       而區塊 2 要在「一檔都沒列」時改走 `empty_state()`（D-2）——
       那是**另一個元件**，塞不進 `render_cards` 的 dict 形狀。
       ⛔ 硬要用 `render_cards` 的話，只剩下「把空狀態降級成一張灰卡」這條路，
       那會把「你還沒列入任何基金」（**使用者的處境，有下一步**）
       講成「這塊還沒接上」（**我們的進度，沒有下一步**）—— 那是說謊。
    """
    with card_row() as (_c1, _c2, _c3):
        with _c1:
            _render_source_health()
        with _c2:
            _render_nav_status()
        with _c3:
            _render_keys()


def _render_backfill_form() -> None:
    """區塊 4｜手動補資料（`card span3`，**全寬**）。**本批唯一做完的一塊。**

    線框逐字：「CSV 匯入淨值歷史、一鍵補抓、逐檔結果。**寫入類動作，全部 Form 封裝。**」
    chip：「Form 封裝」「寫入類」。

    ⚠️ **「全部 Form 封裝」是線框用粗體寫的硬要求**，不是建議 ——
       本塊的每一個輸入都在 `applied_form` 裡，勾選當下不觸發任何事，
       按下「{SUBMIT_LABEL}」才算數。由
       `tests/test_wf05_settings_skeleton.py::test_the_write_block_is_form_wrapped` 釘住。
    ⚠️ **「逐檔結果」本批不畫** —— 那要有真的補抓結果才有東西可列，
       本批沒有接線。⛔ **不得**先畫一張空的結果表佔位（鐵則 04：首屏無冗餘占位）。
    ⛔ **本批不做任何實際寫入**：送出只把請求存進 session（:data:`_SK_APPLIED`），
       **沒有任何 I/O**。這是刻意的 —— 一個「按了會真的寫」的鈕接在還沒驗過的骨架上，
       比沒有那個鈕危險得多。
    """
    _cur = _applied_request() or {}
    with applied_form(_FORM_KEY, submit_label=SUBMIT_LABEL) as _gate:
        st.caption(
            f"{nav_manual_label()}：這是**寫入類**動作 —— 勾選的當下不會發生任何事，"
            f"按「{SUBMIT_LABEL}」才算。")
        _csv = st.checkbox(
            _LABEL_SOURCE_CSV,
            value=bool(_cur.get("csv_import", _DEFAULT_SOURCE_CSV)),
            help="從你手上的 CSV 把淨值歷史補進雲端。",
        )
        _refetch = st.checkbox(
            _LABEL_SOURCE_REFETCH,
            value=bool(_cur.get("refetch", _DEFAULT_SOURCE_REFETCH)),
            help="向既有來源重新抓一次，補上中間缺掉的日期。",
        )
        _only_missing = st.checkbox(
            _LABEL_ONLY_MISSING,
            value=bool(_cur.get("only_missing", _DEFAULT_ONLY_MISSING)),
            help="只處理歷史有缺口的檔；取消勾選會重跑全部（比較慢）。",
        )

    # ⚠️ `if _gate:` 必須在 `with` **之外**（送出鈕在 `yield` 之後才建立）。
    if _gate:
        # ⛔ 兩個來源都沒勾 ＝ 沒有要補任何東西，**不算一次已送出的請求**。
        #    對照 ④ 的「可動用金額 0 不算試算」——「按了鈕」不等於「有事要做」。
        if _csv or _refetch:
            st.session_state[_SK_APPLIED] = _normalise_request(
                _csv, _refetch, _only_missing)
        else:
            not_ready("還沒選要補什麼 —— 請至少勾一種來源。")


def _render_manual() -> None:
    """區塊 5｜使用手冊（`card span3 dim`，**全寬**）。**靜態文字，不是灰態**（D-1）。

    線框逐字：「指標定義、門檻由來、常見誤讀。**純文字，不佔首屏**。」

    ⛔ **這一塊不准畫成灰態。** 完整依據（`dim` 的兩種意思、5 個命中的逐一判讀）
       寫在模組 docstring 的 **(D-1)**。一句話：這張卡**沒有** `灰態` chip，
       它的 `dim` 是**視覺降權**，不是「還沒接上」。
    ⚠️ **「不佔首屏」怎麼落地**：本塊排在最後、且**收在 `st.expander` 裡預設不展開** ——
       線框的 `dim`（虛線框 + 灰標題）是 HTML 的視覺降權手法，在 Streamlit 沒有等價物；
       「預設收合」是本 repo 拿得到、且**語意相同**（在，但不搶版面）的那一個。
       ⚠️ **這是本組挑的落地方式，不是線框指定的** —— 線框只說「不佔首屏」。
    ⚠️ **本批只放三個標題，內容分批填**：這三行是**目錄**不是內容，
       而目錄本身就是真的（線框逐字列了這三項）。
       ⛔ **不得**在這裡編一段「指標定義」充數 —— 那是造假（§1），
       而且是在一份**專門用來解釋門檻由來**的文件裡造假。
    """
    with st.expander(BLOCK_MANUAL, expanded=False):
        st.markdown(
            "- **指標定義**\n"
            "- **門檻由來**\n"
            "- **常見誤讀**\n")
        # ⚠️ 這一句是**誠實揭露**，不是灰態：它沒有走 `not_ready()`，
        #    因為上面那三行**已經是真的內容**（線框逐字的目錄），不是佔位。
        st.caption("以上三項的內文分批補上；這一塊不影響任何數字。")


def render_settings_and_diagnostics() -> None:
    """渲染「⑤ 設定與診斷」整頁。

    ⚠️ **本批尚未接進 `app.py`**（客戶明令舊分頁不動、不接線、不下架），
    所以現在**沒有 production caller** —— 這是**刻意的中間狀態**，不是漏接。

    ⚠️ **沒有 `render_story_nav("settings")`** —— 它會靜默 no-op，理由見模組 docstring。

    ⚠️ **區塊之間走 `safe_section()` 隔離**：`st.tabs` 是單次 run 渲染全部分頁，
    任一區塊拋未捕捉例外會**中止整個 script**，其後所有分頁空白。
    `safe_section` **不吞例外**（§1）：它走 `system_error()` 顯式紅框 ＋ traceback。

    ⚠️ **沒有頁面層級的空狀態**（D-2）—— 與 ④ 刻意不同，理由見模組 docstring。
    """
    st.markdown(f"## {tab_label('settings')}")
    # 線框 Tab 05 的職責宣告 ＋「這裡不放什麼」。
    # ⚠️ 指路的顆粒度**跟著線框走**：線框寫「任何投資判斷 → 01 ~ 04」（整個分頁），
    #    所以這裡指 `macro` 與 `portfolio` 兩個**分頁**當範圍的兩端，不是頁內分區。
    st.caption(
        "回答一個問題：**資料本身可不可信、要不要我補？** 平常不用進來；"
        f"出事時第一個進來 —— 任何投資判斷在 {where_to_find('macro')} "
        f"到 {where_to_find('portfolio')} 之間。")

    safe_section("狀態三卡", _render_grid)
    st.markdown(f"#### {nav_manual_label()}")
    safe_section(nav_manual_label(), _render_backfill_form)
    safe_section(BLOCK_MANUAL, _render_manual)
