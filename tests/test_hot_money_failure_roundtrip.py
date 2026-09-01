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
    # body status 是 **2xx/3xx** → `kind_for_status` 回 `""`（SSOT 的「這不是失敗」哨符），
    # 而 `cooldown_for("")` 走 default 60s > 0 —— 若不接住哨符就會登記一筆 kind 為空的退避
    "body_201":   (200, b'{"msg": "created", "status": 201}'),
    # HTTP 200 但 body 是空白 → `fund_fetcher.fetch_url_with_retry` 尾端
    # `return resp if resp.text.strip() else None` 會把它轉成 None，
    # 而 `fetch_url` 早已 `_note_success()` → **誰都沒有記退避**（同 body_404 的處境）
    "http_200_empty_body": (200, b'   '),
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

        ⚠️ 刻意回傳整串而不是最後一次：第 2 次起會被退避擋下、訊息換掉，
        **第一次**那個才是真正的失敗原因，對錯誤訊息的斷言必須打在 `results[0]` 上。

        ⚠️ **2026-09-01 第三輪更正（有意識的更正，不是漏刪 · 決策者：本修復組）**：
        本段原寫 ~~「被退避在 **`fetch_url` 進場處**擋下，訊息換成「**來源**退避冷卻中」」~~
        —— **兩句都是 `7a45c89` 自己弄假的**。它們在 `fe664ad`（退避鍵還是 host 粒度）
        為真；`7a45c89` 把鍵縮成 dataset 之後，`fetch_url` **只查 host 鍵、查不到它**
        （那正是 `7a45c89` 在 `repositories/hot_money_repository.py` 檔頭與
        `_fetch_foreign_flow_series_uncached` docstring 裡**親手劃掉**的同一句話）。

        **實測（同一支探針，在 `should_skip` 上掛 tracer）**：

            rerun#1  should_skip: [(dataset, False), (host, False)]   net=1
            rerun#2  should_skip: [(dataset, True)]                   net=1  ← host 那支根本沒被問
            err#2 = "FinMind TaiwanStockTotalInstitutionalInvestors 退避冷卻中（…）"

        **現行事實**：攔截點是 `_fetch_foreign_flow_series_uncached` **開頭**的
        `should_skip(_FINMIND_DATASET_KEY)`；訊息是 **dataset 變體**
        （帶 dataset 名，不是「來源退避冷卻中」——那是 `r is None` 那一支才會出現的變體）。

        ⛔ **根因比這兩行重要，寫在這裡免得下一輪再犯**：`7a45c89` 的 PR 描述
        列了兩條掃描指令去掃五個載體，**但兩條的字表不一樣** ——
        非 tests 那條有 `進場處`，tests 這條**沒有**。於是「更正措辭時只修被點名的那個載體」
        這條教訓，**在照著它做的那一輪、以另一個維度（載體之間字表不同）再發生一次**。
        → **同一次更正必須用同一份字表掃全部五個載體**，字表本身也要是同一份。
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

    _states = _sb.get_backoff_state()
    live = [d for d in _states if d["source"] == hm._FINMIND_DATASET_KEY]
    assert live, (
        f"{scenario}: 應用層失敗沒有登記退避 —— "
        f"這是 HTTP 200，fetch_url 已經 _note_success() 解除冷卻了，"
        f"不補記就會每次 rerun 真打一次上游。目前 state={_states}"
    )
    # ⭐ 反向鎖（2026-09-01 第二輪的核心迴歸）：**不得**登記到 host 鍵上。
    # host 鍵一被寫進去，`infra/proxy.py::fetch_url` 就會把同一個 host 上
    # 完全健康的其它 dataset 一起擋掉 —— 實測誤殺 NDC 景氣對策信號
    # （`ui/helpers/macro/ndc.py`，Tab1 資產水位 / 動態 Z 門檻 + Tab2 再平衡訊號）。
    # 跨 dataset 的端對端證明另見 `test_sibling_dataset_on_same_host_is_untouched`。
    assert not [d for d in _states if d["source"] == hm._FINMIND_HOST_KEY], (
        f"{scenario}: dataset 專屬的 payload 失敗被登記到 host 鍵 "
        f"{hm._FINMIND_HOST_KEY!r} —— 會誤殺同 host 的其它 dataset。state={_states}"
    )

    # 第一次真的打了；第 2/3 次被退避擋下 → 不再有網路往返。
    # ⚠️ 2026-09-01 第三輪更正：原註寫「被退避在 **fetch_url 進場處**擋下」——
    #    退避鍵自 `7a45c89` 起是 dataset 粒度，而 `fetch_url` 只查 host 鍵；
    #    實測 rerun#2 只問了 dataset 鍵一次，**host 那支根本沒被問到**。
    #    真正的攔截點是 `_fetch_foreign_flow_series_uncached` 開頭的 `should_skip`。
    #    （這一行與 `harness::run` 的 docstring 是同一句話的兩個副本，一起改。）
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
    # 冷卻訊息要講清楚**冷卻的是誰**（不是整個來源）——否則讀 log 的人會以為
    # FinMind 整台被關掉，然後去找一個不存在的 host 冷卻。
    assert hm._FINMIND_DATASET in _later_err, (
        f"{scenario}: 冷卻訊息未指出是哪一個 dataset 在冷卻：{_later_err!r}"
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
# ⭐ 跨 dataset 隔離：同一個 host 上的鄰居不得被連坐
# ════════════════════════════════════════════════════════════════════
def test_sibling_dataset_on_same_host_is_untouched(monkeypatch):
    """外資 dataset 壞掉，**不得**害到同一個 host 上健康的 NDC 景氣對策信號。

    ## 這一條是 `fe664ad` 迴歸的端對端證明（2026-09-01 第二輪，兩組獨立稽核指出）

    第一版把 payload 形狀失敗登記在 **host 鍵**（`api.finmindtrade.com`）上，
    於是 `infra/proxy.py::fetch_url` 在進場處把**同一個 host 的所有查詢**一起擋掉。
    實測（只讓外資 dataset 壞、NDC dataset 全程健康）：

        b5b0464 / bf9ddc2 : NDC score=31，TaiwanBusinessIndicator 打上游 1 次
        fe664ad           : NDC score=None，打上游 0 次
                            [proxy] 退避中，跳過不打（source=api.finmindtrade.com）

    NDC 是**活的 production 消費者**（`ui/helpers/macro/ndc.py::_fetch_ndc_score`
    → Tab1 資產水位 / 動態 Z 門檻、Tab2 再平衡訊號），拿不到分數就退預設門檻。

    ## 為什麼不能只靠上面那條反向鎖

    `test_app_level_failure_is_not_cached_and_registers_backoff` 的反向鎖只證明
    「沒有寫進 host 鍵」；本條證明的是**下游真的還拿得到資料** ——
    中間還隔著 `fetch_url` 的進場檢查、`_ttl_cache`、以及 NDC 自己的解析。
    只鎖登記表、不驗端對端，等於相信「鍵沒寫錯 ⇒ 行為就對了」。
    """
    _require_real_streamlit()
    import repositories.macro_tw_local_repository as _tw

    _ndc_body = json.dumps({"status": 200, "data": [
        {"date": f"2026-{m:02d}-01", "monitoring": 29 + (m % 3),
         "monitoring_color": "綠燈", "leading": 100.0} for m in range(1, 9)
    ]}).encode()

    seen: dict[str, int] = {}

    class _DispatchSession:
        def get(self, url, **kw):
            _ds = (kw.get("params") or {}).get("dataset", "?")
            seen[_ds] = seen.get(_ds, 0) + 1
            if _ds == "TaiwanBusinessIndicator":            # 鄰居：完全健康
                return _FakeResp(200, _ndc_body)
            return _FakeResp(*_SCENARIOS["quota_402"])      # 外資：壞掉

    monkeypatch.setattr(_proxy, "_get_thread_session", lambda: _DispatchSession())
    monkeypatch.setattr(_proxy, "get_proxy_config", lambda: None)

    hm.fetch_foreign_flow_series.clear()
    _tw.fetch_ndc_signal_history.cache_clear()
    _sb.reset_all()
    try:
        _df, _err = hm.fetch_foreign_flow_series(122)
        assert _df.empty and "402" in _err, f"前置條件沒成立（外資該壞）：{_err!r}"

        _ndc = _tw.fetch_ndc_signal_history(token="")
        assert seen.get("TaiwanBusinessIndicator") == 1, (
            f"NDC 的查詢被擋掉了，一個封包都沒發出去 —— 退避鍵誤殺鄰居。"
            f"實際上游呼叫：{seen}；退避狀態：{_sb.get_backoff_state()}"
        )
        assert _ndc.get("score_latest") is not None, (
            f"NDC 拿不到分數（error={_ndc.get('error')!r}）—— "
            f"退避狀態：{_sb.get_backoff_state()}"
        )
    finally:
        hm.fetch_foreign_flow_series.clear()
        _tw.fetch_ndc_signal_history.cache_clear()
        _sb.reset_all()


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


def test_http_200_empty_body_falls_back_to_caching(harness):
    """HTTP 200 但 body 空 → `fetch_url` 判定成功、沒人記退避 → **必須落回快取**。

    ## 這一條擋的是本 PR 自己製造過的迴歸（2026-09-01 第二輪實測）

    `fe664ad` 在這個情境下是 **rerun#1..#3 各打一次上游**（實測 total=3），
    而改版前（`b5b0464`）是 **1**（失敗被 `@st.cache_data` 鎖 30 分鐘）。
    也就是說：一個以「不要連續轟炸來源」為題的 PR，在這條路徑上**把請求量放大了 3 倍**。

    根因是本檔的節流不變式漏了一格：失敗**只有在確實有節流器時才可以 raise**。
    這裡三個節流器都不在（dataset 沒登記、host 被 `_note_success` 清掉、
    raise 又穿過快取），所以唯一正確的做法是 `return`，讓 `TTL_30MIN` 接手。
    """
    run, net, impl = harness
    df, err = run("http_200_empty_body", days=120)[0]
    assert df.empty and err
    assert impl["n"] == 1, (
        f"沒有節流器的失敗必須落回快取（實作跑了 {impl['n']} 次，預期 1）—— "
        f"否則每次 rerun 都真打一次上游，比改版前更糟"
    )
    assert net["n"] == 1, f"3 次 rerun 打了 {net['n']} 次上游（預期 1）"
    assert not _sb.get_backoff_state(), f"這一支不該登記任何退避：{_sb.get_backoff_state()}"


def test_backoff_expiry_lets_the_chain_retry(harness, monkeypatch):
    """冷卻期滿後**這條鏈**要真的重試 —— 退避不可讓資料永久消失（§1 對偶）。

    ⚠️ `tests/test_source_backoff.py` 驗的是**模組**的到期行為；本條驗的是
    **熱錢這條鏈**接上去之後到期會不會真的重打（進場處的 `should_skip` 有沒有接對）。
    兩者不可互相取代：模組對了但鏈沒接，一樣是永久黑掉。
    """
    run, net, impl = harness
    _t = {"now": 1000.0}
    monkeypatch.setattr(_sb, "_clock", lambda: _t["now"])

    results = run("quota_402", days=121, reruns=2)
    assert net["n"] == 1, f"冷卻期內仍在打上游：{net['n']}"
    assert "退避冷卻中" in results[-1][1]

    # 跳過整個冷卻期（server_error = 300s，取 +1 秒確保過期）
    _cd = _sb.get_backoff_state()
    assert _cd and _cd[0]["cooldown_sec"] > 0, _cd
    _t["now"] += _cd[0]["cooldown_sec"] + 1

    _before = net["n"]
    _df, _err = hm.fetch_foreign_flow_series(121)
    assert net["n"] == _before + 1, (
        f"冷卻期滿後沒有重試（上游呼叫數停在 {net['n']}）—— 退避把資料永久藏起來了"
    )
    assert "退避冷卻中" not in _err, f"冷卻已到期，訊息卻仍說在冷卻：{_err!r}"


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
    assert not _sb.get_backoff_state(), (
        f"not_found 不該進退避（host 或 dataset 都不該）：{_sb.get_backoff_state()}"
    )


def test_ssot_non_failure_status_is_not_registered_as_backoff(harness):
    """body status 是 **2xx/3xx** → `kind_for_status` 回 `""`（「這不是失敗」的哨符）。

    ## 這一條擋的是 `7a45c89` 上活著的一個 bug（2026-09-01 第三輪稽核指出）

    `infra/source_backoff.py::kind_for_status` 對 2xx/3xx **回空字串**，
    就地註解寫著 `return ""   # 2xx/3xx 不是失敗`。但 `cooldown_for("")` 走的是
    「**未知 kind 從寬**」的 default（實測 **60**），於是舊寫法只判
    `cooldown_for(_kind) <= 0` 時**會照樣退避**，並 `record_failure(key, "")`。

    **`7a45c89` 實跑**（body `{"status":201}`，3 次 rerun）：

        backoff: [{'source': 'finmind-dataset:…', 'kind': '', 'cooldown_sec': 60, …}]
        err#3  : "FinMind … 退避冷卻中（前次失敗分類 ，剩餘約 60 秒）"   ← 分類欄是空的

    本檔自陳「分類走 SSOT，不自己另立對照表」，**卻沒有接住 SSOT 的哨符** ——
    抄了對照表卻沒抄它的語意。突變：把 `not _kind or` 拿掉 → 本條轉紅。
    """
    run, net, impl = harness
    df, err = run("body_201", days=123)[0]
    assert df.empty and "201" in err
    assert not _sb.get_backoff_state(), (
        f"2xx/3xx 是 SSOT 的「非失敗」哨符，不得登記成退避（尤其不得登記成空分類）："
        f"{_sb.get_backoff_state()}"
    )
    assert impl["n"] == 1, (
        f"沒有節流器的失敗必須落回快取（實作跑了 {impl['n']} 次，預期 1）"
    )
    assert net["n"] == 1, f"3 次 rerun 打了 {net['n']} 次上游（預期 1）"
    # 使用者不該看到「前次失敗分類 （空白）」這種訊息
    assert "退避冷卻中" not in err, f"不該進退避卻顯示了冷卻訊息：{err!r}"


def test_usdtwd_schema_violation_falls_back_to_caching(monkeypatch):
    """⭐ Yahoo 回 **HTTP 200 + 畸形 payload** → `validate_yf_close` 拋 SchemaError。

    ## 這一條擋的是 `7a45c89` 仍然帶著的一個**可達**迴歸（第三輪稽核指出）

    節流不變式：**失敗只在確實有節流器時才 raise**。這一支三個節流器都沒有：

    - `repositories/macro/yf.py::fetch_yf_close` 的 `validate_yf_close(s)`
      **刻意放在 parse 的 try-except 之外**（該檔就地註明：schema 違反是上游 bug，
      須當場 raise）→ 例外冒泡；
    - 它的 `@_ttl_cache` **不存例外** → 擋不住；
    - `fetch_url` 看到 HTTP 200 已 `_note_success()` → **沒有 host 冷卻**；
    - `_fetch_usdtwd_series_uncached` 若在這裡 raise，又穿過 `@st.cache_data`
      → **連 TTL 都沒有** → **每次 rerun 真打一次 Yahoo**。

    **實測（同一支探針，3 次 rerun 的每輪 `sess.get` 增量）**：

        b5b0464(base) [1, 0, 0]      ← 失敗被快取，10 分鐘才打一次
        fe664ad       [1, 1, 1]  ⛔
        7a45c89       [1, 1, 1]  ⛔   ← 第二輪修了外資那側，這一側漏了
        本輪          [1, 0, 0]  ✅

    ⚠️ **為什麼上一輪沒抓到**：它實測的 `yfnull` / `yfempty` / `http500`
    **三種都是「回值」**，剛好全部避開了唯一會 **raise** 的那一種；
    而該檔的辯護詞「上游 `fetch_yf_close` 已有自己的節流器」
    **正好對這一支不成立** —— `_ttl_cache` 唯一擋不住的就是例外。

    突變：把 `_fetch_usdtwd_series_uncached` 的 `except` 分支改回
    `raise _FetchFailed(...)` → 本條轉紅（`net` 由 1 變 3）。
    """
    _require_real_streamlit()
    import repositories.macro.yf as _yf

    # Yahoo Chart 200，但 close 全 <= 0 → YahooCloseSchema 契約違反 → SchemaError
    _bad = json.dumps({"chart": {"result": [{
        "timestamp": [1767225600, 1767312000],
        "indicators": {"quote": [{"close": [-1.0, -2.0]}]},
    }]}}).encode()

    net = {"n": 0}

    class _S:
        def get(self, url, **kw):
            net["n"] += 1
            return _FakeResp(200, _bad)

    monkeypatch.setattr(_proxy, "_get_thread_session", lambda: _S())
    monkeypatch.setattr(_proxy, "get_proxy_config", lambda: None)

    _yf.fetch_yf_close.cache_clear()
    hm.fetch_usdtwd_series.clear()
    _sb.reset_all()
    try:
        per_rerun = []
        for _ in range(3):
            _before = net["n"]
            df, err = hm.fetch_usdtwd_series(30)
            per_rerun.append(net["n"] - _before)

        assert df.empty and err, f"schema 違反必須誠實回報失敗：{err!r}"
        assert "抓取失敗" in err, f"訊息應保留上游原因：{err!r}"
        assert per_rerun == [1, 0, 0], (
            f"沒有節流器的失敗必須落回快取，實測每輪上游呼叫 {per_rerun}（預期 [1, 0, 0]）"
            f" —— [1, 1, 1] 代表每次 rerun 都真打一次 Yahoo，比改版前更糟"
        )
        assert not _sb.get_backoff_state(), (
            f"本支不登記來源冷卻（會把 VIX/DGS10/DXY/SPY 一起鎖住）："
            f"{_sb.get_backoff_state()}"
        )
    finally:
        _yf.fetch_yf_close.cache_clear()
        hm.fetch_usdtwd_series.clear()
        _sb.reset_all()


def test_empty_frames_carry_real_dtypes(harness):
    """失敗回傳的空 df 帶正確 dtype（datetime64 / float64），不是 object。

    改版前 base 自己就不一致（一條 object、一條 typed）；本 PR 統一。
    現行消費端都先判 `.empty`，實務影響為零。

    ⚠️ **2026-09-01 第二輪更正（有意識的更正，不是漏刪）**：本段原本寫
    ~~「但『回傳形狀逐字相同』要為真就不能留差異」~~ —— **因果講反了**。
    統一 dtype **本身就是形狀變更**（實測 7/7 個失敗分支的 dtype 都變了），
    所以它是「逐字相同不成立」的原因，不是讓它成立的手段。
    那句假宣稱當時被寫進**三個載體**（本檔、`_empty_flow_df` docstring、
    兩支公開 `fetch_*` 的 docstring），三份一起錯 ——
    正是 `infra/source_backoff.py::_BackoffRegistryProxy` 記載的那個教訓：
    「更正措辭時只修被點名的那個載體，剩下的副本會繼續說謊。」
    現行的變更清單寫在兩支公開 `fetch_*` 的 docstring 裡（唯一真相源）。
    """
    run, _net, _impl = harness
    df, _err = run("quota_402", days=119)[0]
    assert str(df["date"].dtype) == "datetime64[ns]", df.dtypes.to_dict()
    assert str(df["foreign_net_yi"].dtype) == "float64", df.dtypes.to_dict()
