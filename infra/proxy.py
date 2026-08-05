"""infra/proxy.py — NAS Squid 中繼站通用模組（v11.0 從 proxy_helper.py 搬入）

可直接複製到任何 Streamlit 專案使用。
讀取 st.secrets 中的 PROXY_URL 或 [proxy] section，自動降級直連。

v11.0 分層歸位：本檔屬於 Infrastructure Layer，純 HTTP 基礎設施，零業務邏輯。
向後相容：根目錄 proxy_helper.py 保留 `from infra.proxy import *` shim，
        E 階段收尾後 shim 刪除。
"""
import threading

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


# v19.333 review F6:fetch_url 原本每次呼叫都 new Session → TCP/TLS 連線池
# 完全無法跨請求複用,跨國 RTT + handshake 逐請求重付(單檔基金 fallback 鏈
# 動輒十幾個請求,全部重建連線)。改 thread-local 單例:
# - 同執行緒重複呼叫共用同一 Session(urllib3 連線池 keep-alive 生效)
# - 不同執行緒各持一份(requests.Session 非嚴格 thread-safe,per-thread 隔離)
# - proxies / verify 本就逐請求傳入(見 fetch_url),共用 Session 不影響
#   proxy 降級直連邏輯;Retry adapter 隨 make_retry_session 一次掛好
_TLS_HTTP = threading.local()


def _get_thread_session() -> requests.Session:
    """回傳本執行緒的共用 Session(懶建立,含 5xx Retry adapter)。"""
    s = getattr(_TLS_HTTP, "session", None)
    if s is None:
        s = make_retry_session()
        _TLS_HTTP.session = s
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
      ProxyError    → **立刻**降級直連（不 sleep、不重試 —— proxy 連不上時
                      重試同一個 proxy 必然重複失敗，只是白付 retries × 2s）
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

    # 【log 遮罩 query string】§1 保守優先的資安預防。
    # 現況查證:FinMind token 走 `params['token']`、FRED api_key 走 `params['api_key']`,
    # 都不進 url 字串 → 目前無洩漏。但 fetch_url 是全站 30+ caller 的公用入口,任何未來
    # 把 key 塞進 query string 的 caller 都會直接把 secret 印進 stdout,而 Streamlit Cloud
    # 的 log 是 collaborator 可見。砍掉 `?` 之後即可根絕,且 scheme+host+path 完整保留
    # → 除錯仍看得出「哪個來源、哪支 endpoint」,資訊價值不減。
    _url_log = url.split("?")[0]

    sess     = _get_thread_session()   # v19.333 F6:複用 thread-local 連線池
    _perr    = 0
    _block   = 0
    _tmo     = 0   # v18.223：累計 proxy 逾時次數 → 逾時也要降級直連
    _rl_atmp = 0   # v18.278：429 backoff 指針，最多走完 _RATE_LIMIT_BACKOFF_SEC 序列
    # 【狀態碼黑洞修補】原 if 鏈只處理 407/403/429/200，其餘（402 額度用盡 / 401 /
    # 404 / 5xx）什麼都不做就進下一輪，最後 `return None` 零 log → 呼叫端只能報
    # 「無回應」，實際狀態碼與 API msg 全部遺失（FinMind 免費額度 402 被靜默吞掉
    # 130 天即此坑）。以下 `_last_status` 保留最後一次**看到**的狀態碼供收尾 log。
    # ⚠️ 語意精確化：只在 `sess.get` 有回傳 Response 時更新 —— 若 attempt 1 拿 404、
    #    attempt 2 逾時，收尾時 `_last_status` 仍是 404（最後一次「看到」的，不是最後
    #    一次「嘗試」的結果）。收尾 log 因此用 `last_seen_status=` 具名，避免同一行
    #    出現 `status=404, tmo=1` 時被讀 log 的人誤判「最後一次是 404」。
    # §1 Fail Loud：不改回傳型別（維持 Response | None，零 caller 受影響），
    # 只補可觀測性。
    _last_status: "int | None" = None

    for attempt in range(retries):
        try:
            r = sess.get(url, headers=_hdr, params=params,
                         timeout=timeout, proxies=_proxy, verify=_verify)
            _last_status = r.status_code
            if r.status_code == 407:
                print("[proxy] 407 Auth Failed — 確認 secrets 帳密")
                return None
            if r.status_code == 403:
                _block += 1
                # §2.1「MoneyDJ 子網域 403 走 fallback chain」是核心情境，原本零 log
                # → 無法分辨「來源被擋」與「網路壞掉」。補 log 讓 fallback 可觀測。
                print(f"[proxy] 403 Forbidden ({_block}/2) — 來源封鎖或需 Referer：{_url_log[:80]}")
                # 【v19.425 修：先判「還會不會再試」，再決定要不要 sleep】
                # 原碼順序是 `sleep → if _block >= 2: break`，兩種情況白睡：
                #   (a) `_block >= 2` → sleep 完立刻 break，那 2.5~6s 沒有任何
                #       retry 在等它；接手的是下方**降級直連**（`proxies={}`，
                #       走的是完全不同的出口 IP，與 proxy 端的封鎖狀態無共享），
                #       而 ProxyError 分支本來就是 0 sleep 直接降級 —— 行為對齊。
                #   (b) `_block == 1` 但已是最後一次 attempt → sleep 完 `continue`，
                #       for 迴圈當場耗盡，且 `_block < 2` 連降級都不觸發 = 純浪費。
                # sleep 的原意是「retry 前退避」，因此只在**確定還有下一輪**時睡。
                # `_block` 計數與 break 條件均不變 → 降級判斷（`_block >= 2`）行為零改動。
                if _block >= 2 or attempt >= retries - 1:
                    break
                _t.sleep(_rnd.uniform(2.5, 6.0))
                continue
            if r.status_code == 429:
                if _rl_atmp < len(_RATE_LIMIT_BACKOFF_SEC):
                    _sleep_s = _RATE_LIMIT_BACKOFF_SEC[_rl_atmp]
                    # 【v19.425 修：最後一次 attempt 後不再退避】
                    # 預設 retries=3、backoff=(2,4,8) → attempt 2（最後一次）時
                    # `_rl_atmp=2 < 3` 成立 → sleep **8 秒** → continue → for 迴圈
                    # 當場耗盡，那 8 秒沒有任何 retry 在等它，是三個分支裡最大的
                    # 淨損失。（也因此 `_rl_atmp >= len(...)` 的放棄分支在預設
                    # retries=3 下其實永遠走不到。）
                    # 只拿掉 sleep、**不改控制流**（仍 `continue`）—— 若同一 URL
                    # 先前發生過 Timeout/ProxyError，下方 `_tmo/_perr > 0` 的
                    # 降級直連仍有機會救回來，不可在此提前 return。
                    if attempt < retries - 1:
                        print(f"[proxy] 429 Rate Limit — sleep {_sleep_s}s before retry "
                              f"({_rl_atmp + 1}/{len(_RATE_LIMIT_BACKOFF_SEC)}): {_url_log[:80]}")
                        _t.sleep(_sleep_s)
                    else:
                        print(f"[proxy] 429 Rate Limit — 已無重試次數 "
                              f"(attempt {attempt + 1}/{retries})，不再退避：{_url_log[:80]}")
                    _rl_atmp += 1
                    continue
                print(f"[proxy] 429 已重試 {_rl_atmp} 次仍 rate-limited，放棄：{_url_log[:80]}")
                return None
            if r.status_code == 200:
                return r
            # ── 未預期狀態碼（402 額度用盡 / 401 / 404 / 5xx …）─────────────
            # 原本這裡沒有 else，直接掉出 if 鏈進下一輪重試，狀態碼與 body 全丟。
            # §1：不可讓錯誤靜默 —— 至少要能在 log 看見「是誰、回了什麼」。
            # body 取前 200 字：FinMind 402 的 {"msg": "...", "status": 402} 就在裡面。
            # ⚠️ 這行在 try 內，**加 log 不可自殘**：
            #   (a) `getattr(r, "text", "")` 的 default 只攔 AttributeError，攔不住
            #       property getter 內部拋的例外（stream 中斷 / charset_normalizer
            #       解碼例外 / 非標準 Response 物件）→ 例外會冒泡到下方
            #       `except Exception: break`，把本該 retry 3 次的路徑變成立刻中斷，
            #       且 _perr/_block/_tmo 全為 0 → 連降級直連都不觸發，直接 return None。
            #   (b) `r.text` 對大 body 會觸發 apparent_encoding（chardet /
            #       charset_normalizer 全文掃描）；幾 MB 的非 200 HTML 會有可觀延遲。
            # → 改讀 bytes：`r.content` 不觸發編碼偵測，**先切片再 decode**（只解 200
            #   bytes），`errors="replace"` 保證不拋；外層再包 try 兜住缺 content 的物件。
            try:
                _body = r.content[:200].decode("utf-8", errors="replace").replace("\n", " ")
            except Exception:
                _body = "<body unavailable>"
            print(f"[proxy] 未預期狀態碼 {r.status_code} "
                  f"(attempt {attempt + 1}/{retries}): {_url_log[:80]} | body={_body}")
        except requests.exceptions.ProxyError as e:
            _perr += 1
            # 【v19.424 修:立刻 break,不 sleep 不重試】
            # ProxyError = **proxy 本身**連不上(連線被拒 / DNS 失敗 / Squid 掛掉),
            # 對「同一個壞掉的 proxy」重試 3 次必然重複失敗,只是白付 3×2s sleep。
            # 本函式 docstring 的行為矩陣原本就寫「ProxyError → 降級直連」——
            # 立刻 break 讓下方降級區塊接手,才是原設計意圖;`_perr` 已 +1,
            # `if _proxy and (_perr > 0 ...)` 仍會觸發降級,行為不變只是快 6 秒。
            # 實測影響:NAS proxy 離線時每個 URL 白等 6s → 28 個總經指標 + 逐檔基金
            # 抓取累積數分鐘純睡眠;tests/test_app_apptest.py 的 _force_network_refused
            # (刻意把 proxy 指向 127.0.0.1:9 讓它快速失敗)也因此被推過 60s timeout。
            # ⚠️ 與 429 的差異:429 是「對端限流」,sleep 後重試同一端點有意義;
            #    ProxyError 是「中繼站不存在」,重試沒有任何狀態會改變。
            print(f"[proxy] ProxyError attempt {attempt+1} — 不重試,直接降級：{e}")
            break
        except requests.exceptions.Timeout:
            _tmo += 1
            print(f"[proxy] Timeout attempt {attempt+1}: {_url_log[:60]}")
            # 【v19.425 修：最後一次 attempt 後不再 sleep】
            # Timeout 與 ProxyError 不同 —— 對端可能只是暫時忙，重試有意義，
            # 所以**保留**退避重試（不比照 ProxyError 立刻 break）。但最後一次
            # attempt 之後 for 迴圈直接結束，那 2s 沒有任何 retry 在等它，
            # 且下方 `_tmo > 0` 的降級直連會立刻接手 → 每條逾時 URL 白付 2s。
            if attempt < retries - 1:
                _t.sleep(2)
        except Exception as e:
            print(f"[proxy] Error: {e}")
            break

    # v18.223：proxy 逾時（_tmo）同樣降級直連 — 原本只有 ProxyError/403 會降級，
    # 導致「proxy 在但很慢」時每個 endpoint 逾時後直接回 None（FRED/Yahoo 本可直連救回）。
    if _proxy and (_perr > 0 or _block >= 2 or _tmo > 0):
        print(f"[proxy] 降級直連：{_url_log[:80]}")
        try:
            r_dc = sess.get(url, headers=_hdr, params=params,
                            timeout=timeout, proxies={}, verify=True)
            _last_status = r_dc.status_code   # 收尾 log 要反映「最後一次」真狀態
            if r_dc.status_code == 200:
                print("[proxy] 直連成功")
                return r_dc
            print(f"[proxy] 直連非 200：status={r_dc.status_code}")
        except Exception as e_dc:
            print(f"[proxy] 直連失敗：{e_dc}")

    # 收尾 log：原本這行是純 `return None`，零輸出 —— 呼叫端只知道「無回應」，
    # 完全無法分辨 402 額度用盡 / 404 dataset 不存在 / 逾時 / proxy 壞掉。
    # `last_seen_status` 而非 `status`：它是「最後一次**看到**的狀態碼」，逾時 /
    # ProxyError 的 attempt 不會更新它。同一行出現 `last_seen_status=404, tmo=1` 時，
    # 措辭本身就講清楚 404 不必然是最後一次嘗試的結果。
    print(f"[proxy] 全部嘗試失敗（last_seen_status={_last_status}, "
          f"perr={_perr}, block={_block}, tmo={_tmo}）：{_url_log[:80]}")
    return None
