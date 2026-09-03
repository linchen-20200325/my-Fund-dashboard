"""tests/test_nav_gate0_retry.py — Gate 0 預讀重試（2026-09-03，production 事故修復）。

背景（獨立調查組實測，2026-08-31 / 09-02 各命中一次）：`scripts/weekly_nav_backfill.py`
→ `services/nav_history_store.py::backfill_to_gs` 在處理任何一檔基金之前，先呼叫
`nav_history_gs.load_points()` 讀雲端既有 nav_history（給 Gate 0 防污染比對）。那一次
讀取被 `client.open_by_key` 的**單次 gspread 5xx** 打斷、**完全沒有重試**，直接判「本次
不寫雲端」（fail-closed，§1）—— 11 檔明明抓到淨值，雲端卻新增 0 筆。

修法：`nav_history_gs.load_points` 新增 opt-in `retries` 參數（預設 `False`，行為與改動
前逐字相同），只有 Gate 0 的呼叫（`backfill_to_gs`）傳 `True`。`retries=True` 時，
`infra.gspread_retry.with_gspread_retry` 依 `kind_for_gspread_error` 分類，只重試
「多半是暫時性」的失敗（5xx / 逾時），且**冷卻只在重試全部用完之後才登記**——這是本案
最容易做錯的地方：2026-09-01 新加的跨呼叫冷卻機制若在「第一次失敗」就登記，接下來
300 秒（`server_error` 的冷卻時長）同一張表的所有讀取會被主動擋下，連自己剛加的重試
機會都用不到（9/2 事故正是這個形狀；對照 8/31，冷卻機制當時還不存在，2 分鐘後同一張
表的其他讀取就成功了，證明那次確實是短暫性的）。

本檔釘住三件事，缺一不可：
  (1) 第一次失敗、第二次成功 → `retries=True` 有重試、最終讀得到資料，且不留冷卻登記；
  (2) 重試全部耗盡 → 仍然 fail-closed（不寫雲端）——**不得**因為加了重試就把
      §1 的 fail-closed 守衛拿掉；
  (3) 冷卻只在「重試全部用完」之後才登記一次 —— 不是每次暫時性失敗就登記一次
      （用 `record_gspread_failure` 的**呼叫次數**量，不能只看事後的 `SB._STATE`，
      因為最終成功會把冷卻清掉，光看終態分不出「中途登記過又被清掉」與「從未登記過」）。

⚠️ 突變驗證（依派工要求逐條實跑，原始輸出見 PR 描述）：把
`services/nav_history_gs.py::load_points` 內 `if retries: ... with_gspread_retry(...)`
那個分支改成永遠走 `_read_once()`（即拿掉 retries 生效的路徑），上面 (1) 應轉紅
（不會重試，第一次 500 就直接 raise）。
"""
from __future__ import annotations

import pandas as pd
import pytest
import requests

from infra import gspread_retry as GR
from infra import source_backoff as SB

NAV_HEADERS = ["code", "date", "nav", "fund_name", "source", "recorded_at"]


def _api_error(status: int, msg: str = "boom"):
    """造一個帶真實 HTTP 狀態碼的 gspread APIError（gspread 6.x 需要 Response）。
    做法與 `tests/test_gspread_source_backoff.py::_api_error` 相同（各檔自帶一份，
    本 repo 測試檔一律不互相 import）。"""
    gex = pytest.importorskip("gspread.exceptions")
    r = requests.Response()
    r.status_code = status
    r._content = ('{"error":{"code":%d,"message":"%s","status":"X"}}'
                  % (status, msg)).encode()
    return gex.APIError(r)


class _Counter:
    def __init__(self):
        self.n = 0


class _FakeWS:
    def __init__(self, counter):
        self._c = counter

    def get_all_values(self):
        self._c.n += 1
        return [NAV_HEADERS, ["ALZF9", "2026-07-22", "12.34", "安聯", "app", "t"]]


class _FakeSpreadsheet:
    def __init__(self, counter):
        self._c = counter

    def worksheet(self, name):
        return _FakeWS(self._c)


class _FlakyClient:
    """`open_by_key` 前 `fail_times` 次拋 `status`（模擬 2026-09-02 事故的失敗點：
    根因是 `client.open_by_key` 的單次 5xx），之後每次成功。"""

    def __init__(self, counter, fail_times, status=500):
        self._c = counter
        self._fail_times = fail_times
        self._status = status
        self.calls = 0

    def open_by_key(self, _k):
        self._c.n += 1
        self.calls += 1
        if self.calls <= self._fail_times:
            raise _api_error(self._status)
        return _FakeSpreadsheet(self._c)


@pytest.fixture
def gs(monkeypatch):
    """接上假 SA 憑證，回一個 factory `make(fail_times, status=500) -> (client, counter)`
    負責產生可控制失敗次數的假 gspread client（同 `tests/test_gspread_source_backoff.py`
    的 `gs` fixture精神，本檔改為可注入 `fail_times` 以測「先失敗、後成功」）。"""
    import infra.config as cfg
    import repositories.policy_repository as polrepo

    sa = {"client_email": "probe@x.iam.gserviceaccount.com"}
    orig = cfg.get_secret
    monkeypatch.setattr(
        cfg, "get_secret",
        lambda k, *a, **kw: (sa if k == "google_service_account" else orig(k, *a, **kw)))
    monkeypatch.setattr(cfg, "require_secret", lambda k: sa)

    def make(fail_times, status=500):
        counter = _Counter()
        client = _FlakyClient(counter, fail_times, status)
        monkeypatch.setattr(polrepo, "get_gspread_client", lambda *a, **k: client)
        return client, counter

    return make


@pytest.fixture(autouse=True)
def _isolate_backoff():
    """每條測試前後清空跨呼叫冷卻狀態，避免互相污染（同 `test_gspread_source_backoff.py`
    的隔離原則；本檔額外在每條測試內自行斷言冷卻狀態，隔離更重要）。"""
    SB.reset_all()
    yield
    SB.reset_all()


# ══════════════════════════════════════════════════════════════
# (1) 第一次 5xx、第二次成功 → retries=True 有重試、最終讀得到資料
# ══════════════════════════════════════════════════════════════
def test_retries_true_recovers_from_one_transient_5xx(gs):
    import services.nav_history_gs as NG

    client, counter = gs(1, status=500)

    got = NG.load_points("ALZF9", retries=True)

    assert got and got[0]["code"] == "ALZF9" and got[0]["nav"] == 12.34
    assert client.calls == 2, f"應該重試一次成功，實際 open_by_key 被呼叫 {client.calls} 次"
    # 最終成功 → 不得殘留任何冷卻登記（正常收尾，不是本測試的核心斷言，另見 test 3）。
    assert not SB._STATE, f"最終成功不該留下冷卻登記，實際 {SB._STATE}"


def test_retries_false_default_does_not_retry(gs):
    """預設 `retries=False`：行為與改動前逐字相同 —— 第一次失敗就直接 raise，
    不重試。這條釘住「新參數不影響既有呼叫點」（`load_series` / `nav_history_hook.py` /
    `coverage_status` 全部沒有傳 `retries`，必須維持零行為變更）。"""
    import services.nav_history_gs as NG

    client, counter = gs(1, status=500)

    with pytest.raises(NG.NavHistoryError):
        NG.load_points("ALZF9")               # 未傳 retries → 預設 False

    assert client.calls == 1, f"retries=False 不該重試，實際被呼叫 {client.calls} 次"


def test_retries_true_only_retries_transient_kinds_not_quota():
    """429（配額）**不**在 `GSPREAD_RETRYABLE_KINDS` 內 —— `shared/backoff_policy.py`
    對它的定性是「對方明確叫我們停，繼續探測會延長封鎖窗口」，立刻重試違反那個定性。
    本測試直接釘 `with_gspread_retry` 本身（不繞遠路建假 SA），對照 5xx 會重試。"""
    calls = {"n": 0}

    def _quota_then_ok():
        calls["n"] += 1
        if calls["n"] == 1:
            raise _api_error(429)
        return "ok"

    with pytest.raises(Exception):
        GR.with_gspread_retry(_quota_then_ok, backoffs=(0.0, 0.0))
    assert calls["n"] == 1, "429 不屬於可重試分類，第一次失敗就該直接拋出"

    calls["n"] = 0

    def _5xx_then_ok():
        calls["n"] += 1
        if calls["n"] == 1:
            raise _api_error(500)
        return "ok"

    assert GR.with_gspread_retry(_5xx_then_ok, backoffs=(0.0, 0.0)) == "ok"
    assert calls["n"] == 2, "5xx 屬於可重試分類，應該重試一次後成功"


# ══════════════════════════════════════════════════════════════
# (2) 重試全部耗盡 → 仍然 fail-closed（不寫雲端 / raise）
# ══════════════════════════════════════════════════════════════
def test_retries_exhausted_still_raises(gs):
    """§1 fail-closed 守衛：全部重試用完仍失敗 → `load_points` 仍然 raise
    （不得因為加了重試就悄悄吞掉最終失敗）。"""
    import services.nav_history_gs as NG

    client, counter = gs(999, status=500)   # 永遠失敗

    with pytest.raises(NG.NavHistoryError):
        NG.load_points("ALZF9", retries=True)

    n_attempts = len(GR.DEFAULT_QUOTA_BACKOFFS)
    assert client.calls == n_attempts, (
        f"應該試滿 {n_attempts} 次才放棄（DEFAULT_QUOTA_BACKOFFS），實際 {client.calls} 次")


def test_gate0_still_fail_closed_when_retries_exhausted(monkeypatch):
    """端到端：Gate 0（`backfill_to_gs`）在 `load_points` 重試全部耗盡後，仍然
    fail-closed —— 這是本案「不得拿掉 fail-closed 守衛，也不得改變 Gate 0 判定語意」
    的硬要求。這裡直接把 `nav_history_gs.load_points` 換成一個「模擬重試已耗盡、
    最終失敗」的假件（不重跑真正的 gspread 重試迴圈 —— 那件事由上面 test_retries_
    exhausted_still_raises 守），驗證的是 `backfill_to_gs` 收到失敗後的行為。"""
    import services.moneydj_fetcher as MF
    import services.nav_history_gs as GS
    import services.nav_history_store as NS

    def _load_points_exhausted(*a, **kw):
        assert kw.get("retries") is True, (
            "Gate 0 必須以 retries=True 呼叫 load_points（否則本次修復沒有生效）")
        raise GS.NavHistoryError("模擬：重試全部耗盡後仍然失敗（gspread 5xx）")

    monkeypatch.setattr(GS, "load_points", _load_points_exhausted)
    monkeypatch.setattr(GS, "is_enabled", lambda: True)

    s = pd.Series([1.0, 1.01], index=pd.to_datetime(["2026-07-21", "2026-07-22"]))
    monkeypatch.setattr(MF, "auto_fetch_moneydj",
                        lambda code, **kw: {"series": s, "fund_name": "測試基金"})

    written: list = []

    def _append(points, **kw):
        written.extend(points)
        return {"written": len(points), "skipped": 0}

    monkeypatch.setattr(GS, "append_points", _append)

    res = NS.backfill_to_gs(["OK"])

    assert not written, "Gate 0 讀不到既有歷史時（重試耗盡後），仍必須擋下所有雲端寫入"
    assert res.get("gs_written") == 0
    assert res.get("gs_error"), "必須誠實回報 gate 讀取失敗，不能靜默"
    # 抓取本身沒有受影響（§1「抓取成功 vs 雲端寫入失敗是兩件事」，不得因為 Gate 0
    # 擋下寫入就連抓取結果都一起沖掉）。
    assert res["results"][0]["fetched"] == 2


# ══════════════════════════════════════════════════════════════
# (3) 冷卻只在「重試全部用完」之後才登記 —— 不是第一次失敗就登記
# ══════════════════════════════════════════════════════════════
def test_cooldown_registered_only_after_retries_exhausted(gs, monkeypatch):
    """本案最容易做錯的地方（9/2 事故的鏡像）：中途的暫時性失敗**不得**提前登記冷卻，
    否則加的重試機會會被自己的冷卻機制擋掉，等於沒加。用呼叫次數量，不能只看事後的
    `SB._STATE`（成功會把冷卻清掉，光看終態分不出「中途登記過又被清掉」與「從未登記過」）。
    """
    import services.nav_history_gs as NG

    calls = {"n": 0}
    orig_fail = GR.record_gspread_failure

    def _spy_fail(*a, **kw):
        calls["n"] += 1
        return orig_fail(*a, **kw)

    monkeypatch.setattr(GR, "record_gspread_failure", _spy_fail)

    # --- 情境 A：先失敗一次、第二次成功 → record_gspread_failure 完全不該被呼叫 ---
    client, counter = gs(1, status=500)
    NG.load_points("ALZF9", retries=True)
    assert calls["n"] == 0, (
        "中途的暫時性失敗（重試最終成功）不該登記冷卻 —— "
        f"record_gspread_failure 被呼叫了 {calls['n']} 次")

    # --- 情境 B：全部重試都失敗 → record_gspread_failure 只該被呼叫「一次」
    #     （不是 len(backoffs) 次；證明冷卻是在重試迴圈之外、例外真正往外傳播之後
    #     才登記，不是每次暫時性失敗各登記一次）---
    calls["n"] = 0
    SB.reset_all()
    client2, counter2 = gs(999, status=500)
    with pytest.raises(NG.NavHistoryError):
        NG.load_points("ALZF9", retries=True)
    assert calls["n"] == 1, (
        "重試全部耗盡後，冷卻只該被登記一次（在 except 那一層），"
        f"實際被呼叫 {calls['n']} 次")
    assert SB._STATE, "重試全部耗盡後，最終仍必須留下冷卻登記（不能連最終失敗都不記）"
