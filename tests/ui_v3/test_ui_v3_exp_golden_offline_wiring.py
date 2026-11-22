# -*- coding: utf-8 -*-
"""🔍 找基金：MoneyDJ golden fixture 離線接線測試（B-EXP-GOLDEN-OFFLINE-S1；**tests-only**）。

證明：真實 MoneyDJ 頁面位元組（`tests/fixtures/moneydj_basic/`，探測 run 38548232056）
→ 真 L1 `declared_profile.fetch_moneydj_basic_fields` → 真 L2 `exp_profile.build_profiles`
→ ui_v3 adapter `lookup_fund` → 五欄（輸入代碼、名稱、配息方式、成立日期、經理費）與各狀態，**全程離線**。

邊界（本檔自己驗，見 `TestBoundaries`）：不改 production；`ui_v3/` 任何 production 檔不得引用本批輔助檔或 `tests/fixtures`；
`ui_v3/app_preview.py` 無 golden／真來源分支；不讀 secrets／NAS 代理設定；0 次真實網路請求。
⚠️ 這是 golden **離線證明**，不是真來源接線；真實來源行為、NAS／TLS、Cloud 均 NOT VERIFIED。

本機執行：
    pytest tests/ui_v3/test_ui_v3_exp_golden_offline_wiring.py -q -p no:cacheprovider
負控字串（不存在的代碼、毒字串）一律在測試中現編，不寫死。
"""
from __future__ import annotations

import ast
import pathlib
import re
import uuid

import pytest

import exp_golden_loader as G
import fund_lookup_support as S
import infra.proxy as proxy_mod
import repositories.fund.declared_profile as dp
from fund_lookup_support import no_real_network  # noqa: F401 - autouse fixture
from services.v2_tables import exp_profile as ep
from ui_v3.adapters import fund_lookup as adapter
from ui_v3.adapters.fund_lookup import lookup_fund, not_queried
from ui_v3.viewmodels.fund_lookup import (
    PAGE_UNMATCHED_REASONS,
    REASON_BLANK,
    REASON_CONTROL_OR_NON_ASCII,
    REASON_ISIN_SHAPE,
    REASON_KEY_REJECTED,
    REASON_LOADER_IO_ERROR,
    REASON_NO_PAGE,
    REASON_SOURCE_COOLING,
    REASON_SOURCE_FAILED,
    REASON_UNRECOGNIZED_PAGE,
    REASON_URL_SHAPE,
    FieldStatus,
    FundLookupView,
    LookupContractError,
    LookupSourceError,
    LookupState,
)

REPO = pathlib.Path(__file__).resolve().parents[2]

#: 代碼 → (名稱, 配息頻率原字面, 成立日期 ISO)。與 manifest 真實頁位元組逐一對照（`TestGoldenFiles` 核 sha256；
#: 預期值本身由 `TestResultMatrix` 對「真解析碼的輸出」比對，不是循環自證）。
EXPECTED = {
    "ACCP138": ("瀚亞多重收益優化組合基金B配息(美元)(本基金得投資於非投資等級之高風險債券基金且配息來源可能為本金)", "月配", "2018-09-26"),
    "ACTI71": ("聯博多元資產收益組合基金AI配息(美元)(本基金得投資於非投資等級之高風險債券基金且配息來源可能為本金及收益平準金)", "月配", "2018-01-16"),
    "JFZN3": ("摩根投資基金-多重收益基金A股(美元對沖)(穩定月配)(本基金有相當比重投資於非投資等級之高風險債券且配息來源可能為本金)", "月配", "2021-07-02"),
    "JFZA6": ("摩根投資基金-多重收益基金A股(美元對沖)(累計)(本基金有相當比重投資於非投資等級之高風險債券)", "", "2012-05-30"),
    "JFZA5": ("摩根投資基金-多重收益基金A股(美元對沖)(每月派息)(本基金有相當比重投資於非投資等級之高風險債券且配息來源可能為本金)", "月配", "2012-08-31"),
    "JFZA3": ("摩根投資基金-多重收益基金A股(美元對沖)(每季派息)(本基金有相當比重投資於非投資等級之高風險債券且配息來源可能為本金)", "季配", "2012-01-13"),
    "JFZK2": ("摩根投資基金-多重收益基金A股(美元對沖)(利率入息)(本基金有相當比重投資於非投資等級之高風險債券且配息來源可能為本金)", "月配", "2018-03-26"),
    "TLZF9": ("安聯收益成長基金-AMg7月收總收益類股(美元)(本基金有相當比重投資於非投資等級之高風險債券且配息來源可能為本金)", "月配", "2020-02-03"),
}
assert set(EXPECTED) == set(G.GOLDEN_CODES)


# ───────────────────────── 共用夾具 ─────────────────────────

@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """每測試前後清掉 L1 的成功快取／失敗記憶；時鐘換假（失敗記憶用）；代理設定被讀到就失敗。"""
    G.reset_l1_state()
    state = {"t": 1000.0}
    monkeypatch.setattr(dp, "_clock", lambda: state["t"])

    def _proxy_read(*_a, **_k):
        raise AssertionError("離線測試不得讀取代理設定（infra.proxy.get_proxy_config）")
    monkeypatch.setattr(proxy_mod, "get_proxy_config", _proxy_read)
    yield state
    G.reset_l1_state()


@pytest.fixture
def clock(_isolate):
    return _isolate


def install(monkeypatch, routes: dict) -> G.OfflineNet:
    net = G.OfflineNet(routes)
    monkeypatch.setattr(dp, "fetch_url_with_retry", net)
    return net


def _assert_golden_result(code: str, view: FundLookupView) -> None:
    """RESULT 且五欄與預期相符（也是突變負控要「打得紅」的那個斷言）。"""
    name, freq, inception = EXPECTED[code]
    assert view.state is LookupState.RESULT and view.reason_code is None
    assert view.input_code == code
    f = view.fields
    assert f is not None
    assert (f.fund_name.status, f.fund_name.value) == (FieldStatus.VALUE, name)
    assert (f.inception_on.status, f.inception_on.value) == (FieldStatus.VALUE, inception)
    if freq == "":
        assert (f.dividend_policy.status, f.dividend_policy.value) == (FieldStatus.MISSING, None)
    else:
        assert (f.dividend_policy.status, f.dividend_policy.value) == (FieldStatus.VALUE, ep.DIVIDEND_POLICY_DIST)
    assert (f.mgmt_fee_rate_pct.status, f.mgmt_fee_rate_pct.value) == (FieldStatus.MISSING, None)


def _invented_code() -> str:
    return "Q" + uuid.uuid4().hex[:9].upper()


def _unmatched_routes(code: str, name: str) -> dict:
    html = G.fixture_html(name, code)
    return {G.mdj_url(host, page, code): ("html", html) for host in (G.WWW,) for page in ("yp011000", "yp011001")}


# ───────────────────────── golden 檔案本身 ─────────────────────────

class TestGoldenFiles:
    def test_manifest_sha256_與位元組一致_八個真實代碼(self):
        m = G.manifest()
        real_codes = {e["code"] for e in m["pages"] if e["kind"] == "real_code"}
        assert real_codes == set(G.GOLDEN_CODES)
        for e in m["pages"]:
            assert G.sha256_of(e["file"]) == e["fixture_raw_sha256"]

    def test_兩種頁型的檔都在_首選頁型表與manifest一致(self):
        files = {e["file"] for e in G.manifest()["pages"]}
        for code in G.GOLDEN_CODES:
            for page in ("yp011000", "yp011001"):
                assert f"moneydj_{code}_{page}.html.gz" in files
            assert G.PREFERRED_PAGE[code] in ("yp011000", "yp011001")

    def test_負控頁只有佔位_不含任何真實代碼(self):
        raw = {n: G.fixture_html(n) for n in ("moneydj_no_data_page.html.gz", "moneydj_shell_page.html.gz")}
        assert "__CODE__" in raw["moneydj_shell_page.html.gz"]
        for html in raw.values():
            assert not any(code in html for code in G.GOLDEN_CODES)


# ───────────────────────── RESULT：八個真實代碼 → 五欄 ─────────────────────────

class TestResultMatrix:
    @pytest.mark.parametrize("code", G.GOLDEN_CODES)
    def test_五欄與預期相符_且只請求兩個本機替身網址(self, monkeypatch, code):
        net = install(monkeypatch, G.golden_routes(code))
        loader = G.GoldenLoader()
        view = lookup_fund(loader, code)
        _assert_golden_result(code, view)
        pref = G.preferred_page(code)
        assert net.calls == [G.mdj_url(G.TCB, pref, code), G.mdj_url(G.WWW, pref, code)]
        assert loader.calls == [code]

    def test_前後空白輸入_以去空白後的代碼送出_仍得同一組欄位(self, monkeypatch):
        install(monkeypatch, G.golden_routes("ACCP138"))
        loader = G.GoldenLoader()
        view = lookup_fund(loader, "  ACCP138 ")
        assert loader.calls == ["ACCP138"] and view.state is LookupState.RESULT
        name, _freq, inception = EXPECTED["ACCP138"]
        assert (view.fields.fund_name.value, view.fields.inception_on.value) == (name, inception)

    def test_JFZA6_配息頻率空白_配息方式為MISSING_不補值(self, monkeypatch):
        install(monkeypatch, G.golden_routes("JFZA6"))
        view = lookup_fund(G.GoldenLoader(), "JFZA6")
        _assert_golden_result("JFZA6", view)
        assert view.fields.dividend_policy.status is FieldStatus.MISSING

    def test_經理費五欄之一恆MISSING_不以最高經理費代替(self, monkeypatch):
        """真頁面有「最高經理費」類標籤時，adapter 仍只回 MISSING（比對 view，不拿含時間戳的 dump 做子字串判斷）。"""
        for code in G.GOLDEN_CODES:
            G.reset_l1_state()
            install(monkeypatch, G.golden_routes(code))
            fee = lookup_fund(G.GoldenLoader(), code).fields.mgmt_fee_rate_pct
            assert (fee.status, fee.value) == (FieldStatus.MISSING, None)


# ───────────────────────── 其餘狀態 ─────────────────────────

class TestStates:
    def test_NOT_QUERIED_未送出_loader與網路皆0次(self, monkeypatch):
        net = install(monkeypatch, G.golden_routes("ACCP138"))
        loader = G.GoldenLoader()
        view = not_queried()
        assert view.state is LookupState.NOT_QUERIED and view.input_code is None and view.fields is None
        assert loader.calls == [] and net.calls == []

    @pytest.mark.parametrize("raw,reason", [
        ("", REASON_BLANK),
        ("   ", REASON_BLANK),
        ("https://example.com/x", REASON_URL_SHAPE),
        ("US0378331005", REASON_ISIN_SHAPE),
        ("基金\u0007", REASON_CONTROL_OR_NON_ASCII),
        ("ＡＢＣ", REASON_CONTROL_OR_NON_ASCII),
    ])
    def test_BLOCKED_入口攔截_loader與網路皆0次(self, monkeypatch, raw, reason):
        net = install(monkeypatch, G.golden_routes("ACCP138"))
        loader = G.GoldenLoader()
        view = lookup_fund(loader, raw)
        assert view.state is LookupState.BLOCKED and view.reason_code == reason and view.fields is None
        assert loader.calls == [] and net.calls == []

    def test_BLOCKED_L2拒絕取數鍵_不取數_網路0次(self, monkeypatch):
        net = install(monkeypatch, G.golden_routes("ACCP138"))
        view = lookup_fund(G.GoldenLoader(key_ok=False), "ACCP138")
        assert view.state is LookupState.BLOCKED and view.reason_code == REASON_KEY_REJECTED and view.fields is None
        assert net.calls == []

    @pytest.mark.parametrize("page_name", ["moneydj_no_data_page.html.gz", "moneydj_shell_page.html.gz"])
    def test_PAGE_UNMATCHED_無資料頁與空殼頁_不宣稱基金不存在(self, monkeypatch, page_name):
        code = _invented_code()
        install(monkeypatch, _unmatched_routes(code, page_name))
        view = lookup_fund(G.GoldenLoader(), code)
        assert view.state is LookupState.PAGE_UNMATCHED and view.reason_code == REASON_UNRECOGNIZED_PAGE
        assert view.reason_code in PAGE_UNMATCHED_REASONS and view.fields is None

    def test_PAGE_UNMATCHED_全部404_是no_page_不是來源失敗(self, monkeypatch):
        code = _invented_code()
        install(monkeypatch, {})
        view = lookup_fund(G.GoldenLoader(), code)
        assert view.state is LookupState.PAGE_UNMATCHED and view.reason_code == REASON_NO_PAGE and view.fields is None

    def test_SOURCE_FAILED_逾時_進入冷卻_時鐘過期後才再打(self, monkeypatch, clock):
        code = _invented_code()
        failing = {G.mdj_url(h, p, code): ("fail", "timeout") for h in (G.WWW, G.TCB) for p in ("yp011000", "yp011001")}
        net = install(monkeypatch, failing)
        first = lookup_fund(G.GoldenLoader(), code)
        assert first.state is LookupState.SOURCE_FAILED and first.reason_code == REASON_SOURCE_FAILED and first.fields is None
        n_first = len(net.calls)
        assert n_first > 0
        second = lookup_fund(G.GoldenLoader(), code)
        assert second.state is LookupState.SOURCE_FAILED and second.reason_code == REASON_SOURCE_COOLING
        assert len(net.calls) == n_first                     # 冷卻中不重打
        clock["t"] += 100_000.0                              # 只動假時鐘；不用當下時間補任何值
        third = lookup_fund(G.GoldenLoader(), code)
        assert third.reason_code in (REASON_SOURCE_FAILED, REASON_SOURCE_COOLING) and third.state is LookupState.SOURCE_FAILED
        assert len(net.calls) > n_first                      # 過期後確實重打

    def test_MISSING_標籤改名_成立日期缺值_其餘欄照常(self, monkeypatch):
        code = "ACCP138"
        pref = G.preferred_page(code)
        html = G.fixture_html(f"moneydj_{code}_{pref}.html.gz").replace("成立日期", "成立日")
        install(monkeypatch, G.golden_routes(code, override={G.mdj_url(G.WWW, pref, code): ("html", html)}))
        view = lookup_fund(G.GoldenLoader(), code)
        assert view.state is LookupState.RESULT
        assert view.fields.inception_on.status is FieldStatus.MISSING and view.fields.inception_on.value is None
        assert view.fields.fund_name.status is FieldStatus.VALUE
        assert view.fields.dividend_policy.status is FieldStatus.VALUE

    def test_同標籤出現不同值_真實鏈路映為MISSING_不是CONFLICT(self, monkeypatch):
        """現行真實 L2 對四欄不產生 `inconsistent`；同標籤不同值走 L1 `label_conflicts` → 該欄 MISSING（adapter 檔頭已揭露）。"""
        code = "ACCP138"
        pref = G.preferred_page(code)
        html = G.fixture_html(f"moneydj_{code}_{pref}.html.gz")
        anchor = "興櫃交易代碼</td><td class=t3t2></td></tr>"
        assert anchor in html
        dup = html.replace(anchor, anchor + "<tr><td class=t2c1 nowrap>成立日期</td><td class=t3t2>2000/01/01</td></tr>", 1)
        install(monkeypatch, G.golden_routes(code, override={G.mdj_url(G.WWW, pref, code): ("html", dup)}))
        raw = dp.fetch_moneydj_basic_fields(code)
        assert any(c.get("label") == "成立日期" for c in raw.get("label_conflicts") or ())      # 機制確實是「同標籤不同值」
        view = lookup_fund(G.GoldenLoader(), code)
        assert view.state is LookupState.RESULT
        assert view.fields.inception_on.status is FieldStatus.MISSING and view.fields.inception_on.value is None

    def test_CONFLICT_只能由L2形狀注入產生_合成注入_非真實鏈路(self, monkeypatch):
        """真實 L2 不可達；此處在 loader 後處理把配息方式格改成 L2 的 `inconsistent` 形狀，僅證明 adapter 這條路徑接得到。"""
        install(monkeypatch, G.golden_routes("ACCP138"))

        def tamper(result: dict) -> dict:
            cell = result["cells"]["ACCP138"]["dividend_policy"]
            cell["status"], cell["value"] = ep.STATUS_INCONSISTENT, None
            return result
        view = lookup_fund(G.GoldenLoader(tamper=tamper), "ACCP138")
        assert view.state is LookupState.RESULT
        assert (view.fields.dividend_policy.status, view.fields.dividend_policy.value) == (FieldStatus.CONFLICT, None)


# ───────────────────────── 錯誤與契約（負控） ─────────────────────────

def _check_unknown_exception_propagates(lookup) -> None:
    """程式／契約錯誤必須原樣往外拋（不得被吞成來源失敗）。"""
    for exc in (KeyError("k"), RuntimeError("r"), ValueError("v"), TypeError("t")):
        def loader(_q, _exc=exc):
            raise _exc
        with pytest.raises(type(exc)):
            lookup(loader, "ACCP138")


class TestErrors:
    def test_未知例外原樣拋出_不轉狀態(self):
        _check_unknown_exception_propagates(lookup_fund)

    @pytest.mark.parametrize("exc", [LookupSourceError("x"), ConnectionError("x"), TimeoutError("x")])
    def test_來源類例外才轉SOURCE_FAILED_且不帶例外文字(self, exc):
        def loader(_q):
            raise exc
        view = lookup_fund(loader, "ACCP138")
        assert view.state is LookupState.SOURCE_FAILED and view.reason_code == REASON_LOADER_IO_ERROR and view.fields is None

    def test_契約破壞_缺cells_raise_LookupContractError(self, monkeypatch):
        install(monkeypatch, G.golden_routes("ACCP138"))
        with pytest.raises(LookupContractError):
            lookup_fund(G.GoldenLoader(tamper=lambda r: {k: v for k, v in r.items() if k != "cells"}), "ACCP138")

    def test_契約破壞_來源狀態不明_raise(self, monkeypatch):
        install(monkeypatch, G.golden_routes("ACCP138"))

        def tamper(result: dict) -> dict:
            result["source_status"]["ACCP138"]["MoneyDJ"]["status"] = "mystery"
            return result
        with pytest.raises(LookupContractError):
            lookup_fund(G.GoldenLoader(tamper=tamper), "ACCP138")

    def test_契約破壞_經理費格被改成ok_raise_不顯示費率(self, monkeypatch):
        install(monkeypatch, G.golden_routes("ACCP138"))

        def tamper(result: dict) -> dict:
            cell = result["cells"]["ACCP138"]["mgmt_fee_rate_pct"]
            cell["status"], cell["value"] = ep.STATUS_OK, 1.5
            return result
        with pytest.raises(LookupContractError):
            lookup_fund(G.GoldenLoader(tamper=tamper), "ACCP138")


# ───────────────────────── 零網路／零設定 ─────────────────────────

class TestZeroNetwork:
    def test_代表性全流程_網路守衛0次_代理設定未讀(self, monkeypatch, no_real_network):
        for code in ("ACCP138", "JFZA6"):
            install(monkeypatch, G.golden_routes(code))
            _assert_golden_result(code, lookup_fund(G.GoldenLoader(), code))
        install(monkeypatch, {})
        lookup_fund(G.GoldenLoader(), _invented_code())
        assert no_real_network == []                          # autouse 守衛的嘗試紀錄

    def test_守衛本身有效_真的碰socket會被擋並記錄(self, no_real_network):
        import socket
        with pytest.raises(S.NetworkAttempt):
            socket.create_connection(("127.0.0.1", 9), timeout=0.01)
        assert no_real_network == ["socket.create_connection"]
        no_real_network.clear()                               # 這一筆是刻意的負控，清掉才不讓 teardown 誤判

    def test_離線替身只回golden位元組_未登錄網址一律404類失敗(self):
        net = G.OfflineNet({})
        assert net("https://example.invalid/x") is None
        assert proxy_mod._TLS_FAIL.kind == "not_found" and net.calls == ["https://example.invalid/x"]


# ───────────────────────── 突變負控：證明上面的斷言「打得紅」 ─────────────────────────

class TestMutationControls:
    def test_把首選頁換成空殼頁_五欄斷言必須失敗(self, monkeypatch):
        code = "ACCP138"
        pref = G.preferred_page(code)
        shell = G.fixture_html("moneydj_shell_page.html.gz", code)
        routes = G.golden_routes(code, override={G.mdj_url(G.WWW, pref, code): ("html", shell),
                                                 G.mdj_url(G.WWW, G.other_page(pref), code): ("html", shell)})
        install(monkeypatch, routes)
        view = lookup_fund(G.GoldenLoader(), code)
        assert view.state is not LookupState.RESULT
        with pytest.raises(AssertionError):
            _assert_golden_result(code, view)

    def test_改一個日期字元_成立日期預期必須失敗(self, monkeypatch):
        code = "ACCP138"
        pref = G.preferred_page(code)
        html = G.fixture_html(f"moneydj_{code}_{pref}.html.gz")
        assert "2018/09/26" in html
        install(monkeypatch, G.golden_routes(code, override={G.mdj_url(G.WWW, pref, code): ("html", html.replace("2018/09/26", "2018/09/27"))}))
        view = lookup_fund(G.GoldenLoader(), code)
        assert view.state is LookupState.RESULT and view.fields.inception_on.value == "2018-09-27"
        with pytest.raises(AssertionError):
            _assert_golden_result(code, view)

    def test_吞例外的錯誤版lookup_必須被傳播斷言抓到(self):
        def swallowing_lookup(loader, raw):                   # 模擬把程式錯誤偽裝成來源失敗的壞實作
            try:
                return lookup_fund(loader, raw)
            except Exception:
                return FundLookupView(LookupState.SOURCE_FAILED, raw, REASON_LOADER_IO_ERROR, None)
        with pytest.raises(BaseException) as info:
            _check_unknown_exception_propagates(swallowing_lookup)
        assert "DID NOT RAISE" in str(info.value) or info.type.__name__ == "Failed"

    def test_golden位元組被改_sha256核對必須失敗(self):
        entry = next(e for e in G.manifest()["pages"] if e["kind"] == "real_code")
        wrong = entry["fixture_raw_sha256"][:-1] + ("0" if entry["fixture_raw_sha256"][-1] != "0" else "1")
        assert G.sha256_of(entry["file"]) != wrong


# ───────────────────────── 邊界（靜態；production 不得沾到本批） ─────────────────────────

def _ui_v3_sources():
    return sorted(p for p in (REPO / "ui_v3").rglob("*.py"))


def _imports(path: pathlib.Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class TestBoundaries:
    def test_ui_v3_production_不引用本批輔助檔_也不引用tests_fixtures(self):
        needles = ("exp_golden_loader", "exp_golden_offline", "tests/fixtures", "moneydj_basic")
        offenders = [str(p.relative_to(REPO)) for p in _ui_v3_sources()
                     if any(n in p.read_text(encoding="utf-8") for n in needles)]
        assert offenders == []

    def test_app_preview_沒有golden或真來源分支(self):
        path = REPO / "ui_v3" / "app_preview.py"
        text = path.read_text(encoding="utf-8").lower()
        assert "golden" not in text and "declared_profile" not in text and "build_profiles" not in text
        banned = {"services", "repositories", "infra", "requests"}
        top = {m.split(".")[0] for m in _imports(path)}
        assert not (top & banned)

    def test_ui_v3_adapter_與其他production檔_不import_L1或L2(self):
        banned = ("services", "repositories", "infra", "requests", "streamlit")
        for rel in ("adapters/fund_lookup.py", "viewmodels/fund_lookup.py"):
            top = {m.split(".")[0] for m in _imports(REPO / "ui_v3" / rel)}
            assert not (top & set(banned)), rel

    def test_本批只有tests檔_且輔助檔不被任何production匯入(self):
        helper = "exp_golden_loader"
        for root in ("ui_v3", "services", "repositories", "infra", "shared", "ui", "app.py"):
            base = REPO / root
            files = [base] if base.is_file() else sorted(base.rglob("*.py")) if base.exists() else []
            for p in files:
                assert helper not in {m.split(".")[-1] for m in _imports(p)}, str(p.relative_to(REPO))

    def test_adapter的L2形狀常數與真L2相同(self):
        """離線輔助走真 L2；若 adapter 另存的 L2 字面與真 L2 漂移，這裡先紅。"""
        assert adapter.L2_CELL_OK == ep.STATUS_OK and adapter.L2_CELL_NOT_READY == ep.STATUS_NOT_READY
        assert adapter.L2_CELL_INCONSISTENT == ep.STATUS_INCONSISTENT and adapter.L2_CELL_FETCH_FAILED == ep.STATUS_FAILED
        assert adapter.L2_SOURCE_OK == dp.STATUS_OK and adapter.L2_SOURCE_FAILED == dp.STATUS_FAILED
        assert adapter.L2_SOURCE_NOT_LISTED == dp.STATUS_NOT_LISTED
        assert re.fullmatch(adapter.L2_PURE_CODE_PATTERN, "ACCP138") is not None
