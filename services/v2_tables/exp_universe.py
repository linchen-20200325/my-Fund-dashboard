# -*- coding: utf-8 -*-
"""標的探索（exp）正式模式的候選母體：選股池的基金代碼（L2；不接 streamlit、不讀秘密值）。

依據：客戶 2026-10-13 裁示（B 線標的探索正式模式第一批 ——
「只有代碼、其餘欄 ⬜」；「禁止從基金名稱、代碼或 AI 推測任何屬性；缺值保持缺值、不填 0」）。

本檔只做一件事：呼叫 L1 `repositories/pool_repository.py::list_pool`，**只取 `code` 這一欄**，
回傳去空白、去重（保持原順序）後的代碼清單與計數。

- ⛔ **選股池的 `name`／`currency`／`category`／`type_override`（以及 `isin`、`morningstar_secid`、
  `status`、`note`、`added_at`）一律不讀** —— 客戶已判定選股池的幣別等欄為系統推測、不可信；
  本檔的回傳值結構上就沒有那些欄（`load_pool_codes` 只碰 `entry.code`）。
- ⛔ **不過濾 `status`**（含 `CLOSED` 也列）：客戶沒有訂哪一種狀態不算母體，本層不自創篩選規則。
- **先檢查 `pool_backend_status(...)`**：回 `"local"`（沒有服務帳戶、也沒有注入登入者 OAuth）時，
  **不讀本機 JSON 當母體**（`cache/fund_pool/pool.json` 在雲端重開就消失，那不是使用者的選股池），
  照實回 `STATUS_NOT_CLOUD`，畫面顯示「選股池未設定雲端來源」。
- 讀取失敗 → 回 `STATUS_FAILED` 與遮蔽後的訊息原文（§1：「讀不到」不得長得跟「池是空的」一樣）。
- **空字串代碼**：丟棄並計數（`dropped_blank`）。⚠️ L1 `PoolEntry.from_row` 本來就把代碼為空的列
  丟掉（回 None）、`__post_init__` 也已去空白 —— 所以這裡的計數只涵蓋**到得了本層**的空代碼，
  在 L1 被丟掉的那幾列本層看不到、也數不到（據實寫明，不宣稱「全部空列都數到了」）。
- 不放任何快取（快取只在 L1，`49` §4.4）；不發任何網路請求以外的副作用（L1 讀取路徑唯讀，
  `GoogleSheetsPoolStore._ws` 2026-09-06 起不建表、不補表頭）。

秘密值由 L3（`ui_v2/exp/source.py`）讀好傳進來，失敗訊息在這裡遮一次（體例同 `settings_store`）。
"""

from __future__ import annotations

from repositories import pool_repository
from services.v2_tables.masking import mask_message

STATUS_OK = "ok"
STATUS_NOT_CLOUD = "pool_not_cloud"
STATUS_FAILED = "failed"

# 回 `"local"` 時的訊息（字面為本組擬定；畫面照印）。
TEXT_NOT_CLOUD = "選股池未設定雲端來源（沒有服務帳戶憑證），不讀本機暫存檔當母體"


def _empty(status: str, backend: str, message) -> dict:
    return {"status": status, "backend": backend, "codes": [], "dropped_blank": 0,
            "duplicates": 0, "message": message}


def load_pool_codes(secret_values, *, oauth_client=None) -> dict:
    """選股池的基金代碼。

    回傳 `{"status", "backend", "codes", "dropped_blank", "duplicates", "message"}`：
    - `status`：`STATUS_OK`／`STATUS_NOT_CLOUD`／`STATUS_FAILED`；
    - `backend`：`pool_backend_status` 的原值（`service_account`／`oauth`／`local`）；
    - `codes`：去前後空白、去重（第一次出現的位置為準）後的代碼清單；**大小寫原樣保留**
      （不 upper —— 本層不替使用者改寫代碼）；
    - `dropped_blank`：去空白後為空字串而被丟掉的筆數；`duplicates`：重複而被併掉的筆數；
    - `message`：失敗或未設定雲端時的訊息（已遮蔽）；OK 時為 None。

    `oauth_client`：L1 的注入點（登入者的 gspread client）。⚠️ ui_v2 目前沒有取得它的途徑
    （取它的現有函式住在舊樹 `ui/`，ui_v2 不得 import），呼叫端恆傳 None ⇒ 只有服務帳戶一條路。

    ⚠️ 讀取例外一律收成 `STATUS_FAILED`（訊息帶例外型別名）：`list_pool` 往外拋的型別沒有封閉清單
    （gspread 的 `APIError`、憑證錯誤、`RuntimeError`／`KeyError` 都會出現，本套件不得 import gspread 去列舉），
    而這一支唯一的動作就是讀選股池 —— 任何例外都是「這次讀不到」，在畫面上以紅字照實顯示，
    **不是吞掉**（§1）。`pool_backend_status` 本身是純判斷，不包在 try 裡。
    """
    mask = lambda text: mask_message(text, list(secret_values))  # noqa: E731
    backend = pool_repository.pool_backend_status(oauth_client)
    if backend == "local":
        return _empty(STATUS_NOT_CLOUD, backend, TEXT_NOT_CLOUD)
    try:
        entries = pool_repository.list_pool(oauth_client)
    except Exception as exc:  # noqa: BLE001 — 理由見 docstring：照實回失敗，不吞
        return _empty(STATUS_FAILED, backend, mask(f"{type(exc).__name__}: {exc}"))
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
    return {"status": STATUS_OK, "backend": backend, "codes": codes, "dropped_blank": dropped_blank,
            "duplicates": duplicates, "message": None}
