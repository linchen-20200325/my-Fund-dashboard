"""v19.124 起 / v19.128 縮減 / 2026-08-05 F2 再縮 — 四時域 + 五桶 summary 邏輯測試。

驗證:
1. compute_four_horizon_summary / compute_five_bucket_summary 分級正確
2. 缺指標時 graceful(不 raise)
3. SSOT 閾值正確套用(SAHM 0.5 / CFNAI -0.7 / NEWS_SYSTEMIC_*_COUNT)

v19.128 刪除:render / 教室 / 章節內容守衛 tests(對應功能已從 production 移除)
2026-08-05 F2 刪除:三大紅綠燈那兩組 tests —— 被測函式本身已依
`PROCESS.md §4` 0-consumer 條款從 production 移除(它 production 0 caller,
唯一消費者就是這個檔)。**保護沒有變弱**:它與四時域 summary 重疊的三處判斷
(景氣 0-10 分級 / 警訊觸發 / SSOT 閾值套用)在本檔
`TestComputeFourHorizonSummary` 都有等價守衛,且那組守的是**真的在畫面上**的
那條路徑;測一個已刪除的函式沒有意義。
"""
from __future__ import annotations

import sys
import types



def _stub_streamlit():
    if "streamlit" in sys.modules and getattr(
        sys.modules["streamlit"], "_is_test_stub", False
    ):
        return
    _mod = types.ModuleType("streamlit")
    _mod._is_test_stub = True

    def _noop(*a, **k):
        return None

    def _ctx(*a, **k):
        class _Ctx:
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False
        return _Ctx()

    for _name in (
        "markdown", "caption", "divider", "warning", "info", "success",
    ):
        setattr(_mod, _name, _noop)
    _mod.expander = _ctx
    # v19.128 — render_four_horizon_bar 需 st.columns(int) 回傳 N 個 ctx managers
    _mod.columns = lambda spec, **k: [_ctx() for _ in range(spec if isinstance(spec, int) else len(spec))]

    class _SS(dict):
        def get(self, k, default=None):
            return super().get(k, default)
    _mod.session_state = _SS()
    sys.modules["streamlit"] = _mod


# v19.174:module-top stub call 拿掉 — 改由 conftest._switch_streamlit_module_per_test
# fixture per-test 裝(避免 stub 污染後續 collect 的 test,例如 AppTest)。
# _stub_streamlit()


# 2026-08-05 F2:`TestComputeTrafficLights`(13 條)+ `TestSSOTThresholdsApplied`
# (2 條)刪除 —— 被測的三大紅綠燈函式已從 production 移除(0 caller,見本檔
# docstring)。等價保護見下方 `TestComputeFourHorizonSummary`。


# ════════════════════════════════════════════════════════════════
# v19.128 — 四時域 summary 守衛
# ════════════════════════════════════════════════════════════════

class TestComputeFourHorizonSummary:
    """compute_four_horizon_summary 純函式守衛"""

    def test_empty_returns_4_buckets(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary({})
        assert set(r.keys()) == {"long", "mid", "short", "inflection"}
        for _k, _d in r.items():
            assert "level" in _d
            assert "label" in _d
            assert "headline" in _d
            assert "color" in _d
            assert "emoji" in _d

    def test_none_indicators_no_raise(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary(None, phase_info={"phase": "復甦", "score": 6.5})
        assert r["long"]["level"] == "green"  # score 6.5 → green

    def test_long_horizon_uses_phase_score(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        # score 高 → green
        r_g = compute_four_horizon_summary({}, phase_info={"phase": "擴張", "score": 7.0})
        assert r_g["long"]["level"] == "green"
        # score 低 → red
        r_r = compute_four_horizon_summary({}, phase_info={"phase": "衰退", "score": 2.0})
        assert r_r["long"]["level"] == "red"
        # score 中 → yellow
        r_y = compute_four_horizon_summary({}, phase_info={"phase": "減速", "score": 4.5})
        assert r_y["long"]["level"] == "yellow"

    def test_short_horizon_vix_panic_red(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary(
            {"VIX": {"value": 35.0}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["short"]["level"] == "red"
        assert "VIX" in r["short"]["headline"]

    def test_short_horizon_vix_warning_yellow(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary(
            {"VIX": {"value": 22.0}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["short"]["level"] == "yellow"

    def test_inflection_sahm_triggers_red(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary(
            {"SAHM": {"value": 0.55}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["inflection"]["level"] == "red"
        assert "薩姆" in r["inflection"]["headline"]

    def test_inflection_yield_inversion_yellow(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary(
            {"YIELD_10Y2Y": {"value": -0.5}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["inflection"]["level"] == "yellow"

    def test_inflection_two_warnings_escalate_to_red(self):
        """≥ 2 個 warning(無 trigger)→ 紅燈(多重警訊)"""
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary(
            {
                "YIELD_10Y2Y": {"value": -0.5},
                "YIELD_10Y3M": {"value": -0.3},
            },
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["inflection"]["level"] == "red"

    def test_mid_horizon_pmi_contraction(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary(
            {"PMI": {"value": 45.0}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["mid"]["level"] == "yellow"
        assert "PMI" in r["mid"]["headline"]

    def test_all_healthy_all_green(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary(
            {
                "VIX": {"value": 14.0},
                "HY_SPREAD": {"value": 3.0},
                "SAHM": {"value": 0.2},
                "YIELD_10Y2Y": {"value": 0.5},
                "PMI": {"value": 52.0},
                # ⚠️ 2026-08-05:CPI / 失業率 / 領先指標三顆的 key 全部改成
                # 服務層真的會寫入的那一個(原本餵的三個 key production 從不
                # 存在,這條「全綠」因此是靠 3 顆缺席指標拿到的,不是靠健康讀數)。
                # 領先指標另外指名移動平均那一欄 —— 官方衰退線是對它定義的。
                "CPI": {"value": 2.5},
                "UNEMPLOYMENT": {"value": 4.0},
                "LEI": {"value": 0.3, "ma3": 0.3},
            },
            phase_info={"phase": "擴張", "score": 6.5},
        )
        assert r["long"]["level"] == "green"
        assert r["mid"]["level"] == "green"
        assert r["short"]["level"] == "green"
        assert r["inflection"]["level"] == "green"

    # 2026-08-05 F1:`test_render_no_raise`(render_four_horizon_bar)刪除 ——
    # 該 renderer 已隨五桶 bar 一併移除,四時域一覽改由總表「② 依據」表承接。
    # 取代它的渲染守衛在 `tests/test_audit_20260805_tab1_summary.py`
    # (`TestEvidenceTableRender`),那裡用真 streamlit + monkeypatch 攔
    # `st.dataframe`,能驗到「表格真的收到 6 列」而不只是「沒 raise」。

    def test_ssot_thresholds_from_signal_thresholds(self):
        """確認用 SSOT(SAHM_RECESSION_THRESHOLD / CFNAI_RECESSION_THRESHOLD)而非 inline magic

        ⚠️ 2026-08-05:領先指標改餵服務層真實 key + 移動平均那一欄。
        `value` 故意放一個**不會觸發**的數 —— 若實作退回讀 `value`,本條會紅。
        """
        from shared.signal_thresholds import (
            CFNAI_RECESSION_THRESHOLD,
            SAHM_RECESSION_THRESHOLD,
        )
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        # 剛好 = SSOT 閾值 → 觸發
        r1 = compute_four_horizon_summary(
            {"SAHM": {"value": SAHM_RECESSION_THRESHOLD}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r1["inflection"]["level"] == "red"
        r2 = compute_four_horizon_summary(
            {"LEI": {"value": 0.5, "ma3": CFNAI_RECESSION_THRESHOLD}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r2["inflection"]["level"] == "red"


# ════════════════════════════════════════════════════════════════
# v19.146 — 五桶 summary 擴充(4-horizon + 📰 新聞)
# 守 SSOT 對齊 + 向下相容(4-horizon 仍可運作 + render fallback)
# ════════════════════════════════════════════════════════════════
class TestFiveBucketSummary:
    """compute_five_bucket_summary 守衛(計算層;渲染層見本檔末說明)"""

    def test_news_gray_when_news_items_none(self):
        """news_items=None → 第 5 桶 ⬜「未掃描」(對齊 Stock 未抓 RSS 狀態)。"""
        from ui.helpers.macro_beginner_view import compute_five_bucket_summary
        r = compute_five_bucket_summary({}, phase_info={}, news_items=None)
        assert "news" in r
        assert r["news"]["level"] == "gray"
        assert "⬜" in r["news"]["emoji"]

    def test_news_green_when_no_systemic_hit(self):
        """news_items 有資料但無 systemic → 🟢 無系統風險。"""
        from ui.helpers.macro_beginner_view import compute_five_bucket_summary
        items = [
            {"title": "Fed signals patience", "is_systemic": False},
            {"title": "Earnings beat", "is_systemic": False},
        ]
        r = compute_five_bucket_summary({}, phase_info={}, news_items=items)
        assert r["news"]["level"] == "green"
        assert "🟢" in r["news"]["emoji"]
        assert "2 則" in r["news"]["headline"]

    def test_news_yellow_on_one_systemic(self):
        """1 則 systemic → 🟡(對齊 SSOT NEWS_SYSTEMIC_YELLOW_COUNT=1)。"""
        from ui.helpers.macro_beginner_view import compute_five_bucket_summary
        items = [
            {"title": "Bank run risk warning", "is_systemic": True},
            {"title": "Earnings beat", "is_systemic": False},
        ]
        r = compute_five_bucket_summary({}, phase_info={}, news_items=items)
        assert r["news"]["level"] == "yellow"
        assert "🟡" in r["news"]["emoji"]
        assert "🚨" in r["news"]["headline"]

    def test_news_red_on_two_or_more_systemic(self):
        """≥2 則 systemic → 🔴(對齊 SSOT NEWS_SYSTEMIC_RED_COUNT=2)。"""
        from ui.helpers.macro_beginner_view import compute_five_bucket_summary
        items = [
            {"title": "War escalates", "is_systemic": True},
            {"title": "Major bank fails", "is_systemic": True},
            {"title": "VIX spikes", "is_systemic": True},
        ]
        r = compute_five_bucket_summary({}, phase_info={}, news_items=items)
        assert r["news"]["level"] == "red"
        assert "🔴" in r["news"]["emoji"]
        assert "系統性警報" in r["news"]["label"]

    def test_preserves_four_horizons(self):
        """v19.146 不破壞既有 4-horizon — 應仍含 long/mid/short/inflection 完整 dict。"""
        from ui.helpers.macro_beginner_view import compute_five_bucket_summary
        r = compute_five_bucket_summary(
            {"PMI": {"value": 45.0}},
            phase_info={"phase": "減速", "score": 4.0},
            news_items=None,
        )
        for k in ("long", "mid", "short", "inflection", "news"):
            assert k in r
            assert "level" in r[k]
            assert "label" in r[k]
            assert "emoji" in r[k]
            assert "color" in r[k]

    def test_ssot_thresholds_imported_not_hardcoded(self):
        """v19.146 應 import SSOT NEWS_SYSTEMIC_*_COUNT,非 inline 寫死。"""
        from shared.macro_buckets import (
            NEWS_SYSTEMIC_YELLOW_COUNT, NEWS_SYSTEMIC_RED_COUNT,
        )
        assert NEWS_SYSTEMIC_YELLOW_COUNT == 1
        assert NEWS_SYSTEMIC_RED_COUNT == 2


# 2026-08-05 F1:`TestFiveBucketBarRender`(五桶 bar 的 5 / 4 columns 守衛)刪除。
#
# 五桶 bar 的內容(桶數 / 燈 / 判讀 / 一句話)整批收進總表「② 依據」表格,
# `render_five_bucket_bar` 隨之成為 production 0 consumer 並依 `PROCESS.md §4`
# 移除 —— 測一個已刪除函式的 columns 數沒有意義。
#
# **保護沒有變弱**:對應守衛移到 `tests/test_audit_20260805_tab1_summary.py`,
# 且從「畫幾個 column」升級為「表格真的收到哪幾列、每列的值是不是來自 SSOT」:
#   - `test_rows_follow_bucket_order_and_include_all_buckets` — 5 桶一個不少
#   - `test_missing_news_bucket_just_drops_that_row`          — 4 桶時的降級
#   - `TestEvidenceTableRender`                               — 渲染端真的收到列
# 計算層 `compute_five_bucket_summary` 的測試(本檔 `TestFiveBucketSummary`)
# 完全保留,未受影響。
