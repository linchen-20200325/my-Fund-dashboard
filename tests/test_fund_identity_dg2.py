# -*- coding: utf-8 -*-
"""DG-2 Stage-1：C+ canonical fund identity resolver（Shadow Mode）測試。無網路。

客戶裁示 `DEC-2026-10-28-05` 第 10 項指定的驗證：Identity／Platform suffix／Unknown／
External source validation／Cross-View；另加 shadow 輸出形狀、flag-off 無效果、flag-on 不改回傳值。
"""

from __future__ import annotations

import logging

import pytest

import shared.fund_identity as flags
from services import fund_identity as fi
from services import fund_identity_shadow as shadow
from services.v2_tables import fund_keys

TABLE = {"TLZF9": [("fundrwd.entiebank.com.tw", "TLZF9-24A7", "moneydj_wb01"),
                   ("taishinlife.moneydj.com", "TLZF9-AL001", "moneydj_wb01")]}

SAME_FUND_INPUTS = [
    "TLZF9", "tlzf9", " TLZF9 ", "TLZF9-AL001", "TLZF9-24A7", "tlzf9-al001",
    "https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=TLZF9-AL001",
    "https://www.moneydj.com/funddj/ya/yp010000.djhtm?a=tlzf9-al001",
    "https://m.moneydj.com/a1.aspx?a=TLZF9-AL001",
    "https://www.moneydj.com/mobile/b1.aspx?a=TLZF9-24A7",
    "https://taishinlife.moneydj.com/mobile/b1.aspx?a=TLZF9-AL001",
    "https://taishinlife.moneydj.com/w/wb/wb01.djhtm?a=TLZF9-AL001",
    "https://fundrwd.entiebank.com.tw/w/wb/wb01.djhtm?a=TLZF9-24A7",
    "https://chubb.moneydj.com/w/wr/wr01.djhtm?a=TLZF9-AL001",
    "https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=TLZF9-AL001#frag",
    "https://www.moneydj.com/funddj/ya/yp010001.djhtm?area=TW&a=TLZF9-AL001",
]


# ═══════════════ Identity ═══════════════

@pytest.mark.parametrize("raw", SAME_FUND_INPUTS)
def test_同一核心基金_各種輸入都得到同一base(raw):
    ident = fi.resolve_fund_identity(raw, channel_table=TABLE)
    assert ident.base_fund_code == "TLZF9"
    assert ident.canonical_key == "TLZF9"
    assert ident.verification_status == flags.STATUS_BASE_RESOLVED


def test_通路metadata逐輸入保留且彼此不同():
    bare = fi.resolve_fund_identity("TLZF9", channel_table=TABLE)
    al = fi.resolve_fund_identity("tlzf9-al001", channel_table=TABLE)
    a7 = fi.resolve_fund_identity("https://fundrwd.entiebank.com.tw/w/wb/wb01.djhtm?a=TLZF9-24A7",
                                  channel_table=TABLE)
    assert (bare.original_code, bare.platform_suffix, bare.channel_code, bare.source_url) == (
        "TLZF9", None, None, None)
    assert (al.original_code, al.platform_suffix, al.channel_code, al.source_url) == (
        "TLZF9-AL001", "AL001", "taishinlife.moneydj.com", None)
    assert (a7.original_code, a7.platform_suffix, a7.channel_code) == (
        "TLZF9-24A7", "24A7", "fundrwd.entiebank.com.tw")
    assert a7.source_url == "https://fundrwd.entiebank.com.tw/w/wb/wb01.djhtm?a=TLZF9-24A7"
    assert a7.page_type == "wb01"
    assert fi.same_canonical_fund(bare, al) is True and fi.same_canonical_fund(al, a7) is True


def test_後綴不在通路表_channel為Unknown_不猜():
    ident = fi.resolve_fund_identity("TLZF9-ZZ99", channel_table=TABLE, namespace="moneydj")
    assert ident.base_fund_code == "TLZF9" and ident.channel_code == flags.UNKNOWN
    assert fi.resolve_fund_identity("TLZF9-AL001", namespace="moneydj").channel_code == flags.UNKNOWN  # 沒注入表


@pytest.mark.parametrize("raw", ["", "   ", None, 12345, "TL", "TLZF9 X", "actı171",
                                 "https://www.moneydj.com/funddj/ya/yp010001.djhtm",
                                 "https://x/?a=FOO123&a=BAR456"])
def test_壞輸入_明確unresolved_不猜(raw):
    ident = fi.resolve_fund_identity(raw)
    assert ident.verification_status == flags.STATUS_UNRESOLVED
    assert ident.base_fund_code is None and ident.canonical_key is None and ident.error


def test_channel_table形狀錯直接拋():
    with pytest.raises(TypeError):
        fi.resolve_fund_identity("TLZF9-AL001", channel_table=[("x", "TLZF9-AL001")])
    with pytest.raises(TypeError):
        fi.resolve_fund_identity("TLZF9-AL001", channel_table={"TLZF9": ["bad"]})


# ═══════════════ Platform suffix：預設不建第二個 canonical；例外不合併 ═══════════════

def test_後綴預設不建立第二個canonical_fund():
    keys = {fi.resolve_fund_identity(r, namespace="moneydj").canonical_key
            for r in ("TLZF9", "TLZF9-AL001", "TLZF9-24A7")}
    assert keys == {"TLZF9"}
    keys2 = {fi.resolve_fund_identity(r, channel_table=TABLE).canonical_key
             for r in ("TLZF9", "TLZF9-AL001", "TLZF9-24A7")}
    assert keys2 == {"TLZF9"}


def test_預設例外登記為空():
    assert flags.IDENTITY_EXCEPTIONS == frozenset()


def test_例外登記命中_不合併_待決():
    excs = {("TLZF9", "AL001")}
    al = fi.resolve_fund_identity("TLZF9-AL001", exceptions=excs, namespace="moneydj")
    a7 = fi.resolve_fund_identity("TLZF9-24A7", exceptions=excs, namespace="moneydj")
    bare = fi.resolve_fund_identity("TLZF9", exceptions=excs)
    assert al.verification_status == flags.STATUS_EXCEPTION == "exception_distinct_series_needs_decision"
    assert al.canonical_key is None and al.base_fund_code == "TLZF9"
    assert fi.same_canonical_fund(al, bare) is None  # 不合併、也不宣稱不同
    assert a7.canonical_key == "TLZF9" and fi.same_canonical_fund(a7, bare) is True
    other = fi.resolve_fund_identity("ANZ89")
    assert fi.same_canonical_fund(al, other) is False


def test_證據_同日同幣別NAV不同_產生例外紀錄():
    rec = fi.evaluate_suffix_evidence(
        {"fund_code": "TLZF9", "nav": 10.0, "nav_date": "2026-10-27", "currency": "USD", "source": "a"},
        {"fund_code": "TLZF9-AL001", "nav": 9.8, "nav_date": "2026-10-27", "currency": "usd", "source": "b"})
    assert rec["kind"] == flags.STATUS_EXCEPTION and rec["base_fund_code"] == "TLZF9"
    assert rec["suggested_registry_entries"] == (("TLZF9", "AL001"),)
    assert rec["differences"][0]["attribute"] == "nav_same_date_same_currency"


def test_證據_已知幣別不同_產生例外紀錄():
    rec = fi.evaluate_suffix_evidence({"fund_code": "TLZF9", "currency": "USD"},
                                      {"fund_code": "TLZF9-24A7", "currency": "TWD"})
    assert [d["attribute"] for d in rec["differences"]] == ["currency"]


@pytest.mark.parametrize("a,b", [
    ({"fund_code": "TLZF9", "nav": 10.0, "nav_date": "2026-10-27", "currency": "USD"},
     {"fund_code": "TLZF9-AL001", "nav": 10.0, "nav_date": "2026-10-27", "currency": "USD"}),
    ({"fund_code": "TLZF9", "nav": 10.0, "nav_date": "2026-10-27", "currency": "USD"},
     {"fund_code": "TLZF9-AL001", "nav": 9.0, "nav_date": "2026-10-26", "currency": "USD"}),  # 不同日：不可比
    ({"fund_code": "TLZF9", "nav": 10.0, "nav_date": "2026-10-27"},
     {"fund_code": "TLZF9-AL001", "nav": 9.0, "nav_date": "2026-10-27"}),  # 幣別 Unknown：不可比
    ({"fund_code": "TLZF9", "currency": "USD"}, {"fund_code": "TLZF9-AL001"}),  # Unknown ≠ 衝突
])
def test_證據不足_回None(a, b):
    assert fi.evaluate_suffix_evidence(a, b) is None


def test_證據_base不同或同碼_拋():
    with pytest.raises(ValueError):
        fi.evaluate_suffix_evidence({"fund_code": "TLZF9"}, {"fund_code": "ANZ89-1G11"})
    with pytest.raises(ValueError):
        fi.evaluate_suffix_evidence({"fund_code": "TLZF9-AL001"}, {"fund_code": "tlzf9-al001"})


# ═══════════════ 命名空間（獨立稽核 MUST 1）：FundClear 級別碼不得被剝後綴合併 ═══════════════

def test_FundClear級別碼_AGIF_HT5與HTG_預設不合併():
    # tests/test_fundclear_offshore.py：AGIF-HT5＝IT 累積類股、AGIF-HTG＝A 配息類股，同一基金的不同級別
    ht5 = fi.resolve_fund_identity("AGIF-HT5")
    htg = fi.resolve_fund_identity("AGIF-HTG")
    for ident in (ht5, htg):
        assert ident.verification_status == flags.STATUS_NAMESPACE_UNKNOWN
        assert ident.base_fund_code is None and ident.platform_suffix is None and ident.canonical_key is None
    assert ht5.original_code == "AGIF-HT5" and htg.original_code == "AGIF-HTG"
    assert fi.same_canonical_fund(ht5, htg) is not True
    assert fi.same_canonical_fund(ht5, fi.resolve_fund_identity("agif-ht5")) is True  # 完整代碼逐字相同


def test_FundClear級別碼_明示命名空間_範圍外_不合併():
    ht5 = fi.resolve_fund_identity("AGIF-HT5", namespace="fundclear")
    htg = fi.resolve_fund_identity("AGIF-HTG", namespace="fundclear")
    assert ht5.verification_status == flags.STATUS_OUT_OF_SCOPE_NAMESPACE
    assert fi.same_canonical_fund(ht5, htg) is None
    with pytest.raises(ValueError):  # 證據函式也不把它們當成同 base 的後綴
        fi.evaluate_suffix_evidence({"fund_code": "AGIF-HT5"}, {"fund_code": "AGIF-HTG"}, namespace="fundclear")


def test_呼叫端明示moneydj時_AGIF級別碼會被合併_守門靠呼叫端不誤標():
    # 記錄現況：命名空間守門只擋「沒有證據」；呼叫端若對 FundClear 級別碼誤標 moneydj，仍會合併
    ht5 = fi.resolve_fund_identity("AGIF-HT5", namespace="moneydj")
    htg = fi.resolve_fund_identity("AGIF-HTG", namespace="moneydj")
    assert ht5.base_fund_code == htg.base_fund_code == "AGIF"
    assert fi.same_canonical_fund(ht5, htg) is True


@pytest.mark.parametrize("raw", ["TLZF9-ZZ99", "ACDD01-EQTAL005"])
def test_shadow_後綴未剝_原因寫進reason(raw):
    rec = shadow.shadow_compare(raw)
    assert rec["resolver_result"]["verification_status"] == flags.STATUS_NAMESPACE_UNKNOWN
    assert any(r.startswith("後綴未剝：無命名空間證據（不在通路表／非 MoneyDJ 頁型") for r in rec["reason"])


def test_無後綴代碼不受命名空間影響():
    assert fi.resolve_fund_identity("AGIF").canonical_key == "AGIF"


# ═══════════════ 別名表（獨立稽核 SHOULD b） ═══════════════

def test_別名表注入後_ACTI171_ACTI7_ACTI71同一base_未注入則各自():
    from repositories.fund.sources import load_fund_code_mapping
    builtin = load_fund_code_mapping(path="")  # 不讀檔，只回內建表
    codes = ("ACTI171", "ACTI7", "ACTI71")
    assert {fi.resolve_fund_identity(c, alias_mapping=builtin).base_fund_code for c in codes} == {"ACTI71"}
    assert {fi.resolve_fund_identity(c).base_fund_code for c in codes} == set(codes)  # 預設不做別名（已知缺口）


def test_shadow_hook把production對照表傳給resolver(monkeypatch, caplog):
    monkeypatch.setattr(flags, "DG2_SHADOW_ENABLED", True)
    with caplog.at_level(logging.INFO, logger="services.fund_identity_shadow"):
        fund_keys.resolve_full_keys(["ACTI171"], mapping={"ACTI171": {"public_code": "ACTI71"}})
    (rec,) = [r for r in caplog.records if r.name == "services.fund_identity_shadow"]
    assert "'base_fund_code': 'ACTI71'" in rec.getMessage()


# ═══════════════ Unknown ═══════════════

def test_Unknown_不猜_缺ISIN不失敗_不預設USD():
    ident = fi.resolve_fund_identity("TLZF9-AL001", channel_table=TABLE)
    assert ident.isin is None and ident.verification_status == flags.STATUS_BASE_RESOLVED
    assert (ident.currency, ident.share_class, ident.distribution_type, ident.hedge_status) == (
        "Unknown",) * 4
    # 名稱寫「美元」的 TLZF9、帶後綴的代碼：一律不推 currency／share class
    assert fi.resolve_fund_identity("TLZF9").currency == flags.UNKNOWN


def test_可靠來源給的屬性才填_空白仍Unknown():
    ident = fi.resolve_fund_identity("TLZF9", currency="usd", share_class="AMg7", isin=" lu0000000000 ",
                                     distribution_type="  ", hedge_status=None, as_of="2026-10-28")
    assert (ident.currency, ident.share_class, ident.isin) == ("USD", "AMg7", "LU0000000000")
    assert ident.distribution_type == flags.UNKNOWN and ident.hedge_status == flags.UNKNOWN
    assert ident.as_of == "2026-10-28"


def test_Unknown比較語意_既不相同也不相異():
    assert fi.compare_attribute("Unknown", "Unknown") == fi.UNKNOWN_CMP
    assert fi.compare_attribute("USD", "Unknown") == fi.UNKNOWN_CMP
    assert fi.compare_attribute(None, "USD") == fi.UNKNOWN_CMP
    assert fi.compare_attribute("usd", "USD") == fi.SAME
    assert fi.compare_attribute("USD", "TWD") == fi.DIFFERENT


# ═══════════════ External source validation ═══════════════

def test_外部候選_已知屬性衝突_拒收並顯示指定文字():
    ident = fi.resolve_fund_identity("TLZF9", currency="USD")
    res = fi.validate_external_candidate(
        ident, {"source": "morningstar:results[0]", "base_fund_code": "TLZF9", "currency": "EUR",
                "as_of": "2026-10-27"})
    assert res["status"] == flags.CANDIDATE_REJECTED
    assert res["display_text"] == "⬜ 資料來源不一致，暫無法判定"
    assert res["rejected_source"] == "morningstar:results[0]" and res["freshness"] == "2026-10-27"
    assert res["conflicts"] == [{"attribute": "currency", "identity_value": "USD", "candidate_value": "EUR"}]


def test_外部候選_base衝突也拒收():
    res = fi.validate_external_candidate(fi.resolve_fund_identity("TLZF9"),
                                         {"source": "ms", "base_fund_code": "ANZ89"})
    assert res["status"] == flags.CANDIDATE_REJECTED and res["display_text"] == flags.SOURCE_CONFLICT_TEXT


def test_外部候選_相符則收():
    res = fi.validate_external_candidate(fi.resolve_fund_identity("TLZF9", currency="USD"),
                                         {"source": "ms", "base_fund_code": "TLZF9", "currency": "USD"})
    assert res["status"] == flags.CANDIDATE_ACCEPTED and res["display_text"] is None
    assert res["confirmed"] == ["base_fund_code", "currency"]


def test_外部候選_只有幣別相符_不接受_unverified():
    # 獨立稽核 MUST 2：同幣別的別檔基金很多，只有 currency 相符不得 accepted
    res = fi.validate_external_candidate(fi.resolve_fund_identity("TLZF9", currency="USD"),
                                         {"source": "ms", "currency": "USD"})
    assert res["status"] == flags.CANDIDATE_UNVERIFIED and res["confirmed"] == ["currency"]
    assert res["display_text"] is None


def test_外部候選_isin相符則收():
    res = fi.validate_external_candidate(fi.resolve_fund_identity("TLZF9", isin="LU0000000000"),
                                         {"source": "ms", "isin": "lu0000000000"})
    assert res["status"] == flags.CANDIDATE_ACCEPTED and res["confirmed"] == ["isin"]


def test_外部候選_只有Unknown對值_unverified():
    res = fi.validate_external_candidate(fi.resolve_fund_identity("TLZF9"),
                                         {"source": "ms", "currency": "USD", "isin": "LU0000000000"})
    assert res["status"] == flags.CANDIDATE_UNVERIFIED and res["conflicts"] == [] and res["confirmed"] == []
    res2 = fi.validate_external_candidate(fi.resolve_fund_identity(""), {"base_fund_code": "TLZF9"})
    assert res2["status"] == flags.CANDIDATE_UNVERIFIED


# ═══════════════ Cross-View NAV（與 identity 分開） ═══════════════

def test_跨頁NAV_同日同幣別一致():
    res = fi.check_cross_view_nav("TLZF9", [
        ("tab2", 12.99, "2026-02-27", "USD", "FundClear"),
        {"view": "hld", "nav": 12.99, "nav_date": "2026-02-27", "currency": "usd", "source": "FundClear"}])
    assert res["status"] == flags.NAV_CONSISTENT and res["conflicts"] == []


def test_跨頁NAV_同日同幣別不同_source_conflict_不建第二個identity():
    res = fi.check_cross_view_nav("TLZF9", [("tab2", 12.99, "2026-02-27", "USD", "A"),
                                            ("t7", 11.11, "2026-02-27", "USD", "Yahoo")])
    assert res["status"] == flags.NAV_CONFLICT
    (c,) = res["conflicts"]
    assert c["base_fund_code"] == "TLZF9" and c["display_text"] == flags.SOURCE_CONFLICT_TEXT
    assert res["base_fund_code"] == "TLZF9" and "canonical_key" not in res


@pytest.mark.parametrize("obs", [
    [("tab2", 12.99, "2026-02-27", "USD", "A"), ("t7", 11.11, "2026-02-26", "USD", "B")],
    [("tab2", 12.99, "2026-02-27", "USD", "A"), ("t7", 400.0, "2026-02-27", "TWD", "B")],
    [("tab2", 12.99, "2026-02-27", "Unknown", "A"), ("t7", 11.11, "2026-02-27", None, "B")],
    [],
])
def test_跨頁NAV_不同日或不同幣別_不可比(obs):
    res = fi.check_cross_view_nav("TLZF9", obs)
    assert res["status"] == flags.NAV_NOT_COMPARABLE and res["conflicts"] == []


@pytest.mark.parametrize("nav", [0, -1.0, float("nan"), "12.9", None, True])
def test_跨頁NAV_壞值直接拋(nav):
    with pytest.raises((TypeError, ValueError)):
        fi.check_cross_view_nav("TLZF9", [("tab2", nav, "2026-02-27", "USD", "A")])


# ═══════════════ Shadow comparator ═══════════════

def test_shadow輸出形狀():
    rec = shadow.shadow_compare("TLZF9-AL001")
    assert set(rec) == {"raw_input", "current_parser_results", "resolver_result", "difference", "reason"}
    assert set(rec["current_parser_results"]) == set(shadow.PARSER_NAMES)
    assert rec["resolver_result"]["base_fund_code"] == "TLZF9"
    assert rec["resolver_result"]["channel_code"] == "taishinlife.moneydj.com"  # 綁定 L1 _BANK_PLATFORM_CODES
    assert rec["difference"] == {"cache_normalizer": ""}  # 裸碼：cache 正規化得空鍵


def test_shadow_回報已知現有parser分歧():
    frag = shadow.shadow_compare("https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=TLZF9-AL001#frag")
    # DG-2 §10 缺陷 C 修正後翻轉:policy_v1 的 `#FRAG`／`TW` 分歧已消失(不再出現在 difference);
    # 其餘舊 parser 分歧(cache_normalizer 小寫 a=／canonicalize 行動版)不在本批修正範圍,維持原斷言。
    assert "policy_v1_extract_code_from_url" not in frag["difference"]
    area = shadow.shadow_compare("https://www.moneydj.com/funddj/ya/yp010001.djhtm?area=TW&a=TLZF9-AL001")
    assert "policy_v1_extract_code_from_url" not in area["difference"]
    low = shadow.shadow_compare("https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=tlzf9-al001")
    assert low["difference"]["cache_normalizer"] == ""
    mob = shadow.shadow_compare("https://m.moneydj.com/a1.aspx?a=TLZF9-AL001")
    assert mob["difference"]["canonicalize_then_parse"] == "TLZF9"  # 只有行動版網址會剝後綴
    for rec in (frag, area, low, mob):
        assert rec["resolver_result"]["base_fund_code"] == "TLZF9" and rec["reason"]


def test_shadow_壞輸入_resolver判unresolved():
    rec = shadow.shadow_compare("TLZF9 X")
    assert rec["resolver_result"]["verification_status"] == flags.STATUS_UNRESOLVED
    assert rec["difference"]["parse_moneydj_input"] == "TLZF9 X"


# ═══════════════ Feature flag：預設關、關閉無效果、開啟不改回傳值 ═══════════════

CODES = ["TLZF9", "tlzf9-al001", "https://m.moneydj.com/a1.aspx?a=TLZF9-AL001", "bad code", 7]


def test_flag預設關():
    assert flags.DG2_SHADOW_ENABLED is False


def test_flag關_shadow_hook不被呼叫且結果不變(monkeypatch):
    baseline = fund_keys.resolve_full_keys(CODES, mapping={})

    def _boom(*a, **k):
        raise AssertionError("flag 關閉時不得呼叫 shadow hook")

    monkeypatch.setattr(shadow, "log_shadow_for_fund_keys", _boom)
    assert flags.DG2_SHADOW_ENABLED is False
    assert fund_keys.resolve_full_keys(CODES, mapping={}) == baseline


def test_flag開_只寫log_不改回傳值(monkeypatch, caplog):
    baseline = fund_keys.resolve_full_keys(CODES, mapping={})
    monkeypatch.setattr(flags, "DG2_SHADOW_ENABLED", True)
    with caplog.at_level(logging.INFO, logger="services.fund_identity_shadow"):
        assert fund_keys.resolve_full_keys(CODES, mapping={}) == baseline
    shadow_logs = [r for r in caplog.records if r.name == "services.fund_identity_shadow"]
    assert len(shadow_logs) == len(CODES)


def test_flag開_shadow內部失敗_不影響production(monkeypatch, caplog):
    baseline = fund_keys.resolve_full_keys(CODES, mapping={})
    monkeypatch.setattr(flags, "DG2_SHADOW_ENABLED", True)

    def _boom(*a, **k):
        raise RuntimeError("shadow boom")

    monkeypatch.setattr(shadow, "shadow_compare", _boom)
    with caplog.at_level(logging.INFO, logger="services.fund_identity_shadow"):
        assert fund_keys.resolve_full_keys(CODES, mapping={}) == baseline
    assert any("dg2_shadow 失敗" in r.getMessage() for r in caplog.records)


def test_flag開_shadow模組import失敗_不影響production(monkeypatch, caplog):
    import sys
    baseline = fund_keys.resolve_full_keys(CODES, mapping={})
    monkeypatch.setattr(flags, "DG2_SHADOW_ENABLED", True)
    monkeypatch.setitem(sys.modules, "services.fund_identity_shadow", None)  # import 時拋 ImportError
    with caplog.at_level(logging.ERROR, logger="services.v2_tables.fund_keys"):
        assert fund_keys.resolve_full_keys(CODES, mapping={}) == baseline
    assert any("dg2_shadow hook 失敗" in r.getMessage() for r in caplog.records)


def test_flag關_新模組不會被import_子程序():
    import subprocess
    import sys
    from pathlib import Path
    code = ("import sys; import services.v2_tables.fund_keys as fk; "
            "fk.resolve_full_keys(['TLZF9', 'TLZF9-AL001'], mapping={}); "
            "print('DG2MODS', 'services.fund_identity' in sys.modules, 'services.fund_identity_shadow' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    (line,) = [ln for ln in out.stdout.splitlines() if ln.startswith("DG2MODS")]
    assert line == "DG2MODS False False", line


def test_resolver_不import_L1私有通路表與IO套件():
    import ast
    from pathlib import Path
    tree = ast.parse(Path(fi.__file__).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.add(node.module)
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    assert "_BANK_PLATFORM_CODES" not in names
    assert not names & {"requests", "httpx", "bs4", "feedparser", "streamlit"}
    assert not any(n and n.startswith("ui") for n in names)
