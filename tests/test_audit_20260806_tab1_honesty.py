"""2026-08-06 — Tab① 誠實度四修的守衛(user 四原則:不闔上 / 去重複 / 刪幽靈 / 多說明)。

本檔守四件事,每一條都標明「修正前紅在哪」,並區分兩種紅:
  - **ImportError 紅**:被測的東西修正前根本不存在(新函式 / 新常數);
  - **行為衝突紅**:函式修正前就在,但舊行為與斷言直接互斥 —— 這種才是真守衛,
    因為它會在有人把修正 revert 回去時再度變紅。

  🔴 必修 1 — 缺值被畫成「正常」。`ui/helpers/macro/beginner_view.py` 的
              VIX / HY / 薩姆三處寫 `_v(...) or 0.0`,抓不到時變讀數 0.0,
              0.0 低於所有警戒門檻 → 畫面印「VIX 0.0 正常」🟢。同檔拐點桶的
              10Y-2Y / CFNAI / SLOOS 早就用 `is not None` 寫對了,這三處是漏網。
              連帶:全綠 headline 寫死「三項皆健康」「全綠」,缺值時照樣宣告。
  🔴 必修 2 — ② 依據表渲染失敗時,`_5b_summary` 維持 `{}`,③ 例外層讀不出
              「② 沒跑完」與「② 跑完且全綠」的差別,於是印出「各桶讀數**完整**
              列在上方 ② 依據表」—— ② 剛用紅字說自己壞了。
  🔴 必修 3 — ② 說明欄被 `st.dataframe` 截斷(瀏覽器實測)。欄內留短句、
              長句搬到表下同一則 caption;**只搬不刪**。
  🔴 必修 4 — ⚡ 今日關鍵橫幅把訊號層與拐點層直接相加,而兩層吃同一批 FRED
              序列(CFNAI / 薩姆 / 10Y-2Y / HY),同一個經濟因子各冒一條。

⚠️ 測試自身可執行性(`PROCESS.md §4`):本檔**不寫任何 importorskip、不 skip**。
   pandas / streamlit 是本 repo 硬依賴,缺件時本檔應該紅而不是製造保護網假象。

⚠️ 位置 / 接線類斷言一律走 **AST**,不切原始碼字串比對:註解裡提到函式名會讓
   `index()` 提前命中,把斷言變成恆真的假通過(本 repo 已踩過兩次同型陷阱)。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_TAB1 = _ROOT / "ui" / "tab1_macro.py"

_PHASE = {"phase": "擴張", "score": 6.8}

# 三層標題的前綴(不含破折號後的副標 —— 副標是文案,隨時可能改字)
_H_L2 = 'st.markdown("### ② 依據'
_H_L3 = 'st.markdown("### ③ 例外'
_H_L4 = 'st.markdown("### ④ 可信度'


def _fn_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    return str(getattr(call.func, "attr", ""))


def _tab1_tree() -> ast.Module:
    return ast.parse(_TAB1.read_text(encoding="utf-8"))


def _calls(fname: str) -> list:
    return [n for n in ast.walk(_tab1_tree())
            if isinstance(n, ast.Call) and _fn_name(n) == fname]


def _line_of(marker: str) -> int:
    _src = _TAB1.read_text(encoding="utf-8")
    return _src[:_src.index(marker)].count("\n") + 1


def _render_capturing_levels(monkeypatch, st_sys, mbv, render, rows, fn, coll):
    """跑 `render_evidence_table` 並把 caption **依揭露層級**分開收。

    回傳 `[(層名, [該層的 caption, ...]), ...]`。`st.expander` 被換成一個
    context manager,進去之後的 caption 記到摺疊層 —— 這樣才分得出
    「散成兩則」與「分成兩層」(舊斷言 `len(_caps) == 1` 分不出來)。
    """
    import contextlib
    _levels: list = [("常駐", [])]
    _cur = {"buf": _levels[0][1]}

    @contextlib.contextmanager
    def _fake_expander(label, **kw):
        assert kw.get("expanded") is not True, (
            "摺疊區用了 expanded=True —— 那是空殼,見 test_audit_20260810_tab1_shells")
        _buf: list = []
        _levels.append((f"摺疊<{label}>", _buf))
        _prev, _cur["buf"] = _cur["buf"], _buf
        try:
            yield
        finally:
            _cur["buf"] = _prev

    for _mod in {id(st_sys): st_sys, id(mbv.st): mbv.st}.values():
        monkeypatch.setattr(_mod, "caption",
                            lambda *a, **k: _cur["buf"].append(str(a[0])),
                            raising=False)
        monkeypatch.setattr(_mod, "dataframe", lambda df, **kw: None, raising=False)
        monkeypatch.setattr(_mod, "expander", _fake_expander, raising=False)
    render(rows, footnotes=fn, collapsed_footnotes=coll)
    return [(_n, _c) for _n, _c in _levels if _c]


def _summary(indicators=None, *, phase_info=None, news_items=None):
    from ui.helpers.macro.beginner_view import compute_five_bucket_summary
    return compute_five_bucket_summary(
        indicators or {},
        phase_info=_PHASE if phase_info is None else phase_info,
        news_items=news_items)


# ══════════════════════════════════════════════════════════════
# 🔴 必修 1 — 缺值不得被畫成「正常」
# ══════════════════════════════════════════════════════════════
class TestMissingReadingsAreNotPaintedGreen:
    def test_short_bucket_without_vix_or_hy_is_not_green(self):
        """**修正前必紅(行為衝突)** —— 修正前 `_v("VIX") or 0.0` 讓空 indicators
        走出 `level="green"` + headline「VIX 0.0 正常」。0.0 是**捏造的讀數**,
        而且剛好是最健康的那一端(§1:錯誤的數字比沒有數字更危險)。"""
        _s = _summary({})
        assert _s["short"]["level"] != "green", "缺 VIX / HY 卻亮綠燈"
        assert "0.0" not in _s["short"]["headline"], (
            f"headline 又出現捏造的 0.0 讀數:{_s['short']['headline']!r}")
        assert _s["short"].get("spec_key") is None, (
            "沒有讀數卻還指著 VIX 的門檻 —— 讀者會以為畫面正在講 VIX")

    def test_short_bucket_falls_back_to_hy_when_only_hy_is_available(self):
        """只有 HY 有值 → 仍報真實讀數(不是退回「未取得」),spec 指向 HY。
        **修正前必紅(行為衝突)**:修正前恆報 `VIX 0.0 正常` / spec 恆為 vix。"""
        _s = _summary({"HY_SPREAD": {"value": 3.21}})
        # ⚠️ 2026-09-04 第五輪稽核 F8：舊斷言是 ~~`level == "green"`~~
        # （**有意識的更正，不是漏刪**）。兩顆只取到一顆，而「兩顆都沒越線」是
        # 一句**點名輸入的全稱話** —— 缺 VIX 就不能講，燈號改灰。
        # **本測試要測的東西沒有變**（真實讀數要報出來、spec 指向 HY），
        # 那兩條原封保留；變的只是「一顆就宣告全清」這個舊判定。
        assert _s["short"]["level"] == "gray"
        assert "3.21" in _s["short"]["headline"]
        assert _s["short"]["spec_key"] == "hy_spread"

    def test_inflection_without_sahm_does_not_count_it_as_safe(self):
        """**修正前必紅(行為衝突)** —— 薩姆 `or 0.0` 讓「沒抓到」被算成
        「0.0 遠低於 0.5,安全」,並計入全綠宣告。"""
        _s = _summary({})
        assert _s["inflection"]["level"] != "green"
        assert "薩姆" in _s["inflection"]["headline"], "沒說薩姆這顆是未取得"

    def test_all_clear_headline_names_only_what_was_actually_checked(self):
        """**修正前必紅(行為衝突)** —— 修正前寫死「PMI/CPI/失業 三項皆健康」,
        只有 PMI 抓到時畫面照樣宣告三項皆健康(把「沒問到」講成「問過了沒事」)。

        刻意不比對整句文案(user 可改字),只驗兩件事:有值的被點名、
        缺的那幾顆有出現在同一句裡。"""
        _s = _summary({"PMI": {"value": 55.0}})
        _h = _s["mid"]["headline"]
        # ⚠️ 2026-09-04 第五輪稽核 F8：舊斷言是
        # ~~`assert _s["mid"]["level"] == "green", "PMI 有值且未越線 → 這一桶確實是綠"`~~
        # （**有意識的更正，不是漏刪**）。**這一條正是稽核逐字點名的那個狀態**：
        #     只取到 PMI → {"level":"green","label":"循環健康",
        #                   "headline":"PMI 皆未越線；CPI／失業 未取得"}
        # headline 誠實、燈號說謊，而使用者先看到的是燈號與顏色。
        # 「三項都沒越線」是點名輸入的全稱話 ⇒ 缺一項就不能出綠燈。
        # **本測試原本要測的東西一字未動**（下面兩條：有值的被點名、缺的被標出來），
        # 而且下一條 `test_full_house_still_reports_plain_green` 仍然釘住
        # 「三顆全在就要出綠燈」—— 沒有把這一桶灰死。
        assert _s["mid"]["level"] == "gray", "三顆只取到一顆，不得宣告『循環健康』"
        assert "PMI" in _h
        for _absent in ("CPI", "失業"):
            assert _absent in _h, f"缺的 {_absent} 沒被標出來:{_h!r}"

    def test_full_house_still_reports_plain_green(self):
        """反向:三顆都有值且都沒越線 → 綠燈,且**不得**出現「未取得」字樣
        (為了修上一條而把健康講成缺料,是另一種假訊號)。"""
        _s = _summary({"PMI": {"value": 55.0}, "CPI": {"value": 2.1},
                       "UNEMPLOYMENT": {"value": 4.0}})
        assert _s["mid"]["level"] == "green"
        assert "未取得" not in _s["mid"]["headline"]

    def test_hit_path_is_unchanged(self):
        """回歸:真的越線時,讀數與 spec 身分一字未變(修的是缺值,不是判讀)。"""
        _s = _summary({"VIX": {"value": 35.0}, "SAHM": {"value": 0.6}})
        assert _s["short"]["level"] == "red" and "35.0" in _s["short"]["headline"]
        assert _s["inflection"]["level"] == "red"
        assert _s["inflection"]["spec_key"] == "sahm"

    def test_no_data_buckets_render_a_gray_light_not_a_blank(self):
        """§1 + dataviz:沒資料要有自己的燈(⬜)+ 文字,不是空白或綠。"""
        _s = _summary({})
        for _k in ("mid", "short", "inflection"):
            assert _s[_k]["emoji"], f"{_k} 桶沒有燈號 emoji"
            assert _s[_k]["label"].strip(), f"{_k} 桶沒有判讀文字"
            assert _s[_k]["color"], f"{_k} 桶沒有色票 —— gray 沒進 level→color 表"


# ══════════════════════════════════════════════════════════════
# 🔴 必修 2 — ② 降級時 ③ 不得宣稱「都不在警戒狀態」
# ══════════════════════════════════════════════════════════════
class TestSummaryFailureIsNotReportedAsAllClear:
    def test_sentinel_none_produces_an_honest_line(self):
        """**修正前必紅(ImportError)** —— 判讀函式本輪新增。
        `None` = ② 沒跑完 → 必須補一條「無法判定」,③ 才不會走到全清那句。"""
        from ui.tab1_macro import _bucket_status_unavailable_line
        _lines = _bucket_status_unavailable_line(None)
        assert len(_lines) == 1 and _lines[0].strip()

    def test_summary_that_ran_produces_nothing_extra(self):
        """反向:② 跑完(dict,含空 dict)→ 不得憑空多一條警示。"""
        from ui.tab1_macro import _bucket_status_unavailable_line
        assert _bucket_status_unavailable_line({}) == []
        assert _bucket_status_unavailable_line({"news": {"level": "green"}}) == []

    def test_layer_three_is_wired_to_the_sentinel(self):
        """接線(`PROCESS.md §4`):判讀寫得再對,③ 沒呼叫就是 0 consumer。
        用 AST + lineno 釘在 ③~④ 之間 —— 拿掉那一行就紅。
        **修正前必紅(ImportError→AST 找不到呼叫)**。"""
        _lo, _hi = _line_of(_H_L3), _line_of(_H_L4)
        assert [c for c in _calls("_bucket_status_unavailable_line")
                if _lo < c.lineno < _hi], "③ 例外層沒讀哨兵 —— ② 壞掉時又會宣稱全清"

    def test_summary_variable_starts_as_the_sentinel_not_an_empty_dict(self):
        """**修正前必紅(行為衝突)** —— 修正前是 `_5b_summary: dict = {}`,
        ② 整段 except 時它維持 `{}`,與「② 跑完但全綠」完全同形,兩態無法區分。

        釘的是**② 這一層的初值**:AST 找 ②~③ 之間對 `_5b_summary` 的賦值,
        它必須是 `None` 常數。有人改回 `{}` / `dict()` → 這裡紅。"""
        _lo, _hi = _line_of(_H_L2), _line_of(_H_L3)
        _inits = [
            _n for _n in ast.walk(_tab1_tree())
            if isinstance(_n, (ast.Assign, ast.AnnAssign))
            and _lo < _n.lineno < _hi
            and any(isinstance(_t, ast.Name) and _t.id == "_5b_summary"
                    for _t in (getattr(_n, "targets", None) or [_n.target]))
        ]
        assert _inits, "找不到 `_5b_summary` 的初值賦值 —— 結構變了,本測試需重寫"
        _first = min(_inits, key=lambda n: n.lineno)
        assert isinstance(_first.value, ast.Constant) and _first.value.value is None, (
            "`_5b_summary` 的初值不是 None 哨兵 —— ② 降級與 ② 全綠又變成同一態")


# ══════════════════════════════════════════════════════════════
# 🔴 必修 3 — 欄內短句 / 長句搬表下(只搬不刪)
# ══════════════════════════════════════════════════════════════
class TestLongNotesMovedBelowTheTable:
    def test_short_threshold_is_a_truncation_not_a_rewrite(self):
        """§3.3:短句不得手打。截斷規則只做一件事 —— 去掉尾端補充括號;
        沒有尾括號的 note 原樣回傳(一個字都不動)。
        **修正前必紅(ImportError)**。"""
        from ui.helpers.macro.beginner_view import _spec_threshold_short
        assert _spec_threshold_short("≥22 警戒 / ≥30 危機") == "≥22 警戒 / ≥30 危機"
        assert _spec_threshold_short("A / B(補充說明)") == "A / B"
        assert _spec_threshold_short("A / B（全形補充）") == "A / B"
        assert _spec_threshold_short("") == ""
        # 短句必須是完整 note 的**前綴**(才叫截斷),對 registry 每一條都成立
        from shared.macro_buckets import BUCKET_DANGER_SPECS
        for _s in BUCKET_DANGER_SPECS:
            assert _s.note.startswith(_spec_threshold_short(_s.note)), (
                f"{_s.key} 的短句不是 note 的前綴 —— 那就是改寫不是截斷")

    def test_every_footnote_starts_with_the_row_it_belongs_to(self):
        """表下每一則要說得出它對應上表哪一列,面向走 `BUCKET_META` SSOT。
        **修正前必紅(ImportError)**。"""
        from shared.macro_buckets import BUCKET_META
        from ui.helpers.macro.beginner_view import (
            _STRENGTH_FACE,
            build_evidence_footnotes,
        )
        _fn = build_evidence_footnotes(_summary(news_items=[]))
        # 刻意用 `startswith` 而不是切分隔符再比對:分隔符是全形冒號,
        # 肉眼分不出全形 `:` 與半形 `:`,在測試裡重打一次就是埋假警報。
        assert any(_f.startswith(_STRENGTH_FACE) for _f in _fn)
        for _k in ("long", "mid", "short", "inflection", "news"):
            _face = f'{BUCKET_META[_k]["emoji"]} {BUCKET_META[_k]["title"]}'
            assert any(_f.startswith(_face) for _f in _fn), (
                f"表下少了 {_face} 那一列的完整說明")

    def test_footnotes_are_empty_safe(self):
        """邊界:summary 全空 / None → 仍回得出強度那一則,不 raise。"""
        from ui.helpers.macro.beginner_view import build_evidence_footnotes
        for _s in (None, {}, "boom"):
            _fn = build_evidence_footnotes(_s)
            assert _fn and all(str(_x).strip() for _x in _fn)

    def test_composite_action_moved_out_of_the_cell_into_the_footnote(self):
        """**修正前必紅(行為衝突)** —— 白話行動原本擠在 🩺 那一格,實測斷在
        「…衛星部位積」。搬到表下;沒傳就不寫(§1 不捏造)。"""
        from ui.helpers.macro.beginner_view import (
            build_evidence_footnotes,
            build_evidence_rows,
        )
        _s = _summary()
        _act = "衛星部位積極加碼哨兵字串"
        _cell = " ".join(str(_v) for _r in build_evidence_rows(
            _s, composite_score=1.0, composite_icon="🟢", composite_level="樂觀",
            composite_action=_act, n_indicators=25) for _v in _r.values())
        assert _act not in _cell, "白話行動還留在格子裡,會被 dataframe 截斷"
        assert _act in "\n".join(
            build_evidence_footnotes(_s, composite_action=_act))
        assert _act not in "\n".join(build_evidence_footnotes(_s))

    def test_footnotes_ride_in_one_caption_per_disclosure_level(self, monkeypatch):
        """契約回歸(2026-09-03 減字 B 後改寫,**不是放寬**)。

        ⚠️ **舊契約是什麼、為什麼要改**:舊斷言是 `len(_caps) == 1`
        (「表下註記只有一則 caption」)。它要防的是 user 說的「不要留兩份說法」——
        也就是**同一層裡**散成一堆各自為政的註腳,以及長句被塞回 `st.dataframe`
        的字串格裡被截斷(2026-08-05 必修 3 的本體)。
        減字 B 之後,表下分成**兩層**:常駐 caption 一則 + 摺疊區內 caption 一則,
        `len(_caps) == 1` 會把**分層**誤報成**散落**。

        **新契約比舊的嚴,守的是同樣三件事外加一件**:
          (a) **每一層各自只有一則** caption(散落仍然紅);
          (b) 層數**最多兩層**(常駐 + 一個摺疊),不得再長出第三層;
          (c) 每一則 footnote 都真的出現在某一層(一則都不掉);
          (d) 🆕 footnote 全文**不得**出現在 dataframe 的格子裡 ——
              這是舊斷言只靠 docstring 交代、**從來沒有真的驗過**的那一半
              (必修 3 的原始病灶就是它被截斷)。
        """
        import streamlit as _st_sys

        import ui.helpers.macro.beginner_view as _mbv
        from ui.helpers.macro.beginner_view import (
            build_evidence_footnotes,
            build_evidence_rows,
            render_evidence_table,
            split_evidence_footnotes,
        )
        _s = _summary(news_items=[])
        _act = "哨兵行動"
        _fn = build_evidence_footnotes(_s, composite_action=_act)
        _pin, _coll = split_evidence_footnotes(_s, composite_action=_act)
        _rows_ = build_evidence_rows(
            _s, composite_score=1.0, composite_icon="🟢", composite_level="樂觀",
            composite_action=_act, n_indicators=25)

        _levels = _render_capturing_levels(
            monkeypatch, _st_sys, _mbv, render_evidence_table,
            _rows_, _fn, _coll)

        # (b) 常駐 + 最多一個摺疊
        assert 1 <= len(_levels) <= 2, f"表下層數異常:{len(_levels)}"
        # (a) 每一層各自只有一則 caption
        for _lvl, _caps in _levels:
            assert len(_caps) == 1, f"{_lvl} 這一層有 {len(_caps)} 則 caption,應只有一則"
        # (c) 一則都不掉
        _all = "\n".join(_c for _, _caps in _levels for _c in _caps)
        for _f in _fn:
            assert _f in _all, f"表下漏掉一則:{_f!r}"
        # (d) 長句不得回到會被截斷的格子裡
        _cells = " ".join(str(_v) for _r in _rows_ for _v in _r.values())
        for _f in _fn:
            _body = _f.split(":", 1)[-1]
            assert _body not in _cells, (
                f"footnote 全文又被塞回 dataframe 格子(會被截斷):{_f!r}")
        assert _pin and _coll, "分層失效 —— 有一層是空的"

    def test_tab1_actually_passes_the_footnotes(self):
        """**接線**(`PROCESS.md §4`,本輪唯一的側車):helper 算得再對,
        `render_evidence_table` 沒收到 `footnotes=` 就等於那幾句在畫面上消失。
        判準:拿掉呼叫端那個關鍵字引數 → 本條紅。
        **修正前必紅(AST 找不到 `build_evidence_footnotes`)**。"""
        assert _calls("build_evidence_footnotes"), "tab1 沒建表下說明"
        _rt = _calls("render_evidence_table")
        assert _rt, "tab1 沒渲染 ② 依據表"
        _kw = {k.arg: k.value for c in _rt for k in c.keywords}
        assert "footnotes" in _kw, "render_evidence_table 沒收到 footnotes"
        assert not isinstance(_kw["footnotes"], ast.Constant), (
            "footnotes 傳的是常數字面值 —— 表下說明不會跟著資料動")


# ══════════════════════════════════════════════════════════════
# 🔴 必修 4 — ⚡ 今日關鍵橫幅跨層去重
# ══════════════════════════════════════════════════════════════
def _ind(score=-1.0, weight=1.0, name="測試指標", value=1.23, unit="%"):
    return {"name": name, "value": value, "unit": unit,
            "score": score, "weight": weight}


def _tp(icon="🔴", *, indicator_key=None, label="拐點", signal="訊號",
        note="白話說明", source_ok=True):
    _d = {"icon": icon, "signal": signal, "label": label,
          "note": note, "source_ok": source_ok}
    if indicator_key is not None:
        _d["indicator_key"] = indicator_key
    return _d


class TestKeyAlertsCrossLayerDedup:
    def test_same_factor_is_not_announced_twice(self):
        """**修正前必紅(行為衝突)** —— 修正前兩層直接相加,CFNAI 這一顆
        訊號層一條 + 拐點層一條,橫幅上同一個經濟因子講兩次
        (與本檔案 :53-54 對 M2 去重寫下的判準完全同一條)。"""
        from services.macro.daily_key_alerts import collect_key_alerts
        _out = collect_key_alerts(
            {"LEI": _ind(name="CFNAI 領先指標")},
            {"lei_cfnai": _tp(indicator_key="LEI", label="CFNAI 領先指標 3M MA")})
        assert len(_out["items"]) == 1
        assert _out["items"][0]["layer"] == "turning_point", (
            "留下來的應該是拐點層那條(帶事件語意 + note 白話)")

    def test_non_event_turning_point_does_not_silence_the_signal_layer(self):
        """反向(不可少報):拐點是 🟢 非事件時,它根本沒進橫幅 —— 此時訊號層
        那條講的是另一件事(水位 vs 轉折),必須照常顯示。"""
        from services.macro.daily_key_alerts import collect_key_alerts
        _out = collect_key_alerts(
            {"LEI": _ind(name="CFNAI 領先指標")},
            {"lei_cfnai": _tp("🟢", indicator_key="LEI")})
        assert len(_out["items"]) == 1
        assert _out["items"][0]["layer"] == "signal"

    def test_unrelated_factors_both_survive(self):
        """反向(不可誤殺):拐點自報的 key 與訊號層不同 → 兩條都留。"""
        from services.macro.daily_key_alerts import collect_key_alerts
        _out = collect_key_alerts(
            {"VIX": _ind(name="VIX")},
            {"sahm_rule": _tp(indicator_key="SAHM")})
        assert len(_out["items"]) == 2

    def test_turning_point_without_a_key_dedups_nothing(self):
        """§3.3:去重事實由**產生端**的 `indicator_key` 提供;沒宣告就不去重
        (消費端不得自己猜 key 對應)。"""
        from services.macro.daily_key_alerts import collect_key_alerts
        _out = collect_key_alerts({"LEI": _ind()}, {"pmi_diff": _tp()})
        assert len(_out["items"]) == 2

    def test_producer_declares_the_mapping(self):
        """產生端守衛(與上面的消費端合起來才是完整接線)——
        四個同因子拐點各自宣告 key,新訂單−庫存那個刻意是 None(不同定義)。
        **修正前必紅(欄位不存在 → KeyError)**。"""
        from services.macro.turning_points import detect_turning_points
        _out = detect_turning_points("")   # 無 key → 全部走預設骨架
        _want = {"yield_curve": "YIELD_10Y2Y", "hy_spread": "HY_SPREAD",
                 "sahm_rule": "SAHM", "lei_cfnai": "LEI", "pmi_diff": None}
        for _k, _v in _want.items():
            assert _out[_k]["indicator_key"] == _v, f"{_k} 的同因子宣告不對"

    def test_declared_keys_exist_in_the_indicator_registry(self):
        """漂移鎖:拐點宣告的 key 必須是服務層真的會產生的指標 key,
        否則去重永遠不會命中(「算對了但沒接出去」的同型缺陷,`PROCESS.md §4`)。

        比對集合用**兩份既有 SSOT 的聯集**,本檔不另抄一份清單:
          - `ui.helpers.session.D5_KEYS`(v19.195,16 個資料健康關鍵指標)
          - `ui.tab1_macro_midcycle._ZS_INDICATORS`(Z-Score 矩陣盤,18 個)
        兩份各自都不完整(前者無 LEI、後者無殖利率差 / HY / 薩姆),
        聯集才覆蓋得到四個同因子拐點對應的 key。
        """
        from services.macro.turning_points import detect_turning_points
        from ui.helpers.session import D5_KEYS
        from ui.tab1_macro_midcycle import _ZS_INDICATORS
        _known = set(D5_KEYS) | {_r[0] for _r in _ZS_INDICATORS}
        for _k, _d in detect_turning_points("").items():
            _ik = _d.get("indicator_key")
            if _ik is not None:
                assert _ik in _known, f"{_k} 宣告了不存在的指標 key {_ik!r}"


# ══════════════════════════════════════════════════════════════
# 🟡 建議 7 — 歷史錨點名單鋪滿全表
# ══════════════════════════════════════════════════════════════
class TestEduAnchorCoversTheWholeMatrix:
    def test_pilot_list_is_derived_from_the_matrix(self):
        """**修正前必紅(行為衝突)** —— 修正前是 3 個 key 的樣張硬編碼。
        名單改由 `_ZS_INDICATORS` 導出,矩陣增減指標時自動跟上(§3.3)。"""
        from ui.tab1_macro_midcycle import _EDU_ANCHOR_PILOT, _ZS_INDICATORS
        assert _EDU_ANCHOR_PILOT == frozenset(_r[0] for _r in _ZS_INDICATORS)

    def test_coverage_still_reports_the_honest_number(self):
        """§1:鋪滿名單**不等於**每張都有錨點 —— `MACRO_EDU` 缺語料的那幾張
        不掛也不計入覆蓋率,caption 上的數字仍是真的。"""
        from ui.components.macro_card_edu import MACRO_EDU
        from ui.tab1_macro import _zs_danger_spec_key
        from ui.tab1_macro_midcycle import (
            _decoration_coverage,
            _EDU_ANCHOR_PILOT,
            _ZS_INDICATORS,
        )
        _keys = [_r[0] for _r in _ZS_INDICATORS]
        _want = len([_k for _k in _keys if _k in _EDU_ANCHOR_PILOT
                     and str((MACRO_EDU.get(_k) or {}).get(
                         "historical_anchor") or "").strip()])
        _n_anchor, _ = _decoration_coverage(_zs_danger_spec_key)
        assert _n_anchor == _want
        assert _n_anchor <= len(_keys), "覆蓋率不可能超過總張數"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
