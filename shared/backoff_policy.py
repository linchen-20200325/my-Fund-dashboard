"""shared/backoff_policy.py — 來源失敗「退避冷卻期」SSOT（L0，純常數，零 I/O）。

## 為什麼有這個檔（v3 憲法 §02 新增要求）

> 「外部 API 取數必須落實：**只快取成功結果；失敗時退避，不連續轟炸來源**。」

「只快取成功結果」本 repo 早已達成（`repositories/fund/fx_and_main.py` v18.275 的
positive-only `_FX_CACHE`、`infra/cache.py::_daily_cache` v19.253 R23 的 `cache_if`
失敗過濾）。**「失敗時退避」則是全新要求** —— 在此之前，失敗**單純不快取**，
於是下一次操作會**立刻把整條 fallback chain 再打一遍**：

- MoneyDJ 子網域鏈 yp010000 → yp010001 → TDCC → FundClear → Cnyes（§2.1）
- TW PMI 9 源並行賽跑（`repositories/tw_pmi_repository.PMI_SOURCE_REGISTRY`）
- NAV 三源（FundClear / TDCC / MoneyDJ）

而 Streamlit **每一次互動都 rerun**，放大倍數等於使用者的點擊頻率。這就是憲法
所稱的「連續轟炸來源」。

## ⚠️ 為什麼這**不會**推翻 `fx_and_main.py` v18.275 的 positive-only 快取（必讀）

後人同時讀到這兩處，第一反應會是「矛盾」：v18.275 的註解白紙黑字寫
「**None 不入 cache → 下次仍會 retry**」，而本檔要做的是「失敗後一段時間不要再打」。
**兩者不衝突，因為它們管的是不同的東西**：

| | v18.275 positive-only `_FX_CACHE` | 本檔的來源退避 |
|---|---|---|
| 存什麼 | **值**（`rate: float > 0`） | **時間戳 + 失敗分類**，**不存任何值** |
| 防什麼 | **None-poisoning** —— 一次失敗把假的「查無匯率」鎖住整個 TTL，讓 caller 在 5 分鐘內**拿到錯的答案** | **連續轟炸** —— 每次 rerun 把整條 chain 重打一遍 |
| 退避期內 caller 拿到什麼 | （不適用） | 與「真的打了但失敗」**完全相同的 `None`** |

關鍵在第三列：**退避期內回傳的 `None` 不是被記住的失敗值，而是「這個來源這次沒有值」。**
v18.275 要防的是「**曾經失敗過 → 之後拿到一個錯的答案**」；本檔不可能造成那件事，
因為它**結構上就沒有地方放答案**（`infra/source_backoff.py` 的狀態 dict 只有
`until / kind / cooldown / fails / last_fail` 五個欄位，測試
`test_backoff_module_stores_no_payload` 釘住這一點）。

v18.275 的 `_FX_CACHE` **一行都不用改，也沒有被改** —— 它繼續只快取正值；
退避發生在更下層的 `infra.proxy.fetch_url`，兩者是串聯而非競爭。
唯一的行為交集是：FX chain 的某一段來源若在冷卻期，該段直接回 `None`，
chain 往下一段走 —— 那與該段「打了但失敗」的既有行為**逐字相同**。

## ⚠️ 與既有「單次呼叫內重試」的分工（兩層，各司其職，不要合併）

本 repo 早已有**單次呼叫內**的重試 / 退避，且**本次一行都沒動**：
`infra/proxy.py` 的 `_RATE_LIMIT_BACKOFF_SEC = (2.0, 4.0, 8.0)` 與 `backoff_on_429`、
`repositories/policy/_helpers.py`、`repositories/snapshot_repository.py`、
`repositories/fundclear_offshore.py` 各自的 5xx/429 重試。

| 層 | 範圍 | 問的問題 | 時間尺度 |
|---|---|---|---|
| **既有：單次呼叫內重試** | 一次 `fetch_url()` 之內 | 「**再試一下**會不會就好了？」 | 秒（2/4/8 s） |
| **本次新增：跨呼叫來源冷卻** | 跨 rerun、跨 chain、跨 fetcher | 「**這一輪還要不要碰**這個來源？」 | 分鐘（60 s ~ 30 min） |

⚠️ 兩層**刻意不合併**：前者的重試額度耗盡，正是後者的**輸入訊號**
（`fetch_url` 收尾時才記 `record_failure`）。把兩者揉在一起會失去
「已經在一次呼叫內盡力過了」這個資訊，也會讓 429 的 2/4/8 秒序列與分鐘級冷卻互相污染。
`backoff_on_429=False` 的 caller（v19.507 Yahoo）是最清楚的例子：它取消的是**上層**
（不要在這次呼叫裡白等 14 秒），**下層**的來源冷卻照記 —— 見 `infra/proxy.py` 該處註解。

## 這裡的「退避」是什麼、不是什麼

- ✅ **是**：某個來源剛失敗過 → 冷卻期內**這次不試它**，直接跳過走下一個來源。
- ❌ **不是**快取失敗值。§1 Fail Loud 完全不變 —— 退避期內該來源回 `None`
  （與「真的打了但失敗」回傳完全相同的值），呼叫端的 fallback chain 語意零改動；
  **整條 chain 都退避時照樣 fail loud**，不回舊值、不回假資料、不回 dummy。

## 冷卻期怎麼定（§1「錯誤的數字比沒有數字更危險」的對偶：**退避不可讓資料長期消失**）

⚠️ 硬約束：**任何冷卻期都必須遠短於該資料自身的發布週期**，否則退避會把
「這次沒抓到」變成「這個資料點永遠沒看到」。本 repo 最快的來源是 Yahoo EOD
（日頻，§2.3），最慢的是 PMI / CPI（月頻）。故**上限釘在 30 分鐘** ——
即使踩到最長的冷卻期，也不可能錯過任何一個「新資料點」。

另有兩道保險：
1. `infra.source_backoff` 已註冊進 `infra.cache._CACHE_REGISTRY`
   → sidebar「全域刷新」/ `clear_all_caches()` **一鍵清空全部退避狀態**，
     使用者永遠有立即重試的逃生門。
2. 冷卻期**不累積、不指數放大**：連續失敗只會刷新同一段冷卻期，不會越退越久。

## 為什麼分失敗類型（§-1.5 v2 第一條 1「程式碼與資料修正」內部自決）

不同失敗的**復原時間尺度差了三個數量級**，用同一個數字必然一邊太鬆一邊太緊；
更關鍵的是有兩種失敗**根本不該退避**（見 `NO_COOLDOWN_KINDS`）。

| kind | 觸發 | 冷卻 | 為什麼是這個長度 |
|---|---|---|---|
| `unreachable` | Timeout / ProxyError / 連線錯誤 | 60 s | 多半是**我方**網路或 NAS Squid 的暫時抖動，秒級～分鐘級自癒。`fetch_url` 單次逾時已付出 ~20 s + 2 s sleep + 一次降級直連；60 s 把這個代價壓到「每來源每分鐘最多一次」，同時短到任何暫時性失敗都不會被藏超過一分鐘。 |
| `server_error` | 5xx / 401 / 402 等非 404 的錯誤碼 | 300 s | 直接沿用 `shared.ttls.TTL_5MIN` —— 那是本 repo 對「即時值可以多舊」既有的答案。冷卻期不長於同類值的快取 TTL，退避就不可能讓資料比快取層本來就允許的更舊。5xx 通常分鐘級恢復；402（額度用盡）不會，但每 5 分鐘一次探測成本極低。 |
| `blocked` | HTTP 403 | 900 s | 403 是**IP / Referer 層級的封鎖**（MoneyDJ 子網域、CIER cloudflare），由對方按來源 IP 決定，**不會在幾秒內解除**。15 分鐘內重試的成功機率趨近 0，卻要付 2 次 attempt + 2.5~6 s sleep + 一次降級直連。15 min ≪ NAV(T+1) / PMI(月) 的自身週期，觀測上零損失。 |
| `rate_limited` | HTTP 429 | 1800 s | **唯一一種「對方明確叫我們停」**的失敗。繼續探測會延長封鎖窗口。公開 endpoint（Yahoo Chart / FRED / open.er-api）的限流窗口以數十分鐘計，30 min ≈ 一個窗口。本 repo 的 Yahoo 用法是日頻收盤（`range_="5d", interval="1d"`），30 分鐘看不到 = 零資訊損失。 |
| `not_found` | HTTP 404 | **0（不退避）** | 404 代表**來源活著而且明確回答了**，只是這支 URL 不存在 —— 那是 URL 的問題不是來源的問題。若因 404 就把整個 host 退避掉，會直接打死 `tw_pmi_repository._pmi_src_cier_en_monthly`（它刻意輪 3 個月份 slug，**舊月份 404 是正常流程**）與所有「試幾個 page_type」式的探測。 |
| `proxy_auth` | HTTP 407 | **0（不退避）** | 407 是 **NAS Squid 帳密設定錯**，請求**根本沒有到達來源**，退避來源等於罰錯人；更糟的是它會把一個「改 secrets 就能修好」的設定錯誤，偽裝成一整排來源的「已跳過」。407 走 `fetch_url` 既有的 fail-loud log，不進退避。 |

> ⚠️ 退避的粒度是 **host**，不是完整 URL。理由：403 / 429 / 連線失敗都是對方按
> **host（+ 我方 IP）** 判定的，同一 host 換個 query string 一樣會被擋 ——
> 那正是「yp010000 失敗馬上打 yp010001」這種轟炸要擋掉的東西。反過來，
> **URL 專屬**的失敗（404）已由上表排除在退避之外，故 host 粒度不會誤殺。
"""
from __future__ import annotations

# ── 冷卻秒數（唯一真相源；`infra/source_backoff.py` 只讀不定義）────────────
BACKOFF_UNREACHABLE_SEC: int = 60
BACKOFF_SERVER_ERROR_SEC: int = 300     # 對齊 shared.ttls.TTL_5MIN（刻意同值，理由見 docstring）
BACKOFF_BLOCKED_SEC: int = 900
BACKOFF_RATE_LIMITED_SEC: int = 1800

# 失敗類型 → 冷卻秒數。0 = 不退避。
BACKOFF_COOLDOWN_SEC: dict[str, int] = {
    "unreachable":  BACKOFF_UNREACHABLE_SEC,
    "server_error": BACKOFF_SERVER_ERROR_SEC,
    "blocked":      BACKOFF_BLOCKED_SEC,
    "rate_limited": BACKOFF_RATE_LIMITED_SEC,
    "not_found":    0,
    "proxy_auth":   0,
}

# 明確「不退避」的類型（與上表 0 值同義，另立一份給 caller / 測試做語意斷言，
# 避免有人把 `cooldown == 0` 讀成「查表沒查到」）。
NO_COOLDOWN_KINDS: frozenset = frozenset({"not_found", "proxy_auth"})

# 查不到的 kind 一律當 unreachable（最短冷卻）—— 未知失敗**從寬**，
# 寧可多打一次來源，也不要讓沒想到的情況把資料藏起來。
BACKOFF_DEFAULT_KIND: str = "unreachable"

# ⚠️ 上限守衛：任何冷卻期都不得超過此值。理由見 docstring
# 「退避不可讓資料長期消失」—— 本 repo 最快的來源是 Yahoo EOD（日頻，§2.3），
# 30 分鐘保證不會錯過任何一個新資料點。由 `tests/test_source_backoff.py` 釘住。
BACKOFF_MAX_COOLDOWN_SEC: int = 1800

# 記憶體上限：退避狀態表最多追蹤幾個 host（超過時先清已到期的，仍超過就清最舊的）。
# 本 repo 全部外部來源 host 數約 20~30（§2.1 的 18 來源 + fallback 子網域），
# 128 有 4 倍餘裕，同時保證長跑 session 不會無界成長。
BACKOFF_MAX_TRACKED_HOSTS: int = 128
