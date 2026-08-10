"""test_compute_1y_total_return.py — v18.134 共用 1Y 含息報酬 helper 測試

修使用者反饋「Tab2 vs Tab3 同基金 1Y 報酬不同」— 抽 helper 後驗證統一行為。

2026-08-10:來源標籤(會原樣印在健診大表「1Y 來源」欄與 Tab2 KPI 卡上)改成白話,
內部代號拿掉。本檔原本用 `"wb01" in src` / `"ret_1y_total" in src` 這種**內部代號
子字串**當斷言 —— 那些字正是要從畫面上消失的東西,故一律改成比對 SSOT 常數
(`services.fund_total_return.SRC_*`)。等值比對比原本的子字串比對**更嚴**,
沒有放寬任何一條。
"""
from __future__ import annotations

from services.fund_total_return import (
    SRC_NONE,
    SRC_OFFICIAL,
    SRC_PERF_UNLABELED,
    SRC_SELF_ANNUALIZED,
    SRC_SELF_NAV_ONLY,
    SRC_SELF_RESTORED,
    SRC_SELF_TOTAL,
)
from ui.helpers.macro_helpers import compute_1y_total_return


def test_perf_1y_takes_priority():
    """perf['1Y'] 應該最優先（官方績效表真 1Y 最權威，PR #122 設計）。

    本 case 沒給 `perf_source` → 有數字但來源不明,標籤必須誠實說「未標註」，
    **不得**冒充官方（§1）。
    """
    obj = {
        "metrics": {"ret_1y_total": 37.6, "ret_1y": 10.0},   # 本地計算 high
        "moneydj_raw": {"perf": {"1Y": 9.09}},                 # 官方績效表 low
    }
    v, src = compute_1y_total_return(obj)
    assert v == 9.09
    assert src == SRC_PERF_UNLABELED


def test_official_source_label():
    obj = {
        "moneydj_raw": {"perf": {"1Y": 9.09}},
        "perf_source": "wb01",
    }
    v, src = compute_1y_total_return(obj)
    assert v == 9.09
    assert src == SRC_OFFICIAL


def test_local_calc_source_label():
    obj = {
        "moneydj_raw": {"perf": {"1Y": 12.5}},
        "perf_source": "local_calc",
    }
    v, src = compute_1y_total_return(obj)
    assert v == 12.5
    assert src == SRC_SELF_RESTORED
    assert "自算" in src, "本地還原是本站算的,不可被誤讀成官方值"


def test_fallback_to_local_total_return():
    """perf['1Y'] 缺 → fallback 本站自算含息。"""
    obj = {"metrics": {"ret_1y_total": 15.2}, "moneydj_raw": {}}
    v, src = compute_1y_total_return(obj)
    assert v == 15.2
    assert src == SRC_SELF_TOTAL


def test_short_window_label():
    """窗口 < 350 天應標出實際天數(跨檔比大小的陷阱不可藏)。"""
    obj = {
        "metrics": {"ret_1y_total": 25.0, "ret_1y_window_days": 90},
        "moneydj_raw": {},
    }
    v, src = compute_1y_total_return(obj)
    assert v == 25.0
    assert src.startswith(SRC_SELF_TOTAL)
    assert "90" in src and "窗口" in src, f"短窗口天數不可弄丟:{src!r}"


def test_fallback_to_nav_only():
    """自算含息也缺 → 純淨值變化(不含配息),標籤必須講明不含配息。"""
    obj = {"metrics": {"ret_1y": 8.5}, "moneydj_raw": {}}
    v, src = compute_1y_total_return(obj)
    assert v == 8.5
    assert src == SRC_SELF_NAV_ONLY
    assert "不含配息" in src


def test_all_missing_returns_none():
    obj = {"metrics": {}, "moneydj_raw": {}}
    v, src = compute_1y_total_return(obj)
    assert v is None
    assert src == SRC_NONE


def test_nav_series_fallback():
    """metrics 全缺、有 NAV series → 自算年化。"""
    import pandas as pd
    idx = pd.date_range("2024-01-01", "2025-01-01", freq="D")
    s = pd.Series([100.0] * len(idx[:-1]) + [110.0], index=idx)
    obj = {"metrics": {}, "moneydj_raw": {}, "series": s}
    v, src = compute_1y_total_return(obj)
    assert v is not None
    assert abs(v - 10.0) < 1.0   # ~10% over 1 year
    # 最不可靠的一層 —— 必須自報「這是自算的外推值」且帶樣本天數(可信度資訊不可省)。
    # 用模板本身組正則,避免在測試裡再抄一份文案。
    import re
    assert re.fullmatch(SRC_SELF_ANNUALIZED.replace("{days}", r"\d+"), src), (
        f"外推年化標籤不符 SSOT 模板({SRC_SELF_ANNUALIZED!r}):{src!r}")


# ──────────────────────────────────────────────────────────
# v19.178 — shape normalize regression(健診表平坦 fd 對齊 Tab2 nested)
# ──────────────────────────────────────────────────────────
class TestFlatFdShapeNormalize:
    """v19.178 守:健診表 _auto_fetch_moneydj() 平坦 fd 直接傳入 SSOT 函式時,
    必須能拿到官方 perf['1Y'] 而非走 NAV 序列年化 fallback。

    修「FTZU8 在 Tab2(nested)🟢 健康 vs 健診表(平坦)🔴 吃本金 結論相反」根因。
    """

    def test_flat_fd_with_perf_1y_uses_official(self):
        """平坦 fd:top-level 有 perf 但無 moneydj_raw → 應自動 wrap 命中官方 perf['1Y']。"""
        flat_fd = {
            "perf": {"1Y": 12.35},
            "perf_source": "wb01",
            "series": None,
            "metrics": {},
            "dividends": [],
            "moneydj_div_yield": 7.49,
        }
        v, src = compute_1y_total_return(flat_fd)
        assert v == 12.35, (
            f"平坦 fd 應拿到官方 perf['1Y']=12.35,實際 {v}(若走 NAV fallback 才會 None / 不準)"
        )
        assert src == SRC_OFFICIAL, f"src 應標官方,實際 {src}"

    def test_flat_fd_vs_nested_same_result(self):
        """同樣資料用 flat 與 nested 兩種 shape 包,SSOT 函式應回相同結果。"""
        flat_fd = {
            "perf": {"1Y": 12.35},
            "perf_source": "wb01",
            "metrics": {"ret_1y_total": 99.0},  # 故意設離譜值,perf 優先應勝出
        }
        nested_fd = {
            "moneydj_raw": {"perf": {"1Y": 12.35}},
            "perf_source": "wb01",
            "metrics": {"ret_1y_total": 99.0},
        }
        v_flat, src_flat = compute_1y_total_return(flat_fd)
        v_nested, src_nested = compute_1y_total_return(nested_fd)
        assert v_flat == v_nested == 12.35, (
            f"flat vs nested 結果不同(v_flat={v_flat}, v_nested={v_nested})— SSOT 違反"
        )

    def test_flat_fd_without_perf_falls_back_normally(self):
        """平坦 fd 但 perf 也缺 → 走 metrics fallback(不該強迫 wrap 後出錯)。"""
        flat_fd = {
            "perf": {},  # top-level perf 是空 dict
            "series": None,
            "metrics": {"ret_1y_total": 8.0},
            "dividends": [],
        }
        v, src = compute_1y_total_return(flat_fd)
        assert v == 8.0
        assert src == SRC_SELF_TOTAL

    def test_nested_fd_unchanged_after_normalize(self):
        """既有 nested fd 不應被 normalize 邏輯破壞(向後相容)。"""
        nested_fd = {
            "moneydj_raw": {"perf": {"1Y": 15.0}},
            "perf_source": "wb01",
            "metrics": {"ret_1y_total": 99.0},
        }
        v, src = compute_1y_total_return(nested_fd)
        assert v == 15.0
        assert src == SRC_OFFICIAL
