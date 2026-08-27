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

# v3 憲法 §02「失敗時退避，不連續轟炸來源」——「本次不試這個來源」的狀態機。
# 分層：兩者同為 L0 Infra（infra.source_backoff → infra.cache → shared.backoff_policy，
# 全程下行 / 同層，無 L1+ 依賴，不違 §8.2 硬規則 3）。
from infra import source_backoff as _sb

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
    backoff_on_429: bool = True,
    bypass_backoff: bool = False,
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

    v3 憲法 §02「失敗時退避，不連續轟炸來源」（`infra.source_backoff`）：
      進場   → 該 host 仍在冷卻期 → **一個封包都不發**，直接回 None（呼叫端
               的 fallback chain 會自然走下一個來源；語意與「打了但失敗」相同）
      200    → 解除該 host 的退避（含降級直連成功）
      失敗   → 依失敗類型套用冷卻期（403 封鎖 / 429 限流 / 逾時 / 5xx 各不同；
               **404 與 407 刻意不退避**，理由見 `shared/backoff_policy.py`）
      ⚠️ 退避**不快取任何值** —— 不存成功值也不存失敗值，只存「何時可以再試」，
         故 §1 Fail Loud 完全不受影響：整條 chain 都在冷卻時照樣 fail loud。
      `bypass_backoff=True` 供「刻意逐源探測」的診斷路徑用（Tab5 資料看板），
      本輪**無 caller** —— 改 UI 屬 §-1.5.4 草稿先行，只留介面不動畫面。
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

    # ── v3 §02 退避進場檢查：冷卻期內直接放棄，**不發任何請求** ──────────
    # 放在 session 建立與 proxy 讀取之**前**：退避的整個意義就是「這一輪連碰都不碰」。
    _src_key = _sb.source_key(url)
    if not bypass_backoff:
        _skip, _left, _kind = _sb.should_skip(_src_key)
        if _skip:
            print(f"[proxy] 退避中，跳過不打（source={_src_key}, kind={_kind}, "
                  f"剩餘 {_left:.0f}s）：{_url_log[:80]}")
            return None

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

    # v19.501 §2 durable:scalar timeout 被 requests 分別套在 connect/read 上,但 proxy
    # 半死時 20s 的 TCP 握手太久(user 2026-08-21 總經載入卡 10 分鐘的放大器之一)。拆成
    # (connect, read):握手 5s 快速失敗→轉降級直連,read 保留完整秒數。呼叫端傳入的
    # timeout(12/15/20)全部沿用,零 caller 介面改動。
    _to = (min(5, timeout), timeout) if isinstance(timeout, (int, float)) else timeout

    for attempt in range(retries):
        try:
            r = sess.get(url, headers=_hdr, params=params,
                         timeout=_to, proxies=_proxy, verify=_verify)
            _last_status = r.status_code
            if r.status_code == 407:
                print("[proxy] 407 Auth Failed — 確認 secrets 帳密")
                # v3 §02：407 是**我方 NAS Squid 帳密設定錯**，請求根本沒到達來源
                # → 分類為 proxy_auth，`shared/backoff_policy.py` 明訂**不退避**
                # （退避來源等於罰錯人，還會把一個改 secrets 就能修的設定錯誤，
                #   偽裝成一整排來源的「已跳過」）。呼叫仍走分類函式，讓「退不退避」
                #   這個決定只有 SSOT 一個地方說了算。
                _sb.record_failure(_src_key, "proxy_auth")
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
                # v19.507:caller 明確要求「429 不退避」(如 Yahoo Chart:限流不會在 2/4/8s
                # 內解除,重試純白等 ~14s/次 × 8 標的 = ~56s,是總經載入 75s 逾時的主因)→
                # 直接回 None,那個指標誠實留空(§1)。預設 backoff_on_429=True 行為與契約測試不變。
                if not backoff_on_429:
                    print(f"[proxy] 429 Rate Limit — fail-fast(caller 要求不退避):{_url_log[:80]}")
                    # v3 §02：`backoff_on_429=False` 說的是「**這一次呼叫內**不要 sleep 重試」
                    # （v19.507：Yahoo 限流不會在 2/4/8s 內解除，白等 14s）——
                    # 它**不是**「下一次 rerun 可以馬上再打一次」。來源級冷卻照記，
                    # 這正是「不連續轟炸」要擋的那個放大器（8 標的 × 每次互動 rerun）。
                    _sb.record_failure(_src_key, "rate_limited")
                    return None
                # ⚠️ v19.425 已查證但**未動**的同型問題（待 user 裁示，§-1）：
                #   預設 retries=3、backoff=(2,4,8) → attempt 2（最後一次）時
                #   `_rl_atmp=2 < 3` 仍成立 → sleep **8 秒** → continue → for 迴圈
                #   當場耗盡，那 8 秒沒有任何 retry 在等它（三個分支裡最大的淨損失；
                #   也因此下方 `_rl_atmp >= len(...)` 的放棄分支在預設 retries=3
                #   永遠走不到）。**不改的理由**：`tests/test_proxy_infra.py::
                #   test_fetch_url_429_exhausts_returns_none_with_full_backoff_sequence`
                #   把 `sleeps == [2.0, 4.0, 8.0]` 釘成契約（v18.277 對齊 cron job），
                #   改行為必須同步改那個測試 = 契約變更，需明確核准。
                if _rl_atmp < len(_RATE_LIMIT_BACKOFF_SEC):
                    _sleep_s = _RATE_LIMIT_BACKOFF_SEC[_rl_atmp]
                    print(f"[proxy] 429 Rate Limit — sleep {_sleep_s}s before retry "
                          f"({_rl_atmp + 1}/{len(_RATE_LIMIT_BACKOFF_SEC)}): {_url_log[:80]}")
                    _t.sleep(_sleep_s)
                    _rl_atmp += 1
                    continue
                print(f"[proxy] 429 已重試 {_rl_atmp} 次仍 rate-limited，放棄：{_url_log[:80]}")
                _sb.record_failure(_src_key, "rate_limited")
                return None
            if r.status_code == 200:
                _sb.record_success(_src_key)   # v3 §02:來源活著 → 立刻解除退避
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
                            timeout=_to, proxies={}, verify=True)
            _last_status = r_dc.status_code   # 收尾 log 要反映「最後一次」真狀態
            if r_dc.status_code == 200:
                print("[proxy] 直連成功")
                # 降級直連成功也算來源活著（走的是另一個出口 IP，但資料拿到了）
                # → 解除退避。否則「proxy 被擋、直連可用」的常態會被自己的退避鎖死。
                _sb.record_success(_src_key)
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
    # ── v3 §02 退避分類（順序有意義，逐條理由見 shared/backoff_policy.py）──────
    # ① 404 最優先：來源**活著而且明確回答了**，只是這支 URL 不存在 → URL 的問題，
    #    不是來源的問題。若因 404 退避整個 host，會直接打死
    #    `tw_pmi_repository._pmi_src_cier_en_monthly`（刻意輪 3 個月份 slug，
    #    **舊月份 404 是正常流程**）等所有「試幾個候選 URL」式的探測。
    # ② 看過 403 → 封鎖（IP / Referer 層級，不會在幾秒內解除）。
    # ③ 其餘 4xx/5xx → server_error（5xx 分鐘級恢復、402 額度用盡）。
    # ④ 完全沒收到狀態碼（逾時 / ProxyError / 連線錯誤）→ unreachable（最短冷卻）。
    if _last_status == 404:
        _fail_kind = "not_found"
    elif _last_status == 429:
        # ⚠️ 這條**會**走到，不是防禦性冗餘：預設 retries=3 + backoff=(2,4,8) 時，
        # 上面 429 分支的 `_rl_atmp` 在最後一次 attempt 仍 < 3 → sleep 完 continue →
        # for 迴圈當場耗盡，**永遠走不到**那個 `return None` 的放棄分支
        # （infra/proxy.py 內 v19.425 已查證並記載的既有行為，本次未改動它）。
        # 少了這一條，429 會在收尾處被誤分類成 server_error(300s)，
        # 「對方明確叫我們停」這個最強訊號反而拿到最短的冷卻期。
        _fail_kind = "rate_limited"
    elif _block >= 1:
        _fail_kind = "blocked"
    elif _last_status is not None and _last_status >= 400:
        _fail_kind = "server_error"
    else:
        _fail_kind = "unreachable"
    _sb.record_failure(_src_key, _fail_kind)
    return None
