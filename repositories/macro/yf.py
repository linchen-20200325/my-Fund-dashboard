"""repositories/macro/yf.py — Yahoo Finance Chart API 抓取(B1 拆自 macro_repository v19.205).

從原 1078 LOC god module 拆出:
- YF_CHART_BASE 常數
- fetch_yf_close(單 ticker DatetimeIndex Series)
- fetch_yf_latest(多 ticker 最新值 dict)
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from infra.proxy import fetch_url, mark_fetch_failed_if_retryable
from fund_fetcher import _ttl_cache, register_cache
from shared.ttls import TTL_5MIN, TTL_10MIN

YF_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"


@register_cache
@_ttl_cache(ttl_sec=TTL_10MIN, maxsize=64)   # v18.58: Yahoo Chart，渲染同一 ticker 多次免重抓
def fetch_yf_close(ticker: str, range_: str = "2y", interval: str = "1d") -> pd.Series:
    """
    抓取 Yahoo Finance 收盤價序列(透過 NAS proxy 直打 Chart API)。

    為何不用 yfinance:yfinance 預設不走 proxy,且常因雲端節點 IP
    被 Yahoo 限流(429)而失敗。直接呼叫 Chart REST API + NAS 中繼,
    取得台灣 IP 出口,穩定許多。

    Returns
    -------
    pd.Series  index 為 DatetimeIndex,value 為收盤價。失敗時回傳空 Series。
               provenance(F-PROV-1 v19.83):成功時 `s.attrs` 含
               `source="Yahoo:<ticker>"` + `fetched_at=UTC ISO`。

    快取語意(2026-08-31,v3 §02「只快取成功結果」):
        **`fetch_url` 回 None(連不上/逾時/403/429/5xx)時回傳的空 Series 帶
        `mark_fetch_failed` 標記 → 不入 `@_ttl_cache`**,下次呼叫真的重試;
        重試是否真的出門由 `infra.source_backoff` 的來源冷卻決定,故不會轟炸來源。
        **HTTP 200 但序列為空(該區間真的沒有觀測)不標記,照常快取** —— 那是答案,
        不是失敗。兩者回傳值長得一模一樣,差別只在這個標記,**裝飾器不猜**(§1)。

        ⚠️ **2026-08-31 修正（有意識的更正，不是漏刪）**:404(`not_found`) 與
        407(`proxy_auth`)**不標記、照舊快取** —— `shared/backoff_policy.py` 明訂
        這兩種**刻意不退避**,`_ttl_cache` 是它們唯一的節流器;若連它也拆掉,
        每次 rerun 都會重打一輪(實測 5 次 rerun:404 由 3 個請求變 15 個)。
        判準與完整理由見 `infra/proxy.py::mark_fetch_failed_if_retryable`。
    """
    url = f"{YF_CHART_BASE}/{ticker}"
    r = fetch_url(
        url,
        params={"interval": interval, "range": range_},
        timeout=15,
        backoff_on_429=False,   # v19.507:Yahoo 限流不會在 2/4/8s 內解除,重試純白等
                                # ~14s/標的 → 總經載入 8 標的爆 75s 逾時。遇 429 直接留空(§1)。
    )
    if r is None:
        # 抓失敗(非「真的沒有」)→ **依失敗分類**決定要不要標記。原本無條件快取,
        # 一次瞬斷就把空序列鎖住整個 TTL_10MIN,而 VIX/DGS10/USDTWD/DXY/SPY 全走這裡。
        # ⚠️ 404/407 走「不標記、照舊快取」那一支,理由見該 helper 的 docstring。
        return mark_fetch_failed_if_retryable(
            pd.Series(dtype=float, name=ticker), f"fetch_url returned None: {ticker}")
    try:
        d = r.json()
        result = d["chart"]["result"][0]
        ts = result["timestamp"]
        close = result["indicators"]["quote"][0]["close"]
        s = pd.Series(close, index=pd.to_datetime(ts, unit="s"), dtype=float).dropna()
        s.name = ticker
        # v19.83 F-PROV-1 phase 2:provenance via Series.attrs(§2.2)
        # Series 無 column 概念,改用 pandas 內建 attrs dict 承載血緣。
        # caller 不存取 attrs 時無感;需要追溯時 s.attrs["source"] / s.attrs["fetched_at"]。
        s.attrs["source"] = f"Yahoo:{ticker}"
        s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    except Exception as e:
        print(f"[macro_core/yf] {ticker} 解析失敗: {e}")
        # ⚠️ 這一支**刻意不標記**(2026-08-31),不是漏掉:
        # 走到這裡代表 HTTP 200 已經拿到手、來源活著而且明確回答了,只是內容
        # 不符預期(壞 ticker 會讓 Yahoo 回 result:null → 這裡 TypeError)。
        # 同一個回應再要一次還是同樣結果 → **重抓不會變好,只會每次呼叫多打一次來源**。
        # 只有「連回應都沒拿到」(上面 r is None)重試才有意義,故只標記那一支。
        return pd.Series(dtype=float, name=ticker)
    # v19.161 A1 Phase B:pandera schema 驗 final contract(values+index+attrs)
    # 此驗證**故意放在 parse try-except 之外**,schema 違反(values=NaN /
    # close<=0 / source 缺前綴等)為上游 bug,須當場 raise,**不**靜默返回空 Series。
    from shared.schemas import validate_yf_close
    validate_yf_close(s)
    return s


@register_cache
@_ttl_cache(ttl_sec=TTL_5MIN, maxsize=16)   # v19.64：盤中 ticker rerun dedupe
def fetch_yf_latest(tickers: tuple[str, ...]) -> dict[str, Optional[float]]:
    """批次抓多個 ticker 最新收盤(空值代表抓不到)。

    v19.233 F-PROV-1 cluster C 補洞:加 `_provenance` key(schema-additive,既有
    caller 用 `out[ticker]` 直接 key access 不會踩到 _provenance)。
    """
    out: dict[str, Optional[float]] = {}
    _success_tickers: list[str] = []
    for t in tickers:
        s = fetch_yf_close(t, range_="5d")
        out[t] = round(float(s.iloc[-1]), 4) if not s.empty else None
        if out[t] is not None:
            _success_tickers.append(t)
    out["_provenance"] = {
        "sources": [f"Yahoo:{t}:5d_latest" for t in _success_tickers],
        "fetched_at": pd.Timestamp.now('UTC').isoformat(),
    }
    return out


# ════════════════════════════════════════════════════════════
# 投資組合基準對比序列(v19.531 Phase 1.2 — P-UIHTTP-1 之 _get_benchmark_series 部分)
# ════════════════════════════════════════════════════════════
# 搬遷來源:ui/components/mk_dashboard.py::_get_benchmark_series
# 原實作在 **L3 UI 層**直接 `import yfinance` 抓 SPY/QQQ,並用
# `st.session_state["mk_bench_cache"]` 自建快取 —— 同時命中 CLAUDE.md
# §-1.5.1c v3 §01 三層圖 UI 框那句的兩個動詞:「嚴禁在 UI 層私自
# **存放**或**抓取**原始資料」。
#
# 為什麼放這個檔:
#   `fetch_yf_close` 是 **`services/**` 消費 Yahoo 日線收盤的既有共用入口**
#   (risk_radar / liquidity_engine / crisis_backtest / macro/* 都走它),
#   基準序列要的正是同一個來源、同一個欄位,只差窗口與 index 表示法。
#   沿用它,是為了**不再開第三套**;另開 repositories/benchmark_repository.py
#   只為一個轉接函式,是 §8.1 step 6「用不到的抽象」的反例。
#
# ⛔ **不得宣稱本檔是「全 repo 唯一的 Yahoo 取數實作」——那是假的。**
#   2026-08-28 獨立稽核以完整字表 + AST 交叉,實測本 repo **至少另有兩套獨立的
#   Yahoo v8 chart 日線實作**,外加一處真的 `import yfinance`:
#     - `repositories/fund/sources.py::_src_yahoo_finance_nav`
#       (`YF_MORNINGSTAR_CHART_URL` → query2;自己的 `urllib.request.urlopen`,
#        **不走 infra.proxy**,自己 parse chart.result[0].indicators.quote[0].close)
#     - `scripts/fetch_nav_cache.py::fetch_yahoo_finance_history`
#       (第三套 parser,共用同一個 URL 常數,GitHub Actions 排程實跑)
#     - `repositories/financial_repository.py` 的 `import yfinance` + `yf.Ticker`
#       (季財報,非日線)
#   而且 repo 自己早就記過這件事:`shared/api_endpoints.py` 檔頭逐字寫著
#   「✅ YF query2 Morningstar URL 真 dupe(repositories/fund/sources.py:833
#   ↔ scripts/fetch_nav_cache.py:301)」。
#   → 本次搬遷做到的是「**不新增第三套**」,**不是**「全站收斂成一套」。
#   v3 §01-2 的「同一資料來源全站只能有一處取數實作」在本 repo **尚未達成**;
#   `_src_yahoo_finance_nav` 與本函式算不算「同一資料來源」是**待總管裁決**的
#   判斷題(若算,§8.2.A EX-PASSTHRU-1 的升級觸發條件會要求上提 L2)。
#
# ⚠️ 本函式由 L3 UI(`ui/components/mk_dashboard.py::_get_benchmark_series`)**直呼**,
#   已登錄 CLAUDE.md §8.2.A **EX-PASSTHRU-1**。升級觸發條件見該表 ——
#   其中一條是「本 fetcher 出現第二個 UI caller」,屆時應比照 v19.247 R16 上提 L2。

# 抓取窗口:取 `1y` 再依日期裁到 9 個月。
#
# ⛔ **這裡不宣稱「與搬遷前窗口一致」——那句話不可證,而且我原本的理由是錯的。**
# 我原本寫「Chart API 的 range 只吃固定枚舉、沒有 9mo」,那是**沒查證的斷言**。
# 2026-08-28 稽核實測 yfinance 1.6.0 原始碼(scrapers/history.py):
#   - L188-192:無 start/end 時 `params = {"range": period}` —— **"9mo" 原封送去 Yahoo**,
#     client 端**不會**轉成 period1/period2;
#   - L318-324 確實算了一個 `start`,但 L408-416 那個 `start` **只用來裁
#     dividends / capital_gains / splits**;價格 DataFrame `quotes` 全程沒被它裁過
#     (grep L324 之後所有 `start` 用法可複驗)。
# ⇒ **搬遷前的窗口 100% 等於「Yahoo 對 range=9mo 回什麼」,而那個沙箱測不到。**
#   兩種情境並陳,哪一種為真**未知**:
#     A) Yahoo 接受 9mo → 搬遷前約 9 個月,本函式的裁切還原之;
#     B) Yahoo 拒絕 9mo → 搬遷前 yfinance 拿到空表 → 舊碼 series=None →
#        **Benchmark_Lag 從來沒亮過、對比圖從來沒畫出來過**;搬遷後會正常取到
#        ~196 個交易日 → 這兩個功能會**從死的變成活的**(使用者可見的大變更)。
#   → 部署後必須實地確認是哪一種(見 PR 的「部署後必須確認」清單)。
#
# 選 `1y` 的理由與上面那個未知**無關**,它自己站得住:
#   (a) `1y` 在本 repo production 已實證可用(services/risk_radar.py 等 2 處);
#   (b) 9 個月窗口要餵 `_quarter_rets_from_series` 的 130 個交易日門檻,
#       `6mo`(~126 交易日)不夠,`1y` 是滿足門檻的最小既有枚舉值。
_BENCHMARK_FETCH_RANGE = "1y"
_BENCHMARK_WINDOW_MONTHS = 9


def fetch_benchmark_close(ticker: str = "SPY") -> Optional[pd.Series]:
    """抓投資組合對比基準(SPY / QQQ 等)近 9 個月日線收盤序列。

    快取:**不自建第二層** —— 直接吃上游 `fetch_yf_close` 的
    `@_ttl_cache(ttl_sec=TTL_10MIN)`(TTL 走 `shared/ttls.py` SSOT,§3.3)。
    同一份資料疊兩層 TTL 會讓失效語意無法推理,故本函式刻意無裝飾器。

    ⚠️ **相對於搬遷前(UI 層 yfinance 直抓)的行為變更,逐項列出,不藏**:
      1. **傳輸路徑整個換掉**:yfinance 直連 → `infra.proxy.fetch_url`
         (NAS Squid 中繼、台灣出口 IP)。`fetch_yf_close` 自己的 docstring 就寫
         「yfinance 預設不走 proxy,常因雲端節點 IP 被 Yahoo 限流(429)」——
         兩條路徑的可達性與失敗率本來就不同,**不是零變更**。
      2. **429 語意**:上游帶 `backoff_on_429=False`,遇 429 **立刻放棄不重試**;
         舊路徑走 yfinance 自己的 session / retry。
      3. **快取範圍**:`st.session_state` 是**每個使用者各自一份**;
         `@_ttl_cache(maxsize=64)` 是**全 process 共享、跨所有使用者**,
         且被 `@register_cache` 收進 `infra.cache._CACHE_REGISTRY` ——
         UI 的「🔄 清空快取」現在會**一併清掉基準**。
      4. **pandera schema 首次套用到基準資料**:上游 `validate_yf_close(s)` 在
         try/except **之外**,違約會 raise;舊碼的 `except Exception` 會吞掉。
         本函式與 UI 端都不攔 → **會炸穿 Streamlit render,整個戰情室 tab 掛掉**。
         這是刻意的(§1 Fail Loud:壞資料不得靜默流入計算),但要知道它炸在哪。
      5. **失敗重試頻率**:舊碼把 `None` 也存進 session 快取 → 一個 session 最多試一次;
         `_ttl_cache` 無條件 `_cache[key] = (now, result)`,空序列同樣被快取
         → 改為**每 10 分鐘重試一次**。

    Returns
    -------
    pd.Series | None
        DatetimeIndex(已 normalize 成當日 00:00),value 為收盤價。
        **取不到時回 None**,不回空 Series、更不回假序列(§1 Fail Loud)——
        呼叫端據此顯示「基準目前無法取得」,而不是畫一張空圖假裝正常。
        失敗原因由上游 `fetch_yf_close` 印出。

    ⚠️ **已知陷阱(登記,未修)**:`ticker` 無任何驗證。`normalize()` 假設交易所開盤
    時刻落在當日 UTC 內;**開盤早於 00:00 UTC 的交易所(ASX ~23:00Z、NZX ~21:00Z)
    會被 normalize 到前一天**。目前 UI selectbox 只有 SPY / QQQ(美股,13:30Z),
    所以現在不是 bug —— 但擴充 ticker 清單前必須先處理。

    Raises
    ------
    AssertionError
        normalize 後索引重複或非遞增(§4.2 不變量;上游 schema 已驗過原始索引,
        這裡守的是本函式自己的後處理)。壞索引會讓「連續兩季落後」比錯期別,
        屬「錯誤的數字比沒有數字更危險」,一律當場炸掉,不靜默修補。
    """
    s = fetch_yf_close(ticker, range_=_BENCHMARK_FETCH_RANGE, interval="1d")
    if s is None or s.empty:
        return None
    _attrs = dict(getattr(s, "attrs", {}) or {})
    out = s.copy()
    # yfinance `.history()` 的日線 index 是「交易所當地午夜」,tz_localize(None)
    # 後即為純日期;Chart API 回的是開盤時刻 epoch(如 13:30Z)。normalize 到當日
    # 00:00 才能與搬遷前的 index 完全對齊(對比圖 x 軸、與基金 NAV 的日期比對)。
    out.index = pd.DatetimeIndex(out.index).normalize()
    cutoff = pd.Timestamp.now("UTC").tz_localize(None).normalize() \
        - pd.DateOffset(months=_BENCHMARK_WINDOW_MONTHS)
    out = out[out.index >= cutoff]
    if out.empty:
        return None
    assert out.index.is_unique, f"fetch_benchmark_close({ticker}): normalize 後日期重複"
    assert out.index.is_monotonic_increasing, \
        f"fetch_benchmark_close({ticker}): 時序未排序"
    out.name = ticker
    # provenance(§2.2):保留上游血緣,補記本函式做過的窗口裁切。
    out.attrs.update(_attrs)
    out.attrs["source"] = _attrs.get("source") or f"Yahoo:{ticker}"
    out.attrs["window"] = f"{_BENCHMARK_WINDOW_MONTHS}mo(from {_BENCHMARK_FETCH_RANGE})"
    return out
