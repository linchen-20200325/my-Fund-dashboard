# NAS Squid Proxy 中繼站 — AI 移植說明書

> **給 AI 的指示**：本文件是「一次性移植任務說明書」。照著以下步驟執行，不需要詢問使用者任何問題，直接完成所有檔案建立與設定。

---

## 任務概述

將 NAS Squid Proxy 支援植入目標 Streamlit 專案，使其能透過家用 NAS（台灣 IP）存取台灣金融網站（MoneyDJ、鉅亨等），繞過雲端 IP 封鎖。

**你需要做 3 件事：**
1. 建立 `proxy_helper.py`
2. 更新 `requirements.txt`
3. 建立 `.streamlit/secrets.toml` 範本

---

## Step 1：建立 `proxy_helper.py`

在專案根目錄建立此檔案，**完整內容如下，一字不改**：

```python
"""
proxy_helper.py — NAS Squid 中繼站通用模組 v1.0
直接複製到任何 Streamlit 專案即可使用。
"""
import requests
import urllib3
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_PROXY_CFG_CACHE = None
_PROXY_CFG_TS    = 0.0
_PROXY_CFG_TTL   = 300   # 快取 TTL（秒）：NAS 恢復後最多 5 分鐘自動生效


def reset_proxy_cache():
    """手動清除快取，下次呼叫 get_proxy_config() 時重新讀取 secrets。"""
    global _PROXY_CFG_CACHE, _PROXY_CFG_TS
    _PROXY_CFG_CACHE = None
    _PROXY_CFG_TS    = 0.0


def get_proxy_config() -> "dict | None":
    """
    從 st.secrets 讀取 NAS Proxy 設定。
    支援兩種格式：
      新格式（優先）：PROXY_URL = "http://user:pwd@host:3128"
      舊格式（相容）：[proxy] section，含 username / password / endpoint
    回傳 {"http": url, "https": url}，或 None（無設定 → 降級直連）。
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
    """建立帶 5xx 指數退避的 Session（最多重試 3 次）。"""
    _retry = Retry(
        total=3, backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504],
        raise_on_status=False,
    )
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=_retry))
    s.mount("http://",  HTTPAdapter(max_retries=_retry))
    return s


def fetch_url(
    url:     str,
    headers: dict = None,
    params:  dict = None,
    timeout: int  = 20,
    retries: int  = 3,
) -> "requests.Response | None":
    """
    通用 HTTP GET，含 NAS Proxy 中繼 + 自動降級直連。

    行為：
      ✅ Proxy 正常   → 走 NAS，SSL verify=False（Squid CONNECT 相容）
      ❌ 407 帳密錯誤 → 立即回傳 None，不重試
      ❌ 403 封鎖 ×2  → 提前跳出，降級直連
      ❌ ProxyError   → 自動降級直連
      ⚪ 無 Proxy 設定 → 直連，SSL verify=True
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
                print("[proxy] 407 Auth Failed — 確認 secrets 帳密正確")
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

    # 降級直連
    if _proxy and (_perr > 0 or _block >= 2):
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
```

---

## Step 2：更新 `requirements.txt`

確認以下兩行存在（若已存在則跳過）：

```
requests>=2.31.0
urllib3>=2.0.0
```

---

## Step 3：建立 `.streamlit/secrets.toml` 範本

若 `.streamlit/` 目錄不存在，先建立它。
建立 `.streamlit/secrets.toml`（或在現有檔案末尾**追加**以下內容）：

```toml
# ── NAS Proxy 中繼站設定 ──────────────────────────────────────
# 格式選一填寫（新格式優先）：

# 【新格式】單行 URL（推薦）
PROXY_URL = "http://你的帳號:你的密碼@yourname.synology.me:3128"

# 【舊格式】分段填寫（二選一，不要兩種同時放）
# [proxy]
# username = "你的帳號"
# password = "你的密碼"
# endpoint = "yourname.synology.me:3128"
```

> ⚠️ `secrets.toml` **不可 commit 進 git**。確認 `.gitignore` 含有：
> ```
> .streamlit/secrets.toml
> ```

---

## Step 4：在目標程式碼中呼叫

### 4-1 抓取網頁（最常用）

```python
from proxy_helper import fetch_url

resp = fetch_url("https://www.moneydj.com/funddj/yb/YP010001.djhtm?a=TLZF9")
if resp:
    html = resp.text
```

### 4-2 取得 proxies dict（傳給 requests）

```python
from proxy_helper import get_proxy_config

proxies = get_proxy_config() or {}
resp = requests.get(url, proxies=proxies, verify=not bool(proxies), timeout=20)
```

### 4-3 Sidebar 顯示 Proxy 狀態（Streamlit）

在 `app.py` 的 sidebar 區塊加入：

```python
from proxy_helper import get_proxy_config
import re

_proxy_cfg = get_proxy_config()
_proxy_ep  = ""
if _proxy_cfg:
    _m = re.search(r'@(.+)', _proxy_cfg.get("http", ""))
    _proxy_ep = _m.group(1) if _m else "已設定"

st.caption(
    f"🔒 Proxy: {_proxy_ep}" if _proxy_cfg
    else "⚠️ Proxy 未設定（可能被境外封鎖）"
)
```

### 4-4 手動重置快取（NAS 維修後）

```python
from proxy_helper import reset_proxy_cache

if st.button("🔄 重置 Proxy 快取"):
    reset_proxy_cache()
    st.success("已清除，下次請求將重新讀取 secrets")
```

---

## Step 5：Streamlit Cloud 部署設定

**不要上傳 `secrets.toml`**，改在 Streamlit Cloud 設定：

```
App → Settings → Secrets → 貼入：

PROXY_URL = "http://你的帳號:你的密碼@yourname.synology.me:3128"
```

---

## NAS 端建置需求（給人類操作）

> AI 不需要執行這段，提供給使用者自行完成。

| 項目 | 需求 |
|------|------|
| 硬體 | Synology NAS（任何型號） |
| 套件 | DSM 套件中心安裝 **Squid**（SynoCommunity） |
| 網路 | 路由器開通 **Port 3128 TCP** 轉發至 NAS 內網 IP |
| DDNS | Synology DDNS（`yourname.synology.me`）或自訂域名 |

**Squid 最小設定（`squid.conf`）：**

```
http_port 3128

auth_param basic program /usr/lib/squid/basic_ncsa_auth /etc/squid/passwd
auth_param basic realm NAS Proxy
acl authenticated proxy_auth REQUIRED
acl CONNECT method CONNECT

http_access allow CONNECT authenticated
http_access allow authenticated
http_access deny all
```

**測試指令（本機執行）：**

```bash
curl -x http://帳號:密碼@yourname.synology.me:3128 \
     https://www.moneydj.com/ -I
# 預期：HTTP/1.1 200 OK
```

---

## 行為速查表

| 狀況 | 結果 |
|------|------|
| `secrets.toml` 有 `PROXY_URL`，NAS 正常 | 走 NAS，`verify=False` |
| `secrets.toml` 無 proxy 設定 | 直連，`verify=True` |
| NAS 關機（ProxyError） | 自動降級直連 |
| MoneyDJ 封鎖（403 × 2） | 自動降級直連 |
| 帳密錯誤（407） | 立即回傳 `None` |
| NAS 恢復 | TTL 300s 過期後自動重接 |

---

## 完成驗證 Checklist

```
□ proxy_helper.py 建立於專案根目錄
□ requirements.txt 含 requests / urllib3
□ .streamlit/secrets.toml 已填入 PROXY_URL
□ .gitignore 含 .streamlit/secrets.toml
□ python3 -c "from proxy_helper import fetch_url; print('OK')"  → OK
□ Streamlit Cloud Secrets 已設定 PROXY_URL
□ Sidebar 顯示 "🔒 Proxy: yourname.synology.me:3128"
```
