# -*- coding: utf-8 -*-
"""呈現語意規則資料表（presentation-semantic constants）—— New UI2 批 2b。

依據：`docs/v2/80_new_ui2_architecture_proposal.md` 第 3.3 節 (c)（規則資料表＋純函式放共同層）、
第 4.2 節（`shared/<presentation-semantic 常數模組>`，名稱屬內部決定）、第 6 節（view model contract）；
NG-4 A（`DEC-2026-11-02-05`：保留既有狀態符號、顏色語意與正式用字）。

- 只用標準函式庫；不 import streamlit、services、repositories、infra 或任何 UI 套件（Old UI、ui_v2、New UI2）。
- import 時零副作用（模組層只有常數、def、class）。
- New UI2 的 viewmodels／pages 兩層可以 import 本套件（New UI2 import 守衛的明列白名單，見下方註解）；
  ui_v2 是否改讀本表屬 NG-2 maintenance 批，本批不動 ui_v2。
- ⚠️ 本套件的字串常數（含 docstring）不得出現 New UI2 的目錄名：正式入口守衛會掃 shared/ 的字串常數，
  防止 preview 被正式路徑引用；路徑請寫在 `#` 註解裡。

規則內容住 `rules.py`；本檔只重新匯出。
"""
# 白名單住 tests/ui_v3/ui_v3_guard_lib.py（SHARED_ALLOWED_PACKAGE／SHARED_ALLOWED_LAYERS）。
from shared.ui_semantics.rules import (  # noqa: F401
    ACTION_UNDETERMINED_FORM,
    ACTION_WORDS,
    APPROVED_WORDING,
    ApprovedWording,
    approved,
    BETA_LEVELS,
    BETA_QUOTE,
    CHIP_KIND_TO_KEY,
    ENTRIES,
    FETCH_FAILED_SAME_SOURCE_TEXT,
    FETCH_FAILED_SCREEN_FORM,
    MISSING_TEXT,
    NOT_CONFIGURED_FORM,
    PENDING_WORDING,
    PrecedenceLevel,
    REASON_NOT_CONFIGURED,
    SemanticEntry,
    TONES,
    entry,
    entry_for_chip_kind,
    entry_for_freshness,
    entry_for_status,
    pending_entries,
    resolve_precedence,
)
