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
    # ~~MoneyDJ 命名空間＋未知後綴 → base TLZF9、channel Unknown~~ → DEC-2026-10-29-01（有意識的更正，不是漏刪）：
    # 客戶裁示「未知來源或未知後綴不得盲目剝除」—— MoneyDJ 命名空間內也只剝已驗證 mapping 命中的後綴。
    for ident in (fi.resolve_fund_identity("TLZF9-ZZ99", channel_table=TABLE, namespace="moneydj"),
                  fi.resolve_fund_identity("TLZF9-AL001", namespace="moneydj")):  # 後者：沒注入表 ＝ 未驗
        assert ident.verification_status == flags.STATUS_SUFFIX_UNVERIFIED
        assert ident.base_fund_code is None and ident.canonical_key is None and ident.channel_code is None
    assert fi.resolve_fund_identity("TLZF9-ZZ99", namespace="moneydj").original_code == "TLZF9-ZZ99"


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
    # DEC-2026-10-29-01（有意識的更正，不是漏刪）：只宣告 namespace 不夠，後綴須命中已驗證 mapping 才剝。
    keys = {fi.resolve_fund_identity(r, namespace="moneydj", channel_table=TABLE).canonical_key
            for r in ("TLZF9", "TLZF9-AL001", "TLZF9-24A7")}
    assert keys == {"TLZF9"}
    keys2 = {fi.resolve_fund_identity(r, channel_table=TABLE).canonical_key
             for r in ("TLZF9", "TLZF9-AL001", "TLZF9-24A7")}
    assert keys2 == {"TLZF9"}


def test_預設例外登記為空():
    assert flags.IDENTITY_EXCEPTIONS == frozenset()


def test_例外登記命中_不合併_待決():
    excs = {("TLZF9", "AL001")}
    # DEC-2026-10-29-01：注入通路表（已驗證 mapping）才會剝後綴，再看例外登記
    al = fi.resolve_fund_identity("TLZF9-AL001", exceptions=excs, namespace="moneydj", channel_table=TABLE)
    a7 = fi.resolve_fund_identity("TLZF9-24A7", exceptions=excs, namespace="moneydj", channel_table=TABLE)
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


def test_呼叫端誤標moneydj時_AGIF級別碼也不被合併():
    # ~~記錄現況：呼叫端若對 FundClear 級別碼誤標 moneydj，仍會合併（base AGIF、same is True）~~
    # → DEC-2026-10-29-01（有意識的更正，不是漏刪）：後綴須命中已驗證 mapping 才剝，誤標 namespace 也不合併。
    ht5 = fi.resolve_fund_identity("AGIF-HT5", namespace="moneydj")
    htg = fi.resolve_fund_identity("AGIF-HTG", namespace="moneydj")
    for ident in (ht5, htg):
        assert ident.verification_status == flags.STATUS_SUFFIX_UNVERIFIED and ident.base_fund_code is None
    assert fi.same_canonical_fund(ht5, htg) is None


# ~~`["TLZF9-ZZ99", "ACDD01-EQTAL005"]`~~ → DEC-2026-10-29-01（有意識的更正，不是漏刪）：`ACDD01-EQTAL005` 已列入
# L0 客戶確認表，成為命名空間證據並剝成 `ACDD01`（見下方〈DEC-2026-10-29-01〉測試）。
@pytest.mark.parametrize("raw", ["TLZF9-ZZ99", "ACDD01-ZZ99"])
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


# ═══════════════ DEC-2026-10-29-01：Sheet 基金代號欄＝MoneyDJ 基本代碼 ═══════════════

SHEET = flags.INPUT_SOURCE_SHEET_FUND_CODE
SHEET_EXAMPLES = ["ACTI71", "JFZN3", "ACCP138", "ACDD01", "ACDD19", "TLZF9", "ACTI94", "ALBT8"]  # 客戶裁示第 1 項


@pytest.mark.parametrize("code", SHEET_EXAMPLES)
def test_Sheet基金代號_客戶8例_各自就是基本代碼(code):
    from repositories.fund.sources import load_fund_code_mapping
    for mapping in (None, load_fund_code_mapping(path="")):  # 不注入別名表／注入內建表，結果都一樣
        ident = fi.resolve_fund_identity(code, input_source=SHEET, alias_mapping=mapping)
        assert ident.verification_status == flags.STATUS_BASE_RESOLVED
        assert ident.base_fund_code == ident.canonical_key == ident.original_code == code
        assert ident.platform_suffix is None and ident.input_source == SHEET and ident.raw_input == code
        assert (ident.page_type_source, ident.url_page_market) == (flags.UNKNOWN, flags.UNKNOWN)  # 裸碼不推頁型


def test_Sheet命名空間只限該欄_不推廣():
    assert dict(flags.INPUT_SOURCE_NAMESPACES) == {SHEET: flags.NAMESPACE_MONEYDJ}
    with pytest.raises(ValueError):  # 未知來源不得被默默當成 MoneyDJ
        fi.resolve_fund_identity("TLZF9", input_source="sheet_any_column")
    with pytest.raises(ValueError):  # 與明示命名空間衝突
        fi.resolve_fund_identity("TLZF9", input_source=SHEET, namespace="fundclear")
    # 沒宣告來源的同一字串照舊走證據規則（不因 Sheet 裁示而全 repo 視為 MoneyDJ）
    assert fi.resolve_fund_identity("AGIF-HT5").verification_status == flags.STATUS_NAMESPACE_UNKNOWN


@pytest.mark.parametrize("raw", [
    "ACDD01-EQTAL005", "TLZF9-AL001", "AGIF-HT5",
    "https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=TLZF9",
    "TLZF9 X", "AB", "A" * 31, "actı171", "", "   ", None, 12345,
])
def test_Sheet契約違反_原值保留_不剝不截不改寫(raw):
    ident = fi.resolve_fund_identity(raw, input_source=SHEET, channel_table=TABLE)
    assert ident.verification_status == flags.STATUS_SHEET_CONTRACT_VIOLATION
    assert ident.raw_input is raw  # 原值原物件保留
    assert ident.base_fund_code is None and ident.original_code is None and ident.canonical_key is None
    assert ident.platform_suffix is None and ident.error
    assert fi.same_canonical_fund(ident, fi.resolve_fund_identity("TLZF9")) is None


def test_Sheet大小寫與前後空白沿用fund_keys第0到2步():
    ident = fi.resolve_fund_identity(" tlzf9 ", input_source=SHEET)
    assert ident.base_fund_code == "TLZF9" and ident.raw_input == " tlzf9 "


def test_shadow_可宣告Sheet來源_hook不宣告():
    rec = shadow.shadow_compare("ACDD01-EQTAL005", input_source=SHEET)
    assert rec["resolver_result"]["verification_status"] == flags.STATUS_SHEET_CONTRACT_VIOLATION
    assert any("Sheet 基金代號欄契約違反" in r for r in rec["reason"])
    assert shadow.shadow_compare("ACDD01")["resolver_result"]["input_source"] is None


def test_hook輸入混有非Sheet欄來源_不標記Sheet(monkeypatch):
    # hook 只拿到字串串列，無法證明逐筆來源（`docs/v2/70` 第 15 節〈hook 呼叫鏈〉），故不傳 input_source
    import inspect
    seen = []
    real = shadow.shadow_compare
    monkeypatch.setattr(shadow, "shadow_compare", lambda raw, **kw: seen.append(kw) or real(raw, **kw))
    monkeypatch.setattr(flags, "DG2_SHADOW_ENABLED", True)
    fund_keys.resolve_full_keys(["TLZF9"], mapping={})
    assert seen and all("input_source" not in kw for kw in seen)
    assert "input_source" not in inspect.signature(fund_keys.resolve_full_keys).parameters


# ═══════════════ DEC-2026-10-29-01：ACDD01-EQTAL005（客戶確認）與 FundClear 反例 ═══════════════

def test_客戶確認表_ACDD01_EQTAL005_只此一筆_NAV未驗():
    assert set(flags.CUSTOMER_CONFIRMED_SUFFIXES) == {("ACDD01", "EQTAL005")}
    entry = flags.CUSTOMER_CONFIRMED_SUFFIXES[("ACDD01", "EQTAL005")]
    assert entry["provenance"] == "customer_confirmed_2026-10-29" and entry["decision"] == "DEC-2026-10-29-01"
    assert entry["nav_equivalence"] == "UNVERIFIED"
    assert "channel" not in entry and "domain" not in entry  # 客戶未給通路名稱，不自編


@pytest.mark.parametrize("raw", [
    "ACDD01-EQTAL005", "acdd01-eqtal005",
    "https://chubb.moneydj.com/w/wr/wr01.djhtm?a=ACDD01-EQTAL005",
    "https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=ACDD01-EQTAL005",
])
def test_ACDD01_EQTAL005_裸碼與網址_得ACDD01與後綴與出處(raw):
    ident = fi.resolve_fund_identity(raw)  # 不注入通路表：靠 L0 客戶確認表
    assert ident.verification_status == flags.STATUS_BASE_RESOLVED
    assert (ident.base_fund_code, ident.original_code, ident.platform_suffix) == ("ACDD01", "ACDD01-EQTAL005", "EQTAL005")
    assert ident.suffix_provenance == flags.SUFFIX_PROVENANCE_CUSTOMER_2026_10_29
    assert ident.channel_code == flags.UNKNOWN  # 不在通路表 → 通路未知，不猜
    assert fi.same_canonical_fund(ident, fi.resolve_fund_identity("ACDD01", input_source=SHEET)) is True


def test_通路表命中的後綴_出處為channel_table():
    ident = fi.resolve_fund_identity("TLZF9-AL001", channel_table=TABLE)
    assert ident.suffix_provenance == flags.SUFFIX_PROVENANCE_CHANNEL_TABLE
    assert fi.resolve_fund_identity("TLZF9").suffix_provenance is None


@pytest.mark.parametrize("namespace", [None, "fundclear", "moneydj"])
def test_FundClear_AGIF_HT5_HTG_任何命名空間都不剝成AGIF(namespace):
    ht5 = fi.resolve_fund_identity("AGIF-HT5", namespace=namespace)
    htg = fi.resolve_fund_identity("AGIF-HTG", namespace=namespace)
    assert ht5.base_fund_code is None and htg.base_fund_code is None
    assert ht5.original_code == "AGIF-HT5" and htg.original_code == "AGIF-HTG"
    assert fi.same_canonical_fund(ht5, htg) is not True


def test_MoneyDJ網址_未驗後綴_不剝():
    ident = fi.resolve_fund_identity("https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=TLZF9-ZZ99",
                                     channel_table=TABLE)
    assert ident.verification_status == flags.STATUS_SUFFIX_UNVERIFIED
    assert ident.original_code == "TLZF9-ZZ99" and ident.base_fund_code is None
    assert ident.page_type_source == "url" and ident.url_page_market == "offshore"  # 頁型證據照記


# ═══════════════ DEC-2026-10-29-01：MoneyDJ 境內／境外頁型（第 5 項） ═══════════════

@pytest.mark.parametrize("raw,page_type,market", [
    ("https://www.moneydj.com/funddj/ya/yp010000.djhtm?a=ACDD19", "yp010000", "domestic"),
    ("https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=TLZF9", "yp010001", "offshore"),
    # 網址明示優先：ACDD 前綴推斷為境內，但網址是 yp010001 → 照網址記（舊 UI 也是頁型優先，見 `_is_domestic_code`）
    ("https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=ACDD01", "yp010001", "offshore"),
    ("https://taishinlife.moneydj.com/w/wb/wb01.djhtm?a=TLZF9-AL001", "wb01", flags.UNKNOWN),
    ("https://m.moneydj.com/a1.aspx?a=acdd01", "a1_mobile", flags.UNKNOWN),
])
def test_網址明示頁型_記為證據(raw, page_type, market):
    ident = fi.resolve_fund_identity(raw, channel_table=TABLE)
    assert (ident.page_type, ident.page_type_source, ident.url_page_market) == (page_type, "url", market)


@pytest.mark.parametrize("code", ["ACDD01", "ACTI71", "TLZF9", "ALBT8", "ACDD01-EQTAL005"])
def test_裸碼頁型_一律Unknown_不用前綴或對照表推斷(code):
    ident = fi.resolve_fund_identity(code)
    assert (ident.page_type, ident.page_type_source, ident.url_page_market) == ("", flags.UNKNOWN, flags.UNKNOWN)


def test_頁型對應與L1一致_前綴推斷與網址可衝突():
    from repositories.fund import sources
    assert dict(flags.MONEYDJ_PAGE_MARKET) == {"yp010000": "domestic", "yp010001": "offshore"}
    # L1：網址頁型優先於任何推斷
    assert sources._is_domestic_code("TLZF9", "yp010000") is True
    assert sources._is_domestic_code("ACDD01", "yp010001") is False
    # 前綴推斷（無 csv 時）與 canonicalize 都把 ACDD01 推成境內頁，卻與上面那個明示 yp010001 的網址衝突
    assert sources._is_domestic_code("ACDD01") is True
    assert "yp010000" in sources.canonicalize_moneydj_url("https://m.moneydj.com/a1.aspx?a=acdd01")
    assert sources.get_page_types_to_try("yp010000") == ["yp010000", "yp010001"]  # 失敗即互換：推斷只是路由


# ═══════════════ DEC-2026-10-29-01：基金身份 ≠ 保單持倉身份（第 2 項） ═══════════════

HOLDINGS = [
    {"policy_id": "P-001", "fund_code": "TLZF9", "units": 100.0, "invest_twd": 300000},
    {"policy_id": "P-002", "fund_code": "TLZF9", "units": 40.5, "invest_twd": 120000},
    {"policy_id": "P-002", "fund_code": "ACDD01", "units": 10.0, "invest_twd": 50000},
]


def test_多張保單持有同一基金_共用基金身份_持倉各自獨立():
    import copy
    before = copy.deepcopy(HOLDINGS)
    idents = [fi.resolve_fund_identity(h["fund_code"], input_source=SHEET) for h in HOLDINGS]
    assert idents[0].canonical_key == idents[1].canonical_key == "TLZF9"
    assert fi.same_canonical_fund(idents[0], idents[1]) is True
    assert HOLDINGS == before and len(HOLDINGS) == 3  # resolver 不碰持倉紀錄
    holding_keys = {(h["policy_id"], h["fund_code"]) for h in HOLDINGS}
    assert len(holding_keys) == 3  # 持倉鍵仍分開；同基金不同保單不合併
    assert sum(h["units"] for h in HOLDINGS if h["policy_id"] == "P-001") == 100.0


def test_shadow_hook逐筆記錄_不去重不彙總(monkeypatch, caplog):
    codes = [h["fund_code"] for h in HOLDINGS]
    baseline = fund_keys.resolve_full_keys(codes, mapping={})
    assert len(baseline["results"]) == 3  # production 逐筆，同碼兩筆仍兩筆
    monkeypatch.setattr(flags, "DG2_SHADOW_ENABLED", True)
    with caplog.at_level(logging.INFO, logger="services.fund_identity_shadow"):
        assert fund_keys.resolve_full_keys(codes, mapping={}) == baseline
    assert len([r for r in caplog.records if r.name == "services.fund_identity_shadow"]) == 3


def test_resolver與shadow原始碼不含持倉欄位():
    import ast
    from pathlib import Path
    for mod in (fi, shadow):
        tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        names |= {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        assert not names & {"policy_id", "units", "invest_twd", "avg_nav", "holding_id"}, mod.__name__


# ═══════════════ DEC-2026-10-29-01：Unknown（第 8 項） ═══════════════

@pytest.mark.parametrize("raw,kw", [
    ("TLZF9", {"input_source": SHEET}),
    ("ACDD01-EQTAL005", {}),
    ("https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=TLZF9", {}),
])
def test_Unknown_不猜幣別類股_缺ISIN不警告(raw, kw, caplog):
    with caplog.at_level(logging.DEBUG):
        ident = fi.resolve_fund_identity(raw, **kw)
    assert (ident.currency, ident.share_class, ident.distribution_type, ident.hedge_status) == ("Unknown",) * 4
    assert ident.currency != "USD" and ident.isin is None
    assert ident.verification_status == flags.STATUS_BASE_RESOLVED  # 缺 ISIN 不影響
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
