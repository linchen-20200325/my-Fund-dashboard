# -*- coding: utf-8 -*-
"""`tests/fixtures/alo_core_golden_before.json`（BL-0542 G1-① 黃金檔）的情境矩陣與錄製腳本（測試共用；不是測試檔）。

用途：把 💼 ALO 配置核心（`ui_v2/alo/logic.py` 的 `basis_value_with_key`／`basis_value`／`_category_values`／
`_build_alo2` 及其下游 `_build_alo0`／`conclusion_light`／`_build_alo3`／`_build_alo6`／`_fx_missing_for_mv`）
**搬遷（G1-②）之前**的行為整個序列化存檔；搬遷後 `tests/test_alo_core_golden.py` 以**同一份**情境矩陣
對工作樹再跑一次，序列化結果必須與檔案**逐位元組相同**。

基準：commit `e6ff19025f7e2c56c6c398de7c59188194aa96ab`、tree `abebfa59e4112e970c4bccb2ddda9253ed4b3675`。

用法（在**乾淨解開的基準版本目錄**執行；不打網路、不讀試算表）::

    git archive e6ff1902 | tar -x -C <乾淨目錄>
    cp tests/_alo_core_golden.py <乾淨目錄>/tests/
    cd <乾淨目錄> && python tests/_alo_core_golden.py <輸出 JSON> --commit <sha> --tree <sha>

⚠️ 不得用改動後的程式重錄來「讓測試變綠」—— 那會讓「搬遷前後逐位元組相同」變成循環論證
（同 `tests/_nav_dividend_golden_c3a.py`、`tests/_record_a_chain_golden.py` 的體例）。
⚠️ 預期值一律由程式錄出，不手寫；本檔只負責「輸入」與「序列化」。

序列化慣例（同 `tests/test_v2_domain_port.py`）：浮點用 `repr`；dict 保留插入順序；set 排序；
例外記 (型別名, 訊息)，但訊息不含中文字元者（Python 內建的英文訊息，各版本可能不同）只留型別；
本 repo 自己組的中文訊息照留。

已知差異（**照現況錄下，不修**）：市值基準下「某類別缺匯率、另一類別有值」時，有值的類別分母只含自己 ⇒ 顯示 100.0%。
這與客戶核可的方案 A 不同（見 `docs/BACKLOG.md` BL-0542）；本黃金檔凍結的是**現況**，不是理想行為。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
NAN = float("nan")
INF = float("inf")

RECORDER_NAME = "tests/_alo_core_golden.py"
#: 影響黃金檔行為的檔案（檔頭記 git blob 雜湊）。
FEEDING_FILES = (
    "ui_v2/alo/logic.py",
    "services/v2_domain/holdings.py",
    "ui_v2/v2_domain_shim.py",
    "ui_v2/page_health.py",
    "ui_v2/status_class.py",
)


def setup_path(root=None):
    root = pathlib.Path(root or _ROOT)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def live_namespace():
    """工作樹上的 `ui_v2.alo.logic` 命名空間（dict；矩陣一律對 dict 取名字，好讓突變測試換成自己的）。"""
    setup_path()
    import importlib
    return vars(importlib.import_module("ui_v2.alo.logic"))


def git_blob_hash(path) -> str:
    data = pathlib.Path(path).read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


# ───────────────────────── 序列化 ─────────────────────────


def has_cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" or "　" <= ch <= "〿" or "＀" <= ch <= "￯" for ch in text)


def canon(value):
    """值 → JSON 原生結構（可逆、保序、不丟型別）。不認得的型別 → 當場炸。"""
    if isinstance(value, BaseException):
        msg = str(value)
        return {"__exc__": [type(value).__name__, msg if has_cjk(msg) else None]}
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return {"__float__": repr(value)}
    if isinstance(value, dict):
        if all(isinstance(k, str) and not k.startswith("__") for k in value):
            return {k: canon(v) for k, v in value.items()}
        return {"__dict__": [[canon(k), canon(v)] for k, v in value.items()]}
    if isinstance(value, (set, frozenset)):
        items = [canon(v) for v in value]
        return {"__set__": sorted(items, key=lambda x: json.dumps(x, ensure_ascii=False))}
    if isinstance(value, tuple):
        return {"__tuple__": [canon(v) for v in value]}
    if isinstance(value, list):
        return [canon(v) for v in value]
    raise TypeError(f"黃金檔遇到不能序列化的型別 {type(value).__name__}: {value!r}")


def _compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def dumps(value) -> str:
    """穩定序列化（不排序鍵：dict 插入順序本身就是被凍結的行為）。
    形狀 {"header"?, "strings"?, "matrix": {組: {情境: …}}}：每個情境佔一行（壓成單行 JSON），檔案才看得懂 diff。"""
    if not isinstance(value, dict):
        return _compact(value) + "\n"
    parts = []
    for key, sub in value.items():
        if key == "matrix" and isinstance(sub, dict):
            groups = []
            for group, cases in sub.items():
                inner = ",\n".join(f"   {_compact(k)}: {_compact(v)}" for k, v in cases.items())
                groups.append(f"  {_compact(group)}: {{\n{inner}\n  }}")
            parts.append(f" {_compact(key)}: {{\n" + ",\n".join(groups) + "\n }")
        else:
            parts.append(f" {_compact(key)}: {_compact(sub)}")
    return "{\n" + ",\n".join(parts) + "\n}\n"


def encode_matrix(matrix) -> dict:
    """無損壓縮：重複出現的長字串（畫面固定說明句、模板句）收進 `strings`，原位置換成 {"__s__": 編號}。
    編號依第一次出現的順序，與內容無關的決定性演算法 ⇒ 同一份矩陣永遠得到同一份位元組。
    理由：fixture 單檔逼近 pre-commit `check-added-large-files` 的 500 KB 上限，且逐案 diff 時固定說明句只是雜訊。"""
    counts = {}

    def walk(node):
        if isinstance(node, str):
            if len(node) >= 12:
                counts[node] = counts.get(node, 0) + 1
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(k)
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(matrix)
    table = []
    index = {}

    def pack(node):
        if isinstance(node, str):
            if counts.get(node, 0) >= 3:
                if node not in index:
                    index[node] = len(table)
                    table.append(node)
                return {"__s__": index[node]}
            return node
        if isinstance(node, dict):
            if all(isinstance(k, str) for k in node):
                return {k: pack(v) for k, v in node.items()}
        if isinstance(node, list):
            return [pack(v) for v in node]
        return node

    packed = pack(matrix)
    return {"strings": table, "matrix": packed}


def decode_matrix(encoded) -> dict:
    """`encode_matrix` 的反運算 → 還原成原本的 {組: {情境: 結果}}。"""
    table = encoded["strings"]

    def unpack(node):
        if isinstance(node, dict):
            if set(node) == {"__s__"}:
                return table[node["__s__"]]
            return {k: unpack(v) for k, v in node.items()}
        if isinstance(node, list):
            return [unpack(v) for v in node]
        return node

    return unpack(encoded["matrix"])


def call(fn, *args, **kwargs):
    """('ok', 值) 或 ('raise', 例外)；例外本身就是要凍結的行為。"""
    try:
        return {"ok": canon(fn(*args, **kwargs))}
    except Exception as exc:  # noqa: BLE001
        return {"raise": canon(exc)}


class Spy(dict):
    """記下被讀過的頂層鍵（`[]`、`get`、`in`）；用來凍結「惰性」：哪些表在哪些路徑不該被碰。"""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.touched = set()

    def __getitem__(self, key):
        self.touched.add(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self.touched.add(key)
        return super().get(key, default)

    def __contains__(self, key):
        self.touched.add(key)
        return super().__contains__(key)


# ───────────────────────── 素材 ─────────────────────────

CORE, SAT, BOND = "核心", "衛星", "債券"
NAMES = (CORE, SAT)
FX_USD, FX_EUR, FX_JPY = "fx_twd_per_usd", "fx_twd_per_eur", "fx_twd_per_jpy"


def H(code, *, bucket=CORE, ccy="USD", units=10.0, cost=3000.0, policy="P1", name=None, cost_orig=100.0):
    return {"holding_id": f"H-{policy}-{code}", "policy_id": policy, "fund_code": code,
            "fund_name": name or f"基金{code}", "ccy": ccy, "units_shares": units, "cost_orig_ccy": cost_orig,
            "cost_twd": cost, "opened_on": "2026-01-01", "bucket": bucket, "last_synced_at": "2026-10-01T00:00:00Z"}


def N(code, day, nav, ccy="USD"):
    return {"fund_code": code, "nav_date": day, "nav_orig_ccy": nav, "ccy": ccy, "source_tier": "淨值",
            "is_estimated": False, "fetched_at": "2026-10-04T00:00:00Z"}


def FX(key, day, value):
    return {"indicator_key": key, "obs_date": day, "release_date": day, "value_num": value, "value_unit": "TWD",
            "source_tier": "市場指標", "is_revised": False, "fetched_at": "2026-10-04T00:00:00Z"}


def settings(targets, tol, basis, names, scenario):
    def row(key, value):
        return {"setting_key": key, "setting_value": value, "value_kind": None,
                "updated_at": "2026-10-01T00:00:00Z" if value is not None else None}
    return [row("alo_target_weights", targets), row("alo_tolerance_pp", tol), row("alo_basis", basis),
            row("alo_bucket_names", list(names) if names is not None else None), row("alo_scenario_input", scenario)]


TARGETS = [{"bucket": CORE, "weight_ratio": 0.6}, {"bucket": SAT, "weight_ratio": 0.4}]
SCEN = [{"bucket": CORE, "amount_twd": 1000.0}, {"bucket": SAT, "amount_twd": -500.0},
        {"bucket": "不存在", "amount_twd": 1.0}, {"bucket": CORE, "amount_twd": None},
        {"bucket": SAT, "amount_twd": -10 ** 9}]
POLICIES = [{"policy_id": "DIRECT", "policy_name": "直接持有"}, {"policy_id": "P1", "policy_name": "保單一"}]

NAV_STD = [N("A", "2026-10-03", 10.0, "USD"), N("B", "2026-10-03", 20.0, "TWD"), N("C", "2026-10-03", 5.0, "EUR")]
FX_STD = [FX(FX_USD, "2026-10-03", 30.0), FX(FX_EUR, "2026-10-03", 35.0)]


def DS(holdings, nav=(), fx=(), *, targets=TARGETS, tol=5.0, basis="成本", names=NAMES, scenario=None,
       errors=None, nav_not_ready=None, skipped_holdings=None, skipped_tabs=None, policy=POLICIES, save_errors=None,
       raw_settings=None):
    ds = {"holding": [dict(h) for h in holdings], "nav": [dict(n) for n in nav],
          "market_indicator": [dict(f) for f in fx], "policy": [dict(p) for p in policy],
          "user_setting": raw_settings if raw_settings is not None else settings(targets, tol, basis, names, scenario),
          "errors": dict(errors or {}), "save_errors": dict(save_errors or {})}
    if nav_not_ready is not None:
        ds["nav_not_ready"] = nav_not_ready
    if skipped_holdings is not None:
        ds["skipped_holdings"] = skipped_holdings
    if skipped_tabs is not None:
        ds["skipped_tabs"] = skipped_tabs
    return ds


def NNR(codes, days=10, last=None):
    out = {"codes": list(codes), "days": days}
    if last is not None:
        out["last"] = dict(last)
    return out


# ───────────────────────── (1) basis_value(_with_key) ─────────────────────────

MV, COST = "市值", "成本"


def _basis_cases():
    """(名稱, holding, 資料集內容 dict, basis)。資料集以 Spy 包起來，記下被讀過的表。"""
    cases = []

    def add(label, holding, basis, **tables):
        cases.append((label, holding, tables, basis))

    a = H("A")
    # 成本基準：惰性（資料集完全空也不讀 nav／市場指標）
    add("cost:float", a, COST)
    add("cost:int", H("A", cost=3000), COST)
    add("cost:str12", H("A", cost="12"), COST)
    add("cost:str_bad", H("A", cost="abc"), COST)
    add("cost:none", H("A", cost=None), COST)
    add("cost:nan", H("A", cost=NAN), COST)
    add("cost:zero", H("A", cost=0.0), COST)
    add("cost:negative", H("A", cost=-5.0), COST)
    add("cost:missing_key", {k: v for k, v in a.items() if k != "cost_twd"}, COST)
    add("cost:ignores_nav", a, COST, nav=NAV_STD, market_indicator=FX_STD)
    # 市值基準：新臺幣／美元／歐元／日圓
    add("mv:twd", H("B", ccy="TWD", units=100.0), MV, nav=NAV_STD, market_indicator=[])
    add("mv:twd_no_market_indicator_key", H("B", ccy="TWD", units=100.0), MV, nav=NAV_STD)
    add("mv:usd", a, MV, nav=NAV_STD, market_indicator=FX_STD)
    add("mv:usd_no_market_indicator_key", a, MV, nav=NAV_STD)
    add("mv:eur", H("C", ccy="EUR", units=2.0), MV, nav=NAV_STD, market_indicator=FX_STD)
    add("mv:jpy_missing_key", H("J"), MV, nav=[N("J", "2026-10-03", 100.0, "JPY")], market_indicator=FX_STD)
    add("mv:jpy_ok", H("J"), MV, nav=[N("J", "2026-10-03", 100.0, "JPY")],
        market_indicator=[FX(FX_JPY, "2026-10-03", 0.2)])
    add("mv:units_zero", H("A", units=0.0), MV, nav=NAV_STD, market_indicator=FX_STD)
    add("mv:units_nan", H("A", units=NAN), MV, nav=NAV_STD, market_indicator=FX_STD)
    add("mv:nav_nan_usd", a, MV, nav=[N("A", "2026-10-03", NAN)], market_indicator=FX_STD)
    add("mv:nav_nan_twd", H("B", ccy="TWD"), MV, nav=[N("B", "2026-10-03", NAN, "TWD")])
    add("mv:nav_negative", a, MV, nav=[N("A", "2026-10-03", -1.0)], market_indicator=FX_STD)
    add("mv:nav_none_value", a, MV, nav=[N("A", "2026-10-03", None)], market_indicator=FX_STD)
    add("mv:fx_zero_is_value_not_missing", a, MV, nav=NAV_STD, market_indicator=[FX(FX_USD, "2026-10-03", 0.0)])
    add("mv:fx_none_value", a, MV, nav=NAV_STD, market_indicator=[FX(FX_USD, "2026-10-03", None)])
    # 缺淨值
    add("mv:nav_missing", H("Z"), MV, nav=NAV_STD, market_indicator=FX_STD)
    add("mv:nav_empty", a, MV, nav=[], market_indicator=FX_STD)
    # 淨值過期（舊形狀／新形狀／列了但有淨值／沒列）
    add("mv:stale_old_shape", H("Z"), MV, nav=[], market_indicator=[], nav_not_ready=NNR(["Z"], 10))
    add("mv:stale_new_shape", H("Z"), MV, nav=[], market_indicator=[],
        nav_not_ready=NNR(["Z"], 10, {"Z": "2026-09-01"}))
    add("mv:stale_listed_but_nav_present", a, MV, nav=NAV_STD, market_indicator=FX_STD,
        nav_not_ready=NNR(["A"], 10, {"A": "2026-09-01"}))
    add("mv:stale_other_code_listed", H("Z"), MV, nav=[], market_indicator=[],
        nav_not_ready=NNR(["Y"], 10, {"Y": "2026-09-01"}))
    add("mv:stale_empty_codes", H("Z"), MV, nav=[], market_indicator=[], nav_not_ready=NNR([], None))
    add("mv:stale_bad_shape_nav_missing", H("Z"), MV, nav=[], market_indicator=[], nav_not_ready={"codes": ["Z"]})
    add("mv:stale_bad_shape_nav_present", a, MV, nav=NAV_STD, market_indicator=FX_STD, nav_not_ready={"codes": ["Z"]})
    add("mv:stale_bad_days", H("Z"), MV, nav=[], market_indicator=[], nav_not_ready=NNR(["Z"], -1))
    add("mv:stale_bad_last_date", H("Z"), MV, nav=[], market_indicator=[],
        nav_not_ready=NNR(["Z"], 10, {"Z": "20260901"}))
    add("mv:stale_last_mismatch", H("Z"), MV, nav=[], market_indicator=[],
        nav_not_ready=NNR(["Z"], 10, {"Y": "2026-09-01"}))
    add("mv:stale_none_value", H("Z"), MV, nav=[], market_indicator=[], nav_not_ready=None)
    # 缺匯率
    add("mv:fx_missing_usd", a, MV, nav=NAV_STD, market_indicator=[])
    add("mv:fx_missing_eur_key_in_message", H("C", ccy="EUR"), MV, nav=NAV_STD, market_indicator=[FX(FX_USD, "2026-10-03", 30.0)])
    # 匯率對齊日：等於／晚於／早於／同日多列
    nav_day = [N("A", "2026-10-03", 10.0)]
    add("fx:obs_equal_nav_date", a, MV, nav=nav_day, market_indicator=[FX(FX_USD, "2026-10-03", 31.0)])
    add("fx:obs_later_only", a, MV, nav=nav_day, market_indicator=[FX(FX_USD, "2026-10-04", 31.0)])
    add("fx:obs_earlier_only", a, MV, nav=nav_day, market_indicator=[FX(FX_USD, "2026-10-02", 29.0)])
    add("fx:earlier_equal_later", a, MV, nav=nav_day, market_indicator=[
        FX(FX_USD, "2026-10-04", 33.0), FX(FX_USD, "2026-10-03", 31.0), FX(FX_USD, "2026-10-02", 29.0)])
    add("fx:same_day_two_rows_first_wins", a, MV, nav=nav_day, market_indicator=[
        FX(FX_USD, "2026-10-03", 31.0), FX(FX_USD, "2026-10-03", 99.0)])
    add("fx:same_day_two_rows_reverse", a, MV, nav=nav_day, market_indicator=[
        FX(FX_USD, "2026-10-03", 99.0), FX(FX_USD, "2026-10-03", 31.0)])
    add("fx:other_key_only", a, MV, nav=nav_day, market_indicator=[FX(FX_EUR, "2026-10-03", 35.0)])
    add("fx:obs_none_row", a, MV, nav=nav_day, market_indicator=[FX(FX_USD, None, 31.0)])
    add("fx:uses_latest_nav_date", a, MV, nav=[N("A", "2026-10-01", 10.0), N("A", "2026-10-05", 12.0)],
        market_indicator=[FX(FX_USD, "2026-10-01", 29.0), FX(FX_USD, "2026-10-04", 31.0), FX(FX_USD, "2026-10-05", 32.0)])
    add("nav:same_day_two_rows_first_wins", a, MV,
        nav=[N("A", "2026-10-03", 10.0), N("A", "2026-10-03", 99.0)], market_indicator=FX_STD)
    add("nav:latest_by_date_not_order", a, MV,
        nav=[N("A", "2026-10-05", 12.0), N("A", "2026-10-01", 10.0)], market_indicator=FX_STD)
    # 幣別異常
    add("ccy:lowercase", a, MV, nav=[N("A", "2026-10-03", 10.0, "usd")], market_indicator=FX_STD)
    add("ccy:none", a, MV, nav=[N("A", "2026-10-03", 10.0, None)], market_indicator=FX_STD)
    add("ccy:four_letters", a, MV, nav=[N("A", "2026-10-03", 10.0, "USDT")], market_indicator=FX_STD)
    add("ccy:twd_lowercase", a, MV, nav=[N("A", "2026-10-03", 10.0, "twd")], market_indicator=FX_STD)
    # basis 為 None／未知字串 → 目前走市值路徑
    for label, b in (("none", None), ("unknown", "未知基準"), ("empty", ""), ("trailing_space", "市值 "),
                     ("english", "market"), ("cost_english", "cost")):
        add(f"basis:{label}_usd", a, b, nav=NAV_STD, market_indicator=FX_STD)
        add(f"basis:{label}_cost_holding_only", a, b)
    return cases


def run_basis(ns):
    out = {}
    for label, holding, tables, basis in _basis_cases():
        spy1, spy2 = Spy(), Spy()
        for k, v in tables.items():
            spy1[k] = v
            spy2[k] = v
        r1 = call(ns["basis_value_with_key"], spy1, holding, basis)
        r2 = call(ns["basis_value"], spy2, holding, basis)
        out[label] = {"with_key": r1, "touched": sorted(spy1.touched), "plain": r2, "touched_plain": sorted(spy2.touched)}
    return out


# ───────────────────────── (2) _category_values ─────────────────────────


def _cat_cases():
    cases = []

    def add(label, holdings, basis=MV, nav=(), fx=(), names=NAMES, **extra):
        cases.append((label, DS(holdings, nav, fx, basis=basis, names=names, **extra), basis, names))

    nav_all = [N("A", "2026-10-03", 10.0, "USD"), N("B", "2026-10-03", 20.0, "TWD"), N("C", "2026-10-03", 5.0, "EUR"),
               N("D", "2026-10-03", 8.0, "USD")]
    add("complete_cost", [H("A", cost=100.0), H("B", bucket=SAT, cost=50.0), H("C", cost=25.0)], COST)
    add("complete_mv", [H("A"), H("B", bucket=SAT, ccy="TWD"), H("C", ccy="EUR")], MV, nav_all, FX_STD)
    # 同類別多理由
    add("reasons:fx_then_nav", [H("A"), H("Z")], MV, nav_all, [])
    add("reasons:nav_then_fx", [H("Z"), H("A")], MV, nav_all, [])
    add("reasons:fx_then_nav_then_value", [H("A"), H("Z"), H("B", ccy="TWD")], MV, nav_all, [])
    add("reasons:nav_then_nav", [H("Z"), H("Y")], MV, nav_all, FX_STD)
    # 過期＋過期併日期
    last2 = {"Z": "2026-09-01", "Y": "2026-09-05"}
    last3 = {"Z": "2026-09-01", "Y": "2026-09-05", "X": "2026-08-20"}
    add("stale:two_same_cat", [H("Z"), H("Y")], MV, nav_all, FX_STD, nav_not_ready=NNR(["Z", "Y"], 10, last2))
    add("stale:three_same_cat", [H("Z"), H("Y"), H("X")], MV, nav_all, FX_STD, nav_not_ready=NNR(["Z", "Y", "X"], 10, last3))
    add("stale:two_cats", [H("Z"), H("Y", bucket=SAT)], MV, nav_all, FX_STD, nav_not_ready=NNR(["Z", "Y"], 10, last2))
    add("stale:same_code_two_policies_dedupe", [H("Z", policy="P1"), H("Z", policy="P2"), H("Y", policy="P1")], MV, nav_all, FX_STD,
        nav_not_ready=NNR(["Z", "Y"], 10, last2))
    add("stale:then_fx_missing", [H("Z"), H("A")], MV, nav_all, [], nav_not_ready=NNR(["Z"], 10, {"Z": "2026-09-01"}))
    add("stale:fx_then_stale", [H("A"), H("Z")], MV, nav_all, [], nav_not_ready=NNR(["Z"], 10, {"Z": "2026-09-01"}))
    add("stale:then_nav_missing", [H("Z"), H("Q")], MV, nav_all, FX_STD, nav_not_ready=NNR(["Z"], 10, {"Z": "2026-09-01"}))
    add("stale:stale_then_nav_missing_then_stale", [H("Z"), H("Q"), H("Y")], MV, nav_all, FX_STD,
        nav_not_ready=NNR(["Z", "Y"], 10, last2))
    add("stale:old_shape_not_merged", [H("Z"), H("Y")], MV, nav_all, FX_STD, nav_not_ready=NNR(["Z", "Y"], 10))
    add("stale:value_then_stale", [H("B", ccy="TWD"), H("Z")], MV, nav_all, FX_STD,
        nav_not_ready=NNR(["Z"], 10, {"Z": "2026-09-01"}))
    add("stale:stale_then_value", [H("Z"), H("B", ccy="TWD")], MV, nav_all, FX_STD,
        nav_not_ready=NNR(["Z"], 10, {"Z": "2026-09-01"}))
    add("stale:cost_basis_ignores_stale", [H("Z"), H("Y")], COST, nav_all, FX_STD, nav_not_ready=NNR(["Z", "Y"], 10, last2))
    add("stale:listed_but_nav_present", [H("A")], MV, nav_all, FX_STD, nav_not_ready=NNR(["A"], 10, {"A": "2026-09-01"}))
    add("stale:bad_shape_mv", [H("A")], MV, nav_all, FX_STD, nav_not_ready={"codes": "AAA", "days": 1})
    # 值／缺／值 的 count 行為
    add("count:value_missing_value", [H("B", ccy="TWD"), H("Z"), H("D", ccy="USD")], MV, nav_all, FX_STD)
    add("count:missing_value_value", [H("Z"), H("B", ccy="TWD"), H("D", ccy="USD")], MV, nav_all, FX_STD)
    add("count:value_value_missing", [H("B", ccy="TWD"), H("D", ccy="USD"), H("Z")], MV, nav_all, FX_STD)
    # 類別順序
    add("order:sat_core_unbucketed", [H("A", bucket=SAT, cost=1.0), H("B", bucket=CORE, cost=2.0),
                                      H("C", bucket=None, cost=3.0), H("D", bucket="其他", cost=4.0)], COST)
    add("order:names_none", [H("A", cost=1.0), H("B", bucket=SAT, cost=2.0)], COST, names=None)
    add("order:names_empty", [H("A", cost=1.0)], COST, names=())
    add("order:names_string", [H("A", cost=1.0)], COST, names="核心衛星")
    add("order:empty_holdings", [], COST)
    # 例外先後
    add("exc:conflict_bucket_cost", [H("A", bucket=CORE), H("A", bucket=SAT)], COST)
    add("exc:conflict_bucket_mv", [H("A", bucket=CORE), H("A", bucket=SAT)], MV, nav_all, FX_STD)
    add("exc:conflict_ccy_cost", [H("A", ccy="USD"), H("A", ccy="EUR")], COST)
    add("exc:bad_nnr_and_conflict_mv", [H("A", bucket=CORE), H("A", bucket=SAT)], MV, nav_all, FX_STD,
        nav_not_ready={"bad": 1})
    add("exc:bad_nnr_and_conflict_cost", [H("A", bucket=CORE), H("A", bucket=SAT)], COST, nav_all, FX_STD,
        nav_not_ready={"bad": 1})
    add("exc:bad_nnr_empty_holdings_mv", [], MV, nav_all, FX_STD, nav_not_ready={"bad": 1})
    add("exc:ccy_lowercase_in_second_cat", [H("B", ccy="TWD", bucket=SAT), H("E")], MV,
        nav_all + [N("E", "2026-10-03", 1.0, "usd")], FX_STD)
    add("sum:aggregate_same_key", [H("A", cost=100.0), H("A", cost=50.0), H("B", cost=1.0)], COST)
    add("sum:nan_value", [H("A", units=NAN), H("B", ccy="TWD", bucket=SAT)], MV, nav_all, FX_STD)
    cases.append(("exc:no_holding_key", {"user_setting": [], "nav": [], "market_indicator": []}, COST, NAMES))
    return cases


def run_category_values(ns):
    out = {}
    for label, ds, basis, names in _cat_cases():
        fn = ns["_category_values"]
        sentinel = {"預填": [("X", "2000-01-01")]}
        stale_out = dict(sentinel)
        out[label] = {
            "no_stale_out": call(fn, ds, basis, names),
            "with_stale_out": call(fn, ds, basis, names, stale_out),
            "stale_out_after": canon(stale_out),
        }
    return out


# ───────────────────────── (3)(4) _build_alo2 與下游 ─────────────────────────


def _alo2_cases():
    cases = {}

    def add(label, ds):
        cases[label] = ds

    nav_all = [N("A", "2026-10-03", 10.0, "USD"), N("B", "2026-10-03", 20.0, "TWD"), N("C", "2026-10-03", 5.0, "EUR"),
               N("D", "2026-10-03", 8.0, "USD")]
    core2 = [H("A", cost=3000.0), H("B", cost=3000.0, ccy="TWD")]
    sat1 = [H("C", bucket=SAT, cost=4000.0, ccy="EUR")]
    # 完整、成本基準：帶內／帶外／端點
    add("cost:complete_on_target", DS(core2 + sat1))
    add("cost:complete_off_target", DS([H("A", cost=7000.0), H("C", bucket=SAT, cost=3000.0)]))
    add("cost:diff_exactly_tolerance", DS([H("A", cost=6500.0), H("C", bucket=SAT, cost=3500.0)]))
    add("cost:diff_within_1e9_of_tolerance", DS([H("A", cost=6500.0000000001), H("C", bucket=SAT, cost=3499.9999999999)]))
    add("cost:diff_just_above_tolerance", DS([H("A", cost=6500.01), H("C", bucket=SAT, cost=3499.99)]))
    add("cost:tolerance_zero_zero_diff", DS([H("A", cost=6000.0), H("C", bucket=SAT, cost=4000.0)], tol=0.0))
    add("cost:tolerance_zero_nonzero_diff", DS([H("A", cost=6001.0), H("C", bucket=SAT, cost=3999.0)], tol=0.0))
    add("cost:tolerance_none", DS(core2 + sat1, tol=None))
    add("cost:tolerance_negative", DS(core2 + sat1, tol=-1.0))
    add("cost:tolerance_nan", DS(core2 + sat1, tol=NAN))
    add("cost:tied_leaders_order", DS([H("A", cost=7000.0), H("C", bucket=SAT, cost=3000.0)], tol=1.0,
                                      targets=[{"bucket": SAT, "weight_ratio": 0.5}, {"bucket": CORE, "weight_ratio": 0.5}]))
    three = [{"bucket": CORE, "weight_ratio": 0.5}, {"bucket": SAT, "weight_ratio": 0.3}, {"bucket": BOND, "weight_ratio": 0.2}]
    add("cost:near_tied_leaders_within_1e9", DS([H("A", cost=5500.0000003), H("C", bucket=SAT, cost=2499.9999998),
                                                 H("D", bucket=BOND, cost=1999.9999999)], tol=1.0, targets=three, names=NAMES + (BOND,)))
    add("cost:not_tied_leaders_beyond_1e9", DS([H("A", cost=5500.003), H("C", bucket=SAT, cost=2499.998),
                                                H("D", bucket=BOND, cost=1999.999)], tol=1.0, targets=three, names=NAMES + (BOND,)))
    # 目標：沒持倉的類別、留空比重、未知、未設
    add("targets:bucket_without_holdings", DS(core2, targets=TARGETS + [{"bucket": BOND, "weight_ratio": 0.1}],
                                                names=NAMES + (BOND,)))
    add("targets:names_has_extra_no_target", DS(core2, names=NAMES + (BOND,)))
    add("targets:weight_none", DS(core2 + sat1, targets=[{"bucket": CORE, "weight_ratio": None}, {"bucket": SAT, "weight_ratio": 0.4}]))
    add("targets:weight_zero", DS(core2 + sat1, targets=[{"bucket": CORE, "weight_ratio": 0.0}, {"bucket": SAT, "weight_ratio": 1.0}]))
    add("targets:unset_none", DS(core2 + sat1, targets=None))
    add("targets:unset_empty_list", DS(core2 + sat1, targets=[]))
    add("targets:sum_not_one", DS(core2 + sat1, targets=[{"bucket": CORE, "weight_ratio": 0.9}, {"bucket": SAT, "weight_ratio": 0.9}]))
    add("targets:dup_bucket", DS(core2 + sat1, targets=[{"bucket": CORE, "weight_ratio": 0.5}, {"bucket": CORE, "weight_ratio": 0.7}]))
    add("basis:unset", DS(core2 + sat1, basis=None))
    add("basis:unknown_string_goes_market_path", DS([H("A"), H("C", bucket=SAT, ccy="EUR")], nav_all, FX_STD, basis="未知"))
    add("basis:unknown_string_no_nav", DS(core2, basis="未知"))
    add("names:unset", DS(core2 + sat1, names=None))
    add("holdings:empty", DS([]))
    add("holdings:empty_mv", DS([], basis=MV))
    # 未分類
    add("unclassified:none_bucket", DS(core2 + [H("C", bucket=None, cost=1000.0)]))
    add("unclassified:other_bucket_name", DS(core2 + [H("C", bucket="其他", cost=1000.0)]))
    add("unclassified:both_merge", DS(core2 + [H("C", bucket=None, cost=1000.0), H("D", bucket="其他", cost=500.0)]))
    add("unclassified:only", DS([H("C", bucket=None, cost=1000.0)]))
    add("unclassified:literal_name_as_bucket", DS(core2 + [H("C", bucket="未分類", cost=1000.0)]))
    # 同鍵
    add("key:aggregate_sum", DS([H("A", cost=3000.0), H("A", cost=3000.0), H("C", bucket=SAT, cost=4000.0)]))
    add("key:conflict_bucket", DS([H("A", bucket=CORE), H("A", bucket=SAT)]))
    add("key:conflict_ccy", DS([H("A", ccy="USD"), H("A", ccy="EUR")]))
    add("key:same_code_two_policies", DS([H("A", policy="P1", cost=3000.0), H("A", policy="P2", cost=3000.0)]))
    # 市值基準：完整
    add("mv:complete", DS([H("A"), H("B", ccy="TWD", units=100.0), H("C", bucket=SAT, ccy="EUR", units=20.0)], nav_all, FX_STD, basis=MV))
    add("mv:complete_off_band", DS([H("A", units=100.0), H("C", bucket=SAT, ccy="EUR", units=1.0)], nav_all, FX_STD, basis=MV))
    # 部分缺（分母不含缺類別；合計未涵蓋）
    add("mv:partial_fx_missing_core", DS([H("A"), H("B", bucket=SAT, ccy="TWD", units=100.0)], nav_all, [], basis=MV))
    add("mv:partial_nav_missing_core", DS([H("Z"), H("B", bucket=SAT, ccy="TWD", units=100.0)], nav_all, FX_STD, basis=MV))
    add("mv:partial_missing_sat", DS([H("B", ccy="TWD", units=100.0), H("A", bucket=SAT)], nav_all, [], basis=MV))
    add("mv:partial_missing_with_unclassified", DS([H("A"), H("B", bucket=SAT, ccy="TWD"), H("D", bucket=None, ccy="TWD")],
                                                   nav_all + [N("D", "2026-10-03", 8.0, "TWD")], [], basis=MV))
    # 已知差異：美元缺匯率、新臺幣有值 → 新臺幣類別 100.0%（現況照錄，不修）
    add("known_diff:usd_missing_twd_valued_twd_100pct", DS([H("A", bucket=CORE, ccy="USD"), H("B", bucket=SAT, ccy="TWD", units=100.0)],
                                                          nav_all, [], basis=MV, names=NAMES))
    add("known_diff:twd_100pct_with_eur_missing", DS([H("C", bucket=CORE, ccy="EUR"), H("B", bucket=SAT, ccy="TWD", units=50.0)],
                                                     nav_all, [FX(FX_USD, "2026-10-03", 30.0)], basis=MV))
    # 全缺：單一理由／多理由
    add("mv:all_missing_single_reason_fx", DS([H("A"), H("D", bucket=SAT)], nav_all, [], basis=MV))
    add("mv:all_missing_single_reason_nav", DS([H("Z"), H("Y", bucket=SAT)], nav_all, FX_STD, basis=MV))
    add("mv:all_missing_mixed_reasons", DS([H("A"), H("Z", bucket=SAT)], nav_all, [], basis=MV))
    add("mv:all_missing_mixed_reasons_reverse", DS([H("Z"), H("A", bucket=SAT)], nav_all, [], basis=MV))
    add("mv:all_missing_mixed_with_target_cat_no_holding", DS([H("A"), H("Z", bucket=SAT)], nav_all, [], basis=MV,
                                                              targets=TARGETS + [{"bucket": BOND, "weight_ratio": 0.0}],
                                                              names=NAMES + (BOND,), scenario=SCEN))
    add("mv:all_missing_mixed_no_scenario", DS([H("A"), H("Z", bucket=SAT)], nav_all, [], basis=MV, scenario=None))
    add("mv:all_missing_two_fx_keys", DS([H("A"), H("C", bucket=SAT, ccy="EUR")], nav_all, [], basis=MV))
    # 全過期
    last = {"Z": "2026-09-01", "Y": "2026-09-05"}
    add("mv:all_stale_new_shape", DS([H("Z"), H("Y", bucket=SAT)], nav_all, FX_STD, basis=MV, nav_not_ready=NNR(["Z", "Y"], 10, last)))
    add("mv:all_stale_new_shape_same_cat", DS([H("Z"), H("Y")], nav_all, FX_STD, basis=MV, nav_not_ready=NNR(["Z", "Y"], 10, last)))
    add("mv:all_stale_new_shape_reverse_order", DS([H("Y"), H("Z", bucket=SAT)], nav_all, FX_STD, basis=MV, nav_not_ready=NNR(["Z", "Y"], 10, last)))
    add("mv:all_stale_old_shape", DS([H("Z"), H("Y", bucket=SAT)], nav_all, FX_STD, basis=MV, nav_not_ready=NNR(["Z", "Y"], 10)))
    add("mv:stale_plus_nav_missing", DS([H("Z"), H("Q", bucket=SAT)], nav_all, FX_STD, basis=MV, nav_not_ready=NNR(["Z"], 10, {"Z": "2026-09-01"})))
    add("mv:stale_plus_fx_missing", DS([H("Z"), H("A", bucket=SAT)], nav_all, [], basis=MV, nav_not_ready=NNR(["Z"], 10, {"Z": "2026-09-01"})))
    add("mv:partial_stale_core_valued_sat", DS([H("Z"), H("B", bucket=SAT, ccy="TWD", units=100.0)], nav_all, FX_STD, basis=MV,
                                              nav_not_ready=NNR(["Z"], 10, {"Z": "2026-09-01"})))
    add("mv:partial_two_stale_same_cat_valued_other", DS([H("Z"), H("Y"), H("B", bucket=SAT, ccy="TWD", units=100.0)], nav_all, FX_STD, basis=MV,
                                                        nav_not_ready=NNR(["Z", "Y"], 10, last)))
    add("mv:stale_bad_shape", DS([H("A")], nav_all, FX_STD, basis=MV, nav_not_ready={"codes": ["A"]}))
    # 分母零／負
    add("denominator:all_zero_cost", DS([H("A", cost=0.0), H("C", bucket=SAT, cost=0.0)]))
    add("denominator:negative_total", DS([H("A", cost=-100.0), H("C", bucket=SAT, cost=50.0)]))
    add("denominator:zero_net", DS([H("A", cost=100.0), H("C", bucket=SAT, cost=-100.0)]))
    add("denominator:one_negative_one_positive_positive_total", DS([H("A", cost=-100.0), H("C", bucket=SAT, cost=300.0)]))
    add("denominator:tiny_positive", DS([H("A", cost=1e-300), H("C", bucket=SAT, cost=0.0)]))
    add("denominator:nan_value_mv", DS([H("A", units=NAN), H("B", bucket=SAT, ccy="TWD")], nav_all, FX_STD, basis=MV))
    add("denominator:zero_with_missing_mv", DS([H("B", ccy="TWD", units=0.0), H("A", bucket=SAT)], nav_all, [], basis=MV))
    # 略過列與略過分頁
    omitted = [{"tab": "保單甲", "row": 5, "fund_code": "A", "reasons": ["缺 bucket", "cost 非數字"]},
               {"tab": None, "row": None, "fund_code": None, "reasons": []}]
    tabs = [{"tab": "保單乙", "error": "讀取逾時"}, {"tab": "保單丙"}]
    add("omitted:rows_with_unclassified", DS(core2 + [H("C", bucket=None, cost=1.0)], skipped_holdings=omitted))
    add("omitted:rows_no_unclassified", DS(core2 + sat1, skipped_holdings=omitted))
    add("omitted:tabs_only", DS(core2 + sat1, skipped_tabs=tabs))
    add("omitted:rows_and_tabs", DS(core2 + sat1, skipped_holdings=omitted, skipped_tabs=tabs))
    add("omitted:empty_holdings_rows", DS([], skipped_holdings=omitted))
    add("omitted:empty_holdings_tabs", DS([], skipped_tabs=tabs))
    add("omitted:empty_holdings_both", DS([], skipped_holdings=omitted, skipped_tabs=tabs))
    add("omitted:bad_tab_name", DS(core2, skipped_tabs=[{"tab": "  "}]))
    add("omitted:bad_rows_shape", DS(core2, skipped_holdings="x"))
    add("omitted:target_unset_with_rows", DS(core2, targets=None, skipped_holdings=omitted))
    add("omitted:tolerance_none_with_tabs", DS(core2, tol=None, skipped_tabs=tabs))
    # 取數失敗
    for table in ("holding", "nav", "market_indicator", "user_setting", "policy"):
        add(f"error:{table}_cost", DS(core2 + sat1, errors={table: f"HTTP 503 {table}"}))
        add(f"error:{table}_mv", DS([H("A"), H("B", bucket=SAT, ccy="TWD")], nav_all, FX_STD, basis=MV, errors={table: f"HTTP 503 {table}"}))
    add("error:holding_and_nav_mv", DS([H("A")], nav_all, FX_STD, basis=MV, errors={"holding": "H", "nav": "N"}))
    add("error:unknown_table_key", DS(core2, errors={"weird": "x"}))
    # 試算（ALO-3）
    add("scenario:effective_mixed", DS(core2 + sat1, scenario=SCEN))
    add("scenario:overflow_only", DS(core2 + sat1, scenario=[{"bucket": SAT, "amount_twd": -999999.0}]))
    add("scenario:zero_total", DS([H("A", cost=100.0), H("C", bucket=SAT, cost=100.0)],
                                  scenario=[{"bucket": CORE, "amount_twd": -100.0}, {"bucket": SAT, "amount_twd": -100.0}]))
    add("scenario:accumulates_per_bucket", DS(core2 + sat1, scenario=[{"bucket": CORE, "amount_twd": 100.0}, {"bucket": CORE, "amount_twd": -50.0}]))
    add("scenario:with_missing_category_mv", DS([H("A"), H("B", bucket=SAT, ccy="TWD", units=100.0)], nav_all, [], basis=MV, scenario=SCEN))
    add("scenario:with_unclassified", DS(core2 + [H("C", bucket=None, cost=1000.0)], scenario=[{"bucket": UNCLASSIFIED_NAME, "amount_twd": 5.0}]))
    add("scenario:target_none_weight_row", DS(core2 + sat1, targets=[{"bucket": CORE, "weight_ratio": None}, {"bucket": SAT, "weight_ratio": 0.4}], scenario=SCEN))
    add("scenario:placeholder_upstream_notarget", DS(core2 + sat1, targets=None, scenario=SCEN))
    add("scenario:placeholder_upstream_nobasis", DS(core2 + sat1, basis=None, scenario=SCEN))
    add("scenario:save_error", DS(core2 + sat1, scenario=SCEN, save_errors={"alo_scenario_input": "寫入衝突"}))
    # 設定缺列／壞形狀
    add("settings:missing_row_key", DS(core2 + sat1, raw_settings=[]))
    add("settings:fetch_error_empty_rows", DS(core2 + sat1, raw_settings=[], errors={"user_setting": "boom"}))
    # 其他幣別
    add("mv:jpy_ok", DS([H("J", ccy="JPY", bucket=CORE)], [N("J", "2026-10-03", 100.0, "JPY")], [FX(FX_JPY, "2026-10-03", 0.2)], basis=MV))
    add("mv:fx_obs_later_than_nav", DS([H("A")], nav_all, [FX(FX_USD, "2026-10-04", 31.0)], basis=MV))
    add("mv:fx_same_day_two_rows", DS([H("A")], nav_all, [FX(FX_USD, "2026-10-03", 31.0), FX(FX_USD, "2026-10-03", 99.0)], basis=MV))
    add("mv:ccy_lowercase_error", DS([H("A")], [N("A", "2026-10-03", 10.0, "usd")], FX_STD, basis=MV))
    add("mv:twd_nav_with_no_fx_table_rows", DS([H("B", ccy="TWD", units=100.0)], nav_all, [], basis=MV))
    return cases


UNCLASSIFIED_NAME = "未分類"


def run_alo2_family(ns):
    out = {}
    for label, ds in _alo2_cases().items():
        alo2_call = call(ns["_build_alo2"], ds)
        entry = {"alo2": alo2_call}
        entry["fx_missing_for_mv"] = call(ns["_fx_missing_for_mv"], ds)
        if "ok" in alo2_call:
            alo2 = ns["_build_alo2"](ds)
            entry["conclusion_light"] = call(ns["conclusion_light"], alo2)
            entry["alo0"] = call(ns["_build_alo0"], alo2)
            entry["alo3"] = call(ns["_build_alo3"], ds, alo2)
        entry["alo6"] = call(ns["_build_alo6"], ds)
        model = call(ns["build_page_model"], ds)
        entry["page_model_sha256"] = hashlib.sha256(dumps(model).encode("utf-8")).hexdigest()
        entry["page_model_ok"] = "ok" in model
        if "raise" in model:
            entry["page_model_raise"] = model["raise"]
        out[label] = entry
    return out


# ───────────────────────── 矩陣 ─────────────────────────

TARGET_FUNCTIONS = ("basis_value_with_key", "basis_value", "_category_values", "_build_alo2", "_build_alo0",
                    "conclusion_light", "_build_alo3", "_build_alo6", "_fx_missing_for_mv", "build_page_model")


def run_matrix(ns):
    """對 `ns`（`ui_v2.alo.logic` 的命名空間 dict）跑完整矩陣 → 可序列化結構。"""
    return {"basis_value": run_basis(ns), "category_values": run_category_values(ns), "alo2_family": run_alo2_family(ns)}


def counts():
    return {"basis_value": len(_basis_cases()), "category_values": len(_cat_cases()), "alo2_family": len(_alo2_cases())}


def instrumented_namespace(ns):
    """回 (包過的命名空間 dict, 呼叫計數 dict)：每個 TARGET_FUNCTIONS 都包一層計數（防空掃用）。
    ⚠️ 只換矩陣取名字用的那份 dict；`ns` 本身（函式的 globals）不動，所以函式彼此的內部呼叫不計。"""
    hits = {name: 0 for name in TARGET_FUNCTIONS}
    wrapped = dict(ns)
    for name in TARGET_FUNCTIONS:
        def make(fn, key):
            def inner(*a, **k):
                hits[key] += 1
                return fn(*a, **k)
            return inner
        wrapped[name] = make(ns[name], name)
    return wrapped, hits


def header(root, commit, tree):
    root = pathlib.Path(root)
    return {
        "recorder": RECORDER_NAME,
        "baseline_commit": commit,
        "baseline_tree": tree,
        "python": sys.version.split()[0],
        "blob_hashes": {rel: git_blob_hash(root / rel) for rel in FEEDING_FILES},
        "counts": counts(),
        "note": "凍結現況；含已知差異（缺匯率類別旁的有值類別顯示 100.0%），不得以修改後的程式重錄。",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--commit", required=True)
    parser.add_argument("--tree", required=True)
    args = parser.parse_args(argv)
    setup_path()
    ns = live_namespace()
    doc = {"header": header(_ROOT, args.commit, args.tree), **encode_matrix(run_matrix(ns))}
    pathlib.Path(args.out).write_text(dumps(doc), encoding="utf-8")
    print(f"wrote {args.out}", counts())


if __name__ == "__main__":
    main()
