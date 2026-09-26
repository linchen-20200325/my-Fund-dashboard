# -*- coding: utf-8 -*-
"""失敗訊息遮蔽（`ACCEPTANCE.md` 七；客戶 2026-09-26 裁示 Q13）。

本模組是純函式：**不讀 secrets、不讀環境變數、不 import streamlit**。
秘密值由 L3（`ui_v2/<頁>/source.py`）從 `st.secrets`、環境變數與登入後的權杖讀好，
整理成「來源 mapping」傳進 `secret_values`，再把得到的值交給 `mask_message`。

規則（ACCEPTANCE 7.3，逐條對應）：
- 固定記號 `‹已遮蔽›`；一個秘密值換成一個記號；其餘字元逐字保留。
- 每一次出現都換；同一個值另外遮 `quote(值, safe="")`、`quote_plus(值)` 兩種編碼形態；
  服務帳戶 `private_key` 另外遮「換行被跳脫成反斜線加 n」的寫法。
- 由長到短替換；空值不參與；大小寫敏感、完全相同才換；不猜「像金鑰的字串」。
- 遮蔽只在寫出點做一次（本批的寫出點是 mkt 正式入口的畫面；`fetch_log` 尚未落地，Q12）。

鍵名表（ACCEPTANCE 7.2 甲、乙、乙之二）寫在 `MASKED_*`；7.2 丙「讀到但不遮」寫在 `NOT_MASKED_KEYS`。
兩張範本 `secrets.toml.example`、`.streamlit/secrets.toml.example` 的每個鍵都必須落在其中之一，
由 `tests/test_v2_tables_masking.py` 比對，範本多了新鍵而表沒跟上就紅。
"""

from __future__ import annotations

import json
from typing import Iterable, Mapping, Optional

MASK = "‹已遮蔽›"  # ‹已遮蔽›

# 7.2 甲／乙／乙之二：頂層鍵，整個值遮。
MASKED_WHOLE_VALUE_KEYS = (
    "FRED_API_KEY", "FINMIND_TOKEN", "ALPHAVANTAGE_API_KEY",
    "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
    "LINE_CHANNEL_TOKEN", "LINE_CHANNEL_ACCESS_TOKEN", "GITHUB_TOKEN",
    # 設定與取數紀錄試算表的 ID（總管 2026-09-26 回修第 2 輪裁示：歸「要遮」）。
    # 與 7.2 丙其餘試算表 ID 刻意不同：`50` 第 2 節定案這本的 ID 只放 secret、不得公開
    # （它會被寫入，連錯本就是把設定寫進別人的檔）。⚠️ ACCEPTANCE.md 7.2 的表尚未同步這一列。
    "SETTINGS_SHEET_ID",
) + tuple(f"GEMINI_API_KEY_{i}" for i in range(1, 11))
# 逗號分隔多把、逐把遮。
MASKED_COMMA_LIST_KEYS = ("GEMINI_API_KEYS",)
# 網址型：只遮 userinfo 的帳號與密碼，主機與埠不遮。
MASKED_URL_USERINFO_KEYS = ("PROXY_URL",)
# 區段型：區段名 → 要遮的子鍵。
MASKED_SECTION_FIELDS = {
    "proxy": ("username", "password"),
    "google_service_account": ("private_key", "private_key_id"),
    "google_oauth": ("client_secret",),
}
# 服務帳戶 JSON 字串（排程腳本與 TOML 的 JSON 字串寫法）：遮其中 private_key、private_key_id。
MASKED_SA_JSON_KEYS = ("GOOGLE_SERVICE_ACCOUNT_JSON", "GSPREAD_SA_JSON")
# 登入後才有的 OAuth 權杖（`st.session_state["gsheet_tokens"]`）與使用者自填的 OAuth 設定。
MASKED_TOKEN_FIELDS = ("access_token", "refresh_token", "id_token")
MASKED_CUSTOM_OAUTH_FIELDS = ("client_secret",)

# 7.2 丙：讀到了、但本規則不遮（不是憑證；遮了反而無法除錯）。區段內欄位寫成「區段.欄位」。
NOT_MASKED_KEYS = (
    "POLICY_SHEET_ID", "NAV_SHEET_ID", "POOL_SHEET_ID", "macro_weights_sheet_id", "SHEET_ID",
    "WATCH_CSV_URL", "LINE_USER_ID", "GITHUB_REPOSITORY", "NAV_GATE0_MODE", "NAV_CODES",
    "US_STOCK_IDS", "FUND_DB", "GOOGLE_APPLICATION_CREDENTIALS", "CHROMIUM_EXECUTABLE_PATH",
    "GITHUB_STEP_SUMMARY",
    "proxy.endpoint",
    "google_service_account.type", "google_service_account.project_id",
    "google_service_account.client_email", "google_service_account.client_id",
    "google_service_account.auth_uri", "google_service_account.token_uri",
    "google_service_account.auth_provider_x509_cert_url",
    "google_service_account.client_x509_cert_url",
    "google_oauth.client_id", "google_oauth.redirect_uri",
)


def _get(mapping, key):
    try:
        return mapping.get(key)
    except Exception:  # noqa: BLE001 —— st.secrets 缺檔時 .get 會拋；當作沒有這個鍵
        return None


def _section(mapping, name) -> Optional[Mapping]:
    """區段可能是 mapping（TOML 表格）或 JSON 字串（ACCEPTANCE 7.2：兩種寫法都收）。"""
    value = _get(mapping, name)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    return value if hasattr(value, "get") else None


_UNRESERVED = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-~")


def _quote(value: str, *, plus: bool) -> str:
    """與 `urllib.parse.quote(value, safe="")`／`quote_plus(value)` 相同的輸出。

    ⚠️ 自己寫而不 import `urllib`：L2 純度守衛（tests/test_services_purity_contract.py）
    的 import 白名單不含 `urllib`（它同時是網路套件的根）。對照測試拿 `urllib` 逐字比。
    """
    out = []
    for byte in value.encode("utf-8"):
        if byte in _UNRESERVED:
            out.append(chr(byte))
        elif plus and byte == 0x20:
            out.append("+")
        else:
            out.append(f"%{byte:02X}")
    return "".join(out)


def _userinfo(url) -> list:
    """`scheme://帳號:密碼@主機:埠/…` 的帳號與密碼（原樣，不解碼）；主機與埠不收。"""
    if not isinstance(url, str) or "://" not in url:
        return []
    rest = url.split("://", 1)[1]
    if "@" not in rest:
        return []
    # 以最後一個 `@` 切（密碼可能含 `/`、`@` 以外的任何字元；代理網址沒有路徑）
    info = rest.rsplit("@", 1)[0]
    user, _sep, password = info.partition(":")
    return [v for v in (user, password) if v]


def secret_values(sources: Iterable[Mapping], *, oauth_tokens=None, custom_oauth_cfg=None) -> list:
    """從各來源 mapping（例如 `st.secrets`、`os.environ`）取出 7.2 列名鍵的**值**。

    同一個鍵在多個來源都有值時全部收（值不同就兩個都遮）。回傳去重後的非空字串清單。
    """
    found: list = []

    def add(value):
        if isinstance(value, str) and value != "":
            found.append(value)

    for mapping in sources:
        if mapping is None:
            continue
        for key in MASKED_WHOLE_VALUE_KEYS:
            add(_get(mapping, key))
        for key in MASKED_COMMA_LIST_KEYS:
            raw = _get(mapping, key)
            if isinstance(raw, str):
                for piece in raw.split(","):
                    add(piece.strip())
        for key in MASKED_URL_USERINFO_KEYS:
            for piece in _userinfo(_get(mapping, key)):
                add(piece)
        for name, fields in MASKED_SECTION_FIELDS.items():
            section = _section(mapping, name)
            if section is not None:
                for field in fields:
                    add(_get(section, field))
        for key in MASKED_SA_JSON_KEYS:
            section = _section(mapping, key)
            if section is not None:
                for field in MASKED_SECTION_FIELDS["google_service_account"]:
                    add(_get(section, field))
    if oauth_tokens is not None and hasattr(oauth_tokens, "get"):
        for field in MASKED_TOKEN_FIELDS:
            add(_get(oauth_tokens, field))
    if custom_oauth_cfg is not None and hasattr(custom_oauth_cfg, "get"):
        for field in MASKED_CUSTOM_OAUTH_FIELDS:
            add(_get(custom_oauth_cfg, field))
    return list(dict.fromkeys(found))


def _forms(value: str) -> list:
    forms = [value, _quote(value, plus=False), _quote(value, plus=True)]
    if "\n" in value:
        forms.append(value.replace("\n", "\\n"))
    return forms


def mask_message(message: str, secrets: Iterable[str]) -> str:
    """把 message 裡每一個秘密值（含編碼形態）換成 `MASK`；其餘字元逐字保留。"""
    if not isinstance(message, str):
        raise TypeError(f"mask_message 只收字串（{type(message).__name__}）")
    forms = {f for value in secrets if isinstance(value, str) and value != "" for f in _forms(value)}
    forms.discard("")
    out = message
    for form in sorted(forms, key=lambda f: (-len(f), f)):  # 由長到短
        out = out.replace(form, MASK)
    return out


def is_masked(message) -> bool:
    """字串裡確實含記號才回 True（ACCEPTANCE 7.4：沒有遮任何東西時不加註記）。"""
    return isinstance(message, str) and MASK in message
