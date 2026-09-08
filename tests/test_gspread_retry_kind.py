"""tests/test_gspread_retry_kind.py — gspread 重試分類：**永久性錯誤不得被重試**（2026-09-07）。

背景（憲法 §8.3.P `P-RETRYKIND-1`）
----------------------------------
`infra/gspread_retry.py::with_gspread_retry` 原本直接拿**冷卻分類**
（`kind_for_gspread_error` → `kind_for_status`）當**重試判準**，而那兩件事是不同的軸：

  · `kind_for_status` 把 400 / 401 / 402 / 409 / 410 等非特例的 4xx 與 5xx **一起**歸
    `server_error`（`shared/backoff_policy.py` 對**冷卻長度**刻意的分法）；
  · `kind_for_gspread_error` 把 404 / 407 **改判**成 `unreachable`（為了拿 60s 冷卻）。

兩者都在 `GSPREAD_RETRYABLE_KINDS` 裡 ⇒ **400 / 404 / 407 / 409 / 410 全部會被重試**。
**2026-09-07 實測（修復前）：各重打 4 次。**

為什麼這是 bug 不是小事
------------------------
重試一個永久性錯誤，等於把**確定性失敗**變成**多打三次再失敗**，而且**遮蔽根因**。
400 `exceeds grid limits` 正是 2026-09 那班 NAV 排程失敗的第一根因的形狀 ——
重打一百次還是同一個 400。

本檔釘住三件事
--------------
  (1) **分類軸**：`is_transient_gspread_error` 對每個狀態碼的判定（含正／負對照）；
  (2) **行為軸**：`with_gspread_retry` 的**實際嘗試次數**（sleep 換成計數器，
      迴圈保留、wall time 歸零）；
  (3) **兩軸沒有被合併**：冷卻分類**維持原樣**（404/407 仍是 `unreachable`、
      400 仍是 `server_error`）—— 有人若靠改冷卻分類來「修」重試，本檔會轉紅。

⚠️ **本檔刻意不用 `importorskip` 跳過**
---------------------------------------
`tests/test_nav_append_retry.py` 對需要真 `APIError` 的條目用 `importorskip`，
於是**無 gspread 的精簡環境完全守不到這件事**。本檔改用「有 gspread 就用真的、
沒有就注入一個滿足 `http_status_of` duck-type 契約的 stub」，讓分類邏輯在**任何**
環境都真的被跑到。stub 只是造例外物件，**不發任何請求、不裝任何套件**。
"""
from __future__ import annotations

import sys
import types

import pytest

from infra import gspread_retry as GR

# 與真實排程等長（同 test_nav_append_retry 的理由：寫死長度會製造與程式無關的假紅燈）
_FAST = (0.0,) * len(GR.DEFAULT_QUOTA_BACKOFFS)
_N = len(_FAST)

# 分類軸與行為軸**共用同一份清單**，兩軸因此不可能再各自漂移（2026-09-08）。
#
# ⚠️ 為什麼要共用：它們原本是兩份手寫清單，分類軸有 10 個、行為軸只有 7 個
# —— 少的正是 401 / 402 / 422。獨立稽核用突變證明那是**真破洞**：把 401 偷偷放回
# 重試，行為真的變了（attempts 1 → 4），而整套測試**全綠、毫無反應**。
# 成因是兩份清單**出處不同**（行為軸照著當時重現表的 5 個永久碼 + 403/429 寫，
# 分類軸則涵蓋更廣），而**沒有任何一條規則要求它們一致**。
#
# 這裡不是「再補一次漏掉的三個」，是把「兩份清單必須一致」從**人的自律**
# 改成**結構上的必然** —— 往後新增一個狀態碼，兩軸同時生效，漏不掉。
# 若日後真有狀態碼需要「分類是 4xx 但行為不同」，必須**明確拆開並寫下理由**，
# 那正是應該被迫思考的時刻。
_NON_TRANSIENT_STATUSES = [400, 401, 402, 403, 404, 407, 409, 410, 422, 429]


def _stub_gspread(monkeypatch):
    """注入一個最小 `gspread.exceptions`，只為讓 `http_status_of` 認得出 `APIError`。

    `http_status_of` 對它的唯一要求：`isinstance(exc, APIError)` 且
    `exc.response.status_code` 是 int。真 gspread 6.x 的 `APIError(Response)` 同形。
    """
    g = types.ModuleType("gspread")
    ge = types.ModuleType("gspread.exceptions")

    class APIError(Exception):
        def __init__(self, response):
            super().__init__(f"APIError {response.status_code}")
            self.response = response

    ge.APIError = APIError
    g.exceptions = ge
    monkeypatch.setitem(sys.modules, "gspread", g)
    monkeypatch.setitem(sys.modules, "gspread.exceptions", ge)
    return APIError


@pytest.fixture
def api_error(monkeypatch):
    """回一個 `make(status) -> APIError`。有真 gspread 就用真的，否則注入 stub。

    ⚠️ 兩條路走的是**同一段** `http_status_of`，差別只在 `APIError` 這個類別哪來的。
    """
    try:
        from gspread.exceptions import APIError as _Real  # noqa: F401
        import requests

        def make(status: int):
            r = requests.Response()
            r.status_code = status
            r._content = (b'{"error":{"code":%d,"message":"boom","status":"X"}}'
                          % status)
            return _Real(r)
    except Exception:                       # noqa: BLE001 — 精簡環境無 gspread
        _Stub = _stub_gspread(monkeypatch)

        class _Resp:
            def __init__(self, sc):
                self.status_code = sc

        def make(status: int):
            return _Stub(_Resp(status))

    # 輸入非空 / 自我驗證：造出來的例外必須真的被 http_status_of 認出，否則整檔量測無效
    assert GR.http_status_of(make(404)) == 404, "APIError 造不出來，本檔的量測全部無效"
    return make


class _ConnLayer(Exception):
    """連線層失敗（逾時 / DNS / 連線被重設）—— **無** HTTP 狀態碼。"""


@pytest.fixture
def attempts(monkeypatch):
    """回 `run(exc_factory) -> (嘗試次數, sleep 次數)`。

    `time.sleep` 換成計數器：**重試迴圈與分類邏輯全是真的**，只把 wall time 拿掉。
    """
    sleeps: list = []
    monkeypatch.setattr(GR, "time", types.SimpleNamespace(sleep=sleeps.append))

    def run(exc_factory):
        sleeps.clear()
        calls = {"n": 0}

        def boom(*_a, **_k):
            calls["n"] += 1
            raise exc_factory()

        with pytest.raises(Exception):
            GR.with_gspread_retry(boom, backoffs=_FAST)
        return calls["n"], len(sleeps)

    return run


# ══════════════════════════════════════════════════════════════
# (1) 分類軸：is_transient_gspread_error
# ══════════════════════════════════════════════════════════════
@pytest.mark.parametrize("status", _NON_TRANSIENT_STATUSES)
def test_client_errors_are_not_transient(api_error, status):
    """4xx 一律**不是**暫時性 —— 請求／權限／設定問題，隔一秒再打不會變好。"""
    assert GR.is_transient_gspread_error(api_error(status)) is False


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_server_errors_are_transient(api_error, status):
    """正對照：5xx **是**暫時性 —— 這正是 2026-09-02 事故命中的那一種，不可被一起修掉。"""
    assert GR.is_transient_gspread_error(api_error(status)) is True


def test_connection_layer_without_status_is_transient():
    """無狀態碼（逾時 / DNS / 連線重設）＝ 暫時性。不依賴 gspread，任何環境都跑。"""
    assert GR.is_transient_gspread_error(_ConnLayer("read timed out")) is True


def test_quota_error_without_status_is_not_transient():
    """負對照：只剩字串的 429 **不是**暫時性 —— 「對方明確叫我們停」，
    立刻重試會延長封鎖窗口（`shared/backoff_policy.py` 對 `rate_limited` 的定性）。"""
    assert GR.is_transient_gspread_error(RuntimeError("Quota exceeded")) is False


# ══════════════════════════════════════════════════════════════
# (2) 行為軸：with_gspread_retry 的實際嘗試次數
# ══════════════════════════════════════════════════════════════
@pytest.mark.parametrize("status", _NON_TRANSIENT_STATUSES)
def test_permanent_status_is_attempted_exactly_once(api_error, attempts, status):
    """⛔ 永久性錯誤：**只打一次**，一次 sleep 都不能有。

    修復前實測（2026-09-08 於 merge-base `810ebc5` 的 `infra/gspread_retry.py`
    重跑，⛔ 非轉述）：**400 / 401 / 402 / 404 / 407 / 409 / 410 / 422 各打 4 次、
    sleep 3 次**；403 / 429 本來就只打 1 次。

    ⚠️ **401 / 402 / 422 是 2026-09-08 才補進來的**（本檔原先只覆蓋 7 個）。
    它們與另外五個**修復前後的數字完全一樣**（4 → 1），沒有任何理由被排除在外
    —— 那是漏的，不是刻意的。**參數表已改為與分類軸共用
    `_NON_TRANSIENT_STATUSES`，同一個漏法不會再發生第二次。**
    """
    n, s = attempts(lambda: api_error(status))
    assert (n, s) == (1, 0), (
        f"HTTP {status} 不是暫時性抖動，必須第一次失敗就拋；"
        f"實際嘗試 {n} 次、sleep {s} 次")


@pytest.mark.parametrize("status", [500, 503])
def test_transient_status_is_retried_to_the_end(api_error, attempts, status):
    """正對照：5xx 仍然重試滿 `len(backoffs)` 次 —— 證明上一條的 `1` 不是
    「量測器壞掉、什麼都不重試」造成的假綠燈。"""
    n, s = attempts(lambda: api_error(status))
    assert (n, s) == (_N, _N - 1), f"5xx 應重試滿 {_N} 次，實際 {n} 次 / sleep {s} 次"


def test_connection_layer_is_retried_to_the_end(attempts):
    """正對照（不依賴 gspread）：連線層失敗仍然重試滿 —— 精簡環境的重試守衛。"""
    n, _ = attempts(_ConnLayer)
    assert n == _N, f"連線層失敗應重試滿 {_N} 次，實際 {n} 次"


def test_success_path_makes_exactly_one_call(attempts, monkeypatch):
    """負對照：成功時不得多打 —— 證明重試包裝在快樂路徑上零成本。"""
    monkeypatch.setattr(GR, "time", types.SimpleNamespace(sleep=lambda _d: None))
    calls = {"n": 0}

    def ok(*_a, **_k):
        calls["n"] += 1
        return "done"

    assert GR.with_gspread_retry(ok, backoffs=_FAST) == "done"
    assert calls["n"] == 1


# ══════════════════════════════════════════════════════════════
# (3) 兩軸沒有被合併（修對的路只有一條）
# ══════════════════════════════════════════════════════════════
@pytest.mark.parametrize("status,cool_kind", [(400, "server_error"),
                                              (404, "unreachable"),
                                              (407, "unreachable"),
                                              (409, "server_error"),
                                              (410, "server_error")])
def test_cooldown_axis_is_untouched(api_error, status, cool_kind):
    """**冷卻分類必須維持原樣。**

    這五個狀態碼的冷卻分類今天仍然落在 `GSPREAD_RETRYABLE_KINDS` 裡 ——
    那**不是**遺漏，而是本次刻意不動冷卻軸的結果：
      · 404 / 407 的 `unreachable` 是 `kind_for_gspread_error` **刻意改判**來的
        （為了 60s 冷卻，而不是 `not_found` / `proxy_auth` 的 0），
        `tests/test_gspread_source_backoff.py` 有兩條在守它；
      · 400 / 409 / 410 的 `server_error` 是 `shared/backoff_policy.py`
        （冷卻 SSOT，**在本批邊界外**）明訂的 300s 那一格。
    若有人靠「把它們踢出冷卻分類」來修重試，本條會轉紅 —— 那條路會連冷卻長度一起改掉。
    """
    exc = api_error(status)
    assert GR.kind_for_gspread_error(exc) == cool_kind
    assert cool_kind in GR.GSPREAD_RETRYABLE_KINDS
    assert GR.is_transient_gspread_error(exc) is False   # 重試軸仍然說「不要重試」


_ALL_KINDS = frozenset({"server_error", "unreachable", "blocked",
                        "rate_limited", "not_found", "proxy_auth"})


def _count_attempts(exc_factory, **kw) -> int:
    """跑一次 `with_gspread_retry`（必失敗），回實際嘗試次數。"""
    calls = {"n": 0}

    def boom(*_a, **_k):
        calls["n"] += 1
        raise exc_factory()

    with pytest.raises(Exception):
        GR.with_gspread_retry(boom, backoffs=_FAST, **kw)
    return calls["n"]


def test_retry_kinds_narrows(monkeypatch):
    """`retry_kinds` 降級為 caller 的**收窄旋鈕** —— 收窄仍然有效。

    把 `unreachable` 拿掉之後，連線層失敗（本來會重試滿）**只打一次**。
    """
    monkeypatch.setattr(GR, "time", types.SimpleNamespace(sleep=lambda _d: None))
    assert _count_attempts(_ConnLayer) == _N, "先確認不收窄時它真的會重試滿"
    assert _count_attempts(_ConnLayer,
                           retry_kinds=frozenset({"server_error"})) == 1


def test_retry_kinds_cannot_widen_back_to_4xx(api_error, monkeypatch):
    """⛔ 但它**不能放寬**：caller 就算把全部冷卻分類都放進 `retry_kinds`，
    4xx 仍然只打一次 —— 判準在 `is_transient_gspread_error`，不在這個旋鈕。"""
    monkeypatch.setattr(GR, "time", types.SimpleNamespace(sleep=lambda _d: None))
    assert _count_attempts(lambda: api_error(400), retry_kinds=_ALL_KINDS) == 1
    assert _count_attempts(lambda: api_error(404), retry_kinds=_ALL_KINDS) == 1
    # 正對照：同一個放寬過的 retry_kinds 下，5xx 照樣重試滿 —— 證明不是「全都不重試」
    assert _count_attempts(lambda: api_error(500), retry_kinds=_ALL_KINDS) == _N


# ══════════════════════════════════════════════════════════════
# (4) 已知 fail-open：無 gspread 時狀態碼撈不到 → 退回「當暫時性」
# ══════════════════════════════════════════════════════════════
def test_known_limitation_without_gspread_status_is_lost(api_error, monkeypatch):
    """⚠️ **誠實揭露的已知缺口，不是期望行為**（§-2 規則 6）。

    `http_status_of` 在 `import gspread.exceptions` 失敗時**一律回 `None`**
    （該函式對精簡環境的既有處置）。於是在沒有 gspread 的環境裡，一個帶 400 的
    `APIError` 會退化成「無狀態碼」→ 被判為暫時性 → **照舊重試**。

    本 repo `requirements.txt` pin 了 `gspread>=6.0.0`，正常 CI 與 production
    不會落到這條路；本條**釘住這個退化的形狀**，好讓它哪天被收斂時有人看得見。
    """
    exc = api_error(400)
    assert GR.is_transient_gspread_error(exc) is False       # 有 gspread：判得出來

    monkeypatch.setitem(sys.modules, "gspread", None)        # 模擬「沒有 gspread」
    monkeypatch.setitem(sys.modules, "gspread.exceptions", None)
    assert GR.http_status_of(exc) is None, "無 gspread 時本來就撈不到狀態碼"
    assert GR.is_transient_gspread_error(exc) is True, (
        "已知缺口：撈不到狀態碼時退回『當暫時性』。若這條轉紅，代表有人收斂了這個 "
        "fail-open —— 那是好事，請把本條改成斷言新行為並更新 "
        "is_transient_gspread_error 的『已知限制』段。")
