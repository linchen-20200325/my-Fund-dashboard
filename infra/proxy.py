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
    """5xx 指數退避 Session（最多重試 3 次，backoff 0.3/0.6/1.2s）。"""
    _retry = Retry(
        total=3, backoff_factor=0.3,
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
      ProxyError    → 降級直連
      無 Proxy 設定 → 直連，SSL verify=True
    """
    import time as _t, random as _rnd

    _proxy  = get_proxy_config() or {}
    _verify = not bool(_proxy)
    _hdr = {
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9",
    }
    if headers:
        _hdr.update(headers)

    sess   = make_retry_session()
    _perr  = 0
    _block = 0

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
            if r.status_code == 200:
                return r
        except requests.exceptions.ProxyError as e:
            _perr += 1
            print(f"[proxy] ProxyError attempt {attempt+1}: {e}")
            _t.sleep(2)
        except requests.exceptions.Timeout:
            print(f"[proxy] Timeout attempt {attempt+1}: {url[:60]}")
            _t.sleep(2)
        except Exception as e:
            print(f"[proxy] Error: {e}")
            break

    if _proxy and (_perr > 0 or _block >= 2):
        print(f"[proxy] 降級直連：{url[:80]}")
        try:
            r_dc = sess.get(url, headers=_hdr, params=params,
                            timeout=timeout, proxies={}, verify=True)
            if r_dc.status_code == 200:
                print(f"[proxy] 直連成功")
                return r_dc
        except Exception as e_dc:
            print(f"[proxy] 直連失敗：{e_dc}")

    return None
