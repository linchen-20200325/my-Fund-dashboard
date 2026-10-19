# -*- coding: utf-8 -*-
"""一般畫面去工程化（Phase 3 P0-①；`docs/v2/44_fund_ui_ssot.md` 第七節第三小節之七其二）。

純函式模組：**不 import streamlit、不 import 舊樹**（`tests/ui_v2/test_ui_v2_live_import_guard.py`），
除標準庫（`copy`、`re`）外不 import 任何模組；對照表與 `ui_v2/set/spec.py` 的一致性由測試比對。

做什麼：正式模式的頁面模型（各頁 `logic`／`live` 已經算好、判定完的那一份）**深拷貝**後，
把畫面上的工程字樣換成使用者語言，原文另交出來給設定與診斷頁的「進階診斷（原始訊息）」。

- 失敗原文（`⛔ 取數失敗：<原文>`、`⛔ 設定讀不到：<原文>`、`存檔寫入失敗：<鍵>：<原文>`）→ 一句狀態描述；
  ⛔ 與紅色照舊（顏色、狀態、嚴重度住在 `_` 開頭的鍵，本模組一個都不碰）。原文收進 `raw_entries`。
- 原始鍵名（欄位鍵、指標鍵、表名、設定鍵）→ 中文名：**逐字對照表**（`EXACT_LABELS` 整串對整串、
  `KEY_NAMES` 只換整個詞，前後不接英數字與底線），不拿 regex 改任意文字。
- 句中塊代號（`MKT-1` 等）→ 塊名；「層 N」→ 段名；`Provider:Method` → Provider。

**不做什麼（判定照舊，護欄 2）**：不改 `_` 開頭鍵的純量值（狀態、顏色、啟用與否、輸入欄的值）、`code`、`name`、
任何數值、選項清單（`options`／`sort_options`／`tier_options`／`basis_option_labels`）、塊數、列數；
不新增也不刪除任何一列資料。唯一會讓串列變短的是持倉體檢的 `PRINT_AS_IS_LINE`（「訊息原文照印……」）——
原文已不在一般畫面上，這句話留著就是假話。

**示範模式不經過本模組**（BL-0367）；本模組只由各頁 `page.py` 的正式模式分支呼叫。

需要舊樹的訊息常數時，本檔放**鏡像常數**（下方 `MSG_*`），由 `tests/ui_v2/test_plain_logic.py` 逐字比對真身。
"""

from __future__ import annotations

import copy
import re


# ───────────────────────── 頁與塊 ─────────────────────────

PAGE_NAMES = {"mkt": "市場總覽", "hld": "持倉體檢", "exp": "標的探索", "alo": "資產配置", "set": "設定與診斷"}

# 塊名：逐字等於各頁 `logic` 的 `title`（測試逐字比對；漂了就紅）。
BLOCK_NAMES = {
    "MKT-0": "環境結論燈", "MKT-1": "風險情緒卡", "MKT-2": "景氣位置卡", "MKT-3": "資金與匯率卡",
    "MKT-4": "觀察窗與比較基準輸入", "MKT-5": "指標清單設定", "MKT-6": "指標明細表", "MKT-7": "新鮮度與來源清單",
    "HLD-0": "體檢結論燈", "HLD-1": "偏離提示卡", "HLD-2": "績效與風險卡", "HLD-3": "配息與本金卡",
    "HLD-4": "檢視區間與門檻輸入", "HLD-5": "單檔展開", "HLD-6": "淨值與配息序列", "HLD-7": "計算軌跡",
    "HLD-8": "最大回撤與本金類配息佔比",
    "EXP-0": "篩選結果結論列", "EXP-1": "條件輸入卡", "EXP-2": "候選清單卡", "EXP-3": "並排對照卡",
    "EXP-4": "欄位與排序設定", "EXP-5": "加入觀察清單", "EXP-6": "單檔基礎資料", "EXP-7": "篩選軌跡",
    "ALO-0": "差距結論燈", "ALO-1": "目標輸入卡", "ALO-2": "目標對照卡", "ALO-3": "情境試算卡",
    "ALO-4": "分組定義", "ALO-5": "試算結果匯出", "ALO-6": "歸屬明細", "ALO-7": "目標修改紀錄",
    "SET-0": "可信度結論燈", "SET-1": "資料新鮮度卡", "SET-2": "來源健康卡", "SET-3": "規則參數卡",
    "SET-4": "參數編輯", "SET-5": "重新取數", "SET-6": "取數紀錄", "SET-7": "欄位對照表",
}

# 四段式的段名（44 第七節第三小節之七其一）。層 3、層 4 併入 ④，在其中各自一個小標。
SECTION_CONCLUSION = "①結論"
SECTION_KEY_NUMBERS = "②關鍵數字"
# ③需要注意（不是層、不是塊；之七其一第 2 條）—— Phase 3 P1-④ 起正式模式畫出來（`ui_v2/sections.py`）。
SECTION_ATTENTION = "③需要注意"
SECTION_DETAILS = "④詳細資料"
SUBSECTION_OPERATIONS = "操作"
SUBSECTION_EVIDENCE = "證據／來源"
LAYER_WORDS = {
    "1": SECTION_CONCLUSION,
    "2": SECTION_KEY_NUMBERS,
    "3": f"{SECTION_DETAILS}「{SUBSECTION_OPERATIONS}」",
    "4": f"{SECTION_DETAILS}「{SUBSECTION_EVIDENCE}」",
}
# 頁面上四個段標籤（取代 `層 1　結論` 等）。~~本批不重排 ③④ —— 那是 P1-④~~ → P1-④ 起另有 ③（`LABEL_ATTENTION`）。
LABEL_LAYER1 = SECTION_CONCLUSION
LABEL_LAYER2 = SECTION_KEY_NUMBERS
LABEL_ATTENTION = SECTION_ATTENTION
LABEL_DETAILS = f"{SECTION_DETAILS}（預設收合）"
LABEL_LAYER3 = SUBSECTION_OPERATIONS
LABEL_LAYER4 = SUBSECTION_EVIDENCE

ADVANCED_DIAG_TITLE = "進階診斷（原始訊息）"

# ───────────────────────── 鍵名 → 中文名（只維護這一份） ─────────────────────────

# 第四節八張表（`spec.SPEC_TABLES` 的表名）。
TABLE_NAMES = {
    "holding": "持倉", "nav": "淨值", "dividend": "配息", "policy": "保單",
    "market_indicator": "市場指標", "user_setting": "使用者設定", "fetch_log": "取數紀錄",
    "fund_profile": "基金基本資料",
}

# 欄位鍵（`spec.SPEC_TABLES` 全部欄位，測試逐一比對沒有缺、沒有多）。
COLUMN_NAMES = {
    "holding_id": "持倉編號", "policy_id": "保單編號", "fund_code": "基金代碼", "fund_name": "基金名稱",
    "ccy": "計價幣別", "units_shares": "持有單位數", "cost_orig_ccy": "原幣成本", "cost_twd": "新臺幣成本",
    "opened_on": "開始日", "bucket": "類別", "last_synced_at": "最後核對時間",
    "nav_date": "淨值日", "nav_orig_ccy": "原幣淨值", "source_tier": "來源層級", "is_estimated": "是否推估",
    "fetched_at": "取得時間",
    "ex_date": "除息日", "pay_date": "發放日", "div_per_unit_orig_ccy": "每單位配息（原幣）", "div_kind": "配息類型",
    "policy_name": "保單名稱", "issuer": "發行公司", "premium_paid_twd": "已繳保費（新臺幣）",
    "fee_rate_pct": "費用率", "status": "狀態",
    "indicator_key": "指標", "obs_date": "觀測日", "release_date": "公布日", "value_num": "數值",
    "value_unit": "單位", "is_revised": "是否修正",
    "setting_key": "設定項目", "setting_value": "設定值", "value_kind": "值的型別", "updated_at": "更新時間",
    "log_id": "紀錄編號", "started_at": "開始時間", "finished_at": "結束時間", "outcome": "結果",
    "row_count": "筆數", "message": "訊息",
    "inception_on": "成立日", "dividend_policy": "配息方式", "mgmt_fee_rate_pct": "經理費率",
}

# 使用者設定的鍵（`spec.SPEC_SETTING_KEYS`，測試逐一比對）。
SETTING_NAMES = {
    "alo_basis": "計算基礎", "alo_bucket_names": "類別名稱", "alo_scenario_input": "情境試算輸入",
    "alo_target_weights": "目標比重", "alo_tolerance_pp": "容許帶", "exp_filter_rules": "篩選條件",
    "exp_sort_column": "排序欄位", "exp_visible_columns": "顯示欄位", "exp_watchlist": "觀察清單",
    "hld_deviation_rules": "偏離門檻", "hld_window_end": "檢視區間迄日", "hld_window_start": "檢視區間起日",
    "mkt_baseline_date": "比較基準日", "mkt_compare_pair": "比較條件", "mkt_indicator_keys": "要看的指標",
    "mkt_window_days": "觀察窗長度", "set_log_keep_rows": "取數紀錄保留筆數", "set_max_age_days": "新鮮度上限日數",
}

# 市場指標鍵：逐字等於市場總覽 `logic._CARD_SPECS` 的中文名（測試比對）；`term_spread_pct` 不在三張卡上，
# 名稱照預覽入口檔頭的字（`ui_v2/app_preview.py`：「期限利差」）。
INDICATOR_NAMES = {
    "vol_index": "波動度指數", "credit_spread_pct": "高收益信用利差", "leading_index": "領先指標",
    "coincident_index": "同時指標", "policy_rate_pct": "政策利率", "fx_twd_per_usd": "新臺幣對美元匯率",
    "term_spread_pct": "期限利差",
}

# 規格外、但各頁以欄名當標籤或句中寫出的鍵（每一條都在 `ui_v2` 原始碼裡逐字出現；測試檢查沒有死條目）。
EXTRA_KEY_NAMES = {
    "days_calendar": "日曆日",
    "weight_ratio": "比重",
    "amount_twd": "金額（新臺幣）",
    "div_ratio_pct": "近 12 個月配息佔淨值比",
    "action_kind": "按鈕類別",
}

KEY_NAMES = {**TABLE_NAMES, **COLUMN_NAMES, **SETTING_NAMES, **INDICATOR_NAMES, **EXTRA_KEY_NAMES}

# 整串對整串的標籤對照（先於 `KEY_NAMES` 的整詞替換；用在「中文名＋括號裡的鍵名」這種會重複兩次的字樣）。
EXACT_LABELS = {
    "目標比重 weight_ratio": "目標比重",
    "金額 amount_twd": "金額（新臺幣）",
    "觀察窗長度（days_calendar）": "觀察窗長度（日曆日）",
    "最近淨值（nav_orig_ccy，原幣）": "最近淨值（原幣）",
    "成立日（inception_on）": "成立日",
    "配息方式（dividend_policy）": "配息方式",
    "費率欄（mgmt_fee_rate_pct）": "費率欄",
    "成本（cost_twd）": "成本（新臺幣）",
    "市值（淨值 × 單位數，美元依 fx_twd_per_usd 換算）": "市值（淨值 × 單位數，美元依新臺幣對美元匯率換算）",
    "距今日數（days_calendar）": "距今日數（日曆日）",
}

_EXACT_ORDER = tuple(sorted(EXACT_LABELS, key=len, reverse=True))

# 匯率鍵家族（`fx_twd_per_<幣別>`；資產配置依持倉幣別組出來，母體不封閉，只認這一個形狀）。
_FX_KEY = re.compile(r"(?<![A-Za-z0-9_])fx_twd_per_([a-z]{3})(?![A-Za-z0-9_])")

# ───────────────────────── 鏡像常數（真身在舊樹，測試逐字比對） ─────────────────────────

# `repositories/settings_sheet_repository.py::NOT_CONFIGURED_MESSAGE`
MSG_SETTINGS_NOT_CONFIGURED = "未設定試算表 ID，暫停寫入"
# `repositories/settings_sheet_repository.py::NO_SERVICE_ACCOUNT_MESSAGE`（`policy_supplement_repository` 同字）
MSG_NO_SERVICE_ACCOUNT = "未設定服務帳戶（google_service_account）"
# `repositories/policy_supplement_repository.py::NOT_CONFIGURED_MESSAGE`
MSG_POLICY_NOT_CONFIGURED = "未設定保單試算表 ID（POLICY_SHEET_ID），不讀取"
# `services/v2_tables/market_indicator.py::MISSING_FRED_API_KEY`
MSG_FRED_MISSING = "未設定 FRED_API_KEY"
# `services/v2_tables/exp_universe.py::TEXT_NOT_CLOUD`
MSG_POOL_NOT_CLOUD = "選股池未設定雲端來源（沒有服務帳戶憑證），不讀本機暫存檔當母體"

# 已知訊息 → (資料類，None ＝ 沿用該塊的資料類；一句狀態描述)。比對用「訊息含這一串」。
_KNOWN_MESSAGES = (
    (MSG_SETTINGS_NOT_CONFIGURED, "使用者設定", "設定試算表尚未設定"),
    (MSG_POLICY_NOT_CONFIGURED, "保單與持倉", "保單試算表尚未設定"),
    (MSG_NO_SERVICE_ACCOUNT, None, "讀取用的服務帳戶尚未設定"),
    (MSG_FRED_MISSING, "市場指標", "資料來源的金鑰尚未設定"),
    (MSG_POOL_NOT_CLOUD, "選股池", "選股池的雲端來源尚未設定"),
)

# 各頁 `logic`／`live` 的失敗字首（ui_v2 內的常數；測試逐字比對各頁真身）。
FETCH_FAIL_PREFIX = "⛔ 取數失敗："        # 五頁 `logic.fetch_failed_text`
SETTINGS_UNREADABLE_PREFIX = "⛔ 設定讀不到："  # `ui_v2/mkt/logic.py::TEXT_SETTINGS_UNREADABLE_PREFIX`
SAVE_FAIL_PREFIX = "存檔寫入失敗："       # `ui_v2/mkt/live.py`、`ui_v2/hld/live.py` 的 `TEXT_SAVE_FAILED`
# `ui_v2/hld/logic.py::PRINT_AS_IS_LINE`：原文已移到設定與診斷頁，一般畫面不再說「照印」。
PRINT_AS_IS_LINE = "訊息原文照印，不改寫成安撫語句。"

# 一句狀態描述的預設（沒有認出是哪一種已知訊息時）。字面為本組擬定（44 只定了「⛔ <中文資料類> 取數失敗」
# 加一句影響範圍），只描述狀態、不指示動作（客戶 2026-10-03、2026-10-02 兩則裁示）。
STATE_FETCH_DEFAULT = "相關數字暫時無法判定"
# 客戶 2026-10-18 裁示 BL-0375（`docs/DECISIONS.md` `DEC-2026-10-18-02`；44 第七節第三小節之十）：淨值即時取數失敗、退回的預存序列
# 又超過 10 日 → 各頁寫「⛔ 取數失敗：[<代碼>：]改用 <日期> 的預存淨值」。這一句是本頁自己組的（不是上游原文），
# 而且日期是裁示要求留在畫面上的那一期 ⇒ 一般畫面照留，不換成狀態描述、不移到進階診斷（體例同下方存檔失敗那一族
# 「本頁自己寫的那一句不是原文，照留」）；資料類寫「淨值」。鏡像 `ui_v2/hld/live.py`、`ui_v2/exp/live.py` 的
# `NAV_RETREAT_FAILED_TEXT`（本檔不 import 它們，由測試逐字比對）。
NAV_RETREAT_FAILED_TEXT = "改用 {day} 的預存淨值"
_NAV_RETREAT = re.compile(
    "^" + re.escape(NAV_RETREAT_FAILED_TEXT).replace(re.escape("{day}"), r"\d{4}-\d{2}-\d{2}") + "$")
STATE_SETTINGS_DEFAULT = "已存的設定暫時讀不到"
STATE_SAVE_DEFAULT = "這一次沒有存進去"
STATE_PAGE_DEFAULT = "本頁暫時無法判定"
DATA_CLASS_DEFAULT = "資料"

# ───────────────────────── 句中記號 ─────────────────────────

_BLOCK_CODE = re.compile(r"\b(MKT|HLD|EXP|ALO|SET)-\d\b")
_LAYER = re.compile(r"層\s*([1-4])")
_PROVIDER_METHOD = re.compile(r"(?<![A-Za-z0-9_/])([A-Z][A-Za-z0-9]*):[A-Za-z][A-Za-z0-9_]*")
_TABLE_PREFIX = re.compile(
    r"(?<![A-Za-z0-9_])(" + "|".join(sorted(TABLE_NAMES, key=len, reverse=True)) + r")：\s*$"
)
_FUND_HEAD = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]{1,30})：(.*)$", re.S)
_KEY_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_])("
    + "|".join(sorted((re.escape(k) for k in KEY_NAMES), key=len, reverse=True))
    + r")(?![A-Za-z0-9_])"
)

# 使用者自己的資料（基金名、保單名、類別名、已存的設定值）：顯示時不換任何字。`value_text` 只在紀錄列
# （`_` 開頭容器裡的每一列，例：資產配置 ALO-7 修改紀錄、設定與診斷 SET-3）受保護；主值節點的 `value_text`
# 是本頁組的字（可能是失敗原文），照常換。（2026-10-17 獨立稽核建議）
_USER_DATA_KEYS = frozenset({"fund_name", "policy_name", "fund_text", "policy_text", "bucket_text", "raw_text"})
_ROW_USER_DATA_KEYS = frozenset({"value_text"})

# 不碰的鍵：識別、選項清單、下載檔名、畫面拿去當查表鍵的清單（值會被程式拿去比對、查表或寫出）。
# 另外凡是名字以 `_keys` 結尾的鍵也不碰（`column_keys`、`row_keys` 這類鍵名清單）。
_PROTECTED_KEYS = frozenset(
    {"code", "name", "options", "sort_options", "tier_options", "basis_option_labels", "file_name",
     "sort_shown"}
)


# 設定與診斷頁照舊照印原文、照列鍵名與塊代號的塊（44 第七節第三小節之七其二第 1、2 條：
# `SET-2` 訊息原文、`SET-6` 取數紀錄、`SET-7` 欄位對照表；`SET-3`／`SET-4` 的鍵名不在本批）。
_SET_KEEP_CODES = frozenset({"SET-2", "SET-6", "SET-7"})
_SET_KEY_BLOCKS = frozenset({"SET-0", "SET-1"})


def _protected(key) -> bool:
    return isinstance(key, str) and (key in _PROTECTED_KEYS or key.endswith("_keys"))


# ~~`_block_data_class(code)`：依該塊來源欄推一個資料類~~ → 2026-10-17 獨立稽核必修（有意識的更正，不是漏刪；
# 決策者：AI 總管依稽核）：一塊可以照抄別塊的失敗字串（例：資產配置 ALO-3 照抄 ALO-2 的持倉／匯率失敗），
# 依「這一塊的來源」推資料類會把它標成「使用者設定」—— 錯誤歸因。改為：只有失敗字首帶表鍵、或認得出是
# 已知訊息時才寫具體資料類，否則一律寫「資料」（`DATA_CLASS_DEFAULT`）。舊推法在寫下當時以為各塊只印自己的來源。


def key_name(key) -> str:
    """一個鍵的中文名（找不到 → 原樣）。給輸入元件的 `format_func` 用：顯示換字，底層值不變。"""
    if key is None:
        return ""
    text = str(key)
    return EXACT_LABELS.get(text) or KEY_NAMES.get(text) or _FX_KEY.sub(_fx_name, text)


def _fx_name(match) -> str:
    return f"新臺幣對{match.group(1).upper()}匯率"


def not_configured_state(raw):
    """一句失敗原文若是「尚未設定」那一族（`_KNOWN_MESSAGES`），回那一句狀態描述（例「設定試算表尚未設定」）；否則 None。"""
    if not isinstance(raw, str):
        return None
    known = _known(raw)
    return known[1] if known else None


def _known(raw: str):
    for message, data_class, state in _KNOWN_MESSAGES:
        if message in raw:
            return data_class, state
    return None


class _Context:
    def __init__(self, page: str) -> None:
        self.page = page
        self.raw: list = []
        self.fetch_failed: set = set()
        self.not_configured: set = set()

    def where(self, block) -> str:
        if not block:
            return PAGE_NAMES.get(self.page, self.page)
        return f"{block.get('code')} {block.get('title', '')}".strip()

    def keep(self, block, text: str) -> None:
        entry = {"where": self.where(block), "text": text}
        if entry not in self.raw:
            self.raw.append(entry)


def _rewrite_failure(text: str, block, ctx: _Context):
    """失敗原文那一族 → 一句狀態描述。回 (新字串, 是否改寫)。"""
    if FETCH_FAIL_PREFIX in text:
        prefix, raw = text.split(FETCH_FAIL_PREFIX, 1)
        data_class = DATA_CLASS_DEFAULT
        table = _TABLE_PREFIX.search(prefix)
        if table:   # 標的探索的「<表鍵>：⛔ 取數失敗：…」：表鍵就是資料類，不再另寫一次
            data_class, prefix = TABLE_NAMES[table.group(1)], prefix[: table.start()]
        fund = ""
        match = _FUND_HEAD.match(raw)
        if match and not re.search(r"(Error|Exception)$", match.group(1)) and match.group(1) not in KEY_NAMES:
            fund, raw = match.group(1), match.group(2)
        if _NAV_RETREAT.match(raw):   # BL-0375：本頁自己組的日期句，照留（見 `NAV_RETREAT_FAILED_TEXT`）
            ctx.fetch_failed.add(TABLE_NAMES["nav"])
            ctx.keep(block, text)   # 進階診斷照舊收一份（同其他失敗句），一般畫面另照留日期
            return f"{prefix}⛔ {TABLE_NAMES['nav']} 取數失敗：{fund + '：' if fund else ''}{raw}", True
        known = _known(raw)
        state = STATE_FETCH_DEFAULT
        if known:
            data_class, state = known[0] or data_class, known[1]
            ctx.not_configured.add(known[1])
        ctx.fetch_failed.add(data_class)
        ctx.keep(block, text)
        target = f"{fund} 的{state}" if fund else state
        return f"{prefix}⛔ {data_class} 取數失敗：{target}", True
    if text.startswith(SETTINGS_UNREADABLE_PREFIX):
        raw = text[len(SETTINGS_UNREADABLE_PREFIX):]
        known = _known(raw)
        if known:
            ctx.not_configured.add(known[1])
        ctx.fetch_failed.add(TABLE_NAMES["user_setting"])
        ctx.keep(block, text)
        return SETTINGS_UNREADABLE_PREFIX + (known[1] if known else STATE_SETTINGS_DEFAULT), True
    if SAVE_FAIL_PREFIX in text:
        prefix, rest = text.split(SAVE_FAIL_PREFIX, 1)
        key, sep, raw = rest.partition("：")
        if sep and key in KEY_NAMES:
            label = KEY_NAMES[key] + "："
        else:
            label, raw = "", rest
        known = _known(raw)
        if not known and not _looks_raw(raw):
            # 本頁自己寫的那一句（例「前一個鍵存檔失敗，本鍵未寫入」、「未存檔：…」）不是原文，照留（鍵名照換）。
            return f"{prefix}{SAVE_FAIL_PREFIX}{label}{raw}", False
        ctx.keep(block, text)
        return f"{prefix}{SAVE_FAIL_PREFIX}{label}{known[1] if known else STATE_SAVE_DEFAULT}", True
    return text, False


_ASCII_WORD = re.compile(r"[A-Za-z]{3,}")


def _looks_raw(message: str) -> bool:
    """存檔失敗那一句後半是不是上游原文：本頁自己的句子都是中文（帶「未存檔」或整句中文）；
    扣掉已知鍵名之後還有三個以上連續英文字母 → 當成原文（例「HTTP 503」「quota exceeded」「timeout」）。
    ⚠️ 判斷只決定要不要把它移到進階診斷；判錯的代價是一句中文原文留在一般畫面，或一句本頁的句子被換成
    「這一次沒有存進去」—— 兩者都不改任何判定，也不讓原文消失。"""
    if "未存檔" in message:
        return False
    return bool(_ASCII_WORD.search(_KEY_TOKEN.sub("", message)))


def _plain_text(text: str, block, ctx: _Context) -> str:
    code = (block or {}).get("code")
    set_page = ctx.page == "set"
    if set_page and code in _SET_KEEP_CODES:
        return text
    if not set_page:
        text, _ = _rewrite_failure(text, block, ctx)
        for message, _data_class, state in _KNOWN_MESSAGES:
            if message in text:
                ctx.keep(block, text)
                ctx.not_configured.add(state)
                text = text.replace(message, state)
    if not set_page or code in _SET_KEY_BLOCKS:
        for phrase in _EXACT_ORDER:   # 固定字樣（整段原字照對照表換；先長後短）
            if phrase in text:
                text = text.replace(phrase, EXACT_LABELS[phrase])
        text = _KEY_TOKEN.sub(lambda m: KEY_NAMES[m.group(1)], text)
        text = _FX_KEY.sub(_fx_name, text)
    if not set_page:
        text = _PROVIDER_METHOD.sub(lambda m: m.group(1), text)
    text = _BLOCK_CODE.sub(lambda m: BLOCK_NAMES.get(m.group(0), m.group(0)), text)
    text = _LAYER.sub(lambda m: LAYER_WORDS[m.group(1)], text)
    return text


def _is_input_field(node: dict) -> bool:
    return "name" in node and "label" in node and ("value_text" in node or "_value" in node)


def _walk(node, block, ctx: _Context, private: bool = False):
    """`private`：正在 `_` 開頭的鍵底下。那裡的字串與數值一律原樣（它們是程式拿去比對、當鍵用的值，
    例：`_columns` 的欄位鍵）；只有其中的 dict 仍逐鍵往下走（例：`_rows` 每一列裡給人看的字）。"""
    if isinstance(node, dict):
        if isinstance(node.get("code"), str) and node.get("code") in BLOCK_NAMES:
            block = node
        for key in list(node):
            value = node[key]
            if _protected(key):
                continue
            if isinstance(key, str) and key.startswith("_"):
                if isinstance(value, (dict, list, tuple)):
                    node[key] = _walk(value, block, ctx, private=True)
                continue
            if isinstance(value, str) and (key in _USER_DATA_KEYS or (private and key in _ROW_USER_DATA_KEYS)):
                continue   # 使用者的資料（字串本身），不換字；同名鍵底下是一格值節點（例 EXP-2 的 `_cells`）時照常往下走
            if key == "value_text" and _is_input_field(node):
                continue   # 輸入欄的當下值是使用者的資料，不換字
            node[key] = _walk(value, block, ctx)
        return node
    if isinstance(node, list):
        out = []
        for item in node:
            if not private and ctx.page == "hld" and item == PRINT_AS_IS_LINE:
                continue
            out.append(_walk(item, block, ctx, private))
        return out
    if isinstance(node, tuple):
        return tuple(_walk(item, block, ctx, private) for item in node)
    if isinstance(node, str) and not private:
        return _plain_text(node, block, ctx)
    return node


def plain_model(model: dict, *, page: str):
    """正式模式模型 → (一般畫面用的模型, 原始訊息清單, 狀態摘要)。輸入模型一個字都不改（先深拷貝）。

    原始訊息清單：`[{"where": "<塊代號> <塊名>"（頁首的字為頁名）, "text": <被換掉的原字串>}]`，同一筆只收一次。
    狀態摘要：`{"fetch_failed": [中文資料類…], "not_configured": [狀態句…], "raw_count": n}` —— 只是本頁已畫出來的字
    的整理，不是新的判定（給之後的資料狀態行用；本批不畫）。
    """
    if page not in PAGE_NAMES:
        raise ValueError(f"不認得的頁：{page}")
    ctx = _Context(page)
    display = _walk(copy.deepcopy(model), None, ctx)
    status = {
        "fetch_failed": sorted(ctx.fetch_failed),
        "not_configured": sorted(ctx.not_configured),
        "raw_count": len(ctx.raw),
    }
    return display, list(ctx.raw), status


def plain_text(text: str, *, page: str, code=None) -> str:
    """單一字串走 `plain_model` 同一套換字（`code`：這句話所在的塊；頁首的字不給）。給測試對照用。"""
    if page not in PAGE_NAMES:
        raise ValueError(f"不認得的頁：{page}")
    block = {"code": code, "title": BLOCK_NAMES.get(code, "")} if code else None
    return _plain_text(text, block, _Context(page))


def plain_error_line(raw_line: str, *, page: str):
    """整頁錯誤畫面（持倉體檢、資產配置）那一行 → (一般畫面那一行, 原始訊息清單)。原文只進清單（不吞）。"""
    ctx = _Context(page)
    ctx.keep(None, raw_line)
    known = _known(raw_line)
    state = known[1] if known else STATE_PAGE_DEFAULT
    data_class = (known[0] if known else None) or DATA_CLASS_DEFAULT
    return f"⛔ {data_class} 取數失敗：{state}", list(ctx.raw)


def section_text(text: str) -> str:
    """頁面自己寫的字（不在模型裡的那幾句）走同一套句中記號替換。"""
    return _LAYER.sub(lambda m: LAYER_WORDS[m.group(1)], _BLOCK_CODE.sub(
        lambda m: BLOCK_NAMES.get(m.group(0), m.group(0)), text))


# ───────────────────────── 跨頁的原始訊息（進階診斷） ─────────────────────────

# ⛔ 不得列入 `ui_v2/app_preview.py::_PAGE_STATE_TO_DROP`：它要跨頁留著，設定與診斷頁才讀得到（守衛測試）。
RAW_STATE = "_ui_v2_raw_diagnostics"


def record_raw(session_state, slug: str, entries, now) -> None:
    """記下這一頁這一次渲染的原始訊息（**整格覆寫**；沒有就寫空，免得舊的錯誤留著說謊）。

    `now`：記錄時間（`datetime` 或已格式化的字串），由呼叫端給 —— 本模組不讀時鐘。
    """
    store = dict(session_state.get(RAW_STATE) or {})
    stamp = now.isoformat(timespec="seconds") if hasattr(now, "isoformat") else str(now)
    store[slug] = {"at": stamp, "entries": [dict(entry) for entry in entries or ()]}
    session_state[RAW_STATE] = store


def clear_raw(session_state, slug: str) -> None:
    """拿掉這一頁記下的原始訊息（設定與診斷頁載入成功時拿掉自己上一次載入失敗的那一筆；Phase 3 P1-⑤）。
    沒有那一筆 → 一個字都不寫（不新增「已記錄的頁」）。"""
    store = session_state.get(RAW_STATE) or {}
    if slug in store:
        store = dict(store)
        del store[slug]
        session_state[RAW_STATE] = store


def raw_entries(session_state) -> list:
    """設定與診斷頁讀：`[(頁名, 記錄時間, 位置, 原文), ...]`，依五頁頁序；沒開過的頁不在裡面。"""
    store = session_state.get(RAW_STATE) or {}
    out = []
    for slug in PAGE_NAMES:
        if slug not in store:
            continue
        record = store[slug]
        for entry in record.get("entries") or ():
            out.append((PAGE_NAMES[slug], record.get("at", ""), entry.get("where", ""), entry.get("text", "")))
    return out


def recorded_pages(session_state) -> list:
    """本次瀏覽記錄過的頁（含沒有任何原始訊息的頁）：`[(頁名, 記錄時間), ...]`。"""
    store = session_state.get(RAW_STATE) or {}
    return [(PAGE_NAMES[slug], store[slug].get("at", "")) for slug in PAGE_NAMES if slug in store]
