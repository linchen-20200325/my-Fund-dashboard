# -*- coding: utf-8 -*-
"""BL-0542 G1-①：ALO 配置核心黃金檔的**突變測試** —— 證明黃金檔真的咬得到（不是空掃）。

做法：讀工作樹**當下**的 `ui_v2/alo/logic.py`（或 `services/v2_domain/holdings.py`）原始碼，做一處記憶體內字串替換
（舊字串必須**剛好出現一次**，否則當場紅燈 —— 目標消失或變成兩處都要有人看），把改壞的模組 exec 進隔離命名空間
（不寫檔、不進 `sys.modules`），以 `tests/_alo_core_golden.py` 的**同一份**情境矩陣重跑，結果必須**不同於**黃金檔。

✅ G1-②（最小 PORT）已完成：`basis_value_with_key`／`_category_values` 的數值與缺值判定本體搬到
   `services/v2_domain/holdings.py::basis_value_with_reason`／`category_values`，原本鎖在 `ui_v2/alo/logic.py` 的突變目標
   已**跟著搬到新位置**（每一筆仍剛好比對一次、仍被黃金檔抓到，偵測力不減）；仍留在 `logic.py` 的（薄包裝、中文字面、
   ALO-2 以後的下游）原地不動。另新增 M37 起針對新程式碼（缺值代碼對照、結構式過期判定、累加順序、資料類互換……）的突變。

對照組（`test_對照組_未突變的載入器重現黃金檔`）：用同一個載入器載入**未改**的原始碼，結果必須等於黃金檔 —— 證明
「突變體不同於黃金檔」是突變造成的，不是載入方式造成的。

## 倖存突變（等價或矩陣打不到；**不為了殺它而硬湊斷言**）

見模組常數 `SURVIVORS_DOCUMENTED`（含理由）。其餘每一筆都由 `test_突變被黃金檔抓到` 逐筆斷言「結果不同」。
"""

from __future__ import annotations

import json
import pathlib
import types

import pytest

import _alo_core_golden as G
from _py_baseline_guard import baseline_python_only   # BL-0342／BL-0453：黃金檔基準是 CPython 3.11，非基準版本 skip／CI fail

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_GOLDEN = _ROOT / "tests" / "fixtures" / "alo_core_golden_before.json"

_LOGIC = "ui_v2/alo/logic.py"
_HOLD = "services/v2_domain/holdings.py"

_DATED = 'NAV_NOT_READY_DATED_TEXT = "⬜ 資料未備：最近一筆淨值 {day}，已超過 {days} 日"'

# (編號, 檔案, 舊字串（剛好一次）, 新字串, 說明)
MUTATIONS = [
    ("M01_cost_returns_cost_orig_ccy", _HOLD, 'return float(holding["cost_twd"]), None, None',
     'return float(holding["cost_orig_ccy"]), None, None', "成本基準回原幣成本"),
    ("M02_usd_not_multiplied_by_fx", _HOLD, "return value * rate, None, None", "return value, None, None", "非新臺幣不乘匯率"),
    ("M03_fx_obs_date_lt", _HOLD, 'r["obs_date"] <= nav_date', 'r["obs_date"] < nav_date', "匯率對齊 <= 改 <"),
    ("M04_twd_not_shortcut", _HOLD, '    if nav["ccy"] == "TWD":\n        return value, None, None\n',
     '    if False:\n        return value, None, None\n', "新臺幣也走換匯路徑"),
    ("M05_missing_summed_as_zero", _HOLD, "slot[0], slot[1], slot[3] = None, reason, kind\n",
     "slot[0], slot[1], slot[3] = 0.0, reason, kind\n", "缺值當 0.0 記進類別"),
    ("M06_missing_not_counted", _HOLD, "slot[0], slot[1], slot[3] = None, reason, kind\n",
     "slot[0], slot[1], slot[3] = None, reason, kind\n            slot[2] -= 1\n", "缺值的持倉不計入件數"),
    ("M07_last_reason_wins", _HOLD, "        if slot[1] is not None:\n            if is_stale",
     "        if slot[1] is not None and value is not None:\n            if is_stale", "第一種理由定案 → 最後一種理由定案"),
    ("M08_stale_sentence_loses_date", _LOGIC, _DATED,
     'NAV_NOT_READY_DATED_TEXT = "⬜ 資料未備：最近一筆淨值，已超過 {days} 日"', "過期句子不帶日期"),
    ("M09_stale_merge_keeps_first_date_only", _HOLD,
     "stale[cat] = StaleMerge(stale[cat].entries + ((code, reason.stale_day),), reason.stale_days)",
     "stale[cat] = stale[cat]", "同類別過期只留第一檔日期"),
    ("M10_denominator_lt_zero", _LOGIC, "if denominator <= 0:", "if denominator < 0:", "分母 <= 0 改 < 0"),
    ("M11_missing_key_fx_as_nav", _HOLD, "return None, MissingReason(REASON_FX_ABSENT, fx_key=key), KIND_FX",
     "return None, MissingReason(REASON_FX_ABSENT, fx_key=key), KIND_NAV", "缺匯率記成淨值類"),
    ("M12_missing_key_nav_as_fx", _HOLD, "return None, MissingReason(REASON_NAV_ABSENT), KIND_NAV",
     "return None, MissingReason(REASON_NAV_ABSENT), KIND_FX", "缺淨值記成匯率類"),
    ("M13_single_reason_ge", _LOGIC, "elif len(reasons) == 1 and None not in reasons:",
     "elif len(reasons) >= 1 and None not in reasons:", "單一理由判斷 == 1 改 >= 1"),
    ("M14_exceeds_endpoint_is_breach", _HOLD,
     "return abs(diff) > tolerance and not math.isclose(abs(diff), tolerance, abs_tol=1e-9)",
     "return abs(diff) >= tolerance", "端點相等算超出"),
    ("M15_row_order_sorted", _LOGIC, "for bucket in _row_order(targets, bucket_names, values):",
     "for bucket in sorted(_row_order(targets, bucket_names, values)):", "ALO-2 列序排序"),
    ("M16_category_order_sorted", _HOLD,
     "return {cat: CategorySlot(s[0], s[1], s[2], s[3]) for cat, s in slots.items()}, stale",
     "return {cat: CategorySlot(s[0], s[1], s[2], s[3]) for cat, s in sorted(slots.items())}, stale", "類別順序排序"),
    ("M17_basis_not_mv_goes_cost", _LOGIC, "        holding, dataset, market=(basis != BASIS_COST), fx_key_of=fx_key_for,",
     "        holding, dataset, market=(basis == BASIS_MV), fx_key_of=fx_key_for,",
     "基準 None／未知字串改走成本路徑（單檔包裝）"),
    ("M17b_category_basis_not_mv_goes_cost", _LOGIC,
     "aggregated_holdings(dataset), dataset, market=(basis != BASIS_COST), track_stale=track_stale,",
     "aggregated_holdings(dataset), dataset, market=(basis == BASIS_MV), track_stale=track_stale,",
     "基準 None／未知字串改走成本路徑（類別加總包裝）"),
    ("M18_cost_basis_reads_nav", _HOLD, '    if not market:\n        return float(holding["cost_twd"]), None, None\n',
     '    tables["nav"]\n    if not market:\n        return float(holding["cost_twd"]), None, None\n',
     "成本基準也讀淨值（破壞惰性）"),
    ("M19_nav_not_ready_checked_eagerly", _HOLD, '    code = holding["fund_code"]\n    nav = latest_nav_row(tables["nav"], code)\n',
     '    code = holding["fund_code"]\n    stale_provider()\n    nav = latest_nav_row(tables["nav"], code)\n',
     "nav_not_ready 形狀檢查提前到有淨值也做"),
    # G1-③：匯率對齊的唯一實作搬到 `fx_row_as_of`（`fx_rate_as_of` 委派過去），本筆目標字串跟著搬；偵測力不變。
    ("M20_fx_same_day_last_wins", _HOLD, 'return max(rows, key=lambda r: r["obs_date"]) if rows else None',
     'return max(reversed(rows), key=lambda r: r["obs_date"]) if rows else None', "同日多列匯率取最後一列"),
    ("M21_latest_nav_min", _HOLD, 'return max(rows, key=lambda r: r["nav_date"]) if rows else None',
     'return min(rows, key=lambda r: r["nav_date"]) if rows else None', "最近一筆淨值改取最舊"),
    ("M22_no_uncovered_tail", _LOGIC, 'tail_lines.append("合計未涵蓋 " + "、".join(uncovered))', "pass",
     "表尾不寫合計未涵蓋"),
    ("M23_alo3_total_lt_zero", _LOGIC, "if total <= 0:", "if total < 0:", "ALO-3 試算總額 <= 0 改 < 0"),
    ("M24_light_ignores_incomplete", _LOGIC, 'incomplete = source_incomplete or len(computed) < len(alo2["_rows"])',
     "incomplete = source_incomplete", "燈不把『有類別未評估』算不完整"),
    ("M25_fx_missing_no_dedupe", _LOGIC, "and key not in missing:", ":", "缺匯率鍵不去重"),
    ("M26_blocks_lamp_never", _LOGIC,
     '        row["_blocks_lamp"] = row["_current_pct"] is None and row["_target_pct"] is not None',
     '        row["_blocks_lamp"] = False', "有目標卻算不出差距的列不擋燈"),
    ("M27_alo6_nonpositive_total_still_shares", _LOGIC, 'if row["_value"] is None or total <= 0:',
     'if row["_value"] is None:', "ALO-6 合計不為正仍算佔比"),
    ("M28_alo6_excluded_flag_dropped", _LOGIC, "if value is None and basis is not None:",
     "if False:", "ALO-6 缺基準值格不記資料未備"),
    ("M29_unclassified_label", _LOGIC, "    return UNCLASSIFIED if category is None else category",
     '    return "其他" if category is None else category', "未分類字樣改"),
    ("M30_tolerance_none_ignored", _LOGIC, "    if tolerance is None:\n        return TEXT_UNSET",
     "    if False:\n        return TEXT_UNSET", "容許帶未設仍判內外"),
    ("M31_stale_dedupe_removed", _HOLD, "code not in {c for c, _ in stale[cat].entries}", "True",
     "同代碼多保單過期不去重"),
    ("M32_stale_listing_ignored", _HOLD, 'if holding["fund_code"] in codes:', "if False:",
     "nav_not_ready 名單被忽略"),
    ("M33_pct_not_times_100", _LOGIC, 'row["_current_pct"] = slot["value"] / denominator * 100.0',
     'row["_current_pct"] = slot["value"] / denominator', "目前比重不乘 100"),
    ("M35_exceeds_no_float_tolerance", _HOLD,
     "return abs(diff) > tolerance and not math.isclose(abs(diff), tolerance, abs_tol=1e-9)",
     "return abs(diff) > tolerance", "容許帶端點不留浮點容差"),
    ("M36_leaders_exact_equality", _LOGIC, 'math.isclose(abs(r["_diff"]), top, abs_tol=1e-9)',
     'abs(r["_diff"]) == top', "並列最大差距改精確相等"),
    # ── G1-② 起針對新程式碼（領域核心＋薄包裝）的突變 ──
    ("M37_wrapper_undated_uses_dated_text", _LOGIC, "return NAV_NOT_READY_TEXT.format(days=missing.stale_days)",
     "return NAV_NOT_READY_DATED_TEXT.format(day=missing.stale_day, days=missing.stale_days)",
     "包裝：舊形狀過期代碼誤對到有日期句子"),
    ("M38_wrapper_nav_absent_text_swapped", _LOGIC,
     '    if code == _v2d.holdings.REASON_NAV_ABSENT:\n        return empty_source_text(["nav"])',
     '    if code == _v2d.holdings.REASON_NAV_ABSENT:\n        return fx_missing_text("nav")', "包裝：缺淨值代碼對到缺匯率句子"),
    ("M39_wrapper_fx_absent_drops_key", _LOGIC, "return fx_missing_text(missing.fx_key)", "return fx_missing_text(FX_KEY)",
     "包裝：缺匯率句子不帶實際匯率鍵"),
    ("M40_domain_undated_code_swapped", _HOLD, "MissingReason(REASON_NAV_STALE_UNDATED, stale_days=days)",
     "MissingReason(REASON_NAV_STALE, stale_days=days)", "領域：舊形狀過期回成有日期代碼"),
    ("M41_domain_dated_code_swapped", _HOLD, "MissingReason(REASON_NAV_STALE, stale_day=last[holding[\"fund_code\"]], stale_days=days)",
     "MissingReason(REASON_NAV_STALE_UNDATED, stale_days=days)", "領域：有日期過期回成舊形狀代碼"),
    ("M42_domain_is_stale_true_for_fx_absent", _HOLD, "reason.code == REASON_NAV_STALE\n",
     "reason.code != REASON_NAV_ABSENT\n", "領域：結構式過期判定把缺匯率也當過期"),
    ("M43_domain_is_stale_ignores_track_stale", _HOLD, "is_stale = track_stale and value is None",
     "is_stale = value is None", "領域：非市值基準（None／未知字串）也做過期併日期"),
    ("M44_domain_iterates_reversed", _HOLD, "    for holding in holdings:\n        cat = category_of(holding)",
     "    for holding in reversed(list(holdings)):\n        cat = category_of(holding)", "領域：持倉倒序累加（類別順序、定案順序、累加順序皆變）"),
    ("M45_domain_slot_start_int_zero", _HOLD, "slots.setdefault(cat, [0.0, None, 0, None])",
     "slots.setdefault(cat, [0, None, 0, None])", "領域：累加起點 0.0 改整數 0"),
    ("M46_domain_dedupe_by_day", _HOLD, "code not in {c for c, _ in stale[cat].entries}",
     "reason.stale_day not in {d for _, d in stale[cat].entries}", "領域：過期去重改以日期（而非代碼）判斷"),
    ("M47_wrapper_kind_nav_as_fx", _LOGIC, "    if kind == _v2d.holdings.KIND_NAV:\n        return _CLASS_NAV",
     "    if kind == _v2d.holdings.KIND_NAV:\n        return _CLASS_FX", "包裝：資料類代碼 nav 對到市場指標類"),
    ("M48_wrapper_stale_out_not_filled", _LOGIC,
     "stale_out.update({cat: list(merge.entries) for cat, merge in stale.items()})", "stale_out.update({})",
     "包裝：stale_out 不回填"),
    ("M49_wrapper_missing_key_dropped", _LOGIC,
     '            values[cat]["_missing_key"] = _class_of_kind(slot.kind)', "            pass",
     "包裝：類別缺值不記資料類"),
    ("M50_domain_slot_missing_kind_lost", _HOLD, "slot[0], slot[1], slot[3] = None, reason, kind\n",
     "slot[0], slot[1], slot[3] = None, reason, None\n", "領域：類別缺值的資料類丟失"),
    ("M51_domain_nav_date_from_wrong_row", _HOLD, 'nav_date = nav["nav_date"]\n', 'nav_date = "9999-12-31"\n',
     "領域：匯率對齊日不取淨值日"),
    ("M34_diff_reversed", _LOGIC, 'row["_diff"] = row["_current_pct"] - row["_target_pct"]',
     'row["_diff"] = row["_target_pct"] - row["_current_pct"]', "差額方向相反"),
]

#: 倖存的突變（等價或矩陣打不到）→ 理由。跑完實測後填入；空表 = 全數被抓到。
SURVIVORS_DOCUMENTED: dict = {
    "M43_domain_is_stale_ignores_track_stale": (
        "黃金檔沒有『非市值基準（None／未知字串）＋過期名單＋同類別兩檔過期』這個組合；等價性改由 "
        "`tests/test_v2_domain_alo_core.py` 的探針突變測試與對搬遷前實作的隨機差分咬住（不改黃金檔）。"),
    "M45_domain_slot_start_int_zero": (
        "黃金檔的金額全是浮點，`0 + 浮點` 與 `0.0 + 浮點` 逐位元組相同；只有全整數輸入才看得出型別差，"
        "由 `tests/test_v2_domain_alo_core.py` 的探針（整數單位數 × 整數淨值）咬住。"),
    "M46_domain_dedupe_by_day": (
        "黃金檔的過期情境裡，不同代碼的最後淨值日都不同、同代碼的日期必相同 ⇒ 以日期或以代碼去重結果一樣；"
        "『不同代碼同一天』由 `tests/test_v2_domain_alo_core.py` 的探針咬住。"),
}


def _exec_module(source: str, name: str, package: str) -> dict:
    ns = {"__name__": name, "__package__": package}
    # dont_inherit=True：不繼承本測試檔的 `from __future__ import annotations`（否則被載入的模組裡 dataclass 欄位註記
    # 會變成字串，而突變體不進 sys.modules，dataclasses 查不到模組會炸）。被載入的原始碼自己有沒有 future import 照它自己的。
    exec(compile(source, f"<mutant:{name}>", "exec", dont_inherit=True), ns)   # noqa: S102 — 只執行 repo 自己的原始碼（改過一處）
    return ns


def load_namespace(mutation=None) -> dict:
    """載入 `ui_v2.alo.logic`（可帶一處突變）。回命名空間 dict；**不進 sys.modules**。"""
    G.setup_path()
    logic_src = (_ROOT / _LOGIC).read_text(encoding="utf-8")
    hold_src = (_ROOT / _HOLD).read_text(encoding="utf-8")
    target_file = None
    if mutation is not None:
        _id, target_file, old, new, _doc = mutation
        base = logic_src if target_file == _LOGIC else hold_src
        count = base.count(old)
        assert count == 1, f"{_id}：舊字串在 {target_file} 出現 {count} 次（要剛好 1 次）—— 突變目標消失或變多"
        if target_file == _LOGIC:
            logic_src = base.replace(old, new)
        else:
            hold_src = base.replace(old, new)
    ns = _exec_module(logic_src, "ui_v2.alo._mutant_logic", "ui_v2.alo")
    if target_file == _HOLD:
        hold_ns = _exec_module(hold_src, "services.v2_domain._mutant_holdings", "services.v2_domain")
        holdings = types.SimpleNamespace(**{k: v for k, v in hold_ns.items() if not k.startswith("__")})
        ns["_v2d"] = types.SimpleNamespace(holdings=holdings)
        ns["exceeds"] = holdings.exceeds
    return ns


def _golden_encoded() -> dict:
    doc = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    return {"strings": doc["strings"], "matrix": doc["matrix"]}


def _groups_that_differ(ns) -> list:
    now = G.encode_matrix(G.run_matrix(ns))
    gold = _golden_encoded()
    if now == gold:
        return []
    # 壓縮編號會連動，逐組比對要先解壓
    now_dec = G.decode_matrix(now)
    gold_dec = G.decode_matrix(gold)
    return sorted(g for g in gold_dec if gold_dec[g] != now_dec.get(g))


@baseline_python_only
def test_對照組_未突變的載入器重現黃金檔():
    assert _groups_that_differ(load_namespace()) == []


@pytest.mark.parametrize("mutation", [m for m in MUTATIONS if m[0] not in SURVIVORS_DOCUMENTED], ids=lambda m: m[0])
@baseline_python_only   # 非基準版本時未突變基準本身就與黃金檔不同 ⇒ `assert differ` 空泛為真（假綠燈），故同樣只在基準版本執行
def test_突變被黃金檔抓到(mutation):
    try:
        differ = _groups_that_differ(load_namespace(mutation))
    except AssertionError:
        raise
    except Exception:  # noqa: BLE001 — 突變體整個炸掉也算「和黃金檔不同」，但矩陣是逐案包 try 的，這裡炸代表載入器本身壞了
        raise
    assert differ, f"{mutation[0]}（{mutation[4]}）：突變體的輸出與黃金檔完全相同 —— 黃金檔沒咬到這一處"


def test_倖存突變的目標字串仍在_理由有登記():
    for mutation_id, reason in SURVIVORS_DOCUMENTED.items():
        mutation = next(m for m in MUTATIONS if m[0] == mutation_id)
        load_namespace(mutation)                  # 剛好一次，否則當場紅
        assert reason.strip()


def test_防空掃_突變清單不是空的_編號不重複():
    ids = [m[0] for m in MUTATIONS]
    assert len(ids) == len(set(ids)) >= 30
    assert {m[1] for m in MUTATIONS} == {_LOGIC, _HOLD}


def test_突變不污染_sys_modules():
    import sys
    load_namespace(MUTATIONS[0])
    assert not any("_mutant" in name for name in sys.modules)
