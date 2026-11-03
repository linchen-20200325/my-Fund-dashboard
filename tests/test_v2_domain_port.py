# -*- coding: utf-8 -*-
"""2026-11-02 ui_v2 領域計算 PORT 到 `services/v2_domain/` 的守衛（`docs/v2/80` 第 3.2、3.3 (a)(b)、8、13、14 節；
客戶 `DEC-2026-11-02-05` NG-2 A：ui_v2 行為不變、搬遷批需獨立稽核）。

三組守衛：
(a) **等價**：搬遷前的原始實作（`git show a7f120c9:<檔>`，在記憶體裡 `exec` 進一個隔離的 namespace，不寫任何檔）
    與搬遷後 ui_v2 原位置的公開符號、以及 L2 本體，對一大組輸入（None、空、NaN、單點、負數、極值、重複鍵、
    缺欄、型別不合、各種例外）逐案比對「回傳值或例外型別＋訊息」完全相同。
    另把整組結果的摘要（sha256）釘成常數：CI 的淺層 clone 拿不到 `a7f120c9` 時，仍以摘要比對；
    拿得到時，另驗「摘要確實是由原始實作算出來的」。
(b) **分層**：`services/v2_domain` 只 import fail-closed 白名單（標準庫純運算＋`shared`＋同套件），
    不碰 streamlit／`ui`／`ui_v2`／`ui_v3`／網路／檔案；非 docstring 的字串常數不得含中文（畫面字留在 ui_v2）。
    另驗 ui_v2 碰 `services.v2_domain` 的只有 `ui_v2/v2_domain_shim.py` 一檔（import 守衛逐檔白名單）。
(c) **`NAV_NOT_READY_DAYS` 單一來源**：全 repo（ui_v2／ui_v3／services／shared）只有一處以字面值給它值、值為 10。
    ⚠️ 本批**未**把它搬進 `services/v2_domain`：`tests/ui_v2/test_alo_live_logic.py::test_10天門檻_兩頁引用同一個共用常數_值為10`
    鎖定唯一的給值處必須是 `ui_v2/thresholds.py` 的字面值 10 —— 這是 C 類 ownership lock
    （`tests/ui_v2/test_alo_live_logic.py::test_10天門檻_兩頁引用同一個共用常數_值為10`）；放寬需總管／客戶裁示；本批不改。
    裁示放寬後，把下方 `_NAV_DAYS_OWNER` 改成新住址即可。
"""

from __future__ import annotations

import ast
import decimal
import hashlib
import importlib.util
import pathlib
import subprocess
from datetime import date, timedelta, timezone

import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:  # 本機以 `--noconftest` 跑；pytest 不會自動把 repo 根放進 sys.path
    sys.path.insert(0, str(_ROOT))

from services.v2_domain import deviation as d_deviation  # noqa: E402
from services.v2_domain import freshness as d_freshness  # noqa: E402
from services.v2_domain import holdings as d_holdings  # noqa: E402
from services.v2_domain import nav_metrics as d_nav  # noqa: E402
from services.v2_domain import periods as d_periods  # noqa: E402
from services.v2_domain import rule_filter as d_rule  # noqa: E402
from ui_v2.alo import logic as new_alo  # noqa: E402
from ui_v2.exp import logic as new_exp  # noqa: E402
from ui_v2.hld import logic as new_hld  # noqa: E402
from ui_v2.mkt import chart as new_chart  # noqa: E402
from ui_v2.mkt import logic as new_mkt  # noqa: E402

_BASE = "a7f120c9"   # 搬遷前的 main（#1122 合併點）

NAN = float("nan")
INF = float("inf")


# ═══════════════════════ 搬遷前原始實作（記憶體內載入） ═══════════════════════


def _git_source(rel):
    try:
        out = subprocess.run(["git", "show", f"{_BASE}:{rel}"], cwd=_ROOT, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8")


_ORIG_CACHE = {}


def _orig(rel, package):
    """把搬遷前的模組原始碼 exec 進隔離 namespace（不進 sys.modules、不寫檔）。拿不到 → None。"""
    if rel not in _ORIG_CACHE:
        source = _git_source(rel)
        if source is None:
            _ORIG_CACHE[rel] = None
        else:
            ns = {"__name__": "_v2_domain_port_orig." + rel.replace("/", ".")[:-3], "__package__": package}
            exec(compile(source, f"<{_BASE}:{rel}>", "exec"), ns)   # noqa: S102 — 只執行 repo 自己的歷史版本
            _ORIG_CACHE[rel] = ns
    return _ORIG_CACHE[rel]


def _need(rel, package):
    ns = _orig(rel, package)
    if ns is None:
        pytest.skip(f"拿不到 {_BASE}:{rel}（淺層 clone）；等價改由摘要常數守住（見 test_摘要常數_*）")
    return ns


# ═══════════════════════ 比對工具 ═══════════════════════


def _canon(value):
    """可比較、可摘要的正規形：保留 dict 插入順序與 list 順序；set 排序（不受雜湊種子影響）；
    浮點以 repr 比（NaN 才比得出相等）；例外物件以 (型別名, 訊息) 比。"""
    if isinstance(value, BaseException):
        return ("EXC", type(value).__name__, str(value))
    if isinstance(value, float):
        return ("float", repr(value))
    if isinstance(value, dict):
        return ("dict", tuple((_canon(k), _canon(v)) for k, v in value.items()))
    if isinstance(value, (set, frozenset)):
        return (type(value).__name__, tuple(sorted((_canon(v) for v in value), key=repr)))
    if isinstance(value, (list, tuple)):
        return (type(value).__name__, tuple(_canon(v) for v in value))
    return (type(value).__name__, repr(value))


def _call(fn, *args, **kwargs):
    try:
        return ("ok", _canon(fn(*args, **kwargs)))
    except Exception as exc:  # noqa: BLE001 — 例外本身就是要比對的行為
        return ("raise", _canon(exc))


def _pin_view(value):
    """摘要用的形狀：Python 內建例外的英文訊息在不同直譯器版本可能不同（CI 跑 3.11），摘要只留型別；
    本 repo 自己組的中文訊息（含中文字元者）照留。逐案比對（非摘要）仍比完整訊息。"""
    if isinstance(value, tuple):
        if len(value) == 3 and value[0] == "EXC":
            return ("EXC", value[1], value[2] if _has_cjk(value[2]) else None)
        return tuple(_pin_view(v) for v in value)
    if isinstance(value, list):
        return [_pin_view(v) for v in value]
    return value


def _digest(results) -> str:
    return hashlib.sha256(repr(_pin_view(results)).encode("utf-8")).hexdigest()[:16]


def _copy_rows(rows):
    return [dict(r) for r in rows]


# ═══════════════════════ 輸入組 ═══════════════════════

_NAV_SERIES = [
    None, [], (), [1.0], [0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 0.0, 2.0], [1e-13, 1.0], [1.0, 1e-13],
    [10.0, 11.0], [10.0, 11.0, 9.0, 12.0], [10, 11, 9, 12], (10.0, 12.5, 11.0),
    [-1.0, -2.0, -3.0], [-1.0, 1.0], [5.0] * 10, [NAN, 1.0, 2.0], [1.0, NAN, 2.0], [1.0, 2.0, NAN],
    [INF, 1.0], [1.0, INF], [1e308, 1e308, 1e-308], [1e-300, 1e300, 1e-300],
    [100.0 + 0.37 * i - (i % 7) * 1.9 for i in range(300)],
    [1.0, None], [None, 1.0], ["1", "2"], [decimal.Decimal("1"), decimal.Decimal("2")],
]

_HOLD = {"policy_id": "P1", "fund_code": "F1", "units_shares": 10.0, "cost_orig_ccy": 100.0, "cost_twd": 3000.0,
         "ccy": "USD", "bucket": "核心", "opened_on": "2024-01-01", "last_synced_at": "2026-10-01T00:00:00Z",
         "holding_id": "h1", "fund_name": "甲"}


def _h(**over):
    row = dict(_HOLD)
    row.update(over)
    return row


_HOLDING_CASES = [
    [],
    [_h()],
    [_h(), _h(holding_id="h2")],
    [_h(), _h(holding_id="h2", fund_name="乙")],                              # 名稱不同照加（hld）
    [_h(), _h(fund_code=" F1 ", holding_id="h2")],                            # hld 去空白、alo 不去
    [_h(), _h(policy_id="P2", holding_id="h2"), _h(holding_id="h3")],
    [_h(), _h(ccy="EUR", holding_id="h2")],
    [_h(), _h(bucket="衛星", holding_id="h2")],
    [_h(), _h(bucket="衛星", ccy="EUR", opened_on="2020-01-01", holding_id="h2")],
    [_h(), _h(last_synced_at=None, holding_id="h2")],
    [_h(units_shares=NAN), _h(holding_id="h2")],
    [_h(units_shares=-5.0), _h(holding_id="h2", units_shares=5.0)],
    [_h(cost_twd=None), _h(holding_id="h2")],                                  # None + float → TypeError
    [_h(), {k: v for k, v in _h(holding_id="h2").items() if k != "cost_twd"}],  # 缺加總欄 → KeyError
    [{k: v for k, v in _h().items() if k != "policy_id"}],                     # 缺鍵欄（hld .get → None；alo KeyError）
    [_h(policy_id=1, fund_code=2), _h(policy_id=1, fund_code=2, holding_id="h2")],
    [_h(fund_code=None), _h(fund_code=None, holding_id="h2")],
    [_h(units_shares=1e308), _h(units_shares=1e308, holding_id="h2")],
]


# ═══════════════════════ (a) 等價：hld ═══════════════════════


def _hld_nav_results(mod_return, mod_drawdown, mod_vol):
    return [(_call(mod_return, s), _call(mod_drawdown, s), _call(mod_vol, s)) for s in _NAV_SERIES]


def _hld_merge_results(merge):
    out = []
    for rows in _HOLDING_CASES:
        before = _canon(rows)
        got = _call(merge, rows)
        out.append((got, _canon(rows) == before))    # 不改輸入
    return out


def _metric(code, nodes, *, nav_missing=False, nav_not_ready=None, ccy="USD"):
    metric = {"_fund_code": code, "fund_name": f"基金{code}", "_ccy": ccy, "nav_missing": nav_missing}
    if nav_not_ready is not None:
        metric["nav_not_ready"] = nav_not_ready
    metric.update(nodes)
    return metric


def _node(mod, state, raw=None, text="x"):
    return {"_state": state, "_raw": raw, "text": text}


def _deviation_cases(mod):
    ok, miss, biz, err = mod["STATE_OK"], mod["STATE_MISSING"], mod["STATE_BIZ"], mod["STATE_ERROR"]
    names = ("最大回撤", "配息佔淨值比", "區間報酬率", "期間波動")

    def full(code, state, raw, **kw):
        return _metric(code, {n: _node(mod, state, raw, f"{n}{raw}") for n in names}, **kw)

    rules_all = [{"indicator": "最大回撤", "direction": "低於", "value": -10.0},
                 {"indicator": "區間報酬率", "direction": "高於", "value": 5.0},
                 {"indicator": "期間波動", "direction": "低於", "value": 0.0},
                 {"indicator": "配息佔淨值比", "direction": "高於", "value": -1e9}]
    rules_odd = [{"indicator": "不存在的指標", "direction": "低於", "value": 1.0},
                 {"indicator": "最大回撤", "direction": "持平", "value": 1.0},
                 {"indicator": "最大回撤", "direction": "高於"}]                   # 缺 value
    metrics_mix = [full("B", ok, -20.0), full("A", ok, 7.0), full("C", miss, None, nav_missing=True),
                   full("D", miss, None, nav_missing=True, nav_not_ready=True), full("E", miss, None),
                   full("F", biz, None), full("G", err, None), full("H", ok, -10.0), full("I", ok, NAN),
                   full("J", ok, INF), full("K", ok, -INF)]
    err_and_miss = _metric("Z", {"最大回撤": _node(mod, err), "區間報酬率": _node(mod, miss),
                                 "期間波動": _node(mod, biz), "配息佔淨值比": _node(mod, ok, 1.0)},
                           nav_missing=True)
    return [
        ([], rules_all),
        (metrics_mix, []),
        (metrics_mix, rules_all),
        (metrics_mix, rules_odd[:2]),
        ([full("A", ok, -20.0)], rules_odd),                       # 缺 value 的方向是「高於」→ KeyError
        ([full("A", ok, 2.0)], [rules_odd[1], rules_odd[0]]),      # 未知方向 → 不讀 value、不超出
        ([err_and_miss], rules_all),                                # 取數失敗優先
        ([full("A", None, None)], rules_all),                       # 未排名狀態 → 照舊拿 None 去比 → TypeError
        ([full("A", ok, None)], rules_all),
        ([full("A", ok, -20.0), full("A", ok, -30.0)], rules_all),  # 同代碼兩列
        ([_metric("A", {})], rules_all),                            # 缺指標節點 → KeyError
    ]


def _hld_deviation_results(mod):
    out = []
    for metrics, rules in _deviation_cases(mod):
        out.append(_call(mod["deviation_rows"], metrics, rules))
    for rule in ({"direction": "低於", "value": 1.0}, {"direction": "高於", "value": 1.0},
                 {"direction": "持平"}, {"direction": "低於"}, {"value": 1.0}):
        for value in (0.0, 1.0, 2.0, NAN, None, "1"):
            out.append(_call(mod["_breaches"], rule, value))
    return out


def _new_hld_ns():
    return vars(new_hld)


def test_hld_三個區間指標_L2本體與搬遷前逐案相同():
    orig = _need("ui_v2/hld/logic.py", "ui_v2.hld")
    want = _hld_nav_results(orig["return_pct"], orig["drawdown_pct"], orig["vol_pct"])
    assert _hld_nav_results(d_nav.return_pct, d_nav.drawdown_pct, d_nav.vol_pct) == want
    assert _hld_nav_results(new_hld.return_pct, new_hld.drawdown_pct, new_hld.vol_pct) == want
    assert new_hld.return_pct is d_nav.return_pct and new_hld.vol_pct is d_nav.vol_pct   # re-export 同一物件
    assert orig["TRADING_DAYS_PER_YEAR"] == new_hld.TRADING_DAYS_PER_YEAR == d_nav.TRADING_DAYS_PER_YEAR == 252


def test_hld_同鍵合併_與搬遷前逐案相同_含例外型別與原字訊息():
    orig = _need("ui_v2/hld/logic.py", "ui_v2.hld")
    want = _hld_merge_results(orig["merge_same_key_holdings"])
    assert _hld_merge_results(new_hld.merge_same_key_holdings) == want
    assert orig["HOLDING_SUM_COLUMNS"] == new_hld.HOLDING_SUM_COLUMNS
    assert orig["HOLDING_SAME_COLUMNS"] == new_hld.HOLDING_SAME_COLUMNS
    assert any(r[0][0] == "raise" and r[0][1][1] == "ValueError" for r in want)   # 真的走到衝突那一支


def test_hld_偏離列_與搬遷前逐案相同():
    orig = _need("ui_v2/hld/logic.py", "ui_v2.hld")
    want = _hld_deviation_results(orig)
    got = _hld_deviation_results(_new_hld_ns())
    assert len(got) == len(want)
    for i, (g, w) in enumerate(zip(got, want)):
        assert g == w, i
    kinds = {r[0] for r in want}
    assert kinds == {"ok", "raise"}                                       # 正常與例外兩支都走到


# ═══════════════════════ (a) 等價：alo ═══════════════════════


def _alo_dataset(holdings, nav=(), fx=()):
    return {"holding": _copy_rows(holdings), "nav": list(nav), "market_indicator": list(fx)}


_NAV_ROWS = [
    {"fund_code": "F1", "nav_date": "2026-10-01", "nav_orig_ccy": 10.0, "ccy": "USD"},
    {"fund_code": "F1", "nav_date": "2026-10-03", "nav_orig_ccy": 11.0, "ccy": "USD"},
    {"fund_code": "F1", "nav_date": "2026-10-03", "nav_orig_ccy": 99.0, "ccy": "USD"},   # 同日第二列
    {"fund_code": "F2", "nav_date": "2026-09-30", "nav_orig_ccy": 20.0, "ccy": "TWD"},
    {"fund_code": "F3", "nav_date": "2026-10-02", "nav_orig_ccy": 5.0, "ccy": "EUR"},
]
_FX_ROWS = [
    {"indicator_key": "fx_twd_per_usd", "obs_date": "2026-10-02", "value_num": 32.0},
    {"indicator_key": "fx_twd_per_usd", "obs_date": "2026-10-03", "value_num": 32.5},
    {"indicator_key": "fx_twd_per_usd", "obs_date": "2026-10-04", "value_num": 33.0},   # 晚於淨值日，不得用
    {"indicator_key": "fx_twd_per_eur", "obs_date": "2026-10-05", "value_num": 35.0},
    {"indicator_key": "fx_twd_per_usd", "obs_date": "2026-10-03", "value_num": 31.0},   # 同日第二列
]


def _alo_results(mod):
    out = []
    for rows in _HOLDING_CASES:
        out.append(_call(mod["aggregated_holdings"], _alo_dataset(rows)))
    for code in ("F1", "F2", "F3", "F9", None):
        out.append(_call(mod["latest_nav"], _alo_dataset([], _NAV_ROWS), code))
        out.append(_call(mod["latest_nav"], _alo_dataset([], []), code))
    for day in ("2026-10-01", "2026-10-02", "2026-10-03", "2026-10-09", ""):
        for key in (None, "fx_twd_per_usd", "fx_twd_per_eur", "fx_twd_per_jpy"):
            args = (_alo_dataset([], fx=_FX_ROWS), day) + (() if key is None else (key,))
            out.append(_call(mod["fx_for_date"], *args))
    out.append(_call(mod["fx_for_date"], _alo_dataset([], fx=[{"indicator_key": "fx_twd_per_usd",
                                                                   "obs_date": None, "value_num": 1.0}]), "2026-10-01"))
    for bucket in (None, "", "核心", "衛星", "未分類", "其他", 0):
        for names in (None, (), ("核心", "衛星"), ["核心", "未分類"], ("",), "核心衛星"):
            out.append(_call(mod["category_of"], {"bucket": bucket}, names))
    out.append(_call(mod["category_of"], {}, ("核心",)))
    for diff in (0.0, 0.05, -0.05, 0.05 + 1e-10, 0.0500000001, 0.06, -0.06, NAN, INF, -INF, 5):
        for tol in (0.05, 0.0, NAN, INF, 5):
            out.append(_call(mod["exceeds"], diff, tol))
    out.append(_call(mod["exceeds"], None, 0.05))
    for targets in (None, [], [{"weight_ratio": 0.6}, {"weight_ratio": 0.4}], [{"weight_ratio": None}],
                    [{"weight_ratio": 0.1}, {"weight_ratio": None}, {"weight_ratio": 0.2}],
                    [{"weight_ratio": NAN}], [{"weight_ratio": -0.5}, {"weight_ratio": 1.5}], [{}]):
        out.append(_call(mod["target_sum"], targets))
    # basis_value 整支（本頁包裝，內部改用 L2 查表）：成本／市值，新臺幣、美元、歐元、缺淨值、缺匯率
    nav_ds = _alo_dataset([], _NAV_ROWS, _FX_ROWS)
    for holding in (_h(fund_code="F1"), _h(fund_code="F2"), _h(fund_code="F3"), _h(fund_code="F9"),
                    _h(fund_code="F1", units_shares=NAN), _h(fund_code="F1", cost_twd="12")):
        for basis in (mod["BASIS_COST"], mod["BASIS_MV"]):
            out.append(_call(mod["basis_value"], nav_ds, holding, basis))
    return out


def test_alo_同鍵加總_查表_類別_容許帶_目標合計_與搬遷前逐案相同():
    orig = _need("ui_v2/alo/logic.py", "ui_v2.alo")
    want = _alo_results(orig)
    got = _alo_results(vars(new_alo))
    assert len(got) == len(want)
    for i, (g, w) in enumerate(zip(got, want)):
        assert g == w, i
    assert new_alo.exceeds is d_holdings.exceeds and new_alo.target_sum is d_holdings.target_sum


# ═══════════════════════ (a) 等價：exp ═══════════════════════

try:   # pandas 的 NA／NaT 是 is_missing 的一支；本環境若沒有 pandas 就只少那兩個輸入
    import pandas as _pd
    _PANDAS_VALUES = [_pd.NA, _pd.NaT]
except Exception:  # noqa: BLE001
    _PANDAS_VALUES = []


class _Weird:
    """比較會炸、轉 float 也會炸的物件。"""

    def __ne__(self, other):
        raise RuntimeError("no compare")

    def __repr__(self):
        return "<Weird>"

    def __str__(self):
        return "weird"


_LEFTS = [None, "", "  ", "abc", "1.5", " 2 ", "-3", "nan", "inf", "2026-10-01", "2026-10-31", 0, 1, -1, 1.5,
          NAN, INF, -INF, True, decimal.Decimal("1.25"), decimal.Decimal("NaN"), decimal.Decimal("sNaN"),
          10 ** 400, [], {}, (1,), _Weird()] + _PANDAS_VALUES
_RIGHTS = ["1", "1.5", "", "abc", "nan", "2026-10-15", 10 ** 400]
_OPS = ["等於", "不等於", "大於", "小於", "早於或等於", "晚於", "相等", "", None, ["大於"]]


def _exp_compare_results(mod):
    out = []
    for left in _LEFTS:
        out.append(_call(mod["is_missing"], left))
        for op in _OPS:
            for right in _RIGHTS:
                out.append((_call(mod["compare_tristate"], left, op, right), _call(mod["_compare"], left, op, right)))
    return out


_ROWS = [
    {"fund_code": "A", "ccy": "USD", "mgmt_fee_rate_pct": 1.5, "inception_on": "2010-01-01"},
    {"fund_code": "B", "ccy": None, "mgmt_fee_rate_pct": "abc", "inception_on": "2020-06-30"},
    {"fund_code": "C", "ccy": "TWD", "mgmt_fee_rate_pct": NAN, "inception_on": ""},
    {"fund_code": "D", "ccy": "USD", "inception_on": "2015-01-01"},
    {"fund_code": "B", "ccy": "USD", "mgmt_fee_rate_pct": 0.5, "inception_on": "2001-01-01"},   # 重複代碼
]
_RULE_SETS = [
    [],
    [{"field": "ccy", "op": "等於", "value": "USD"}],
    [{"field": "ccy", "op": "等於", "value": ""}, {"field": "mgmt_fee_rate_pct", "op": "小於", "value": "2"}],
    [{"field": "mgmt_fee_rate_pct", "op": "大於", "value": "abc"}, {"field": "ccy", "op": "不等於", "value": "TWD"}],
    [{"field": "inception_on", "op": "早於或等於", "value": "2015-12-31"},
     {"field": "ccy", "op": "等於", "value": "USD"}, {"field": "mgmt_fee_rate_pct", "op": "大於", "value": "1"}],
    [{"field": "inception_on", "op": "晚於", "value": "2000-01-01"}, {"field": "nope", "op": "等於", "value": "x"}],
    [{"field": "ccy", "op": "相等", "value": "USD"}],                                  # 不認得的方向 → raise
    [{"field": "ccy", "op": "等於", "value": "XXX"}, {"field": "ccy", "op": "相等", "value": "USD"}],  # 無列可比 → 不 raise
    [{"field": "ccy", "op": "等於", "value": "  "}],
    [{"field": "ccy", "op": "等於"}],                                                    # 沒有 value 鍵 → 不生效
    [{"op": "等於", "value": "USD"}],                                                    # 沒有 field 鍵 → KeyError
]


def _exp_rules_results(mod):
    out = []
    for rules in _RULE_SETS:
        for rows in (_ROWS, [], _ROWS[:1]):
            out.append(_call(mod["apply_rules_tristate"], list(rows), rules))
            out.append(_call(mod["apply_rules"], list(rows), rules))
        for rule in rules:
            out.append(_call(mod["rule_is_effective"], rule))
    for rule in ({"value": 0}, {"value": None}, {"value": " "}, {}, {"value": NAN}):
        out.append(_call(mod["rule_is_effective"], rule))
    return out


def test_exp_缺值判定與三態比較_與搬遷前逐案相同():
    orig = _need("ui_v2/exp/logic.py", "ui_v2.exp")
    want = _exp_compare_results(orig)
    got = _exp_compare_results(vars(new_exp))
    assert len(got) == len(want)
    for i, (g, w) in enumerate(zip(got, want)):
        assert g == w, i
    assert orig["KNOWN_OPERATORS"] == new_exp.KNOWN_OPERATORS
    assert new_exp.UnspecifiedComparison.__name__ == "UnspecifiedComparison"


def test_exp_逐條累計篩選_與搬遷前逐案相同():
    orig = _need("ui_v2/exp/logic.py", "ui_v2.exp")
    want = _exp_rules_results(orig)
    got = _exp_rules_results(vars(new_exp))
    assert len(got) == len(want)
    for i, (g, w) in enumerate(zip(got, want)):
        assert g == w, i


def test_exp_回傳的條件物件是呼叫端傳進來的同一個():
    rules = [{"field": "ccy", "op": "等於", "value": "USD"}]
    steps, listed, _undet = new_exp.apply_rules_tristate(_ROWS, rules)
    assert steps[0][0] is rules[0] and all(any(r is row for row in _ROWS) for r in listed)


# ═══════════════════════ (a) 等價：mkt ═══════════════════════


def _pts(*pairs):
    return [{"obs_date": d, "value_num": v} for d, v in pairs]


_POINT_CASES = [
    [],
    _pts(("2026-10-01", None)),
    _pts(("2026-10-01", NAN), ("2026-10-02", "1")),
    _pts(("2026-10-01", 1.0)),
    _pts(("2025-10-01", 1.0), ("2026-10-01", 2.0)),
    _pts(("2026-10-01", 2.0), ("2025-10-01", 1.0), ("2026-04-01", None), ("2026-07-01", True)),
    _pts(("2026-03-31", 1.0), ("2026-02-28", 1.5), ("2026-01-01", 3.0), ("2025-12-31", 4.0)),
    _pts(("2023-09-30", 1.0), ("2026-09-30", 2.0), ("2024-02-29", 3.0), ("2026-09-29", INF)),
    _pts(*[((date(2023, 1, 1) + timedelta(days=i)).isoformat(), float(i % 11) if i % 5 else None)
           for i in range(0, 1400, 3)]),
    [{"obs_date": "2026-10-01"}],                                                     # 沒有 value_num 鍵
    _pts(("2026-10-01", 1.0), ("2026-10-01", 2.0)),                                    # 同日兩點
    [{"value_num": 1.0}],                                                             # 沒有 obs_date → KeyError
    _pts(("not-a-date", 1.0)),                                                        # 日期格式壞
]


def _mkt_results(chart_ns, logic_ns):
    out = []
    for points in _POINT_CASES:
        for period in ("3M", "6M", "1Y", "3Y", "2Y", "", None):
            out.append(_call(chart_ns["slice_period"], [dict(p) for p in points], period))
    out.append(_call(chart_ns["slice_period"], [], ["1Y"]))                         # 不可雜湊 → TypeError
    for day, months in ((date(2026, 3, 31), 1), (date(2024, 2, 29), 12), (date(2026, 1, 15), 36),
                        (date(2026, 12, 31), 0), (date(1, 2, 1), 1)):
        out.append(_call(chart_ns["months_back"], day, months))
    taipei = timezone(timedelta(hours=8))
    for obs, fetched in (("2026-10-01", "2026-10-02T03:00:00Z"), ("2026-10-01", "2026-10-01T20:00:00+00:00"),
                         ("2026-10-05", "2026-10-01T00:00:00Z"), ("2026-10-01", "2026-10-02T03:00:00"),
                         ("2026-10-01", "bad"), ("bad", "2026-10-02T03:00:00Z"), ("2026-10-01", "2026-10-02")):
        for tz in (None, taipei, timezone.utc):
            out.append(_call(logic_ns["delay_days"], obs, fetched, tz=tz))
    return out


def test_mkt_期間切片與延遲日數_與搬遷前逐案相同():
    orig_chart = _need("ui_v2/mkt/chart.py", "ui_v2.mkt")
    orig_logic = _need("ui_v2/mkt/logic.py", "ui_v2.mkt")
    want = _mkt_results(orig_chart, orig_logic)
    got = _mkt_results(vars(new_chart), vars(new_mkt))
    assert len(got) == len(want)
    for i, (g, w) in enumerate(zip(got, want)):
        assert g == w, i
    for name in ("PERIODS", "PERIOD_MONTHS", "DEFAULT_PERIOD", "STATUS_OK", "STATUS_EMPTY", "STATUS_INSUFFICIENT",
                 "TEXT_INSUFFICIENT", "TEXT_EMPTY"):
        assert orig_chart[name] == getattr(new_chart, name), name
    assert {p: orig_chart["availability"](_POINT_CASES[8])[p] for p in d_periods.PERIODS} \
        == new_chart.availability(_POINT_CASES[8])


# ═══════════════════════ (a) 摘要常數（淺層 clone 時的等價守衛） ═══════════════════════
# 這些摘要由搬遷前原始實作（a7f120c9）對上面同一組輸入算出；拿得到原始碼時 test_摘要常數_由原始實作算出 另行驗證。

_PINNED = {
    "alo": "ba392ed5e09663b3",
    # 依「本環境有沒有 pandas」各釘一個（見下方 `_PANDAS_MODE`）；兩個值都由原始實作 a7f120c9 算出。
    "exp_compare": {"pandas": "192bf4e68238e9bc", "no_pandas": "40e1cc53c9167aff"},
    "exp_rules": "10cc4aa6a7b4d2eb",
    "hld_deviation": "0f7f2ad7e16c98ce",
    "hld_merge": "dd37fe7bc27ddae6",
    # 依直譯器的浮點 sum() 模式各釘一個（見下方 `_SUM_MODE`）；兩個值都由原始實作 a7f120c9 在各該直譯器算出。
    "hld_nav": {"compensated": "24b7473258ea79a9", "naive": "eb5608866323b376"},
    "mkt": "d6aa40076da8b713",
}

# Python 3.12 起內建 `sum()` 對浮點改用補償求和（Neumaier；3.12 What's New），3.11 是逐項相加。
# `vol_pct` 用 `sum()` 求平均與變異數，於是 300 點那一組輸入的期間波動在兩種直譯器差最後一個 ulp
# （3.11：54.77718607978292；3.13：54.777186079782915）—— 這是直譯器內建算術的差，不是本批的行為改變
# （同一直譯器下原始實作與搬遷後實作逐位元相同；CI 跑 3.11）。處置：不放寬比對（仍逐位元比 repr），
# 改依「這個直譯器的 sum() 是哪一種」挑對應的摘要；特徵偵測用 3.12 What's New 的同一個例子。
_SUM_MODE = "compensated" if sum([0.1] * 10) == 1.0 else "naive"


# 2026-11-03 補：`exp_compare` 的輸入組 `_LEFTS` 在有 pandas 時多兩個值（`pd.NA`、`pd.NaT`），沒有 pandas 時沒有；
# 於是同一份原始實作在「沒有 pandas 的直譯器」算出的摘要不同（實測 3.13 擋掉 pandas、3.11 無 pandas 皆為
# `40e1cc53c9167aff`；有 pandas 為 `192bf4e68238e9bc`；與 sum() 模式無關）。舊寫法只在「搬遷後」那支測試遇無 pandas 時
# skip，「由原始實作算出」那支沒有 skip → 在無 pandas、又拿得到 git 歷史的環境必紅（CI 是淺層 clone，該支被 skip，所以沒抓到）。
# 處置：不 skip、不放寬，改依本環境挑對應摘要（兩個摘要都由原始實作算出），兩支測試在兩種環境都真的比對。
_PANDAS_MODE = "pandas" if _PANDAS_VALUES else "no_pandas"
# 每個「依環境分歧」的家族用哪一個環境特徵挑摘要。
_PIN_VARIANT = {"hld_nav": _SUM_MODE, "exp_compare": _PANDAS_MODE}


def _pinned(family) -> str:
    value = _PINNED[family]
    return value[_PIN_VARIANT[family]] if isinstance(value, dict) else value


def _families(hld_ns, alo_ns, exp_ns, chart_ns, mkt_ns):
    return {
        "hld_nav": lambda: _hld_nav_results(hld_ns["return_pct"], hld_ns["drawdown_pct"], hld_ns["vol_pct"]),
        "hld_merge": lambda: _hld_merge_results(hld_ns["merge_same_key_holdings"]),
        "hld_deviation": lambda: _hld_deviation_results(hld_ns),
        "alo": lambda: _alo_results(alo_ns),
        "exp_compare": lambda: _exp_compare_results(exp_ns),
        "exp_rules": lambda: _exp_rules_results(exp_ns),
        "mkt": lambda: _mkt_results(chart_ns, mkt_ns),
    }


@pytest.mark.parametrize("family", sorted(_PINNED))
def test_摘要常數_搬遷後的ui_v2輸出符合(family):
    fams = _families(vars(new_hld), vars(new_alo), vars(new_exp), vars(new_chart), vars(new_mkt))
    assert _digest(fams[family]()) == _pinned(family), (family, _SUM_MODE, _PANDAS_MODE)


@pytest.mark.parametrize("family", sorted(_PINNED))
def test_摘要常數_由原始實作算出(family):
    hld = _need("ui_v2/hld/logic.py", "ui_v2.hld")
    alo = _need("ui_v2/alo/logic.py", "ui_v2.alo")
    exp = _need("ui_v2/exp/logic.py", "ui_v2.exp")
    chart = _need("ui_v2/mkt/chart.py", "ui_v2.mkt")
    mkt = _need("ui_v2/mkt/logic.py", "ui_v2.mkt")
    assert _digest(_families(hld, alo, exp, chart, mkt)[family]()) == _pinned(family), (family, _SUM_MODE, _PANDAS_MODE)


def test_依環境分歧的摘要_每一個都有對應的環境特徵():
    # 防呆：dict 型摘要必須在 `_PIN_VARIANT` 登記，且目前環境的特徵值必須是它的一個鍵（否則是 KeyError 而不是誤綠）
    for family, value in _PINNED.items():
        if isinstance(value, dict):
            assert family in _PIN_VARIANT and _PIN_VARIANT[family] in value, family


# ═══════════════════════ L2 本體（中性代碼）的直接行為 ═══════════════════════


def test_L2三態比較_用中性代碼_缺值不是不符合也不是符合():
    assert d_rule.compare_tristate(None, d_rule.OP_EQ, "x") == (None, d_rule.UNDET_MISSING)
    assert d_rule.compare_tristate(NAN, d_rule.OP_GT, "1") == (None, d_rule.UNDET_MISSING)
    assert d_rule.compare_tristate("abc", d_rule.OP_GT, "1") == (None, d_rule.UNDET_LEFT_NOT_NUMBER)
    assert d_rule.compare_tristate("2", d_rule.OP_LT, "x") == (None, d_rule.UNDET_RIGHT_NOT_NUMBER)
    assert d_rule.compare_tristate("2", d_rule.OP_GT, "1") == (True, None)
    with pytest.raises(d_rule.UncomparableValues):
        d_rule.compare_tristate("2", "大於", "1")                      # L2 不認中文方向字面
    rows = [{"fund_code": "A", "x": None}, {"fund_code": "B", "x": "2"}, {"fund_code": "C", "x": "0"}]
    steps, listed, undet = d_rule.apply_rules_tristate(rows, [{"field": "x", "op": d_rule.OP_GT, "value": "1"}])
    assert [r["fund_code"] for r in listed] == ["A", "B"]
    assert undet == {"A": [(d_rule.UNDET_MISSING, "x")]} and steps[0][1:] == (3, 1, 1)


def test_L2持倉_未分類回None_衝突丟中性例外():
    assert d_holdings.bucket_category("其他", ("核心",)) is None
    assert d_holdings.bucket_category("核心", ("核心",)) == "核心"
    with pytest.raises(d_holdings.HoldingKeyConflict) as info:
        d_holdings.aggregate_holding_rows([_h(), _h(ccy="EUR")])
    assert info.value.columns == ("ccy",) and isinstance(info.value, ValueError)


def test_L2偏離_方向代碼與取數失敗優先():
    assert d_deviation.breaches(d_deviation.DIRECTION_BELOW, -20.0, -10.0) is True
    assert d_deviation.breaches(d_deviation.DIRECTION_ABOVE, -20.0, -10.0) is False
    assert d_deviation.breaches("低於", -20.0, -10.0) is False         # L2 不認中文方向字面
    skipped = {"missing": {"A", "B"}, "missing_other": {"A"}, "error": {"A"}, "na": {"A", "C"}, "not_ready": set()}
    assert d_deviation.apply_error_precedence(skipped) is skipped
    assert skipped == {"missing": {"B"}, "missing_other": set(), "error": {"A"}, "na": {"C"}, "not_ready": set()}


def test_L2延遲日數與期間切片_例外是中性的ValueError子類():
    with pytest.raises(d_freshness.NaiveTimestampError):
        d_freshness.delay_days("2026-10-01", "2026-10-02T00:00:00", tz=timezone.utc)
    with pytest.raises(ValueError):
        d_periods.slice_period([], "2Y")


# ═══════════════════════ (b) 分層守衛 ═══════════════════════

_DOMAIN_DIR = _ROOT / "services" / "v2_domain"
# fail-closed：不在這張表的 import 一律紅（新套件預設違規）。
_DOMAIN_ALLOWED_IMPORTS = {
    "__future__", "__future__.annotations", "math", "decimal", "datetime", "datetime.date", "datetime.datetime",
    "datetime.timedelta", "shared.signal_thresholds", "shared.signal_thresholds.TRADING_DAYS_PER_YEAR",
    # 2026-11-03 BL-0536-H1 `normalization.py` 的 frozen dataclass 回傳型別（標準庫、純資料結構、無 I/O）。
    "dataclasses", "dataclasses.dataclass",
}
_DOMAIN_FORBIDDEN_CALLS = {"open", "exec", "eval", "compile", "__import__", "input", "print"}


def _has_cjk(text: str) -> bool:
    return any("　" <= ch <= "鿿" or "＀" <= ch <= "￯" for ch in text)


def _domain_imports(tree):
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                out.append("." * node.level + (node.module or ""))
                continue
            out.append(node.module or "")
            out.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return out


def _domain_violations(source: str) -> list:
    tree = ast.parse(source)
    bad = []
    for module in _domain_imports(tree):
        if module.startswith("services.v2_domain"):
            continue
        if module not in _DOMAIN_ALLOWED_IMPORTS:
            bad.append(f"import {module}")
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstrings.add(id(first.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _DOMAIN_FORBIDDEN_CALLS:
            bad.append(f"call {node.func.id}()")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings \
                and _has_cjk(node.value):
            bad.append(f"中文字串常數 {node.value!r}")
    return bad


def _domain_files():
    return sorted(p for p in _DOMAIN_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def test_v2_domain_母體不是空的():
    names = {p.name for p in _domain_files()}
    assert {"__init__.py", "nav_metrics.py", "holdings.py", "deviation.py", "rule_filter.py", "periods.py",
            "freshness.py", "normalization.py"} <= names, names


def test_v2_domain只import白名單_不碰streamlit_ui_網路_檔案_也不帶中文畫面字():
    problems = {p.relative_to(_ROOT).as_posix(): _domain_violations(p.read_text(encoding="utf-8"))
                for p in _domain_files()}
    assert {k: v for k, v in problems.items() if v} == {}


@pytest.mark.parametrize("code", [
    "import streamlit as st",
    "from ui_v2 import page_health",
    "from ui_v2.hld import logic",
    "import ui_v3.viewmodels",
    "from ui.tab1 import x",
    "import requests",
    "from urllib import request",
    "import os",
    "import io",
    "import pathlib",
    "from services.v2_tables import masking",
    "from repositories.macro import yf",
    "from . import holdings",
    "def f():\n    import socket",
    "x = open('a')",
    "STATE = '資料未備'",
    "def f():\n    return '系統錯誤'",
])
def test_v2_domain分層守衛會咬_正控(code):
    assert _domain_violations(code), code


@pytest.mark.parametrize("code", [
    "from __future__ import annotations\nimport math\nfrom datetime import date",
    "from services.v2_domain import holdings",
    "def f():\n    '''中文 docstring 可以'''\n    return 'ok'",
    "# 中文註解可以\nX = 'missing'",
])
def test_v2_domain分層守衛不誤報_負控(code):
    assert _domain_violations(code) == [], code


def _load_ui_v2_import_guard():
    path = _ROOT / "tests" / "ui_v2" / "test_ui_v2_live_import_guard.py"
    spec = importlib.util.spec_from_file_location("_v2_domain_port_ui_v2_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ui_v2碰v2_domain的只有shim一檔():
    users = set()
    for path in sorted((_ROOT / "ui_v2").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for module in _domain_imports(tree):
            if module.startswith("services"):
                rel = path.relative_to(_ROOT).as_posix()
                if not rel.endswith("/source.py"):
                    users.add(rel)
    assert users == {"ui_v2/v2_domain_shim.py"}, users


@pytest.mark.parametrize("rel, code, ok", [
    ("ui_v2/v2_domain_shim.py", "from services.v2_domain import holdings, rule_filter", True),
    ("ui_v2/v2_domain_shim.py", "import services.v2_domain.periods", True),
    ("ui_v2/hld/logic.py", "from services.v2_domain import holdings", False),       # 白名單只給 shim
    ("ui_v2/hld/source.py", "from services.v2_domain import holdings", False),      # source.py 也不行
    ("ui_v2/v2_domain_shim.py", "from services.v2_tables import masking", False),   # shim 只開 v2_domain
    ("ui_v2/v2_domain_shim.py", "from services import fund_service", False),
    ("ui_v2/v2_domain_shim.py", "from services.v2_domain import zzz", False),       # 逐模組列名
    ("ui_v2/v2_domain_shim.py", "import requests", False),
    ("ui_v2/v2_domain_shim.py", "import importlib", False),
])
def test_ui_v2_import守衛的v2_domain白名單_正控負控(rel, code, ok):
    guard = _load_ui_v2_import_guard()
    found = guard._check(rel, code)
    assert (found == []) is ok, (rel, code, found)


# ═══════════════════════ (c) NAV_NOT_READY_DAYS 單一來源 ═══════════════════════

_NAV_DAYS_OWNER = "ui_v2/thresholds.py"   # C 類 ownership lock（見檔頭 (c)）；放寬需總管／客戶裁示；本批不改


def test_NAV_NOT_READY_DAYS_全repo只有一處給值_值為10():
    owners = {}
    for top in ("ui_v2", "ui_v3", "services", "shared"):
        for path in sorted((_ROOT / top).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                targets = node.targets if isinstance(node, ast.Assign) else \
                    [node.target] if isinstance(node, (ast.AnnAssign, ast.AugAssign)) else []
                if any(isinstance(t, ast.Name) and t.id == "NAV_NOT_READY_DAYS" for t in targets):
                    owners.setdefault(path.relative_to(_ROOT).as_posix(), []).append(ast.unparse(node.value))
    assert owners == {_NAV_DAYS_OWNER: ["10"]}, owners
    from ui_v2 import thresholds
    assert thresholds.NAV_NOT_READY_DAYS == 10 and type(thresholds.NAV_NOT_READY_DAYS) is int
    assert not hasattr(d_holdings, "NAV_NOT_READY_DAYS")
