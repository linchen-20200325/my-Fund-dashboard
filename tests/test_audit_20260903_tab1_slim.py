"""2026-09-03 減字(TAB1-SLIM)—— ① 市場總覽「總表區」去重與收摺的守衛。

本輪只做**去重 + 收摺推導細節**,零功能變更、零誠實損失。全面卡片化是另一批。
守的三件事,每條都標明「修正前紅在哪」+「拿掉修復會不會轉紅」(突變判準):

  C2  **表下註記一則都不掉。** `build_evidence_footnotes()` 產出的每一則,
      都必須真的出現在畫面上的某一層(常駐 caption 或摺疊區),且**恰好一次**。
      ⚠️ 本檔刻意**不**用「有沒有呼叫 producer」當判準 —— 同 repo 已有一條
      `tests/test_audit_20260805_tab1_wiring.py::test_reasons_are_rendered_not_dropped`
      名為 `rendered_not_dropped`、實際只 AST 驗「有沒有呼叫 `.get("reasons")`」,
      突變「讀了但一條都不畫」照樣全綠。**那種守衛等於沒有守衛,不要再造一條。**
      本檔一律**真的跑 renderer、真的攔 streamlit 輸出**再斷言。

  C3  **④ 可信度層不得被收進任何可收合容器**(含 `expanded=False`)。
      代理值 / 缺漏指標 chip、資料新鮮度條、>4h 過期警告、FRED 降級 caption
      都是**已經算好的唯讀讀數**,依既有守衛的原話「闔起來等於算了不給看」
      (`test_audit_20260810_tab1_shells.py::
      test_china_drag_panel_renders_without_a_collapsible_frame`)。
      ⚠️ 既有守衛只禁 `expanded=True`;`expanded=False` 對 ④ 目前**零保護** ——
      實測把 ④ 整段包進 `expanded=False` 的 expander,全套測試照樣綠。本條補這個洞。

  C4  **分層的判準本身**:可收的只有「上表『說明』欄短版的完整版」。
      沒有欄內短版的兩則(🌳 兩套切點揭露 / 🩺 算式 + 白話行動)不得收進摺疊。

⚠️ 測試自身可執行性(`PROCESS.md §4`):本檔**不寫任何 importorskip、不 skip**。
   pandas / streamlit 是本 repo 硬依賴,缺件時本檔應該紅而不是製造保護網假象。

⚠️ 位置 / 結構類斷言一律走 **AST**:`ui/tab1_macro.py` 的沿革註解大量引述區塊名,
   `src.index()` / `in src` 會提前命中註解變成恆真的假通過(本 repo 已踩過兩次)。
"""
from __future__ import annotations

import ast
import contextlib
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_TAB1 = _ROOT / "ui" / "tab1_macro.py"

# 同 tests/test_app_smoke.py / test_audit_20260810_tab1_shells.py 的清單 ——
# 這幾個 streamlit primitive 都渲染成「可收合容器」。
_COLLAPSIBLE_ATTRS = ("expander", "status", "popover", "dialog")

_PHASE = {"phase": "擴張", "score": 6.8}
# 全綠情境:總表區字最多的那一天(也是 A1 去重唯一會觸發的那一天)
_ALL_GREEN = {"PMI": {"value": 55.0}, "VIX": {"value": 15.0},
              "HY_SPREAD": {"value": 3.21}, "SAHM": {"value": 0.1}}
_ACT = "哨兵白話行動"


def _summary(indicators=None):
    from ui.helpers.macro.beginner_view import compute_five_bucket_summary
    return compute_five_bucket_summary(
        indicators if indicators is not None else _ALL_GREEN,
        phase_info=_PHASE, news_items=[])


def _summary_without(bucket_key: str):
    """把某一桶拿掉的 summary —— 驗「條件性存在的列」相關的假設。

    ⚠️ production 路徑走不到(`compute_five_bucket_summary` 對 None / {} / 全 None
    三種輸入,`long` 恆存在且非空,2026-09-03 總管複驗)。但
    `build_evidence_footnotes` / `render_evidence_table` 的 docstring 自陳
    「缺哪一桶就少一列」、程式碼也為此留了 `if "long" in _faces:` 防身分支 ——
    **既然分支存在,依賴「它不會發生」的字串就是潛在假話**,本組情境要走得到。
    """
    return {_k: _v for _k, _v in _summary().items() if _k != bucket_key}


_CJK_NUM = {"一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6}


def _claimed_note_count(text: str):
    """從前導句裡解出它**宣稱**的則數(阿拉伯數字或中文數字);沒宣稱 → None。"""
    _m = re.search(r"([0-9]+|[一二兩三四五六])\s*則", text)
    if not _m:
        return None
    _g = _m.group(1)
    return int(_g) if _g.isdigit() else _CJK_NUM[_g]


def _render_and_capture(monkeypatch, summary, *, collapse=True, footnotes=None):
    """真的跑 `render_evidence_table`,把畫面輸出依**揭露層級**收回來。

    回傳 `dict(visible=[...], hidden=[...], labels=[...], n_captions=int)`:
      - `visible` = 常駐層(不必點就看得到)的 caption 字串
      - `hidden`  = 摺疊區內的 caption 字串(要點一下才看得到)
    """
    import streamlit as _st_sys

    import ui.helpers.macro.beginner_view as _mbv
    from ui.helpers.macro.beginner_view import (
        build_evidence_footnotes,
        build_evidence_rows,
        render_evidence_table,
        split_evidence_footnotes,
    )
    _visible: list[str] = []
    _hidden: list[str] = []
    _labels: list[str] = []
    _cur = {"buf": _visible}

    @contextlib.contextmanager
    def _fake_expander(label, **kw):
        _labels.append(str(label))
        _prev, _cur["buf"] = _cur["buf"], _hidden
        try:
            yield
        finally:
            _cur["buf"] = _prev

    for _mod in {id(_st_sys): _st_sys, id(_mbv.st): _mbv.st}.values():
        monkeypatch.setattr(_mod, "caption",
                            lambda *a, **k: _cur["buf"].append(str(a[0])),
                            raising=False)
        monkeypatch.setattr(_mod, "dataframe", lambda df, **kw: None, raising=False)
        monkeypatch.setattr(_mod, "expander", _fake_expander, raising=False)

    _rows = build_evidence_rows(
        summary, composite_score=1.0, composite_icon="🟢",
        composite_level="樂觀", composite_action=_ACT, n_indicators=25)
    _fn = (build_evidence_footnotes(summary, composite_action=_ACT)
           if footnotes is None else footnotes)
    _kw = {}
    if collapse:
        _, _kw["collapsed_footnotes"] = split_evidence_footnotes(
            summary, composite_action=_ACT)
    render_evidence_table(_rows, footnotes=_fn, **_kw)
    return dict(visible=_visible, hidden=_hidden, labels=_labels,
                n_captions=len(_visible) + len(_hidden), rows=_rows, fn=_fn)


# ══════════════════════════════════════════════════════════════
# C2 — 每一則註記都真的畫出來(不是「有沒有呼叫 producer」)
# ══════════════════════════════════════════════════════════════
class TestEveryFootnoteReachesTheScreen:
    def test_every_footnote_is_rendered_exactly_once(self, monkeypatch):
        """**突變判準**:在 `render_evidence_table` 裡把 `_pinned` 或 `_hidden`
        任一批改成不印(或只印前 N 則),本條必紅。

        ⚠️ 這條**真的跑 renderer**,不是 AST 看有沒有呼叫某個函式 ——
        「讀了但一條都不畫」正是本 repo 已有的那條假守衛漏掉的東西。
        """
        _cap = _render_and_capture(monkeypatch, _summary())
        _screen = "\n".join(_cap["visible"] + _cap["hidden"])
        assert _cap["fn"], "情境不對:這個 summary 根本沒有註記可驗"
        for _f in _cap["fn"]:
            assert _screen.count(_f) == 1, (
                f"註記在畫面上出現 {_screen.count(_f)} 次(應為 1):{_f!r}")

    def test_nothing_is_dropped_when_collapse_is_not_requested(self, monkeypatch):
        """**失效方向鎖**:不傳 `collapsed_footnotes` 時全部常駐、摺疊區不出現,
        **且回到 `render_evidence_table` docstring 明訂的單一 caption 契約**。

        本層的失效方向必須恆為「多印」而非「少印」—— 有人把預設值改成
        「沒指定就收起來」,本條紅。

        ⚠️ **2026-09-04 稽核 + 總管複驗補的一行**:原版只驗內容有沒有漏印,
        沒驗**則數**;而 `test_footnotes_ride_in_one_caption_per_disclosure_level`
        (`tests/test_audit_20260806_tab1_honesty.py`)**永遠帶著
        `collapsed_footnotes=` 呼叫**,從未走過「不收摺」這條路。兩條測試合起來
        對「不收摺時仍散成多則 caption」這個突變(稽核 M13)**完全零保護**
        (86 passed)。本行補上那半格。
        """
        _cap = _render_and_capture(monkeypatch, _summary(), collapse=False)
        assert not _cap["hidden"] and not _cap["labels"], (
            "沒要求收摺卻長出摺疊區 —— 失效方向反了")
        assert len(_cap["visible"]) == 1, (
            f"不收摺時應仍是單一 caption(既有契約),實際 {len(_cap['visible'])} 則")
        _screen = "\n".join(_cap["visible"])
        for _f in _cap["fn"]:
            assert _f in _screen, f"全常駐模式下仍漏掉一則:{_f!r}"

    def test_unknown_collapse_entries_cannot_hide_anything(self, monkeypatch):
        """`collapsed_footnotes` 給了 `footnotes` 沒有的東西 → 單純不匹配,
        **不得**因此少印任何一則(§1:寧可版面長一點,不可靜默吞掉揭露)。"""
        import streamlit as _st_sys

        import ui.helpers.macro.beginner_view as _mbv
        from ui.helpers.macro.beginner_view import (
            build_evidence_footnotes,
            build_evidence_rows,
            render_evidence_table,
        )
        _s = _summary()
        _fn = build_evidence_footnotes(_s, composite_action=_ACT)
        _caps: list[str] = []
        for _mod in {id(_st_sys): _st_sys, id(_mbv.st): _mbv.st}.values():
            monkeypatch.setattr(_mod, "caption",
                                lambda *a, **k: _caps.append(str(a[0])), raising=False)
            monkeypatch.setattr(_mod, "dataframe", lambda df, **kw: None, raising=False)
        render_evidence_table(
            build_evidence_rows(_s, composite_score=1.0, composite_icon="🟢",
                                composite_level="樂觀", composite_action=_ACT,
                                n_indicators=25),
            footnotes=_fn, collapsed_footnotes=["不存在的一則", ""])
        _screen = "\n".join(_caps)
        for _f in _fn:
            assert _f in _screen, f"對不上的 collapse 清單害得一則消失:{_f!r}"

    def test_split_is_an_exhaustive_ordered_partition(self):
        """`split_evidence_footnotes` 的兩份**聯集逐則等於**完整清單,順序不變。

        **突變判準**:在 `_evidence_footnote_items` 裡漏掉任一則(或讓
        `split_...` 過濾而不是分流),本條紅 —— 分類只決定印在哪一層,
        不決定印不印。
        """
        from ui.helpers.macro.beginner_view import (
            build_evidence_footnotes,
            split_evidence_footnotes,
        )
        for _ind in (_ALL_GREEN, {}, {"PMI": {"value": 45.0}},
                     {"VIX": {"value": 33.0}, "SAHM": {"value": 0.62}}):
            _s = _summary(_ind)
            _full = build_evidence_footnotes(_s, composite_action=_ACT)
            _pin, _coll = split_evidence_footnotes(_s, composite_action=_ACT)
            assert sorted(_pin + _coll) == sorted(_full), (
                f"分層不是完整分割,有一則被吃掉了:{_ind!r}")
            assert [_f for _f in _full if _f in _pin] == _pin, "常駐層順序被打亂"
            assert [_f for _f in _full if _f in _coll] == _coll, "摺疊層順序被打亂"


# ══════════════════════════════════════════════════════════════
# C4 — 收的必須是推導細節,讀數不得收
# ══════════════════════════════════════════════════════════════
class TestOnlyDerivationDetailIsCollapsed:
    def test_the_two_cutoff_sets_stay_visible(self, monkeypatch):
        """🌳 長期的**兩套切點揭露**不得收進摺疊。

        它要防的失效模式是「① 亮 🟡 而 ② 的 🌳 亮 🟢,使用者當成 bug」
        (2026-08-05 必修 1)。格子裡只有位階尺度那句短版,**切點差異在表上
        沒有任何對應的短版** —— 收起來等於把那個矛盾的唯一解釋,
        放在一次「讀者不知道自己該點」的點擊後面。

        **突變判準**:把 `long` 那則在 `_evidence_footnote_items` 標成 `True`,本條紅。
        """
        from services.macro.action_light import _BUY_SCORE_10
        from ui.helpers.macro.beginner_view import _MACRO_SCORE_HEALTHY_MIN
        _cap = _render_and_capture(monkeypatch, _summary())
        _vis = "\n".join(_cap["visible"])
        for _v in (_MACRO_SCORE_HEALTHY_MIN, _BUY_SCORE_10):
            assert f"{float(_v):.1f}" in _vis, (
                f"切點 {_v} 不在常駐層 —— 兩把尺的差異又變成要點一下才看得到")

    def test_the_plain_language_action_stays_visible(self, monkeypatch):
        """🩺 的**白話行動**是 `composite_verdict()` 已經算好的結論,不是推導細節;
        依既有守衛的原話,已經算好的唯讀結果「闔起來等於算了不給看」。

        **突變判準**:把 `strength` 那則標成可收,本條紅。
        """
        _cap = _render_and_capture(monkeypatch, _summary())
        assert _ACT in "\n".join(_cap["visible"]), "白話行動被收進摺疊區了"

    def test_threshold_full_text_is_the_thing_that_collapses(self, monkeypatch):
        """反向:可收的那批**確實**收起來了,而且摺疊標籤說得出裡面是什麼。

        標籤不說清楚 = 讀者不知道自己該不該點 = 「收摺」變成「藏起來」。
        **突變判準**:把摺疊那段拿掉(全部常駐),本條紅。
        """
        from ui.helpers.macro.beginner_view import split_evidence_footnotes
        _s = _summary()
        _, _coll = split_evidence_footnotes(_s, composite_action=_ACT)
        _cap = _render_and_capture(monkeypatch, _s)
        assert _cap["labels"], "沒有摺疊區 —— 推導細節沒有收起來"
        assert len(_cap["labels"]) == 1, f"摺疊區不只一個:{_cap['labels']}"
        assert "完整版" in _cap["labels"][0] or "全文" in _cap["labels"][0], (
            f"摺疊標籤沒說清楚裡面是什麼:{_cap['labels'][0]!r}")
        _hid = "\n".join(_cap["hidden"])
        for _f in _coll:
            assert _f in _hid, f"該收的沒收進摺疊區:{_f!r}"

    def test_collapsed_container_is_never_default_open(self, monkeypatch):
        """回歸:摺疊區必須 `expanded=False`。`expanded=True` 是空殼 ——
        外框沒擋住任何東西,只多印一次標題(見 test_audit_20260810_tab1_shells)。"""
        import streamlit as _st_sys

        import ui.helpers.macro.beginner_view as _mbv
        from ui.helpers.macro.beginner_view import (
            build_evidence_footnotes,
            build_evidence_rows,
            render_evidence_table,
            split_evidence_footnotes,
        )
        _seen: list[dict] = []

        @contextlib.contextmanager
        def _exp(label, **kw):
            _seen.append(kw)
            yield

        for _mod in {id(_st_sys): _st_sys, id(_mbv.st): _mbv.st}.values():
            monkeypatch.setattr(_mod, "caption", lambda *a, **k: None, raising=False)
            monkeypatch.setattr(_mod, "dataframe", lambda df, **kw: None, raising=False)
            monkeypatch.setattr(_mod, "expander", _exp, raising=False)
        _s = _summary()
        _, _coll = split_evidence_footnotes(_s, composite_action=_ACT)
        render_evidence_table(
            build_evidence_rows(_s, composite_score=1.0, composite_icon="🟢",
                                composite_level="樂觀", composite_action=_ACT,
                                n_indicators=25),
            footnotes=build_evidence_footnotes(_s, composite_action=_ACT),
            collapsed_footnotes=_coll)
        assert _seen, "摺疊區沒出現"
        for _kw in _seen:
            assert _kw.get("expanded") is False, (
                f"表下摺疊區不是 expanded=False:{_kw!r}")


# ══════════════════════════════════════════════════════════════
# A2 / A3 — 欄內短句不得在表下再抄一份
# ══════════════════════════════════════════════════════════════
class TestScaleNotesAreNotPrintedTwice:
    def test_the_column_phrases_live_in_the_cells_not_also_in_the_caption(
            self, monkeypatch):
        """`_SCALE_NOTE_PHASE` / `_STRENGTH_UNIT` 是**欄內短句** ——
        它們就印在正上方那張表的「說明」欄裡,表下那句 📐 不該再抄一份。

        ⚠️ **這條守的是「不重複」,不是「不要講」**:同一則 caption 仍必須點名
        兩把尺各是什麼(位階 / 強度)、講出「別互相換算」這個跨列警告、
        並指出單位去哪讀 —— 那三件事由下一條 `test_...still_self_contained` 釘住。
        兩條合起來才是完整契約:**少了任一條,這裡就會退化成「為了減字而砍話」。**

        **突變判準**:把 `({_SCALE_NOTE_PHASE})` / `({_STRENGTH_UNIT})` 加回
        📐 那句,本條紅。
        """
        from ui.helpers.macro.beginner_view import (
            _SCALE_NOTE_PHASE,
            _STRENGTH_UNIT,
        )
        _cap = _render_and_capture(monkeypatch, _summary())
        _screen = "\n".join(_cap["visible"] + _cap["hidden"])
        _cells = " ".join(str(_v) for _r in _cap["rows"] for _v in _r.values())
        for _phrase, _who in ((_SCALE_NOTE_PHASE, "🌳 長期"),
                              (_STRENGTH_UNIT, "🩺 綜合健康度")):
            assert _phrase in _cells, (
                f"{_who} 的欄內短句不在格子裡了 —— 那不是去重,是把話砍掉:{_phrase!r}")
            assert _phrase not in _screen, (
                f"{_who} 的欄內短句在表下又抄了一份(格子裡已經有):{_phrase!r}")

    def test_the_two_scales_sentence_is_still_self_contained(self, monkeypatch):
        """去重不得讓 📐 那句失去自我完備性。

        減字之前那句是「上表『說明』欄已分別標明:🌳…(位階 0-10 分,恆非負);
        🩺…(指標加權淨分(有正負))」。直接把括號砍掉會剩下
        「已分別標明」卻**不說明標了什麼** —— 句子當場讀不通。
        改寫後保留的必須是**這句話真正的職責**:
          (a) 點名兩把尺各是什麼(位階 / 強度);
          (b) 講出跨列的那個警告(不同義、別互相換算);
          (c) 指出單位與範圍去哪讀(上表「說明」欄)。

        **突變判準**:把 📐 那句改成只剩警告、不點名兩把尺(或不指路),本條紅。
        """
        _cap = _render_and_capture(monkeypatch, _summary())
        _vis = "\n".join(_cap["visible"])
        _line = next(_l for _l in _vis.splitlines() if _l.lstrip().startswith("📐"))
        for _must in ("位階", "強度"):        # (a)
            assert _must in _line, f"📐 那句沒點名「{_must}」這把尺:{_line!r}"
        assert "別互相換算" in _line, f"📐 那句掉了跨列警告:{_line!r}"      # (b)
        assert "說明" in _line, f"📐 那句沒說單位去哪讀:{_line!r}"          # (c)


# ══════════════════════════════════════════════════════════════
# 缺桶情境 — 使用者可見字串不得寫死「條件性的事實」
# ══════════════════════════════════════════════════════════════
class TestVisibleStringsDoNotHardcodeConditionalFacts:
    """2026-09-03 獨立稽核 + 總管複驗抓到的兩筆(#8 / #9)。

    **根因是同一個**:`_evidence_footnote_items` 裡 🌳 長期那一則掛在
    `if "long" in _faces:` —— 它是**條件性的**;而兩句使用者可見字串把它當成
    **必然存在**:前導句寫死「兩則」、📐 那句無條件點名 🌳 長期並叫讀者去上表看。

    ⚠️ **本組原本的守衛為什麼漏了**:`TestScaleNotesAreNotPrintedTwice` 兩條
    都**只跑全綠情境**(long 必存在),於是「long 缺席會怎樣」從來沒被執行到 ——
    **只跑會過的那個情境,就是本輪稽核抓到的三個洞裡兩個的成因。** 本類補這一格。
    """

    @pytest.mark.parametrize(
        "summary_factory,label",
        [(lambda: _summary(), "有 long(production 路徑)"),
         (lambda: _summary_without("long"), "缺 long(直呼可達)")],
        ids=["with_long", "without_long"])
    def test_the_lead_never_claims_a_count_that_is_not_true(
            self, monkeypatch, summary_factory, label):
        """(a) 常駐前導句**宣稱的則數**必須等於**實際列數**。

        **修正前必紅(缺 long 那一格)** —— `_PINNED_FOOTNOTE_LEAD` 寫死
        「…的**兩則**:」,而缺 long 時常駐只有 1 則。
        寫死一個條件性的數量,就是 §3.3 在使用者可見字串上的同一個病。
        """
        from ui.helpers.macro.beginner_view import split_evidence_footnotes
        _s = summary_factory()
        _pin, _ = split_evidence_footnotes(_s, composite_action=_ACT)
        _cap = _render_and_capture(monkeypatch, _s)
        _lead = [_l for _l in _cap["visible"][0].splitlines()
                 if _l.lstrip().startswith("🔍")]
        assert _lead, f"{label}:常駐層找不到前導句"
        _claim = _claimed_note_count(_lead[0])
        assert _claim in (None, len(_pin)), (
            f"{label}:前導句宣稱 {_claim} 則,實際常駐 {len(_pin)} 則 —— "
            f"寫死了一個條件性的數量:{_lead[0].strip()!r}")

    @pytest.mark.parametrize(
        "summary_factory,label",
        [(lambda: _summary(), "有 long(production 路徑)"),
         (lambda: _summary_without("long"), "缺 long(直呼可達)")],
        ids=["with_long", "without_long"])
    def test_the_two_scales_sentence_only_names_scales_that_are_on_the_table(
            self, monkeypatch, summary_factory, label):
        """(b) 📐 那句點名的每一把尺,**表上都要有對應那一列**。

        **修正前必紅(缺 long 那一格)** —— 📐 無條件寫「🌳 長期 是景氣位階…
        各自的單位與範圍**見上表「說明」欄**」,而缺 long 時表上**沒有那一列** ——
        指路指向空氣,而且比原版更糟:原版把單位內嵌在句子裡(常數),
        **就算指路錯了讀者仍拿得到單位**;本 PR 把單位移出後只剩指路,
        那一列缺席時這句話從「指路錯但仍自足」退化成「空指路」。
        **這個退化是本 PR 造成的,不是繼承的。**

        面向字串一律從 `BUCKET_META` / `_STRENGTH_FACE` 導出(§3.3),
        本測試不重打桶名。
        """
        from shared.macro_buckets import BUCKET_META
        from ui.helpers.macro.beginner_view import _STRENGTH_FACE
        _s = summary_factory()
        _cap = _render_and_capture(monkeypatch, _s)
        _geo = [_l for _l in _cap["visible"][0].splitlines()
                if _l.lstrip().startswith("📐")]
        assert _geo, f"{label}:常駐層找不到 📐 那一句"
        _sentence = _geo[0]
        _faces_on_table = {str(_r["面向"]) for _r in _cap["rows"]}
        _long_face = f'{BUCKET_META["long"]["emoji"]} {BUCKET_META["long"]["title"]}'
        for _face in (_long_face, _STRENGTH_FACE):
            if _face in _sentence:
                assert _face in _faces_on_table, (
                    f"{label}:📐 那句點名「{_face}」,但表上沒有這一列 —— "
                    f"「見上表『說明』欄」是空指路:{_sentence.strip()!r}")
        # 至少要點名一把尺,否則那句話沒有主詞(不得為了通過而整句砍掉)
        assert _long_face in _sentence or _STRENGTH_FACE in _sentence, (
            f"{label}:📐 那句一把尺都沒點名 —— 那不是修,是砍話:{_sentence.strip()!r}")


# ══════════════════════════════════════════════════════════════
# C3 — ④ 可信度層不得被收進任何可收合容器
# ══════════════════════════════════════════════════════════════
def _tree() -> ast.Module:
    return ast.parse(_TAB1.read_text(encoding="utf-8"))


def _fn_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    return str(getattr(call.func, "attr", ""))


def _heading_line(prefix: str) -> int:
    """`st.markdown("<prefix>…")` 那一行的行號(AST,不切原始碼字串)。

    註解裡大量引述區塊名,`src.index()` 會提前命中而讓斷言恆真 —— 故走 AST。
    """
    _hits = [_n.lineno for _n in ast.walk(_tree())
             if isinstance(_n, ast.Call) and _fn_name(_n) == "markdown"
             and _n.args and isinstance(_n.args[0], ast.Constant)
             and isinstance(_n.args[0].value, str)
             and _n.args[0].value.startswith(prefix)]
    assert len(_hits) == 1, f"標題 {prefix!r} 應恰好一處,實際 {_hits}"
    return _hits[0]


def _summary_panel_span() -> tuple[int, int]:
    """總表區①~④**整段**的行號範圍 = ① 標題 → 下一個一級區塊(🔎 詳細區)標題。

    2026-09-04 稽核 + 總管複驗 F-1:原本這裡叫 `_trust_layer_span()`、只從
    `### ④ 可信度` 起算 —— **①②③ 完全在射程外**。獨立稽核用突變證實
    (G1 把 ① 整段包進 `expanded=False`、G2 同樣包 ③,兩次都是全套測試
    92 passed、0 failed),總管複驗同一組突變、結果一致。函式與測試名稱
    改成誠實反映新射程:它現在守的是**整個總表區**,不只 ④。
    """
    _start = _heading_line("### ① 結論")
    _end = _heading_line("## 🔎 詳細資料與說明")
    assert _start < _end, f"① 應在詳細區之前:{_start} vs {_end}"
    return _start, _end


def _collapsible_with_nodes() -> list[ast.With]:
    return [_n for _n in ast.walk(_tree())
            if isinstance(_n, ast.With)
            and any(isinstance(_i.context_expr, ast.Call)
                    and _fn_name(_i.context_expr) in _COLLAPSIBLE_ATTRS
                    for _i in _n.items)]


class TestSummaryPanelIsNeverCollapsed:
    """2026-09-04 由 `TestTrustLayerIsNeverCollapsed` 擴大射程改名而來 ——

    舊名字只守 ④,新名字誠實反映它現在守 ①~④ 整段(見 `_summary_panel_span`)。
    """

    def test_no_part_of_the_summary_panel_is_inside_any_collapsible_container(self):
        """**修正前(僅 ④ 射程):①③零保護。** 獨立稽核突變證實:
        把 ① 整段包進 `expanded=False`(G1)或把 ③ 整段包進 `expanded=False`
        (G2),全套既有測試(含當時的舊版本條)照樣 **92 passed,0 failed**。

        ①~④ 底下全部是**已經算好的唯讀讀數 / 結論**:① 結論行與 reasons、
        ② 建議資產水位與非投資指示免責、對帳 chip、③ 三態(有例外/沒例外/
        算不出來)、④ 代理值 / 缺漏指標 chip、新鮮度條、過期警告、FRED 降級。
        依既有守衛的原話,已算好的唯讀結果「闔起來等於算了不給看」。

        **突變判準**:把①~④任一段(含新鮮度條)包進任何一個
        `with st.expander(...)` —— 不論 `expanded` 傳什麼 —— 本條必紅。
        """
        _start, _end = _summary_panel_span()
        _bad = [(_n.lineno, getattr(_n, "end_lineno", _n.lineno))
                for _n in _collapsible_with_nodes()
                # 區間相交即算(整段包住 / 只包住其中幾行,都不行)
                if _n.lineno < _end and getattr(_n, "end_lineno", _n.lineno) > _start]
        assert not _bad, (
            f"總表區(行 {_start}~{_end})被收進可收合容器 {_bad} —— "
            "①~④ 全是已經算好的唯讀讀數 / 結論,闔起來等於算了不給看")

    def test_the_summary_panel_still_contains_the_things_it_must_show(self):
        """伴生鎖:上一條只證明「沒被收起來」,不證明「東西還在」。

        有人把①~④的內容整段刪掉,上一條會**恆真地通過**(沒有內容就沒有東西
        被包)。本條逐層釘住必須留在該區間內的東西,**刪掉任一樣就紅**。
        """
        _start, _end = _summary_panel_span()
        _src = _TAB1.read_text(encoding="utf-8").splitlines()
        _seg = "\n".join(_src[_start - 1:_end - 1])
        for _must, _what in (
            # 同上一批更正的同一種問題:短字串在 span 內還會命中「說明性註解」
            # (①③④ 各自標題附近都有沿革註解重述同一句話),把功能字串刪掉、
            # 只留註解,舊字串仍判定「有」。逐一核對:含花括號 / 破折號的較長
            # 片段只出現在真正組字串的那一行(已用 `grep -c` 逐一確認唯一)。
            # ⚠️ 2026-09-04 第四輪就地更新(**有意識的更新,不是把守衛改鬆**):
            # ①結論的「印什麼」已抽成同檔純函式 `_conclusion_line_state()`
            # (客戶授權的行為變更:證據撐不住時走誠實灰態),於是原本釘在 span 內的
            # 兩個字面值 ~~「現在能不能買 ── 」~~ / ~~`.get("reasons")`~~ 移出了 span。
            # **它們守的東西沒有變**(結論行還在、理由條列還在),變的是**住在哪**。
            # 故改為釘住「span 內確實把那個函式的輸出畫出來」＋
            # 在**函式端**另有行為測試釘住輸出內容
            # (`tests/test_batch2_top_card_grid.py::test_the_conclusion_line_*`)。
            # ⛔ 不得改回字面值:那會把守衛綁回一個已經不在那裡的實作細節。
            ("_conclusion_line_state(_al)", "① 結論行(改由純函式產生)"),
            ("_action_light_renderer(_al_light)", "① 結論行的渲染呼叫"),
            ("建議資產水位", "② 建議資產水位"),
            ("非投資指示", "② 非投資指示免責"),
            ("對帳:加權淨分與多空投票同向", "② 對帳 chip"),
            ("_exception_lines(", "③ 例外判定(三態邏輯的一半)"),
            ("_bucket_status_unavailable_line(", "③ 算不出來判定(三態邏輯另一半)"),
            # ⚠️ 2026-09-04 F-1 擴大射程後補的更正:span 起點提前到 ①,
            # 原本用的短字串「代理值」「缺漏指標」在新射程內會**額外命中**
            # ④ 標題前一句說明性註解(「代理值與缺漏指標(§1 誠實揭露)」)——
            # 拿掉真正的 chip、只留註解,舊字串仍會判定「有」,是假陰性。
            # 改用含 f-string 花括號的較長片段,只在真正組字串的那一行才有。
            ("代理值 {_n_proxy}", "④ 代理值 chip"),
            ("缺漏指標 {_n_missing}", "④ 缺漏指標 chip"),
            ("<b>資料新鮮度</b>", "④ 資料新鮮度條"),
            ("未更新", "④ >4h 過期警告"),
            ("部分 FRED 序列失敗或過期", "④ FRED 降級 caption"),
        ):
            assert _must in _seg, f"總表區少了 {_what}(找不到 {_must!r})"


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
