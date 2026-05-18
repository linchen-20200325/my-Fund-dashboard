# NAS 中繼站使用說明書

> 版本：v1.0 | 適用專案：任何部署在 Streamlit Cloud 且需要抓取台灣金融網站（MoneyDJ / 鉅亨等）的 Python 應用。

---

## 一、為什麼需要 NAS 中繼站？

```
Streamlit Cloud (美國 IP)
        │
        │  直連 → MoneyDJ 403 封鎖（境外 IP）
        │
        ▼
    NAS 中繼站（台灣 IP / 你家 DDNS）
        │
        │  Squid CONNECT 隧道（Port 3128）
        │
        ▼
  MoneyDJ / 任何台灣網站 ✅
```

Streamlit Cloud 的伺服器在美國，MoneyDJ 等台灣金融網站會對境外 IP 回傳 403。NAS 中繼站作為台灣本地的 HTTP Proxy（Squid），讓雲端應用借道台灣 IP 存取資料。

---

## 二、NAS 環境需求

| 項目 | 需求 |
|------|------|
| 硬體 | Synology NAS（任何型號，能跑 Docker 或套件中心即可） |
| 軟體 | **Web Station** + **Squid** 套件，或 Docker 執行 Squid |
| 網路 | 路由器開通 **Port 3128** TCP 對外轉發至 NAS 內網 IP |
| DDNS | Synology DDNS（如 `yourname.synology.me`）或自訂域名 |

---

## 三、NAS 側設定步驟

### 3-1 安裝 Squid（套件中心）

1. DSM → 套件中心 → 搜尋 **Squid**（由 SynoCommunity 提供）
2. 安裝後，進入 Squid 設定面板
3. 開啟「需要身份驗證」，設定帳號密碼（後續填入 secrets）

### 3-2 Squid 最小設定（`squid.conf` 關鍵段落）

```
http_port 3128

auth_param basic program /usr/lib/squid/basic_ncsa_auth /etc/squid/passwd
auth_param basic realm NAS Proxy
acl authenticated proxy_auth REQUIRED

http_access allow authenticated
http_access deny all

# CONNECT 隧道（讓 HTTPS 能穿透）
acl CONNECT method CONNECT
http_access allow CONNECT authenticated
```

> 若使用 Docker 版 Squid，直接 `docker run` 並 mount 設定檔即可，原理相同。

### 3-3 路由器 Port Forwarding

```
外部 Port 3128  →  NAS 內網 IP:3128  (TCP)
```

登入路由器管理介面（通常是 192.168.1.1），在「虛擬伺服器」或「Port Forwarding」設定。

### 3-4 確認可用

在本機終端測試：
```bash
curl -x http://帳號:密碼@yourname.synology.me:3128 \
     https://www.moneydj.com/ -I
# 應看到 HTTP/1.1 200 OK
```

---

## 四、Python 程式碼整合

### 4-1 複製核心模組（共 4 個函式）

將以下程式碼區塊貼入你的專案的任意 `.py` 模組（建議建立 `proxy_helper.py`）：

```python
# proxy_helper.py
import requests
import urllib3
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── 模組層級快取（TTL 300s，NAS 恢復後自動生效）──
_PROXY_CFG_CACHE = None
_PROXY_CFG_TS    = 0.0
_PROXY_CFG_TTL   = 300

def reset_proxy_cache():
    """手動清除 Proxy 快取，下次請求時重新讀取 st.secrets。"""
    global _PROXY_CFG_CACHE, _PROXY_CFG_TS
    _PROXY_CFG_CACHE = None
    _PROXY_CFG_TS    = 0.0


def get_proxy_config() -> dict | None:
    """
    讀取 NAS Proxy 設定（從 st.secrets）。
    支援兩種格式：
      新格式：PROXY_URL = "http://user:pwd@host:port"
      舊格式：[proxy] section with username/password/endpoint
    回傳：{"http": url, "https": url}  或  None（降級直連）
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
    """urllib3 指數退避 Session：5xx 自動重試最多 3 次。"""
    _retry = Retry(
        total=3, backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504],
        raise_on_status=False,
    )
    _s = requests.Session()
    _s.mount("https://", HTTPAdapter(max_retries=_retry))
    _s.mount("http://",  HTTPAdapter(max_retries=_retry))
    return _s


def fetch_url(url: str, headers: dict = None,
              params: dict = None, timeout: int = 20) -> requests.Response | None:
    """
    通用抓取函式（含 NAS Proxy + 自動降級直連）。
    - Proxy 可用 → 透過 NAS 中繼抓取（SSL verify=False，Squid CONNECT 模式）
    - Proxy 失敗（ProxyError / 403×2）→ 自動降級直連
    """
    import time as _t, random as _rnd
    _proxy  = get_proxy_config() or {}
    _verify = not bool(_proxy)          # proxy 模式跳過 SSL 驗證
    _hdr = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9",
    }
    if headers:
        _hdr.update(headers)

    _sess  = make_retry_session()
    _perr  = 0   # ProxyError 計數
    _block = 0   # 403 計數

    for attempt in range(3):
        try:
            r = _sess.get(url, headers=_hdr, params=params,
                          timeout=timeout, proxies=_proxy, verify=_verify)
            if r.status_code == 407:
                print("[proxy] 407 Auth Failed — 請確認帳密正確")
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

    # 降級直連
    if _proxy and (_perr > 0 or _block >= 2):
        print(f"[proxy] 降級直連：{url[:80]}")
        try:
            r_dc = _sess.get(url, headers=_hdr, params=params,
                             timeout=timeout, proxies={}, verify=True)
            if r_dc.status_code == 200:
                return r_dc
        except Exception as e_dc:
            print(f"[proxy] 直連失敗：{e_dc}")
    return None
```

### 4-2 在你的專案中呼叫

```python
from proxy_helper import fetch_url, get_proxy_config

# 抓取台灣金融頁面
resp = fetch_url("https://www.moneydj.com/funddj/yb/YP010001.djhtm?a=TLZF9")
if resp:
    print(resp.text[:500])

# 或直接取得 proxies dict（傳給 requests / pandas / yfinance）
proxies = get_proxy_config() or {}
import yfinance as yf
# yfinance 不直接支援 proxies 參數，但可透過環境變數
import os
if proxies:
    os.environ["HTTP_PROXY"]  = proxies["http"]
    os.environ["HTTPS_PROXY"] = proxies["https"]
```

---

## 五、Streamlit Secrets 設定

### 新格式（推薦）

```toml
# .streamlit/secrets.toml

FRED_API_KEY   = "your-fred-api-key"
GEMINI_API_KEY = "your-gemini-api-key"

PROXY_URL = "http://帳號:密碼@yourname.synology.me:3128"
```

### 舊格式（向下相容）

```toml
# .streamlit/secrets.toml

[proxy]
username = "your-nas-username"
password = "your-nas-password"
endpoint = "yourname.synology.me:3128"
```

> **Streamlit Cloud 部署**：不上傳 `secrets.toml`，改在 Streamlit Cloud → App Settings → Secrets 介面逐行貼入。

---

## 六、行為矩陣

| 狀況 | 程式行為 |
|------|---------|
| secrets 有 PROXY_URL，NAS 正常 | 全程走 NAS 中繼，SSL verify=False |
| secrets 無 proxy 設定 | 直連，SSL verify=True |
| NAS 暫時關機（ProxyError） | 自動降級直連，印 `[proxy] 降級直連` |
| MoneyDJ 封鎖（403 ×2） | 提前跳出重試迴圈，改直連嘗試 |
| NAS 帳密錯誤（407） | 立即回傳 None，不重試 |
| NAS 恢復（300s 後） | TTL 快取過期，自動重新讀取 secrets |

---

## 七、故障排除

### Q1：`ProxyError: Cannot connect to proxy`
```
原因：路由器 Port 3128 未開放，或 NAS 的 Squid 服務未啟動。
解法：
  1. 確認 NAS 的 Squid 服務狀態為「執行中」
  2. 路由器 Port Forwarding 確認 3128 → NAS 內網 IP
  3. 本機 curl 測試（見第三節 3-4）
```

### Q2：`407 Proxy Auth Failed`
```
原因：secrets.toml 的帳號/密碼有誤，或 Squid 的 passwd 檔案未更新。
解法：
  1. 重新確認 secrets.toml 的 username/password
  2. 重建 Squid passwd 檔：htpasswd -c /etc/squid/passwd 帳號
  3. 重啟 Squid 服務
```

### Q3：`SSL: CERTIFICATE_VERIFY_FAILED`
```
原因：proxy 模式的 SSL verify=False 未正確套用。
解法：確認 get_proxy_config() 有正確回傳非 None，
     或在 fetch_url() 中明確傳入 verify=False。
```

### Q4：NAS 回復後仍走直連
```
原因：_PROXY_CFG_CACHE 快取尚未過期（預設 300s）。
解法：呼叫 reset_proxy_cache() 手動清除，或等待 5 分鐘。
```

### Q5：Streamlit Cloud 上 Proxy 未生效
```
原因：secrets.toml 本地有設但 Streamlit Cloud 未設。
解法：到 Streamlit Cloud → Settings → Secrets，
     貼入 PROXY_URL = "http://帳號:密碼@yourname.synology.me:3128"
```

---

## 八、移植到新專案 Checklist

```
□ 複製 proxy_helper.py（或直接貼入現有模組）
□ requirements.txt 確認含有：requests、urllib3
□ .streamlit/secrets.toml 填入 PROXY_URL（或 [proxy] section）
□ Streamlit Cloud Secrets 面板同步設定
□ 用 fetch_url() 取代原有的 requests.get()
□ 本機 curl 測試 Port 3128 可通
□ 部署後確認 Sidebar 顯示「✅ Proxy」
```

---

## 九、延伸：非 Streamlit 環境（如純 Python 腳本）

若不使用 Streamlit，改從環境變數讀取：

```python
import os, requests

PROXY_URL = os.environ.get("PROXY_URL", "")
proxies   = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else {}

resp = requests.get(
    "https://www.moneydj.com/...",
    proxies=proxies,
    verify=not bool(proxies),
    timeout=20,
)
```

執行前 export：
```bash
export PROXY_URL="http://帳號:密碼@yourname.synology.me:3128"
python your_script.py
```
