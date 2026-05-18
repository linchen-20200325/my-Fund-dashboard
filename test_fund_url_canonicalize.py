"""
test_fund_url_canonicalize — v18.22 抓取規則 audit fix
覆蓋：
- parse_moneydj_input page_type regex 對 `.aspx` / `/w/wb/` / `/w/wr/` 新支援
- canonicalize_moneydj_url 把 mobile / 平台 URL → www.moneydj.com canonical
- is_valid_moneydj_page 第 3 條對 m.moneydj.com 子網域不再死碼
"""
import pytest

from fund_fetcher import (
    canonicalize_moneydj_url,
    is_valid_moneydj_page,
    parse_moneydj_input,
)


# ──────────────────────────────────────────────────────────────────────
# parse_moneydj_input — page_type 擴充
# ──────────────────────────────────────────────────────────────────────
def test_parse_canonical_yp010000_still_detected():
    info = parse_moneydj_input("https://www.moneydj.com/funddj/ya/yp010000.djhtm?a=acdd01")
    assert info["code"] == "ACDD01"
    assert info["page_type"] == "yp010000"


def test_parse_canonical_yp010001_still_detected():
    info = parse_moneydj_input("https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=tlzf9")
    assert info["code"] == "TLZF9"
    assert info["page_type"] == "yp010001"


def test_parse_mobile_a1_aspx_detected_as_page_type():
    """v18.22：行動版 /a1.aspx 不再被當成 page_type=""，標 `a1_mobile`。"""
    info = parse_moneydj_input("https://m.moneydj.com/a1.aspx?a=acdd01")
    assert info["code"] == "ACDD01"
    assert info["page_type"] == "a1_mobile"


def test_parse_chubb_wr01_detected():
    info = parse_moneydj_input(
        "https://chubb.moneydj.com/w/wr/wr01.djhtm?a=ACDD01-EQTAL005"
    )
    assert info["code"] == "ACDD01-EQTAL005"
    assert info["page_type"] == "wr01"


def test_parse_bank_wb02_detected():
    info = parse_moneydj_input(
        "https://chbfund.moneydj.com/w/wb/wb02.djhtm?a=ANZ89-3827"
    )
    assert info["code"] == "ANZ89-3827"
    assert info["page_type"] == "wb02"


def test_parse_taiwanlife_b1_mobile_detected():
    info = parse_moneydj_input(
        "https://taishinlife.moneydj.com/mobile/b1.aspx?a=TLZF9-AL001"
    )
    assert info["code"] == "TLZF9-AL001"
    assert info["page_type"] == "b1_mobile"


# ──────────────────────────────────────────────────────────────────────
# canonicalize_moneydj_url
# ──────────────────────────────────────────────────────────────────────
def test_canonicalize_mobile_a1_to_www_yp010000():
    """ACDD01 是境內前綴 → yp010000。"""
    out = canonicalize_moneydj_url("https://m.moneydj.com/a1.aspx?a=acdd01")
    assert out == "https://www.moneydj.com/funddj/ya/yp010000.djhtm?a=ACDD01"


def test_canonicalize_chubb_wr01_passthrough():
    """平台桌面頁（chubb / tcbbankfund 等 /w/wr/ /w/wb/）**不** canonicalize，
    保留平台後綴給 _BANK_PLATFORM_CODES 路徑處理，才能拿到該保單該基金
    扣手續費後的 NAV（與裸 ACDD01 不同）。"""
    src = "https://chubb.moneydj.com/w/wr/wr01.djhtm?a=ACDD01-EQTAL005"
    assert canonicalize_moneydj_url(src) == src


def test_canonicalize_offshore_code_uses_yp010001():
    """TLZF9 非境內前綴 → yp010001。"""
    out = canonicalize_moneydj_url(
        "https://taishinlife.moneydj.com/mobile/b1.aspx?a=TLZF9-AL001"
    )
    assert out == "https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=TLZF9"


def test_canonicalize_preserves_already_canonical_url():
    """已是 canonical 格式 → 原樣回傳，不重複處理。"""
    src = "https://www.moneydj.com/funddj/ya/yp010000.djhtm?a=ACDD01"
    assert canonicalize_moneydj_url(src) == src


def test_canonicalize_passes_through_non_target_url():
    """其他 MoneyDJ 路徑（如 /funddj/ya/yp081000.djhtm 境外舊頁）原樣回傳。"""
    src = "https://www.moneydj.com/funddj/ya/yp081000.djhtm?a=ANZ89"
    assert canonicalize_moneydj_url(src) == src


def test_canonicalize_handles_empty_or_invalid():
    assert canonicalize_moneydj_url("") == ""
    assert canonicalize_moneydj_url(None) == ""
    assert canonicalize_moneydj_url("not a url") == "not a url"


def test_canonicalize_no_code_in_url_returns_original():
    src = "https://m.moneydj.com/a1.aspx"  # 缺 ?a=
    assert canonicalize_moneydj_url(src) == src


# ──────────────────────────────────────────────────────────────────────
# is_valid_moneydj_page — 第 3 條放寬
# ──────────────────────────────────────────────────────────────────────
def test_is_valid_accepts_m_moneydj_subdomain_html():
    """m.moneydj.com 行動版頁面 HTML 通常不含 `/funddj/` 但仍是合法基金頁。"""
    # 模擬：純英文 HTML（避開 path 1 中文 keyword 短路），長度 > 2000，含 moneydj.com
    fake_html = "<html><body>" + ("x" * 2500) + "<a href='https://m.moneydj.com/'>home</a></body></html>"
    assert is_valid_moneydj_page(fake_html) is True


def test_is_valid_rejects_short_html():
    assert is_valid_moneydj_page("<html></html>") is False
    assert is_valid_moneydj_page("") is False


def test_is_valid_accepts_via_chinese_keywords():
    """path 1：中文 keyword ≥ 2 個（即使無 moneydj.com URL pattern）"""
    # 不耍機巧拼字數：直接 padding 至 600
    fake_html = "x" * 600 + "淨值 基金 日期"
    assert len(fake_html) > 500
    assert is_valid_moneydj_page(fake_html) is True
