"""🎯「選基金」低基期篩選 —— **與健診大表「基期」欄同一把尺**（HWM σ rank）。

2026-08-07 user 拍板前的狀況（本檔守的就是「不准再退回去」）
==========================================================
screener 與大表各有一套低基期演算法：

| | screener（舊） | 大表「基期」欄 |
|---|---|---|
| 演算法 | `高點 − N×NAV 標準差` | `(現價 − HWM) / σ_abs` |
| 符號 | 深度取**正數**（「低幾σ」） | **負數** σ rank |
| 門檻 | 使用者選 1 或 2σ | 固定 `ROTATION_BUY_SIGMA` |
| 回看期 | 使用者選 1/2/3 年 | 固定 252 交易日 |

同一檔可能在 screener 標「✅ 低基期」、在大表標「⚪ 中性」——
使用者照 screener 買進，回頭看大表發現系統自己說不是低基期。
`test_volatile_fund_near_high_is_not_low_base` 就是那個分歧的具體實例：
高波動、現價離高點 20% 的基金，舊演算法判「低基期（低 2σ）」，
σ rank 只有 −0.11σ（因為它自己的波動就有那麼大）→ 其實是**高基期**。

本檔守的不變量
==============
1. σ rank 一律**負數**（§4.1 sign convention），愈負愈低基期；
2. 門檻與回看窗全部走 SSOT（`shared/signal_thresholds` + `calc_hwm_sigma_levels`
   的 lookback 預設），UI / 本模組都不得自帶第二組數字；
3. **停售 / NAV 不動（σ≈0）的基金絕不可被推薦**（§1）；
4. screener 與大表對同一條 NAV 必須得到**同一個基期結論**。
"""
from __future__ import annotations

import pandas as pd

from services.fund_screening import (
    LOW_BASE_LOOKBACK_DEFAULT,
    LOW_BASE_MIN_POINTS,
    compute_base_state,
    screen_funds,
)
from shared.signal_thresholds import ROTATION_BUY_SIGMA, ROTATION_SELL_SIGMA


def _series(values: list[float]) -> pd.Series:
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D")
    return pd.Series([float(v) for v in values], index=idx)


# 深跌：前 40 天貼在 100，後 20 天一路跌到 60 → σ rank ≈ −4σ（明確低基期）
_DEEP_DROP = [100.0] * 40 + [100.0 - (i + 1) * 2.0 for i in range(20)]
# 高波動且現價離高點 20%：100/80 交替 → 日報酬 std ≈ 0.226 → σ_abs 巨大
# → σ rank ≈ −0.11σ（**高基期**）。舊「高點−1σ」演算法會判它低基期。
_VOLATILE_NEAR_HIGH = [100.0 if i % 2 == 0 else 80.0 for i in range(60)]
# 單調上升，現價 = 期間高點 → σ rank = 0 → 高基期
_AT_HIGH = [100.0 + i * 0.5 for i in range(60)]
# 停售 / 清算：NAV 完全不動 → σ≈0 → 無法定位階
_FROZEN = [10.0] * 100


# ══════════════════════════════════════════════════════════════
# 1. SSOT 對齊（門檻 + 回看窗都不得在本模組另寫一份）
# ══════════════════════════════════════════════════════════════
def test_lookback_matches_the_big_table_default():
    """漂移鎖：本模組顯式傳的 lookback 必須等於大表走的預設值。

    **修正前必紅（本輪新增）**。σ_abs 隨 √n 縮放 —— 兩邊窗口一旦不同，同一檔就會
    算出不同 σ rank，兩把尺又回來了。大表（`hwm_sigma_by_code`）不傳 lookback，
    所以真正的 SSOT 是 `calc_hwm_sigma_levels` 的函式預設值。
    """
    import inspect

    from services.precision_service import calc_hwm_sigma_levels
    _default = inspect.signature(calc_hwm_sigma_levels).parameters["lookback"].default
    assert _default == LOW_BASE_LOOKBACK_DEFAULT, (
        f"大表用 {_default} 天、screener 用 {LOW_BASE_LOOKBACK_DEFAULT} 天 → 兩把尺")


def test_thresholds_come_from_shared_ssot():
    """預設門檻必須是 `shared/signal_thresholds` 那兩個常數，且都是負數。"""
    r = compute_base_state(_series(_DEEP_DROP), min_points=5)
    assert r["buy_sigma"] == ROTATION_BUY_SIGMA
    assert r["sell_sigma"] == ROTATION_SELL_SIGMA
    assert ROTATION_BUY_SIGMA < 0 and ROTATION_SELL_SIGMA < 0, (
        "σ rank 體系是負數；門檻若被改成正數，整條線會靜默反向（§4.1）")


def test_old_positive_sigma_algorithm_is_deleted():
    """**修正前必紅（反向鎖）** —— 舊的「高點−N×std」演算法必須真的不存在。

    留著它 = 留著第二把尺，下一個人會再把它接回某個畫面。
    """
    import services.fund_screening as _fs
    for _name in ("compute_low_base", "LOW_BASE_STD_EPS"):
        assert not hasattr(_fs, _name), f"{_name} 仍在 —— 第二套低基期演算法復活了"


# ══════════════════════════════════════════════════════════════
# 2. compute_base_state 數學與符號
# ══════════════════════════════════════════════════════════════
def test_deep_drop_is_low_base_with_negative_sigma():
    r = compute_base_state(_series(_DEEP_DROP), min_points=5)
    assert r["base"] == "low" and r["is_low_base"] is True
    assert r["sigma_rank"] is not None and r["sigma_rank"] <= ROTATION_BUY_SIGMA
    assert r["sigma_rank"] < 0, "σ rank 必須是負數（不得回到正數深度）"
    assert r["hwm"] == 100.0 and r["current"] == 60.0
    assert r["dist_to_hwm_pct"] < 0


def test_volatile_fund_near_high_is_not_low_base():
    """**修正前必紅（行為衝突）** —— 這正是兩把尺打架的實例。

    舊演算法：std(NAV 價位) ≈ 10，門檻 = 100 − 10 = 90，現價 80 ≤ 90 → ✅ 低基期。
    新口徑：這檔自己的日波動就有 ±20%，σ_abs 遠大於 20 元的跌幅 → σ rank ≈ −0.11σ
    → 其實貼著高點（高基期）。使用者若照舊 screener 買進，大表會說它是 🔴 高基期。
    """
    r = compute_base_state(_series(_VOLATILE_NEAR_HIGH), min_points=5)
    assert r["base"] == "high", f"σ rank={r['sigma_rank']} 竟被判成 {r['base']}"
    assert r["is_low_base"] is False
    assert r["sigma_rank"] >= ROTATION_SELL_SIGMA


def test_at_period_high_is_high_base():
    r = compute_base_state(_series(_AT_HIGH), min_points=5)
    assert r["base"] == "high" and r["sigma_rank"] == 0.0


def test_buy_threshold_nav_uses_signed_addition():
    """買點門檻價 = HWM + buy_sigma×σ_abs（buy_sigma 為負 → 價位低於 HWM）。"""
    r = compute_base_state(_series(_DEEP_DROP), min_points=5)
    assert r["buy_threshold_nav"] is not None
    assert r["buy_threshold_nav"] < r["hwm"]
    # 現價已跌破買點門檻，正是它被判低基期的原因
    assert r["current"] < r["buy_threshold_nav"]


def test_custom_thresholds_are_plumbed_through():
    """門檻若沒真的傳到 `classify_base`，同一條 σ rank 不會換結論 → 本條紅。"""
    _s = _series(_DEEP_DROP)
    assert compute_base_state(_s, min_points=5, buy_sigma=-10.0)["base"] == "mid"
    assert compute_base_state(
        _s, min_points=5, buy_sigma=-10.0, sell_sigma=-5.0)["base"] == "high"


# ══════════════════════════════════════════════════════════════
# 3. §1 Fail Loud 邊界 —— 停售基金絕不可被推薦
# ══════════════════════════════════════════════════════════════
def test_frozen_nav_is_undetermined_not_low_base():
    """§1：NAV 完全不動（停售 / 清算）→ 無法定位階，不得誤判成低基期。"""
    r = compute_base_state(_series(_FROZEN))
    assert r["base"] == "unknown"
    assert r["is_low_base"] is None and r["sigma_rank"] is None
    assert "σ" in r["note"] or "波動" in r["note"], "沒說清楚為什麼判不出來"


def test_frozen_fund_is_excluded_from_recommendations():
    """**修正前必紅（行為衝突）** —— 端到端：停售基金不得出現在進場候選清單。

    舊演算法對 std≈0 已回 `is_low_base=None`（正確），本條確保換演算法時
    那個正確處置沒有在改寫中弄丟。
    """
    rows = screen_funds([
        {"code": "FROZEN", "name": "已停售", "series": _series(_FROZEN),
         "currency": "USD", "category": "平衡型", "eats_principal": False},
    ], min_points=5)
    assert rows == [], "停售基金被當成低基期推薦出去了"


def test_short_series_cannot_be_positioned():
    """NAV 不足 30 筆 → 上游回 error → unknown（不硬算）。"""
    r = compute_base_state(_series([100.0] * 10 + [50.0]), min_points=5)
    assert r["base"] == "unknown" and r["sigma_rank"] is None


def test_reliability_flag_tracks_sample_size():
    r_small = compute_base_state(_series(_DEEP_DROP), min_points=LOW_BASE_MIN_POINTS + 10)
    assert r_small["reliable"] is False and "可信度低" in r_small["note"]
    r_ok = compute_base_state(_series(_DEEP_DROP), min_points=5)
    assert r_ok["reliable"] is True and r_ok["n_points"] == len(_DEEP_DROP)


def test_empty_and_none_and_bad_type():
    assert compute_base_state(None)["note"] == "無 NAV"
    empty = compute_base_state(pd.Series(dtype=float))
    assert empty["base"] == "unknown" and empty["note"] == "NAV 全空"
    assert compute_base_state(123)["note"] == "NAV 型別非序列"


def test_dataframe_input_squeezed():
    df = pd.DataFrame({"nav": _DEEP_DROP},
                      index=pd.date_range("2024-01-01", periods=len(_DEEP_DROP)))
    r = compute_base_state(df, min_points=5)
    assert r["base"] == "low" and r["current"] == 60.0


# ══════════════════════════════════════════════════════════════
# 4. screen_funds 濾鏡 / 去重 / 排序
# ══════════════════════════════════════════════════════════════
def _item(code, ccy, cat, eats, vals):
    return {"code": code, "name": f"fund-{code}", "series": _series(vals),
            "currency": ccy, "category": cat, "eats_principal": eats}


def _base_items():
    return [
        _item("F1", "USD", "平衡型", False, _DEEP_DROP),          # 低基期+不吃 → 入選
        _item("F2", "USD", "平衡型", False, _AT_HIGH),            # 高基期 → 剔除
        _item("F3", "TWD", "股票型", True, _DEEP_DROP),           # 吃本金 → 剔除
        _item("F4", "USD", "平衡型", None, _DEEP_DROP),           # 吃本金狀態未知 → 剔除
    ]


def test_screen_default_keeps_only_low_base_and_no_eat():
    rows = screen_funds(_base_items(), min_points=5)
    assert [r["code"] for r in rows] == ["F1"]


def test_screen_only_no_eat_false_includes_unknown_and_eaters():
    rows = screen_funds(_base_items(), min_points=5, only_no_eat=False)
    assert {r["code"] for r in rows} == {"F1", "F3", "F4"}


def test_screen_currency_filter():
    rows = screen_funds(_base_items(), min_points=5,
                        only_no_eat=False, currencies={"USD"})
    assert {r["code"] for r in rows} == {"F1", "F4"}


def test_screen_category_filter():
    rows = screen_funds(_base_items(), min_points=5,
                        only_no_eat=False, categories={"平衡型"})
    assert {r["code"] for r in rows} == {"F1", "F4"}


def test_screen_dedup_same_code():
    items = _base_items() + [_item("F1", "USD", "平衡型", False, _DEEP_DROP)]
    rows = screen_funds(items, min_points=5)
    assert [r["code"] for r in rows] == ["F1"]


def test_screen_sorted_by_sigma_rank_ascending():
    """σ rank 遞增 = 跌最深的在最上面（負數體系，**不是**舊的正數深度遞減）。"""
    rows = screen_funds(
        [_item("HIGH", "USD", "平衡型", False, _VOLATILE_NEAR_HIGH),
         _item("DEEP", "USD", "平衡型", False, _DEEP_DROP)],
        min_points=5, only_low_base=False)
    assert [r["code"] for r in rows] == ["DEEP", "HIGH"]
    assert rows[0]["sigma_rank"] < rows[1]["sigma_rank"]


def test_screen_puts_unpositionable_funds_last():
    """無法定位階者排最後（不得混在跌最深的那一端誤導使用者）。"""
    rows = screen_funds(
        [_item("FROZEN", "USD", "平衡型", False, _FROZEN),
         _item("DEEP", "USD", "平衡型", False, _DEEP_DROP)],
        min_points=5, only_low_base=False)
    assert [r["code"] for r in rows] == ["DEEP", "FROZEN"]
    assert rows[-1]["sigma_rank"] is None


# ══════════════════════════════════════════════════════════════
# 5. 跨畫面一致性 —— 本檔存在的理由
# ══════════════════════════════════════════════════════════════
def test_screener_and_big_table_always_agree():
    """**修正前必紅（行為衝突）** —— screener 與大表對同一條 NAV 的基期結論必須相同。

    大表走 `ui/helpers/fund_grp_health/risk.hwm_sigma_by_code` →
    `services/rotation.classify_base`；screener 走 `compute_base_state`。
    兩條路徑各自獨立呼叫，但底層是同一支 σ rank + 同一組門檻 → 結論必須一致。
    舊 screener 對 `_VOLATILE_NEAR_HIGH` 會說「低基期」，大表說「高基期」。
    """
    from services.rotation import classify_base
    from ui.helpers.fund_grp_health.risk import hwm_sigma_by_code

    for _vals in (_DEEP_DROP, _VOLATILE_NEAR_HIGH, _AT_HIGH, _FROZEN):
        _s = _series(_vals)
        _screen = screen_funds([_item("X", "USD", "平衡型", False, _vals)],
                               min_points=5, only_low_base=False)
        _big = hwm_sigma_by_code([{"code": "X", "series": _s}])
        _big_base = classify_base(_big["X"].get("σ rank"),
                                  ROTATION_SELL_SIGMA, ROTATION_BUY_SIGMA)
        if not _screen:                       # 兩邊都判不出來時 screener 仍會出列
            raise AssertionError("only_low_base=False 不該濾掉任何一檔")
        assert _screen[0]["base"] == _big_base, (
            f"同一條 NAV：screener={_screen[0]['base']} vs 大表={_big_base}")
