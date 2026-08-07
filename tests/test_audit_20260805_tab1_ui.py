"""2026-08-05 稽核 — Tab① 總經 UI 六項必修的守衛 + **接線驗證**(`PROCESS.md §4`)。

覆蓋:
  必修 1  PMI 代理值必須帶標記進 AI prompt(§1 反造假)
  必修 2  三處指路文案改吃 `story_nav.tab_label()`(分頁名 SSOT)
  必修 3  兩套評分尺度消歧義 + 位階字卡收 `format_phase_score` SSOT
  必修 4  詳細區版面順序 + 決策矩陣預設展開
          (2026-08-07 user 拍板「四時域優先」:長期 → 中期 → 短線 → 拐點 →
           決策矩陣;原本的「決策矩陣在四時域之前」已被此拍板取代,
           但「不得跑到總表前面」那條上界一字未動)
  必修 5  status / stat_tile / tables 三元件的 0-consumer 裁決
  必修 6  SPEC §1-B 與單軌實作對齊

⚠️ 設計準則(`PROCESS.md §4`):本 repo 已四次出現「算對了但沒接出去」。
   因此凡是「服務層/元件早就備妥、只差 caller」的項目,本檔一律**檢查呼叫端**
   (AST 找 Call 節點 / 比對 caller 實際輸出),而不是只檢查函式本身能不能跑 ——
   後者在 caller 沒改時照樣綠,等於沒測。
   每條 test 的 docstring 標明「修正前紅在哪」。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_TAB1 = _ROOT / "ui" / "tab1_macro.py"
_TAB1_INFL = _ROOT / "ui" / "tab1_macro_inflection.py"
_TAB3 = _ROOT / "ui" / "tab3_portfolio.py"
_TAB6 = _ROOT / "ui" / "tab6_manual.py"
_BEGINNER = _ROOT / "ui" / "helpers" / "macro" / "beginner_view.py"
_SPEC = _ROOT / "SPEC.md"


# ══════════════════════════════════════════════════════════════
# 共用 AST 工具
# ══════════════════════════════════════════════════════════════
def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _fn_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    return str(getattr(call.func, "attr", ""))


def _is_alias_of(call: ast.Call, fname: str) -> bool:
    """本 repo 慣用 `from x import f as _f` / `as _f_v19xxx` 的 lazy import 別名,
    因此以「去底線前綴後 startswith」判定,避免別名一改測試就瞎。"""
    return _fn_name(call).lstrip("_").startswith(fname)


def _call_first_str_args(path: Path, fname: str) -> set[str]:
    """回傳該檔內所有 `fname(...)`(含別名)呼叫的第一個字串引數。"""
    out: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Call) and _is_alias_of(node, fname):
            if node.args and isinstance(node.args[0], ast.Constant) \
                    and isinstance(node.args[0].value, str):
                out.add(node.args[0].value)
    return out


def _is_called(path: Path, fname: str) -> bool:
    return any(isinstance(n, ast.Call) and _is_alias_of(n, fname)
               for n in ast.walk(_tree(path)))


def _string_constants(path: Path) -> list[str]:
    """只取**字串字面值**(不含 `#` 註解)—— 讓「註解裡引述舊文案」不會誤判為未修。"""
    return [n.value for n in ast.walk(_tree(path))
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


# ── 版面位置專用:一律走 AST + lineno,不用 `src.index()` ──────────────
# 理由與本檔既有慣例相同:`index()` 會被註解裡引述的區塊名 / 函式名提前命中,
# 使「順序」斷言變成恆真的假通過(本 repo 已踩過同型陷阱兩次)。
def _render_line(fname: str) -> int:
    """`ui/tab1_macro.py` 內某個 renderer 的**唯一**渲染點行號。

    兩種形式都算:裸呼叫 `fname(...)`,以及 v19.429 §1 區塊隔離後的
    `_safe_section("標籤", fname, ...)` —— 後者 renderer 是 `ast.Name` 引數
    而不是 `ast.Call`,只掃 Call 會整個漏掉。刻意**只認 `_safe_section` 的引數
    位置**,不掃全檔 `ast.Name`:後者會命中 import alias,「恰好一處」就失去
    鑑別力(同 `test_audit_20260805_tab1_exceptions.py` 的做法)。
    """
    _t = _tree(_TAB1)
    _lines = [n.lineno for n in ast.walk(_t)
              if isinstance(n, ast.Call) and _fn_name(n) == fname]
    _lines += [a.lineno for n in ast.walk(_t)
               if isinstance(n, ast.Call) and _fn_name(n) == "_safe_section"
               for a in n.args if isinstance(a, ast.Name) and a.id == fname]
    assert len(_lines) == 1, f"{fname} 的渲染點應恰好一處,實際 {len(_lines)} 處"
    return _lines[0]


def _md_heading_line(text: str) -> int:
    """`st.markdown("<text>")` 這個呼叫節點的行號(恰好一處)。"""
    _hits = [n.lineno for n in ast.walk(_tree(_TAB1))
             if isinstance(n, ast.Call) and _fn_name(n) == "markdown"
             and n.args and isinstance(n.args[0], ast.Constant)
             and n.args[0].value == text]
    assert len(_hits) == 1, f"{text!r} 這個標題應恰好一處,實際 {len(_hits)} 處"
    return _hits[0]


def _block_openers_between(lo: int, hi: int) -> list[str]:
    """落在 (lo, hi) 之間的「一級區塊開頭」——
    `st.markdown("## …")` 標題與 `st.expander(…)` 面板兩種都算(後者是本檔
    中國副盤那類沒有 `##` 標題、卻確實佔一整段版面的區塊)。"""
    _out: list[str] = []
    for _n in ast.walk(_tree(_TAB1)):
        if not (isinstance(_n, ast.Call) and lo < _n.lineno < hi
                and _n.args and isinstance(_n.args[0], ast.Constant)
                and isinstance(_n.args[0].value, str)):
            continue
        if _fn_name(_n) == "expander":
            _out.append(_n.args[0].value)
        elif _fn_name(_n) == "markdown" and _n.args[0].value.startswith("## "):
            _out.append(_n.args[0].value)
    return _out


# 四時域四段的 renderer(順序即 `shared.macro_buckets.BUCKET_ORDER` 去掉新聞桶)
_HORIZON_RENDERERS = ("render_long_term_section", "render_mid_cycle_section",
                      "render_short_radar_section", "render_inflection_alert_section")


# ══════════════════════════════════════════════════════════════
# 必修 1 — PMI 代理值進 AI prompt 必須帶標記
# ══════════════════════════════════════════════════════════════
class _FakeSessionState(dict):
    def __getattr__(self, k):
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v


@pytest.fixture()
def _mock_ss(monkeypatch):
    import streamlit as st
    monkeypatch.setattr(st, "session_state", _FakeSessionState({}))


_PROXY_PMI = {
    # 形狀對齊 services/macro/us_indicators.py:483-495 的 R["PMI"]
    "name": "ISM 製造業 PMI（Phil Fed 替代）",
    "value": 63.8,
    "unit": "",
    "signal": "🟢",
    "source": "FRED:GACDFSA066MSFRBPHI:proxy",
    "is_proxy": True,
    "proxy_note": "Phil Fed 擴散指數轉換為 PMI 刻度",
}


class TestProxyReachesAiPrompt:
    """§1:代理值不可以官方本尊之名進 Gemini prompt。"""

    def test_proxy_name_note_and_source_all_in_prompt(self, _mock_ss):
        """**修正前必紅** —— 原本 prompt 寫的是 dict key「PMI」,
        `name` / `is_proxy` / `proxy_note` / `source` 四個欄位 0 consumer。"""
        from ui.tab1_macro_ai import _build_macro_ai_snapshot
        snap, _, _ = _build_macro_ai_snapshot({"PMI": dict(_PROXY_PMI)}, {}, {}, {}, [])
        assert "ISM 製造業 PMI（Phil Fed 替代）" in snap, "prompt 未帶服務層 name"
        assert "PROXY" in snap, "prompt 未標示這是代理值"
        assert "Phil Fed 擴散指數轉換為 PMI 刻度" in snap, "proxy_note 仍 0 consumer"
        assert "FRED:GACDFSA066MSFRBPHI:proxy" in snap, "來源未進 prompt"

    def test_proxy_marker_before_the_value(self, _mock_ss):
        """代理標記必須與數值同一行/在其前,否則 AI 可能只讀到 63.8。"""
        from ui.tab1_macro_ai import _build_macro_ai_snapshot
        snap, _, _ = _build_macro_ai_snapshot({"PMI": dict(_PROXY_PMI)}, {}, {}, {}, [])
        _line = next(ln for ln in snap.splitlines() if "63.8" in ln)
        assert "PROXY" in _line, f"數值行沒有代理標記:{_line!r}"

    def test_non_proxy_indicator_not_mislabeled(self, _mock_ss):
        """§1 反向:非代理指標不得被誤加 [PROXY](假警報同樣是失真)。"""
        from ui.tab1_macro_ai import _build_macro_ai_snapshot
        ind = {"VIX": {"name": "VIX 恐慌指數", "value": 18.0, "unit": "",
                       "signal": "🟢", "is_proxy": False, "source": "Yahoo:^VIX"}}
        snap, _, _ = _build_macro_ai_snapshot(ind, {}, {}, {}, [])
        assert "VIX 恐慌指數" in snap
        assert "PROXY" not in snap

    def test_missing_name_falls_back_to_key(self, _mock_ss):
        """邊界:服務層沒給 name → 退回 dict key,不得變成空白/None。"""
        from ui.tab1_macro_ai import _build_macro_ai_snapshot
        snap, _, _ = _build_macro_ai_snapshot({"CFNAI": {"value": -0.2}}, {}, {}, {}, [])
        assert "CFNAI：-0.2" in snap

    def test_proxy_flag_wins_over_name_wording(self, _mock_ss):
        """旗標優先於文案:name 沒寫「替代」二字,只要 is_proxy=True 就得標記。"""
        from ui.tab1_macro_ai import _build_macro_ai_snapshot
        ind = {"PMI": {"name": "ISM 製造業 PMI", "value": 63.8, "is_proxy": True,
                       "proxy_note": "", "source": ""}}
        snap, _, _ = _build_macro_ai_snapshot(ind, {}, {}, {}, [])
        assert "PROXY" in snap


def test_tab6_indicator_name_not_truncated_through_proxy_label():
    """**修正前必紅**(18 < 20) —— tab6 的 `[:18]` 會把
    「ISM 製造業 PMI（Phil Fed 替代）」切成「…（Phil Fed 替」,
    剛好砍掉「替代」的下半,代理值在 23 項明細表看起來像官方本尊。"""
    import re
    src = _TAB6.read_text(encoding="utf-8")
    m = re.search(r'_iv\.get\("name", _ik\)[^\[]*\[:(\d+)\]', src)
    assert m, "tab6_manual.py 找不到指標 name 截斷點(結構已變,請更新本測試)"
    assert int(m.group(1)) >= len(_PROXY_PMI["name"]), (
        f"截斷長度 {m.group(1)} < 代理值全名 {len(_PROXY_PMI['name'])} 字 → 標籤會被切掉")


# ══════════════════════════════════════════════════════════════
# 必修 2 — 三處指路文案接 story_nav.tab_label()
# ══════════════════════════════════════════════════════════════
# (檔案 → 該檔應呼叫的 tab_label key, 該檔不得再出現的死分頁名字面值)
_HINT_SITES = (
    (_TAB1,      "portfolio", "📦 投資組合"),
    (_TAB1_INFL, "portfolio", "📊 組合基金"),
    (_TAB3,      "fund",      "單檔基金"),
)


@pytest.mark.parametrize("path,key,dead", _HINT_SITES,
                         ids=[p.name for p, _, _ in _HINT_SITES])
def test_hint_text_wired_to_tab_label(path: Path, key: str, dead: str):
    """**修正前必紅** —— `tab_label()` 早就存在,但這三處仍是寫死字串。

    兩段都要過才算接線:
      (a) 該檔真的有 `tab_label('<key>')` **呼叫**(不是只 import);
      (b) 死分頁名不再出現在任何**字串字面值**裡(註解引述舊文案不算)。
    """
    assert key in _call_first_str_args(path, "tab_label"), (
        f"{path.name} 沒有 tab_label('{key}') 呼叫 —— 指路文案未接 SSOT")
    for s in _string_constants(path):
        assert dead not in s, f"{path.name} 仍有寫死的死分頁名字面值:{s!r}"


def test_tab3_hint_drops_stale_tab_ordinal():
    """Tab2 序號必須拿掉 —— 個基深掘早已不是第 2 個分頁(app.py 現為 5 分頁)。"""
    for s in _string_constants(_TAB3):
        assert "Tab2" not in s, f"tab3_portfolio.py 仍寫死分頁序號:{s!r}"


def test_hint_keys_exist_in_story_nav():
    """指路用的 key 必須是 `_STEPS` 合法站別(§1:未知 key 會 KeyError 當場炸)。"""
    from ui.helpers.story_nav import tab_label
    for _p, _key, _dead in _HINT_SITES:
        assert tab_label(_key)


# ══════════════════════════════════════════════════════════════
# 必修 3 — 兩套評分尺度消歧義
# ══════════════════════════════════════════════════════════════
class TestPhaseScoreSsot:
    def test_long_bucket_headline_equals_format_phase_score(self):
        """**修正前必紅** —— 原本自組 `擴張 (6.8/10)`(多一層括號),
        沒吃 v19.403 DUP-3 建的 SSOT `format_phase_score`(輸出 `擴張 6.8/10`)。"""
        from ui.helpers.macro.beginner_view import compute_four_horizon_summary
        from ui.helpers.macro.helpers import format_phase_score
        _pi = {"phase": "擴張", "score": 6.8}
        r = compute_four_horizon_summary({}, phase_info=_pi)
        assert r["long"]["headline"] == format_phase_score(_pi)

    def test_phase_score_never_signed(self):
        """位階恆 0-10,格式不得帶正負號(帶了就會與 hero 的有號淨分撞臉)。"""
        from ui.helpers.macro.beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary({}, phase_info={"phase": "擴張", "score": 6.8})
        assert "+" not in r["long"]["headline"]

    def test_score_zero_is_not_falsy_replaced_by_neutral_five(self):
        """**修正前必紅** —— `phase_info.get("score") or 5.0` 對 score=0.0
        (極端衰退,calc_macro_phase clamp 下界)會 falsy 回退成中性 5.0,
        桶色被誤判成 yellow「轉折中」(`PROCESS.md §4` M2 去重同型)。"""
        from ui.helpers.macro.beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary({}, phase_info={"phase": "衰退", "score": 0.0})
        assert r["long"]["level"] == "red", "score=0.0 應為紅燈,不該被回退成 5.0"
        assert "0.0/10" in r["long"]["headline"]

    def test_missing_phase_still_renders_something(self):
        """邊界:phase 缺失 → SSOT 回 "",須有 fallback 不留空桶。"""
        from ui.helpers.macro.beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary({}, phase_info={})
        assert r["long"]["headline"].strip()


def test_hero_card_discloses_both_scales():
    """**修正前必紅** —— hero 副標只寫加權淨分,
    與 20 幾行外的五桶「🌳 長期 擴張 (6.8/10)」兩套尺度並列卻無對照說明。

    ⚠️ 2026-08-05 第二輪:原本這裡還斷言副標寫死的指標筆數字面值。
       該筆數已改吃 `provenance_out["n_indicators"]`。

    ⚠️ 2026-08-05 F1 重構:hero 卡 + 五桶 bar + 中間那行對照 caption 三者
       合併成總表「② 依據」表格,文案隨之搬到
       `ui/helpers/macro/beginner_view.py::build_evidence_rows`。
       原本的字串掃描(掃 `_TAB1` 的 literal)在搬家後只會抓到搬走的空殼,
       改成**功能斷言**:直接跑 builder,驗兩把尺確實各自出現在同一張表、
       且各自標明怎麼讀。這比字串掃描強 —— 有人把說明欄刪掉時字串掃描
       可能因為別處還有同一個詞而不紅,功能斷言一定紅。
    """
    from ui.helpers.macro.beginner_view import (
        build_evidence_rows,
        compute_five_bucket_summary,
    )
    from ui.helpers.macro.helpers import format_phase_score
    _pi = {"phase": "擴張", "score": 6.8}
    _rows = build_evidence_rows(
        compute_five_bucket_summary({}, phase_info=_pi, news_items=None),
        composite_score=15.5, composite_icon="🟢", composite_level="極度樂觀",
        composite_action="多頭市場強勁", n_indicators=25)
    _blob = " ".join(str(_v) for _r in _rows for _v in _r.values())
    assert "強度" in _blob, "② 依據表未標示『強度』"
    assert "位階" in _blob, "② 依據表未對照『位階』"
    assert "指標加權淨分" in _blob, "② 依據表掉了『指標加權淨分』說明"
    # 位階那格必須是 SSOT 輸出,不得有人另外自組格式
    _long = [_r for _r in _rows if _r["面向"].endswith("長期")]
    assert _long and format_phase_score(_pi) in " ".join(_long[0].values())
    # 接線:tab1 真的建了列並渲染(只在 helper 裡寫好不算)
    assert _is_called(_TAB1, "build_evidence_rows")
    assert _is_called(_TAB1, "render_evidence_table")


def test_two_scales_not_merged():
    """§8:**不得**把兩個尺度合併成一個數字 —— 6+ consumer 吃 phase.score。

    2026-08-05 F1 把兩者放進同一張表,那是**併陳**不是併算:
    強度仍走 `calculate_composite_score`,位階仍走 phase score,兩條路徑各自獨立。
    """
    assert _is_called(_TAB1, "calculate_composite_score")
    from ui.helpers.macro.beginner_view import compute_four_horizon_summary
    r = compute_four_horizon_summary({}, phase_info={"phase": "擴張", "score": 7.0})
    assert r["long"]["level"] == "green"


# ══════════════════════════════════════════════════════════════
# 必修 4 — 詳細區版面順序(四時域優先)+ 決策矩陣預設展開
# ══════════════════════════════════════════════════════════════
def test_detail_zone_opens_with_the_first_horizon_section():
    """**修正前必紅**(舊行為與斷言衝突,非 ImportError)。

    ② 依據表每一列都寫「詳細在下方哪一段」,表下還附一份四段的目錄;但改排前
    往下捲第一個撞到的是兩個目錄**沒提**的區塊(唯讀副盤 + 決策矩陣),
    指路與版面對不上。2026-08-07 user 拍板「四時域優先」後,詳細區分界之後
    的第一個一級區塊必須就是第一個時域。
    """
    _detail = _md_heading_line("## 🔎 詳細資料與說明")
    _lines = [_render_line(_f) for _f in _HORIZON_RENDERERS]
    assert _detail < min(_lines), "四時域跑到詳細區分界前面了"
    _between = _block_openers_between(_detail, min(_lines))
    assert not _between, f"第一個時域之前還夾著一級區塊:{_between}"


def test_the_four_horizon_sections_stay_in_order_and_contiguous():
    """② 表下那份目錄現在直接宣稱「往下捲會依序看到這四段」——
    本條就是那句話的**接線鎖**(`PROCESS.md §4`:文案宣稱的事要有東西守著)。

    **修正前會不會紅**:不會(改排前四段本來就已相鄰)。本條是**新增的回歸鎖**:
    改排讓「連續」從巧合變成目錄明講的承諾,日後任何人往中間插一個區塊,
    目錄就會變成假話 —— 這裡先紅,而不是等使用者捲下去才發現。
    """
    _lines = [_render_line(_f) for _f in _HORIZON_RENDERERS]
    assert _lines == sorted(_lines), (
        f"四時域順序跑掉了(應為 長期 → 中期 → 短線 → 拐點):{_lines}")
    _between = _block_openers_between(_lines[0], _lines[-1])
    assert not _between, f"四時域四段中間夾了別的一級區塊:{_between}"


def test_decision_matrix_sits_after_the_horizons_and_before_the_ai_summary():
    """**修正前必紅**(舊行為與斷言衝突,非 ImportError)——
    改排前本區塊在四時域**之前**,舊斷言守的正是相反方向。

    2026-08-07 user 拍板「四時域優先」:長期 → 中期 → 短線 → 拐點 → 決策矩陣。
    本條同時守**三個**方向,少任何一條位置契約就會鬆掉:
      (a) 不得跑到總表 ② 依據表前面(會擋住總經,違反 v19.41 那條指示)——
          與舊版一字不改,那條指示沒有被本次拍板推翻;
      (b) 必須在最後一個時域之後(舊版守的是反向,隨拍板翻轉);
      (c) 必須在 🤖 AI 總結**之前**。這是新加的下界 —— 舊版的「不得埋回底部」
          原意本來由 (b) 的反向不等式承擔,翻轉後若不補 (c),整條下界就消失,
          有人把它挪到全頁最後一區也不會紅。

    ⚠️ 錨點全部走 AST + lineno(見 `_render_line`),不用 `src.index()`:
       本檔守的三個區塊名在 `ui/tab1_macro.py` 的沿革註解裡都被引述過,
       字串比對會提前命中註解而變成假通過。
    """
    _bar = _render_line("render_evidence_table")
    _matrix = _render_line("_render_realtime_decision_dashboard")
    _last_horizon = _render_line(_HORIZON_RENDERERS[-1])
    _ai = _render_line("render_ai_summary_section")
    assert _bar < _matrix, "決策矩陣跑到總表 ② 依據表前面了(會擋住總經,違反 v19.41 指示)"
    assert _last_horizon < _matrix, "決策矩陣還在四時域之前(user 拍板四時域優先)"
    assert _matrix < _ai, "決策矩陣被挪到 AI 總結之後 —— 逐檔行動不得埋在全頁最末"


def test_decision_matrix_expander_defaults_open():
    """**修正前必紅**(原 expanded=False)—— 算好的結論預設收合等於沒揭露。"""
    _found: list = []
    for node in ast.walk(_tree(_TAB1)):
        if not isinstance(node, ast.With):
            continue
        _body = ast.dump(ast.Module(body=list(node.body), type_ignores=[]))
        if "_render_realtime_decision_dashboard" not in _body:
            continue
        for item in node.items:
            _ctx = item.context_expr
            if isinstance(_ctx, ast.Call) and _fn_name(_ctx) == "expander":
                _found += [kw.value.value for kw in _ctx.keywords
                           if kw.arg == "expanded" and isinstance(kw.value, ast.Constant)]
    assert _found == [True], f"決策矩陣 expander 的 expanded 應為 True,實際 {_found}"


def test_decision_matrix_heading_still_present_once():
    """搬家不得把區塊搬丟或搬成兩份。"""
    src = _TAB1.read_text(encoding="utf-8")
    assert src.count('st.markdown("## 📋 即時訊號 + 決策矩陣")') == 1
    # v19.429:呼叫改由 _safe_section 包裹,匹配包裹後的呼叫形(仍須恰好一處)。
    assert src.count("_render_realtime_decision_dashboard, ind)") == 1


def test_decision_matrix_caption_not_claiming_last_position():
    """文案同步:原 caption 寫「跨時域殿後」,搬到前面後就變成假話。

    2026-08-07「四時域優先」重排後本條**仍然成立且仍有鑑別力**:本區塊後面還接
    唯讀副盤與 AI 總結兩段,它不是最後一段,那句宣稱照樣是假話。
    """
    for s in _string_constants(_TAB1):
        assert "殿後" not in s, f"決策矩陣已上移,caption 仍寫『殿後』:{s!r}"


def _first_caption_after(lineno: int) -> str:
    """`lineno` 之後第一個 `st.caption("…")` 的字面文案(AST,不吃註解)。

    相鄰字串字面值由 parser 併成同一個 `ast.Constant`,所以跨行寫的 caption
    也拿得到完整一句。
    """
    _caps = sorted((n.lineno, n.args[0].value) for n in ast.walk(_tree(_TAB1))
                   if isinstance(n, ast.Call) and _fn_name(n) == "caption"
                   and n.args and isinstance(n.args[0], ast.Constant)
                   and isinstance(n.args[0].value, str) and n.lineno > lineno)
    assert _caps, f"line {lineno} 之後找不到任何 caption"
    return _caps[0][1]


def test_decision_matrix_caption_points_the_right_way():
    """**修正前必紅**(舊行為與斷言衝突,非 ImportError)——
    原 caption 寫「推導細節見**下方**四時域」。本區塊搬到四時域之後,那四段
    改在它**上面**,同一句話就把讀者往錯的方向指(§1 的同族:錯的指引比沒有更糟)。

    只驗**方位詞與指涉對象**,不釘整句文案 —— user 改字不該誤紅,
    指錯方向或整個不再指回推導依據才該紅。
    """
    _cap = _first_caption_after(_md_heading_line("## 📋 即時訊號 + 決策矩陣"))
    assert "四時域" in _cap, f"決策矩陣 caption 沒有指回推導依據:{_cap!r}"
    assert "上方" in _cap and "下方" not in _cap, (
        f"決策矩陣現在排在四時域之後,caption 卻仍往下指:{_cap!r}")


# ══════════════════════════════════════════════════════════════
# 必修 5 — 三個 v19.388 元件的 0-consumer 裁決
# ══════════════════════════════════════════════════════════════
class TestComponentAdjudication:
    """`PROCESS.md §4` 稽核落地條款:0 consumer → 接線 or 刪除,不得留著假裝有揭露。"""

    def test_stat_tile_has_real_production_caller(self):
        """**修正前必紅** —— stat_tile 自 v19.388 起 production 0 caller。"""
        assert _is_called(_TAB1, "stat_tile"), "stat_tile 仍無 production caller"
        assert "from ui.components.stat_tile import stat_tile" in \
            _TAB1.read_text(encoding="utf-8")

    def test_styled_dataframe_has_real_production_caller(self):
        """**修正前必紅** —— tables.styled_dataframe 自 v19.388 起 production 0 caller。"""
        assert _is_called(_TAB1, "styled_dataframe")

    def test_styled_dataframe_defaults_match_replaced_call(self, monkeypatch):
        """接線不得改變行為:仍須 hide_index=True + use_container_width=True
        (原呼叫就是這兩個參數,替換後若預設飄掉 = 悄悄改了畫面)。"""
        import streamlit as _st
        from ui.components.tables import styled_dataframe
        _captured: dict = {}
        monkeypatch.setattr(_st, "dataframe",
                            lambda df, **kw: _captured.update(kw))
        _sentinel = object()
        styled_dataframe(_sentinel)
        assert _captured.get("hide_index") is True
        assert _captured.get("use_container_width") is True

    def test_status_chip_has_real_production_caller(self):
        """**修正前必紅** —— hero 下方那段程式的註解自己叫「對帳 chip」,
        卻是手刻 emoji 的 st.caption;`status_chip()` 自 v19.388 起 0 caller。"""
        assert _is_called(_TAB1, "status_chip")

    def test_reconcile_chip_keeps_all_original_facts(self):
        """接線不得掉資訊:對帳 chip 仍須帶 note / 多空票數 / net 比值。"""
        _consts = " ".join(_string_constants(_TAB1))
        assert "對帳" in _consts
        assert "vote_net_ratio" in _TAB1.read_text(encoding="utf-8")
        for _k in ("n_pos", "n_neg", "note"):
            assert _k in _TAB1.read_text(encoding="utf-8"), f"對帳 chip 掉了 {_k}"

    def test_status_table_is_the_single_light_emoji_source(self):
        """**修正前必紅** —— beginner_view 原本在 3 個函式裡各寫一份
        {"green":"🟢","yellow":"🟡","red":"🔴"},是 status.py `_TABLE` 之外的複本。"""
        from ui.components.status import status_color
        from ui.helpers.macro.beginner_view import _LEVEL_EMOJI
        for _lv in ("green", "yellow", "red", "gray"):
            assert _LEVEL_EMOJI[_lv] == status_color(_lv).emoji
        # ⚠️ 原本這裡是 `_src.count('"green": "🟢"') == 0`,那條**修正前後都綠**、
        #    零鑑別力(違 PROCESS.md §4「拿掉呼叫端那一行測試仍綠 → 測試無效」):
        #    (a) 上面的值比對兩邊本來就相同;(b) 舊碼寫法是 `{"green":"🟢"}`(冒號後
        #    無空格),字面比對抓不到。改成 AST 結構掃描,任何**形狀**的燈號 emoji
        #    對照表 literal 都會被抓到,不受空白/引號風格影響。
        import ast
        _tree = ast.parse(_BEGINNER.read_text(encoding="utf-8"))
        _dup = [
            n for n in ast.walk(_tree)
            if isinstance(n, ast.Dict)
            and any(isinstance(k, ast.Constant) and k.value in ("green", "yellow", "red")
                    for k in n.keys)
            and any(isinstance(v, ast.Constant) and v.value in ("🟢", "🟡", "🔴")
                    for v in n.values)
        ]
        assert not _dup, (
            f"beginner_view 仍有 {len(_dup)} 份硬寫的燈號 emoji 對照表 dict literal —— "
            "唯一來源必須是 ui/components/status.py::_TABLE")

    def test_five_bucket_gray_still_renders_unknown_square(self):
        """回歸:收 SSOT 後第 5 桶「未掃描」仍是 ⬜(§1 誠實,不能變綠)。"""
        from ui.helpers.macro.beginner_view import compute_five_bucket_summary
        r = compute_five_bucket_summary({}, phase_info={}, news_items=None)
        assert r["news"]["level"] == "gray"
        assert r["news"]["emoji"] == "⬜"

    def test_num_col_deleted_not_left_as_dead_abstraction(self):
        """**修正前必紅** —— `num_col()` 自 v19.388 起 0 caller,
        依 §4「若確實不需要 → 刪除,而不是留著假裝有揭露」處置。"""
        import ui.components.tables as _tables
        assert not hasattr(_tables, "num_col"), "num_col 仍在(0 consumer 的用不到抽象)"

    def test_no_stale_reference_to_deleted_num_col(self):
        """刪除必須連引用一起清 —— 對照 `PROCESS.md §4` 第 4 個案例
        (ruff 白名單沒同步清 → 指向不存在程式碼的永久豁免)。

        用 AST 找「真的 import / 呼叫」,不掃字面文字 —— 否則 tables.py
        docstring 裡的裁決紀錄會被誤判成殘留引用。
        """
        for _p in (list((_ROOT / "ui").rglob("*.py"))
                   + list((_ROOT / "services").rglob("*.py"))):
            try:
                _t = ast.parse(_p.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for _n in ast.walk(_t):
                if isinstance(_n, ast.Call) and _fn_name(_n) == "num_col":
                    pytest.fail(f"{_p} 仍呼叫已刪除的 num_col")
                if isinstance(_n, ast.ImportFrom) and any(
                        a.name == "num_col" for a in _n.names):
                    pytest.fail(f"{_p} 仍 import 已刪除的 num_col")


# ══════════════════════════════════════════════════════════════
# 必修 6 — SPEC §1-B 對齊單軌實作
# ══════════════════════════════════════════════════════════════
def _spec_section_1b() -> str:
    _txt = _SPEC.read_text(encoding="utf-8")
    _i = _txt.index("## §1-B")
    _j = _txt.index("## §2 ", _i)
    return _txt[_i:_j]


class TestSpec1BMatchesReality:
    def test_no_longer_specifies_beginner_expert_mode_switch(self):
        """**修正前必紅** —— SPEC 仍規範「新手/老手雙軌 + 模式切換」,
        但 v17.0 / v19.128 已兩次移除,矛盾的一方是 SPEC。"""
        _sec = _spec_section_1b()
        assert "新手/老手兼顧" not in _sec, "§1-B 標題仍寫雙軌"
        assert "AI 輸出雙軌格式" not in _sec, "§1-B 仍要求雙軌 AI 輸出"
        assert "（新手模式）" not in _sec and "（老手模式）" not in _sec

    def test_records_both_removal_decisions_with_dates(self):
        """§2.2 可追溯:兩次移除的版本 + user 決策日期都要在 SPEC 留痕。"""
        _sec = _spec_section_1b()
        for _mark in ("v17.0", "v19.128", "2026-06-25"):
            assert _mark in _sec, f"§1-B 未記錄 {_mark}"

    def test_does_not_resurrect_rejected_feature(self):
        """§-1:SPEC 更正是「反映實況」,不是把 user 否決的功能寫回需求。"""
        _sec = _spec_section_1b()
        assert "單軌" in _sec

    def test_documents_two_score_scales(self):
        """必修 3 的消歧義規範要落進 SPEC,否則下一版又會有人合併兩個分數。"""
        _sec = _spec_section_1b()
        assert "format_phase_score" in _sec
        assert "強度" in _sec and "位階" in _sec


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
