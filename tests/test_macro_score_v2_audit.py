"""2026-08-05 稽核 — 評分函式解析度 / HY 上緣 / CPI 中間帶 / Fed 標籤 / 新聞門檻 SSOT。

對應稽核四項必修中屬本 Coder 所有權的部分:
  必修 1(部分)— `detect_systemic_risk` HIGH/MEDIUM 門檻由 inline 10/5 收 SSOT
  必修 2(部分)— 淨流動性 desc 附「誰在抽水」分解,不再讓畫面被讀成「急速縮表」
  必修 3        — PMI 階梯 → 連續 tanh(旗標控制)
  必修 4        — HY OAS 極緊上緣罰則 + CPI 中間帶遞減罰則(旗標控制)

╔══════════════════════════════════════════════════════════════════════════╗
║ 每個 class 的「修正前會不會紅」標註在各自 docstring。整體規則:            ║
║   - 凡 import `score_pmi` / `score_hy_spread` / `score_cpi` /            ║
║     `_net_liq_decomposition` / `MACRO_SCORE_V2_FLAGS` 的 → **修正前紅**   ║
║     (符號不存在,collection error)。                                      ║
║   - 「接線測試」(TestWiring / test_*_reaches_*) 特別設計成:即使產生端     ║
║     完全正確、但沒接進 production 路徑 → **會紅**(PROCESS.md §4)。       ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

import inspect
import math

import pandas as pd
import pytest

from services.calibration.macro_score import (
    score_cpi,
    score_hy_spread,
    score_pmi,
)
from shared.macro_thresholds_v2 import (
    CPI_YOY_THRESHOLDS as _CPI_THR,
    HY_SPREAD_THRESHOLDS as _HY_THR,
    PMI_THRESHOLDS as _PMI_THR,
)
from shared.signal_thresholds import MACRO_SCORE_V2_FLAGS

_TOL = 1e-9   # §4.3 浮點禁 ==,一律走 math.isclose


@pytest.fixture
def flags_on(monkeypatch):
    """把三個 v2 旗標一次打開;離開測試自動還原(monkeypatch.setitem)。"""
    def _on(*names):
        for _n in names:
            monkeypatch.setitem(MACRO_SCORE_V2_FLAGS, _n, True)
    return _on


# ══════════════════════════════════════════════════════════════════
# 0. 產線預設 — 旗標必須全 OFF(未經 user 拍板不得改變投資結論)
# ══════════════════════════════════════════════════════════════════
class TestDefaultsAreOff:
    """修正前:紅(常數不存在)。修正後:綠。

    這條的價值在**未來**:若有人「順手」把旗標預設打開,等於未經 user 拍板
    就改動所有歷史分數與位階建議 → 立刻紅。
    """

    def test_all_v2_flags_default_false(self):
        assert MACRO_SCORE_V2_FLAGS == {
            "pmi_continuous": False,
            "hy_complacency": False,
            "cpi_graded": False,
        }


# ══════════════════════════════════════════════════════════════════
# 1. Legacy 逐點等值 — 旗標 OFF 時,新函式必須與稽核前的 inline 三元式完全相同
# ══════════════════════════════════════════════════════════════════
class TestLegacyParity:
    """修正前:紅(函式不存在)。

    這是「重構不改行為」的保證:三個 scorer 是從 `fetch_all_indicators` 與
    `FACTORS` 兩處 inline 三元式收編而來,旗標 OFF 必須逐點還原原式。
    """

    @pytest.mark.parametrize("v", [30.0, 40.0, 44.9, 45.0, 46.0, 49.9,
                                   50.0, 55.6, 63.8, 70.0])
    def test_pmi_ladder_unchanged(self, v):
        _old = 2 if v >= 50 else (-2 if v < 45 else -1)
        assert math.isclose(score_pmi(v, max_abs=2.0), _old, abs_tol=_TOL)

    @pytest.mark.parametrize("v", [1.0, 2.41, 2.78, 3.0, 3.99, 4.0,
                                   5.0, 6.0, 6.01, 12.0])
    def test_hy_ladder_unchanged(self, v):
        _old = 2 if v < 4 else (-2 if v > 6 else 0)
        assert math.isclose(score_hy_spread(v, max_abs=2.0), _old, abs_tol=_TOL)

    @pytest.mark.parametrize("v", [-1.0, 0.5, 1.0, 1.5, 2.49, 2.5, 3.0,
                                   3.46, 4.0, 4.01, 9.0])
    def test_cpi_ladder_unchanged(self, v):
        _old = 1 if 1 < v < 2.5 else (-1 if v > 4 else 0)
        assert math.isclose(score_cpi(v, max_abs=1.0), _old, abs_tol=_TOL)


# ══════════════════════════════════════════════════════════════════
# 2. 必修 3 — PMI 連續函數
# ══════════════════════════════════════════════════════════════════
class TestPmiContinuous:
    """修正前:紅(旗標與 continuous_scale 皆不存在)。"""

    def test_scale_is_derived_from_ssot_not_a_new_magic_number(self):
        """分母 5 必須是 (expansion_above − recession_below) 推導,不是新常數。

        這條同時是漂移鎖:未來若有人改 50 / 45,連續版尺度自動跟著走。
        """
        _sf = _PMI_THR["score_function"]
        assert math.isclose(
            _sf["continuous_scale"],
            _sf["expansion_above"] - _sf["recession_below"], abs_tol=_TOL)
        assert math.isclose(_sf["continuous_scale"], 5.0, abs_tol=_TOL)

    def test_zero_at_expansion_line(self, flags_on):
        """v = 50 → 0,與階梯的翻正點對齊(不引入新的中性點)。"""
        flags_on("pmi_continuous")
        assert math.isclose(score_pmi(50.0, max_abs=2.0), 0.0, abs_tol=_TOL)

    def test_resolution_fixes_audit_case(self, flags_on):
        """稽核核心:錯值 63.8 與真值 55.6 在階梯下同分,連續版必須可分辨。"""
        _wrong_old = score_pmi(63.8, max_abs=2.0)
        _true_old = score_pmi(55.6, max_abs=2.0)
        assert math.isclose(_wrong_old, _true_old, abs_tol=_TOL), (
            "階梯下兩者本來就同分(這是被修的缺陷本身)")

        flags_on("pmi_continuous")
        _wrong_new = score_pmi(63.8, max_abs=2.0)
        _true_new = score_pmi(55.6, max_abs=2.0)
        assert not math.isclose(_wrong_new, _true_new, abs_tol=1e-3)
        # 公式對帳(主)+ 數值 sanity(輔,鬆容差避免手算尾數綁死測試)
        assert math.isclose(_true_new, 2 * math.tanh(5.6 / 5.0), abs_tol=1e-12)
        assert math.isclose(_wrong_new, 2 * math.tanh(13.8 / 5.0), abs_tol=1e-12)
        assert 1.61 < _true_new < 1.62
        assert 1.98 < _wrong_new < 1.99

    def test_no_cliff_at_the_50_line(self, flags_on):
        """49.9 → 50.1 的跳動:階梯 3 分 → 連續 0.08 分。"""
        _old_jump = abs(score_pmi(50.1, max_abs=2.0) - score_pmi(49.9, max_abs=2.0))
        assert math.isclose(_old_jump, 3.0, abs_tol=_TOL)

        flags_on("pmi_continuous")
        _new_jump = abs(score_pmi(50.1, max_abs=2.0) - score_pmi(49.9, max_abs=2.0))
        assert math.isclose(_new_jump, 0.08, abs_tol=1e-3)

    def test_bounded_and_monotonic(self, flags_on):
        """值域仍在 (−max_abs, +max_abs) 且單調遞增(不可翻轉方向)。"""
        flags_on("pmi_continuous")
        _grid = [30.0, 35.0, 40.0, 45.0, 48.0, 50.0, 52.0, 55.0, 60.0, 65.0, 70.0]
        _vals = [score_pmi(v, max_abs=2.0) for v in _grid]
        assert all(-2.0 < s < 2.0 for s in _vals)
        assert all(b > a for a, b in zip(_vals, _vals[1:]))

    def test_saturation_covers_sanity_range(self, flags_on):
        """PMI ≤35 / ≥65(§3.2 合理範圍邊緣)已接近飽和 → 常見值域不被壓平。"""
        flags_on("pmi_continuous")
        assert score_pmi(65.0, max_abs=2.0) > 1.98
        assert score_pmi(35.0, max_abs=2.0) < -1.98


# ══════════════════════════════════════════════════════════════════
# 3. 必修 4 — HY OAS 極緊上緣 / CPI 中間帶遞減
# ══════════════════════════════════════════════════════════════════
class TestHyComplacency:
    """修正前:紅(`complacency` section 不存在)。"""

    def test_threshold_registered_in_ssot_with_provenance(self):
        _c = _HY_THR["complacency"]
        assert math.isclose(_c["historic_low_pct"], 2.41, abs_tol=_TOL)
        assert _c["historic_low_date"] == "2007-06-05"
        assert math.isclose(_c["complacency_below"], 3.0, abs_tol=_TOL)
        # 自滿帶必須嚴格落在既有 tight_below 之內,否則會吃掉整個 +滿分帶
        assert _c["complacency_below"] < _HY_THR["score_function"]["tight_below"]
        assert _c["complacency_below"] > _c["historic_low_pct"]

    def test_audit_value_no_longer_full_score(self, flags_on):
        """2026-08-03 實測 2.78% —— 修正前拿滿分 +2,修正後降半檔 +1。"""
        assert math.isclose(score_hy_spread(2.78, max_abs=2.0), 2.0, abs_tol=_TOL)
        flags_on("hy_complacency")
        assert math.isclose(score_hy_spread(2.78, max_abs=2.0), 1.0, abs_tol=_TOL)

    def test_penalty_does_not_flip_negative(self, flags_on):
        """罰則只降半檔不翻負:極緊 ≠ 現在有事(§1 誠實,不誤報)。"""
        flags_on("hy_complacency")
        assert score_hy_spread(2.41, max_abs=2.0) > 0

    def test_healthy_tight_band_untouched(self, flags_on):
        """3.0 ~ 4.0 的「健康偏緊」仍是滿分,只有極緊帶降檔。"""
        flags_on("hy_complacency")
        assert math.isclose(score_hy_spread(3.5, max_abs=2.0), 2.0, abs_tol=_TOL)
        assert math.isclose(score_hy_spread(3.01, max_abs=2.0), 2.0, abs_tol=_TOL)
        # 邊界 3.0 本身屬自滿帶(<=)
        assert math.isclose(score_hy_spread(3.0, max_abs=2.0), 1.0, abs_tol=_TOL)

    def test_wide_side_unchanged(self, flags_on):
        flags_on("hy_complacency")
        assert math.isclose(score_hy_spread(6.5, max_abs=2.0), -2.0, abs_tol=_TOL)
        assert math.isclose(score_hy_spread(5.0, max_abs=2.0), 0.0, abs_tol=_TOL)


class TestCpiGraded:
    """修正前:紅(旗標不存在)。"""

    def test_middle_band_no_longer_free(self, flags_on):
        """2026-06 實測 +3.46% —— 修正前落在免罰走廊得 0,修正後 −0.64。"""
        assert math.isclose(score_cpi(3.46, max_abs=1.0), 0.0, abs_tol=_TOL)
        flags_on("cpi_graded")
        _exp = -(3.46 - 2.5) / (4.0 - 2.5)
        assert math.isclose(score_cpi(3.46, max_abs=1.0), _exp, abs_tol=1e-9)
        assert math.isclose(score_cpi(3.46, max_abs=1.0), -0.64, abs_tol=1e-9)

    def test_endpoints_continuous_with_legacy(self, flags_on):
        """端點必須接住 legacy:2.5 → 0、4.0 → −1(不製造新跳斷)。"""
        flags_on("cpi_graded")
        assert math.isclose(score_cpi(2.5, max_abs=1.0), 0.0, abs_tol=_TOL)
        assert math.isclose(score_cpi(4.0, max_abs=1.0), -1.0, abs_tol=_TOL)
        assert math.isclose(score_cpi(4.01, max_abs=1.0), -1.0, abs_tol=_TOL)

    def test_monotonic_decreasing_in_band(self, flags_on):
        flags_on("cpi_graded")
        _vals = [score_cpi(v, max_abs=1.0) for v in (2.5, 2.8, 3.1, 3.46, 3.8, 4.0)]
        assert all(b < a for a, b in zip(_vals, _vals[1:]))

    def test_ideal_and_deflation_bands_untouched(self, flags_on):
        flags_on("cpi_graded")
        assert math.isclose(score_cpi(2.0, max_abs=1.0), 1.0, abs_tol=_TOL)
        assert math.isclose(score_cpi(0.5, max_abs=1.0), 0.0, abs_tol=_TOL)

    def test_thresholds_come_from_ssot(self):
        """遞減罰則的兩個端點必須是既有 SSOT,不得新增數字。"""
        _sf = _CPI_THR["score_function"]
        assert math.isclose(_sf["ideal_high"], 2.5, abs_tol=_TOL)
        assert math.isclose(_sf["elevated_above"], 4.0, abs_tol=_TOL)


# ══════════════════════════════════════════════════════════════════
# 4. 接線測試(PROCESS.md §4)— 「算對了但沒接出去」必須變紅
# ══════════════════════════════════════════════════════════════════
class TestWiringIntoProduction:
    """修正前:紅。

    設計判準(PROCESS.md §4):把 `us_indicators.py` 裡呼叫 scorer 的那一行
    改回 inline 三元式 → 上面所有純函式測試**仍然全綠**,只有本 class 會紅。
    """

    @staticmethod
    def _src() -> str:
        import services.macro.us_indicators as _ui
        return inspect.getsource(_ui)

    def test_fetch_all_indicators_calls_shared_scorers(self):
        _s = self._src()
        for _fn in ("_score_pmi(", "_score_hy_spread(", "_score_cpi("):
            assert _fn in _s, f"production 未接 {_fn} — 評分仍走各自的 inline 拷貝"

    def test_old_inline_ladders_removed(self):
        """舊 inline 三元式必須消失,否則會出現「兩份評分邏輯」再度漂移。"""
        _s = self._src()
        assert "score = 2 if v >= 50 else (-2 if v < 45 else -1)" not in _s
        assert "score=2 if v<4 else (-2 if v>6 else 0)" not in _s
        assert "score=1 if 1<v<2.5 else (-1 if v>4 else 0)" not in _s

    def test_calibration_replay_shares_same_implementation(self):
        """歷史 replay 的 FACTORS 也必須吃同一組函式(否則回測與產線不同源)。

        用行為而非字串比對:直接餵 FACTORS 的 scorer,斷言它跟共用函式同值,
        且旗標打開後兩邊一起變 —— 這比 grep 原始碼更難被繞過。
        """
        import services.calibration.macro_score as _ms
        for _fn, _shared, _w in ((_ms._s_pmi, score_pmi, 2.0),
                                 (_ms._s_hy_spread, score_hy_spread, 2.0),
                                 (_ms._s_cpi, score_cpi, 1.0)):
            for _v in (2.0, 2.78, 3.46, 45.0, 50.0, 55.6, 63.8):
                assert math.isclose(float(_fn(_v)),
                                    float(_shared(_v, max_abs=_w)), abs_tol=_TOL)

    def test_calibration_replay_follows_the_flag(self, flags_on):
        """旗標打開後,回測 replay 的 PMI 分數必須跟著變(否則兩邊會漂移)。"""
        import services.calibration.macro_score as _ms
        _before = float(_ms._s_pmi(55.6))
        flags_on("pmi_continuous")
        _after = float(_ms._s_pmi(55.6))
        assert not math.isclose(_before, _after, abs_tol=1e-3)

    def test_news_risk_thresholds_are_ssot_not_inline(self):
        _s = self._src()
        assert "_NEWS_RISK_HIGH" in _s and "_NEWS_RISK_MED" in _s
        assert "if total_score >= 10:" not in _s
        assert "elif total_score >= 5:" not in _s

    def test_news_risk_threshold_actually_consumed(self, monkeypatch):
        """行為層接線:把門檻調到天文數字 → 原本 HIGH 的輸入必須降級。

        若有人把 SSOT 常數 import 進來卻仍用 inline 10/5 判斷,這條會紅。
        """
        import services.macro.us_indicators as _ui
        _news = [{"title": "Lehman-style default sparks contagion",
                  "summary": "bank run and bankruptcy fears"}]
        assert _ui.detect_systemic_risk(_news)["risk_level"] == "HIGH"
        monkeypatch.setattr(_ui, "_NEWS_RISK_HIGH", 10_000)
        monkeypatch.setattr(_ui, "_NEWS_RISK_MED", 10_001)
        assert _ui.detect_systemic_risk(_news)["risk_level"] == "LOW"

    def test_net_liq_decomposition_reaches_desc(self):
        """必修 2:淨流動性分解必須真的接進 `_fedbs_desc`(不是算完丟掉)。"""
        _s = self._src()
        assert "_net_liq_decomposition(df, _df_rrp, _df_tga)" in _s
        assert "_fedbs_desc = f\"{_fedbs_desc}｜{_fedbs_decomp}\"" in _s
        # 文案本身必須先否定「數字轉負 = Fed 縮表」的誤讀
        assert "數字轉負≠Fed 縮表" in _s


# ══════════════════════════════════════════════════════════════════
# 5. 端到端 — 連續分數真的傳得到 calc_macro_phase(不被整數化 / 夾掉)
# ══════════════════════════════════════════════════════════════════
class TestPhaseAggregationPropagatesFractionalScore:
    """修正前:紅(score_pmi 不存在)。

    這條擋的是另一種「算對了但沒接出去」:scorer 回浮點,但聚合端若有
    `int()` / round 到整數 / 夾擠邊界寫錯,連續化就完全沒有效果。
    """

    @staticmethod
    def _phase(pmi_score: float) -> float:
        from services.macro.us_indicators import calc_macro_phase
        _ind = {
            "PMI": {"weight": 2, "score": pmi_score},
            # 中性填充,把權重總和撐到 20,避免單一指標讓分數飽和到 10
            "_filler_note": "meta key 不參與計算",
            "FILLER": {"weight": 18, "score": 0},
        }
        return float(calc_macro_phase(_ind)["score"])

    def test_continuous_pmi_moves_the_phase_score(self, flags_on):
        _ladder = self._phase(score_pmi(55.6, max_abs=2.0))
        flags_on("pmi_continuous")
        _cont = self._phase(score_pmi(55.6, max_abs=2.0))
        # 解析式:Δscore = 5 × Δearned_w / total_w = 5 × (1.61514 − 2) / 20
        assert math.isclose(_ladder, 5.5, abs_tol=1e-6)
        assert math.isclose(_cont, 5.4, abs_tol=1e-6)
        assert _cont < _ladder

    def test_meta_key_still_excluded(self):
        """順帶守 v19.404 的 meta 排除:`_filler_note` 不得灌水分母。"""
        assert math.isclose(self._phase(2.0), 5.5, abs_tol=1e-6)


# ══════════════════════════════════════════════════════════════════
# 6. 必修 2 — 淨流動性 YoY 分解(用稽核實抓的 FRED 三條原始數字)
# ══════════════════════════════════════════════════════════════════
def _weekly_df(first_value: float, last_value: float) -> pd.DataFrame:
    """2025-07-23 → 2026-07-29 週頻(54 點);除末筆外全為 first_value。

    刻意讓首筆落在 `最新日 − 365d`(= 2025-07-29)之前,as-of 回看才取得到它。
    """
    _idx = pd.date_range("2025-07-23", "2026-07-29", freq="7D")
    _vals = [first_value] * (len(_idx) - 1) + [last_value]
    return pd.DataFrame({"date": _idx, "value": _vals})


def _daily_df(first_value: float, last_value: float) -> pd.DataFrame:
    _idx = pd.date_range("2025-07-23", "2026-07-29", freq="D")
    _vals = [first_value] * (len(_idx) - 1) + [last_value]
    return pd.DataFrame({"date": _idx, "value": _vals})


class TestNetLiquidityDecomposition:
    """修正前:紅(`_net_liq_decomposition` 不存在)。

    數字來自稽核用 FRED 三條原始序列的獨立重算(非杜撰):
        WALCL  2026-07-29 = 6,738,190 百萬 / 2025-07-30 = 6,642,578 百萬
        TGA    2026-07-29 =   910,776 百萬 / 2025-07-30 =   370,507 百萬
        RRP    2026-07-29 =     2.576 十億 / 2025-07-30 =   155.481 十億
        ⇒ 淨流動性 5.824838T vs 6.116590T = −4.77%(與畫面分毫不差)
        ⇒ 但 Fed 資產毛額 YoY = +1.44%,跌幅幾乎全來自 TGA +5,403 億
    """

    @staticmethod
    def _decomp() -> str:
        from services.macro.us_indicators import _net_liq_decomposition
        return _net_liq_decomposition(
            _weekly_df(6_642_578.0, 6_738_190.0),   # WALCL(百萬)
            _daily_df(155.481, 2.576),              # RRP(十億)
            _weekly_df(370_507.0, 910_776.0),       # TGA(百萬)
        )

    def test_gross_walcl_is_positive_not_shrinking(self):
        """核心:敘述必須說得出「Fed 資產其實是增加的」。"""
        _s = self._decomp()
        assert "Fed資產 +1.44%" in _s, _s
        assert "+956 億" in _s, _s

    def test_tga_identified_as_the_drain(self):
        _s = self._decomp()
        assert "TGA +5,403 億(抽水)" in _s, _s

    def test_rrp_identified_as_release(self):
        _s = self._decomp()
        assert "RRP -1,529 億(釋水)" in _s, _s

    def test_missing_component_returns_empty_not_fabricated(self):
        """§1:任一組件缺 → 回空字串,不得編造分解數字。"""
        from services.macro.us_indicators import _net_liq_decomposition
        _empty = pd.DataFrame(columns=["date", "value"])
        _ok = _weekly_df(1.0, 2.0)
        assert _net_liq_decomposition(_empty, _ok, _ok) == ""
        assert _net_liq_decomposition(_ok, _empty, _ok) == ""
        assert _net_liq_decomposition(_ok, _ok, _empty) == ""
        assert _net_liq_decomposition(None, None, None) == ""

    def test_asof_lookback_is_backward_only(self):
        """§2.3 防 lookahead:as-of 回看只能取「截止日以前」已公布的值。"""
        from services.macro.us_indicators import _asof_year_ago
        _s = _weekly_df(100.0, 200.0).set_index("date")["value"]
        assert math.isclose(_asof_year_ago(_s), 100.0, abs_tol=_TOL)
        # 序列太短(只有 1 點)→ None,不猜
        _short = pd.Series([1.0], index=pd.to_datetime(["2026-07-29"]))
        assert _asof_year_ago(_short) is None
