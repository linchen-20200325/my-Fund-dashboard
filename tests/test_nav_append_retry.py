"""tests/test_nav_append_retry.py — NAV **寫入**路徑的 gspread 暫時性失敗重試（2026-09-07 P0）。

背景（NAV 每日排程 `weekly_nav_backfill` 失敗事故的**第二根因**）
----------------------------------------------------------------
第一根因是網格寬度（客戶表 6 欄 / `_NAV_HEADERS` 7 欄 → 寫 `G1` 觸發 400
`exceeds grid limits`），已由 `_ensure_grid_width` 修掉，**本檔不碰它**。

本檔守的是第二根因：**`append_points` 整條寫入路徑零重試**。
`services/nav_history_store.py::backfill_to_gs` 收齊所有點之後一次呼叫
`nav_history_gs.append_points(...)`；該函式內 `_get_sheet()` 的
`client.open_by_key` 吃到**單次** gspread 5xx，整批寫入就直接 fail（§1 往上拋），
`backfill_to_gs` 回 `gs_error` → cron `exit 1`。

`abba317`（2026-09-03）只修了**讀取端**（`load_points(retries=True)`，Gate 0 預讀），
並在 `load_points` docstring 內明文記下：「`append_points()` 內部同樣呼叫 `_get_sheet()`
且同樣零重試 …… 寫入路徑的 `_get_sheet()` 零重試現況維持不變，留給後續任務視情況處理」。
**本檔即為該後續任務的守衛。**

為什麼寫入端一律重試、而讀取端是 opt-in（`retries=False` 預設）
--------------------------------------------------------------
兩者失敗的代價不對稱：
  · 讀取失敗 → **fail-soft**（`fund_service` 退回 live-only，下次 rerun 再讀，什麼都沒少）。
  · 寫入失敗 → 這張表 `(code, date)` 去重且**只增不減**，cron 隔天抓的是隔天的淨值、
    不會回頭補這一格 → **那一天的淨值永久缺一格**。
而且 P0 的呼叫點 `backfill_to_gs` **沒有傳任何旗標**，預設 `False` 的 opt-in 旗標
對這次事故等於沒修。取捨與代價逐條寫在 `append_points` 內的就地註解。

本檔釘住四件事，缺一不可
------------------------
  (1) `_get_sheet` 前兩次 5xx、第三次成功 → `append_points` **仍能完成**且真的寫進去；
  (2) 永久性錯誤（400 / 403 / 404 / 407 / 409 / 410 / 429 配額）→ **不重試、第一次就拋**
      —— 重試不得把永久性錯誤也吞掉重打；
      ⚠️ **2026-09-07 註**：本行原寫「400 / 403 / 429」，其中 **400 在寫下當時並不成立**
      —— 實作直到 2026-09-07 才真的讓 400 不重試（見下方 `test_known_gap_*` 的翻面記錄）。
      本次把清單補成與實作一致，並補上同型的 404 / 407 / 409 / 410。
  (3) 重試全部耗盡 → 仍然 raise 且**一列都沒寫**（不得因為加了重試就吞掉最終失敗）；
  (4) `_sheet=` 測試注入路徑**零行為變更**（不進重試、完全不碰 gspread）。

⚠️ **環境註記**：`(1)` 與 `(2)` 的 400/403/429 需要真的 `gspread.exceptions.APIError`
才能讓 `infra.gspread_retry.http_status_of` 取到狀態碼，故以 `importorskip` 保護
（本 repo CI 有 `gspread>=6.0.0`；無 gspread 的精簡環境會 skip 這幾條）。
其餘各條**不依賴 gspread**，任何環境都會實跑 —— 這是刻意的：連線層失敗
（無狀態碼 → `unreachable`）本來就是 `GSPREAD_RETRYABLE_KINDS` 的另一半，
且它讓「重試有沒有生效」在精簡環境也守得住。
"""
from __future__ import annotations

import pytest
import requests

from infra import gspread_retry as GR
from infra import source_backoff as SB

NAV_HEADERS = ["code", "date", "nav", "fund_name", "source", "recorded_at", "currency"]

# 退避節奏在測試中歸零：本檔量的是**重試次數與最終結果**，不是真的等 1+2+4 秒。
# ⚠️ **長度必須跟著真實排程走**（而不是寫死 4 個 0.0）：下面的「試滿幾次才放棄」
# 直接拿 `len(GR.DEFAULT_QUOTA_BACKOFFS)` 斷言，若哪天真實排程改成 5 拍而這裡寫死 4，
# 測試會吐出一個與程式無關的假紅燈。
_FAST = (0.0,) * len(GR.DEFAULT_QUOTA_BACKOFFS)


def _api_error(status: int, msg: str = "boom"):
    """造一個帶真實 HTTP 狀態碼的 gspread APIError（gspread 6.x 需要 Response）。
    做法與 `tests/test_nav_gate0_retry.py::_api_error` 相同（各檔自帶一份，
    本 repo 測試檔一律不互相 import）。"""
    gex = pytest.importorskip("gspread.exceptions")
    r = requests.Response()
    r.status_code = status
    r._content = ('{"error":{"code":%d,"message":"%s","status":"X"}}'
                  % (status, msg)).encode()
    return gex.APIError(r)


class _Transient(Exception):
    """無狀態碼的連線層失敗（逾時 / 連線被重設）。

    `kind_for_gspread_error` 對它回 `"unreachable"`，與 5xx 的 `"server_error"`
    同屬 `GSPREAD_RETRYABLE_KINDS` —— 這是**不依賴 gspread** 就能量到重試的那一半。"""


class _FakeWS:
    """夠用就好的假 worksheet：`col_count` / 表頭都已是最終形狀，
    好讓 `_ensure_grid_width` 與 `_get_worksheet` 的補表頭分支都 no-op ——
    本檔量的是**重試**，不是那兩件事（它們各有自己的守衛檔）。"""

    col_count = len(NAV_HEADERS)

    def __init__(self, appended):
        self._appended = appended

    def row_values(self, _n):
        return list(NAV_HEADERS)

    def get_all_values(self):
        return [list(NAV_HEADERS)]          # 只有表頭 → 沒有既有列可去重

    def append_rows(self, rows, **_kw):
        self._appended.extend(rows)


class _FakeSpreadsheet:
    def __init__(self, appended):
        self._appended = appended

    def worksheet(self, _name):
        return _FakeWS(self._appended)


class _FlakyClient:
    """`open_by_key` 前 `fail_times` 次拋 `exc_factory()`，之後每次成功。

    失敗點刻意選在 `open_by_key` —— 那正是 2026-08-31 / 09-02 兩班 cron 斷掉的位置，
    也是 `_get_sheet()` 唯一一次遠端往返。"""

    def __init__(self, appended, fail_times, exc_factory):
        self._appended = appended
        self._fail_times = fail_times
        self._exc_factory = exc_factory
        self.calls = 0

    def open_by_key(self, _k):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise self._exc_factory()
        return _FakeSpreadsheet(self._appended)


@pytest.fixture
def gs(monkeypatch):
    """接上假 SA 憑證，回 factory `make(fail_times, exc_factory) -> (client, appended)`。

    同 `tests/test_nav_gate0_retry.py::gs` 的精神；本檔改為可注入**任意例外工廠**，
    才能同時涵蓋「有狀態碼（400/403/429/500）」與「無狀態碼（連線層）」兩類。
    退避一併歸零，避免測試真的睡 7 秒。"""
    import infra.config as cfg
    import repositories.policy_repository as polrepo

    sa = {"client_email": "probe@x.iam.gserviceaccount.com"}
    orig = cfg.get_secret
    monkeypatch.setattr(
        cfg, "get_secret",
        lambda k, *a, **kw: (sa if k == "google_service_account" else orig(k, *a, **kw)))
    monkeypatch.setattr(cfg, "require_secret", lambda k: sa)

    # ⚠️ **不能用 `monkeypatch.setattr(GR, "DEFAULT_QUOTA_BACKOFFS", _FAST)`** ——
    # `with_gspread_retry(..., backoffs=DEFAULT_QUOTA_BACKOFFS)` 是**預設引數**，
    # 在 def 當下就綁死了，改模組屬性對它完全無效（初版就是這樣寫的，結果測試真的
    # 睡滿 7 秒、而「試滿 4 次」是靠 `len(_FAST)` 恰好等於真實排程長度才矇對）。
    # 改成包一層真正的 `with_gspread_retry`：**重試迴圈與分類邏輯全是真的**，
    # 只把 sleep 排程換成 0 —— 而且 `append_points` 是在函式內 lazy import 它，
    # 走的是 module attribute 查找，所以這個替換攔得到。
    _orig_retry = GR.with_gspread_retry
    monkeypatch.setattr(
        GR, "with_gspread_retry",
        lambda call, *a, **kw: _orig_retry(call, *a, **{**kw, "backoffs": _FAST}))

    def make(fail_times, exc_factory=_Transient):
        appended: list = []
        client = _FlakyClient(appended, fail_times, exc_factory)
        monkeypatch.setattr(polrepo, "get_gspread_client", lambda *a, **k: client)
        return client, appended

    return make


@pytest.fixture(autouse=True)
def _isolate_backoff():
    """每條測試前後清空跨呼叫冷卻狀態（`append_points` 成功時會呼叫
    `record_gspread_success`），避免互相污染。"""
    SB.reset_all()
    yield
    SB.reset_all()


def _one_point():
    return [{"code": "ALZF9", "nav": 12.34, "nav_date": "2026-09-07"}]


# ══════════════════════════════════════════════════════════════
# (1) 前兩次 5xx、第三次成功 → append_points 仍能完成
# ══════════════════════════════════════════════════════════════
def test_append_recovers_after_two_transient_5xx(gs):
    """派工單指名的核心情境：`_get_sheet` 前兩次拋 5xx、第三次成功
    → `append_points` 仍能完成，且那一列**真的寫進去**。

    ⚠️ 斷言「真的寫進去」而不只是回傳值 —— 回傳的 `written` 是算出來的，
    只看它會被一個「數對了但沒送出」的實作騙過。"""
    import services.nav_history_gs as NG

    client, appended = gs(2, lambda: _api_error(500))

    res = NG.append_points(_one_point())

    assert client.calls == 3, f"應重試到第 3 次才成功，實際 open_by_key {client.calls} 次"
    assert res["written"] == 1
    assert [r[0] for r in appended] == ["ALZF9"], f"那一列必須真的送到 append_rows，實際 {appended}"


def test_append_recovers_after_two_connection_level_failures(gs):
    """同 (1)，但用**無狀態碼**的連線層失敗（`unreachable`）——
    這條**不依賴 gspread**，精簡環境也會實跑，是本檔在無 gspread 時的重試守衛。"""
    import services.nav_history_gs as NG

    client, appended = gs(2, _Transient)

    res = NG.append_points(_one_point())

    assert client.calls == 3, f"應重試到第 3 次才成功，實際 open_by_key {client.calls} 次"
    assert res["written"] == 1
    assert [r[0] for r in appended] == ["ALZF9"]


def test_happy_path_makes_no_extra_call(gs):
    """正對照：**沒有失敗時不得多打一次** —— 證明重試包裝在成功路徑上零成本、
    也證明上面兩條的 `calls == 3` 不是「無條件打三次」造成的假陽性。"""
    import services.nav_history_gs as NG

    client, appended = gs(0, _Transient)

    res = NG.append_points(_one_point())

    assert client.calls == 1, f"成功路徑只該打一次，實際 {client.calls} 次"
    assert res["written"] == 1 and len(appended) == 1


# ══════════════════════════════════════════════════════════════
# (2) 永久性錯誤 → 不重試、第一次就拋
# ══════════════════════════════════════════════════════════════
@pytest.mark.parametrize("status", [400, 403, 404, 407, 409, 410, 429])
def test_append_does_not_retry_permanent_errors(gs, status):
    """⛔ 重試**不得**把永久性錯誤也吞掉重打。

    · 400 / 409 / 410 → 請求本身壞掉（400 正是 `exceeds grid limits` 的形狀），
      重打一百次還是同一個錯；
    · 403 → 權限／封鎖，秒級重試不會解除；
    · 404 / 407 → sheet_id 不存在／沒被分享、或 proxy 設定錯 —— 設定問題不會自癒；
    · 429 → `shared/backoff_policy.py` 對它的定性是「唯一一種『對方明確叫我們停』的
      失敗，繼續探測會延長封鎖窗口」—— 重試等於違反那個定性。

    全部必須第一次失敗就拋。
    ⚠️ 狀態碼是經 `NavHistoryError.__cause__` 鏈取得的（`_get_sheet` 會把底層例外
    包成 `NavHistoryError(...) from e`），這正是 `http_status_of` 走 cause 鏈的理由。

    ~~⚠️ **400 / 404 / 407 刻意不在這條的參數裡** —— 它們今天**會**被重試，
    見下一條 `test_known_gap_*`。~~
    ⚠️ **2026-09-07 政策變更（有意識的變更，不是漏刪 · 決策者：F30 修復組，依客戶
    2026-09-07「非 UI 的底層技術／模組修復一律內部自決」授權）**：該缺口已修
    （`infra/gspread_retry.py::is_transient_gspread_error`），400 / 404 / 407 依原
    作者在下一條留下的指示**加回本參數表**；順帶補上同型的 409 / 410
    （`kind_for_status` 對它們同樣回 `server_error`，修復前一樣會被重打 4 次）。
    """
    import services.nav_history_gs as NG

    client, appended = gs(999, lambda: _api_error(status))

    with pytest.raises(NG.NavHistoryError):
        NG.append_points(_one_point())

    assert client.calls == 1, (
        f"HTTP {status} 屬永久性/配額錯誤，不得重試；實際 open_by_key {client.calls} 次")
    assert appended == [], "失敗時不得寫入任何一列"


@pytest.mark.parametrize("status", [400, 404, 407])
def test_known_gap_non_transient_statuses_are_no_longer_retried(gs, status):
    """✅ **已修（2026-09-07）—— 這條從「釘現況」翻面成「釘應然」。**

    ⚠️ **有意識的政策變更，不是漏刪** · 日期 **2026-09-07** · 決策者：**F30 修復組**
    （依客戶 2026-09-07「非 UI 的底層技術／模組修復一律內部自決」授權）。
    **本條刻意保留、不刪除** —— 它是這三個狀態碼唯一的回歸守衛，
    刪掉等於把「曾經壞過」這件事一起刪掉。

    ~~**舊斷言（修復前的現況記錄）**：`client.calls == len(GR.DEFAULT_QUOTA_BACKOFFS)`
    —— 400 / 404 / 407 **會**被重試滿 4 次。~~
    **新斷言**：`client.calls == 1` —— 第一次失敗就拋。
    **2026-09-07 實測**：修復前 4 次 → 修復後 1 次（400 / 404 / 407 / 409 / 410 皆同）。

    ## 這條與上一條不重複：它釘的是**機制**，不只是次數

    修好這件事有兩條路，只有一條是對的：
      · ✅ **本次採用**：新增獨立的重試軸 `is_transient_gspread_error()`，
        **冷卻分類原封不動**；
      · ⛔ **看起來也會過、但是錯的**：去改 `kind_for_status` / `kind_for_gspread_error`
        讓 400 / 404 / 407 不再落在 `GSPREAD_RETRYABLE_KINDS` 裡 —— 那會把**冷卻長度**
        一起改掉（404 / 407 的 60s 冷卻是 `kind_for_gspread_error` 刻意改判來的，
        `tests/test_gspread_source_backoff.py` 有兩條在守它）。
    故本條**同時**斷言「冷卻分類沒被動到」與「重試軸說不該重試」，
    讓走錯那條路的人在**這裡**就轉紅，而不是去弄壞別的檔。

    ## 原始缺口記錄（保留，供追溯）

    下列三個狀態碼**今天會被重試**，而它們都不是暫時性抖動：

      · **400**（請求本身壞掉）→ `infra/source_backoff.py::kind_for_status(400)`
        回 `"server_error"`（該函式對 4xx 沒有與 5xx 分開），落進
        `GSPREAD_RETRYABLE_KINDS`。⚠️ 這正是本次 NAV 事故**第一根因**的形狀
        （`exceeds grid limits` 就是 400）—— 那種錯誤重打一百次還是 400。
      · **404 / 407** → `kind_for_gspread_error` 明文把它們改判成 `"unreachable"`，
        而 `"unreachable"` 也在 `GSPREAD_RETRYABLE_KINDS` 內。

    ⛔ **與已合併的文件直接矛盾**：`infra/gspread_retry.py::with_gspread_retry`
    的 docstring 寫著「非 `retry_kinds` 內的分類（429 / 403 / **404** / 407）
    **第一次失敗就直接拋出，不重試**」—— 實測 404 / 407 **會**重試。

    **為什麼本批不修**：根因在 `infra/source_backoff.py` 與 `infra/gspread_retry.py`，
    **不在本批的檔案邊界內**（本批只准動 `services/nav_history_gs.py` 與本測試檔）；
    而且這個行為**不是本次改動引入的** —— 2026-09-03 `abba317` 已合併的
    `load_points(retries=True)`（Gate 0 讀取）走的是**同一個** `with_gspread_retry`，
    今天在 production 就是這個分類。本次只是把同一套行為對稱地帶到寫入路徑。
    已於本批 PR 描述具名回報為提案，**未動手**。

    ~~**這條測試的用途**：當有人真的去修 `kind_for_status` / `GSPREAD_RETRYABLE_KINDS`
    時，本條會**轉紅**，逼他回來把預期改掉（並順手把上一條的參數表補回 400/404/407）
    —— 而不是讓這個缺口悄悄地被修掉或悄悄地繼續存在。~~
    → **2026-09-07：該事件已發生，本條照原作者的指示轉向** —— 上一條的參數表已補回
    400 / 404 / 407（另加同型的 409 / 410）；本條依客戶「不得刪除該測試」的指示
    **保留並翻面**，改守機制。
    """
    import services.nav_history_gs as NG

    client, appended = gs(999, lambda: _api_error(status))

    with pytest.raises(NG.NavHistoryError):
        NG.append_points(_one_point())

    assert client.calls == 1, (
        f"HTTP {status} 不是暫時性抖動，必須第一次失敗就拋；實際 open_by_key "
        f"{client.calls} 次（修復前是 {len(GR.DEFAULT_QUOTA_BACKOFFS)} 次）")
    assert appended == [], "不論重試幾次，失敗時都不得寫入任何一列"

    # ── 機制斷言：修對的路只有一條 ──────────────────────────────────────
    exc = _api_error(status)
    assert GR.kind_for_gspread_error(exc) in GR.GSPREAD_RETRYABLE_KINDS, (
        f"HTTP {status} 的**冷卻分類**必須維持原樣（仍落在 GSPREAD_RETRYABLE_KINDS "
        f"裡）—— 若這裡轉紅，代表有人是靠改冷卻分類來『修』重試，"
        f"那會連 404/407 的 60s 冷卻一起改掉，見 tests/test_gspread_source_backoff.py")
    assert GR.is_transient_gspread_error(exc) is False, (
        f"HTTP {status} 必須被**重試軸**判為非暫時性")


# ══════════════════════════════════════════════════════════════
# (3) 重試耗盡 → 仍然 raise，且一列都沒寫
# ══════════════════════════════════════════════════════════════
def test_append_exhausted_still_raises_and_writes_nothing(gs):
    """§1 fail-loud 守衛：全部重試用完仍失敗 → 仍然 raise `NavHistoryError`，
    且**一列都沒寫**。不得因為加了重試就把最終失敗吞成「成功」。"""
    import services.nav_history_gs as NG

    client, appended = gs(999, _Transient)

    with pytest.raises(NG.NavHistoryError):
        NG.append_points(_one_point())

    n = len(GR.DEFAULT_QUOTA_BACKOFFS)
    assert client.calls == n, f"應試滿 {n} 次才放棄（DEFAULT_QUOTA_BACKOFFS），實際 {client.calls} 次"
    assert appended == [], "最終失敗時不得留下任何半寫入的列"


# ══════════════════════════════════════════════════════════════
# (4) `_sheet=` 注入路徑零行為變更
# ══════════════════════════════════════════════════════════════
def test_injected_sheet_path_is_unchanged(monkeypatch):
    """`_sheet=`（測試注入）不進重試包裝、完全不碰 gspread —— 既有大量測試走這條路，
    必須零行為變更。用「`_get_sheet` 一旦被呼叫就炸」來釘死它真的沒被走到。"""
    import services.nav_history_gs as NG

    def _boom(*_a, **_kw):
        raise AssertionError("_sheet 注入路徑不得呼叫 _get_sheet()")

    monkeypatch.setattr(NG, "_get_sheet", _boom)

    appended: list = []
    res = NG.append_points(_one_point(), _sheet=_FakeSpreadsheet(appended))

    assert res["written"] == 1
    assert [r[0] for r in appended] == ["ALZF9"]
