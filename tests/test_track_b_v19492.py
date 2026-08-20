"""v19.492 軌B:健診表標籤正名 / 中國顯示層修 / 對帳旗標 / 口徑明示。

稽核改善方案(7-AI 交叉評審後)的低風險批:
- 中國面板 `_china_regime_color`:classify_china_regime 不回 color 鍵 → 從 regime emoji 推色(顯示層,不碰 :672 傳參)。
- `reconcile_by_code`:Sharpe/1Y/配息率 三組雙演算法對帳 → 決策面一欄 worst-of-3 旗標。
- 吃本金欄 drift-lock:合併大表只准出現 1 個吃本金欄變體(防空白對齊觸發重複)。
"""
import pytest


# ── 中國 regime 顏色(顯示層修)──────────────────────────────────────────
def test_china_regime_color_from_emoji():
    from shared.colors import TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, TRAFFIC_YELLOW
    from ui.tab1_macro import _china_regime_color
    assert _china_regime_color("🟢 擴張") == TRAFFIC_GREEN
    assert _china_regime_color("🟡 減速") == TRAFFIC_YELLOW
    assert _china_regime_color("🔴 衰退/緊縮") == TRAFFIC_RED
    assert _china_regime_color("⚪ 中性") == TRAFFIC_NEUTRAL       # 中性 → 中性色
    assert _china_regime_color("⬜ 資料不足") == TRAFFIC_NEUTRAL   # 資料不足 → 中性色(非 None)
    assert _china_regime_color("—") == TRAFFIC_NEUTRAL
    assert _china_regime_color("") == TRAFFIC_NEUTRAL
    assert _china_regime_color(None) == TRAFFIC_NEUTRAL          # §1 不炸、退中性


# ── 對帳 worst-of-3 旗標 ────────────────────────────────────────────────
def _fund(code, statuses):
    """statuses: {reconcile_key: status}。"""
    return {"code": code, "metrics": {k: {"status": v} for k, v in statuses.items()}}


def test_reconcile_worst_of_3():
    from ui.helpers.fund_grp_health.unified import reconcile_by_code
    A = "sharpe_reconcile"
    B = "ret_1y_reconcile"
    C = "div_yield_reconcile"

    # 全 agree → ✅ 一致
    assert reconcile_by_code([_fund("A", {A: "agree", B: "agree", C: "agree"})])["A"]["對帳"] == "✅ 一致"
    # 任一 disagree → ⚠️ 有矛盾(最差態優先)
    assert reconcile_by_code([_fund("B", {A: "agree", B: "disagree", C: "agree"})])["B"]["對帳"] == "⚠️ 有矛盾"
    # 有 agree + 有缺對照 → ✅ 部分
    assert reconcile_by_code([_fund("C", {A: "agree", B: "a_missing", C: "b_missing"})])["C"]["對帳"] == "✅ 部分"
    # 三組皆無法對帳 → ⬜ 單源
    assert reconcile_by_code([_fund("D", {A: "a_missing", B: "both_missing", C: "b_missing"})])["D"]["對帳"] == "⬜ 單源"


def test_reconcile_no_metrics_is_dash():
    from ui.helpers.fund_grp_health.unified import reconcile_by_code
    assert reconcile_by_code([{"code": "E"}])["E"]["對帳"] == "⬜ —"           # 無 metrics → 不猜
    assert reconcile_by_code([{"code": "F", "metrics": {}}])["F"]["對帳"] == "⬜ —"


def test_reconcile_disagree_beats_missing():
    """disagree 優先於缺對照:一項矛盾 + 兩項缺 → 仍 ⚠️(§4.3 決策面不可漏矛盾)。"""
    from ui.helpers.fund_grp_health.unified import reconcile_by_code
    r = reconcile_by_code([_fund("G", {"sharpe_reconcile": "disagree",
                                       "ret_1y_reconcile": "a_missing",
                                       "div_yield_reconcile": "both_missing"})])
    assert r["G"]["對帳"] == "⚠️ 有矛盾"


def test_reconcile_empty_code_skipped():
    from ui.helpers.fund_grp_health.unified import reconcile_by_code
    assert reconcile_by_code([{"code": ""}]) == {}
    assert reconcile_by_code([]) == {}
    assert reconcile_by_code(None) == {}


def test_reconcile_column_registered_in_unified_front():
    """對帳欄已進 _UNIFIED_FRONT(source=extra)→ 自動流入健檢 + 批次大表。"""
    from ui.helpers.fund_grp_health.unified import _UNIFIED_FRONT
    _names = {c for c, _ in _UNIFIED_FRONT}
    assert "對帳" in _names
    assert ("對帳", "extra") in _UNIFIED_FRONT


def test_reconcile_column_flows_to_batch_schema():
    """對帳欄自動出現在批次寬表 schema(BATCH_UNIFIED_COLUMNS 由 _UNIFIED_FRONT 派生)。"""
    from ui.helpers.fund_grp_health.unified import BATCH_UNIFIED_COLUMNS
    assert "對帳" in BATCH_UNIFIED_COLUMNS


# ── 吃本金欄 drift-lock(防空白變體重複)────────────────────────────────
def test_single_eat_column_in_unified():
    """合併大表只准出現 **1 個**吃本金欄 —— 目前靠 base 版('吃本金燈號 (1Y · )')唯一入 front,
    div 端 no-space 變體不在 _UNIFIED_FRONT 故被濾掉。任何人若把兩處空白對齊 / 把變體加進 front,
    本測試即 fail(§1:把 whitespace 被動去重從 silent 轉 loud)。"""
    from ui.helpers.fund_grp_health.unified import _BATCH_BASE_KEYS, _unified_columns
    cols, _ = _unified_columns(list(_BATCH_BASE_KEYS))
    _eat = [c for c in cols if "吃本金" in c]
    assert len(_eat) == 1, f"合併表應只有 1 個吃本金欄,實際 {_eat}"
    assert _eat[0] == "吃本金燈號 (1Y · )"
