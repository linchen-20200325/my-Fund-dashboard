"""ui/helpers/fund_grp_health/capture.py — 逐檔上/下檔捕捉率 + 操盤評分 + vs 大盤%(v19.414;v19.420)。

供**健診大表 + 批次大表共用**(併入 `build_merged_extra_columns`)。每檔基金 NAV 與
「依幣別選定的大盤基準」(TWD→TWII、**USD→SPX、其餘無基準**)算:上/下檔捕捉率 +
操盤評分(v19.414)**及 vs 大盤%**(v19.420 近1年純價格報酬差)。四值**共用同一次基準
抓取**(F-BM-2:vs大盤% 併入本 fetcher,不另開第二個 N-pass,基準失敗時不放大成 2×N),
基準序列 module 級 success-only 快取(400 檔批次每市場只抓一次),抓失敗不快取 → 下次重試;
**帶 TTL**(`_BENCH_TTL_SEC`,走 `shared/ttls.py` 語意常數)—— 長時間運行的 process 不再
永遠用開站那一刻的序列(§2.4),過期重抓失敗時不回傳 stale 冒充新鮮值。

另出兩個**可信度旗標欄**(2026-08-06 必修 5):
- `捕捉樣本` ← `compute_capture` 的 `low_confidence` / `n_up` / `n_down`
- `vs 大盤期間` ← `excess_return` 的 `full_period`
兩者原本算完就被丟掉,大表只有欄位 help 泛泛提醒,逐列看不出樣本差異(§1 缺料須帶旗標)。

架構:L3 orchestrator → L2 `services.capture_ratio` + `services.benchmark_compare`(純數學)
+ `services.crisis_backtest`(基準抓取)。§1:缺料 / 基準抓不到 / 月數不足 → None(不假精確),
且旗標欄要說出**為什麼**留白。
"""
from __future__ import annotations

import time as _time

from shared.ttls import TTL_1HOUR

# 基準序列快取 TTL(§2.4「超過 TTL 應重新抓取」)。原本是**無 TTL** 的 module dict:
# 長時間運行的 Streamlit process 會一直用開站那一刻抓到的序列,「vs 大盤%」與捕捉率的
# 最後一點會逐日變舊而畫面上看不出來。
# 為什麼選 TTL_1HOUR(走 shared/ttls.py 語意常數,不新造數字):
#   (a) 基準是「10 年日線指數」,拿來當比較尺,不是即時報價;對面的基金 NAV 本身就是
#       T+1~T+3 才公布 —— 一小時的基準延遲遠比它比較的對象新鮮。
#   (b) 400 檔批次要跑 30~40 分鐘,一小時的窗口讓**整批**落在同一個基準快照內,
#       同一張表的各列才可比(換成更短的 TTL 會在跑批中途換基準端點)。
#   (c) 上游 L1 `fetch_yf_close` 自己有 10 分鐘 TTL;本層只負責把 N 檔的 fan-out
#       收斂成一次抓取,不是第二層權威。
_BENCH_TTL_SEC: int = TTL_1HOUR
# 只快取「成功」的基準序列(失敗不入 → 下次重試,避免暫時性失敗永久卡 None)
# 值 = (抓到的時間 monotonic 秒, series)
_BENCH_CACHE: dict = {}


def _benchmark_nav(market):
    """抓大盤基準 NAV(10 年);成功則 module 快取 `_BENCH_TTL_SEC` 秒。

    回傳 pd.Series(空 / None = 無基準)。

    `market` 為 None 時(= 幣別非 TWD/USD,`benchmark_for_currency` 誠實拒答)直接回 None,
    不打網路、也不退回 SPX(§4.1:原幣 NAV 對 USD 指數 = 把匯率當績效)。

    TTL 過期後重抓;**重抓失敗不回傳過期序列**(§2.4 禁止靜默返回 stale)——
    直接回上游的空序列,讓呼叫端的旗標欄照實顯示「基準抓取失敗」,
    並丟掉過期項目讓下一次重試。
    """
    if market is None:
        return None
    _now = _time.monotonic()
    _hit = _BENCH_CACHE.get(market)
    if _hit is not None and (_now - _hit[0]) < _BENCH_TTL_SEC:
        return _hit[1]
    from services.crisis_backtest import fetch_market_series
    s = fetch_market_series(market, years=10)
    if s is not None and len(s) > 0:
        _BENCH_CACHE[market] = (_now, s)
    elif _hit is not None:
        _BENCH_CACHE.pop(market, None)      # 過期又抓不到 → 不留 stale 冒充新鮮值
    return s


def _sample_label(r: dict) -> str:
    """捕捉率的**樣本旗標**(§1 第 3 項:低信心必須逐列可見)。

    `compute_capture` 算好的 `low_confidence` / `n_up` / `n_down` 原本整個被丟掉,
    大表只在欄位 help 泛泛說「3–5 月為參考值」—— 於是「3 個下跌月的操盤評分 92」
    與「40 個下跌月的 92」在表上完全一樣、還能點欄比大小。
    """
    if r.get("score") is None:
        return "⬜ 月數不足"
    _u, _d = int(r.get("n_up") or 0), int(r.get("n_down") or 0)
    _mark = "⚠️" if r.get("low_confidence") else "✅"
    return f"{_mark} {_u}漲/{_d}跌"


def _window_label(ex: dict) -> str:
    """vs 大盤% 的**窗口旗標**:近 1 年 vs 全期(共同歷史不足 1 年 → 跨檔不可比)。"""
    if ex.get("excess_pct") is None:
        return "⬜ —"
    return "⚠️ 全期(<1年)" if ex.get("full_period") else "近1年"


def capture_by_code(funds: list) -> dict:
    """每檔 → {上檔捕捉%, 下檔捕捉%, 操盤評分, 捕捉樣本, vs 大盤%, vs 大盤期間}(keyed by code)。

    缺料 / 基準 / 月數不足 → 數值 None,兩個旗標欄說明**為什麼**留白(§1)。
    四值**共用同一次基準抓取**(F-BM-2:vs 大盤% 不另開第二個 N-pass fetcher,基準失敗時
    不放大成 2×N 呼叫)。
    """
    from services.benchmark_compare import excess_return
    from services.capture_ratio import benchmark_for_currency, compute_capture
    from services.currency import normalize_ccy

    import sys

    def _blank(note: str) -> dict:
        return {"上檔捕捉%": None, "下檔捕捉%": None, "操盤評分": None,
                "捕捉樣本": note, "vs 大盤%": None, "vs 大盤期間": note}

    out: dict = {}
    for _f in funds:
        _code = _f.get("code", "?")
        try:
            _series = _f.get("series")
            if _series is None or len(_series) < 3:      # 基本 sanity;有效性交給下游月數/共同日把關
                out[_code] = _blank("⬜ NAV 太短")
                continue
            _ccy = normalize_ccy(_f.get("currency"), default="")
            if not _ccy:            # 無幣別 → 無法選基準 → None(不默認 SPX 錯配 TWD 基金,§1)
                out[_code] = _blank("⬜ 缺幣別")
                continue
            _mkt = benchmark_for_currency(_ccy)
            if _mkt is None:        # §4.1 非 TWD/USD → 無可比基準,誠實留白(必修 7)
                out[_code] = _blank(f"⬜ {_ccy} 無對應基準")
                continue
            _bench = _benchmark_nav(_mkt)
            if _bench is None or len(_bench) == 0:
                out[_code] = _blank("⬜ 基準抓取失敗")
                continue
            _r = compute_capture(_series, _bench)                # v19.414 捕捉率(月頻分組)
            _ex = excess_return(_series, _bench)                 # v19.420 vs 大盤%(近1Y純價格,同一 _bench)
            out[_code] = {"上檔捕捉%": _r["upside"], "下檔捕捉%": _r["downside"],
                          "操盤評分": _r["score"], "捕捉樣本": _sample_label(_r),
                          "vs 大盤%": _ex["excess_pct"], "vs 大盤期間": _window_label(_ex)}
        except Exception as _e:  # noqa: BLE001 — 單檔失敗不拖垮整組 extra 欄
            print(f"[capture] {_code} 失敗: {type(_e).__name__}: {_e}", file=sys.stderr)
            out[_code] = _blank(f"⬜ 計算失敗({type(_e).__name__})")
    return out
