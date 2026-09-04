"""2026-09-04 第四輪稽核 — 「證據支撐」產出端契約的守衛。

## 這個檔在守什麼（讀之前先讀這一段）

連續四輪獨立稽核，**每一輪都在一個新的地方**找到同一類缺陷：
**畫面宣稱了一個「它取到的資料撐不起來」的定論**（第 1 輪卡 3 零觀測、
第 2 輪卡 3 打平、第 3 輪卡 1／卡 5 完全斷線、第 4 輪卡 3 **只剩一筆觀測**）。
每一輪的修法都是**在那張卡上再手推一道閘門**，而每一道手推的閘門都漏掉下一種形態。

本輪把判定收到**產出端**（`shared/evidence_support.py` 的規則
＋ `services/macro/evidence.py` 的領域表與 builder），消費端只讀 `.sufficient`。
本檔守的是那條契約本身：

  · **漂移鎖** —— 權重表 / 相位帶 / 雙軸 key 表 / score 上界，全部必須逐一等於
    `services/macro/us_indicators.py` 裡的**生產端字面值**（兩個方向都鎖）。
  · **規則本身** —— 四條規則各自的判定，含每一輪那四種形態。
  · **R4-F1 的兩個實測情境** —— 逐字釘住「修好之前會渲染成什麼」。

⚠️ **本檔刻意不驗畫面**（那在 `tests/test_batch2_top_card_grid.py`）。
兩邊都要有：這裡驗「產出端說了什麼」，那裡驗「消費端有沒有照著做」。
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from services.macro.composite_score import (
    COMPOSITE_ALARM_LEVELS,
    calculate_composite_score,
    composite_verdict,
)
from services.macro.evidence import (
    GROWTH_AXIS_KEYS,
    INFLATION_AXIS_KEYS,
    MACRO_CORRELATED_FAMILIES,
    MACRO_INDICATOR_MAX_ABS_SCORE,
    MACRO_INDICATOR_SCORING_WEIGHTS,
    MAX_CORRELATED_FAMILY_WEIGHT,
    PHASE_BAND_EDGES,
    PHASE_NARROWEST_BAND,
    PHASE_SCALE,
    PHASE_WEIGHT_PER_BAND,
    phase_band,
    phase_support,
    scoring_weight,
)
from services.macro.us_indicators import (
    EXPECTED_INDICATOR_KEYS,
    calc_growth_inflation_axis,
    calc_macro_phase,
)
from shared.evidence_support import (
    EvidenceSupport, all_of, combine, net_margin, summed_verdict, weighted_verdict,
    witnessed,
)
from shared.signal_thresholds import MACRO_PHASE_MIN_TOTAL_WEIGHT

_US_IND = pathlib.Path("services/macro/us_indicators.py")


# ════════════════════════════════════════════════════════════════════════
# A. 漂移鎖 —— 領域表必須逐一等於生產端的字面值
# ════════════════════════════════════════════════════════════════════════
def _producer_weight_sites() -> tuple[dict, list]:
    """AST 掃 `R[...] = dict(..., weight=...)`，回 (literal-key 表, 變數-key 節點)。

    ⚠️ 刻意**不用字串 grep**：`weight=` 這三個字在註解、docstring 與別的 dict
    裡都會出現（本 repo 的憲法逐字記載過「grep 會被 docstring 騙」）。
    """
    _tree = ast.parse(_US_IND.read_text(encoding="utf-8"))
    _literal: dict = {}
    _dynamic: list = []
    for _n in ast.walk(_tree):
        if not (isinstance(_n, ast.Assign) and len(_n.targets) == 1):
            continue
        _t = _n.targets[0]
        if not (isinstance(_t, ast.Subscript) and isinstance(_t.value, ast.Name)
                and _t.value.id == "R"):
            continue
        _v = _n.value
        if not (isinstance(_v, ast.Call) and getattr(_v.func, "id", None) == "dict"):
            continue
        _w_node = next((k.value for k in _v.keywords if k.arg == "weight"), None)
        if _w_node is None:
            continue
        # `weight=(0 if hit else 1)` → 取所有字面值的**最大**（＝上界，從嚴）
        _ws = [c.value for c in ast.walk(_w_node)
               if isinstance(c, ast.Constant) and isinstance(c.value, (int, float))]
        assert _ws, f"weight 表達式無法解析（第 {_n.lineno} 行）：{ast.unparse(_w_node)}"
        try:
            _key = ast.literal_eval(_t.slice)
        except Exception:                        # noqa: BLE001 — 變數 key（FX 迴圈）
            _dynamic.append((float(max(_ws)), _n.lineno))
            continue
        _literal[_key] = float(max(_ws))
    return _literal, _dynamic


def test_the_weight_table_matches_the_producer():
    """`MACRO_INDICATOR_SCORING_WEIGHTS` **逐一等於**生產端的 `weight=` 字面值。

    **兩個方向都鎖**（少一個、多一個、值不同，三種都轉紅）—— 這正是 R4-F8 記載的
    「只鎖一邊等於沒鎖」：constant-side 與 function-side 必須互為充要。

    突變驗證：
      · 把表裡 `PMI` 改成 1.0            → 轉紅（值不同）
      · 把表裡 `LEI` 整行刪掉            → 轉紅（生產端有、表裡沒有）
      · 在表裡多加 `"FOO": 1.0`          → 轉紅（表裡有、生產端沒有）
    """
    _literal, _dynamic = _producer_weight_sites()
    # FX 三兄弟走 `R[_key] = dict(...)` 的變數 key，字面掃不到 —— 單獨核對
    _fx = {"EURUSD", "USDJPY", "USDCNH"}
    assert len(_dynamic) == 1, (
        f"生產端出現 {len(_dynamic)} 個變數-key 的 `R[...] = dict(...)`；"
        f"本鎖只認得 FX 迴圈那一個，新增的請一併登記")
    assert _dynamic[0][0] == 1.0, f"FX 迴圈的 weight 不是 1.0：{_dynamic[0]}"
    for _k in _fx:
        assert MACRO_INDICATOR_SCORING_WEIGHTS.get(_k) == 1.0, (
            f"{_k} 的權重與 FX 迴圈的字面值不符")

    assert set(_literal) | _fx == set(MACRO_INDICATOR_SCORING_WEIGHTS), (
        "權重表與生產端的 key 集合不一致：\n"
        f"  只在生產端：{sorted((set(_literal) | _fx) - set(MACRO_INDICATOR_SCORING_WEIGHTS))}\n"
        f"  只在表裡：{sorted(set(MACRO_INDICATOR_SCORING_WEIGHTS) - (set(_literal) | _fx))}")
    for _k, _w in _literal.items():
        assert MACRO_INDICATOR_SCORING_WEIGHTS[_k] == _w, (
            f"{_k} 權重漂移：表 {MACRO_INDICATOR_SCORING_WEIGHTS[_k]} vs 生產端 {_w}")


def test_the_weight_table_covers_exactly_the_declared_indicator_contract():
    """權重表的 key 集合 ＝ `EXPECTED_INDICATOR_KEYS`（既有的產出契約）。

    兩份清單分開放（一份給診斷、一份給證據會計）本來就有漂移風險，故直接鎖死。
    """
    assert set(MACRO_INDICATOR_SCORING_WEIGHTS) == set(EXPECTED_INDICATOR_KEYS), (
        f"只在權重表：{sorted(set(MACRO_INDICATOR_SCORING_WEIGHTS) - set(EXPECTED_INDICATOR_KEYS))}；"
        f"只在 EXPECTED：{sorted(set(EXPECTED_INDICATOR_KEYS) - set(MACRO_INDICATOR_SCORING_WEIGHTS))}")


@pytest.mark.parametrize("score", [round(i * 0.1, 1) for i in range(0, 101)])
def test_the_band_function_matches_the_producer(score):
    """`phase_band()` 與 `calc_macro_phase` 的 if-chain **逐點等價**（0.0~10.0 每 0.1）。

    本輪刻意**不改**那段 if-chain（改它有引入 bug 的風險），改用漂移鎖。
    突變驗證：把 `PHASE_BAND_EDGES` 的 5.0 改成 4.0 → 多個格子轉紅。
    """
    _ind = {"X": {"weight": 1, "score": score / 5.0 - 1.0}}   # 造一個目標分數
    _phase = calc_macro_phase(_ind)
    assert phase_band(_phase["score"]) == _phase["phase"], (
        f"score={_phase['score']}：band 函式說 {phase_band(_phase['score'])}，"
        f"生產端說 {_phase['phase']}")


def test_the_axis_key_tables_match_the_producer():
    """雙軸 key 表 **逐一等於** `calc_growth_inflation_axis` 實際 `_get(...)` 的 key。

    順序也要一致 —— `_axis_signals` 靠「在場的 key 依同一順序」與 signals 列表對齊。
    突變驗證：把 `GROWTH_AXIS_KEYS` 的 `COPPER` 拿掉 → 轉紅。
    """
    _src = inspect.getsource(calc_growth_inflation_axis)
    _tree = ast.parse(_src.lstrip())
    _keys: list = []
    for _n in ast.walk(_tree):
        if (isinstance(_n, ast.Call) and getattr(_n.func, "id", None) == "_get"
                and _n.args and isinstance(_n.args[0], ast.Constant)):
            _keys.append(_n.args[0].value)
    assert list(GROWTH_AXIS_KEYS) + list(INFLATION_AXIS_KEYS) == _keys, (
        f"雙軸 key 表與生產端讀取順序不符：表={list(GROWTH_AXIS_KEYS) + list(INFLATION_AXIS_KEYS)}"
        f" vs 生產端={_keys}")


def test_no_producer_emits_a_score_beyond_the_declared_bound():
    """`MACRO_INDICATOR_MAX_ABS_SCORE` 必須是生產端 `score=` 的真上界。

    綜合健康度的「沒取到的那些可能貢獻多少」用它當上界；低估就會 fail-open。
    ⚠️ 本鎖**要求 score 表達式維持可分析**（字面值 / IfExp of 字面值 /
    帶 `max_abs=` 的呼叫 / 解析得到的區域變數）—— 寫成別的形狀就轉紅，
    那是刻意的：不可分析 ＝ 這條上界不再有人守。
    """
    _tree = ast.parse(_US_IND.read_text(encoding="utf-8"))
    # ⚠️ 名稱解析**必須限定在同一個函式內**：`score` 這個變數名在
    # `fetch_all_indicators`（PMI 那格）與 `calc_macro_phase`（最後的正規化）
    # **兩個函式裡都有**，跨函式收集會把 `round(max(0, min(10, norm)), 1)`
    # 當成 PMI 的 score —— 那正是本 repo 憲法點名過的「工具選錯 → 結論必錯」。
    _fetch_fn = next(_f for _f in ast.walk(_tree)
                     if isinstance(_f, ast.FunctionDef)
                     and _f.name == "fetch_all_indicators")
    _assigned: dict = {}
    for _n in ast.walk(_fetch_fn):
        if not (isinstance(_n, ast.Assign) and len(_n.targets) == 1):
            continue
        _tgt = _n.targets[0]
        if isinstance(_tgt, ast.Name):
            _assigned.setdefault(_tgt.id, []).append(_n.value)
        elif isinstance(_tgt, ast.Tuple):
            # `score_nfp, sig_nfp, col_nfp = _nfp_tier(cur_d)` —— 解包無法逐位對應，
            # 整個呼叫都掛上去，由 `_bound` 去掃那個函式的 return 字面值（從嚴）。
            for _e in _tgt.elts:
                if isinstance(_e, ast.Name):
                    _assigned.setdefault(_e.id, []).append(_n.value)

    def _bound(node) -> float:
        if isinstance(node, ast.Call):
            _m = next((k.value for k in node.keywords if k.arg == "max_abs"), None)
            if _m is not None and isinstance(_m, ast.Constant):
                return abs(float(_m.value))
            # `_nfp_tier(...)` 這種:回去掃那個函式的 return 字面值
            _fn = getattr(node.func, "id", "")
            for _f in ast.walk(_tree):
                if isinstance(_f, ast.FunctionDef) and _f.name == _fn:
                    _vals = [c.value for c in ast.walk(_f)
                             if isinstance(c, ast.Constant)
                             and isinstance(c.value, (int, float))]
                    return max(abs(float(v)) for v in _vals)
            raise AssertionError(f"score 呼叫無法解析上界：{ast.unparse(node)}")
        if isinstance(node, ast.Name):
            _cands = _assigned.get(node.id) or []
            assert _cands, f"score 變數無法解析：{node.id}"
            return max(_bound(c) for c in _cands)
        _vals = [c.value for c in ast.walk(node)
                 if isinstance(c, ast.Constant) and isinstance(c.value, (int, float))]
        if isinstance(node, ast.IfExp):
            # 只取「結果位置」的字面值，比較式裡的門檻不算
            _vals = []
            _stack = [node]
            while _stack:
                _x = _stack.pop()
                if isinstance(_x, ast.IfExp):
                    _stack += [_x.body, _x.orelse]
                elif isinstance(_x, ast.UnaryOp) and isinstance(_x.op, ast.USub):
                    _stack.append(_x.operand)
                elif isinstance(_x, ast.Constant):
                    _vals.append(_x.value)
                else:
                    _stack.append(_x)
        assert _vals, f"score 表達式無法解析：{ast.unparse(node)}"
        return max(abs(float(v)) for v in _vals)

    _worst = 0.0
    for _n in ast.walk(_fetch_fn):
        if not (isinstance(_n, ast.Assign) and len(_n.targets) == 1):
            continue
        _t = _n.targets[0]
        if not (isinstance(_t, ast.Subscript) and isinstance(_t.value, ast.Name)
                and _t.value.id == "R"):
            continue
        _v = _n.value
        if not (isinstance(_v, ast.Call) and getattr(_v.func, "id", None) == "dict"):
            continue
        _s = next((k.value for k in _v.keywords if k.arg == "score"), None)
        if _s is None:
            continue
        _worst = max(_worst, _bound(_s))
    assert _worst <= MACRO_INDICATOR_MAX_ABS_SCORE, (
        f"生產端最大 |score| = {_worst}，超過宣告上界 "
        f"{MACRO_INDICATOR_MAX_ABS_SCORE} —— 綜合健康度的缺值上界會低估（fail-open）")


def test_the_alarm_levels_exist_in_the_verdict():
    """`COMPOSITE_ALARM_LEVELS` 的字串必須真的是 `composite_verdict` 會吐的 level。

    否則規則 3 的豁免會**永遠不觸發**（把真警訊灰掉），而沒有人會發現。
    突變驗證：把常數改成 `("悲觀ish",)` → 轉紅。
    """
    _levels = {composite_verdict(_t)[1] for _t in
               (-99, -12, -7, 0, 7, 12, 99)}
    for _lv in COMPOSITE_ALARM_LEVELS:
        assert _lv in _levels, f"{_lv!r} 不是 composite_verdict 會產生的 level：{_levels}"


def test_the_threshold_constant_is_derived_not_typed():
    """門檻常數 ＝ （scale / 最窄帶）× 最大相關族權重，**逐項可算**（R4-F6）。"""
    assert PHASE_WEIGHT_PER_BAND == PHASE_SCALE / PHASE_NARROWEST_BAND
    assert MACRO_PHASE_MIN_TOTAL_WEIGHT == PHASE_WEIGHT_PER_BAND * MAX_CORRELATED_FAMILY_WEIGHT
    assert PHASE_NARROWEST_BAND == min(
        PHASE_BAND_EDGES[0], PHASE_BAND_EDGES[1] - PHASE_BAND_EDGES[0],
        PHASE_BAND_EDGES[2] - PHASE_BAND_EDGES[1], PHASE_SCALE - PHASE_BAND_EDGES[2])
    # 相關族全部由權重表導出，不得寫死
    assert MAX_CORRELATED_FAMILY_WEIGHT == max(
        sum(MACRO_INDICATOR_SCORING_WEIGHTS.get(_k, 0.0) for _k in _m)
        for _m in MACRO_CORRELATED_FAMILIES.values())


def test_every_declared_family_member_is_a_real_indicator():
    """相關族表不得指向不存在的 key（指錯了就等於那一族沒有被算進去）。"""
    for _name, _members in MACRO_CORRELATED_FAMILIES.items():
        for _k in _members:
            assert _k in MACRO_INDICATOR_SCORING_WEIGHTS, (
                f"相關族「{_name}」列了一個不存在的指標 {_k!r}")


# ════════════════════════════════════════════════════════════════════════
# B. 規則本身 —— 四輪找到的四種形態，一條規則全吃
# ════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("n_obs,expect", [
    (0, False),   # 第 1 輪：零觀測
    (1, False),   # 第 4 輪 R4-F1：一筆觀測給出 ±1.00（最大強度）
    (2, True),    # 兩筆同向、只缺一筆 → 缺的那筆反向也翻不掉
    (3, True),    # 全到齊
])
def test_the_margin_rule_covers_every_shape_found_in_four_audits(n_obs, expect):
    """通膨軸（3 個輸入）：**淨邊際 > 沒取到的筆數**。

    突變驗證（本輪實跑）：把 `net_margin` 的 `abs(_net) > len(_miss)`
    改成 **`bool(_got)`（只看有沒有觀測 ＝ 舊的「只數筆數」閘門）**
    → `n_obs=1` 那一格立刻轉紅。
    """
    _sig = {k: 1.0 for k in INFLATION_AXIS_KEYS[:n_obs]}
    assert net_margin("t", signals=_sig, expected=INFLATION_AXIS_KEYS).sufficient is expect


def test_a_tie_is_never_sufficient():
    """第 2 輪的形態（正負相抵）也被同一條規則吃掉。"""
    _sig = {"CPI": 1.0, "PPI": -1.0}
    _s = net_margin("t", signals=_sig, expected=INFLATION_AXIS_KEYS)
    assert not _s.sufficient and "正負相抵" in _s.reason


def test_a_witnessed_alarm_is_always_sufficient_even_with_missing_inputs():
    """規則 3（不對稱）：有實際觀測越線 → 恆充足，即使其他輸入都沒取到。

    突變驗證：把 `witnessed` 的 `sufficient=bool(_w)` 改成
    `sufficient=not missing` → 轉紅（真警報被灰掉，比假綠燈更糟）。
    """
    _s = witnessed("alarm", witnesses=["VIX"], obtained=["VIX"])
    assert _s.sufficient and not _s.reason


def test_a_universal_claim_needs_every_named_input():
    """規則 1：「四項均未觸發」少一項就不能講。"""
    _s = all_of("四項均未觸發", expected=("A", "B", "C", "D"), obtained=("A", "B", "C"))
    assert not _s.sufficient and "D" in _s.reason


def test_combine_requires_every_part():
    _ok = witnessed("x", witnesses=["A"])
    _bad = all_of("y", expected=("A", "B"), obtained=("A",))
    assert combine("z", _ok, _ok).sufficient
    assert not combine("z", _ok, _bad).sufficient


def test_support_refuses_to_be_silently_inconsistent():
    """不變量：充足不得帶理由、不充足不得沒有理由（§1 不靜默）。"""
    with pytest.raises(ValueError):
        EvidenceSupport(claim="c", rule="r", sufficient=True, reason="x")
    with pytest.raises(ValueError):
        EvidenceSupport(claim="c", rule="r", sufficient=False, reason="")


def test_a_single_correlated_family_must_not_decide_the_phase(): # noqa: D401
    """R4-F6 的實測邊界：`total_w == 10.0` 且殖利率兩腳都在 → **不充足**。

    修復前：舊閘門 `>= 10.0` 判它「充足」，而曲線一族單獨就能把分數
    從 4.0（復甦「最高勝率買點！逐步加碼」）推到 6.0（擴張「股優於債」）。

    突變驗證：把 `weighted_verdict` 的 `_T > _required` 改回
    `_T >= MACRO_PHASE_MIN_TOTAL_WEIGHT`（舊式）→ 轉紅。
    """
    _ind = {"YIELD_10Y2Y": {"weight": 2, "score": 2},
            "YIELD_10Y3M": {"weight": 2, "score": 2},
            "PMI": {"weight": 2, "score": 2},
            "HY_SPREAD": {"weight": 2, "score": 1},
            "M2": {"weight": 1, "score": 1},
            "VIX": {"weight": 1, "score": 1}}
    assert scoring_weight(_ind) == 10.0, "前提：這一組的權重合計剛好是門檻邊界"
    _p = calc_macro_phase(_ind)
    assert not _p["support"].sufficient, (
        f"權重合計 10.0、殖利率一族佔 4.0，仍被判為充足：{_p['support'].detail}")


def test_the_boundary_is_strictly_greater_not_greater_or_equal():
    """R4-F5：推導寫 `>`，實作就必須是 `>`（邊界值本身不算充足）。"""
    _sup = weighted_verdict(
        "c", score=6.0, obtained=("A",), missing=(),
        obtained_weight=10.0, missing_weight=0.0,
        family_weights={"F": 2.0}, band_of=phase_band,
        scale=PHASE_SCALE, weight_per_band=PHASE_WEIGHT_PER_BAND)
    assert not _sup.sufficient, "`total_w == 5×W` 是邊界，不該算充足（推導寫的是 >）"


def test_the_summed_verdict_treats_missing_as_the_fillna_zero_it_is():
    """綜合健康度：零指標 → 總分 0.0 → 「中性 + 分批進場」是 `fillna(0)` 的產物。"""
    _prov: dict = {}
    _total = calculate_composite_score({"_fred_sources": {}}, provenance_out=_prov)
    assert _total == 0.0 and composite_verdict(_total)[1] == "中性"
    assert not _prov["support"].sufficient, "零指標卻宣稱『中性』站得住"


def test_the_summed_verdict_keeps_the_pessimistic_alarm(): # noqa: D401
    """規則 3 在綜合健康度上**必須**保留：悲觀側是警訊，不得被灰掉。

    突變驗證：把 `composite_support(..., alarm_bands=...)` 的 `alarm_bands`
    拿掉 → 轉紅（真警訊被灰掉，稽核已逐字確認卡 2／卡 5 的不對稱性不可反轉）。
    """
    _ind = {"YIELD_10Y2Y": {"weight": 2, "score": -2},
            "YIELD_10Y3M": {"weight": 2, "score": -2},
            "HY_SPREAD": {"weight": 2, "score": -2}}
    _prov: dict = {}
    _total = calculate_composite_score(_ind, provenance_out=_prov)
    assert composite_verdict(_total)[1] in COMPOSITE_ALARM_LEVELS, "前提：這組是悲觀側"
    assert _prov["support"].sufficient, "真的悲觀警訊被充足性閘門吃掉了"


def test_summed_verdict_math():
    _s = summed_verdict("c", total=7.0, obtained=("A",), missing=("B",),
                        missing_swing=4.0, band_of=lambda t: composite_verdict(t)[1])
    assert not _s.sufficient and "+3.0" in _s.reason and "+11.0" in _s.reason


# ════════════════════════════════════════════════════════════════════════
# C. R4-F1 的兩個實測情境 —— 逐字釘住「修好之前渲染成什麼」
# ════════════════════════════════════════════════════════════════════════
_R4F1_THREE = {"PMI": {"value": 55.0}, "YIELD_10Y2Y": {"value": 0.8},
               "M2": {"value": 4.0}, "ADL": {"prev": 1.0},
               "CONSUMER_CONF": {"value": 85.0}, "JOBLESS": {"value": 22.0},
               "COPPER": {"value": 3.0},
               "CPI": {"value": 5.5}, "PPI": {"value": 6.0},
               "FED_RATE": {"value": 2.0}}
#: 同一組資料，只是通膨那三項裡有兩項沒抓到
_R4F1_ONE = {k: v for k, v in _R4F1_THREE.items() if k not in ("CPI", "PPI")}


def test_two_failed_fetches_must_not_flip_the_verdict_from_overheat_to_goldilocks():
    """**R4-F1 的核心情境**（實測值逐字釘住）：

        三項通膨都在：+0.33 → 「🔥 過熱」（注意泡沫與緊縮風險）
        只剩 FED_RATE：−1.00 → 「🌱 復甦/擴張」（黃金期，積極持有風險資產）

    兩次失敗的取數把「注意泡沫」翻成「積極持有」，而頭條那句「通膨 −1.00」
    ——**最強的「通膨受控」讀數** —— 來自一個**政策利率**觀測，不是通膨讀數。

    突變驗證：把 `net_margin` 的判定改成「有觀測就算數」→ 轉紅。
    """
    _gi3 = calc_growth_inflation_axis(_R4F1_THREE)
    _gi1 = calc_growth_inflation_axis(_R4F1_ONE)
    # 前提：生產端**確實**會吐出那兩個相反的象限（否則這條在守一個不存在的風險）
    assert _gi3["quadrant"] == "過熱" and _gi3["inflation_score"] == 0.33
    assert _gi1["quadrant"] == "復甦/擴張" and _gi1["inflation_score"] == -1.0
    # 修復：三項在 → 撐得住；只剩一項 → 撐不住
    assert _gi3["support"].sufficient, _gi3["support"].reason
    assert not _gi1["support"].sufficient
    assert not _gi1["inflation_support"].sufficient


def test_one_observation_is_indistinguishable_from_unanimity_without_support():
    """`n=1` 與「十項一致」的既有 key **逐位元組相同** —— 這就是舊閘門看不到它的原因。

    本條把那個事實釘住（它是 R4-F1 的成因），同時證明 support **能**分開它們。
    """
    _unanimous = dict(_R4F1_THREE)
    _unanimous.update({"CPI": {"value": 1.0}, "PPI": {"value": 1.0}})  # 三項全低
    _gi_u = calc_growth_inflation_axis(_unanimous)
    _gi_1 = calc_growth_inflation_axis(_R4F1_ONE)
    _face = ("quadrant", "quad_color", "quad_desc", "inflation_score",
             "inflation_dir", "inflation_up")
    assert all(_gi_u[k] == _gi_1[k] for k in _face), (
        "前提不成立：兩者的既有 key 應該逐一相同（那正是舊閘門分不開的原因）")
    # 只有 support 分得開
    assert _gi_u["support"].sufficient and not _gi_1["support"].sufficient


def test_total_outage_no_longer_supports_any_verdict():
    """完全斷線：分數仍是 5.0（**本輪未動生產端的算法**），但 support 說撐不住。"""
    _out = {"_fred_sources": {"DGS10": {"success": False}}}
    _p = calc_macro_phase(_out)
    assert _p["score"] == 5 and _p["phase"] == "擴張", "前提：生產端行為未變"
    assert not _p["support"].sufficient
    assert "一個計分指標都沒取到" in _p["support"].reason


# ════════════════════════════════════════════════════════════════════════
# 2026-09-04 突變驗證補課：下面三條是**突變測試抓出來的缺口**，不是新需求。
#
# 實測（`shared/evidence_support.py` 逐條改壞、跑完整兩個測試檔）：
#   · `_dominance_ok = (_T > _required)`  → `(len(_got) >= 3)`   **全綠**
#   · `_invariant = (band_of(_lo) == ...)` → `(len(_got) > 0)`   **全綠**
#   · `_ok = abs(_net) > len(_miss)`       → `>=`                 **全綠**
# 也就是說：**產出端那三條規則當時各自都可以被換成「數個數」而沒有任何測試會紅**
# —— 而「gate on count only」正是本輪要根除的那個錯法。
# 三條缺口的共通成因：既有的場景測試都是**端到端**的（餵真指標 → 看卡片），
# 於是兩條規則同時生效時，任一條被拿掉另一條仍會擋下來，突變就活了下來。
# 補法：**逐條隔離** —— 每條規則各構造一組「只有它會擋、另一條不會擋」的輸入。
# ════════════════════════════════════════════════════════════════════════
def test_dominance_alone_rejects_a_verdict_one_family_could_flip():
    """只有**族群支配**這條規則擋得住的情形：一項都沒缺，但取到的太少。

    `missing_weight == 0` → 不變性檢查必然通過（可達區間退化成一個點）；
    唯一還能擋下來的是「單一相關族翻向就足以跨過一整條分界」。
    突變驗證：`_dominance_ok` 改成 `len(_got) >= 3`（數個數）→ 本條轉紅。
    """
    _sup = weighted_verdict(
        "景氣位階", score=6.5,                       # 6.5 深在 5~8 這一格中間
        obtained=("a", "b", "c", "d"), missing=(),   # 一項都沒缺 → 不變性必過
        obtained_weight=10.0, missing_weight=0.0,
        family_weights={"殖利率曲線": 4.0, "其他": 1.0},
        band_of=phase_band, scale=PHASE_SCALE,
        weight_per_band=PHASE_WEIGHT_PER_BAND)       # 需 > 5.0 × 4.0 = 20.0
    assert not _sup.sufficient, (
        "取到的權重只有 10.0，而殖利率曲線這一族就佔 4.0 —— 它翻向就跨一整格")
    assert "單一相關族" in _sup.reason and "殖利率曲線" in _sup.reason
    assert _sup.detail["required_weight"] == PHASE_WEIGHT_PER_BAND * 4.0
    # 反向：同一組輸入把權重加到門檻之上 → 立刻放行（證明擋的是權重不是別的）
    assert weighted_verdict(
        "景氣位階", score=6.5, obtained=("a", "b", "c", "d"), missing=(),
        obtained_weight=20.5, missing_weight=0.0,
        family_weights={"殖利率曲線": 4.0, "其他": 1.0},
        band_of=phase_band, scale=PHASE_SCALE,
        weight_per_band=PHASE_WEIGHT_PER_BAND).sufficient


def test_invariance_alone_rejects_a_verdict_the_missing_weight_could_move():
    """只有**區間不變性**這條規則擋得住的情形：族群支配過得了，但缺太多。

    族最大權重壓到 0.5 → `required = 2.5`，取到 5.0 已達標；
    真正擋下來的是「還有 22.0 權重沒取到，任一種實現都會跨格」。
    突變驗證：`_invariant` 改成 `len(_got) > 0`（數個數）→ 本條轉紅。
    """
    _sup = weighted_verdict(
        "景氣位階", score=5.0,
        obtained=("a",), missing=("b", "c"),
        obtained_weight=5.0, missing_weight=22.0,
        family_weights={"單項": 0.5},                # 需 > 2.5，取到 5.0 → 過
        band_of=phase_band, scale=PHASE_SCALE,
        weight_per_band=PHASE_WEIGHT_PER_BAND)
    assert not _sup.sufficient
    assert "沒取到" in _sup.reason and "不是同一個判讀" in _sup.reason
    assert "單一相關族" not in _sup.reason, (
        "族群支配這條本來就該放行（`required` 只有 2.5）—— 擋下來的必須是不變性")


def test_a_tie_between_net_margin_and_missing_count_is_not_enough():
    """`|淨邊際| == 缺的筆數` 是**邊界上**的一點：必須判「不足」（R4-F5 同型）。

    2 個 +1 對上 2 項沒取到 —— 那兩項若都是 -1，淨邊際歸零，方向翻掉。
    突變驗證：`abs(_net) > len(_miss)` 改成 `>=` → 本條轉紅。
    """
    _sup = net_margin("成長方向",
                      signals={"a": 1.0, "b": 1.0},
                      expected=("a", "b", "c", "d"))
    assert not _sup.sufficient, (
        "淨邊際 2 對上 2 項未取得 —— 那兩項全反就歸零，撐不起方向宣稱")
    # 邊界的另一側：淨邊際 3 > 缺 2 → 放行（證明擋的是那個等號，不是別的）
    assert net_margin("成長方向",
                      signals={"a": 1.0, "b": 1.0, "c": 1.0},
                      expected=("a", "b", "c", "d", "e")).sufficient


def test_a_missing_phase_score_is_never_coerced_into_a_verdict():
    """`phase_support` 拿不到分數時**不得**補一個預設值再去跑不變性檢查。

    這是 §1 的直接落地：`calc_macro_phase` 的正規化在分母為零時吐 5.0，
    那個 5.0 是**分母為零時的預設值，不是量測**。若在 support 這一層再補一次，
    就會拿一個捏造的分數去背書自己。
    突變驗證：把那個 early-return 改成 `_score = 5.0` 往下跑 → 本條轉紅。
    """
    for _bad in (None, "", "n/a", float("nan")):
        _sup = phase_support({}, _bad)
        assert not _sup.sufficient, f"score={_bad!r} 竟被判為足以支撐一個判讀"
        if _bad != _bad:          # NaN 走得到 float()，落在不變性那一支
            continue
        assert "分數未取得" in _sup.reason, (_bad, _sup.reason)
        assert "detail" not in _sup.reason
        assert _sup.detail.get("obtained_weight") == 0.0
