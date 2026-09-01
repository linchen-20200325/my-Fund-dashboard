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
# 手法沿用既有先例 `repositories/fund/fx_and_main.py::get_latest_fx`
# (裸 `requests.get` 拿不到 `fetch_url` 的內建退避,檔內自己接同一套)。
from infra import source_backoff as _sb_hm


def _empty_flow_df() -> pd.DataFrame:
    """外資序列的空 DataFrame —— **帶正確 dtype**(date=datetime64[ns], 值=float64)。

    ⚠️ 為什麼要有這個建構子:`pd.DataFrame(columns=[...])` 造出來的兩欄都是
    **object** dtype,而成功路徑造出來的是 datetime64/float64。改版前這兩種空 df
    在不同分支各出現一次,**base 自己就不一致**;統一成帶型別的版本,
    `pd.concat` / `merge` 才不會在空集合上噴 dtype 警告。
    現行消費端(`ui/hot_money.py` / `services/hot_money_service.py`)全部先判
    `.empty` 才動欄位,實務影響為零 —— 但「回傳形狀逐字相同」這句話要為真,
    就不能留著這個差異(§1:記錄不可說謊)。
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
#   本檔現在會在應用層失敗時呼叫 `_sb_hm.record_failure(...)` 登記來源冷卻,
#   下一次 rerun 在 `fetch_url` **進場處**就被擋下、一個封包都不發。
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


_FINMIND_SOURCE_KEY = _sb_hm.source_key(_FINMIND_BASE)


def _finmind_failed(msg: str, kind: str = "server_error") -> _FetchFailed:
    """登記一次 FinMind **應用層**失敗(跨呼叫來源冷卻),再回傳例外物件供 `raise`。

    用法一律是 `raise _finmind_failed(...)` —— 記錄與拋出綁在同一個運算式裡,
    不可能只做一半(同 `infra/proxy.py::_note_failure` 把兩件事包成一個函式的理由)。

    ## ⚠️ 什麼時候**不**該呼叫它(這比什麼時候該呼叫更重要)

    · **`fetch_url` 已經回 None 的路徑** —— 那代表 `infra/proxy.py` 收尾時
      **已經**依 `_last_status` 呼叫過 `_note_failure`,分類由 SSOT
      (`shared/backoff_policy.py`)決定。在這裡再記一次,等於用本檔的猜測
      **覆蓋 SSOT 的裁決** —— 尤其 404/407 是 SSOT 明訂「刻意不退避」的,
      硬記下去會把「輪候選 URL」那類正常流程整個 host 打死。
    · **`fetch_url_with_retry` 自己拋例外的路徑** —— `fetch_url` 內部
      `except Exception: break` 已兜住所有連線層例外並記過失敗;能冒泡到本檔的
      幾乎只剩 `ImportError` 之類**與來源無關**的錯,替來源記一筆冷卻是罰錯人。

    → 也就是說:本 helper **只用在「HTTP 200 已經到手、但 payload 不可用」** 這一類,
      那正好是 `fetch_url` 看不到、而它已經 `_note_success()` 解除冷卻的那個缺口。

    ## 與憲法 §-2.A #1 那條「已知會誤判的 AST 規則」無關

    那條規則管的是 `infra.proxy.mark_fetch_failed_if_retryable` —— 它靠
    **thread-local 側車**(`pop_last_fail_kind`)取得分類,所以對「與 `fetch_url`
    之間有沒有分支」極度敏感。本 helper **不讀任何側車**:key 與 kind 都是
    明確參數,放在哪個分支裡都不會拿到別人的殘值。
    """
    _sb_hm.record_failure(_FINMIND_SOURCE_KEY, kind)
    return _FetchFailed(msg)


def _fetch_foreign_flow_series_uncached(
    days: int, token: str = "",
) -> tuple[pd.DataFrame, str]:
    """`fetch_foreign_flow_series` 的真實實作 —— **未被快取裝飾**。

    ⚠️ 取數失敗一律 `raise _finmind_failed(<err 字串>, <失敗分類>)`,**不**回
    (空 df, err):例外穿過 `@st.cache_data` 不入快取,同時登記來源冷卻讓下一次
    rerun 在 `fetch_url` 進場處被擋下(v3 §02「只快取成功結果;失敗時退避」)。

    **唯一仍會 `return`(＝仍被快取)的失敗分支**:body status 對應到
    `NO_COOLDOWN_KINDS`(`not_found` / `proxy_auth`)時 —— SSOT 明訂那兩種
    **刻意不退避**,此時若還 raise 就完全沒有節流器。判斷與 `repositories/macro/yf.py`
    對 404/407 的既有處置逐字同源(「`_ttl_cache` 是它們唯一的節流器」)。
    """
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
        _skip, _left, _kind = _sb_hm.should_skip(_FINMIND_SOURCE_KEY)
        if _skip:
            raise _FetchFailed(
                f"FinMind 來源退避冷卻中（前次失敗分類 {_kind}，剩餘約 {_left:.0f} 秒）："
                f"本次**未發出任何請求**，冷卻結束後會自動重試；"
                f"首次失敗的完整原因（含狀態碼 / API msg）見 [proxy] 與 [hot_money] log")
        raise _FetchFailed(
            "FinMind 無回應（fetch_url 全部重試失敗；狀態碼見 [proxy] log）")

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
        if _sb_hm.cooldown_for(_kind) <= 0:
            # `not_found` / `proxy_auth`:SSOT 明訂**刻意不退避** → 這裡若還 raise,
            # 就一個節流器都不剩(每次 rerun 真打一次)。改為 return、由 TTL 承擔,
            # 與 `repositories/macro/yf.py` 對 404/407 的既有判斷同源。
            print(f"[hot_money] ⚠️ FinMind {_api_status} 分類為 {_kind}(不退避)"
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
        raise _finmind_failed(
            f"FinMind 回 200 但 {_win_days} 天視窗內 0 筆資料"
            f"（視窗遠長於任何連假，屬上游異常；payload keys={sorted(_payload)[:6]}）")

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

    ⚠️ 回傳形狀與訊息內容與改版前**逐字相同**;變的只有「失敗結果不再進快取」。
    """
    try:
        return _cached_foreign_flow_series(days, token)
    except _FetchFailed as e:
        return _empty_flow_df(), str(e)


def _fetch_usdtwd_series_uncached(days: int) -> tuple[pd.DataFrame, str]:
    """`fetch_usdtwd_series` 的真實實作 —— **未被快取裝飾**。

    兩個失敗點都**無二義**(上游拋例外 / Yahoo 回空),一律 `raise _FetchFailed`。
    """
    try:
        from repositories.macro_repository import fetch_yf_close
        # range_ 換算：days ≤365 保持原行為(6mo/1y/2y);>365 才解鎖更長區間
        # (v19.427 配置回測需滿 NAV 重疊期,單向擴充不改既有 caller —— 現有 caller 全 days≤365)
        range_ = ("max" if days > 3650 else "10y" if days > 1825 else "5y" if days > 730
                  else "2y" if days > 365 else "1y" if days > 90 else "6mo")
        series = fetch_yf_close("USDTWD=X", range_=range_, interval="1d")
    except Exception as e:
        raise _FetchFailed(f"USDTWD 抓取失敗：{e}") from e

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

    ⚠️ 回傳形狀與訊息內容與改版前**逐字相同**;變的只有「失敗結果不再進快取」。
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
