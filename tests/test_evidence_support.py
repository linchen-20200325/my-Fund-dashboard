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
    # ⚠️ 2026-09-04 第五輪：~~`assert MACRO_PHASE_MIN_TOTAL_WEIGHT == ...`~~
    # **已移除**（有意識的更正，不是漏刪）：那個常數是被第四輪改動製造出來的
    # 孤兒（production 0 caller，只剩測試在引用），本輪依 GC 收尾義務實體刪除，
    # 它的「最壞情況值」現在是下面兩項的**計算結果**，不再是第二份真相。
    assert PHASE_WEIGHT_PER_BAND * MAX_CORRELATED_FAMILY_WEIGHT == 20.0
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
    `_T >= 20.0`（舊式定值門檻）→ 轉紅。
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


# ════════════════════════════════════════════════════════════════════════
# 2026-09-04 **第五輪**獨立稽核
#
# F1（🔴）`weighted_verdict` 對「顯示端會四捨五入」這件事沒有建模，於是它宣告
#         「充足」的判讀，缺一顆指標就能翻掉。契約寫得是絕對的
#         （「沒取到的那些證據，不論實際是什麼值，都不會改變它」），
#         而消費端只讀 `.sufficient` —— 看不出它其實是近似的。
# F2（🔴）產出端認證過的 🔴 被整句灰掉（不對稱反了）。
# F4（🟠）規則本身有測試，**接線沒有** —— 兩個 call-site 突變全綠。
# F5（🟠）`summed_verdict` 的 swing 大小沒有守衛。
# ════════════════════════════════════════════════════════════════════════
_ALL_W = MACRO_INDICATOR_SCORING_WEIGHTS


def _ind_from(scores: dict) -> dict:
    """`{key: score}` → `calc_macro_phase` 吃得下的 indicators dict。"""
    return {_k: dict(value=1.0, weight=_ALL_W[_k], score=_s)
            for _k, _s in scores.items()}


def _flip_extremes(scores: dict, missing) -> list:
    """把 `missing` 補到兩個極端（全負 / 全正），回傳兩個 `calc_macro_phase` 結果。

    分數對缺項貢獻是**單調**的，所以這兩個端點界住了每一種實現。
    """
    _out = []
    for _sign in (-1.0, +1.0):
        _alt = dict(scores)
        for _k in missing:
            _alt[_k] = _sign * _ALL_W[_k]
        _out.append(calc_macro_phase(_ind_from(_alt)))
    return _out


def test_a_sufficient_phase_verdict_cannot_be_flipped_by_one_missing_indicator():
    """**F1 的最小可達實例**：28 項只缺 `UNEMPLOYMENT`（權重 0.5）一項。

    修復前（實測，`a88f896`）：
        displayed 4.9 復甦｜support sufficient=True｜reachable 4.81～4.99
        該項若取到 +0.5 → 5.0 擴張
        「復甦期：最高勝率買點！逐步加碼」→「股優於債：核心高股息ETF…」
    兩個誤差源疊在 5.0 這條帶邊界上：傳進來的 `score` 已經 round 過（±0.05），
    每一種實現也會再 round 一次（±0.05）。
    突變驗證：拿掉 `round_to=` **或** 拿掉 `score_tolerance=` → 本條轉紅。
    """
    _scores = {_k: 0.0 for _k in _ALL_W if _k != "UNEMPLOYMENT"}
    _scores["PMI"] = -0.4                      # 把分數推到剛好在 5.0 邊界下方
    _base = calc_macro_phase(_ind_from(_scores))
    assert (_base["score"], _base["phase"]) == (4.9, "復甦"), _base["score"]

    _lo, _hi = _flip_extremes(_scores, ["UNEMPLOYMENT"])
    assert _hi["phase"] != _base["phase"], (
        "前提不成立：這個狀態其實翻不掉，換一組（不要 skip）")
    assert not _base["support"].sufficient, (
        f"缺一項就能把「{_base['phase']}」翻成「{_hi['phase']}」，卻宣告證據充足 —— "
        f"reachable {_base['support'].detail['reachable_low']}～"
        f"{_base['support'].detail['reachable_high']}")


def test_no_sufficient_phase_verdict_anywhere_is_flippable():
    """**F1 的量化版**：掃一片狀態空間，`sufficient=True` 的**一個都不准**翻得掉。

    這一條與上一條的差別：上一條釘住一個已知實例（會被「只修那一格」的
    突變騙過），本條是**窮舉性質**的 —— 它問的是「還有沒有第二個」。
    修復前實測：14728 個狀態中 7646 個 sufficient，其中 **286 個可翻**（3.74%）。
    修復後：**0**。
    突變驗證：拿掉 `round_to=` → 轉紅；拿掉 `score_tolerance=` → 轉紅。
    """
    import itertools
    import random
    _rng = random.Random(20260904)
    _special = {"SAHM": (-1.5, 0.0, 1.5), "SLOOS": (-1.5, 0.0, 1.5)}

    def _domain(_k):
        return _special.get(_k, (-_ALL_W[_k], 0.0, _ALL_W[_k]))

    _keys = list(_ALL_W)
    _bad, _n_suff = [], 0
    # 缺 1～2 項的全部組合（單元測試要跑得快；缺 3 項的版本在 PR 描述裡跑過）
    for _miss in (s for r in (1, 2) for s in itertools.combinations(_keys, r)):
        _got = [_k for _k in _keys if _k not in _miss]
        _scores = {_k: _rng.choice(_domain(_k)) for _k in _got}
        _base = calc_macro_phase(_ind_from(_scores))
        if not _base["support"].sufficient:
            continue
        _n_suff += 1
        for _alt in _flip_extremes(_scores, _miss):
            if _alt["phase"] != _base["phase"]:
                _bad.append((list(_miss), _base["score"], _base["phase"],
                             _alt["score"], _alt["phase"]))
                break
    assert _n_suff > 100, f"前提：樣本裡要有夠多的 sufficient 狀態才測得到（{_n_suff}）"
    assert not _bad, (
        f"{len(_bad)} / {_n_suff} 個「充足」的判讀可以被缺項翻掉，例如：{_bad[:3]}")


def test_the_low_side_flip_that_producer_rounding_alone_does_not_catch():
    """**F1 的第二個誤差源**：只把兩個界照生產端 round 一次，**還不夠**。

    稽核給的低側實例（本組實測重現，`missing=['NEW_HOME','SLOOS']`）：
        displayed 3.2 復甦｜缺項全負 → **2.9 衰退**｜缺項全正 → 3.7 復甦
    只加 `round_to=`（不加 `score_tolerance=`）時 `reachable_low` 算出**恰好 3.0**
    → 判「充足」。真值卻可以低到 3.15×r，round 後是 2.9 —— 差的那一格
    正是「傳進來的 `score` 本身已經被 round 過」帶來的半格誤差。
    突變驗證：拿掉 `score_tolerance=` → 本條轉紅（`round_to=` 仍在也擋不住）。
    """
    _scores = {"PMI": -2.0, "LEI": -1.0, "NFP": 1.0, "PERMIT_HOUSING": -0.5,
               "CONSUMER_CONF": -0.5, "CPI": 0.5, "PPI": -0.5,
               "INFL_EXP_5Y": -1.0, "JOBLESS": -0.5, "CONT_CLAIMS": -0.5,
               "SAHM": -1.5, "M2_WEEKLY": -1.0, "FED_RATE": -0.5,
               "YIELD_10Y3M": -2.0, "COPPER": 0.5, "EURUSD": -1.0,
               "USDCNH": 1.0}
    _scores.update({_k: 0.0 for _k in _ALL_W
                    if _k not in _scores and _k not in ("NEW_HOME", "SLOOS")})
    _base = calc_macro_phase(_ind_from(_scores))
    assert (_base["score"], _base["phase"]) == (3.2, "復甦"), _base["score"]
    _lo, _hi = _flip_extremes(_scores, ["NEW_HOME", "SLOOS"])
    assert (_lo["score"], _lo["phase"]) == (2.9, "衰退"), (
        f"前提不成立（換一組，不要 skip）：{_lo['score']} {_lo['phase']}")
    assert not _base["support"].sufficient, (
        "低側翻掉（3.2 復甦 → 2.9 衰退）卻宣告證據充足 —— "
        "只 round 兩個界、沒有把輸入自己的 round 誤差加寬回去")


def test_the_producer_wiring_declares_both_rounding_error_sources():
    """接線守衛：`phase_support` 必須把**兩個**誤差源都宣告給規則。

    ⚠️ ~~**據實說明本條為什麼是結構性而不是行為性的**：本組用約 4.9 萬個抽樣
    狀態去找「只拿掉 `round_to=` 就會漏掉的翻轉」，**沒有找到** …
    所以用結構守衛釘住它不會悄悄消失。**沒找到反例 ≠ 不存在**。~~
    → **2026-09-04 第六輪稽核 B1 推翻，有意識的更正，不是漏刪。**
    **兩個參數都是承重的（行為性的），不是只有結構守衛。**
    ⚠️ 「上一輪為什麼沒找到」本組**沒有**上一輪的產生器，下面是**本組自己的**
    重現經過，不是對上一輪的斷言：本組第一次寫的產生器同樣把 earned 直接對準
    每一格顯示值的**正中央**，結果 holes 一律是 0；把**格內偏移**
    （±0.02 / ±0.049）加進去之後，稽核給的那個反例當場重現 ——
    也就是 `round_to=` 專屬的洞住在**格內的邊緣**，掃格點正中央結構上看不到。
        缺 `PMI` 一項、顯示 `2.4 衰退`、拿掉 `round_to=` → 契約說「充足」，
        而真的生產端把 `PMI` 補成 `+2.0` 時顯示 **`3.0 復甦`** —— 翻帶。
    量化（本組 2026-09-04 實測，缺 1～2 項全組合 × 每格 5 個格內偏移）：
        兩個都在      → holes **0** / 0
        只拿掉 round_to        → holes **40**（缺 1 項）／**577**（缺 2 項）
        只拿掉 score_tolerance → holes **84**（缺 1 項）／**1078**（缺 2 項）
    行為守衛見 `test_dropping_the_display_rounding_alone_opens_a_real_hole`。
    本條保留為**接線**守衛（兩個參數有沒有真的被傳下去），不再宣稱
    「`round_to=` 只有結構意義」。
    """
    from services.macro.evidence import (
        PHASE_SCORE_DECIMALS, PHASE_SCORE_ROUNDING_TOLERANCE,
    )
    _ind = _ind_from({_k: 0.0 for _k in _ALL_W if _k != "UNEMPLOYMENT"})
    _d = calc_macro_phase(_ind)["support"].detail
    assert _d["round_to"] == PHASE_SCORE_DECIMALS, (
        f"接線沒有把顯示端的四捨五入位數傳給規則：{_d['round_to']!r}")
    assert _d["score_tolerance"] == PHASE_SCORE_ROUNDING_TOLERANCE > 0, (
        f"接線沒有把「輸入本身已被 round」的誤差傳給規則：{_d['score_tolerance']!r}")


def test_the_phase_rounding_matches_the_producer():
    """漂移鎖：`PHASE_SCORE_DECIMALS` ≡ 生產端 `round(..., N)` 的那個 N。

    這兩個數字分岔 = F1 又回來了（區間會用錯的格點去 round）。
    **AST 讀生產端的字面值**，不是字串搜尋。
    突變驗證：把 `calc_macro_phase` 的 `round(..., 1)` 改成 `round(..., 2)` → 轉紅。
    """
    from services.macro.evidence import (
        PHASE_SCORE_DECIMALS, PHASE_SCORE_ROUNDING_TOLERANCE,
    )
    _fn = [n for n in ast.walk(ast.parse(_US_IND.read_text(encoding="utf-8")))
           if isinstance(n, ast.FunctionDef) and n.name == "calc_macro_phase"][0]
    # ⚠️ 只鎖**指派給 `score` 的那一個** round —— 同一個函式裡另有一處
    # `round(1 / (1 + exp(-logit)) * 100, 1)`（衰退機率），與本鎖無關。
    _rounds = [_n.value for _n in ast.walk(_fn)
               if isinstance(_n, ast.Assign)
               and any(isinstance(_t, ast.Name) and _t.id == "score"
                       for _t in _n.targets)
               and isinstance(_n.value, ast.Call)
               and isinstance(_n.value.func, ast.Name)
               and _n.value.func.id == "round"]
    assert len(_rounds) == 1, (
        f"`score = round(...)` 不是恰好一處，漂移鎖失焦："
        f"{[ast.unparse(r) for r in _rounds]}")
    assert isinstance(_rounds[0].args[1], ast.Constant), ast.unparse(_rounds[0])
    assert _rounds[0].args[1].value == PHASE_SCORE_DECIMALS, (
        f"生產端 round 到 {_rounds[0].args[1].value} 位，證據會計以為是 "
        f"{PHASE_SCORE_DECIMALS} 位")
    # 容差由位數導出，不寫死
    assert PHASE_SCORE_ROUNDING_TOLERANCE == 0.5 * (10.0 ** -PHASE_SCORE_DECIMALS)


def test_the_rounding_parameters_default_to_off():
    """沒有 round 的生產端不該被迫宣告一個它沒有的誤差（兩個參數預設關閉）。"""
    _kw = dict(obtained=("a",), missing=(), obtained_weight=10.0,
               missing_weight=0.0, family_weights={"a": 1.0},
               band_of=lambda s: "hi" if s >= 5 else "lo",
               scale=10.0, weight_per_band=2.0)
    _off = weighted_verdict("x", score=4.999, **_kw)
    _on = weighted_verdict("x", score=4.999, round_to=1,
                           score_tolerance=0.05, **_kw)
    assert _off.detail["reachable_low"] == _off.detail["reachable_high"] == 5.0
    assert _off.detail["round_to"] is None and _off.detail["score_tolerance"] == 0.0
    # 開了之後：4.999 會被 round 成 5.0，而 band 是拿**原始 score** 算的 → 不同帶
    assert _on.detail["round_to"] == 1


# ── F4（🟠）規則有測試、接線沒有 —— 兩個 call-site 突變全綠 ─────────────
def test_the_wiring_passes_the_real_family_weights_not_an_empty_dict():
    """**F4 / 突變 M24**：`phase_support` 必須把**真的**族權重餵進規則。

    `family_weights` 若恆為空 dict，`weighted_verdict` 的支配性條件（規則 B）
    就整條短路成 `True`（它把空 dict 讀成「一個指標都沒取到」）。
    實測：M24 單獨施加 → `308 passed, 32 skipped`，**全綠**。
    本條直接驗接線的產出：族權重必須逐項等於「在場成員的權重合計」。
    突變驗證：把 `phase_support` 的 `family_weights=` 改成 `{}` → 轉紅。
    """
    _ind = _ind_from({"YIELD_10Y2Y": 2.0, "YIELD_10Y3M": 2.0, "PMI": 2.0})
    _fam = phase_support(_ind, calc_macro_phase(_ind)["score"]).detail
    assert _fam["max_family_weight"] == 4.0, (
        "族權重沒有被餵進規則（殖利率曲線 2+2 = 4）："
        f"{_fam['max_family_weight']}")
    assert _fam["required_weight"] == PHASE_WEIGHT_PER_BAND * 4.0


def test_the_wiring_makes_a_dominant_family_grey_through_the_real_producer():
    """**F4 / M24 的行為面**：一族就能決定判讀時，走真的生產端也必須灰掉。

    M24 之所以全綠，是因為支配性只有兩條**直接呼叫 `weighted_verdict`** 的
    單元測試在守；經由 `calc_macro_phase` 的那條路**沒有任何測試**。
    """
    # 殖利率一族（4.0）+ 幾顆小的：權重過得了不變性，但一族就能推過一整條帶
    _ind = _ind_from({"YIELD_10Y2Y": 2.0, "YIELD_10Y3M": 2.0,
                      "HY_SPREAD": 2.0, "PMI": 2.0, "VIX": 1.0,
                      "M2": 1.0, "FED_BS": 1.0, "ADL": 1.0})
    _sup = calc_macro_phase(_ind)["support"]
    assert _sup.detail["obtained_weight"] < _sup.detail["required_weight"]
    assert not _sup.sufficient, "單一相關族就能決定的判讀，竟被判為充足"
    assert "相關族" in _sup.reason, _sup.reason


def test_the_wiring_passes_the_real_missing_weight_not_zero():
    """**F4 / 突變 M25**：`phase_support` 必須把**真的**缺漏權重餵進規則。

    `missing_weight` 若恆為 0，區間不變性整條退化成「恆成立」——
    完全斷線也會宣告充足。實測：M25 單獨施加 → `308 passed, 32 skipped`，**全綠**；
    M24+M25 一起施加 → 一個會畫出 9.5「高峰」的狀態拿到 `sufficient=True`。
    """
    _ind = _ind_from({"PMI": 2.0, "HY_SPREAD": 2.0})
    _sup = calc_macro_phase(_ind)["support"]
    _expect = sum(_w for _k, _w in _ALL_W.items() if _k not in _ind)
    assert _sup.detail["missing_weight"] == _expect > 0, (
        f"缺漏權重沒有被餵進規則：{_sup.detail['missing_weight']} != {_expect}")
    assert not _sup.sufficient
    # M24+M25 一起：這個狀態會畫出 9.5「高峰」，兩個突變都在時它會被放行
    assert calc_macro_phase(_ind)["score"] == 10.0


# ── F5（🟠）`summed_verdict` 的 swing 大小沒有守衛 ─────────────────────
def test_the_composite_swing_is_the_full_possible_contribution_of_what_is_missing():
    """**F5 / 突變 M14**：swing 必須是「缺項可能貢獻的**全部**」，不是它的一半。

    實測：`M14 swing 減半 → 308 passed, 32 skipped`，**全綠**；而 swing 減半
    正好讓第三輪的 blocker（`fillna(0)` 等價的 0.0 分被畫成「🟡 中性／分批進場」）
    重新亮起來。
    本條兩段：(1) 數值上 swing ≡ Σ(權重 × 單顆分數上界)；
    (2) 行為上，把 swing 減半會讓一個該灰的狀態變成不該地「充足」。
    """
    from services.macro.evidence import composite_support
    _ind = _ind_from({"PMI": 2.0, "HY_SPREAD": -2.0})     # 兩項相抵 → 總分 0.0
    _prov: dict = {}
    calculate_composite_score(_ind, provenance_out=_prov)
    _sup = _prov["support"]
    _expect = sum(_ALL_W[_k] * MACRO_INDICATOR_MAX_ABS_SCORE
                  for _k in _ALL_W if _k not in _ind)
    assert _sup.detail["missing_swing"] == _expect > 0, (
        f"swing 不是「缺項可能貢獻的全部」：{_sup.detail['missing_swing']} != {_expect}")
    assert not _sup.sufficient, "0.0 分（缺值被當成 0 加進去）竟被判為足以下結論"

    # 行為面：拿**真的** `composite_verdict` 當帶函式，挑一個總分落在
    # 「半個 swing 內安全、整個 swing 內就跨帶」的位置（cutoff 5.0，總分 5.7）：
    #   full swing 1.0 → [4.7, 6.7] 橫跨「中性」/「樂觀」 → 不充足（正確）
    #   half swing 0.5 → [5.2, 6.2] 同帶            → 充足（**放行了不該放行的**）
    _band = lambda _t: composite_verdict(_t)[1]      # noqa: E731
    _kw = dict(total=5.7, obtained=("a",), missing=("b",), band_of=_band)
    _full = summed_verdict("x", missing_swing=1.0, **_kw)
    _half = summed_verdict("x", missing_swing=0.5, **_kw)
    assert not _full.sufficient and _half.sufficient, (
        "swing 減半對判定毫無影響 —— 那表示 swing 的大小根本沒有被用到："
        f"full={_full.sufficient} half={_half.sufficient}")
    assert composite_support is not None      # 引用一下，避免 lint 誤判未使用


# ── 第七輪稽核：`summed_verdict` 三點同帶的**上端**那一半沒有行為守衛 ──────
def test_only_the_high_end_of_the_composite_interval_can_flip_this_verdict():
    """**第七輪稽核**：`summed_verdict` 三點同帶裡的**上端**那一半，全套零守衛。

    實測（第七輪，`84ebc2f`）：把
        `_ok = (band_of(_lo) == _band == band_of(_hi))`
    砍成 `_ok = (band_of(_lo) == _band)` → **7114 passed, 45 skipped**，全綠。

    那個突變**不是惰性的**：走真正的入口 `calculate_composite_score(...,
    provenance_out=…)` 掃三萬多個綜合健康度狀態，有 **1121** 個**只在上端**翻帶
    —— 砍掉上端那一半，就會讓這 1121 個狀態重新宣告一個「沒取到的那幾項若真的
    取到，就會被推到另一條帶」的定論（第 2 輪起每一輪都是同一類缺陷）。

    本條是那一類的**最小可達實例**，而且**走生產端**、不手搭 `EvidenceSupport`
    —— 本批的歷史正是「手搭 fixture 剛好蓋住這一類」，前幾輪的缺陷因此活到稽核。

    **構造全部從真實 cutoff 推出來，不寫死任何一個數字**：28 項只缺
    `UNEMPLOYMENT`（權重 0.5 ⇒ swing = 0.5 × 2 = 1.0），總分放在 `c2 − swing/2`：
        · 低端 `c2 − 1.5×swing` → 仍在「中性」⇒ **低端那一半放行**
        · 高端 `c2 + 0.5×swing` → 「樂觀」   ⇒ **只有上端那一半攔得下來**

    ⚠️ **對稱的那一半（低端）已經有守衛**，是同檔的
    `test_the_composite_swing_is_the_full_possible_contribution_of_what_is_missing`
    —— 它的 `_full` 是 total=5.7 / swing=1.0（低端 4.7 落回「中性」、高端 6.7
    仍是「樂觀」），剛好只有低端攔得住。⚠️ 但那一條是**手搭的直呼**
    （直接叫 `summed_verdict(...)`、自己指定 total），**沒有走生產端** ——
    據實記在這裡，不在本輪擴充。
    兩條互為鏡像，缺任一邊就有半個可及區間沒人看。
    突變驗證：砍上端 → **本條**轉紅；砍低端 → **那一條**轉紅。
    """
    from services.macro.weights_store import get_verdict_cutoffs

    _band = lambda _t: composite_verdict(_t)[1]      # noqa: E731
    _omit = "UNEMPLOYMENT"
    _swing = _ALL_W[_omit] * MACRO_INDICATOR_MAX_ABS_SCORE
    _c2 = get_verdict_cutoffs()[1]                   # 「樂觀」切點
    # 目標總分：距「樂觀」切點不到一個 swing（上端跨得過去），
    # 但距「中性」下緣還有一個 swing 以上（下端跨不過去）。
    _target = _c2 - _swing / 2.0

    _scores = {_k: 0.0 for _k in _ALL_W if _k != _omit}
    _scores["PMI"] = MACRO_INDICATOR_MAX_ABS_SCORE           # 頂到宣告的 |score| 上界
    _scores["CPI"] = ((_target - MACRO_INDICATOR_MAX_ABS_SCORE * _ALL_W["PMI"])
                      / _ALL_W["CPI"])                       # 其餘補到 `_target`
    assert abs(_scores["CPI"]) <= MACRO_INDICATOR_MAX_ABS_SCORE, (
        "構造超出生產端宣告的 |score| 上界 —— 這個狀態生產端到不了，換一組")

    _prov: dict = {}
    _total = calculate_composite_score(_ind_from(_scores), provenance_out=_prov)
    _sup = _prov["support"]

    # ── 前提：不成立就大聲失敗，不要靜默地為了錯的理由而通過 ──────────────
    assert _total == pytest.approx(_target), (_total, _target)
    assert _sup.rule == "summed_verdict", (
        f"這個狀態走的不是規則 2-c（rule={_sup.rule}）—— 若落進警報帶就會走"
        " `witnessed` 豁免，那就測不到本條要測的東西")
    assert _sup.detail["missing_swing"] == _swing, _sup.detail
    assert _band(_total - _swing) == _band(_total), (
        "前提不成立：低端已經翻帶了，那低端那一半也攔得住 —— 換一組（不要 skip）")
    assert _band(_total + _swing) != _band(_total), (
        "前提不成立：高端沒翻帶，這個狀態本來就充足 —— 換一組（不要 skip）")

    # ── 本體：這個狀態**只有**上端那一半攔得住 ────────────────────────────
    assert not _sup.sufficient, (
        f"總分 {_total:+.2f}「{_band(_total)}」被判為足以下結論，但沒取到的"
        f" {_omit} 若真的取到，總分可及 {_total + _swing:+.2f}"
        f"「{_band(_total + _swing)}」—— 三點同帶的**上端**那一半失效了")


# ── `witnessed()` 的空證人契約（第五輪點名：public L0 API，零覆蓋）──────
def test_witnessed_with_no_witnesses_is_not_an_alarm():
    """`witnesses` 為空 ⇒ 沒有任何觀測作證 ⇒ **不是警報**，是無話可說。

    實測（第五輪）：`M12 witnessed 恆充足 → 308 passed`，**全綠** ——
    這條 public L0 API 的空證人分支在本 repo 裡零覆蓋。
    目前 production 走不到它（`composite_support` 只在 alarm band 呼叫，
    而 alarm band 必有觀測），但它是 public API，**契約要有守衛**。
    """
    _empty = witnessed("誰都沒越線", witnesses=())
    assert not _empty.sufficient
    assert _empty.reason and "不是警報" in _empty.reason
    assert witnessed("有人越線", witnesses=("VIX",)).sufficient


# ── F3（🟠）記錄下來的理由是錯的：那個不對稱是**政策**，不是後設規則的推論 ──
def test_the_composite_alarm_carve_out_is_not_implied_by_monotonicity():
    """把「這個豁免不是推導」變成一條**可被檢查的事實**，不是只改註解。

    `witnessed(claim, witnesses=_got)` 收到的是**全部取到的 key**，不是
    「越線的那幾個」；而宣稱是「**加總跨過切點**」—— 對證據**不單調**。
    實測（第五輪稽核，本組重現）：28 項只取到 2 項、總分 −8.0 → 「悲觀」警訊、
    `sufficient=True`；若 28 項全部取到且**每顆都給生產端宣告的上界** `score=+weight`，
    總分是 **+35.0 極度樂觀**。
    ⚠️ 稽核報告寫的是 +19.0；本組**沒有重現出那個數字**（+19.0 應該來自另一種
    「最大正向」的定義，例如逐顆用它自己 tier 表裡的最大值而不是 `weight`）。
    **結論不受影響**（兩者都遠在警訊帶之外），但據實標明數字是本組自己量的。
    也就是**這面紅旗確實可能被沒取到的資料翻掉** —— 它照放是因為
    「寧可多報一次警」，不是因為它證明了不會被翻掉。

    ⚠️ 本條的用途是**擋掉一次未來的化簡**：若有人以為「不對稱會從後設規則自己
    掉出來」而把 `alarm_bands` 這個參數拿掉，那個化簡是不安全的。
    突變驗證：把 `alarm_bands=COMPOSITE_ALARM_LEVELS` 改成 `()` → 既有兩條
    「警訊不得被灰掉」轉紅（本條則證明**為什麼**那兩條不能靠推導取代）。
    """
    _two = {"PMI": {"value": 38.0, "weight": 2, "score": -2},
            "HY_SPREAD": {"value": 9.0, "weight": 2, "score": -2}}
    _prov: dict = {}
    _total = calculate_composite_score(_two, provenance_out=_prov)
    assert _total == -8.0, _total
    assert composite_verdict(_total)[1] in COMPOSITE_ALARM_LEVELS
    assert _prov["support"].sufficient, "前提：警訊照放（政策豁免）"
    assert _prov["support"].rule == "witnessed"
    # 那些「證人」其實只是**取到的 key**，不是越線的那幾個 —— 這正是不單調的來源
    assert set(_prov["support"].detail["witnesses"]) == set(_two)

    # 而且它**真的**會被翻掉：全部取到、全部最大正向 → 極度樂觀
    _all_max = {_k: {"value": 1.0, "weight": _w, "score": _w}
                for _k, _w in _ALL_W.items()}
    _flipped = calculate_composite_score(_all_max)
    assert _flipped == 35.0, _flipped
    assert composite_verdict(_flipped)[1] not in COMPOSITE_ALARM_LEVELS, (
        "前提不成立：那就沒有『可能被翻掉』這回事了（換一組，不要 skip）")


# ════════════════════════════════════════════════════════════════════════
# 2026-09-04 **第六輪**獨立稽核
#
# F-A1（🔴 回歸，本批自己造成的）`weighted_verdict` 的可及區間**上界多了一格**：
#      F1 把 `[score-0.05, score+0.05]` 兩個端點都 round，但**恰好等於**
#      `score+0.05` 的真值自己會顯示成 `score+0.1` —— 它不在這個顯示值的原像裡。
#      於是 28 項全取到（沒有任何缺項可言）的健康日，一部分分數被灰掉：
#          28 obtained, 0 missing → scores declared INSUFFICIENT: [4.9, 7.9]
#          ①結論「⬜ 這次的資料撐不起任何結論」／卡 1、卡 5「⬜ 資料不足」
#          去處還寫「按『🔄 更新總經資料』重新載入」—— 但根本沒有東西可以補。
#      **而且它隨浮點表示而異**：`2.9` 沒事、`4.9` 中招（見下方測試）。
#      同一個邏輯情境兩種結果 ⇒ 界算錯了，不是「保守了一點」。
# B1  「只拿掉 `round_to=` 找不到反例」的說法被稽核推翻 —— 兩個參數都是承重的。
# ════════════════════════════════════════════════════════════════════════
_PHASE_TICKS = [round(_i / 10.0, 1) for _i in range(0, 101)]


def _all_28_at(score_target: float) -> dict:
    """28 顆全取到、合成顯示分數 ≈ `score_target` 的 indicators dict。"""
    _tw = sum(_ALL_W.values())
    _earned, _sc = (score_target / 10.0 * 2 - 1) * _tw, {}
    _rem = _earned
    for _k in _ALL_W:
        _v = max(-_ALL_W[_k], min(_ALL_W[_k], _rem))
        _sc[_k] = _v
        _rem -= _v
    return _ind_from(_sc)


@pytest.mark.parametrize("score", _PHASE_TICKS)
def test_nothing_missing_means_the_reachable_display_set_is_exactly_the_score(score):
    """**F-A1 的可證版本**：`missing_weight == 0` ⇒ 可及顯示值集合 ≡ `{score}`。

    這是**斷言不是抽樣**：沒有任何缺項貢獻時，可及的**真值**就是這個顯示值
    自己的原像 `[score-tol, score+tol)`，而那個集合依定義每一點都 round 回
    `score`。所以 `reachable_low == reachable_high == score`，而且**恆充足**。

    修復前（`fb770b4` 實測）：`4.9` 與 `7.9` 兩格 `sufficient=False`，
    reason 逐字寫「還有 **0** 權重沒取到（**0** 項）」——
    一句字面上自相矛盾的話，配一個做不到的去處（沒有東西可以重新載入）。
    突變驗證（**逐一實跑過，不是推測**）：拿掉 `weighted_verdict` 裡
    `_M <= 0 < _T` 那條短路 → 本條 44 個參數轉紅；用 `fb770b4` 的契約全檔跑 → 同樣轉紅。
    """
    _sup = weighted_verdict(
        "t", score=score, obtained=list(_ALL_W), missing=[],
        obtained_weight=sum(_ALL_W.values()), missing_weight=0.0,
        family_weights={"f": 1.0}, band_of=phase_band, scale=PHASE_SCALE,
        weight_per_band=PHASE_WEIGHT_PER_BAND,
        round_to=1, score_tolerance=0.05)
    assert (_sup.detail["reachable_low"], _sup.detail["reachable_high"]) == (score, score), (
        f"沒有任何缺項，可及顯示值卻不是單點 {{{score}}}："
        f"{_sup.detail['reachable_low']}～{_sup.detail['reachable_high']}")
    assert _sup.sufficient, f"score={score}：0 項缺漏卻宣告證據不足 —— {_sup.reason}"


def test_the_float_representation_must_not_decide_who_gets_greyed():
    """**F-A1 的浮點不對稱**：`2.9` 型與 `4.9` 型必須有同一個結果。

    `round(2.9 + 0.05, 1) == 2.9`（float 2.9499999999999997）
    `round(4.9 + 0.05, 1) == 5.0`（float 4.95000000000000017…）
    舊實作把兩個端點一視同仁地 round，於是**同一個邏輯情境**在 `2.9` 上放行、
    在 `4.9` 上灰掉。本條把兩型都釘住，日後任何「只修一型」的改法都會被抓到。
    突變驗證（**逐一實跑過**）：把 `_display_max_below` 的本體改回 `round()`
    → 本條轉紅；用 `fb770b4` 的契約跑 → 轉紅（那份契約裡根本沒有這個函式）。
    ⚠️ **拿掉 `_M <= 0 < _T` 短路本條不會轉紅** —— 它直接驗上界那個 helper，
    而短路是另一半（可證性）。**兩半各有各的守衛，不要拿一條去替另一條背書。**
    """
    import shared.evidence_support as _es
    _survivors = [_s for _s in _PHASE_TICKS
                  if round(_s + 0.05, 1) == _s]          # 「2.9 型」
    _victims = [_s for _s in _PHASE_TICKS
                if round(_s + 0.05, 1) != _s]            # 「4.9 型」
    assert 2.9 in _survivors and 3.9 in _survivors, "前提變了：2.9/3.9 不再是倖存型"
    assert 4.9 in _victims and 6.4 in _victims, "前提變了：4.9/6.4 不再是中招型"
    # 契約層：兩型的上界都必須是它自己（不可及的那一點不算進來）
    for _s in (2.9, 3.9, 4.9, 6.4, 7.9):
        assert _es._display_max_below(_s + 0.05, 1) == _s, (
            f"{_s}+0.05 的**開**上界被算成 {_es._display_max_below(_s + 0.05, 1)}，"
            f"而恰好等於 {_s + 0.05:.2f} 的真值會顯示成 {round(_s + 0.05, 1)}，"
            f"不在 {_s} 的原像裡")


def test_a_fully_obtained_day_is_never_greyed_by_the_rounding_widening():
    """**F-A1 的行為版**：走**真的生產端**，28 顆全取到時沒有一格會灰。

    這是使用者實際會撞到的那條路：`calc_macro_phase` → `support` → ①結論／卡 1／卡 5。
    修復前實測（`fb770b4`）：`28 obtained, 0 missing` 之下 `4.9` 與 `7.9` 兩格
    `sufficient=False`，①結論退成「⬜ 這次的資料撐不起任何結論」。
    突變驗證（**逐一實跑過**）：用 `fb770b4` 的契約跑 → 本條轉紅。
    ⚠️ **兩個單獨的突變（只拿掉短路／只拿掉開區間上界）本條都不會轉紅** ——
    因為那兩半在這條路徑上互相遮蔽（上界修好之後低側就碰不到帶邊界）。
    據實寫出來：本條守的是**兩半合起來的結果**，逐半的守衛在上面兩條。
    """
    _greyed = []
    for _t in _PHASE_TICKS:
        _ph = calc_macro_phase(_all_28_at(_t))
        if not _ph["support"].sufficient:
            _greyed.append((_ph["score"], _ph["support"].reason))
    assert not _greyed, (
        f"28 顆全取到（沒取到的權重 = 0）卻有 {len(_greyed)} 格被判證據不足："
        f"{_greyed[:3]}")


def test_the_reachable_upper_bound_is_half_open_not_closed():
    """**F-A1 的通則**：上界是**開的** —— 恰好等於上界的真值不在原像裡。

    `missing_weight > 0` 時同樣成立，只是不像 `missing_weight == 0` 那樣可以
    整段短路。這裡直接構造一個上界**恰好落在進位分界上**的狀態：
        T = 10.1、M = 0.1、score+tol = 4.9 ⇒ 可及上界 = 4.95（開）
    閉區間讀法會把它 round 成 `5.0` 而跨過相位帶邊界 → 誤判「不足」；
    開區間讀法給 `4.9`，與下界同帶 → 充足。
    突變驗證：把 `_display_max_below(_hi, round_to)` 改回 `round(_hi, round_to)`
    → 本條轉紅。
    """
    _sup = weighted_verdict(
        "t", score=4.85, obtained=["a"], missing=["b"],
        obtained_weight=10.1, missing_weight=0.1,
        family_weights={"a": 1.0}, band_of=phase_band, scale=PHASE_SCALE,
        weight_per_band=PHASE_WEIGHT_PER_BAND,
        round_to=1, score_tolerance=0.05)
    assert _sup.detail["reachable_high"] == 4.9, (
        f"可及上界被算成 {_sup.detail['reachable_high']} —— 真值必須**嚴格小於** "
        f"4.95，而 4.95 本身會顯示成 5.0，不在 4.9 的原像裡")
    assert _sup.sufficient, _sup.reason


#: **B1 的具體反例**（2026-09-04 第六輪稽核給的那一個，本組重現並抽成常數）：
#: 28 顆缺 `PMI` 一項，其餘如下 → 顯示 `2.4 衰退`。
#: 只拿掉 `round_to=` 時契約會說「充足」，而把 `PMI` 補成 `+2.0` 的**真實**實現
#: 顯示 `3.0 復甦` —— 跨帶。上一輪的產生器只掃格點正中央，掃不到這個格內狀態。
_B1_ROUND_TO_HOLE_SCORES: dict = {
    "LEI": -1.0, "NFP": -1.0, "PERMIT_HOUSING": -0.5, "NEW_HOME": -0.5,
    "CONSUMER_CONF": -0.5, "CPI": -0.5, "PPI": -0.5, "INFL_EXP_5Y": -1.0,
    "UNEMPLOYMENT": -0.5, "JOBLESS": -0.5, "CONT_CLAIMS": -0.5, "SAHM": -1.5,
    "M2": -1.0, "M2_WEEKLY": -1.0, "FED_BS": -1.0, "FED_RATE": -0.5,
    "SLOOS": -1.364,
}


def _b1_hole_indicators() -> dict:
    _sc = {_k: _B1_ROUND_TO_HOLE_SCORES.get(_k, 0.0)
           for _k in _ALL_W if _k != "PMI"}
    return _ind_from(_sc)


def test_dropping_the_display_rounding_alone_opens_a_real_hole():
    """**B1**：`round_to=` 是**行為性**的，不是只有結構意義（推翻上一輪的說法）。

    這一條同時釘住兩件事：
      1. **現行實作把這個狀態判為不足**（正確）——「缺 PMI、顯示 2.4 衰退」，
         而 `PMI = +2.0` 的實現顯示 `3.0 復甦`。
      2. **把 `round_to=` 拿掉就會放行它** —— 用 monkeypatch 直接示範，
         所以這條測試在「有人為了簡化而刪掉那個參數」時會轉紅，
         而不是只有在「參數名被改掉」時轉紅。
    突變驗證：`_scored_verdict_support` 拿掉 `round_to=` → 本條轉紅。
    """
    _ind = _b1_hole_indicators()
    _base = calc_macro_phase(_ind)
    assert (_base["score"], _base["phase"]) == (2.4, "衰退"), (
        f"前提不成立（換一組，不要 skip）：{_base['score']} {_base['phase']}")
    _flip = dict(_B1_ROUND_TO_HOLE_SCORES)
    _flip["PMI"] = _ALL_W["PMI"]
    _alt = calc_macro_phase(_ind_from({_k: _flip.get(_k, 0.0) for _k in _ALL_W}))
    assert (_alt["score"], _alt["phase"]) == (3.0, "復甦"), (
        f"前提不成立：補上 PMI 之後應該跨帶，實得 {_alt['score']} {_alt['phase']}")
    assert not _base["support"].sufficient, (
        "缺 PMI 就能把「衰退」翻成「復甦」，契約卻說證據充足")


def test_both_rounding_parameters_are_load_bearing_not_just_one(monkeypatch):
    """**B1 的兩個方向**：任一參數被拿掉，上面那個狀態都會被錯放行。

    `score_tolerance=` 早就有行為守衛
    （`test_the_low_side_flip_that_producer_rounding_alone_does_not_catch`）；
    本條補上 `round_to=` 缺席的那一半，並把**兩者**放在同一條裡，
    讓「只保住一個」的改法也會轉紅。
    """
    import services.macro.evidence as _ev
    import shared.evidence_support as _es
    _orig = _es.weighted_verdict
    for _drop in ("round_to", "score_tolerance"):
        def _patched(_claim, __drop=_drop, **_kw):
            _kw[__drop] = None if __drop == "round_to" else 0.0
            return _orig(_claim, **_kw)
        monkeypatch.setattr(_ev, "weighted_verdict", _patched)
        _sup = calc_macro_phase(_b1_hole_indicators())["support"]
        assert _sup.sufficient, (
            f"前提不成立：拿掉 `{_drop}=` 之後這個狀態應該被**錯誤地**放行，"
            f"若它本來就被擋住，本條就證明不了那個參數是承重的（reason={_sup.reason}）")
        monkeypatch.undo()
