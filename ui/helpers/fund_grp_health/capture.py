"""ui/helpers/fund_grp_health/capture.py — 逐檔上/下檔捕捉率 + 操盤評分(v19.414)。

供**健診大表 + 批次大表共用**(併入 `build_merged_extra_columns`)。每檔基金 NAV 與
「依幣別選定的大盤基準」(TWD→TWII、其餘→SPX)算捕捉率 + 操盤評分。基準序列只抓一次
(module 級 success-only 快取;400 檔批次不重抓),抓失敗不快取 → 下次重試。

架構:L3 orchestrator → L2 `services.capture_ratio`(純數學)+ `services.crisis_backtest`
(基準抓取)。§1:缺料 / 基準抓不到 / 月數不足 → None(不假精確)。
"""
from __future__ import annotations

# 只快取「成功」的基準序列(失敗不入 → 下次重試,避免暫時性失敗永久卡 None)
_BENCH_CACHE: dict = {}


def _benchmark_nav(market: str):
    """抓大盤基準 NAV(10 年);成功則 module 快取。回傳 pd.Series(空 = 失敗)。"""
    if market in _BENCH_CACHE:
        return _BENCH_CACHE[market]
    from services.crisis_backtest import fetch_market_series
    s = fetch_market_series(market, years=10)
    if s is not None and len(s) > 0:
        _BENCH_CACHE[market] = s
    return s


def capture_by_code(funds: list) -> dict:
    """每檔 → {上檔捕捉%, 下檔捕捉%, 操盤評分}(keyed by code)。缺料/基準/月數不足 → None。"""
    from services.capture_ratio import benchmark_for_currency, compute_capture
    from services.currency import normalize_ccy

    import sys

    out: dict = {}
    for _f in funds:
        _code = _f.get("code", "?")
        _blank = {"上檔捕捉%": None, "下檔捕捉%": None, "操盤評分": None}
        try:
            _series = _f.get("series")
            if _series is None or len(_series) < 3:      # 基本 sanity;有效性交給 compute_capture 月數把關
                out[_code] = _blank
                continue
            _ccy = normalize_ccy(_f.get("currency"), default="")
            if not _ccy:            # 無幣別 → 無法選基準 → None(不默認 SPX 錯配 TWD 基金,§1)
                out[_code] = _blank
                continue
            _bench = _benchmark_nav(benchmark_for_currency(_ccy))
            if _bench is None or len(_bench) == 0:
                out[_code] = _blank
                continue
            _r = compute_capture(_series, _bench)
            out[_code] = {"上檔捕捉%": _r["upside"], "下檔捕捉%": _r["downside"], "操盤評分": _r["score"]}
        except Exception as _e:  # noqa: BLE001 — 單檔失敗不拖垮整組 extra 欄
            print(f"[capture] {_code} 失敗: {type(_e).__name__}: {_e}", file=sys.stderr)
            out[_code] = _blank
    return out
