"""repositories/external_market_repository.py — 第三方公開市場資料(v19.197 P1-3)

從 services/valuation.py + services/risk_radar.py 下沉的 HTTP fetcher,
修 ARCHITECTURE_AUDIT V5+V7 違憲(L2 service 直 import yfinance / urllib + HTTP)。

對外 API:
- `fetch_yf_forward_pe(symbol)` — yfinance Ticker.info forwardPE / trailingPE chain
- `fetch_multpl_pe()` — multpl.com HTML scrape S&P 500 trailing P/E
- `fetch_stooq_csv(symbol, trace)` — stooq.com daily CSV + headerless fallback

所有抓取統一走 `infra.proxy.fetch_url`(L0 NAS Squid 中繼)。
"""
from __future__ import annotations

import io
import re
import urllib.parse as _up
from typing import Optional

import pandas as pd


def fetch_yf_forward_pe(symbol: str = "^GSPC") -> Optional[float]:
    """從 yfinance Ticker.info 取 forwardPE,缺則降級 trailingPE。失敗回 None。

    v19.197 P1-3:V5 修補,從 services/valuation.py:154-167 下沉。

    F-PROV-1 註:Optional[float] 結構性無 .attrs,**provenance 由
    `services.valuation.detect_valuation()` orchestrator-level `_provenance.sources`
    捕(phase 19 v19.105),記為 `"yfinance:^GSPC.info:forwardPE→trailingPE→multpl.com"`。
    本 fn 屬 leaf scalar,不重複 stamp 避免冗餘。
    """
    try:
        import yfinance as yf
        info = yf.Ticker(symbol).info
        v = info.get("forwardPE")
        if v:
            return float(v)
        v_trail = info.get("trailingPE")
        if v_trail:
            print(f"[external_market/{symbol}] forwardPE 缺,降級用 trailingPE")
            return float(v_trail)
    except Exception as e:  # noqa: BLE001
        print(f"[external_market/{symbol}] yfinance 失敗: {e}")
    return None


def fetch_multpl_pe() -> Optional[float]:
    """從 multpl.com 抓 S&P 500 P/E ratio（trailing TTM）作為 Forward P/E 代理。

    Forward P/E 公開免費源稀缺,trailing PE 與 forward PE 歷史相關性 > 0.85,
    作為 yfinance Ticker.info["forwardPE"] 掛點時的降級備援。multpl.com 結構 10+ 年
    穩定(id="current" 區塊內含當前 PE)。

    v19.197 P1-3:V5 修補,從 services/valuation.py:110-142 下沉。

    F-PROV-1 註:Optional[float] 結構性無 .attrs,**provenance 由
    `services.valuation.detect_valuation()` orchestrator-level `_provenance.sources`
    捕(phase 19 v19.105),記為 chain 末段「→multpl.com」。

    Returns:
        float | None: 最近一期 trailing PE;任意失敗回 None;console log 印 root cause 助 debug。
    """
    try:
        from infra.proxy import fetch_url
        r = fetch_url("https://www.multpl.com/s-p-500-pe-ratio", timeout=15)
        if r is None or getattr(r, "status_code", 0) != 200:
            print(f"[external_market/multpl] HTTP {getattr(r, 'status_code', None)}")
            return None
        # multpl.com 頁面結構:「Current S&P 500 PE Ratio: NN.NN」字串緊跟主數字
        m = re.search(r"Current S&amp;P 500 PE Ratio[:\s]+(\d+\.?\d*)", r.text)
        if not m:
            m = re.search(r"Current S&P 500 PE Ratio[:\s]+(\d+\.?\d*)", r.text)
        if not m:
            # 二度 fallback:id="current" 區塊抓首個浮點數
            m = re.search(r'id="current"[^<]*<[^>]*>\s*(\d+\.?\d*)', r.text)
        if not m:
            print("[external_market/multpl] 解析失敗:未找到 PE 數字(頁面結構可能變動)")
            return None
        return float(m.group(1))
    except Exception as e:  # noqa: BLE001
        print(f"[external_market/multpl] 失敗: {e}")
        return None


def fetch_stooq_csv(symbol: str, trace: list[str] | None = None) -> pd.Series:
    """stooq.com 公開歷史 CSV → 收盤 Series（key: symbol e.g. '^vix3m' / '^vxv' / '^cpc'）。

    URL pattern: https://stooq.com/q/d/l/?s={symbol}&i=d
    對 CBOE 系列指數的第 4 層備援（公開 CDN 不需登入),多數 NAS Squid 環境可直連。

    v19.197 P1-3:V7 修補,從 services/risk_radar.py:169-249 下沉。

    參數 trace:可選 list 收集失敗原因供 UI 顯示。失敗或無此 symbol 回空 Series。

    fallback:
    - 主路徑 read_csv 解析(Date + Close 欄)
    - 主路徑失敗加 headerless fallback(stooq 偶爾回 'YYYY-MM-DD,o,h,l,close,vol' 純資料)
    - 失敗時 trace 加入回應體首 80 字方便 user 看到實際長相
    """
    from infra.proxy import fetch_url

    def _t(msg: str) -> None:
        if trace is not None:
            trace.append(f"stooq {symbol}: {msg}")

    def _parse_standard(text: str) -> pd.Series:
        df = pd.read_csv(io.StringIO(text))
        if "Date" not in df.columns or "Close" not in df.columns or df.empty:
            return pd.Series(dtype=float)
        idx = pd.to_datetime(df["Date"], errors="coerce")
        vals = pd.to_numeric(df["Close"], errors="coerce")
        return pd.Series(vals.values, index=idx).dropna().sort_index()

    def _parse_headerless(text: str) -> pd.Series:
        """stooq 偶爾回的 'YYYY-MM-DD,open,high,low,close,volume\\n' 無 header 格式。"""
        rows = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line or "," not in line:
                continue
            parts = line.split(",")
            if len(parts) < 5:
                continue
            try:
                dt = pd.to_datetime(parts[0].strip(), errors="raise")
                val = float(parts[4].strip())
                rows.append((dt, val))
            except (ValueError, TypeError):
                continue
        if not rows:
            return pd.Series(dtype=float)
        s = pd.Series([v for _, v in rows], index=[d for d, _ in rows])
        return s.sort_index().dropna()

    try:
        url = f"https://stooq.com/q/d/l/?s={_up.quote(symbol, safe='')}&i=d"
        r = fetch_url(url, timeout=15)
        if r is None or getattr(r, "status_code", 0) != 200:
            code = getattr(r, "status_code", None)
            _t(f"HTTP {code}")
            print(f"[external_market/stooq] {symbol} HTTP {code}")
            return pd.Series(dtype=float)
        text = r.text
        if "No data" in text or len(text) < 50:
            _t(f"No data / body 過短 (len={len(text)})")
            print(f"[external_market/stooq] {symbol} 無資料")
            return pd.Series(dtype=float)

        s = _parse_standard(text)
        if not s.empty:
            s.attrs["source"] = f"stooq:{symbol}"
            s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
            return s.tail(180)

        # headerless fallback
        s_hl = _parse_headerless(text)
        if not s_hl.empty:
            _t(f"headerless fallback hit ({len(s_hl)} rows)")
            s_hl.attrs["source"] = f"stooq:{symbol}:headerless"
            s_hl.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
            return s_hl.tail(180)

        sample = repr(text[:80])
        _t(f"無法解析 sample={sample}")
        print(f"[external_market/stooq] {symbol} 無法解析,sample={sample}")
        return pd.Series(dtype=float)
    except Exception as e:  # noqa: BLE001
        _t(f"exception {str(e)[:40]}")
        print(f"[external_market/stooq] {symbol} 失敗: {e}")
        return pd.Series(dtype=float)


def fetch_cboe_csv(short_name: str, trace: list[str] | None = None) -> pd.Series:
    """CBOE 官方每日 CSV → 收盤 Series(key: short_name 如 'VIX3M' / 'CPC' / 'CPCE')。

    URL pattern: https://cdn.cboe.com/api/global/us_indices/daily_prices/{short}_History.csv
    對 ^VIX3M、^CPC、^CPCE 等 Yahoo 已停供 ticker 的官方替代源。

    v19.221 P1-3 修補 N2(架構越權):從 services/risk_radar.py 下沉至 L1
    repository。trace list 可選收集失敗原因。失敗回空 Series。
    """
    import io

    from infra.proxy import fetch_url

    def _t(msg: str) -> None:
        if trace is not None:
            trace.append(f"CBOE {short_name}: {msg}")
    try:
        url = ("https://cdn.cboe.com/api/global/us_indices/"
               f"daily_prices/{short_name}_History.csv")
        r = fetch_url(url, timeout=15)
        if r is None or getattr(r, "status_code", 0) != 200:
            code = getattr(r, "status_code", None)
            _t(f"HTTP {code}")
            print(f"[external_market/cboe] {short_name} HTTP {code}")
            return pd.Series(dtype=float)
        df = pd.read_csv(io.StringIO(r.text))
        date_col = next((c for c in df.columns if "DATE" in c.upper()), None)
        close_col = next((c for c in df.columns if "CLOSE" in c.upper()), None)
        if not date_col or not close_col or df.empty:
            _t(f"欄位不符 {list(df.columns)[:3]}")
            print(f"[external_market/cboe] {short_name} 欄位不符: {list(df.columns)}")
            return pd.Series(dtype=float)
        idx = pd.to_datetime(df[date_col], errors="coerce")
        vals = pd.to_numeric(df[close_col], errors="coerce")
        s = pd.Series(vals.values, index=idx).dropna().sort_index()
        s.attrs["source"] = f"CBOE:cdn:daily_prices:{short_name}_History.csv"
        s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
        return s.tail(180)
    except Exception as e:  # noqa: BLE001
        _t(f"exception {str(e)[:40]}")
        print(f"[external_market/cboe] {short_name} 失敗: {e}")
        return pd.Series(dtype=float)
