"""v19.484 稽核 PR-4b:換股/輪動 跨幣別標註(#3)+ 短NAV候選剔除標名(#5)。

user 2026-08-19 核准「標註匯差但保留」——跨計價幣別配對只加 cross_ccy 旗標 + UI 提醒,
**不砍掉**跨幣別分散/賺價差機會(§4.1)。未知幣別 → 不判 cross(§1 不臆測,無假警報)。
"""
from pathlib import Path

from services.rotation import suggest_rotation_pairs
from services.switch_advisor import _best_candidate, advise_holding

_ROOT = Path(__file__).resolve().parent.parent

_HEALTHY_BUY = {
    "code": "B1", "name": "買方台幣債", "基金類別": "債券", "σ rank": "-2.50σ",
    "4D Grade": "A", "吃本金燈號": "🟢 健康", "操盤評分": 80, "距 HWM %": -18,
}


# ── #3 rotation:cross_ccy 旗標 ──────────────────────────────────────────
def test_rotation_cross_ccy_flagged_when_currencies_differ():
    rows = [
        {"code": "S1", "name": "賣方美元股", "基金類別": "股票", "σ rank": "0.10σ", "currency": "USD"},
        dict(_HEALTHY_BUY, currency="TWD"),
    ]
    p = suggest_rotation_pairs(rows)
    assert p[0]["buy_code"] == "B1"
    assert p[0]["cross_ccy"] is True
    assert p[0]["sell_ccy"] == "USD" and p[0]["buy_ccy"] == "TWD"


def test_rotation_same_ccy_not_flagged():
    rows = [
        {"code": "S1", "name": "賣方台幣股", "基金類別": "股票", "σ rank": "0.10σ", "currency": "TWD"},
        dict(_HEALTHY_BUY, currency="TWD"),
    ]
    assert suggest_rotation_pairs(rows)[0]["cross_ccy"] is False


def test_rotation_unknown_ccy_no_false_positive():
    # §1:任一邊幣別未知 → 不判跨幣別(寧可漏標,不假警報)
    rows = [
        {"code": "S1", "name": "賣方", "基金類別": "股票", "σ rank": "0.10σ", "currency": None},
        dict(_HEALTHY_BUY, currency="TWD"),
    ]
    assert suggest_rotation_pairs(rows)[0]["cross_ccy"] is False


def test_rotation_no_buy_candidate_cross_ccy_false():
    rows = [{"code": "S1", "name": "賣方", "基金類別": "股票", "σ rank": "0.10σ", "currency": "USD"}]
    p = suggest_rotation_pairs(rows)
    assert p[0]["buy_code"] is None
    assert p[0]["cross_ccy"] is False and p[0]["buy_ccy"] is None


# ── #3 switch_advisor:_best_candidate cross_ccy + advise_holding 理由標註 ──
def test_best_candidate_cross_ccy():
    pool = [dict(_HEALTHY_BUY, currency="TWD", nav_series=None)]
    assert _best_candidate("S1", pool, held_ccy="USD")["cross_ccy"] is True
    assert _best_candidate("S1", pool, held_ccy="TWD")["cross_ccy"] is False
    assert _best_candidate("S1", pool, held_ccy="")["cross_ccy"] is False  # 持倉幣別未知 → 不假警報


def test_advise_holding_switch_reason_carries_cross_ccy_note():
    # 持倉:震盪型(override 強制)+ 高基期;池中低基期健康別類 + 不同幣別 → 理由帶「跨幣別」
    held = {"code": "H1", "name": "持倉美元股", "基金類別": "股票", "σ rank": "0.20σ",
            "currency": "USD", "type_override": "震盪", "nav_series": None}
    pool = [dict(_HEALTHY_BUY, 基金類別="債券", currency="TWD", type_override="震盪", nav_series=None)]
    a = advise_holding(held, pool)
    assert a["action"] == "switch"
    assert a["switch_to"]["cross_ccy"] is True
    assert "跨幣別" in a["reason"]


def test_advise_holding_same_ccy_switch_no_note():
    held = {"code": "H1", "name": "持倉台幣股", "基金類別": "股票", "σ rank": "0.20σ",
            "currency": "TWD", "type_override": "震盪", "nav_series": None}
    pool = [dict(_HEALTHY_BUY, 基金類別="債券", currency="TWD", type_override="震盪", nav_series=None)]
    a = advise_holding(held, pool)
    assert a["action"] == "switch"
    assert a["switch_to"]["cross_ccy"] is False
    assert "跨幣別" not in a["reason"]


# ── L3 plumbing:批次大表 df 的 ccy 欄有帶進 rotation rows ──────────────
def test_rows_from_batch_df_carries_currency():
    import pandas as pd
    from ui.helpers.fund_grp_health.rotation import rows_from_batch_df
    df = pd.DataFrame([{
        "code": "X1", "基金名": "測試", "基金類別": "股票", "4D Grade": "A",
        "σ rank": "-1.0σ", "距 HWM %": "-10%", "操盤評分": 70,
        "吃本金燈號 (1Y · )": "🟢 健康", "ccy": "USD",
    }])
    rows = rows_from_batch_df(df)
    assert rows[0]["currency"] == "USD"


# ── #5 + #3 UI:誠實提示片語存在於原始碼(§1)────────────────────────────
def test_rotation_ui_has_cross_ccy_and_exclusion_notes():
    src = (_ROOT / "ui" / "helpers" / "fund_grp_health" / "rotation.py").read_text(encoding="utf-8")
    assert "跨幣別" in src and "換股時會**被動吃到匯率變動**" in src   # #3 標註
    assert "未納入買方候選(σ 資料不足" in src                         # #5 剔除標名
