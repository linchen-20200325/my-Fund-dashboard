"""① 市場總覽 —— 五分頁動線重構的第一頁（全新撰寫，非舊 `tab*.py` 的搬運）。

客戶方針（2026-09-04）第 1 條：UI 渲染層打掉重練，不改舊 `tab*.py`，從零撰寫全新 View。

⚠️ **本批刻意只做「兩份線框讀法一致」的部分 —— 整頁骨架未定，不選邊。**
`docs/wireframes/` 底下有**兩份都經客戶拍板、而且對 ① 的骨架互相衝突**的線框：

============================ ================================= =================================
項目                          `ia-wireframe.html` Tab 01        `wireframe-macro-health.html` ①重組後
============================ ================================= =================================
Form 欄位                     觀察區間 ＋ 資料源                 ☑ 總經/新聞/雷達/拐點 ＋ ☐ 強制重抓
首屏第一個結論區塊              資產水位建議（**全寬**卡）          ① 結論（`macro_action_light` 行動燈，全寬）
建議資產水位的位置              首屏、**全寬**                     在「② 依據」之後、**三欄之一**
主要大表                      總經燈號全表（17 項 × 值/位階/日期/來源）  ② 依據（五桶證據表）
卡片集合                      景氣位階/波動與信用/通膨與利率/熱錢/極端風險/新聞情緒  建議資產水位/③ 例外/④ 可信度
詳細區                        無                                🔎 詳細五時域（長期→中期→短線→拐點→AI）
============================ ================================= =================================

**這是真衝突，不是措辭差異**，已送客戶裁決。在答覆之前本檔只實作三件兩種讀法都成立的事：

1. **載入閘門 Form**（兩份都有；**欄位集在衝突清單裡 → 本批只做骨架與送出鈕**）；
2. **三欄自適應卡片網格本身**（兩份都有卡片網格，差別在它是不是整頁骨架）；
3. **三態顏色 / 空狀態三要素 / 指路 / 顏色來源**這些鐵律機制（與骨架無關）。

骨架相關的區塊**不畫、也不假裝完成**，改以畫面上可見的灰態佔位逐項列出（見
:func:`_render_deferred_blocks`）—— 依鐵則 04，未完成不得留白，也不得畫空表格外框。

線框的「**這裡不放什麼**」段落是**禁令**，本檔逐條遵守：
持有部位表現 → ②；單一基金深度研究 → ③；資料源健康度／快取狀態 → ⑤。

⛔ **不復活「總經羅盤」。** `ia-wireframe.html` 的「從哪裡搬來」寫了
   `app.py ─ 總經羅盤（目前內嵌在 app.py）`，但整條鏈已於 **2026-08-05 移除**
   （早於線框日期），且有反向守衛
   `tests/test_audit_20260805_tab1_summary.py::test_compass_modules_are_not_importable_at_all`。
   **線框那一行是錯的，照做會直接讓 CI 紅。** 三個羅盤讀數已併入 🎯 短線雷達。

四大鐵律的落點（本檔不自己實作任何一條，一律走既有共用元件）
------------------------------------------------------------
- **鐵則 01 三欄網格** → `ui.helpers.ia.render_cards`（內部走 `card_grid`，已登記於
  `tests/test_ui_grid_contract.py::GRID_EXEMPT_SITES`）。**本檔沒有任何 `st.columns` 呼叫**。
- **鐵則 02 Form 防重繪** → `ui.helpers.ia.applied_form`。**本檔沒有任何 `st.form(` 站點**
  —— 自己寫 `st.form` 會讓 `FORM_SITE_TOTAL`（精確 `==` 7）變 8 而轉紅。
- **鐵則 03 三態顏色** → `ui.helpers.render_state`（經 `ia.state_card` 的 `state=`）。
- **鐵則 04 空狀態三要素** → `ui.helpers.ia.empty_state`（住在 `ui/helpers/ia/empty_state.py`，
  **不是** `render_state.py`）。

⚠️ **本檔只呼叫 `services/**` 的 public 函式**（方針第 2 條「UI 與底層嚴格只讀對接」）。
   **不 import** `repositories/**`、`infra/**`、`requests`、`yfinance`、`gspread`。
   取不到的東西**一律做成灰態並誠實說明**，**不反向要求修改底層**。

⚠️ **金鑰讀 `os.environ`，不讀 `infra.config`。** `app.py::_load_keys()` 已把
   `FRED_API_KEY` 從 secrets 鏡射進 `os.environ`；舊頁用的也正是
   `os.environ.get("FRED_API_KEY", "")`。讀環境變數是 stdlib，不是資料層呼叫。
   ⚠️ **`FINMIND_TOKEN` 沒有被鏡射**（`_load_keys()` 只鏡射 FRED / GEMINI / ANTHROPIC / OPENAI），
   故本頁只在環境變數真的有值時才帶 token，否則帶空字串走 FinMind 匿名額度
   —— **真實的降級，不是造假**，並在卡片註腳寫明。
"""
from __future__ import annotations

import os
from typing import Any

import pandas as pd
import streamlit as st

from services.hot_money_service import fetch_hot_money_frames
from services.macro import calc_macro_phase, fetch_all_indicators
from services.risk_radar import detect_risk_radar, summarize_radar
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
from ui.helpers.render_state import not_ready, system_error
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
    return {
        "title": "熱錢動向",
        "value": f"外資 {_flow_sum:+,.0f}",
        "note": (f"近 {_HOT_MONEY_WINDOW_DAYS} 天累計（沿用來源單位，不代為換算成「億」）；"
                 f"{_fx_txt}。"),
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
# 待裁決區塊的誠實佔位（鐵則 04：未完成不留白，也不畫空表格外框）
# ══════════════════════════════════════════════════════════════════
def _render_deferred_blocks() -> None:
    """把「本批刻意沒做的區塊」逐項畫成灰態，不留白、不假裝完成。

    ⚠️ 這些**不是**失敗，也不是還沒抓到資料 —— 是**整頁骨架尚未裁決**，
       所以一律走灰態（`not_ready`），不上紅（鐵則 03）。
    """
    st.divider()
    st.markdown("#### 待客戶裁決後才動工的區塊")
    empty_state(
        "整頁骨架待裁決，以下區塊本批刻意未實作",
        "兩份客戶已拍板的線框對 ① 的骨架互相衝突（Form 欄位集、建議資產水位是全寬還是"
        "三欄之一、主要大表是「總經燈號全表」還是「② 依據五桶證據表」、卡片集合、"
        "以及是否保留「🔎 詳細五時域」）",
        where=_where_to_load(),
        footer="裁決後這幾塊會接在同一個載入閘門下，取數與三態機制本批已經就位。",
    )
    for _title, _why in (
        ("建議資產水位",
         "服務端已可用；**卡住的只有版面** —— 一份線框要全寬首屏，另一份要三欄之一。"
         "另有一處未裁決：線框寫「核心 70／衛星 30」，但服務回的是股／債／現金三分，"
         "全 repo 沒有由總經分數導出核心／衛星的服務。"),
        ("主要大表",
         "「總經燈號全表」與「② 依據五桶證據表」是兩份線框各自的主表，二選一未定。"),
        ("🔎 詳細五時域",
         "只有一份線框有（長期→中期→短線雷達→拐點→AI），是否保留未定。"),
    ):
        st.caption(f"⬜ {_title} — {_why}")


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
        # 尚未載入：卡片仍然畫出來，但一律灰態 ——「還沒點」不是故障。
        render_cards([
            {"title": _t, "state": STATE_NOT_READY,
             "note": "尚未載入總經資料。", "where": _where_to_load()}
            for _t in ("景氣位階", "波動與信用", "通膨與利率",
                       "熱錢動向", "極端風險警語", "新聞情緒")
        ])
        _render_deferred_blocks()
        return

    # ── 鐵則 01：3 欄自適應網格（6 張卡 → 2 列 × 3 欄）────────────────
    # ⚠️ 卡片**集合**在兩份線框之間並不一致（見模組 docstring 的對照表），
    #    這裡先用市場層、與持倉無關的那一組；最終集合待裁決。
    render_cards([
        _card_phase(_ind),
        _card_vol_credit(_ind),
        _card_infl_rate(_ind),
        _card_hot_money(),
        _card_risk_radar(),
        _card_news(),
    ])
    _render_deferred_blocks()
