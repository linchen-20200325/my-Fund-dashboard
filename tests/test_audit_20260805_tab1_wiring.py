"""2026-08-05 稽核第二輪 — Tab① 總經「已寫好但沒接線」資產的**接線驗證**。

本輪主題:10 項教學／SSOT 資產裡有 9 項 production 0 consumer。修的不是演算法,
是「算對了但沒接出去」(`PROCESS.md §4` 明列的本 repo 最高重工成本失效模式)。

覆蓋:
  必修 1  `services.macro.action_light.macro_action_light` 回歸接回 Tab① 頂部
  必修 2  Z-Score 卡 sparkline 接 `shared.macro_buckets` 危險門檻 registry
  必修 3  五桶 / 四時域 bar 的桶標籤收 `BUCKET_ORDER` + `BUCKET_META`
  必修 4  hero 卡指標筆數改吃 `provenance_out["n_indicators"]`
  必修 5  第三套指標分類法(category_* 一組)刪除且無殘留引用

⚠️ 設計準則(`PROCESS.md §4`):每條測試都必須能在「產生端完全正確、但呼叫端
   那一行被拿掉」時**變紅**。只驗「函式自己能跑」的測試在本檔一律不算數。
   每條 docstring 標明修正前紅在哪。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_TAB1 = _ROOT / "ui" / "tab1_macro.py"
_BEGINNER = _ROOT / "ui" / "helpers" / "macro" / "beginner_view.py"

# ⚠️ 刻意**不寫** `pytest.importorskip("plotly")`(`PROCESS.md §4` 測試自身可執行性):
#    plotly 是本 repo 的硬依賴(`ui/tab1_macro.py` module 頂部就 import),
#    缺件時本檔應該**紅**而不是 skip —— skip 會製造「有測試守著」的假象。


# ══════════════════════════════════════════════════════════════
# 共用 AST 工具(與 test_audit_20260805_tab1_ui.py 同慣例)
# ══════════════════════════════════════════════════════════════
def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _fn_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    return str(getattr(call.func, "attr", ""))


def _calls(path: Path, fname: str) -> list:
    return [n for n in ast.walk(_tree(path))
            if isinstance(n, ast.Call) and _fn_name(n) == fname]


def _exact_string_constants(path: Path) -> set:
    """該檔所有**字串字面值**(exact set)。

    用 exact 比對而非子字串:docstring / 註解式說明常引述舊文案,
    子字串比對會把「文件裡提到」誤判成「程式碼裡還寫死」。
    """
    return {n.value for n in ast.walk(_tree(path))
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def _shape_ys(fig) -> list:
    return [s.y0 for s in fig.layout.shapes]


# ══════════════════════════════════════════════════════════════
# 必修 1 — 「現在能不能買」一句話結論回歸
# ══════════════════════════════════════════════════════════════
class TestActionLightWiredBackToTab1:
    """`macro_action_light` v19.316 就實作完成、8 條測試守著,但原掛載點
    `_render_beginner_dashboard` 於 v19.401 被當死面板整塊拔除,把燈一起帶走。
    今日 UI 端 0 caller(唯一 caller 是 `mcp_server/tools_macro.py`)。"""

    def test_tab1_actually_calls_macro_action_light(self):
        """**修正前必紅** —— 全 repo 只有 mcp_server 呼叫,`ui/tab1_macro.py` 0 caller。

        這是本檔最核心的一條:拿掉那行呼叫就紅,服務層自己能不能跑不算接線。
        """
        assert _calls(_TAB1, "macro_action_light"), (
            "ui/tab1_macro.py 沒有 macro_action_light(...) 呼叫 —— "
            "服務層算得出結論,畫面上仍看不到(PROCESS.md §4)")

    def test_called_with_real_phase_score_not_a_literal(self):
        """接線不得半套:第 2 引數必須是**真的位階分數運算式**。

        寫成 `macro_action_light(ind, None)` 這種常數 → 燈永遠只會回
        「🟡 資料不足」,等於掛了個假燈(§1 不下假結論)。
        """
        _cs = _calls(_TAB1, "macro_action_light")
        assert _cs, "先過 test_tab1_actually_calls_macro_action_light"
        _ok = [c for c in _cs
               if len(c.args) >= 2 and not isinstance(c.args[1], ast.Constant)]
        assert _ok, (
            "macro_action_light 的位階分數引數是常數字面值 —— "
            "必須傳入實際的 phase score,否則燈恆為『資料不足』")

    def test_light_sits_above_the_hero_card(self):
        """位置硬約束:結論燈必須在綜合健康度分數**之前**(第一眼先給結論)。

        且**不可**插進「② 依據表 → 決策矩陣」之間 ——
        那段順序由 test_audit_20260805_tab1_ui.py 鎖死,插進去會撞。

        ⚠️ 2026-08-05 F1 重構:hero 卡與五桶 bar 併成總表「② 依據」表格,
           錨點字串隨之改為 `render_evidence_table(...)`;
           `calculate_composite_score(` 仍是綜合健康度那一列的取數點,
           契約(結論在前、依據在後、決策矩陣不得插隊)一字未變。
        """
        src = _TAB1.read_text(encoding="utf-8")
        i_light = src.index("macro_action_light(")
        i_hero = src.index("calculate_composite_score(")
        i_bar = src.index("render_evidence_table(_ev_rows)")
        i_matrix = src.index("_render_realtime_decision_dashboard(ind)")
        assert i_light < i_hero, "結論燈跑到綜合健康度取數之後了"
        assert i_light < i_bar < i_matrix, (
            "結論燈不得插在 ② 依據表與決策矩陣之間(會撞既有順序鎖)")

    def test_renderer_maps_light_to_native_alert_widget(self):
        """燈色 → streamlit 原生元件,不手刻 HTML、不新造色票(§3.3)。"""
        import streamlit as st
        from ui.tab1_macro import _action_light_renderer
        assert _action_light_renderer("🟢") is st.success
        assert _action_light_renderer("🔴") is st.error
        assert _action_light_renderer("🟡") is st.warning

    def test_unknown_light_falls_back_to_warning_never_success(self):
        """§1 反向:服務層日後新增燈色時,未知值不得被當綠燈放行。"""
        import streamlit as st
        from ui.tab1_macro import _action_light_renderer
        for _bad in ("", "🟣", None, "green"):
            assert _action_light_renderer(_bad) is st.warning

    def test_every_real_service_light_has_a_renderer(self):
        """端到端:服務層三條分支(override 紅 / 位階三級 / 缺位階 🟡)
        實際吐出的燈色,都要能被 renderer 對應到 3 個原生元件之一。"""
        import streamlit as st
        from services.macro import macro_action_light
        from ui.tab1_macro import _action_light_renderer

        def _ind(**kw):
            return {k: {"value": v} for k, v in kw.items()}

        _cases = [
            macro_action_light(_ind(VIX=32.0), 9.0),                       # override 紅
            macro_action_light(_ind(VIX=15.0, YIELD_10Y2Y=0.8), 7.2),      # 位階綠
            macro_action_light(_ind(VIX=15.0, YIELD_10Y2Y=0.8), 5.0),      # 位階黃
            macro_action_light(_ind(VIX=15.0, YIELD_10Y2Y=0.8), 2.0),      # 位階紅
            macro_action_light(_ind(VIX=15.0, YIELD_10Y2Y=0.8), None),     # 缺位階
        ]
        _widgets = {st.success, st.warning, st.error}
        for _r in _cases:
            assert _action_light_renderer(_r["light"]) in _widgets, \
                f"服務層燈色 {_r['light']!r} 沒有對應的原生元件"

    def test_reasons_are_rendered_not_dropped(self):
        """接線不得掉資訊:燈只給結論、不給「為什麼」= 使用者無從判斷。

        用 AST 找 `<action_light 結果>.get("<欄位>")` 的實際讀取,
        不掃字面文字 —— 否則說明文字裡提到欄位名就會誤判成有讀。
        """
        _read: set = set()
        for _n in ast.walk(_tree(_TAB1)):
            if (isinstance(_n, ast.Call)
                    and isinstance(_n.func, ast.Attribute)
                    and _n.func.attr == "get"
                    and isinstance(_n.func.value, ast.Name)
                    and _n.func.value.id.startswith("_al")
                    and _n.args and isinstance(_n.args[0], ast.Constant)):
                _read.add(_n.args[0].value)
        assert {"reasons", "override"} <= _read, (
            f"結論燈掉了觸發理由 / 安全層標記,實際讀到的欄位:{sorted(_read)}")


# ══════════════════════════════════════════════════════════════
# 必修 2 — Z-Score 卡 sparkline 接危險門檻 registry
# ══════════════════════════════════════════════════════════════
class TestZScoreSparklineDangerLines:
    """`ui/helpers/chart/danger.py::add_danger_hlines` 自 v19.145 Phase B 寫好
    (10 條測試守著)卻 production 0 caller;SPEC §16.2 的「Phase B 把 SSOT 套到
    chart」從未落地 → 18 張 Z-Score 卡沒有任何警戒線。"""

    def test_spark_key_maps_only_direct_registry_hits(self):
        """key 對應**只有一條規則**:去前綴轉小寫直查 registry。

        **禁止 UI 層別名表**(§3.3 第二份真相):矩陣 key 與 registry spec key
        大量不同名,對不上就誠實回 None、不畫線(§1)。
        本測試以「registry 有沒有 → 該不該對上」互推,不寫死今日覆蓋清單,
        日後 user 核准在 registry 補 spec 時本測試不會誤紅。
        """
        from shared.macro_buckets import SPECS_BY_KEY
        from ui.tab1_macro import _zs_danger_spec_key
        from ui.tab1_macro_midcycle import _ZS_INDICATORS

        for _spec in _ZS_INDICATORS:
            _k = _spec[0]
            _got = _zs_danger_spec_key(f"zs_{_k}")
            if _k.lower() in SPECS_BY_KEY:
                assert _got == _k.lower(), f"{_k} 應直接對上 registry"
            else:
                assert _got is None, (
                    f"{_k} 在 registry 沒有 spec,卻對應到 {_got!r} —— "
                    "UI 層疑似偷寫了別名對照表(§3.3)")

    def test_non_zs_keys_are_not_hijacked(self):
        """短線雷達 / 拐點的 key 不得被 zs 分支吃掉(既有線不能被換掉)。"""
        from ui.tab1_macro import _zs_danger_spec_key
        for _k in ("vix_level", "hy_oas_delta", "us_m2_yoy", "pmi", "", None, 123):
            assert _zs_danger_spec_key(_k) is None

    def test_registered_zs_card_gets_registry_lines(self):
        """**修正前必紅** —— `_radar_threshold_lines` 對 `zs_*` 一律 `return []`,
        PMI 卡上沒有 50 榮枯線、也沒有 46 嚴重線,初學者看不出數字算好算壞。

        拿掉 `_make_radar_sparkline` 內的 `add_danger_hlines` 呼叫 → shapes 空 → 紅。
        """
        from ui.tab1_macro import _make_radar_sparkline
        _fig = _make_radar_sparkline([52.0, 51.0, 49.5, 48.0], "zs_PMI", "#888888")
        assert _fig is not None, "sparkline 建不出來"
        _ys = _shape_ys(_fig)
        assert len(_ys) == 2, f"PMI 應有黃/紅 2 條線,實際 {_ys}"

    def test_line_values_track_the_registry_not_a_local_copy(self):
        """漂移鎖:線的高度必須等於 registry 的值 —— 有人在 UI 抄一份就會紅。

        浮點比較用 `pytest.approx`(CLAUDE.md §4.3 禁 `==`)。
        """
        from shared.macro_buckets import SPECS_BY_KEY
        from ui.tab1_macro import _make_radar_sparkline
        _spec = SPECS_BY_KEY["pmi"]
        _fig = _make_radar_sparkline([52.0, 51.0, 49.5, 48.0], "zs_PMI", "#888888")
        _ys = sorted(_shape_ys(_fig))
        assert _ys == pytest.approx(sorted([_spec.yellow, _spec.red]))

    def test_unregistered_zs_card_draws_nothing(self):
        """§1 誠實:registry 沒註冊的指標(ADL 等)寧可沒有警戒線,
        也不畫一條沒有 SSOT 背書的線。"""
        from ui.tab1_macro import _make_radar_sparkline
        for _k in ("zs_ADL", "zs_DXY", "zs_CPI", "zs_M2", "zs_LEI", "zs_FED_BS"):
            _fig = _make_radar_sparkline([0.28, 0.29, 0.30], _k, "#888888")
            assert _shape_ys(_fig) == [], f"{_k} 不在 registry,不該畫線"

    def test_existing_radar_lines_unchanged(self):
        """回歸:短線雷達既有的 inline threshold 線(與 services 分級同源)
        不得被本次改動影響。"""
        from ui.tab1_macro import _make_radar_sparkline
        _fig = _make_radar_sparkline([18.0, 22.0, 26.0], "vix_level", "#888888")
        _ys = sorted(_shape_ys(_fig))
        assert _ys == pytest.approx([25.0, 30.0])


# ══════════════════════════════════════════════════════════════
# 必修 3 — 桶標籤收 BUCKET_ORDER / BUCKET_META
# ══════════════════════════════════════════════════════════════
class TestBucketBarLabelsUseSsot:
    """`shared.macro_buckets.BUCKET_ORDER` + `BUCKET_META` 全 repo 唯一消費者
    是 tests;真正畫在畫面上的是 beginner_view 裡兩份硬寫副本。"""

    def test_helper_exists_and_follows_bucket_order(self):
        """**修正前必紅** —— `_bucket_bar_cells` 不存在(兩份 `_order` 各自寫死)。"""
        from shared.macro_buckets import BUCKET_ORDER
        from ui.helpers.macro.beginner_view import _bucket_bar_cells
        assert [c[0] for c in _bucket_bar_cells(BUCKET_ORDER)] == BUCKET_ORDER

    def test_titles_derived_from_bucket_meta(self):
        """桶名 / emoji 必須由 registry 導出 —— registry 改了畫面就跟著改。"""
        from shared.macro_buckets import BUCKET_META, BUCKET_ORDER
        from ui.helpers.macro.beginner_view import _bucket_bar_cells
        for _k, _title, _sub in _bucket_bar_cells(BUCKET_ORDER):
            _m = BUCKET_META[_k]
            assert _title == f"{_m['emoji']} {_m['title']}"

    def test_no_hardcoded_bucket_title_literals_left(self):
        """**修正前必紅** —— 兩份 `_order` 裡各有 4~5 個寫死的桶標籤字面值。

        用 **exact** 比對:docstring / 註解裡引述桶名不算殘留副本
        (本檔多處說明文字含這些字,子字串比對會永遠紅)。
        """
        from shared.macro_buckets import BUCKET_META
        _consts = _exact_string_constants(_BEGINNER)
        for _k, _m in BUCKET_META.items():
            _label = f"{_m['emoji']} {_m['title']}"
            assert _label not in _consts, (
                f"beginner_view.py 仍有寫死的桶標籤 {_label!r} —— "
                "唯一來源必須是 shared/macro_buckets.BUCKET_META")

    def test_display_text_is_byte_for_byte_unchanged(self):
        """**本波只做 DRY,一字不改顯示文字**(user 未核准文案改寫)。

        這是 golden 鎖:任何人把副標順手「白話化」都會在這裡紅,
        必須先拿到 user 拍板。

        ⚠️ 若只有拐點桶那格不符,先比對兩邊 emoji 的 variation selector
        (U+FE0F)有沒有一致 —— 那也是真的顯示差異,不是測試寫錯。
        """
        from shared.macro_buckets import BUCKET_ORDER
        from ui.helpers.macro.beginner_view import _bucket_bar_cells
        # ⚠️ 2026-08-05 user 拍板:副標改吃 registry(原 `_BAR_SUB_CURRENT`
        #    override 已刪)。三桶文案因此改變 —— 這是**核准過的**變更,不是漂移:
        #      long: `regime / 結構` → `結構 / 景氣位階`(消除英文行話 regime)
        #      mid : `景氣循環`      → `景氣循環 3-12 月`(補上時間尺度)
        #      news: `系統性風險`    → `系統性風險掃描`(講清楚是「掃描」不是「已發生」)
        #    golden 鎖本身保留:日後任何人再順手改副標,仍要先拿到 user 拍板。
        assert _bucket_bar_cells(BUCKET_ORDER) == [
            ("long",       "🌳 長期", "結構 / 景氣位階"),
            ("mid",        "📈 中期", "景氣循環 3-12 月"),
            ("short",      "🎯 短線", "即時 risk-off"),
            ("inflection", "⚠️ 拐點", "領先警報"),
            ("news",       "📰 新聞", "系統性風險掃描"),
        ]

    def test_no_local_sub_override_table_left(self, monkeypatch):
        """**修正前必紅** —— 副標必須只有 registry 一份真相。

        `_BAR_SUB_CURRENT` 是收 SSOT 過程中的過渡表,user 拍板後已刪除。
        本測試防它以任何形式復活(含改名)。

        ⚠️ 2026-08-05 重寫。舊版是 **AST 形狀掃描**:抓「任何 key 是桶名的
        dict literal」。那個形狀根本不是「本地文案覆蓋表」的特徵 ——
        `compute_four_horizon_summary` 的 return dict、以及任何以桶 key 當索引
        的對照結構(區段標題鏡像等)都是同一個形狀,全部被誤判。實測本檔在
        production 完全正確的狀態下也會紅,屬**假警報型守衛**。

        改成**行為斷言**,直接測要保護的那條契約本身:把 registry 的桶標籤與
        副標換掉,`_bucket_bar_cells` 的輸出必須跟著換。只要有任何一份本地覆蓋
        (不管它叫什麼名字、長什麼形狀),被覆蓋的那一桶就不會跟著變 → 紅。
        逐桶檢查,避免只改一桶的局部覆蓋躲過。
        """
        from shared.macro_buckets import BUCKET_ORDER
        import ui.helpers.macro.beginner_view as _mbv
        for _k in BUCKET_ORDER:
            _orig = _mbv._BUCKET_META[_k]
            monkeypatch.setitem(_mbv._BUCKET_META, _k, dict(
                _orig, emoji="🛎️", title=f"哨兵標題{_k}", sub=f"哨兵副標{_k}"))
            _cells = {c[0]: c for c in _mbv._bucket_bar_cells(BUCKET_ORDER)}
            assert _cells[_k][1] == f"🛎️ 哨兵標題{_k}", (
                f"{_k} 桶的標籤沒跟著 registry 走 —— UI 層另有一份本地覆蓋")
            assert _cells[_k][2] == f"哨兵副標{_k}", (
                f"{_k} 桶的副標沒跟著 registry 走 —— UI 層另有一份本地覆蓋")
            monkeypatch.undo()

    def test_four_horizon_bar_excludes_news_bucket(self):
        """四時域 bar 只有 4 桶,新聞是五桶 bar 才有的第 5 桶。"""
        from shared.macro_buckets import BUCKET_ORDER
        from ui.helpers.macro.beginner_view import _bucket_bar_cells
        _four = _bucket_bar_cells([_k for _k in BUCKET_ORDER if _k != "news"])
        assert [c[0] for c in _four] == ["long", "mid", "short", "inflection"]

    def test_unknown_bucket_key_fails_loud(self):
        """§1:未知桶 key 當場炸,不得靜默少畫一桶。"""
        from ui.helpers.macro.beginner_view import _bucket_bar_cells
        with pytest.raises(KeyError):
            _bucket_bar_cells(["not_a_bucket"])

    def test_status_emoji_table_still_single_sourced(self):
        """回歸:本次動 `_order` 不得順手引入新的燈號 emoji 對照表 literal
        (test_audit_20260805_tab1_ui.py 有同型 AST 掃描,此處為就近保護)。"""
        _dup = [
            n for n in ast.walk(_tree(_BEGINNER))
            if isinstance(n, ast.Dict)
            and any(isinstance(k, ast.Constant) and k.value in ("green", "yellow", "red")
                    for k in n.keys)
            and any(isinstance(v, ast.Constant) and v.value in ("🟢", "🟡", "🔴")
                    for v in n.values)
        ]
        assert not _dup


# ══════════════════════════════════════════════════════════════
# 必修 4 — hero 卡指標筆數改吃 provenance 側車
# ══════════════════════════════════════════════════════════════
class TestHeroIndicatorCountFromProvenance:
    def test_hero_passes_provenance_out(self):
        """**修正前必紅** —— hero 呼叫 `calculate_composite_score(ind)`,
        沒傳側車;筆數是寫死字面值(且已與實際不符)。"""
        _cs = _calls(_TAB1, "calculate_composite_score")
        assert _cs, "tab1_macro.py 沒有 calculate_composite_score 呼叫"
        assert any(kw.arg == "provenance_out" for c in _cs for kw in c.keywords), (
            "hero 未傳 provenance_out= —— 側車算好的 n_indicators 仍 0 consumer")

    def test_hero_reads_n_indicators_key(self):
        """**修正前必紅** —— 傳了側車卻不讀 `n_indicators` 等於白傳
        (`PROCESS.md §4` coverage_out 同型:算得完整、就是漏了呼叫端那一行)。"""
        assert "n_indicators" in _TAB1.read_text(encoding="utf-8"), (
            "tab1_macro.py 沒讀 provenance 的 n_indicators")

    def test_no_hardcoded_indicator_count_string(self):
        """**修正前必紅** —— 三處寫死指標筆數字面值。

        只掃**字串字面值**;註解裡的說明文字不算(避免說明自己讓自己紅)。
        """
        import re
        _bad = [s for s in _exact_string_constants(_TAB1)
                if re.search(r"\d+\s*(指標|項指標)", s)]
        assert not _bad, (
            f"tab1_macro.py 仍有寫死的指標筆數文案:{_bad!r} —— "
            "筆數隨來源命中浮動,必須由 provenance n_indicators 導出")

    def test_sidecar_counts_real_indicators_only(self):
        """產生端契約:`_` 前綴 meta 不算指標,型別錯的條目也不算。

        (這條是產生端保護;真正的接線由上面兩條守 —— 兩者缺一不可。)
        """
        from services.macro.composite_score import calculate_composite_score
        _prov: dict = {}
        calculate_composite_score(
            {
                "PMI": {"score": 1, "weight": 1.0},
                "VIX": {"score": -1, "weight": 2.0},
                "_fred_sources": {"DGS10": {"success": True}},
                "BROKEN": "not-a-dict",
            },
            provenance_out=_prov)
        assert _prov["n_indicators"] == 2
        assert "_fred_sources" not in _prov["contributions"]

    def test_empty_indicators_reports_zero_not_a_fake_count(self):
        """§1 邊界:沒有任何指標時筆數必須是 0,不得沿用任何預設值。"""
        from services.macro.composite_score import calculate_composite_score
        _prov: dict = {}
        calculate_composite_score({}, provenance_out=_prov)
        assert _prov["n_indicators"] == 0


# ══════════════════════════════════════════════════════════════
# 必修 5 — 第三套指標分類法刪除
# ══════════════════════════════════════════════════════════════
_DEAD_CATEGORY_NAMES = ("category_score", "category_history",
                        "category_verdict", "_CATEGORY_MAP")


class TestThirdTaxonomyDeleted:
    """`PROCESS.md §4`:0 consumer → 接線或刪除,不得留著假裝有揭露。
    這一組是「第三套分類法」,與本輪「歸類」主題直接衝突。"""

    def test_symbols_gone_from_module(self):
        """**修正前必紅** —— 四個符號都還在。"""
        import ui.helpers.macro.helpers as _h
        for _n in _DEAD_CATEGORY_NAMES:
            assert not hasattr(_h, _n), f"{_n} 仍在(production 0 caller 的死碼)"

    def test_symbols_gone_from_backward_compat_shim(self):
        """shim 用 `import *` + dir() 轉發,漏刪會從側門復活。"""
        import ui.helpers.macro_helpers as _shim
        for _n in _DEAD_CATEGORY_NAMES:
            assert not hasattr(_shim, _n), f"shim 仍轉發 {_n}"

    def test_no_stale_call_or_import_anywhere(self):
        """刪除必須連引用一起清(對照 `PROCESS.md §4` ruff 白名單案例)。

        用 AST 找**真的 import / 呼叫**,不掃字面文字 —— 否則刪除理由的
        說明文字會被誤判成殘留引用。
        """
        for _p in (list((_ROOT / "ui").rglob("*.py"))
                   + list((_ROOT / "services").rglob("*.py"))
                   + list((_ROOT / "mcp_server").rglob("*.py"))):
            try:
                _t = ast.parse(_p.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for _n in ast.walk(_t):
                if isinstance(_n, ast.Call) and _fn_name(_n) in _DEAD_CATEGORY_NAMES:
                    pytest.fail(f"{_p} 仍呼叫已刪除的 {_fn_name(_n)}")
                if isinstance(_n, ast.ImportFrom) and any(
                        a.name in _DEAD_CATEGORY_NAMES for a in _n.names):
                    pytest.fail(f"{_p} 仍 import 已刪除的 category_* 符號")

    def test_surviving_helpers_still_importable(self):
        """刪錯東西的防護:同檔其餘 helper 不得被連坐。"""
        from ui.helpers.macro.helpers import (  # noqa: F401
            calculate_composite_score,
            composite_verdict,
            format_phase_score,
            mk_fund_signal,
            quartile_check,
        )


# ══════════════════════════════════════════════════════════════
# 2026-08-05 追加 — UI 讀的指標代碼必須真的存在於服務層產出
#
# 病灶:四時域桶的其中四個判讀分支讀的代碼,服務層從來沒有寫過。取值失敗被
# `or 0.0` / `is not None` 吸收 → 分支**永遠不觸發**,畫面上那一桶看起來有在
# 掃四顆、實際只掃兩顆。這種缺陷對 lint / type check / 產生端單元測試全部免疫
# (`PROCESS.md §4` 的「算對了但沒接出去」同一族),而守它的測試又剛好餵人造
# 輸入 —— 只走了 production 永遠走不到的那條路,於是雙重空轉。
#
# 本組因此**兩邊都從真實原始碼導出**,不比對任何人工維護的清單:
#   產生端 → AST 解析服務層那支抓取函式,收集它實際寫入的每一個代碼
#   消費端 → AST 解析 UI helper,收集取值 helper 每一次呼叫傳入的代碼
# 兩份都是「程式碼現在真的長怎樣」,任一邊改名而另一邊沒跟上 → 當場紅。
# ══════════════════════════════════════════════════════════════
_US_IND = _ROOT / "services" / "macro" / "us_indicators.py"
_FETCH_FN = "fetch_all_indicators"
_ACC = "R"                 # 抓取函式內累積結果的區域變數名
_READER_FN = "_v"          # beginner_view 內部的取值 helper


def _service_indicator_constructions() -> dict:
    """服務層抓取函式實際寫入的 {代碼: 該筆 dict(...) 的 keyword 名稱集合}。

    `PROCESS.md §4` 測試自身可執行性:找不到檔 / 找不到函式 / 收不到任何一筆
    →**直接 fail**,不得回空集讓下面的子集斷言恆真(那就是第二次空轉)。
    """
    if not _US_IND.exists():
        raise AssertionError(f"找不到服務層來源檔 {_US_IND} —— 本測試需要它才能比對")
    _fn = [n for n in ast.walk(_tree(_US_IND))
           if isinstance(n, ast.FunctionDef) and n.name == _FETCH_FN]
    if not _fn:
        raise AssertionError(f"{_US_IND} 內找不到 {_FETCH_FN} —— 函式改名了?")
    _out: dict = {}
    for _n in ast.walk(_fn[0]):
        if not (isinstance(_n, ast.Assign) and _n.targets
                and isinstance(_n.targets[0], ast.Subscript)
                and isinstance(_n.targets[0].value, ast.Name)
                and _n.targets[0].value.id == _ACC):
            continue
        _sl = _n.targets[0].slice
        if not (isinstance(_sl, ast.Constant) and isinstance(_sl.value, str)):
            continue          # 迴圈內以變數當代碼的那幾筆,靜態解析不到 → 跳過
        _kw: set = set()
        if isinstance(_n.value, ast.Call):
            _kw = {k.arg for k in _n.value.keywords if k.arg}
        _out.setdefault(_sl.value, set()).update(_kw)
    if not _out:
        raise AssertionError(
            f"{_FETCH_FN} 內解析不到任何指標寫入 —— 寫法變了,本測試已失效需重寫")
    return _out


def _ui_indicator_reads() -> list:
    """beginner_view 內每一次取值呼叫的 (代碼, 欄位名)。

    欄位名省略時填 None(= 取值 helper 的預設欄位,由呼叫端 signature 決定,
    這裡不重寫一份預設值)。代碼非字面常數 → fail(靜態驗不到就不能假裝驗過)。
    """
    _out: list = []
    for _n in ast.walk(_tree(_BEGINNER)):
        if not (isinstance(_n, ast.Call) and getattr(_n.func, "id", "") == _READER_FN):
            continue
        if not _n.args:
            raise AssertionError("取值 helper 被無引數呼叫,無法驗證")
        _k = _n.args[0]
        if not (isinstance(_k, ast.Constant) and isinstance(_k.value, str)):
            raise AssertionError(
                "取值 helper 的代碼引數不是字面常數 —— 靜態驗不到,"
                "請改回字面常數或為它補一條等價的行為測試")
        _f = _n.args[1] if len(_n.args) >= 2 else None
        _out.append((_k.value,
                     _f.value if isinstance(_f, ast.Constant) else None))
    if not _out:
        raise AssertionError(
            "beginner_view 解析不到任何取值呼叫 —— helper 改名了,本測試已失效需重寫")
    return _out


class TestIndicatorKeysExistInServiceLayer:
    """UI ↔ 服務層的指標代碼漂移鎖。"""

    def test_every_key_the_ui_reads_is_actually_produced(self):
        """**修正前必紅**(舊行為與斷言衝突,非 ImportError):

        修正前 UI 有 4 個判讀分支 + 3 個別名 fallback 讀的代碼,服務層那支抓取
        函式一個都沒寫過 → 這裡列得出具體幾個,直接紅。
        """
        _produced = _service_indicator_constructions()
        _missing = sorted({k for k, _f in _ui_indicator_reads() if k not in _produced})
        assert not _missing, (
            f"UI 讀了服務層不存在的指標代碼:{_missing} —— "
            f"這些判讀分支 production 永遠不會觸發(§1:不要留恆不觸發的死判讀)。"
            f"服務層目前產出 {len(_produced)} 個代碼。")

    def test_every_named_field_exists_on_that_indicator(self):
        """欄位層的同型守衛。

        指名欄位(而非預設欄位)的那幾筆,欄位名必須真的出現在服務層該筆的建構
        引數裡。服務層日後把該欄改名 → 這裡紅,而不是靜悄悄退回不觸發。
        """
        _produced = _service_indicator_constructions()
        _bad = [(k, f) for k, f in _ui_indicator_reads()
                if f is not None and k in _produced and f not in _produced[k]]
        assert not _bad, (
            f"UI 指名了服務層沒有的欄位:{_bad} —— 取值恆 None,判讀永不觸發")

    def test_default_field_exists_on_every_key_the_ui_reads(self):
        """未指名欄位的那幾筆,走的是取值 helper 的預設欄位 —— 同樣要存在。

        預設欄位名從 helper 的 signature 取,不在測試裡重打一份。
        """
        _inner = next(n for n in ast.walk(_tree(_BEGINNER))
                      if isinstance(n, ast.FunctionDef) and n.name == _READER_FN)
        assert _inner.args.defaults, "取值 helper 沒有預設欄位了 —— 本測試需重寫"
        _default = _inner.args.defaults[-1]
        assert isinstance(_default, ast.Constant), "取值 helper 的預設欄位不是常數"
        _produced = _service_indicator_constructions()
        _bad = [k for k, f in _ui_indicator_reads()
                if f is None and k in _produced and _default.value not in _produced[k]]
        assert not _bad, f"這些指標沒有預設欄位:{_bad}"

    def test_trust_layer_expected_list_is_all_produced(self):
        """④ 可信度層的分母(既有 SSOT 清單)也必須全部產得出來。

        分母若含服務層根本不會產的代碼,那個 chip 會恆報缺漏 —— 與本輪必退 1
        修的「chip 自己打自己」是同一個病灶的另一面。
        """
        from ui.helpers.session import D5_KEYS
        _produced = _service_indicator_constructions()
        _ghost = [k for k in D5_KEYS if k not in _produced]
        assert not _ghost, f"可信度層分母含服務層不產出的代碼:{_ghost}"

    def test_the_scan_is_not_vacuous(self):
        """守衛的守衛(`PROCESS.md §4`):兩邊的掃描都必須真的掃到東西。

        任一邊因寫法變更而回空,上面四條會全部變成恆真的假通過。
        """
        _produced = _service_indicator_constructions()
        _reads = _ui_indicator_reads()
        assert len(_produced) >= 10, f"服務層只掃到 {len(_produced)} 個代碼,不合理"
        assert len(_reads) >= 5, f"UI 只掃到 {len(_reads)} 次取值,不合理"
        # 欄位集合也要真的收集到(否則欄位層那兩條同樣會恆真)。
        # provenance meta 那類直接指派變數的條目沒有建構引數,不計入。
        assert sum(1 for v in _produced.values() if v) >= 10, (
            "解析得到的欄位集合幾乎全空 —— 建構寫法變了,欄位層守衛已失效")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
