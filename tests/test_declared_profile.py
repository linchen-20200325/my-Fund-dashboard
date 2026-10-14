"""`repositories/fund/declared_profile.py`（exp 正式模式批 C 的 C1：L1 自報基本資料取數）守衛。

⚠️ **本檔的 HTML 與 JSON 全部是手寫的最小樣本**，標籤結構（MoneyDJ 基本資料表）、
清單欄名（TDCC 3-2）、回應鍵名（FundClear `GetFundBasicInfo`）**都未以真實回應樣本驗證** ——
repo 裡沒有這三個來源的原始回應，本環境也連不到。樣本照 repo 既有解析碼
（`sources._src_tcb_meta`／`_src_tdcc_meta`／`_src_fundclear_meta`）會吃的形狀寫。
→ 2026-10-14 補記：檔尾另有 **MoneyDJ 真實頁面 golden fixture** 的測試（#961 探測報告，GitHub runner 直連；
`tests/fixtures/moneydj_basic/`）。上面那句「全部是手寫」自此只指檔尾那一段以外的測試；TDCC、FundClear 仍是手寫樣本。

全程不打網路：`fetch_url_with_retry` 換成依網址回應的替身（失敗時照 `infra.proxy.fetch_url`
的做法把分類寫進 thread-local，讓 `pop_last_fail_kind()` 走真的那條路）；`_tdcc_get` 換成替身，
或保留真的 `_tdcc_get` 但預先放好它的行程內快取並把 `urlopen` 換成一碰就炸的替身。
"""
from __future__ import annotations

import json

import pytest

import infra.proxy as proxy_mod
import infra.source_backoff as sb
import repositories.fund.declared_profile as dp
from repositories.fund import sources as src

CODE = "TLZF9"
TCB = "tcbbankfund.moneydj.com"
WWW = "www.moneydj.com"


def _mdj(host, page, code=CODE):
    return f"https://{host}/funddj/yp/{page}.djhtm?a={code}"


# 境外（預設）順序：yp011001 tcb → yp011001 www → yp011000 tcb → yp011000 www
U1, U2, U3, U4 = (_mdj(TCB, "yp011001"), _mdj(WWW, "yp011001"),
                  _mdj(TCB, "yp011000"), _mdj(WWW, "yp011000"))

_PAD = "<p>" + ("基金 淨值 日期 績效 " * 40) + "</p>"   # 讓頁面長度 > 500 且過得了 is_valid_moneydj_page


def _page(rows_html: str, code: str = CODE, pad: bool = True) -> str:
    return (f"<html><body>{_PAD if pad else ''}<a href='/w/wb/wb01.djhtm?a={code}'>{code}</a>"
            f"<table>{rows_html}</table></body></html>")


def _row2(k, v):
    return f"<tr><td>{k}</td><td>{v}</td></tr>"


def _row4(k1, v1, k2, v2):
    return f"<tr><td>{k1}</td><td>{v1}</td><td>{k2}</td><td>{v2}</td></tr>"


FULL_TABLE = (_row2("基金名稱", "安聯收益成長基金-AM穩定月收類股(美元)")
              + _row4("計價幣別", "美元", "配息頻率", "月配")
              + _row4("成立日期", "2012/03/23", "最高經理費(%)", "1.80"))

SHELL = "<html><body>" + _PAD + ("x" * 2000) + "</body></html>"   # 長度夠、沒表、沒代碼


class _Resp:
    def __init__(self, text=None, payload=None):
        self.text = text if text is not None else json.dumps(payload or {})
        self._payload = payload

    def json(self):
        if self._payload is None:
            return json.loads(self.text)
        return self._payload


class _Net:
    """依網址回應的 `fetch_url_with_retry` 替身。spec：("html", str) / ("json", obj) / ("fail", kind) / ("empty",)。"""

    def __init__(self, routes: dict):
        self.routes = routes
        self.calls: list = []

    def __call__(self, url, headers=None, params=None, timeout=20, retries=3, sleep_sec=2):
        self.calls.append(url)
        proxy_mod._TLS_FAIL.kind = ""          # 同 fetch_url：進場先清
        spec = self.routes.get(url, ("fail", "not_found"))
        if spec[0] == "html":
            return _Resp(text=spec[1])
        if spec[0] == "json":
            return _Resp(payload=spec[1])
        if spec[0] == "fail":
            proxy_mod._TLS_FAIL.kind = spec[1]   # 同 fetch_url 的 _note_failure
            return None
        return None                            # empty：200 但內文空 → None 且無分類


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    for fn in (dp.fetch_moneydj_basic_fields, dp.fetch_tdcc_listing, dp.fetch_fundclear_declared_ccy):
        fn.cache_clear()
    dp._TDCC_OBSERVED.clear()
    monkeypatch.setattr(src, "_is_domestic_code", lambda code, page_type="": False)
    monkeypatch.setattr(src, "_tdcc_cache", {})

    def _no_network(*a, **k):
        raise AssertionError("測試不得打網路（urllib）")
    import urllib.request as ur
    monkeypatch.setattr(ur, "urlopen", _no_network)
    yield
    for fn in (dp.fetch_moneydj_basic_fields, dp.fetch_tdcc_listing, dp.fetch_fundclear_declared_ccy):
        fn.cache_clear()
    dp.clear_failure_memory()
    dp._TDCC_OBSERVED.clear()


@pytest.fixture(autouse=True)
def mclock(monkeypatch):
    """失敗記憶用的假時鐘（`dp._clock`）。`mclock["t"] += N` 讓記憶過期；成功快取的時鐘（time.time）不受影響。"""
    state = {"t": 1000.0}
    monkeypatch.setattr(dp, "_clock", lambda: state["t"])
    return state


@pytest.fixture
def clock(monkeypatch):
    """讓 `_now_iso` 每次呼叫前進一秒，才驗得出「命中快取時時刻沒被改寫」。"""
    state = {"n": 0}

    def _tick():
        state["n"] += 1
        return f"2026-10-14T00:00:{state['n']:02d}+00:00"
    monkeypatch.setattr(dp, "_now_iso", _tick)
    return state


def _net(monkeypatch, routes):
    net = _Net(routes)
    monkeypatch.setattr(dp, "fetch_url_with_retry", net)
    return net


# ═════════════════════════════ MoneyDJ ═════════════════════════════

class TestMoneyDJLabels:
    def test_reads_exactly_the_four_labels_with_raw_literals(self, monkeypatch):
        _net(monkeypatch, {U1: ("html", _page(FULL_TABLE))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "ok"
        assert r["fields"] == {"基金名稱": "安聯收益成長基金-AM穩定月收類股(美元)",
                               "計價幣別": "美元", "配息頻率": "月配", "成立日期": "2012/03/23"}
        assert r["provenance"] == {"host": TCB, "page_type": "yp011001", "url": U1}
        assert r["error"] is None

    def test_max_mgmt_fee_is_never_read(self, monkeypatch):
        _net(monkeypatch, {U1: ("html", _page(FULL_TABLE))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        dumped = json.dumps(r, ensure_ascii=False)
        assert "經理費" not in dumped and "1.80" not in dumped

    def test_near_miss_labels_are_not_accepted(self, monkeypatch):
        rows = (_row2("基金名稱", "某基金") + _row2("設立日期", "2001/01/01")
                + _row2("成立日", "2002/02/02") + _row2("計價幣別：", "美元")
                + _row2("配息頻率(年)", "12"))
        _net(monkeypatch, {U1: ("html", _page(rows))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "ok"
        assert r["fields"]["成立日期"] is None
        assert r["fields"]["計價幣別"] is None
        assert r["fields"]["配息頻率"] is None

    def test_surrounding_whitespace_is_stripped_for_label_match(self, monkeypatch):
        rows = _row2("基金名稱", "某基金") + _row2("  計價幣別\n", " 新臺幣 ")
        _net(monkeypatch, {U1: ("html", _page(rows))})
        assert dp.fetch_moneydj_basic_fields(CODE)["fields"]["計價幣別"] == "新臺幣"

    def test_missing_fields_are_none_not_zero(self, monkeypatch):
        _net(monkeypatch, {U1: ("html", _page(_row2("基金名稱", "某基金")))})
        f = dp.fetch_moneydj_basic_fields(CODE)["fields"]
        assert f == {"基金名稱": "某基金", "計價幣別": None, "配息頻率": None, "成立日期": None}

    def test_two_cell_and_four_cell_rows(self, monkeypatch):
        rows = (_row4("基金名稱", "甲", "計價幣別", "歐元") + _row2("配息頻率", "季配")
                + "<tr><td>成立日期</td><td>2010/01/01</td><td>孤兒格</td></tr>")   # 3 格不收
        _net(monkeypatch, {U1: ("html", _page(rows))})
        f = dp.fetch_moneydj_basic_fields(CODE)["fields"]
        assert f["基金名稱"] == "甲" and f["計價幣別"] == "歐元" and f["配息頻率"] == "季配"
        assert f["成立日期"] is None

    def test_conflicting_duplicate_label_sets_none_and_reports_values(self, monkeypatch):
        # 2026-10-14 改名（有意識的更正，不是漏刪；決策者 AI 總管；依據稽核 N）：
        # 舊名 `test_conflicting_duplicate_label_keeps_first_and_is_reported` 已名不副實（不再取第一個）。
        # 2026-10-14 修正輪（稽核非阻擋 2；決策者 AI 總管）：同標籤兩個不同值 → 該欄設 None、兩個值都記下，
        # 不再取第一個。舊斷言：`assert r["fields"]["計價幣別"] == "美元"`（取第一個）。
        rows = (_row2("基金名稱", "甲") + _row2("計價幣別", "美元") + _row2("計價幣別", "台幣")
                + _row2("配息頻率", "月配"))
        _net(monkeypatch, {U1: ("html", _page(rows))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "ok"
        assert r["fields"]["計價幣別"] is None
        assert r["fields"]["配息頻率"] == "月配" and r["fields"]["基金名稱"] == "甲"   # 其他欄照收
        assert r["label_conflicts"] == [{"label": "計價幣別", "values": ["美元", "台幣"]}]

    def test_identical_duplicate_label_is_not_a_conflict(self, monkeypatch):
        rows = _row2("基金名稱", "甲") + _row2("計價幣別", "美元") + _row2("計價幣別", "美元")
        _net(monkeypatch, {U1: ("html", _page(rows))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["fields"]["計價幣別"] == "美元" and r["label_conflicts"] == []

    def test_conflicting_fund_name_is_not_adopted(self, monkeypatch):
        rows = _row2("基金名稱", "甲") + _row2("基金名稱", "乙")
        _net(monkeypatch, {U1: ("html", _page(rows))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        # 2026-10-14 身分判準修訂（有意識的更正，不是漏刪；決策者 AI 總管；依據 #961 探測報告）：
        # 頁面回來了但名稱自相矛盾、其餘網址 404 → unrecognized_page（不是取數失敗）。舊斷言：status == "failed"。
        assert r["status"] == "unrecognized_page"
        assert r["attempts"][0]["outcome"] == "unrecognized_page"
        assert "出現不同的值" in r["attempts"][0]["problem"] and "出現不同的值" in r["reason"]

    def test_nested_table_rows_do_not_leak_into_outer_table(self, monkeypatch):
        inner = "<table>" + _row2("計價幣別", "日圓") + "</table>"
        rows = _row2("基金名稱", "甲") + f"<tr><td>{inner}</td></tr>"
        _net(monkeypatch, {U1: ("html", _page(rows))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "ok" and r["fields"]["計價幣別"] is None

    def test_rows_under_tbody_are_read(self, monkeypatch):
        rows = "<tbody>" + _row2("基金名稱", "甲") + _row2("計價幣別", "美元") + "</tbody>"
        _net(monkeypatch, {U1: ("html", _page(rows))})
        assert dp.fetch_moneydj_basic_fields(CODE)["fields"]["計價幣別"] == "美元"

    def test_table_without_fund_name_row_is_not_selected(self, monkeypatch):
        html = (f"<html><body>{_PAD}<p>{CODE}</p>"
                f"<table>{_row2('計價幣別', '台幣')}</table>"
                f"<table>{_row2('基金名稱', '甲')}{_row2('計價幣別', '美元')}</table></body></html>")
        _net(monkeypatch, {U1: ("html", html)})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["fields"] == {"基金名稱": "甲", "計價幣別": "美元", "配息頻率": None, "成立日期": None}


class TestMoneyDJUrlChain:
    def test_shell_page_long_enough_does_not_stop_the_chain(self, monkeypatch):
        net = _net(monkeypatch, {U1: ("html", SHELL), U2: ("html", _page(FULL_TABLE))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert len(SHELL) > 500
        assert r["status"] == "ok" and r["provenance"]["url"] == U2
        assert net.calls == [U1, U2]
        # 2026-10-14 修正輪（BLOCKING 1；決策者 AI 總管；依據稽核 M 反例）：MoneyDJ 不再有「確定沒有」這一類，
        # 空殼頁一律算無法判讀。舊斷言：`... == "valid_page_without_code_or_table"`。
        assert r["attempts"][0]["outcome"] == "unrecognized_page"

    def test_page_not_mentioning_code_is_now_adopted_and_recorded(self, monkeypatch):
        # 2026-10-14 身分判準修訂（有意識的更正，不是漏刪；決策者 AI 總管；依據 #961 探測報告）：
        # 舊名 `test_page_not_mentioning_code_is_not_adopted`；舊斷言：provenance 是 U2、U1 判 unrecognized_page、
        # 打了 [U1, U2]。真實頁面可見文字本來就不印代碼（8/8），可見文字提不提到代碼不再是門檻 ——
        # 以請求代碼取回、恰一張非空名稱表就採用；提不提到照實記在 binding。
        other = _page(FULL_TABLE, code="OTHER1")
        net = _net(monkeypatch, {U1: ("html", other), U2: ("html", _page(FULL_TABLE))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "ok" and r["provenance"]["url"] == U1
        assert r["binding"]["code_in_page_text"] is False
        assert net.calls == [U1]

    def test_domestic_code_tries_yp011000_first(self, monkeypatch):
        monkeypatch.setattr(src, "_is_domestic_code", lambda code, page_type="": True)
        net = _net(monkeypatch, {})
        dp.fetch_moneydj_basic_fields(CODE)
        assert net.calls == [U3, U4, U1, U2]

    def test_each_url_has_an_attempt_with_classified_fail_kind(self, monkeypatch):
        net = _net(monkeypatch, {U1: ("fail", "unreachable"), U2: ("fail", "blocked"),
                                 U3: ("fail", "rate_limited"), U4: ("fail", "server_error")})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "failed"
        assert [a["url"] for a in r["attempts"]] == [U1, U2, U3, U4] == net.calls
        assert [a["fail_kind"] for a in r["attempts"]] == ["unreachable", "blocked", "rate_limited", "server_error"]
        assert all(a["outcome"] == "http_failed" for a in r["attempts"])
        for u in (U1, U2, U3, U4):
            assert u in r["error"]
        assert r["fetched_at"] is None
        assert proxy_mod.pop_last_fail_kind() == ""   # 分類被讀走了，沒有殘值留給下一個 caller

    def test_all_404_and_codeless_page_is_failed_not_not_listed(self, monkeypatch):
        # 2026-10-14 改名（有意識的更正，不是漏刪；決策者 AI 總管；依據稽核 N）：
        # 舊名 `test_all_definite_absent_is_not_listed` 已名不副實（這組輸入現在必須判 failed）。
        # 2026-10-14 修正輪（BLOCKING 1；決策者 AI 總管；依據稽核 M 反例）：在拿到真實「查無此基金」頁面樣本前，
        # MoneyDJ 一律不判 not_listed —— 404 與「正常頁但沒代碼沒表」都證明不了查無此代碼。
        # 舊斷言：status == "not_listed"、error is None、第 3 筆 outcome == "valid_page_without_code_or_table"。
        # 第一輪修正時測試名保留（不刪測試）；本輪依稽核 N 改名，守的是反面：這組輸入**不得**判成 not_listed。
        valid_no_code = "<html><body>" + _PAD + "</body></html>"
        _net(monkeypatch, {U1: ("fail", "not_found"), U2: ("fail", "not_found"),
                           U3: ("html", valid_no_code), U4: ("fail", "not_found")})
        r = dp.fetch_moneydj_basic_fields(CODE)
        # 2026-10-14 身分判準修訂（有意識的更正，不是漏刪；決策者 AI 總管；依據 #961 探測報告）：
        # 一頁回來了（沒有表）、其餘 404 → unrecognized_page；仍然**不是** not_listed。舊斷言：status == "failed"。
        assert r["status"] == "unrecognized_page" and r["status"] != "not_listed"
        assert r["error"] and U1 in r["error"]
        assert [a["outcome"] for a in r["attempts"]] == [
            "not_found_404", "not_found_404", "unrecognized_page", "not_found_404"]

    @pytest.mark.parametrize("routes", [
        {U1: ("html", SHELL), U2: ("html", SHELL), U3: ("html", SHELL), U4: ("html", SHELL)},
        {u: ("html", "<html><body><p>系統維護中，基金 淨值 績效 資料暫停提供</p>" + "x" * 800 + "</body></html>")
         for u in (U1, U2, U3, U4)},
        {U1: ("fail", "not_found"), U3: ("fail", "not_found"), U2: ("html", SHELL), U4: ("html", SHELL)},
    ], ids=["four_shells", "four_maintenance_pages", "tcb_404_www_shell"])
    def test_audit_m_counterexamples_are_failed_and_not_cached(self, monkeypatch, mclock, routes):
        net = _net(monkeypatch, routes)
        r = dp.fetch_moneydj_basic_fields(CODE)
        # 2026-10-14 身分判準修訂（有意識的更正，不是漏刪；決策者 AI 總管；依據 #961 探測報告）：
        # 這三組都是「頁面回來了但不符判準」→ unrecognized_page（不是 failed、更不是 not_listed）；
        # 「不進 1 小時快取、記憶過期就重打」照舊（稽核 M 的理由不變）。舊斷言：status == "failed"。
        assert r["status"] == "unrecognized_page"
        mclock["t"] += dp.FAILURE_MEMORY_SEC + 1           # 失敗記憶過期 → 重打（成功快取沒有收它）
        dp.fetch_moneydj_basic_fields(CODE)
        assert len(net.calls) == 8

    def test_prefix_sharing_code_is_not_a_mention(self, monkeypatch):
        other = _page(FULL_TABLE, code=CODE + "0")         # 頁面只提到 TLZF90
        net = _net(monkeypatch, {U1: ("html", other), U2: ("html", other),
                                 U3: ("html", other), U4: ("html", other)})
        r = dp.fetch_moneydj_basic_fields(CODE)
        # 2026-10-14 身分判準修訂（有意識的更正，不是漏刪；決策者 AI 總管；依據 #961 探測報告）：
        # 詞界規則本身不變（TLZF90 不算提到 TLZF9），但它已降為附加資訊：頁面以請求代碼取回、恰一張非空名稱表 → ok。
        # 舊斷言：status == "failed"、打 4 次、四筆 unrecognized_page、基金名稱 None。
        assert r["status"] == "ok" and len(net.calls) == 1
        assert r["binding"]["code_in_page_text"] is False
        from bs4 import BeautifulSoup
        assert dp._mentions_code(BeautifulSoup(other, "lxml"), CODE) is False

    def test_code_only_in_link_attribute_is_not_a_mention(self, monkeypatch):
        html = (f"<html><body>{_PAD}<a href='/w/wb/wb01.djhtm?a={CODE}'>淨值走勢</a>"
                f"<table>{FULL_TABLE}</table></body></html>")
        _net(monkeypatch, {U1: ("html", html)})
        r = dp.fetch_moneydj_basic_fields(CODE)
        # 2026-10-14 身分判準修訂（有意識的更正，不是漏刪；決策者 AI 總管；依據 #961 探測報告）：
        # 這正是真實頁面的形狀（代碼只在 href）。屬性裡的代碼仍「不算提到」（附加資訊照實為 False），
        # 但不再擋採用。舊斷言：status == "failed"、outcome == "unrecognized_page"。
        assert r["status"] == "ok" and r["attempts"][0]["outcome"] == "ok"
        assert r["binding"]["code_in_page_text"] is False

    def test_code_preceded_by_alnum_is_not_a_mention(self, monkeypatch):
        html = (f"<html><body>{_PAD}<p>相關代碼：X{CODE}</p>"
                f"<table>{FULL_TABLE}</table></body></html>")
        _net(monkeypatch, {U1: ("html", html), U2: ("html", html), U3: ("html", html), U4: ("html", html)})
        r = dp.fetch_moneydj_basic_fields(CODE)
        # 2026-10-14 身分判準修訂（有意識的更正，不是漏刪；決策者 AI 總管；依據 #961 探測報告）：
        # 詞界規則不變（XTLZF9 不算），但已降為附加資訊。舊斷言：status == "failed"、四筆 unrecognized_page。
        assert r["status"] == "ok" and r["binding"]["code_in_page_text"] is False

    def test_code_mention_is_case_insensitive_whole_word(self, monkeypatch):
        html = (f"<html><body>{_PAD}<p>代碼：{CODE.lower()}。</p>"
                f"<table>{FULL_TABLE}</table></body></html>")
        _net(monkeypatch, {U1: ("html", html)})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "ok" and r["binding"]["code_in_page_text"] is True   # 附加資訊照實

    def test_exception_path_is_recorded_and_failed(self, monkeypatch):
        def boom(url, **k):
            raise RuntimeError("解析爆炸")
        monkeypatch.setattr(dp, "fetch_url_with_retry", boom)
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "failed"
        assert all(a["outcome"] == "exception" and a["fail_kind"] == "exception" for a in r["attempts"])
        assert "RuntimeError: 解析爆炸" in r["error"]

    def test_lowercase_input_is_normalized_and_shares_cache_cell(self, monkeypatch):
        net = _net(monkeypatch, {U1: ("html", _page(FULL_TABLE))})
        a = dp.fetch_moneydj_basic_fields(" tlzf9")
        b = dp.fetch_moneydj_basic_fields("TLZF9")
        assert a["full_key"] == "TLZF9" and a["status"] == b["status"] == "ok"
        assert net.calls == [U1]

    # 2026-10-14 身分判準修訂（有意識的更正，不是漏刪；決策者 AI 總管；依據 #961 探測報告）：
    # 參數原含 `("empty",)`（200 但內文空白）—— 它是 200 的回應，不是網路錯誤／逾時／5xx／例外，
    # 改歸 unrecognized_page（見 `test_empty_200_with_404s_is_unrecognized_not_failed`）。
    @pytest.mark.parametrize("bad", [("fail", "unreachable"), ("fail", "blocked"), ("fail", "rate_limited"),
                                     ("fail", "server_error"), ("fail", "proxy_auth")])
    def test_any_indeterminate_attempt_makes_it_failed_not_not_listed(self, monkeypatch, bad):
        _net(monkeypatch, {U1: ("fail", "not_found"), U2: ("fail", "not_found"),
                           U3: ("fail", "not_found"), U4: bad})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "failed"
        assert U4 in r["error"]

    def test_empty_200_with_404s_is_unrecognized_not_failed(self, monkeypatch):
        _net(monkeypatch, {U1: ("fail", "not_found"), U2: ("fail", "not_found"),
                           U3: ("fail", "not_found"), U4: ("empty",)})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "unrecognized_page"
        assert "內文空白" in r["reason"] and U4 in r["error"]

    def test_empty_response_is_classified(self, monkeypatch):
        _net(monkeypatch, {U1: ("empty",)})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["attempts"][0]["outcome"] == "empty_response"

    def test_host_in_cooldown_is_not_fetched_and_counts_as_failed(self, monkeypatch):
        sb.record_failure(TCB, "blocked")
        net = _net(monkeypatch, {U2: ("fail", "not_found"), U4: ("fail", "not_found")})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert net.calls == [U2, U4]                       # tcbbankfund 兩個網址沒打
        cd = [a for a in r["attempts"] if a["host"] == TCB]
        assert len(cd) == 2 and all(a["fail_kind"] == "cooldown" for a in cd)
        assert all(a["cooldown_origin_kind"] == "blocked" for a in cd)
        assert r["status"] == "failed"

    def test_invalid_full_key_raises_without_network(self, monkeypatch):
        net = _net(monkeypatch, {})
        with pytest.raises(ValueError):
            dp.fetch_moneydj_basic_fields("a b")
        with pytest.raises(TypeError):
            dp.fetch_moneydj_basic_fields(None)
        assert net.calls == []


class TestMoneyDJCache:
    def test_ok_is_cached_and_fetched_at_unchanged_on_hit(self, monkeypatch, clock):
        net = _net(monkeypatch, {U1: ("html", _page(FULL_TABLE))})
        a = dp.fetch_moneydj_basic_fields(CODE)
        b = dp.fetch_moneydj_basic_fields(CODE)
        assert len(net.calls) == 1
        assert a["fetched_at"] and b["fetched_at"] == a["fetched_at"]
        assert dp.fetch_moneydj_basic_fields.cache_info()["hits"] == 1

    def test_all_404_is_failed_and_remembered_not_cached(self, monkeypatch):
        # 2026-10-14 改名（有意識的更正，不是漏刪；決策者 AI 總管；依據稽核 N）：
        # 舊名 `test_not_listed_is_cached` 已名不副實（全部 404 現在是 failed、進失敗記憶、不進成功快取）。
        # 2026-10-14 修正輪（BLOCKING 1＋稽核 N-2；決策者 AI 總管）：全部 404 不再判 not_listed、不進 1 小時快取，
        # 改判 failed 並進 5 分鐘失敗記憶 —— 記憶期間第二次呼叫照樣不出門，所以請求數仍是 4。
        # 舊斷言：`assert ...["status"] == "not_listed"`。
        net = _net(monkeypatch, {})   # 全部 404
        # 2026-10-14 身分判準修訂（有意識的更正，不是漏刪；決策者 AI 總管；依據 #961 探測報告）：
        # 全部 404 → not_found（仍不進 1 小時快取、仍進記憶）。舊斷言：status == "failed"。
        assert dp.fetch_moneydj_basic_fields(CODE)["status"] == "not_found"
        again = dp.fetch_moneydj_basic_fields(CODE)
        assert len(net.calls) == 4
        assert again["cooling"] is True
        assert dp.fetch_moneydj_basic_fields.cache_info()["size"] == 0   # 沒進成功快取

    def test_failed_is_not_cached(self, monkeypatch, mclock):
        # 2026-10-14 修正輪：failed 改進失敗記憶，第二次呼叫要等記憶過期才重打（舊版是立刻重打）。
        net = _net(monkeypatch, {U1: ("fail", "unreachable")})
        assert dp.fetch_moneydj_basic_fields(CODE)["status"] == "failed"
        dp.fetch_moneydj_basic_fields(CODE)
        assert len(net.calls) == 4
        mclock["t"] += dp.FAILURE_MEMORY_SEC + 1
        dp.fetch_moneydj_basic_fields(CODE)
        assert len(net.calls) == 8
        assert dp.fetch_moneydj_basic_fields.cache_info()["uncached_fail"] == 2

    def test_returns_deep_copy(self, monkeypatch):
        _net(monkeypatch, {U1: ("html", _page(FULL_TABLE))})
        a = dp.fetch_moneydj_basic_fields(CODE)
        a["fields"]["計價幣別"] = "被改掉"
        a["attempts"].clear()
        b = dp.fetch_moneydj_basic_fields(CODE)
        assert b["fields"]["計價幣別"] == "美元" and b["attempts"]

    def test_registered_in_cache_registry(self):
        # 2026-10-14 修正輪：成功快取改住在內層 `_..._cached`（公開入口先正規化代碼），另登記失敗記憶。
        from infra.cache import _CACHE_REGISTRY
        names = {getattr(f, "__name__", "") for f in _CACHE_REGISTRY}
        assert {"_fetch_moneydj_basic_fields_cached", "_fetch_tdcc_listing_cached",
                "_fetch_fundclear_declared_ccy_cached", "declared_profile_failure_memory"} <= names


class TestFailureMemory:
    def test_memory_window_no_request_and_cooling_flags(self, monkeypatch, mclock, clock):
        net = _net(monkeypatch, {U1: ("fail", "unreachable")})
        a = dp.fetch_moneydj_basic_fields(CODE)
        assert a["cooling"] is False and a["cooling_remaining_sec"] is None
        mclock["t"] += 100
        b = dp.fetch_moneydj_basic_fields(CODE)
        assert len(net.calls) == 4                          # 記憶期間不出門
        assert b["status"] == "failed" and b["cooling"] is True
        assert b["cooling_remaining_sec"] == pytest.approx(dp.FAILURE_MEMORY_SEC - 100)
        assert b["error"] == a["error"] and b["attempts"] == a["attempts"]
        assert b["fetched_at"] == a["fetched_at"]           # 不刷新成當下

    def test_memory_key_is_normalized(self, monkeypatch):
        net = _net(monkeypatch, {U1: ("fail", "unreachable")})
        dp.fetch_moneydj_basic_fields(" tlzf9 ")
        r = dp.fetch_moneydj_basic_fields("TLZF9")
        assert len(net.calls) == 4 and r["cooling"] is True

    def test_memory_stores_a_copy_not_the_returned_object(self, monkeypatch):
        _net(monkeypatch, {U1: ("fail", "unreachable")})
        a = dp.fetch_moneydj_basic_fields(CODE)
        original_error = a["error"]
        a["error"] = "呼叫端改掉"
        a["attempts"].clear()
        b = dp.fetch_moneydj_basic_fields(CODE)
        assert b["cooling"] is True
        assert b["error"] == original_error and len(b["attempts"]) == 4

    def test_single_function_cache_clear_only_clears_its_own_memory(self, monkeypatch):
        net = _net(monkeypatch, {U1: ("fail", "unreachable"), FC_URL: ("fail", "unreachable")})
        dp.fetch_moneydj_basic_fields(CODE)
        dp.fetch_fundclear_declared_ccy(CODE)
        assert len(net.calls) == 5
        dp.fetch_moneydj_basic_fields.cache_clear()
        assert dp.fetch_moneydj_basic_fields(CODE)["cooling"] is False     # 自己那份清掉 → 重打
        assert len(net.calls) == 9
        assert dp.fetch_fundclear_declared_ccy(CODE)["cooling"] is True    # 別支的不清
        assert len(net.calls) == 9

    def test_memory_key_is_per_function(self, monkeypatch):
        _tdcc(monkeypatch, [], error="URLError: timed out")
        assert dp.fetch_tdcc_listing(CODE)["status"] == "failed"
        net = _net(monkeypatch, {FC_URL: ("json", {"Data": {"Currency": "USD"}})})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert net.calls == [FC_URL] and r["status"] == "ok"

    def test_memory_expiry_boundary_is_inclusive(self, monkeypatch, mclock):
        # 現行判準 `now - 記下時刻 >= FAILURE_MEMORY_SEC` 即過期：差 0.1 秒仍在記憶中，剛好 300 秒就重打。
        net = _net(monkeypatch, {FC_URL: ("fail", "unreachable")})
        dp.fetch_fundclear_declared_ccy(CODE)
        mclock["t"] += dp.FAILURE_MEMORY_SEC - 0.1
        assert dp.fetch_fundclear_declared_ccy(CODE)["cooling"] is True
        mclock["t"] += 0.1
        assert dp.fetch_fundclear_declared_ccy(CODE)["cooling"] is False
        assert net.calls == [FC_URL, FC_URL]

    def test_memory_expiry_refetches(self, monkeypatch, mclock):
        net = _net(monkeypatch, {FC_URL: ("fail", "unreachable")})
        dp.fetch_fundclear_declared_ccy(CODE)
        mclock["t"] += dp.FAILURE_MEMORY_SEC - 1
        assert dp.fetch_fundclear_declared_ccy(CODE)["cooling"] is True
        mclock["t"] += 2
        c = dp.fetch_fundclear_declared_ccy(CODE)
        assert c["cooling"] is False and net.calls == [FC_URL, FC_URL]

    def test_memory_returns_deep_copy(self, monkeypatch):
        _net(monkeypatch, {U1: ("fail", "unreachable")})
        dp.fetch_moneydj_basic_fields(CODE)
        b = dp.fetch_moneydj_basic_fields(CODE)
        b["attempts"].clear()
        b["error"] = "被改掉"
        c = dp.fetch_moneydj_basic_fields(CODE)
        assert c["attempts"] and c["error"] != "被改掉"

    def test_memory_is_cleared_by_global_clear(self, monkeypatch):
        from infra.cache import clear_all_caches
        net = _net(monkeypatch, {U1: ("fail", "unreachable")})
        dp.fetch_moneydj_basic_fields(CODE)
        clear_all_caches()
        dp.fetch_moneydj_basic_fields(CODE)
        assert len(net.calls) == 8

    def test_tdcc_failed_memory(self, monkeypatch):
        calls = _tdcc(monkeypatch, [], error="URLError: timed out")
        sb.reset_all()   # 只驗失敗記憶：清掉 record_failure 造成的冷卻，免得兩道防線混在一起
        dp.fetch_tdcc_listing(CODE)
        sb.reset_all()
        r = dp.fetch_tdcc_listing(CODE)
        assert calls == ["3-2"] and r["cooling"] is True


# ═════════════════════════════ TDCC ═════════════════════════════

TDCC_ROWS = [
    {"基金代碼": "AAA01", "基金名稱": "甲基金", "計價幣別": "USD"},
    {"境外基金代碼": "tlzf9", "基金名稱": "安聯收益成長", "計價幣別": "美元"},
]


def _tdcc(monkeypatch, data, error=None):
    calls = []

    def fake(ep, *, error_out=None):
        calls.append(ep)
        if error and error_out is not None:
            error_out["error"] = error
        return data
    monkeypatch.setattr(src, "_tdcc_get", fake)
    return calls


class TestTdcc:
    def test_listed_by_offshore_code_key(self, monkeypatch):
        _tdcc(monkeypatch, TDCC_ROWS)
        r = dp.fetch_tdcc_listing(CODE)
        assert r["status"] == "ok"
        assert r["fields"] == {"基金名稱": "安聯收益成長", "計價幣別": "美元"}
        assert r["provenance"]["code_key"] == "境外基金代碼"
        assert r["fetched_at"] is None and r["observed_at"]

    def test_non_empty_list_without_code_is_code_unmapped(self, monkeypatch):
        # 2026-10-14 身分判準修訂（有意識的更正，不是漏刪；決策者 AI 總管；依據 #961 探測報告）：
        # 舊名 `test_non_empty_list_without_code_is_not_listed`；舊斷言：status == "not_listed"。
        # 3-2 用另一套代碼，0 命中證明不了未收錄 → code_unmapped（代碼無法對照），一樣進 1 小時快取。
        _tdcc(monkeypatch, TDCC_ROWS)
        r = dp.fetch_tdcc_listing("ZZZ99")
        assert r["status"] == "code_unmapped" and r["error"] is None
        assert "不同的代碼體系" in r["attempts"][0]["detail"]
        assert r["fields"] == {"基金名稱": None, "計價幣別": None}            # 不以名稱比對補任何值
        dp.fetch_tdcc_listing("ZZZ99")
        assert dp.fetch_tdcc_listing.cache_info()["hits"] == 1

    def test_missing_currency_key_is_none(self, monkeypatch):
        _tdcc(monkeypatch, [{"基金代碼": CODE, "基金名稱": "甲"}])
        assert dp.fetch_tdcc_listing(CODE)["fields"]["計價幣別"] is None

    def test_empty_list_with_error_is_failed_and_records_backoff(self, monkeypatch):
        _tdcc(monkeypatch, [], error="HTTPError: HTTP Error 403: Forbidden")
        r = dp.fetch_tdcc_listing(CODE)
        assert r["status"] == "failed" and "403" in r["error"]
        assert r["attempts"][0]["fail_kind"] == "blocked"
        skip, _left, kind = sb.should_skip("openapi.tdcc.com.tw")
        assert skip and kind == "blocked"

    def test_fresh_empty_list_without_error_is_failed(self, monkeypatch):
        _tdcc(monkeypatch, [])
        r = dp.fetch_tdcc_listing(CODE)
        assert r["status"] == "failed"
        assert r["attempts"][0]["outcome"] == "empty_or_non_list"

    def test_cached_empty_list_from_real_tdcc_get_is_failed(self, monkeypatch):
        # 真的 `_tdcc_get`；行程內快取放 `[]`（它把非清單回應永久快取成這個）；urlopen 一碰就炸。
        monkeypatch.setattr(src, "_tdcc_cache", {"3-2": []})
        r = dp.fetch_tdcc_listing(CODE)
        assert r["status"] == "failed"
        assert r["attempts"][0]["outcome"] == "cached_empty_list"
        assert not sb.should_skip("openapi.tdcc.com.tw")[0]   # 沒發請求，不記失敗

    def test_cooldown_does_not_call_tdcc_get(self, monkeypatch):
        calls = _tdcc(monkeypatch, TDCC_ROWS)
        sb.record_failure("openapi.tdcc.com.tw", "unreachable")
        r = dp.fetch_tdcc_listing(CODE)
        assert calls == []
        assert r["status"] == "failed" and r["attempts"][0]["fail_kind"] == "cooldown"

    def test_ok_cached_failed_not_cached(self, monkeypatch, mclock):
        calls = _tdcc(monkeypatch, TDCC_ROWS)
        dp.fetch_tdcc_listing(CODE)
        dp.fetch_tdcc_listing(CODE)
        assert calls == ["3-2"]
        calls2 = _tdcc(monkeypatch, [])
        dp.fetch_tdcc_listing("BBB02")
        mclock["t"] += dp.FAILURE_MEMORY_SEC + 1   # 2026-10-14 修正輪：failed 先進失敗記憶，過期後才重打
        dp.fetch_tdcc_listing("BBB02")
        assert calls2 == ["3-2", "3-2"]

    def test_non_dict_rows_are_skipped(self, monkeypatch):
        _tdcc(monkeypatch, ["垃圾", None, 3, {"基金代碼": CODE, "基金名稱": "甲", "計價幣別": "USD"}])
        assert dp.fetch_tdcc_listing(CODE)["status"] == "ok"

    def test_fresh_success_releases_backoff(self, monkeypatch):
        seen = []
        monkeypatch.setattr(sb, "record_success", lambda key: seen.append(key) or True)
        _tdcc(monkeypatch, TDCC_ROWS)
        dp.fetch_tdcc_listing(CODE)
        assert seen == ["openapi.tdcc.com.tw"]

    def test_code_key_order_follows_src_tdcc_meta(self, monkeypatch):
        # 同 `_src_tdcc_meta` 的 `or` 串：有「基金代碼」就用它，不再看「境外基金代碼」。
        _tdcc(monkeypatch, [{"基金代碼": "OTHER1", "境外基金代碼": CODE, "基金名稱": "甲", "計價幣別": "USD"}])
        # 2026-10-14：0 命中改叫 code_unmapped（舊斷言 == "not_listed"；有意識的更正，不是漏刪）
        assert dp.fetch_tdcc_listing(CODE)["status"] == "code_unmapped"

    def test_identical_duplicates_are_ok(self, monkeypatch):
        row = {"基金代碼": CODE, "基金名稱": "甲", "計價幣別": "USD"}
        _tdcc(monkeypatch, [dict(row), dict(row)])
        r = dp.fetch_tdcc_listing(CODE)
        assert r["status"] == "ok" and r["match_count"] == 2

    def test_non_json_200_is_server_error_kind(self, monkeypatch):
        _tdcc(monkeypatch, [], error="JSONDecodeError: Expecting value: line 1 column 1 (char 0)")
        r = dp.fetch_tdcc_listing(CODE)
        assert r["status"] == "failed" and r["attempts"][0]["fail_kind"] == "server_error"
        assert sb.should_skip("openapi.tdcc.com.tw")[2] == "server_error"

    def test_observed_at_is_first_observation_of_same_list(self, monkeypatch, clock):
        _tdcc(monkeypatch, TDCC_ROWS)
        a = dp.fetch_tdcc_listing(CODE)
        b = dp.fetch_tdcc_listing("AAA01")        # 不同 key、同一份清單物件
        assert a["observed_at"] == b["observed_at"]
        _tdcc(monkeypatch, list(TDCC_ROWS))       # 換成另一份清單物件（快取被換掉）
        c = dp.fetch_tdcc_listing("ZZZ99")
        assert c["observed_at"] != a["observed_at"]

    def test_cache_hit_keeps_observed_at(self, monkeypatch, clock):
        _tdcc(monkeypatch, TDCC_ROWS)
        a = dp.fetch_tdcc_listing(CODE)
        b = dp.fetch_tdcc_listing(CODE)
        assert a["observed_at"] == b["observed_at"]

    def test_ambiguous_duplicate_code_is_failed(self, monkeypatch):
        _tdcc(monkeypatch, [{"基金代碼": CODE, "基金名稱": "甲", "計價幣別": "USD"},
                            {"基金代碼": CODE, "基金名稱": "甲", "計價幣別": "TWD"}])
        r = dp.fetch_tdcc_listing(CODE)
        assert r["status"] == "failed" and r["match_count"] == 2


# ═════════════════════════════ FundClear ═════════════════════════════

FC_URL = ("https://www.fundclear.com.tw/SmartFundAPI/api/FundAjax"
          f"/GetFundBasicInfo?FundCode={CODE}")


class TestFundClear:
    def test_reads_currency_from_data(self, monkeypatch):
        _net(monkeypatch, {FC_URL: ("json", {"Data": {"FundName": "甲", "Currency": "USD"}})})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert r["status"] == "ok"
        assert r["fields"] == {"currency": "USD"} and r["currency_key"] == "Currency"
        assert r["provenance"]["url"] == FC_URL

    def test_lowercase_currency_key_recorded(self, monkeypatch):
        _net(monkeypatch, {FC_URL: ("json", {"Data": [{"currency": "歐元"}]})})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert r["fields"]["currency"] == "歐元" and r["currency_key"] == "currency"

    def test_without_data_key_outer_payload_is_not_read(self, monkeypatch):
        _net(monkeypatch, {FC_URL: ("json", {"Currency": "USD", "FundName": "冒充", "data": {"Currency": "JPY"}})})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert r["status"] == "failed"
        assert r["fields"]["currency"] is None
        assert "USD" not in json.dumps(r["fields"]) and r["attempts"][0]["outcome"] == "no_data_key"

    def test_missing_currency_is_none_not_zero(self, monkeypatch):
        _net(monkeypatch, {FC_URL: ("json", {"Data": {"FundName": "甲", "Currency": ""}})})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert r["status"] == "ok" and r["fields"]["currency"] is None and r["currency_key"] is None

    def test_inception_date_is_not_read(self, monkeypatch):
        _net(monkeypatch, {FC_URL: ("json", {"Data": {"Currency": "USD", "InceptionDate": "2001-01-01"}})})
        assert "2001" not in json.dumps(dp.fetch_fundclear_declared_ccy(CODE))

    def test_null_data_is_not_listed_and_cached(self, monkeypatch):
        net = _net(monkeypatch, {FC_URL: ("json", {"Data": None})})
        assert dp.fetch_fundclear_declared_ccy(CODE)["status"] == "not_listed"
        dp.fetch_fundclear_declared_ccy(CODE)
        assert net.calls == [FC_URL]

    @pytest.mark.parametrize("payload,outcome", [
        ({"Data": [{"Currency": "USD"}, {"Currency": "TWD"}]}, "data_ambiguous"),
        ({"Data": {"FundCode": "OTHER", "Currency": "USD"}}, "code_mismatch"),
        ({"Data": "x"}, "data_not_dict"),
        ([1, 2], "no_data_key"),
    ])
    def test_shape_failures(self, monkeypatch, payload, outcome):
        _net(monkeypatch, {FC_URL: ("json", payload)})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert r["status"] == "failed" and r["attempts"][0]["outcome"] == outcome
        assert r["fields"]["currency"] is None

    def test_404_is_failed_not_cached(self, monkeypatch, mclock):
        net = _net(monkeypatch, {FC_URL: ("fail", "not_found")})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert r["status"] == "failed" and r["attempts"][0]["fail_kind"] == "not_found"
        mclock["t"] += dp.FAILURE_MEMORY_SEC + 1   # 2026-10-14 修正輪：failed 先進失敗記憶，過期後才重打
        dp.fetch_fundclear_declared_ccy(CODE)
        assert net.calls == [FC_URL, FC_URL]

    @pytest.mark.parametrize("payload", [
        {"Data": None, "Message": "查無資料", "Success": False},
        {"Data": {"Currency": "USD"}, "Success": False},
        {"Data": None, "Message": "系統錯誤"},
        {"Data": [], "message": "error"},
        {"Data": {"Currency": "USD"}, "IsSuccess": False},
        {"Data": {"Currency": "USD"}, "isSuccess": False},
        {"Data": {"Currency": "USD"}, "success": False},
        {"Data": {"Currency": "USD"}, "Success": "false"},
        {"Data": {"Currency": "USD"}, "Success": " FALSE "},
        {"Data": {"Currency": "USD"}, "IsSuccess": "False"},
    ], ids=["Success_False_null", "Success_False_data", "msg_null", "msg_empty_list",
            "IsSuccess", "isSuccess", "lower_success", "str_false", "str_FALSE_padded", "str_False_IsSuccess"])
    def test_error_flag_is_failed_not_not_listed(self, monkeypatch, payload):
        _net(monkeypatch, {FC_URL: ("json", payload)})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert r["status"] == "failed" and r["attempts"][0]["outcome"] == "error_flag"

    @pytest.mark.parametrize("value", [0, "0", "no", None, True, "true"])
    def test_other_non_bool_success_values_are_not_error_flags(self, monkeypatch, value):
        _net(monkeypatch, {FC_URL: ("json", {"Data": {"Currency": "USD"}, "Success": value})})
        assert dp.fetch_fundclear_declared_ccy(CODE)["status"] == "ok"

    @pytest.mark.parametrize("empty", [{}, []])
    def test_empty_data_container_is_not_listed(self, monkeypatch, empty):
        _net(monkeypatch, {FC_URL: ("json", {"Data": empty})})
        assert dp.fetch_fundclear_declared_ccy(CODE)["status"] == "not_listed"

    def test_lowercase_fundcode_mismatch(self, monkeypatch):
        _net(monkeypatch, {FC_URL: ("json", {"Data": {"fundCode": "OTHER1", "Currency": "USD"}})})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert r["status"] == "failed" and r["attempts"][0]["outcome"] == "code_mismatch"

    def test_non_json_is_failed(self, monkeypatch):
        _net(monkeypatch, {FC_URL: ("html", "<html>維護中</html>")})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert r["status"] == "failed" and r["attempts"][0]["outcome"] == "exception"
        assert "JSONDecodeError" in r["error"]

    def test_cooldown_not_fetched(self, monkeypatch):
        sb.record_failure("www.fundclear.com.tw", "server_error")
        net = _net(monkeypatch, {FC_URL: ("json", {"Data": {"Currency": "USD"}})})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert net.calls == [] and r["status"] == "failed"
        assert r["attempts"][0]["fail_kind"] == "cooldown"

    def test_fetched_at_unchanged_on_cache_hit(self, monkeypatch, clock):
        _net(monkeypatch, {FC_URL: ("json", {"Data": {"Currency": "USD"}})})
        a = dp.fetch_fundclear_declared_ccy(CODE)
        b = dp.fetch_fundclear_declared_ccy(CODE)
        assert a["fetched_at"] and a["fetched_at"] == b["fetched_at"]


# ═════════════════════ 2026-10-14 C2：MoneyDJ 表格與代碼的綁定 ═════════════════════

def _bind_page(table_extra_rows: str = "", *, outside: str = "", nested: str = "") -> str:
    """含基金名稱那張表；代碼放在哪裡由參數決定。`outside`：表外（例如導覽列）的可見文字；
    `nested`：巢狀在那張表某一格裡的內層表。"""
    nested_row = f"<tr><td>附表</td><td><table>{nested}</table></td></tr>" if nested else ""
    return (f"<html><body>{_PAD}<div class='nav'>{outside}</div>"
            f"<table>{_row2('基金名稱', '某基金')}{table_extra_rows}{nested_row}</table>"
            f"<table>{_row2('其他', '別的表')}</table></body></html>")


class TestMoneyDJBinding:
    def test_表內有代碼_綁定為真(self, monkeypatch):
        _net(monkeypatch, {U1: ("html", _bind_page(_row2("基金代碼", CODE)))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "ok"
        # 2026-10-14 身分判準修訂（有意識的更正，不是漏刪；決策者 AI 總管；依據 #961 探測報告）：
        # binding 多了新判準的欄位；舊兩鍵保留為附加資訊。舊斷言：binding == {兩個舊鍵: True}。
        assert r["binding"] == {"method": dp.MONEYDJ_BINDING_METHOD, "identity_confirmed": True,
                                "name_table_count": 1, "populated_name_table_count": 1, "name_nonempty": True,
                                "code_in_label_table": True, "code_in_page_text": True}

    def test_表內代碼大小寫不分(self, monkeypatch):
        _net(monkeypatch, {U1: ("html", _bind_page(_row2("基金代碼", CODE.lower())))})
        assert dp.fetch_moneydj_basic_fields(CODE)["binding"]["code_in_label_table"] is True

    def test_代碼只在導覽列_ok但未綁定(self, monkeypatch):
        _net(monkeypatch, {U1: ("html", _bind_page(outside=CODE))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "ok"
        # 2026-10-14：舊斷言 binding == {"code_in_label_table": False, "code_in_page_text": True}（新增鍵，舊鍵值不變）
        assert r["binding"]["code_in_label_table"] is False and r["binding"]["code_in_page_text"] is True
        assert r["binding"]["identity_confirmed"] is True

    def test_代碼只在別張表_未綁定(self, monkeypatch):
        page = _bind_page().replace("別的表", CODE)
        _net(monkeypatch, {U1: ("html", page)})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "ok" and r["binding"]["code_in_label_table"] is False

    def test_代碼只在巢狀內層表_未綁定(self, monkeypatch):
        _net(monkeypatch, {U1: ("html", _bind_page(nested=_row2("代碼", CODE)))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "ok" and r["binding"]["code_in_label_table"] is False

    def test_TLZF90不命中TLZF9(self, monkeypatch):
        _net(monkeypatch, {U1: ("html", _bind_page(_row2("基金代碼", "TLZF90"), outside=CODE))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "ok" and r["binding"]["code_in_label_table"] is False

    def test_既有頁面樣本_代碼在表外連結_未綁定(self, monkeypatch):
        # `_page` 把代碼放在表外的 <a>（C1 的樣本形狀）：ok 但未綁定 —— L2 會判三欄資料未備
        _net(monkeypatch, {U1: ("html", _page(FULL_TABLE))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "ok" and r["binding"]["code_in_label_table"] is False

    def test_failed結果沒有binding鍵(self, monkeypatch):
        _net(monkeypatch, {})
        assert "binding" not in dp.fetch_moneydj_basic_fields(CODE)

    def test_parse_label_table_with_node交回表格節點(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(_bind_page(_row2("基金代碼", CODE)), "lxml")
        fields, conflicts, tbl = dp._parse_label_table_with_node(soup)
        assert fields["基金名稱"] == "某基金" and conflicts == [] and tbl is soup.find_all("table")[0]
        assert dp._parse_label_table_with_node(BeautifulSoup("<p>x</p>", "lxml")) == (None, [], None)

    def test_parse_label_table維持C1的兩值介面(self):
        # 2026-10-14 稽核 W（BLOCKING）：平行的 #961 探測腳本以兩個值接收，介面不得再改
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(_bind_page(_row2("基金代碼", CODE)), "lxml")
        out = dp._parse_label_table(soup)
        assert isinstance(out, tuple) and len(out) == 2
        assert out == dp._parse_label_table_with_node(soup)[:2]
        assert dp._parse_label_table(BeautifulSoup("<p>x</p>", "lxml")) == (None, [])


# ═════════════════════ 2026-10-14 C2：reset_tdcc_list_cache_if_empty ═════════════════════

class TestResetTdccEmpty:
    def test_只丟空清單(self):
        src._tdcc_cache["3-2"] = []
        src._tdcc_cache["3-1"] = []
        assert dp.reset_tdcc_list_cache_if_empty() is True
        assert "3-2" not in src._tdcc_cache and src._tdcc_cache["3-1"] == []   # 其他端點不動

    def test_非空清單不動(self):
        data = [{"基金代碼": CODE}]
        src._tdcc_cache["3-2"] = data
        assert dp.reset_tdcc_list_cache_if_empty() is False
        assert src._tdcc_cache["3-2"] is data

    def test_沒有這一筆_回False(self):
        assert dp.reset_tdcc_list_cache_if_empty() is False and src._tdcc_cache == {}

    def test_丟掉後下一次真的重試(self, monkeypatch):
        src._tdcc_cache["3-2"] = []
        assert dp.fetch_tdcc_listing(CODE)["status"] == "failed"
        dp.fetch_tdcc_listing.cache_clear()          # 公開 cache_clear 連同失敗記憶一起清
        dp.reset_tdcc_list_cache_if_empty()
        calls = []

        def fake_get(ep, *, error_out=None):
            calls.append(ep)
            src._tdcc_cache[ep] = [{"基金代碼": CODE, "基金名稱": "某基金", "計價幣別": "USD"}]
            return src._tdcc_cache[ep]
        monkeypatch.setattr(src, "_tdcc_get", fake_get)
        assert dp.fetch_tdcc_listing(CODE)["status"] == "ok" and calls == ["3-2"]



# ═════════════════════ 2026-10-14 身分判準修訂：真實頁面 golden fixture ═════════════════════
#
# 來源：#961 探測報告 `origin/probe/moneydj-basic-results:results/20261014T101710Z_run38548232056/report.json`
# （GitHub runner 直連；與 production 經 NAS 代理的路徑不同，**是否相同未驗**）。
# `tests/fixtures/moneydj_basic/` 逐頁存 gzip 後的原始位元組（big5；gzip 是為了不讓 pre-commit 的空白修正動到內容）；
# 真實代碼頁的 sha256 與報告逐頁相同（見 `manifest.json`，本段有測試核對）。負控代碼頁裡的代碼已換成 `__CODE__`，
# 測試在執行時現編一個代碼代回去（本檔不寫任何具體的負控代碼）。

import gzip as _gzip  # noqa: E402
import hashlib as _hashlib  # noqa: E402
import pathlib as _pathlib  # noqa: E402
import uuid as _uuid  # noqa: E402

_FIX = _pathlib.Path(__file__).parent / "fixtures" / "moneydj_basic"
_REAL_IS_DOMESTIC = src._is_domestic_code          # 模組載入時的真函式（autouse 夾具會換掉它）

#: 報告實測的四欄原字面（已去頭尾空白／`\xa0`）。8/8 成立日期補零 YYYY/MM/DD、幣別「美元」；JFZA6 配息頻率空白。
GOLDEN = {
    "ACCP138": ("yp011000", "瀚亞多重收益優化組合基金B配息(美元)(本基金得投資於非投資等級之高風險債券基金且配息來源可能為本金)",
                "美元", "月配", "2018/09/26"),
    "ACTI71": ("yp011000", "聯博多元資產收益組合基金AI配息(美元)(本基金得投資於非投資等級之高風險債券基金且配息來源可能為本金及收益平準金)",
               "美元", "月配", "2018/01/16"),
    "JFZN3": ("yp011001", "摩根投資基金-多重收益基金A股(美元對沖)(穩定月配)(本基金有相當比重投資於非投資等級之高風險債券且配息來源可能為本金)",
              "美元", "月配", "2021/07/02"),
    "JFZA6": ("yp011001", "摩根投資基金-多重收益基金A股(美元對沖)(累計)(本基金有相當比重投資於非投資等級之高風險債券)",
              "美元", "", "2012/05/30"),
    "JFZA5": ("yp011001", "摩根投資基金-多重收益基金A股(美元對沖)(每月派息)(本基金有相當比重投資於非投資等級之高風險債券且配息來源可能為本金)",
              "美元", "月配", "2012/08/31"),
    "JFZA3": ("yp011001", "摩根投資基金-多重收益基金A股(美元對沖)(每季派息)(本基金有相當比重投資於非投資等級之高風險債券且配息來源可能為本金)",
              "美元", "季配", "2012/01/13"),
    "JFZK2": ("yp011001", "摩根投資基金-多重收益基金A股(美元對沖)(利率入息)(本基金有相當比重投資於非投資等級之高風險債券且配息來源可能為本金)",
              "美元", "月配", "2018/03/26"),
    "TLZF9": ("yp011001", "安聯收益成長基金-AMg7月收總收益類股(美元)(本基金有相當比重投資於非投資等級之高風險債券且配息來源可能為本金)",
              "美元", "月配", "2020/02/03"),
}
_OTHER = {"yp011000": "yp011001", "yp011001": "yp011000"}


def _fixture_bytes(name: str) -> bytes:
    return _gzip.decompress((_FIX / name).read_bytes())


def _fixture_html(name: str, code: str = "") -> str:
    """同 requests 對 MoneyDJ 的解碼（`fetch_url_with_retry` 設 big5，`.text` 用 errors="replace"）。"""
    text = _fixture_bytes(name).decode("big5", errors="replace")
    return text.replace("__CODE__", code) if code else text


def _invented_code() -> str:
    """測試內現編的不存在代碼（每次執行都不同，不寫進任何檔案）。"""
    return "Q" + _uuid.uuid4().hex[:9].upper()


def _real_routes(code: str, *, drop_preferred=False, preferred_override=None) -> dict:
    """照報告實測：tcbbankfund 兩頁型 404、www 兩頁型回 fixture。"""
    pref = GOLDEN[code][0]
    sec = _OTHER[pref]
    routes = {_mdj(TCB, pref, code): ("fail", "not_found"), _mdj(TCB, sec, code): ("fail", "not_found"),
              _mdj(WWW, pref, code): ("html", _fixture_html(f"moneydj_{code}_{pref}.html.gz")),
              _mdj(WWW, sec, code): ("html", _fixture_html(f"moneydj_{code}_{sec}.html.gz"))}
    if drop_preferred:
        routes[_mdj(WWW, pref, code)] = ("fail", "not_found")
    if preferred_override is not None:
        routes[_mdj(WWW, pref, code)] = preferred_override
    return routes


class TestGoldenFixtureFiles:
    def test_manifest與檔案一致_真實頁sha256與報告相同_單檔小於100KB(self):
        manifest = json.loads((_FIX / "manifest.json").read_text(encoding="utf-8"))
        files = sorted(p.name for p in _FIX.glob("*.html.gz"))
        assert files == sorted(e["file"] for e in manifest["pages"]) and len(files) == 18
        for e in manifest["pages"]:
            raw = _fixture_bytes(e["file"])
            assert _hashlib.sha256(raw).hexdigest() == e["fixture_raw_sha256"]
            if e["kind"] == "real_code":
                assert e["fixture_raw_sha256"] == e["report_raw_sha256"]
            assert (_FIX / e["file"]).stat().st_size < 100_000
        kinds = [e["kind"] for e in manifest["pages"]]
        assert kinds.count("real_code") == 16 and kinds.count("negative_control") == 2

    def test_真實頁面可見文字不印代碼_代碼只在屬性或script(self):
        from bs4 import BeautifulSoup
        for code, (pref, *_rest) in GOLDEN.items():
            html = _fixture_html(f"moneydj_{code}_{pref}.html.gz")
            assert code in html                                           # 有回顯（href／onclick／script）
            assert dp._mentions_code(BeautifulSoup(html, "lxml"), code) is False


class TestGoldenMoneyDJ:
    @pytest.mark.parametrize("code", sorted(GOLDEN))
    def test_八個真實代碼全部ok_四欄原字面正確(self, monkeypatch, code):
        monkeypatch.setattr(src, "_is_domestic_code", _REAL_IS_DOMESTIC)
        pref, name, ccy, freq, inception = GOLDEN[code]
        net = _net(monkeypatch, _real_routes(code))
        r = dp.fetch_moneydj_basic_fields(code)
        assert r["status"] == "ok", r.get("reason")
        assert r["fields"] == {"基金名稱": name, "計價幣別": ccy, "配息頻率": freq, "成立日期": inception}
        assert all("\xa0" not in v for v in r["fields"].values())       # 境外頁幣別尾端的 &nbsp; 已去掉
        assert r["provenance"] == {"host": WWW, "page_type": pref, "url": _mdj(WWW, pref, code)}
        assert net.calls == [_mdj(TCB, pref, code), _mdj(WWW, pref, code)]
        assert r["binding"] == {"method": dp.MONEYDJ_BINDING_METHOD, "identity_confirmed": True,
                                "name_table_count": 1, "populated_name_table_count": 1, "name_nonempty": True,
                                "code_in_label_table": False, "code_in_page_text": False}   # 舊兩條件照實 0/8

    def test_空殼頁與無資料頁_判unrecognized不是failed(self, monkeypatch):
        neg = _invented_code()
        shell = _fixture_html("moneydj_shell_page.html.gz", neg)
        no_data = _fixture_html("moneydj_no_data_page.html.gz", neg)
        assert neg in shell and "__CODE__" not in shell
        # 報告實測的形狀：首選頁型 www 回「無資料」、另一頁型 www 回空殼、tcbbankfund 都 404
        _net(monkeypatch, {U1: ("fail", "not_found"), U2: ("html", no_data),
                           U3: ("fail", "not_found"), U4: ("html", shell)})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "unrecognized_page"
        assert [a["outcome"] for a in r["attempts"]] == ["not_found_404", "unrecognized_page",
                                                          "not_found_404", "unrecognized_page"]
        assert "頁面可見文字僅「無資料」" in r["attempts"][1]["problem"]
        assert "頁面沒有含「基金名稱」標籤的表" in r["attempts"][3]["problem"]
        assert r["fields"] == {lb: None for lb in dp.MONEYDJ_LABELS} and r["fetched_at"] is None
        assert "binding" not in r

    @pytest.mark.parametrize("code", ["ACCP138", "ACTI71"])
    def test_境內代碼打到境外頁型_空名稱表_title有名稱也不採用(self, monkeypatch, code):
        from bs4 import BeautifulSoup
        monkeypatch.setattr(src, "_is_domestic_code", _REAL_IS_DOMESTIC)
        wrong = _fixture_html(f"moneydj_{code}_yp011001.html.gz")
        assert GOLDEN[code][1][:10] in BeautifulSoup(wrong, "lxml").title.get_text()   # title 帶名稱
        _net(monkeypatch, _real_routes(code, drop_preferred=True))
        r = dp.fetch_moneydj_basic_fields(code)
        assert r["status"] == "unrecognized_page"
        att = r["attempts"][3]
        assert att["page_type"] == "yp011001" and att["outcome"] == "unrecognized_page"
        assert "基金名稱欄為空白" in att["problem"]
        assert att["identity_check"]["name_table_count"] == 1
        assert att["identity_check"]["populated_name_table_count"] == 0

    def test_境外代碼打到境內頁型_空殼_不採用(self, monkeypatch):
        monkeypatch.setattr(src, "_is_domestic_code", _REAL_IS_DOMESTIC)
        _net(monkeypatch, _real_routes("TLZF9", drop_preferred=True))
        r = dp.fetch_moneydj_basic_fields("TLZF9")
        assert r["status"] == "unrecognized_page"
        assert "頁面沒有含「基金名稱」標籤的表" in r["attempts"][3]["problem"]

    def test_兩張非空基金名稱表_不採用(self, monkeypatch):
        html = _fixture_html("moneydj_TLZF9_yp011001.html.gz")
        dup = ("<table><tr><td>基金名稱</td><td>另一檔基金</td></tr>"
               "<tr><td>計價幣別</td><td>歐元</td></tr></table>")
        html2 = html.replace("</body>", dup + "</body>", 1)
        assert html2 != html
        _net(monkeypatch, {U2: ("html", html2), U4: ("html", html2)})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "unrecognized_page"
        assert "2 張含「基金名稱」標籤的表（其中 2 張非空白）" in r["attempts"][1]["problem"]

    def test_一張非空加一張空白名稱表_也不採用(self, monkeypatch):
        html = _fixture_html("moneydj_TLZF9_yp011001.html.gz")
        html2 = html.replace("</body>", "<table><tr><td>基金名稱</td><td>&nbsp;</td></tr></table></body>", 1)
        _net(monkeypatch, {U2: ("html", html2)})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "unrecognized_page"
        assert "（其中 1 張非空白）" in r["attempts"][1]["problem"]

    def test_名稱只有nbsp_算空白(self, monkeypatch):
        page = _page(_row2("基金名稱", "&nbsp;　 ") + _row2("計價幣別", "美元"))
        _net(monkeypatch, {U1: ("html", page)})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "unrecognized_page" and "基金名稱欄為空白" in r["attempts"][0]["problem"]

    def test_首選頁網路例外_其餘照實_failed(self, monkeypatch):
        monkeypatch.setattr(src, "_is_domestic_code", _REAL_IS_DOMESTIC)
        routes = _real_routes("TLZF9")
        target = _mdj(WWW, "yp011001", "TLZF9")

        def fetch(url, **k):
            proxy_mod._TLS_FAIL.kind = ""
            if url == target:
                raise ConnectionError("連線被重置")
            spec = routes[url]
            if spec[0] == "fail":
                proxy_mod._TLS_FAIL.kind = spec[1]
                return None
            return _Resp(text=spec[1])
        monkeypatch.setattr(dp, "fetch_url_with_retry", fetch)
        r = dp.fetch_moneydj_basic_fields("TLZF9")
        assert r["status"] == "failed"
        assert "ConnectionError: 連線被重置" in r["error"] and "連線被重置" in r["reason"]

    @pytest.mark.parametrize("kind", ["server_error", "unreachable", "blocked", "rate_limited", "proxy_auth"])
    def test_首選頁取不到_另一頁空殼_仍是failed不是unrecognized(self, monkeypatch, kind):
        monkeypatch.setattr(src, "_is_domestic_code", _REAL_IS_DOMESTIC)
        _net(monkeypatch, _real_routes("TLZF9", preferred_override=("fail", kind)))
        r = dp.fetch_moneydj_basic_fields("TLZF9")
        assert r["status"] == "failed"                                    # 沒讀到的那一頁可能正是本檔
        assert [a["outcome"] for a in r["attempts"]] == ["not_found_404", "http_failed",
                                                          "not_found_404", "unrecognized_page"]

    def test_主機冷卻中_其餘不符_仍是failed(self, monkeypatch):
        sb.record_failure(WWW, "server_error")
        _net(monkeypatch, {})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "failed"
        assert "主機冷卻中" in r["reason"]

    def test_全部404_not_found_原因逐網址(self, monkeypatch):
        _net(monkeypatch, {})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "not_found"
        assert r["reason"].count("HTTP 404") == 4
        for host in (TCB, WWW):
            for page in ("yp011001", "yp011000"):
                assert f"{page}@{host}：HTTP 404" in r["reason"]

    def test_unrecognized進短期記憶_不進成功快取(self, monkeypatch, mclock):
        neg = _invented_code()
        shell = _fixture_html("moneydj_shell_page.html.gz", neg)
        net = _net(monkeypatch, {U2: ("html", shell), U4: ("html", shell)})
        assert dp.fetch_moneydj_basic_fields(CODE)["status"] == "unrecognized_page"
        again = dp.fetch_moneydj_basic_fields(CODE)
        assert len(net.calls) == 4 and again["cooling"] is True and again["status"] == "unrecognized_page"
        assert dp.fetch_moneydj_basic_fields.cache_info()["size"] == 0
        mclock["t"] += dp.FAILURE_MEMORY_SEC + 1
        dp.fetch_moneydj_basic_fields(CODE)
        assert len(net.calls) == 8

    @pytest.mark.parametrize("text, want", [("\xa0", True), ("\xa0 \xa0　", True), ("", True),
                                            ("\xa0甲\xa0", False), ("甲", False)])
    def test_blank_去除nbsp與空白後判空(self, text, want):
        assert dp._blank(text) is want
