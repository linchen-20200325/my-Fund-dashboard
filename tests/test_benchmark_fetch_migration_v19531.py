"""P-UIHTTP-1 取數下沉守衛（v19.531 Phase 1.2）。

守三件事，每一條都對應報告裡的一句「絕不」：

A. **UI 層不得再自己抓 / 自己存**（憲法 §-1.5.1c v3 §01 三層圖 UI 框：
   「嚴禁在 UI 層私自存放或抓取原始資料」）——
   `ui/components/mk_dashboard.py` 不得 import yfinance、不得再持有
   `st.session_state["mk_bench_cache"]`。

B. **L1 `fetch_benchmark_close` 的 §1 Fail Loud 契約** ——
   取不到回 None（不回空序列、不回假序列、不 ffill、不 fillna），
   後處理破壞索引不變量時當場 raise。

C. **零行為變更** —— 同一份來源資料，搬遷後產出的序列與搬遷前
   （yfinance `period="9mo"` + `tz_localize(None)`）在 index、values、
   下游 `tag_benchmark_lag` 判定、對比圖歸一化基準上完全一致。

⚠️ 沙箱無外網（CONNECT 403），本檔一律以 patch 掉 `fetch_yf_close` 的方式
驗**契約**，不驗真實 Yahoo 回應。
"""
from __future__ import annotations

import ast
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import pytest

from dateutil.relativedelta import relativedelta

import repositories.macro.yf as yfmod
from repositories.macro.yf import fetch_benchmark_close

ROOT = Path(__file__).parents[1]
MK = ROOT / "ui" / "components" / "mk_dashboard.py"


# ════════════════════════════════════════════════════════════
# 共用 fixture：模擬「同一天的 Yahoo 原始資料」的兩種表示法
# ════════════════════════════════════════════════════════════
_N_DAYS = 320


def _prices(n: int = _N_DAYS) -> np.ndarray:
    """決定性的合成收盤價（>0、無 NaN，符合 YahooCloseSchema）。"""
    rng = np.random.default_rng(20260828)
    return 100.0 * np.cumprod(1.0 + rng.normal(0.0004, 0.01, n))


def _dates(n: int = _N_DAYS) -> pd.DatetimeIndex:
    end = pd.Timestamp.now("UTC").tz_localize(None).normalize()
    return pd.bdate_range(end=end, periods=n)


def _chart_api_series(vals=None, days=None) -> pd.Series:
    """搬遷後的上游長相：Chart API epoch → naive UTC，帶開盤時刻 13:30。"""
    days = _dates() if days is None else days
    vals = _prices(len(days)) if vals is None else vals
    s = pd.Series(vals, index=days + pd.Timedelta(hours=13, minutes=30),
                  dtype=float, name="SPY")
    s.attrs["source"] = "Yahoo:SPY"
    s.attrs["fetched_at"] = "2026-08-28T00:00:00+00:00"
    return s


def _legacy_yfinance_series(vals=None, days=None) -> pd.Series:
    """搬遷**前**的長相：yfinance `.history(period="9mo")` + tz_localize(None)。

    yfinance 的 period="9mo" 是 `now - relativedelta(months=9)`，日線 index
    為交易所當地午夜、去 tz 後即純日期。這裡照那個語意重建，**不引用被測程式碼
    的任何常數或表達式**（否則等於拿實作驗實作）。
    """
    days = _dates() if days is None else days
    vals = _prices(len(days)) if vals is None else vals
    s = pd.Series(vals, index=days, dtype=float, name="SPY")
    start = pd.Timestamp.now("UTC").tz_localize(None).normalize() - relativedelta(months=9)
    return s[s.index >= start].dropna()


# ════════════════════════════════════════════════════════════
# A. UI 層不得再自己抓 / 自己存
# ════════════════════════════════════════════════════════════
def _mk_tree() -> ast.Module:
    return ast.parse(MK.read_text(encoding="utf-8"), filename=str(MK))


def test_ui_does_not_import_yfinance() -> None:
    """mk_dashboard 不得 import yfinance（含函式內 late import）。

    以 AST 判定，不用字串比對 —— 檔內 docstring 為了說明搬遷歷史會提到
    「import yfinance」這幾個字，字串比對會被那段文件誤判成命中。

    ⚠️ **已知繞道（本條**不是** fail-closed，別把它當保證）**：本條只認
    `ast.Import` / `ast.ImportFrom` 這種**靜態 import 形態**。用
    `importlib.import_module("yfinance")` 取得同一個模組，本條**照樣綠燈** ——
    2026-08-28 稽核實測復辟違憲後本條仍 pass。
    真正擋下該繞道的是 `test_ui_benchmark_path_delegates_to_l1`（sentinel 往返）。
    本條的定位是**形態偵測**：擋「不小心寫回去」，擋不住「刻意繞過」。
    """
    hits = []
    for node in ast.walk(_mk_tree()):
        if isinstance(node, ast.Import):
            hits += [a.name for a in node.names if a.name.split(".")[0] == "yfinance"]
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] == "yfinance":
                hits.append(node.module)
    assert hits == [], f"UI 層又自己抓資料了（v3 §01「嚴禁在 UI 層私自抓取」）：{hits}"


def test_ui_holds_no_benchmark_session_cache() -> None:
    """mk_dashboard 不得再持有 `mk_bench_cache` 這個 UI 層自建快取。

    同上以 AST 的**字串常值**判定（docstring 是一整段長字串，值不會恰好等於
    "mk_bench_cache"，故不會誤判）；快取已下沉 L1 `@_ttl_cache`（TTL 走
    `shared/ttls.py` SSOT），UI 層再存一份即 v3 §01「私自存放」。

    ⚠️ **已知繞道（本條**不是** fail-closed）**：它只認 `"mk_bench_cache"` 這一個字面值。
    快取 key 改名成 `"mk_bench_cache_v2"` 即可完全繞過，本條照樣綠燈
    （2026-08-28 稽核實測）。同上，兜底的是 sentinel 那條。
    """
    hits = [n.value for n in ast.walk(_mk_tree())
            if isinstance(n, ast.Constant) and n.value == "mk_bench_cache"]
    assert hits == [], "UI 層又自建基準快取了（v3 §01「嚴禁在 UI 層私自存放」）"


def test_ui_benchmark_path_delegates_to_l1() -> None:
    """UI 的 `_get_benchmark_series` 必須真的走 L1，而不是自己又長一套。"""
    from ui.components import mk_dashboard as mk

    sentinel = object()
    with mock.patch("repositories.macro.yf.fetch_benchmark_close",
                    return_value=sentinel) as m:
        assert mk._get_benchmark_series("QQQ") is sentinel
    m.assert_called_once_with("QQQ")


def test_l1_benchmark_reuses_single_yahoo_fetcher() -> None:
    """L1 基準抓取必須走既有共用入口 `fetch_yf_close`，不得自己再開一套。

    ⚠️ **本測試的斷言沒變；改掉的是它原本宣稱的理由。** 原 docstring 寫
    「本 repo **唯一**的 Yahoo 取數實作」—— 那是**假的**，2026-08-28 稽核實測本 repo
    至少另有 `repositories/fund/sources.py::_src_yahoo_finance_nav`（urlopen 直打 query2，
    不走 infra.proxy）與 `scripts/fetch_nav_cache.py::fetch_yahoo_finance_history` 兩套獨立
    實作（repo 自己也記在 `shared/api_endpoints.py` 檔頭：「YF query2 Morningstar URL 真 dupe」）。

    本測試真正守的是：**基準序列不得再新增第四套取數實作** ——
    若 `fetch_benchmark_close` 自己開 HTTP / 自己 import yfinance，這個 patch 就不會被呼叫。
    """
    with mock.patch.object(yfmod, "fetch_yf_close",
                           return_value=_chart_api_series()) as m:
        assert fetch_benchmark_close("SPY") is not None
    m.assert_called_once()
    assert m.call_args.args[0] == "SPY"


# ════════════════════════════════════════════════════════════
# B. §1 Fail Loud 契約
# ════════════════════════════════════════════════════════════
@pytest.mark.parametrize("upstream", [
    pd.Series(dtype=float),                      # 上游抓失敗 → 空序列
    None,                                        # 上游回 None
])
def test_returns_none_not_fake_series_when_unavailable(upstream) -> None:
    """取不到時回 None —— 不回空序列冒充「有資料只是空的」，更不回假序列。

    這條擋的是「畫一張空圖假裝正常」：呼叫端只認 None 才會顯示
    「📡 基準指數目前無法取得」。
    """
    with mock.patch.object(yfmod, "fetch_yf_close", return_value=upstream):
        assert fetch_benchmark_close("SPY") is None


def test_returns_none_when_window_has_no_data() -> None:
    """上游只有 9 個月以前的舊資料 → 窗口內空 → None，不得回傳過期序列充數（§2.4）。"""
    old_days = pd.bdate_range(end=pd.Timestamp.now("UTC").tz_localize(None).normalize()
                              - relativedelta(months=14), periods=40)
    with mock.patch.object(yfmod, "fetch_yf_close",
                           return_value=_chart_api_series(days=old_days)):
        assert fetch_benchmark_close("SPY") is None


def test_no_imputation_no_reindex() -> None:
    """輸出必須是輸入的**子集**：不補洞、不 ffill、不 fillna、不 asfreq（§1）。"""
    days = _dates()
    vals = _prices(len(days))
    up = _chart_api_series(vals=vals, days=days)
    with mock.patch.object(yfmod, "fetch_yf_close", return_value=up):
        out = fetch_benchmark_close("SPY")
    assert out is not None
    # 每個輸出日期都必須在輸入裡找得到（沒有被補出來的日子）
    src_days = set(days)
    assert set(out.index) <= src_days, "輸出出現了來源沒有的日期 → 被補值了"
    # 值必須逐點等於來源，沒有被平滑 / 前填
    lookup = pd.Series(vals, index=days)
    assert np.allclose(out.values, lookup.reindex(out.index).values)
    # 沒有週末（來源是 bdate_range）→ 若被 asfreq('D').ffill() 會冒出週末
    assert not any(d.weekday() >= 5 for d in out.index)


def test_duplicate_dates_after_normalize_raise() -> None:
    """normalize 後若日期重複 → 當場 AssertionError，不靜默去重（§4.2 不變量）。

    重複日會讓「連續兩季」的 65/130 交易日視窗比錯期別 ——
    §1「錯誤的數字比沒有數字更危險」。
    """
    days = _dates(200)
    idx = (days + pd.Timedelta(hours=13, minutes=30)).append(
        pd.DatetimeIndex([days[-1] + pd.Timedelta(hours=20)]))
    s = pd.Series(np.linspace(100, 120, len(idx)), index=idx, dtype=float, name="SPY")
    s.attrs["source"] = "Yahoo:SPY"
    with mock.patch.object(yfmod, "fetch_yf_close", return_value=s):
        with pytest.raises(AssertionError, match="日期重複"):
            fetch_benchmark_close("SPY")


def test_provenance_preserved() -> None:
    """§2.2：上游血緣必須帶下來，不得在轉接層弄丟。"""
    with mock.patch.object(yfmod, "fetch_yf_close",
                           return_value=_chart_api_series()):
        out = fetch_benchmark_close("SPY")
    assert out.attrs.get("source") == "Yahoo:SPY"
    assert out.attrs.get("fetched_at")


def test_l1_has_no_second_cache_layer() -> None:
    """`fetch_benchmark_close` 本身不得再掛 TTL 快取。

    上游 `fetch_yf_close` 已帶 `@_ttl_cache(TTL_10MIN)`；同一份資料疊兩層 TTL
    ＝失效語意不可推理（憲法 EX-UICACHE-1 升級觸發條件 (3) 點名的形態）。
    以「連呼兩次、上游要被呼叫兩次」證明本層沒有記憶。
    """
    with mock.patch.object(yfmod, "fetch_yf_close",
                           return_value=_chart_api_series()) as m:
        fetch_benchmark_close("SPY")
        fetch_benchmark_close("SPY")
    assert m.call_count == 2, "本層自建了快取（上游只被呼叫一次）"


# ════════════════════════════════════════════════════════════
# C. 與「搬遷前行為模型」一致（⚠️ 不是等價證明，看清楚差別）
# ════════════════════════════════════════════════════════════
# ⛔ **本組證明的是「實作符合我們對舊行為的模型」，不是「與舊行為等價」。**
# 原標題寫「零行為變更」是高估，2026-08-28 稽核擋下。差在哪：
#   本組餵給「搬遷前那條路」的，是我們**自己建的** yfinance 輸出模型
#   （`_legacy_yfinance_series`），而那個模型假設 yfinance 會把價格序列裁成 9 個月。
#   實測 yfinance 1.6.0 原始碼：`params = {"range": period}`（"9mo" 原封送出），
#   且 L408-416 算出來的 `start` **只裁 dividends / capital_gains / splits，不裁 quotes**。
#   ⇒ 搬遷前的實際窗口 = 「Yahoo 對 range=9mo 回什麼」，**沙箱無外網，測不到**。
#   用 `relativedelta` 而非被測程式碼的 `DateOffset` 只避開了常數引用，
#   **繞不開「模型本身可能是錯的」**。
# 兩種情境，哪一種為真未知 → 部署後必須實地確認：
#   A) Yahoo 接受 9mo → 本組的一致性即等價；
#   B) Yahoo 拒絕 9mo → 搬遷前拿到空表、`series=None`，
#      **Benchmark_Lag 從沒亮過、對比圖從沒畫過**；搬遷後兩者會從死的變成活的。
# 本組仍有價值：它釘死「窗口裁切與 index normalize 這兩段後處理不准被偷改」
#   （M6/M7 突變即由本組擋下），只是不能拿它當「使用者看到的東西沒變」的證明。
def test_series_identical_to_legacy_yfinance_shape() -> None:
    """同一份 Yahoo 收盤資料，搬遷後與搬遷前的序列 index / values 完全一致。"""
    days, vals = _dates(), _prices()
    legacy = _legacy_yfinance_series(vals=vals, days=days)
    with mock.patch.object(yfmod, "fetch_yf_close",
                           return_value=_chart_api_series(vals=vals, days=days)):
        new = fetch_benchmark_close("SPY")
    assert new is not None
    assert new.index.equals(legacy.index), "日期軸與搬遷前不一致"
    assert np.allclose(new.values, legacy.values), "收盤值與搬遷前不一致"


@pytest.mark.parametrize("drift", [-0.02, -0.001, 0.0, 0.001, 0.02])
def test_benchmark_lag_verdict_identical_to_legacy(drift: float) -> None:
    """下游 `tag_benchmark_lag` 的判定（Lag / OK / N/A）與搬遷前逐案一致。"""
    from ui.components.mk_dashboard import tag_benchmark_lag

    days, vals = _dates(), _prices()
    legacy = _legacy_yfinance_series(vals=vals, days=days)
    with mock.patch.object(yfmod, "fetch_yf_close",
                           return_value=_chart_api_series(vals=vals, days=days)):
        new = fetch_benchmark_close("SPY")

    fund_idx = pd.bdate_range(end=days[-1], periods=200)
    fund = {"series": pd.Series(
        _prices(200) * np.cumprod(np.full(200, 1.0 + drift / 100.0)),
        index=fund_idx, dtype=float)}
    assert tag_benchmark_lag(fund, new) == tag_benchmark_lag(fund, legacy)


def test_chart_normalization_baseline_identical_to_legacy() -> None:
    """對比圖的歸一化基準（起點＝100）與搬遷前一致 —— 窗口沒有被偷偷放大。

    這條特別重要：Yahoo Chart API 沒有 "9mo" 這個 range，若圖省事改抓 "1y"
    不裁切，圖的起點會整個往前挪，線形跟著變。
    """
    days, vals = _dates(), _prices()
    legacy = _legacy_yfinance_series(vals=vals, days=days)
    with mock.patch.object(yfmod, "fetch_yf_close",
                           return_value=_chart_api_series(vals=vals, days=days)):
        new = fetch_benchmark_close("SPY")

    legacy_norm = (legacy.dropna() / float(legacy.dropna().iloc[0])) * 100.0
    new_norm = (new.dropna() / float(new.dropna().iloc[0])) * 100.0
    assert new_norm.index.equals(legacy_norm.index)
    assert np.allclose(new_norm.values, legacy_norm.values)
    assert len(new_norm) == len(legacy_norm)
