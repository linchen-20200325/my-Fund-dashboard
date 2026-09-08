"""infra/gspread_retry.py — Google Sheets (gspread) 429 / 配額退避共用工具 (v19.385 T2a)。

原本 `repositories/policy/_helpers.py` 與 `repositories/snapshot_repository.py` 各持一份
near-identical 的 `_is_quota_error` + `_with_quota_retry`(逐字重複),本檔抽 L0 infra 收斂。

⚠️ 退避排程(backoffs)保留為**參數**而非寫死常數 —— 兩處刻意不同節奏(§8.4 值不同不可強收):
  - policy 層  `(2, 4, 8, 16)` = 總 30s(v18.253:給 Google quota 視窗多一拍 reset)
  - snapshot 層 `(1, 2, 4, 8)`  = 總 15s
各 caller 傳自己的 backoffs;本檔只提供共用的偵測 + 重試迴圈。

L0 infra:無上行依賴。2026-09-01 起另含 gspread 專用的**跨呼叫來源冷卻**
(見檔尾「跨呼叫『來源冷卻』」段),該段以 **函式內 lazy import** 取用同屬 L0 的
`infra.source_backoff` 與(選用的)`gspread.exceptions` —— 仍無上行依賴,
lazy 是為了不讓本檔在 module load 時把 streamlit/gspread 依賴鏈拉起來。
"""
from __future__ import annotations

import time
from typing import Any, Callable

# caller 未指定時的預設(對齊 snapshot 原節奏);policy 明確傳 (2,4,8,16)。
DEFAULT_QUOTA_BACKOFFS: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0)


def is_quota_error(exc: BaseException) -> bool:
    """偵測 gspread 429 / RESOURCE_EXHAUSTED;不依賴 gspread.exceptions 細節以容版差。"""
    msg = str(exc)
    return ("429" in msg or "Quota exceeded" in msg or "RATE_LIMIT" in msg
            or "RESOURCE_EXHAUSTED" in msg)


def with_quota_retry(call: Callable, *args,
                     backoffs: tuple[float, ...] = DEFAULT_QUOTA_BACKOFFS,
                     **kwargs) -> Any:
    """包裝 gspread 呼叫:遇 429 依 `backoffs` 逐次退避重試;非配額錯誤立即拋。

    嘗試次數 = len(backoffs);最後一次仍 429 → 拋出原例外(§1 fail loud,不吞)。
    最後一個 backoff 值不會被 sleep(該次即 raise),與原兩份實作行為一致。
    """
    last_err: BaseException | None = None
    for attempt, delay in enumerate(backoffs):
        try:
            return call(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 — gspread 例外類型隨版本變
            last_err = e
            is_last = attempt == len(backoffs) - 1
            if not is_quota_error(e) or is_last:
                raise
            time.sleep(delay)
    if last_err is not None:
        raise last_err
    return None


# ════════════════════════════════════════════════════════════════════
# 跨呼叫「來源冷卻」—— gspread 版（2026-09-01，客戶指示：批次 2）
# ════════════════════════════════════════════════════════════════════
# ## 為什麼 gspread 需要自己接一次
#
# `infra/source_backoff.py` 的冷卻只由 `infra/proxy.py::fetch_url` 在進場處查
# （查的是 `source_key(url)` ＝ host）。**gspread 完全不經過 `fetch_url`** ——
# 它用自己的 `requests.Session` 直打 Google API。所以退避對它是「**沒接**」，
# 不是「不能接」。先例：`repositories/fund/fx_and_main.py::get_latest_fx` 用裸
# `requests.get`、同樣拿不到 `fetch_url` 的內建退避，於是檔內手動接上同一套。
# 本段把那個手動接法**收成共用的一份**，避免兩個 gspread 站點各寫一遍後漂移（§2 SSOT）。
#
# ## 為什麼要**兩把鑰匙**，不是一把（這是本段最重要的設計決定）
#
# 退避鍵的粒度太粗會**誤殺健康的消費者**，太細會**漏放同一個受害者**。gspread 的
# 失敗有兩種完全不同的作用域，用同一把鑰匙必然犯其中一種錯：
#
# | 失敗 | 真實作用域 | 用哪把鑰匙 |
# |---|---|---|
# | 429 / 配額耗盡 | **憑證**（Sheets API 的配額維度是 *per user per project*，不是 per spreadsheet） | `gspread:quota:<actor>` |
# | 403 / 404 / 該本沒被分享 | **那一本試算表** | `gspread:sheet:<actor>:<sheet_id>` |
# | 5xx / 連線層 | 保守視為**那一本** | 同上 |
#
# ⚠️ **配額維度是查證出來的，不是猜的**：Google「Usage limits」文件列的兩個讀取配額是
# 「300 read requests per minute **per project**」與「60 read requests per minute
# **per user per project**」—— 維度是 *user（憑證）* 與 *project*，**沒有 spreadsheet
# 這一維**。⚠️ 但本次**沒能讀到一手頁面**（本環境的 egress proxy 擋掉
# `developers.google.com`），上述數值取自該官方頁的搜尋摘要 —— 依 §-2 規則 6 據實標明。
#
# **被排除的粒度與理由（寫出來，免得後人以為沒想過）**：
# - **per-worksheet**（`_fund_pool` / `nav_history`）：403 與配額**從來不是** worksheet
#   作用域。切這麼細，等於讓同一本壞掉的試算表「每個分頁各被打一次」才冷卻 —— 正是
#   「太細 → 漏放同一個受害者」。
# - **只用憑證一把鑰匙**：本 repo 明文有**兩本不同**的試算表（`POOL_SHEET_ID` /
#   `NAV_SHEET_ID`），且兩處 docstring 都寫著「SA 信箱須被加為**該本**的編輯者」——
#   「一本分享了、另一本沒分享」是**預期中的狀態**。單一憑證鍵會讓沒分享那本的 403
#   把健康的那本一起關掉（「太粗 → 誤殺」）。
# - **host 鍵（`source_backoff.source_key(url)`）**：所有 gspread 流量都走
#   `sheets.googleapis.com` —— **每一本試算表、每一個憑證共用同一個 host**，是最粗的
#   一種切法；而且 `fetch_url` 根本看不到這些呼叫，登記 host 鍵會變成「登記了一個沒人
#   讀的旗標」。
#
# ## actor（憑證身分）為什麼只有 "sa" / "oauth" 兩個值
# 本 App 同一時間最多一個 Service Account ＋ 一個登入者，兩者是**不同配額桶**，
# 而同類只有一份 —— `"sa"` / `"oauth"` 已足以區分，且不把 SA 信箱寫進 log。
# ⚠️ 若日後出現多把 SA，這裡要改成帶 client_email 的鍵。

_GSPREAD_QUOTA_KEY_PREFIX = "gspread:quota:"
_GSPREAD_SHEET_KEY_PREFIX = "gspread:sheet:"


def quota_key(actor: str) -> str:
    """憑證層（配額）退避鍵。actor ∈ {"sa", "oauth"}。"""
    return f"{_GSPREAD_QUOTA_KEY_PREFIX}{actor}"


def sheet_key(actor: str, sheet_id: str) -> str:
    """單一試算表層（403 / 404 / 5xx）退避鍵。"""
    return f"{_GSPREAD_SHEET_KEY_PREFIX}{actor}:{sheet_id}"


def http_status_of(exc: BaseException) -> "int | None":
    """從例外（含 `__cause__` 鏈）挖出 gspread `APIError` 的 HTTP 狀態碼；挖不到回 None。

    為什麼要走 cause 鏈：`services/nav_history_gs.py` 會把底層例外包成
    `NavHistoryError(...) from e`，狀態碼藏在 `__cause__` 裡。
    """
    try:
        from gspread.exceptions import APIError
    except Exception:                       # noqa: BLE001 — 無 gspread（CI 精簡環境）
        return None
    seen = 0
    cur: "BaseException | None" = exc
    while cur is not None and seen < 8:      # 8 層護欄，防自我參照的 cause 迴圈
        if isinstance(cur, APIError):
            _resp = getattr(cur, "response", None)
            _sc = getattr(_resp, "status_code", None)
            if isinstance(_sc, int):
                return _sc
            _code = getattr(cur, "code", None)
            return _code if isinstance(_code, int) and _code > 0 else None
        cur = cur.__cause__ or cur.__context__
        seen += 1
    return None


def kind_for_gspread_error(exc: BaseException) -> str:
    """gspread 例外 → `infra.source_backoff` 的失敗分類。

    ⚠️ **刻意不整段沿用 `kind_for_status`**：那張表的 `not_found`(404) 與
    `proxy_auth`(407) 都是 **0 冷卻**，但**兩者的豁免理由完全不同**，
    必須各問一次「這條理由在 gspread 這個位置成不成立」（§8.2.A.0 規則 5：
    豁免理由要說明「為什麼這個位置是對的」，不能照抄結論）。

    **404 —— `not_found`**：`shared/backoff_policy.py` 的原文理由是「404 代表**來源
    活著而且明確回答了**，只是這支 URL 不存在」，並點名它服務的是
    `tw_pmi_repository._pmi_src_cier_en_monthly` 那種「刻意輪 3 個月份 slug、
    舊月份 404 是正常流程」的探測鏈。**gspread 沒有任何探測鏈** —— 這裡的 404
    只有一個意思：「這個 sheet_id 不存在，或這把憑證沒被分享」，**每次 rerun 都會
    重演**。那條理由在這裡不成立 → 改判最短冷卻。

    **407 —— `proxy_auth`**：原文理由**一個字都沒提探測鏈**（⚠️ 2026-09-01 更正：
    本 docstring 前一版把 404 的理由誤植給 407，見下方「舊表述」）。它的原文是：
    407 是 **NAS Squid 帳密設定錯**，請求**根本沒有到達來源**，退避來源等於**罰錯人**；
    更糟的是它會把一個「改 secrets 就能修好」的設定錯誤，偽裝成一整排來源的「已跳過」。
    **這條理由在 gspread 這裡同樣不成立，但不成立的原因不一樣** ——
    ⚠️ **2026-09-01 第二次更正（稽核 NEW-5；有意識的更正，不是漏刪）**：
    ~~gspread 走自己的 `requests.Session`、**不經過 NAS Squid**，所以「罰錯人」的前提
    （中間有一層我方 proxy）根本不存在；而 Google 若真的回 407，那就是**對方**在回應
    這把憑證，退避的正是該退避的那個對象。~~
    **上面這兩句機制都講錯了**，逐句更正：
      (i) 「gspread 不經過 proxy」**不是它用自己的 Session 決定的** ——
          `requests.Session.trust_env` **預設 True**，gspread 沒有關掉它，
          **只要環境設了 `HTTPS_PROXY`，gspread 就會走 proxy**。
          **真正讓這句成立的是「本 repo 不設 env proxy」**：非測試碼裡
          `HTTP(S)_PROXY` 0 命中，`infra/proxy.py` 是**逐請求傳 `proxies=`**，
          不碰環境變數。→ 前提成立，但**它是本 repo 的配置事實，不是 gspread 的性質**；
          哪天有人設了 env proxy，這半個理由就會失效。
      (ii) 「Google 回 407 就是對方在回應這把憑證」**是錯的**：
          407 依 RFC 9110 §15.5.8 是 **proxy 的狀態碼**，origin server 不該發它。
    **結論（407 改判 60s）不因此動搖** —— 它靠的是下面這個**獨立成立**的理由：
    **60 秒**短到使用者改完 secrets 重整就恢復，且本模組進入退避時一律 stdout log
    （`[source_backoff] … 進入退避`），**不會靜默**，所以「把設定錯誤偽裝成一整排
    來源的已跳過」那個危害在這裡不成立。
    ⚠️ **這是同一段第二次因為「理由不對、結論對」被退回** —— 上一次是把 404 的理由
    誤植給 407。教訓一樣：**寫實際成立的那個理由，不要寫一個聽起來合理的。**

    ~~兩類的 0 冷卻豁免都服務於 `tw_pmi_repository` 的探測鏈。~~
    → **2026-09-01 更正（有意識的更正，不是漏刪；決策者：客戶指派的稽核複驗）**：
    **該句對 404 成立、對 407 不實** —— `proxy_auth` 的原文理由是「請求沒到達來源、
    退避等於罰錯人」，與探測鏈無關。**結論（407 改判 60s）未變、仍可辯護**，
    改掉的是**理由**。舊表述的用意仍然成立（它想說「不要照抄 0 冷卻」），
    被權衡掉的是它的事實面：它把兩條不同的理由壓成同一條，於是其中一條是編的。

    （這一步是先例 `fx_and_main` 那句「HTTP 200 但 payload 不可用 → 不退避」的同款
    判斷：**先問那條豁免的理由在這裡成不成立**，不是照抄結論。）
    """
    from infra import source_backoff as _sb

    _status = http_status_of(exc)
    if _status is not None:
        _kind = _sb.kind_for_status(_status)
        if _kind in ("not_found", "proxy_auth"):
            return "unreachable"            # 見 docstring：gspread 無探測鏈
        return _kind or "unreachable"       # 2xx/3xx 卻拋例外 → 當連線層問題
    if is_quota_error(exc):                 # 有些包裝只剩字串，撈不到狀態碼
        return "rate_limited"
    # 連線逾時 / 憑證建置失敗 / SpreadsheetNotFound(str 常空) → 最短冷卻
    return "unreachable"


# gspread 失敗分類中，值得在**同一次呼叫內**立刻重試的種類。
#
# ⚠️ 刻意排除 `rate_limited`（429）—— `shared/backoff_policy.py` 對它的定性是
# 「唯一一種『對方明確叫我們停』的失敗，繼續探測會延長封鎖窗口」；立刻重試等於違反
# 那個定性。也排除 `blocked`（403，IP/Referer 層級封鎖，秒級重試不會解除）與
# `not_found` / `proxy_auth`（設定問題，不是暫時性抖動，重試不會自癒）。
# ~~只留 `server_error`（5xx）與 `unreachable`（逾時／連線層）—— 兩者才是「多半是
# 暫時性抖動」的分類，這正是 2026-09-02 production 事故命中的那一種。~~
#
# ⚠️ **2026-09-07 更正（有意識的更正，不是漏刪 · 決策者：F30 修復組，依客戶
# 2026-09-07「非 UI 的底層技術／模組修復一律內部自決」授權）**：
# **上面括號裡的等式是假的，兩個都是** ——
#   · `server_error` **不等於** 5xx：`kind_for_status` 把 400 / 401 / 402 / 409 / 410
#     等**非特例的 4xx 一起**歸進來（那是 `shared/backoff_policy.py` 對**冷卻長度**
#     刻意的分法，見該檔表格「5xx / 401 / 402 等非 404 的錯誤碼 → 300s」）；
#   · `unreachable` **不等於**逾時／連線層：`kind_for_gspread_error` 明文把
#     **404 / 407 改判**成它（為了拿到 60s 冷卻，而不是 0）。
# 於是把本集合當成重試判準時，400 / 404 / 407 / 409 / 410 全部落進「可重試」——
# **2026-09-07 實測（修復前）各重打 4 次**，而它們一次都不該重打。
#
# **本集合自 2026-09-07 起降為「caller 的收窄旋鈕」，不再是重試判準。**
# 判準改由 `is_transient_gspread_error()` 承擔（獨立的一條軸，見該函式 docstring）。
# 本集合保留不刪的理由：它仍是 `with_gspread_retry(retry_kinds=...)` 的預設值，
# 讓 caller 能**再收窄**（例如只重試 5xx、不重試連線層）；**它只能收窄，不能放寬**。
GSPREAD_RETRYABLE_KINDS: "frozenset[str]" = frozenset({"server_error", "unreachable"})


def is_transient_gspread_error(exc: BaseException) -> bool:
    """這次失敗值不值得**在同一次呼叫內立刻重試**？（重試軸判準，2026-09-07 新增）

    ## 為什麼不能沿用冷卻分類（這是本函式存在的唯一理由）

    `kind_for_status` / `kind_for_gspread_error` 回的是**冷卻分類** —— 它們回答的是
    「**這個來源接下來幾秒不要碰**」，不是「**這次值不值得馬上再打一次**」。
    兩條軸多數時候一致，但有三處**必然分岔**；舊實作直接把冷卻分類當重試判準，
    三處全錯：

    | 狀態 | 冷卻分類 | 冷卻軸為何這樣分 | 重試軸的正確答案 |
    |---|---|---|---|
    | 400 / 409 / 410 等 4xx | `server_error` | `shared/backoff_policy.py` 明文把「5xx / 401 / 402 等非 404 的錯誤碼」**一起**給 300s —— 對**冷卻長度**而言它們同級 | ⛔ **不重試**：請求本身壞掉，重打一百次還是同一個錯 |
    | 404 | `unreachable`（60s） | gspread 沒有探測鏈，不能照抄 `not_found` 的 0 冷卻 | ⛔ **不重試**：sheet_id 不存在／沒被分享，每次 rerun 都重演 |
    | 407 | `unreachable`（60s） | 同上，取最短冷卻讓使用者改完 secrets 就恢復 | ⛔ **不重試**：設定問題，秒級重打不會自癒 |

    **`unreachable` 這個名字是給冷卻軸用的**（意思是「給它最短的冷卻」），
    重試軸卻把它讀成「連線層抖動 → 值得重試」—— **同一個字串在兩條軸上意思不同**，
    這就是 2026-09-07 之前 400 / 404 / 407 會被重打 4 次的機制。

    ⚠️ **為什麼不去改 `kind_for_status` 讓它把 4xx 分出來**（本次刻意不做，理由存證）：
    (a) 那張表是**冷卻**的 SSOT，`shared/backoff_policy.py` 白紙黑字把 401 / 402 歸在
        `server_error`，**改它等於改一份本批邊界外的 SSOT**；
    (b) 它另有兩個 production 消費者（`repositories/fund/fx_and_main.py`、
        `repositories/hot_money_repository.py`），兩者都**只拿它決定冷卻長度**，
        分裂分類會讓它們的冷卻從 300s 掉到 60s（未知 kind 從寬的預設）——
        一個沒有人要求、也沒有人量過的行為變更；
    (c) `tests/test_gspread_source_backoff.py` 已釘住 `kind_for_status(401) == "server_error"`
        與 `kind_for_gspread_error(404/407) == "unreachable"`，該檔在本批邊界外。
    → **兩條軸分開，才是既修對又不外溢的做法。**

    ## 判準

    - **有 HTTP 狀態碼** → 只有 **5xx** 算暫時性。4xx 一律是「請求／權限／設定」問題，
      不會因為隔一秒再打就變好。
    - ~~**沒有狀態碼** → 連線層（逾時 / DNS / 連線被重設）算暫時性~~，**除非**它是只剩
      字串的配額錯誤（`is_quota_error`）—— 429 是「對方明確叫我們停」，立刻重試會
      延長封鎖窗口（`shared/backoff_policy.py` 對 `rate_limited` 的定性）。
      → ⚠️ **2026-09-08 就地更正（有意識的更正，不是漏刪；日期 2026-09-08；
      決策者：品管與 CI 守衛組，依獨立稽核指出並實測確認）**：劃掉的半句**把實作寫窄了**。
      程式並沒有去判斷「這是不是連線層」——它是**「撈不到狀態碼、又不是配額錯誤」
      就一律回 `True`**。也就是說**任何**無狀態碼的例外都會被當成暫時性，
      **包含永久性的那些**。完整後果與實測見下方「**已知限制 (2)**」。

    ## ⚠️ 已知限制（誠實揭露，§-2 規則 6）—— **兩條，不是一條**

    **(1) 無 gspread 的精簡環境：狀態碼整個撈不到。**
    狀態碼來自 `http_status_of`，而它在**無 gspread 的精簡環境**一律回 `None`
    （該函式對 `ImportError` 的既有處置）。在那種環境裡，一個帶 400 的 `APIError`
    會退化成「無狀態碼」→ 判為暫時性 → 照舊重試。本 repo `requirements.txt` pin 了
    `gspread>=6.0.0`，正常 CI 與 production 不會落到這條路；但**這個 fail-open 是
    真的存在**，不要以為它守得住沒有 gspread 的環境。
    `tests/test_gspread_retry_kind.py` 有一條專門釘住這個退化行為。

    **(2) 有 gspread 的正常環境也一樣：無狀態碼的永久性錯誤，本函式一律判錯。**
    ⚠️ **這一條在正常 production 就會發生，不是只在精簡環境** —— 上面 (1) 講的是
    「gspread 不在」，這一條講的是「gspread 在，但那個例外本來就沒有 HTTP 狀態碼」。

    本函式的判準是「**有狀態碼 → 只有 5xx 算暫時**」，對**撈不到狀態碼**的例外完全
    無效：它們一律走到最後那個 `return True`。於是下列**永久性**失敗仍會被重打滿
    `len(backoffs)` 次（2026-09-08 實測，同一支 before/after 對照器）：

    | 例外 | 實務上的成因 | 修復前 | 修復後 |
    |---|---|---|---|
    | `SpreadsheetNotFound()`（`str()` 常空） | **SA 沒有被分享**到那份 sheet | 4 次 | **4 次（未修好）** |
    | 裸 `PermissionError()`（`str()` 空） | gspread 6.x 對 **403** 的形狀（見 `tests/test_describe_sheet_exc.py` 記載的 2026-08-11 線上事故 v19.431） | 4 次 | **4 次（未修好）** |
    | `WorksheetNotFound()` | 分頁名打錯 | 4 次 | **4 次（未修好）** |
    | `ValueError("bad credentials JSON")` | 憑證 JSON 壞掉 | 4 次 | **4 次（未修好）** |

    ⚠️ **這不是本次改動造成的退步** —— 修復前後**完全相同**（4 → 4），本次一個字都
    沒有把它弄壞；**但它也不是「設計如此、沒問題」**。它是**尚未處理的既有限制**：
    本次的分軸只蓋到「**有狀態碼**」那一半，**無狀態碼那一半整類沒修**。

    ⛔ **特別要記的是**：實務上本 repo 真的會發生的那兩種永久性失敗
    （**SA 沒被分享** → `SpreadsheetNotFound`、**憑證沒權限** → 裸 `PermissionError`）
    **都是無狀態碼的**，因此**都不在本次修好的範圍內**。換句話說，本函式擋掉的是
    「帶 400 / 404 / 407 狀態碼」那一類，**不是**「所有永久性錯誤」。
    不要因為本次修過就以為永久性錯誤都不會被重打了。

    **為什麼沒有一起修**：收斂它要動 `http_status_of` 的契約（讓它有辦法表達
    「這是永久性、只是沒有狀態碼」），而該函式有 `services/nav_history_gs.py` 與
    `repositories/pool_repository.py` 兩個**本批邊界外**的消費者。依 `CLAUDE.md §-1`
    無觸發，**登記，不動工**。
    """
    _status = http_status_of(exc)
    if _status is not None:
        return 500 <= _status <= 599
    if is_quota_error(exc):     # 只剩字串的 429：對方叫我們停，不是抖動
        return False
    return True                 # 逾時 / DNS / 連線被重設


def with_gspread_retry(call: Callable, *args,
                       backoffs: tuple[float, ...] = DEFAULT_QUOTA_BACKOFFS,
                       retry_kinds: "frozenset[str]" = GSPREAD_RETRYABLE_KINDS,
                       **kwargs) -> Any:
    """包裝 gspread 呼叫：依 `kind_for_gspread_error` 分類，只重試「多半是暫時性」的種類。

    為什麼不能直接沿用 `with_quota_retry`
    --------------------------------------
    `with_quota_retry` 只認 429（配額），是**寫入路徑**既有的既定行為（兩份原始實作
    `policy/_helpers.py` / `snapshot_repository.py` 逐字複製而來，本檔只抽共用，刻意
    不改判準 —— 改判準等於改變既有 caller 的行為，超出「抽 SSOT」的範圍）。

    本函式服務的是另一個問題 —— **2026-09-02 production 事故**：
    `nav_history_gs.load_points` 的 Gate 0 預讀被 `client.open_by_key` 的一次 **5xx**
    打斷、**零重試**，直接判定「讀不到既有歷史 → fail-closed 本次不寫雲端」（8/31、9/2
    各中一次；15 次執行 2 次命中）。5xx 不是配額，`is_quota_error` 抓不到它；
    `kind_for_gspread_error` 才分得出 429 / 403 / 5xx / 逾時，本函式據此分流重試。

    嘗試次數 = `len(backoffs)`；最後一次仍失敗 → 拋出原例外（§1 fail loud，不吞）。

    ~~非 `retry_kinds` 內的分類（429 / 403 / 404 / 407）**第一次失敗就直接拋出，不重試**。~~
    ⚠️ **2026-09-07 更正（有意識的更正，不是漏刪 · 決策者：F30 修復組，依客戶
    2026-09-07「非 UI 的底層技術／模組修復一律內部自決」授權）**：
    **上句自寫下起就與實作不符** —— 404 / 407 被 `kind_for_gspread_error` 明文改判成
    `"unreachable"`，而 `"unreachable"` **就在** `retry_kinds` 裡；400 / 409 / 410 則被
    `kind_for_status` 歸進 `"server_error"`（同樣在裡面）。**2026-09-07 實測（修復前）：
    400 / 404 / 407 / 409 / 410 各被重打 4 次。**
    ⛔ **本次修的是行為，不是這句話** —— 那句話描述的**才是對的行為**，錯的是實作；
    故不採「改 docstring 去遷就壞行為」的解法。修法：新增
    `is_transient_gspread_error()` 這條**獨立的重試軸**（兩軸為何必須分開，見該函式
    docstring 的對照表），不再拿冷卻分類當重試判準。

    **現行行為（兩道閘門，兩道都過才重試）**：
      1. `is_transient_gspread_error(e)` —— **判準**：只有 5xx 與連線層算暫時性；
      2. `kind_for_gspread_error(e) in retry_kinds` —— **旋鈕**：留給 caller 再收窄
         （例如只重試 5xx、不重試連線層）。**只能收窄，不能放寬。**
    → 400 / 403 / 404 / 407 / 409 / 410 / 429 一律**第一次失敗就直接拋出，不重試**。

    ⚠️ **429 刻意維持「不重試」，本次沒有改**（理由寫在這裡，免得後人以為是漏掉）：
    (a) `shared/backoff_policy.py` 對它的定性是「唯一一種『對方明確叫我們停』的失敗，
        繼續探測會延長封鎖窗口」；(b) 429 已經有專屬的重試路徑
        `with_quota_retry`（`repositories/policy/_helpers.py` /
        `snapshot_repository.py` 在用），本函式與它是**刻意的分工**，
        讓本函式也重試 429 會把那個分工壓平；(c) 它現況沒壞，且已被
        `tests/test_nav_append_retry.py` 與 `tests/test_nav_gate0_retry.py` 各釘一條。

    ⚠️ **本函式本身不登記冷卻**（`record_gspread_failure` 一律留給呼叫端，在重試迴圈
    之外、例外真正往外傳播之後才呼叫）—— 這是 2026-09-02 事故的第二個教訓：
    9/2 那次已有跨呼叫冷卻機制在跑，若讓「第一次失敗」就登記冷卻，接下來 300 秒
    （`server_error` 的冷卻時長）同一張表的所有讀取會被 `should_skip_gspread` 主動
    擋下 —— **連自己剛加的重試機會都用不到**。冷卻只能在「重試全部用完」之後才登記。
    """
    last_err: BaseException | None = None
    for attempt, delay in enumerate(backoffs):
        try:
            return call(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 — gspread 例外類型隨版本變
            last_err = e
            is_last = attempt == len(backoffs) - 1
            # 兩道閘門，順序有意義：先問「這是不是暫時性」（判準），
            # 再問「caller 允不允許這個冷卻分類」（旋鈕，只能收窄）。
            _retry = (is_transient_gspread_error(e)
                      and kind_for_gspread_error(e) in retry_kinds)
            if not _retry or is_last:
                raise
            time.sleep(delay)
    if last_err is not None:
        raise last_err
    return None


def should_skip_gspread(actor: str, sheet_id: str) -> "tuple[bool, float, str]":
    """這把憑證 + 這本試算表，現在該不該跳過？→ (skip, 剩餘秒數, kind)。

    ⚠️ **兩把鑰匙都要查** —— 這是 `infra/proxy.py::fetch_url` 學不來的一點：它只查
    `source_key(url)` 一把。自訂鍵**必須由呼叫端自己在進場處查**，否則登記的旗標
    沒有任何人會讀。
    """
    from infra import source_backoff as _sb

    if not actor:
        return (False, 0.0, "")             # 無憑證（本地後端）→ 不上網，不退避
    for _k in (quota_key(actor), sheet_key(actor, sheet_id)):
        _skip, _left, _kind = _sb.should_skip(_k)
        if _skip:
            return (True, _left, _kind)
    return (False, 0.0, "")


def record_gspread_failure(actor: str, sheet_id: str,
                           exc: BaseException) -> "tuple[str, int]":
    """記一次 gspread 失敗。回 (實際登記的鍵, 冷卻秒數)；無憑證時回 ("", 0)。

    配額類記在**憑證**鍵（同一把憑證的所有試算表一起冷卻，因為配額是共用的）；
    其餘記在**單一試算表**鍵（不誤殺同憑證下健康的另一本）。
    """
    from infra import source_backoff as _sb

    if not actor:
        return ("", 0)
    _kind = kind_for_gspread_error(exc)
    _key = (quota_key(actor) if _kind == "rate_limited"
            else sheet_key(actor, sheet_id))
    return (_key, _sb.record_failure(_key, _kind))


def record_gspread_success(actor: str, sheet_id: str) -> None:
    """成功一次 → **兩把鑰匙都解除**。

    成功同時證明了兩件事：這把憑證**當下打得通**（配額鍵可解）、這本試算表讀得到
    （試算表鍵可解）。
    ⚠️ **2026-09-01 措辭收緊（稽核 NEW-7）**：~~「這把憑證沒有被限流」~~ 說得太滿 ——
    Sheets 的**讀與寫是不同的配額桶**，一次成功的**寫入**不證明**讀**配額可用。
    本函式由讀取端與寫入端共用，故改成不逾越證據的說法。
    ⚠️ 稽核與本組**都沒能一手查證**那兩個桶的關係（本環境 egress 擋掉
    `developers.google.com`），因此這裡**不對配額做任何宣稱**。
    """
    from infra import source_backoff as _sb

    if not actor:
        return
    _sb.record_success(quota_key(actor))
    _sb.record_success(sheet_key(actor, sheet_id))
