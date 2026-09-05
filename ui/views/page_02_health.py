"""② 持倉體檢 —— 五分頁動線重構的第二頁（全新撰寫，非舊 `ui/tab_fund_grp_health.py` 的搬運）。

客戶方針（2026-09-04）第 1 條：UI 渲染層打掉重練，不改舊 `tab*.py`，從零撰寫全新 View。
客戶方針（2026-09-05）：本頁**只做骨架 + 灰態**；三張卡與逐檔表的真內容**分批填**。

整頁骨架 —— 逐字取自已核准線框 `docs/wireframes/ia-wireframe.html` 的 **Tab 02**
------------------------------------------------------------------------------

===== ================================== ==========================================
順序   區塊                                版面
===== ================================== ==========================================
1      Form — 診斷條件（σ／回看窗／只看衛星）  `applied_form`，按「套用」才算
2      組合健康總分                          **全寬**
3      吃本金警示／衛星連續落後／影子基金重疊    3 欄自適應網格
4      逐檔體檢表（9 欄）                    **全寬 + 橫向捲動**
–      尚未設定持倉                          空狀態三要素（取代 2～4）
===== ================================== ==========================================

線框同時釘死了本頁的**職責邊界**，這一條比版面更要緊：

> 回答一個問題：**我手上這些，哪一檔出問題了？**
> **只診斷、不決策** —— 要換什麼、怎麼配，在 ④。

⛔ **因此本頁不放：換股建議、再平衡試算、任何「你應該買/賣什麼」的輸出。**
   線框「這裡不放什麼」逐字寫著「換股建議與再平衡試算 → 04（那是決策，不是診斷）」。
   下一批填內容時，看到 `services/switch_advisor.py` / `services/rotation.py`
   這類**建議**類服務要停手 —— 它們的落點是 ④，不是這裡。

⛔ **不修補舊 ②，也不委派它。** 舊實作（`ui/tab_fund_grp_health.py` 1,441 行
   ＋ `ui/helpers/fund_grp_health/` 一整包）依方針第 3 條會在五頁驗收完成後**整批拔除**。
   本檔**一行都不 import 它們** —— 每多一條委派，那一刻就多一處會斷頭。
   ⚠️ 這一點是 ① 的既有教訓：`ui/views/page_01_macro.py` 留了一條對
   `ui/tab1_macro_midcycle.py` 的委派，它自己的 docstring 就登記著
   「有效期到舊 tab 整批拔除為止」。**本檔一條都沒有。**

⛔ **波段觀測站（`ui/components/mk_dashboard.py`）本批完全不碰。**
   線框「從哪裡搬來」把它列進 ②，但客戶 2026-09-05 裁決：**搬，排在本頁上線之後的獨立批次**。
   本檔沒有任何對它的 import 或呼叫。

⚠️ **本頁本批尚未接進 `app.py`。** `app.py` 的 `with tab_health:` 仍呼叫舊的
   `render_fund_grp_health_tab()`，客戶明令「舊 ② 這批不動、不接線、不下架」。
   接線是下一批的事 —— 骨架先上線、CI 綠、再分批填內容。

Form 為什麼是本批唯一「真的做完」的一塊
--------------------------------------
線框在 Tab 02 的 Form 區塊就地點名了舊 ② 的缺陷：**「目前每拉一格全頁重繪，本次一併修掉」**。
這**不是新增需求，是四大鐵律之一**（鐵則 02），所以它必須由**建構**就解掉，
不能留給下一批 —— 一旦骨架先用裸 widget 寫成，下一批要改就是回頭重做。

**解法的結構（這一段是本檔最重要的設計決定）**：
widget 的**當下值**與**已套用值**是兩個不同的東西，本檔只讓下游讀後者
（:data:`_SK_APPLIED`）。使用者拖滑桿時 Streamlit 仍會 rerun（那是 `st.form` 擋不住的），
但 rerun 讀到的 `_SK_APPLIED` **沒有變** → 下游的取數與計算不會被觸發。
**只包 form 而不分離「已套用值」，省下的只有 widget 互動的 rerun，沒有省下重運算**
（`ui/helpers/ia/gated_form.py` 的模組 docstring 把這個陷阱寫得很清楚）。

⚠️ **`if _gate:` 一定要寫在 `with` 之外** —— 送出鈕是在 `yield` 之後才建立的，
   區塊內判斷恆為 `False`。

持股從哪裡來
------------
**一律從組合帶入**（客戶 2026-09-05 裁決：**不保留手動輸入基金代號**）。
來源是 `st.session_state["portfolio_funds"]` —— 由 ④ 資產配置／雲端讀回
（`ui/helpers/cloud_io.py`）寫入的既有 session 契約。
**讀 session 不是資料層呼叫**，不違反「資料只走 `services/**`」。

⚠️ **本批沒有任何 `services/**` 呼叫** —— 骨架階段沒有東西要算。
   下一批填內容時，取數一律走 `services/**` 的 public 函式
   （已實地確認存在的入口：`services.health` 的 `compute_4d_health` /
   `classify_eating_principal`、`services.portfolio_service.calc_holdings_overlap`），
   **不 import** `repositories/**`、`infra/**`、`requests`、`yfinance`、`gspread`。
   取不到的東西**一律做成灰態並誠實說明**，**不反向要求修改底層**。
   ⚠️ 上面那串入口是本組**實測看到的**，**不是**「這些就夠了」的宣稱 ——
   夠不夠要等真的去接才知道，本檔不預先斷言。

三態與空狀態：兩種灰的理由不同，文案必須分開
------------------------------------------
- **沒有持倉** → 線框指定的空狀態三要素，指路到 ④（使用者**照著做真的能解決**）。
- **有持倉、但這一塊的內容還沒填** → 「本頁分批上線」的灰態。
  ⚠️ 這兩句混成一句，會讓使用者以為「去 ④ 加了基金這裡就會出現」—— 不會。
  同樣的分岔在 ① 也做過一次（`page_01_macro.py::_detail_pending`）。

四大鐵律的落點（本檔不自己實作任何一條，一律走既有共用元件）
------------------------------------------------------------
- **鐵則 01 三欄網格** → `ui.helpers.ia.render_cards`。**本檔沒有任何 `st.columns` 呼叫**
  —— 自己寫會讓 `tests/test_ui_grid_contract.py::GRID_EXEMPT_CALL_TOTAL`（精確 `==` 90）轉紅。
- **鐵則 02 Form 防重繪** → `ui.helpers.ia.applied_form`。**本檔沒有任何 `st.form(` 站點**
  —— 自己寫會讓 `tests/test_ui_rerun_contract.py::FORM_SITE_TOTAL`（精確 `==` 7）轉紅。
- **鐵則 03 三態顏色** → `ui.helpers.render_state`（經 `ia.state_card` 的 `state=`）。
- **鐵則 04 空狀態三要素** → `ui.helpers.ia.empty_state` ＋ `wide_table` 的空分支。
- **指路一律走 `ui.helpers.story_nav`**，不手抄分頁名
  （`tests/test_wpf_five_tab_wiring.py` 兩條規則會擋）。
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from ui.helpers.ia import (
    STATE_NOT_READY,
    applied_form,
    render_cards,
    wide_table,
)
from ui.helpers.ia.empty_state import empty_state
from ui.helpers.render_state import not_ready, safe_section
from ui.helpers.story_nav import render_story_nav, tab_label, where_to_find

# ── session 鍵名（本檔自己的命名空間）────────────────────────────────────────
# ⚠️ 刻意**不**沿用舊 ② 的鍵：舊頁依方針第 3 條仍在磁碟上、且仍接在 `app.py`，
#    共用鍵會讓兩套 View 互相覆寫對方的狀態，而 payload 形狀並不相同。
_FORM_KEY: str = "v02_health_filter_form"
#: **已套用**的診斷條件（不是 widget 當下值）。下游只准讀這個 —— 理由見模組 docstring。
_SK_APPLIED: str = "v02_health_applied_filters"

#: 使用者的持股來源。既有 session 契約，由 ④ 資產配置／`ui/helpers/cloud_io.py` 寫入。
#: ⚠️ 這個字串是**別人定義**的鍵名，本檔只讀不寫 —— 不要在這裡「順手改個好名字」。
_SK_PORTFOLIO: str = "portfolio_funds"

# ── 診斷條件的預設值（線框 Tab 02 逐字）──────────────────────────────────
#: 線框：「輪動門檻　σ ±1.0」。
_DEFAULT_SIGMA: float = 1.0
#: 線框：「回看窗　12 個月」。
_DEFAULT_WINDOW_MONTHS: int = 12
#: 線框：「只看衛星　☐」（預設不勾）。
_DEFAULT_SATELLITE_ONLY: bool = False

#: 滑桿範圍。⚠️ 線框只給了預設值 **±1.0**，**沒有給範圍** ——
#: 這裡的 0.5～2.0 是本組挑的，`σ` 在 0 附近沒有鑑別度、超過 2 幾乎不會觸發。
#: **這是實作細節不是業務規格**，若客戶要別的範圍改這兩個常數即可。
_SIGMA_MIN: float = 0.5
_SIGMA_MAX: float = 2.0
_SIGMA_STEP: float = 0.1
_WINDOW_MIN: int = 1
_WINDOW_MAX: int = 36

#: 逐檔體檢表的欄位 —— **線框 Tab 02 逐字**：
#: 「代碼 / 名稱 / 幣別 / 近 1 年 / Sharpe / 最大回撤 / 配息覆蓋 / 五桶評等 / 資料日期」。
#: ⚠️ 定成常數而不是散在下一批的程式碼裡，是為了讓「欄位少了一欄」看得見
#: （`tests/test_wf02_health_skeleton.py` 釘住它是 9 欄且逐字相符）。
#: ⚠️ **下一批填內容時，任一欄取不到 → 那一格走灰態，不得從別的欄位湊一個數字充數**（§1）。
HEALTH_TABLE_COLUMNS: tuple[str, ...] = (
    "代碼", "名稱", "幣別", "近 1 年", "Sharpe",
    "最大回撤", "配息覆蓋", "五桶評等", "資料日期",
)

#: 本批共用的灰態理由。**只有一句話**，因為它會出現在四個地方，
#: 四個地方各寫一句就是四份會各自漂移的真相源（§2.1）。
_PENDING_NOTE: str = "本頁分批上線，這一塊的內容還沒接上"


def _pending_where(block: str) -> str:
    """「內容還沒填」這種灰態的指路。

    ⚠️ **這種灰跟「沒有持倉」那種灰不一樣，使用者沒有地方可以去** ——
    所以指路能給的最誠實的東西是「**現在哪一塊是完整的**」，而不是假裝有個開關可以按。
    同樣的處理在 ① 做過一次（`page_01_macro.py::_detail_pending`）。

    ⚠️ 分頁名走 `where_to_find()`，**不手抄**；區塊名由呼叫端傳進來，
    不在這裡再抄一份（手抄的指路在本 repo 已經指錯三次）。
    """
    return f"{where_to_find('health')} → 目前只有「{block}」是完整的"


def _holdings() -> list[dict[str, Any]]:
    """使用者**目前持有**的基金。

    讀既有 session 契約 `portfolio_funds`（由 ④ 寫入），**不自己取數**。

    ⚠️ **`loaded` 過濾是刻意的**：那份清單裡會有「已列入但 NAV 還沒抓回來」
    與「抓取失敗」的項目（`ui/helpers/portfolio/load.py` 寫入 `loaded` / `load_error`
    兩個旗標）。拿那些去算體檢分數，等於用不完整的資料生一個看起來完整的結論（§1）。
    ⚠️ **回傳空 list 有兩種原因**（完全沒設定 vs 設定了但都還沒載入成功），
    本批的骨架**不區分**它們 —— 因為兩者的下一步都是先去 ④。
    下一批若要分開講，這裡是分岔點。
    """
    _raw = st.session_state.get(_SK_PORTFOLIO) or []
    if not isinstance(_raw, list):
        return []
    return [_f for _f in _raw
            if isinstance(_f, dict) and _f.get("loaded") and not _f.get("load_error")]


def _applied_filters() -> dict[str, Any]:
    """**已套用**的診斷條件；沒按過「套用」就是線框寫的那組預設值。

    ⚠️ 下游一律讀這個，**不要讀 widget 的回傳值** —— 讀了就等於沒有 form
    （鐵則 02 的重點不是「有沒有 form」，是「重運算有沒有被 gate 住」）。
    """
    _cur = st.session_state.get(_SK_APPLIED)
    if isinstance(_cur, dict):
        return _cur
    return {
        "sigma": _DEFAULT_SIGMA,
        "window_months": _DEFAULT_WINDOW_MONTHS,
        "satellite_only": _DEFAULT_SATELLITE_ONLY,
    }


def _render_filter_form() -> None:
    """區塊 1｜Form — 診斷條件。**本批唯一做完的一塊。**

    線框 Tab 02 逐字：「輪動門檻　σ ±1.0／回看窗　12 個月／只看衛星　☐／套用」。

    ⚠️ **沒有基金代號輸入框，這是客戶 2026-09-05 的裁決，不是漏做**：
    持股一律從組合帶入（見 :func:`_holdings`）。日後若有人覺得「加個代號框比較方便」，
    那是**把 ③ 標的探索的職責搬進來**，線框把「我沒持有的基金」明列在「這裡不放什麼」。
    """
    _cur = _applied_filters()
    with applied_form(_FORM_KEY) as _gate:
        st.caption("條件改完按「套用」才重算 —— 拖滑桿的當下不會觸發任何取數。")
        _sigma = st.slider(
            "輪動門檻　σ", min_value=_SIGMA_MIN, max_value=_SIGMA_MAX,
            value=float(_cur["sigma"]), step=_SIGMA_STEP,
            help="偏離同類均值幾個標準差才算異常。",
        )
        _window = st.number_input(
            "回看窗（月）", min_value=_WINDOW_MIN, max_value=_WINDOW_MAX,
            value=int(_cur["window_months"]), step=1,
            help="往回看多久的績效來判定。",
        )
        _satellite_only = st.checkbox(
            "只看衛星", value=bool(_cur["satellite_only"]),
            help="勾選後只診斷衛星部位，核心部位不列入。",
        )

    # ⚠️ `if _gate:` 必須在 `with` **之外**（送出鈕在 `yield` 之後才建立）。
    if _gate:
        st.session_state[_SK_APPLIED] = {
            "sigma": float(_sigma),
            "window_months": int(_window),
            "satellite_only": bool(_satellite_only),
        }


def _render_no_holdings() -> None:
    """線框指定的空狀態 —— **三要素逐字取自線框**，這一段不要「潤飾」。

    線框 Tab 02：
      標題「尚未設定持倉」／缺什麼「還沒有任何保單或扣款標的」／
      去哪補「到『04 資產配置 › 保單與扣款標的』新增」／
      footer「補完後這裡會自動出現逐檔體檢」。

    ⚠️ **「去哪補」不照線框那句字面抄，走 `where_to_find('pf_add')`。**
    線框寫的是「保單與扣款標的」，而 SSOT（`ui/helpers/story_nav.py`）現行的區塊名是
    「➕ 加入與管理基金」—— **兩者不一致**。抄線框會產生第二份真相源，
    下一次區塊改名就指錯（本 repo 這個形狀已經死過三次）。
    **線框定的是「指到哪個分區」，不是「那個分區叫什麼名字」。**
    """
    empty_state(
        "尚未設定持倉",
        "還沒有任何保單或扣款標的",
        where=where_to_find("pf_add"),
        footer="補完後這裡會自動出現逐檔體檢。",
    )


def _render_health_score() -> None:
    """區塊 2｜組合健康總分（**全寬**）。本批灰態。

    線框：「72 ／ 100　五桶評等加權。下方三張卡是扣分最重的三項，點進去看逐檔。」

    ⛔ **不畫那個 72。** 線框裡的數字是**示意**，不是資料。填一個看起來合理的分數
    正是 §1 點名最危險的那種造假 —— 它會被使用者拿去做決定，而且完全看不出是假的。
    """
    st.markdown("#### 組合健康總分")
    not_ready(f"{_PENDING_NOTE}（五桶評等加權總分）。", where=_pending_where("診斷條件"))


def _render_alert_cards() -> None:
    """區塊 3｜三張卡（3 欄自適應網格）。本批三張全灰。

    線框 Tab 02 三張卡逐字：
      「吃本金警示／2 檔／配息覆蓋率低於 1.0，實際在配回本金。」（業務警示）
      「衛星連續落後／1 檔／連兩季落後對比基準（SPY / QQQ）。」（業務警示）
      「影子基金重疊／相似度 0.78／兩檔持股高度重疊，分散效果打折。」（業務警示）

    ⚠️ **線框把三張都標成「業務警示」，那是因為線框在示範「有壞消息時長什麼樣」。**
    真接上之後，**沒有壞消息就該是 `STATE_OK`**，不是永遠紅著 ——
    三態的選擇由**資料**決定，不是由線框的示意圖決定（鐵則 03：`state` 決定視覺，不是文案）。

    ⛔ **本批不畫「2 檔」「1 檔」「0.78」** —— 同 :func:`_render_health_score`，那些是示意值。
    """
    _where = _pending_where("診斷條件")
    render_cards([
        {"title": "吃本金警示", "state": STATE_NOT_READY,
         "note": f"{_PENDING_NOTE}（配息覆蓋率是否低於 1.0）。", "where": _where},
        {"title": "衛星連續落後", "state": STATE_NOT_READY,
         "note": f"{_PENDING_NOTE}（是否連兩季落後對比基準）。", "where": _where},
        {"title": "影子基金重疊", "state": STATE_NOT_READY,
         "note": f"{_PENDING_NOTE}（持股重疊度）。", "where": _where},
    ])


def _render_health_table() -> None:
    """區塊 4｜逐檔體檢表（**全寬 + 橫向捲動**）。本批無列資料 → 走空狀態。

    線框：「欄位多，全寬橫向捲動」「不畫空表格外框」。

    ⚠️ **走 `wide_table()` 而不是 `st.dataframe()`**：空資料不畫空框這件事，
    只有收在唯一的大表入口才有機械上的著力點（`ui/helpers/ia/layout.py` 的 docstring）。
    本批傳空 list，它會走 `empty_state()` 分支 —— **這不是繞過，這就是它設計的用法。**

    ⚠️ **這張表不得放進 `render_cards()` 的欄位裡**（9 欄在 1/3 寬會被壓成無法閱讀），
    所以它是頁面層級的直接呼叫，不在任何網格內。
    """
    st.markdown("#### 逐檔體檢表")
    st.caption("　/　".join(HEALTH_TABLE_COLUMNS))
    wide_table(
        [],
        empty_title="逐檔體檢還沒有可顯示的列",
        empty_missing=f"{_PENDING_NOTE}（每一檔的績效、風險與配息覆蓋）。",
        empty_where=_pending_where("診斷條件"),
    )


def render_holdings_health() -> None:
    """渲染「② 持倉體檢」整頁。

    ⚠️ **本批尚未接進 `app.py`**（客戶明令舊 ② 不動、不接線、不下架），
    所以現在**沒有 production caller** —— 這是**刻意的中間狀態**，不是漏接。
    接線是下一批的事。

    ⚠️ **區塊之間走 `safe_section()` 隔離**：`st.tabs` 是單次 run 渲染全部分頁，
    任一區塊拋未捕捉例外會**中止整個 script**，其後所有分頁空白。
    `app.py` 已有分頁級的 try，但那是「一頁失敗不連坐其他頁」；
    區塊級隔離要的是「一塊失敗不連坐同一頁的其他塊」。
    ⚠️ `safe_section` **不吞例外**（§1）：它走 `system_error()` 顯式紅框 ＋ traceback。
    """
    st.markdown(f"## {tab_label('health')}")
    render_story_nav("health")
    # 線框 Tab 02 的職責宣告，逐字。**只診斷不決策**這半句是邊界，不是文案。
    st.caption("回答一個問題：**我手上這些，哪一檔出問題了？** "
               f"只診斷、不決策 —— 要換什麼、怎麼配，在 {where_to_find('pf_add')}。")

    safe_section("診斷條件", _render_filter_form)

    if not _holdings():
        # 沒有持倉時，下面三塊沒有任何東西可以診斷 —— 直接走空狀態，
        # **不要**把三塊各印一次灰（那會變成四份在講同一件事的灰字）。
        safe_section("尚未設定持倉", _render_no_holdings)
        return

    safe_section("組合健康總分", _render_health_score)
    safe_section("警示卡片", _render_alert_cards)
    safe_section("逐檔體檢表", _render_health_table)
