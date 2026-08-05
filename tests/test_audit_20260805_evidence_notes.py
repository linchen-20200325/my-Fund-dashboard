"""2026-08-05 F2 — ② 依據表「說明欄」與表下註記的守衛。

承接 `tests/test_audit_20260805_tab1_summary.py`(那檔守「表存在 / 列齊 / 指路
不指到空氣」),本檔守**欄位有沒有履行欄名的承諾**,對應本輪稽核五項:

  🔴 必修 1 — 同一顆位階分數被兩套切點判讀,相隔兩行亮不同顏色 → 🌳 長期列
              的說明欄必須揭露差異,且兩組切點都從各自 SSOT f-string 進來。
  🔴 必修 2 — 欄名寫「這個數字怎麼讀」,但只有 🌳 長期列真的有說明,其餘四列
              填的是桶副標 → 四列都要說出該列讀數的判讀門檻,且門檻要**對得上
              當下實際顯示的那個指標**(讀數是動態的,先觸發者勝)。
  🟡 必修 3 — 綜合健康度的指路漏掉 ⚠️ 拐點,而權重最高的幾顆(殖利率差 ×2)
              細節正好住在那一段。
  🟡 建議 4 — 239 LOC 死碼移除(production 0 caller)。
  🟡 建議 5/6/7 — Z-Score 裝飾覆蓋率誠實揭露 / 表下補區塊順序目錄 /
              雷達圖警戒線與本表門檻的差異註記。

⚠️ 測試自身可執行性(`PROCESS.md §4`):本檔**不寫任何 importorskip、不 skip**。
   pandas / streamlit 是本 repo 硬依賴,缺件時本檔應該紅而不是製造「有測試守著」
   的假象。

⚠️ 接線驗證(`PROCESS.md §4`):`spec_key` 是這次新增的側車欄位。
   `TestNoteMatchesTheActualReading` 是它的接線測試 —— 產生端(compute 層)算得
   再對,只要 `build_evidence_rows` 沒把它讀出來(拿掉 `_how_to_read(...)` 那個
   引數),說明欄就退回桶副標,那一組立刻紅。只測產生端在本 repo 不算數。

每條 test 標明「修正前紅在哪」。
"""
from __future__ import annotations

import ast
import dataclasses
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_MIDCYCLE = _ROOT / "ui" / "tab1_macro_midcycle.py"

_PHASE = {"phase": "擴張", "score": 6.8}


def _rows(indicators=None, *, phase_info=None, news_items=None):
    from ui.helpers.macro.beginner_view import (
        build_evidence_rows,
        compute_five_bucket_summary,
    )
    _s = compute_five_bucket_summary(
        indicators or {},
        phase_info=_PHASE if phase_info is None else phase_info,
        news_items=news_items,
    )
    return build_evidence_rows(
        _s, composite_score=15.5, composite_icon="🟢",
        composite_level="極度樂觀", composite_action="多頭市場強勁",
        n_indicators=25)


def _note_col() -> str:
    """「說明」欄名從 SSOT 取(全形括號肉眼難辨,重打一次 = 埋假警報)。"""
    from ui.helpers.macro.beginner_view import EVIDENCE_COLUMNS
    return EVIDENCE_COLUMNS[3]


def _row(rows, face_fragment: str) -> dict:
    return next(r for r in rows if face_fragment in r["面向"])


# ══════════════════════════════════════════════════════════════
# 🔴 必修 1 — 兩套切點的差異必須揭露,且兩邊都吃 SSOT
# ══════════════════════════════════════════════════════════════
class TestPhaseCutoffDisclosure:
    def test_long_row_discloses_both_cutoff_sets(self):
        """**修正前必紅** —— 修正前 🌳 長期列的說明只有桶副標 + 位階尺度那句,
        完全沒提「① 結論燈用的是另一組切點」。位階落在 6.0~6.5 時
        ① 顯示 🟡 而本列顯示 🟢,使用者只能當成 bug。"""
        from services.macro.action_light import _BUY_SCORE_10, _HOLD_SCORE_10
        from ui.helpers.macro.beginner_view import (
            _MACRO_SCORE_DANGER_MAX,
            _MACRO_SCORE_HEALTHY_MIN,
        )
        _note = _row(_rows(), "長期")[_note_col()]
        for _v in (_MACRO_SCORE_HEALTHY_MIN, _MACRO_SCORE_DANGER_MAX,
                   _BUY_SCORE_10, _HOLD_SCORE_10):
            assert f"{float(_v):.1f}" in _note, (
                f"說明欄沒揭露切點 {_v} —— 兩把尺的差異又變成看不見的:{_note!r}")

    def test_conclusion_light_cutoff_is_read_not_retyped(self, monkeypatch):
        """§3.3 反捏造的**真檢查**:把結論燈的加碼門檻換掉,說明欄必須跟著變。

        若有人圖方便在文案裡寫死一份 6.5,這條會紅(說明欄仍印舊值)。
        **修正前必紅**(那句話整個不存在)。"""
        monkeypatch.setattr("services.macro.action_light._BUY_SCORE_10", 9.1)
        _note = _row(_rows(), "長期")[_note_col()]
        assert "9.1" in _note, f"結論燈門檻是寫死的第二份,不是讀 SSOT:{_note!r}"

    def test_own_cutoff_is_read_not_retyped(self, monkeypatch):
        """同上,反向守本表自己那組切點。"""
        import ui.helpers.macro.beginner_view as _mbv
        monkeypatch.setattr(_mbv, "_MACRO_SCORE_HEALTHY_MIN", 7.3)
        assert "7.3" in _row(_rows(), "長期")[_note_col()]

    def test_scale_note_survives_alongside_the_new_disclosure(self):
        """回歸:新增揭露不得把原本「位階 / 恆非負」那句擠掉
        (`test_audit_20260805_tab1_summary.py` 以它區分兩把尺)。"""
        from ui.helpers.macro.beginner_view import _SCALE_NOTE_PHASE
        assert _SCALE_NOTE_PHASE in _row(_rows(), "長期")[_note_col()]


# ══════════════════════════════════════════════════════════════
# 🔴 必修 2 — 四列說明欄要履行欄名,且對得上實際讀數(含接線驗證)
# ══════════════════════════════════════════════════════════════
class TestEveryRowExplainsItsNumber:
    def test_four_remaining_rows_say_more_than_the_bucket_subtitle(self):
        """**修正前必紅** —— 修正前 mid / short / inflection / news 的說明欄
        `== 桶副標`(「景氣循環 3-12 月」之類),讀數寫「PMI 48.5 收縮」而說明
        不告訴你 48.5 該怎麼讀。"""
        from ui.helpers.macro.beginner_view import _bucket_bar_cells
        _subs = {k: s for k, _t, s in _bucket_bar_cells(
            ("mid", "short", "inflection", "news"))}
        _r = _rows(news_items=[])
        for _key, _face in (("mid", "中期"), ("short", "短線"),
                            ("inflection", "拐點"), ("news", "新聞")):
            _note = _row(_r, _face)[_note_col()]
            assert _note.startswith(_subs[_key]), "副標不該被擠掉,只該被延長"
            assert _note != _subs[_key], (
                f"{_face} 這列的說明還是只有桶副標,欄名承諾沒履行:{_note!r}")


class TestNoteMatchesTheActualReading:
    """`spec_key` 側車的**接線測試**(`PROCESS.md §4`)。

    判準:把 `build_evidence_rows` 裡讀 `spec_key` 的那個引數拿掉,本組必須紅。
    拿掉後說明欄退回桶副標 → 下面每一條的 `in` 斷言都不成立。
    """

    def test_pmi_reading_gets_the_pmi_threshold(self):
        """**修正前必紅**。讀數是 PMI → 說明必須講 PMI 的門檻。"""
        from shared.macro_buckets import SPECS_BY_KEY
        _mid = _row(_rows({"PMI": {"value": 45.0}}), "中期")
        assert "PMI" in _mid["讀數"]
        assert SPECS_BY_KEY["pmi"].note in _mid[_note_col()]

    def test_cpi_reading_gets_the_cpi_threshold_not_pmi(self):
        """讀數欄是**動態**的(先觸發者勝)—— 同一列改成顯示 CPI 時,說明欄
        必須跟著換成 CPI 的門檻。寫死「PMI 50 是榮枯線」那種做法在這裡紅。

        ⚠️ 2026-08-05:輸入 key 改成**服務層真的會產生的那一個**。原本餵的是
        一個 production 從不存在的 key,等於只走了一條畫面永遠走不到的路
        (本 repo 病歷上重複出現的失效型態)。key 正確性由
        `test_audit_20260805_tab1_wiring.py` 的 key 漂移鎖獨立守著。
        """
        from shared.macro_buckets import SPECS_BY_KEY
        _mid = _row(_rows({"CPI": {"value": 5.5}}), "中期")
        assert "CPI" in _mid["讀數"]
        assert SPECS_BY_KEY["cpi_yoy"].note in _mid[_note_col()]
        assert SPECS_BY_KEY["pmi"].note not in _mid[_note_col()], (
            "說明欄講的是另一顆指標的門檻 —— 答非所問")

    def test_inflection_reading_gets_the_matching_threshold(self):
        """⚠️ 拐點列:讀數 CFNAI -0.80 → 說明要講 CFNAI 怎麼讀。
        這正是稽核點名的第二個例子。

        ⚠️ 2026-08-05:改餵**服務層真實的 key + 真實的欄位**。這顆的官方衰退線
        是對 3 月移動平均定義的,服務層把它另存一欄;餵當期值那一欄等於在測一條
        production 走不到、且口徑不對的路(§4.1)。
        """
        from shared.macro_buckets import SPECS_BY_KEY
        _inf = _row(_rows({"LEI": {"value": 0.1, "ma3": -0.85}}), "拐點")
        assert "CFNAI" in _inf["讀數"]
        assert SPECS_BY_KEY["cfnai"].note in _inf[_note_col()]

    def test_thresholds_are_read_from_registry_not_retyped(self, monkeypatch):
        """§3.3:門檻描述改在 registry,說明欄必須跟著變。
        有人把門檻文字抄一份到 UI 層 → 這條紅。"""
        from shared.macro_buckets import SPECS_BY_KEY
        _fake = dataclasses.replace(SPECS_BY_KEY["pmi"], note="XX 哨兵門檻 XX")
        monkeypatch.setitem(SPECS_BY_KEY, "pmi", _fake)
        _mid = _row(_rows({"PMI": {"value": 45.0}}), "中期")
        assert "XX 哨兵門檻 XX" in _mid[_note_col()]

    def test_short_row_has_a_threshold_even_when_green(self):
        """🎯 短線列全綠時讀數仍是數字(VIX 讀數),所以照樣指得出門檻,
        不該退回通用規則。"""
        from shared.macro_buckets import SPECS_BY_KEY
        _short = _row(_rows(), "短線")
        assert SPECS_BY_KEY["vix"].note in _short[_note_col()]

    def test_all_green_rows_explain_when_a_number_will_appear(self):
        """全綠時讀數是**狀態詞不是數字**(「三項皆健康」/「全綠」),
        此時說明欄答「什麼情況會變成數字」,而**不得**硬塞一個沒觸發的門檻
        (硬塞會讓讀者以為畫面正在講那一顆)。"""
        from shared.macro_buckets import SPECS_BY_KEY
        from ui.helpers.macro.beginner_view import _NO_SPEC_READ_RULE
        _r = _rows()
        for _face in ("中期", "拐點"):
            _note = _row(_r, _face)[_note_col()]
            assert _NO_SPEC_READ_RULE in _note
        assert SPECS_BY_KEY["pmi"].note not in _row(_r, "中期")[_note_col()]

    def test_unknown_spec_key_fails_loud(self):
        """§1:registry 查不到的 spec key 當場炸,不得在說明欄印一段指向
        不存在指標的門檻(同 `section_hint` 的既有處置)。"""
        from ui.helpers.macro.beginner_view import _how_to_read
        with pytest.raises(KeyError):
            _how_to_read("not_a_real_spec")

    def test_compute_layer_actually_emits_the_spec_key(self):
        """產生端守衛(與上面的消費端合起來才是完整接線)。

        ⚠️ 2026-08-05:輸入全面改為服務層真實 key / 真實欄位(理由同上兩條)。
        """
        from ui.helpers.macro.beginner_view import compute_five_bucket_summary
        _s = compute_five_bucket_summary(
            {"PMI": {"value": 45.0}, "LEI": {"value": 0.1, "ma3": -0.85}},
            phase_info=_PHASE, news_items=[])
        assert _s["mid"]["spec_key"] == "pmi"
        assert _s["inflection"]["spec_key"] == "cfnai"
        assert _s["news"]["spec_key"] == "news_systemic"


# ══════════════════════════════════════════════════════════════
# 🟡 必修 3 — 綜合健康度的指路要含 ⚠️ 拐點
# ══════════════════════════════════════════════════════════════
class TestStrengthRowPointsAtEveryContributor:
    def test_inflection_section_is_in_the_pointer(self):
        """**修正前必紅** —— 修正前只列 🌳 / 📈 / 🎯 三段,但綜合健康度是
        `Σ score×weight` 跑遍全部指標,權重最高的殖利率差(各 2)與
        Sahm / SLOOS(各 1.5)細節都住在 ⚠️ 拐點段,使用者照指路找不到。"""
        from ui.helpers.macro.beginner_view import _BUCKET_SECTION_HINT
        _p = _row(_rows(), "綜合健康度")["詳細在下方哪一段"]
        assert _BUCKET_SECTION_HINT["inflection"] in _p, f"指路漏了拐點段:{_p!r}"

    def test_the_other_three_sections_are_still_there(self):
        """回歸:補拐點不得順手弄丟原本那三段。"""
        from ui.helpers.macro.beginner_view import _BUCKET_SECTION_HINT
        _p = _row(_rows(), "綜合健康度")["詳細在下方哪一段"]
        for _k in ("long", "mid", "short"):
            assert _BUCKET_SECTION_HINT[_k] in _p

    def test_pointer_sections_are_derived_not_retyped(self, monkeypatch):
        """§3.3:區段名改在鏡像表,指路必須跟著變(不得在表格層抄第二份)。"""
        import ui.helpers.macro.beginner_view as _mbv
        monkeypatch.setitem(_mbv._BUCKET_SECTION_HINT, "inflection", "🛎️ 哨兵段")
        assert "🛎️ 哨兵段" in _row(_rows(), "綜合健康度")["詳細在下方哪一段"]


# ══════════════════════════════════════════════════════════════
# 🟡 建議 4 — 死碼真的移除,且沒有殘留引用
# ══════════════════════════════════════════════════════════════
class TestDeadTrafficLightHelperRemoved:
    def test_symbol_is_gone(self):
        """**修正前必紅**(那時它還在)。239 LOC、production 0 caller,
        且內含三份與現役邏輯重疊的判斷 —— `PROCESS.md §4` 0-consumer 條款。"""
        import ui.helpers.macro.beginner_view as _mbv
        assert not hasattr(_mbv, "compute_traffic_lights")

    def test_no_production_reference_left_behind(self):
        """ruff 白名單那個教訓:刪碼要連引用一起清,否則留下指向不存在
        程式碼的殘留。掃 `ui/` + `services/` 全部 import 與呼叫。"""
        for _p in (list((_ROOT / "ui").rglob("*.py"))
                   + list((_ROOT / "services").rglob("*.py"))):
            try:
                _t = ast.parse(_p.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for _n in ast.walk(_t):
                if isinstance(_n, ast.ImportFrom) and any(
                        a.name == "compute_traffic_lights" for a in _n.names):
                    pytest.fail(f"{_p} 仍 import 已刪除的死碼")
                if isinstance(_n, ast.Call) and str(
                        getattr(_n.func, "id", "")
                        or getattr(_n.func, "attr", "")) == "compute_traffic_lights":
                    pytest.fail(f"{_p} 仍呼叫已刪除的死碼")

    def test_the_two_live_compute_functions_are_untouched(self):
        """刪錯東西的防護:另外兩個 compute 真的有 consumer,必須還在。"""
        from ui.helpers.macro.beginner_view import (  # noqa: F401
            compute_five_bucket_summary,
            compute_four_horizon_summary,
        )


# ══════════════════════════════════════════════════════════════
# 🟡 建議 5 — Z-Score 裝飾覆蓋率必須導出
# ══════════════════════════════════════════════════════════════
class TestZScoreDecorationCoverage:
    def test_counts_match_the_real_render_conditions(self):
        """覆蓋率必須等於「渲染時真的會裝飾到幾張」,不是拍腦袋的數字。

        本測試用**獨立算式**(直接查 registry / MACRO_EDU)重算一次對答案 ——
        production 端改用別的條件就會兩邊對不上。"""
        from shared.macro_buckets import SPECS_BY_KEY
        from ui.components.macro_card_edu import MACRO_EDU
        from ui.tab1_macro import _zs_danger_spec_key
        from ui.tab1_macro_midcycle import (
            _decoration_coverage,
            _EDU_ANCHOR_PILOT,
            _ZS_INDICATORS,
        )
        _keys = [r[0] for r in _ZS_INDICATORS]
        _want_anchor = len([k for k in _keys if k in _EDU_ANCHOR_PILOT
                            and (MACRO_EDU.get(k) or {}).get("historical_anchor")])
        _want_line = len([k for k in _keys if k.lower() in SPECS_BY_KEY])
        assert _decoration_coverage(_zs_danger_spec_key) == (_want_anchor, _want_line)

    def test_counts_are_derived_not_hardcoded(self):
        """§3.3:pilot 擴充後數字會漂移 —— 換掉解析器,警戒線張數必須跟著變。
        **修正前必紅**(整個函式不存在;caption 也沒有覆蓋率這件事)。"""
        from ui.tab1_macro_midcycle import _decoration_coverage, _ZS_INDICATORS
        assert _decoration_coverage(lambda _k: None)[1] == 0
        assert _decoration_coverage(lambda _k: "x")[1] == len(_ZS_INDICATORS)

    def test_anchor_count_follows_the_pilot_list(self, monkeypatch):
        """pilot 名單縮到 1 個 → 錨點張數必須變 1(不得是寫死的常數)。"""
        import ui.tab1_macro_midcycle as _mc
        monkeypatch.setattr(_mc, "_EDU_ANCHOR_PILOT", frozenset({"PMI"}))
        assert _mc._decoration_coverage(lambda _k: None)[0] == 1

    def test_render_actually_calls_the_coverage_helper(self):
        """接線:算得再對,沒接進 caption 就是 0 consumer(`PROCESS.md §4`)。
        用 AST 找呼叫,不用字串比對 —— 註解裡提到函式名不會造成假通過。"""
        _tree = ast.parse(_MIDCYCLE.read_text(encoding="utf-8"))
        _fn = next(n for n in ast.walk(_tree)
                   if isinstance(n, ast.FunctionDef)
                   and n.name == "render_mid_cycle_section")
        assert [n for n in ast.walk(_fn)
                if isinstance(n, ast.Call)
                and getattr(n.func, "id", "") == "_decoration_coverage"], (
            "render 沒呼叫覆蓋率 helper —— 揭露沒接出去")


# ══════════════════════════════════════════════════════════════
# 🟡 建議 6 / 🟢 建議 7 — 表下註記(仍維持單一 caption)
# ══════════════════════════════════════════════════════════════
def _capture_caption(monkeypatch) -> list:
    """攔 `st.caption`。兩個進入點都 patch,理由同 tab1_summary 那檔:
    conftest 會 per-test 換 `sys.modules['streamlit']`,但模組層綁定不跟著換。"""
    import streamlit as _st_sys

    import ui.helpers.macro.beginner_view as _mbv
    _caps: list = []
    for _mod in {id(_st_sys): _st_sys, id(_mbv.st): _mbv.st}.values():
        monkeypatch.setattr(_mod, "caption",
                            lambda *a, **k: _caps.append(str(a[0])), raising=False)
        monkeypatch.setattr(_mod, "dataframe", lambda df, **kw: None, raising=False)
    return _caps


class TestTableFooterNote:
    def test_still_exactly_one_caption_call(self, monkeypatch):
        """回歸鎖:user 要求「不要留兩份說法」,新增內容一律併進同一則 caption。
        本輪加了兩段(區塊順序目錄 + 雷達線差異註記),若有人改成各發一個
        `st.caption`,這裡與 tab1_summary 那檔的同名守衛會同時紅。"""
        from ui.helpers.macro.beginner_view import render_evidence_table
        _caps = _capture_caption(monkeypatch)
        render_evidence_table(_rows())
        assert len(_caps) == 1, f"表下註記應只有一則,實際 {len(_caps)}"

    def test_lists_the_section_walk_in_page_order(self, monkeypatch):
        """**修正前必紅** —— 指路欄塞在 dataframe 字串格裡不可點,使用者只拿到
        區塊「名字」沒有「位置」。表下要有一份順序當目錄。"""
        from ui.helpers.macro.beginner_view import _section_walk, render_evidence_table
        _caps = _capture_caption(monkeypatch)
        render_evidence_table(_rows())
        assert _section_walk() in _caps[0], f"表下沒有區塊順序目錄:{_caps[0]!r}"

    def test_section_walk_is_derived_and_deduped(self, monkeypatch):
        """§3.3:區段名從鏡像表導出,不得寫第二份;📰 新聞與 🌳 長期同名要去重。"""
        import ui.helpers.macro.beginner_view as _mbv
        _walk = _mbv._section_walk()
        for _k in ("long", "mid", "short", "inflection"):
            assert _mbv._BUCKET_SECTION_HINT[_k] in _walk
        assert _walk.count(_mbv._BUCKET_SECTION_HINT["long"]) == 1, "同名段沒去重"
        monkeypatch.setitem(_mbv._BUCKET_SECTION_HINT, "short", "🛎️ 哨兵段")
        assert "🛎️ 哨兵段" in _mbv._section_walk()

    def test_notes_the_radar_line_divergence(self, monkeypatch):
        """**修正前必紅** —— VIX 在同一個 Tab 有多套刻度:本表判「警戒」時,
        使用者照指路捲到雷達卻看到當前值在警戒線**下方**,像是自相矛盾。
        門檻不動(user 2026-06-26 已撤銷 harmonize),改為誠實註記差異。"""
        from ui.helpers.macro.beginner_view import render_evidence_table
        _caps = _capture_caption(monkeypatch)
        render_evidence_table(_rows())
        assert "略有差異" in _caps[0] and "以本表的判讀欄為準" in _caps[0], (
            f"表下沒有雷達線差異註記:{_caps[0]!r}")

    def test_both_scales_are_still_named(self, monkeypatch):
        """回歸:新增兩段不得把原本那句對照擠掉。"""
        from ui.helpers.macro.beginner_view import render_evidence_table
        _caps = _capture_caption(monkeypatch)
        render_evidence_table(_rows())
        assert "位階" in _caps[0] and "強度" in _caps[0]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
