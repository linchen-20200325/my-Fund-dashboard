# -*- coding: utf-8 -*-
"""BL-0536-H1＋H1b：`services/v2_domain/normalization.py`（🌍 TAIEX vs S&P 500 歸一化比較）的守衛。

規則出處：客戶 `DEC-2026-11-03-01`（逐字 `docs/evidence/decisions/2026-11-03_mkt_wireframe_ruling.md`）；
`docs/v2/81_new_ui2_wireframe_01_market.md` 第 7 節 Q2-a／b／c A、第 4.1 節情境表；UI-13（基準值 100，`DEC-2026-11-02-07`）；
H1b：客戶 `DEC-2026-11-03-04` A2／B2／C2（逐字 `docs/evidence/decisions/2026-11-03_normalization_abc_and_min_cost_rule.md`；
讀法與殘留邊界見 `docs/v2/81` 第 9 節 H1b 註記）。

四組：
(a) golden：手算的小序列（算式寫在註解裡；刻意挑二進位可精確表示的比值，故用 `==` 比對，不依賴浮點加總）；
(b) property：本環境與 requirements-dev 皆無 hypothesis → 用固定種子的隨機迴圈；
(c) 邊界：無共同日、一條空、一條全 None、單點、終點不同、期間不足、重複日期、未排序、非有限值、週末起點；
    H1b：A2 比較視窗涵蓋、殘留邊界釘住現行行為、B2／C2 退回單序列；
(d) 分層：AST 只准標準庫（`__future__`／`dataclasses`／`datetime`）＋ `services.v2_domain` 同套件；
    非 docstring 的字串常數不得含中文。另 `tests/test_v2_domain_port.py` 的套件級守衛會自動涵蓋本檔。
"""

from __future__ import annotations

import ast
import dataclasses
import math
import pathlib
import random
import sys
from datetime import date, datetime, timedelta

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:  # 本機以 `--noconftest` 跑
    sys.path.insert(0, str(_ROOT))

from services.v2_domain import normalization as nz  # noqa: E402
from services.v2_domain import periods  # noqa: E402

NAN = float("nan")
INF = float("inf")


def P(day, value):
    return {"obs_date": day, "value_num": value}


def by_key(result):
    return {s.key: s for s in result.series}


def pts(series_result):
    return [(p.obs_date, p.value) for p in series_result.points]


# ═══════════════════════ (a) golden ═══════════════════════
#
# 期間 3M。
# taiex 最後有效觀測日 2026-04-10（五）→ 自身起點 months_back(…, 3) = 2026-01-10（六）；最早有效 2026-01-09 ≤ 起點 → 涵蓋。
# sp500 最後有效觀測日 2026-04-13（一）→ 自身起點 2026-01-13（二）；最早有效 2026-01-12 ≤ 起點 → 涵蓋。
# 比較視窗起點 ＝ max(2026-01-10, 2026-01-13) ＝ 2026-01-13（Q2-a A：較晚者）。
# 2026-01-13：taiex 為 None、sp500 = 40.0 → 不是共同有效日；2026-01-14 兩條都有 → 基準日 2026-01-14（≠ 視窗起點）。
# taiex 2026-01-12 = 100.0 在比較視窗之前 → pair 模式不輸出、也不是基準。
# 共同有效日 ＝ {01-14, 01-16}（01-15 sp500 為 None；04-10／04-13 不同日）→ 共 2 天，達「一個點畫不成線」的 2 天下限。
# taiex 基準原值 200：01-14 200/200*100 = 100；01-15 250/200*100 = 125；01-16 150/200*100 = 75；
#   04-10 300/200*100 = 150 → 期間漲跌 +50。
# sp500 基準原值 40：01-14 100；01-15 None（缺口保留）；01-16 30/40*100 = 75；04-13 50/40*100 = 125 → 期間漲跌 +25。
# 兩條各自畫到自己最後一天（04-10 與 04-13；Q2-b A）。

TAIEX = [
    P("2026-01-09", 80.0), P("2026-01-12", 100.0), P("2026-01-13", None),
    P("2026-01-14", 200.0), P("2026-01-15", 250.0), P("2026-01-16", 150.0), P("2026-04-10", 300.0),
]
SP500 = [
    P("2026-01-12", 999.0), P("2026-01-13", 40.0), P("2026-01-14", 40.0),
    P("2026-01-15", None), P("2026-01-16", 30.0), P("2026-04-13", 50.0),
]


def test_golden_pair_基準日晚於視窗起點_各自終點不同():
    r = nz.normalize_pair({"taiex": TAIEX, "sp500": SP500}, "3M")
    assert (r.status, r.mode, r.period, r.fallback_reason) == (nz.STATUS_OK, nz.MODE_PAIR, "3M", None)
    assert r.window_start == "2026-01-13"
    assert r.base_date == "2026-01-14"
    assert r.base_value == 100 == nz.BASE_VALUE
    assert r.missing_keys == ()
    assert [s.key for s in r.series] == ["taiex", "sp500"]
    t, s = by_key(r)["taiex"], by_key(r)["sp500"]
    assert (t.status, t.own_window_start, t.last_obs_date, t.base_raw) == ("ok", "2026-01-10", "2026-04-10", 200.0)
    assert pts(t) == [("2026-01-14", 100.0), ("2026-01-15", 125.0), ("2026-01-16", 75.0), ("2026-04-10", 150.0)]
    assert (t.last_normalized, t.period_change) == (150.0, 50.0)
    assert (s.status, s.own_window_start, s.last_obs_date, s.base_raw) == ("ok", "2026-01-13", "2026-04-13", 40.0)
    assert pts(s) == [("2026-01-14", 100.0), ("2026-01-15", None), ("2026-01-16", 75.0), ("2026-04-13", 125.0)]
    assert (s.last_normalized, s.period_change) == (125.0, 25.0)


def test_golden_沒有共同終點日欄位():
    # Q2-b A：不得有一個暗示兩條同日結束的共用欄位
    names = {f.name for f in dataclasses.fields(nz.NormalizedComparison)}
    assert not any("end" in n or "last" in n for n in names), names


def test_golden_single_缺一條_基準日改取該條自己視窗首筆():
    # sp500 缺（None）→ taiex 單獨：自身視窗起點 2026-01-10；視窗內首筆有效 2026-01-12（100.0）為基準。
    # 01-12 100/100*100 = 100；01-13 None；01-14 200；01-15 250；01-16 150；04-10 300 → 期間漲跌 +200。
    r = nz.normalize_pair({"taiex": TAIEX, "sp500": None}, "3M")
    assert (r.status, r.mode, r.window_start, r.base_date, r.base_value) == (
        nz.STATUS_OK, nz.MODE_SINGLE, "2026-01-10", "2026-01-12", 100)
    assert r.missing_keys == ("sp500",)
    t, s = by_key(r)["taiex"], by_key(r)["sp500"]
    assert pts(t) == [("2026-01-12", 100.0), ("2026-01-13", None), ("2026-01-14", 200.0),
                      ("2026-01-15", 250.0), ("2026-01-16", 150.0), ("2026-04-10", 300.0)]
    assert (t.last_obs_date, t.last_normalized, t.period_change, t.base_raw) == ("2026-04-10", 300.0, 200.0, 100.0)
    assert (s.status, s.points, s.last_obs_date, s.own_window_start) == (nz.SERIES_MISSING, (), None, None)


def test_golden_single_另一條全None也算缺():
    r = nz.normalize_pair({"taiex": [P("2026-01-14", None), P("2026-01-15", NAN)], "sp500": SP500}, "3M")
    assert (r.status, r.mode, r.missing_keys) == (nz.STATUS_OK, nz.MODE_SINGLE, ("taiex",))
    s = by_key(r)["sp500"]
    # sp500 自身起點 2026-01-13，首筆有效 01-13 = 40 → 01-13 100；01-14 100；01-15 None；01-16 75；04-13 125
    assert r.base_date == "2026-01-13"
    assert pts(s) == [("2026-01-13", 100.0), ("2026-01-14", 100.0), ("2026-01-15", None),
                      ("2026-01-16", 75.0), ("2026-04-13", 125.0)]
    assert by_key(r)["taiex"].status == nz.SERIES_MISSING


def test_golden_視窗起點在週末_基準取其後第一個共同日():
    # A2：兩條最後一天都是 2026-04-10（五）→ 起點 2026-01-10（六，無觀測日）；兩條 01-09 都有值 → 歷史延伸到起點之前
    # → 涵蓋（不是歷史不足）；01-12（一）是起點後第一個共同有效日 ＝ 基準（不是容忍幾天，是「視窗內第一個共同有效日」）。
    a = [P("2026-01-09", 1.0), P("2026-01-12", 8.0), P("2026-04-10", 10.0)]
    b = [P("2026-01-09", 1.0), P("2026-01-12", 4.0), P("2026-04-10", 2.0)]
    r = nz.normalize_pair({"a": a, "b": b}, "3M")
    assert (r.status, r.window_start, r.base_date) == ("ok", "2026-01-10", "2026-01-12")
    assert pts(by_key(r)["a"]) == [("2026-01-12", 100.0), ("2026-04-10", 125.0)]   # 10/8*100
    assert pts(by_key(r)["b"]) == [("2026-01-12", 100.0), ("2026-04-10", 50.0)]    # 2/4*100


def test_golden_基準日恰為比較視窗起點_且不四捨五入():
    # 兩條最後一天都是 2026-04-13（一）→ 起點 2026-01-13（二）；兩條在 01-13 當天都有效 → 基準日＝視窗起點。
    # 01-12 在視窗之前（兩條都有效）：若視窗過濾誤寫成「>」，基準會跳到 01-14，本案即紅。
    # 比值刻意取非二進位可精確表示者（÷3、÷7），期望值以同一運算式 value / base * 100 算出 → 任何 round() 都會紅。
    a = [P("2026-01-12", 1.0), P("2026-01-13", 3.0), P("2026-01-14", 7.0), P("2026-04-13", 5.0)]
    b = [P("2026-01-12", 1.0), P("2026-01-13", 7.0), P("2026-01-14", 1.0), P("2026-04-13", 22.0)]
    r = nz.normalize_pair({"a": a, "b": b}, "3M")
    assert (r.status, r.window_start, r.base_date) == ("ok", "2026-01-13", "2026-01-13")
    assert pts(by_key(r)["a"]) == [("2026-01-13", 100.0), ("2026-01-14", 7.0 / 3.0 * 100),
                                   ("2026-04-13", 5.0 / 3.0 * 100)]
    assert pts(by_key(r)["b"]) == [("2026-01-13", 100.0), ("2026-01-14", 1.0 / 7.0 * 100),
                                   ("2026-04-13", 22.0 / 7.0 * 100)]
    assert by_key(r)["a"].period_change == 5.0 / 3.0 * 100 - 100


# ─────── 與 Old UI 先例 `services/benchmark_compare.py::rebased_pair` 對照（`docs/v2/81` 第 6 節計畫） ───────
# 只在測試裡唯讀 import；L2 本體不得 import 它（見分層守衛正控）。它依賴 pandas（CI 有）：
# 本環境缺 pandas 時以 importorskip 跳過「只因缺第三方套件」的這三支，不影響其餘測試。
# 先例語意：窗口＝兩序列共同日期；終點＝最後共同日；起點＝終點往回推 `days` 個日曆日；共同歷史不足時縮成全期。
# Q2 裁示不同處：(1) 終點各畫到自己最後觀測日（Q2-b A）；(2) 不足就標不足、不縮短（Q2-a A）；
# (3) H1b：先例在沒有共同日時回 None（整張不畫）；H1b（C2）停更時另一條退回單序列照畫、停更那條標原因。
# 相同處：兩條最後一天相同、`days` 取「3 個月」的日曆日數時，兩者窗口與共同錨日一致，共同日上的歸一化值逐位元相同。


def _rebased(a_points, b_points, days):
    pd = pytest.importorskip("pandas")
    from services.benchmark_compare import rebased_pair   # 唯讀先例，只在測試中使用

    def series(points):
        valid = [(p["obs_date"], p["value_num"]) for p in points if periods.is_number(p["value_num"])]
        return pd.Series([v for _, v in valid], index=pd.to_datetime([d for d, _ in valid]))

    return rebased_pair(series(a_points), series(b_points), days=days, fund_label="a", bench_label="b")


_SAME_END_A = [P("2026-01-09", 5.0), P("2026-01-12", 8.0), P("2026-01-13", 9.0), P("2026-01-14", None),
               P("2026-02-02", 11.0), P("2026-04-10", 10.0)]
_SAME_END_B = [P("2026-01-09", 2.0), P("2026-01-12", 4.0), P("2026-01-14", 3.0), P("2026-02-02", 6.0),
               P("2026-04-10", 5.0)]


def test_先例對照_語意重疊處_共同錨日與共同日數值相同():
    days = (date(2026, 4, 10) - periods.months_back(date(2026, 4, 10), 3)).days   # 3M 視窗的日曆日數（90）
    old = _rebased(_SAME_END_A, _SAME_END_B, days)
    r = nz.normalize_pair({"a": _SAME_END_A, "b": _SAME_END_B}, "3M")
    assert r.status == "ok" and old is not None
    assert old.index[0].date().isoformat() == r.base_date == "2026-01-12"
    common = [d for d in old.dropna().index]
    assert len(common) >= 3
    mine = {k: dict(pts(by_key(r)[k])) for k in ("a", "b")}
    for stamp in common:
        day = stamp.date().isoformat()
        assert mine["a"][day] == old.loc[stamp, "a"] and mine["b"][day] == old.loc[stamp, "b"], day


def test_先例對照_終點_先例截到最後共同日_H1各畫到自己最後一天():
    a = _SAME_END_A + [P("2026-04-13", 12.0)]          # a 比 b 多一天
    old = _rebased(a, _SAME_END_B, 90)
    r = nz.normalize_pair({"a": a, "b": _SAME_END_B}, "3M")
    assert old.index[-1].date().isoformat() == "2026-04-10"                  # 先例：最後共同日
    assert by_key(r)["a"].last_obs_date == "2026-04-13" == pts(by_key(r)["a"])[-1][0]   # H1：自己的最後一天
    assert by_key(r)["b"].last_obs_date == "2026-04-10"


def test_先例對照_歷史不足_先例縮成全期_H1標不足():
    short_a = [P("2025-06-02", 8.0), P("2025-09-01", 9.0), P("2026-04-10", 10.0)]
    short_b = [P("2025-06-02", 4.0), P("2025-09-01", 5.0), P("2026-04-10", 5.0)]
    old = _rebased(short_a, short_b, 365 * 3)
    assert old is not None and old.index[0].date().isoformat() == "2025-06-02"   # 先例：縮成共同全期照畫
    r = nz.normalize_pair({"a": short_a, "b": short_b}, "3Y")
    assert r.status == nz.STATUS_INSUFFICIENT and all(s.points == () for s in r.series)   # H1：不縮短，標不足


def test_先例對照_停更_先例回None_H1b另一條退回單序列():
    stale = [P("2025-08-01", 1.0), P("2025-10-01", 2.0), P("2025-12-01", 3.0)]
    assert _rebased(stale, SP500, 90) is None                                     # 先例：無共同日 → 整張不畫
    r = nz.normalize_pair({"a": stale, "b": SP500}, "3M")
    assert (r.mode, r.status) == (nz.MODE_FALLBACK, nz.STATUS_OK)                # H1b：sp500 單獨照畫
    assert by_key(r)["a"].status == nz.STATUS_NO_COMMON_BASE and by_key(r)["a"].points == ()


# ═══════════════════════ (c) 邊界 ═══════════════════════


def test_無共同日_no_common_base_不出線():
    a = [P("2026-01-09", 1.0), P("2026-01-12", 2.0), P("2026-04-10", 3.0)]
    b = [P("2026-01-09", 1.0), P("2026-01-13", 2.0), P("2026-04-09", 3.0), P("2026-04-10", None)]
    # b 最後有效 04-09 → 起點 01-09；a 起點 01-10；視窗起點 01-10；a 有效 {01-12, 04-10}、b 有效 {01-13, 04-09} → 無交集
    # 兩條在比較視窗內各有 2 筆有效值（只是日期錯開，不是停更）→ 不退回單序列，兩條都 withheld（C2 只管停更）。
    r = nz.normalize_pair({"a": a, "b": b}, "3M")
    assert (r.status, r.mode, r.base_date, r.base_value, r.fallback_reason) == (
        nz.STATUS_NO_COMMON_BASE, nz.MODE_PAIR, None, None, None)
    assert all(s.status == nz.SERIES_WITHHELD and s.points == () and s.last_normalized is None for s in r.series)
    assert by_key(r)["b"].last_obs_date == "2026-04-09"   # 不出線仍帶自身資料日


def test_只有一個共同日_too_few_common_days_不出線():
    a = [P("2026-01-09", 1.0), P("2026-01-12", 2.0), P("2026-04-10", 3.0)]
    b = [P("2026-01-09", 1.0), P("2026-01-12", 2.0), P("2026-04-09", 3.0)]
    # 兩條在比較視窗內各有 2 筆有效值（都沒停更）→ 不退回單序列。
    r = nz.normalize_pair({"a": a, "b": b}, "3M")
    assert (r.status, r.mode, r.base_date, r.fallback_reason) == (nz.STATUS_TOO_FEW_COMMON_DAYS, nz.MODE_PAIR, None, None)
    assert all(s.status == nz.SERIES_WITHHELD and s.points == () for s in r.series)


def test_兩條各有很多點但只共用一天_仍是too_few_common_days():
    # Q2-a A 原文「視窗內共同有值日不足 2 天 → 無法判定」：以共同有效日計，不以各條點數計。
    t = [p for p in TAIEX if p["obs_date"] != "2026-01-16"]   # 拿掉 01-16 → 共同有效日只剩 01-14
    r = nz.normalize_pair({"taiex": t, "sp500": SP500}, "3M")
    assert (r.status, r.base_date) == (nz.STATUS_TOO_FEW_COMMON_DAYS, None)
    assert all(s.status == nz.SERIES_WITHHELD and s.points == () for s in r.series)


# ─────── H1b（`DEC-2026-11-03-04`）A2：涵蓋按比較視窗判定；B2／C2：退回單序列 ───────


def test_A2_各自起點落在週末_比較視窗已涵蓋_改判可比較():
    # H1 字面讀法（已 superseded）會判 insufficient：a 自 2026-01-12（一）起有資料，自身起點 2026-01-10（六）。
    # A2：比較視窗起點 W ＝ max(01-10, 01-13) ＝ 01-13（b 的起點）；a 首筆 01-12 ≤ W、b 首筆 01-12 ≤ W → 兩條都涵蓋。
    # 01-13 兩條都有效 → 基準 01-13；共同有效日 {01-13, 02-02}。a 02-02 4/2*100 = 200、04-10 3/2*100 = 150；
    # b 02-02 1/2*100 = 50、04-13 3/2*100 = 150。
    a = [P("2026-01-12", 1.0), P("2026-01-13", 2.0), P("2026-02-02", 4.0), P("2026-04-10", 3.0)]
    b = [P("2026-01-12", 1.0), P("2026-01-13", 2.0), P("2026-02-02", 1.0), P("2026-04-13", 3.0)]
    r = nz.normalize_pair({"a": a, "b": b}, "3M")
    assert (r.status, r.mode, r.window_start, r.base_date, r.fallback_reason) == (
        nz.STATUS_OK, nz.MODE_PAIR, "2026-01-13", "2026-01-13", None)
    assert by_key(r)["a"].own_window_start == "2026-01-10"      # 自身起點仍照實回報；涵蓋改看 W
    assert pts(by_key(r)["a"]) == [("2026-01-13", 100.0), ("2026-02-02", 200.0), ("2026-04-10", 150.0)]
    assert pts(by_key(r)["b"]) == [("2026-01-13", 100.0), ("2026-02-02", 50.0), ("2026-04-13", 150.0)]


def test_A2_首筆恰在比較視窗起點當天_涵蓋():
    # b 最後一天 04-13 → W ＝ 01-13；b 有史以來第一筆恰為 01-13 → 「W 當日或之前有有效觀測」成立 → 涵蓋（邊界取等號）。
    # 共同有效日 {01-13, 02-02}：a 02-02 4/2*100 = 200、04-10 3/2*100 = 150；b 02-02 1/2*100 = 50、04-13 3/2*100 = 150。
    a = [P("2026-01-09", 1.0), P("2026-01-13", 2.0), P("2026-02-02", 4.0), P("2026-04-10", 3.0)]
    b = [P("2026-01-13", 2.0), P("2026-02-02", 1.0), P("2026-04-13", 3.0)]
    r = nz.normalize_pair({"a": a, "b": b}, "3M")
    assert (r.status, r.mode, r.window_start, r.base_date, r.fallback_reason) == (
        nz.STATUS_OK, nz.MODE_PAIR, "2026-01-13", "2026-01-13", None)
    assert pts(by_key(r)["b"]) == [("2026-01-13", 100.0), ("2026-02-02", 50.0), ("2026-04-13", 150.0)]


def test_A2_不設容忍_平日起點晚一天開始仍是真正歷史不足():
    # b 最後一天 04-13（一）→ W ＝ 01-13（二，平日）。a 首筆 01-14（三）：只晚 1 天，但 W 是平日、W 之前 a 沒有任何觀測
    # → 單憑資料就是歷史沒涵蓋到 W → insufficient（任何「容忍 1 天」都會把它判成涵蓋，本案即紅）。
    a = [P("2026-01-14", 1.0), P("2026-01-15", 2.0), P("2026-04-10", 3.0)]
    r = nz.normalize_pair({"a": a, "b": SP500}, "3M")
    assert by_key(r)["a"].status == nz.STATUS_INSUFFICIENT
    assert (r.mode, r.fallback_reason) == (nz.MODE_FALLBACK, nz.STATUS_INSUFFICIENT)


def test_A2_殘留邊界_待客戶確認_起點週末而首筆恰為下個交易日_現行判不足():
    # ⚠️ 殘留邊界（待客戶確認，`docs/v2/81` 第 9 節 H1b 註記）：兩條最後一天都是 04-10（五）→ W ＝ 01-10（六）。
    # a 有史以來第一筆恰為 01-12（一）＝ W 之後第一個交易日。週末本來就沒有觀測，但單憑資料無法證明 a 的歷史
    # 「延伸到 W」（要日曆或容忍才能證明；裁示禁止兩者）→ 現行規則判 a insufficient，b 退回單序列。
    # 本測試釘住現行行為；客戶若另有裁示，改這裡並重跑公式稽核。
    a = [P("2026-01-12", 8.0), P("2026-02-02", 9.0), P("2026-04-10", 10.0)]
    b = [P("2026-01-09", 1.0), P("2026-01-12", 4.0), P("2026-04-10", 2.0)]
    r = nz.normalize_pair({"a": a, "b": b}, "3M")
    assert (r.status, r.mode, r.fallback_reason) == (nz.STATUS_OK, nz.MODE_FALLBACK, nz.STATUS_INSUFFICIENT)
    assert by_key(r)["a"].status == nz.STATUS_INSUFFICIENT and by_key(r)["a"].points == ()
    # b 單獨：自身起點 01-10，視窗內首筆有效 01-12（4.0）→ 01-12 100；04-10 2/4*100 = 50
    assert (r.window_start, r.base_date) == ("2026-01-10", "2026-01-12")
    assert pts(by_key(r)["b"]) == [("2026-01-12", 100.0), ("2026-04-10", 50.0)]
    # 同一個殘留邊界在單序列模式（另一條缺）也一樣判不足（＝ `periods` 已知限制）。
    assert nz.normalize_pair({"a": a, "b": None}, "3M").status == nz.STATUS_INSUFFICIENT


def test_B2_一條真正歷史不足_另一條退回單序列_不足者明確標示():
    # taiex 首筆 02-02；W ＝ max(taiex 01-10, sp500 01-13) ＝ 01-13；02-02 > W → taiex 真正歷史不足。
    # sp500 退回單序列：自身視窗起點 01-13、視窗內首筆有效 01-13（40）→ 01-13 100；01-14 100；01-15 None；01-16 75；04-13 125。
    short = [P("2026-02-02", 1.0), P("2026-04-10", 2.0)]
    r = nz.normalize_pair({"taiex": short, "sp500": SP500}, "3M")
    assert (r.status, r.mode, r.fallback_reason, r.missing_keys) == (
        nz.STATUS_OK, nz.MODE_FALLBACK, nz.STATUS_INSUFFICIENT, ())
    assert (r.window_start, r.base_date, r.base_value) == ("2026-01-13", "2026-01-13", 100)
    t, s = by_key(r)["taiex"], by_key(r)["sp500"]
    assert (t.status, t.points, t.base_raw, t.last_normalized, t.period_change) == (nz.STATUS_INSUFFICIENT, (), None, None, None)
    assert (t.own_window_start, t.last_obs_date) == ("2026-01-10", "2026-04-10")   # 不足者仍帶自身資料日
    assert pts(s) == [("2026-01-13", 100.0), ("2026-01-14", 100.0), ("2026-01-15", None),
                      ("2026-01-16", 75.0), ("2026-04-13", 125.0)]
    # 被畫那條與「另一條傳 None」時逐欄相同（不足那條的資料不影響它）
    assert s == by_key(nz.normalize_pair({"taiex": None, "sp500": SP500}, "3M"))["sp500"]


def test_B2_不足者是較晚結束那條_被畫那條用自己的視窗_不被比較視窗縮短():
    # sp_short 最後一天 04-13 → 自身起點 01-13 ＝ W；首筆 03-02 > W → 不足。taiex 退回單序列用**自己的**視窗
    # （起點 01-10、首筆有效 01-12 ＝ 100），不是比較視窗 W（若誤用 W，基準會變 01-14）。
    sp_short = [P("2026-03-02", 1.0), P("2026-04-13", 2.0)]
    r = nz.normalize_pair({"taiex": TAIEX, "sp500": sp_short}, "3M")
    assert (r.status, r.mode, r.window_start, r.base_date) == (nz.STATUS_OK, nz.MODE_FALLBACK, "2026-01-10", "2026-01-12")
    assert pts(by_key(r)["taiex"]) == [("2026-01-12", 100.0), ("2026-01-13", None), ("2026-01-14", 200.0),
                                       ("2026-01-15", 250.0), ("2026-01-16", 150.0), ("2026-04-10", 300.0)]
    assert by_key(r)["sp500"].status == nz.STATUS_INSUFFICIENT


def test_B2_退回那條自己的視窗也不足_兩條都不畫():
    # a（較晚結束）首筆 03-02 > W ＝ 01-13 → 不足；b 涵蓋 W（首筆 01-12 ≤ 01-13），但退回單序列後以自己的視窗
    # （起點 01-10（六））判定，首筆 01-12 > 01-10 → 也不足（同上殘留邊界）。兩條都不畫，不縮短冒充。
    a = [P("2026-03-02", 1.0), P("2026-04-13", 2.0)]
    b = [P("2026-01-12", 1.0), P("2026-01-13", 2.0), P("2026-04-10", 3.0)]
    r = nz.normalize_pair({"a": a, "b": b}, "3M")
    assert (r.status, r.mode, r.fallback_reason, r.base_date) == (
        nz.STATUS_INSUFFICIENT, nz.MODE_FALLBACK, nz.STATUS_INSUFFICIENT, None)
    assert all(s.status == nz.STATUS_INSUFFICIENT and s.points == () for s in r.series)


def test_C2_一條停更超過期間_另一條退回單序列_停更者標no_common_base():
    # a 最後一天 2025-12-01（自身起點 2025-09-01）；W ＝ 2026-01-13（sp500 起點）之後 a 沒有任何有效值 → 停更。
    # sp500 單獨照畫（同 B2 golden 的 sp500）；a 標真正原因 no_common_base；只有一個 100、只在 01-13。
    a = [P("2025-08-01", 1.0), P("2025-10-01", 2.0), P("2025-12-01", 3.0)]
    r = nz.normalize_pair({"a": a, "b": SP500}, "3M")
    assert (r.status, r.mode, r.fallback_reason, r.window_start, r.base_date) == (
        nz.STATUS_OK, nz.MODE_FALLBACK, nz.STATUS_NO_COMMON_BASE, "2026-01-13", "2026-01-13")
    stale, s = by_key(r)["a"], by_key(r)["b"]
    assert (stale.status, stale.points, stale.last_obs_date, stale.own_window_start) == (
        nz.STATUS_NO_COMMON_BASE, (), "2025-12-01", "2025-09-01")
    assert pts(s)[0] == ("2026-01-13", 100.0) and s.period_change == 25.0


def test_C2_停更在比較視窗內只剩一個共同日_too_few_common_days_另一條退回單序列():
    # a 最後一天 01-14（自身起點 2025-10-14）；W ＝ 01-13；a 在 W 之後只有 01-14 一筆（停在這天）、與 sp500 共用 → 共同日 1 天。
    a = [P("2025-10-01", 1.0), P("2025-12-01", 2.0), P("2026-01-14", 3.0)]
    r = nz.normalize_pair({"a": a, "b": SP500}, "3M")
    assert (r.status, r.mode, r.fallback_reason) == (nz.STATUS_OK, nz.MODE_FALLBACK, nz.STATUS_TOO_FEW_COMMON_DAYS)
    assert by_key(r)["a"].status == nz.STATUS_TOO_FEW_COMMON_DAYS and by_key(r)["a"].points == ()
    assert r.base_date == "2026-01-13" and pts(by_key(r)["b"])[0] == ("2026-01-13", 100.0)


def test_C2_兩條都停更_不退回單序列_兩條withheld():
    # 3M：a 最後一天 04-10 → 起點 01-10；b 最後一天 04-09 → 起點 01-09；W ＝ 01-10。
    # W 之後 a 只有 04-10、b 只有 04-09（兩條都不足 2 筆，原因不只落在一條）→ 共同日 0 → 不退回，兩條 withheld。
    a = [P("2026-01-01", 1.0), P("2026-04-10", 2.0)]
    b = [P("2026-01-01", 1.0), P("2026-04-09", 2.0)]
    r = nz.normalize_pair({"a": a, "b": b}, "3M")
    assert (r.status, r.mode, r.fallback_reason, r.base_date) == (nz.STATUS_NO_COMMON_BASE, nz.MODE_PAIR, None, None)
    assert all(s.status == nz.SERIES_WITHHELD and s.points == () for s in r.series)


def test_C2_停更且唯一一筆不是共同日_no_common_base():
    # a 在 W 之後只有 01-15 一筆（sp500 該日 None）→ 共同日 0 → no_common_base；a 停更 → sp500 退回單序列。
    a = [P("2025-10-01", 1.0), P("2026-01-15", 3.0)]
    r = nz.normalize_pair({"a": a, "b": SP500}, "3M")
    assert (r.mode, r.fallback_reason, by_key(r)["a"].status) == (
        nz.MODE_FALLBACK, nz.STATUS_NO_COMMON_BASE, nz.STATUS_NO_COMMON_BASE)


def test_沿用限制_非int_float子類的數值當缺口_adapter須先轉float():
    import decimal
    a = [P("2026-01-09", 1.0), P("2026-01-12", 8.0), P("2026-02-02", decimal.Decimal("9")), P("2026-04-10", 10.0)]
    b = [P("2026-01-09", 1.0), P("2026-01-12", 4.0), P("2026-02-02", 5.0), P("2026-04-10", 2.0)]
    r = nz.normalize_pair({"a": a, "b": b}, "3M")
    assert dict(pts(by_key(r)["a"]))["2026-02-02"] is None


def test_兩條都不足():
    r = nz.normalize_pair({"a": [P("2026-04-01", 1.0), P("2026-04-10", 2.0)],
                           "b": [P("2026-04-02", 1.0), P("2026-04-10", 2.0)]}, "1Y")
    assert r.status == nz.STATUS_INSUFFICIENT
    assert all(s.status == nz.STATUS_INSUFFICIENT and s.points == () for s in r.series)


def test_單序列不足():
    r = nz.normalize_pair({"a": [P("2026-04-01", 1.0), P("2026-04-10", 2.0)], "b": None}, "3M")
    assert (r.status, r.mode, r.missing_keys) == (nz.STATUS_INSUFFICIENT, nz.MODE_SINGLE, ("b",))
    assert by_key(r)["a"].status == nz.STATUS_INSUFFICIENT and by_key(r)["a"].points == ()


def test_單點序列_必判不足():
    # 單點：起點＝該點回推 3 個月，最早有效＝該點 > 起點 → slice_period 判不足（一個點畫不成線）
    r = nz.normalize_pair({"a": [P("2026-04-10", 5.0)], "b": None}, "3M")
    assert r.status == nz.STATUS_INSUFFICIENT


def test_單序列視窗內只有一個有效點_too_few_points():
    # 起點 2026-01-10；01-01 在起點前（涵蓋），視窗內只有 04-10 一個有效點
    r = nz.normalize_pair({"a": [P("2026-01-01", 1.0), P("2026-02-02", None), P("2026-04-10", 2.0)], "b": []}, "3M")
    assert (r.status, r.mode, r.missing_keys) == (nz.STATUS_TOO_FEW_POINTS, nz.MODE_SINGLE, ("b",))
    assert by_key(r)["a"].status == nz.STATUS_TOO_FEW_POINTS and by_key(r)["a"].points == ()


@pytest.mark.parametrize("a, b", [(None, None), ([], []), ([P("2026-01-01", None)], None), ([], [P("2026-01-01", NAN)])])
def test_兩條都缺_both_missing(a, b):
    r = nz.normalize_pair({"a": a, "b": b}, "1Y")
    assert (r.status, r.mode, r.missing_keys, r.window_start, r.base_date) == (
        nz.STATUS_BOTH_MISSING, nz.MODE_NONE, ("a", "b"), None, None)
    assert all(s.status == nz.SERIES_MISSING and s.points == () for s in r.series)


def test_重複日期_大聲失敗_不去重():
    with pytest.raises(nz.NormalizationInputError, match="duplicate"):
        nz.normalize_pair({"a": [P("2026-01-12", 1.0), P("2026-01-12", 2.0)], "b": None}, "3M")
    # date 物件與字串指同一天也算重複
    with pytest.raises(nz.NormalizationInputError, match="duplicate"):
        nz.normalize_pair({"a": [P(date(2026, 1, 12), 1.0), P("2026-01-12", None)], "b": None}, "3M")


@pytest.mark.parametrize("bad", ["2026/01/12", "20260112", "2026-1-12", "", 20260112, None,
                                 datetime(2026, 1, 12, 0, 0), 1.5])
def test_obs_date不是日期_大聲失敗(bad):
    with pytest.raises(nz.NormalizationInputError):
        nz.normalize_pair({"a": [P(bad, 1.0)], "b": None}, "3M")


@pytest.mark.parametrize("bad_series", [
    {"a": "2026-01-12"}, {"a": [("2026-01-12", 1.0)]}, {"a": [{"value_num": 1.0}]}, {"a": {"x": 1}},
])
def test_序列或點格式錯誤_大聲失敗(bad_series):
    with pytest.raises(nz.NormalizationInputError):
        nz.normalize_pair({**bad_series, "b": None}, "3M")


@pytest.mark.parametrize("series", [{}, {"a": None}, {"a": None, "b": None, "c": None}, {"": None, "b": None},
                                    {1: None, "b": None}, [("a", None), ("b", None)]])
def test_series參數必須恰好兩個非空字串鍵(series):
    with pytest.raises(nz.NormalizationInputError):
        nz.normalize_pair(series, "3M")


def test_期間不合_ValueError_即使兩條都缺():
    with pytest.raises(ValueError):
        nz.normalize_pair({"a": None, "b": None}, "2Y")


def test_基準原值不為正_大聲失敗():
    with pytest.raises(nz.NormalizationInputError, match="base value"):
        nz.normalize_pair({"a": [P("2026-01-09", 1.0), P("2026-01-12", 0.0), P("2026-04-10", 3.0)],
                           "b": [P("2026-01-09", 1.0), P("2026-01-12", 2.0), P("2026-04-10", 3.0)]}, "3M")
    with pytest.raises(nz.NormalizationInputError, match="base value"):
        nz.normalize_pair({"a": [P("2026-01-01", 1.0), P("2026-01-12", -2.0), P("2026-04-10", 3.0)], "b": None}, "3M")


@pytest.mark.parametrize("junk", [NAN, INF, -INF, True, False, "12.5", None])
def test_非有限值與非數字_當缺口不當0(junk):
    a = [P("2026-01-09", 1.0), P("2026-01-12", 8.0), P("2026-02-02", junk), P("2026-04-10", 10.0)]
    b = [P("2026-01-09", 1.0), P("2026-01-12", 4.0), P("2026-02-02", 5.0), P("2026-04-10", 2.0)]
    r = nz.normalize_pair({"a": a, "b": b}, "3M")
    assert r.status == "ok"
    assert pts(by_key(r)["a"]) == [("2026-01-12", 100.0), ("2026-02-02", None), ("2026-04-10", 125.0)]


def test_未排序輸入_與排序後結果相同():
    rng = random.Random(7)
    shuffled_t, shuffled_s = TAIEX[:], SP500[:]
    rng.shuffle(shuffled_t)
    rng.shuffle(shuffled_s)
    assert nz.normalize_pair({"taiex": shuffled_t, "sp500": shuffled_s}, "3M") == \
        nz.normalize_pair({"taiex": TAIEX, "sp500": SP500}, "3M")


def test_date物件輸入_與字串輸入結果相同():
    as_dates = [P(date.fromisoformat(p["obs_date"]), p["value_num"]) for p in TAIEX]
    assert nz.normalize_pair({"taiex": as_dates, "sp500": SP500}, "3M") == \
        nz.normalize_pair({"taiex": TAIEX, "sp500": SP500}, "3M")


def test_不改呼叫端的輸入():
    t, s = [dict(p) for p in TAIEX], [dict(p) for p in SP500]
    nz.normalize_pair({"taiex": t, "sp500": s}, "3M")
    assert t == TAIEX and s == SP500


def test_回傳不可變():
    r = nz.normalize_pair({"taiex": TAIEX, "sp500": SP500}, "3M")
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.status = "x"
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.series[0].points[0].value = 1.0
    assert isinstance(r.series, tuple) and isinstance(r.series[0].points, tuple)


# ═══════════════════════ (b) property（固定種子） ═══════════════════════


def _random_series(rng, last_day):
    """以工作日為主的隨機序列：隨機起點、隨機缺口（None／NaN／inf／bool）、隨機休市（日期不出現）。"""
    span = rng.choice([30, 80, 200, 400, 800, 1200])
    day = last_day - timedelta(days=span)
    out = []
    while day <= last_day:
        if day.weekday() < 5 and rng.random() > 0.08:            # 休市＝日期不出現
            roll = rng.random()
            if roll < 0.06:
                value = rng.choice([None, NAN, INF, True])
            else:
                value = rng.uniform(1.0, 30000.0)
            out.append(P(day.isoformat(), value))
        day += timedelta(days=1)
    # 確保最後一天是有效值（讓「自身最後有效觀測日」可預期）
    if out:
        out[-1] = P(out[-1]["obs_date"], rng.uniform(1.0, 30000.0))
    return out


def _last_valid(points):
    valid = [p["obs_date"] for p in points if periods.is_number(p["value_num"])]
    return max(valid) if valid else None


def _cases(n=300, seed=20261103):
    rng = random.Random(seed)
    for _ in range(n):
        anchor = date(2026, 4, 10)
        lag_a, lag_b = rng.randint(0, 6), rng.randint(0, 6)
        if rng.random() < 0.15:     # H1b C2：讓其中一條停更（最後一天大幅提早）
            if rng.random() < 0.5:
                lag_a += rng.randint(20, 1500)
            else:
                lag_b += rng.randint(20, 1500)
        a = _random_series(rng, anchor - timedelta(days=lag_a))
        b = _random_series(rng, anchor - timedelta(days=lag_b))
        if rng.random() < 0.1:
            b = None
        yield {"taiex": a, "sp500": b}, rng.choice(periods.PERIODS)


def _first_valid(points):
    valid = [p["obs_date"] for p in points if periods.is_number(p["value_num"])]
    return min(valid) if valid else None


def _check_modes(series, r):
    """H1b：模式明示、永不出現兩個不同日期的 100、A2 涵蓋判定、B2／C2 退回單序列的結構。"""
    drawn = [s for s in r.series if s.status == nz.STATUS_OK]
    # 任何結果：所有被畫的序列基準點都在同一天（永不出現兩個不同日期的 100）
    assert len({s.points[0].obs_date for s in drawn}) <= 1
    assert all(s.points[0].value == 100.0 and s.points[0].obs_date == r.base_date for s in drawn)
    if r.mode == nz.MODE_PAIR:
        assert r.fallback_reason is None and r.missing_keys == ()
        assert len(drawn) in (0, 2) and (len(drawn) == 2) == (r.status == nz.STATUS_OK)
        w = max(s.own_window_start for s in r.series)
        assert r.window_start == w
        for s in r.series:   # A2：涵蓋 ⇔ 比較視窗起點當日或之前有有效觀測
            covered = _first_valid(series[s.key]) <= w
            assert covered == (s.status != nz.STATUS_INSUFFICIENT)
        if r.status == nz.STATUS_INSUFFICIENT:   # pair 模式的 insufficient 只在兩條都不足時發生（否則應退回單序列）
            assert all(s.status == nz.STATUS_INSUFFICIENT for s in r.series)
        if r.status in (nz.STATUS_NO_COMMON_BASE, nz.STATUS_TOO_FEW_COMMON_DAYS):
            in_window = [sum(1 for p in series[s.key] if p["obs_date"] >= w and periods.is_number(p["value_num"]))
                         for s in r.series]
            assert sum(c < nz.MIN_LINE_POINTS for c in in_window) != 1   # 恰一條停更 → 應退回單序列
            assert all(s.status == nz.SERIES_WITHHELD for s in r.series)
    elif r.mode == nz.MODE_FALLBACK:
        assert r.missing_keys == () and len(drawn) <= 1 and (len(drawn) == 1) == (r.status == nz.STATUS_OK)
        excluded = [s for s in r.series if s.status == r.fallback_reason]
        assert r.fallback_reason in (nz.STATUS_INSUFFICIENT, nz.STATUS_NO_COMMON_BASE, nz.STATUS_TOO_FEW_COMMON_DAYS)
        assert excluded and all(s.points == () for s in excluded)
        w = max(s.own_window_start for s in r.series)
        if r.fallback_reason == nz.STATUS_INSUFFICIENT:   # B2：被排除那條的歷史確實沒涵蓋到比較視窗起點
            assert any(_first_valid(series[s.key]) > w for s in excluded)
        else:                                             # C2：被排除那條在比較視窗內有效觀測不足 2 筆（停更）
            assert len(excluded) == 1   # 單序列狀態不會是 no_common_base／too_few_common_days → 被排除者唯一
            assert sum(1 for p in series[excluded[0].key]
                       if p["obs_date"] >= w and periods.is_number(p["value_num"])) < nz.MIN_LINE_POINTS
        # 被畫（或試畫）那條與「另一條傳 None」時逐欄相同（被排除那條的資料不影響它）
        def alone(key):
            return nz.normalize_pair({k: (v if k == key else None) for k, v in series.items()}, r.period)
        kept = [s for s in r.series
                if by_key(alone(s.key))[s.key] == s and (alone(s.key).status, alone(s.key).base_date) == (
                    r.status, r.base_date)]
        assert kept and all(d in kept for d in drawn)
    elif r.mode == nz.MODE_SINGLE:
        assert r.fallback_reason is None and len(r.missing_keys) == 1 and len(drawn) <= 1
    else:
        assert r.mode == nz.MODE_NONE and not drawn


def test_property_不變量():
    seen = {nz.STATUS_OK: 0, nz.STATUS_INSUFFICIENT: 0}
    modes = {}
    for series, period in _cases():
        r = nz.normalize_pair(series, period)
        seen[r.status] = seen.get(r.status, 0) + 1
        modes[(r.mode, r.fallback_reason)] = modes.get((r.mode, r.fallback_reason), 0) + 1
        _check_modes(series, r)
        if r.status != nz.STATUS_OK:
            # 不足／不可畫 → 永不出線
            assert r.base_date is None and r.base_value is None
            assert all(s.points == () and s.last_normalized is None and s.period_change is None for s in r.series)
            continue
        raw = {k: {p["obs_date"]: p["value_num"] for p in (v or [])} for k, v in series.items()}
        drawn = [s for s in r.series if s.status == nz.STATUS_OK]
        assert drawn and r.base_value == 100
        for s in drawn:
            # 基準點恰為 100（精確）
            assert s.points[0].obs_date == r.base_date and s.points[0].value == 100.0
            # 基準日前沒有點；日期嚴格遞增
            assert all(p.obs_date >= r.base_date for p in s.points)
            assert [p.obs_date for p in s.points] == sorted({p.obs_date for p in s.points})
            # 逆算回原值（相對誤差 1e-12）；缺口位置與原輸入的無效值一一對應
            for p in s.points:
                original = raw[s.key][p.obs_date]
                if p.value is None:
                    assert not periods.is_number(original)
                else:
                    assert math.isclose(p.value * s.base_raw / 100, original, rel_tol=1e-12)
            # 原序列在 [base_date, last] 的每一天都出現在輸出（不丟日、不補日）
            expected_days = sorted(d for d in raw[s.key] if r.base_date <= d <= s.last_obs_date)
            assert [p.obs_date for p in s.points] == expected_days
            # 最後一點＝該序列自己的最後有效觀測日
            assert s.points[-1].obs_date == s.last_obs_date == _last_valid(series[s.key])
            assert s.last_normalized == s.points[-1].value and s.period_change == s.last_normalized - 100
        if r.mode == nz.MODE_PAIR:
            # 基準日兩條都有效、且是比較視窗起點後第一個共同有效日
            a, b = (raw[k] for k in ("taiex", "sp500"))
            common = sorted(d for d in a if d >= r.window_start and periods.is_number(a[d])
                            and d in b and periods.is_number(b[d]) and d <= min(s.last_obs_date for s in drawn))
            assert common[0] == r.base_date
            assert r.window_start == max(s.own_window_start for s in r.series)
    # 種子有涵蓋到主要結果與 H1b 退回路徑（防止 property 空轉）
    assert seen[nz.STATUS_OK] > 50 and seen[nz.STATUS_INSUFFICIENT] > 10, seen
    assert modes.get((nz.MODE_PAIR, None), 0) > 30, modes
    assert modes.get((nz.MODE_FALLBACK, nz.STATUS_INSUFFICIENT), 0) > 10, modes
    assert modes.get((nz.MODE_FALLBACK, nz.STATUS_NO_COMMON_BASE), 0) > 5, modes


def test_property_尺度不變():
    rng = random.Random(99)
    checked = 0
    for series, period in _cases(150, seed=4242):
        k = rng.choice([0.001, 0.37, 3.0, 1234.5])
        scaled = {key: None if pts_ is None else
                  [P(p["obs_date"], p["value_num"] * k if periods.is_number(p["value_num"]) else p["value_num"])
                   for p in pts_] for key, pts_ in series.items()}
        r1, r2 = nz.normalize_pair(series, period), nz.normalize_pair(scaled, period)
        assert (r1.status, r1.mode, r1.base_date, r1.window_start) == (r2.status, r2.mode, r2.base_date, r2.window_start)
        for s1, s2 in zip(r1.series, r2.series):
            assert [p.obs_date for p in s1.points] == [p.obs_date for p in s2.points]
            for p1, p2 in zip(s1.points, s2.points):
                assert (p1.value is None) == (p2.value is None)
                if p1.value is not None:
                    assert math.isclose(p1.value, p2.value, rel_tol=1e-12)
                    checked += 1
    assert checked > 1000, checked


def test_property_只縮放其中一條_另一條結果不變():
    for series, period in _cases(80, seed=777):
        if series["sp500"] is None:
            continue
        scaled = {"taiex": series["taiex"],
                  "sp500": [P(p["obs_date"], p["value_num"] * 7.0 if periods.is_number(p["value_num"]) else p["value_num"])
                            for p in series["sp500"]]}
        assert by_key(nz.normalize_pair(series, period))["taiex"] == by_key(nz.normalize_pair(scaled, period))["taiex"]


# ═══════════════════════ (d) 分層 ═══════════════════════

_SRC = _ROOT / "services" / "v2_domain" / "normalization.py"
_ALLOWED = {"__future__", "dataclasses", "datetime"}


def _has_cjk(text: str) -> bool:
    return any("　" <= ch <= "鿿" or "＀" <= ch <= "￯" for ch in text)


def _violations(source: str) -> list:
    tree = ast.parse(source)
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = ["." * node.level + (node.module or "")]
        else:
            continue
        for m in mods:
            if m.startswith("services.v2_domain.") or m == "services.v2_domain":
                continue
            if m.split(".")[0] not in _ALLOWED or m.startswith("."):
                bad.append(f"import {m}")
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstrings.add(id(first.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings \
                and _has_cjk(node.value):
            bad.append(f"cjk literal {node.value!r}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {
                "open", "exec", "eval", "compile", "__import__", "input", "print"}:
            bad.append(f"call {node.func.id}()")
    return bad


def test_分層_只import標準庫與同套件_無中文字串常數():
    assert _violations(_SRC.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("code", [
    "import streamlit as st", "import pandas as pd", "import requests", "from ui_v3 import x", "import ui_v2",
    "from ui.tab2_single_fund import y", "from services.benchmark_compare import rebased_pair",
    "from services.v2_tables import market_view", "import os", "from shared import ui_semantics",
    "from . import periods", "X = '資料未備'", "def f():\n    import socket", "open('x')",
])
def test_分層守衛會咬_正控(code):
    assert _violations(code), code


@pytest.mark.parametrize("code", [
    "from __future__ import annotations\nfrom dataclasses import dataclass\nfrom datetime import date",
    "from services.v2_domain.periods import slice_period", "def f():\n    '''中文 docstring'''\n    return 'ok'",
])
def test_分層守衛不誤報_負控(code):
    assert _violations(code) == [], code
