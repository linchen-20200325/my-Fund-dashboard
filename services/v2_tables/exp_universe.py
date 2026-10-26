# -*- coding: utf-8 -*-
"""標的探索（exp）正式模式的候選母體：選股池的基金代碼（L2；不接 streamlit、不讀秘密值）。

依據：客戶 2026-10-13 裁示（B 線標的探索正式模式第一批 ——
「只有代碼、其餘欄 ⬜」；「禁止從基金名稱、代碼或 AI 推測任何屬性；缺值保持缺值、不填 0」）。

本檔只做一件事：讀選股池，**只取 `code` 這一欄**，回傳去空白、去重（保持原順序）後的代碼清單與計數。

- ⛔ **選股池的 `name`／`currency`／`category`／`type_override`（以及 `isin`、`morningstar_secid`、
  `status`、`note`、`added_at`）一律不讀** —— 客戶已判定選股池的幣別等欄為系統推測、不可信；
  本檔的回傳值結構上就沒有那些欄（只碰 `entry.code`）。
- ⛔ **不過濾 `status`**（含 `CLOSED` 也列）：客戶沒有訂哪一種狀態不算母體，本層不自創篩選規則。
- **本機 JSON 不當母體**：~~先檢查 `pool_backend_status(...)` 回 `"local"`~~ → 2026-10-13 稽核 K 回修
  （有意識的更正，不是漏刪；決策者：AI 總管）：**直接看 `get_pool_store(...)` 交回的 store 型別** ——
  是 `LocalJsonPoolStore` 就照實回 `STATUS_NOT_CLOUD`，並且**就讀這一個 store**（不再另外呼叫 `list_pool`）。
  舊寫法靠 `pool_backend_status` 與 `get_pool_store` 兩支 L1 函式的判斷碰巧一致；
  稽核 K 的反例：服務帳戶在、但試算表 ID 為空 → 前者回 `service_account`、後者卻交出本機 store，
  舊寫法就會把本機暫存檔當母體讀。
- 讀取失敗 → 回 `STATUS_FAILED` 與遮蔽後的訊息原文（§1：「讀不到」不得長得跟「池是空的」一樣）。
- **空字串代碼**：丟棄並計數（`dropped_blank`）。⚠️ L1 `PoolEntry.from_row` 本來就把代碼為空的列
  丟掉（回 None）—— 這裡的計數只涵蓋**到得了本層**的空代碼（據實寫明，不宣稱全部數到了）。

**快取與失敗冷卻（2026-10-13 稽核 L 回修；總管技術裁定）** —— 正式頁每一次互動都會重跑 `load_live`，
沒有快取時每一次都打一次 Google Sheets、失敗也不退避：
- **只快取成功結果**（`STATUS_OK`），TTL 取 `shared.ttls.TTL_1HOUR`。理由：選股池是使用者手動維護的清單，
  變動頻率以天計；而失敗冷卻沿用 `infra.gspread_retry`，最長一種（限流，`shared.backoff_policy.
  BACKOFF_RATE_LIMITED_SEC` ＝ 1800 秒）必須**短於**成功 TTL，`TTL_30MIN` 會與它相等，故取下一級。
  代價：在別處改了選股池，本頁最多晚一小時看到（畫面上 `EXP-2` 說明行寫出讀取時間與更新間隔）。
  ~~側欄「全域刷新」（`infra.cache.clear_all_caches`）會清掉這份快取（本檔以 `register_cache` 登記），
  那是立即生效的逃生門。~~ → 2026-10-13 第二輪複驗更正（有意識的更正，不是漏刪；決策者：AI 總管）：
  **那句不成立** —— ui_v2 全樹沒有任何 `clear_all_caches` 呼叫點，那個側欄按鈕住在舊站（另一個程式）。
  **實況：B 線目前沒有清除入口**，只能等一小時過期或重啟程式。`register_cache` 的登記照留
  （同一個行程裡若有人呼叫 `clear_all_caches` 仍清得掉），但它不是使用者在 B 線摸得到的東西。
  ⚠️ `49` §4.4 寫「快取只在 L1」：L1 `list_pool()` 本身沒有快取（`_cached_pool_map` 是另一支、回的是
  補淨值查表用的 map），本頁又不得改 L1，所以快取放在這一層（總管 2026-10-13 指定 L2 或 source 二選一）。
- **失敗冷卻**：沿用 `infra.gspread_retry` 的 `should_skip_gspread`／`record_gspread_failure`／
  `record_gspread_success`，鍵取 L1 `pool_repository._pool_backoff_ident(...)`（與 L1 自己讀選股池的冷卻
  **同一把鑰匙** —— 同一本試算表、同一把憑證，失敗一次全部讀取點一起冷卻）。冷卻期內**不重打**，
  回上一次的失敗原文並註明「冷卻中」；冷卻到期由 `infra.source_backoff` 自動解除，下一次就真的重試。
  ⚠️ **歸因（2026-10-13 第二輪複驗回修）**：限流冷卻記在**整把憑證**上（`gspread:quota:<actor>`），
  別本試算表（設定、保單）被 429 也會讓本頁跳過 —— 那時選股池一次都沒讀過，不得寫「選股池剛讀取失敗過」。
  種類為限流 → 寫「同一把<憑證>目前被 Google 限流……本次未讀選股池」；
  不是限流、但本模組沒有自己記過失敗 → 寫「其他讀取點剛讀取失敗」；
  **只有本模組自己記過同一種失敗時**才接「上次失敗：<原文>」。
  存檔不涉選股池，不清這份快取。
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from infra.cache import register_cache
from infra.gspread_retry import (
    kind_for_gspread_error,
    record_gspread_failure,
    record_gspread_success,
    should_skip_gspread,
)
from repositories import pool_repository
from services.v2_tables.masking import mask_message
from shared.ttls import TTL_1HOUR

STATUS_OK = "ok"
STATUS_NOT_CLOUD = "pool_not_cloud"
STATUS_FAILED = "failed"

# 本機 store 時的訊息（字面為本組擬定；畫面照印）。
TEXT_NOT_CLOUD = "選股池未設定雲端來源（沒有服務帳戶憑證），不讀本機暫存檔當母體"
# 2026-10-26 J-7（移除寫死預設本）：`POOL_SHEET_ID` 未設定時同走 `STATUS_NOT_CLOUD`，但原因要寫對。
TEXT_NO_SHEET_ID = "選股池未設定雲端來源（部署端未設定選股池試算表），不讀本機暫存檔當母體"
# 冷卻中時的訊息前半（後面接上一次的失敗原文）。字面為本組擬定。
TEXT_COOLING = "選股池剛讀取失敗過，冷卻中（約剩 {left} 秒），本次不重打 Google Sheets"
# 2026-10-13 第二輪複驗回修：冷卻不是本模組自己的失敗造成時的兩句（字面為本組擬定）。
TEXT_COOLING_QUOTA = "同一把{actor}目前被 Google 限流，冷卻中（約剩 {left} 秒），本次未讀選股池"
TEXT_COOLING_OTHER = "選股池在其他讀取點剛讀取失敗過，冷卻中（約剩 {left} 秒），本次未讀選股池"
_ACTOR_TEXT = {"sa": "服務帳戶", "oauth": "登入身分"}

SUCCESS_TTL_SEC = TTL_1HOUR

_LOCK = threading.Lock()
_CACHE: dict = {}          # (actor, sheet_id) → (存入時間 monotonic, 成功結果 dict)
# (actor, sheet_id) → (冷卻種類, 原文〔未遮蔽，回傳前才遮〕, 冷卻到期時刻〔monotonic〕)。
# 2026-10-13 稽核 K 第三輪：記下這一筆冷卻**何時到期**，只有與目前正在生效的那筆冷卻是同一筆
# （到期時刻相差不到 `_SAME_COOLDOWN_SEC`）時才接「上次失敗」——舊紀錄不得接到不相干的冷卻上。
# 比對對象取 `should_skip_gspread` 交回的剩餘秒數（`infra.source_backoff` 那一筆的 until），
# 不直接讀 `infra.source_backoff`（不在 L2 的 infra 子模組白名單上）。
# ⚠️ 已知限制（總管 2026-10-13 決定不修：要修得改 L1／infra，超出本檔射程）：同一身分、同一種類的冷卻
# 若在本頁記下之後被別處覆寫，而新那一筆的到期時刻恰好與本頁記的相差不到 `_SAME_COOLDOWN_SEC`
# （或反過來，同一筆被誤判成不是同一筆），本頁會判錯「這筆冷卻是不是自己記的」。
# 判錯時，冷卻說明的**主句**（「選股池剛讀取失敗過」或「選股池在其他讀取點剛讀取失敗過」）與後面附的
# 「上次失敗」原文**會一起錯**；燈色、狀態與任何資料都不受影響。
# （〔已撤〕舊註寫「只影響後面附的原文」—— 稽核 L 第六輪指出主句也會跟著錯，有意識的更正，不是漏刪。）
_LAST_FAILURE: dict = {}
_SAME_COOLDOWN_SEC = 2.0
# 與 `infra.source_backoff._clock` 同一種時鐘（monotonic）；模組層變數讓測試能注入同一個假時鐘。
_clock = time.monotonic


class _PoolCodesCache:
    """給 `infra.cache` 的登記物件：`clear_all_caches()` 會呼叫 `cache_clear()`。
    `cache_info()` 照 `infra/cache.py` 的欄位契約只交必備的 `name`／`size`（沒有命中率統計 —— 不湊 0）。"""

    __name__ = "exp_pool_codes"

    def cache_clear(self) -> None:
        with _LOCK:
            _CACHE.clear()
            _LAST_FAILURE.clear()

    def cache_info(self) -> dict:
        with _LOCK:
            return {"name": self.__name__, "size": len(_CACHE), "ttl_sec": SUCCESS_TTL_SEC}


_REGISTERED = register_cache(_PoolCodesCache())


def clear_cache() -> None:
    _REGISTERED.cache_clear()


def _empty(status: str, backend: str, message, *, cooling: bool = False) -> dict:
    # `cooling`：這一次是因為冷卻中而沒有去讀（不是讀了失敗）。畫面據此如實寫摘要（稽核 L 第六輪）。
    return {"status": status, "backend": backend, "codes": [], "dropped_blank": 0,
            "duplicates": 0, "message": message, "read_at": None, "ttl_sec": SUCCESS_TTL_SEC,
            "cooling": cooling}


def _own_for(record, kind: str, left: float, clock: float):
    """本模組自己記過的那一筆，若與目前生效的冷卻是同一筆（同種類、到期時刻一致）→ `(種類, 原文)`；否則 None。"""
    if record is None:
        return None
    own_kind, raw, until = record
    if own_kind != kind or abs((clock + left) - until) > _SAME_COOLDOWN_SEC:
        return None
    return own_kind, raw


def cooling_text(actor: str, left: float, kind: str, own) -> str:
    """冷卻中時的那一句（未遮蔽）。`own`：本模組自己記過、而且就是目前這筆冷卻的 `(種類, 原文)`，沒有為 None。"""
    seconds = int(left + 0.999)
    if kind == "rate_limited":
        text = TEXT_COOLING_QUOTA.format(actor=_ACTOR_TEXT.get(actor, "憑證"), left=seconds)
    elif own is not None:
        text = TEXT_COOLING.format(left=seconds)
    else:
        text = TEXT_COOLING_OTHER.format(left=seconds)
    if own is not None and own[0] == kind:
        text += f"；上次失敗：{own[1]}"
    return text


def _codes_of(entries) -> dict:
    codes, seen = [], set()
    dropped_blank = duplicates = 0
    for entry in entries:
        code = str(entry.code if entry.code is not None else "").strip()
        if not code:
            dropped_blank += 1
            continue
        if code in seen:
            duplicates += 1
            continue
        seen.add(code)
        codes.append(code)
    return {"codes": codes, "dropped_blank": dropped_blank, "duplicates": duplicates}


def load_pool_codes(secret_values, *, oauth_client=None, now=None, wall=None) -> dict:
    """選股池的基金代碼。

    回傳 `{"status", "backend", "codes", "dropped_blank", "duplicates", "message"}`：
    - `status`：`STATUS_OK`／`STATUS_NOT_CLOUD`／`STATUS_FAILED`；
    - `backend`：L1 store 的 `backend_name`（`google-sheets`／`local-json`）；
    - `codes`：去前後空白、去重（第一次出現的位置為準）後的代碼清單；**大小寫原樣保留**；
    - `dropped_blank`／`duplicates`：被丟掉的空代碼筆數／被併掉的重複筆數；
    - `message`：失敗、冷卻中或未設定雲端時的訊息（已遮蔽）；OK 時為 None。
    - `read_at`：這一份代碼**實際讀自試算表**的時間（UTC，ISO 8601）；快取命中時沿用原讀取時間；失敗時為 None。
    - `ttl_sec`：成功結果的快取秒數（畫面據此寫「最長約多久更新一次」）。

    `oauth_client`：L1 的注入點。⚠️ ui_v2 目前沒有取得它的途徑（取它的現有函式住在舊樹 `ui/`），呼叫端恆傳 None。
    `now`：測試用（monotonic 秒）；不傳取 `time.monotonic()`。`wall`：測試用（讀取時間）；不傳取現在的 UTC 時間。

    ⚠️ 讀取例外一律收成 `STATUS_FAILED`（訊息帶例外型別名）：`list_pool` 往外拋的型別沒有封閉清單
    （gspread 的 `APIError`、憑證錯誤、`RuntimeError`／`KeyError` 都會出現，本套件不得 import gspread 去列舉），
    而這一段唯一的動作就是讀選股池 —— 任何例外都是「這次讀不到」，在畫面上以紅字照實顯示，**不是吞掉**（§1）。
    """
    mask = lambda text: mask_message(text, list(secret_values))  # noqa: E731
    now = time.monotonic() if now is None else now
    store = pool_repository.get_pool_store(oauth_client)
    backend = getattr(store, "backend_name", type(store).__name__)
    if isinstance(store, pool_repository.LocalJsonPoolStore):
        text = TEXT_NOT_CLOUD if pool_repository.pool_sheet_configured() else TEXT_NO_SHEET_ID
        return _empty(STATUS_NOT_CLOUD, backend, text)

    key = pool_repository._pool_backoff_ident(oauth_client)
    with _LOCK:
        hit = _CACHE.get(key)
    if hit is not None and now - hit[0] < SUCCESS_TTL_SEC:
        return dict(hit[1], codes=list(hit[1]["codes"]))

    skip, left, kind = should_skip_gspread(*key)
    if skip:
        with _LOCK:
            own = _own_for(_LAST_FAILURE.get(key), kind, left, _clock())
        return _empty(STATUS_FAILED, backend, mask(cooling_text(key[0], left, kind, own)), cooling=True)

    try:
        entries = store.list_pool()
    except Exception as exc:  # noqa: BLE001 — 理由見 docstring：照實回失敗，不吞
        # 失敗種類直接從例外判（與 `record_gspread_failure` 內部用的是同一支），不事後再查冷卻表（稽核 K 第三輪）。
        recorded_kind = kind_for_gspread_error(exc)
        _key, cooldown = record_gspread_failure(key[0], key[1], exc)
        raw = f"{type(exc).__name__}: {exc}"
        with _LOCK:
            if cooldown:
                _LAST_FAILURE[key] = (recorded_kind, raw, _clock() + cooldown)
            else:
                _LAST_FAILURE.pop(key, None)
        return _empty(STATUS_FAILED, backend, mask(raw))
    record_gspread_success(*key)
    read_at = (wall or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    result = {"status": STATUS_OK, "backend": backend, "message": None, "read_at": read_at,
              "ttl_sec": SUCCESS_TTL_SEC, "cooling": False, **_codes_of(entries)}
    with _LOCK:
        _LAST_FAILURE.pop(key, None)
        _CACHE[key] = (now, dict(result, codes=list(result["codes"])))
    return result
