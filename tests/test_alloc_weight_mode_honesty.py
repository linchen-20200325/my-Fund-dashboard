# -*- coding: utf-8 -*-
"""🧭 核心/衛星配置檢查 —— caption「加權方式」誠實性鎖(§1 Fail Loud, Never Fake)。

背景(2026-08-04 稽核)
=====================
`services/health/asset_class.summarize_core_satellite_allocation()` 本身是正確的
金額加權;但**健診 Tab 只有一個本金欄位**(`ui/tab_fund_grp_health.py` 的
`principal_twd`),經 `_run_batch_health` → `services/fund_row.process_one_fund`
→ 每列 `_principal_twd` 完全相同 → 傳進來的 weight 全等 → **實際是等權**
(比例 ≡ 檔數佔比)。程式碼註解自己都寫「健檢 Tab 全檔本金 100 萬 = 等權」,
但 19 行後的 caption 對 user 說「依各檔投入本金加權」—— **陳述與行為不符**。

實害:持有 90 萬核心 + 10 萬衛星(9:1)在健診 Tab 顯示「核心 50% / 衛星 50%」,
且總計顯示 2,000,000 TWD,配置評估燈號完全失真。

修法(本檔守的不變量)
====================
1. L2 依**實際權重**推斷 `weight_mode`(不由 caller 自稱)—— 因為 `_render_health_3tables`
   被健診 Tab 與 Tab3 共用,且 Tab3 在 user 全未填 invest_twd 時也會退成等權,
   caller 自稱參數擋不住這個案例。
2. L3 caption 一律讀 `weight_mode` 措辭,**全等權時不得出現「依各檔投入本金加權」**。
"""
from __future__ import annotations

from pathlib import Path

from services.health.asset_class import (
    infer_weight_mode,
    summarize_core_satellite_allocation,
)

_ROOT = Path(__file__).resolve().parents[1]
_GRP = _ROOT / "ui" / "tab_fund_grp_health.py"

# 健診 Tab 的實況:單一本金 broadcast 給全部基金
_EQUAL_ITEMS = [
    {"label": "🟦 核心", "weight": 1_000_000},
    {"label": "🟠 衛星", "weight": 1_000_000},
    {"label": "🟠 衛星", "weight": 1_000_000},
]
# Tab3 實況:各檔真實 invest_twd(9:1)
_AMOUNT_ITEMS = [
    {"label": "🟦 核心", "weight": 900_000},
    {"label": "🟠 衛星", "weight": 100_000},
]


# ── L2 infer_weight_mode 純函式 ──────────────────────────────
def test_infer_none_when_empty():
    assert infer_weight_mode([]) == "none"


def test_infer_single_when_one_weight():
    assert infer_weight_mode([1_000_000.0]) == "single"


def test_infer_equal_when_all_same():
    assert infer_weight_mode([1_000_000.0] * 8) == "equal"


def test_infer_amount_when_any_differs():
    assert infer_weight_mode([900_000.0, 100_000.0]) == "amount"


def test_infer_equal_tolerates_float_noise():
    """§4.3 浮點比較用容差,不用 `==` —— 1e-9 級噪音仍算等權。"""
    assert infer_weight_mode([1_000_000.0, 1_000_000.0 + 1e-7]) == "equal"


def test_infer_amount_for_materially_different_weights():
    """真差異(1 元)不可被容差吃掉 → 仍是金額加權。"""
    assert infer_weight_mode([1_000_000.0, 1_000_001.0]) == "amount"


# ── L2 summarize 回傳 weight_mode ────────────────────────────
def test_summary_flags_equal_mode():
    r = summarize_core_satellite_allocation(_EQUAL_ITEMS)
    assert r["weight_mode"] == "equal"
    # 等權 ⟺ 比例 = 檔數佔比(1/3 核心)
    assert round(r["core_pct"]) == 33


def test_summary_flags_amount_mode():
    r = summarize_core_satellite_allocation(_AMOUNT_ITEMS)
    assert r["weight_mode"] == "amount"
    assert r["core_pct"] == 90.0


def test_summary_flags_single_mode():
    r = summarize_core_satellite_allocation([{"label": "核心", "weight": 1_000_000}])
    assert r["weight_mode"] == "single"


def test_summary_flags_none_mode_when_no_valid_weight():
    assert summarize_core_satellite_allocation([])["weight_mode"] == "none"
    assert summarize_core_satellite_allocation(
        [{"label": "核心", "weight": 0}, {"label": "衛星", "weight": "x"}]
    )["weight_mode"] == "none"


def test_skipped_weights_do_not_affect_mode():
    """weight ≤ 0 / 非數已在分母被略過 → 也不得參與加權方式推斷。"""
    r = summarize_core_satellite_allocation([
        {"label": "核心", "weight": 500_000},
        {"label": "衛星", "weight": 500_000},
        {"label": "衛星", "weight": 0},        # 略過
        {"label": "待定", "weight": "x"},      # 略過
    ])
    assert r["weight_mode"] == "equal"


def test_existing_amount_weighted_contract_unchanged():
    """回歸:既有 test_asset_class_core_satellite.py 的金額加權契約不得被破壞。

    2026-08-07:`status` 已由「配置評價燈」改為「分類涵蓋度」(本表降為純資訊),
    故這裡改斷言 COVERAGE_OK;金額加權本身的契約(80/20 + amount)不變。
    """
    from services.health.asset_class import COVERAGE_OK
    r = summarize_core_satellite_allocation([
        {"label": "🟦 核心", "weight": 800_000},
        {"label": "🟠 衛星", "weight": 200_000},
    ])
    assert r["core_pct"] == 80.0 and r["satellite_pct"] == 20.0
    assert r["status"] == COVERAGE_OK and r["weight_mode"] == "amount"


# ── L3 caption 措辭誠實性 ────────────────────────────────────
def test_caption_never_claims_amount_weighting_when_equal():
    """核心鎖:全檔權重相同時,caption 不得宣稱「依各檔投入本金加權」。"""
    from ui.tab_fund_grp_health import _weight_basis_note
    note = _weight_basis_note(summarize_core_satellite_allocation(_EQUAL_ITEMS))
    assert "依各檔投入本金加權" not in note
    assert "檔數佔比" in note, "等權時應明講比例 = 檔數佔比"


def test_caption_claims_amount_weighting_only_when_amounts_differ():
    from ui.tab_fund_grp_health import _weight_basis_note
    note = _weight_basis_note(summarize_core_satellite_allocation(_AMOUNT_ITEMS))
    assert "依各檔投入本金加權" in note
    assert "1,000,000 TWD" in note   # 總計 90 萬 + 10 萬


def test_caption_single_fund_is_neutral():
    from ui.tab_fund_grp_health import _weight_basis_note
    note = _weight_basis_note(
        summarize_core_satellite_allocation([{"label": "核心", "weight": 1_000_000}]))
    assert "依各檔投入本金加權" not in note and "檔數佔比" not in note


def test_caption_falls_back_to_none_wording_on_missing_mode():
    """缺 weight_mode(舊 dict / 例外路徑)→ 不猜、不宣稱金額加權。"""
    from ui.tab_fund_grp_health import _weight_basis_note
    note = _weight_basis_note({"total_weight": 123.0})
    assert "依各檔投入本金加權" not in note


def test_caption_equal_wording_reports_per_fund_amount():
    from ui.tab_fund_grp_health import _weight_basis_note
    note = _weight_basis_note(summarize_core_satellite_allocation(_EQUAL_ITEMS))
    assert "1,000,000 TWD × 3 檔" in note


# ── source-text 鎖(對齊 tests/test_grp_health_bugfixes.py 風格)──
def test_caption_no_hardcoded_weighting_claim_in_source():
    src = _GRP.read_text(encoding="utf-8")
    # 2026-08-04 QA 條件 4:call site 加了 source_tab 參數 → 鎖新的精確呼叫形式
    #（比舊的 `_weight_basis_note(_csa)` 更強：舊字面同時命中註解，鎖不住真 call site）。
    assert "_weight_basis_note(_csa, source_tab)" in src, \
        "caption 應改走 weight_mode 措辭 helper 並帶 source_tab"
    assert "（依各檔投入本金加權" not in src, (
        "caption 不得再寫死「依各檔投入本金加權」—— 健診 Tab 實際是等權(§1)"
    )


# ══════════════════════════════════════════════════════════════
# 2026-08-04 QA 條件 4 — 「修掉一個謊，種了另一個」補正
#
# 舊 equal 措辭尾巴接了：
#   「非依實際金額加權；要看真實金額配置，請到「組合配置」Tab 逐檔填投入金額」
# 情境：user 在 Tab3 **真的逐檔填了**，但每檔恰好 100 萬（平均配置是常見策略）。
#   (1)「非依實際金額加權」→ 假陳述：它就是金額加權，只是金額相同（§1 反向違規）。
#   (2)「請到組合配置 Tab 填」→ 對已填完的 user 下錯誤指示；且 `_render_health_3tables`
#       被兩個 Tab 共用，在 Tab3 渲染時等於叫 user 去他當下所在的地方。
# 修法：equal 只留數學上恆真的那半；「去填金額」導引改成僅健診 Tab 分支（source_tab）。
# ══════════════════════════════════════════════════════════════
def test_equal_caption_drops_false_causal_claim():
    """核心鎖:等權措辭不得宣稱「非依實際金額加權」（金額相同時它可能就是金額加權）。

    修正前會紅（舊措辭字面含這句）。
    """
    from ui.tab_fund_grp_health import _weight_basis_note
    csa = summarize_core_satellite_allocation(_EQUAL_ITEMS)
    for _st in (None, "health", "portfolio"):
        note = _weight_basis_note(csa, _st)
        assert "非依實際金額加權" not in note, f"source_tab={_st} 仍留假陳述"
        # 數學上恆真的那半必須留著
        assert "檔數佔比" in note and "1,000,000 TWD × 3 檔" in note


def test_equal_caption_hint_only_in_health_tab():
    """「請到組合配置 Tab 逐檔填」只在健診 Tab 印。修正前會紅（兩個 caller 都印）。"""
    from ui.tab_fund_grp_health import _weight_basis_note
    csa = summarize_core_satellite_allocation(_EQUAL_ITEMS)
    assert "組合配置" in _weight_basis_note(csa, "health"), "健診 Tab 應保留導引"
    assert "組合配置" not in _weight_basis_note(csa), "Tab3 embed（預設）不得下錯誤指示"
    assert "組合配置" not in _weight_basis_note(csa, "portfolio")


def test_non_equal_modes_never_get_the_hint():
    """amount / single / none 措辭不受 source_tab 影響（導引只綁 equal）。"""
    from ui.tab_fund_grp_health import _weight_basis_note
    for _items in (_AMOUNT_ITEMS, [{"label": "核心", "weight": 1_000_000}], []):
        csa = summarize_core_satellite_allocation(_items)
        assert _weight_basis_note(csa, "health") == _weight_basis_note(csa)


def test_weight_basis_note_default_arg_keeps_old_callers_safe():
    """`source_tab` 有預設值 → 未在所有權內的 ui/tab3_portfolio.py caller 零改動可跑。"""
    import inspect
    from ui.tab_fund_grp_health import _render_health_3tables, _weight_basis_note
    for _fn in (_weight_basis_note, _render_health_3tables):
        _p = inspect.signature(_fn).parameters["source_tab"]
        assert _p.default is None, f"{_fn.__name__}.source_tab 必須有 None 預設值"


def test_health_tab_caller_declares_source_tab_in_source():
    """source-text 鎖:健診 Tab caller 必須自報 source_tab="health"。修正前會紅。"""
    src = _GRP.read_text(encoding="utf-8")
    assert 'source_tab="health"' in src, "健診 Tab 呼叫端應宣告 source_tab"
    assert "非依實際金額加權" not in src, "假因果宣稱不得殘留在措辭 SSOT"
