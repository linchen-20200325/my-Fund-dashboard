"""輪動配對 — 批次「組合健診大表」df 入口(rows_from_batch_df)v19.417。

批次分頁不重抓,直接把已算好的大表 df 餵給 suggest_rotation_pairs。這裡驗:
(1) 欄名 → dict key 對映(尤其 `吃本金燈號 (1Y · MK)` → `吃本金燈號`)、
(2) 跨類別配對可從 df 正常產出、
(3) 失敗檔的 NaN/None 不會變成字串 'nan' 混進類別 / σ。
"""
import pandas as pd

from services.rotation import suggest_rotation_pairs
from ui.helpers.fund_grp_health.rotation import rows_from_batch_df


def _df(records):
    return pd.DataFrame(records)


def test_rows_from_batch_df_maps_columns():
    df = _df([{
        "code": "A", "基金名": "A基金", "基金類別": "股票型", "4D Grade": "B",
        "σ rank": "-0.20σ", "距 HWM %": "-3%", "操盤評分": 70,
        "吃本金燈號 (1Y · MK)": "🟢 未吃本金",
    }])
    row = rows_from_batch_df(df)[0]
    assert row["code"] == "A" and row["name"] == "A基金"
    assert row["基金類別"] == "股票型" and row["4D Grade"] == "B"
    assert row["σ rank"] == "-0.20σ" and row["操盤評分"] == 70
    assert row["吃本金燈號"] == "🟢 未吃本金"      # 大表欄名帶 (1Y · MK) → 收斂為 key 吃本金燈號


def test_name_falls_back_to_code_when_blank():
    df = _df([{"code": "X", "基金名": None}])
    assert rows_from_batch_df(df)[0]["name"] == "X"


def test_batch_df_cross_category_pairing():
    """賣 股票型高基期 → 買 債券型低基期健康(跨類別),全程從 df 走。"""
    df = _df([
        {"code": "A", "基金名": "A", "基金類別": "股票型", "4D Grade": "A",
         "σ rank": "-0.20σ", "距 HWM %": "-3%", "操盤評分": 80, "吃本金燈號 (1Y · MK)": "🟢"},
        {"code": "B", "基金名": "B", "基金類別": "債券型", "4D Grade": "A",
         "σ rank": "-2.00σ", "距 HWM %": "-18%", "操盤評分": 75, "吃本金燈號 (1Y · MK)": "🟢"},
    ])
    pairs = suggest_rotation_pairs(rows_from_batch_df(df))
    assert len(pairs) == 1
    assert pairs[0]["sell_code"] == "A" and pairs[0]["buy_code"] == "B"
    assert pairs[0]["sell_cat"] == "股票型" and pairs[0]["buy_cat"] == "債券型"


def test_batch_df_nan_row_not_polluting():
    """失敗檔整列 None(批次不丟棄)→ 不得變 'nan' 類別、不得被當賣/買方。"""
    df = _df([
        {"code": "A", "基金名": "A", "基金類別": "股票型", "4D Grade": "A",
         "σ rank": "-0.20σ", "距 HWM %": "-3%", "操盤評分": 80, "吃本金燈號 (1Y · MK)": "🟢"},
        {"code": "B", "基金名": "B", "基金類別": None, "4D Grade": None,
         "σ rank": None, "距 HWM %": None, "操盤評分": None, "吃本金燈號 (1Y · MK)": None},
    ])
    rows = rows_from_batch_df(df)
    assert rows[1]["基金類別"] is None and rows[1]["σ rank"] is None   # NaN/None → None,非 'nan'
    pairs = suggest_rotation_pairs(rows)
    assert pairs[0]["sell_code"] == "A" and pairs[0]["buy_code"] is None   # B 無效 → A 無健康買方
