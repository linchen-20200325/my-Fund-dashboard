"""DG-2 §10（docs/v2/70 §14 已知缺陷 1～4）解析缺陷：characterization → 修正後鎖定。

第一個 commit 只釘「現況」（缺陷行為）；修正 commit 會把對應斷言翻轉並註明。
無網路：以 monkeypatch 取代 `fetch_url_with_retry`／`_src_cache_files`。
"""
from __future__ import annotations

import pandas as pd
import pytest

_URL_UP = "HTTPS://WWW.MONEYDJ.COM/FUNDDJ/YA/YP010001.DJHTM?A=TLZF9-AL001"
_URL = "https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=TLZF9-AL001"


# ── A. 手動加入把網址整行轉大寫 ───────────────────────────────
def test_A_舊寫法仍會產生HTTPS_證明缺陷機制存在():
    """舊 UI 寫法（先 upper）的機制仍成立；修正在 UI 端改用 normalize_manual_fund_input。"""
    from repositories.fund.sources import parse_moneydj_input
    from services.moneydj_fetcher import build_moneydj_url
    built = build_moneydj_url(_URL.strip().upper(), "yp010001")
    assert parse_moneydj_input(built)["code"] == "HTTPS"


@pytest.mark.parametrize("raw,expected", [
    (_URL, "TLZF9-AL001"),
    ("  " + _URL + "  ", "TLZF9-AL001"),
    (_URL.upper(), "TLZF9-AL001"),
    ("HTTPS://WWW.MONEYDJ.COM/FUNDDJ/YA/YP010000.DJHTM?a=acdd01", "ACDD01"),
    ("https://m.moneydj.com/a1.aspx?a=acdd01", "ACDD01"),
    ("https://www.moneydj.com/funddj/ya/yp010001.djhtm", ""),   # 抽不出代碼 → 空（不猜）
])
def test_A_網址先判斷再取代碼(raw, expected):
    from services.moneydj_fetcher import normalize_manual_fund_input
    assert normalize_manual_fund_input(raw) == expected


@pytest.mark.parametrize("raw", ["tlzf9", "TLZF9", " acdd01 ", "TLZF9-AL001", "tlzf9-al001", "a" * 40, "", "  ", "ab c", "中文"])
def test_A_裸碼行為與修正前逐字相同(raw):
    from services.moneydj_fetcher import normalize_manual_fund_input
    assert normalize_manual_fund_input(raw) == raw.strip().upper()


def test_A_None安全():
    from services.moneydj_fetcher import normalize_manual_fund_input
    assert normalize_manual_fund_input(None) == ""


# ── B. fetch_nav / fetch_div 以後綴當代碼 ─────────────────────
@pytest.fixture
def _nav_spy(monkeypatch):
    from repositories.fund import nav_metrics as nm
    urls, cache_codes = [], []

    def _fake_fetch(url, **kw):
        urls.append(url)
        return None

    def _fake_cache(code):
        cache_codes.append(code)
        return pd.Series(dtype=float)

    monkeypatch.setattr(nm, "fetch_url_with_retry", _fake_fetch)
    monkeypatch.setattr(nm, "_src_cache_files", _fake_cache)
    return nm, urls, cache_codes


def _fresh(fn):
    fn = getattr(fn, "__wrapped__", fn)
    return fn


def test_B_fetch_nav_不再以後綴AL001當代碼(_nav_spy):
    nm, urls, cache_codes = _nav_spy
    nm.fetch_nav("TLZF9-AL001")
    assert not any("a=AL001" in u for u in urls)
    assert any(u.endswith("yp004001.djhtm?a=TLZF9-AL001") for u in urls)  # 完整鍵照舊先試
    assert "AL001" not in cache_codes and cache_codes == []  # 含 '-' 的鍵不查預存檔(不新增讀取)


def test_B_fetch_div_不再以後綴AL001當代碼(_nav_spy):
    nm, urls, _ = _nav_spy
    nm.fetch_div("TLZF9-AL001")
    assert not any("a=AL001" in u for u in urls)
    assert any(u.endswith("yp004003.djhtm?a=TLZF9-AL001") for u in urls)


def test_B_無破折號的鍵_網址序列與預存檔查詢逐字不變(_nav_spy):
    nm, urls, cache_codes = _nav_spy
    nm.fetch_nav("tlzf9")  # 修正前後皆:境外 → wb02、wf01、yp004001(一次,原本 mj_short==full_key 會重複同一網址)
    assert cache_codes == ["TLZF9"]
    assert urls[0].endswith("/w/wb/wb02.djhtm?a=tlzf9") and urls[1].endswith("/w/wf/wf01.djhtm?a=tlzf9")
    assert urls.count("https://www.moneydj.com/funddj/yf/yp004001.djhtm?a=tlzf9") == 1


# ── C. policy v1 _extract_code_from_url ───────────────────────
def _old_extract(url):
    """修正前實作(逐字抄自 base 84a956b5),作差分對照基準。"""
    if not url:
        return ""
    s = str(url).strip()
    if "://" not in s and "/" not in s:
        return s.upper()
    for token in s.replace("?", "&").split("&"):
        if "=" in token:
            k, v = token.split("=", 1)
            if k.lower().endswith(("a", "code")) and v:
                return v.strip().upper()
    tail = s.rstrip("/").split("/")[-1]
    return tail.split(".")[0].upper()


_MJ = "https://www.moneydj.com/funddj/ya/yp010001.djhtm"


@pytest.mark.parametrize("raw,expected", [
    (_URL + "#frag", "TLZF9-AL001"),
    (_MJ + "?area=TW&a=TLZF9-AL001", "TLZF9-AL001"),
    (_MJ + "?A=tlzf9-al001#x", "TLZF9-AL001"),
    (_MJ + "?yp=010001&a=ACDD01&b=1", "ACDD01"),
    (_MJ + "?data=1&a=ACDD01", "ACDD01"),
    ("www.moneydj.com/funddj/ya/yp010001.djhtm?a=acdd01", "ACDD01"),  # 無 scheme 但含 /
])
def test_C_缺陷輸入_修正後(raw, expected):
    from repositories.policy.v1 import _extract_code_from_url
    assert _extract_code_from_url(raw) == expected


# 目前正確的輸入:修正前後輸出必須逐字相同(holding key `{policy_id}::{CODE}` 不變)
_VALID = [
    "TLZF9", "tlzf9", " acdd01 ", "TLZF9-AL001", "tlzf9-al001", "a=tlzf9",
    "", None,
    _MJ + "?a=ACDD01", _MJ + "?a=acdd01", _MJ + "?A=ACDD01", _MJ + "?yp=010001&a=ACDD01",
    _MJ + "?b=1&a=ACDD01&c=2", _MJ + "?a=ACDD01-EQTAL005",
    "https://chubb.moneydj.com/w/wr/wr01.djhtm?a=ACDD01-EQTAL005",
    "https://m.moneydj.com/a1.aspx?a=acdd01",
    "https://tcbbankfund.moneydj.com/w/wb/wb02.djhtm?a=TLZF9",
    "https://x.example/p?code=XYZ123", "https://x.example/p?fundcode=XYZ123&z=1",
    "https://x.example/p?code=XYZ123&a=ACDD01",  # code 在 a 之前 → 取 code(舊行為)
    "https://x.example/p?a=",  # a 空值 → 走路徑尾段
    "https://www.moneydj.com/funddj/ya/yp010001.djhtm",  # 無 query → 路徑尾段
    "https://x.example/fund/ABC123/", "https://x.example/fund/ABC123.html",
    _MJ + "?a=ACDD01&a=BAR456",  # 重複 a → 取第一個
]


@pytest.mark.parametrize("raw", _VALID)
def test_C_目前正確的輸入_輸出與修正前逐字相同(raw):
    from repositories.policy.v1 import _extract_code_from_url
    assert _extract_code_from_url(raw) == _old_extract(raw)


def test_C_持股鍵格式不變_對既有valid列(monkeypatch):
    """`sync_policies_to_portfolio_funds` 的 pk 字串 `{policy_id}::{CODE}`:valid 列(裸碼/一般網址/平台後綴)
    在修正前後逐字相同;含 fragment／area 誘餌的人工構造列才會不同(那些是缺陷輸入)。"""
    import pandas as pd
    import repositories.policy.v1 as v1
    rows = [(f"P{i}", u) for i, u in enumerate(u for u in _VALID if u and str(u).strip())]
    df = pd.DataFrame([{"policy_id": pid, "fund_url": u, "invest_twd": 1000} for pid, u in rows])
    _, new_rep = v1.sync_policies_to_portfolio_funds(df, [])
    monkeypatch.setattr(v1, "_extract_code_from_url", _old_extract)
    _, old_rep = v1.sync_policies_to_portfolio_funds(df, [])
    assert new_rep == old_rep
    assert any(k.endswith("::ACDD01-EQTAL005") for k in new_rep["added"])  # 平台後綴鍵仍保留


# ── D. infra.cache._normalize_moneydj_url_for_cache ───────────
# 僅釘住現況，本批不修:`git grep _normalize_moneydj_url_for_cache` 除定義與測試外唯一引用是
# services/fund_identity_shadow.py(flag 預設關的 shadow 記錄),production 0 呼叫者(docs/v2/70 §10 第 6 點)。
# 小寫 `a=`／裸碼得空碼鍵(`fetch_fund||default`)是已知缺陷;若日後有人把它接進 production,
# 空碼鍵會讓不同基金共用同一把 cache 鍵 → 屆時必須先修(或改用 fund_keys 的代碼)再接線。
def test_D_現況_小寫a與裸碼都得空碼鍵_production無呼叫者_僅釘住():
    from infra.cache import _normalize_moneydj_url_for_cache as n
    assert n("https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=tlzf9-al001") == "fetch_fund||default"
    assert n("TLZF9-AL001") == "fetch_fund||default"
    # 兩檔不同基金在空碼鍵下碰撞(這就是不得接進 production 的理由)
    assert n("https://x/p?a=tlzf9") == n("https://x/p?a=acdd01")


def test_D_現況_大寫a正常_大寫碼與頁型():
    from infra.cache import _normalize_moneydj_url_for_cache as n
    assert n("https://x/p?A=ACDD01&yp=010001") == "fetch_fund|ACDD01|010001"
    assert n("https://x/p?a=ACDD01") == "fetch_fund|ACDD01|default"


def test_D_確認production無呼叫者():
    import pathlib, subprocess
    root = pathlib.Path(__file__).resolve().parents[1]
    out = subprocess.check_output(["git", "grep", "-l", "_normalize_moneydj_url_for_cache", "--", "*.py"], cwd=root, text=True).split()
    prod = [f for f in out if not f.startswith("tests/") and f != "infra/cache.py"]
    assert prod == ["services/fund_identity_shadow.py"]
