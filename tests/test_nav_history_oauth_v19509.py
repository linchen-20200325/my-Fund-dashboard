"""v19.509:nav_history SA→OAuth 回退 + 讀寫核心 OAuth 穿透(手機免設 Service Account)。

user 2026-08-22「都用手機 沒有電腦」+「健診資料還是不完整」:SA 缺時,由健診 UI 於**主
執行緒**捕獲登入者 OAuth gspread client,顯式傳入抓取核心,讓補回的雲端歷史在健診看得到
(worker 執行緒內取不到 session_state,故 client 必須主執行緒傳)。

守住的不變量(mirror 選股池 pool_repository v19.508):
  - SA 優先;429/配額不降級(§1 往上拋);SA 未分享(403)且有 OAuth → 降級;兩者皆無 → raise。
  - headless/cron 不傳 oauth_client → 純 SA/空,零 regression。
讀寫鏈逐段透傳 oauth_client:
  process_one_fund → auto_fetch_moneydj → *_enriched → finalize_fund_metrics
  → _merge_nav_history_series → load_series;寫:backfill_to_gs → append_points。
"""
import pandas as pd
import pytest

import services.nav_history_gs as NG


class _FakeClient:
    def __init__(self, name, exc=None):
        self.name = name
        self.exc = exc
        self.opened = []

    def open_by_key(self, sid):
        self.opened.append(sid)
        if self.exc:
            raise self.exc
        return f"SHEET::{self.name}::{sid}"


def _sheet(monkeypatch):
    monkeypatch.setattr(NG, "_nav_sheet_id", lambda: "NAVBOOK")


def _wire_sa(monkeypatch, client, present=True):
    _sa = {"client_email": "sa@x.iam"} if present else {}
    monkeypatch.setattr("infra.config.get_secret",
                        lambda k, default=None: (_sa if k == "google_service_account" else default))
    if present:
        monkeypatch.setattr("repositories.policy_repository.get_gspread_client",
                            lambda creds: client)


# ── _get_sheet:SA-first / OAuth 回退 / 429 不降級 / 皆無 raise ──────────
def test_sa_present_uses_sa_ignores_oauth(monkeypatch):
    _sheet(monkeypatch)
    sa, oauth = _FakeClient("SA"), _FakeClient("OAUTH")
    _wire_sa(monkeypatch, sa, present=True)
    assert NG._get_sheet(oauth_client=oauth) == "SHEET::SA::NAVBOOK"
    assert oauth.opened == []


def test_sa_absent_uses_oauth(monkeypatch):
    _sheet(monkeypatch)
    _wire_sa(monkeypatch, None, present=False)
    oauth = _FakeClient("OAUTH")
    assert NG._get_sheet(oauth_client=oauth) == "SHEET::OAUTH::NAVBOOK"


def test_sa_quota_error_no_fallback(monkeypatch):
    _sheet(monkeypatch)
    sa, oauth = _FakeClient("SA", exc=RuntimeError("429")), _FakeClient("OAUTH")
    _wire_sa(monkeypatch, sa, present=True)
    monkeypatch.setattr("infra.gspread_retry.is_quota_error", lambda e: True)
    with pytest.raises(NG.NavHistoryError):
        NG._get_sheet(oauth_client=oauth)
    assert oauth.opened == []                       # 配額錯不可降級


def test_sa_403_falls_back_to_oauth(monkeypatch):
    _sheet(monkeypatch)
    sa, oauth = _FakeClient("SA", exc=PermissionError("403")), _FakeClient("OAUTH")
    _wire_sa(monkeypatch, sa, present=True)
    monkeypatch.setattr("infra.gspread_retry.is_quota_error", lambda e: False)
    assert NG._get_sheet(oauth_client=oauth) == "SHEET::OAUTH::NAVBOOK"


def test_sa_403_no_oauth_raises(monkeypatch):
    _sheet(monkeypatch)
    sa = _FakeClient("SA", exc=PermissionError("403"))
    _wire_sa(monkeypatch, sa, present=True)
    monkeypatch.setattr("infra.gspread_retry.is_quota_error", lambda e: False)
    with pytest.raises(NG.NavHistoryError):
        NG._get_sheet(oauth_client=None)


def test_no_creds_raises(monkeypatch):
    _sheet(monkeypatch)
    _wire_sa(monkeypatch, None, present=False)
    with pytest.raises(NG.NavHistoryError):
        NG._get_sheet(oauth_client=None)


# ── backend_status:誠實三態 ─────────────────────────────────────────
def test_backend_status(monkeypatch):
    monkeypatch.setattr(NG, "is_enabled", lambda: True)
    assert NG.backend_status(None) == "service_account"
    assert NG.backend_status(object()) == "service_account"     # SA 優先
    monkeypatch.setattr(NG, "is_enabled", lambda: False)
    assert NG.backend_status(object()) == "oauth"
    assert NG.backend_status(None) == "local"


# ── append_points gate + OAuth 透傳 ─────────────────────────────────
class _FakeWS:
    def __init__(self):
        self.appended = []

    def get_all_values(self):
        return [NG._NAV_HEADERS]

    def append_rows(self, rows, value_input_option=None):
        self.appended.extend(rows)


class _FakeSheet:
    def __init__(self):
        self.ws = _FakeWS()

    def worksheet(self, name):
        return self.ws


def test_append_points_noop_no_sa_no_oauth(monkeypatch):
    monkeypatch.setattr(NG, "is_enabled", lambda: False)
    r = NG.append_points([{"code": "X", "nav": 1.0, "nav_date": "2020-01-01"}])
    assert r["written"] == 0                        # 缺 SA 缺 OAuth → 安靜 no-op


def test_append_points_writes_via_oauth(monkeypatch):
    monkeypatch.setattr(NG, "is_enabled", lambda: False)
    captured = {}

    def _spy(oauth_client=None):
        captured["oauth"] = oauth_client
        return _FakeSheet()

    monkeypatch.setattr(NG, "_get_sheet", _spy)
    sentinel = object()
    r = NG.append_points([{"code": "X", "nav": 1.0, "nav_date": "2020-01-01"}],
                         oauth_client=sentinel)
    assert captured["oauth"] is sentinel and r["written"] == 1


# ── 讀取鏈逐段透傳 oauth_client ──────────────────────────────────────
def test_merge_threads_oauth_to_load_series(monkeypatch):
    import services.fund_service as FS
    captured = {}

    def _fake_load_series(code, oauth_client=None):
        captured["oauth"] = oauth_client
        return pd.Series(dtype=float)

    monkeypatch.setattr("services.nav_history_gs.load_series", _fake_load_series)
    sentinel = object()
    FS._merge_nav_history_series(pd.Series([1.0], index=pd.to_datetime(["2020-01-01"])),
                                 "X", oauth_client=sentinel)
    assert captured["oauth"] is sentinel


def test_finalize_threads_oauth_to_merge(monkeypatch):
    import services.fund_service as FS
    captured = {}

    def _fake_merge(s, code, oauth_client=None):
        captured["oauth"] = oauth_client
        return s, None

    monkeypatch.setattr(FS, "_merge_nav_history_series", _fake_merge)
    ser = pd.Series([10.0, 10.1, 10.2],
                    index=pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"]))
    sentinel = object()
    FS.finalize_fund_metrics({"series": ser, "fund_code": "X", "dividends": []},
                             oauth_client=sentinel)
    assert captured["oauth"] is sentinel


def test_enriched_wrapper_threads_oauth_to_finalize(monkeypatch):
    import services.fund_service as FS
    captured = {}
    monkeypatch.setattr("repositories.fund.fetch_fund_from_moneydj_url",
                        lambda url: {"series": None, "fund_code": "X"})

    def _fake_finalize(result, oauth_client=None):
        captured["oauth"] = oauth_client
        return result

    monkeypatch.setattr(FS, "finalize_fund_metrics", _fake_finalize)
    sentinel = object()
    FS.fetch_fund_from_moneydj_url_enriched("http://x/yp010000/y", oauth_client=sentinel)
    assert captured["oauth"] is sentinel


def test_auto_fetch_threads_oauth_to_enriched(monkeypatch):
    import services.moneydj_fetcher as MF
    captured = {}

    def _fake_enriched(url, oauth_client=None):
        captured["oauth"] = oauth_client
        return {"status": "complete", "series": None}

    monkeypatch.setattr("services.fund_service.fetch_fund_from_moneydj_url_enriched",
                        _fake_enriched)
    sentinel = object()
    MF.auto_fetch_moneydj("http://x/yp010000/y", oauth_client=sentinel)
    assert captured["oauth"] is sentinel


def test_process_one_fund_threads_oauth_to_auto_fetch(monkeypatch):
    import services.fund_row as FR
    captured = {}

    def _fake_auto(code, oauth_client=None, **kw):
        captured["oauth"] = oauth_client
        return {"error": "stop"}     # 無 series → process_one_fund 於捕獲後即回錯誤列

    monkeypatch.setattr("services.moneydj_fetcher.auto_fetch_moneydj", _fake_auto)
    sentinel = object()
    FR.process_one_fund("X", 1_000_000.0, oauth_client=sentinel)
    assert captured["oauth"] is sentinel


# ── 寫入鏈:backfill_to_gs OAuth 啟用 + 透傳 append_points ────────────
def test_backfill_gs_on_with_oauth_even_if_sa_absent(monkeypatch):
    import services.nav_history_store as NS
    monkeypatch.setattr(NG, "is_enabled", lambda: False)
    monkeypatch.setattr("services.moneydj_fetcher.auto_fetch_moneydj",
                        lambda code, **kw: {"error": "x"})
    out = NS.backfill_to_gs(["A"], oauth_client=object())
    assert out["gs_enabled"] is True             # OAuth 讓雲端後端啟用(SA 缺也可寫)


def test_backfill_threads_oauth_to_append(monkeypatch):
    import services.nav_history_store as NS
    monkeypatch.setattr(NG, "is_enabled", lambda: False)
    monkeypatch.setattr(NS, "_load_cache_series", lambda code: pd.Series(dtype=float))
    monkeypatch.setattr(NS, "_save_cache_series", lambda code, s: None)
    # 跨度 > 5 年(_SPAN_TARGET_DAYS=1825)→ 跳過 backfill 內層 _rescue_by_isin(nested,無法 patch)。
    _ser = pd.Series([10.0, 11.0], index=pd.to_datetime(["2017-01-01", "2024-01-01"]))
    monkeypatch.setattr("services.moneydj_fetcher.auto_fetch_moneydj",
                        lambda code, **kw: {"series": _ser, "fund_name": "F"})
    captured = {}

    def _fake_append(points, oauth_client=None):
        captured["oauth"] = oauth_client
        return {"written": len(points), "skipped": 0}

    monkeypatch.setattr(NG, "append_points", _fake_append)
    sentinel = object()
    NS.backfill_to_gs(["A"], oauth_client=sentinel)
    assert captured["oauth"] is sentinel
