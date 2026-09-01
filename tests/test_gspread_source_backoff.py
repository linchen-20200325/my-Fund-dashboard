"""tests/test_gspread_source_backoff.py — gspread 跨呼叫來源冷卻（2026-09-01 批次 2）

客戶 2026-09-01 指示：「批次 2（gspread 相關站點）：加上跨呼叫冷卻退避
（避免 WebSocket 斷線事故）」。

本檔釘住三件事，缺一不可：
  (1) **失敗會被登記**（沒登記 → 冷卻永遠不會發生 → 每次 rerun 重打）；
  (2) **冷卻期內真的不打上游**（用「上游往返計數器」量，不是看有沒有印字）；
  (3) **冷卻期滿會真的重試**（用注入的假時鐘走完整段冷卻，不是只跑一次）。

⚠️ 為什麼要數「上游往返次數」而不是斷言回傳值：`@st.cache_data` 會讓
「沒有重打」與「重打了但拿到一樣的值」在回傳值上完全一樣。**只有計數器分得出來。**
"""
from __future__ import annotations

import pytest
import requests

from infra import gspread_retry as GR
from infra import source_backoff as SB

POOL_HEADERS = ["code", "name", "category", "type_override", "note", "added_at",
                "status", "isin", "currency", "morningstar_secid"]
NAV_HEADERS = ["code", "date", "nav", "fund_name", "source", "recorded_at"]


def _api_error(status: int, msg: str = "boom"):
    """造一個帶真實 HTTP 狀態碼的 gspread APIError（gspread 6.x 需要 Response）。"""
    gex = pytest.importorskip("gspread.exceptions")
    r = requests.Response()
    r.status_code = status
    r._content = ('{"error":{"code":%d,"message":"%s","status":"X"}}'
                  % (status, msg)).encode()
    return gex.APIError(r)


# ══════════════════════════════════════════════════════════════
# 1) 失敗分類：gspread 的 404/407 **刻意不沿用** kind_for_status 的 0 冷卻
# ══════════════════════════════════════════════════════════════
@pytest.mark.parametrize("status,expect", [
    (429, "rate_limited"),
    (403, "blocked"),
    (500, "server_error"),
    (401, "server_error"),
])
def test_kind_follows_status_table(status, expect):
    assert GR.kind_for_gspread_error(_api_error(status)) == expect


def test_gspread_404_does_not_inherit_the_zero_cooldown_exemption():
    """`source_backoff.kind_for_status(404)` 是 `not_found`（**0 冷卻**）——
    那條豁免服務的是「輪好幾個月份 slug、舊月份 404 是正常流程」的探測鏈。
    gspread **沒有探測鏈**：404 只代表 sheet_id 不存在或這把憑證沒被分享，
    每次 rerun 都會重演。照抄 0 冷卻 = 設定錯誤被連續轟炸。"""
    assert SB.kind_for_status(404) == "not_found"
    assert SB.cooldown_for("not_found") == 0                 # 原表確實是 0
    assert GR.kind_for_gspread_error(_api_error(404)) == "unreachable"
    assert SB.cooldown_for(GR.kind_for_gspread_error(_api_error(404))) > 0


def test_kind_walks_the_cause_chain():
    """`services/nav_history_gs` 會把底層例外包成 `NavHistoryError(...) from e`，
    狀態碼藏在 `__cause__` 裡 —— 撈不到就會全部退成 unreachable(60s)，
    429 的 30 分鐘冷卻等於失效。"""
    try:
        raise _api_error(429)
    except Exception as inner:
        wrapped = RuntimeError("nav_history load 失敗")
        wrapped.__cause__ = inner
    assert GR.http_status_of(wrapped) == 429
    assert GR.kind_for_gspread_error(wrapped) == "rate_limited"


def test_quota_error_without_status_still_classified():
    assert GR.kind_for_gspread_error(RuntimeError("Quota exceeded")) == "rate_limited"


def test_transport_failure_falls_back_to_shortest_cooldown():
    assert GR.kind_for_gspread_error(TimeoutError("read timed out")) == "unreachable"


# ══════════════════════════════════════════════════════════════
# 2) 兩把鑰匙：配額記在憑證層、其餘記在單一試算表層
# ══════════════════════════════════════════════════════════════
def test_quota_failure_cools_the_whole_credential_not_one_sheet():
    """Sheets API 的讀取配額維度是 *per user per project*（憑證），不是 per spreadsheet
    —— 429 只冷卻「那一本」等於放任同一把憑證繼續打其他本，配額不會恢復。"""
    key, cd = GR.record_gspread_failure("sa", "SHEET_A", _api_error(429))
    assert key == GR.quota_key("sa") and cd > 0
    assert GR.should_skip_gspread("sa", "SHEET_A")[0] is True
    assert GR.should_skip_gspread("sa", "SHEET_B")[0] is True     # 同憑證的另一本也停
    assert GR.should_skip_gspread("oauth", "SHEET_A")[0] is False  # 另一把憑證不受影響


def test_permission_failure_cools_only_that_sheet():
    """本 repo 有兩本不同的試算表（POOL_SHEET_ID / NAV_SHEET_ID），且兩處 docstring
    都寫著「SA 須被加為**該本**的編輯者」——「一本分享了、另一本沒有」是預期狀態。
    403 若冷卻整把憑證，就會用沒分享那本去關掉健康的那本（誤殺）。"""
    key, cd = GR.record_gspread_failure("sa", "SHEET_A", _api_error(403))
    assert key == GR.sheet_key("sa", "SHEET_A") and cd > 0
    assert GR.should_skip_gspread("sa", "SHEET_A")[0] is True
    assert GR.should_skip_gspread("sa", "SHEET_B")[0] is False    # ← 沒有被誤殺


def test_success_clears_both_keys():
    GR.record_gspread_failure("sa", "SHEET_A", _api_error(429))
    GR.record_gspread_failure("sa", "SHEET_A", _api_error(403))
    GR.record_gspread_success("sa", "SHEET_A")
    assert GR.should_skip_gspread("sa", "SHEET_A")[0] is False


def test_no_credential_means_no_backoff_at_all():
    """本地 JSON 後端不上網 —— 沒有來源可以退避，也不該有。"""
    assert GR.record_gspread_failure("", "", _api_error(429)) == ("", 0)
    assert GR.should_skip_gspread("", "")[0] is False


def test_backoff_stores_no_payload():
    """退避只存「何時可以再試」，**不存任何值** —— 這是它與『快取失敗值』的分界
    （§1：退避期內回的與『真的打了但失敗』完全相同）。"""
    GR.record_gspread_failure("sa", "SHEET_A", _api_error(429))
    for ent in SB._STATE.values():
        assert set(ent) == {"until", "kind", "cooldown", "fails", "last_fail"}


# ══════════════════════════════════════════════════════════════
# 3) 假 gspread：可注入失敗、可數上游往返次數
# ══════════════════════════════════════════════════════════════
class _Counter:
    def __init__(self):
        self.n = 0


class _FakeWS:
    def __init__(self, name, counter, fail_at):
        self._name, self._c, self._fail = name, counter, fail_at

    def get_all_values(self):
        self._c.n += 1
        if "values" in self._fail:
            raise _api_error(429)
        if self._name == "_fund_pool":
            return [POOL_HEADERS,
                    ["ALZF9", "安聯", "股票", "", "", "2026-01-01", "WATCHING",
                     "LU0766462157", "USD", "F00000P8WB"]]
        return [NAV_HEADERS, ["ALZF9", "2026-07-22", "12.34", "安聯", "app", "t"]]

    def row_values(self, _n):
        return POOL_HEADERS


class _FakeSpreadsheet:
    def __init__(self, counter, fail_at):
        self._c, self._fail = counter, fail_at

    def worksheet(self, name):
        self._c.n += 1
        if "worksheet" in self._fail:
            raise _api_error(429)
        if "worksheet_missing" in self._fail:
            raise RuntimeError("WorksheetNotFound")   # 非 API 錯誤：分頁真的還沒建
        return _FakeWS(name, self._c, self._fail)


class _FakeClient:
    def __init__(self, counter, fail_at):
        self._c, self._fail = counter, fail_at

    def open_by_key(self, _k):
        self._c.n += 1
        if "open" in self._fail:
            raise _api_error(429)
        return _FakeSpreadsheet(self._c, self._fail)


@pytest.fixture
def gs(monkeypatch):
    """接上假 SA 憑證 + 假 gspread client，回 (counter, set_fail)。"""
    import infra.config as cfg
    import repositories.policy_repository as polrepo

    sa = {"client_email": "probe@x.iam.gserviceaccount.com"}
    orig = cfg.get_secret
    monkeypatch.setattr(
        cfg, "get_secret",
        lambda k, *a, **kw: (sa if k == "google_service_account" else orig(k, *a, **kw)))
    monkeypatch.setattr(cfg, "require_secret", lambda k: sa)

    counter, fail = _Counter(), set()
    monkeypatch.setattr(polrepo, "get_gspread_client",
                        lambda *a, **k: _FakeClient(counter, fail))

    def set_fail(*where):
        fail.clear()
        fail.update(where)

    return counter, set_fail


# ══════════════════════════════════════════════════════════════
# 4) 選股池（repositories/pool_repository）
# ══════════════════════════════════════════════════════════════
def _fresh_pool():
    import repositories.pool_repository as P
    P._clear_pool_cache()
    try:
        import streamlit as st
        st.cache_data.clear()
    except Exception:                                # pragma: no cover
        pass
    return P


def test_pool_load_raises_instead_of_swallowing(gs):
    """§1「空有兩義」：**空選股池是合法狀態**。把讀失敗吞成 `{}` 之後，
    `@st.cache_data` 會把那個假空池鎖滿 30 分鐘 TTL。"""
    _c, set_fail = gs
    set_fail("open")
    P = _fresh_pool()
    with pytest.raises(Exception):
        P._load_pool_map()


def test_pool_lookup_stops_hitting_sheets_after_one_failure(gs):
    """連呼 3 次 → 上游只被打 1 次（其餘在進場處被冷卻擋下）。"""
    counter, set_fail = gs
    set_fail("open")
    P = _fresh_pool()
    counter.n = 0
    for _ in range(3):
        assert P.resolve_secid("ALZF9") is None       # 抓取鏈不中斷（外譯）
    assert counter.n == 1, f"上游被打了 {counter.n} 次，冷卻沒生效"


def test_pool_failure_is_actually_registered(gs):
    """**突變哨兵**：拿掉 `_load_pool_map` 裡的 `record_gspread_failure`，本條轉紅。"""
    _c, set_fail = gs
    set_fail("open")
    P = _fresh_pool()
    P.resolve_secid("ALZF9")
    assert GR.should_skip_gspread(*P._pool_backoff_ident())[0] is True


def test_pool_recovers_after_cooldown_expires_fake_clock(gs, monkeypatch):
    """**假時鐘**：走完整段冷卻後必須**真的重試**，不是永久靜音。"""
    counter, set_fail = gs
    now = [1000.0]
    monkeypatch.setattr(SB, "_clock", lambda: now[0])
    set_fail("open")
    P = _fresh_pool()
    counter.n = 0
    assert P.resolve_secid("ALZF9") is None
    assert counter.n == 1
    _key, cooldown = GR.record_gspread_failure("sa", P._pool_backoff_ident()[1],
                                               _api_error(429))
    assert cooldown > 0

    now[0] += cooldown - 1                            # 冷卻**還沒**滿
    counter.n = 0
    P.resolve_secid("ALZF9")
    assert counter.n == 0, "冷卻未滿卻打了上游"

    now[0] += 2                                       # 冷卻期滿
    set_fail()                                        # 上游恢復
    counter.n = 0
    assert P.resolve_secid("ALZF9") == ("F00000P8WB", "USD")
    assert counter.n > 0, "冷卻期滿卻沒有重試（等於把來源永久靜音）"


def test_pool_local_backend_is_untouched(monkeypatch, tmp_path):
    """沒有 SA → 走本地 JSON，不上網、不退避、行為與改動前一致。"""
    import repositories.pool_repository as P
    monkeypatch.setattr(P, "_sa_present", lambda: False)
    assert P._pool_backoff_ident() == ("", "")
    store = P.LocalJsonPoolStore(base_dir=tmp_path)
    store.upsert(P.PoolEntry(code="ALZF9", morningstar_secid="SEC1", currency="TWD"))
    monkeypatch.setattr(P, "get_pool_store", lambda oauth_client=None: store)
    monkeypatch.setattr(P, "_cached_pool_map", P._load_pool_map)
    assert P.resolve_secid("alzf9") == ("SEC1", "TWD")


# ══════════════════════════════════════════════════════════════
# 5) nav_history（services/nav_history_gs）
# ══════════════════════════════════════════════════════════════
def test_nav_worksheet_api_error_is_no_longer_swallowed(gs):
    """`try: ws = sh.worksheet(...) / except: return []` 原本把 429 壓成
    「這張表沒有 nav_history 分頁」—— 對外與「分頁真的還沒建」同義（§1 空有兩義），
    而且冷卻機制永遠學不到那次失敗。"""
    import services.nav_history_gs as NG
    _c, set_fail = gs
    set_fail("worksheet")
    with pytest.raises(NG.NavHistoryError):
        NG.load_points("ALZF9")


def test_nav_missing_worksheet_still_returns_empty(gs):
    """反向護欄：分頁**真的**還沒建（非 API 錯誤）→ 照舊回 []，不得跟著炸。"""
    import services.nav_history_gs as NG
    _c, set_fail = gs
    set_fail("worksheet_missing")
    assert NG.load_points("ALZF9") == []


def test_nav_stops_hitting_sheets_after_one_failure(gs):
    """健診每檔基金各呼叫一次 `load_series` → 25 檔 ≈ 75 趟/rerun，
    而讀取配額是 60/min/憑證。連呼 3 次只准打 1 次。"""
    import services.nav_history_gs as NG
    counter, set_fail = gs
    set_fail("open")
    counter.n = 0
    for _ in range(3):
        with pytest.raises(NG.NavHistoryError):
            NG.load_points("ALZF9")
    assert counter.n == 1, f"上游被打了 {counter.n} 次，冷卻沒生效"


def test_nav_cooldown_raises_rather_than_returning_empty(gs):
    """冷卻期內**不可**回 `[]` —— 那會與「這檔真的還沒累積」同義，
    `fund_service` 會印出與事實不符的「⬜ 累積序列空」然後靜靜少算歷史。"""
    import services.nav_history_gs as NG
    counter, set_fail = gs
    set_fail("open")
    with pytest.raises(NG.NavHistoryError):
        NG.load_points("ALZF9")
    counter.n = 0
    with pytest.raises(NG.NavHistoryError, match="冷卻"):
        NG.load_points("ALZF9")
    assert counter.n == 0


def test_nav_failure_is_actually_registered(gs):
    """**突變哨兵**：拿掉 `load_points` 裡的 `record_gspread_failure`，本條轉紅。"""
    import services.nav_history_gs as NG
    _c, set_fail = gs
    set_fail("open")
    with pytest.raises(NG.NavHistoryError):
        NG.load_points("ALZF9")
    assert GR.should_skip_gspread(*NG._nav_backoff_ident())[0] is True


def test_nav_recovers_after_cooldown_expires_fake_clock(gs, monkeypatch):
    """**假時鐘**：冷卻期滿必須真的重試並拿到真資料。"""
    import services.nav_history_gs as NG
    counter, set_fail = gs
    now = [5000.0]
    monkeypatch.setattr(SB, "_clock", lambda: now[0])
    set_fail("open")
    counter.n = 0
    with pytest.raises(NG.NavHistoryError):
        NG.load_points("ALZF9")
    assert counter.n == 1
    cooldown = SB.cooldown_for("rate_limited")

    now[0] += cooldown - 1
    counter.n = 0
    with pytest.raises(NG.NavHistoryError, match="冷卻"):
        NG.load_points("ALZF9")
    assert counter.n == 0, "冷卻未滿卻打了上游"

    now[0] += 2
    set_fail()
    counter.n = 0
    got = NG.load_points("ALZF9")
    assert got and got[0]["code"] == "ALZF9" and got[0]["nav"] == 12.34
    assert counter.n > 0, "冷卻期滿卻沒有重試"


def test_nav_test_injected_sheet_bypasses_backoff_entirely(gs):
    """`_sheet=` 是測試注入路徑（不碰真 gspread）→ 不查冷卻、不登記，
    以免污染其他測試的退避狀態。"""
    import services.nav_history_gs as NG
    _c, set_fail = gs
    set_fail("open")
    GR.record_gspread_failure(*NG._nav_backoff_ident(), _api_error(429))

    class _Sh:
        def worksheet(self, _n):
            return _FakeWS("nav_history", _Counter(), set())

    assert NG.load_points("ALZF9", _sheet=_Sh())          # 冷卻中仍讀得到
    assert SB._STATE                                       # 且沒有清掉既有退避狀態


def test_nav_disabled_returns_empty_without_touching_backoff(monkeypatch):
    """未啟用（無 SA 無 OAuth）→ 照舊安靜回 []，不登記任何退避。"""
    import services.nav_history_gs as NG
    monkeypatch.setattr(NG, "is_enabled", lambda: False)
    assert NG.load_points("ALZF9") == []
    assert NG._nav_backoff_ident() == ("", "")
    assert not SB._STATE
