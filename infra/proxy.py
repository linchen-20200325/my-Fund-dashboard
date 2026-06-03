"""infra/proxy.py — NAS Squid 中繼站通用模組（v11.0 從 proxy_helper.py 搬入）

可直接複製到任何 Streamlit 專案使用。
讀取 st.secrets 中的 PROXY_URL 或 [proxy] section，自動降級直連。

v11.0 分層歸位：本檔屬於 Infrastructure Layer，純 HTTP 基礎設施，零業務邏輯。
向後相容：根目錄 proxy_helper.py 保留 `from infra.proxy import *` shim，
        E 階段收尾後 shim 刪除。
"""
import requests
import urllib3
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_PROXY_CFG_CACHE = None
_PROXY_CFG_TS    = 0.0
_PROXY_CFG_TTL   = 300   # 秒：NAS 恢復後最多 5 分鐘自動生效


def reset_proxy_cache():
    """手動清除快取，下次 get_proxy_config() 重新讀取 secrets。"""
    global _PROXY_CFG_CACHE, _PROXY_CFG_TS
    _PROXY_CFG_CACHE = None
    _PROXY_CFG_TS    = 0.0


def get_proxy_config() -> "dict | None":
    """
    讀取 NAS Proxy 設定。
    新格式（優先）：st.secrets["PROXY_URL"] = "http://user:pwd@host:3128"
    舊格式（相容）：st.secrets["proxy"]["username/password/endpoint"]
    回傳 {"http": url, "https": url}，或 None（無設定 / 例外 → 降級直連）。
    """
    global _PROXY_CFG_CACHE, _PROXY_CFG_TS
    import time as _t
    if _PROXY_CFG_CACHE is not None and (_t.time() - _PROXY_CFG_TS) < _PROXY_CFG_TTL:
        return _PROXY_CFG_CACHE if _PROXY_CFG_CACHE else None
    try:
        import streamlit as _st
        if "PROXY_URL" in _st.secrets:
            _url = _st.secrets["PROXY_URL"]
        else:
            _p   = _st.secrets["proxy"]
            _url = f"http://{_p['username']}:{_p['password']}@{_p['endpoint']}"
        _PROXY_CFG_CACHE = {"http": _url, "https": _url}
    except Exception:
        _PROXY_CFG_CACHE = {}
    _PROXY_CFG_TS = _t.time()
    return _PROXY_CFG_CACHE if _PROXY_CFG_CACHE else None


def make_retry_session() -> requests.Session:
    """5xx 指數退避 Session。

    v18.220 fail-fast：`read=0` — read-timeout 不在 urllib3 層重試（交給外層
    fetch_url 迴圈 + 直連降級處理），避免「逾時被三層重試放大」拖慢抓取；
    `status=2` 仍保留伺服器暫時 5xx（500/502/503/504）的重試韌性。
    """
    _retry = Retry(
        total=2, connect=1, read=0, status=2,
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504],
        raise_on_status=False,
    )
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=_retry))
    s.mount("http://",  HTTPAdapter(max_retries=_retry))
    return s


# ════════════════════════════════════════════════════════════
# v18.115 B-A：fund_fetcher 殘 593 行 HTTP 層收口到本檔
# ════════════════════════════════════════════════════════════
def _proxies() -> dict:
    """便利函式：回傳 proxies dict（無 Proxy 時為空 dict，不影響直連）。"""
    return get_proxy_config() or {}


def _ssl_verify() -> bool:
    """Proxy 模式跳過 SSL 驗證（Squid CONNECT 隧道與 MoneyDJ 憑證不相容），
    直連模式則正常驗證。"""
    return not bool(get_proxy_config())


# ── 全局 urllib opener 安裝 ────────────────────────────────
# 場景：repositories/fund_repository.py 內有 30+ 處裸 urllib.request.urlopen()
#      （TDCC / cnyes / TCB / Morningstar 等資料來源），它們**沒**走 requests 的
#      proxies 參數 → Streamlit Cloud IP 被 moneydj 封時整條死。
# 修法：install_opener 一次性把 NAS Proxy 套到所有 urllib.request 呼叫，
#      無需逐個 source 改寫。已快取 → 重複呼叫零成本。
_URLLIB_OPENER_INSTALLED = False


def install_global_urllib_proxy() -> None:
    """把 NAS Proxy 套到全局 urllib opener，讓裸 urlopen() 也走中繼站。"""
    global _URLLIB_OPENER_INSTALLED
    if _URLLIB_OPENER_INSTALLED:
        return
    cfg = get_proxy_config()
    if not cfg:
        _URLLIB_OPENER_INSTALLED = True   # 標記已嘗試，避免每次呼叫都讀 secrets
        return
    import urllib.request as _ur
    handler = _ur.ProxyHandler({"http": cfg["http"], "https": cfg["https"]})
    _ur.install_opener(_ur.build_opener(handler))
    _URLLIB_OPENER_INSTALLED = True
    print("[proxy] urllib 全局 opener 已安裝，所有裸 urlopen() 自動走 NAS")


# 模組載入即嘗試安裝（無 proxy 時 no-op；fund_fetcher / fund_repository 任一 import
# infra.proxy 都會觸發，零額外配置）
install_global_urllib_proxy()


# v18.278：429 rate-limit 重試間隔（鏡像 scripts/update_macro_history.py 的
# `_FRED_429_BACKOFF_SEC`）。FRED / Yahoo / er-api 等公開 endpoint 在 burst
# 後常回 429，舊版 fetch_url 沒處理 429 → 整 series 靜默掉資料。
_RATE_LIMIT_BACKOFF_SEC: tuple = (2.0, 4.0, 8.0)


def fetch_url(
    url:     str,
    headers: dict = None,
    params:  dict = None,
    timeout: int  = 20,
    retries: int  = 3,
) -> "requests.Response | None":
    """
    通用 HTTP GET（含 NAS Proxy 中繼 + 自動降級直連）。

    行為矩陣：
      Proxy 正常    → 走 NAS，SSL verify=False（Squid CONNECT 相容）
      407 Auth      → 立即回傳 None，不重試
      403 ×2        → 提前跳出，降級直連
      429 Rate Limit→ exponential backoff sleep 2/4/8 秒後重試（最多 3 次）
      ProxyError    → 降級直連
      無 Proxy 設定 → 直連，SSL verify=True
    """
    import time as _t
    import random as _rnd

    _proxy  = get_proxy_config() or {}
    _verify = not bool(_proxy)
    _hdr = {
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9",
    }
    if headers:
        _hdr.update(headers)

    sess     = make_retry_session()
    _perr    = 0
    _block   = 0
    _tmo     = 0   # v18.223：累計 proxy 逾時次數 → 逾時也要降級直連
    _rl_atmp = 0   # v18.278：429 backoff 指針，最多走完 _RATE_LIMIT_BACKOFF_SEC 序列

    for attempt in range(retries):
        try:
            r = sess.get(url, headers=_hdr, params=params,
                         timeout=timeout, proxies=_proxy, verify=_verify)
            if r.status_code == 407:
                print("[proxy] 407 Auth Failed — 確認 secrets 帳密")
                return None
            if r.status_code == 403:
                _block += 1
                _t.sleep(_rnd.uniform(2.5, 6.0))
                if _block >= 2:
                    break
                continue
            if r.status_code == 429:
                if _rl_atmp < len(_RATE_LIMIT_BACKOFF_SEC):
                    _sleep_s = _RATE_LIMIT_BACKOFF_SEC[_rl_atmp]
                    print(f"[proxy] 429 Rate Limit — sleep {_sleep_s}s before retry "
                          f"({_rl_atmp + 1}/{len(_RATE_LIMIT_BACKOFF_SEC)}): {url[:80]}")
                    _t.sleep(_sleep_s)
                    _rl_atmp += 1
                    continue
                print(f"[proxy] 429 已重試 {_rl_atmp} 次仍 rate-limited，放棄：{url[:80]}")
                return None
            if r.status_code == 200:
                return r
        except requests.exceptions.ProxyError as e:
            _perr += 1
            print(f"[proxy] ProxyError attempt {attempt+1}: {e}")
            _t.sleep(2)
        except requests.exceptions.Timeout:
            _tmo += 1
            print(f"[proxy] Timeout attempt {attempt+1}: {url[:60]}")
            _t.sleep(2)
        except Exception as e:
            print(f"[proxy] Error: {e}")
            break

    # v18.223：proxy 逾時（_tmo）同樣降級直連 — 原本只有 ProxyError/403 會降級，
    # 導致「proxy 在但很慢」時每個 endpoint 逾時後直接回 None（FRED/Yahoo 本可直連救回）。
    if _proxy and (_perr > 0 or _block >= 2 or _tmo > 0):
        print(f"[proxy] 降級直連：{url[:80]}")
        try:
            r_dc = sess.get(url, headers=_hdr, params=params,
                            timeout=timeout, proxies={}, verify=True)
            if r_dc.status_code == 200:
                print("[proxy] 直連成功")
                return r_dc
        except Exception as e_dc:
            print(f"[proxy] 直連失敗：{e_dc}")

    return None
