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
**線框事實**：Tab 05 **沒有畫任何空狀態區塊**（②③④ 之中**只有 ② 有**）。

⚠️ **2026-09-05 獨立稽核更正（有意識的更正，不是漏刪）**：本句原寫
~~「（**②③④ 都有**）」~~ —— **括號那半是假的**。實測：全檔 `class="empty"`
**唯一一處在 `:486`**，落在 Tab 02 的 panel（`p2` 為 `:433`~`:521`）；
Tab 03／04 兩個 panel 逐行掃過 `<h4>`／chip／「尚未|還沒|沒有」，**都沒有任何形式的空狀態區塊**。
**前半句（Tab 05 沒有）為真，所以 (D-2) 的結論不受影響** —— 被推翻的只有那個括號。
⛔ **這一句的來歷要一起記，因為錯的不是事實，是「事實」這個標籤**：
括號那半原本出自**總管的判斷**，派工單裡明白標了「⚠️ 這是我的判斷，不是線框寫的」，
**落到本檔時卻被寫進「線框事實」那一行底下** —— **一句被升級成事實的判斷，
比一句誠實的判斷危險得多**：它讓後人以為那是可以直接引用的線框依據。
**升級的那一半剛好不成立，這不是巧合 —— 沒有人去查過它，所以才敢升級。**

**以下是總管的判斷，不是線框寫的 —— 寫在這裡讓後人能推翻**：

- 「資料來源健康度」「連線與金鑰」**永遠有狀態可說** —— 沒設定金鑰**本身就是一個
  真答案**，不是「空」。把「你沒設金鑰」畫成空狀態，等於把一個已知事實
  講成「查不到」。→ 兩者用**灰態**（本批未接線）。
- 「手動補資料」是 Form、「使用手冊」是靜態文字 → **都不會空**。
- ~~**只有「NAV 累積狀態」可能真的空**（一檔基金都沒有 → 沒有涵蓋度可談）
  → **那一塊**走 :func:`ui.helpers.ia.empty_state.empty_state`，指路指向 ④。~~
  → ⚠️ **2026-09-06（P05-1）就地更正：括號裡那個條件是錯的，而且它會讓畫面說謊**
  （**有意識的更正，不是漏刪** · 決策者 **AI 總管** · 依據：**實測**）。
  **仍然成立的半句**：這一頁**只有 NAV 累積狀態可能真的空**，其餘四塊不會 ——
  **(D-2) 的結論一個字都沒有被推翻。**
  **被推翻的是它的判定條件**：舊版把「空」綁在 `portfolio_funds`（`_holdings()`）上，
  而 :func:`services.nav_history_gs.coverage_status` 讀的是**整張雲端 sheet**，
  **與那個 session 鍵毫無關係**。於是一個雲端已經累積三年的人，
  開站第一眼看到的是「這個工作階段還沒載入任何基金…就沒有涵蓋度可看」——
  **那句話的每一個字都對，合起來卻把使用者導向一個錯的結論**（他以為要先去列入基金）。
  **現行**：空狀態**只在「gate 勾了 → 後端已啟用 → 真的讀到、而且一筆都沒有」時出現**；
  `portfolio_funds` **降級為一個標記**（逐檔明細裡標「本 session 已列入」），不再決定任何分支。
  **兩邊理由並陳**：舊條的用意仍然成立（它想避免對一個什麼都沒有的人畫一張空表），
  **被權衡掉的是它挑錯了那個「什麼都沒有」的量**。
  → 守衛：:func:`~tests.test_wf05_settings_skeleton.test_the_empty_state_only_appears_after_a_successful_read`。

⛔ **不得**因為別頁有頁面層級空狀態就照抄一個到 ⑤（實際上也只有 ② 有）。
⚠️ 對照 `page_04_portfolio.py`：④ 的空狀態是**頁面層級**的（沒持倉 ⇒ 四塊全都無意義），
   ⑤ **不是**（沒持倉時，來源健康度與金鑰狀態照樣有話可說）。**兩者不要互相抄。**

(D-3) 線框裡的示意值**一個都不准畫**
------------------------------------
`18 源 · 2 異常`／`42 檔 · 最長 6.2 年`／`正常` **全是線框示範版面用的假數字**。

⚠️ **2026-09-06（P05-1）補一則射程說明，(D-3) 本身未變**：NAV 那一塊現在會印
**真的**「N 檔 · 共 M 筆」。那不是示意值 —— 它有出處
（:func:`services.nav_history_gs.coverage_status` 回傳的逐檔點數），
每一個數字都答得出「從哪個函式來、來源是誰」。
⛔ **但「最長 X 年」永遠不會回來**：不是因為它是線框的假數字，
而是因為 `span_days = last - first` **單獨出現就會說謊**（見 :func:`coverage_line`）。
⚠️ **黑名單的已知代價，就地登記**：`_PINNED_FAKE_VALUES` 收了字面值 `"42 檔"`，
而本頁現在會印真的「N 檔」—— **測試資料剛好是 42 檔時，那條守衛會誤紅**。
黑名單式守衛的既有性質，**登記在此，不是沒看到**。

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

from services.nav_history_gs import (
    coverage_status as fetch_nav_coverage,
    status as fetch_nav_backend_status,
)
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

# ── 區塊 2「NAV 累積狀態」的接線常數（2026-09-06 第一批 P05-1）──────────────
#: 讀雲端 NAV 累積狀態的 **Checkbox Gate**。勾起來才會去讀一次。
#:
#: ⚠️ **為什麼是 gate 而不是 `@st.cache_data`（總管裁決，理由寫在這裡讓後人能推翻）**：
#:    (a) 在 `ui/**` 自建 `@st.cache_data` 會替憲法例外 `EX-UICACHE-1` 新增一個成員，
#:        而那個例外的成立**繫於一個尚未裁決的問題**（`CLAUDE.md §8.3.P` 的
#:        `P-UIGSPREAD-1`：gspread 直呼算不算 EX-CRUD-1 的「本地持久化」）；
#:    (b) `coverage_status()` 內部走 `load_points(None)` —— **一次讀完整張 sheet**，
#:        而 L2 那層**沒有**任何快取，UI 再疊一層就會變成 `P-NDCCACHE-1` 的同型
#:        （兩層 TTL 疊加、失效語意不可推理）。
#:    → gate 同時解掉這兩件事：**沒勾就一次都不讀**，勾了才讀，而且讀的責任留在 L2。
#: ⚠️ **gate 是唯一一個落在 `applied_form(...)` 之外的輸入元件**，
#:    由 `tests/test_wf05_settings_skeleton.py::test_the_write_block_is_form_wrapped`
#:    的**唯讀閘門豁免**明文登記（那條同時證明本函式寫不到任何 session）。
NAV_GATE_LABEL: str = "讀取雲端 NAV 累積狀態"

#: 逐檔明細的展開器標題（線框：「雲端歷史涵蓋度，**逐檔可展開**」）。
#: ⚠️ **刻意是固定字串、不帶檔數** —— 它在 `_units()` 裡是一個**單位名**，
#:    帶了檔數就會隨資料變動，`test_unit_names_are_unique` 之類的斷言會失去錨點。
NAV_DETAIL_LABEL: str = "逐檔明細"

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

#: 後端未啟用時的灰態本文開頭。⚠️ **這不是「沒有資料」，是「我們沒辦法去看」**（§1）。
_BACKEND_UNAVAILABLE_NOTE: str = (
    "讀不到雲端 NAV 歷史 —— 累積功能所需的設定不完整，"
    "所以**這一格不知道你累積了多少**（不是「你沒有累積」）。缺少：")

#: 真的讀到了、但一筆都沒有時的空狀態三要素。
#: ⚠️ 這一則**只在真的讀成功之後**才可能出現（見 :func:`_render_nav_status` 的分流），
#:    所以它可以對「那本試算表」下斷言 —— 它**沒有**對使用者的資產下任何斷言。
_EMPTY_TITLE: str = "雲端 NAV 歷史目前一筆都沒有"
_EMPTY_MISSING: str = (
    "已經讀到雲端了，但 nav_history 裡沒有任何一筆紀錄 —— "
    "可能是還沒開始累積，也可能是那張工作表還沒建立")
_EMPTY_FOOTER: str = "開始累積之後，這裡會逐檔列出點數與首末日期。"


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


def coverage_headline(coverage: dict[str, Any]) -> str:
    """涵蓋度的一句話總結 —— **只講數量，不講跨度**。

    ⛔ **這裡刻意不放「最長 N 年」**（線框的示意值正是「42 檔 · 最長 6.2 年」）。
    理由不是「線框的數字是假的」（那由 D-3 管），而是**跨度單獨出現會說謊**：
    `span_days = last - first`，一檔只有兩個點、相距六年，也會顯示「六年」。
    跨度只在 :func:`coverage_line` 裡出現，而且**永遠與點數同行**。

    ⚠️ 純函式、無 I/O —— 這樣「這句話怎麼算出來的」可以被單獨測，
    不必先跑起一整個 Streamlit session。
    """
    _codes = [_c for _c, _e in coverage.items() if isinstance(_e, dict)]
    _points = 0
    for _e in coverage.values():
        if isinstance(_e, dict):
            try:
                _points += int(_e.get("points") or 0)
            except (TypeError, ValueError):
                # §1：壞值不猜、也不靜默當 0 影響結論 —— 它就是「這一筆算不出來」，
                # 但總數仍要誠實反映其餘可算的部分，故只跳過這一筆。
                continue
    return f"{len(_codes)} 檔 · 共 {_points} {POINTS_UNIT}"


def coverage_line(code: str, entry: dict[str, Any], *, held: bool = False) -> str:
    """一檔的明細行。**全檔唯一被允許讀 `span_days` 的地方。**

    ⛔ **跨度永遠與點數同行，這是本函式存在的唯一理由**（總管裁決，2026-09-06）：
    `span_days` 是 `last - first`，**中間有沒有斷掉它一個字都沒說**。
    單獨印一個「6.2 年」會被讀成「我有六年的完整歷史」，而真相可能是兩個點。
    → 本函式的輸出**恆含**點數（`{N} 筆`），措辭也用 :data:`SPAN_PHRASE`
    （「首末相距」）而不是「跨度」，讓那句話自己說出它只量了頭尾兩點。

    ⚠️ **守衛靠的是「機制」不是「這一行長怎樣」**（`tests/test_wf05_settings_skeleton.py`）：
    (a) AST 驗 `"span_days"` 這個鍵**只在本函式內被讀**；
    (b) 對任意輸入驗「輸出裡只要有 :data:`SPAN_PHRASE`，就一定有點數」。
    改文案不會讓守衛失效，把跨度搬去別的地方單獨印才會 —— **那正是要擋的那件事。**

    Parameters
    ----------
    held : 這一檔是不是**這個 session 已列入**的持倉。
           ⚠️ 只是一個標記；**沒列入不代表使用者沒有它**（`portfolio_funds`
           開站不自動載入），所以沒有標記的那些**不寫任何否定的話**。
    """
    try:
        _points = int(entry.get("points") or 0)
    except (TypeError, ValueError):
        _points = 0
    try:
        _span = int(entry.get("span_days") or 0)
    except (TypeError, ValueError):
        _span = 0
    _first = str(entry.get("first") or "").strip() or "?"
    _last = str(entry.get("last") or "").strip() or "?"
    _mark = " ・本 session 已列入" if held else ""
    return (f"- `{code}`{_mark}：**{_points} {POINTS_UNIT}**"
            f"（{_first} → {_last}，{SPAN_PHRASE} {_span} 天）")


def coverage_lines(coverage: dict[str, Any], held_codes: set[str]) -> list[str]:
    """逐檔明細的全部行，**依代碼排序**（穩定順序，不隨 dict 插入序漂移）。"""
    return [coverage_line(_c, _e, held=_c.upper() in held_codes)
            for _c, _e in sorted(coverage.items())
            if isinstance(_e, dict)]


def held_codes() -> set[str]:
    """這個 session 已列入的基金代碼（大寫）。**只用來加標記，不用來過濾。**

    ⛔ **不得**拿它去縮小 `coverage_status()` 的範圍：雲端累積的是**整張表**，
    用一個「開站不會自動載入」的 session 鍵去過濾，等於把使用者真的有、
    但這個 session 還沒載入的那些**藏起來**（§1：不知道 ≠ 沒有）。
    """
    return {str(_f.get("code", "")).strip().upper()
            for _f in _holdings() if str(_f.get("code", "")).strip()}


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
    """區塊 2｜NAV 累積狀態（`grid3` 第 2 欄）。**2026-09-06 第一批 P05-1 接上真取數。**

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
    `coverage_status()` 在**未啟用**與**工作表不存在**時**都回 `{}`**
    —— 它自己的 docstring 逐字寫著「呼叫端須據此顯示『未啟用』而非『0 點』，
    兩者意義完全不同（§1：不知道 ≠ 沒有）」。
    先分流 `status()["enabled"]`，才有辦法把這兩件事分開講。
    **本組已實測那條路徑**：`load_points()` 開頭
    ``if _sheet is None and not is_enabled() and oauth_client is None: return []``
    → `coverage_status()` 的 ``if not _pts: return {}``。**兩條路真的會匯流成同一個 `{}`。**

    ⛔ **不畫「42 檔 · 最長 6.2 年」** —— 線框示意值（D-3）。
       ⚠️ 現在這一格會印**真的**「N 檔」了；`_PINNED_FAKE_VALUES` 黑名單裡有
       `"42 檔"` 這個字面寫法，也就是說**如果哪天測試用的資料剛好是 42 檔，
       那條守衛會誤紅**。已在測試檔就地登記，不是沒看到。

    ⚠️ **為什麼標題是手寫的 `st.markdown(f"**{…}**")` 而不是 `state_card()`**：
       `state_card(state=STATE_OK)` 走的是 `st.metric(title, value)`，
       而 `st.metric` 在 AppTest 的元素樹裡**不是 `[Markdown] **標題**`** ——
       `tests/test_wf05_settings_skeleton.py::_units` 的 `_CARD_OPEN` 認不出它。
       **後果是：這一塊一旦真的有資料，它就不再是一個「單位」**，
       所有 unit-scoped 的守衛（灰態、結論字表、指路）會**在它終於有內容的那一刻
       靜靜停止覆蓋它**，而且沒有任何測試會紅。
       → 故本塊四種狀態**一律先手寫同一個標題**，讓單位邊界不隨資料變動。
       **這是實測出來的，不是風格選擇**（`_flat()` 對 Metric 走的是 `[Metric] 標籤` 那一支）。

    ⚠️ **gate 的 `st.checkbox` 是全檔唯一落在 form 外的輸入元件** ——
       它是**唯讀閘門**（本函式一個 session 鍵都不寫、一次寫入都沒有），
       與線框那句「寫入類動作，全部 Form 封裝」不衝突。
       守衛的豁免與其**證明**寫在
       `tests/test_wf05_settings_skeleton.py::test_the_write_block_is_form_wrapped`。

    ⚠️ **本塊不自己接 `try/except`**：`coverage_status()` 在來源冷卻期／真 I/O 失敗時
       **會拋 `NavHistoryError`**（那是 L2 刻意的 §1 行為，不是 bug）。
       由 :func:`_render_grid` 幫本塊單獨包一層 `safe_section()` 接住 ——
       **只倒這一張卡，不連坐另外兩張**。自己 `except` 會變成吞例外（§1 違憲）。
    """
    # 標題先畫 —— 四種狀態共用同一個單位邊界（理由見 docstring）。
    st.markdown(f"**{nav_status_label()}**")
    _open = st.checkbox(
        NAV_GATE_LABEL,
        value=False,
        help="讀一次 Google Sheets 的 nav_history；沒勾就完全不連線。",
    )
    if not _open:
        not_ready(_NOT_LOADED_NOTE, where=_pending_where(nav_status_label()))
        return

    # ⛔ 先問「能不能看」，再問「看到什麼」—— 順序顛倒就會把「未啟用」講成「0 點」。
    _backend = fetch_nav_backend_status()
    if not _backend.get("enabled"):
        _missing = ", ".join(str(_m) for _m in (_backend.get("missing") or [])) or "（未回報）"
        not_ready(
            f"{_BACKEND_UNAVAILABLE_NOTE}{_missing}。"
            # ⚠️ **刻意不寫「這兩把」** —— `status()` 的 `missing` 可能只有一項
            #    （`NAV_SHEET_ID` 有 baked 預設 → 多數情況只缺 SA 那一把）。
            #    在一個職責是「資料可不可信」的頁面上，連數量詞都不該猜。
            "這些是部署環境的 secret，畫面上改不了。",
            # ⚠️ **這一則指路是「一個地方」，但它不保證有效** —— 「連線與金鑰」那一塊
            #    本批仍是灰態，去了也不能在畫面上設 secret。
            #    照 `_pending_where` 已登記的分界：**指的是「誰負責這件事」，
            #    不是「按這裡就會好」**；本文那句「畫面上改不了」已經先講清楚了。
            #    ⛔ 不要因此改指別的地方 —— 本頁沒有更接近的地方，
            #    指到手動補資料反而會讓人以為「補一下就好」（補不了，是設定缺）。
            where=_pending_where(BLOCK_KEYS))
        return

    _coverage = fetch_nav_coverage()
    if not _coverage:
        empty_state(_EMPTY_TITLE, _EMPTY_MISSING,
                    where=_pending_where(nav_manual_label()),
                    footer=_EMPTY_FOOTER)
        return

    st.markdown(f"### {coverage_headline(_coverage)}")
    with st.expander(NAV_DETAIL_LABEL, expanded=False):
        st.caption(
            f"「{SPAN_PHRASE}」量的是**第一筆到最後一筆**的日曆天數，"
            "**不代表中間每天都有**；能不能算長期指標看的是點數。")
        for _line in coverage_lines(_coverage, held_codes()):
            st.markdown(_line)


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
            # ⚠️ **只有這一張卡另外包一層 `safe_section()`，這是刻意的**（2026-09-06）：
            #    它是本頁唯一會真的做 I/O 的一塊，而 `coverage_status()` 在
            #    來源冷卻期／真 I/O 失敗時**會拋 `NavHistoryError`**（L2 的 §1 行為）。
            #    外層 `safe_section("狀態三卡", _render_grid)` 接得住，但它會把
            #    **三張卡一起**換成一個紅框 —— 資料來源健康度與連線與金鑰
            #    明明沒壞，卻跟著消失。**把診斷跟故障綁在同一條命上，是最糟的順序**
            #    （`render_state.safe_section` 的 docstring 逐字寫著這句）。
            safe_section(nav_status_label(), _render_nav_status)
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
            # ⚠️ **這一句是必要的，不是客套**（2026-09-05 獨立稽核應修）。
            #    在補上它之前：勾選 → 按鈕 → rerun，**整頁一個字都沒變**，
            #    只有 session 靜靜寫入。而畫面上寫著「按『{SUBMIT_LABEL}』**才算**」，
            #    另外三塊都誠實掛著 ⬜「這一塊的內容還沒接上」，
            #    **唯獨這一塊沒有** —— 而它是唯一一個帶動作動詞、看起來會寫資料的。
            # ⛔ 「不接真寫入」這個取捨本身是對的（一個按了會真的寫的鈕，
            #    接在還沒驗過的骨架上更危險）；**錯的是不說**。
            #    「看起來會寫、其實不寫、而且不說」在一個職責是「資料可不可信」的頁面上，
            #    比多一句話糟得多（§1）。
            #    由 `test_pressing_submit_says_the_backfill_is_not_wired_yet` 釘住。
            not_ready("已記下你的選擇 —— 但**實際補抓功能尚未接上**，"
                      "這次按下去沒有任何資料被寫入或抓取。",
                      where=_pending_where(nav_manual_label()))
        else:
            # ⚠️ **`where=` 不是為了過測試才加的**（`tests/test_batch2_top_card_grid.py::`
            #    `test_where_is_mandatory` 抓到本處漏了它，2026-09-05）——
            #    這一則的指路**真的有效**：使用者要做的就是回到這一塊、勾一個來源再按一次。
            #    ⚠️ 它指的地方**就是使用者現在所在的那一塊**，讀起來有點繞；
            #    但「有效」比「不繞」重要，而且本頁只有這一塊能解決它。
            #    ⛔ **不要**因為繞就改指別的地方 —— 那會變成一句指錯路的話。
            #    ⛔ **也不要**把它加進 `WHERE_MISSING_EXEMPT`：那個豁免是給
            #    「真的無處可指」的，這裡有處可指。
            not_ready("還沒選要補什麼 —— 請至少勾一種來源再按一次。",
                      where=_pending_where(nav_manual_label()))


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
