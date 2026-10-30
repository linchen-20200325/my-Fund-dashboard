# -*- coding: utf-8 -*-
"""持倉體檢（hld）與資產配置（alo）的「個人 Active Sheet」入口閘門（批 3b-4；客戶 2026-10-26 裁示 J-7、J-13）。

兩頁的持倉原始表**只**來自使用者在設定頁選定並驗證過的 Active Sheet（個人 Google 帳號、唯讀）；沒有 Active
就沒有持倉資料，**不退回** `POLICY_SHEET_ID`／服務帳戶。本檔只管畫面這一端：

- `NoActiveSource`：source 在「沒有 Active Sheet」時拋出（`AUTH_REQUIRED` 未登入、`UNAVAILABLE` 沒有可用的 Active），
  page 在 `load_live()` 外層接住、改畫 `render_no_active`。這是**明確的第三種狀態**：不是 0、不是中性、不是「空持倉（正常）」、
  不是 HOLD；缺就是缺（Missing stays Missing）。
- `failure_text(code)`：其餘失敗碼（`AUTH_EXPIRED`／`PERMISSION_DENIED`／`SHEET_NOT_FOUND`／`SCHEMA_INVALID`／
  `NETWORK_ERROR`／`UPSTREAM_ERROR`／`AUTH_STATE_INVALID`；只有 `ui_v2_error_codes` 的九個 code，不新增）→ 一句純文字，
  交給兩頁**既有**的持倉讀取失敗路徑（`holding_error` → 「⛔ 取數失敗」＋ plain 換成使用者語言）。顏色不是唯一資訊（⛔ 與字都在）。
  文字不含 token、不含上游原文。字面與 `repositories/personal_drive_repository.py::_SAFE_MESSAGES` 逐字一致（測試比對；
  本檔不 import 舊樹）。

新增的使用者可見字樣（`TEXT_NO_ACTIVE`、`LINK_LABEL`、`FAILURE_TEXT` 的 `AUTH_STATE_INVALID`／`UNAVAILABLE` 以外各句）
**待客戶確認用字**（PR 說明「awaiting customer wording」）。`TEXT_NO_ACTIVE` 與 `LINK_LABEL` 的字面取自
`shared/active_sheet.py` 檔頭記載的 J-13 畫面路徑「⬜ 尚未選定持倉資料來源 → 前往 ⚙️ 設定」。
"""

from __future__ import annotations

import html
from datetime import datetime, timezone

import streamlit as st

from . import page_health

TEXT_NO_ACTIVE = "⬜ 尚未選定持倉資料來源"
LINK_LABEL = "前往 ⚙️ 設定"
# 單頁入口（沒有 `st.navigation`，換不了頁）時的說明行。
LINK_ELSEWHERE_TEXT = "請到「設定」頁選定持倉資料來源"
# 總表「尚未設定」那一族要寫哪一項（`page_health.make_item` 的 key）。
UNCONFIGURED_KEY = "持倉資料來源"

# 沒有 Active 的兩個 code：未登入（連選的機會都還沒有）、沒有可用的 Active（含帳號不符）。
NO_ACTIVE_CODES = frozenset({"AUTH_REQUIRED", "UNAVAILABLE"})

# 其餘失敗碼 → 一句純文字（鏡像 `repositories/personal_drive_repository.py::_SAFE_MESSAGES`；測試逐字比對）。
FAILURE_TEXT = {
    "AUTH_EXPIRED": "Google 登入已過期，需要重新登入",
    "PERMISSION_DENIED": "沒有權限讀取該資源",
    "SHEET_NOT_FOUND": "找不到該試算表",
    "UPSTREAM_ERROR": "Google 服務回應異常",
    "NETWORK_ERROR": "無法連線到 Google",
    "SCHEMA_INVALID": "試算表不符合必要條件（缺少保單分頁）",
}
# 不在上表的 code（`AUTH_STATE_INVALID`，或未知）：只講事實，不編原因。
FAILURE_TEXT_DEFAULT = "無法讀取所選的持倉資料來源"
# `SCHEMA_INVALID` 的細分（同一個 code，不新增 code）：`reason` → 固定句。標頭原文可能是使用者資料，**不上畫面**。
# `no_policy_tab` 沿用上表 `SCHEMA_INVALID` 那句（缺少保單分頁）；其餘兩句是新增，待客戶確認用字。
SCHEMA_REASON_TEXT = {
    "no_policy_tab": FAILURE_TEXT["SCHEMA_INVALID"],
    "policy_header": "保單分頁的標頭不符（第 1 列有空白或重複的欄位）",
    "supplement_header": "補充分頁的標頭與規格不符",
}


class NoActiveSource(Exception):
    """沒有 Active Sheet（未登入或沒有可用的 Active）。只帶 code，不帶 token 與上游原文。"""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


# `UNAVAILABLE` 身兼數職（沒有 Active／部署設定缺…）：只有 reason 是這個固定值才是「沒有 Active」。
# 字面與 `services/v2_tables/personal_session.REASON_NO_ACTIVE` 一致（測試比對；本檔不 import L2 橋接）。
REASON_NO_ACTIVE = "no_active"


def is_no_active(code, reason=None) -> bool:
    """AUTH_REQUIRED（未登入）→ 沒有 Active；UNAVAILABLE 只在 reason 為 `no_active` 時才算。
    其餘（含 UNAVAILABLE 的其他原因，如部署設定缺）走既有失敗路徑，不當成「尚未選定」。"""
    if code == "UNAVAILABLE":
        return reason == REASON_NO_ACTIVE
    return code in NO_ACTIVE_CODES


def failure_text(code, reason=None) -> str:
    if code == "SCHEMA_INVALID" and reason in SCHEMA_REASON_TEXT:
        return SCHEMA_REASON_TEXT[reason]
    return FAILURE_TEXT.get(code, FAILURE_TEXT_DEFAULT)


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def record_no_active(slug: str) -> None:
    """各頁資料狀態總表記一筆「尚未設定：持倉資料來源」（`render_no_active` 的記錄那一半；BL-0525 Batch D 抽出，
    合併頁一次要記 hld 與 alo 兩格）。"""
    if slug in page_health.PAGE_NAMES:
        page_health.record(
            st.session_state, slug,
            [page_health.make_item(
                page_health.KIND_UNCONFIGURED, UNCONFIGURED_KEY,
                # 讓值讀不到（整頁沒有持倉資料）→ 擋主要原因，不落在「只影響比較值」（順位 6）
                [page_health.affected(UNCONFIGURED_KEY, "", unreadable=True)], lamp=True, order=0)],
            as_of=None, now=datetime.now(timezone.utc))


def render_no_active(slug: str, *, title: str, answers: str, title_class: str, sub_class: str, tone_hex,
                     settings_page=None) -> None:
    """整頁「尚未選定持倉資料來源」畫面：頁名、提問句、一行狀態（灰、`⬜`）、一枚只換頁的連結；其餘塊不畫。

    各頁資料狀態總表記一筆「尚未設定：持倉資料來源」（不記成取數失敗、也不記成「沒有異常」）。只換頁、不取數、不寫入。
    """
    record_no_active(slug)
    st.markdown(f'<div class="{_esc(title_class)}">{_esc(title)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="{_esc(sub_class)}">{_esc(answers)}</div>', unsafe_allow_html=True)
    render_no_active_status(tone_hex=tone_hex, settings_page=settings_page)


def render_no_active_status(*, tone_hex, settings_page=None) -> None:
    """「⬜ 尚未選定持倉資料來源」一行（灰）＋ 一枚只換頁的連結（沒有 `settings_page` 時只寫說明行）。
    `render_no_active` 的畫面那一半（BL-0525 Batch D 抽出；合併頁把它放在頁頂「持倉資料來源」那一列）。只換頁、不取數、不寫入。"""
    st.markdown(
        f'<div class="v2-no-active" role="status" style="color:{tone_hex("灰")}">{_esc(TEXT_NO_ACTIVE)}</div>',
        unsafe_allow_html=True,
    )
    if settings_page is not None:
        st.page_link(settings_page, label=LINK_LABEL)
    else:
        st.caption(LINK_ELSEWHERE_TEXT)
