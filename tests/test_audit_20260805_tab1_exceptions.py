"""2026-08-05 F3 — Tab① 總表 ③ 例外層的死分支修正 + 詳細區指南針位置。

承接 `test_audit_20260805_tab1_summary.py`(守四層存在與順序)與
`test_audit_20260805_evidence_notes.py`(守 ② 說明欄),本檔守兩件事:

  🔴 必修 1 — ③「例外」層的條件原本是「`systemic_risk_data` 有沒有東西」。
              但服務層 `detect_systemic_risk()` **恆回非空 dict**,而載入成功
              時它一定被寫進 session → 條件恆真 → 平靜的日子「③ 例外」底下
              永遠掛著一條「風險最低級」,而該層自己的契約寫的是「沒有例外時
              誠實說沒有,不硬擠內容」(§1)。「沒有例外」那條敘述只有在新聞
              掃描整個炸掉時才跑得到 = 死分支。
              把「沒事」放進「例外」欄位 → 這一層永遠有內容 → 使用者學會忽略它。

  🟡 建議 6 — 🧭 總經指南針原本擋在詳細區開頭,但它無快取時整塊只顯示
              「請按右上按鈕載入」;使用者剛按過「載入總經資料」、VIX 已經在
              ② 依據表裡,詳細區第一句話卻要他再按一次抓 VIX。
              且 ② 表沒有任何一列指向它。下移到 🌳 長期座標之後。

⚠️ 測試自身可執行性(`PROCESS.md §4`):本檔**不寫任何 importorskip、不 skip**。
   streamlit / pandas 是本 repo 硬依賴,缺件時本檔應該紅,而不是製造「有測試
   守著」的假象。

⚠️ 位置類斷言一律走 **AST + lineno**,不切原始碼字串比對:註解裡提到區塊名
   會讓 `index()` 提前命中,使斷言變成恆真的假通過(本 repo 已踩過同型陷阱兩次)。

每條 test 標明「修正前紅在哪」。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_TAB1 = _ROOT / "ui" / "tab1_macro.py"

# 三層標題的**前綴**(不含破折號後的副標:副標是文案,隨時可能改字)
_H_L3 = 'st.markdown("### ③ 例外'
_H_L4 = 'st.markdown("### ④ 可信度'

# 平靜的一天:風險最低級 + 兩個桶都綠
_CALM_RISK = {"risk_level": "LOW", "risk_score": 0, "risk_icon": "✅",
              "advice": "新聞面暫無系統性異常，維持既有配置策略"}
_CALM_BUCKETS = {
    "inflection": {"level": "green", "emoji": "🟢", "label": "拐點警報",
                   "headline": "全綠"},
    "news":       {"level": "green", "emoji": "🟢", "label": "市場新聞",
                   "headline": "無系統性新聞"},
}


def _fn_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    return str(getattr(call.func, "attr", ""))


def _calls(fname: str) -> list:
    _tree = ast.parse(_TAB1.read_text(encoding="utf-8"))
    return [n for n in ast.walk(_tree)
            if isinstance(n, ast.Call) and _fn_name(n) == fname]


def _line_of(marker: str) -> int:
    _src = _TAB1.read_text(encoding="utf-8")
    return _src[:_src.index(marker)].count("\n") + 1


def _safe_section_arg_lines(fname: str) -> list:
    """v19.429 §1 區塊隔離後,section renderer 的渲染點從 `render_x(...)`
    變成 `_safe_section("標籤", render_x, ...)` 的**引數** —— 是 ast.Name
    不是 ast.Call,`_calls()` 掃不到。

    只認 `_safe_section` 的引數位置,**不**掃全檔 ast.Name:後者會命中
    import alias 等非渲染點,「恰好一處」會失去鑑別力。
    """
    _tree = ast.parse(_TAB1.read_text(encoding="utf-8"))
    return [_a.lineno
            for _n in ast.walk(_tree)
            if isinstance(_n, ast.Call) and _fn_name(_n) == "_safe_section"
            for _a in _n.args
            if isinstance(_a, ast.Name) and _a.id == fname]


def _sole_call_line(fname: str) -> int:
    """渲染點行號 —— 裸呼叫與 `_safe_section` 包裹形兩種都算。"""
    _lines = [_c.lineno for _c in _calls(fname)] + _safe_section_arg_lines(fname)
    assert len(_lines) == 1, f"{fname} 的渲染點應恰好一處,實際 {len(_lines)} 處"
    return _lines[0]


# ══════════════════════════════════════════════════════════════
# 🔴 必修 1 — 例外層只列真的該警覺的
# ══════════════════════════════════════════════════════════════
class TestExceptionLayerOnlyListsRealExceptions:
    def test_calm_day_yields_no_exception_lines(self):
        """**修正前必紅** —— 修正前條件只判「有沒有資料」,平靜的一天照樣
        產出一條新聞風險。回傳空 list 才走得到「沒有例外」那條敘述。"""
        from ui.tab1_macro import _exception_lines
        assert _exception_lines(_CALM_RISK, _CALM_BUCKETS) == []

    def test_alerting_risk_level_is_listed(self):
        """反向:真的達到警覺等級就必須列出來(不能為了讓上一條過而整段拿掉)。"""
        from ui.tab1_macro import _NEWS_RISK_ALERT_LEVELS, _exception_lines
        for _lvl in _NEWS_RISK_ALERT_LEVELS:
            _srd = dict(_CALM_RISK, risk_level=_lvl, risk_score=12, risk_icon="🚨")
            _lines = _exception_lines(_srd, _CALM_BUCKETS)
            assert len(_lines) == 1, f"{_lvl} 沒被列進例外層"
            assert _lvl in _lines[0] and "12" in _lines[0]

    def test_yellow_or_red_bucket_is_listed_even_when_news_is_calm(self):
        """桶警戒與新聞風險是兩件事,任一亮起都算例外。

        ⚠️ 2026-08-06 必修 5(**修正前必紅**,舊行為與斷言衝突):
        原本 ③ 把 ② 那一列的 `label` + `headline` **原字串**再印一次,而 ③ 就
        緊貼在 ② 表下方兩行 —— 同一句話上下相鄰出現兩次(user 原則 2)。
        現在改成一句「是哪幾列」的指路,桶名走 `BUCKET_META` SSOT。
        """
        from shared.macro_buckets import BUCKET_META
        from ui.tab1_macro import _exception_lines
        _face = f'{BUCKET_META["inflection"]["emoji"]} {BUCKET_META["inflection"]["title"]}'
        for _lvl in ("yellow", "red"):
            _b = {"inflection": dict(_CALM_BUCKETS["inflection"], level=_lvl,
                                     headline="CFNAI -0.85 衰退"),
                  "news": _CALM_BUCKETS["news"]}
            _lines = _exception_lines(_CALM_RISK, _b)
            assert len(_lines) == 1, "桶警戒應收斂成一句指路,不是逐桶各一條"
            assert _face in _lines[0], f"指路沒說是哪一列:{_lines[0]!r}"
            assert "CFNAI -0.85 衰退" not in _lines[0], (
                "② 那一列的讀數又被原字串抄了一次 —— 這正是必修 5 要消滅的重複")

    def test_bucket_pointer_names_come_from_the_ssot(self, monkeypatch):
        """§3.3:桶名走 `shared.macro_buckets.BUCKET_META`,③ 不得重打一份。
        改 SSOT 的桶名 → 指路必須跟著變。"""
        import shared.macro_buckets as _mb
        from ui.tab1_macro import _exception_lines
        monkeypatch.setitem(_mb.BUCKET_META, "news",
                            {"emoji": "🛎️", "title": "哨兵桶", "sub": "x"})
        _b = {"inflection": _CALM_BUCKETS["inflection"],
              "news": dict(_CALM_BUCKETS["news"], level="red")}
        assert "🛎️ 哨兵桶" in _exception_lines(_CALM_RISK, _b)[0]

    def test_both_alerting_buckets_collapse_into_one_pointer(self):
        """兩桶同時亮 → 仍然只有一句(③ 的職責是指路,不是重印 ② 的內容)。"""
        from ui.tab1_macro import _exception_lines
        _b = {k: dict(v, level="red") for k, v in _CALM_BUCKETS.items()}
        _lines = _exception_lines(_CALM_RISK, _b)
        assert len(_lines) == 1

    def test_missing_or_broken_inputs_do_not_fabricate_an_exception(self):
        """§1 邊界:沒資料 ≠ 有例外。None / 空 dict / 型別不對都回空 list,
        不得憑空生出一條警示。"""
        from ui.tab1_macro import _exception_lines
        for _srd in (None, {}, "boom", []):
            for _sum in (None, {}, "boom"):
                assert _exception_lines(_srd, _sum) == []

    def test_hint_text_is_not_retyped_in_this_layer(self, monkeypatch):
        """§3.3:指路字串必須走 `section_hint`(桶→區段名的鏡像表),
        本層不得抄第二份。改鏡像表 → 例外層文字必須跟著變。"""
        import ui.helpers.macro.beginner_view as _mbv
        from ui.tab1_macro import _exception_lines
        monkeypatch.setitem(_mbv._BUCKET_SECTION_HINT, "news", "🛎️ 哨兵段")
        _srd = dict(_CALM_RISK, risk_level="HIGH", risk_score=12)
        assert "🛎️ 哨兵段" in _exception_lines(_srd, _CALM_BUCKETS)[0]


class TestAlertLevelMirrorDoesNotDrift:
    """`_NEWS_RISK_ALERT_LEVELS` 是服務層等級字串的鏡像(等級由
    `services/macro/us_indicators.py` 產生,不在 Tab① 的所有權內)。
    本組**實際呼叫服務層**產生各級再比對 —— 服務層改名 / 增級,這裡就紅。"""

    _HOT_NEWS = [{"title": "Lehman-style default sparks contagion",
                  "summary": "bank run and bankruptcy fears"}]

    def test_quiet_news_produces_a_level_that_is_not_an_alert(self):
        """空新聞 → 最低級,且該級**不得**在警覺集合裡(否則死分支回來了)。"""
        from services.macro.us_indicators import detect_systemic_risk
        from ui.tab1_macro import _NEWS_RISK_ALERT_LEVELS
        _srd = detect_systemic_risk([])
        assert _srd, "服務層回空 dict —— 原本的「有沒有資料」條件就不會恆真了"
        assert _srd["risk_level"] not in _NEWS_RISK_ALERT_LEVELS

    def test_every_non_quiet_level_the_service_emits_is_covered(self, monkeypatch):
        """服務層能產生的兩個非最低級都必須在鏡像集合裡,且集合不多不少。

        兩級用調門檻的方式逼出來(同 `test_macro_score_v2_audit` 既有手法),
        不依賴關鍵字權重表的實際數值。
        """
        import services.macro.us_indicators as _ui
        from ui.tab1_macro import _NEWS_RISK_ALERT_LEVELS
        _quiet = _ui.detect_systemic_risk([])["risk_level"]
        _top = _ui.detect_systemic_risk(self._HOT_NEWS)["risk_level"]
        monkeypatch.setattr(_ui, "_NEWS_RISK_HIGH", 10_000)
        monkeypatch.setattr(_ui, "_NEWS_RISK_MED", 1)
        _mid = _ui.detect_systemic_risk(self._HOT_NEWS)["risk_level"]
        assert len({_quiet, _top, _mid}) == 3, "服務層等級數變了,鏡像須同步"
        assert set(_NEWS_RISK_ALERT_LEVELS) == {_top, _mid}

    def test_predicate_reads_the_mirror_not_a_second_copy(self, monkeypatch):
        """§3.3 的真檢查:把鏡像換掉,判讀必須跟著變(有人在函式裡又寫死一份
        等級字串 → 這條紅)。"""
        import ui.tab1_macro as _t1
        monkeypatch.setattr(_t1, "_NEWS_RISK_ALERT_LEVELS", ("SENTINEL",))
        assert _t1._systemic_risk_is_alerting({"risk_level": "SENTINEL"})
        assert not _t1._systemic_risk_is_alerting({"risk_level": "HIGH"})


class TestExceptionLayerIsWiredUp:
    def test_layer_three_actually_calls_the_judge(self):
        """接線(`PROCESS.md §4`):判讀寫得再對,沒被 ③ 這一層呼叫就是 0 consumer。
        **修正前必紅**(函式不存在)。用 AST + lineno,註解提到函式名不會假通過。"""
        _lo, _hi = _line_of(_H_L3), _line_of(_H_L4)
        assert [c for c in _calls("_exception_lines") if _lo < c.lineno < _hi], (
            "③ 例外層沒呼叫例外判讀 —— 條件又回到原地了")

    def test_the_no_exception_branch_is_reachable(self):
        """死分支的結構檢查:③ 層裡必須有一個 `if <判讀結果>: … else: …`,
        且 else 分支有輸出。修正前那個 `if` 判的是 session 裡的原始 dict
        (恆真),else 永遠跑不到。"""
        _tree = ast.parse(_TAB1.read_text(encoding="utf-8"))
        _lo, _hi = _line_of(_H_L3), _line_of(_H_L4)
        _calls_in_range = [c for c in _calls("_exception_lines")
                           if _lo < c.lineno < _hi]
        assert _calls_in_range, "③ 例外層沒呼叫例外判讀"
        _names = {t.id for n in ast.walk(_tree) if isinstance(n, ast.Assign)
                  and _lo < n.lineno < _hi
                  and isinstance(n.value, ast.Call)
                  and _fn_name(n.value) == "_exception_lines"
                  for t in n.targets if isinstance(t, ast.Name)}
        assert _names, "例外判讀的結果沒被接住,不可能拿來分支"
        _ifs = [n for n in ast.walk(_tree) if isinstance(n, ast.If)
                and _lo < n.lineno < _hi
                and isinstance(n.test, ast.Name) and n.test.id in _names
                and n.orelse]
        assert _ifs, "沒有以判讀結果分支的 if/else —— 「沒有例外」那條走不到"


# ══════════════════════════════════════════════════════════════
# 🟡 建議 6 — 指南針下移到 🌳 長期座標之後
# ══════════════════════════════════════════════════════════════
class TestCompassRemoved:
    """2026-08-06 必修 6 —— 指南針從「下移一段」升級為「整塊移除」。

    原本這一組守的是它的**位置**(在 🌳 長期之後、📈 中期之前)。查證後
    三張卡在 🎯 短線雷達全部有現成的燈,且它自己還要再按一次按鈕才有資料
    → user 原則 2 + 原則 3,整塊拿掉。位置守衛隨之改成**不存在守衛**。
    刪除的完整殘留掃描(ui/ + services/ + app.py)在
    `test_audit_20260805_tab1_summary.py::TestSectionHints`;這裡只釘 Tab① 本身。
    """

    def test_tab1_no_longer_renders_the_compass(self):
        """**修正前必紅**(舊行為與斷言衝突,非 ImportError):
        修正前 `ui/tab1_macro.py` 詳細區有 `_rmc()` 這個呼叫節點。
        用 AST 掃呼叫節點 —— 註解裡提到指南針的沿革不會造成假紅。"""
        assert not _calls("_rmc"), "Tab① 仍在呼叫指南針"
        assert not _calls("render_macro_compass"), "Tab① 仍在呼叫指南針"

    def test_the_two_neighbouring_sections_are_untouched(self):
        """刪錯東西的防護:它上下那兩段(🌳 長期 / 📈 中期)必須原樣還在,
        且順序不變 —— 移除的只有夾在中間的指南針。"""
        assert (_sole_call_line("render_long_term_section")
                < _sole_call_line("render_mid_cycle_section"))

    def test_section_walk_caption_does_not_mention_the_compass(self):
        """回歸:② 表下那行「往下捲依序是…」只列四時域四段且從桶對照表導出,
        所以搬動指南針不會讓它過期。若日後有人把指南針寫進那份目錄,
        這條會提醒他:那份目錄就變成會隨版面漂移的鏡像了。"""
        from ui.helpers.macro.beginner_view import _section_walk
        assert "指南針" not in _section_walk()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
