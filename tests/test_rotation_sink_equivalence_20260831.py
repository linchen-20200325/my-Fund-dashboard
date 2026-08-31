"""輪動配對計算下沉(2026-08-31)— 零行為變更的機器證據 + 突變守衛。

本輪把仍住在 `ui/helpers/fund_grp_health/rotation.py` 的**計算**逐字下沉
`services/rotation.py`(全站單一份底層核心):
  1. `_cell`(NaN → None 正規化)
  2. `rows_from_batch_df`(批次大表 df → 配對核心輸入契約)
  3. `_render_pairs_ui` 內的「σ 資料不足標名」門檻判斷 → `insufficient_sigma_names`

本檔驗三件事:
  A. **輸出等價**(路徑 ② rows 已組好 / 路徑 ③ 批次 df):同輸入下,
     下沉後的 L2 函式輸出 == 下沉前 UI inline 版(逐字凍結於本檔)的輸出,逐項相等。
  B. **委派為真**:UI 端的名字就是 L2 的函式(identity)、`_render_pairs_ui`
     實際經 `services.rotation.insufficient_sigma_names` 取得標名清單(sentinel)。
  C. **單一份不回退**:UI 檔不得再長回自己的 `def rows_from_batch_df` / `def _cell`;
     services 端核心被拿掉(刪函式)→ 本檔 import 當場紅。

⚠️ 凍結參考實作(`_old_*`)是 2026-08-31 下沉前 `ui/helpers/fund_grp_health/rotation.py`
   (git main 96bd538 當時內容)的**逐字複本**,只改名加 `_old_` 前綴 —— 不得「順手優化」,
   它的存在意義就是當那把不會漂移的尺。
"""
from __future__ import annotations

import pandas as pd
import pytest

import services.rotation as SR
from services.rotation import (
    classify_base,
    insufficient_sigma_names,
    rows_from_batch_df,
    suggest_rotation_pairs,
)

# ═══════════════════════════════════════════════════════════════════════
# 凍結:下沉前的 UI inline 實作(逐字複本,僅改名)
# ═══════════════════════════════════════════════════════════════════════


def _old_cell(row, col):
    """(凍結)從 pandas Series / dict 取值,NaN → None。"""
    v = row.get(col)
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _old_rows_from_batch_df(df) -> list:
    """(凍結)批次「組合健診大表」df → suggest_rotation_pairs 所需 rows。"""
    rows = []
    for _, r in df.iterrows():
        _code = _old_cell(r, "code")
        rows.append({
            "code": _code,
            "name": _old_cell(r, "基金名") or _code,
            "基金類別": _old_cell(r, "基金類別"),
            "4D Grade": _old_cell(r, "4D Grade"),
            "σ rank": _old_cell(r, "σ rank"),
            "距 HWM %": _old_cell(r, "距 HWM %"),
            "操盤評分": _old_cell(r, "操盤評分"),
            "吃本金燈號": _old_cell(r, "吃本金燈號 (1Y · )"),
            "currency": _old_cell(r, "ccy"),
        })
    return rows


def _old_insufficient(rows, _sell, _buy) -> list:
    """(凍結)`_render_pairs_ui` 原 inline 的 σ 資料不足標名判斷。"""
    return [str(r.get("name") or r.get("code"))
            for r in rows
            if classify_base(r.get("σ rank"), _sell, _buy) == "unknown"]


# ═══════════════════════════════════════════════════════════════════════
# 輸入 battery(涵蓋 §4.6 邊界:NaN 整列、缺欄、空 df、單筆、σ 字尾)
# ═══════════════════════════════════════════════════════════════════════

_DFS = {
    "normal_two_ccy": pd.DataFrame([
        {"code": "A", "基金名": "A基", "基金類別": "股票型", "4D Grade": "A",
         "σ rank": "-0.20σ", "距 HWM %": "-3%", "操盤評分": 80,
         "吃本金燈號 (1Y · )": "🟢", "ccy": "USD"},
        {"code": "B", "基金名": "B基", "基金類別": "債券型", "4D Grade": "B",
         "σ rank": "-2.00σ", "距 HWM %": "-18%", "操盤評分": 75,
         "吃本金燈號 (1Y · )": "🟡 注意", "ccy": "TWD"},
    ]),
    "nan_row": pd.DataFrame([
        {"code": "A", "基金名": "A", "基金類別": "股票型", "4D Grade": "A",
         "σ rank": "-0.10σ", "距 HWM %": "-2%", "操盤評分": 80,
         "吃本金燈號 (1Y · )": "🟢", "ccy": "USD"},
        {"code": "B", "基金名": None, "基金類別": None, "4D Grade": None,
         "σ rank": None, "距 HWM %": None, "操盤評分": None,
         "吃本金燈號 (1Y · )": None, "ccy": None},
    ]),
    "no_ccy_col_single": pd.DataFrame([
        {"code": "C", "基金名": "C", "基金類別": "平衡型", "4D Grade": "C",
         "σ rank": "-1.60σ", "距 HWM %": "-12%", "操盤評分": 55,
         "吃本金燈號 (1Y · )": "🟢"},
    ]),
    "empty": pd.DataFrame(columns=["code", "基金名"]),
}

# 路徑 ②:已組好的 rows(形狀 = `_assemble_rows` 產物;含 σ 缺值檔)
_ASSEMBLED_ROWS = [
    {"code": "A", "name": "A", "基金類別": "股票型", "4D Grade": "A",
     "σ rank": "-0.2σ", "距 HWM %": "-3%", "操盤評分": 80,
     "吃本金燈號": "🟢", "currency": "USD"},
    {"code": "B", "name": "B", "基金類別": "債券型", "4D Grade": "B",
     "σ rank": "-2.0σ", "距 HWM %": "-18%", "操盤評分": 75,
     "吃本金燈號": "🟢", "currency": "TWD"},
    {"code": "C", "name": "C基", "基金類別": None, "4D Grade": None,
     "σ rank": None, "距 HWM %": None, "操盤評分": None,
     "吃本金燈號": None, "currency": None},
    {"code": "D", "name": "", "基金類別": "貨幣型", "4D Grade": "B",
     "σ rank": "0.10σ", "距 HWM %": "-1%", "操盤評分": 60,
     "吃本金燈號": "🟢", "currency": "TWD"},
]

# 滑桿門檻網格(UI 三滑桿的端點與預設)
_THRESHOLD_GRID = [(-0.5, -1.5), (-2.0, -3.0), (0.5, -0.5), (-1.0, -1.0)]


# ═══════════════════════════════════════════════════════════════════════
# A. 輸出等價
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("name", sorted(_DFS))
def test_path3_rows_from_batch_df_identical(name):
    """路徑 ③(批次 df 入口):下沉後 rows == 下沉前 rows,逐項逐 key 相等。"""
    df = _DFS[name]
    assert rows_from_batch_df(df) == _old_rows_from_batch_df(df)


@pytest.mark.parametrize("name", sorted(_DFS))
def test_path3_end_to_end_pairs_identical(name):
    """路徑 ③ 全程:df → rows → 配對,下沉前後配對輸出逐項相等。"""
    df = _DFS[name]
    assert (suggest_rotation_pairs(rows_from_batch_df(df))
            == suggest_rotation_pairs(_old_rows_from_batch_df(df)))


@pytest.mark.parametrize("sell,buy", _THRESHOLD_GRID)
def test_path2_insufficient_names_identical(sell, buy):
    """路徑 ②(rows 已組好):σ 資料不足標名,下沉後 == 凍結 inline 判斷。"""
    assert (insufficient_sigma_names(_ASSEMBLED_ROWS, sell, buy)
            == _old_insufficient(_ASSEMBLED_ROWS, sell, buy))


def test_path2_insufficient_flags_only_missing_sigma():
    """語意錨點(非只比自己):battery 內唯一 σ 缺值檔 C 被標名、且 name 缺退 code。"""
    assert insufficient_sigma_names(_ASSEMBLED_ROWS, -0.5, -1.5) == ["C基"]
    _rows = [{"code": "Z", "name": None, "σ rank": None}]
    assert insufficient_sigma_names(_rows, -0.5, -1.5) == ["Z"]


def test_path2_pairs_golden():
    """路徑 ② 語意錨點:A(高基期股票)→ B(低基期債券健康),C σ 缺不入候選。"""
    pairs = suggest_rotation_pairs(_ASSEMBLED_ROWS)
    assert [p["sell_code"] for p in pairs] == ["A", "D"]
    assert pairs[0]["buy_code"] == "B" and pairs[0]["cross_ccy"] is True
    assert pairs[0]["potential_pct"] == pytest.approx(22.0, abs=0.5)


# ═══════════════════════════════════════════════════════════════════════
# B. 委派為真(突變方向:UI 若重新 inline,以下當場紅)
# ═══════════════════════════════════════════════════════════════════════


def test_ui_rows_from_batch_df_is_the_l2_function():
    """UI 名字 == L2 函式本體(identity,不是另一份複本)。"""
    import ui.helpers.fund_grp_health.rotation as UIR
    assert UIR.rows_from_batch_df is SR.rows_from_batch_df


def test_render_pairs_ui_routes_through_l2_sentinel(monkeypatch):
    """`_render_pairs_ui` 的 σ 不足標名**真的**經 services.rotation 取得。

    突變驗證(fail-closed):把 UI 端改回 inline 判斷(不呼叫 L2)→ sentinel
    不會被呼叫 → 本測試紅。headless bare mode 下 streamlit 呼叫僅發警告,可執行。
    """
    from ui.helpers.fund_grp_health.rotation import _render_pairs_ui

    called: dict = {}
    _orig = SR.insufficient_sigma_names

    def _rec(rows, sell, buy):
        called["args"] = (len(rows), sell, buy)
        return _orig(rows, sell, buy)

    monkeypatch.setattr(SR, "insufficient_sigma_names", _rec)
    _render_pairs_ui(list(_ASSEMBLED_ROWS), key_prefix="eq_t_", offer_download=False)
    assert called.get("args") == (len(_ASSEMBLED_ROWS), -0.5, -1.5), (
        "_render_pairs_ui 未經 services.rotation.insufficient_sigma_names —— "
        "σ 不足標名的門檻判斷被搬回 UI(或斷線),違反本輪下沉的單一核心要求。")


# ═══════════════════════════════════════════════════════════════════════
# C. 單一份不回退(源碼層守衛;不寫行號,§8.2.A.0 規則 1)
# ═══════════════════════════════════════════════════════════════════════


def _src(rel: str) -> str:
    from pathlib import Path
    return (Path(__file__).resolve().parent.parent / rel).read_text(encoding="utf-8")


def test_ui_file_does_not_regrow_its_own_copy():
    """UI 檔不得再定義自己的 df 轉接 / NaN 正規化(否則兩份實作重新分家)。"""
    src = _src("ui/helpers/fund_grp_health/rotation.py")
    assert "def rows_from_batch_df" not in src, "UI 檔長回自己的 rows_from_batch_df"
    assert "def _cell" not in src, "UI 檔長回自己的 _cell"
    assert "from services.rotation import rows_from_batch_df" in src, (
        "UI 檔的 rows_from_batch_df re-export 斷線 —— 既有 caller import 路徑會壞")


def test_l2_core_holds_the_single_copy():
    """核心住在 services/rotation.py(把它拿掉 → 本檔 module import 先紅,這裡再紅一次)。"""
    src = _src("services/rotation.py")
    for sym in ("def rows_from_batch_df", "def _cell", "def insufficient_sigma_names"):
        assert sym in src, f"services/rotation.py 缺 {sym} —— 下沉核心被移除"
