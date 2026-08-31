"""⑤ 承接「📋 保單管理（Google Sheets）」的橋接層 —— 本批預設由旗標關閉。

線框（客戶已拍板）`docs/wireframes/fund-wireframe-final.html` §03 ⑤
「A · 🔌 連線與帳號」把 ④ 的保單管理設定區列為搬入項；WP-D（#736）已把該區
790 行原封抽成 `ui/helpers/portfolio/policy_admin_section.py`，本檔是 ⑤ 端的
承接口。**這一批不切換**：

- 旗標（`merge_context.POLICY_ADMIN`）**預設關閉** → ⑤ 只顯示 ⬜ 灰色說明，
  `render_policy_admin_section` 一行都不會跑；④ 的 `ui/tab3_portfolio.py`
  照舊呼叫、一個字未改 —— 同一塊不會被畫兩次。
- 旗標打開屬**接線批次**的動作，且有下列**硬前置**，缺一不可：

⚠️ 接線批次切換旗標前必須先處置的前置（已知清單，非窮舉）
----------------------------------------------------------
1. **session_state 先寫後讀耦合（#736 兩輪稽核留下的施工指南）**：
   保單管理區與 ④ 之間有**至少四處**同一次 run 內先寫後讀 / 先讀後寫的耦合 ——
   `portfolio_core_pct`／`policy_sheet_id`／`gsheet_tokens`／`_schema_ver`。
   **完整清單與逐條說明在 `ui/tab3_portfolio.py` 的
   「⚠️ 為什麼用 container 佔位」註解區（該處明標「已知清單，不是窮舉」）**。
   把本區搬到 ④ 之後執行（⑤ 在分頁列的位置在 ④ 之後）會讓 ④ 讀到舊值 ——
   切旗標＝改變執行順序，**必須先重掃再動**。
2. **`sheet_client` 尚無可 import 的 SSOT**：SA-first + 403 回退決策目前是
   `ui/tab3_portfolio.py::render_portfolio_tab()` 內的 closure
   （`_t3_sheet_client`，含 `_t3_sa_can_open` session 快取），**無法 import**。
   本檔拒絕複製那 ~50 行（複製＝第二份真相源，`CLAUDE.md §2.1`），
   故要求接線批次先把它抽成共用 helper 再注入 —— 在那之前旗標開著也會
   **當場 raise**（§1 Fail Loud），不會拿一個假 client 渲染到一半才炸。
3. **oauth snapshot 的 fresh 紀律**：`ui/helpers/oauth_state` 的 6 個名字是
   module-level snapshot，必須「先 `refresh_oauth_state()` 再重新 import」
   才拿得到 fresh 值（v18.148 修過的 bug；`policy_admin_section.py` docstring
   有完整說明）。本檔的旗標開啟路徑已照做，接線批次不必另行處理，
   但**不得**改成 module 頂部 import。
"""
from __future__ import annotations

from typing import Callable, Optional

from ui.helpers.render_state import not_ready
from ui.helpers.settings_diag.merge_context import (
    POLICY_ADMIN,
    owned_by_settings_page,
)


def render_policy_admin_bridge(
    sheet_client: Optional[Callable] = None,
) -> Optional[str]:
    """⑤ 的「保單管理（連線與授權）」承接口。

    Parameters
    ----------
    sheet_client : 接線批次注入的 Sheet client 決策 callable
        （語意同 `ui/tab3_portfolio.py::_t3_sheet_client`：SA-first + 403 回退）。
        本批一律傳 None —— 旗標關閉時根本用不到；旗標開啟而沒注入時當場 raise。

    Returns
    -------
    Optional[str]
        旗標開啟且渲染完成時，回傳 `render_policy_admin_section` 算出的
        `_sheet_id`（語意見該檔 docstring）；旗標關閉時回傳 None。
    """
    if not owned_by_settings_page(POLICY_ADMIN):
        # 本批狀態：⑤ 未接線。什麼都沒壞 → ⬜ 灰色說明，不是紅燈（三態規則）。
        #
        # ⚠️ 2026-08-31 由 WP-F 修正（**有意識的政策變更，不是漏改** ·
        # 決策者：AI 總管 · 依據：客戶 2026-08-31 拍板的五分頁線框）。
        # 舊寫法 ~~`where="📊 配置 & 帳本 → 📋 保單管理（Google Sheets）"`~~ 的理由
        # **仍然成立** ——「灰色說明要指出去哪裡才能用到這個功能」這個目的沒有變。
        # 被權衡掉的是它**寫死了一個已經不存在的分頁名**：七→五之後 ④ 叫
        # 「📊 我的配置」，分頁列上沒有「📊 配置 & 帳本」。
        # 它與同一個函式（`not_ready(where=...)`）在 `fetch_diag_section.py` 被修掉的
        # 那一處是**同一種寫法、同一種病**：不經 `tab_label` 所以**連 raise 都不會**，
        # 只會安靜地指到一個不存在的分頁名 —— 那一批只修了一隻，這是它的兄弟。
        # 改吃 SSOT：`where_to_find('portfolio')` 回「④ 📊 我的配置」，
        # 站號與分頁名都由 `_TAB_LABELS` 的順序推導，不寫死。
        # （「📋 保單管理（Google Sheets）」是 ④ **頁內**的區塊標題、不是分區 key，
        #   故原樣接在後面 —— 它不在 `_SECTION_LABELS` 裡，硬塞進去會讓
        #   `section_label()` 回一個沒有對應分區錨點的名字。）
        from ui.helpers.story_nav import where_to_find  # noqa: PLC0415

        not_ready(
            "保單管理（Sheet 連線／OAuth 授權／v1→v2 升級）尚未接線到本頁 ——"
            "接線前它仍完整住在配置分頁，不會少功能也不會出現兩份",
            where=f"{where_to_find('portfolio')} → 📋 保單管理（Google Sheets）",
        )
        return None

    if sheet_client is None:
        # §1 Fail Loud：旗標開了卻沒給 client ＝ 接線批次跳過了硬前置。
        # 拿假 client 渲染到使用者按下按鈕才炸，是更糟的結果 —— 在這裡就炸。
        raise RuntimeError(
            "POLICY_ADMIN 旗標已開啟，但未注入 sheet_client。"
            "接線批次必須先把 ui/tab3_portfolio.py::_t3_sheet_client"
            "（SA-first + 403 回退決策）抽成共用 SSOT 再注入本函式；"
            "並先處置 tab3 註解列出的至少四處 session_state 先寫後讀耦合"
            "（portfolio_core_pct / policy_sheet_id / gsheet_tokens / _schema_ver，"
            "明標非窮舉）。詳見本模組 docstring。")

    # ── 旗標開啟路徑（接線批次才會走到）────────────────────────────────
    # oauth snapshot 的 fresh 紀律：先 refresh 再 local re-import（v18.148；
    # 與 ④ 的 caller 完全同款，理由見 policy_admin_section.py docstring）。
    from ui.helpers.oauth_state import refresh_oauth_state as _refresh_oauth_state
    _refresh_oauth_state()
    from ui.helpers.oauth_state import (  # noqa: PLC0415 — 必須在 refresh 之後
        _oauth_configured,
        _resolve_oauth_cfg,
        _get_oauth_client,
        _gsa_secret,
        _sheet_id_secret,
        get_login_state as _get_login_state,
    )
    from ui.helpers.portfolio.policy_admin_section import (  # noqa: PLC0415
        render_policy_admin_section as _render_policy_admin,
    )

    return _render_policy_admin(
        oauth_configured=_oauth_configured,
        resolve_oauth_cfg=_resolve_oauth_cfg,
        get_oauth_client=_get_oauth_client,
        gsa_secret=_gsa_secret,
        sheet_id_secret=_sheet_id_secret,
        get_login_state=_get_login_state,
        sheet_client=sheet_client,
    )
