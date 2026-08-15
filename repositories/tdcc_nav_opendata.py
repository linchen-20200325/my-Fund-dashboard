"""repositories/tdcc_nav_opendata.py — TDCC 境外基金淨值(data.gov.tw dataset 11641)L1 fetcher。

政府開放資料(免登入、你的 App 連得到、非 FundClear 那種會擋):**近 7 天**境外基金每日淨值。
用途:每日 cron 往後累積全持倉官方淨值 → nav_history / cache,根治「抓不到 → 外推 → 假吃本金」。
⚠️ **只有近 7 天**,不能回補過去(過去仍用 FundClear query-history)。

流程(對齊 `tw_pmi_repository` 的 data.gov.tw 慣例):metadata API 取 CSV resource URL → 下載 CSV →
解析 [基金代碼, 基金名稱, 日期, 基金淨值, 計價幣別, ISIN代碼, 總代理機構]。
輸出 `DataFrame[fund_code, name, nav_date↑, nav>0, currency, isin, agent]`(§8.2 L1 純 I/O + 解析)。

⚠️ 日期/欄名格式部署後首抓需人工確認(政府資料偶用民國年或 YYYYMMDD);parse_nav_csv 為純函式,
拿到真實 CSV 一段即可加對應 fixture 鎖定。
"""
from __future__ import annotations

import csv as _csv
import io as _io
import logging

import pandas as pd

from infra.proxy import fetch_url

logger = logging.getLogger(__name__)

_DATASET_ID = "11641"
_META_URLS = (
    f"https://data.gov.tw/api/v2/rest/dataset/{_DATASET_ID}",
    f"https://data.gov.tw/api/v1/rest/dataset/{_DATASET_ID}",
)
_OUT_COLS = ["fund_code", "name", "nav_date", "nav", "currency", "isin", "agent"]

# 欄名候選(TDCC / data.gov.tw 中文欄;各匯出略有差異 → 容忍多名)
_COL_CODE = ("基金代碼", "境外基金代碼", "fundCode")
_COL_NAME = ("基金名稱", "fundName")
_COL_DATE = ("日期", "淨值日期", "navDate", "date")
_COL_NAV = ("基金淨值", "淨值", "nav", "navValue")
_COL_CCY = ("計價幣別", "幣別", "currency")
_COL_ISIN = ("ISIN代碼", "ISIN", "isinCode", "isin")
_COL_AGENT = ("總代理機構", "總代理名稱", "總代理")


def _pick(row: dict, keys) -> str:
    for _k in keys:
        _v = row.get(_k)
        if _v not in (None, ""):
            return str(_v).strip()
    return ""


def _empty() -> pd.DataFrame:
    return pd.DataFrame({_c: pd.Series(dtype="datetime64[ns]" if _c == "nav_date"
                                       else ("float64" if _c == "nav" else "object"))
                         for _c in _OUT_COLS})


def parse_nav_csv(text: str) -> pd.DataFrame:
    """11641 CSV 文字 → `DataFrame[fund_code,name,nav_date↑,nav>0,currency,isin,agent]`。純函式。

    清洗:淨值去逗號/空白轉數值;日期 coerce;丟 NaN/nav<=0;同(code,date)去重 keep-last;
    依 (code, date) 升冪。空/壞 → 空 df 且欄位齊全(不回 None)。
    """
    _rows = list(_csv.DictReader(_io.StringIO(text or "")))
    _recs = []
    for _r in _rows:
        _code = _pick(_r, _COL_CODE)
        _nav = _pick(_r, _COL_NAV).replace(",", "").replace(" ", "")
        _date = _pick(_r, _COL_DATE)
        if not _code or not _nav or not _date:
            continue
        _recs.append({
            "fund_code": _code.upper(), "name": _pick(_r, _COL_NAME),
            "nav_date_raw": _date, "nav_raw": _nav,
            "currency": _pick(_r, _COL_CCY), "isin": _pick(_r, _COL_ISIN),
            "agent": _pick(_r, _COL_AGENT),
        })
    if not _recs:
        return _empty()
    df = pd.DataFrame(_recs)
    df["nav_date"] = pd.to_datetime(df["nav_date_raw"], errors="coerce")
    df["nav"] = pd.to_numeric(df["nav_raw"], errors="coerce")
    df = df.dropna(subset=["nav_date", "nav"])
    df = df[df["nav"] > 0]
    df = df.drop_duplicates(subset=["fund_code", "nav_date"], keep="last")
    df = df.sort_values(["fund_code", "nav_date"]).reset_index(drop=True)
    return df[_OUT_COLS]


def fetch_offshore_nav_recent() -> pd.DataFrame:
    """抓 data.gov.tw 11641(近 7 天境外基金淨值)→ DataFrame。抓不到 → 空 df(欄位齊全,§1 不偽造)。"""
    _csv_url = None
    for _mu in _META_URLS:
        try:
            _r = fetch_url(_mu, timeout=10, retries=1, headers={"Accept": "application/json"})
            if _r is None or _r.status_code != 200:
                continue
            _j = _r.json()
            _res = (_j.get("result", {}).get("resources")
                    or _j.get("resources")
                    or _j.get("data", {}).get("resources") or [])
            for _it in _res:
                _fmt = str(_it.get("format", "")).upper()
                _url = _it.get("url") or _it.get("resourceDownloadUrl")
                if _url and (_fmt == "CSV" or "csv" in str(_url).lower()):
                    _csv_url = _url
                    break
            if _csv_url:
                break
        except Exception as _e:  # noqa: BLE001 — metadata 取不到就換下一個變體
            logger.info("11641 metadata %s 失敗:%s", _mu, _e)
    if not _csv_url:
        logger.warning("11641 找不到 CSV resource URL(data.gov.tw metadata 全敗)")
        return _empty()
    _rc = fetch_url(_csv_url, timeout=15, retries=2)
    if _rc is None or _rc.status_code != 200:
        logger.warning("11641 CSV 下載失敗:%s", _csv_url)
        return _empty()
    return parse_nav_csv(_rc.content.decode("utf-8-sig", errors="ignore"))


__all__ = ["fetch_offshore_nav_recent", "parse_nav_csv"]
