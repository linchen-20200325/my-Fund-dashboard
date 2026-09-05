"""① 市場總覽 —— 五分頁動線重構的第一頁（全新撰寫，非舊 `tab*.py` 的搬運）。

客戶方針（2026-09-04）第 1 條：UI 渲染層打掉重練，不改舊 `tab*.py`，從零撰寫全新 View。

整頁骨架 —— **客戶 2026-09-04 已拍板，本檔照它排**
--------------------------------------------------
骨架取 `docs/wireframes/wireframe-macro-health.html` 的**四層閱讀順序**，
並把 `ia-wireframe.html` 的**卡片網格插在「① 結論」與「② 依據」之間**：

===== ============================== ==========================================
層     區塊                            版面
===== ============================== ==========================================
1      🧾 ① 結論 — 現在該加碼還是防禦   **全寬**（一句行動 ＋ 理由條列）
–      六張市場卡片                    3 欄自適應網格（`ia` 線框那組）
2      🧾 ② 依據 — 憑什麼這樣說         **全寬表**（五桶證據表）
3      📐 建議資產水位／⚡ ③ 例外／🔍 ④ 可信度   **三欄**
4      🔎 詳細資料與說明（五塊，順序不動）  五塊皆為真內容（2026-09-05 批次三-B）
===== ============================== ==========================================

拍板同時解掉的三件事（**不要再當成待裁決**）
------------------------------------------
- **主要大表 ＝ ② 依據五桶證據表**；「總經燈號全表」**不做**（理由見
  :func:`_render_deferred_blocks`，那是資料層限制，不是版面偏好）。
- **新聞情緒與系統性風險 ＝ 灰態**（客戶已拍板）。本組**沒有找到** `services/**` 的
  新聞取數入口（實測取數住在 `repositories/news_repository.py`），依方針第 2 條
  不反向修底層 → 維持誠實灰態（見 :func:`_card_news`）。
  ⚠️「services 裡沒有」取決於有沒有漏看，本組**不作全稱宣稱**；
  **處置不繫於它** —— 灰態是客戶拍板的結果，不是這句話推出來的。
- **建議資產水位不出核心／衛星**。⚠️ 這一條最容易做錯，展開寫在下面。

🔎 詳細區五塊：**2026-09-05 批次三-B 起全部是真內容**
------------------------------------------------
在此之前只有 📈 中期循環是真的，其餘四塊是灰態佔位。現況與取數來源：

===== ================== ==================================================
塊     取數（**全部走 `services/**`**）  本檔內的渲染函式
===== ================== ==================================================
🌳 長期座標   `us_liquidity_engine.fetch_us_liquidity_snapshot`  :func:`_detail_long`
📈 中期循環   （委派 `ui/tab1_macro_midcycle.py`，見 :func:`_detail_mid`）  :func:`_detail_mid`
🎯 短線雷達   `risk_radar.detect_risk_radar` ＋ `liquidity_engine.*`  :func:`_detail_short`
⚠️ 拐點警報   `ind`（SAHM/SLOOS/ADL）＋ `macro.detect_turning_points`  :func:`_detail_inflection`
🤖 AI 總結    `ai_prompts` ＋ `ai_service`（Gemini）  :func:`_detail_ai`
===== ================== ==================================================

⛔ **四塊一律在本檔內寫完，不新增任何對 `ui/tab1_macro*.py` 的委派。**
   📈 中期循環那一條委派是**既有**的技術債（它自己的 docstring 已登記
   「有效期到舊 tab 整批拔除為止」）；客戶方針第 3 條要在五頁驗收完成後把舊 tab
   **整批拔除**，每多一條委派，那一刻就多一處會斷頭。**本批一條都沒加。**

⛔ **這四塊沒有各自的「載入」按鈕。** 已拍板線框
   `docs/wireframes/fund-wireframe-final.html` 明文把「『載入流動性引擎』這顆按鈕的
   按鈕」列為要拿掉的東西（原文：「主載入鈕按完後，短線雷達裡**還要再按一次**……
   → **併入主載入**」）。四塊的取數因此全部掛在 :func:`_load_everything` 底下。
   唯一的例外是 🤖 AI 總結的「生成」—— 那是**送出一次外部 LLM 請求**、不是取數，
   而且它走 `applied_form()`（鐵則 02），不是裸按鈕。

⚠️ **本批判定「資料給不出來」而走灰態的項目**，逐條寫在各自的渲染函式 docstring：
   💰 資本防線 ／ 🚦 持倉紅綠燈 ／ 📋 逐檔決策矩陣（線框判「搬去 ②」，本頁不畫）、
   📦 ARCHIVED 台股熱錢（線框判「不裁決」，未拍板不進新畫面）、
   拐點的歷史回測與變數重要性（`backtest_turning_points` 是第二次對外取數，
   兩種掛法都與鐵則 02 衝突 → 登記待客戶裁決）。

⛔ 「建議資產水位」為什麼是**股／債／現金**，不是核心／衛星
----------------------------------------------------------
`services.allocation_ladder.allocation_from_composite()` 回的是
`allocation = {equity, bond, cash}` —— **它的回傳欄位就是股／債／現金**。
把 `equity` 改標成「核心」，就是拿 A 欄位的數字冒充 B 的答案（§1 造假）。
**這個理由是可自驗的：打開那個函式看它回什麼欄位就結案，不必相信任何人的清單。**

⚠️ **2026-09-05 撤回一句假宣稱（獨立稽核 A776 指出；commit `541a7ec` 的訊息與本檔
   前一版都帶著它，commit message 無法重寫，故在此撤回）**：
   原文寫「**全 repo 沒有任何由總經分數導出核心／衛星的服務**」—— **那句是假的。**
   本組實測到的反例（每一條都自己重跑過）：
   - `services/macro/composite_score.py::composite_verdict()` —— **唯一輸入就是總經綜合分數**，
     回傳的 `action_text` 逐字寫「衛星部位積極佈局成長題材」「核心持有不動」「核心轉防守型」。
     ⚠️ **本檔的 `_render_layer_evidence()` 正在呼叫它** —— 一邊呼叫、一邊宣稱它不存在。
   - `services/macro/explain.py` —— 同樣那四句。
   - `services/macro/us_indicators.py::identify_regime()` 的 `alloc_by_regime` 是
     **帶數字**的 dict，鍵含「核心債券」「衛星主題」。
   ⛔ **不要把它換成一句更小心的全稱句**（例如「沒有導出核心／衛星**比例**的服務」）——
   那一樣取決於「我有沒有漏看」，而上面第三條就正好站在那條線上。**直接不要全稱句。**
   **拿掉它不影響任何結論**：不改標的理由是上一段那句可自驗的欄位事實，
   全稱句對結論沒有貢獻，只是純負債（§-2 規則 6）。

⚠️ **Z 門檻目前是固定的預設值，畫面必須說出來。**
`allocation_from_composite(score, ndc_score)` 的第二個參數要台灣景氣對策信號分數，
而它**唯一的入口是直呼 L1 的 UI helper**（`ui/helpers/macro/ndc.py`，屬憲法
§8.2.A.1 EX-PASSTHRU-1），**不是 Service 函式** → 依方針第 2 條本頁不接，
一律傳 `None`。服務端收到 `None` 會退回預設門檻並在回傳裡把 `light` 設成 `None`
（`source="default"`）—— 本檔**讀那個旗標**再決定文案，不寫死「預設」兩個字，
這樣日後真的接上景氣燈號時，畫面會自己改口而不是繼續說謊。

四大鐵律的落點（本檔不自己實作任何一條，一律走既有共用元件）
------------------------------------------------------------
- **鐵則 01 三欄網格** → `ui.helpers.ia.render_cards`（內部走 `card_grid`，已登記於
  `tests/test_ui_grid_contract.py::GRID_EXEMPT_SITES`）。**本檔沒有任何 `st.columns` 呼叫**
  —— 自己寫會讓 `GRID_EXEMPT_CALL_TOTAL`（精確 `==` 90）變 91 而轉紅。
- **鐵則 02 Form 防重繪** → `ui.helpers.ia.applied_form`。**本檔沒有任何 `st.form(` 站點**
  —— 自己寫會讓 `FORM_SITE_TOTAL`（精確 `==` 7）變 8 而轉紅。
- **鐵則 03 三態顏色** → `ui.helpers.render_state`（經 `ia.state_card` 的 `state=`）。
- **鐵則 04 空狀態三要素** → `ui.helpers.ia.empty_state`（住在 `ui/helpers/ia/empty_state.py`，
  **不是** `render_state.py`）。

⚠️ **資料一律只走 `services/**` 的 public 函式**（方針第 2 條）。
   **不 import** `repositories/**`、`infra/**`、`requests`、`yfinance`、`gspread`。
   取不到的東西**一律做成灰態並誠實說明**，**不反向要求修改底層**。

⚠️ **`ui/helpers/**` 照用，那不是資料層。** 四大鐵律本身就要求走 `ui/helpers/ia/`、
   `ui/helpers/render_state.py`、`ui/helpers/story_nav.py`。② 依據表同理走既有實作
   `ui/helpers/macro/beginner_view.py`（`compute_five_bucket_summary` /
   `build_evidence_rows` / `render_evidence_table`）—— **不重寫一份**（§2.1 SSOT）。
   ✅ **實測（2026-09-05）**：`beginner_view.py` 的 import 清單裡
   **沒有任何 `repositories` / `infra`**；它往下只碰 `shared/**`、`services/**`、
   `ui/components/**`、`ui/helpers/**`。其 `ui/**` 相依（`ui/components/status.py`、
   `ui/components/tables.py`、`ui/helpers/macro/helpers.py`）同樣 0 命中。

⚠️ **② 依據表的欄位以程式碼的 `EVIDENCE_COLUMNS` 為準，不照線框那張示意表。**
   實測：線框畫 6 欄，實作是 **5 欄**
   （面向／判讀／讀數／說明（這個數字怎麼讀）／詳細在下方哪一段）。
   照線框硬湊第 6 欄＝憑空生一欄沒有來源的資料。

⚠️ **金鑰讀 `os.environ`，不讀 `infra.config`。** `app.py::_load_keys()` 已把
   `FRED_API_KEY` 從 secrets 鏡射進 `os.environ`；舊頁用的也正是
   `os.environ.get("FRED_API_KEY", "")`。讀環境變數是 stdlib，不是資料層呼叫。
   ⚠️ **`FINMIND_TOKEN` 沒有被鏡射**（`_load_keys()` 只鏡射 FRED / GEMINI / ANTHROPIC / OPENAI），
   故本頁只在環境變數真的有值時才帶 token，否則帶空字串走 FinMind 匿名額度
   —— **真實的降級，不是造假**，並在卡片註腳寫明。

⛔ **不復活「總經羅盤」。** `ia-wireframe.html` 的「從哪裡搬來」寫了
   `app.py ─ 總經羅盤（目前內嵌在 app.py）`，但整條鏈已於 **2026-08-05 移除**
   （早於線框日期），且有反向守衛
   `tests/test_audit_20260805_tab1_summary.py::test_compass_modules_are_not_importable_at_all`。
   **線框那一行是錯的，照做會直接讓 CI 紅。** 三個羅盤讀數已併入 🎯 短線雷達。
"""
from __future__ import annotations

import html
import os
from collections.abc import Callable
from functools import partial
from typing import Any

import pandas as pd
import streamlit as st

from services.ai_prompts import build_structured_summary_prompt
from services.ai_service import gemini_generate, get_gemini_keys
from services.allocation_ladder import allocation_from_composite
from services.hot_money_service import fetch_hot_money_frames
from services.liquidity_engine import (
    compute_liquidity_score,
    fetch_liquidity_factors,
    liquidity_verdict,
)
from services.macro import (
    calc_macro_phase,
    detect_turning_points,
    fetch_all_indicators,
    macro_action_light,
)
from services.macro.composite_score import (
    calculate_composite_score,
    composite_verdict,
    is_meta_key,
)
from services.risk_radar import detect_risk_radar, summarize_radar
from services.us_liquidity_engine import fetch_us_liquidity_snapshot
from shared.evidence_support import is_sufficient
from shared.macro_buckets import BUCKET_ORDER
from shared.ui_control_labels import MACRO_LOAD_BTN_AGAIN, MACRO_LOAD_BTN_FIRST
from ui.helpers.ia import (
    STATE_BUSINESS,
    STATE_ERROR,
    STATE_NOT_READY,
    STATE_OK,
    applied_form,
    render_cards,
    wide_table,
)
from ui.helpers.ia.empty_state import empty_state
from ui.helpers.macro.beginner_view import (
    build_evidence_footnotes,
    build_evidence_rows,
    compute_five_bucket_summary,
    render_evidence_table,
    split_evidence_footnotes,
)
from ui.helpers.render_state import (
    business_alert,
    not_ready,
    safe_section,
    system_error,
)
from ui.helpers.story_nav import render_story_nav, tab_label, where_to_find

# ── session 鍵名（本檔自己的命名空間）────────────────────────────────────────
# ⚠️ 刻意**不**沿用 `ui/tab1_macro.py` 的鍵：舊頁依方針第 3 條仍在磁碟上，
#    共用鍵會讓兩套 View 互相覆寫對方的載入結果，而 payload 形狀並不相同。
#    本批**不**把它們收進 `shared/session_keys.py` —— 那個 L0 模組的存在理由是
#    「L0 / L2 的刷新入口也要清這些鍵」（見該檔 docstring），本頁沒有那個需求；
#    等真的需要跨層作廢時再上移，不預先造一個沒人用的抽象（§8.1 step 6）。
_SK_IND: str = "v01_macro_indicators"
_SK_ERR: str = "v01_macro_load_error"
_SK_HOT: str = "v01_macro_hot_money"
#: 🎯 短線雷達的**原始 10 燈**（`detect_risk_radar` 的回傳，未彙總）。
#: ⚠️ **2026-09-05 起存的是原始 dict，不再是 `summarize_radar()` 的摘要。**
#:    理由：層 1 的「極端風險警語」卡只要摘要，但層 4 的 🎯 短線雷達要逐燈列出。
#:    存摘要 → 詳細區只能**再抓一次**，同一份資料就會有兩個取數點（§2.1）。
#:    現在存原始、由各消費端各自呼叫 `summarize_radar()` 彙總（那是純函式，無 I/O）。
_SK_RADAR: str = "v01_macro_risk_radar"
_FORM_KEY: str = "v01_macro_load_form"

# ── 層 4「🔎 詳細資料與說明」四塊各自的取數結果 ─────────────────────────
# ⚠️ **一塊一個鍵，刻意不合併成一個大 dict**：合併之後任一塊的取數失敗會讓
#    整包變成 Exception，四塊一起變紅 —— 而它們的上游其實互不相干
#    （FRED 流動性 / FRED+Yahoo 雷達 / FRED 拐點）。分開存，一塊壞不連坐。
#: 🌳 長期座標：`fetch_us_liquidity_snapshot` 的 7 個子指標。
_SK_USLIQ: str = "v01_macro_us_liquidity"
#: 🎯 短線雷達 ⑤：`(factors, score)` —— 深水區 4 因子與其加權合成分數。
_SK_LIQ: str = "v01_macro_liquidity_stress"
#: ⚠️ 拐點警報 ②：`detect_turning_points` 的 5 組月級結構訊號。
_SK_TP: str = "v01_macro_turning_points"
#: 層 1／層 2 算好的 `calc_macro_phase()` 結果，供 🤖 AI 總結**複用而不重算**。
#: ⚠️ 重算會讓同一個位階分數有兩個計算點（見 `render_market_overview()` 的同一則警語）。
_SK_PHASE: str = "v01_macro_phase"
#: 層 2 `_render_layer_evidence()` 的回傳，供 🤖 AI 總結複用（同上，不重算）。
_SK_EV: str = "v01_macro_evidence"
#: 🤖 AI 總結的載入閘門 key 與生成結果快取 key。
_AI_FORM_KEY: str = "v01_macro_ai_form"
_SK_AI: str = "v01_macro_ai_text"

#: 🤖 AI 總結送出鈕的兩種字。
#:
#: ⚠️ **2026-09-05 稽核 F5：具名之前，這兩個字串在本檔出現三次** ——
#: `applied_form(submit_label=…)` 的條件式兩個，加上灰態指路裡**手抄的第三個**
#: （`where=f"… → 上方「▶️ 生成 AI 總結」"`）。那正是本檔別處反覆寫著
#: 「**不手抄**」要防的形狀，而它就長在同一份 diff 裡。
#: 現在 `_detail_ai()` 先把這一輪要用的字**算成一個變數**，再同時交給送出鈕與指路
#: —— **兩邊因此不可能分岔**，做法與本檔既有的 `_SK_BTN` / `_where_to_load()` 完全一致。
#: ⚠️ **代價要講清楚**：跨檔規則
#: `tests/test_batch2_top_card_grid.py::test_every_where_names_something_that_exists_on_screen`
#: 是**以 `「」` 內的字面值 opt-in** 的；改成變數之後它**看不到這一站了**。
#: 那不是把覆蓋面弄丟 —— 漂移在這裡已經**結構上不可能**，沒有東西可以驗；
#: 但為了不讓它變成一個沒人看的角落，本檔另有一條**更強**的守衛盯著這個配對：
#: `tests/test_wf01_detail_zone_order.py::test_the_ai_remedy_names_the_button_that_is_actually_rendered`
#: （它比對的是**執行期真的印出來的**送出鈕字，不是原始碼裡的字面值）。
_AI_BTN_FIRST: str = "▶️ 生成 AI 總結"
_AI_BTN_AGAIN: str = "🔄 重新生成 AI 總結"
#: 這一輪**實際交給送出鈕的那個字**。指路文案一律讀它，不自己再判一次載入狀態。
#: ⚠️ 存的是「畫面上印了什麼」，不是「資料載入了沒」—— 兩者在**剛按下按鈕的那一輪
#: 並不一致**（見 `_where_to_load()` 的說明），而使用者看的是前者。
_SK_BTN: str = "v01_macro_submit_label"

#: 熱錢／匯率序列的回看天數。
#: ⚠️ **刻意用具名常數而不是畫面上的控制項**：兩份線框的 Form 欄位集互相衝突
#: （`ia` 有「觀察區間」下拉、`macro-health` 沒有、改成四個資料類別勾選框），
#: 欄位集**待客戶裁決**。在那之前把天數固定成一個具名值，
#: 功能照跑、但**不預先把任一份線框的欄位畫進畫面**。
_HOT_MONEY_WINDOW_DAYS: int = 180


def _where_to_load() -> str:
    """「去哪補」：指到本頁載入閘門裡的那顆送出鈕。

    **一律回「畫面上這一輪實際印出來的那個字」** —— 讀 :data:`_SK_BTN`，
    那是 :func:`render_market_overview` 交給 `applied_form(submit_label=...)`
    的**同一個變數**，所以指路的字與按鈕的字**不可能分岔**。

    ⚠️ **2026-09-05 修正：本函式原本寫死 `MACRO_LOAD_BTN_FIRST`，那是錯的。**
    舊 docstring 的理由是「灰態卡只在未載入時出現，故指名 FIRST」——
    **那句話是假的**。全檔 17 個 `where=_where_to_load()` 站點裡，只有 4 個
    （`render_market_overview` 的未載入早退區塊）在 FIRST 狀態渲染；
    其餘 13 個住在六張卡片建構器、三欄卡片建構器與 `_render_deferred_blocks`，
    **只在載入之後才被呼叫**，而那時按鈕已經變成 `MACRO_LOAD_BTN_AGAIN`。
    `_render_deferred_blocks` 每次成功載入都會渲染 → **不是邊角情形，是必中**。

    AppTest 實測（修正前）：載入後畫面上的按鈕是「🔄 更新總經資料」，
    而灰態說明寫「請先到：… → 「📡 載入總經資料」」—— 指一顆當下不存在的按鈕。

    ⚠️ **為什麼不在這裡重判一次載入狀態**（例如 `isinstance(...get(_SK_IND), dict)`）：
    在**使用者剛按下送出鈕的那一輪**，兩者會分岔 —— 表單是用「按之前」的狀態決定
    標籤（印 FIRST），但 `_load_everything()` 隨後就把 `_SK_IND` 寫進去了，
    此時重判會得到 AGAIN，於是又指錯一次，只是方向相反。
    **存下實際用過的那個字，是唯一不會分岔的做法。**

    ⚠️ 分頁名走 `where_to_find()`、按鈕名走 SSOT 常數（經 `_SK_BTN` 轉手）：
    兩者都不手抄，故本字串不可能因為改名而漂成死指路。
    ⚠️ 預設值 `MACRO_LOAD_BTN_FIRST` 只在「表單都還沒渲染就有人呼叫本函式」時生效
    —— 現行流程不會發生（所有呼叫點都在表單之後），留著是為了不回傳空字串。
    """
    _label = st.session_state.get(_SK_BTN) or MACRO_LOAD_BTN_FIRST
    return f"{where_to_find('macro')} → 「{_label}」"


# ══════════════════════════════════════════════════════════════════
# 取數（全部在載入閘門之後才跑）
# ══════════════════════════════════════════════════════════════════
def _load_everything(fred_key: str) -> None:
    """按下送出鈕之後才呼叫。結果與失敗都寫進 session，供後續 rerun 重用。

    §1 Fail Loud：**不吞例外**。主指標的例外**往上拋**給唯一的呼叫點去印；
    副來源（雷達 / 熱錢）的例外原樣存進 session，由各自的卡片渲染成紅框。
    **一個失敗只准有一個紅框** —— 這是本函式不自己印任何東西的唯一理由。
    """
    # ⚠️ **主指標的例外刻意不在這裡捕捉** —— 讓它往上拋給唯一的呼叫點。
    #    在這裡再 catch 一次會變成「同一個失敗印兩個紅框」：一個在這裡、
    #    一個在下面 `render_market_overview()` 從 session 重讀時。
    #    **一個失敗只准有一個紅框**，否則使用者找不到真正的那一個。
    st.session_state[_SK_IND] = fetch_all_indicators(fred_key)
    st.session_state[_SK_ERR] = None

    # ── 風險雷達（同一把 FRED 金鑰，額外一次取數）──────────────────────
    # ⚠️ 存**原始 10 燈**，不是摘要 —— 見 `_SK_RADAR` 的說明。
    try:
        st.session_state[_SK_RADAR] = detect_risk_radar(fred_key)
    except Exception as _exc_radar:                 # noqa: BLE001 — 見下方 ⚠️
        # ⚠️ **這不是靜默吞（§1）**：例外物件原樣存進 session，由
        #    `_card_risk_radar()` 走 `state_card(state=STATE_ERROR, exc=...)` 渲染
        #    —— 那條路徑最終呼叫的就是 `render_state.system_error()`（紅框 + 技術細節）。
        #    **在這裡不印**，是為了不要「handler 印一個、卡片再印一個」變成兩個紅框。
        #    副來源失敗只讓**它自己那一張卡**變紅，其餘卡片照常（分頁不連坐）。
        st.session_state[_SK_RADAR] = _exc_radar

    # ── 熱錢（FinMind 外資 ＋ Yahoo USDTWD）────────────────────────────
    # `fetch_hot_money_frames` 走 L1 的「內拋外譯」：失敗回錯誤字串而不是拋例外，
    # 故這裡收到的是 `(flow_df, fx_df, flow_err, fx_err)`，四元組原樣存起來。
    _token = os.environ.get("FINMIND_TOKEN", "")
    try:
        st.session_state[_SK_HOT] = fetch_hot_money_frames(
            _HOT_MONEY_WINDOW_DAYS, _token)
    except Exception as _exc_hm:                    # noqa: BLE001 — 同上，見 `_SK_RADAR` 的 ⚠️
        # 例外原樣存進 session，由 `_card_hot_money()` 渲染成唯一那個紅框。
        st.session_state[_SK_HOT] = _exc_hm

    # ══════════════════════════════════════════════════════════════
    # 層 4「🔎 詳細資料與說明」四塊的取數 —— **一律掛在這一顆送出鈕底下**
    # ══════════════════════════════════════════════════════════════
    # ⚠️ **為什麼不各給一顆「載入」鈕**：已拍板線框
    #    `docs/wireframes/fund-wireframe-final.html` 明文把
    #    「『載入流動性引擎』這顆按鈕的按鈕」列為**要拿掉的東西** ——
    #    原文：「主載入鈕按完後，短線雷達裡**還要再按一次**才看得到流動性引擎，
    #    之後又有第三顆重抓鈕……→ **併入主載入**」。本檔照它做。
    # ⚠️ 三塊各自 try：它們的上游互不相干，一塊失敗不得讓另外兩塊也變紅。
    #    例外**原樣存進 session**（不是靜默吞，§1）—— 由各自的區塊渲染成紅框。

    # 🌳 長期座標：美股流動性 × 信用 × 情緒（7 個子指標，服務層自己並行）
    try:
        st.session_state[_SK_USLIQ] = fetch_us_liquidity_snapshot(fred_key)
    except Exception as _exc_usliq:                 # noqa: BLE001 — 同上
        st.session_state[_SK_USLIQ] = _exc_usliq

    # 🎯 短線雷達 ⑤：深水區流動性壓力（4 因子 → 加權合成分數）
    # ⚠️ `compute_liquidity_score` 是**純函式**（吃上一行的輸出），
    #    放在同一個 try 裡是因為它的輸入來自同一次取數 —— 不是額外的 I/O。
    try:
        _liq_factors = fetch_liquidity_factors(fred_key)
        st.session_state[_SK_LIQ] = (
            _liq_factors, compute_liquidity_score(_liq_factors))
    except Exception as _exc_liq:                   # noqa: BLE001 — 同上
        st.session_state[_SK_LIQ] = _exc_liq

    # ⚠️ 拐點警報 ②：拐點偵測中心（5 組月級結構訊號）
    try:
        st.session_state[_SK_TP] = detect_turning_points(fred_key)
    except Exception as _exc_tp:                    # noqa: BLE001 — 同上
        st.session_state[_SK_TP] = _exc_tp


# ══════════════════════════════════════════════════════════════════
# 指標讀取小工具
# ══════════════════════════════════════════════════════════════════
def _ind_signal(ind: dict, key: str) -> str:
    _d = ind.get(key)
    return str(_d.get("signal") or "") if isinstance(_d, dict) else ""


def _fmt(ind: dict, key: str, digits: int = 1) -> str:
    """`值 + 單位` 的顯示字串；缺值回 `—`。

    ⚠️ `fetch_all_indicators` 的契約是「**抓到才寫 key**」，所以 key 不存在
       代表那一項這一輪真的沒拿到 —— **不得**用 0 或上一輪的值頂替（§1）。
    """
    _d = ind.get(key)
    if not isinstance(_d, dict) or _d.get("value") is None:
        return "—"
    _v: Any = _d.get("value")
    _unit = str(_d.get("unit") or "")
    if isinstance(_v, (int, float)):
        return f"{_v:.{digits}f}{_unit}"
    return f"{_v}{_unit}"


def _worst_state(ind: dict, keys: tuple[str, ...]) -> str:
    """一組指標裡最差的燈 → 卡片狀態。

    ⚠️ **紅燈映射到「業務警示」而不是「系統紅框」**：VIX 衝上 30 是**市場**壞消息，
       資料本身完全可信 —— 那是莓紅左軌（業務色），不是紅框（系統真出錯）。
       把它畫成紅框會稀釋真紅燈的份量（鐵則 03）。
    ⚠️ 一項都沒抓到 → 灰態（不是綠燈）。**沒有資料不等於一切正常。**
    """
    _signals = [_ind_signal(ind, _k) for _k in keys]
    if not any(_s for _s in _signals):
        return STATE_NOT_READY
    return STATE_BUSINESS if "🔴" in _signals else STATE_OK


def _radar_lit(summary: dict) -> int:
    """10 燈裡**真的有讀數**的盞數（🔴 ＋ 🟡 ＋ 🟢；⬜ 不算）。

    ⛔ **這個函式存在的唯一理由，是讓「全 ⬜ 不得說平靜」只有一個定義。**

    `services.risk_radar.summarize_radar()` 的分級**只看 `red` / `yellow` 兩個計數**：
    10 燈全部抓不到時 `{red:0, yellow:0, green:0, gray:10}` → 它照樣回
    `level="平靜"`、`color` 是綠的（本組 2026-09-05 在無網路環境實跑確認）。
    照搬那個結果就是把「什麼都沒抓到」講成「市場很平靜」——
    也就是本檔 `_worst_state()` 已經寫過的那句：**沒有資料不等於一切正常**（§1）。
    服務層**不改**（客戶方針第 2 條：不反向修底層），一律在**消費端**擋。

    ⚠️ **2026-09-05 稽核 F1：本函式是被一次真實漏網逼出來的，不是一開始就有的。**
    前一版把那道防線**各自 inline 寫在消費端**，於是第三個消費端
    （`_ai_snapshot()`，把摘要寫進交給 LLM 的 prompt）**整個漏掉** ——
    而它比畫面更嚴重：prompt 開頭寫著「**只能根據下面的資料快照來講**」，
    等於直接告訴模型「市場平靜」。當時的守衛只側錄 `st.*` 渲染 API，
    **prompt 字串不經過任何 `st.*`**，所以一條都不會紅。
    → 現在三個消費端**共用這一支**，並由
    `tests/test_wf01_detail_zone_order.py::test_every_summarize_radar_consumer_goes_through_the_lit_guard`
    以 AST 鎖住「`summarize_radar()` 有幾個呼叫點，`_radar_lit()` 就要有幾個」。

    ⚠️ **這句話原本寫太滿，2026-09-05 稽核 R1 就地更正（有意識的更正，不是漏刪）**：
    ~~**第四個消費端漏掉這道防線會直接轉紅**，不必再靠下一個人記得。~~
    那條鎖**初版按裸名字計數**，`from … import summarize_radar as _sr2` 的別名寫法
    **整個隱形**（稽核實跑：`3 / 3`、`225 passed` 零紅燈，而「平靜」照樣進 prompt）。
    別名解析已於同輪修好（復用 `tests/test_batch2_top_card_grid.py::_call_name`）。

    ⚠️ **下面刻意寫成「已知擋得住／已知擋不住」，不是能力清單** ——
    **清單讀起來像窮舉**，而這正是本註解已經錯過兩次的形狀
    （2026-09-05 第三輪稽核：上一版寫成「擋得住 A、B；擋不住 C、D」，
    它當場又打穿兩種沒列到的）。**非窮舉，請照這樣讀。**

    **已知擋得住（各實測過一次突變）**
      - `summarize_radar(...)` 直接呼叫漏配對；
      - `from services.risk_radar import summarize_radar as _sr2` 的 **import 別名**。

    **已知擋不住（四種，皆 2026-09-05 實測 `21 passed` 零紅燈；非窮舉）**
      - **本地變數別名**：`_sum_fn = summarize_radar` 之後 `_sum_fn(_r4)`
        —— AST 看到的呼叫名是 `_sum_fn`，`_import_alias()` 只解析 import 別名；
      - **動態取名**：`getattr(_rr, "summarize_radar")(_r4)`；
      - **配對了但沒用回傳值**（那一半由兩條行為鎖守，不由本鎖守）；
      - **跨檔**：本鎖只讀 `ui/views/page_01_macro.py` 一個檔，
        第四個消費端若寫在別的檔，它看不到。

    ⛔ **所以它是「少一道人為疏漏」，不是「不可能再漏」。**
    """
    return (int(summary.get("red") or 0) + int(summary.get("yellow") or 0)
            + int(summary.get("green") or 0))


# ══════════════════════════════════════════════════════════════════
# 卡片
# ══════════════════════════════════════════════════════════════════
def _card_phase(ind: dict) -> dict:
    _phase = calc_macro_phase(ind)
    return {
        "title": "景氣位階",
        "value": f"{_phase.get('phase') or '—'}（{_phase.get('score')}/10）",
        # ⚠️ `ia` 線框把本卡描述成「NDC 燈號 ＋ PMI ＋ 殖利率差合成」，但
        #    `calc_macro_phase` 實際的組成是**美國總經 12 項加權，不含 NDC**。
        #    NDC 目前唯一的入口是 `ui/helpers/macro/ndc.py`（直呼 L1，屬憲法
        #    §8.2.A.1 EX-PASSTHRU-1），不是 Service 函式 → 依方針第 2 條本頁不接。
        #    **此處照實寫真正的組成，不照抄線框那句話** —— 標錯出處就是造假（§2.2）。
        "note": "殖利率曲線 ＋ PMI ＋ 信用利差 ＋ 流動性等 12 項加權（美國總經；未含台灣 NDC）。",
        "state": STATE_OK if _phase.get("phase") else STATE_NOT_READY,
        "where": _where_to_load(),
    }


def _card_vol_credit(ind: dict) -> dict:
    return {
        "title": "波動與信用",
        "value": f"VIX {_fmt(ind, 'VIX')}",
        "note": f"HY 信用利差 {_fmt(ind, 'HY_SPREAD')}；兩者同看，單看 VIX 會漏掉信用面。",
        "state": _worst_state(ind, ("VIX", "HY_SPREAD")),
        "where": _where_to_load(),
    }


def _card_infl_rate(ind: dict) -> dict:
    return {
        "title": "通膨與利率",
        "value": f"CPI {_fmt(ind, 'CPI')}",
        "note": (f"聯邦基金利率 {_fmt(ind, 'FED_RATE', 2)}；"
                 f"10Y-2Y 利差 {_fmt(ind, 'YIELD_10Y2Y', 2)}。"),
        "state": _worst_state(ind, ("CPI", "FED_RATE", "YIELD_10Y2Y")),
        "where": _where_to_load(),
    }


def _card_hot_money() -> dict:
    _stash = st.session_state.get(_SK_HOT)
    if isinstance(_stash, BaseException):
        return {"title": "熱錢動向", "state": STATE_ERROR, "exc": _stash,
                "note": "外資 / 匯率序列這一輪沒取到。"}
    if not isinstance(_stash, tuple) or len(_stash) != 4:
        return {"title": "熱錢動向", "state": STATE_NOT_READY,
                "note": "尚未載入外資買賣超與匯率序列。", "where": _where_to_load()}

    _flow_df, _fx_df, _flow_err, _fx_err = _stash
    if _flow_err or _fx_err:
        # L1 的「內拋外譯」把例外翻成字串再回傳，這裡把它**原文**裝回一個例外物件
        # 交給系統紅框 —— 訊息一個字都沒有改寫，不是新編的錯誤（§1）。
        return {"title": "熱錢動向", "state": STATE_ERROR,
                "exc": RuntimeError(str(_flow_err or _fx_err)),
                "note": "外資或匯率其中一路取數失敗。"}

    _flow_sum = None
    if isinstance(_flow_df, pd.DataFrame) and not _flow_df.empty:
        _num = _flow_df.select_dtypes("number")
        if not _num.empty:
            _flow_sum = float(_num.iloc[:, 0].sum())
    if _flow_sum is None:
        return {"title": "熱錢動向", "state": STATE_NOT_READY,
                "note": "外資序列回來是空的，這一輪沒有可用的買賣超數字。",
                "where": _where_to_load()}

    _fx_last = None
    if isinstance(_fx_df, pd.DataFrame) and not _fx_df.empty:
        _fxn = _fx_df.select_dtypes("number")
        if not _fxn.empty:
            _fx_last = float(_fxn.iloc[-1, 0])
    _fx_txt = f"USDTWD {_fx_last:.3f}" if _fx_last is not None else "USDTWD —"
    # ⚠️ **2026-09-04 回修（有意識的更正，不是漏刪 · 決策者：回修組 WF01-F）**
    #
    # 舊表述：`"value": f"外資 {_flow_sum:+,.0f}"`（**頭條數字不帶單位**）
    #         ＋ note 括號寫「沿用來源單位，**不代為換算成「億」**」。
    #
    # **為什麼非改不可**：畫面會印出「外資 +340」，讀者無從分辨那是 340 億還是 340 元
    # —— `CLAUDE.md §4.1` 點名的「元 vs 百萬元 vs 億」單位陷阱，也是 §1
    # 「錯誤的數字比沒有數字更危險」。**同一個教訓舊 ① 自己就寫過**：
    # `ui/tab1_macro.py::_render_top_card_grid` 該卡就地註明「**頭條數字不標單位期間 ＝
    # 另一種誤導**」，並印 `f"外資 {_hm_net:+.0f}億"`。
    #
    # **舊 note 的括號在讀者視角是假的 —— 換算早就發生了，只是不在本檔**（實測）：
    #     repositories/hot_money_repository.py::_fetch_foreign_flow_series_uncached
    #         .assign(foreign_net_yi=lambda d: d["net"] / 1e8)      ← 元 → 億元
    #     同檔 fetch_foreign_flow_series docstring
    #         Returns: (df[date, foreign_net_yi 億元], error_msg or "")
    # 也就是說 `_flow_sum` 加總的那一欄（df 唯一的數值欄）**單位就是億元**。
    # ⚠️ **公平地說，舊句有一種讀法是真的**：從「**本函式**做了什麼」看，本檔確實
    #    沒有再換算一次。但**兩種讀法下缺陷都成立** —— 值本身連單位都沒有，
    #    而那句括號只會讓讀者以為「這個數字不是億」。故改為**陳述來源單位**。
    #
    # 「億」與數字之間留一個空格，是照客戶已拍板的線框逐字寫法：
    # `docs/wireframes/ia-wireframe.html` 該格為 `<span class="big">外資 +182 億</span>`。
    #
    # ⚠️ **`note` 刻意只寫「單位為億元新臺幣」，不把 L1 的函式名／欄名寫進畫面**：
    #    `note` 經 `ia.state_card` 走 `st.caption(note)` → **會被當 markdown 算繪**，
    #    反引號會變成 code span。**實測（AST 數，2026-09-04）：本檔 13 個 `note` 值裡
    #    含反引號的是 0 個** —— 全部是使用者語言、沒有任何內部符號名；
    #    線框那格的註腳也只有「近 5 日累計；USDTWD 同軸對照。」。
    #    **出處留在這段註解裡就夠了，不必端到使用者面前。**
    return {
        "title": "熱錢動向",
        "value": f"外資 {_flow_sum:+,.0f} 億",
        "note": f"近 {_HOT_MONEY_WINDOW_DAYS} 天累計，單位為億元新臺幣；{_fx_txt}。",
        "state": STATE_OK,
    }


def _card_risk_radar() -> dict:
    _stash = st.session_state.get(_SK_RADAR)
    if isinstance(_stash, BaseException):
        return {"title": "極端風險警語", "state": STATE_ERROR, "exc": _stash,
                "note": "10 燈短線風險雷達這一輪沒算出來。"}
    if not isinstance(_stash, dict):
        return {"title": "極端風險警語", "state": STATE_NOT_READY,
                "note": "尚未計算短線風險雷達。", "where": _where_to_load()}
    # ⚠️ **2026-09-05：本卡改吃原始 10 燈，摘要在這裡當場算。**
    #    `summarize_radar()` 是純函式（無 I/O），所以「一份資料兩個消費端」
    #    只是同一份 dict 被彙總兩次，不是第二個取數點。
    _sum = summarize_radar(_stash)
    # ⛔ **§1 的必要防線，理由與唯一定義都在 `_radar_lit()`。**（消費端 1／3）
    if not _radar_lit(_sum):
        return {
            "title": "極端風險警語",
            "state": STATE_NOT_READY,
            "note": "10 燈這一輪一盞都沒有取到讀數，沒有可以下的風險結論。",
            "where": _where_to_load(),
        }
    _level = str(_sum.get("level") or "")
    return {
        "title": "極端風險警語",
        "value": _level or "—",
        "note": (f"🔴 {_sum.get('red', 0)} ／ 🟡 {_sum.get('yellow', 0)} ／ "
                 f"🟢 {_sum.get('green', 0)} ／ ⬜ {_sum.get('gray', 0)}（共 10 燈）。"),
        "state": STATE_BUSINESS if _level and _level != "平靜" else STATE_OK,
    }


def _card_news() -> dict:
    """新聞情緒 —— **本批為灰態，且不是因為抓取失敗**。

    情緒判讀那一半在 Service 層
    （`services/macro/us_indicators.py::detect_systemic_risk(news_items)`），
    但**餵給它的新聞從哪來沒有 Service 入口**：全 repo 唯一的取數是
    `repositories/news_repository.fetch_market_news`，舊頁是經由根目錄的相容 shim
    `fund_fetcher.py`（`from repositories.news_repository import fetch_market_news`）拿到的。
    依方針第 2 條「絕不反向要求修改底層」，本頁**不新增 Service wrapper**，
    照實做成灰態，交由客戶決定要不要為它開一個例外。
    """
    return {
        "title": "新聞情緒",
        "note": ("本頁尚未接上新聞取數：情緒判讀本身在 Service 層，"
                 "但新聞來源目前只有資料層入口，本批不反向改底層。"),
        "state": STATE_NOT_READY,
        # 使用者現在真的能做的事：到 ⑤ 看那 5 條 RSS 來源還活著沒有。
        "where": where_to_find("diag"),
    }


# ══════════════════════════════════════════════════════════════════
# 層 1：🧾 ① 結論（全寬）
# ══════════════════════════════════════════════════════════════════
def _render_layer_conclusion(ind: dict, phase: dict) -> None:
    """🧾 ① 結論 —— 全頁最上面唯一的結論，**全寬、不進三欄**（線框逐字要求）。

    走 Service 的 `macro_action_light()`；它除了燈號本身，還回一個
    `support`（這盞燈**撐不撐得住**）。本檔**只讀 `is_sufficient()`**
    —— 那是全站唯一被允許的判斷式（`shared/evidence_support.py` 的 L0 SSOT，
    docstring 明令消費端不得自己去看 `obtained` / `missing` 的長度再下判斷）。

    ⚠️ **撐不住時不印燈、只印原因。** 完全斷線時 `macro_action_light` 仍會回一盞
    🟡「資料不足」，但它附帶的理由句會點名幾個**根本沒抓到**的輸入 ——
    照印就是拿空氣當證據（§1）。`support.reason` 是產出端寫給使用者看的中文，
    直接印它，不在本層另編一句。

    ⚠️ **理由逐條 `html.escape`**：`business_alert()` 走 `unsafe_allow_html`，
    服務層字串若含 `<` / `>` 會被當標籤吃掉（同 `ui/tab1_macro.py` 的 ② 對帳 chip
    與 `tab1_macro_midcycle._card_note` 的既有處置）。
    """
    st.markdown("### 🧾 ① 結論 — 現在該加碼還是防禦")
    _light = macro_action_light(ind, phase.get("score"))
    _support = _light.get("support")
    if not is_sufficient(_support):
        # 灰，不是紅 —— 這不是故障，是「這一輪的證據撐不起一句結論」。
        not_ready(
            "這一輪的資料撐不起一個結論："
            f"{getattr(_support, 'reason', '') or '證據不足'}",
            where=_where_to_load())
        return

    _reasons = [str(_r) for _r in (_light.get("reasons") or [])]
    if _light.get("light") == "🔴":
        # 莓紅左軌：市場是壞消息，但**資料完全可信** —— 不是系統紅框（鐵則 03）。
        # ⚠️ **只有這一條路徑要 `html.escape`**：`business_alert()` 走
        #    `unsafe_allow_html`，服務層字串若含 `<` / `>` 會被當標籤吃掉
        #    （同 `ui/tab1_macro.py` ② 對帳 chip、`tab1_macro_midcycle._card_note`）。
        business_alert(f"{_light['light']} {_light.get('action', '')}",
                       [html.escape(_r) for _r in _reasons])
        return
    st.markdown(f"**{_light.get('light', '')} {_light.get('action', '')}**")
    for _r in _reasons:
        # ⚠️ **這裡刻意不 escape**：`st.caption()` 走 markdown，Streamlit 自己會把
        #    HTML 擋掉。先 escape 再交給它 ＝ 雙重跳脫，`<` 會原樣印成 `&lt;`。
        st.caption(f"・{_r}")


# ══════════════════════════════════════════════════════════════════
# 層 2：🧾 ② 依據（全寬表）
# ══════════════════════════════════════════════════════════════════
def _render_layer_evidence(ind: dict, phase: dict) -> dict:
    """🧾 ② 依據 —— 五桶證據表，**全寬**（多欄位表塞進三欄會被壓成兩個字）。

    **不重寫一份表**：`compute_five_bucket_summary` / `build_evidence_rows` /
    `build_evidence_footnotes` / `split_evidence_footnotes` / `render_evidence_table`
    都是 `ui/helpers/macro/beginner_view.py` 既有且正在被舊頁使用的實作（§2.1 SSOT）。
    欄位以該檔的 `EVIDENCE_COLUMNS`（5 欄）為準，**不照線框那張 6 欄示意表**。

    ⚠️ **`news_items` 一律傳 `None`（客戶 2026-09-04 拍板第 2 條）**：
    本組沒有找到 `services/**` 的新聞取數入口，本頁不反向修底層（**不作全稱宣稱**；
    灰態是客戶拍板的結果）。`None` 是
    `compute_five_bucket_summary` 明文支援的輸入 —— 它會把新聞桶標成
    ⬜「未掃描」，**而不是綠燈**。傳 `[]`（空清單）會被讀成「掃過了、0 則系統性風險」，
    那才是造假。

    ⚠️ **綜合健康度那一列的 §1 陷阱，本函式擋在這裡。**
    `calculate_composite_score` 的 docstring 自陳「缺值 / NaN / 型別錯誤
    **一律以 0 處理（`fillna(0)` 等價）**」→ 完全斷線時總分是 `0.0`，
    而 `composite_verdict(0.0)` 會回「🟡 中性」**外加一句可以照做的投資建議**。
    那是 `fillna(0)` 直接長成一個行動指示。故：撐不住時**分數照印**
    （它是真的加總，不是捏造的），但**不給等級、不給行動**，並把原因寫進表下註記。

    Returns
    -------
    dict : `{"summary", "score", "prov", "sufficient", "level"}`，供層 3 三欄複用
           —— **層 3 不重算**，否則同一個數字會有第二個真相源。
    """
    st.markdown("### 🧾 ② 依據 — 憑什麼這樣說")
    _prov: dict = {}
    _score = calculate_composite_score(ind, provenance_out=_prov)
    _icon, _level, _color, _action = composite_verdict(_score)
    _ok = is_sufficient(_prov.get("support"))
    if not _ok:
        # 分數留著（真的加總過），等級與行動清空 —— 見上方 ⚠️。
        _icon, _level, _action = "⬜", "", ""

    _5b = compute_five_bucket_summary(ind, phase, news_items=None)
    _rows = build_evidence_rows(
        _5b,
        composite_score=_score,
        composite_icon=_icon,
        composite_level=_level,
        composite_action=_action,
        n_indicators=int(_prov.get("n_indicators") or 0),
    )
    _notes = list(build_evidence_footnotes(_5b, composite_action=_action))
    if not _ok:
        _reason = getattr(_prov.get("support"), "reason", "")
        _notes.append(
            "⬜ 綜合健康度這一列只印分數、不給等級與行動："
            f"{_reason or '這一輪取到的指標撐不起一個等級判定'}。")
    # 兩份的聯集逐則等於 `build_evidence_footnotes()`；分類只決定印在哪一層。
    _, _collapse = split_evidence_footnotes(_5b, composite_action=_action)
    render_evidence_table(_rows, footnotes=_notes, collapsed_footnotes=_collapse)
    return {"summary": _5b, "score": _score, "prov": _prov,
            "sufficient": _ok, "level": _level}


# ══════════════════════════════════════════════════════════════════
# 層 3：📐 建議資產水位 ／ ⚡ ③ 例外 ／ 🔍 ④ 可信度（三欄）
# ══════════════════════════════════════════════════════════════════
def _card_allocation(ev: dict) -> dict:
    """📐 建議資產水位 —— **股／債／現金**，不是核心／衛星（理由見模組 docstring）。

    ⚠️ **`ndc_score` 一律傳 `None`**：台灣景氣對策信號分數唯一的入口是直呼 L1 的
    UI helper，不是 Service 函式（模組 docstring 已展開）。服務端收到 `None` 會
    退回預設 Z 門檻，並把回傳的 `light` 設成 `None`。

    ⚠️ **文案讀 `light` 旗標，不寫死「預設」兩個字**：日後真的接上景氣燈號時，
    這張卡會自己改口；寫死的話它會繼續說「沒有跟著景氣變動」而那時已是假話。
    """
    if not ev.get("sufficient"):
        # 總分撐不住 → **不給水位**。給了就是拿 `fillna(0)` 的 0.0 分去配資產。
        return {
            "title": "📐 建議資產水位",
            "state": STATE_NOT_READY,
            "note": "這一輪取到的總經指標還撐不起一個總分，先不給配置建議。",
            "where": _where_to_load(),
        }
    _al = allocation_from_composite(ev.get("score"), None)
    if _al.get("status") != "ok":
        return {
            "title": "📐 建議資產水位",
            "state": STATE_NOT_READY,
            "note": str(_al.get("reason") or "這一輪算不出配置水位。"),
            "where": _where_to_load(),
        }
    _a = _al["allocation"]
    # ⚠️ 「股票 / 債券 / 現金」是**資產類別**。刻意逐字寫出這三個字，
    #    不用「核心 / 衛星」那組詞 —— 它們是不同的分類軸（模組 docstring）。
    # ⚠️ **「Z」對使用者是黑話，必須就地解釋，而且要說清楚它量的是哪一個數字。**
    #    實測出處 `shared/signal_thresholds.py`「模組②:Z-Score 位階窗」：
    #    `ZSCORE_WINDOW_DAYS = 756`（3 年交易日）、`ZSCORE_MIN_OBS = 252  # 有效 NAV 點` ——
    #    也就是 Z 量的是**單一基金的淨值**離它自己近三年平均有多遠（以標準差為單位），
    #    **不是**總經分數的 Z。免責句本身合格不代表被免責的那兩個數字可以是黑話。
    _gate = (f"停利 Z ≥ {_al['stop_gain_z']:+.2f}、加碼 Z ≤ {_al['add_z']:+.2f}"
             "（Z 是「一檔基金現在的淨值，離它自己近三年的平均有多遠」，"
             "0 就是剛好在平均、正的偏貴、負的偏便宜）")
    _gate_src = (f"這兩個門檻已依台灣景氣{_al['light']}燈調整。"
                 if _al.get("light")
                 else "這兩個門檻是固定的預設值，不會跟著台灣景氣燈號變動。")
    return {
        "title": "📐 建議資產水位",
        "value": (f"股票 {_a['equity']}％ ・債券 {_a['bond']}％ "
                  f"・現金 {_a['cash']}％"),
        "note": ("錢該放在哪一類資產的建議（不是「核心／衛星」那種角色分配）。"
                 f"{_gate}；{_gate_src}"),
        "state": STATE_OK,
    }


def _card_exceptions(ev: dict) -> dict:
    """⚡ ③ 例外 —— 只講「該警覺的」；沒有例外時誠實說沒有，不硬擠內容（§1）。

    讀的是層 2 已經算好的五桶 summary（拐點桶 ＋ 新聞桶）與已在 session 裡的
    風險雷達 —— **零新取數**，也不重算任何一個數字。
    """
    _sm = ev.get("summary") or {}
    _infl = _sm.get("inflection") or {}
    _news = _sm.get("news") or {}
    if not _infl:
        return {"title": "⚡ ③ 例外", "state": STATE_NOT_READY,
                "note": "五桶證據還沒算出來，這裡先不下判斷。",
                "where": _where_to_load()}

    _radar = st.session_state.get(_SK_RADAR)
    _red = int(_radar.get("red", 0)) if isinstance(_radar, dict) else 0
    _yellow = int(_radar.get("yellow", 0)) if isinstance(_radar, dict) else 0
    _lvl = str(_infl.get("level", ""))
    _alarm = _lvl == "red" or _red > 0
    # 新聞桶恆為 ⬜「未掃描」（客戶拍板第 2 條）—— 把它**說出來**，
    # 否則「沒有系統性風險」與「沒有掃描系統性風險」在畫面上長得一模一樣。
    _note = (f"短線雷達 🔴 {_red} ／ 🟡 {_yellow}。"
             f"系統性風險（新聞面）{_news.get('emoji', '⬜')} "
             f"{_news.get('label', '未掃描')} —— 本頁尚未接上新聞取數，"
             "所以這一項不是「沒有風險」，是「沒有查」。")
    if _alarm:
        # 有已知的例外 —— 莓紅左軌（業務警示），不是系統紅框（鐵則 03）。
        _state = STATE_BUSINESS
    elif _lvl == "gray":
        # ⚠️ **拐點沒取到 ⇒ 灰態，不是綠燈。** 「沒有資料」不等於「一切正常」——
        #    這一條與 `_worst_state()` 的同名規則同源；把 ⬜「資料未取得」畫成
        #    STATE_OK（綠色 metric），使用者會讀成「今天沒有該警覺的事」，
        #    而實際上我們根本沒查（§1）。
        _state = STATE_NOT_READY
    else:
        _state = STATE_OK
    _card: dict = {
        "title": "⚡ ③ 例外",
        "value": f"拐點 {_infl.get('emoji', '⬜')} {_infl.get('label', '—')}",
        "note": _note,
        "state": _state,
    }
    if _state == STATE_NOT_READY:
        # 灰態的空狀態三要素：`state_card` 的灰分支不印 value，故把讀數併進 note。
        _card["note"] = f"拐點 {_infl.get('emoji', '⬜')} {_infl.get('label', '—')}。{_note}"
        _card["where"] = _where_to_load()
    return _card


def _card_credibility(ind: dict, ev: dict) -> dict:
    """🔍 ④ 可信度 —— 這一輪的數字**能信到什麼程度**。

    ⚠️ 這張卡刻意報「**有幾項附得出來源**」：實測（2026-09-05，AST 數
    `fetch_all_indicators` 內各 `dict(...)` 呼叫的具名引數）——
    帶 `source=` 的只有 **1 個**（PMI），帶 `fetched_at=` 的 **0 個**。
    ⚠️ **這裡刻意不寫「共幾項指標」的總數**：AST 實測 `R` 有 27 個下標賦值、
    其中 26 個是字面 key，而那 26 個裡還混著一個 `_fred_sources`（meta，不是指標），
    另有非字面 key 的動態賦值 —— **它沒有一個乾淨的單一總數**，
    寫死一個會過期也會失真（§8.2.A.0 規則 4：會漂移的量測值不寫死）。
    本卡的分母改由執行期實際數（已用 `is_meta_key()` 濾掉 meta）。
    血緣在 L1 是有寫的（`repositories/macro/fred.py` 會寫 `source` / `fetched_at`），
    **但 L2 沒有把它接下來**。這正是「總經燈號全表」做不出「來源」欄的原因
    （見 :func:`_render_deferred_blocks`）—— 同一個限制，在這裡誠實講一次。
    """
    _prov = ev.get("prov") or {}
    # ⚠️ **`_` 開頭的 key 不是指標**（例如 `_fred_sources`）—— 走 Service 自己的
    #    `is_meta_key()`，不在本層重寫一份判斷（§2.1）。少了這一道，分母會被
    #    meta 條目灌水，而那正是產出端 v19.425 修過的同一個坑。
    _real = {_k: _v for _k, _v in (ind or {}).items()
             if isinstance(_v, dict) and not is_meta_key(_k)}
    _total = len(_real)
    _proxy = len([_k for _k, _v in _real.items() if _v.get("is_proxy")])
    _srcs = len(_prov.get("sources") or [])
    if not _total:
        return {"title": "🔍 ④ 可信度", "state": STATE_NOT_READY,
                "note": "這一輪一項指標都沒取到。", "where": _where_to_load()}
    _note = [f"其中 {_srcs} 項附得出資料來源，其餘沒有。"]
    if _proxy:
        _note.append(f"另有 {_proxy} 項是用替代來源估出來的，不是原始指標。")
    if not ev.get("sufficient"):
        _note.append("證據不足，上方沒有給等級與行動。")
    # ⚠️ **刻意不印「N / M 項參與計算」那種比例。** 實測 `n_indicators` 的遞增條件
    #    是「非 meta 的 dict 條目且 score/weight 可解析」—— 缺 score 會被當 0 一起算，
    #    所以它幾乎恆等於分母，比例永遠是 N/N。印出來會讓使用者以為「全部都取到了」，
    #    而真相恰恰相反（缺的那些是被當 0 加進去的）。那個真相由 ② 表下的
    #    `support.reason` 負責講，這裡只報一個不會說謊的數字。
    return {
        "title": "🔍 ④ 可信度",
        "value": f"{_total} 項指標",
        "note": "".join(_note),
        # 附不出來源、或證據撐不住 → 這是「這個數字要打折看」的**業務警示**，
        # 不是系統故障（資料本身抓回來了）。鐵則 03。
        "state": (STATE_BUSINESS
                  if (not ev.get("sufficient") or _proxy) else STATE_OK),
    }


# ══════════════════════════════════════════════════════════════════
# 層 4：🔎 詳細資料與說明（五塊，順序不動）
# ══════════════════════════════════════════════════════════════════
# ⚠️ **2026-09-05 就地更正（有意識的更正，不是漏刪 · 決策者：AI 總管）——
#    本區塊前一版寫「6 塊」，那也是錯的。**
#
#    ~~「🔎 詳細區 — 四時域 ＋ 決策矩陣 ＋ AI」，**6 塊**：🌳 長期座標／📈 中期循環／
#    🎯 短線雷達／⚠️ 拐點警報／**📋 即時訊號 ＋ 決策矩陣**／🤖 AI 景氣判斷總結~~
#
#    **舊表述在寫下當天，逐字抄對了它引用的那一段** —— 它確實照著
#    `docs/wireframes/wireframe-macro-health.html` 寫，字也沒抄錯。
#    **被推翻的是它的前提：抄錯了「哪一段」。** 那句「6 塊」住在
#    **section 01「現況盤點 — 兩頁目前實際渲染了什麼」**，也就是
#    **「現在長什麼樣」**；**拍板的目標版面在 section 03「重組後版面」**。
#    拿現況當目標，等於把這次重構要搬走的東西照著搬回來。
#
#    **本組實測（可自驗，指令與輸出如下）**：
#      `git show origin/main:docs/wireframes/wireframe-macro-health.html | grep -n 'sec-num'`
#        → 01=364、02=508、**03=633**、04=901、05=933
#      同檔 `grep -n '詳細區'` → **只有一處，line 403** ⇒ 403 落在 [364, 508) ＝ **section 01**。
#
#    **section 03 的 ①（＝目標）**：
#      「🔎 詳細資料與說明」〈保留 · **順序不動**〉：
#      🌳 長期座標 ▸ 📈 中期循環 ▸ 🎯 短線雷達 ▸ ⚠️ 拐點警報 ▸ 🤖 AI 景氣判斷總結
#    緊接著三項標「**→ 移去 ②**」：💰 資本防線／🚦 持倉紅綠燈／📋 逐檔決策矩陣，
#    且 verdict 大卡標「**刪除**」（DUP-5）。**section 04「搬移對照表」三列獨立佐證**，
#    去處都是「② 行動摘要」；同表另有一列寫「四時域詳細 ＋ 🤖 AI 景氣總結 → 留 · ① 原位」。
#
#    ⛔ **所以「📋 即時訊號 ＋ 決策矩陣」不屬於本頁的詳細區** —— 它要搬去 ②。
#    前一版把它列進來，會讓批次三照著把一塊**已拍板要搬走的東西**重寫回 ①。
#
# 📌 **前一版那則「五時域是假標籤」的更正註記，其結論仍然成立，不撤回**
#    （「時域是 4 個不是 5 個，第 5 個 render 函式是 AI 總結」——本更正未推翻它）；
#    它只是**在修掉一個錯的同時，從錯的那一段抄了另一個數字**。兩則更正併讀。
#
# ⚠️ **標題文字不是本組發明的**：五個標題與**舊頁各子模組實際渲染的 `## ` 標題逐字相同**
#    （`ui/tab1_macro_longterm.py` 🌳 長期座標／`ui/tab1_macro_midcycle.py` 📈 中期循環／
#     `ui/tab1_macro_radar.py` 🎯 短線雷達／`ui/tab1_macro_inflection.py` ⚠️ 拐點警報／
#     `ui/tab1_macro_ai.py` 🤖 AI 景氣判斷總結），且與線框 section 03 逐字相同。
#    **線框與現行實作在這五個名字上一致，本組沒有在兩者之間做取捨。**

#: 詳細區的區塊標題（**不是**分頁名，故不走 `story_nav`；那支管的是分頁與分區導覽）。
#: 對映 key → 標題。四時域的 key 直接是 `BUCKET_ORDER` 的桶名，AI 總結另給哨兵 key。
_DETAIL_AI_KEY: str = "ai"

#: 四時域的 key —— **從 `shared.macro_buckets.BUCKET_ORDER` 推導，不手抄第二份順序。**
#: ⚠️ 用「濾掉新聞桶」而不是 `BUCKET_ORDER[:4]`：後者在有人於中間插一個新桶時
#: ~~會**靜默**把 `inflection` 擠掉~~，而濾法只會讓新桶出現（看得見，會被守衛擋下）。
#: → **2026-09-05 A779-b 就地更正（有意識的更正，不是漏刪）**：**「靜默」二字不成立。**
#:
#:   ⚠️ **本更正自己也被實測修正過一次，兩個數字都照實留著**：
#:   本更正的**第一版**寫「把上式改成 `BUCKET_ORDER[:4]` → 結構鎖 **2 failed**」——
#:   **那個數字是編的，實跑是 `10 passed`。** 原因很簡單、也是本註解真正該講的事：
#:   **今天 `news` 就排在第 5 位，所以 `[:4]` 與「濾掉 news」的結果一模一樣**
#:   （實測：`BUCKET_ORDER[:4] == [k for k in BUCKET_ORDER if k != "news"]` → `True`）。
#:   兩者今天**沒有任何差別**，換過去當然不會有守衛響。
#:
#:   **兩者的差別只在「有人於中間插一個新桶」時才會現形**，實測（在測試行程內
#:   把 `BUCKET_ORDER` 換成 `[long, mid, short, credit, inflection, news]` 模擬，
#:   **未改動 `shared/`**）：
#:     - **濾法（現行）** → `2 failed`：新桶 `credit` **出現在畫面上**，
#:       守衛說「多了一塊沒登記的」，人會回去看線框。
#:     - **切片 `[:4]`** → `4 failed`：`inflection` 被擠掉，
#:       **⚠️ 拐點警報從畫面消失**，壞的東西比較多。
#:   → **兩種都會響**，所以「靜默」在任何一邊都不成立；
#:     **濾法仍然較好**（失效模式是「多一塊看得見的」而不是「少一塊該在的」），
#:     **選擇沒有被推翻，被推翻的是那個形容詞與那個編出來的數字。**
#:
#: ⚠️ **這一筆的教訓比它本身重要，兩層都要記**：
#:   (1) 同一句「靜默」我在 PR 描述裡撤回過、**卻沒有在這裡撤** ——
#:       PR 描述是會被關掉、後人不會回頭讀的地方；**程式碼註解才是後人一定會讀的地方**。
#:       撤回只做在前者 ＝ 沒有撤。
#:   (2) 而我**在修這一筆的時候，又把一個沒跑過的數字寫進了註解**。
#:       **這正是本 PR 自己在修的那一類病，在修它的那一次改動裡又犯了一遍。**
#:       規則：**註解裡的每一個數字，送出前都要真的跑一次**；跑不了就不要寫數字。
#: 📰 新聞桶不在詳細區：線框 section 03 的五塊沒有它，它在本頁是上方的「新聞情緒」卡。
_DETAIL_HORIZON_KEYS: tuple[str, ...] = tuple(
    _k for _k in BUCKET_ORDER if _k != "news"
)

_DETAIL_TITLES: dict[str, str] = {
    "long":            "🌳 長期座標",
    "mid":             "📈 中期循環",
    "short":           "🎯 短線雷達",
    "inflection":      "⚠️ 拐點警報",
    _DETAIL_AI_KEY:    "🤖 AI 景氣判斷總結",
}

_DETAIL_HEADING: str = "🔎 詳細資料與說明"


def _detail_pending(title: str) -> None:
    """尚未搬遷的詳細區塊：畫出**標題**，內容誠實留灰（鐵則 04 三要素）。

    ⚠️ **為什麼標題用 `st.markdown("#### …")` 而不是 `empty_state()` 的標題**：
    這五塊是**頁面的一級區塊**，標題必須與同層的真區塊看齊（📈 中期循環由
    `ui/tab1_macro_midcycle.py` 自己印 `## `）；`empty_state()` 的標題是刻意壓小的
    inline 灰字，用在這裡會讓四塊看起來像「中期循環的子項」。
    **三要素一項不少**：標題（本行）＋ 缺什麼＋去哪補（下一行的 `not_ready()`）——
    而 `not_ready()` 正是 `empty_state()` 內部委派的**同一支 SSOT**，
    所以這裡**沒有**另起一套灰態（`ui/helpers/ia/empty_state.py` 的模組 docstring 禁的是那件事）。

    ⚠️ **兩種灰的理由不同，文案必須分開**：`ind` 還沒載入 → 「你還沒按載入」；
    已載入 → 「這一塊還沒搬過來」。混成一句會讓使用者以為按了載入就會出現。
    """
    st.markdown(f"#### {title}")
    if isinstance(st.session_state.get(_SK_IND), dict):
        not_ready(
            "這一塊還沒從舊版總經頁搬過來（UI 打掉重練的其餘批次處理）",
            # 區塊名吃 `_DETAIL_TITLES`，不手抄 —— 手抄的指路在本 repo 已死過三次
            # （`ui/helpers/story_nav.py` 的 `RETIRED_TAB_LABELS`）。
            where=(f"{where_to_find('macro')} → "
                   f"目前只有「{_DETAIL_TITLES['mid']}」是完整的"),
        )
    else:
        not_ready("尚未載入總經資料。", where=_where_to_load())


def _detail_mid() -> None:
    """📈 中期循環 —— 本批**唯一**真的搬過來的一塊。

    直接委派 `ui/tab1_macro_midcycle.py::render_mid_cycle_section(ind)`，
    **本檔不重寫一份**（§2.1 SSOT）。它自己會印 `## 📈 中期循環` 標題，
    所以這裡**刻意不印標題** —— 印了會變兩個。

    ⚠️ **它為什麼是第一塊被搬的（本組逐條實測，2026-09-05）**：
    `ui/tab1_macro_midcycle.py` 不寫 `st.session_state`（`grep -c` 得 1，但那一處是
    **檔頭 docstring 裡的一句話**「純渲染 + ind 讀取(不寫 session_state)」，不是程式）、module-level import 只有
    `shared/**` ＋ `ui/components/**` ＋ streamlit（**零** `repositories` / `infra` /
    `requests` / `yfinance` / `gspread` / `urlopen`）、`st.form(` `st.error(`
    `st.warning(` `st.button(` **各 0 處**、`st.columns(` 只有一處 `(5)` 且已登記於
    `tests/test_ui_grid_contract.py::GRID_EXEMPT_SITES`。
    它只吃 `ind`，而 `ind` 就是本頁 `_load_everything()` 放進 session 的那一份
    （同一支 `services.macro.fetch_all_indicators`）。

    ⛔ **技術債（本批刻意不還，登記在此）**：`render_mid_cycle_section` 內部
    lazy import 了兩個**舊頁的私有符號** ——
    `ui.tab1_macro._render_macro_indicator_card` 與 `ui.tab1_macro._zs_danger_spec_key`。
    也就是說 **① 頁的新 View 目前仍在執行期相依 `ui/tab1_macro.py`**，
    而客戶方針第 3 條要在五頁驗收完成後把舊 tab **整批拔除** ——
    **這條相依會擋住那一步，必須另批處理。**
    **本批不搬它們的理由（實測，不是推測）**：`_render_macro_indicator_card` 同時被
    `ui/tab1_macro_longterm.py`（🌳 長期座標）與本模組使用，
    `_zs_danger_spec_key` 另有多個 `tests/**` 以 `patch.object(tab1_macro, …)` 綁在
    `ui.tab1_macro` 這個模組物件上。現在搬＝在還不知道另外三塊要什麼的情況下搬第一次，
    之後很可能再搬第二次，並且會同時動到一批測試的 patch 目標。
    → **等 🌳 長期座標 那一塊也搬過來時，兩個消費者到齊，一次搬完。**

    ⛔ **2026-09-05 追記：客戶架構方針讓這筆債的性質變了（不是新增理由，是加上死線）。**
    客戶 2026-09-05 頒布：(1) UI 層禁止在舊 tab 檔上修補，一律開新檔重寫；
    (2) **新 UI 只呼叫既有 Service 函式**，欄位缺失／取數異常一律落實灰態三要素、
    **絕不反向要求修改底層**；(3) **舊版 tab 檔暫留作參考，待新版 5 頁驗收完成後整批拔除**。
      - **死線（方針 3）**：這條相依**必須在「舊 tab 整批拔除」之前拆完**，
        否則那一刻 ① 頁**會直接壞掉**（lazy import 找不到模組）。
        它因此**不是**「早晚要還」，而是「**在一個已知時點前必須還完**」。
      - **定性（方針 2）**：`render_mid_cycle_section` 住在 `ui/tab1_macro_midcycle.py`，
        **那是 UI renderer，不是 Service** —— 所以這條委派**本來就不符合方針 2 的形狀**。
        它是一個**有效期到「整批拔除」為止的過渡**，不是可以長期存在的設計。
    ⚠️ **上面「本批不搬的理由」一字未刪，因為它仍然成立** —— 那是**當時**不搬的正確理由
    （兩個消費者未到齊、會動到一批測試的 patch 目標）。
    **被權衡掉的只是它隱含的那個前提：「可以無限期留著」。** 兩邊理由並陳。
    ⚠️ 這是**登記**，不是動工授權（§-1）；**本輪刻意不拆**，拆它會動到 `ui/tab*.py`，
    正是方針 1 明禁的「在舊檔上修補」。**X5 只把記錄改成不說謊。**
    """
    _ind = st.session_state.get(_SK_IND)
    if not isinstance(_ind, dict):
        # 沒有 ind 就沒有東西可畫 —— 標題照印（骨架不消失），內容誠實留灰。
        _detail_pending(_DETAIL_TITLES["mid"])
        return
    from ui.tab1_macro_midcycle import render_mid_cycle_section  # noqa: PLC0415
    render_mid_cycle_section(_ind)


# ══════════════════════════════════════════════════════════════════
# 詳細區共用小工具（四塊都在本檔內自己畫，**不 delegate 回 `ui/tab1_macro*.py`**）
# ══════════════════════════════════════════════════════════════════
# ⛔ **為什麼四塊不比照 📈 中期循環走委派**：`_detail_mid()` 的 docstring 已登記
#    那條委派是「**有效期到舊 tab 整批拔除為止的過渡**」，而且它還把
#    `ui/tab1_macro.py` 的兩個私有符號拖成執行期相依。客戶方針第 3 條要在五頁
#    驗收完成後把舊 tab **整批拔除** —— 每多一條委派，那一刻就多一處會斷頭。
#    本批四塊因此**一律在本檔內寫完**，一條新的委派都不加。


def _detail_title(title: str) -> None:
    """印一塊詳細區的一級標題。

    ⚠️ **`####`（H4）是刻意的，而且是唯一允許的一級開頭。**
    `tests/test_wf01_detail_zone_order.py` 的行為鎖把 H2~H4 一律認成「一級區塊」，
    並要求詳細區的一級序列**恰好**是「區頭 ＋ 五塊」。所以：
      - 塊**標題**用 `####`；
      - 塊**內部**的分節一律用 `#####`（H5）—— 守衛刻意不收 H5，
        正是為了讓一塊裡面可以有自己的子標題而不破壞「連續」。
    改成 `st.subheader()` / `###` 會讓那條鎖轉紅，那是**對的**：
    它在告訴你「你多畫了一個與那五塊平起平坐的區塊」。
    """
    st.markdown(f"#### {title}")


def _detail_not_loaded(title: str) -> bool:
    """四塊共用的最前置檢查：總經指標還沒載入 → 標題照印、內容誠實留灰。

    Returns
    -------
    bool : `True` 代表已經印過灰態，呼叫端應該直接 `return`。

    ⚠️ **骨架照畫、內容留灰**（鐵則 04）：整塊消失會讓「還沒載入」與「這頁壞了」
    長得一模一樣 —— 這與 `render_market_overview()` 未載入分支的處置一致。
    """
    if isinstance(st.session_state.get(_SK_IND), dict):
        return False
    _detail_title(title)
    not_ready("尚未載入總經資料。", where=_where_to_load())
    return True


def _entry_card(title: str, entry: Any, *, note_prefix: str = "",
                value_digits: int = 2) -> dict:
    """把「服務層的一個子指標 dict」翻成一張卡片規格。

    本 repo 的服務層對「這一項這次沒拿到」有一個**共同慣例**：回一個帶 `_err`
    的 dict（`us_liquidity_engine` / `liquidity_engine` 都是），成功時帶
    `value` / `unit` / `label` / `date` / `source`。本函式只做那個翻譯。

    三態對映（鐵則 03）：
      - `_err`          → **系統紅框**。上游取數失敗＝「這個數字不可信」。
                          錯誤字串**原文**裝進 `RuntimeError`，一個字沒改寫（§1）——
                          與 `_card_hot_money()` 對 L1「內拋外譯」的處理同一套做法。
      - `value is None` → **灰態**。抓回來了但這一項是空的，不是故障。
      - `label` 以 🔴 開頭 → **業務警示（莓紅）**。信用利差衝高是市場壞消息，
                          資料本身完全可信 —— 那不是紅框（同 `_worst_state()` 的理由）。
      - 其餘            → 正常。
    """
    if not isinstance(entry, dict):
        return {"title": title, "state": STATE_NOT_READY,
                "note": f"{note_prefix}這一輪沒有回傳這個指標。",
                "where": _where_to_load()}
    _err = entry.get("_err")
    if _err:
        return {"title": title, "state": STATE_ERROR,
                "exc": RuntimeError(str(_err)),
                "note": f"{note_prefix}上游取數失敗，這個數字這一輪不可信。"}
    _val = entry.get("value")
    if _val is None:
        return {"title": title, "state": STATE_NOT_READY,
                "note": f"{note_prefix}來源回來了，但這一項是空的。",
                "where": _where_to_load()}
    _unit = str(entry.get("unit") or "")
    _txt = (f"{_val:,.{value_digits}f}{_unit}"
            if isinstance(_val, (int, float)) else f"{_val}{_unit}")
    _label = str(entry.get("label") or "")
    _date = str(entry.get("date") or "")
    _note = note_prefix + _label + (f"　資料日 {_date}" if _date else "")
    return {"title": title, "value": _txt, "note": _note.strip() or "—",
            "state": STATE_BUSINESS if _label.startswith("🔴") else STATE_OK}


def _err_of(entry: Any) -> str:
    """子指標 dict 的 `_err` 字串；沒有就回空字串。"""
    return str(entry.get("_err") or "") if isinstance(entry, dict) else ""


# ══════════════════════════════════════════════════════════════════
# 🌳 長期座標
# ══════════════════════════════════════════════════════════════════
#: 7 個子指標的**顯示名與分組**。
#:
#: ⚠️ **為什麼這份對照表寫在本檔**：服務層 `us_liquidity_engine` 的子 dict
#: **沒有「指標名」這個欄位** —— 它的 `label` 是**判讀句**（「🔴 信用緊縮 / 熱錢撤離」），
#: 不是名字。也就是說服務層根本沒有一份可以引用的顯示名 SSOT，
#: 這裡不是抄第二份，是**唯一一份**。
#: ⚠️ **順序即畫面順序**，並照線框 section 01 對本塊的描述分成
#: 「流動性 × 信用 × 情緒」三組（`docs/wireframes/wireframe-macro-health.html`：
#: 「💵 美股流動性 × 熱錢 — 流動性 M2/WALCL/RRP × 信用 HY OAS/HYG-LQD × 情緒 AAII」）。
#: ⚠️ **服務層新增子指標時不會被靜默丟掉**：`_detail_long()` 會把本表沒列到的 key
#: 用原始 key 當標題補在最後（見該處），所以漏登記的後果是「畫面上多一張名字很醜的卡」
#: 而不是「一項指標無聲消失」。
_US_LIQ_ROWS: tuple[tuple[str, str, str], ...] = (
    ("m2_yoy",  "M2 年增率",        "流動性"),
    ("walcl",   "Fed 資產負債表",   "流動性"),
    ("rrp",     "隔夜逆回購 RRP",   "流動性"),
    ("net_liq", "淨流動性",         "流動性"),
    ("hy_oas",  "HY 信用利差 OAS",  "信用"),
    ("hyg_lqd", "HYG ÷ LQD",        "信用"),
    ("aaii",    "AAII 散戶情緒",    "情緒"),
)


def _detail_long() -> None:
    """🌳 長期座標 —— 美股流動性 × 信用 × 情緒（`services.us_liquidity_engine`）。

    **線框依據**：`docs/wireframes/wireframe-macro-health.html`
    section 03「重組後版面」把本塊列為〈保留 · 順序不動〉的第一塊；
    section 04「搬移對照表」把 **💰 資本防線（含息 vs 配息）搬去 ②**
    （理由逐字：「逐檔吃本金，不是市場位階」），所以**本塊不畫任何一檔基金**
    —— 這也正是 `ia-wireframe.html` Tab 01「這裡不放什麼」的第一條。

    **📦 ARCHIVED 台股熱錢本塊不畫**：線框 section 04 對它的處置逐字是
    「**不裁決**」（「看起來像廢棄，但『還有沒有人用』取決於有沒有漏看，
    本組未做 caller 實測，不提刪除」）。**沒有拍板的東西不進新畫面** ——
    把一個未裁決的區塊重寫進來，等於用實作替客戶做了那個決定。
    """
    if _detail_not_loaded(_DETAIL_TITLES["long"]):
        return
    _detail_title(_DETAIL_TITLES["long"])

    _snap = st.session_state.get(_SK_USLIQ)
    if isinstance(_snap, BaseException):
        system_error("美股流動性 × 信用 × 情緒這一輪沒算出來", _snap,
                     hint="本塊的 7 個子指標全部來自同一次取數，故只印一個紅框。")
        return
    if not isinstance(_snap, dict):
        not_ready("尚未取得美股流動性、信用與情緒指標。", where=_where_to_load())
        return

    # 服務層自己塞的 meta，不是指標（同 `_card_credibility` 濾 `_fred_sources` 的理由）。
    _entries = {_k: _v for _k, _v in _snap.items() if _k != "_provenance"}
    # 本表沒列到的 key 用原始 key 當標題補在最後 —— **寧可醜，不可無聲消失**。
    _known = {_k for _k, _t, _g in _US_LIQ_ROWS}
    _extra = tuple((_k, _k, "未登記") for _k in _entries if _k not in _known)

    # ⛔ **全滅時只印一個紅框，不是 7 個。** 7 個子指標同一把 FRED 金鑰、同一條網路，
    #    全滅幾乎必然是**同一個根因**；印 7 個紅框會讓使用者找不到真正的那一個
    #    （同本檔 `_load_everything()` 那句「一個失敗只准有一個紅框」）。
    #    **部分失敗則逐項紅** —— 那時候它們真的是不同的問題。
    _errs = [_err_of(_entries.get(_k)) for _k, _t, _g in (*_US_LIQ_ROWS, *_extra)]
    if _entries and all(_errs):
        system_error(
            "美股流動性 × 信用 × 情緒：7 個子指標全部取數失敗",
            RuntimeError("；".join(_e for _e in _errs if _e)),
            hint="全部失敗通常是同一個根因（FRED 金鑰或對外連線），"
                 "故只印一個紅框而不是逐項印。")
        return

    st.markdown("##### 💵 美股流動性 × 熱錢 — 流動性 × 信用 × 情緒")
    # 鐵則 01：3 欄自適應網格（7 張卡 → 3 列）。
    render_cards([
        _entry_card(_t, _entries.get(_k), note_prefix=f"{_g}｜")
        for _k, _t, _g in (*_US_LIQ_ROWS, *_extra)
    ])

    # ── 線框 section 01 對本塊點名的「Raw data expander」──────────────
    # ⚠️ 原始讀數表**帶來源與資料日**：這一頁其餘地方拿不出血緣
    #    （見 `_card_credibility`：`fetch_all_indicators` 只有 1 項帶 `source`），
    #    而 `us_liquidity_engine` 的每個子指標**都帶** `source` —— 有就要印出來（§2.2）。
    with st.expander("📋 原始讀數與來源", expanded=False):
        _rows = []
        for _k, _t, _g in (*_US_LIQ_ROWS, *_extra):
            _e = _entries.get(_k)
            if not isinstance(_e, dict):
                continue
            _rows.append({
                "分組": _g,
                "指標": _t,
                "讀數": ("—" if _e.get("value") is None
                         else f"{_e.get('value')}{_e.get('unit') or ''}"),
                "判讀": str(_e.get("label") or _e.get("_err") or "—"),
                "資料日": str(_e.get("date") or "—"),
                "來源": str(_e.get("source") or "—"),
            })
        wide_table(
            pd.DataFrame(_rows) if _rows else None,
            empty_title="這一輪沒有任何子指標可以列出來源",
            empty_missing="7 個子指標都沒有回傳可用的 dict。",
            empty_where=_where_to_load(),
            hide_index=True,
        )


# ══════════════════════════════════════════════════════════════════
# 🎯 短線雷達
# ══════════════════════════════════════════════════════════════════
#: 10 燈的顯示名。
#:
#: ⚠️ **同 `_US_LIQ_ROWS`：服務層沒有可引用的顯示名。** `detect_risk_radar()`
#: 每一燈的 `label` 是**來源說明**（「Yahoo ^VIX 日線」），不是指標名 ——
#: 本表是唯一一份，不是第二份 SSOT。
#: ⚠️ 漏登記的 key 同樣**不會被丟掉**（見 `_detail_short()`）。
_RADAR_ROWS: tuple[tuple[str, str], ...] = (
    ("vix_level",       "VIX 絕對值 ＋ 日變化"),
    ("vix_term_struct", "VIX 期限結構"),
    ("hy_oas_delta",    "HY 利差變動"),
    ("yield_10y_shock", "10Y 殖利率急變"),
    ("move_level",      "MOVE 債市波動"),
    ("spx_trend_break", "SPX 趨勢破線"),
    ("sox_drop",        "費半急跌"),
    ("sector_rotation", "類股輪動落差"),
    ("put_call_ratio",  "Put／Call 比"),
    ("asia_overnight",  "亞洲隔夜盤"),
)

#: 深水區 4 因子的顯示名（同上，服務層無顯示名可引用）。
_LIQ_FACTOR_ROWS: tuple[tuple[str, str], ...] = (
    ("XCCY_PROXY",   "美元荒代理（跨幣別基差）"),
    ("CARRY_UNWIND", "套利交易平倉壓力"),
    ("MOVE_VIX",     "債市／股市波動背離"),
    ("SSR",          "鏈上子彈水位 SSR"),
)


def _detail_short() -> None:
    """🎯 短線雷達 —— ④ 10 燈短線風險雷達 ＋ ⑤ 深水區流動性壓力。

    **線框依據**：`wireframe-macro-health.html` section 01 對本塊的描述逐字是
    「④ ⚡ 短線風險雷達（`services.risk_radar.detect_risk_radar`…含 `vix_level`／
    `yield_10y_shock`／`spx_trend_break`）／⑤ 🌊 流動性壓力預警引擎（深水區 4 因子）」，
    section 03 把整塊列為〈保留 · 順序不動〉。

    ⚠️ **10 燈用全寬表而不是 10 張卡**：`ia-wireframe.html` Rule 01 自己就寫著
    「卡片與指標排 3 欄；**多欄位大表維持全寬橫向捲動**」。10 燈 × 5 欄
    （燈／讀數／前值／說明／來源）是大表，塞進 3 欄會被壓成兩個字。
    ⑤ 的 4 因子是少數幾個讀數，才走 3 欄卡。
    """
    if _detail_not_loaded(_DETAIL_TITLES["short"]):
        return
    _detail_title(_DETAIL_TITLES["short"])

    # ── ④ 10 燈短線風險雷達 ────────────────────────────────────────
    st.markdown("##### ④ ⚡ 短線風險雷達（24H 避險轉向速度）")
    _radar = st.session_state.get(_SK_RADAR)
    if isinstance(_radar, BaseException):
        system_error("10 燈短線風險雷達這一輪沒算出來", _radar,
                     hint="10 盞燈由同一次呼叫產出，故只印一個紅框。")
    elif not isinstance(_radar, dict):
        not_ready("尚未計算短線風險雷達。", where=_where_to_load())
    else:
        _sum = summarize_radar(_radar)
        # ⛔ 同 `_card_risk_radar()`，理由見 `_radar_lit()`。（消費端 2／3）
        if not _radar_lit(_sum):
            not_ready("10 盞燈這一輪一盞都沒有取到讀數，沒有可以下的風險結論。",
                      where=_where_to_load())
        else:
            st.caption(
                f"整體：**{_sum.get('level') or '—'}**　"
                f"🔴 {_sum.get('red', 0)} ／ 🟡 {_sum.get('yellow', 0)} ／ "
                f"🟢 {_sum.get('green', 0)} ／ ⬜ {_sum.get('gray', 0)}（共 10 燈）。"
                "　⬜ 代表這一輪沒抓到，不是「沒事」。")
        _known = {_k for _k, _t in _RADAR_ROWS}
        _extra = tuple((_k, _k) for _k in _radar if _k not in _known)
        _rows = []
        for _k, _t in (*_RADAR_ROWS, *_extra):
            _e = _radar.get(_k)
            if not isinstance(_e, dict):
                continue
            _rows.append({
                "訊號": _t,
                "燈": str(_e.get("signal") or "—"),
                "讀數": "—" if _e.get("value") is None else _e.get("value"),
                "前值": "—" if _e.get("prev") is None else _e.get("prev"),
                "說明": str(_e.get("note") or "—"),
                "來源": str(_e.get("label") or "—"),
            })
        wide_table(
            pd.DataFrame(_rows) if _rows else None,
            empty_title="這一輪一盞燈都沒有回傳",
            empty_missing="10 盞燈全部沒有可用的內容。",
            empty_where=_where_to_load(),
            hide_index=True,
        )

    # ── ⑤ 🌊 深水區流動性壓力 ──────────────────────────────────────
    st.markdown("##### ⑤ 🌊 流動性壓力預警引擎（深水區 4 因子）")
    _liq = st.session_state.get(_SK_LIQ)
    if isinstance(_liq, BaseException):
        system_error("深水區流動性因子這一輪沒算出來", _liq,
                     hint="4 個因子由同一次呼叫產出，故只印一個紅框。")
        return
    if not isinstance(_liq, tuple) or len(_liq) != 2:
        not_ready("尚未計算深水區流動性壓力。", where=_where_to_load())
        return

    _factors, _score = _liq
    _factors = _factors if isinstance(_factors, dict) else {}
    _known_f = {_k for _k, _t in _LIQ_FACTOR_ROWS}
    _extra_f = tuple((_k, _k) for _k in _factors
                     if _k != "_provenance" and _k not in _known_f)
    # 鐵則 01：4~5 張卡 → 3 欄網格。
    render_cards([
        _entry_card(_t, _factors.get(_k))
        for _k, _t in (*_LIQ_FACTOR_ROWS, *_extra_f)
    ])
    if isinstance(_score, dict):
        _tier = str(_score.get("tier") or "")
        _val = _score.get("value")
        st.caption(
            f"壓力分數 **{_val if _val is not None else '—'}**"
            f"（{_tier or '—'}）：{liquidity_verdict(_score, _factors)}")
    else:
        # `compute_liquidity_score()` 的契約：三個壓力因子**全缺**時回 `None`。
        # 那不是故障，是「這一輪沒有足夠因子可以合成」→ 灰態（鐵則 03）。
        not_ready(
            "壓力分數合不出來：三個壓力因子（美元荒／套利平倉／波動背離）"
            "這一輪一個都沒取到。",
            where=_where_to_load())


# ══════════════════════════════════════════════════════════════════
# ⚠️ 拐點警報
# ══════════════════════════════════════════════════════════════════
def _detail_inflection() -> None:
    """⚠️ 拐點警報 —— ① 全域導航塔（3 儀表）＋ ② 拐點偵測中心（5 組結構訊號）。

    **線框依據**：`wireframe-macro-health.html` section 01 對本塊的描述逐字是
    「① 🎯 全域導航塔（薩姆／SLOOS／廣度，3 欄）／🚦 持倉紅綠燈（讀 portfolio_funds）／
    ② 🎯 拐點偵測中心（`detect_turning_points`：新訂單−庫存、10Y-2Y、HY、薩姆、
    CFNAI、歷史回測、變數重要性）」。

    ⛔ **🚦 持倉紅綠燈本塊不畫** —— section 04「搬移對照表」把它標「**搬 → ② 行動摘要**」，
    理由逐字：「逐檔燈號…同時是 DUP-2 三個矛盾答案之一」。它已經有一句指路
    （`_render_matrix_signpost()`），這裡**不再畫第二次**，也不畫一個灰色空殼
    —— 線框把它標「搬」不是「待補」，畫灰殼會讓它看起來像沒做完（鐵則 04）。

    ⛔ **歷史回測與變數重要性本塊不畫。** `backtest_turning_points()` 是**另一次
    對外取數**（它自己再抓一次 FRED 與 SPX），而本頁的鐵則 02 是「一顆送出鈕之後
    不再有第二顆載入鈕」。把它掛進主載入會讓每次載入多一條長往返；
    掛一顆自己的鈕又正好是線框點名要拿掉的那種「按鈕的按鈕」。
    **兩條路都不對 → 本批不做，據實登記，留給客戶裁決要不要為它開一次載入。**
    """
    if _detail_not_loaded(_DETAIL_TITLES["inflection"]):
        return
    _detail_title(_DETAIL_TITLES["inflection"])
    _ind = st.session_state.get(_SK_IND) or {}

    # ── ① 全域導航塔：薩姆 ／ SLOOS ／ 市場廣度 ─────────────────────
    # 三個讀數**全部來自 `ind`**（`fetch_all_indicators` 的 SAHM / SLOOS / ADL），
    # 沒有額外取數。鐵則 01：正好 3 張 → 一列 3 欄。
    st.markdown("##### ① 🎯 全域導航塔（薩姆 ＋ SLOOS ＋ 市場廣度）")
    render_cards([
        _nav_tower_card(_ind, "SAHM", "薩姆規則 · 衰退機率",
                        _sahm_band, "失業率 3 個月均較過去 12 個月低點高出的百分點；"
                                    "≥0.5 判定衰退已經開始。"),
        _nav_tower_card(_ind, "SLOOS", "SLOOS · 銀行信貸標準",
                        _sloos_band, "聯準會季度調查；正值＝銀行在收緊放貸。"),
        _breadth_card(_ind),
    ])

    # ── ② 拐點偵測中心 ─────────────────────────────────────────────
    st.markdown("##### ② 🎯 拐點偵測中心（月級結構訊號）")
    _tp = st.session_state.get(_SK_TP)
    if isinstance(_tp, BaseException):
        system_error("拐點偵測這一輪沒算出來", _tp,
                     hint="5 組訊號由同一次呼叫產出，故只印一個紅框。")
        return
    if not isinstance(_tp, dict) or not _tp:
        not_ready("尚未計算拐點偵測。", where=_where_to_load())
        return

    render_cards([_tp_card(_k, _v) for _k, _v in _tp.items()])
    if not any(isinstance(_v, dict) and _v.get("source_ok") for _v in _tp.values()):
        # 全部 `source_ok=False` ＝ 5 組訊號都沒有真的算出來。
        # ⚠️ 各卡自己已經是灰態，這一行是**整塊的結論**：不得讓使用者以為
        #    「5 個都沒亮紅燈 ＝ 沒有拐點風險」（§1）。
        not_ready("5 組拐點訊號這一輪全部沒有取到資料，"
                  "上面的 ⬜ 是「沒算出來」，不是「沒有拐點」。",
                  where=_where_to_load())


def _sahm_band(v: float) -> tuple[bool, str]:
    """薩姆規則讀數 → （**是不是業務警示**, 一句話）。

    ⚠️ **回 `bool` 而不是回 `STATE_*` 字串，是刻意的。**
    `tests/test_batch2_top_card_grid.py::test_not_ready_cards_carry_a_remedy_too`
    以 AST 檢查卡片 dict：`state` 若是一個**變數**（靜態看不出是哪一態），
    它會保守地當成「可能是灰態」而要求帶 `where=`。
    把分級結果留成 `bool`、由呼叫端寫成
    `STATE_BUSINESS if _alert else STATE_OK` 這種**兩個字面值的條件式**，
    那條規則就能靜態判定「這裡不可能是灰態」——
    **不是為了繞過規則，是讓規則看得懂**（繞過的做法是硬加一個用不到的 `where`）。

    ⚠️ 門檻 0.5 不是本檔發明的：`shared/signal_thresholds.py` 的
    `SAHM_RECESSION_THRESHOLD` 就是它，`services/macro/turning_points.py` 也用它。
    這裡刻意**只用它做文案分級**、不參與任何計算 —— 需要判定時看 ② 拐點偵測中心
    的 `sahm_rule` 那一張，那才是走 SSOT 算出來的。
    """
    if v >= 0.5:
        return True, "🔴 已達衰退判定門檻（≥0.5）"
    if v >= 0.3:
        return False, "🟡 進入警戒區（≥0.3）"
    return False, "🟢 低於警戒區（<0.3）"


def _sloos_band(v: float) -> tuple[bool, str]:
    """SLOOS 讀數 → （是不是業務警示, 一句話）。回傳形狀的理由見 `_sahm_band`。"""
    if v > 20:
        return True, "🔴 銀行明顯收緊放貸（>20%）"
    if v > 0:
        return False, "🟡 中性偏緊（>0%）"
    return False, "🟢 信貸寬鬆（<0%）"


def _nav_tower_card(ind: dict, key: str, title: str,
                    band: Callable[[float], tuple[bool, str]],
                    what: str) -> dict:
    """全域導航塔的一張卡：從 `ind[key]["value"]` 取讀數 → 分級 → 卡片規格。"""
    _d = ind.get(key)
    _v = _d.get("value") if isinstance(_d, dict) else None
    if not isinstance(_v, (int, float)):
        # ⚠️ **缺值不畫 0**：舊頁 v19.387 就是在修這個 —— `or 0` 會把「沒資料」
        #    畫成 0.00 的綠燈，也就是偽裝健康（§1）。
        return {"title": title, "state": STATE_NOT_READY,
                "note": f"這一輪沒有取到讀數。{what}",
                "where": _where_to_load()}
    _alert, _verdict = band(float(_v))
    _unit = str(_d.get("unit") or "")
    return {"title": title, "value": f"{float(_v):.2f}{_unit}",
            "note": f"{_verdict}　{what}",
            # 🔴 ＝市場壞消息、數字可信 → 業務警示；不是系統紅框（鐵則 03）。
            "state": STATE_BUSINESS if _alert else STATE_OK}


def _breadth_card(ind: dict) -> dict:
    """市場廣度（RSP／SPY）那一張。**量綱陷阱寫在這裡，不要照搬 `value`。**

    ⚠️ `ind["ADL"]` 的 `value` 是 **RSP÷SPY 的比值**（無因次、量級 ~0.29、恆為正），
    而**月變動百分比**由服務層放在 `prev` 欄（同 dict 的 `unit` 也是空字串）。
    舊頁 `ui/tab1_macro_inflection.py` 已就地記過這個坑：整組刻度是為「月變動 %」
    設計的，餵比值進去會讓指針恆黏在 0.29、燈恆亮中性 —— **不論真實廣度如何**。
    依 `CLAUDE.md §4.1` 命名規範，本函式的變數名帶單位，避免下一個人再接錯。
    """
    _d = ind.get("ADL")
    _mom_pct = _d.get("prev") if isinstance(_d, dict) else None
    if not isinstance(_mom_pct, (int, float)):
        return {"title": "市場廣度 · RSP／SPY", "state": STATE_NOT_READY,
                "note": "這一輪沒有取到廣度的月變動。"
                        "等權重／市值加權比值上升＝中小型股也在漲（健康）。",
                "where": _where_to_load()}
    _pct = float(_mom_pct)
    # 分級結果留成 `bool` + 文案，`state` 由兩個字面值組出來 —— 理由見 `_sahm_band`。
    _alert = _pct < -2
    if _alert:
        _verdict = "🔴 廣度收窄，只有大型股撐盤"
    elif _pct > 2:
        _verdict = "🟢 廣度健康"
    else:
        _verdict = "🟡 廣度持平"
    return {"title": "市場廣度 · RSP／SPY", "value": f"{_pct:+.2f}%",
            "note": f"{_verdict}　RSP÷SPY 的**月變動**（不是比值本身）。",
            "state": STATE_BUSINESS if _alert else STATE_OK}


def _tp_card(key: str, entry: Any) -> dict:
    """拐點偵測中心的一張卡。

    ⚠️ **標題吃服務層自己的 `label`**（例：「新訂單 YoY − 庫存 YoY (M3 製造業)」）——
    那一欄就是指標名，本檔**不另抄一份**（§2.1）。抄不到時退回 key，
    寧可醜也不要無聲消失。
    ⚠️ `source_ok=False` ＝ 這一組這一輪沒算出來 → **灰態**，不是綠燈也不是紅框。
    """
    if not isinstance(entry, dict):
        return {"title": key, "state": STATE_NOT_READY,
                "note": "這一輪沒有回傳這一組拐點。", "where": _where_to_load()}
    _title = str(entry.get("label") or key)
    _note = str(entry.get("note") or "—")
    if not entry.get("source_ok"):
        return {"title": _title, "state": STATE_NOT_READY,
                "note": _note, "where": _where_to_load()}
    _sig = str(entry.get("signal") or "")
    _val = entry.get("value")
    return {
        "title": _title,
        "value": f"{_val}" if _val is not None else "—",
        "note": f"{_sig}　{_note}",
        # 🔴 開頭＝景氣壞消息，資料本身可信 → 業務警示，不是系統紅框（鐵則 03）。
        "state": STATE_BUSINESS if _sig.startswith("🔴") else STATE_OK,
    }


# ══════════════════════════════════════════════════════════════════
# 🤖 AI 景氣判斷總結
# ══════════════════════════════════════════════════════════════════
#: AI 逐章節結論要涵蓋的章節名 —— **就是本頁詳細區的四塊 ＋ 兩層總表**。
#: 不手抄第二份區塊名：四時域直接吃 `_DETAIL_TITLES`（見 `_ai_sections()`）。
_AI_TAB_LABEL: str = "總經位階"

#: 資料完整率低於這個百分比就**不讓 AI 跑**（阻斷），介於兩者之間則降可信度。
#: ⚠️ 兩個門檻沿用舊頁 `ui/tab1_macro_ai.py` 已經在用的 50 / 80 ——
#: 這不是本檔發明的政策，是把既有行為原樣帶過來。
_AI_BLOCK_PCT: int = 50
_AI_WARN_PCT: int = 80


def _ai_sections() -> list[str]:
    """AI 要逐節下結論的章節清單（順序即畫面順序）。"""
    return ["① 結論與依據（五桶證據表）",
            *[_DETAIL_TITLES[_k] for _k in _DETAIL_HORIZON_KEYS]]


def _ai_completeness_pct(ind: dict) -> int:
    """這一輪的資料完整率 %。

    ⚠️ **分母不寫死**（同 `_card_credibility` 的理由：`fetch_all_indicators` 沒有
    一個乾淨的總數，寫死會過期也會失真）。這裡用的是**執行期實際數**：
    非 meta 的 dict 條目裡，`value` 真的不是 `None` 的比例。
    """
    _real = {_k: _v for _k, _v in (ind or {}).items()
             if isinstance(_v, dict) and not is_meta_key(_k)}
    if not _real:
        return 0
    _have = len([_v for _v in _real.values() if _v.get("value") is not None])
    return round(_have * 100 / len(_real))


def _ai_snapshot(ind: dict, phase: dict, ev: dict) -> str:
    """交給 AI 的資料快照。**只把已經算好的讀數排版成字串，不新增任何計算。**

    ⚠️ 每一行都標明「這一項有沒有取到」——`—` 就是 `—`，
    **不補值、不四捨五入成 0**（§1）。AI 讀到 `—` 才會知道那一項是缺的；
    餵 0 進去它會當成一個真的觀測值去推論。
    """
    _lines: list[str] = []
    _lines.append(f"[總經位階] {phase.get('phase') or '—'}"
                  f"（分數 {phase.get('score')}/10）")
    _score = ev.get("score")
    _lines.append(f"[綜合健康度] 加權淨分 "
                  f"{_score if _score is not None else '—'}"
                  f"｜等級 {ev.get('level') or '（證據不足，未給等級）'}")

    _real = {_k: _v for _k, _v in (ind or {}).items()
             if isinstance(_v, dict) and not is_meta_key(_k)}
    _lines.append(f"[指標完整率] {_ai_completeness_pct(ind)}%"
                  f"（{len(_real)} 項中有讀數者）")
    for _k, _v in sorted(_real.items()):
        _val = _v.get("value")
        _lines.append(
            f"  - {_v.get('name') or _k}："
            f"{'—' if _val is None else _val}{_v.get('unit') or ''}"
            f"｜{_v.get('signal') or ''} {_v.get('desc') or ''}".rstrip())

    _radar = st.session_state.get(_SK_RADAR)
    if isinstance(_radar, dict):
        _s = summarize_radar(_radar)
        # ⛔ **消費端 3／3 —— 這一份是 2026-09-05 稽核 F1 補的，前一版漏掉。**
        #    它比另外兩個更嚴重：這一行會進 prompt，而 prompt 開頭寫著
        #    「**只能根據下面的『資料快照』來講**」——
        #    餵 `整體 平靜` 進去，等於**直接告訴模型市場平靜**，
        #    而實際上 10 盞燈一盞都沒抓到。理由與唯一定義見 `_radar_lit()`。
        if not _radar_lit(_s):
            # ⚠️ **這一行刻意連「平靜」兩個字都不出現。**
            #    守衛 `test_the_ai_snapshot_never_calls_the_market_calm_when_nothing_was_fetched`
            #    用的是最鈍的斷言（整份快照不得含那兩個字），而它第一次就抓到
            #    **本行原本的警語自己帶著那兩個字** —— 對 LLM 而言，
            #    「不得推論市場平靜」與「市場平靜」在 token 層級高度重疊，
            #    寫進 prompt 本身就是一種提示。**警語要用不會被誤讀的措辭。**
            _lines.append(
                "[短線雷達] 無法研判：10 盞燈這一輪一盞都沒有取到讀數"
                "（⬜×10）。這是「沒抓到」，不是「沒有風險」；"
                "**不得**據此對短線風險下任何結論。")
        else:
            _lines.append(f"[短線雷達] 整體 {_s.get('level')}｜"
                          f"🔴{_s.get('red')} 🟡{_s.get('yellow')} "
                          f"🟢{_s.get('green')} ⬜{_s.get('gray')}（⬜＝沒抓到）")
    _tp = st.session_state.get(_SK_TP)
    if isinstance(_tp, dict):
        for _k, _v in _tp.items():
            if isinstance(_v, dict):
                _lines.append(
                    f"[拐點] {_v.get('label') or _k}："
                    f"{_v.get('signal')}"
                    f"{'' if _v.get('source_ok') else '（未取到資料）'}")
    _usl = st.session_state.get(_SK_USLIQ)
    if isinstance(_usl, dict):
        for _k, _t, _g in _US_LIQ_ROWS:
            _e = _usl.get(_k)
            if isinstance(_e, dict) and not _e.get("_err"):
                _lines.append(f"[{_g}] {_t}：{_e.get('value')}"
                              f"{_e.get('unit') or ''}｜{_e.get('label') or ''}")
    return "\n".join(_lines)


def _detail_ai() -> None:
    """🤖 AI 景氣判斷總結 —— 逐章節白話結論。

    **線框依據**：`wireframe-macro-health.html` section 03 把
    「🤖 AI 景氣判斷總結」列為詳細區〈保留 · 順序不動〉的**第五塊**，
    section 04 另有一列寫「四時域詳細 ＋ 🤖 AI 景氣總結 → **留 · ① 原位**」。

    ⛔ **不委派 `ui/helpers/ai_summary.py::render_ai_summary_widget`**，兩個理由：
    1. **它會多印一個 H4 標題**（`#### 🤖 AI 白話總體檢（…）`），而詳細區的一級
       序列被 `tests/test_wf01_detail_zone_order.py` 鎖成「區頭 ＋ 恰好五塊」——
       委派過去會憑空多出第六個一級區塊。**那條鎖是對的，該讓的是本塊。**
    2. 它自帶一顆裸 `st.button`；本頁的鐵則 02 落點是
       `ui.helpers.ia.applied_form`（送出鈕之外不放第二顆載入鈕）。
    本塊因此直接呼叫**服務層**的 `build_structured_summary_prompt` ／
    `gemini_generate` ／ `get_gemini_keys` —— 那比委派 UI helper 更貼近客戶方針
    第 2 條（「新 UI 僅呼叫既有 Service 函式」）。

    ⚠️ **生成結果只放 session，不落地磁碟。** 舊 widget 有一層
    `repositories.ai_cache` 磁碟續存；那是 L1，本頁依方針第 2 條不碰資料層。
    代價據實寫在畫面上：reboot 之後要重按一次。
    """
    if _detail_not_loaded(_DETAIL_TITLES[_DETAIL_AI_KEY]):
        return
    _detail_title(_DETAIL_TITLES[_DETAIL_AI_KEY])
    _ind = st.session_state.get(_SK_IND) or {}

    _keys = get_gemini_keys()
    if not _keys:
        not_ready("未設定 Gemini 金鑰，AI 總結無法生成",
                  where="Streamlit Cloud → Settings → Secrets 的 `GEMINI_API_KEY`")
        return

    _pct = _ai_completeness_pct(_ind)
    if _pct < _AI_BLOCK_PCT:
        # ⚠️ **這是「前提不足」不是「系統故障」→ 灰態，不是紅框**（鐵則 03）。
        #    舊頁這裡畫的是紅色阻斷框；紅色在新版專屬「系統真出錯」，
        #    而這裡什麼都沒壞 —— 只是資料還不夠讓 AI 講話。
        not_ready(f"總經資料完整率只有 {_pct}%（低於 {_AI_BLOCK_PCT}%），"
                  "這種輸入下 AI 的結論會建立在一堆缺值上，故不生成。",
                  where=_where_to_load())
        return

    _phase = st.session_state.get(_SK_PHASE) or {}
    _ev = st.session_state.get(_SK_EV) or {}
    _snapshot = _ai_snapshot(_ind, _phase, _ev)
    _stale = ""
    if _pct < _AI_WARN_PCT:
        # 不擋，但**把折扣寫進交給 AI 的輸入本身**，不是只印在畫面上 ——
        # 只印畫面的話，AI 仍然會用一句斬釘截鐵的話講一份殘缺的資料。
        _stale = (f"⚠️ 這一輪的總經資料完整率只有 {_pct}%，"
                  "缺值的指標一律以「—」呈現，請在結論裡明說哪幾項沒有資料。")
        st.caption(f"🟡 資料完整率 **{_pct}%**（低於 {_AI_WARN_PCT}%），"
                   "AI 結論的參考性下降；缺的項目在快照裡是「—」，不是 0。")

    # ── 鐵則 02：生成也走 form，不放裸按鈕 ──────────────────────────
    # ⚠️ 走 `applied_form()` 而不是自己寫 `st.form(` —— 後者會讓
    #    `tests/test_ui_rerun_contract.py::FORM_SITE_TOTAL`（精確 `==` 7）變 8 而轉紅。
    # 這一輪送出鈕上要印的字。**先算成一個變數，再同時交給送出鈕與下方的指路**
    # —— 兩邊因此不可能分岔（同 `_SK_BTN` / `_where_to_load()` 的做法）。
    _ai_label = (_AI_BTN_AGAIN if st.session_state.get(_SK_AI)
                 else _AI_BTN_FIRST)
    with applied_form(_AI_FORM_KEY, submit_label=_ai_label) as _gate:
        st.caption(
            f"把這一頁已經取到的讀數（{len(_snapshot.splitlines())} 行快照）交給 AI，"
            "逐段用白話講「現在是好是壞、下一步怎麼做」。"
            "　⚠️ AI 只會看到上面那些數字，缺的項目是「—」。")

    if _gate:
        _prompt = build_structured_summary_prompt(
            tab_label=_AI_TAB_LABEL, snapshot=_snapshot,
            sections=_ai_sections(), headlines=[], stale_note=_stale,
        )
        try:
            with st.spinner("🤖 AI 正在逐段判讀（約 10-20 秒）…"):
                st.session_state[_SK_AI] = gemini_generate(
                    _prompt, max_tokens=3500, keys=_keys)
        except Exception as _exc_ai:                # noqa: BLE001 — §1：下一行就印
            st.session_state[_SK_AI] = None
            system_error("AI 總結生成失敗", _exc_ai,
                         hint="上游 Gemini 可能暫時不可用或額度用盡；"
                              "稍後再按一次送出鈕。")
            return

    _text = st.session_state.get(_SK_AI)
    if not _text:
        # ⚠️ 指路吃的是**上面那顆鈕實際用的那個變數**，不是抄一份字面值（F5）。
        not_ready("還沒有生成過 AI 總結。",
                  where=f"{where_to_find('macro')} → 上方「{_ai_label}」")
        return
    st.markdown(_text)
    st.caption("⚠️ AI 生成內容僅供參考，數字一律以上方各區塊的讀數為準。"
               "　本頁的 AI 結果只存在這個 session，重新啟動後要再按一次。")


#: 詳細區的**渲染序列** —— `(key, 標題, render callable)`，**順序即畫面順序**。
#:
#: ⚠️ **前四項的 key 由 `BUCKET_ORDER` 導出**（見 `_DETAIL_HORIZON_KEYS`）：
#: 「長期 → 中期 → 短線 → 拐點」這個順序在本 repo 只有一個出處，本檔**不抄第二份**。
#: 第五項是 🤖 AI 總結 —— 它**不是時域桶**，`BUCKET_ORDER` 裡沒有它，故另給哨兵 key。
#: 守衛：`tests/test_wf01_detail_zone_order.py`（結構鎖 ＋ 行為鎖，見該檔）。
#: 每一塊自己的 render 函式。**一塊一支，不共用**。
#:
#: ⚠️ **2026-09-05 批次三-B：四塊灰態佔位全部換成真內容。**
#: 在此之前這裡是
#: `_detail_mid if _k == "mid" else partial(_detail_pending, …)` ——
#: 也就是「一塊真的、四塊灰的」。現在五塊各有自己的渲染函式。
#: `_detail_pending` **保留不刪**，但**它的射程只剩兩處**（2026-09-05 稽核 F4 更正）：
#: ~~它仍是**四塊各自**的「還沒載入」出口（經 `_detail_not_loaded()`）~~ ——
#: **那句不成立**。實測（AST，本檔全檔）`_detail_pending` 的呼叫點只有兩個：
#:   (1) `_detail_mid()` 的「沒有 ind」分支（**一塊**，不是四塊）；
#:   (2) 下方 `_DETAIL_ZONE` 生成式裡的 `partial(...)` fallback（沒登記的 key）。
#: **四塊走的是 `_detail_not_loaded()`，而那一支自己呼叫 `not_ready()`，
#: 並不經過 `_detail_pending`。** 兩者只是印出來的東西很像，不是同一條路。
#: ⚠️ **上面那個「兩個」還要再精確兩點（2026-09-05 稽核 F4 殘留，就地補）**：
#:   (a) 第 (2) 個**在嚴格 AST 意義下不是呼叫點** —— `partial(_detail_pending, …)`
#:       裡的 `_detail_pending` 是傳給 `partial()` 的 **`Name` 引數**，不是 `Call.func`；
#:   (b) 它**今天執行期不可達** —— `_DETAIL_RENDERERS` 五個 key 全部登記，
#:       `.get(_k) or partial(...)` 的 `or` 會短路，**`partial(...)` 連建構都不會發生**。
#: → **今天真正跑得到 `_detail_pending` 的只有 `_detail_mid()` 那一處。**
#:   第 (2) 個是**留給「有人新增區塊卻忘了登記」的安全網**，不是現行路徑。
#: ⚠️ 這一筆記在這裡，是因為「它還被四個地方用著」會讓下一個人不敢動它 ——
#: 實際上動它只影響 📈 中期循環與 fallback 這兩處。
#: ⚠️ **對照表在這裡，不在 `_DETAIL_ZONE` 的生成式裡** —— 生成式裡塞
#: `if/else` 鏈在第五塊之後就沒人看得懂哪個 key 配哪支函式了。
_DETAIL_RENDERERS: dict[str, Callable[[], None]] = {
    "long":         _detail_long,
    "mid":          _detail_mid,
    "short":        _detail_short,
    "inflection":   _detail_inflection,
    _DETAIL_AI_KEY: _detail_ai,
}

_DETAIL_ZONE: tuple[tuple[str, str, Callable[[], None]], ...] = tuple(
    (
        _k,
        _DETAIL_TITLES[_k],
        # ⚠️ 沒登記的 key **退回灰態佔位，不是 KeyError** —— 那樣整頁會被
        #    `app.py` 的分頁級 try 換成一個紅框，而使用者其實只是少了一塊。
        #    `partial` 而不是 lambda：lambda 在生成式裡會**共用同一個 `_k`**
        #    （late binding），沒登記的幾塊會全部印成最後一個標題。
        _DETAIL_RENDERERS.get(_k) or partial(_detail_pending, _DETAIL_TITLES[_k]),
    )
    for _k in (*_DETAIL_HORIZON_KEYS, _DETAIL_AI_KEY)
)


def _render_detail_zone() -> None:
    """層 4：🔎 詳細資料與說明 —— 依 :data:`_DETAIL_ZONE` **逐塊按順序**渲染。

    ⚠️ **順序不動是線框明寫的**（section 03「保留 · **順序不動**」），
    而 ② 依據表的「詳細在下方哪一段」那一欄**直接指向這幾塊** ——
    順序一亂，那一欄就開始說謊。故本區塊有專屬守衛，見
    `tests/test_wf01_detail_zone_order.py`。

    ⚠️ **一個本批沒有修、也修不了的視覺不一致（據實揭露，不要當成沒看到）**：
    本頁的層級是「`##` 頁標題 → `###` 層 → `####` 詳細區塊」，四塊灰態照這個層級走；
    但 📈 中期循環是由 `ui/tab1_macro_midcycle.py` **自己印 `## 📈 中期循環`**，
    比它上面的區頭 `### 🔎 詳細資料與說明` **還大一級**。
    **修它要動 `ui/tab*.py`，那是客戶方針第 1 條明禁的**（不在舊檔上修改），
    所以本批不動。等其餘四塊也重寫過來、五塊都由本檔控制標題時，一併統一。
    ⚠️ 守衛（`tests/test_wf01_detail_zone_order.py`）**刻意只鎖標題文字、不鎖級數**，
    就是為了不讓這個過渡狀態變成一條與版面演進作對的假紅。
    """
    st.divider()
    st.markdown(f"### {_DETAIL_HEADING}")
    for _key, _title, _render in _DETAIL_ZONE:   # noqa: B007 — key 供守衛讀
        # ⚠️ **每一塊各自包一層區塊級隔離** —— 走既有共用 helper
        # `ui/helpers/render_state.py::safe_section`（**不是** `ui/tab*.py` 裡那份私有的，
        # 方針第 1 條不准動舊檔；這一支是 SSOT 側的公開版，它的 docstring 講的正是這件事）。
        #
        # ⛔ **2026-09-05 稽核實測，這不是預防性加固，是修一個已經會發生的斷頭**：
        # 讓 `render_mid_cycle_section` 拋一個例外（模擬上游 `ind` 形狀變動），
        # 前一版的結果是 —— 例外一路逃出 `render_market_overview`，
        # **🎯 短線雷達 / ⚠️ 拐點警報 / 🤖 AI 總結三塊全部消失，
        # 連 `_render_matrix_signpost()` 那句指路也一起沒了**，
        # 最近的網子只剩 `app.py` 的**分頁級** try（整頁換成一個紅框）。
        # 而那句指路是整批搬移裡**唯一留給使用者的線索** ——
        # 為它單獨寫一條守衛、卻讓一個上游變動就能把它帶走，是自相矛盾的。
        #
        # ⚠️ `safe_section` **不吞例外**（§1）：它走 `system_error()` 顯式紅框 ＋
        # log ＋ 可展開 traceback，只是把爆炸範圍收斂到那一塊。
        safe_section(_title, _render)
    _render_matrix_signpost()


def _render_matrix_signpost() -> None:
    """線框 section 05 點名要留的那一句指路：逐檔加減碼建議要去 ② 找。

    ⚠️ **時態是中性的，這是刻意的** —— 見本函式末段與 `st.caption` 上方的註解：
    決策矩陣**目前還沒有真的落到 ②**，所以不能寫「已經搬到 ② 了」。

    **線框原文（section 05「據實揭露」）**：
    「① 頁會變短、變得『只講市場』。習慣在 ① 頁底看逐檔加減碼建議的人，會找不到它
    —— 需要在 ① 的決策矩陣原位留一句指路到 ②。」

    **放在詳細區最後一塊之後**，理由三條：
    1. **那就是「原位」**。舊頁的 📋 即時訊號 ＋ 決策矩陣**渲染在四時域之後**
       （`ui/tab1_macro.py` 的 `## 📋 即時訊號 + 決策矩陣`，且
       `tests/test_audit_20260805_tab1_ui.py`
       ::test_decision_matrix_sits_after_the_horizons_and_before_the_ai_summary
       就是守它「在時域之後」的那條）。使用者往下捲到底找它，指路就該在那裡等他。
    2. **不做一個空的「決策矩陣」區塊**。線框把它整組標「搬」、verdict 大卡標「刪除」，
       畫一個灰色的空殼會讓它看起來像「還沒做完」而不是「已經搬走了」——
       那正是鐵則 04 要避免的「把消失換成灰色的消失」。
    3. **它不是灰態**。灰態說的是「缺東西、補了就有」；這裡東西沒有缺，只是**換了地方**
       ——所以走 `st.caption` 指路，不走 `not_ready()`。

    ⚠️ **分頁名走 `where_to_find()`，不手抄** —— 線框 section 05 同段明寫
    「本次搬移會新增一批需要指路的位置（① 決策矩陣原位 → ②…），
    **那些新指路屬本次範圍，一律走同一支 SSOT，不得手抄**」。
    本 repo 的「指路指到一個不存在的分頁名」已發作三次
    （見 `ui/helpers/story_nav.py` 的 `RETIRED_TAB_LABELS` / `MISWRITTEN_TAB_NAMES`）。

    ⚠️ **本段位置由本組判斷**（線框只寫「原位」，沒有指定新頁的哪一行），
    **未經第二組獨立驗證**（§-2 規則 6）—— 它是可以被推翻的版面決定，
    不是查證出來的事實。
    """
    # ⚠️ **時態刻意是中性的（「請到」，不是「已搬到」）—— 總管 2026-09-05 裁決。**
    # 「已經搬到 ② 了」在**本 commit 尚未為真**：逐檔決策矩陣整組目前只存在於
    # `ui/tab1_macro.py`，而該檔已不接線到任何分頁 —— 它現在**哪裡都到不了**，
    # ② 底下也還沒有線框說的那一區。寫「已搬到」會讓使用者跑去 ② 找一組
    # **還不存在的東西**，那就是一句會改變行為的假敘述（客戶 2026-09-05 標準：
    # 不接受假資料／缺資料）。
    # ✅ 等矩陣真的落到 ② 之後，再把這句改成過去式。
    # ⚠️ 分頁名仍走 `where_to_find()` SSOT，本次只改時態，不改指向。
    st.caption(
        f"📋 **逐檔的加減碼建議請到 {where_to_find('health')}。**"
        f"　這一頁只講市場（大盤與總經），不出現任何一檔你持有的基金；"
        f"「我手上這幾檔該加該減」是 {where_to_find('health')} 的題目。"
    )


# ══════════════════════════════════════════════════════════════════
# 已裁決不做的區塊：誠實灰態（鐵則 04：未完成不留白，也不畫空表格外框）
# ══════════════════════════════════════════════════════════════════
def _render_deferred_blocks() -> None:
    """層 4（詳細區）＋「已拍板不做」的區塊。

    ⚠️ 這些**不是**失敗，也不是抓取失敗 → 一律灰態（`not_ready` 系），不上紅（鐵則 03）。
    """
    _render_detail_zone()
    empty_state(
        "總經燈號全表（值／位階／資料日期／來源）—— 已拍板不做",
        "「來源」欄目前**只有 1 項指標**帶得回來源標記，其餘全部會是「—」；"
        "而「位階」欄兩份線框都沒有定義過它的意思",
        where=where_to_find("diag"),
        footer="這不是壞掉：資料層有記來源，是計算層沒有把它一起帶下來；"
               "補齊要動到底層，不在本頁的範圍內。"
               "本頁的主要大表是上面那張「② 依據」五桶證據表。",
    )


# ══════════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════════
def render_market_overview() -> None:
    """渲染「① 市場總覽」整頁。`app.py` 的 `with tab_macro:` 呼叫它。"""
    # ⚠️ 分頁名**不寫死**：只准有一個來源 `ui/helpers/story_nav.py`
    # （`tests/test_wpf_five_tab_wiring.py::test_no_live_string_hardcodes_a_tab_name` 守）。
    st.markdown(f"## {tab_label('macro')}")
    render_story_nav("macro")
    # 兩份線框對「① 回答什麼」的說法一致，這一句不涉衝突。
    st.caption("回答一個問題：**現在市場環境該進攻還是防守？** "
               "這裡只有大盤與總經，不出現任何一檔你持有的基金。")

    _fred_key = os.environ.get("FRED_API_KEY", "")
    _loaded = isinstance(st.session_state.get(_SK_IND), dict)
    # 這一輪要印在送出鈕上的字。**先算出來、存起來、再交給表單** ——
    # 指路文案（`_where_to_load()`）讀的就是這個變數，兩邊因此不可能分岔。
    _submit_label = MACRO_LOAD_BTN_AGAIN if _loaded else MACRO_LOAD_BTN_FIRST
    st.session_state[_SK_BTN] = _submit_label

    # ── 鐵則 02：載入閘門（按送出鈕才取數）──────────────────────────
    # ⚠️ 走 `applied_form()` 而不是自己寫 `st.form(` —— 後者會讓
    #    `tests/test_ui_rerun_contract.py::FORM_SITE_TOTAL`（精確 `==` 7）變 8 而轉紅。
    # ⚠️ `if _gate:` **必須寫在 `with` 之外**：送出鈕是在 `yield` 之後才建立的，
    #    區塊內判斷恆為 False（`ui/helpers/ia/gated_form.py` 的模組 docstring）。
    with applied_form(
            _FORM_KEY,
            submit_label=_submit_label,
    ) as _gate:
        st.caption("資料源　FRED ＋ FinMind。"
                   "⬜ 表單欄位待客戶裁決：兩份線框一份是「觀察區間 ＋ 資料源」，"
                   "另一份是「四個資料類別勾選框 ＋ 強制重抓」。本批只做骨架與送出鈕。")

    if not _fred_key:
        # 金鑰沒填是「你還沒設定」，不是「系統壞了」→ 一律灰色說明，不上紅。
        not_ready("尚未設定 FRED 金鑰，無法載入總經資料",
                  where="Streamlit Cloud → Settings → Secrets 的 `FRED_API_KEY`")
        _render_deferred_blocks()
        return

    if _gate:
        try:
            _load_everything(_fred_key)
        except Exception as _exc:                   # noqa: BLE001 — §1：不靜默吞，下一行就印
            st.session_state[_SK_ERR] = _exc
            st.session_state[_SK_IND] = None
            system_error("總經指標載入失敗", _exc,
                         hint="上游 FRED / PMI 來源可能暫時不可用；"
                              "稍後再按一次送出鈕。")
            _render_deferred_blocks()
            return                                  # ← 印過了，不要再從 session 印第二次

    _err = st.session_state.get(_SK_ERR)
    if isinstance(_err, BaseException):
        # 只印**一個**紅框：`N 張卡 N 個紅框` 會讓使用者找不到真正的那一個。
        system_error("總經指標載入失敗", _err,
                     hint="這一頁的卡片以它為前提，故本輪不渲染卡片。"
                          "請稍後再按一次送出鈕。")
        _render_deferred_blocks()
        return

    _ind = st.session_state.get(_SK_IND)
    if not isinstance(_ind, dict):
        # 尚未載入：四層的骨架仍然畫出來，但一律灰態 ——「還沒點」不是故障。
        # ⚠️ 骨架照畫、內容留灰，使用者才看得出「這一頁有哪幾層、我還缺什麼」；
        #    整頁空白會讓「還沒載入」與「這頁壞了」長得一模一樣（鐵則 04）。
        st.markdown("### 🧾 ① 結論 — 現在該加碼還是防禦")
        not_ready("尚未載入總經資料，還沒有結論可以下。", where=_where_to_load())
        render_cards([
            {"title": _t, "state": STATE_NOT_READY,
             "note": "尚未載入總經資料。", "where": _where_to_load()}
            for _t in ("景氣位階", "波動與信用", "通膨與利率",
                       "熱錢動向", "極端風險警語", "新聞情緒")
        ])
        st.markdown("### 🧾 ② 依據 — 憑什麼這樣說")
        not_ready("尚未載入總經資料，五桶證據表還沒有內容。", where=_where_to_load())
        render_cards([
            {"title": _t, "state": STATE_NOT_READY,
             "note": "尚未載入總經資料。", "where": _where_to_load()}
            for _t in ("📐 建議資產水位", "⚡ ③ 例外", "🔍 ④ 可信度")
        ])
        _render_deferred_blocks()
        return

    # ══════════════════════════════════════════════════════════
    # 四層骨架（客戶 2026-09-04 拍板）—— 順序即閱讀順序，不要調換
    # ══════════════════════════════════════════════════════════
    # ⚠️ `calc_macro_phase(_ind)` 在這裡**算一次**，往下傳給層 1 與層 2。
    #    兩層各自呼叫一次不會出錯，但那會讓同一個位階分數有兩個計算點 ——
    #    日後任一邊換了輸入，畫面上「① 的燈」與「② 的長期桶」會無聲分岔（§2.1）。
    _phase = calc_macro_phase(_ind)
    # 🤖 AI 總結（層 4）要用同一份 phase，**存起來給它讀，不讓它自己再算一次**
    # —— 理由同上一段：兩個計算點會讓「① 的燈」與「AI 講的位階」無聲分岔。
    st.session_state[_SK_PHASE] = _phase

    # ── 層 1：🧾 ① 結論（全寬）───────────────────────────────
    _render_layer_conclusion(_ind, _phase)

    # ── 卡片網格：`ia` 線框那六張，插在 ① 與 ② 之間（拍板第 1 條）──
    # 鐵則 01：3 欄自適應網格（6 張卡 → 2 列 × 3 欄）
    render_cards([
        _card_phase(_ind),
        _card_vol_credit(_ind),
        _card_infl_rate(_ind),
        _card_hot_money(),
        _card_risk_radar(),
        _card_news(),
    ])

    # ── 層 2：🧾 ② 依據（全寬表）─────────────────────────────
    # ⚠️ 表格渲染失敗**不得擋掉整頁**，但也不得靜默 —— 走系統紅框，
    #    並讓層 3 收到一個「② 沒跑完」的哨兵，它才不會宣稱
    #    「讀數完整列在上方 ② 依據表」（那張表根本不在畫面上）。
    try:
        _ev = _render_layer_evidence(_ind, _phase)
    except Exception as _ev_e:              # noqa: BLE001 — §1：不靜默吞，下一行就印
        system_error("② 依據表渲染失敗", _ev_e,
                     hint="這一頁數字最密集的一塊沒畫出來；"
                          "下方三欄會因此少掉水位與可信度。")
        _ev = {"summary": None, "score": None, "prov": {},
               "sufficient": False, "level": ""}
    # 同 `_SK_PHASE`：層 4 的 🤖 AI 總結讀這一份，**不重算綜合分數**。
    # ⚠️ 上面那條 except 走過時存的是**哨兵**（score=None、sufficient=False），
    #    AI 快照會照實印「—」與「證據不足，未給等級」，不會拿一個算失敗的數字去講話。
    st.session_state[_SK_EV] = _ev

    # ── 層 3：📐 建議資產水位 ／ ⚡ ③ 例外 ／ 🔍 ④ 可信度（三欄）──
    # 鐵則 01：正好 3 張 → 一列 3 欄。**三張都吃層 2 算好的結果，不重算。**
    render_cards([
        _card_allocation(_ev),
        _card_exceptions(_ev),
        _card_credibility(_ind, _ev),
    ])

    # ── 層 4：🔎 詳細區（批次三）＋ 已拍板不做的燈號全表 ──
    _render_deferred_blocks()
