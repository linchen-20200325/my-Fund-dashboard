"""v19.35 Fund + ETF Screener v2 — 3-pipeline data sourcing + normalized schema.

依 user 2026-06-09 spec：
- 管道 A（TWSE ETF）：TWSE OpenAPI `BWIBBU_ALL` 取殖利率 + yfinance 補總報酬
- 管道 B（US ETF / 境外基金）：yfinance 抓 1Y total return + dividend yield
- 管道 C（台灣傳統共同基金）：SITCA 月報 scrape，robots.txt 檢查 + UA rotation + 低頻 sleep
- 統一 schema：id / name / currency / country / total_return / dividend_rate
- 篩選：currency × country × (total_return ≥ dividend_rate)
- 本地備援：data_cache/screener_v2/{pipeline}.json，斷網時自動載入

注意：本模組是 v19.34 之上的進階副 tab，與 services/fund_screener.py 並存；
共同基金核心（KNOWN_OVERSEAS_FUNDS / 三色燈）零改動。
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from infra.cache import _ttl_cache, register_cache
from infra.proxy import fetch_url

# ════════════════════════════════════════════════════════════════
# §1 統一 schema（對齊 user spec §2 Data Matrix）
# ════════════════════════════════════════════════════════════════
SCHEMA_KEYS: tuple[str, ...] = (
    "id", "name", "currency", "country", "total_return", "dividend_rate",
)
PIPELINE_LABELS: dict[str, str] = {
    "twse": "🇹🇼 TWSE ETF",
    "yfinance": "🌐 yfinance",
    "sitca": "🏛️ SITCA",
    "cache": "💾 本地備援",
}


@dataclass
class FundETFRow:
    """user spec §2 標準化 row。"""
    id: str
    name: str
    currency: str          # USD / TWD / EUR ...
    country: str           # USA / Taiwan / Global ...
    total_return: float    # 年化含息報酬率 %
    dividend_rate: float   # 年化配息率 %（不配息填 0）
    source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _coerce_pct(v: Any) -> float | None:
    """字串 "8.5%" → 8.5；小數 0.085 自動 ×100。NaN/None/非數值 → None。"""
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip().replace("%", "").replace(",", "")
        if not s:
            return None
        try:
            f = float(s)
        except ValueError:
            return None
    else:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
    if f != f:  # NaN
        return None
    if -1.0 < f < 1.0 and f != 0:
        return f * 100
    return f


def normalize_row(
    *,
    raw_id: Any,
    raw_name: Any,
    raw_currency: Any = "TWD",
    raw_country: Any = "Taiwan",
    raw_total_return: Any = None,
    raw_dividend_rate: Any = None,
    source: str = "unknown",
) -> FundETFRow | None:
    """缺 id/name → None；缺 return/dividend → 守底 0.0。"""
    if raw_id is None or raw_name is None:
        return None
    sid = str(raw_id).strip()
    name = str(raw_name).strip()
    if not sid or not name:
        return None
    tr = _coerce_pct(raw_total_return)
    dr = _coerce_pct(raw_dividend_rate)
    return FundETFRow(
        id=sid,
        name=name,
        currency=(str(raw_currency).strip().upper() or "TWD"),
        country=(str(raw_country).strip() or "Taiwan"),
        total_return=tr if tr is not None else 0.0,
        dividend_rate=dr if dr is not None else 0.0,
        source=source,
    )


# ════════════════════════════════════════════════════════════════
# §2 本地備援 cache（user spec §5 Rate Limit fallback）
# ════════════════════════════════════════════════════════════════
_CACHE_ROOT = Path(__file__).resolve().parent.parent / "data_cache" / "screener_v2"


def _cache_path(pipeline: str) -> Path:
    return _CACHE_ROOT / f"{pipeline}.json"


def save_cache(pipeline: str, rows: list[FundETFRow]) -> None:
    """成功抓資料後寫快取，下次斷網／rate-limit 時可載入。"""
    try:
        _CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        path = _cache_path(pipeline)
        payload = {"ts": int(time.time()), "rows": [r.to_dict() for r in rows]}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    except OSError as e:
        print(f"[screener_v2/cache] save({pipeline}) failed: {e}")


def load_cache(pipeline: str) -> list[FundETFRow]:
    path = _cache_path(pipeline)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text())
        rows = []
        for d in payload.get("rows", []):
            try:
                rows.append(FundETFRow(**d))
            except TypeError:
                continue
        return rows
    except (json.JSONDecodeError, OSError) as e:
        print(f"[screener_v2/cache] load({pipeline}) failed: {e}")
        return []


def cache_age_days(pipeline: str) -> int | None:
    path = _cache_path(pipeline)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
        ts = int(payload.get("ts", 0))
        if ts == 0:
            return None
        return max(0, (int(time.time()) - ts) // 86400)
    except (json.JSONDecodeError, OSError, ValueError):
        return None


# ════════════════════════════════════════════════════════════════
# §3 反封鎖 helper：隨機 UA + 延遲 + robots.txt（user spec §5）
# ════════════════════════════════════════════════════════════════
_USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
)


def _random_ua() -> str:
    return random.choice(_USER_AGENTS)


def _polite_sleep(min_sec: float = 1.0, max_sec: float = 3.0) -> None:
    time.sleep(random.uniform(min_sec, max_sec))


_ROBOTS_CACHE: dict[str, RobotFileParser | None] = {}


def _check_robots(url: str, ua: str = "*") -> bool:
    """robots.txt allow 才回 True；fetch 失敗保守 False（不爬）。"""
    try:
        parsed = urlparse(url)
        host = f"{parsed.scheme}://{parsed.netloc}"
        if host not in _ROBOTS_CACHE:
            rp = RobotFileParser()
            rp.set_url(f"{host}/robots.txt")
            try:
                rp.read()
                _ROBOTS_CACHE[host] = rp
            except Exception as e:
                print(f"[screener_v2/robots] fetch failed for {host}: {e}")
                _ROBOTS_CACHE[host] = None
                return False
        rp = _ROBOTS_CACHE.get(host)
        if rp is None:
            return False
        return rp.can_fetch(ua, url)
    except Exception as e:
        print(f"[screener_v2/robots] exception: {e}")
        return False


# ════════════════════════════════════════════════════════════════
# §4 管道 A — 台灣掛牌 ETF（TWSE OpenAPI）
# ════════════════════════════════════════════════════════════════
_TWSE_ETF_LIST_URL = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"

# 已知 TW ETF whitelist（避免抓全 1000+ 個股無 ETF 標誌）
_TW_ETF_CODES: tuple[str, ...] = (
    "0050", "0056", "00878", "00919", "00929", "00713", "00701",
    "00692", "0061", "00646", "00679B", "00761B", "006208", "00891",
    "00892", "00893", "00900", "00915", "00918", "00940",
)

_TW_ETF_META: dict[str, str] = {
    "0050": "元大台灣50",
    "0056": "元大高股息",
    "00878": "國泰永續高股息",
    "00919": "群益台灣精選高息",
    "00929": "復華台灣科技優息",
    "00713": "元大台灣高息低波",
    "00701": "國泰股利精選30",
    "00692": "富邦公司治理",
    "0061":  "元大寶滬深",
    "00646": "元大S&P500",
    "00679B": "元大美債20年",
    "00761B": "國泰A級公司債",
    "006208": "富邦台50",
    "00891": "中信關鍵半導體",
    "00892": "富邦台灣半導體",
    "00893": "國泰智能電動車",
    "00900": "富邦特選高股息30",
    "00915": "凱基優選高股息30",
    "00918": "大華優利高填息30",
    "00940": "元大台灣價值高息",
}


@register_cache
@_ttl_cache(ttl_sec=3600, maxsize=4)
def fetch_twse_etf_pool(use_cache_fallback: bool = True) -> list[FundETFRow]:
    """TWSE BWIBBU_ALL → 過濾 ETF whitelist → 取殖利率 (DividendYield)。"""
    try:
        resp = fetch_url(_TWSE_ETF_LIST_URL, timeout=15, retries=2)
        if resp is None or resp.status_code != 200:
            print("[screener_v2/twse] HTTP fail → fallback cache")
            return load_cache("twse") if use_cache_fallback else []
        data = resp.json()
        rows: list[FundETFRow] = []
        for item in data:
            code = str(item.get("Code", "")).strip()
            if code not in _TW_ETF_CODES:
                continue
            yield_str = item.get("DividendYield") or "0"
            name = item.get("Name") or _TW_ETF_META.get(code) or code
            row = normalize_row(
                raw_id=code,
                raw_name=name,
                raw_currency="TWD",
                raw_country="Taiwan",
                raw_total_return=None,  # OpenAPI 無；UI 可後續補
                raw_dividend_rate=yield_str,
                source="twse",
            )
            if row:
                rows.append(row)
        if rows:
            save_cache("twse", rows)
        return rows
    except Exception as e:
        print(f"[screener_v2/twse] exception: {e}")
        return load_cache("twse") if use_cache_fallback else []


# ════════════════════════════════════════════════════════════════
# §5 管道 B — yfinance（US ETF + 境外基金）
# ════════════════════════════════════════════════════════════════
_YFINANCE_POOL: tuple[tuple[str, str, str, str], ...] = (
    # (ticker, name, currency, country)
    ("SPY",  "SPDR S&P 500 ETF",                 "USD", "USA"),
    ("VTI",  "Vanguard Total Stock Market",      "USD", "USA"),
    ("VYM",  "Vanguard High Dividend Yield",     "USD", "USA"),
    ("SCHD", "Schwab US Dividend Equity",        "USD", "USA"),
    ("QQQ",  "Invesco NASDAQ-100",               "USD", "USA"),
    ("VEA",  "Vanguard FTSE Developed Markets",  "USD", "Global"),
    ("VWO",  "Vanguard FTSE Emerging Markets",   "USD", "Global"),
    ("BND",  "Vanguard Total Bond Market",       "USD", "USA"),
    ("AGG",  "iShares Core US Aggregate Bond",   "USD", "USA"),
    ("HYG",  "iShares iBoxx HY Corp Bond",       "USD", "USA"),
)


@register_cache
@_ttl_cache(ttl_sec=1800, maxsize=4)
def fetch_yfinance_pool(use_cache_fallback: bool = True) -> list[FundETFRow]:
    """yfinance: 1Y close % + info.yield。"""
    try:
        import yfinance as yf
    except ImportError:
        print("[screener_v2/yfinance] yfinance not installed")
        return load_cache("yfinance") if use_cache_fallback else []

    rows: list[FundETFRow] = []
    for ticker, name, currency, country in _YFINANCE_POOL:
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            tr_pct: float | None = None
            try:
                hist = t.history(period="1y")
                if hist is not None and not hist.empty and len(hist) > 2:
                    start = float(hist["Close"].iloc[0])
                    end = float(hist["Close"].iloc[-1])
                    if start > 0:
                        tr_pct = (end / start - 1) * 100
            except Exception as he:
                print(f"[screener_v2/yfinance] {ticker} history fail: {he}")
            div_rate = info.get("yield") or info.get("dividendYield") or 0
            row = normalize_row(
                raw_id=ticker,
                raw_name=name,
                raw_currency=currency,
                raw_country=country,
                raw_total_return=tr_pct,
                raw_dividend_rate=div_rate,
                source="yfinance",
            )
            if row:
                rows.append(row)
        except Exception as e:
            print(f"[screener_v2/yfinance] {ticker} fail: {e}")
            continue
    if rows:
        save_cache("yfinance", rows)
        return rows
    return load_cache("yfinance") if use_cache_fallback else []


# ════════════════════════════════════════════════════════════════
# §6 管道 C — SITCA / FundRich（純研究用 + robots.txt 守門）
# ════════════════════════════════════════════════════════════════
_SITCA_REPORT_BASE = "https://www.sitca.org.tw/ROC/Industry/IN2422.aspx"


def fetch_sitca_pool(
    use_cache_fallback: bool = True,
    respect_robots: bool = True,
    sleep_range: tuple[float, float] = (3.0, 5.0),
) -> list[FundETFRow]:
    """SITCA scrape stub：robots.txt 守門 + UA rotation + 3-5s sleep。

    當前為「框架就緒、parser TODO」狀態：
    - robots.txt 不允許 → 直接讀 cache
    - HTTP 200 → 仍走 cache（ASPX postback 表格解析待後續迭代）
    user 後續可在 `_parse_sitca_html(html)` 補 BeautifulSoup 抽 row。
    """
    if respect_robots and not _check_robots(_SITCA_REPORT_BASE):
        print("[screener_v2/sitca] robots.txt deny → cache fallback")
        return load_cache("sitca") if use_cache_fallback else []
    try:
        _polite_sleep(*sleep_range)
        resp = fetch_url(
            _SITCA_REPORT_BASE,
            headers={"User-Agent": _random_ua()},
            timeout=20, retries=2,
        )
        if resp is None or resp.status_code != 200:
            print("[screener_v2/sitca] HTTP fail → cache")
            return load_cache("sitca") if use_cache_fallback else []
        print("[screener_v2/sitca] HTML 200 but parser stub — TODO")
        return load_cache("sitca")
    except Exception as e:
        print(f"[screener_v2/sitca] exception: {e}")
        return load_cache("sitca") if use_cache_fallback else []


# ════════════════════════════════════════════════════════════════
# §7 篩選（user spec §3）
# ════════════════════════════════════════════════════════════════
def filter_rows(
    rows: Iterable[FundETFRow],
    currency: str | None = None,
    country: str | None = None,
    require_return_cover_div: bool = True,
) -> list[FundETFRow]:
    """三條件 AND：currency × country × (total_return ≥ dividend_rate)。

    currency / country = None / "全部" / "ALL" / "*" 視作不限。
    """
    out: list[FundETFRow] = []
    cur = (currency or "").strip()
    cty = (country or "").strip()
    skip_cur = (not cur) or cur in ("全部", "ALL", "*")
    skip_cty = (not cty) or cty in ("全部", "ALL", "*")
    for r in rows:
        if not skip_cur and r.currency.upper() != cur.upper():
            continue
        if not skip_cty and r.country != cty:
            continue
        if require_return_cover_div and r.total_return < r.dividend_rate:
            continue
        out.append(r)
    return out


# ════════════════════════════════════════════════════════════════
# §8 主入口：三軌調度
# ════════════════════════════════════════════════════════════════
def fetch_all_pools(
    use_twse: bool = True,
    use_yfinance: bool = True,
    use_sitca: bool = False,
) -> list[FundETFRow]:
    """同時抓 3 軌（SITCA 預設關，parser stub 階段）。"""
    pool: list[FundETFRow] = []
    if use_twse:
        pool.extend(fetch_twse_etf_pool())
    if use_yfinance:
        pool.extend(fetch_yfinance_pool())
    if use_sitca:
        pool.extend(fetch_sitca_pool())
    return pool


def collect_currencies(rows: Iterable[FundETFRow]) -> list[str]:
    return sorted({r.currency for r in rows if r.currency})


def collect_countries(rows: Iterable[FundETFRow]) -> list[str]:
    return sorted({r.country for r in rows if r.country})
