# -*- coding: utf-8 -*-
"""BL-0542 G1-②（最小 PORT）：`services/v2_domain/holdings.py` 新增的 ALO 配置核心（`basis_value_with_reason`／
`category_values`）與 `ui_v2/alo/logic.py` 薄包裝的守衛。

不可變的總證明是 `tests/test_alo_core_golden.py`（212 情境逐位元組）＋ `tests/test_alo_core_golden_mutations.py`；本檔補
黃金檔打不到的角落，分六組：

1. **領域單元**：每個缺值代碼、惰性取表、例外時機、累加順序與起點、第一種缺值定案、過期併日期與去重、缺值不是 0、
   純度（不改輸入）、凍結型別。
2. **缺值代碼 ↔ 舊中文句子**：薄包裝輸出與搬遷前的字面逐字相同（含舊形狀、有日期、缺淨值、缺匯率、多檔併日期）。
3. **領域層不帶畫面字**：跑真的 `_domain_violations` 守衛。
4. **與搬遷前實作的差分**（git `1f260bfc`，拿不到就 skip）：黃金檔之外，再以固定種子隨機產生的資料集比對
   `basis_value_with_key`／`_category_values`（含 `stale_out` 回填、例外型別與訊息）。
5. **針對新程式碼的突變**（黃金檔未涵蓋、改由本檔咬到的幾處）。
6. **shim 面**：ui_v2 只經 `_v2d.holdings.<名>` 取用，`__all__` 有登記。
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import importlib.util
import pathlib
import random
import subprocess
import types

import pytest

import _alo_core_golden as G

G.setup_path()

from services.v2_domain import holdings as D  # noqa: E402
from ui_v2 import page_health  # noqa: E402
from ui_v2 import v2_domain_shim  # noqa: E402
from ui_v2.alo import logic as L  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_BASE_COMMIT = "1f260bfc949a6d1435a5f2abd74731cb8d76f047"   # G1-① 合併點；本批搬遷前

MV, COST = G.MV, G.COST
H, N, FX, DS, NNR = G.H, G.N, G.FX, G.DS, G.NNR
FX_USD, FX_EUR = G.FX_USD, G.FX_EUR


def _no_stale():
    return frozenset(), None, None


def _fx_key(ccy):
    if not (isinstance(ccy, str) and len(ccy) == 3 and ccy.isupper()) or ccy == "TWD":
        raise ValueError(f"bad ccy {ccy!r}")
    return "fx_twd_per_" + ccy.lower()


def _bv(holding, tables, *, market=True, stale=_no_stale, fx_key_of=_fx_key):
    return D.basis_value_with_reason(holding, tables, market=market, fx_key_of=fx_key_of, stale_provider=stale)


def _cv(holdings, tables, *, market=True, track_stale=True, stale=_no_stale, fx_key_of=_fx_key, category_of=None):
    return D.category_values(holdings, tables, market=market, track_stale=track_stale,
                             category_of=category_of or (lambda h: h["bucket"]), fx_key_of=fx_key_of,
                             stale_provider=stale)


class _Touch(dict):
    """記下被 `[]` 讀過的表名（惰性守衛）。"""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.touched = []

    def __getitem__(self, key):
        self.touched.append(key)
        return super().__getitem__(key)


# ═══════════════════════ 1. 領域單元：基準值 ═══════════════════════


def test_成本基準不碰任何表_也不呼叫注入函式():
    class Boom(dict):
        def __getitem__(self, key):
            raise AssertionError(f"成本基準不該讀 {key!r}")

    def boom(*_a):
        raise AssertionError("成本基準不該呼叫注入函式")

    assert D.basis_value_with_reason(H("A", cost=123.0), Boom(), market=False, fx_key_of=boom, stale_provider=boom) \
        == (123.0, None, None)


def test_成本基準_數值轉型與例外照舊():
    assert _bv(H("A", cost="12"), {}, market=False)[0] == 12.0 and type(_bv(H("A", cost=3000), {}, market=False)[0]) is float
    with pytest.raises(ValueError):
        _bv(H("A", cost="abc"), {}, market=False)
    with pytest.raises(TypeError):
        _bv(H("A", cost=None), {}, market=False)


def test_缺值代碼_缺淨值():
    assert _bv(H("Z"), {"nav": []}) == (None, D.MissingReason(D.REASON_NAV_ABSENT), D.KIND_NAV)


def test_缺值代碼_過期_有日期與舊形狀():
    dated = lambda: (frozenset({"Z"}), 10, {"Z": "2026-09-01"})   # noqa: E731
    undated = lambda: (frozenset({"Z"}), 10, None)                # noqa: E731
    assert _bv(H("Z"), {"nav": []}, stale=dated) == (
        None, D.MissingReason(D.REASON_NAV_STALE, stale_day="2026-09-01", stale_days=10), D.KIND_NAV)
    assert _bv(H("Z"), {"nav": []}, stale=undated) == (
        None, D.MissingReason(D.REASON_NAV_STALE_UNDATED, stale_days=10), D.KIND_NAV)
    # 在名單上但該檔有淨值 → 照算（名單只在「沒有淨值」時才看）
    value, reason, kind = _bv(H("A"), {"nav": [N("A", "2026-10-03", 10.0)], "market_indicator": [FX(FX_USD, "2026-10-03", 30.0)]},
                              stale=lambda: (frozenset({"A"}), 10, {"A": "2026-09-01"}))
    assert (value, reason, kind) == (10.0 * 10.0 * 30.0, None, None)
    # 不在名單 → 缺淨值
    assert _bv(H("Q"), {"nav": []}, stale=dated)[1].code == D.REASON_NAV_ABSENT


def test_缺值代碼_缺匯率_帶實際匯率鍵():
    tables = {"nav": [N("A", "2026-10-03", 10.0, "USD"), N("C", "2026-10-03", 5.0, "EUR")], "market_indicator": []}
    assert _bv(H("A"), tables) == (None, D.MissingReason(D.REASON_FX_ABSENT, fx_key="fx_twd_per_usd"), D.KIND_FX)
    assert _bv(H("C", ccy="EUR"), tables)[1] == D.MissingReason(D.REASON_FX_ABSENT, fx_key="fx_twd_per_eur")


def test_匯率是零是真值_不是缺值():
    tables = {"nav": [N("A", "2026-10-03", 10.0)], "market_indicator": [FX(FX_USD, "2026-10-03", 0.0)]}
    value, reason, kind = _bv(H("A"), tables)
    assert value == 0.0 and reason is None and kind is None
    assert value != _bv(H("A"), {"nav": [N("A", "2026-10-03", 10.0)], "market_indicator": []})[0]   # None != 0.0


def test_新臺幣淨值不讀市場指標_也不呼叫換鍵():
    tables = _Touch({"nav": [N("B", "2026-10-03", 20.0, "TWD")]})
    value, reason, kind = _bv(H("B", ccy="TWD", units=100.0), tables, fx_key_of=lambda c: (_ for _ in ()).throw(AssertionError(c)))
    assert (value, reason, kind) == (2000.0, None, None) and tables.touched == ["nav"]


def test_匯率對齊用淨值日_取不晚於淨值日的最近一筆():
    tables = {"nav": [N("A", "2026-10-03", 10.0)],
              "market_indicator": [FX(FX_USD, "2026-10-01", 29.0), FX(FX_USD, "2026-10-03", 30.0), FX(FX_USD, "2026-10-09", 99.0)]}
    assert _bv(H("A"), tables)[0] == 10.0 * 10.0 * 30.0


# 例外時機（與搬遷前逐字相同）


def test_例外時機_先讀fund_code_再讀nav表():
    with pytest.raises(KeyError) as info:
        _bv({"units_shares": 1.0}, {})   # 兩者都缺：先炸的是 fund_code
    assert info.value.args == ("fund_code",)
    with pytest.raises(KeyError) as info:
        _bv(H("A"), {})
    assert info.value.args == ("nav",)


def test_例外時機_有淨值後才換鍵_換鍵在讀市場指標之前():
    tables = _Touch({"nav": [N("A", "2026-10-03", 10.0, "usd")], "market_indicator": []})
    with pytest.raises(ValueError, match="bad ccy 'usd'"):
        _bv(H("A"), tables)
    assert tables.touched == ["nav"]           # 換鍵炸了，市場指標還沒碰
    tables2 = _Touch({"nav": []})
    assert _bv(H("A"), tables2)[1].code == D.REASON_NAV_ABSENT    # 沒有淨值：永遠不到換鍵


def test_例外時機_名單形狀只在沒有淨值時才驗():
    calls = []

    def provider():
        calls.append(1)
        raise TypeError("stale shape")

    tables = {"nav": [N("A", "2026-10-03", 10.0, "TWD")]}
    assert _bv(H("A", ccy="TWD"), tables, stale=provider)[0] == 100.0 and calls == []
    with pytest.raises(TypeError, match="stale shape"):
        _bv(H("Z"), tables, stale=provider)
    assert calls == [1]


def test_例外時機_讀淨值欄的順序_單位數先於淨值欄():
    tables = {"nav": [{"fund_code": "A", "nav_date": "2026-10-03", "ccy": "USD"}]}   # 缺 nav_orig_ccy
    with pytest.raises(KeyError) as info:
        _bv({"fund_code": "A"}, tables)       # holding 缺 units_shares：先炸單位數
    assert info.value.args == ("units_shares",)
    with pytest.raises(KeyError) as info:
        _bv(H("A"), tables)
    assert info.value.args == ("nav_orig_ccy",)


# ═══════════════════════ 1b. 領域單元：類別加總 ═══════════════════════

_NAV = [N("A", "2026-10-03", 10.0, "USD"), N("B", "2026-10-03", 20.0, "TWD"), N("C", "2026-10-03", 5.0, "EUR"),
        N("D", "2026-10-03", 8.0, "USD")]
_FXT = [FX(FX_USD, "2026-10-03", 30.0), FX(FX_EUR, "2026-10-03", 35.0)]


def test_類別依第一次出現的順序_件數含全部持倉():
    holdings = [H("B", bucket="衛星", ccy="TWD"), H("A"), H("D", bucket="衛星")]
    slots, stale = _cv(holdings, {"nav": _NAV, "market_indicator": _FXT})
    assert list(slots) == ["衛星", "核心"] and stale == {}
    assert [s.count for s in slots.values()] == [2, 1]


def test_累加起點是浮點零_依持倉順序累加_與逐筆浮點加法逐位元相同():
    vals = [0.1, 0.2, 0.3, 1e16, -1e16, 0.7]
    holdings = [H(f"F{i}", cost=v) for i, v in enumerate(vals)]
    slots, _ = _cv(holdings, {}, market=False, track_stale=False)
    expect = 0.0
    for v in vals:
        expect += v
    assert repr(slots["核心"].value) == repr(expect)
    assert repr(slots["核心"].value) != repr(sum(reversed(vals)))     # 順序有意義：倒著加結果不同
    # 起點是 0.0（浮點），整數輸入也得到 float
    s2, _ = _cv([H("A", cost=3), H("B", cost=4)], {}, market=False, track_stale=False)
    assert type(s2["核心"].value) is float and s2["核心"].value == 7.0


def test_缺值是None不是零_第一種缺值定案_後面的值不再累加但件數照加():
    holdings = [H("A", cost=1.0), H("Z"), H("B", ccy="TWD", cost=5.0)]
    slots, _ = _cv(holdings, {"nav": _NAV, "market_indicator": _FXT})
    slot = slots["核心"]
    assert slot.value is None and slot.count == 3
    assert slot.reason == D.MissingReason(D.REASON_NAV_ABSENT) and slot.kind == D.KIND_NAV
    assert slot.value != 0.0
    # 有值的類別：reason／kind 皆 None
    ok, _ = _cv([H("A")], {"nav": _NAV, "market_indicator": _FXT})
    assert ok["核心"].reason is None and ok["核心"].kind is None and ok["核心"].value == 10.0 * 10.0 * 30.0


@pytest.mark.parametrize("first, second, want_code, want_kind", [
    ("A", "Z", D.REASON_FX_ABSENT, D.KIND_FX),      # 先缺匯率、後缺淨值 → 匯率定案
    ("Z", "A", D.REASON_NAV_ABSENT, D.KIND_NAV),    # 先缺淨值、後缺匯率 → 淨值定案
])
def test_同類別多理由_第一種定案(first, second, want_code, want_kind):
    slots, _ = _cv([H(first), H(second)], {"nav": _NAV, "market_indicator": []})
    assert slots["核心"].reason.code == want_code and slots["核心"].kind == want_kind


def test_後面的持倉雖被忽略仍會被呼叫_例外照丟():
    holdings = [H("Z"), H("E")]                       # 第一檔缺淨值（定案）；第二檔淨值幣別小寫 → 換鍵 ValueError
    tables = {"nav": [N("E", "2026-10-03", 1.0, "usd")], "market_indicator": []}
    with pytest.raises(ValueError, match="bad ccy 'usd'"):
        _cv(holdings, tables)


def test_過期併日期_單檔也包成StaleMerge_多檔依持倉順序_同代碼只一次():
    last = {"Z": "2026-09-01", "Y": "2026-09-02"}
    stale = lambda: (frozenset({"Z", "Y"}), 10, last)   # noqa: E731
    one, merges = _cv([H("Z")], {"nav": []}, stale=stale)
    assert one["核心"].reason == D.StaleMerge((("Z", "2026-09-01"),), 10) and merges == {"核心": one["核心"].reason}
    two, merges = _cv([H("Z", policy="P1"), H("Y"), H("Z", policy="P2"), H("Y", policy="P3")], {"nav": []}, stale=stale)
    want = D.StaleMerge((("Z", "2026-09-01"), ("Y", "2026-09-02")), 10)
    assert two["核心"].reason == want and merges["核心"] == want and two["核心"].count == 4
    assert two["核心"].kind == D.KIND_NAV and two["核心"].value is None


def test_過期去重以代碼為準_不同代碼同一天都保留():
    stale = lambda: (frozenset({"Z", "Y"}), 10, {"Z": "2026-09-01", "Y": "2026-09-01"})   # noqa: E731
    slots, merges = _cv([H("Z"), H("Y"), H("Z", policy="P2")], {"nav": []}, stale=stale)
    assert merges["核心"].entries == (("Z", "2026-09-01"), ("Y", "2026-09-01"))


def test_過期只併同為過期的檔_其他理由不併_第一種定案():
    stale = lambda: (frozenset({"Z"}), 10, {"Z": "2026-09-01"})   # noqa: E731
    # 先過期、後缺匯率：reason 仍是 StaleMerge（一筆），不併匯率
    slots, merges = _cv([H("Z"), H("A")], {"nav": _NAV, "market_indicator": []}, stale=stale)
    assert slots["核心"].reason == D.StaleMerge((("Z", "2026-09-01"),), 10)
    # 先缺匯率、後過期：不併（定案的不是過期）
    slots, merges = _cv([H("A"), H("Z")], {"nav": _NAV, "market_indicator": []}, stale=stale)
    assert slots["核心"].reason.code == D.REASON_FX_ABSENT and merges == {}


def test_過期併日期_非市值基準的track_stale為False時不併():
    stale = lambda: (frozenset({"Z", "Y"}), 10, {"Z": "2026-09-01", "Y": "2026-09-02"})   # noqa: E731
    slots, merges = _cv([H("Z"), H("Y")], {"nav": []}, track_stale=False, stale=stale)
    assert merges == {} and slots["核心"].reason == D.MissingReason(D.REASON_NAV_STALE, stale_day="2026-09-01", stale_days=10)


def test_舊形狀過期不併日期():
    stale = lambda: (frozenset({"Z", "Y"}), 10, None)   # noqa: E731
    slots, merges = _cv([H("Z"), H("Y")], {"nav": []}, stale=stale)
    assert merges == {} and slots["核心"].reason == D.MissingReason(D.REASON_NAV_STALE_UNDATED, stale_days=10)


def test_回傳的過期表依定案先後排序_不是類別出現順序():
    stale = lambda: (frozenset({"Z", "Y"}), 10, {"Z": "2026-09-01", "Y": "2026-09-02"})   # noqa: E731
    holdings = [H("A", bucket="甲"), H("Y", bucket="乙"), H("Z", bucket="丙")]
    slots, merges = _cv(holdings, {"nav": _NAV, "market_indicator": _FXT}, stale=stale)
    assert list(slots) == ["甲", "乙", "丙"] and list(merges) == ["乙", "丙"]


def test_空持倉_空結果_且不呼叫任何注入函式():
    def boom(*_a):
        raise AssertionError

    assert D.category_values([], {}, market=True, track_stale=True, category_of=boom, fx_key_of=boom, stale_provider=boom) == ({}, {})


def test_純度_不改輸入():
    holdings = [H("Z"), H("Y"), H("A"), H("B", ccy="TWD", bucket="衛星")]
    tables = {"nav": copy.deepcopy(_NAV), "market_indicator": copy.deepcopy(_FXT)}
    last = {"Z": "2026-09-01", "Y": "2026-09-02"}
    codes = frozenset({"Z", "Y"})
    snap = copy.deepcopy((holdings, tables, last))
    _cv(holdings, tables, stale=lambda: (codes, 10, last))
    _bv(holdings[2], tables)
    assert (holdings, tables, last) == snap and codes == frozenset({"Z", "Y"})


def test_型別都是凍結的():
    for obj in (D.MissingReason(D.REASON_NAV_ABSENT), D.StaleMerge((), 1), D.CategorySlot(None, None, 0, None)):
        assert dataclasses.is_dataclass(obj)
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.code = "x"   # 凍結：任何欄位名都不准寫


def test_代碼與資料類都是英文常數_互不相同():
    codes = {D.REASON_NAV_ABSENT, D.REASON_NAV_STALE, D.REASON_NAV_STALE_UNDATED, D.REASON_FX_ABSENT}
    assert len(codes) == 4 and all(c.isascii() and c.isidentifier() for c in codes)
    assert {D.KIND_NAV, D.KIND_FX} == {"nav", "fx"}
    assert not hasattr(D, "NAV_NOT_READY_DAYS")           # 天數只由呼叫端（ui_v2/thresholds.py 的唯一給值處）帶進來


# ═══════════════════════ 2. 缺值代碼 ↔ 舊中文句子（薄包裝） ═══════════════════════

_TXT_NAV_ABSENT = "⬜ 資料未備：nav 尚無資料"
_TXT_UNDATED = "⬜ 資料未備：最近淨值已超過 10 日"
_TXT_DATED = "⬜ 資料未備：最近一筆淨值 2026-09-01，已超過 10 日"
_TXT_FX_USD = "⬜ 資料未備：缺換算匯率 fx_twd_per_usd"
_TXT_FX_EUR = "⬜ 資料未備：缺換算匯率 fx_twd_per_eur"
_TXT_MERGED = "⬜ 資料未備：最近一筆淨值 2026-09-01（Z）、2026-09-02（Y），已超過 10 日"
_TXT_MERGED_ONE = "⬜ 資料未備：最近一筆淨值 2026-09-01（Z），已超過 10 日"


@pytest.mark.parametrize("missing, text", [
    (None, None),
    (D.MissingReason(D.REASON_NAV_ABSENT), _TXT_NAV_ABSENT),
    (D.MissingReason(D.REASON_NAV_STALE_UNDATED, stale_days=10), _TXT_UNDATED),
    (D.MissingReason(D.REASON_NAV_STALE, stale_day="2026-09-01", stale_days=10), _TXT_DATED),
    (D.MissingReason(D.REASON_FX_ABSENT, fx_key="fx_twd_per_usd"), _TXT_FX_USD),
    (D.MissingReason(D.REASON_FX_ABSENT, fx_key="fx_twd_per_eur"), _TXT_FX_EUR),
    (D.StaleMerge((("Z", "2026-09-01"),), 10), _TXT_MERGED_ONE),
    (D.StaleMerge((("Z", "2026-09-01"), ("Y", "2026-09-02")), 10), _TXT_MERGED),
])
def test_缺值代碼對照舊中文句子(missing, text):
    assert L._missing_text(missing) == text


def test_未知缺值代碼與資料類_丟錯不猜():
    with pytest.raises(ValueError):
        L._missing_text(D.MissingReason("unknown_code"))
    with pytest.raises(ValueError):
        L._class_of_kind("unknown_kind")
    assert L._class_of_kind(None) is None
    assert L._class_of_kind(D.KIND_NAV) == page_health.DATA_CLASSES["nav"] == "淨值"
    assert L._class_of_kind(D.KIND_FX) == page_health.DATA_CLASSES["market_indicator"] == "市場指標"


def _ds(holdings, nav, fx, **kw):
    return DS(holdings, nav, fx, **kw)


@pytest.mark.parametrize("label, holding, kwargs, basis, want", [
    ("缺淨值", H("Z"), dict(nav=[], fx=[]), MV, (None, _TXT_NAV_ABSENT, "淨值")),
    ("舊形狀過期", H("Z"), dict(nav=[], fx=[], nav_not_ready=NNR(["Z"], 10)), MV, (None, _TXT_UNDATED, "淨值")),
    ("有日期過期", H("Z"), dict(nav=[], fx=[], nav_not_ready=NNR(["Z"], 10, {"Z": "2026-09-01"})), MV, (None, _TXT_DATED, "淨值")),
    ("缺匯率美元", H("A"), dict(nav=_NAV, fx=[]), MV, (None, _TXT_FX_USD, "市場指標")),
    ("缺匯率歐元", H("C", ccy="EUR"), dict(nav=_NAV, fx=[]), MV, (None, _TXT_FX_EUR, "市場指標")),
    ("有值", H("A"), dict(nav=_NAV, fx=_FXT), MV, (10.0 * 10.0 * 30.0, None, None)),
    ("成本", H("A", cost=77.0), dict(), COST, (77.0, None, None)),
    ("未知基準走市值路徑", H("A"), dict(nav=_NAV, fx=_FXT), "未知基準", (10.0 * 10.0 * 30.0, None, None)),
    ("基準None走市值路徑缺淨值", H("Z"), dict(nav=[], fx=[]), None, (None, _TXT_NAV_ABSENT, "淨值")),
])
def test_包裝輸出與舊字面逐字相同(label, holding, kwargs, basis, want):
    ds = _ds([holding], kwargs.pop("nav", ()), kwargs.pop("fx", ()), **kwargs)
    assert L.basis_value_with_key(ds, holding, basis) == want
    assert L.basis_value(ds, holding, basis) == want[:2]


def test_包裝_類別層_合併過期句與鍵序與stale_out():
    last = {"Z": "2026-09-01", "Y": "2026-09-02"}
    ds = _ds([H("Z"), H("Y"), H("A", bucket="衛星")], _NAV, _FXT, basis=MV, nav_not_ready=NNR(["Z", "Y"], 10, last))
    stale_out = {"預填": [("X", "2000-01-01")]}
    values = L._category_values(ds, MV, G.NAMES, stale_out)
    assert values["核心"] == {"value": None, "reason": _TXT_MERGED, "count": 2, "_missing_key": "淨值"}
    assert list(values["核心"]) == ["value", "reason", "count", "_missing_key"]
    assert values["衛星"] == {"value": 10.0 * 10.0 * 30.0, "reason": None, "count": 1}
    assert list(values["衛星"]) == ["value", "reason", "count"]            # 有值的類別沒有 _missing_key
    assert stale_out == {"預填": [("X", "2000-01-01")], "核心": [("Z", "2026-09-01"), ("Y", "2026-09-02")]}
    assert type(stale_out["核心"]) is list and all(type(e) is tuple for e in stale_out["核心"])


def test_包裝_單檔過期類別句子帶代碼_與單檔句子不同():
    ds = _ds([H("Z")], (), (), basis=MV, nav_not_ready=NNR(["Z"], 10, {"Z": "2026-09-01"}))
    assert L._category_values(ds, MV, G.NAMES)["核心"]["reason"] == _TXT_MERGED_ONE != _TXT_DATED


def test_包裝_非市值基準不併日期_也不填stale_out():
    ds = _ds([H("Z"), H("Y")], (), (), basis="未知基準",
             nav_not_ready=NNR(["Z", "Y"], 10, {"Z": "2026-09-01", "Y": "2026-09-02"}))
    stale_out = {}
    values = L._category_values(ds, "未知基準", G.NAMES, stale_out)
    assert values["核心"]["reason"] == _TXT_DATED and stale_out == {}


def test_包裝_名單形狀錯_市值基準先於持倉就炸_成本基準不看():
    ds = _ds([H("A", cost=1.0)], _NAV, _FXT, basis=MV, nav_not_ready={"bad": 1})
    with pytest.raises(TypeError, match="nav_not_ready 應為"):
        L._category_values(ds, MV, G.NAMES)
    with pytest.raises(TypeError, match="nav_not_ready 應為"):
        L._category_values(_ds([], _NAV, _FXT, basis=MV, nav_not_ready={"bad": 1}), MV, G.NAMES)   # 沒持倉也炸
    assert L._category_values(ds, COST, G.NAMES)["核心"]["value"] == 1.0                            # 成本基準不讀名單


def test_包裝_換鍵例外的中文訊息原樣穿過():
    ds = _ds([H("A")], [N("A", "2026-10-03", 10.0, "usd")], _FXT)
    with pytest.raises(ValueError, match="沒有對應的換算匯率鍵"):
        L.basis_value_with_key(ds, H("A"), MV)


# ═══════════════════════ 3. 領域層不帶畫面字（跑真的守衛） ═══════════════════════


def _load_port_guard():
    path = _ROOT / "tests" / "test_v2_domain_port.py"
    spec = importlib.util.spec_from_file_location("_alo_core_port_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_holdings無中文字串常數_無禁用呼叫_import在白名單內():
    guard = _load_port_guard()
    source = (_ROOT / "services" / "v2_domain" / "holdings.py").read_text(encoding="utf-8")
    assert guard._domain_violations(source) == []
    # 負控：同一支守衛對「新函式裡塞中文字串」會咬
    assert guard._domain_violations(source + "\n\ndef _x():\n    return '資料未備'\n")
    assert guard._domain_violations(source + "\nimport streamlit\n")


def test_新增的字串常數全是ASCII():
    tree = ast.parse((_ROOT / "services" / "v2_domain" / "holdings.py").read_text(encoding="utf-8"))
    docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                  and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    bad = [n.value for n in ast.walk(tree)
           if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings and not n.value.isascii()]
    assert bad == []


# ═══════════════════════ 4. 與搬遷前實作的差分（git；拿不到就 skip） ═══════════════════════


def _git_show(rel):
    try:
        out = subprocess.run(["git", "show", f"{_BASE_COMMIT}:{rel}"], cwd=_ROOT, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.decode("utf-8") if out.returncode == 0 else None


_OLD = {}


def _old_namespace():
    if "ns" not in _OLD:
        logic_src, hold_src = _git_show("ui_v2/alo/logic.py"), _git_show("services/v2_domain/holdings.py")
        if logic_src is None or hold_src is None:
            _OLD["ns"] = None
        else:
            hold_ns = {"__name__": "_alo_core_old.holdings", "__package__": "services.v2_domain"}
            exec(compile(hold_src, "<old:holdings>", "exec", dont_inherit=True), hold_ns)   # noqa: S102 — repo 自己的歷史版本
            ns = {"__name__": "_alo_core_old.logic", "__package__": "ui_v2.alo"}
            exec(compile(logic_src, "<old:logic>", "exec", dont_inherit=True), ns)          # noqa: S102
            holdings = types.SimpleNamespace(**{k: v for k, v in hold_ns.items() if not k.startswith("__")})
            ns["_v2d"] = types.SimpleNamespace(holdings=holdings)
            ns["exceeds"] = holdings.exceeds
            _OLD["ns"] = ns
    if _OLD["ns"] is None:
        pytest.skip(f"拿不到 {_BASE_COMMIT}（淺層 clone）；主驗收（黃金檔逐位元組）不依賴它")
    return _OLD["ns"]


def _random_case(rnd):
    codes = ["A", "B", "C", "D", "Z", "Y", "Q"]
    ccy_of = {"A": "USD", "B": "TWD", "C": "EUR", "D": "USD", "Z": "USD", "Y": "USD", "Q": "USD"}
    holdings = []
    bucket_of = {c: rnd.choice(["核心", "核心", "衛星", None, "其他"]) for c in codes}   # 同代碼同類別：避免同鍵衝突洗掉全部情境
    for i in range(rnd.randint(0, 6)):
        code = rnd.choice(codes)
        bucket = bucket_of[code]
        units = rnd.choice([10.0, 3, 0.1, 2.5, 0.0, 7])
        cost = rnd.choice([100.0, 0.1, 3, 250.5, 1e-3])
        holdings.append(H(code, bucket=bucket, units=units, cost=cost, policy=rnd.choice(["P1", "P2"]),
                          ccy=ccy_of[code]))
    nav = []
    for code in codes:
        if rnd.random() < (0.2 if code in ("Z", "Y") else 0.7):     # Z／Y 多半沒淨值：才走得到過期那一支
            nav.append(N(code, rnd.choice(["2026-10-01", "2026-10-03"]), rnd.choice([10.0, 5, 0.3, 8.0]),
                         rnd.choice([ccy_of[code]] * 16 + ["TWD", "usd", "JPY"])))
    fx = []
    for key in (FX_USD, FX_EUR, "fx_twd_per_jpy"):
        if rnd.random() < 0.7:
            fx.append(FX(key, rnd.choice(["2026-09-30", "2026-10-03", "2026-10-09"]), rnd.choice([30.0, 0.0, 35.5, 0.1])))
    stale_codes = rnd.sample(["Z", "Y", "Q", "A"], rnd.randint(1, 3))
    shape = rnd.choice(["none", "old", "new", "new", "new", "new", "new", "new", "new", "new", "bad"])
    last = {c: rnd.choice(["2026-09-01", "2026-09-02", "2026-08-20"]) for c in stale_codes}
    nnr = {"none": None, "old": NNR(stale_codes, 10), "new": NNR(stale_codes, 10, last),
           "bad": rnd.choice([{"codes": stale_codes}, {"bad": 1}, NNR(stale_codes, -1, last)])}[shape]
    basis = rnd.choice([MV, MV, MV, COST, None, "未知基準"])
    names = rnd.choice([G.NAMES, G.NAMES, None])
    ds = DS(holdings, nav, fx, basis=basis, names=names, nav_not_ready=nnr)
    if rnd.random() < 0.05:
        ds.pop("nav")
    return ds, basis, names


def test_差分_隨機資料集_類別加總與單檔基準值與搬遷前逐位元組相同():
    old = _old_namespace()
    rnd = random.Random(20261105)
    compared = kinds = 0
    for _ in range(600):
        ds, basis, names = _random_case(rnd)
        so_old, so_new = {"預填": [("X", "2000-01-01")]}, {"預填": [("X", "2000-01-01")]}
        r_old = G.call(old["_category_values"], copy.deepcopy(ds), basis, names, so_old)
        r_new = G.call(L._category_values, copy.deepcopy(ds), basis, names, so_new)
        assert G.dumps(r_old) == G.dumps(r_new), (ds, basis)
        assert G.dumps(G.canon(so_old)) == G.dumps(G.canon(so_new))
        r_old2 = G.call(old["_category_values"], copy.deepcopy(ds), basis, names)
        r_new2 = G.call(L._category_values, copy.deepcopy(ds), basis, names)
        assert G.dumps(r_old2) == G.dumps(r_new2)
        for holding in ds["holding"]:
            b_old, b_new = G.call(old["basis_value_with_key"], copy.deepcopy(ds), holding, basis), \
                G.call(L.basis_value_with_key, copy.deepcopy(ds), holding, basis)
            assert G.dumps(b_old) == G.dumps(b_new), (holding, basis)
            compared += 1
        kinds += 1 if "raise" in r_new else 0
    assert compared > 500 and 0 < kinds < 600       # 防空掃：正常與例外兩支都有走到


def test_差分_讀表惰性_被讀過的鍵集合與搬遷前相同():
    old = _old_namespace()
    rnd = random.Random(7)
    for _ in range(200):
        ds, basis, names = _random_case(rnd)
        s_old, s_new = G.Spy(ds), G.Spy(copy.deepcopy(ds))
        G.call(old["_category_values"], s_old, basis, names)
        G.call(L._category_values, s_new, basis, names)
        assert s_old.touched == s_new.touched, (basis, s_old.touched, s_new.touched)


# ═══════════════════════ 5. 針對新程式碼的突變（黃金檔沒咬到、改由本檔咬） ═══════════════════════

_HOLD_SRC = (_ROOT / "services" / "v2_domain" / "holdings.py").read_text(encoding="utf-8")


def _holdings_with(old=None, new=None):
    source = _HOLD_SRC
    if old is not None:
        assert source.count(old) == 1, f"突變目標要剛好一次：{old!r}（{source.count(old)}）"
        source = source.replace(old, new)
    ns = {"__name__": "services.v2_domain._mutant_holdings_alo_core", "__package__": "services.v2_domain"}
    exec(compile(source, "<mutant:alo_core>", "exec", dont_inherit=True), ns)   # noqa: S102 — repo 自己的原始碼（改一處）
    return types.SimpleNamespace(**{k: v for k, v in ns.items() if not k.startswith("__")})


def _probe(mod):
    """三個黃金檔沒覆蓋到的探針：非市值基準不併日期／整數輸入的累加型別／不同代碼同一天的過期去重。"""
    mk = lambda: (frozenset({"Z", "Y"}), 10, {"Z": "2026-09-01", "Y": "2026-09-01"})   # noqa: E731
    run = lambda holdings, tables, **kw: mod.category_values(                         # noqa: E731
        holdings, tables, market=kw.get("market", True), track_stale=kw.get("track_stale", True),
        category_of=lambda h: h["bucket"], fx_key_of=_fx_key, stale_provider=mk)
    p1 = run([H("Z"), H("Y")], {"nav": []}, track_stale=False)
    p2 = run([H("B", ccy="TWD", units=2, bucket="衛星"), H("B", ccy="TWD", units=3, bucket="衛星", policy="P2")],
             {"nav": [N("B", "2026-10-03", 5, "TWD")]})
    p3 = run([H("Z"), H("Y"), H("Z", policy="P2")], {"nav": []})
    return repr((p1, [(c, type(s.value).__name__, s.value) for c, s in p2[0].items()], p3))


@pytest.mark.parametrize("name, old, new", [
    ("M43_is_stale_ignores_track_stale", "is_stale = track_stale and value is None", "is_stale = value is None"),
    ("M45_slot_start_int_zero", "slots.setdefault(cat, [0.0, None, 0, None])", "slots.setdefault(cat, [0, None, 0, None])"),
    ("M46_dedupe_by_day", "code not in {c for c, _ in stale[cat].entries}", "reason.stale_day not in {d for _, d in stale[cat].entries}"),
])
def test_突變被本檔探針咬到(name, old, new):
    assert _probe(_holdings_with(old, new)) != _probe(_holdings_with()), name


def test_探針對照組_未突變的載入器等於工作樹模組():
    assert _probe(_holdings_with()) == _probe(D)


# ═══════════════════════ 6. shim 面 ═══════════════════════


def test_shim只轉出模組物件_新函式經_v2d_holdings_取用():
    assert v2_domain_shim.holdings is D
    for name in ("REASON_NAV_ABSENT", "REASON_NAV_STALE", "REASON_NAV_STALE_UNDATED", "REASON_FX_ABSENT", "KIND_NAV", "KIND_FX",
                 "MissingReason", "StaleMerge", "CategorySlot", "basis_value_with_reason", "category_values"):
        assert name in D.__all__ and hasattr(D, name), name
    assert len(set(D.__all__)) == len(D.__all__) and all(hasattr(D, n) for n in D.__all__)
    assert set(v2_domain_shim.__all__) == {"deviation", "freshness", "holdings", "nav_metrics", "periods", "rule_filter"}


def test_ui_v2包裝只經_v2d_holdings_碰領域():
    tree = ast.parse((_ROOT / "ui_v2" / "alo" / "logic.py").read_text(encoding="utf-8"))
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not any(isinstance(n, ast.ImportFrom) and (n.module or "").startswith("services") for n in imports)
    assert not any(isinstance(n, ast.Import) and any(a.name.startswith("services") for a in n.names) for n in imports)
