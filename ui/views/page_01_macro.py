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
4      🔎 詳細五時域                    尚未實作（批次三），誠實灰態
===== ============================== ==========================================

拍板同時解掉的三件事（**不要再當成待裁決**）
------------------------------------------
- **主要大表 ＝ ② 依據五桶證據表**；「總經燈號全表」**不做**（理由見
  :func:`_render_deferred_blocks`，那是資料層限制，不是版面偏好）。
- **新聞情緒與系統性風險 ＝ 灰態**：`services/**` 沒有任何新聞取數函式，
  依方針第 2 條不反向修底層 → 維持誠實灰態（見 :func:`_card_news`）。
- **建議資產水位不出核心／衛星**。⚠️ 這一條最容易做錯，展開寫在下面。

⛔ 「建議資產水位」為什麼是**股／債／現金**，不是核心／衛星
----------------------------------------------------------
`services.allocation_ladder.allocation_from_composite()` 回的是
`allocation = {equity, bond, cash}` —— **資產類別**（錢放在哪一種資產）。
而「核心／衛星」是**角色配置**（這筆錢在組合裡扮演什麼角色），
兩者是不同的分類軸，**全 repo 沒有任何由總經分數導出核心／衛星的服務**。
把 `equity` 改標成「核心」＝ 拿 A 的數字冒充 B 的答案，就是 §1 的造假。

⚠️ **兩份線框在這張卡上寫的不是同一件事**（實測，2026-09-05）：
`ia-wireframe.html` 該卡寫「核心 70 ／ 衛星 30」；
而本檔採用的骨架來源 `wireframe-macro-health.html` 該卡寫
「**股／債／現金 % ＋ 停利、加碼 Z 門檻**」—— **與服務回傳的欄位完全一致**。
也就是說：照拍板的骨架做，線框與服務**沒有衝突**；會衝突的是另一份線框。
客戶拍板第 3 條（核心／衛星不出這張卡）與骨架來源**同向**。

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
from typing import Any

import pandas as pd
import streamlit as st

from services.allocation_ladder import allocation_from_composite
from services.hot_money_service import fetch_hot_money_frames
from services.macro import calc_macro_phase, fetch_all_indicators, macro_action_light
from services.macro.composite_score import (
    calculate_composite_score,
    composite_verdict,
)
from services.risk_radar import detect_risk_radar, summarize_radar
from shared.evidence_support import is_sufficient
from shared.ui_control_labels import MACRO_LOAD_BTN_AGAIN, MACRO_LOAD_BTN_FIRST
from ui.helpers.ia import (
    STATE_BUSINESS,
    STATE_ERROR,
    STATE_NOT_READY,
    STATE_OK,
    applied_form,
    render_cards,
)
from ui.helpers.ia.empty_state import empty_state
from ui.helpers.macro.beginner_view import (
    build_evidence_footnotes,
    build_evidence_rows,
    compute_five_bucket_summary,
    render_evidence_table,
    split_evidence_footnotes,
)
from ui.helpers.render_state import business_alert, not_ready, system_error
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
_SK_RADAR: str = "v01_macro_risk_radar"
_FORM_KEY: str = "v01_macro_load_form"

#: 熱錢／匯率序列的回看天數。
#: ⚠️ **刻意用具名常數而不是畫面上的控制項**：兩份線框的 Form 欄位集互相衝突
#: （`ia` 有「觀察區間」下拉、`macro-health` 沒有、改成四個資料類別勾選框），
#: 欄位集**待客戶裁決**。在那之前把天數固定成一個具名值，
#: 功能照跑、但**不預先把任一份線框的欄位畫進畫面**。
_HOT_MONEY_WINDOW_DAYS: int = 180


def _where_to_load() -> str:
    """「去哪補」：指到本頁載入閘門裡的那顆送出鈕。

    ⚠️ 送出鈕的字是**動態**的（未載入 `📡 載入總經資料` ／ 已載入 `🔄 更新總經資料`），
       而灰態卡**只在未載入時出現**，故此處指名 :data:`MACRO_LOAD_BTN_FIRST`
       —— 指 `AGAIN` 版本等於指一個當下不存在的按鈕
       （這正是 `shared/ui_control_labels.py` docstring 記載的第一則實測錯誤）。
    ⚠️ 分頁名走 `where_to_find()`、按鈕名**內插 SSOT 常數**：兩者都不手抄，
       故本字串不可能因為改名而漂成死指路。
    """
    return f"{where_to_find('macro')} → 「{MACRO_LOAD_BTN_FIRST}」"


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
    try:
        st.session_state[_SK_RADAR] = summarize_radar(detect_risk_radar(fred_key))
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
    _level = str(_stash.get("level") or "")
    return {
        "title": "極端風險警語",
        "value": _level or "—",
        "note": (f"🔴 {_stash.get('red', 0)} ／ 🟡 {_stash.get('yellow', 0)} ／ "
                 f"🟢 {_stash.get('green', 0)} ／ ⬜ {_stash.get('gray', 0)}（共 10 燈）。"),
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
    `services/**` 沒有任何新聞取數函式，本頁不反向修底層。`None` 是
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
    _gate = (f"停利 Z ≥ {_al['stop_gain_z']:+.2f}、加碼 Z ≤ {_al['add_z']:+.2f}")
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

    ⚠️ 這張卡刻意報「**有幾項附得出來源**」：實測（2026-09-05）
    `services/macro/us_indicators.py::fetch_all_indicators` 的 28 個指標裡，
    只有 **1 個**（PMI）帶回 `source=`、**0 個**帶回 `fetched_at=`。
    血緣在 L1 是有寫的（`repositories/macro/fred.py` 會寫 `source` / `fetched_at`），
    **但 L2 沒有把它接下來**。這正是「總經燈號全表」做不出「來源」欄的原因
    （見 :func:`_render_deferred_blocks`）—— 同一個限制，在這裡誠實講一次。
    """
    _prov = ev.get("prov") or {}
    _n = int(_prov.get("n_indicators") or 0)
    _total = len([_k for _k, _v in (ind or {}).items() if isinstance(_v, dict)])
    _proxy = len([_k for _k, _v in (ind or {}).items()
                  if isinstance(_v, dict) and _v.get("is_proxy")])
    _srcs = len(_prov.get("sources") or [])
    if not _total:
        return {"title": "🔍 ④ 可信度", "state": STATE_NOT_READY,
                "note": "這一輪一項指標都沒取到。", "where": _where_to_load()}
    _note = [f"{_total} 項裡有 {_srcs} 項附得出資料來源，其餘沒有。"]
    if _proxy:
        _note.append(f"另有 {_proxy} 項是用替代來源估出來的，不是原始指標。")
    if not ev.get("sufficient"):
        _note.append("證據不足，上方沒有給等級與行動。")
    return {
        "title": "🔍 ④ 可信度",
        "value": f"{_n} / {_total} 項參與計算",
        "note": "".join(_note),
        # 附不出來源、或證據撐不住 → 這是「這個數字要打折看」的**業務警示**，
        # 不是系統故障（資料本身抓回來了）。鐵則 03。
        "state": (STATE_BUSINESS
                  if (not ev.get("sufficient") or _proxy) else STATE_OK),
    }


# ══════════════════════════════════════════════════════════════════
# 層 4 與已裁決不做的區塊：誠實灰態（鐵則 04：未完成不留白，也不畫空表格外框）
# ══════════════════════════════════════════════════════════════════
def _render_deferred_blocks() -> None:
    """把「本批沒做」與「已拍板不做」的區塊畫成灰態 —— **兩者理由不同，分開寫**。

    ⚠️ 這些**不是**失敗，也不是抓取失敗 → 一律灰態（`not_ready` 系），不上紅（鐵則 03）。
    """
    st.divider()
    empty_state(
        "🔎 詳細五時域：長期 → 中期 → 短線雷達 → 拐點 → AI 總結",
        "這五段要從舊版總經頁逐段重寫，份量大，已另立**批次三**處理",
        where=_where_to_load(),
        footer="批次三完成後，這五段會接在同一個載入閘門底下，取數機制現在就已經就位。",
    )
    empty_state(
        "總經燈號全表（值／位階／資料日期／來源）—— 已拍板不做",
        "「來源」欄目前 28 項指標裡只有 1 項帶得回來源標記（其餘會是「—」），"
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

    # ── 鐵則 02：載入閘門（按送出鈕才取數）──────────────────────────
    # ⚠️ 走 `applied_form()` 而不是自己寫 `st.form(` —— 後者會讓
    #    `tests/test_ui_rerun_contract.py::FORM_SITE_TOTAL`（精確 `==` 7）變 8 而轉紅。
    # ⚠️ `if _gate:` **必須寫在 `with` 之外**：送出鈕是在 `yield` 之後才建立的，
    #    區塊內判斷恆為 False（`ui/helpers/ia/gated_form.py` 的模組 docstring）。
    with applied_form(
            _FORM_KEY,
            submit_label=MACRO_LOAD_BTN_AGAIN if _loaded else MACRO_LOAD_BTN_FIRST,
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

    # ── 層 3：📐 建議資產水位 ／ ⚡ ③ 例外 ／ 🔍 ④ 可信度（三欄）──
    # 鐵則 01：正好 3 張 → 一列 3 欄。**三張都吃層 2 算好的結果，不重算。**
    render_cards([
        _card_allocation(_ev),
        _card_exceptions(_ev),
        _card_credibility(_ind, _ev),
    ])

    # ── 層 4：🔎 詳細五時域（批次三）＋ 已拍板不做的燈號全表 ──
    _render_deferred_blocks()
