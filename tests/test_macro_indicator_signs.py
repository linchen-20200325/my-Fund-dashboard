"""v19.404 稽核修復回歸鎖 — 指標符號 / 官方閾值 / meta 污染 / 因子重複計數。

這批 bug 之所以能長期存活，共同原因是**沒有測試守著符號與閾值**。本檔把四件事釘死：

1. **NFP 符號**（任務 2）：非農就業月增為負 = 衰退 = 🔴 = **負分**。
   原碼 `cur_d < 0 → score = +1.5 / 🔴`、`>= 500k → score = -1.0 / 🟢`，
   是全站唯一符號相反的指標（對照同檔 `YIELD_10Y3M score = 2 if v > 0.5 else -2`
   與 `services/macro/explain.py` 的「正分 = 偏多」判讀）。
2. **`_` 前綴 meta 不得參與加權**（任務 1）：`_fred_sources` 是 provenance meta dict，
   沒有 `weight` 欄，舊碼 `.get("weight", 1)` 讓它以 w=1 / s=0 混進 `total_w` 分母，
   把所有分數系統性拉向中性 5.0。
3. **CFNAI 官方閾值**（任務 3）：-0.70 / +0.20 皆為 **CFNAI-MA3** 基準（非月度值）；
   -0.35 是 CFNAI **Diffusion Index** 的門檻，與 CFNAI 水準無關，不得混用。
   出處 https://www.chicagofed.org/-/media/publications/cfnai/background/cfnai-background-pdf.pdf
4. **M2 因子不重複計數**（任務 5）：WM2NS 週頻是 M2SL 月頻的**替代**源，不是加項。

外加一條**全指標符號一致性靜態掃描**：凡是 signal 與 score 用同一組條件寫的三元鏈，
🟢 分支的分數不得為負、🔴 分支的分數不得為正。

──────────────────────────────────────────────────────────────
v19.405（QA Reject 後補洞）— 上面第 4 項當時**只在 `calc_macro_phase` 生效**：
那條路徑內部 `s = max(-w, min(w, s))` 在 w=0 時順手把 score clamp 成 0，
剛好把 bug 蓋住；其餘三條 production 路徑寫的是 `float(v.get("weight", 1) or 1)`，
而 Python `0 or 1 == 1` —— 刻意歸零的權重被 falsy 回退**還原成 1**，去重完全失效。
另有兩條路徑（zpct 對照演算法 / ⚡ 今日關鍵橫幅）根本不讀 weight，`weight=0` 對它們
無效，改以 `superseded_by` 去重。本檔新增：
5. `TestZeroWeightAcrossAllAggregationPaths` — weight=0 在**全部**加權路徑真的等於 0
   （composite_score / cluster / tab6 明細表 + 全 repo falsy 回退漂移鎖）
6. `TestSupersededDedupOnUnweightedPaths` — 不加權路徑以 `superseded_by` 去重，
   且**遞補場景**（月頻缺漏、主源不在場）不得誤刪備源（§1）
7. `TestAggregationContracts` — `coerce_weight` / `is_superseded` 兩條契約的語意分工
另補：LEI 拐點的 `ma3` / `ma3_prev` 降級必須 all-or-nothing（§4.1 不得混基準）、
NFP tier 門檻的出處誠實標註、NFP tier 配色收 `shared/colors.py` SSOT。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_US_IND_PATH = Path(__file__).parent.parent / "services" / "macro" / "us_indicators.py"


# ══════════════════════════════════════════════════════════════
# AST 工具（沿用 test_card_threshold_drift / test_indicator_scale_consistency 慣例）
# ══════════════════════════════════════════════════════════════
def _fetch_all_fn() -> ast.FunctionDef:
    tree = ast.parse(_US_IND_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "fetch_all_indicators":
            return node
    raise AssertionError("找不到 fetch_all_indicators")


def _indicator_kwargs() -> dict[str, dict]:
    """{indicator_key: {kwarg_name: ast_node}}，只收 `R["KEY"] = dict(...)` 靜態 key。"""
    out: dict[str, dict] = {}
    for n in ast.walk(_fetch_all_fn()):
        if (isinstance(n, ast.Assign) and n.targets
                and isinstance(n.targets[0], ast.Subscript)
                and isinstance(n.targets[0].value, ast.Name)
                and n.targets[0].value.id == "R"
                and isinstance(n.value, ast.Call)):
            sl = n.targets[0].slice
            if isinstance(sl, ast.Constant):
                out[sl.value] = {k.arg: k.value for k in n.value.keywords if k.arg}
    return out


def _num(node: ast.AST):
    """數值字面值（含 -0.7 這種 UnaryOp 形式）→ float；非數值 → None。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return float(node.value)
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, (int, float))):
        return -float(node.operand.value)
    return None


def _has_falsy_weight_fallback(tree: ast.AST) -> bool:
    """AST 偵測 `<x>.get("weight", <預設>) or <任何值>` 這種 falsy 回退。

    - 用 **AST** 而非字串比對：註解／docstring 裡引述這個反例（本 PR 的修復說明
      就引了）不該被當成違規，只有真正會被執行的運算式才算。
    - 要求 `.get` 帶**第二個引數**：`d.get("weight", 1) or 1` 是「已經宣告了預設值
      卻又用 `or` 蓋掉」的自相矛盾寫法 —— 這正是 weight=0 被吃掉的形狀。
      而 `d.get("weight") or d.get("percentage")`（services/ai_service.py 的
      持股欄位候選鏈）沒有預設值，是另一種合法慣用法，不在本鎖範圍。
    """
    for n in ast.walk(tree):
        if not (isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or)):
            continue
        first = n.values[0]
        if (isinstance(first, ast.Call)
                and isinstance(first.func, ast.Attribute)
                and first.func.attr == "get"
                and len(first.args) >= 2
                and isinstance(first.args[0], ast.Constant)
                and first.args[0].value == "weight"):
            return True
    return False


def _ifexp_leaves(node: ast.AST) -> set:
    """只收三元鏈 `A if cond else B` 的 **body / orelse 葉節點**數值。

    v19.405 稽核修正（QA 建議 7）：原本用 `ast.walk` 掃整棵樹再以 `abs(v) <= 2.0`
    過濾「非門檻」，等於把 `IfExp.test` 裡的門檻常數（LEI 的 -0.7 / 0.0）也當成
    tier 分值——目前 weight=1 恰好讓 0.7 通過，若 weight 降到 0.5 就會誤報。
    改成只走 body/orelse，門檻常數（在 test 分支）永遠不會被收進來。
    """
    out: set = set()

    def _walk(n: ast.AST) -> None:
        if isinstance(n, ast.IfExp):
            _walk(n.body)
            _walk(n.orelse)
            return
        v = _num(n)
        if v is not None:
            out.add(v)

    _walk(node)
    return out


# ══════════════════════════════════════════════════════════════
# 1. NFP 符號鎖（任務 2）
# ══════════════════════════════════════════════════════════════
class TestNFPSign:
    """`_nfp_tier` 為 v19.404 從 inline 抽出的純函式，專供本組測試釘死符號。"""

    @staticmethod
    def _tier(x):
        from services.macro.us_indicators import _nfp_tier
        return _nfp_tier(x)

    def test_job_losses_are_red_and_negative(self):
        """就業淨減（衰退訊號）→ 🔴 且分數為負。這是原 bug 的正面對照。"""
        for cur_d in (-1.0, -50.0, -300.0):
            score, sig, _color = self._tier(cur_d)
            assert sig == "🔴", f"NFP {cur_d}k 應為 🔴，實際 {sig}"
            assert score < 0, (
                f"NFP {cur_d}k（就業淨減=衰退）分數必須為負，實際 {score}。"
                " 全站 sign convention：正分=偏多、負分=偏空（§4.1）。"
            )

    def test_job_growth_is_green_and_positive(self):
        """強勁就業成長 → 🟢 且分數為正。"""
        for cur_d in (250.0, 400.0, 499.9):
            score, sig, _color = self._tier(cur_d)
            assert sig == "🟢", f"NFP {cur_d}k 應為 🟢，實際 {sig}"
            assert score > 0, f"NFP {cur_d}k（就業強勁）分數必須為正，實際 {score}"

    def test_cold_tier_negative_neutral_tier_zero(self):
        assert self._tier(50.0)[0] < 0, "0–100k 偏冷 → 負分"
        assert self._tier(150.0)[0] == 0.0, "100–250k 中性 → 0 分"

    def test_overheat_capped_below_strong(self):
        """>500k 過熱：仍為正分，但因 Fed 緊縮風險不得高於「強勁」檔（倒 U）。"""
        strong = self._tier(300.0)[0]
        overheat = self._tier(900.0)[0]
        assert overheat > 0
        assert overheat < strong, "過熱檔不應比強勁檔拿更高分（Fed 緊縮風險）"

    def test_monotonic_up_to_strong_tier(self):
        """0 → 強勁檔之間分數必須單調不減（不可再出現方向翻轉）。"""
        xs = [-10.0, 50.0, 150.0, 300.0]
        scores = [self._tier(x)[0] for x in xs]
        assert scores == sorted(scores), f"NFP 分數在 {xs} 上不單調：{scores}"

    def test_magnitude_never_exceeds_weight(self):
        """|score| ≤ weight(1.0)。

        原碼衰退檔給 ±1.5 但 weight=1.0 —— `calc_macro_phase` 會 clamp、
        `services/macro/composite_score.calculate_composite_score` **不 clamp**，
        同一分數在兩條聚合路徑不等價。
        """
        for x in (-500.0, -1.0, 0.0, 99.0, 249.0, 499.0, 5000.0):
            score = self._tier(x)[0]
            assert abs(score) <= 1.0, f"NFP {x}k 分數 {score} 超出 weight=1.0"

    def test_nfp_weight_is_one(self):
        kw = _indicator_kwargs()["NFP"]
        assert _num(kw["weight"]) == 1.0, "NFP weight 應維持 1.0（與上面幅度上限對齊）"

    def test_nfp_thresholds_declare_provenance_honestly(self):
        """v19.405：三個切點必須**據實標註出處**（`shared/macro_buckets.py:23-26` 慣例）。

        同一批修復裡 CFNAI 的 -0.70 / +0.20 附了 Chicago Fed 官方逐字引文 + URL，
        NFP 這三顆卻零出處。本測試不管數值對不對（§-1 沒需求不動數值），
        只要求「有沒有誠實說明來源」：
        - 查得到官方 / 研究出處 → 標 `SSOT:<位置>` 並真的接上該常數
        - 查不到 → 標 `DESIGN`（本專案自訂，無單一官方源）
        **禁止**假造出處：標成 SSOT 就必須指得出來源模組。
        """
        from services.macro import us_indicators as ui_mod
        src = getattr(ui_mod, "_NFP_TIER_SOURCE", None)
        assert src is not None, (
            "NFP tier 門檻缺出處標註 —— 請比照 shared/macro_buckets.py 的 "
            "`SSOT:<位置>` / `DESIGN` 慣例具名宣告 `_NFP_TIER_SOURCE`"
        )
        assert src == "DESIGN" or src.startswith("SSOT:"), (
            f"出處標註格式不合慣例：{src!r}")
        if src.startswith("SSOT:"):
            # 標成 SSOT 就要真的從那個模組 import，不能只是寫個字串充數
            body = _US_IND_PATH.read_text(encoding="utf-8")
            assert src.split(":", 1)[1].strip() in body, (
                "標成 SSOT 但檔內找不到對應來源引用 = 假造出處（§3.3）")

    def test_nfp_tier_colors_come_from_ssot(self):
        """v19.405：tier 配色不得留 inline hex（§3.3 色票 SSOT `shared/colors.py`）。

        原碼「偏冷」檔寫死 `"#ff8a80"`，同函式其餘 tier 全用 MATERIAL_RED /
        MD_AMBER_300 / MD_GREEN_A200 —— 唯獨這格破口。
        """
        from shared.colors import (
            MATERIAL_RED, MD_AMBER_300, MD_GREEN_A200, MD_RED_A100,
        )
        from services.macro.us_indicators import _nfp_tier
        allowed = {MATERIAL_RED, MD_AMBER_300, MD_GREEN_A200, MD_RED_A100}
        for x in (-10.0, 50.0, 150.0, 300.0, 900.0):
            color = _nfp_tier(x)[2]
            assert color in allowed, (
                f"NFP {x}k 用了非 SSOT 色 {color!r} —— 請收進 shared/colors.py")
        assert _nfp_tier(50.0)[2] == MD_RED_A100, "「偏冷」檔應用具名的 MD_RED_A100"


# ══════════════════════════════════════════════════════════════
# 2. `_` 前綴 meta 不得污染權重分母（任務 1）
# ══════════════════════════════════════════════════════════════
class TestMetaKeyExcludedFromScoring:
    @staticmethod
    def _phase(inds):
        from services.macro.us_indicators import calc_macro_phase
        return calc_macro_phase(inds)

    def test_fred_sources_meta_does_not_change_score(self):
        """加入 `_fred_sources` meta 前後，Macro Score 必須完全相同。

        修復前：total_w 從 2 被灌水到 3 → (2+3)/(2*3)*10 = 8.3（而非 10.0），
        所有分數被系統性拉向中性 5.0。
        """
        base = {"PMI": {"value": 55, "weight": 2, "score": 2}}
        with_meta = dict(base)
        with_meta["_fred_sources"] = {
            "DGS10": {"success": True, "last_date": "2026-08-01", "rows": 2600},
            "M2SL": {"success": False, "last_date": "", "rows": 0},
        }
        r_base = self._phase(base)
        r_meta = self._phase(with_meta)
        assert r_base["score"] == pytest.approx(10.0)
        assert r_meta["score"] == pytest.approx(r_base["score"]), (
            "meta dict 混入指標容器後改變了 Macro Score → 權重分母被污染"
        )
        assert r_meta["_provenance"]["total_weight"] == pytest.approx(2.0)
        assert "_fred_sources" not in r_meta["_provenance"]["sources"]

    def test_meta_excluded_from_contributing_count(self):
        base = {"PMI": {"value": 55, "weight": 2, "score": 2, "source": "FRED:X"}}
        with_meta = dict(base)
        with_meta["_fred_sources"] = {"DGS10": {"success": True}}
        assert (self._phase(with_meta)["_provenance"]["contributing"]
                == self._phase(base)["_provenance"]["contributing"] == 1)

    def test_non_dict_value_does_not_crash(self):
        r = self._phase({"PMI": {"value": 55, "weight": 2, "score": 2}, "junk": "abc"})
        assert r["score"] == pytest.approx(10.0)

    def test_composite_provenance_does_not_invent_indicators(self):
        """v19.425：血緣側車不得把 meta 當指標報（§2.2 血緣不含虛構條目）。

        `calculate_composite_score` 的 `total` 本來就不受影響（meta 沒有 score →
        0×1=0），所以這個洞在總分上看不出來；但 `provenance_out` 會寫出
        `n_indicators` 多 1、`contributions["_fred_sources"] = {"score":0.0,
        "weight":1.0,"weighted":0.0}` —— 一個不存在的「指標」進了血緣。
        `mcp_server/tools_macro.py:63` 確實有傳 `provenance_out`，這份假血緣會被輸出。

        修正前：n_indicators=2、contributions 含 `_fred_sources`（本測試紅）。
        """
        from services.macro.composite_score import calculate_composite_score
        ind = {
            "PMI": {"value": 55, "weight": 2, "score": 2, "source": "FRED:NAPM"},
            "_fred_sources": {"DGS10": {"success": True, "rows": 2600}},
        }
        prov: dict = {}
        total = calculate_composite_score(ind, provenance_out=prov)
        assert total == pytest.approx(4.0)
        assert prov["n_indicators"] == 1, (
            f"meta 被算成一顆指標：contributions={prov['contributions']}")
        assert "_fred_sources" not in prov["contributions"]
        assert set(prov["contributions"]) == {"PMI"}

    def test_composite_total_unaffected_by_meta(self):
        """（修正前也綠）總分本來就安全 —— 明確記錄「這個洞只傷血緣不傷分數」，
        避免下一輪稽核誤以為總分曾被污染而去追不存在的數字差異。"""
        from services.macro.composite_score import calculate_composite_score
        base = {"PMI": {"value": 55, "weight": 2, "score": 2}}
        with_meta = dict(base, _fred_sources={"DGS10": {"success": True}})
        assert (calculate_composite_score(with_meta)
                == pytest.approx(calculate_composite_score(base)))

    def test_zpct_skips_meta_without_polluting_skipped_list(self):
        from services.macro.us_indicators import calc_macro_phase_zpct
        r = calc_macro_phase_zpct({"_fred_sources": {"DGS10": {"success": True}}})
        assert r["status"] == "insufficient_data"
        assert not any("_fred_sources" in s for s in r["skipped"]), (
            "meta key 不該出現在 skipped 診斷清單（會讓 audit 誤判成缺資料的指標）"
        )

    def test_only_known_meta_key_exists(self):
        """指標容器內目前只允許 `_fred_sources` 一個 meta；新增 meta 必須 `_` 前綴。"""
        keys = set(_indicator_kwargs().keys())
        underscore = {k for k in keys if k.startswith("_")}
        assert not underscore, (
            f"`R[...] = dict(...)` 形式的指標不得用 `_` 前綴：{underscore}"
        )
        src = _US_IND_PATH.read_text(encoding="utf-8")
        meta_assigns = set(re.findall(r'R\["(_[A-Za-z0-9_]+)"\]\s*=', src))
        assert meta_assigns == {"_fred_sources"}, (
            f"新增 meta key {meta_assigns - {'_fred_sources'}} 請確認已被 "
            "calc_macro_phase / _build_phase_provenance / calc_macro_phase_zpct 的 "
            "`_` 前綴過濾涵蓋，並更新本測試。"
        )


# ══════════════════════════════════════════════════════════════
# 3. CFNAI 官方閾值（任務 3）
# ══════════════════════════════════════════════════════════════
class TestCFNAIOfficialThresholds:
    def test_ssot_constants_match_chicago_fed(self):
        from shared.signal_thresholds import (
            CFNAI_MA3_EXPANSION_THRESHOLD,
            CFNAI_RECESSION_THRESHOLD,
            CFNAI_TREND_GROWTH,
        )
        # Chicago Fed CFNAI background PDF：衰退 -0.70 / 擴張 +0.20（皆 CFNAI-MA3）
        assert CFNAI_RECESSION_THRESHOLD == pytest.approx(-0.70)
        assert CFNAI_MA3_EXPANSION_THRESHOLD == pytest.approx(0.20)
        assert CFNAI_TREND_GROWTH == pytest.approx(0.0)
        # 官方是**非對稱**設計（含遲滯），不得被「順手對稱化」
        assert CFNAI_MA3_EXPANSION_THRESHOLD != -CFNAI_RECESSION_THRESHOLD

    def test_diffusion_index_threshold_not_reused_as_level_threshold(self):
        """-0.35 是 CFNAI **Diffusion Index** 的擴張門檻，不得當 CFNAI 水準門檻。"""
        from shared.macro_buckets import SPECS_BY_KEY
        from shared.signal_thresholds import (
            CFNAI_RECESSION_THRESHOLD, CFNAI_TREND_GROWTH,
        )
        spec = SPECS_BY_KEY["cfnai"]
        assert spec.yellow != pytest.approx(-0.35), (
            "-0.35 為 CFNAI Diffusion Index 門檻，與 CFNAI 水準無關（無官方依據）"
        )
        assert spec.yellow == pytest.approx(float(CFNAI_TREND_GROWTH))
        assert spec.red == pytest.approx(float(CFNAI_RECESSION_THRESHOLD))
        assert spec.direction == "low_bad" and spec.red <= spec.yellow

    def test_lei_card_judges_on_ma3_not_monthly_value(self):
        """LEI 卡的 signal / color / score 必須吃 `v_ma3`（3M 均值），不是月度 `v`。

        月度 CFNAI 波動度約為 MA3 的 √3 ≈ 1.7 倍，拿 MA3 校準的 -0.70 去砍月度值
        會製造大量假衰退訊號。
        """
        kw = _indicator_kwargs()["LEI"]
        for field in ("signal", "color", "score"):
            src = ast.unparse(kw[field])
            assert "v_ma3" in src, f"LEI {field} 未以 CFNAI-MA3 判讀：{src}"
        # 官方擴張門檻必須真的被接上（不是只留註解）
        assert "CFNAI_MA3_EXPANSION_THRESHOLD" in ast.unparse(kw["score"]), (
            "LEI score 缺官方 +0.20 擴張檔 —— 復甦期發不出「衰退結束」訊號"
        )
        assert kw.get("ma3") is not None and kw.get("ma3_prev") is not None, (
            "LEI 須輸出 ma3 / ma3_prev 欄，供 _detect_inflection 以 MA3 判拐點"
        )

    def test_lei_inline_literals_still_mirror_ssot(self):
        """inline 的 -0.7 / 0.0 是 SSOT 的字面鏡像（drift guard 要求字面值）。

        `tests/test_card_threshold_drift.py` 要求 MACRO_THRESHOLDS["LEI"] 的門檻以
        字面值出現在 `R["LEI"]` 區塊內；本測試反向釘住「字面值 == SSOT 常數」，
        兩者任一邊漂移都會被擋下。
        """
        from shared.signal_thresholds import (
            CFNAI_RECESSION_THRESHOLD, CFNAI_TREND_GROWTH,
        )
        kw = _indicator_kwargs()["LEI"]
        lits = set()
        for field in ("signal", "color", "score"):
            for m in ast.walk(kw[field]):
                nv = _num(m)
                if nv is not None:
                    lits.add(nv)
        assert float(CFNAI_RECESSION_THRESHOLD) in lits
        assert float(CFNAI_TREND_GROWTH) in lits

    def test_lei_score_magnitude_within_weight(self):
        kw = _indicator_kwargs()["LEI"]
        w = _num(kw["weight"])
        # v19.405：只取三元鏈的 body/orelse 葉節點 = 真正的 tier 分值。
        # （門檻常數 -0.7 / 0.0 寫在 IfExp.test，天生不會被收進來，
        #   不再需要 `abs(v) <= 2.0` 這種會隨 weight 變動而失準的過濾。）
        tiers = _ifexp_leaves(kw["score"])
        assert tiers, "LEI score 不是三元鏈？掃描器失效"
        assert all(abs(v) <= w for v in tiers), (
            f"LEI 分值 {sorted(tiers)} 超出 weight={w} → clamp 與否會讓兩條聚合路徑不等價"
        )

    def test_inflection_lei_fallback_is_all_or_nothing(self):
        """`ma3` / `ma3_prev` 缺一 → **整組**退回月度 value/prev，不得混基準。

        原碼兩個 fallback 各自獨立：`ma3` 有值但 `ma3_prev` 為 None
        （us_indicators.py 內 `len(_ma3_valid) < 2`，CFNAI 只夠算 1 期 MA3）時，
        lei_v = 三月均值、lei_p = 單月值 → 拿兩個不同基準比「由負轉正」（§4.1）。

        本 fixture：MA3 = +0.10（已翻正）但月度值仍 -0.30、上月 -0.60。
        - 修正前：lei_v=+0.10(MA3) vs lei_p=-0.60(月度) → 誤判「由負轉正」+3 分
        - 修正後：兩者都用月度 → -0.30 未翻正 → 0 分、無訊號
        """
        from services.macro.us_indicators import _detect_inflection
        r = _detect_inflection({
            "LEI": {"value": -0.30, "prev": -0.60, "ma3": 0.10},  # 刻意不給 ma3_prev
        })
        assert r["infl_score"] == 0, (
            f"混基準比較製造了假拐點（infl_score={r['infl_score']}）："
            f"{[s['text'] for s in r['signals']]}"
        )
        assert not any("CFNAI" in s["text"] for s in r["signals"])

    def test_inflection_lei_uses_ma3_when_both_ma3_fields_present(self):
        """正面對照：ma3 + ma3_prev 都在 → 用 MA3 判讀（不因上題退回月度）。"""
        from services.macro.us_indicators import _detect_inflection
        r = _detect_inflection({
            "LEI": {"value": 99.0, "prev": 99.0,      # 月度值刻意給無意義大數
                    "ma3": 0.10, "ma3_prev": -0.20},  # MA3 由負轉正
        })
        assert r["infl_score"] >= 3
        assert any("CFNAI-MA3" in s["text"] for s in r["signals"])

    def test_inflection_uses_ma3_and_has_expansion_exit(self):
        src = _US_IND_PATH.read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_detect_inflection")
        body = ast.unparse(fn)
        assert '"ma3"' in body or "'ma3'" in body, "_detect_inflection 應改吃 CFNAI-MA3"
        assert "CFNAI_MA3_EXPANSION_THRESHOLD" in body, (
            "_detect_inflection 缺官方 +0.20 擴張門檻 → 無「衰退警報解除」拐點"
        )


# ══════════════════════════════════════════════════════════════
# 4. M2 因子不重複計數（任務 5）
# ══════════════════════════════════════════════════════════════
class TestM2NotDoubleCounted:
    def test_weekly_weight_is_conditional_not_constant(self):
        """M2_WEEKLY 的 weight 必須是條件式（月頻命中→0），不可再寫死 1。"""
        kw = _indicator_kwargs()["M2_WEEKLY"]
        w_node = kw["weight"]
        assert _num(w_node) is None, (
            "M2_WEEKLY weight 寫死常數 = 與月頻 M2 重複計數（同一經濟因子計兩次）"
        )
        w_src = ast.unparse(w_node)
        assert "0" in w_src, f"M2_WEEKLY weight 應在月頻命中時降為 0，實際：{w_src}"
        assert kw.get("superseded_by") is not None, (
            "M2_WEEKLY 須以 superseded_by 揭露實際採用哪一個源（§2.2 provenance）"
        )

    def test_is_scored_stays_deleted(self):
        """v19.425：`is_scored` 已刪 —— 不得復活（§2.1 SSOT / §8.1 step 6）。

        原本 M2 / M2_WEEKLY 都輸出 `is_scored`，但：
        - 全 repo **0 production reader**（只有本測試檔在斷言它「不是 None」，
          等於測試自己養活自己）；
        - 值恆等於 `superseded_by is None`，是同一個事實的第二份編碼 ——
          兩欄併存必然漂移（有人只改一邊，讀哪一邊的人得到相反結論）。
        真正的揭露管道有兩條、都有真 reader：機器可讀 `superseded_by`
        （composite_score 加權/投票兩條路徑 + daily_key_alerts），
        人可讀 `desc` 尾綴（「本格僅供顯示、不計入加權分」直接顯示在卡片上）。
        """
        kws = _indicator_kwargs()
        offenders = sorted(k for k, v in kws.items() if "is_scored" in v)
        assert not offenders, (
            f"`is_scored` 在 {offenders} 復活了 —— 這是 0 reader 的死欄位，"
            "且與 `superseded_by` 同義。要揭露請接既有的兩條管道，"
            "不要再開第三份編碼。"
        )

    def test_zero_weight_substitute_contributes_nothing(self):
        """weight=0 的替代源不得進入分子或分母。"""
        from services.macro.us_indicators import calc_macro_phase
        only_monthly = {"M2": {"value": 5.5, "weight": 1, "score": 1}}
        with_weekly = dict(only_monthly)
        # 週頻方向相反（線上實測 Z 反向）：若被計入，分數會被稀釋
        with_weekly["M2_WEEKLY"] = {"value": 5.75, "weight": 0, "score": -1}
        assert (calc_macro_phase(with_weekly)["score"]
                == pytest.approx(calc_macro_phase(only_monthly)["score"]))
        assert calc_macro_phase(with_weekly)["_provenance"]["total_weight"] \
            == pytest.approx(1.0)


# ══════════════════════════════════════════════════════════════
# 4b. weight=0 必須在**所有 production 聚合路徑**都真的等於 0（v19.405）
# ══════════════════════════════════════════════════════════════
# v19.404 只有 `calc_macro_phase` 這一條是對的 —— 它內部 `s = max(-w, min(w, s))`
# 在 w=0 時把 score clamp 成 0，剛好把 bug 蓋掉。其餘三條 production 路徑寫的是
#     float(v.get("weight", 1) or 1)
# 而 Python `0 or 1 == 1`：**刻意歸零的權重被 falsy 回退還原成 1**，
# M2_WEEKLY 以全額權重回到分子分母，去重完全失效。
#
# production 入口（非理論風險）：
#   ui/tab1_macro.py:962            → calculate_composite_score(ind)
#   services/realtime_signal.py:77  → calculate_composite_score
#   services/realtime_signal.py:80  → compute_cluster_signals
#   mcp_server/tools_macro.py:63    → calculate_composite_score
#   ui/tab6_manual.py               → 「完整 23 項指標加扣分明細」表排序
def _m2_pair(with_substitute: bool) -> dict:
    """月頻 M2（主源，偏多）+ 週頻 M2_WEEKLY（已被取代，方向相反）。"""
    ind = {"M2": {"value": 5.5, "weight": 1, "score": 1,
                  "name": "M2 貨幣供給 (YoY)"}}
    if with_substitute:
        ind["M2_WEEKLY"] = {"value": 5.75, "weight": 0, "score": -1,
                            "name": "M2 週頻 (YoY)",
                            "superseded_by": "M2"}
    return ind


class TestZeroWeightAcrossAllAggregationPaths:
    def test_composite_score_ignores_zero_weight(self):
        """路徑 1／3：`calculate_composite_score`（宏觀健康度總分）。

        修正前 `float(v.get("weight", 1) or 1)` → wf=1 → total = 1 + (-1) = 0，
        與只有月頻時的 1.0 差一整分（健康度總分直接被抵銷掉）。
        """
        from services.macro.composite_score import calculate_composite_score
        assert (calculate_composite_score(_m2_pair(True))
                == pytest.approx(calculate_composite_score(_m2_pair(False))))

    def test_composite_provenance_reports_zero_weight(self):
        """血緣側車也不能謊報權重（修正前會寫成 weight=1.0 / weighted=-1.0）。"""
        from services.macro.composite_score import calculate_composite_score
        prov: dict = {}
        calculate_composite_score(_m2_pair(True), provenance_out=prov)
        c = prov["contributions"]["M2_WEEKLY"]
        assert c["weight"] == pytest.approx(0.0)
        assert c["weighted"] == pytest.approx(0.0)

    def test_cluster_liquidity_not_double_counted(self):
        """路徑 2／3：`compute_cluster_signals` 的「💧 貨幣寬鬆」cluster。

        修正前 w 被還原成 1 → clamp 後 s=-1 → sum_w=2 / sum_ws=0 → norm 0.0（🟡），
        與只有月頻時的 norm 1.0（🟢）不同 —— 同一因子雙算後互相抵銷。
        """
        from services.macro import compute_cluster_signals

        def _liq(ind):
            return next(c for c in compute_cluster_signals(ind)
                        if c["name"] == "貨幣寬鬆")

        base, dup = _liq(_m2_pair(False)), _liq(_m2_pair(True))
        assert dup["score_norm"] == pytest.approx(base["score_norm"])
        assert dup["signal"] == base["signal"], (
            f"雙算讓流動性燈號從 {base['signal']} 變成 {dup['signal']}"
        )

    def test_no_falsy_weight_fallback_anywhere_in_repo(self):
        """路徑 3／3 + 全域漂移鎖：`.get("weight", ...) or 1` 一律禁止。

        `ui/tab6_manual.py` 的貢獻明細表是 inline UI 程式碼（需 streamlit runtime
        才跑得起來），用靜態掃描鎖住；順帶把整個 repo 一起掃，避免同一個 falsy
        回退在別處復活。

        **已知待辦（不在本次所有權內）**：`ui/helpers/macro/helpers.py:109`
        `category_score` —— production **0 caller**（全 repo 只剩 docstring／
        BACKLOG 提及），屬死碼，本次不改，列為顯式例外。若哪天它被修好或刪掉，
        本測試會要求同步更新這份清單。
        """
        repo = _US_IND_PATH.resolve().parent.parent.parent
        hits = set()
        for p in repo.rglob("*.py"):
            rel = p.relative_to(repo).as_posix()
            if rel.startswith((".venv/", "venv/", "env/", "tests/",
                               "build/", ".git/", "site-packages/")):
                continue
            try:
                tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue          # 非本 repo 語法（第三方樣板等）→ 不管
            if _has_falsy_weight_fallback(tree):
                hits.add(rel)
        assert hits == {"ui/helpers/macro/helpers.py"}, (
            "weight 的 falsy 回退（Python `0 or 1 == 1`）會把刻意歸零的權重還原成 1，"
            "同因子去重當場失效。請改用 "
            "`services.macro.composite_score.coerce_weight`。\n"
            f"  目前命中：{sorted(hits)}\n"
            "  預期只剩已登記的死碼例外 ui/helpers/macro/helpers.py"
        )


# ══════════════════════════════════════════════════════════════
# 4c. 不吃 weight 的路徑改用 `superseded_by` 去重（v19.405）
# ══════════════════════════════════════════════════════════════
# `calc_macro_phase_zpct`（F-RECON-1 對照演算法）與「⚡ 今日關鍵橫幅」都**不讀
# weight** —— 前者是不加權的 Φ(z) 算術平均（不加權才與主路徑正交），後者的觸發
# 條件只看 score。所以 v19.404 的 `weight=0` 對這兩條完全沒效果，M2 / M2_WEEKLY
# 仍雙算 / 雙報。改讀生產端已輸出的去重事實 `superseded_by`。
class TestSupersededDedupOnUnweightedPaths:
    @staticmethod
    def _series(vals):
        import pandas as pd
        return pd.Series(
            vals, index=pd.date_range("2015-01-01", periods=len(vals), freq="ME"))

    def _zpct_pair(self, with_substitute: bool, superseded: bool = True) -> dict:
        # 60+ 期才會被 zpct 採用；兩者刻意反向（M2 低於均值、M2_WEEKLY 高於均值）
        hist = [float(x) for x in range(1, 81)]      # mean=40.5
        ind = {"M2": {"value": 20.0, "series": self._series(hist),
                      "weight": 1, "score": 1}}
        if with_substitute:
            sub = {"value": 70.0, "series": self._series(hist),
                   "weight": 0, "score": -1}
            if superseded:
                sub["superseded_by"] = "M2"
            ind["M2_WEEKLY"] = sub
        return ind

    def test_zpct_skips_superseded_substitute(self):
        """修正前：兩格都進 sub_pcts（各 1/n）且方向相反 → 訊號互相抵銷。"""
        from services.macro.us_indicators import calc_macro_phase_zpct
        base = calc_macro_phase_zpct(self._zpct_pair(False))
        dup = calc_macro_phase_zpct(self._zpct_pair(True))
        assert base["contributing"] == 1
        assert dup["contributing"] == 1, (
            f"備源仍進了對照演算法：sub_pcts={dup['sub_pcts']}")
        assert "M2_WEEKLY" not in dup["sub_pcts"]
        assert dup["score"] == pytest.approx(base["score"])
        assert any("M2_WEEKLY:superseded_by=M2" in s for s in dup["skipped"]), (
            "跳過原因必須寫進 skipped 診斷清單（§1 不靜默丟資料）"
        )

    def test_zpct_keeps_substitute_when_not_superseded(self):
        """月頻缺漏 → 生產端不標 superseded_by → 週頻要照常遞補計分。

        這是「不用靜態 key 名單」的理由：supersede 是執行期條件，
        寫死 `{"M2_WEEKLY"}` 會連遞補場景一起砍掉 = §1 把僅有的資料丟掉。
        """
        from services.macro.us_indicators import calc_macro_phase_zpct
        r = calc_macro_phase_zpct(self._zpct_pair(True, superseded=False))
        assert r["contributing"] == 2
        assert "M2_WEEKLY" in r["sub_pcts"]

    def test_zpct_keeps_substitute_when_primary_absent(self):
        """`superseded_by` 指向的主源不在場（舊 cache / fixture）→ 不得丟掉備源。"""
        from services.macro.us_indicators import calc_macro_phase_zpct
        ind = self._zpct_pair(True)
        ind.pop("M2")
        r = calc_macro_phase_zpct(ind)
        assert r["contributing"] == 1 and "M2_WEEKLY" in r["sub_pcts"]

    def test_key_alerts_does_not_double_report_same_factor(self):
        """⚡ 今日關鍵橫幅：同一經濟因子不得冒兩條警示。

        修正前：M2_WEEKLY 的 score=-1 ≤ -SIGMA_HIGH_CUTOFF(0.8) → **紅級**成立
        （觸發只看 score，與 weight 無關），只是 _rank=|-1×0|=0 被排到同級最後。
        使用者會看到「M2 貨幣供給緊縮」+「M2 週頻緊縮」兩條，誤以為兩個獨立訊號。
        """
        from services.macro.daily_key_alerts import collect_key_alerts
        ind = {
            "M2": {"name": "M2 貨幣供給 (YoY)", "value": -0.5, "unit": "%",
                   "score": -1, "weight": 1},
            "M2_WEEKLY": {"name": "M2 週頻 (YoY)", "value": -0.4, "unit": "%",
                          "score": -1, "weight": 0, "superseded_by": "M2"},
        }
        out = collect_key_alerts(ind, None)
        assert len(out["items"]) == 1, (
            f"同因子雙報：{[i['text'] for i in out['items']]}")
        assert out["items"][0]["text"].startswith("M2 貨幣供給")

    def test_key_alerts_keeps_substitute_when_promoted(self):
        """月頻缺漏（無 superseded_by）→ 週頻遞補，橫幅照常顯示。"""
        from services.macro.daily_key_alerts import collect_key_alerts
        out = collect_key_alerts(
            {"M2_WEEKLY": {"name": "M2 週頻 (YoY)", "value": -0.4, "unit": "%",
                           "score": -1, "weight": 1}}, None)
        assert len(out["items"]) == 1


# ══════════════════════════════════════════════════════════════
# 4c-2. `reconcile_composite_score` — 不吃 weight 的**第三條**路徑（v19.425）
# ══════════════════════════════════════════════════════════════
# v19.405 的設計文件（composite_score.py 頂部契約）寫「不吃 weight 的路徑改用
# `superseded_by` 去重」，並補到了 `calc_macro_phase_zpct` 與 `collect_key_alerts`。
# 但 `reconcile_composite_score` 同樣**只看 score 正負號**、完全不讀 weight，
# 卻兩道守衛都沒有：
#   (1) M2(+1) 與 M2_WEEKLY(-1) 各投一票互相抵銷 → 該因子淨貢獻從 +1 變 0；
#   (2) `_fred_sources` 是 dict 但無 `score` 鍵 → `sf=0` → n_zero += 1 →
#       meta 被灌進 n_valid 分母（= v19.404 在 calc_macro_phase 修過的同一個病）。
# production reader（會直接呈現給 user，不是死碼）：
#   ui/tab1_macro.py:981（綜合健康度卡下方 ✅/⚠️ 對帳 chip）
#   mcp_server/tools_macro.py:72（MCP snapshot 的 reconciliation 欄）
class TestReconcileDedupAndMetaGuards:
    @staticmethod
    def _recon(ind):
        from services.macro.composite_score import reconcile_composite_score
        return reconcile_composite_score(ind)

    def test_superseded_substitute_does_not_cancel_primary_vote(self):
        """核心紅燈：M2(+1) / M2_WEEKLY(−1, superseded_by=M2) 的雙算。

        修正前：n_pos=1, n_neg=1, n_valid=2 → net_ratio = 0.0（因子淨貢獻 0）
        修正後：n_pos=1, n_neg=0, n_valid=1 → net_ratio = +1.0（淨貢獻 +1）
        """
        r = self._recon(_m2_pair(True))
        assert (r["n_pos"], r["n_neg"], r["n_zero"]) == (1, 0, 0), (
            f"備源仍投了票：{r}")
        assert r["vote_net_ratio"] == pytest.approx(1.0)
        # 與「只有月頻」完全等價 —— 備源在不加權投票裡必須是隱形的
        base = self._recon(_m2_pair(False))
        assert r["vote_net_ratio"] == pytest.approx(base["vote_net_ratio"])
        assert r["dir_vote"] == base["dir_vote"]

    def test_dedup_flips_vote_direction_across_neutral_band(self):
        """雙算足以在 `COMPOSITE_VOTE_NEUTRAL_BAND` 邊界翻掉方向判定。

        這條證明上一題不只是「數字差一點」——`dir_vote` 是 `status`
        （agree / neutral_mix / disagree）的兩個輸入之一，直接決定 tab1
        對帳 chip 顯示 ✅ 還是 ⚠️ 還是不顯示。
        修正前：n_pos=1, n_neg=1, n_zero=2 → net=0.0 → dir_vote='neu'
        修正後：n_pos=1, n_neg=0, n_zero=2 → net=1/3≈0.333 > 0.2 → dir_vote='pos'

        （只斷言 `dir_vote` / `vote_net_ratio`，不斷言 `status` —— `status` 另一半
        輸入 `dir_weighted` 走 `get_verdict_cutoffs()`，會被 active.json 覆蓋，
        不該讓回歸測試依賴使用者的校準檔。）
        """
        from shared.signal_thresholds import COMPOSITE_VOTE_NEUTRAL_BAND as _BAND
        n_fill = 2
        assert (1.0 / (1 + n_fill)) > _BAND, (
            f"fixture 需重新設計：去重後 net_ratio={1 / (1 + n_fill):.3f} "
            f"沒有越過中性帶 {_BAND}，本測試證明不了方向翻轉"
        )
        ind = _m2_pair(True)
        for i in range(n_fill):
            ind[f"FILLER_{i}"] = {"score": 0, "weight": 1}
        r = self._recon(ind)
        assert r["n_zero"] == n_fill
        assert r["vote_net_ratio"] == pytest.approx(1.0 / (1 + n_fill))
        assert r["dir_vote"] == "pos", (
            f"去重後方向仍是 {r['dir_vote']}（修正前為 'neu'）：{r}")

    def test_substitute_skip_reason_is_recorded(self):
        """§1 不靜默丟資料：跳過原因要寫進 `skipped`（對齊 zpct 路徑的慣例）。"""
        r = self._recon(_m2_pair(True))
        assert any("M2_WEEKLY:superseded_by=M2" in s for s in r["skipped"]), r

    def test_meta_key_does_not_inflate_denominator(self):
        """`_fred_sources` 不得被當成一顆 score=0 的指標計入 n_zero / n_valid。

        修正前：n_pos=1, n_zero=1 → n_valid=2 → net = 0.5
        修正後：n_pos=1, n_zero=0 → n_valid=1 → net = 1.0
        """
        base = {"PMI": {"value": 55, "weight": 2, "score": 2}}
        with_meta = dict(base)
        with_meta["_fred_sources"] = {
            "DGS10": {"success": True, "last_date": "2026-08-01", "rows": 2600},
            "M2SL": {"success": False, "last_date": "", "rows": 0},
        }
        r_meta, r_base = self._recon(with_meta), self._recon(base)
        assert r_meta["n_zero"] == 0, f"meta 被當成 score=0 的指標：{r_meta}"
        assert r_meta["vote_net_ratio"] == pytest.approx(1.0)
        assert r_meta["vote_net_ratio"] == pytest.approx(r_base["vote_net_ratio"])
        assert not any("_fred_sources" in s for s in r_meta["skipped"]), (
            "meta 不是指標，不該出現在 skipped 診斷清單（會讓 audit 誤判成缺資料）")

    def test_substitute_still_votes_when_not_superseded(self):
        """反向護欄（修正前也綠）：月頻缺漏 → 無 `superseded_by` → 週頻照常投票。

        `superseded_by` 是**執行期**條件，不是靜態 key 名單；過度去重 = §1 把
        僅有的一筆資料丟掉。這條與下一條確保修正沒有矯枉過正。
        """
        ind = {"M2_WEEKLY": {"value": -0.4, "weight": 1, "score": -1}}
        r = self._recon(ind)
        assert (r["n_pos"], r["n_neg"]) == (0, 1)
        assert r["vote_net_ratio"] == pytest.approx(-1.0)

    def test_substitute_still_votes_when_primary_absent(self):
        """反向護欄（修正前也綠）：`superseded_by` 指向的主源不在場（舊 cache）→ 不得丟掉備源。"""
        ind = _m2_pair(True)
        ind.pop("M2")
        r = self._recon(ind)
        assert (r["n_pos"], r["n_neg"]) == (0, 1), r
        assert not r["skipped"]

    def test_no_data_path_keeps_contract(self):
        """全 meta / 空 dict → status='no_data'，且不得偽造 net_ratio（§1）。"""
        r = self._recon({"_fred_sources": {"DGS10": {"success": True}}})
        assert r["status"] == "no_data"
        assert r["vote_net_ratio"] is None
        assert r["n_pos"] == r["n_neg"] == r["n_zero"] == 0

    def test_reader_contract_keys_present(self):
        """production reader 讀的欄位不得消失（修正前也綠 —— 這是防我自己改壞）。

        ui/tab1_macro.py:982-988 讀 status / note / n_pos / n_neg / vote_net_ratio；
        mcp_server/tools_macro.py:85 把整份 dict 放進 `reconciliation`。
        """
        r = self._recon(_m2_pair(True))
        for k in ("weighted_total", "vote_net_ratio", "n_pos", "n_neg", "n_zero",
                  "dir_weighted", "dir_vote", "status", "note", "skipped"):
            assert k in r, f"對帳 dict 缺欄位 {k}"
        assert isinstance(r["skipped"], list)   # MCP 要 JSON-safe


# ══════════════════════════════════════════════════════════════
# 4d. `superseded_by` / `weight` 兩條契約的語意分工（v19.405）
# ══════════════════════════════════════════════════════════════
class TestAggregationContracts:
    def test_coerce_weight_preserves_zero(self):
        from services.macro.composite_score import coerce_weight
        assert coerce_weight(0) == pytest.approx(0.0)
        assert coerce_weight(0.0) == pytest.approx(0.0)
        assert coerce_weight(None) == pytest.approx(1.0)      # 真的沒填才回退
        assert coerce_weight(2) == pytest.approx(2.0)

    def test_is_meta_key_is_the_single_definition(self):
        """v19.425：`_` 前綴 meta 述詞收 SSOT。

        原本這道守衛被**各自 inline** 在 `calc_macro_phase` / `calc_macro_phase_zpct`，
        而 `calculate_composite_score` / `reconcile_composite_score` 兩條完全沒有 ——
        「同一條契約 4 個 aggregator、2 個漏寫」正是這輪漏網的成因。
        """
        from services.macro.composite_score import is_meta_key
        assert is_meta_key("_fred_sources") is True
        assert is_meta_key("_") is True
        assert is_meta_key("M2") is False
        assert is_meta_key("M2_WEEKLY") is False, "底線在字中不算 meta"
        assert is_meta_key(123) is False          # 非 str key 不炸

    def test_all_aggregators_share_the_meta_predicate(self):
        """漂移鎖：5 條聚合／血緣路徑不得再各自 inline `startswith("_")`。

        （修正前會紅：`us_indicators.py` 當時有 4 處 inline，`composite_score.py`
        兩條路徑則完全沒有守衛。）
        """
        import inspect
        from services.macro import composite_score as cs_mod
        from services.macro import us_indicators as ui_mod
        offenders = []
        for mod, fns in ((cs_mod, ("calculate_composite_score",
                                   "reconcile_composite_score")),
                         (ui_mod, ("calc_macro_phase", "calc_macro_phase_zpct",
                                   "_build_phase_provenance"))):
            for fn in fns:
                src = inspect.getsource(getattr(mod, fn))
                # 去掉註解行後再比對（說明文字引述反例不算違規）
                code = "\n".join(ln for ln in src.splitlines()
                                 if not ln.lstrip().startswith("#"))
                if 'startswith("_")' in code or "startswith('_')" in code:
                    offenders.append(f"{mod.__name__}.{fn}")
                if "is_meta_key" not in code and "_is_meta_key" not in code:
                    offenders.append(f"{mod.__name__}.{fn}（沒接上述詞）")
        assert not offenders, (
            "meta 守衛未收 SSOT（services.macro.composite_score.is_meta_key）："
            f"{offenders}"
        )

    def test_is_superseded_requires_primary_present(self):
        from services.macro.composite_score import is_superseded
        sub = {"superseded_by": "M2"}
        assert is_superseded(sub, {"M2": {"score": 1}, "M2_WEEKLY": sub}) == "M2"
        assert is_superseded(sub, {"M2_WEEKLY": sub}) is None   # 主源不在 → 不丟
        assert is_superseded({"superseded_by": None}) is None
        assert is_superseded({}) is None
        assert is_superseded("not-a-dict") is None

    def test_producer_emits_both_channels(self):
        """生產端 R["M2_WEEKLY"] 必須同時輸出 weight 與 superseded_by 兩條契約。"""
        kw = _indicator_kwargs()["M2_WEEKLY"]
        assert _num(kw["weight"]) is None, "weight 必須是條件式"
        assert kw.get("superseded_by") is not None


# ══════════════════════════════════════════════════════════════
# 5. 全指標符號一致性靜態掃描（任務 2 延伸）
# ══════════════════════════════════════════════════════════════
_GREEN, _RED = "🟢", "🔴"


def _sign_pairs(sig: ast.AST, sc: ast.AST, key: str, out: list) -> None:
    """遞迴比對 signal / score 兩條**條件相同**的三元鏈，收集 (emoji, 分數) 葉節點。

    條件不同就停止（例如 DXY / PPI / SLOOS 的黃紅界本來就寫在不同門檻上），
    避免誤報；能比對的部分才斷言符號。
    """
    while isinstance(sig, ast.IfExp) and isinstance(sc, ast.IfExp):
        if ast.dump(sig.test) != ast.dump(sc.test):
            return
        _leaf(sig.body, sc.body, key, out)
        sig, sc = sig.orelse, sc.orelse
    _leaf(sig, sc, key, out)


def _leaf(sig: ast.AST, sc: ast.AST, key: str, out: list) -> None:
    if isinstance(sig, ast.Constant) and sig.value in (_GREEN, _RED):
        v = _num(sc)
        if v is not None:
            out.append((key, sig.value, v))


def test_green_never_negative_red_never_positive():
    """🟢 分支不得給負分、🔴 分支不得給正分 —— 這就是 NFP 原 bug 的型別。"""
    problems = []
    checked = 0
    for key, kw in _indicator_kwargs().items():
        if "signal" not in kw or "score" not in kw:
            continue
        pairs: list = []
        _sign_pairs(kw["signal"], kw["score"], key, pairs)
        for k, emoji, val in pairs:
            checked += 1
            if emoji == _GREEN and val < 0:
                problems.append(f"{k}: 🟢 卻給負分 {val}")
            if emoji == _RED and val > 0:
                problems.append(f"{k}: 🔴 卻給正分 {val}")
    assert not problems, (
        "指標燈號與分數符號相反（全站慣例：正分=偏多 / 負分=偏空，§4.1）：\n  "
        + "\n  ".join(problems)
    )
    assert checked >= 20, (
        f"符號掃描只比對到 {checked} 組葉節點，掃描器可能失效（預期 ≥ 20）"
    )
