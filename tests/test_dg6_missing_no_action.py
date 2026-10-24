"""DG-6（2026-10-24 客戶裁示 DEC-2026-10-24-12）：Missing／Unknown／INSUFFICIENT 不得經另一單軸訊號重新產生投資行動。

客戶只核准兩條路徑（其餘 BL-0442 平行引擎未核准，本檔不測、也不得延伸）：

1. `services/switch_advisor.py::advise_holding` 的表現差 overlay ＋ `services/switch_notify.py`（LINE 週報）：
   必要資料不足（action == INSUFFICIENT）時，不得由「表現差」重新產生「建議換入／換出」；
   不挑候選、標 `underperf_suppressed=True`、不列入 actionable、週報以 ⬜ 一行揭露。
   HOLD／WARN 的 overlay、SWITCH、SELL_CASH 行為不變。
2. `services/health/replacement.py::check_replacement_recommendation`：
   分類未判定（`services.zscore_engine.is_core_bucket(category) is None`）→ ⬜「分類未判定」、不給換／留；
   任一規則判不動且無觸發／觀察 → ⬜「無法判定」，不得 🟢 保留。分類可判定時 replace／observe 不變。
"""
from __future__ import annotations

import pytest

import services.switch_advisor as sa
from services.health.replacement import check_replacement_recommendation
from services.regime_fit import asset_bucket
from services.switch_advisor import (
    HOLD,
    INSUFFICIENT,
    SWITCH,
    advise_holding,
    advise_switches,
)
from services.switch_notify import build_notification
from services.zscore_engine import is_core_bucket

# ───────────────────────── 共用 fixture ─────────────────────────

_UNDER = {"is_underperforming": True, "reasons": ["跑輸大盤"], "excess_pct": -8.0,
          "benchmark_used": "TWII", "full_period": False, "redlight": None, "lags_benchmark": True}

_POOL = [{"code": "P1", "name": "池中候選", "基金類別": "股票型", "σ rank": "-2.10σ",
          "sigma_rank": -2.10, "4D Grade": "A", "吃本金燈號": "🟢 健康", "操盤評分": 80,
          "距 HWM %": "-12.00%", "currency": "USD", "type_override": "震盪", "nav_series": None}]


def _held(sr, **kw):
    """震盪型持倉;sr = σ rank(-0.2 → 高基期 / -1.0 → 中性 / None → 位置無法判定)。"""
    row = {"code": "H1", "name": "持倉H", "基金類別": "債券型", "σ rank": sr, "sigma_rank": sr,
           "type_override": "震盪", "currency": "USD", "nav_series": None}
    row.update(kw)
    return row


def _no_type_row(code="N1"):
    """型態無法判定(無 override、無淨值序列)→ INSUFFICIENT。"""
    return {"code": code, "name": "型態未知", "nav_series": None}


def _boom(*_a, **_kw):  # 資料不足列不得去選股池找候選
    raise AssertionError("_best_candidate 不得在 INSUFFICIENT 列被呼叫（DG-6）")


# ───────────────────────── Path 1：switch_advisor ─────────────────────────

def test_valid_data_range_high_still_switches():
    """有效資料:震盪型 + 高基期 + 池中有低基期健康標的 → 仍 SWITCH(本次未改)。"""
    a = advise_holding(_held(-0.20), _POOL, fx_label="neutral", macro_composite=0.0)
    assert a["action"] == SWITCH and a["switch_to"]["code"] == "P1"
    assert a["underperf_suppressed"] is False


def test_valid_hold_with_underperf_still_gets_candidate():
    """有效資料 HOLD + 表現差 → overlay 照舊補選股池候選(HOLD／WARN 不在本次裁示範圍)。"""
    a = advise_holding(_held(-1.00), _POOL, fx_label="neutral", macro_composite=0.0,
                       underperformance=_UNDER)
    assert a["action"] == HOLD
    assert a["underperf_candidate"] and a["underperf_candidate"]["code"] == "P1"
    assert "建議從選股池換入" in a["reason"]
    assert a["underperf_suppressed"] is False


@pytest.mark.parametrize("row", [_held(None), _held("—"), _no_type_row()],
                         ids=["range_position_unknown", "range_dash", "type_unknown"])
def test_insufficient_plus_underperf_no_candidate(monkeypatch, row):
    monkeypatch.setattr(sa, "_best_candidate", _boom)
    a = advise_holding(row, _POOL, fx_label="neutral", macro_composite=0.0,
                       underperformance=_UNDER)
    assert a["action"] == INSUFFICIENT and a["action_zh"] == "⬜ 資料不足"
    assert a["underperf_candidate"] is None and a["switch_to"] is None
    assert a["underperf_suppressed"] is True
    assert "建議換入" not in a["reason"] and "建議從選股池換入" not in a["reason"]
    assert "選股池無合適替代標的" not in a["reason"]        # 不暗示已搜尋過
    assert "暫不提供換入／換出建議" in a["reason"]
    # 表現差 block 只當證據保留
    assert a["underperformance"]["is_underperforming"] is True


def test_insufficient_without_underperf_not_suppressed():
    a = advise_holding(_held(None), _POOL, fx_label="neutral", macro_composite=0.0)
    assert a["action"] == INSUFFICIENT and a["underperf_suppressed"] is False


def test_summary_counts_unchanged_for_suppressed(monkeypatch):
    monkeypatch.setattr(sa, "_best_candidate", _boom)
    res = advise_switches([_held(None)], _POOL, underperformance_by_code={"H1": _UNDER})
    assert res["summary"]["n_insufficient"] == 1
    assert res["summary"]["n_underperforming"] == 1        # 證據計數不變


# ───────────────────────── Path 1：switch_notify（LINE 週報）─────────────────────────

def test_notify_insufficient_underperf_only_is_not_actionable():
    res = advise_switches([_held(None)], _POOL, underperformance_by_code={"H1": _UNDER})
    note = build_notification(res, as_of="2026-10-24")
    assert note["should_notify"] is False
    assert note["actionable_codes"] == [] and note["n_actionable"] == 0
    msg = note["message"]
    assert "建議換入" not in msg
    assert "選股池無合適替代標的" not in msg
    assert "✅" not in msg                                   # 全部 ⬜ → 不給 ✅
    assert "⬜ 其中 1 檔有表現差訊號，但必要資料不足（無法判定），不提供換股建議。" in msg


def test_notify_mixed_actionable_and_suppressed():
    rows = [_held(-0.20, code="SW1", name="可換股"), _held(None, code="INS1", name="資料不足檔")]
    res = advise_switches(rows, _POOL, underperformance_by_code={"INS1": _UNDER})
    note = build_notification(res, as_of="2026-10-24")
    assert note["should_notify"] is True
    assert note["actionable_codes"] == ["SW1"]              # 被抑制的列不在 actionable 中
    msg = note["message"]
    assert "資料不足檔" not in msg.split("⬜ 其中")[0]       # 不列入「需留意」明細
    assert "⬜ 其中 1 檔有表現差訊號，但必要資料不足（無法判定），不提供換股建議。" in msg


def test_holding_line_defensive_for_suppressed_row():
    """防禦:即使有人把被抑制的列送進明細,也不得印「建議換入」或「選股池無合適替代標的」。"""
    from services.switch_notify import _holding_line
    a = {"name": "X", "action_zh": "⬜ 資料不足", "underperformance": _UNDER,
         "underperf_suppressed": True,
         "underperf_candidate": {"code": "P1", "name": "不該出現"}}
    line = _holding_line(a)
    assert "建議換入" not in line and "選股池無合適替代標的" not in line
    assert "⬜ 資料不足，不提供換股建議" in line


# ───────────────────────── Path 2：check_replacement_recommendation ─────────────────────────

def _first_category(want_core: bool) -> str:
    """從 asset_bucket SSOT 找一個可對應的類別字串(不寫死桶名對照)。"""
    for cat in ("全球股票型", "科技股票型", "平衡型", "多重資產型", "貨幣市場型"):
        if asset_bucket(cat)[0] is not None and is_core_bucket(cat) is want_core:
            return cat
    raise AssertionError("找不到可對應的類別")


_NONCORE = _first_category(False)
_CORE = _first_category(True)


def _full(cat, **metrics):
    m = {"sharpe": 1.2, "std_1y": 8.0, "max_drawdown": -12.0,
         "ret_3y_ann": 9.0, "ret_3y_ann_tr": 9.0,
         "ret_1y_total": 12.0, "ret_1y_window_days": 365,
         "ret_1y_div_count": 12, "annual_div_rate": 5.0}
    m.update(metrics)
    fd = {"moneydj_raw": {"perf": {"1Y": 12.0}, "moneydj_div_yield": 5.0}, "metrics": m}
    if cat is not None:
        fd["category"] = cat
    return fd


_F_GRADE = {"sharpe": -0.8, "max_drawdown": -42.0}   # 規則 (d) hard trigger


@pytest.mark.parametrize("cat", [None, "", "其他"], ids=["missing", "blank", "unmappable"])
def test_classification_unknown_not_replace(cat):
    assert is_core_bucket(cat) is None
    r = check_replacement_recommendation(_full(cat, **_F_GRADE), holding_years=4)
    assert r["verdict"] == "unknown" and r["emoji"] == "⬜"
    assert r["status"] == "core_unknown" and r["label"] == "分類未判定"
    assert r["triggered_rules"]                          # 規則照算,只當證據
    assert "證據" in r["message"]
    for bad in ("🟢 保留", "建議換 —", "🔴", "🟡 觀察"):
        assert bad not in r["message"]


def test_classification_raises_is_unknown(monkeypatch):
    import services.zscore_engine as ze

    def _raise(_c):
        raise RuntimeError("分類爆炸")
    monkeypatch.setattr(ze, "is_core_bucket", _raise)
    r = check_replacement_recommendation(_full(_NONCORE, **_F_GRADE), holding_years=4)
    assert r["verdict"] == "unknown" and r["status"] == "core_unknown"


def test_classification_unknown_with_no_triggers_is_not_keep():
    r = check_replacement_recommendation(_full("其他"), holding_years=4)
    assert r["verdict"] == "unknown" and r["status"] == "core_unknown"
    assert "保留" not in r["message"] and "證據" not in r["message"]


def test_classification_unknown_excluded_from_red_zone():
    """淘汰候選紅區只篩 `_verdict == "replace"` → 分類未判定不得進入。"""
    from services.health.report import build_dividend_summary_row
    row = build_dividend_summary_row(_full("其他", **_F_GRADE), "UNK1", holding_years=4)
    assert row["_verdict"] != "replace"
    assert row["換標的建議"] == "⬜ 分類未判定"
    rows = [row, build_dividend_summary_row(_full(_NONCORE, **_F_GRADE), "BAD1", holding_years=4)]
    red_zone = [r["code"] for r in rows if r["_verdict"] == "replace"]
    assert red_zone == ["BAD1"]


@pytest.mark.parametrize("cat", [_NONCORE, _CORE], ids=["noncore", "core"])
def test_known_classification_full_data_keep(cat):
    r = check_replacement_recommendation(_full(cat), holding_years=4)
    assert r["verdict"] == "keep" and r["emoji"] == "🟢" and r["status"] == "ok"


@pytest.mark.parametrize("drop,expect_rule", [
    ("ret_3y_ann_tr", "(c)"),                    # 3-3-3 ⬜ 且持有 ≥ 3 年
    ("sharpe", "(d)"),                           # Sharpe 缺
], ids=["missing_333", "missing_sharpe"])
def test_known_classification_missing_data_not_keep(drop, expect_rule):
    fd = _full(_NONCORE)
    fd["metrics"].pop(drop)
    r = check_replacement_recommendation(fd, holding_years=4)
    assert r["verdict"] == "unknown" and r["emoji"] == "⬜"
    assert r["status"] == "rules_incomplete" and r["label"] == "無法判定"
    assert expect_rule in r["message"] and "不提供保留結論" in r["message"]
    assert "🟢" not in r["message"]


def test_known_classification_missing_grade_not_keep():
    """4D 等第算不出(只剩 Sharpe 單維)→ 規則 (b) 判不動 → 不得 🟢。"""
    fd = {"category": _NONCORE,
          "metrics": {"sharpe": 1.0, "max_drawdown": -10.0, "ret_3y_ann_tr": 9.0}}
    r = check_replacement_recommendation(fd, holding_years=0.5)
    assert r["verdict"] == "unknown" and r["status"] == "rules_incomplete"
    assert "(b)" in r["message"]


def test_known_classification_hard_trigger_still_replace():
    r = check_replacement_recommendation(_full(_NONCORE, **_F_GRADE), holding_years=4)
    assert r["verdict"] == "replace" and r["emoji"] == "🔴" and r["status"] == "ok"
    assert any(t.startswith("(d)") for t in r["triggered_rules"])


def test_non_dividend_fund_rule_a_not_applicable_keep():
    """非配息基金(吃本金依既有契約不判)→ 規則 (a) 確定不會觸發 → 其餘判得動即可 🟢。"""
    fd = {"category": _NONCORE, "moneydj_raw": {"perf": {"1Y": 12.0}},
          "metrics": {"sharpe": 1.0, "std_1y": 8.0, "max_drawdown": -15.0,
                      "ret_3y_ann_tr": 9.0, "ret_1y_total": 12.0, "ret_1y_window_days": 365}}
    r = check_replacement_recommendation(fd, holding_years=4)
    assert r["verdict"] == "keep" and r["status"] == "ok"


def test_unknown_message_never_says_keep():
    for fd in (_full(None), _full("其他"), {"category": _NONCORE, "metrics": {"sharpe": 1.0}}, {}):
        r = check_replacement_recommendation(fd, holding_years=4)
        if r["verdict"] == "unknown":
            assert "🟢 保留" not in r["message"]
