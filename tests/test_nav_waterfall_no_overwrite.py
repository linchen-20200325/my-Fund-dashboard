"""NAV 抓取鏈四個結構性缺陷的回歸測試（2026-08-11）。

背景 —— user 的 8 檔持倉，每一檔的 NAV 序列都**剛好只有 30 點**、跨度 0.11 年，
連帶讓 `ret_3y_ann`(需 756 點) / Sharpe·Sortino(250) / MaxDD(125) / σ(252) 全數留白。

追查後找到四個彼此獨立的缺陷，**由重到輕**：

**① `repositories/fund/sources.py` — `None[:40]` 讓整條多來源鏈死掉（主因）。**
`fetch_fund_multi_source` 印 log 時寫 `_result.get('error','')[:40]`。`error` 這個 key
**一定存在**（`_fetch_fund_single` 的 result dict 初始化就是 `error=None`），所以
default `''` 永遠用不到，`.get()` 回 `None` → `None[:40]` → TypeError。
而 `normalize_result_state` 只在 status=="failed"（什麼都沒抓到）時才寫錯誤字串 ——
**語意剛好反過來：抓成功就炸，抓全失敗才活。** 例外被 `fund_orchestration.py`
Step 2 的 `except Exception` 吞成一行「多來源異常」，實際上線的是 legacy 爬蟲的
「近30日」路徑，每檔 ~25-30 點。這直接解釋了「為什麼是每一檔、且剛好都 30」。

**② `fund_fetcher.merge_non_empty` — 遇 `pd.Series` 必拋 ValueError。**
`if v in (None, "", [], {})` 對 pandas 物件會 elementwise 比較再 `bool()`。
而 `series` 正是最重要的合併對象 → 修好①之後立刻踩到②，兩顆串聯。

**③ `sources.py` 安聯 JSON API 漏兩對括號。**
`proxies=_proxies, verify=_ssl_verify` 傳的是**函式物件**而非呼叫結果，requests 在
`merge_environment_settings()` 對它呼叫 `.get()` → AttributeError 在 **HTTP 送出之前**
就被 except 接走。ACTI/ACCP/ACDD/ACTT + TLZF9/ANZ89 唯一能拿 2000 天歷史的
**非 MoneyDJ** 來源，從未真的送出過請求。

**④ waterfall 2a/2b/2c/2e/2f 的無條件覆蓋。**
`nav_s = _src_xxx(_code)` 會把前一順位已抓到、但未達本順位門檻的序列抹成空。
⚠️ **修法刻意不動 `nav_s` 與 gate** —— 第一版把指派改成「較長者勝」，稽核抓到那是
net-negative：gate 吃的就是 `nav_s`，拿到 10~19 筆就會把 2c2/2d/2e/2f… 整層下游關掉，
其中 2d 是 www yp004002 的 2000 天窗。改成另開 `_best_s` 側車 + 收尾救援。

⚠️ 本檔**全部離線可跑**（AST + pandas + monkeypatch，無網路、無 secrets）。
PROCESS.md §4「Test Liveness」：這些測試在任何環境都必須真的執行，不得 skip。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from fund_fetcher import merge_non_empty
from repositories.fund.fund_orchestration import _adopt_if_better, _effective_nav_len

_ROOT = Path(__file__).resolve().parents[1]
_ORCH = _ROOT / "repositories" / "fund" / "fund_orchestration.py"
_SOURCES = _ROOT / "repositories" / "fund" / "sources.py"


def _s(n: int, start: str = "2024-01-01") -> pd.Series:
    if n == 0:
        return pd.Series(dtype=float)
    return pd.Series(range(1, n + 1),
                     index=pd.date_range(start, periods=n, freq="D"),
                     dtype=float)


# ══════════════════════════════════════════════════════════════════════
# 缺陷 ① — fetch_fund_multi_source 的 None[:40]
# ══════════════════════════════════════════════════════════════════════

def test_multi_source_survives_partial_result_with_error_none():
    """接線測試：把 `(_result.get('error') or '')` 改回 `_result.get('error','')`，
    本測試必須轉紅。

    這是本輪最重要的一條 —— 它模擬「抓到資料」（status=partial、error=None）
    這個**最常見**的情境，而舊碼正是在這個情境下 TypeError。
    """
    from repositories.fund import sources as SRC

    _partial = {
        "fund_code": "ACCP138", "fund_name": "測試基金",
        "series": _s(30), "nav_latest": 12.34,
        "dividends": [], "metrics": {}, "perf": {}, "risk_metrics": {},
        "error": None,          # ← partial 時 normalize_result_state 保持 None
        "warning": None,
    }

    _calls: list[str] = []

    def _fake_single(candidate, force_refresh=False, page_type=""):
        _calls.append(candidate)
        return dict(_partial, fund_code=candidate)

    # `_fetch_fund_single` 是在 fetch_fund_multi_source 內部 lazy import 的
    # （v19.340 為解循環 import），所以要 patch 來源模組上的名字。
    from repositories.fund import fund_orchestration as FO
    _orig = FO._fetch_fund_single
    FO._fetch_fund_single = _fake_single
    try:
        _out = SRC.fetch_fund_multi_source("ACCP138", page_type="yp010000")
    finally:
        FO._fetch_fund_single = _orig

    assert _calls, "_fetch_fund_single 應被呼叫"
    assert _out is not None
    assert _out.get("series") is not None and len(_out["series"]) == 30, (
        "多來源結果應原樣帶回 series —— 若這裡拿不到，代表 log 那行又炸了")


def test_no_naked_slicing_of_get_error_anywhere():
    """AST 層釘住這個 bug class —— **掃全 repo**，不只 sources.py。

    `error` 這個 key 在 fund result dict 裡**一定存在**，所以 `.get('error', '預設')`
    的 default 永遠用不到；partial（= 有抓到資料）時值是 None → 直接切片就 TypeError。

    掃描面刻意放大到整個 repo：本輪就在 `ui/tab3_t7_ledger.py` 找到同型漏網。
    只掃 sources.py 的話，那顆會活下來。
    """
    _naked = []
    for _p in _iter_repo_py():
        try:
            _tree = ast.parse(_p.read_text(encoding="utf-8"))
        except SyntaxError as _e:
            raise AssertionError(f"{_p.relative_to(_ROOT)} 語法錯誤: {_e}") from _e
        for _n in ast.walk(_tree):
            # 找 X.get('error', ...) 直接被 Subscript 的形狀
            if not isinstance(_n, ast.Subscript):
                continue
            _v = _n.value
            if (isinstance(_v, ast.Call)
                    and isinstance(_v.func, ast.Attribute) and _v.func.attr == "get"
                    and _v.args
                    and isinstance(_v.args[0], ast.Constant)
                    and _v.args[0].value == "error"):
                _naked.append(f"{_p.relative_to(_ROOT)}:{_n.lineno}")
    assert not _naked, (
        f"{_naked}: `.get('error', ...)` 的結果被直接切片 → None[:N] TypeError。"
        "請改 `(x.get('error') or '預設')[:N]`。")


# ══════════════════════════════════════════════════════════════════════
# 缺陷 ② — merge_non_empty 遇 Series
# ══════════════════════════════════════════════════════════════════════

def test_merge_non_empty_accepts_series_without_raising():
    """接線測試：把 `_is_empty_value` 改回 `if v in (None, '', [], {})`，本測試轉紅
    （ValueError: The truth value of a Series is ambiguous）。"""
    _dst = {"fund_name": "舊名"}
    _src = {"series": _s(30), "data_source": "FundClear"}
    _out = merge_non_empty(_dst, _src)
    assert len(_out["series"]) == 30
    assert _out["data_source"] == "FundClear"
    assert _out["fund_name"] == "舊名"


def test_merge_non_empty_skips_empty_series():
    """空 Series 不得覆蓋既有的非空 Series（這正是本函式存在的理由）。"""
    _dst = {"series": _s(30)}
    _out = merge_non_empty(_dst, {"series": pd.Series(dtype=float)})
    assert len(_out["series"]) == 30


def test_merge_non_empty_does_not_lose_keys_after_series():
    """§1:舊碼在 series 這個 key 上拋例外，dict 是 in-place 改的 →
    series **之後**的 key（含 data_source / source_trace）全丟，半合併狀態。"""
    _src = {"a": 1, "series": _s(5), "data_source": "cnyes",
            "source_trace": [{"source": "x"}]}
    _out = merge_non_empty({}, _src)
    assert set(_out) == {"a", "series", "data_source", "source_trace"}


@pytest.mark.parametrize("val", [0, 0.0, False, ()])
def test_merge_non_empty_preserves_legacy_falsy_semantics(val):
    """`0` / `False` / 空 tuple 在舊語意下算「有值」—— 修 bug 不得順手改到這裡。"""
    _out = merge_non_empty({}, {"k": val})
    assert "k" in _out


@pytest.mark.parametrize("val", [None, "", [], {}])
def test_merge_non_empty_still_skips_classic_empties(val):
    assert merge_non_empty({}, {"k": val}) == {}


# ══════════════════════════════════════════════════════════════════════
# 缺陷 ③ — proxy helper 必須「被呼叫」而不是「被當值傳進去」
# ══════════════════════════════════════════════════════════════════════

_PROXY_HELPERS = {"_proxies", "_ssl_verify"}
_PROXY_KWARGS = {"proxies", "verify"}
_SCAN_DIRS = ("repositories", "services", "infra", "ui", "shared", "scripts", "tests")


def _iter_repo_py() -> list[Path]:
    out: list[Path] = []
    for _sub in _SCAN_DIRS:
        _d = _ROOT / _sub
        # PROCESS.md §4：「工具跑了但沒輸出」不可當成 0 findings。
        # `Path('不存在').rglob()` 回空且不報錯 → 掃描範圍會靜默縮小。
        assert _d.is_dir(), f"掃描目錄 {_sub}/ 不存在，目錄結構已變更，本測試的保護範圍失效"
        out.extend(_d.rglob("*.py"))
    out.extend(_ROOT.glob("*.py"))
    assert len(out) > 100, f"repo 掃描只找到 {len(out)} 個 .py，範圍異常"
    return sorted(out)


def test_proxy_helpers_are_called_not_passed_as_functions():
    """`proxies=_proxies`（少括號）一律視為 bug。

    刻意走 **AST 而非 grep**：本檔與 `sources.py` 的說明註解裡都寫了
    `proxies=_proxies` 這串字，grep 會被自己的註解騙成紅燈（本 repo 已有
    3 次「測試被註解錨點騙過」的前科，方向相反但同一類陷阱）。
    AST 只看真正的 keyword argument。
    """
    bad: list[str] = []
    for _p in _iter_repo_py():
        _txt = _p.read_text(encoding="utf-8")
        try:
            _tree = ast.parse(_txt)
        except SyntaxError as _e:
            # §1：語法錯的檔被靜默跳過 = 那個檔從此不受本測試保護
            raise AssertionError(f"{_p.relative_to(_ROOT)} 語法錯誤: {_e}") from _e
        for _n in ast.walk(_tree):
            if not isinstance(_n, ast.Call):
                continue
            for _kw in _n.keywords:
                if _kw.arg not in _PROXY_KWARGS:
                    continue
                # 少括號 = 把函式名當值傳。裸名 → ast.Name；模組路徑 → ast.Attribute
                _v = _kw.value
                _name = (_v.id if isinstance(_v, ast.Name)
                         else _v.attr if isinstance(_v, ast.Attribute) else None)
                if _name in _PROXY_HELPERS:
                    bad.append(f"{_p.relative_to(_ROOT)}:{_v.lineno} "
                               f"{_kw.arg}={_name} → 應為 {_name}()")
    assert not bad, (
        "以下位置把 proxy helper 的**函式物件**當值傳給 requests，"
        "requests 會在送出前拋 AttributeError（且多半被 except 吞掉）：\n  "
        + "\n  ".join(bad))


def test_sources_requests_calls_pass_called_proxies():
    """接線測試：把 sources.py 那行的括號拿掉，本測試必須轉紅。"""
    _tree = ast.parse(_SOURCES.read_text(encoding="utf-8"))
    _hits = []
    for _n in ast.walk(_tree):
        if not isinstance(_n, ast.Call):
            continue
        _kws = {_k.arg: _k.value for _k in _n.keywords}
        if "proxies" not in _kws or "verify" not in _kws:
            continue
        _hits.append((_n.lineno,
                      isinstance(_kws["proxies"], ast.Call),
                      isinstance(_kws["verify"], ast.Call)))
    assert _hits, "sources.py 應存在帶 proxies/verify 的 requests 呼叫（找不到 = 掃描失效）"
    _bad = [f"L{ln}" for ln, _p, _v in _hits if not (_p and _v)]
    assert not _bad, f"sources.py {_bad} 的 proxies/verify 未加括號"


# ══════════════════════════════════════════════════════════════════════
# 缺陷 ④ — _effective_nav_len / _adopt_if_better 語意
# ══════════════════════════════════════════════════════════════════════

def test_effective_len_ignores_duplicate_dates():
    """§3.1 date unique：40 筆但只有 20 個唯一日期，有效筆數是 20。"""
    _dup = pd.concat([_s(20), _s(20)])
    assert len(_dup) == 40
    assert _effective_nav_len(_dup) == 20


def test_effective_len_ignores_nan_and_non_positive():
    """§3.2 NAV > 0：全 NaN / 0 / 負值不算有效筆數。"""
    assert _effective_nav_len(pd.Series([float("nan")] * 50)) == 0
    assert _effective_nav_len(pd.Series([0.0, -1.0, 3.0])) == 1


def test_effective_len_handles_none_and_empty():
    assert _effective_nav_len(None) == 0
    assert _effective_nav_len(pd.Series(dtype=float)) == 0


def test_dirty_long_series_never_beats_clean_short_series():
    """核心不變量：50 筆全 NaN **不可以**贏過 30 筆乾淨序列。

    只比 `len()` 的版本會讓髒序列勝出，下游 metrics 全吃 NaN —— 那是 §1 意義上
    更糟的失敗（看起來成功、通過所有既有不變量斷言）。
    """
    _dirty = pd.Series([float("nan")] * 50,
                       index=pd.date_range("2020-01-01", periods=50, freq="D"))
    _keep, _src = _adopt_if_better(_s(30), "FundClear", _dirty, "髒來源")
    assert _src == "FundClear" and len(_keep) == 30


def test_incumbent_survives_empty_candidate():
    """核心回歸：step 0 拿到 15 筆，2a 回空 → 15 筆不可以被抹掉。"""
    _keep, _src = _adopt_if_better(_s(15), "allianzgi_tw", _s(0), "FundClear")
    assert len(_keep) == 15 and _src == "allianzgi_tw"


def test_incumbent_survives_shorter_candidate():
    _keep, _src = _adopt_if_better(_s(15), "allianzgi_tw", _s(8), "FundClear")
    assert len(_keep) == 15 and _src == "allianzgi_tw"


def test_incumbent_survives_none_candidate():
    """來源函式回 None（而非空 Series）也不得造成資料遺失。"""
    _keep, _src = _adopt_if_better(_s(15), "allianzgi_tw", None, "FundClear")
    assert len(_keep) == 15 and _src == "allianzgi_tw"


def test_equal_length_keeps_higher_priority_source():
    _keep, _src = _adopt_if_better(_s(30), "FundClear", _s(30), "cnyes")
    assert _src == "FundClear"


def test_series_and_source_swap_together():
    """§2.2：序列換了，來源標籤必須跟著換 —— 不得出現 nav_s 與 nav_source 不同源。"""
    _cand = _s(40)
    _keep, _src = _adopt_if_better(_s(15), "allianzgi_tw", _cand, "FundClear")
    assert _src == "FundClear" and _keep is _cand


def test_span_is_deliberately_not_compared():
    """釘住**行為**而非 docstring：同有效筆數、跨度差 10 倍 → 仍保留先到者。

    這是刻意的範圍限制（跨度優先屬 gate 語意變更，須 user 拍板）。
    寫成行為測試而不是 `assert "跨度" in __doc__` —— 後者是註解錨點，
    永遠不會因為行為 regression 轉紅，且 `python -OO` 下會誤紅。
    """
    _dense = _s(30, "2024-01-01")                                   # 30 天
    _wide = pd.Series(range(1, 31), dtype=float,
                      index=pd.date_range("2018-01-01", periods=30, freq="120D"))
    _keep, _src = _adopt_if_better(_dense, "先到", _wide, "跨度長10倍")
    assert _src == "先到"


@pytest.mark.parametrize("cur,cand", [(0, 0), (0, 1), (5, 5), (5, 4), (5, 6), (30, 756)])
def test_effective_count_is_monotonic_non_decreasing(cur, cand):
    """helper **單步**對有效筆數單調不減。

    ⚠️ 這只保證單步。waterfall 的**全域**行為由下面的側車設計測試把關 ——
    第一版誤把單步單調當成全域單調，是稽核退回的主因。
    """
    _keep, _ = _adopt_if_better(_s(cur), "x", _s(cand), "y")
    assert _effective_nav_len(_keep) == max(cur, cand)


# ══════════════════════════════════════════════════════════════════════
# 缺陷 ④ — 側車設計的接線（gate 不得被動到）
# ══════════════════════════════════════════════════════════════════════

def _waterfall_fn() -> ast.FunctionDef:
    _tree = ast.parse(_ORCH.read_text(encoding="utf-8"))
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.FunctionDef) and _n.name == "_fetch_fund_single":
            return _n
    raise AssertionError("找不到 _fetch_fund_single")


def _call_name(node: ast.Call) -> str:
    _f = node.func
    return _f.id if isinstance(_f, ast.Name) else getattr(_f, "attr", "")


def test_waterfall_records_best_at_every_destructive_site():
    """2a/2b/2c/2e/2f 五處無條件覆蓋 + step 0 初始化 = 至少 6 次側車記錄。

    接線測試：拿掉任何一處 `_best_s, _best_src = _adopt_if_better(...)`，
    本測試轉紅（那一處的資料就會真的遺失）。
    """
    _n = sum(1 for _x in ast.walk(_waterfall_fn())
             if isinstance(_x, ast.Call) and _call_name(_x) == "_adopt_if_better")
    # 刻意用 `==` 而非 `>=`：`>=` 在有人新增第 7 處時，會讓「偷刪一處」不轉紅
    # ——docstring 承諾「拿掉任何一處必轉紅」，斷言就必須真的做到（§1）。
    # 若日後 waterfall 合理地增減順位，請連同這個數字一起改，並在 PR 說明為什麼。
    assert _n == 6, (
        f"_adopt_if_better 側車記錄有 {_n} 處，應恰好 6 處"
        "（step 0 初始化 + 2a/2b/2c/2e/2f 五個無條件覆蓋點）")


def test_waterfall_gates_still_read_nav_s_not_best_s():
    """**反向**接線測試：gate 一律只看 `nav_s`，不得改看 `_best_s`。

    這是稽核退回第一版的原因 —— gate 若吃「歷來最佳」，拿到 10~19 筆就會把
    2c2/2d/2e/2f…（含 www yp004002 的 2000 天窗）整層下游關掉。
    """
    _bad = []
    for _x in ast.walk(_waterfall_fn()):
        if not isinstance(_x, ast.Compare):
            continue
        _l = _x.left
        if (isinstance(_l, ast.Call) and _call_name(_l) == "len"
                and _l.args and isinstance(_l.args[0], ast.Name)
                and _l.args[0].id == "_best_s"):
            _bad.append(_x.lineno)
    # 收尾救援那一處用的是 _effective_nav_len(_best_s)，不是 len(_best_s)，
    # 所以這裡命中任何一筆都代表 gate 被污染了。
    assert not _bad, f"L{_bad}: waterfall gate 讀到了 _best_s，會關掉下游來源"


def test_waterfall_has_final_rescue_before_span_extend():
    """收尾救援必須存在，且必須在 span-extend **之前**（讓跨度救援吃到救回的序列）。"""
    _fn = _waterfall_fn()
    _rescue = [_x.lineno for _x in ast.walk(_fn)
               if isinstance(_x, ast.Call) and _call_name(_x) == "_effective_nav_len"]
    _span = [_x.lineno for _x in ast.walk(_fn)
             if isinstance(_x, ast.Call)
             and _call_name(_x) == "_span_extend_insurance_nav"]
    assert _rescue, "找不到收尾救援（_effective_nav_len 比較）"
    assert _span, "找不到 _span_extend_insurance_nav 呼叫"
    # 用 `max(_rescue)` 而非 `min(_rescue)`：若日後有人在 waterfall 中段新增
    # 別的 `_effective_nav_len` 呼叫，`min()` 會取到那一行 → 斷言仍綠但**已不再
    # 驗救援的位置**（靜默鬆弛，PROCESS.md §4 點名型態）。`max()` 要求「最後一次
    # _effective_nav_len 呼叫」仍在 span-extend 之前，才是真正想守的性質。
    assert max(_rescue) < min(_span), "收尾救援必須在 span-extend 之前"
