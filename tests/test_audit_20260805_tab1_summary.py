"""2026-08-05 F1 — Tab① 總表區(四層資訊架構)的守衛 + **接線驗證**。

user 拍板:「最重要的總表放在最上方,下方都是放詳細資料與說明」,
形式為混合 —— 結論用敘事、依據用表格。四層:
  ① 結論(敘事)  ② 依據(表格)  ③ 例外(敘事)  ④ 可信度(chip + 既有新鮮度條)

本檔守三件事:
  A. **② 依據表的資料契約** —— 兩把尺(景氣位階 / 多空強度)並陳且各自標明
     怎麼讀;5 桶一個不少;缺值誠實留「—」不捏造。
  B. **指路不得指到空氣** —— `_BUCKET_SECTION_HINT` 的每個標題都必須真的是
     下方某個 section 的 heading(對照本 repo 舊 bug:指路文案寫死
     「📦 投資組合」,而 app.py 根本沒有那個分頁)。
  C. **接線** —— tab1 真的建了列、真的渲染、四層真的照 ①②③④ 排;
     `PROCESS.md §4`:只驗「helper 自己能跑」的測試在本 repo 一律不算數。

⚠️ 測試自身可執行性(`PROCESS.md §4`):本檔**不寫任何 importorskip**。
   pandas / streamlit / plotly 都是本 repo 硬依賴,缺件時本檔應該紅而不是
   skip —— skip 會製造「有測試守著」的假象。

每條 test 的 docstring 標明「修正前紅在哪」。本波之前 `build_evidence_rows`
/ `render_evidence_table` / `section_hint` / `_BUCKET_SECTION_HINT` 全部不存在,
故 A / B 兩組修正前一律 **ImportError → 紅**;C 組另有逐條說明。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_TAB1 = _ROOT / "ui" / "tab1_macro.py"
_BEGINNER = _ROOT / "ui" / "helpers" / "macro" / "beginner_view.py"

# 桶 → 該桶細節實際住在哪個檔(指路漂移鎖用)
_HINT_HOME = {
    "long":       _ROOT / "ui" / "tab1_macro_longterm.py",
    "mid":        _ROOT / "ui" / "tab1_macro_midcycle.py",
    "short":      _ROOT / "ui" / "tab1_macro_radar.py",
    "inflection": _ROOT / "ui" / "tab1_macro_inflection.py",
    # 📰 市場新聞是「🌳 長期座標」section 內的折疊區,不是獨立一級區塊
    "news":       _ROOT / "ui" / "tab1_macro_longterm.py",
}

_PHASE = {"phase": "擴張", "score": 6.8}

# 四層標題的**前綴**(刻意不含破折號後的副標):副標是文案,user 隨時可能改字;
# 標題編號與層名才是架構契約。用前綴比對 → 改副標不會誤紅,拿掉整層一定紅。
_H_SUMMARY = 'st.markdown("## 🧾 總表'
_H_L1 = 'st.markdown("### ① 結論'
_H_L2 = 'st.markdown("### ② 依據'
_H_L3 = 'st.markdown("### ③ 例外'
_H_L4 = 'st.markdown("### ④ 可信度'
_H_DETAIL = 'st.markdown("## 🔎 詳細資料'


def _fn_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    return str(getattr(call.func, "attr", ""))


def _calls(path: Path, fname: str) -> list:
    _tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n for n in ast.walk(_tree)
            if isinstance(n, ast.Call) and _fn_name(n) == fname]


def _line_of(src: str, marker: str) -> int:
    """`marker` 首次出現的行號(1-based)。"""
    return src[:src.index(marker)].count("\n") + 1


def _calls_between(fname: str, start_marker: str, end_marker: str) -> list:
    """`ui/tab1_macro.py` 中,落在兩個標題之間的 `fname` 呼叫節點。

    刻意走 **AST + lineno** 而不是「切一段原始碼再 `in` 比對」:
    後者會被註解裡提到的函式名騙成假通過(本 repo 已踩過兩次同型陷阱)。
    AST 只看真的呼叫節點,`lineno` 再確認它落在該層的版面範圍內 ——
    把呼叫端那一行刪掉、或搬到別層,這裡就會紅。
    """
    _src = _TAB1.read_text(encoding="utf-8")
    _lo, _hi = _line_of(_src, start_marker), _line_of(_src, end_marker)
    return [c for c in _calls(_TAB1, fname) if _lo < c.lineno < _hi]


def _norm(s: str) -> str:
    """去掉 emoji variation selector(U+FE0F)再比對。

    它是**不可見**的字型提示,不是語意差異;若不正規化,兩邊只要有一邊多打/
    少打一個 VS16,測試就會以「標題改名了」的錯誤理由紅掉(誤導性遠大於保護)。
    真正的改名(換字、換 emoji base char)照樣會被抓到。

    ⚠️ 這裡刻意用 `chr(0xFE0F)` 而不是直接把那個字元貼進字串 —— 它在編輯器裡
       完全不可見,貼進原始碼後沒有人能用眼睛確認貼對了沒有。
    """
    return s.replace(chr(0xFE0F), "")


def _rows(**kw) -> list[dict]:
    from ui.helpers.macro.beginner_view import (
        build_evidence_rows,
        compute_five_bucket_summary,
    )
    _summary = kw.pop("summary", None)
    if _summary is None:
        _summary = compute_five_bucket_summary(
            kw.pop("indicators", {}), phase_info=kw.pop("phase_info", _PHASE),
            news_items=kw.pop("news_items", None))
    _defaults = dict(composite_score=15.5, composite_icon="🟢",
                     composite_level="極度樂觀", composite_action="多頭市場強勁",
                     n_indicators=25)
    _defaults.update(kw)
    return build_evidence_rows(_summary, **_defaults)


def _note_col() -> str:
    """「說明」欄名 —— 從 SSOT `EVIDENCE_COLUMNS` 取,不在測試裡重打一次。

    該欄名含全形括號,肉眼難以分辨全形 `（` 與半形 `(`;重打一次 = 埋一顆
    「測試因為括號寬度不同而紅」的假警報。
    """
    from ui.helpers.macro.beginner_view import EVIDENCE_COLUMNS
    return EVIDENCE_COLUMNS[3]


# ══════════════════════════════════════════════════════════════
# A — ② 依據表的資料契約
# ══════════════════════════════════════════════════════════════
class TestEvidenceRows:
    def test_rows_follow_bucket_order_and_include_all_buckets(self):
        """**修正前必紅**(函式不存在)—— 5 桶一個不少,且順序照 `BUCKET_ORDER`,
        位階列與強度列**必須相鄰**(兩把尺並陳才看得出差異,這是本表的存在理由)。"""
        from shared.macro_buckets import BUCKET_META
        _r = _rows(news_items=[{"title": "x", "is_systemic": False}])
        _faces = [x["面向"] for x in _r]
        assert len(_r) == 6, f"應為 5 桶 + 綜合健康度 = 6 列,實際 {_faces}"
        assert _faces[0] == f'{BUCKET_META["long"]["emoji"]} {BUCKET_META["long"]["title"]}'
        assert "綜合健康度" in _faces[1], "強度列沒有緊貼位階列 —— 兩把尺沒並陳"
        assert _faces[2:] == [f'{BUCKET_META[k]["emoji"]} {BUCKET_META[k]["title"]}'
                              for k in ("mid", "short", "inflection", "news")]

    def test_both_scales_are_labelled_so_they_cannot_be_confused(self):
        """**修正前必紅** —— 這正是 user 點名的問題:`+15.5` 與 `6.8/10` 並列
        而沒人說它們是兩把尺。位階列要寫「位階 / 恆非負」,強度列要寫
        「強度 / 有正負」,缺一不可。"""
        _r = _rows()
        _long = " ".join(_r[0].values())
        _strength = " ".join(_r[1].values())
        assert "位階" in _long and "恆非負" in _long
        assert "強度" in _strength and "有正負" in _strength
        # 反向:兩列不得互相沾染對方的尺度說明(沾染 = 又變回一鍋粥)
        assert "恆非負" not in _strength

    def test_phase_reading_comes_from_ssot_formatter(self):
        """漂移鎖:位階讀數必須等於 `format_phase_score()`,不得有人另組格式
        (原本 hero 與五桶各寫各的,格式還差一層括號)。"""
        from ui.helpers.macro.helpers import format_phase_score
        assert _rows()[0]["讀數"] == format_phase_score(_PHASE)

    def test_missing_composite_score_shows_dash_not_zero(self):
        """§1 邊界:沒有綜合分數時讀數必須是「—」。
        填 0.0 會被 `composite_verdict` 讀成「中性」= 憑空生出一個判讀。"""
        _r = _rows(composite_score=None, composite_icon="", composite_level="")
        assert _r[1]["讀數"] == "—"
        assert _r[1]["判讀"] == "—"

    def test_missing_indicator_count_is_omitted_not_faked(self):
        """§1 + `PROCESS.md §4`:側車沒給筆數就不要寫筆數。
        **修正前必紅**(舊 hero 卡是寫死字面值,且已與實際漂移)。"""
        import re
        _r = _rows(n_indicators=None)
        _note = _r[1][_note_col()]
        assert "指標加權淨分" in _note
        assert not re.search(r"\d+\s*指標", _note), f"筆數是憑空生出來的:{_note!r}"
        # 有給就要寫出來(反向,確保上面不是因為整段不見才通過)
        assert "25 指標加權淨分" in _rows(n_indicators=25)[1][_note_col()]

    def test_missing_news_bucket_just_drops_that_row(self):
        """向下相容:餵 4 桶 summary(無 news key)→ 少一列,不補假桶、不炸。
        對應舊 `render_five_bucket_bar` 的 5→4 columns fallback。"""
        from ui.helpers.macro.beginner_view import compute_four_horizon_summary
        _r = _rows(summary=compute_four_horizon_summary({}, phase_info=_PHASE))
        assert len(_r) == 5
        assert not [x for x in _r if "新聞" in x["面向"]]

    def test_empty_summary_still_reports_the_strength_row(self):
        """邊界:summary 全空 → 只剩強度列(它不依賴桶),不 raise、不回空 list。"""
        _r = _rows(summary={})
        assert len(_r) == 1 and "綜合健康度" in _r[0]["面向"]

    def test_every_row_points_somewhere(self):
        """本次資訊架構的核心機制:每一列都要說「詳細在下方哪一段」。
        **修正前必紅** —— 舊五桶 bar 完全沒有這一欄,使用者只能自己找。"""
        from ui.helpers.macro.beginner_view import EVIDENCE_COLUMNS
        for _x in _rows(news_items=[]):
            assert set(_x) == set(EVIDENCE_COLUMNS), "欄位與宣告的 schema 不一致"
            assert _x["詳細在下方哪一段"].strip(), f"{_x['面向']} 這列沒有指路"

    def test_labels_still_come_from_bucket_meta(self):
        """回歸:面向 / 說明兩欄仍走 `_bucket_bar_cells`(BUCKET_META SSOT),
        不得有人在表格層又抄一份桶名。

        ⚠️ 說明欄用 `startswith` 而非 `==`:本輪必修 2 之後,這四列的說明欄是
        「桶副標 ＋ 該列讀數的判讀門檻」,`==` 會與那項必修直接互斥。
        `build_evidence_rows._bucket_row` 的組法是「副標在前、延長內容在後」,
        所以 `startswith` 完整保住本測試的原意 —— 有人在表格層重打一份桶名
        (而不是從 SSOT 取)照樣紅。「只有副標、沒有延長」那一面由
        `test_audit_20260805_evidence_notes.py` 的
        `test_four_remaining_rows_say_more_than_the_bucket_subtitle` 守。"""
        from shared.macro_buckets import BUCKET_ORDER
        from ui.helpers.macro.beginner_view import _bucket_bar_cells
        _cells = {k: (t, s) for k, t, s in _bucket_bar_cells(BUCKET_ORDER)}
        _r = _rows(news_items=[])
        for _key in ("mid", "short", "inflection", "news"):
            _t, _s = _cells[_key]
            _row = next(x for x in _r if x["面向"] == _t)
            assert _row[_note_col()].startswith(_s)

    def test_light_emoji_and_text_travel_together(self):
        """dataviz #4:狀態不得只靠顏色 —— 判讀欄必須 emoji + 文字同格。"""
        _r = _rows(indicators={"VIX": {"value": 35.0}},
                   news_items=[{"title": "war", "is_systemic": True},
                               {"title": "bank fails", "is_systemic": True}])
        _short = next(x for x in _r if "短線" in x["面向"])
        assert _short["判讀"].startswith("🔴") and len(_short["判讀"]) > 2


# ══════════════════════════════════════════════════════════════
# B — 指路不得指到空氣(漂移鎖)
# ══════════════════════════════════════════════════════════════
class TestSectionHints:
    def test_macro_compass_moved_out_of_the_summary_zone(self):
        """**修正前必紅** —— 總經指南針原本由 `app.py` 在 `render_macro_tab()`
        之前呼叫,三張原始值卡(VIX / 10Y / S&P 500)永遠壓在總表最上方。

        user 2026-08-05 拍板 A 案:原始值屬「依據 / 例外」層級不是結論,
        應歸詳細區。兩段都要過才算搬完:
          (a) `app.py` 不再呼叫也不再 import(留在那裡 = 沒搬,只是多一份);
          (b) `ui/tab1_macro.py` 真的呼叫了,且位置在「詳細資料與說明」分界**之後**。
        """
        import ast
        _app = _ROOT / "app.py"
        _app_src = _app.read_text(encoding="utf-8")
        _app_tree = ast.parse(_app_src)
        # (a) app.py 已無呼叫、也無 import(註解裡提及沿革不算)
        assert not [
            n for n in ast.walk(_app_tree)
            if isinstance(n, ast.Call)
            and str(getattr(n.func, "id", "") or getattr(n.func, "attr", "")) == "render_macro_compass"
        ], "app.py 仍在呼叫 render_macro_compass —— 指南針沒真的搬走"
        assert not [
            n for n in ast.walk(_app_tree)
            if isinstance(n, ast.ImportFrom)
            and any(a.name == "render_macro_compass" for a in n.names)
        ], "app.py 仍 import render_macro_compass —— 會是 F401 死 import"

        # (b) tab1_macro.py 真的接手,且落在詳細區
        _t1_src = _TAB1.read_text(encoding="utf-8")
        assert "render_macro_compass" in _t1_src, "tab1_macro.py 沒接手指南針 —— 功能整個消失"
        _mount = _t1_src.index("render_macro_compass")
        # ⚠️ 必須比對**完整的 heading 呼叫**。`ui/tab1_macro.py` 有一行註解引用
        #    user 原話「…下方都是放詳細資料與說明」,位置在檔案前段;裸字串會先命中
        #    它,使 `_details` 變得極小 → 本斷言恆成立 = **假通過**(指南針放錯位置
        #    也不會紅)。同型陷阱已在 test_daily_key_alerts_v19_349.py 踩過一次。
        _details = _t1_src.index('st.markdown("## 🔎 詳細資料與說明")')
        assert _details < _mount, "指南針落在總表區 —— 原始值卡又擋在結論前面了"

    def test_section_hints_match_real_headings(self):
        """**修正前必紅**(對照表不存在)。

        每個指路標題都必須真的是對應檔案裡的 `st.markdown("## …")`。
        有人改了 section 標題卻沒同步這張鏡像表 → 這裡紅。
        (本 repo 已經出過一次「指路指向不存在的分頁」的 bug。)
        """
        from ui.helpers.macro.beginner_view import _BUCKET_SECTION_HINT
        assert set(_BUCKET_SECTION_HINT) == set(_HINT_HOME), "桶 key 覆蓋不齊"
        for _k, _heading in _BUCKET_SECTION_HINT.items():
            _src = _norm(_HINT_HOME[_k].read_text(encoding="utf-8"))
            assert _norm(f'st.markdown("## {_heading}")') in _src, (
                f"{_k} 指向「{_heading}」,但 {_HINT_HOME[_k].name} 裡找不到這個標題")

    def test_hint_text_is_actionable(self):
        """指路要是人看得懂的一句話,不是裸標題。"""
        from ui.helpers.macro.beginner_view import section_hint
        _t = section_hint("long")
        assert _t.startswith("詳見下方") and "長期座標" in _t

    def test_unknown_bucket_fails_loud(self):
        """§1:未知桶 key 當場炸,不得回空字串讓畫面出現「詳見下方「」」。"""
        from ui.helpers.macro.beginner_view import section_hint
        with pytest.raises(KeyError):
            section_hint("not_a_bucket")


# ══════════════════════════════════════════════════════════════
# C — 接線(PROCESS.md §4:拿掉呼叫端那一行就要紅)
# ══════════════════════════════════════════════════════════════
class TestTab1WiredToSummaryBlock:
    def test_tab1_builds_and_renders_the_table(self):
        """**修正前必紅** —— 這兩個函式在 tab1 是 0 caller
        (helper 寫得再對,畫面上也看不到)。"""
        assert _calls(_TAB1, "build_evidence_rows"), "tab1 沒有建 ② 依據表的列"
        assert _calls(_TAB1, "render_evidence_table"), "tab1 沒有渲染 ② 依據表"

    def test_table_is_fed_by_the_real_summary_and_provenance(self):
        """接線不得半套:列必須吃真的五桶 summary + provenance 側車筆數,
        不得傳常數(傳常數 = 掛了一張假表)。"""
        _src = _TAB1.read_text(encoding="utf-8")
        assert _calls(_TAB1, "compute_five_bucket_summary"), "沒吃五桶 summary"
        _cs = _calls(_TAB1, "calculate_composite_score")
        assert any(kw.arg == "provenance_out" for c in _cs for kw in c.keywords)
        assert "n_indicators" in _src, "筆數側車沒被讀"
        _b = _calls(_TAB1, "build_evidence_rows")[0]
        _kw = {k.arg: k.value for k in _b.keywords}
        for _name in ("composite_score", "n_indicators"):
            assert _name in _kw, f"build_evidence_rows 少傳 {_name}"
            assert not isinstance(_kw[_name], ast.Constant), (
                f"{_name} 傳的是常數字面值 —— 表格數字不會跟著資料動")

    def test_four_layers_render_in_order(self):
        """**修正前必紅** —— 改版前的順序是「資料新鮮度 → 中國副盤 → 結論燈
        → hero → 五桶」,結論排在第 4 位。user 拍板:結論最上方。"""
        _src = _TAB1.read_text(encoding="utf-8")
        _idx = []
        for _m in (_H_SUMMARY, _H_L1, _H_L2, _H_L3, _H_L4, _H_DETAIL):
            assert _src.count(_m) == 1, f"標題 {_m!r} 應恰好出現一次"
            _idx.append(_src.index(_m))
        assert _idx == sorted(_idx), f"總表四層順序跑掉了:{_idx}"

    def test_details_come_after_the_summary_block(self):
        """詳細區(四時域 + AI)必須全部在總表之後 —— 這是本次重構的主訴求。"""
        _src = _TAB1.read_text(encoding="utf-8")
        _i_detail = _src.index(_H_DETAIL)
        for _sec in ("from ui.tab1_macro_longterm import render_long_term_section",
                     "from ui.tab1_macro_midcycle import render_mid_cycle_section",
                     "from ui.tab1_macro_radar import render_short_radar_section",
                     "from ui.tab1_macro_inflection import render_inflection_alert_section"):
            assert _src.index(_sec) > _i_detail, f"{_sec} 跑到總表前面了"

    def test_key_alerts_banner_moved_into_the_exception_layer(self):
        """**修正前必紅** —— ⚡ 今日關鍵橫幅原本掛在載入按鈕**之前**,
        使用者先看到警示才看到結論,與四層閱讀順序相反。"""
        _src = _TAB1.read_text(encoding="utf-8")
        _i_banner = _src.index("key_alerts_banner")
        assert _src.index(_H_L3) < _i_banner < _src.index(_H_L4), (
            "今日關鍵橫幅不在 ③ 例外層裡")

    def test_trust_layer_discloses_proxy_and_missing_counts(self):
        """**修正前必紅** —— `is_proxy` 旗標服務層早就有,Tab① 頂部
        0 consumer(只有 tab6 明細表與 AI prompt 讀);缺值筆數更是完全沒揭露。
        ④ 可信度層必須讀這兩者,否則「這些數字能信嗎」是空話。

        ⚠️ 兩條斷言原本是**純字串比對**(`'get("value") is None' in _tail`),
        對「那個算式恆為 0」這個缺陷完全免疫 —— 缺值筆數結構上永遠是 0,
        測試照樣綠(`PROCESS.md §4`)。現在改成兩段:
          (a) 這裡驗**接線**(兩個判讀 helper 真的在 ④ 這一層被呼叫);
          (b) 數字對不對由下方 `TestTrustLayerCountsAreReal` 餵資料驗行為。
        """
        assert _calls_between("_proxy_indicator_labels", _H_L4, _H_DETAIL), (
            "④ 可信度沒讀代理值旗標")
        assert _calls_between("_missing_indicator_keys", _H_L4, _H_DETAIL), (
            "④ 可信度沒數缺漏指標")
        assert _calls(_TAB1, "_chip_trust"), "④ 可信度沒用 status_chip 呈現"

    def test_freshness_strip_still_lives_in_the_trust_layer(self):
        """回歸:既有資料新鮮度條(含 FRED 逐序列命中 chip)一字未改地留在 ④,
        沒有在搬家時被順手刪掉。"""
        _src = _TAB1.read_text(encoding="utf-8")
        _tail = _src[_src.index(_H_L4):_src.index(_H_DETAIL)]
        for _keep in ("📊 <b>資料新鮮度</b>", "FRED 命中", "_fred_chip("):
            assert _keep in _tail, f"新鮮度條掉了「{_keep}」"

    def test_old_summary_bars_are_gone_with_no_stale_reference(self):
        """`PROCESS.md §4`:0 consumer → 接線或刪除,不得留著假裝有揭露。
        刪除必須連引用一起清(對照 ruff 白名單那個案例)。"""
        import ui.helpers.macro.beginner_view as _mbv
        for _dead in ("render_four_horizon_bar", "render_five_bucket_bar"):
            assert not hasattr(_mbv, _dead), f"{_dead} 仍在(0 consumer 的死渲染)"
        for _p in (list((_ROOT / "ui").rglob("*.py"))
                   + list((_ROOT / "services").rglob("*.py"))):
            try:
                _t = ast.parse(_p.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for _n in ast.walk(_t):
                if isinstance(_n, ast.Call) and _fn_name(_n) in (
                        "render_four_horizon_bar", "render_five_bucket_bar"):
                    pytest.fail(f"{_p} 仍呼叫已刪除的 summary bar")
                if isinstance(_n, ast.ImportFrom) and any(
                        a.name in ("render_four_horizon_bar", "render_five_bucket_bar")
                        for a in _n.names):
                    pytest.fail(f"{_p} 仍 import 已刪除的 summary bar")

    def test_compute_layer_survived_the_render_deletion(self):
        """刪錯東西的防護:被刪的只有「畫面」,兩個**現役** compute 函式必須
        原樣還在(它們正是 ② 依據表的資料來源)。

        ⚠️ 第三個 compute(交通燈)已於本輪連同 239 LOC 一起移除
        —— production 0 caller,`PROCESS.md §4` 0-consumer 條款;
        它的「確實被刪乾淨」由 `test_audit_20260805_evidence_notes.py`
        的 `TestDeadTrafficLightHelperRemoved` 反向守著。這裡若把它留在
        import list,本檔會 ImportError 全滅。"""
        from ui.helpers.macro.beginner_view import (  # noqa: F401
            compute_five_bucket_summary,
            compute_four_horizon_summary,
        )


# ══════════════════════════════════════════════════════════════
# ④ 可信度層的兩個數字 —— 行為斷言(不是字串比對)
#
# 2026-08-05 稽核 🔴 必修 2 / 🔴 必修 3 / 🟡 建議 5。
# 缺值筆數原本數的是「`value` 為 None 的筆數」,但產生端每一個寫入點都在
# 「值存在」的守衛裡 —— 抓失敗的指標是**整個 key 不存在**。結果是:上游掛掉
# 幾條,這一層照樣顯示 0,而它正是專門回答「這些數字能信嗎」的那一層(§1)。
# 舊測試用字串比對守它,任何恆 0 的實作都照樣綠 → 本組改成餵資料看輸出。
# ══════════════════════════════════════════════════════════════
class TestTrustLayerCountsAreReal:
    def test_missing_count_sees_indicators_that_never_arrived(self):
        """**修正前必紅**(判讀函式不存在;舊算式對這個輸入回 0)。

        模擬上游掛掉 5 條:那 5 個 key **整個不在** `ind` 裡。
        舊寫法遍歷 `ind` 已有的項目找 `value is None`,永遠數到 0。
        """
        from ui.helpers.session import D5_KEYS
        from ui.tab1_macro import _missing_indicator_keys
        _dead = list(D5_KEYS)[:5]
        _ind = {_k: {"name": _k, "value": 1.0}
                for _k in D5_KEYS if _k not in _dead}
        _ind["_fred_sources"] = {"DGS10": {"success": False}}
        assert _missing_indicator_keys(_ind) == _dead

    def test_full_house_reports_nothing_missing(self):
        """反向:16 個關鍵指標都在 → 空 list(不得為了「有揭露」而虛報)。"""
        from ui.helpers.session import D5_KEYS
        from ui.tab1_macro import _missing_indicator_keys
        _ind = {_k: {"name": _k, "value": 1.0} for _k in D5_KEYS}
        assert _missing_indicator_keys(_ind) == []

    def test_expected_list_is_the_shared_ssot_not_a_ui_copy(self):
        """§3.3:預期清單必須是既有 SSOT。全空輸入 → 缺漏數 == 清單長度;
        清單改了(例如日後增列指標),這裡自動跟著變,UI 層抄第二份會對不上。"""
        from ui.helpers.session import D5_KEYS
        from ui.tab1_macro import _missing_indicator_keys
        assert _missing_indicator_keys({}) == list(D5_KEYS)
        assert _missing_indicator_keys(None) == list(D5_KEYS)

    def test_missing_chip_subtitle_carries_both_numbers(self):
        """**修正前必紅**(舊行為與斷言衝突,非 ImportError)。

        缺漏 chip 的主標寫「缺漏 N 筆」,副標卻只帶了**分母**(預期清單長度),
        字面上讀起來是「全部都缺」—— 同一個 chip 兩個數字互相打架。這正是
        §1「錯誤的數字比沒有數字更危險」:修一個假數字時又生一個假數字。

        守法:找「以缺漏清單為條件」的那個三元式,它的**有缺漏那一支**必須同時
        用到分母與分子兩個變數。刻意不比對任何文案字面值 —— user 改寫文案不該
        誤紅,少一個數字才該紅。
        """
        _tree = ast.parse(_TAB1.read_text(encoding="utf-8"))
        _ifexps = [n for n in ast.walk(_tree) if isinstance(n, ast.IfExp)
                   and any(isinstance(x, ast.Name) and x.id == "_missing_keys"
                           for x in ast.walk(n.test))]
        assert _ifexps, "找不到以缺漏清單分支的副標三元式 —— 結構變了,本測試需重寫"
        for _ie in _ifexps:
            _names = {x.id for x in ast.walk(_ie.body) if isinstance(x, ast.Name)}
            assert {"_n_expect", "_n_missing"} <= _names, (
                f"缺漏 chip 副標的有缺漏分支只用到 {_names & {'_n_expect', '_n_missing'}}"
                " —— 只講分母不講分子,畫面會宣稱關鍵指標全數未取得")

    def test_value_present_but_empty_still_counts_as_missing(self):
        """邊界:key 在、值卻是空的(理論上產生端有守衛)→ 寧可多報不可少報。"""
        from ui.helpers.session import D5_KEYS
        from ui.tab1_macro import _missing_indicator_keys
        _ind = {_k: {"name": _k, "value": 1.0} for _k in D5_KEYS}
        _ind[D5_KEYS[0]] = {"name": D5_KEYS[0], "value": None}
        assert _missing_indicator_keys(_ind) == [D5_KEYS[0]]

    def test_proxy_chip_can_name_which_indicator(self):
        """🟡 建議 5 **修正前必紅** —— 原本只有筆數,要知道是哪一筆得往下捲到
        Z-Score 矩陣找 ⚠️ 前綴。名字服務層早就給了(`name`),缺則退 key。"""
        from ui.tab1_macro import _proxy_indicator_labels
        _ind = {
            "PMI": {"name": "PMI（Phil Fed 替代）", "value": 48.0, "is_proxy": True},
            "VIX": {"name": "VIX 恐慌指數", "value": 15.0},
            "DXY": {"value": 100.0, "is_proxy": True},          # 無 name → 退 key
            "_fred_sources": {"DGS10": {"success": True}},      # meta 不算指標
        }
        assert _proxy_indicator_labels(_ind) == ["PMI（Phil Fed 替代）", "DXY"]

    def test_no_proxy_reports_empty_not_a_placeholder(self):
        """§1:沒有代理值就回空,不得回一個佔位字串讓 chip 看起來有內容。"""
        from ui.tab1_macro import _proxy_indicator_labels
        assert _proxy_indicator_labels({"VIX": {"value": 15.0}}) == []
        assert _proxy_indicator_labels({}) == []


# ══════════════════════════════════════════════════════════════
# 渲染端(表格真的收到列,不只是「沒 raise」)
# ══════════════════════════════════════════════════════════════
def _patch_st(monkeypatch, *, on_df=None, on_caption=None):
    """同時攔兩個 streamlit 進入點,因為它們解析時機不同:

    - `st.dataframe` 由 `ui/components/tables.styled_dataframe` **呼叫時**
      `import streamlit` 取得 → patch `sys.modules['streamlit']`;
    - `st.caption` 走 `beginner_view` 的**模組層**綁定 → patch `mbv.st`。

    這兩者在「先跑過 stub-installer test 檔」的情境下可能是不同物件
    (conftest 會 per-test 換 `sys.modules['streamlit']`,但模組層綁定不會跟著換)。
    兩邊都 patch,測試就不吃執行順序的運氣(`PROCESS.md §4` 測試自身可執行性)。
    """
    import streamlit as _st_sys

    import ui.helpers.macro.beginner_view as _mbv
    for _mod in {id(_st_sys): _st_sys, id(_mbv.st): _mbv.st}.values():
        monkeypatch.setattr(_mod, "dataframe", on_df or (lambda df, **kw: None),
                            raising=False)
        monkeypatch.setattr(_mod, "caption", on_caption or (lambda *a, **k: None),
                            raising=False)


class TestEvidenceTableRender:
    def test_dataframe_receives_every_row_and_column(self, monkeypatch):
        """接住 `st.dataframe` 實際拿到的 DataFrame ——
        **修正前必紅**(renderer 不存在);且若日後有人在 renderer 裡
        drop 欄位 / 只畫前 N 列,這裡會紅(§1 不掉行)。"""
        from ui.helpers.macro.beginner_view import EVIDENCE_COLUMNS, render_evidence_table
        _cap: dict = {}
        _patch_st(monkeypatch, on_df=lambda df, **kw: _cap.update(df=df, kw=kw))
        _r = _rows(news_items=[])
        render_evidence_table(_r)
        assert _cap, "st.dataframe 根本沒被呼叫 —— 表格沒渲染出去"
        _df = _cap["df"]
        assert list(_df.columns) == list(EVIDENCE_COLUMNS)
        assert len(_df) == len(_r) == 6
        assert _cap["kw"].get("hide_index") is True
        assert _cap["kw"].get("use_container_width") is True

    def test_scale_note_is_stated_once_below_the_table(self, monkeypatch):
        """user 要求:「不要留兩份說法」。對照文字只在表下出現一次,
        且必須同時點名兩把尺(只講一把 = 又變成單邊說法)。"""
        from ui.helpers.macro.beginner_view import render_evidence_table
        _caps: list = []
        _patch_st(monkeypatch, on_caption=lambda *a, **k: _caps.append(str(a[0])))
        render_evidence_table(_rows())
        assert len(_caps) == 1, f"表下註記應只有一行,實際 {len(_caps)}"
        assert "位階" in _caps[0] and "強度" in _caps[0]

    def test_empty_rows_render_an_empty_table_not_a_crash(self, monkeypatch):
        """邊界:沒有任何列(理論上不會發生,但 caller 端 except 降級路徑會餵)
        → 空表 + 欄位仍在,不 raise、不畫出假資料。"""
        from ui.helpers.macro.beginner_view import EVIDENCE_COLUMNS, render_evidence_table
        _cap: dict = {}
        _patch_st(monkeypatch, on_df=lambda df, **kw: _cap.update(df=df))
        render_evidence_table([])
        assert len(_cap["df"]) == 0
        assert list(_cap["df"].columns) == list(EVIDENCE_COLUMNS)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
