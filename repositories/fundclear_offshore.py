"""repositories/fundclear_offshore.py — 境外基金資訊觀測站(FundClear)歷史淨值 L1 fetcher。

依「境外基金資訊觀測站 歷史淨值抓取程式 開發規格書」(2026-08-13 實測)實作 offshore
`/api/offshore/*` JSON API,與既有 `_src_fundclear_nav`(SmartFundAPI 單碼、~5.5yr)互補:

- **單次 POST 回傳完整歷史**(實測 20yr / 4994 筆,無分頁)→ 不做日期分段(spec FR-2)。
- **3(4)端點列舉**:organize → fund-name → fund-class → query-history,以
  `(organizeCode, fundCode, fundClassCode)` 三碼定位(本 repo 原本無此三碼)。
- **資料陷阱(spec §3,極重要)**:
    * `navValueDiffRate` = 該日持有至最新日的**累積**報酬率(非單日漲跌)→ **丟棄**。
    * `lastDayNav` = 恆等於最新一日淨值(每列都一樣)→ **丟棄**。
    * `navValue` 為六位小數**字串** → 清逗號/空白後轉數值。
- **成功/失敗 schema 不同(spec §2.4)**:以 `tableList` 是否存在且非空判定,**不依賴
  HTTP status**(失敗時仍回 200)。
- **`fundClassCode` 不可傳 "all"**(spec §3.3)→ 明確 raise ValueError。

L1 純網路層(§8.2):走 `infra.proxy.get_proxy_config` 的 proxy→直連降級;節流 ≥0.7s
(FR-4);md5 disk cache(FR-3,**不可用內建 hash()**,PYTHONHASHSEED 隨機化);清洗 FR-7;
輸出 `DataFrame[nav_date↑, nav>0]` + `attrs["currency"]`(FR-6)。不 import streamlit UI。

⚠️ **未驗證項(spec §2.5 / §7)**:機構清單 endpoint 路徑、Python 冷啟動(無 cookie)可行性。
`list_organizes()` 依序試候選路徑;`_post_json` 失敗時附 GET-first-取-cookie 的 fallback。
本模組於**部署環境(NAS proxy)**首次執行時須人工確認上述兩點。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import date
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

BASE_URL = "https://www.fundclear.com.tw"
_ORGANIZE_DEFAULT = "019"                 # ALLIANZ GLOBAL INVESTORS GMBH (AGIF),spec §2.5 已知
_THROTTLE_SEC = 0.7                       # FR-4:相鄰請求最小間隔
_RETRY_STATUS = {429, 500, 502, 503, 504}  # FR-5
_RETRY_MAX = 4
_BACKOFF_FACTOR = 0.8
_TIMEOUT = (10, 90)                        # NFR-1:(connect, read);20yr 回應 ~115KB,read 需寬鬆
_CACHE_DIR = "cache/fundclear"

# 端點(spec §2)
_EP_FUND_NAME = "/api/offshore/common-select/fund-name-selection"
_EP_FUND_CLASS = "/api/offshore/common-select/fund-class-selection"
_EP_QUERY_HISTORY = "/api/offshore/nav-profit/query-history"
# 機構清單:spec §2.5 未驗證,依 common-select 家族命名慣例的候選路徑,依序試
_EP_ORGANIZE_CANDIDATES = (
    "/api/offshore/common-select/organize-selection",
    "/api/offshore/common-select/fund-organize-selection",
    "/api/offshore/common-select/organization-selection",
    "/api/offshore/common-select/institution-selection",
)

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/offshore/nav-profit/fund-nav?type=history",
}

_OUT_COLS = ["nav_date", "nav"]
_last_request_ts = 0.0

# 已知機構代碼(spec §2.5 機構清單 endpoint 未驗證/不可達時的 fallback;user 部署實測回報)。
# 之後可續補;找不到的機構仍可用「掃描全部機構」(find_fund_candidates scan_range)。
_KNOWN_ORGANIZES = (
    {"name": "安聯 Allianz (AGIF)", "value": "019"},
    {"name": "聯博 AllianceBernstein", "value": "037"},
)


class FundclearError(Exception):
    """FundClear offshore 抓取失敗(§1 Fail Loud:呼叫端須看見,不靜默)。"""


# ── 磁碟快取(FR-3:md5(sort_keys),不用內建 hash())────────────────────────
def _cache_key(path: str, body: dict) -> str:
    _raw = json.dumps({"path": path, "body": body}, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(_raw.encode("utf-8")).hexdigest()[:16]


def _cache_read(key: str) -> Any:
    _fp = os.path.join(_CACHE_DIR, f"{key}.json")
    if not os.path.exists(_fp):
        return None
    try:
        with open(_fp, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001 — 快取毀損不該炸主流程,當 miss
        logger.warning("fundclear cache read fail %s: %s", key, e)
        return None


def _cache_write(key: str, data: Any) -> None:
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        with open(os.path.join(_CACHE_DIR, f"{key}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001 — 寫快取失敗只記 warning,不影響回傳
        logger.warning("fundclear cache write fail %s: %s", key, e)


# ── 網路層(POST JSON + 節流 + 退避重試 + proxy→直連降級)────────────────────
def _throttle() -> None:
    global _last_request_ts
    _elapsed = time.time() - _last_request_ts
    if _elapsed < _THROTTLE_SEC:
        time.sleep(_THROTTLE_SEC - _elapsed)
    _last_request_ts = time.time()


def _post_json(path: str, body: dict, *, use_cache: bool = True,
               retries: int = _RETRY_MAX) -> Any:
    """POST JSON → 解析後的 JSON(dict/list)。快取命中不打網路。

    proxy→直連降級(對齊 infra.proxy 慣例);429/5xx 指數退避重試(FR-5)。
    冷啟動(無 cookie)若被拒,spec §7.1 建議先 GET 首頁取 cookie —— 以同一 Session 達成。
    retries:endpoint 探測時傳小值(避免對錯路徑狂重試 + 浪費節流時間)。
    """
    _key = _cache_key(path, body)
    if use_cache:
        _hit = _cache_read(_key)
        if _hit is not None:
            return _hit

    import requests

    from infra.proxy import get_proxy_config
    _proxy = get_proxy_config() or None
    _verify = not bool(_proxy)
    _url = f"{BASE_URL}{path}"

    _last_exc: Exception | None = None
    for _attempt in range(retries):
        try:
            _throttle()   # FR-4:每次實際打網路前節流 ≥0.7s(稽核修:原本定義了卻沒呼叫)
            with requests.Session() as sess:
                sess.headers.update(_HEADERS)
                # spec §7.1:冷啟動先 GET 首頁取 session cookie,再打 API(同一 Session)
                try:
                    sess.get(_HEADERS["Referer"], proxies=_proxy, verify=_verify,
                             timeout=_TIMEOUT)
                except Exception:  # noqa: BLE001 — 取 cookie 失敗不阻斷,直接試 POST
                    pass
                resp = sess.post(_url, json=body, proxies=_proxy, verify=_verify,
                                 timeout=_TIMEOUT)
            if resp.status_code in _RETRY_STATUS:
                raise FundclearError(f"HTTP {resp.status_code}")
            if resp.status_code != 200:
                raise FundclearError(f"非 200:HTTP {resp.status_code}")
            data = resp.json()
            if use_cache:
                _cache_write(_key, data)
            return data
        except Exception as e:  # noqa: BLE001 — 網路/解析例外皆退避重試,末次往上拋
            _last_exc = e
            # proxy 連不上 → 立刻改直連(不 sleep),對齊 infra.proxy 行為
            if _proxy is not None and isinstance(e, requests.exceptions.ProxyError):
                _proxy, _verify = None, True
                continue
            if _attempt < retries - 1:
                time.sleep(_BACKOFF_FACTOR * (2 ** _attempt))
    raise FundclearError(f"POST {path} 失敗(重試 {retries} 次):{_last_exc}") from _last_exc


# ── 解析層(純函式,可用固定 JSON fixture 離線測試,spec §9)────────────────────
def _parse_selection(data: Any) -> list[dict]:
    """`[{name, value}]` 選單回應 → 正規化 list[dict]。非預期形狀 → []。"""
    if not isinstance(data, list):
        return []
    out = []
    for row in data:
        if isinstance(row, dict) and row.get("value"):
            out.append({"name": str(row.get("name") or ""), "value": str(row["value"])})
    return out


def _empty_nav_df() -> pd.DataFrame:
    """空結果:欄位齊全的空 DataFrame(FR-6:不可回 None/raise)。"""
    _df = pd.DataFrame({"nav_date": pd.Series(dtype="datetime64[ns]"),
                        "nav": pd.Series(dtype="float64")})
    _df.attrs["currency"] = ""
    return _df


def _parse_nav_history(data: Any) -> pd.DataFrame:
    """query-history 回應 → `DataFrame[nav_date↑, nav>0]` + attrs["currency"](FR-6/FR-7)。

    §2.4:成功頂層有 tableList、失敗頂層有 message/data → 以 tableList 存在且非空判定。
    §3:丟棄 navValueDiffRate(累積報酬非單日)、lastDayNav(恆為最新日)。
    """
    if not isinstance(data, dict):
        return _empty_nav_df()
    table = data.get("tableList")
    if not isinstance(table, list) or not table:      # 失敗 schema / 空 → 空 df
        return _empty_nav_df()

    _rows = [r for r in table if isinstance(r, dict)]
    df = pd.DataFrame(_rows)
    if "navTxnDate" not in df.columns or "navValue" not in df.columns:
        return _empty_nav_df()

    # FR-7 清洗(全向量化,禁 iterrows/apply)
    nav_date = pd.to_datetime(df["navTxnDate"], format="%Y/%m/%d", errors="coerce")
    nav = pd.to_numeric(
        df["navValue"].astype(str).str.replace(r"[,\s]", "", regex=True),
        errors="coerce",
    )
    out = pd.DataFrame({"nav_date": nav_date, "nav": nav})
    out = out.dropna(subset=["nav_date", "nav"])       # 丟 NaN
    out = out[out["nav"] > 0]                          # 丟 nav<=0(§3.2 / FR-7)
    out = out.drop_duplicates(subset=["nav_date"], keep="first")
    out = out.sort_values("nav_date").reset_index(drop=True)  # API 為降冪 → 轉升冪(§2.4 / FR-6)
    out = out[_OUT_COLS]
    out.attrs["currency"] = str(data.get("fundCurr") or "")  # 陷阱欄位未帶入 → 已丟棄
    return out


# ── 公開 API(FR-1)────────────────────────────────────────────────────────
def list_organizes() -> list[dict]:
    """機構清單 `[{name, value}]`。spec §2.5 未驗證 → 試候選路徑 × body 變體(retries=1,
    避免對錯路徑狂重試),全敗 raise(呼叫端應提示 user 改填機構代碼或回報實際 endpoint)。"""
    for _ep in _EP_ORGANIZE_CANDIDATES:
        for _body in ({"all": False}, {"all": True}, {}):
            try:
                _got = _parse_selection(_post_json(_ep, _body, use_cache=False, retries=1))
                if _got:
                    return _got
            except FundclearError as e:
                logger.info("organize 候選 %s body=%s 失敗:%s", _ep, _body, e)
    # endpoint 全敗 → 退回已知機構 fallback(不 raise:至少 019/037 可用,其餘用掃描)
    logger.warning("機構清單 endpoint 全部候選失敗 → 退回已知機構 fallback(%d 家)",
                   len(_KNOWN_ORGANIZES))
    return list(_KNOWN_ORGANIZES)


def list_funds(organize_code: str = _ORGANIZE_DEFAULT) -> list[dict]:
    """某機構的基金名稱清單 `[{name, value=fundCode}]`。"""
    return _parse_selection(
        _post_json(_EP_FUND_NAME, {"all": False, "organizeCode": organize_code}))


def list_classes(organize_code: str, fund_code: str) -> list[dict]:
    """某基金的級別清單 `[{name, value=fundClassCode}]`。"""
    return _parse_selection(_post_json(
        _EP_FUND_CLASS,
        {"all": False, "organizeCode": organize_code, "fundCode": fund_code}))


def get_nav_history(organize_code: str, fund_code: str, class_code: str,
                    start: date, end: date) -> pd.DataFrame:
    """核心:單次抓完整歷史 → `DataFrame[nav_date↑, nav>0]` + attrs["currency"]。

    class_code="all" → ValueError(spec §3.3:級別代碼不可傳 all)。
    查無資料 → 空 df 且欄位齊全(不 raise / 不回 None,FR-6)。
    """
    if str(class_code).strip().lower() == "all":
        raise ValueError("fundClassCode 不可傳 'all'(spec §3.3);須指定具體級別代碼")
    body = {
        "organizeCode": organize_code,
        "fundCode": fund_code,
        "fundClassCode": class_code,
        "startDate": start.strftime("%Y/%m/%d"),
        "endDate": end.strftime("%Y/%m/%d"),
    }
    return _parse_nav_history(_post_json(_EP_QUERY_HISTORY, body))


__all__ = ["FundclearError", "list_organizes", "list_funds", "list_classes",
           "get_nav_history"]
