# -*- coding: utf-8 -*-
"""A 鏈（`services.moneydj_fetcher.auto_fetch_moneydj` → L2 enriched → L1 `fetch_fund_from_moneydj_url`
→ `_fetch_fund_single` 多來源瀑布）的離線 stub 工具（測試共用；不是測試檔）。

用途：
- `tests/test_a_chain_failure_capture.py`：同一組 stub 輸入，改動前錄下的黃金檔 vs 現在的輸出，
  除了新增鍵其餘欄位逐一相同（總管 2026-10-13 技術裁定第 3 條）。
- `tests/test_v2_tables_nav_chain_handover.py`：B 線 `build_nav_table` 與 A 鏈對同一組 stub
  的來源呼叫順序逐一相同。

做法：把 `repositories.fund.fund_orchestration` 命名空間裡每一個會發請求的名字換成記錄呼叫的假函式
（`_src_*`、`fetch_url_with_retry`、`fetch_nav`、`fetch_risk_metrics`、`fetch_performance_wb01`、
`fetch_holdings`），對照表與選股池查詢也換成固定值；nav_history 讀取換成 `load_points` 的假資料。
**不打任何網路、不讀任何試算表。**
"""

from __future__ import annotations

import pandas as pd

NAV_SOURCES = (
    "_src_allianzgi_nav", "_src_fundclear_nav", "_src_cnyes_nav", "_src_tcb_nav",
    "_src_insurance_subdomain_nav", "_src_sitca_nav", "_src_nav_30day", "_src_bank_platform_nav",
    "_src_morningstar_nav", "_src_yahoo_finance_nav", "_src_alphavantage_nav", "_src_franklin_nav",
    "_src_jpmorgan_nav", "_src_taiwanlife_nav",
)
META_SOURCES = (
    "_src_tdcc_meta", "_src_allianzgi_meta", "_src_tcb_meta", "_src_fundclear_meta", "_src_sitca_meta",
    "_src_direct_moneydj_url",
)
DIV_SOURCES = ("_src_tcb_div", "_src_fundclear_div", "_src_cnyes_div")
DICT_FETCHERS = ("fetch_risk_metrics", "fetch_performance_wb01", "fetch_holdings")


def series(n: int, *, start: str = "2026-01-05", base: float = 10.0, step: float = 0.01,
           attrs: dict | None = None, freq: str = "B") -> pd.Series:
    """`n` 筆淨值（工作日）。`attrs` 原樣掛上。"""
    idx = pd.date_range(start, periods=n, freq=freq)
    s = pd.Series([round(base + i * step, 4) for i in range(n)], index=idx, dtype=float)
    s.attrs.update(attrs or {})
    return s


def _copy(value):
    if isinstance(value, pd.Series):
        out = value.copy()
        out.attrs = dict(value.attrs)
        return out
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        # 2026-10-13：配息解析器的回傳是 `list` 子類別（帶取數狀態屬性），淺拷貝要保留型別與屬性；
        # 一般 list 結果與 `list(value)` 相同。
        import copy as _copy_mod
        return _copy_mod.copy(value) if type(value) is not list else list(value)
    return value


def install(monkeypatch, scenario: dict, calls: list | None = None) -> list:
    """依 `scenario`（`{名字: 回傳值或 callable}`）裝上全部 stub；回傳記錄呼叫的串列。

    特殊鍵：
    - `"fetch_nav"`：legacy 最終備援的回傳（預設空 Series）。
    - `"nav_history_points"`：`services.nav_history_gs.load_points` 回的點（預設 `[]`）；
      值為例外實例 → 呼叫時拋出。
    - `"mapping"`：代碼對照表（預設 `{}`）。
    """
    import repositories.fund.fund_orchestration as fo
    import repositories.fund.sources as src
    import services.nav_history_gs as nh

    calls = [] if calls is None else calls

    def _make(name, default):
        def _stub(*args, **kwargs):
            calls.append((name, args[0] if args else kwargs.get("code")))
            value = scenario.get(name, default)
            if callable(value) and not isinstance(value, pd.Series):
                value = value(*args, **kwargs)
            return _copy(value)
        return _stub

    for name in NAV_SOURCES:
        monkeypatch.setattr(fo, name, _make(name, pd.Series(dtype=float)))
    for name in META_SOURCES:
        monkeypatch.setattr(fo, name, _make(name, {}))
    for name in DIV_SOURCES:
        monkeypatch.setattr(fo, name, _make(name, []))
    for name in DICT_FETCHERS:
        monkeypatch.setattr(fo, name, _make(name, {}))
    monkeypatch.setattr(fo, "fetch_nav", _make("fetch_nav", pd.Series(dtype=float)))

    def _no_http(url, *args, **kwargs):
        calls.append(("fetch_url_with_retry", url.split("?")[0]))
        return None

    monkeypatch.setattr(fo, "fetch_url_with_retry", _no_http)
    monkeypatch.setattr(fo, "_pool_secid_or_isin", lambda code: False)
    mapping = scenario.get("mapping", {})
    monkeypatch.setattr(fo, "load_fund_code_mapping", lambda *a, **k: dict(mapping))
    monkeypatch.setattr(src, "load_fund_code_mapping", lambda *a, **k: dict(mapping))
    fo._holdings_ttl.cache_clear()
    # 2026-10-13：`getattr` 相容 —— 改動前（base）的 L1 沒有快取、沒有 `cache_clear`，錄黃金檔時要能在 base 上跑。
    _clear = getattr(fo.fetch_fund_from_moneydj_url, "cache_clear", None)
    if _clear is not None:
        _clear()
    fo._FUND_SNAPSHOT.clear()

    def _points(code=None, **kwargs):
        calls.append(("nav_history.load_points", code))
        value = scenario.get("nav_history_points", [])
        if isinstance(value, BaseException):
            raise value
        return [dict(p) for p in value if code is None or p["code"] == str(code).strip().upper()]

    monkeypatch.setattr(nh, "load_points", _points)
    return calls


# ───────────────────────── 黃金檔用的正規化 ─────────────────────────

# 每次跑都會變的欄位（呼叫當下的時間）：不比。
VOLATILE_TOP_KEYS = frozenset({"_moneydj_fetched_at", "fetched_at"})


def normalize(value, *, drop: frozenset = frozenset()):
    """把 A 鏈回傳值轉成可存 JSON、可逐欄比對的形狀（浮點取 6 位小數）。"""
    if isinstance(value, pd.Series):
        return {"__series__": [[str(k)[:10], normalize(v)] for k, v in value.items()],
                "attrs": {k: normalize(v) for k, v in sorted(value.attrs.items()) if k not in drop}}
    if isinstance(value, pd.DataFrame):
        return {"__frame__": normalize(value.to_dict(orient="list"))}
    if isinstance(value, dict):
        return {str(k): normalize(v, drop=drop) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))
                if k not in drop}
    if isinstance(value, (list, tuple)):
        return [normalize(v, drop=drop) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int,)) and not isinstance(value, bool):
        return value
    try:
        f = float(value)
    except (TypeError, ValueError):
        return repr(value)
    if f != f:
        return "nan"
    if f in (float("inf"), float("-inf")):
        return repr(f)
    return round(f, 6)


# ───────────────────────── 共用情境 ─────────────────────────

_T0 = "2026-02-01T00:00:00+00:00"


def _hist_points(code: str, dates, *, base: float = 9.0, recorded_at: str = "2026-01-02T03:04:05+00:00"):
    return [{"code": code, "date": d, "nav": round(base + i * 0.01, 4), "fund_name": "", "source": "app",
             "recorded_at": recorded_at if not callable(recorded_at) else recorded_at(i),
             "currency": ""} for i, d in enumerate(dates)]


def scenarios() -> dict:
    """`{情境名: (代碼, scenario)}`。每次呼叫都重建（序列不共用）。"""
    from services.nav_history_gs import NavHistoryError

    fc_attrs = {"source": "FundClear:SmartFundAPI:nav", "fetched_at": _T0, "currency": "USD"}
    old_dates = ["2025-11-03", "2025-11-04", "2025-11-05", "2026-01-05"]   # 最後一天與 live 重疊
    return {
        "S1_complete_fundclear": ("ZZF001", {
            "_src_fundclear_nav": series(25, attrs=fc_attrs),
            "_src_tcb_meta": {"fund_name": "測試基金一", "currency": "USD", "nav_latest": 10.24},
            "nav_history_points": _hist_points(
                "ZZF001", old_dates,
                recorded_at=lambda i: "" if i == 1 else f"2025-11-0{3 + i}T09:00:00+00:00"),
        }),
        "S2_shortwindow_rescue": ("ZZF002", {
            "_src_fundclear_nav": series(8, attrs=fc_attrs),
            "_src_tcb_nav": series(30, attrs={"source": "MoneyDJ:tcb:nav30", "fetched_at": _T0}),
            "_src_tcb_meta": {"fund_name": "測試基金二"},
        }),
        "S3_all_fail": ("ZZF003", {
            "fetch_nav": series(0, attrs={"fetch_error": "fetch_nav('ZZF003') 即時網址與預存檔皆失敗:\n"
                                                         "https://x/wb02 → 取數失敗(kind=blocked)"}),
        }),
        "S4_cache_fallback": ("ZZF004", {
            "fetch_nav": series(40, attrs={
                "source": "GitHubActions:cache/nav/ZZF004.json", "fetched_at": "2026-03-05T00:00:00+00:00",
                "cache_updated_at": "2026-03-01T00:00:00+00:00", "nav_quality": {"stale": True},
                "live_fetch_error": "https://x/wb02 → 取數失敗(kind=blocked)"}),
        }),
        "S5_hist_read_fail": ("ZZF005", {
            "_src_fundclear_nav": series(25, attrs=fc_attrs),
            "_src_tcb_meta": {"fund_name": "測試基金五"},
            "nav_history_points": NavHistoryError("nav_history load 失敗:APIError 429 quota"),
        }),
        "S6_insurance_morningstar": ("TLZZ9", {
            "_src_tdcc_meta": {"fund_name": "保單基金六", "nav_latest": 12.0},
            "_src_morningstar_nav": series(15, attrs={"source": "Morningstar:0P000TEST", "fetched_at": _T0,
                                                      "currency": "USD"}),
        }),
        "S7_hist_rescue": ("ZZF007", {
            "_src_tcb_meta": {"fund_name": "測試基金七"},
            "nav_history_points": _hist_points("ZZF007", [d.date().isoformat() for d in
                                                          pd.date_range("2025-10-01", periods=30, freq="B")]),
        }),
    }


def full_success_scenario(code: str = "ZZF100", *, currency: str = "USD") -> tuple:
    """每個組成部分都成功的情境（名稱、序列、wb07、wb01、持股、配息）—— 只有這種結果會進 L1 十五分鐘快取。
    不放進 `scenarios()`（那七組是黃金檔的母體，不能動）。"""
    attrs = {"source": "FundClear:GetFundNAV", "fetched_at": _T0}
    if currency:
        attrs["currency"] = currency
    return code, {
        # 300 個工作日（跨度遠超過近30日短窗門檻）：短窗序列依 2026-10-13 稽核 6 不入快取
        "_src_fundclear_nav": series(300, start="2025-01-06", attrs=attrs),
        "_src_tcb_meta": {"fund_name": "全成功基金", "nav_latest": 10.24},
        "_src_tcb_div": [{"date": "2026-01-15", "amount": 0.05, "yield_pct": 6.0}],
        "fetch_risk_metrics": {"risk_table": {"1Y": {"std": 10.0}}, "source": "MoneyDJ:x:wb07"},
        "fetch_performance_wb01": {"1Y": 5.0, "source": "MoneyDJ:x:wb01"},
        "fetch_holdings": {"top_holdings": [{"name": "A", "pct": 5.0}], "source": "MoneyDJ:yp:x"},
    }
