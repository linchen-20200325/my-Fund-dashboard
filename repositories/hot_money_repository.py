# -*- coding: utf-8 -*-
"""repositories/hot_money_repository.py — 熱錢監測資料層(L1)

v19.196 P0-4-A 從根目錄 hot_money.py 拆出:
- `fetch_foreign_flow_series` — FinMind 外資買賣超 fetcher
- `fetch_usdtwd_series` — Yahoo USDTWD spot fetcher
- `_yf_series_to_df` — yfinance Series → 標準 DataFrame helper

純 I/O,無 UI 呼叫。EX-CACHE-1 例外:用 `@st.cache_data` 走 Streamlit Cloud 跨 session
cache,decorator-only,不做真 UI 呼叫(st.warning / st.markdown / st.session_state 等)。

UI 渲染(`render_hot_money_section`) + 純函式信號分類(`build_signals`)留在
`ui/hot_money.py`,本檔僅負責資料抓取與 schema 出口契約。
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd
import streamlit as st  # EX-CACHE-1:僅 @st.cache_data decorator,無真 UI 呼叫

from shared.ttls import TTL_10MIN, TTL_30MIN


# v19.223 P1-2:FinMind URL 收口至 shared/api_endpoints.py SSOT
from shared.api_endpoints import FINMIND_BASE as _FINMIND_BASE

# v19.374 B1:向 infra.cache(L0)下行註冊本檔 @st.cache_data fetcher,供 global_refresh_all
# 一併清。取代原 infra.cache 反向 import 本檔的 L0→L1 上行違憲(§8.2 硬規則 3)。
from infra.cache import register_st_cache

# v3 憲法 §02「失敗時退避,不連續轟炸來源」—— **應用層**失敗的退避登記。
#
# 為什麼非得在這一層手動登記(這是 2026-09-01 稽核抓到的洞):
# `infra/proxy.py::fetch_url` 只看 **HTTP 狀態碼** —— 一看到 200 就呼叫
# `_note_success()`,**解除**該 host 的冷卻。而 FinMind 的「額度用盡 / 缺欄 /
# 回非 JSON」**全都是 HTTP 200**(失敗寫在 body 裡)。於是把失敗改成 raise
# (不入快取)之後,這一層就**沒有任何節流器** —— 每次 rerun 都真的打一次上游。
# 實測(修好前,同一個 fake session 數 `sess.get` 次數):402 / 缺類別欄 /
# JSON 解析失敗三種情境 rerun#1..#3 各 1 次呼叫、`get_backoff_state()` 全空;
# 對照組真 HTTP 500 則有登記、第 2 次起直接跳過不打。
#
# ## ⚠️ 退避鍵是 **dataset 專屬**,不是 host —— 這一段是 2026-09-01 第二輪稽核的產物
#
# 第一版把這些失敗以 host 鍵(`api.finmindtrade.com`)登記,**實測誤殺了同一個 host
# 上完全健康的 NDC 景氣對策信號**:只讓外資 dataset 壞掉、NDC dataset 全程正常,
# `ui/helpers/macro/ndc.py::_fetch_ndc_score` 從 `score=31` 變成 `score=None`,
# 而且 `TaiwanBusinessIndicator` 那支查詢**一個封包都沒發出去**
# (`[proxy] 退避中,跳過不打`)。NDC 是活的 production 消費者
# (Tab1 資產水位 / 動態 Z 門檻、Tab2 再平衡訊號)。
#
# **為什麼 host 粒度在這裡是錯的**:`shared/backoff_policy.py` 末段自己寫了它成立的前提
# ——「403 / 429 / 連線失敗都是對方按 **host(+ 我方 IP)** 判定的……**URL 專屬**的失敗
# (404)已由上表排除在退避之外,故 host 粒度**不會誤殺**」。而本檔登記的是
# **dataset 專屬的 payload 形狀失敗**(JSON 壞 / 缺類別欄 / 0 筆 / 無 Foreign 類別),
# 正是該段刻意排除的那一類。base 上唯二的 `record_failure` 呼叫者
# (`infra/proxy.py`、`repositories/fund/fx_and_main.py`)全部是 **status-code / 連線層**;
# 本檔是第一個用 payload 形狀登記的,所以也必須是第一個把鍵縮小的。
#
# **與 `fx_and_main.py::get_latest_fx` 的關係,據實寫清楚(第一版把這句寫錯了)**:
# **機制**確實沿用它 —— 拿不到 `fetch_url` 內建退避的路徑,由 repository 自己接同一套,
# 且它同樣用「自己算出來的鍵」(`_erapi_key`)而不是共用一個全域鍵。
# 但**政策相反**:該檔對「HTTP 200 但 payload 不可用」就地寫著
# 「來源活著,不是來源的錯,**不退避**」,一次都沒登記。本檔選擇登記,
# 是因為這裡的 payload 失敗會**反覆**發生(dataset 改名 / 額度用盡 / 詞彙變更),
# 而 fx 那條有多來源 fallback chain 可以立刻接手、本檔沒有。
# ⚠️ **這是一個有意識的政策分歧,不是「沿用先例」** —— 第一版的檔頭把它寫成沿用,
# 那句話是假的(2026-09-01 稽核指出,本輪更正)。
#
# **未解的前提,誠實揭露(§-2 規則 6)**:FinMind 額度用盡到底是**真 HTTP 402**
# 還是 **HTTP 200 + body `{"status":402}`**,本 repo 的記載自相矛盾
# (`infra/proxy.py` 當它是真狀態碼;本檔與 `repositories/macro_tw_local_repository.py`
# 寫在 body),而**不實打 API 就無法判定**(會消耗使用者額度)。
# 本檔因此**不替 402 另開 host 粒度的特例**:
#   · 若是真 402 → `fetch_url` 既有路徑已經會用 host 粒度退避,不必本檔插手;
#   · 若是 200+body → NDC 自己有 `@_ttl_cache(TTL_15MIN)` 且**失敗 dict 也會被快取**,
#     最多每 15 分鐘白打一次,不構成「轟炸」。
# 用一個查不到的前提去換「多殺一個健康的消費者」的風險,不划算 ——
# 這正是第一版踩到的那顆雷。
# ⚠️ 另一種讀法存在(「402 用 host 鍵才對,額度是帳號級的」),本檔**不宣稱它錯**;
# 只是它**只在其中一個未被證實的假設下才有意義**,故不採用。
from infra import source_backoff as _sb_hm


def _empty_flow_df() -> pd.DataFrame:
    """外資序列的空 DataFrame —— **帶正確 dtype**(date=datetime64[ns], 值=float64)。

    ⚠️ 為什麼要有這個建構子:`pd.DataFrame(columns=[...])` 造出來的兩欄都是
    **object** dtype,而成功路徑造出來的是 datetime64/float64。改版前這兩種空 df
    在不同分支各出現一次,**base 自己就不一致**;統一成帶型別的版本,
    `pd.concat` / `merge` 才不會在空集合上噴 dtype 警告。
    ⚠️ **2026-09-01 更正(有意識的更正,不是漏刪)**:本段原本寫
    ~~「但『回傳形狀逐字相同』這句話要為真,就不能留著這個差異」~~ ——
    **那是把因果講反了**。統一 dtype **本身就是一個形狀變更**
    (改版前 7 個失敗分支全是 `object`,現在全是 typed;**實測 7/7 不同**),
    所以它不是「讓逐字相同成立」的手段,而是「逐字相同不成立」的**原因之一**。
    公開 wrapper 的 docstring 當時同步寫了那句假宣稱,兩處**互相引用、一起錯**。
    現行說法:**這是一個刻意的、已揭露的形狀變更**(變更清單見兩支公開
    `fetch_*` 的 docstring)。**改動本身的理由不變**:base 自己就不一致
    (一條 object、一條 typed),`pd.concat` / `merge` 在空集合上會噴 dtype 警告;
    現行消費端(`ui/hot_money.py` / `services/hot_money_service.py`)全部先判
    `.empty` 才動欄位,實務影響為零。
    """
    return pd.DataFrame({
        "date": pd.Series(dtype="datetime64[ns]"),
        "foreign_net_yi": pd.Series(dtype="float64"),
    })


def _empty_usdtwd_df() -> pd.DataFrame:
    """USDTWD 序列的空 DataFrame —— 帶正確 dtype,理由同 `_empty_flow_df`。"""
    return pd.DataFrame({
        "date": pd.Series(dtype="datetime64[ns]"),
        "usdtwd": pd.Series(dtype="float64"),
    })


def _yf_series_to_df(series: pd.Series) -> pd.DataFrame:
    """`fetch_yf_close` 回傳的 pd.Series → 標準 [date, usdtwd] DataFrame。

    空 series / 壞輸入 → 空 df。
    """
    if series is None or len(series) == 0:
        return _empty_usdtwd_df()
    out = pd.DataFrame({
        "date": pd.to_datetime(series.index).tz_localize(None) if (
            getattr(series.index, "tz", None) is not None
        ) else pd.to_datetime(series.index),
        "usdtwd": pd.to_numeric(series.values, errors="coerce"),
    }).dropna(subset=["usdtwd"])
    out = out[out["usdtwd"] > 0]
    return out.sort_values("date").reset_index(drop=True)


# ════════════════════════════════════════════════════════════════════
# v3 憲法 §02「只快取成功結果；失敗時退避，不連續轟炸來源」— 內拋外譯
# ════════════════════════════════════════════════════════════════════
# ## 這裡解的是什麼
#
# `@st.cache_data` **對「回傳值」快取、對「拋出的例外」不快取**
# (streamlit 1.59.2 實測:拋例外時上游每次都真的重跑;回空值時上游只跑一次)。
# 而本檔原本的慣例是「失敗 → 回 (空 DataFrame, err 字串)」——於是**一次上游瞬斷
# 會把那個空值鎖滿整個 TTL**(外資 30 分 / 匯率 10 分),使用者看到空白畫面,
# 按「強制重抓」也只是把同一份快取再讀一次。這違反 §2.4「超過 TTL 應重新抓取」,
# 而畫面上一個被鎖住的空值,正是 §1「錯誤的數字比沒有數字更危險」講的東西。
#
# ## 做法:內拋外譯(三層,公開介面一個字不變)
#
#   _fetch_*_uncached()        ← 失敗 raise;它**沒有**被裝飾,例外不會進快取
#          ↑
#   @st.cache_data _cached_*() ← 只有成功結果被存下來,例外直接穿過去
#          ↑
#   公開 fetch_*()             ← 接住例外,翻回既有回傳形狀 (df, err)
#
# 刻意**不**建共用機制:本批只有兩支,抽共用抽象是 §8.1 step 6「用不到的抽象」反例。
#
# ## ⚠️ 兩個「刻意不改」的失敗點,2026-09-01 已改成 raise(有意識的政策變更,不是漏刪)
#
# ~~`fetch_foreign_flow_series` 有 7 個失敗 return 點,只有 5 個改成 raise。
#   另外兩個 ——「無資料回傳(可能為非交易日區間)」與「FinMind 無 Foreign 類別資料」
#   —— **維持原樣、照舊快取**,理由是**空有兩義**:連假 / 週末**真的就是沒有資料**,
#   上游是好的。把它們改成 raise,等於每次 rerun 都去打一次 FinMind,
#   免費額度會被燒到 402 —— **用一個 bug 換一個更貴的 bug**。~~
#
# ⛔ **「空有兩義」這個理由被實測推翻(2026-09-01 稽核 + 本組複驗)**:
#
#   · production 的查詢視窗是 `days + 14` 天,而 `days` 來自 `ui/hot_money.py`
#     的 slider(`cc1.slider("回看天數", 60, 365, 180, step=30)`)
#     → **視窗恆為 74 ~ 379 個日曆日**。台灣最長連假約 9 天。
#     **一個 74 天以上的視窗回傳 `data: []`,不可能是「非交易日區間」** ——
#     它一定是上游出事(dataset 改名 / 權限變更 / 靜默壞掉)。
#     本 repo 的病史正是這個形狀:憲法 §2.1 記載 `fetch_tw_export_yoy` 曾掛在一個
#     FinMind **根本不存在的 dataset** 上,「恆無資料」活了好幾個版本沒人發現。
#   · `fdf.empty` 更弱:`rows` 非空代表這個區間**有交易日**;有 rows 卻沒有任何一筆
#     是 Foreign,那是**上游類別詞彙變更**,與隔壁 `name_col is None`
#     (本檔判為「schema 壞 → raise」)**是同一類事實,卻被反向處理**。
#   · 使用者看到的那句「無資料回傳(可能為非交易日區間)」,在**唯一會發生的情境下
#     是錯的歸因**,而且被鎖 30 分鐘 —— §1「錯誤的數字比沒有數字更危險」。
#   · 順帶一個可實測的誤判入口:任何 JSON 只要**沒有 `status` 鍵、也沒有 `data` 鍵**
#     (例如 `{"msg": "..."}`),`_api_status` 為 `None` → 通過狀態檢查 → `rows = []`
#     → 一樣被歸成「非交易日」並快取。
#
# ✅ **「改成 raise 會燒額度」那個擔憂本身是對的,但它的前提已經被同一批修掉了**:
#   本檔現在會在應用層失敗時呼叫 `_sb_hm.record_failure(...)` 登記冷卻,
#   下一次 rerun 在**本 fetcher 的進場處**就被擋下、一個封包都不發。
#   ⚠️ **2026-09-01 更正(有意識的更正,不是漏刪)**:本行原寫
#   ~~「在 `fetch_url` **進場處**就被擋下」~~ —— 自本輪把退避鍵改成 dataset 粒度之後
#   **那句話為假**:`fetch_url` 只查 host 鍵,查不到本檔登記的 dataset 鍵。
#   現行的攔截點是 `_fetch_foreign_flow_series_uncached` 開頭那一段
#   `should_skip(_FINMIND_DATASET_KEY)`。**「一個封包都不發」這個效果不變**,
#   變的是**誰擋的** —— 而那個差別正是「不會誤殺同 host 的 NDC」的來源。
#   有了退避,就可以誠實地 raise。**而原本那個理由若一致套用,會連本檔自己做的
#   402 raise 一起禁掉 —— 舊表述是選擇性套用了自己的判準。**
#
# `infra/cache.py` 論證的「空有兩義,**裝飾器**沒有資訊分辨」仍然成立;
# 差別在於**我們在這一層有資訊**(知道命中的是哪個分支),所以是**逐分支判**,
# 不是讓裝飾器猜 —— 只是逐分支判出來的答案,現在是「兩個都算失敗」。


class _FetchFailed(RuntimeError):
    """本檔內部的取數失敗訊號 —— 只在本檔拋、只在本檔接。

    攜帶的訊息**逐字**就是既有的 `err` 字串,公開 wrapper 原樣翻回 `(空 df, err)`,
    因此公開回傳形狀與訊息內容都不變(caller / 既有測試零改動)。

    ⚠️ 刻意窄型別:schema 契約違反(`validate_foreign_flow` 的 `SchemaError`)
    **不**被接住,照舊往上拋 —— 那是 §1 Fail Loud 要的行為,本次不動。
    """


# 本 fetcher 打的那一個 dataset(退避鍵要用的粒度,見檔頭)。
_FINMIND_DATASET = "TaiwanStockTotalInstitutionalInvestors"

# 「這個視窗長到不可能整段都是休市」的門檻(日曆日)。
# 台灣最長連假(春節)不超過兩週,30 天給了 2 倍以上餘裕。
# ⚠️ 這個常數存在的唯一理由是**歸因誠實**:`fetch_foreign_flow_series` 是**沒有下限的
# public API**,`days=5` → 視窗 19 天,那個長度**確實可能**整段落在連假裡。
# production 現行呼叫點全部 ≥ 60(`ui/hot_money.py` 的 slider 60~365、
# `refresh_hot_money_data(days=180)` 預設),所以這是**潛在**而非現存的誤歸因;
# 但一句「視窗遠長於任何連假」寫死在訊息裡,就是一句會在某些輸入下說謊的話。
_HOLIDAY_SAFE_WINDOW_DAYS = 30

# ⚠️ **兩個鍵,用途嚴格分開,不要混用**:
#   · `_FINMIND_HOST_KEY` —— `infra/proxy.py::fetch_url` 用的那一個(host 粒度)。
#     本檔**只讀不寫**:讀它是為了分辨「這次沒發請求是因為 host 在冷卻」;
#     寫它會殃及同 host 的其它 dataset(NDC 景氣對策信號),那正是本輪修的迴歸。
#   · `_FINMIND_DATASET_KEY` —— 本檔**自己登記、自己查**的 dataset 粒度鍵。
#     刻意帶 `finmind-dataset:` 前綴,讓它在 `get_backoff_state()` / log 裡
#     一眼看得出**不是 host**,而且與**實務上任何 host 鍵都不會相撞**。
#     ⚠️ **2026-09-01 第三輪更正(有意識的更正,不是漏刪 · 決策者:本修復組)**:
#     上一版寫 ~~「`source_key()` 產出的**一定是** netloc,**不可能**相撞」~~ ——
#     **那是結構性宣稱,而它為假**。`infra/source_backoff.py::source_key` 的實作是
#     `urlsplit(url).netloc.lower() **or** str(url)[:80]` —— netloc 為空時
#     **回退成原字串**。**實測**:
#         source_key("finmind-dataset:TaiwanStockTotalInstitutionalInvestors")
#         → 'finmind-dataset:TaiwanStockTotalInstitutionalInvestors'(原樣回傳)
#     也就是說,只要有人拿這個鍵去餵 `source_key()`,就會得到同一個字串。
#     **正確說法是「實務上不會」**(現行 `record_failure` 的呼叫者餵的都是真 URL),
#     **不是「結構上不可能」**。前綴仍然有價值(log 可讀性 + 實務隔離),
#     只是它**不是一道結構保證**,不該被後人當成一道保證來依賴。
#   ⚠️ dataset 鍵**不會**被 `fetch_url` 讀到(它只查 `source_key(url)`)——
#     所以本檔必須在進場處自己查一次,否則等於登記了一個沒有人看的旗標。
#     `infra/source_backoff.py` 的 `_STATE` 是 `dict[str, dict]`、
#     `record_failure/should_skip` 都只把 key 當不透明字串,故非 host 鍵是合法用法
#     (`fx_and_main.py` 同樣是「自己算鍵、自己查」,只是它的鍵剛好是 host)。
_FINMIND_HOST_KEY = _sb_hm.source_key(_FINMIND_BASE)
_FINMIND_DATASET_KEY = f"finmind-dataset:{_FINMIND_DATASET}"


def _finmind_failed(msg: str, kind: str = "server_error") -> _FetchFailed:
    """登記一次本 dataset 的**應用層**失敗(跨呼叫冷卻),再回傳例外物件供 `raise`。

    用法一律是 `raise _finmind_failed(...)` —— 記錄與拋出綁在同一個運算式裡,
    不可能只做一半(同 `infra/proxy.py::_note_failure` 把兩件事包成一個函式的理由)。

    ⚠️ **登記在 `_FINMIND_DATASET_KEY`,不是 host** —— 理由與實測見檔頭。
    一句話:本檔看到的是**這個 dataset 的 payload 壞了**,不是「FinMind 這台主機壞了」,
    拿 host 去退避會把同 host 的 NDC 一起關掉(第一版實測誤殺,`score` 31 → None)。

    ## ⚠️ 什麼時候**不**該呼叫它(這比什麼時候該呼叫更重要)

    · **`fetch_url` 已經回 None 的路徑** —— 那代表 `infra/proxy.py` 收尾時
      **已經**依 `_last_status` 呼叫過 `_note_failure`,分類由 SSOT
      (`shared/backoff_policy.py`)決定。在這裡再記一次,等於用本檔的猜測
      **覆蓋 SSOT 的裁決** —— 尤其 404/407 是 SSOT 明訂「刻意不退避」的,
      硬記下去會把「輪候選 URL」那類正常流程整個 host 打死。
    · **`fetch_url_with_retry` 自己拋例外的路徑** —— 能冒泡到本檔的多半是
      `ImportError` 之類**與來源無關**的錯,替來源記一筆冷卻是罰錯人。
      ⚠️ **2026-09-01 第三輪更正(有意識的更正,不是漏刪 · 決策者:本修復組)**:
      本項原本的辯護詞是 ~~「`fetch_url` 內部 `except Exception: break`
      **已兜住所有連線層例外**並記過失敗」~~ —— **那句話對 HTTP 200 路徑不成立**。
      **可自驗**:`infra/proxy.py` 在 `r.status_code == 200` 時
      `_note_success(_src_key)` 之後**立刻 `return r`**;
      body 是之後才由 `fund_fetcher.fetch_url_with_retry` 讀的
      (`resp.encoding = resp.apparent_encoding` 與 `resp.text.strip()`),
      **那兩行已經在 `fetch_url` 的 try 之外**。若解碼 / charset 偵測在那裡拋錯,
      例外會冒泡到本檔,而 `fetch_url` **已經先 `_note_success()` 解除了冷卻** ——
      也就是這一支**同時沒有 host 冷卻、沒有 dataset 冷卻、也不入快取**。
      ⛔ **這是一個結構性破洞,而不是可達的 bug**:`requests` 在 `stream=False`
      下於 `Session.send` 內就把 body 讀完了,`.text` 又以 `errors="replace"` 解碼,
      本輪**構造不出 production 可達的觸發點**。故**只更正辯護詞、登記,不為它改行為**
      —— 為一個構造不出來的路徑改行為,等於加一段沒有測試看得住的碼。
      ⚠️ **「構造不出」不等於「不可能」**,依 §-2 規則 6 這句只能當**待驗事項**。

    → 也就是說:本 helper **只用在「HTTP 200 已經到手、但 payload 不可用」** 這一類,
      那正好是 `fetch_url` 看不到、而它已經 `_note_success()` 解除冷卻的那個缺口。

    ## 本檔的節流不變式(目標狀態;⚠️ **已知有一個未達標的分支**,見末段)

    失敗**只在「確實有東西在節流」時才 raise**;沒有節流器就得 `return`,
    讓 `@st.cache_data` 的 TTL 承擔。三個節流器:
      1. 本 helper 剛登記的 **dataset 冷卻**(進場處會查) → raise;
      2. `fetch_url` 已登記的 **host 冷卻**(`r is None` 那一支會查) → raise;
      3. 兩者都沒有 → **return**,由 `TTL_30MIN` 節流。已知落在這一類的有:
         `NO_COOLDOWN_KINDS`(`not_found`/`proxy_auth`)、
         **`kind_for_status` 對 2xx/3xx 回的哨符 `""`**、
         或 200 但 body 空被 `fetch_url_with_retry` 轉成 None。
         ⚠️ **這是已知清單,不是窮舉**(同本段末句的但書)。
         ⚠️ **哨符那一項是 2026-09-01 第四輪補上的**:它是**第三輪自己新增的
         第三種 return 情形**(`if not _kind or ...`),當時**沒有進任何一份列舉** ——
         同一輪在別處剛寫下「刻意不寫『只有這兩個』」,卻沒把同一句但書
         套到隔壁的列舉上。**同一把尺只往被點名的那一格用,本 PR 第四次。**
    ⚠️ 少了第 3 條,那些分支會變成「每次 rerun 真打一次上游」——**比改版前更糟**
    (改版前失敗被快取,30 分鐘才打一次)。第一版只對 body-status 那一支想到這件事,
    `r is None` 那一支漏了,第二版補齊(2026-09-01)。

    ⛔ **不變式尚未貫徹,據實登記(2026-09-01 第三輪;有意識的揭露,不是漏想)**:
    上一版把這一段寫成「**三選一,不得有第四種**」,並在別處宣稱已「**逐一**走過每一條
    失敗分支」—— **兩句都太滿,已被本輪實測推翻**。目前**確知有兩個分支不滿足它**:
      · **本檔的 `except Exception as e: raise _FetchFailed(f"FinMind 抓取失敗:…")`**
        —— HTTP 200 之後才在 `fetch_url` 的 try 之外拋錯時,三個節流器一個都沒有
        (見上一段)。**結構性破洞、本輪構造不出 production 可達的觸發點,故只登記不改。**
      · ~~**`fetch_usdtwd_series` 的同型分支**~~ → **本輪已修**(改為 `return`,
        由 `TTL_10MIN` 承擔),實測見 `_fetch_usdtwd_series_uncached` 內註解。
    ⚠️ **本段刻意不寫「只有這兩個」** —— 那正是上一版犯的錯。這是**已知清單**,不是窮舉。

    ## 與憲法 §-2.A #1 那條「已知會誤判的 AST 規則」無關

    那條規則管的是 `infra.proxy.mark_fetch_failed_if_retryable` —— 它靠
    **thread-local 側車**(`pop_last_fail_kind`)取得分類,所以對「與 `fetch_url`
    之間有沒有分支」極度敏感。本 helper **不讀任何側車**:key 與 kind 都是
    明確參數,放在哪個分支裡都不會拿到別人的殘值。

    ⚠️ **本段講的是「那條 AST 規則對分支敏感」,不是「憲法把側車明載為脆弱」** ——
    `CLAUDE.md` 全檔沒有 `pop_last_fail_kind` 這個字串,§-2.A #1 記的是
    **總管自訂的 AST 規則本身寫錯**(3/3 現行消費者被誤判)。本 PR 前一版的
    **commit message 與 PR 描述**把它寫成「憲法明載為脆弱」,那句引用是假的
    (2026-09-01 稽核指出);**本 docstring 當時就沒有那樣寫,說錯的是那兩個載體**,
    更正登記在本輪的 commit message 與 PR 描述裡。
    """
    _sb_hm.record_failure(_FINMIND_DATASET_KEY, kind)
    return _FetchFailed(msg)


def _fetch_foreign_flow_series_uncached(
    days: int, token: str = "",
) -> tuple[pd.DataFrame, str]:
    """`fetch_foreign_flow_series` 的真實實作 —— **未被快取裝飾**。

    ⚠️ 取數失敗一律 `raise _finmind_failed(<err 字串>, <失敗分類>)`,**不**回
    (空 df, err):例外穿過 `@st.cache_data` 不入快取,同時登記 **dataset 粒度**的
    冷卻,讓下一次 rerun 在**本函式的進場處**被擋下
    (v3 §02「只快取成功結果;失敗時退避」)。
    ⚠️ 2026-09-01 第二輪更正:本段原寫 ~~「在 `fetch_url` 進場處被擋下」~~ ——
    退避鍵改成 dataset 粒度之後,`fetch_url` 查不到它(它只查 host 鍵),
    攔截點在本函式開頭。**「一個封包都不發」的效果不變,變的是誰擋的。**

    **仍會 `return`(＝仍被快取)的失敗分支**——一律是「**沒有任何節流器**」那一類
    (見 `_finmind_failed` 的節流不變式)。**以下是已知清單,刻意不寫成窮舉**
    (⚠️ 2026-09-01 第四輪補上第三項與這句但書:第三項是**第三輪自己新增的**,
     當時漏掉了 —— 而同一輪已在 `_finmind_failed` 寫下同一句但書,**沒有套過來**):
      · body status 落在 `NO_COOLDOWN_KINDS`(`not_found` / `proxy_auth`);
      · **body status 是 SSOT `kind_for_status` 對 2xx/3xx 回的哨符 `""`**
        —— 那是「**這不是失敗**」的意思,不是一個失敗分類;
        `cooldown_for("")` 會走「未知 kind 從寬」的 default(非 0),
        所以**不能只判 `cooldown_for(_kind) <= 0`**,必須先判 `not _kind`;
      · `r is None` 且 host **不在**冷卻期(404/407,或 `fetch_url_with_retry` 把
        「HTTP 200 但 body 空」轉成的 None —— 那一種 `fetch_url` 已經
        `_note_success()` 過了,誰都沒有記)。
    判斷與 `repositories/macro/yf.py` 對 404/407 的既有處置同源
    (「`_ttl_cache` 是它們唯一的節流器」)。
    """
    # ── dataset 退避進場檢查 ────────────────────────────────────────
    # ⚠️ 非做不可:退避鍵是 dataset 粒度(見檔頭),而 `fetch_url` 只查 host 鍵 ——
    #    少了這一段,`record_failure` 登記的東西**沒有任何人會讀**,
    #    等於「有登記、無節流」,每次 rerun 照樣真打一次上游。
    # ⚠️ 這裡刻意 `raise _FetchFailed(...)` 而**不是** `_finmind_failed(...)`:
    #    再記一次會把 `until` 往後推 → 只要使用者一直 rerun 就永遠解不開(餓死)。
    _ds_skip, _ds_left, _ds_kind = _sb_hm.should_skip(_FINMIND_DATASET_KEY)
    if _ds_skip:
        raise _FetchFailed(
            f"FinMind {_FINMIND_DATASET} 退避冷卻中"
            f"（前次失敗分類 {_ds_kind}，剩餘約 {_ds_left:.0f} 秒）："
            f"本次**未發出任何請求**，冷卻結束後會自動重試；"
            f"冷卻只針對這一個 dataset，同來源的其它查詢不受影響；"
            f"首次失敗的完整原因見 [hot_money] log")

    _win_days = int(days) + 14   # 實際查詢視窗(見下方 `not rows` 分支的理由)
    try:
        from fund_fetcher import fetch_url_with_retry
        end_d = _dt.date.today()
        start_d = end_d - _dt.timedelta(days=days + 14)
        params = {
            "dataset": "TaiwanStockTotalInstitutionalInvestors",
            "start_date": start_d.strftime("%Y-%m-%d"),
            "end_date":   end_d.strftime("%Y-%m-%d"),
        }
        if token:
            params["token"] = token
        r = fetch_url_with_retry(_FINMIND_BASE, params=params, timeout=15, retries=2)
    except Exception as e:
        # transport 失敗 = 上游問題,不可快取(下次 rerun 應重試)
        raise _FetchFailed(f"FinMind 抓取失敗：{e}") from e

    if r is None:
        # ⚠️ **這一支刻意不呼叫 `_finmind_failed`**:`fetch_url` 收尾時已依
        #    `_last_status` 記過失敗(或依 SSOT 刻意不記,如 404/407),再記一次
        #    等於覆蓋 SSOT 的裁決。理由全文見 `_finmind_failed` docstring。
        # ⚠️ 措辭同時更正:自本批起「來源正在退避冷卻期內」也會走到這裡
        #    (`fetch_url` 進場處直接回 None,**一次都沒重試**),
        #    舊句「全部重試失敗」在那個情境下是假的(§1「錯誤的歸因比沒有歸因更危險」)。
        #    兩種情況分開講,不合併成一句含糊的「無回應」。
        _skip, _left, _kind = _sb_hm.should_skip(_FINMIND_HOST_KEY)
        if _skip:
            raise _FetchFailed(
                f"FinMind 來源退避冷卻中（前次失敗分類 {_kind}，剩餘約 {_left:.0f} 秒）："
                f"本次**未發出任何請求**，冷卻結束後會自動重試；"
                f"首次失敗的完整原因（含狀態碼 / API msg）見 [proxy] 與 [hot_money] log")
        # 走到這裡 = `fetch_url` 看過這次失敗、卻**依 SSOT 刻意沒有退避**
        # (404 / 407),或者它根本判定成功(HTTP 200 但 body 空,
        # `fund_fetcher.fetch_url_with_retry` 尾端 `return resp if resp.text.strip() else None`
        # 會把它轉成 None,而 `fetch_url` 早已 `_note_success()`)。
        # **一個節流器都沒有 → 必須 return 讓 TTL_30MIN 接手**;此處若 raise,
        # 就變成每次 rerun 真打一次上游,比改版前(失敗被快取 30 分鐘)更糟。
        # 這與下面 body-status 落在 `NO_COOLDOWN_KINDS` 時的處置是同一條規則。
        # ⚠️ 措辭:原句的「若為 402 額度用盡,」已刪(**有意識的刪除,不是漏刪**;
        #    2026-09-01,決策者:本修復組)。理由是**它在這一支永遠為假**:
        #    真 402 會被 `fetch_url` 分類成 `server_error` 並登記 300s 冷卻
        #    → 上面那個 `_skip` 分支就先接走了;而 body-402(HTTP 200)根本走不到
        #    `r is None`。留著它等於指一個到不了的方向(§1 錯誤的歸因)。
        #    **保留**「狀態碼見 [proxy] log」——那句仍然為真且是唯一的線索出口。
        print(f"[hot_money] ⚠️ fetch_url 回 None 但來源未進退避"
              f"（多為 404/407 或 200 空 body）→ 本次失敗照舊入快取，由 TTL_30MIN 節流")
        # ⚠️ 訊息不得再寫「**全部重試失敗**」(2026-09-01 第三輪更正,
        #    **有意識的更正,不是漏刪** · 決策者:本修復組)。
        #    上一版把「若為 402 額度用盡,」刪掉時,**留下了同一個分支上另一句假話**:
        #    本支涵蓋的「HTTP 200 但 body 空」子情況裡,`fetch_url` **第一次就成功了**
        #    (它 `_note_success()` 過、回了 200),是 `fund_fetcher.fetch_url_with_retry`
        #    尾端 `return resp if resp.text.strip() else None` 才把它轉成 None ——
        #    **一次重試都沒有失敗**。上一版自己在下方 `print` 裡就寫了「多為 404/407
        #    或 200 空 body」,卻沒把同一把尺套到隔壁這行訊息上(本 PR 第三次同型)。
        #    現行措辭只講**可觀測的事實**(沒有可用回應 + 來源未進退避),不猜過程。
        return _empty_flow_df(), (
            "FinMind 無可用回應且來源未進退避（可能是 404/407 —— SSOT 明訂刻意不退避，"
            "或 HTTP 200 但 body 為空 —— 此時並未發生任何重試失敗）；"
            "實際狀態碼見 [proxy] log")

    try:
        _payload = r.json()
    except Exception as e:
        # HTTP 200 卻不是 JSON = 上游回了預期外的東西(gateway 錯誤頁 / body 截斷)。
        raise _finmind_failed(f"FinMind JSON 解析失敗：{e}") from e

    # 【額度用盡防偽裝 — 本次稽核母題】FinMind 免費額度用盡回
    # {"msg": "Requests reached the upper limit.", "status": 402}，**不帶 data 欄**。
    # 舊版 `.get("data", [])` 直接吐 [] → 被下面歸類成「無資料回傳（可能為非交易日
    # 區間）」，於是「額度用盡」偽裝成「今天沒開盤」，資料硬停在某一天卻無人察覺。
    # §1 Fail Loud：帶上真實 status 與 msg，不可含糊。
    _api_status = _payload.get("status")
    if _api_status not in (None, 200, "200"):
        _msg = str(_payload.get("msg", ""))[:80]
        print(f"[hot_money] ❌ FinMind {_api_status}: {_msg}")
        # 分類走 SSOT `infra.source_backoff.kind_for_status`(不自己另立一張對照表,
        # §2 SSOT)。FinMind 把 HTTP 語意的狀態碼寫在 body 裡,正是該函式的用途:
        # 402 → server_error(300s)、429 → rate_limited(1800s)、無法解析 → unreachable(60s,從寬)。
        try:
            _status_int = int(_api_status)
        except (TypeError, ValueError):
            _status_int = None
        _kind = _sb_hm.kind_for_status(_status_int)
        # ⚠️ `kind_for_status` 對 **2xx/3xx 回 `""`**,那是「**這不是失敗**」的哨符
        #    (SSOT 就地註解:`return ""   # 2xx/3xx 不是失敗`),**不是一個失敗分類**。
        #    上一版只判 `cooldown_for(_kind) <= 0`,而 `cooldown_for("")` 走的是
        #    「未知 kind 從寬」的 default → **60 > 0** → 於是 body status 若是
        #    201 / 304,本檔會**照樣退避並 `record_failure(key, "")`**,
        #    使用者看到「前次失敗分類 ,剩餘約 60 秒」(分類欄是空的)。
        #    **實測**:`kind_for_status(201)` → `''`;`cooldown_for('')` → `60`。
        #    本檔自陳「分類走 SSOT,不自己另立對照表」,**卻沒有接住 SSOT 的哨符** ——
        #    2026-09-01 第三輪補上(有意識的更正,不是漏刪 · 決策者:本修復組)。
        if not _kind or _sb_hm.cooldown_for(_kind) <= 0:
            # `not_found` / `proxy_auth`:SSOT 明訂**刻意不退避** → 這裡若還 raise,
            # 就一個節流器都不剩(每次 rerun 真打一次)。改為 return、由 TTL 承擔,
            # 與 `repositories/macro/yf.py` 對 404/407 的既有判斷同源。
            print(f"[hot_money] ⚠️ FinMind {_api_status} 分類為 "
                  f"{_kind or '(非失敗狀態碼,SSOT 哨符)'}(不退避)"
                  f" → 本次失敗照舊入快取,由 TTL_30MIN 節流")
            return _empty_flow_df(), f"FinMind {_api_status}: {_msg}"
        raise _finmind_failed(f"FinMind {_api_status}: {_msg}", _kind)

    rows = _payload.get("data", []) or []
    if not rows:
        # ⛔ 2026-09-01 由 return 改為 raise(有意識的政策變更,理由見檔頭大段註解)。
        #    關鍵事實:查詢視窗是 `days + 14`,而 production 的 days 來自 60~365 的 slider
        #    → 視窗恆 ≥ 74 天。**台灣沒有 74 天的連假**,所以這裡的空**不是**休市,
        #    是上游異常。舊訊息「可能為非交易日區間」在唯一會發生的情境下是錯的歸因。
        print(f"[hot_money] ❌ FinMind 回 200 但 {_win_days} 天視窗 0 筆;"
              f"payload keys={sorted(_payload)[:6]}")
        # ⚠️ 歸因隨**實際視窗長度**走,不寫死(2026-09-01 稽核指出:原句
        #    「視窗遠長於任何連假」對 `days=5`(視窗 19 天)是假的)。
        _why = ("視窗遠長於任何連假，屬上游異常"
                if _win_days >= _HOLIDAY_SAFE_WINDOW_DAYS
                else f"視窗僅 {_win_days} 天、短於連假安全門檻 "
                     f"{_HOLIDAY_SAFE_WINDOW_DAYS} 天，無法排除整段休市；"
                     f"也可能是上游異常")
        raise _finmind_failed(
            f"FinMind 回 200 但 {_win_days} 天視窗內 0 筆資料"
            f"（{_why}；payload keys={sorted(_payload)[:6]}）")

    df = pd.DataFrame(rows)
    name_col = next((c for c in ("name", "institutional_investors") if c in df.columns), None)
    if name_col is None:
        # schema 壞 = 上游回了預期外的形狀,屬異常,不可快取
        raise _finmind_failed("FinMind 缺類別欄")
    mask = df[name_col].astype(str).str.contains("Foreign|外資", case=False, na=False, regex=True)
    fdf = df.loc[mask].copy()
    if fdf.empty:
        # ⛔ 2026-09-01 由 return 改為 raise(有意識的政策變更):`rows` 非空代表這個
        #    區間**有交易日**;有 rows 卻沒有任何一筆是 Foreign,那是**上游類別詞彙
        #    變更**,與上面 `name_col is None`(判為 schema 壞 → raise)是同一類事實。
        #    舊寫法把同一類事實反向處理,是本檔判準不一致的地方。
        raise _finmind_failed(
            f"FinMind 無 Foreign 類別資料"
            f"（回了 {len(df)} 筆但無任何一筆命中 Foreign|外資，"
            f"上游類別詞彙可能已變更；實際類別={sorted(set(df[name_col].astype(str)))[:6]}）")

    fdf["net"] = pd.to_numeric(fdf["buy"], errors="coerce") - pd.to_numeric(fdf["sell"], errors="coerce")
    out = (fdf.groupby("date", as_index=False)["net"].sum()
              .assign(foreign_net_yi=lambda d: d["net"] / 1e8)
              .loc[:, ["date", "foreign_net_yi"]])
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values("date").reset_index(drop=True)
    # v19.151 F-PROV-1 phase 2:DataFrame.attrs 承載血緣(對齊 fetch_yf_close v19.83)
    out.attrs["source"] = "FinMind:TaiwanStockTotalInstitutionalInvestors"
    out.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    # v19.186 Pandera Phase B:出口 schema 驗證(date 升序唯一 / net 無 NaN / 單位合理)
    # 契約違反 = 上游資料異常,§1 Fail Loud 直接拋(不靜默回髒資料)
    try:
        from shared.schemas import validate_foreign_flow
        out = validate_foreign_flow(out)
    except ImportError:
        pass  # pandera 不在環境(極罕見,requirements 已 pin)→ 降級不驗
    return out, ""


@register_st_cache
@st.cache_data(ttl=TTL_30MIN, show_spinner=False)
def _cached_foreign_flow_series(days: int, token: str = "") -> tuple[pd.DataFrame, str]:
    """只快取成功結果:`_FetchFailed` 從這一層直接穿過去,不會被存下來。"""
    return _fetch_foreign_flow_series_uncached(days, token)


def fetch_foreign_flow_series(days: int, token: str = "") -> tuple[pd.DataFrame, str]:
    """抓最近 N 天外資買賣超（FinMind，沿用 tw_macro pattern + token kwarg）。

    Returns: (df[date, foreign_net_yi 億元], error_msg or "")

    ## ⚠️ 與改版前(`b5b0464`)的差異 —— 這一節是 2026-09-01 稽核的更正

    ~~「回傳形狀與訊息內容與改版前**逐字相同**;變的只有『失敗結果不再進快取』。」~~
    **這句話是假的,兩半都假**(**有意識的更正,不是漏刪** · 2026-09-01 · 決策者:本修復組)。
    它在 `bf9ddc2` 寫下的當天為真;`f5f4a1d` 改了訊息與 dtype 之後**沒有回頭改它**。
    **實測(base / 本分支各跑一次同一支探針,逐分支比對)**:

    | 差異 | 實測 |
    |---|---|
    | **dtype** | **7/7 個失敗分支都變了**:`object` → `datetime64[ns]` / `float64`(見 `_empty_flow_df`) |
    | **訊息** | **3/7 個變了**(其餘 4 個逐字未動) |

    三個訊息變更,逐條列出(**全部是刻意的,不是副作用**):
      1. `data: []` —— 舊「無資料回傳(可能為非交易日區間)」→ 新句帶出實際視窗天數與歸因。
         理由見檔頭大段註解(那個歸因在 production 的唯一情境下是錯的)。
      2. 無 Foreign 類別 —— 舊「FinMind 無 Foreign 類別資料」→ 新句多帶筆數與實際類別。
      3. `r is None` —— 舊句的「**若為 402 額度用盡,**」**已刪**;
         並新增一個「來源退避冷卻中」的變體(改版前不存在這個狀態)。
         刪除理由見該分支就地註解:真 402 會先被 host 冷卻分支接走、
         body-402 根本走不到這裡,那半句在這一支**永遠為假**。

    **行為變更(不是「只有不進快取」)**:
      · 失敗改為 `raise` 穿過 `@st.cache_data` → 失敗不再被鎖滿 TTL;
      · 應用層失敗會登記 **dataset 粒度**的來源冷卻(見檔頭);
      · **但**「完全沒有節流器」的失敗分支仍 `return`(＝仍被快取),
        見 `_finmind_failed` 的節流不變式。
    """
    try:
        return _cached_foreign_flow_series(days, token)
    except _FetchFailed as e:
        return _empty_flow_df(), str(e)


def _fetch_usdtwd_series_uncached(days: int) -> tuple[pd.DataFrame, str]:
    """`fetch_usdtwd_series` 的真實實作 —— **未被快取裝飾**。

    ⚠️ **2026-09-01 第三輪更正(有意識的政策變更,不是漏刪 · 決策者:本修復組)**:
    本段原寫 ~~「兩個失敗點都**無二義**(上游拋例外 / Yahoo 回空),
    一律 `raise _FetchFailed`」~~ —— **後半句自本輪起不成立,而且它一直是錯的判準**。

    現行處置**依 `_finmind_failed` 的節流不變式逐支判**(不看「有沒有二義」,
    看「**有沒有節流器**」):

    | 失敗點 | 有節流器嗎 | 處置 |
    |---|---|---|
    | `except` —— 上游拋例外(主要是 `validate_yf_close` 的 schema 違反) | **沒有**(`_ttl_cache` 不存例外、`fetch_url` 已 `_note_success`) | **`return`**,由 `TTL_10MIN` 承擔 |
    | `df.empty` —— Yahoo 回空 | **有**(`fetch_url` 的 host 冷卻,或 `fetch_yf_close` 的 `_ttl_cache` 存住那個未標記的空 series) | `raise _FetchFailed` |

    「無二義」講的是**這個失敗該不該算失敗**(它仍然成立,兩支都是真失敗);
    但**該不該 raise 從來不是由二義性決定的** —— 那是節流不變式管的事。
    上一版把兩個判準混在一句話裡,於是在沒有節流器的那一支照樣 raise。
    """
    try:
        from repositories.macro_repository import fetch_yf_close
        # range_ 換算：days ≤365 保持原行為(6mo/1y/2y);>365 才解鎖更長區間
        # (v19.427 配置回測需滿 NAV 重疊期,單向擴充不改既有 caller —— 現有 caller 全 days≤365)
        range_ = ("max" if days > 3650 else "10y" if days > 1825 else "5y" if days > 730
                  else "2y" if days > 365 else "1y" if days > 90 else "6mo")
        series = fetch_yf_close("USDTWD=X", range_=range_, interval="1d")
    except Exception as e:
        # ⛔ **這一支必須 `return`,不可 `raise`**(2026-09-01 第三輪修;
        #    **有意識的行為變更,不是漏刪** · 決策者:本修復組)——
        #    它就是 `_finmind_failed` 那條節流不變式的第 3 種情形:**一個節流器都沒有**。
        #
        #    **可達且已實測的觸發點**:`fetch_yf_close` 尾端的
        #    `validate_yf_close(s)` **刻意放在 parse 的 try-except 之外**
        #    (該檔就地註明:schema 違反是上游 bug,須當場 raise)。於是 Yahoo 回
        #    **HTTP 200 + 畸形 payload**(`close <= 0` / timestamp 重複或非遞增 / NaN)時
        #    會拋 `SchemaError`,而:
        #      · 上游的 `@_ttl_cache` **不存例外** → 它擋不住;
        #      · `fetch_url` 看到 200 已 `_note_success()` → **沒有 host 冷卻**;
        #      · 本檔這裡若 raise,又穿過 `@st.cache_data` → **沒有 TTL**。
        #    → **每次 rerun 都真打一次 Yahoo**。
        #
        #    **實測(同一支探針,fake session 數 `sess.get`,3 次 rerun 的每輪增量)**:
        #        b5b0464(base) : [1, 0, 0]      ← 失敗被快取,10 分鐘才打一次
        #        fe664ad       : [1, 1, 1]  ⛔
        #        7a45c89       : [1, 1, 1]  ⛔   ← 第二輪修了外資那側,**這一側漏了**
        #        本輪          : [1, 0, 0]  ✅   ← 回到 base 的節流強度
        #
        #    ⚠️ **本檔原本的辯護詞在這一支正好不成立**:docstring 寫
        #    「本支不登記任何來源冷卻(理由:上游 `fetch_yf_close` 已有自己的節流器)」——
        #    而 `_ttl_cache` **唯一擋不住的就是例外**,也就是這一支。
        #    上一版實測的 `yfnull` / `yfempty` / `http500` **三種都是回值**,
        #    剛好全部避開了唯一會 raise 的那一種。
        #
        #    ⚠️ **這不是把失敗藏起來**:錯誤訊息照樣往上帶(§1 Fail Loud),
        #    Tab1「強制重抓」照樣 `.clear()` 得掉;變的只有**節流由誰承擔**。
        #    這也**正好還原 base 的行為**(base 這一支本來就是 `return`)。
        print(f"[hot_money] ⚠️ USDTWD 取數拋例外且無任何來源冷卻"
              f"（多為 validate_yf_close 的 schema 違反）"
              f"→ 本次失敗照舊入快取，由 TTL_10MIN 節流：{e}")
        return _empty_usdtwd_df(), f"USDTWD 抓取失敗：{e}"

    df = _yf_series_to_df(series)
    if df.empty:
        # 匯率沒有「非交易日就真的沒有資料」的二義性問題:USDTWD 是連續報價序列,
        # 只要 range_ 蓋到過去數月,空 = 上游失敗或被限流,不是「本來就沒有」。
        # ⚠️ **這一支刻意不記來源冷卻**:上游 `fetch_yf_close` 自帶
        #    `@_ttl_cache(TTL_10MIN)`,而且它已經依 `mark_fetch_failed_if_retryable`
        #    做過「要不要快取這次失敗」的判斷 —— 節流器已經在那裡了。
        #    實測(fake session 數 sess.get):yfnull / yfempty / http500 三種情境
        #    本檔改版前後都是 rerun#1..#3 = 1 / 0 / 0,**零額外請求**。
        #    本檔在這裡再記一次 Yahoo 冷卻,只會把 VIX/DGS10/DXY/SPY 一起鎖住。
        raise _FetchFailed("USDTWD 無資料（Yahoo Chart API 失敗或被限流）")
    # 截取最近 days
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
    df = df[df["date"] >= cutoff].reset_index(drop=True)
    # v19.226 F-PROV-1 B5:provenance 補洞(§2.2 schema-additive)
    # tuple 第 2 元素是 error_msg 不是 source(audit 之前誤判),改 df.attrs 補
    df.attrs["source"] = "Yahoo:USDTWD=X:fetch_yf_close"
    df.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    return df, ""


@register_st_cache
@st.cache_data(ttl=TTL_10MIN, show_spinner=False)
def _cached_usdtwd_series(days: int) -> tuple[pd.DataFrame, str]:
    """只快取成功結果:`_FetchFailed` 從這一層直接穿過去,不會被存下來。"""
    return _fetch_usdtwd_series_uncached(days)


def fetch_usdtwd_series(days: int) -> tuple[pd.DataFrame, str]:
    """抓 USDTWD=X 時序（複用 macro_repository.fetch_yf_close + NAS proxy）。

    Returns: (df[date, usdtwd], error_msg or "")

    ## ⚠️ 與改版前(`b5b0464`)的差異 —— 2026-09-01 稽核更正

    ~~「回傳形狀與訊息內容與改版前**逐字相同**」~~ —— **訊息那半是真的,形狀那半是假的**
    (**有意識的更正,不是漏刪** · 2026-09-01 · 決策者:本修復組)。實測:
      · **訊息**:2/2 個失敗分支**逐字未動** ✅
      · **dtype**:失敗回傳的空 df 由 `object` 改為 `datetime64[ns]` / `float64` ❌
        ⚠️ **2026-09-01 第三輪更正(有意識的更正,不是漏刪 · 決策者:本修復組)**:
        上一版在這裡加了括號「(**`USDTWD 抓取失敗` 那一支**)」,**那個射程是錯的**。
        **實測(base / 本分支各跑同一支探針,逐子情境比對)**:

        | 分支 | 子情境 | base | 本分支 |
        |---|---|---|---|
        | `USDTWD 抓取失敗` | 上游拋例外 | `object` | **typed** ❌ 變了 |
        | `USDTWD 無資料`   | 上游回**空 series** | `object` | **typed** ❌ **也變了** |
        | `USDTWD 無資料`   | 上游回值但全被濾掉(NaN / ≤0) | typed | typed ✅ 未變 |

        成因:base 的 `_yf_series_to_df` 對**空輸入**回的是
        `pd.DataFrame(columns=[...])`(object),對「有值但濾光」回的是 typed ——
        **base 自己就不一致**;本分支統一走 `_empty_usdtwd_df()`(typed),
        於是**兩個分支都被影響到,只是後者只在其中一個子情境**。
        **「形狀那半是假的」這個結論不變**,錯的只有上一版括號裡的射程 ——
        而那正是本 PR 一路在犯的同一種錯:**更正一句話時,把它的射程也順手猜了一個**。
    行為變更:**Yahoo 回空**那一支改 `raise` 穿過 `@st.cache_data`,不再被鎖滿 TTL;
    **上游拋例外**那一支維持 `return`(＝仍被快取,與 base 相同),理由見下。
    **本支不登記任何來源冷卻** —— 但**原本的理由只對了一半**
    (2026-09-01 第三輪更正,**有意識的更正,不是漏刪** · 決策者:本修復組):
      · ~~「上游 `fetch_yf_close` 已有自己的節流器」~~ 對**回值**的失敗成立
        (`@_ttl_cache(TTL_10MIN)` 會把空 series 存下來);
      · 對**拋例外**的失敗**不成立** —— `_ttl_cache` **唯一擋不住的就是例外**,
        而那正是 `validate_yf_close` 走的路。故那一支改由本層的
        `@st.cache_data(TTL_10MIN)` 承擔(見 `_fetch_usdtwd_series_uncached` 內註解與實測)。
    「在這裡再記一次 Yahoo 冷卻會把 VIX/DGS10/DXY/SPY 一起鎖住」**這半句仍然成立**,
    也仍然是不登記來源冷卻的理由 —— 被權衡掉的只有「上游已經有節流器」那半句的射程。
    """
    try:
        return _cached_usdtwd_series(days)
    except _FetchFailed as e:
        return _empty_usdtwd_df(), str(e)


# ── `.clear` 相容性:公開名字必須保有 `.clear()` ────────────────────────
#
# ⚠️ **這段不是可有可無的糖衣,拿掉會靜默壞掉一個按鈕。**
# `services/macro/__init__.py::clear_tab1_macro_caches`(Tab1「強制重抓」)是這樣寫的:
#
#     for _fn in (fetch_foreign_flow_series, fetch_usdtwd_series):
#         try:
#             _fn.clear()
#             _stat["st_cache_cleared"] += 1
#         except Exception:
#             pass
#
# `.clear()` 包在 `except Exception: pass` 裡,而計數只在成功時才 +1。
# 拆函式之後公開名字若失去 `.clear`,會 `AttributeError` → 被 `pass` 吞掉 →
# `st_cache_cleared` 靜默停在 0 →「強制重抓」按鈕默默失效,**沒有任何人會發現**。
# `tests/test_hot_money.py::_patch_finmind` 的 `if hasattr(..., 'clear')` 同理。
#
# ⚠️ 為什麼是 `getattr` 而不是直接 `= _cached_x.clear`:
# `conftest.py::_stub_cache_decorator`(無 streamlit 的測試環境)回傳的是**原函式、
# 沒有 `.clear`** —— 無條件取用會在 **import 期**就 `AttributeError`,連鎖弄紅多個
# 測試檔。無快取 = 無需清,退化成 no-op 才是正確語意
# (與 `pool_repository` / `ui/helpers/macro/ndc.py` 既有的 try/except 降級慣例一致)。
def _bind_clear(public_fn, cached_fn) -> None:
    _c = getattr(cached_fn, "clear", None)
    if callable(_c):
        public_fn.clear = _c
        return

    def _noop_clear(_name=getattr(cached_fn, "__name__", "?")) -> None:
        """無快取環境的退化 `.clear()` —— **會留下痕跡,不是靜默 no-op**。

        ⚠️ 2026-09-01 補(稽核指出):`clear_tab1_macro_caches` 的
        `st_cache_cleared` 只在 `.clear()` 沒炸時 +1,所以一個沉默的 no-op 會讓
        那個數字由「**清掉幾個**」悄悄變成「**試了幾個**」—— 而那個數字會印給
        使用者看(`ui/tab1_macro` / `ui/sidebar` 的「st_cache {N} 條」)。
        本組實測認定這條在 production **不可達**(本檔是無條件 `import streamlit`,
        沒有真 streamlit 根本 import 不了;只有 conftest 的 pass-through stub
        走得到,而 stub 底下本來就沒有快取可清),但一旦哪天可達,
        這一行 print 是唯一會留下的訊號(§5 可觀測性)。
        """
        print(f"[hot_money] {_name}.clear() 為 no-op"
              f"（此環境的 cache_data 是 pass-through，沒有快取可清）")

    public_fn.clear = _noop_clear


_bind_clear(fetch_foreign_flow_series, _cached_foreign_flow_series)
_bind_clear(fetch_usdtwd_series, _cached_usdtwd_series)

# `__wrapped__`:讓 `inspect.getsource(fetch_*)` / `inspect.signature` 看穿到真實實作。
# `tests/test_provenance_phase2.py` 就是用 `inspect.getsource` 檢查 provenance attrs
# 有沒有被設 —— 指到實作而不是薄 wrapper,那個檢查才量得到它要量的東西。
fetch_foreign_flow_series.__wrapped__ = _fetch_foreign_flow_series_uncached
fetch_usdtwd_series.__wrapped__ = _fetch_usdtwd_series_uncached
