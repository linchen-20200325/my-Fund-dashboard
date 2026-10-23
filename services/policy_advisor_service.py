"""services/policy_advisor_service.py — 保單視圖純規則建議引擎
（v11.0 C-18 從 policy_advisor.py 搬入）

依據三個訊號（σ 位階、配息覆蓋率、60MA 趨勢）配合可選 VIX，短路匹配 10 條規則，
組合出一句中文操作建議。完全純函數、可獨立單測；唯一的 import 是 L0 常數
（`shared/*` 純 literal、零 I/O），無 HTTP / 無 streamlit / 無 L1 repository。
（2026-10-23 DG-3 C 後：`advise_fund` 另在函式內 lazy import L2 純函式
`services.precision_service.hwm_position_from_rank`，只在 sigma_info 未帶 SSOT label 時取三態用字；零 I/O。）

設計原則（與專案 §2 精準讀寫 §4 鋼鐵自省一致）：
- 不打 HTTP、不讀 streamlit 狀態、不抓即時資料
- 輸入皆為已算好的中間結果（避免重複計算）
- 規則由上往下短路匹配，確保決定性與可追溯

v11.0 分層歸位：本檔屬於 Service Layer，純規則決策（零 I/O；依賴僅 L0 常數）。
向後相容：根目錄 policy_advisor.py 保留 shim re-export，既有 caller 零修改。

⚠️ **legacy 行動語意,待 BL-0428 重新裁示**(2026-10-23 裁示 2C ＋ Stop Gate「選項 1」,BL-0426):
本模組讀到的 σ rank 一律來自唯一 SSOT `services/fund_position.compute_fund_position`
(配息還原序列、fail closed —— 無法判定時 σ rank 缺值,走既有的「資料不足 / unknown」分支,
不補 0、不當中性)。`advise_fund` / `recommend_policy` 的 `sigma_info` 由呼叫端傳入 SSOT 輸出(unavailable 帶 `error`、`sigma_rank=None`)。本模組的買賣 / 加碼 / 換股規則、門檻、決策結構與文字**一字未改**;
σ 位置本身只是「相對自身近一年高點的位置證據」,不是交易建議。

⛔ **2026-10-23 客戶裁示 BL-0428 DG-3 C ＋ DG-1 A(`DEC-2026-10-23-11`)**:
- DG-3 C:**退休由 HWM σ 直接產生的行動文字** —— `advise_fund` 規則 1~9(σ ≤ −2.0 大買區／
  加碼參考區／汰弱換強、−1.0 觀察區留意加碼點／勿接刀、±0.5 停利檢視／健康持有、
  創新高停利、標準持有區)與 `recommend_policy` P3(σ ≤ −2.0 深度超跌「可分批加碼」)全部停用;
  σ 位置只作中性證據顯示(三態 ＋ ⬜)。**沒有把 −0.5／−1.5 升格為行動門檻。**
  其餘非 σ 規則(核心比例 P1/P2、吃本金 P4、級別未設定)不變。
- DG-1 A:位置 ⬜ 不得被讀成中性／安全 —— `recommend_policy` 有任一檔 ⬜ 時不給綠燈
  「配置健康」,改走本模組既有的 `INSUFFICIENT_DATA`(灰色「資料不足，暫無法判斷」),並列出 ⬜ 檔數。
退休的規則代碼常數保留(舊 import 不炸),但本模組不再產生它們。
"""
from __future__ import annotations

from typing import Iterable, Optional

# 唯一的外部依賴：L0 常數（純 literal，零 I/O，不破壞「可獨立單測」）。
# 規則 1 的 VIX 門檻語意 = **全站 panic 線**（SPEC §16.1 C2 系列：panic 全站統一），
# 與 risk_radar 紅燈 / beginner_view 恐慌燈 / macro_validation crisis 同一條線，
# 因此收 `shared.macro_buckets` 的紅界而非黃界（黃界 = 警戒，語意不同，勿誤收）。
from shared.macro_buckets import _VIX_RED as _MB_VIX_RED


# 規則 1「跌了就買」的恐慌門檻（§3.3 不 inline magic number）。
# 對外公開：`ui/tab3_portfolio.py` 的缺值提示要把這個數字講給使用者聽，
# 避免 UI 端另外寫死一份而漂移。
VIX_PANIC_THRESHOLD: float = _MB_VIX_RED


# 規則代碼（測試斷言用，外部勿改字串）
INSUFFICIENT_DATA      = "INSUFFICIENT_DATA"
DEEP_DROP_VIX_BUY      = "DEEP_DROP_VIX_BUY"
DEEP_DROP_RED_SWITCH   = "DEEP_DROP_RED_SWITCH"
DEEP_DROP_NEUTRAL      = "DEEP_DROP_NEUTRAL"
MID_DROP_MA_UP         = "MID_DROP_MA_UP"
MID_DROP_MA_DOWN       = "MID_DROP_MA_DOWN"
NEAR_HWM_RED_TP_CHECK  = "NEAR_HWM_RED_TP_CHECK"
NEAR_HWM_GREEN_HOLD    = "NEAR_HWM_GREEN_HOLD"
ABOVE_HWM_TAKE_PROFIT  = "ABOVE_HWM_TAKE_PROFIT"
DEFAULT_HOLD           = "DEFAULT_HOLD"
# ↑ DEEP_DROP_* / MID_DROP_* / NEAR_HWM_* / ABOVE_HWM_* / DEFAULT_HOLD:2026-10-23 DG-3 C 退休
#   (σ 驅動的行動文字),常數保留供舊 import,本模組不再產生。
# σ 可判定時只回中性位置證據(無行動語意)—— DG-3 C 之後 advise_fund 唯一的非 ⬜ 輸出。
POSITION_EVIDENCE_ONLY = "POSITION_EVIDENCE_ONLY"

# P3：保單級配置建議規則代碼
POLICY_EMPTY                 = "POLICY_EMPTY"
POLICY_CORE_OVER             = "POLICY_CORE_OVER"          # 核心過重
POLICY_CORE_UNDER            = "POLICY_CORE_UNDER"         # 核心過輕
POLICY_RISK_HEAVY_DROP       = "POLICY_RISK_HEAVY_DROP"    # 多檔深度超跌(2026-10-23 DG-3 C 退休,不再產生)
POLICY_RISK_HEAVY_RED        = "POLICY_RISK_HEAVY_RED"     # 多檔吃本金
POLICY_HEALTHY               = "POLICY_HEALTHY"            # 配置健康
POLICY_TIER_UNSET            = "POLICY_TIER_UNSET"         # 無已設定級別且已填本金的基金 → 未判斷配置（2026-10-10）


def _position_unknown(fund: dict) -> bool:
    """保單級:這檔的基金位置是否 ⬜(無法判定)。

    只看**有帶 `sigma_info` 鍵**的條目(production 呼叫端 `ui/tab3_portfolio.py` 一律帶,
    `_hwm_sigma_info_for` 回 None = NAV 不足 30 點、dict 帶 error / sigma_rank 缺 = SSOT ⬜)。
    沒帶這個鍵 = 呼叫端沒有提供位置資訊,本函式不臆測(舊 caller 行為不變)。
    """
    if "sigma_info" not in fund:
        return False
    _sig = fund.get("sigma_info")
    if not isinstance(_sig, dict) or "error" in _sig:
        return True
    _r = _sig.get("sigma_rank")
    return isinstance(_r, bool) or not isinstance(_r, (int, float))


def _coverage_str(div: dict | None) -> str:
    cov = (div or {}).get("coverage")
    return f"{cov:.2f}" if isinstance(cov, (int, float)) else "N/A"


def advise_fund(
    sigma_info: Optional[dict],
    dividend_info: Optional[dict],
    ma60_trend: Optional[str] = None,
    vix: Optional[float] = None,
) -> dict:
    """
    回傳 {text, code, color}

    2026-10-23 DG-3 C 起:⬜ → `INSUFFICIENT_DATA`(灰);σ 可判定 → `POSITION_EVIDENCE_ONLY`
    (灰,只陳述 SSOT 位置三態,不給任何買賣／加碼／停利文字)。dividend_info / ma60_trend / vix
    保留參數(呼叫端相容),本函式目前不使用。

    sigma_info 預期欄位：sigma_rank (float)，或 error (str)
    dividend_info 預期欄位：alert_level ("red"|"yellow"|"green"|"grey")、coverage (float|None)
    ma60_trend："up" | "down" | None
    vix：當前 VIX 值，None 視為未提供
    """
    if not sigma_info or "error" in sigma_info or sigma_info.get("sigma_rank") is None:
        return {
            "text": "⏳ 資料不足，暫無法判斷（NAV 序列 < 30 點或無 σ 位階）",
            "code": INSUFFICIENT_DATA,
            "color": "grey",
        }

    # ── 2026-10-23 DG-3 C:σ 不再產生任何行動文字(原規則 1~9 退休)────────────
    # ~~規則 1 σ ≤ −2.0 + VIX 恐慌 → 跌了就買／規則 2 → 汰弱換強／規則 3 → 加碼參考區~~
    # ~~規則 4/5 −2.0 < σ ≤ −1.0 → 留意 -2σ 加碼點／勿接刀~~
    # ~~規則 6/7 −0.5 < σ ≤ 0.5 → 停利檢視／健康持有~~　~~規則 8 σ > 0.5 → 創新高停利~~
    # ~~規則 9 其他 → 標準持有區~~
    # 位置只作中性證據(SSOT 三態用字;切點為研究候選、未校準)。dividend_info / ma60_trend / vix
    # 原本只在與 σ 組合時使用 —— 單獨拿它們產生建議等於新行動規則,本批不做。
    _label = sigma_info.get("label")
    if not _label:
        from services.precision_service import hwm_position_from_rank
        _label = hwm_position_from_rank(sigma_info.get("sigma_rank"))[1]
    if not _label:
        return {
            "text": "⏳ 資料不足，暫無法判斷（NAV 序列 < 30 點或無 σ 位階）",
            "code": INSUFFICIENT_DATA,
            "color": "grey",
        }
    return {
        "text": f"位置：{_label}（相對自身近一年高點的位置證據，不是買賣建議）",
        "code": POSITION_EVIDENCE_ONLY,
        "color": "grey",
    }


# ══════════════════════════════════════════════════════════════════════
# P3：保單級配置建議（純函式，無 streamlit / 無 I/O）
# ══════════════════════════════════════════════════════════════════════
def recommend_policy(
    funds_in_policy: Iterable[dict],
    target_core_pct: float = 75.0,
    risk_count_threshold: int = 2,
) -> dict:
    """
    輸入單一保單下的 fund 條目集合，依下列訊號短路匹配 5 條規則：
    - core_pct 偏離 target 超過 ±10%（核心過重 / 過輕）
    - ~~多檔深度超跌（sigma_info.sigma_rank ≤ -2.0）~~(2026-10-23 DG-3 C 退休)
    - 多檔吃本金（dividend_info.alert_level == "red"）

    每個 fund 預期欄位：
      invest_twd (int|float)
      is_core (True/False/None) ← 2026-10-10 起為**三態**：True＝明確核心、False＝明確衛星、
                                None／缺鍵＝級別未設定。~~(bool) ← Tab3 已用既有 _is_core_fund heuristic 填好~~
                                （系統已不以基金名稱猜級別）。未設定不進核心／衛星比例的分子與分母；
                                P3／P4（深跌、吃本金）照舊含未設定。
      sigma_info (dict?)     ← optional；~~若 None / 缺 sigma_rank 視為不計~~
                                2026-10-23 DG-1 A:**有帶這個鍵**且 None / error / 缺 sigma_rank
                                → 位置 ⬜,不給綠燈「配置健康」並列出 ⬜ 檔數;不帶這個鍵 → 不臆測
      dividend_info (dict?)  ← optional；若 None / 無 alert_level 視為不計

    回傳: {text, code, color}
    """
    funds = [f for f in (funds_in_policy or []) if isinstance(f, dict)]
    total_amt = sum(float(f.get("invest_twd", 0) or 0) for f in funds)

    if total_amt <= 0:
        return {
            "text": "保單內無有效投入金額；先在 T7「📝 編輯初始持倉」填入單位數。",
            "code": POLICY_EMPTY,
            "color": "grey",
        }

    # 2026-10-10（客戶裁示：級別三態、方案 B）：~~`core_amt / total_amt`（未設定算非核心、進分母）~~
    # → 分母只算已設定級別（is_core 嚴格 True/False）的本金。全部已設定時 classified_amt 與
    # total_amt 以同序加總，結果逐位元相同。分母為 0 → 不算比例、不給 P1/P2/P5。
    core_amt = sum(float(f.get("invest_twd", 0) or 0) for f in funds if f.get("is_core") is True)
    classified_amt = sum(float(f.get("invest_twd", 0) or 0) for f in funds
                         if f.get("is_core") is True or f.get("is_core") is False)
    if classified_amt > 0:
        core_pct = round(core_amt / classified_amt * 100.0, 1)
        diff = round(core_pct - float(target_core_pct), 1)
    else:
        core_pct = None
        diff = None

    # DG-1 A(2026-10-23):位置 ⬜ 檔數(只揭露,不參與 P1/P2/P4 判定)。
    unknown_n = sum(1 for _f in funds if _position_unknown(_f))
    _unk_sfx = f"；另 {unknown_n} 檔基金位置無法判定（資料不足）" if unknown_n else ""

    # ── 規則 P1：核心過重（>target + 10%） ────────────────────────────
    if diff is not None and diff > 10.0:
        return {
            "text": (
                f"核心配置 {core_pct}% 高於目標 {target_core_pct:.0f}%（+{diff:.1f}%）"
                f" → 可釋出至衛星追求成長，或留意核心過度集中{_unk_sfx}"
            ),
            "code": POLICY_CORE_OVER,
            "color": "yellow",
        }

    # ── 規則 P2：核心過輕（<target - 10%） ────────────────────────────
    if diff is not None and diff < -10.0:
        return {
            "text": (
                f"核心配置 {core_pct}% 低於目標 {target_core_pct:.0f}%（{diff:+.1f}%）"
                f" → 評估從衛星轉核心鞏固防禦{_unk_sfx}"
            ),
            "code": POLICY_CORE_UNDER,
            "color": "orange",
        }

    # ── ~~規則 P3：多檔深度超跌（sigma_rank ≤ -2.0）→「可分批加碼但避免單押」~~ ──────────
    # 2026-10-23 客戶裁示 BL-0428 DG-3 C:退休(σ 驅動的加碼文字;門檻未校準)。
    # σ 只用來數「位置無法判定」的檔數(DG-1 A,見上方 unknown_n),不再產生任何行動。

    # ── 規則 P4：多檔吃本金（dividend alert == red） ──────────────────
    red_n = 0
    for _f in funds:
        _div = (_f.get("dividend_info") or {})
        if _div.get("alert_level") == "red":
            red_n += 1
    if red_n >= risk_count_threshold:
        return {
            "text": (
                f"{red_n} 檔基金吃本金（配息 > 含息報酬）→ 檢視配息來源、評估汰弱換強，"
                f"避免本金侵蝕{_unk_sfx}"
            ),
            "code": POLICY_RISK_HEAVY_RED,
            "color": "red",
        }

    # ── 未設定（無已設定級別且已填本金）：只陳述未判斷，不給動作、不亮綠燈 ──
    if core_pct is None:
        return {
            "text": "此保單沒有已設定級別且已填本金的基金，未判斷核心／衛星配置" + _unk_sfx,
            "code": POLICY_TIER_UNSET,
            "color": "grey",
        }

    # ── DG-1 A(2026-10-23):有任一檔位置 ⬜ → 不給綠燈「配置健康」────────────
    # 沿用本模組既有的 INSUFFICIENT_DATA(灰色「資料不足，暫無法判斷」),列出 ⬜ 檔數;
    # 不新增狀態、不新增顏色。核心／衛星比例照實陳述(那是已知事實)。
    if unknown_n:
        return {
            "text": (
                f"⏳ 資料不足，暫無法判斷整體配置：{unknown_n} 檔基金位置無法判定"
                f"（核心 {core_pct}% / 衛星 {100.0 - core_pct:.1f}%，偏差 {diff:+.1f}%）"
            ),
            "code": INSUFFICIENT_DATA,
            "color": "grey",
        }

    # ── 規則 P5：其餘 → 健康 ─────────────────────────────────────────
    return {
        "text": (
            f"核心 {core_pct}% / 衛星 {100.0 - core_pct:.1f}%（偏差 {diff:+.1f}%）"
            f" → 配置健康，持續觀察 60MA 與配息覆蓋率"
        ),
        "code": POLICY_HEALTHY,
        "color": "green",
    }
