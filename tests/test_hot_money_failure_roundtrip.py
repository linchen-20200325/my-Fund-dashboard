# -*- coding: utf-8 -*-
"""行為往返測試：熱錢 fetcher 的失敗**不入** `@st.cache_data`，且應用層失敗會登記來源退避。

## 為什麼非要有這一檔（它補的是一個結構性的缺口）

同目錄的 `test_st_cache_failure_not_cached.py` 是**純 AST 形態守衛** —— 它只問
「這個 `def` 裡有沒有一個 `raise` 節點」，**不問可達性、不問那個 raise 長在不在失敗路徑上**。
2026-09-01 稽核用突變測試打穿了它：

    M2b：把真實失敗路徑全部改回 `return (空 df, err)`，只塞一個
         `if days < 0: raise ValueError("unreachable")` → 那 11 條 AST 守衛 **全數綠燈**。

那正是憲法 §-2 規則 6 創始實證的同一個病（宣稱修好、實際是死碼、production 恆不觸發）——
**而它當時長在專門用來防這個病的守衛裡**。本檔用「**數上游到底跑了幾次**」把它釘死。

## ⚠️ 必須在**真 streamlit** 下跑，否則整檔是空轉

`conftest.py::_stub_cache_decorator` 是 **pass-through** —— stub 底下根本沒有快取，
修好前與修好後表現完全一樣，**結構上不可能證明或證偽這個修復**。
故本檔開頭有一道環境守衛（`_require_real_streamlit`），環境不對就**紅燈**，不是靜默通過。
另外附一條 **positive control**（成功結果必須真的被快取）—— 少了它，
「失敗跑了 3 次」也可能只是因為這個環境的快取根本沒生效。

## 量測手法

- **上游網路呼叫數**：monkeypatch `infra.proxy._get_thread_session`，數 `sess.get` 次數。
  走真的 `fetch_url`，所以連 `infra.source_backoff` 的進場跳過都一起量到。
- **未快取實作的執行數**：包一層 counter 在
  `repositories.hot_money_repository._fetch_foreign_flow_series_uncached` 上。
  **這一項才是分辨「沒被快取」與「被退避擋住」的關鍵** —— 兩者的網路呼叫數都是 0，
  只有實作執行數會分開（沒被快取 = 每次 rerun 都真的跑一次實作）。
"""
from __future__ import annotations

import json

import pytest

import repositories.hot_money_repository as hm
from infra import proxy as _proxy
from infra import source_backoff as _sb


# ════════════════════════════════════════════════════════════════════
# 環境守衛 + 假上游
# ════════════════════════════════════════════════════════════════════
def _require_real_streamlit() -> None:
    """本檔在 stub 下毫無鑑別力 —— 環境不對就紅燈，不靜默通過。

    ⚠️ 檢查的是 **`hm` 模組自己綁到的那個 `st`**，不是 `sys.modules["streamlit"]`：
    模組的 global 在 import 當下就綁定了，`conftest` 事後換 `sys.modules` 不會改到它。
    """
    assert not getattr(hm.st, "_is_test_stub", False), (
        "repositories.hot_money_repository 綁到的是 streamlit stub —— "
        "stub 的 cache_data 是 pass-through，本檔在其下無鑑別力（會假綠）。"
    )
    assert hasattr(hm._cached_foreign_flow_series, "clear"), (
        "_cached_foreign_flow_series 沒有 .clear() —— 這一層不是真的 @st.cache_data。"
    )


class _FakeResp:
    def __init__(self, status: int, body: bytes):
        self.status_code = status
        self.content = body
        self._text = body.decode("utf-8", "replace")
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"

    @property
    def text(self) -> str:
        return self._text

    def json(self):
        return json.loads(self._text)


# 情境 → (HTTP 狀態碼, body)
_SCENARIOS: dict[str, tuple[int, bytes]] = {
    # 應用層失敗（全部是 HTTP 200 —— 這正是 fetch_url 看不到、會誤判成成功的那一類）
    "quota_402":  (200, b'{"msg": "Requests reached the upper limit.", "status": 402}'),
    "bad_json":   (200, b'<html>502 bad gateway</html>'),
    "no_name_col": (200, b'{"status": 200, "data": [{"date": "2026-08-03", "buy": 1, "sell": 2}]}'),
    "empty_data": (200, b'{"status": 200, "data": []}'),
    "no_foreign": (
        200,
        b'{"status": 200, "data": [{"date": "2026-08-03", "name": "Dealer_self",'
        b' "buy": 1, "sell": 2}]}',
    ),
    # 傳輸層失敗（對照組：fetch_url 自己就會登記退避）
    "http_500":   (500, b'{"err": "boom"}'),
    # SSOT 判定「刻意不退避」的分類 → 這一層若還 raise 就一個節流器都不剩
    "body_404":   (200, b'{"msg": "dataset not found", "status": 404}'),
    # positive control：成功
    "ok": (
        200,
        b'{"status": 200, "data": ['
        b'{"date": "2026-08-01", "name": "Foreign_Investor", "buy": 300000000, "sell": 100000000},'
        b'{"date": "2026-08-04", "name": "Foreign_Investor", "buy": 100000000, "sell": 300000000}'
        b']}',
    ),
}


@pytest.fixture
def harness(monkeypatch):
    """裝上假 session + 兩個計數器，回傳 (run, net, impl)。"""
    _require_real_streamlit()

    net = {"n": 0}
    impl = {"n": 0}
    state = {"scenario": "ok"}

    class _FakeSession:
        def get(self, url, **kw):
            net["n"] += 1
            status, body = _SCENARIOS[state["scenario"]]
            return _FakeResp(status, body)

    monkeypatch.setattr(_proxy, "_get_thread_session", lambda: _FakeSession())
    monkeypatch.setattr(_proxy, "get_proxy_config", lambda: None)
    # 5xx 情境內部會 sleep 重試 —— 測試不等
    monkeypatch.setattr(_proxy._t if hasattr(_proxy, "_t") else __import__("time"),
                        "sleep", lambda *a, **k: None, raising=False)

    _orig_impl = hm._fetch_foreign_flow_series_uncached

    def _counting_impl(*a, **k):
        impl["n"] += 1
        return _orig_impl(*a, **k)

    monkeypatch.setattr(hm, "_fetch_foreign_flow_series_uncached", _counting_impl)

    def run(scenario: str, days: int, reruns: int = 3):
        """跑 `reruns` 次 `fetch_foreign_flow_series(days)`，回傳**每一次**的 (df, err)。

        ⚠️ 刻意回傳整串而不是最後一次：第 2 次起會被退避在 `fetch_url` 進場處擋下，
        訊息換成「來源退避冷卻中」——**第一次**那個才是真正的失敗原因，
        對錯誤訊息的斷言必須打在 `results[0]` 上。
        """
        state["scenario"] = scenario
        hm.fetch_foreign_flow_series.clear()
        _sb.reset_all()
        net["n"] = 0
        impl["n"] = 0
        return [hm.fetch_foreign_flow_series(days) for _ in range(reruns)]

    yield run, net, impl

    hm.fetch_foreign_flow_series.clear()
    _sb.reset_all()


# ════════════════════════════════════════════════════════════════════
# positive control：先證明這個環境的快取是活的
# ════════════════════════════════════════════════════════════════════
def test_success_is_cached_positive_control(harness):
    """成功結果**必須**被快取（3 次 rerun 只跑一次實作）。

    ⚠️ 這一條是下面所有「失敗跑了 3 次」斷言的前提：
    少了它，`impl == 3` 也可能只是因為這個環境的 `@st.cache_data` 根本沒生效。
    """
    run, net, impl = harness
    df, err = run("ok", days=101)[0]
    assert err == "", f"positive control 不該失敗：{err!r}"
    assert not df.empty
    assert impl["n"] == 1, f"成功結果沒有被快取（實作跑了 {impl['n']} 次，預期 1）"
    assert net["n"] == 1, f"成功結果沒有被快取（上游打了 {net['n']} 次，預期 1）"


# ════════════════════════════════════════════════════════════════════
# ⭐ 主力：應用層失敗（HTTP 200）不入快取 + 有登記來源退避
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "scenario, days, err_needle",
    [
        ("quota_402",   111, "402"),
        ("bad_json",    112, "JSON 解析失敗"),
        ("no_name_col", 113, "缺類別欄"),
        ("empty_data",  114, "0 筆資料"),
        ("no_foreign",  115, "無 Foreign 類別資料"),
    ],
)
def test_app_level_failure_is_not_cached_and_registers_backoff(
        harness, scenario, days, err_needle):
    """⭐ 突變測試打在這一條。

    兩個斷言缺一不可：

    - `impl == 3` —— 失敗**沒有**被 `@st.cache_data` 存下來（每次 rerun 都真的重跑實作）。
      **這一條就是 M2b 的照妖鏡**：把真實失敗路徑改回 `return`、只留一個不可達的 raise，
      實作的回傳值就會被快取 → `impl` 掉回 1 → 本條紅燈。
    - 退避有登記 —— 這些失敗全是 **HTTP 200**，`infra/proxy.py::fetch_url` 一看到 200 就
      `_note_success()` 解除冷卻；少了本檔在應用層補記的那一筆，「不快取」就等於
      **每次 rerun 都真的打一次上游**（v3 §02「失敗時退避，不連續轟炸來源」）。
    """
    run, net, impl = harness
    results = run(scenario, days=days)
    df, err = results[0]

    assert df.empty, f"{scenario}: 失敗路徑不該回非空 df"
    assert err, f"{scenario}: 失敗路徑必須帶 err 字串"

    assert impl["n"] == 3, (
        f"{scenario}: 失敗被快取了 —— 3 次 rerun 只跑了 {impl['n']} 次實作。"
        f"（@st.cache_data 只對『回傳值』快取，失敗必須 raise 才穿得過去）"
    )

    live = [d for d in _sb.get_backoff_state() if d["source"] == "api.finmindtrade.com"]
    assert live, (
        f"{scenario}: 應用層失敗沒有登記來源退避 —— "
        f"這是 HTTP 200，fetch_url 已經 _note_success() 解除冷卻了，"
        f"不補記就會每次 rerun 真打一次上游。目前 state={_sb.get_backoff_state()}"
    )

    # 第一次真的打了；第 2/3 次被退避在 fetch_url 進場處擋下 → 不再有網路往返
    assert net["n"] == 1, (
        f"{scenario}: 退避沒有生效 —— 3 次 rerun 打了 {net['n']} 次上游（預期 1）"
    )

    assert err_needle in err, f"{scenario}: 錯誤訊息應包含 {err_needle!r}，實際：{err!r}"

    # 第 2/3 次是「退避冷卻中」，措辭必須誠實地說出「沒有發請求」，
    # 不得沿用舊句「全部重試失敗」（那在冷卻期內是假的，§1）。
    _later_err = results[-1][1]
    assert "退避冷卻中" in _later_err and "未發出任何請求" in _later_err, (
        f"{scenario}: 冷卻期的訊息未誠實交代「本次沒有打上游」：{_later_err!r}"
    )


def test_empty_data_is_not_blamed_on_holidays(harness):
    """`data: []` 不得再被說成「非交易日區間」。

    查詢視窗是 `days + 14`，production 的 days 來自 60~365 的 slider
    → 視窗恆 ≥ 74 天，**台灣沒有 74 天的連假**。舊訊息在唯一會發生的情境下是錯的歸因。
    """
    run, _net, _impl = harness
    _df, err = run("empty_data", days=116)[0]
    assert "非交易日" not in err, f"上游異常被誤報成休市：{err!r}"
    assert "130" in err, f"訊息應帶出實際視窗天數（116+14=130），實際：{err!r}"


# ════════════════════════════════════════════════════════════════════
# 對照組
# ════════════════════════════════════════════════════════════════════
def test_transport_failure_backoff_is_left_to_fetch_url(harness):
    """真 HTTP 5xx：`fetch_url` 自己會登記；本檔**不**重複記（不覆蓋 SSOT 的分類）。"""
    run, net, impl = harness
    df, err = run("http_500", days=117)[0]
    assert df.empty and err
    assert impl["n"] == 3, f"傳輸層失敗也不該被快取（實作跑了 {impl['n']} 次）"
    live = [d for d in _sb.get_backoff_state() if d["source"] == "api.finmindtrade.com"]
    assert live and live[0]["fails"] == 1, (
        f"應恰好登記 1 次（由 fetch_url 記，本檔不重複記）：{live}"
    )


def test_no_cooldown_kind_falls_back_to_caching(harness):
    """body status 落在 `NO_COOLDOWN_KINDS`（404 / 407）→ **照舊快取**，不 raise。

    SSOT（`shared/backoff_policy.py`）明訂這兩種**刻意不退避**；此時若還 raise，
    就一個節流器都不剩、每次 rerun 真打一次。判斷與
    `repositories/macro/yf.py` 對 404/407 的既有處置同源。
    """
    run, net, impl = harness
    df, err = run("body_404", days=118)[0]
    assert df.empty and "404" in err
    assert impl["n"] == 1, f"不退避的分類必須由 TTL 承擔節流（實作跑了 {impl['n']} 次）"
    assert net["n"] == 1
    assert not [d for d in _sb.get_backoff_state()
                if d["source"] == "api.finmindtrade.com"], "not_found 不該進退避"


def test_empty_frames_carry_real_dtypes(harness):
    """失敗回傳的空 df 帶正確 dtype（datetime64 / float64），不是 object。

    改版前 base 自己就不一致（一條 object、一條 typed）；本 PR 統一。
    現行消費端都先判 `.empty`，實務影響為零 —— 但「回傳形狀逐字相同」要為真就不能留差異。
    """
    run, _net, _impl = harness
    df, _err = run("quota_402", days=119)[0]
    assert str(df["date"].dtype) == "datetime64[ns]", df.dtypes.to_dict()
    assert str(df["foreign_net_yi"].dtype) == "float64", df.dtypes.to_dict()
