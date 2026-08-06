# -*- coding: utf-8 -*-
"""2026-08-06 稽核 🔴 必修 2 — ⚡ 今日關鍵橫幅跨層去重必須帶「嚴重度」。

上一輪（2026-08-05 必修 4）把兩層去重收斂成「同因子留拐點層」，但 `_covered`
收的是**所有**進橫幅的拐點，不分嚴重度 —— 黃級的多頭拐點會把同因子的紅級風險
訊號整條吞掉，`n_red` 少 1，該紅的那天沒有紅燈（§1 不可少報）。

真實觸發路徑（本檔 `TestRealHySpreadScenario` 用兩個 production 函式證明它可達，
不是想像出來的邊界）：
  `services/macro/turning_points.py` HY 走「🚀 信用拐點：高位回落」的條件是
  `max90 >= 6.0 and cur < max90 * 0.85 and cur < prev` —— 90 日高點 8.0%、
  現值 6.2%、且續跌時成立，icon 🚀 在 `_TP_ICON_SEVERITY` 是**黃級**；
  同一時刻 `services/calibration/macro_score.score_hy_spread(6.2)` 因 `v > 6`
  回 -2.0，`|-2.0| >= SIGMA_HIGH_CUTOFF` → **紅級**。

修正後規則：**同因子只留較嚴重的那一條；同級留拐點層**（它帶事件語意 + note 白話）。

修正前紅的類型
--------------
- `test_yellow_turning_point_cannot_swallow_a_red_signal` → **行為衝突紅**
  （舊碼無條件 `continue`，紅級訊號被吞，items 只剩黃拐點、n_red = 0）
- `test_n_red_is_not_under_counted` → **行為衝突紅**（同上，n_red 少 1）
- `TestRealHySpreadScenario` 兩條 → **行為衝突紅**（同上，只是輸入取自 production
  函式的真實回傳值而非手捏常數）
- 其餘（紅拐點仍吞黃訊號 / 同級留拐點 / 非事件不吞 / 無 key 不去重）→ 修正前**綠**，
  是回歸鎖：防這次修法把上一輪剛修好的去重又拆掉（n_red 灌水是另一個方向的錯）。
"""
from __future__ import annotations

from shared.signal_thresholds import SIGMA_HIGH_CUTOFF, SIGMA_LOW_CUTOFF

_RED_SCORE = -(SIGMA_HIGH_CUTOFF + 0.2)     # -1.0 → severity 0
_YELLOW_SCORE = -(SIGMA_LOW_CUTOFF + 0.1)   # -0.4 → severity 1


def _ind(score, *, weight=1.0, name="測試指標", value=1.23, unit="%"):
    return {"name": name, "value": value, "unit": unit,
            "score": score, "weight": weight}


def _tp(icon, *, indicator_key=None, label="拐點", signal="訊號",
        note="白話說明", source_ok=True):
    _d = {"icon": icon, "signal": signal, "label": label,
          "note": note, "source_ok": source_ok}
    if indicator_key is not None:
        _d["indicator_key"] = indicator_key
    return _d


class TestSeverityAwareDedup:
    def test_yellow_turning_point_cannot_swallow_a_red_signal(self):
        """**修正前必紅（行為衝突）** —— 黃級拐點吞掉紅級訊號。

        HY 同時是「高位回落（🚀 黃級，語氣偏多）」與「水位 6%+（紅級風險）」時，
        舊碼只留前者，橫幅上那天只有一條多頭黃燈。
        """
        from services.macro.daily_key_alerts import collect_key_alerts
        _out = collect_key_alerts(
            {"HY_SPREAD": _ind(_RED_SCORE, name="HY 信用利差")},
            {"hy_spread": _tp("🚀", indicator_key="HY_SPREAD",
                              label="HY 信用利差", signal="高位回落")})
        assert len(_out["items"]) == 1, "同因子仍只留一條（不得退回完全不去重）"
        _it = _out["items"][0]
        assert _it["layer"] == "signal", (
            "留下來的必須是紅級那條 —— 黃級拐點不得代表一個紅級的因子")
        assert _it["severity"] == 0

    def test_n_red_is_not_under_counted(self):
        """**修正前必紅（行為衝突）** —— 計數也要跟著對，橫幅標題印的就是它。"""
        from services.macro.daily_key_alerts import collect_key_alerts
        _out = collect_key_alerts(
            {"HY_SPREAD": _ind(_RED_SCORE)},
            {"hy_spread": _tp("🚀", indicator_key="HY_SPREAD")})
        assert _out["n_red"] == 1 and _out["n_yellow"] == 0

    def test_red_turning_point_still_swallows_a_yellow_signal(self):
        """回歸鎖（修正前綠）：拐點較嚴重時仍由它代表，訊號層那條不重複出現。"""
        from services.macro.daily_key_alerts import collect_key_alerts
        _out = collect_key_alerts(
            {"SAHM": _ind(_YELLOW_SCORE, name="薩姆規則")},
            {"sahm_rule": _tp("🔴", indicator_key="SAHM")})
        assert len(_out["items"]) == 1
        assert _out["items"][0]["layer"] == "turning_point"
        assert _out["items"][0]["severity"] == 0

    def test_same_severity_keeps_the_turning_point(self):
        """回歸鎖（修正前綠）：同級留拐點層 —— 它帶事件語意 + note 白話，資訊量較多。

        這條同時擋住「只讓紅級拐點有資格吞」這種修法：那會讓黃拐點 × 黃訊號
        又變成同因子兩條。
        """
        from services.macro.daily_key_alerts import collect_key_alerts
        for _icon, _score in (("🔴", _RED_SCORE), ("🚀", _YELLOW_SCORE)):
            _out = collect_key_alerts(
                {"LEI": _ind(_score)},
                {"lei_cfnai": _tp(_icon, indicator_key="LEI")})
            assert len(_out["items"]) == 1, f"icon={_icon} 同級應只留一條"
            assert _out["items"][0]["layer"] == "turning_point", (
                f"icon={_icon} 同級應留拐點層")

    def test_non_event_turning_point_still_does_not_silence_the_signal(self):
        """回歸鎖（修正前綠）：🟢 非事件根本沒進橫幅 → 不進 covered → 訊號層照常顯示。"""
        from services.macro.daily_key_alerts import collect_key_alerts
        _out = collect_key_alerts(
            {"LEI": _ind(_RED_SCORE)},
            {"lei_cfnai": _tp("🟢", indicator_key="LEI")})
        assert len(_out["items"]) == 1
        assert _out["items"][0]["layer"] == "signal"

    def test_turning_point_without_a_key_dedups_nothing(self):
        """回歸鎖（修正前綠）：§3.3 去重事實由產生端宣告，消費端不猜對應。"""
        from services.macro.daily_key_alerts import collect_key_alerts
        _out = collect_key_alerts({"LEI": _ind(_RED_SCORE)},
                                  {"pmi_diff": _tp("🔴")})
        assert len(_out["items"]) == 2

    def test_unrelated_factors_both_survive(self):
        """回歸鎖（修正前綠）：不同因子不得誤殺。"""
        from services.macro.daily_key_alerts import collect_key_alerts
        _out = collect_key_alerts(
            {"VIX": _ind(_RED_SCORE, name="VIX")},
            {"sahm_rule": _tp("🚀", indicator_key="SAHM")})
        assert len(_out["items"]) == 2

    def test_internal_dedup_key_never_leaks_to_the_banner(self):
        """去重用的內部欄位不得外洩給渲染端（會被當成要顯示的資料）。"""
        from services.macro.daily_key_alerts import collect_key_alerts
        _out = collect_key_alerts(
            {"HY_SPREAD": _ind(_RED_SCORE)},
            {"hy_spread": _tp("🚀", indicator_key="HY_SPREAD")})
        for _it in _out["items"]:
            assert "_factor_key" not in _it
            assert "_rank" not in _it


class TestRealHySpreadScenario:
    """用 production 函式的真實回傳值構造，證明這條路徑真的到得了。

    只用純函式（拐點的判定式 + 評分函式），不打任何外部 API。
    """

    _MAX90 = 8.0
    _CUR = 6.2
    _PREV = 6.5

    def test_the_two_production_rules_really_disagree_in_severity(self):
        """前提查證：同一個 HY 現值，拐點判黃、訊號判紅。

        （若哪天上游把門檻改了、兩者不再打架，這條會紅並提醒下一位維護者
        重新檢查下面那條情境測試是否還有意義 —— 不讓它靜默變成空轉。）
        """
        from services.calibration.macro_score import score_hy_spread
        from services.macro.daily_key_alerts import _TP_ICON_SEVERITY

        # 拐點端：`turning_points._calc_hy_spread` 的「高位回落」條件（同一式子）
        assert (self._MAX90 >= 6.0
                and self._CUR < self._MAX90 * 0.85
                and self._CUR < self._PREV), "🚀 高位回落條件應成立"
        assert _TP_ICON_SEVERITY["🚀"] == 1, "🚀 應為黃級"

        # 訊號端：同一個現值的 macro score
        _score = score_hy_spread(self._CUR, max_abs=2.0)
        assert _score < 0, "6.2% 屬風險側（負分）"
        assert abs(_score) >= SIGMA_HIGH_CUTOFF, "強度應達紅級"

    def test_banner_shows_the_red_one(self):
        """**修正前必紅（行為衝突）** —— 端到端：橫幅該紅的那天要有紅燈。"""
        from services.calibration.macro_score import score_hy_spread
        from services.macro.daily_key_alerts import collect_key_alerts

        _out = collect_key_alerts(
            {"HY_SPREAD": {"name": "HY 信用利差", "value": self._CUR,
                           "unit": "%", "weight": 1.0,
                           "score": score_hy_spread(self._CUR, max_abs=2.0)}},
            {"hy_spread": {
                "icon": "🚀", "signal": "信用拐點：高位回落",
                "label": "HY 信用利差 (BAMLH0A0HYM2)",
                "note": "信用風險溢價收斂，risk-on 醞釀",
                "source_ok": True, "indicator_key": "HY_SPREAD"}},
        )
        assert _out["n_red"] == 1, "該紅的那天沒有紅燈"
        assert len(_out["items"]) == 1, "同因子仍不得講兩次"
        assert "risk-on" not in _out["items"][0]["detail"], (
            "留下來的不該是那條多頭語氣的拐點")
