# -*- coding: utf-8 -*-
"""DG-2 Stage-1（C+ canonical fund identity，Shadow Mode）的 L0 常數與資料表。

客戶裁示 `DEC-2026-10-28-05`（逐字：`docs/evidence/decisions/2026-10-28_dg2_identity_ruling.md`）。
設計說明：`docs/v2/70_dg2_canonical_identity_proposal.md`〈Stage-1 C+ shadow 設計與實作〉。

本檔只放常數（無 I/O、不 import L1+，`CLAUDE.md` §8.2 硬規則 3）。
"""

from __future__ import annotations

from types import MappingProxyType

# ── Feature flag（預設關）────────────────────────────────────────────────
# 關閉時 production 行為逐位元組不變：`services/v2_tables/fund_keys.py::resolve_full_keys`
# 唯一的 shadow hook 連 import 都不做（測試：`tests/test_fund_identity_dg2.py` flag-off 測試）。
# 打開時 hook 只寫 `logging` 記錄（無 UI、無 Sheet 寫入、不改回傳值）。
# 本 repo 沒有以環境變數覆寫 L0 常數的既有慣例，故不提供 env override；要開請改這一行（須 Decision Gate）。
DG2_SHADOW_ENABLED: bool = False

# ── Unknown sentinel（裁示第 4 項：沒有可靠資料時一律 Unknown，不猜）───────────
UNKNOWN: str = "Unknown"

# ── verification_status ──────────────────────────────────────────────────
STATUS_UNRESOLVED: str = "unresolved"  # 輸入解析不出合格代碼；不猜
STATUS_BASE_RESOLVED: str = "base_resolved_attributes_unverified"  # 依「第一個 - 前＝基金碼」取得 base；其餘屬性未驗
STATUS_EXCEPTION: str = "exception_distinct_series_needs_decision"  # 例外登記／證據顯示後綴可能是不同序列；不合併、待 Decision Gate
# 帶 `-` 的代碼，但沒有證據顯示它屬於 MoneyDJ／平台代碼命名空間（例：FundClear 級別碼 `AGIF-HT5`／`AGIF-HTG`
# 是同一基金的不同級別）→ 不剝後綴、不合併（2026-10-28 獨立稽核 MUST 1）。
STATUS_NAMESPACE_UNKNOWN: str = "namespace_unknown_suffix_not_stripped"
STATUS_OUT_OF_SCOPE_NAMESPACE: str = "out_of_scope_namespace"  # 呼叫端明示非 MoneyDJ 命名空間（例 fundclear）
NAMESPACE_MONEYDJ: str = "moneydj"  # 「第一個 - 前＝基金碼」只在此命名空間成立
# ── 2026-10-29 客戶最終裁示 `DEC-2026-10-29-01`（逐字：`docs/evidence/decisions/2026-10-29_dg2_final_ruling.md`）──
# MoneyDJ 命名空間內，後綴也只在**已驗證 mapping** 命中時才剝（裁示第 4 項第 3、4 點）：
# 有 MoneyDJ 證據但後綴不在通路表／客戶確認表 → 不剝、不合併。
STATUS_SUFFIX_UNVERIFIED: str = "moneydj_suffix_unverified_not_stripped"
# 呼叫端宣告輸入取自 Google Sheet「基金代號」欄（裁示第 1、4 項）：命名空間固定 MoneyDJ，值須為基本代碼。
# 只適用於該欄；不得推廣到其他 Sheet、其他欄或外部 API 的 code。
INPUT_SOURCE_SHEET_FUND_CODE: str = "sheet_fund_code_column"
INPUT_SOURCE_NAMESPACES = MappingProxyType({INPUT_SOURCE_SHEET_FUND_CODE: NAMESPACE_MONEYDJ})
# Sheet 基金代號欄的值不符基本代碼契約（帶 `-`、網址、格式不符…）→ 原值保留、不剝不截不改寫、只標記。
STATUS_SHEET_CONTRACT_VIOLATION: str = "sheet_code_contract_violation"

# ── 已驗證後綴 mapping 的出處標記 ──
SUFFIX_PROVENANCE_CHANNEL_TABLE: str = "channel_table"  # 注入的通路表（shadow 綁定 L1 `_BANK_PLATFORM_CODES`）
SUFFIX_PROVENANCE_CUSTOMER_2026_10_29: str = "customer_confirmed_2026-10-29"
NAV_EQUIVALENCE_UNVERIFIED: str = "UNVERIFIED"
# 客戶確認的業務語意（裁示第 3 項）：完整代碼 → 基本代碼。不含通路名稱（客戶未給，不自編）。
# NAV 等價性未經證據（container 無法連 MoneyDJ，2026-10-29）；不得當成「同一 NAV series」的證據。
# `TLZF9-AL001`／`TLZF9-24A7` 已在通路表內，不重複列。
CUSTOMER_CONFIRMED_SUFFIXES = MappingProxyType({
    ("ACDD01", "EQTAL005"): MappingProxyType({
        "provenance": SUFFIX_PROVENANCE_CUSTOMER_2026_10_29,
        "decision": "DEC-2026-10-29-01",
        "nav_equivalence": NAV_EQUIVALENCE_UNVERIFIED,
    }),
})

# ── MoneyDJ 頁型（裁示第 5 項）──
# 只有**網址明示**的頁型才記；裸碼一律 Unknown（前綴／對照表推斷不可靠，見 `docs/v2/70` 第 15 節）。
# 值是 MoneyDJ 頁面類別（境內／境外頁），不是基金屬性的證明。其他頁型（wb01／wr01／a1_mobile…）→ Unknown。
PAGE_TYPE_SOURCE_URL: str = "url"
MONEYDJ_PAGE_MARKET = MappingProxyType({"yp010000": "domestic", "yp010001": "offshore"})

# ── 外部候選驗證（裁示第 10 項）───────────────────────────────────────────
CANDIDATE_ACCEPTED: str = "accepted"  # base_fund_code 或 isin 已確認相符，且沒有衝突
CANDIDATE_REJECTED: str = "rejected"  # 已知屬性明確衝突 → 拒收、留 evidence
CANDIDATE_UNVERIFIED: str = "unverified"  # 沒有衝突，但 base_fund_code／isin 都未確認（只有幣別等相符也算這裡）
SOURCE_CONFLICT_TEXT: str = "⬜ 資料來源不一致，暫無法判定"  # 客戶指定顯示文字，逐字

# ── Cross-view NAV（裁示第 11 項）────────────────────────────────────────
NAV_CONSISTENT: str = "consistent"
NAV_CONFLICT: str = "source_conflict"
NAV_NOT_COMPARABLE: str = "not_comparable"

# ── 例外登記（裁示第 2 項）───────────────────────────────────────────────
# (base_fund_code, platform_suffix)：有**證據**顯示該後綴對應不同 share class／幣別／配息／避險／NAV series。
# 預設為空：目前沒有任何一筆有證據（`docs/v2/70` 舊 UI 稽核 B.2：只有註解宣稱，無資料）。
# 新增一筆須附 evidence 並走 Decision Gate；命中者 resolver 不合併。
IDENTITY_EXCEPTIONS: frozenset = frozenset()
