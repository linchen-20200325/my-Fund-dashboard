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


def _notes(indicators=None, *, phase_info=None, news_items=None,
           composite_action="多頭市場強勁") -> str:
    """表下 footnotes 併成一段 —— 2026-08-06 必修 3 之後,欄內放不下的長說明
    (兩套切點揭露 / 完整門檻 / 全綠判讀規則 / 白話行動)住在這裡而不是格子裡。

    `st.dataframe` 的字串格會截斷,實測 🌳 長期列斷在「…① 結論燈同一」——
    也就是 §1 要求的揭露只顯示到一半。本輪把長句搬到表下同一則 caption,
    因此原本斷言「切點在說明欄」的幾條改為斷言「切點在表下」。
    """
    from ui.helpers.macro.beginner_view import (
        build_evidence_footnotes,
        compute_five_bucket_summary,
    )
    _s = compute_five_bucket_summary(
        indicators or {},
        phase_info=_PHASE if phase_info is None else phase_info,
        news_items=news_items,
    )
    return "\n".join(build_evidence_footnotes(
        _s, composite_action=composite_action))


def _footnote_list(indicators=None, *, phase_info=None, news_items=None,
                   composite_action="多頭市場強勁") -> list[str]:
    """同 `_notes` 但**不 join** —— 逐則斷言(哪一列有沒有註腳)需要邊界。"""
    from ui.helpers.macro.beginner_view import (
        build_evidence_footnotes,
        compute_five_bucket_summary,
    )
    _s = compute_five_bucket_summary(
        indicators or {},
        phase_info=_PHASE if phase_info is None else phase_info,
        news_items=news_items,
    )
    return build_evidence_footnotes(_s, composite_action=composite_action)


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
        _note = _notes()
        for _v in (_MACRO_SCORE_HEALTHY_MIN, _MACRO_SCORE_DANGER_MAX,
                   _BUY_SCORE_10, _HOLD_SCORE_10):
            assert f"{float(_v):.1f}" in _note, (
                f"表下沒揭露切點 {_v} —— 兩把尺的差異又變成看不見的:{_note!r}")

    def test_conclusion_light_cutoff_is_read_not_retyped(self, monkeypatch):
        """§3.3 反捏造的**真檢查**:把結論燈的加碼門檻換掉,說明欄必須跟著變。

        若有人圖方便在文案裡寫死一份 6.5,這條會紅(說明欄仍印舊值)。
        **修正前必紅**(那句話整個不存在)。"""
        monkeypatch.setattr("services.macro.action_light._BUY_SCORE_10", 9.1)
        _note = _notes()
        assert "9.1" in _note, f"結論燈門檻是寫死的第二份,不是讀 SSOT:{_note!r}"

    def test_own_cutoff_is_read_not_retyped(self, monkeypatch):
        """同上,反向守本表自己那組切點。"""
        import ui.helpers.macro.beginner_view as _mbv
        monkeypatch.setattr(_mbv, "_MACRO_SCORE_HEALTHY_MIN", 7.3)
        assert "7.3" in _notes()

    def test_long_row_cell_stays_short_enough_to_survive_truncation(self):
        """2026-08-06 必修 3(瀏覽器實測):`st.dataframe` 的字串格會截斷,
        🌳 長期列原本斷在「…① 結論燈同一」。欄內只留短句 →
        **修正前必紅**(舊行為與斷言衝突,非 ImportError:舊格內含 98 字的切點揭露)。

        刻意不比對文案字面值(user 隨時可改字),改斷言「切點數字不在格子裡、
        但在表下」—— 也就是這次搬家真的發生了。"""
        from services.macro.action_light import _BUY_SCORE_10
        _cell = _row(_rows(), "長期")[_note_col()]
        assert f"{float(_BUY_SCORE_10):.1f}" not in _cell, (
            f"長句還留在格子裡,會被 dataframe 截斷:{_cell!r}")
        assert f"{float(_BUY_SCORE_10):.1f}" in _notes(), "搬出去卻沒搬到表下 = 資訊掉了"

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

        ⚠️ 2026-08-06 必修 3:欄內改放 note 的**短版**(只截掉尾端補充括號,
        不改寫任何字);未截斷的完整 note 搬到表下 caption。兩邊都驗,
        「短版是從 registry 截出來的」與「完整版沒掉」同時守住。
        """
        from shared.macro_buckets import SPECS_BY_KEY
        from ui.helpers.macro.beginner_view import _spec_threshold_short
        _ind = {"LEI": {"value": 0.1, "ma3": -0.85}}
        _inf = _row(_rows(_ind), "拐點")
        assert "CFNAI" in _inf["讀數"]
        assert _spec_threshold_short(SPECS_BY_KEY["cfnai"].note) in _inf[_note_col()]
        assert SPECS_BY_KEY["cfnai"].note in _notes(_ind), "完整門檻沒出現在表下"

    def test_thresholds_are_read_from_registry_not_retyped(self, monkeypatch):
        """§3.3:門檻描述改在 registry,說明欄必須跟著變。
        有人把門檻文字抄一份到 UI 層 → 這條紅。"""
        from shared.macro_buckets import SPECS_BY_KEY
        _fake = dataclasses.replace(SPECS_BY_KEY["pmi"], note="XX 哨兵門檻 XX")
        monkeypatch.setitem(SPECS_BY_KEY, "pmi", _fake)
        _mid = _row(_rows({"PMI": {"value": 45.0}}), "中期")
        assert "XX 哨兵門檻 XX" in _mid[_note_col()]

    def test_short_row_has_a_threshold_even_when_green(self):
        """🎯 短線列**在 VIX 真的有讀數時**全綠,讀數仍是數字,照樣指得出門檻。

        ⚠️ 2026-08-06 必修 1:原本這裡餵 `{}`(完全沒有 VIX)也期望指得出 VIX 門檻
        —— 那正是被修掉的 bug:`_v("VIX") or 0.0` 讓缺值變成「VIX 0.0 正常」🟢。
        現在改餵一個真的平靜讀數;「沒有 VIX 時會怎樣」由
        `test_audit_20260806_tab1_honesty.py` 反向守著。
        """
        from shared.macro_buckets import SPECS_BY_KEY
        from ui.helpers.macro.beginner_view import _spec_threshold_short
        _short = _row(_rows({"VIX": {"value": 15.0}}), "短線")
        assert "15.0" in _short["讀數"]
        assert _spec_threshold_short(SPECS_BY_KEY["vix"].note) in _short[_note_col()]

    def test_all_green_rows_explain_when_a_number_will_appear(self):
        """全綠時讀數是**狀態詞不是數字**,此時說明欄答「什麼情況會變成數字」,
        而**不得**硬塞一個沒觸發的門檻(硬塞會讓讀者以為畫面正在講那一顆)。

        ⚠️ 2026-08-06 必修 3:76 字的完整規則在格子裡只顯示得到「…僅限本列算」,
        因此欄內改放短指路、全文搬表下。兩邊都驗。
        """
        from shared.macro_buckets import SPECS_BY_KEY
        from ui.helpers.macro.beginner_view import (
            _NO_SPEC_READ_RULE,
            _NO_SPEC_SHORT,
        )
        _ind = {"PMI": {"value": 55.0}, "SAHM": {"value": 0.1}}
        _r = _rows(_ind)
        for _face in ("中期", "拐點"):
            _note = _row(_r, _face)[_note_col()]
            assert _NO_SPEC_SHORT in _note
            assert _NO_SPEC_READ_RULE not in _note, "76 字全文留在格子裡會被截斷"
        assert _NO_SPEC_READ_RULE in _notes(_ind), "全文沒搬到表下 = 掉資訊"
        assert SPECS_BY_KEY["pmi"].note not in _row(_r, "中期")[_note_col()]

    def test_the_all_green_rule_is_printed_once_and_the_rest_point_at_it(self):
        """2026-09-03 減字(A1)的**去重鎖**,取代原本的 `count(...) >= 2`。

        ⚠️ **舊斷言為什麼要換,以及新斷言為什麼不是放寬**:
        舊的 `>= 2` 守的是「全文有沒有搬到表下」,而它用**份數**當代理指標 ——
        全綠時 📈 中期與 ⚠️ 拐點沒有 spec key,`_how_to_read_full` 對兩者回**同一段
        76 字**,於是那則 caption 裡出現兩份逐字複本(全綠又正好是最常見的一天)。
        去重之後份數必然掉到 1,舊斷言會把**去重**誤報成**掉資訊**。

        新契約比舊的**嚴**,守的是舊斷言真正想要的那件事 ——
        「每一個全綠列,讀者都拿得到那條規則」:
          (a) 全文在表下**至少**出現一次(＝真的搬出來了,舊斷言的本意);
          (b) 全文**恰好**出現一次(＝去重鎖;有人把逐字複本加回來,本條紅);
          (c) 每一個欄內顯示 `_NO_SPEC_SHORT` 的列,表下那一則**不是全文就是指路**,
              **不得沒有註腳**(＝擋掉「去重做成刪但書」這種改法);
          (d) 指路指到的那一列**真的存在**、而且**真的**是印全文的那一列
              (＝擋掉指向空氣的指路,同 `section_hint` 的既有處置)。
        """
        from ui.helpers.macro.beginner_view import (
            _NO_SPEC_READ_RULE,
            _NO_SPEC_SHORT,
            _no_spec_rule_pointer,
        )
        _ind = {"PMI": {"value": 55.0}, "SAHM": {"value": 0.1}}
        _rs = _rows(_ind)
        _fn = _footnote_list(_ind)

        _joined = "\n".join(_fn)
        assert _NO_SPEC_READ_RULE in _joined, "(a) 全綠規則全文沒搬到表下"
        assert _joined.count(_NO_SPEC_READ_RULE) == 1, (
            f"(b) 全綠規則全文印了 {_joined.count(_NO_SPEC_READ_RULE)} 次 —— "
            "同一條規則的逐字複本又回來了")

        # 印全文的是哪一列(從註記本身反解,不在測試裡重打桶名 —— §3.3)
        _owner = next(_f.split(":", 1)[0] for _f in _fn
                      if _NO_SPEC_READ_RULE in _f)
        _pointer = _no_spec_rule_pointer(_owner)

        _green_faces = [_r["面向"] for _r in _rs
                        if _NO_SPEC_SHORT in _r[_note_col()]]
        assert len(_green_faces) >= 2, (
            f"這個情境應有多個全綠列才驗得到去重,實際 {_green_faces}")
        for _face in _green_faces:
            _mine = [_f for _f in _fn if _f.startswith(_face)]
            assert _mine, f"(c) {_face} 那一列在表下完全沒有註腳 —— 去重做成了刪但書"
            assert _NO_SPEC_READ_RULE in _mine[0] or _pointer in _mine[0], (
                f"(c) {_face} 的註腳既不是全文也不是指路:{_mine[0]!r}")
        # (d) 指路指到的那一列真的存在,且真的是印全文的那一列
        assert any(_f.startswith(_owner) and _NO_SPEC_READ_RULE in _f
                   for _f in _fn), f"(d) 指路指向不存在 / 沒有全文的列:{_owner!r}"

    def test_the_pointer_follows_the_data_it_is_not_hardcoded(self):
        """§3.3 的**真檢查**:哪一列印全文由資料決定,不是寫死「📈 中期」。

        📈 中期與 🎯 短線都拿到讀數(→ 各自有 spec key、印自己的門檻)時,
        剩下唯一的全綠列 ⚠️ 拐點必須**自己接手印全文**,而不是指向一個
        不在畫面上的列。**把 owner 寫死成「📈 中期」的實作,這條會紅。**

        ⚠️ 情境要挑對:本測試第一版餵 `{PMI, SAHM}`,以為 ⚠️ 拐點會接手,
        實際接手的是 🎯 短線 —— 沒餵 VIX / HY,短線本來就沒有 spec key,
        它在 `("mid","short","inflection","news")` 的順序裡排在拐點前面。
        那不是實作錯,是測試情境設錯;補上 VIX 讀數才真的只剩拐點全綠。
        """
        from ui.helpers.macro.beginner_view import _NO_SPEC_READ_RULE
        # PMI 45 → 中期指 PMI 門檻;VIX 15 → 短線指 VIX 門檻;
        # 只剩 ⚠️ 拐點(SAHM 0.1 安全、無 spec key)是全綠列
        _fn = _footnote_list({"PMI": {"value": 45.0}, "VIX": {"value": 15.0},
                              "SAHM": {"value": 0.1}})
        _owners = [_f.split(":", 1)[0] for _f in _fn if _NO_SPEC_READ_RULE in _f]
        assert _owners == ["⚠️ 拐點"], (
            f"少了 📈 中期時,全文沒有交棒給剩下的全綠列:{_owners!r}")

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
