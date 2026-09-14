"""ui/helpers/portfolio/allocation.py — 核心 / 衛星配置的唯一真相（純函式）。

**為什麼要這一支**：同一頁原本有 4 處各算各的核心/衛星，3 種定義、2 種目標值 ——

| 位置 | 分母 | 分類依據 | 目標 |
|---|---|---|---|
| 組合健康儀表 | 檔數 | `mk_df["MK_Class"]` | 寫死 80 |
| ① 配置總覽 KPI 卡 | 金額 | `is_core` | 無 |
| Hero 卡 + 甜甜圈 | 金額 | `is_core` | `portfolio_core_pct`（預設 75）|
| 保單分組 | 金額 | `policy_tier` → `is_core` | `portfolio_core_pct` |

3 檔核心佔 5 檔 = 60%，但核心若持有 90% 的錢 → 同一頁同時出現「核心 60%」與
「核心 90%」，目標值又 80 vs 75 打架，使用者無從判斷該不該再平衡。

**本模組定的規則**：
1. **分母一律金額**（Σ 投入本金 TWD）。檔數比例只能當附註，不得當「配置比例」。
2. **分類一律 `policy_tier` 優先**（使用者在 Google Sheet 明示的級別），
   缺才退 `is_core`（基金名稱關鍵字啟發式）。
3. **目標一律 `portfolio_core_pct`**（session，預設見 `ui/helpers/session.py`），
   不得在各處寫死。

⚠️ **第 5 個顯示點的處置**（2026-08-06 稽核點名 → 2026-08-07 user 拍板）：
Tab⑤ 下半頁的 💊 持倉健診會 embed `ui/tab_fund_grp_health._render_health_3tables`，
其中「🧭 核心 / 衛星」走的是**另一把尺** ——
`services/health/asset_class.classify_core_satellite`（MoneyDJ 基金類別 +  3-3-3，
三態含「待定」）。

那不是漏收，是**不同問題**：本模組回答「這筆錢的配置定位」（使用者自己在 Sheet
標的），那一區回答「這檔基金的資產屬性」（系統依類別 + 3-3-3 判的）。user 的裁決是
**不合併、但降級**：那一區保留（看得出手上的東西實際偏股還是偏債），但

1. **不再輸出任何配置行動建議**（原本的「核心不足 / 衛星過重」4 級燈號連同其
   建議核心區間常數已從 `services/health/asset_class.py` 移除）；
2. **分母對齊**：那一區也只計使用者實際填過的投入本金 —— 未填者由 caller 補的
   100 萬「模擬本金」只服務逐檔配息試算，以 weight=0 擋在配置比例外。

→ 全站「配置比例 + 該不該再平衡」只有本模組這一個來源。

📌 **2026-08-31 WP-G 狀態更新（上面整段一字未刪未改 —— 這是狀態變更，不是漏刪；
決策者 user：「各頁不重複渲染相同功能 …… ④ 健診改單行連結」）**：
④ 我的配置頁的 💊 持倉健診 **已不再 embed** `_render_health_3tables`，只留一行指路
→ ② 組合健診。**故本段所稱的「第 5 個顯示點」在 ④ 這一頁已不存在**；
「🧭 核心 / 衛星（另一把尺）」現在只出現在 ② 那一頁。
**2026-08-07 user 裁決的兩點（不輸出配置行動建議、分母對齊）仍然有效、一項未減** ——
它們約束的是那一區本身，跟它畫在哪一頁無關；本次改的只有「在幾頁畫」。
⚠️「④ 已無第二把尺」是單組結論，未經第二組驗證（`CLAUDE.md` §-2 規則 6）。

單位約定（CLAUDE.md §4.1）：`*_twd` 為 TWD 金額、`*_pct` 為 0~100 百分比
（**不是** 0~1 小數）、`n_*` 為檔數。
"""
from __future__ import annotations

from typing import Optional

CORE_TIER = "core"
SATELLITE_TIER = "satellite"

# 核心目標 % 的 session key 與其預設值 —— 預設值 SSOT 在
# `ui/helpers/session.INITIAL_SESSION_STATE`，這裡只做轉引用，禁止另寫常數。
CORE_TARGET_SESSION_KEY = "portfolio_core_pct"


def get_core_target_pct(session_state) -> float:
    """取核心目標 %（0~100）。session 沒設就退 `INITIAL_SESSION_STATE` 的預設。

    全站唯一取法；呼叫端不得再寫 `session_state.get(key, <數字>)`（數字會漂移）。
    """
    from ui.helpers.session import INITIAL_SESSION_STATE
    _default = INITIAL_SESSION_STATE[CORE_TARGET_SESSION_KEY]
    try:
        return float(session_state.get(CORE_TARGET_SESSION_KEY, _default))
    except (TypeError, ValueError):
        return float(_default)


def resolve_core_flag(fund: dict | None) -> bool:
    """核心 / 衛星判定：Sheet `policy_tier` 優先，缺則退既有 `is_core` 啟發式。

    與 Tab3 保單分組視圖原本的 `_is_core_in_policy` 同語意（該處已收斂為呼叫本函式），
    差別只在這裡是全頁共用、不再各處各寫一份。
    """
    _f = fund or {}
    _tier = str(_f.get("policy_tier") or "").strip().lower()
    if _tier == CORE_TIER:
        return True
    if _tier == SATELLITE_TIER:
        return False
    return bool(_f.get("is_core"))


def summarize_core_satellite(
    funds: list | None,
    *,
    target_pct: Optional[float] = None,
) -> dict:
    """金額加權的核心 / 衛星配置摘要。

    參數
    ----
    funds       : list[dict]，每筆需有 `invest_twd`（TWD 投入本金）；
                  級別走 `resolve_core_flag`（`policy_tier` → `is_core`）。
    target_pct  : 核心目標 %（0~100）。呼叫端請一律傳
                  `st.session_state.get("portfolio_core_pct", <session 預設>)`，
                  不要在呼叫點另寫常數。None = 不做偏差判定。

    回傳（缺資料時誠實回 None，不捏造 0；CLAUDE.md §1）
    ----
    total_twd / core_twd / sat_twd : float，Σ 投入本金（負值視為 0）
    core_pct / sat_pct             : float | None，金額佔比 %；total_twd = 0 → None
    n_funds / n_core / n_sat       : int，檔數（附註用，**不是**配置比例分母）
    n_tier_from_sheet              : int，級別由 Sheet `policy_tier` 明示的檔數
    n_missing_amount               : int，未填 / 填 0 本金的檔數（金額版看不到它們）
    is_amount_weighted             : bool，False = 全數沒填本金 → `core_pct` 不可信
    target_pct / diff_pct          : float | None，目標與「核心% − 目標%」
    """
    out: dict = {
        "total_twd": 0.0, "core_twd": 0.0, "sat_twd": 0.0,
        "core_pct": None, "sat_pct": None,
        "n_funds": 0, "n_core": 0, "n_sat": 0,
        "n_tier_from_sheet": 0, "n_missing_amount": 0,
        "is_amount_weighted": False,
        "target_pct": target_pct, "diff_pct": None,
    }
    if not funds:
        return out

    for _f in funds:
        _f = _f or {}
        try:
            _amt = float(_f.get("invest_twd", 0) or 0)
        except (TypeError, ValueError):
            _amt = 0.0
        _amt = max(_amt, 0.0)
        _is_core = resolve_core_flag(_f)
        out["n_funds"] += 1
        if _amt <= 0:
            out["n_missing_amount"] += 1
        if str(_f.get("policy_tier") or "").strip().lower() in (
                CORE_TIER, SATELLITE_TIER):
            out["n_tier_from_sheet"] += 1
        if _is_core:
            out["n_core"] += 1
            out["core_twd"] += _amt
        else:
            out["n_sat"] += 1
            out["sat_twd"] += _amt
        out["total_twd"] += _amt

    if out["total_twd"] > 0:
        out["is_amount_weighted"] = True
        out["core_pct"] = out["core_twd"] / out["total_twd"] * 100.0
        out["sat_pct"] = 100.0 - out["core_pct"]
        if target_pct is not None:
            out["diff_pct"] = out["core_pct"] - float(target_pct)
    return out


def format_core_satellite_caption(summary: dict) -> str:
    """一行說明：分母是什麼、級別哪來的、有幾檔沒填本金（原則 4「多做說明」）。

    ⚠️ **2026 文案更正（有意識的變更，不是漏刪）**：舊文案是

        ``f"{k}/{n} 檔級別來自 Google Sheet `policy_tier`，其餘 {n-k} 檔以基金名稱關鍵字推定"``

    **它在三種情況下對客戶說了假話**（三種都在 `origin/main` @ `9cbf0377` 實測過，
    與 Q8 批次一 #842 是否合併無關）：

    1. **把 Sheet 明示的說成系統猜的。** ``n_tier_from_sheet`` 只數 ``policy_tier``
       這個 **v1** 欄位；而 **v2** 讀取路徑（``ui/helpers/cloud_io.py::_load_all_from_sheet_v2``）
       把客戶在 Sheet ``tier`` 欄親手填的值存進 ``is_core``、**不寫** ``policy_tier``
       ⇒ 那一檔被歸進「其餘」，文案宣稱它「以基金名稱關鍵字推定」——
       但它根本沒被猜過，是客戶自己填的。
    2. **把「還沒決定」說成「猜出來的」。** ``is_core`` 缺鍵 / 為 ``None`` 時
       ``resolve_core_flag`` 回 ``False``，那筆金額**靜靜併進衛星**；
       文案同樣說它是名稱推定的結果。
    3. **「其餘 0 檔以…推定」**：全部級別都明示時，舊文案仍會描述一個不存在的群組。

    **新文案的取捨**：`summary` 裡**沒有**任何欄位能區分「`is_core` 是從 Sheet
    讀來的」還是「系統推定的」—— 要區分就得在 :func:`summarize_core_satellite`
    新增欄位，那會動到本模組的回傳契約（超出本批授權：本批**只改文案**，
    不改任何比例數字）。故新文案**不宣稱來源機制**，只說「系統分不出」。

    **並且補上舊文案完全沒講的那一句**：**未設定一律算進衛星。**
    那是 :func:`summarize_core_satellite` 的既有行為（二態，本批不改），
    但畫面上完全看不出來 —— 不講，客戶會把「衛星 X%」讀成「我有 X% 的衛星部位」，
    實際上裡面混著「我還沒決定的部位」（`CLAUDE.md §1`：寧可少講，不可講錯）。

    ⚠️ **2026 第二輪回修（有意識的更正，不是漏刪）—— 第一版的替代文案自己也有問題**

    第一版把 `k` 那半句寫成 ``"{k}/{n} 檔級別由 Sheet `policy_tier` 欄明示"``。
    **對 v2 客戶而言那是假的**：``repositories/policy/v2.py`` 寫進客戶分頁的表頭是
    ``ZH_HEADERS_V2``，``tier`` 那一欄在客戶眼裡叫 **「級別」**；
    而 ``policy_tier`` 這個字只出現在 ``docs/POLICY_SHEETS_SETUP.md`` 的 **v1** 章節。
    ⇒ 一個在「級別」欄親手填了 core 的客戶，會看到「**0/n 檔明示**」——
    文案等於說他沒填。**罪名換了（舊文案說「這是猜的」，第一版說「你沒填」），
    被否定的事實是同一個。**

    現在 `k` 那半句只講**可觀測的事實**（「帶有 ``policy_tier`` 欄的級別值」），
    **不再把 `k` 翻譯成「客戶明示的檔數」** —— 那個翻譯正是上面那句假話的來源。

    ⛔ **刻意不寫「v2 的「級別」欄不會寫進 ``policy_tier``」這種話**（草稿寫過，已撤）：
    **它不是無條件為真。** ``repositories/policy/v2.py::_records_to_policy_df``
    有一份中文表頭映射 ``{"級別": "policy_tier"}``，走
    ``load_policy_worksheet`` / ``load_all_policy_worksheets`` 讀回的混合分頁
    **確實會**把「級別」寫進 ``policy_tier``；只有
    ``ui.helpers.cloud_io._load_all_from_sheet_v2`` 那條路徑不會（它只寫 ``is_core``）。
    **同一個欄位在不同讀取路徑下去處不同 —— 所以文案不得對來源下任何斷言。**

    **本輪的驗證方式（不是「我看過了」）**：四條真實讀取路徑各自造一檔（v1 `policy_tier`／
    v2「級別」／名稱啟發／「➕ 加入組合」留白），兩兩組合共 49 組（涵蓋派工單點名的 36 組），
    逐組比對文案的每一項原子宣稱與該檔的真實來源。
    **修復前 4 組通過、45 組不通過；修復後 49 組全數通過。**
    ⚠️ **該檢查器的已知盲點**：它以「句讀分段 + 不確定性標記」判斷一句話是不是斷言，
    **一個掛著「可能」卻仍然誤導的句子會被放行**（已用突變 M-E 實測確認）。
    """
    if not summary or not summary.get("n_funds"):
        return "尚無持倉可統計核心 / 衛星比例。"
    _n = summary["n_funds"]
    _from_sheet = summary.get("n_tier_from_sheet", 0)
    _other = _n - _from_sheet
    _src = f"{_from_sheet}/{_n} 檔帶有 Sheet `policy_tier` 欄的級別值"
    if _other:
        _src += (f"；其餘 {_other} 檔沒有這個值，"
                 f"**系統分不出它們的級別是誰決定的** —— "
                 f"可能是你在 Sheet 上設定過、"
                 f"可能是系統依基金名稱代為判定，也可能**未設定**；"
                 f"規則上**未設定一律算進衛星**")
    if not summary.get("is_amount_weighted"):
        return (f"⚠️ {_n} 檔皆未填投入本金 → 無法算金額比例（{_src}）。"
                "請在 Sheet 的本金欄，或 T7 帳本的"
                "「✏️ 編輯持倉（手動微調 — 從 CHUBB 對帳單抄入精確值）」"
                "填入本金後再看此比例。")
    _miss = summary.get("n_missing_amount", 0)
    _tail = (f"；⚠️ {_miss} 檔未填本金，未計入分母" if _miss else "")
    return (f"分母 = Σ 投入本金（**金額**加權，非檔數）；"
            f"{_src}{_tail}。")
