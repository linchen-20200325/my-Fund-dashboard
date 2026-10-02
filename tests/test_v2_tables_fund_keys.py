# -*- coding: utf-8 -*-
"""services/v2_tables/fund_keys.py（L2）測試（fast lane；不打網路）。

`parse_moneydj_input`／`load_fund_code_mapping` 用真的 L1（兩者皆純字串處理／讀本地 csv，不連網）；
預設對照表路徑相對於工作目錄，故以 `monkeypatch.chdir(tmp_path)` 控制 csv 有無。
"""

from __future__ import annotations

import inspect
import re

import pytest

from repositories.fund import sources as SRC
from services.v2_tables import fund_keys as FK


@pytest.fixture
def no_csv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # 工作目錄下沒有 fund_code_mapping.csv → 只用內建表
    return tmp_path


def _one(code, **kw):
    out = FK.resolve_full_keys([code], **kw)
    assert len(out["results"]) == 1
    return out["results"][0], out["provenance"]


# ═══════════════════════ 與 L1 原始碼的漂移鎖 ═══════════════════════

def test_pure_code_pattern_matches_l1_source():
    src = inspect.getsource(SRC.parse_moneydj_input)
    assert f'r"{FK.PURE_CODE_PATTERN}"' in src
    assert "_raw[:30]" in src  # 兜底那一支還在；不在了就要重新判讀本檔的兜底判法


_PARITY_CASES = [
    "TLZF9", "ACDD01-EQTAL005", "ABC", "AB", "A" * 30, "A" * 31, "ABC-D", "ABC-DE", "ABC-" + "D" * 20,
    "ABC-" + "D" * 21, "ABC-DE-FG", "-ABC", "ABC-", "AB C", "abc", "ÄBC", "ＡＢＣ", "１２３", "ABC\n",
    "ABC_1", "", "123", "A1B2C3-Z9",
]


@pytest.mark.parametrize("text", _PARITY_CASES + ["AB-CD", "A", "AB-C"])
def test_is_pure_code_parity_with_l1_regex(text):
    # 用 fullmatch 不用 re.match：L1 的 `^…$` 配 re.match 時 `$` 會匹配結尾 `\n` 之前，
    # "ABC\n" 會算符合；本檔進 L1 前已 strip()，等價判準是「整段完全符合」。
    assert FK._is_pure_code(text) is bool(re.fullmatch(FK.PURE_CODE_PATTERN, text))


def test_why_fullmatch_not_match():
    assert re.match(FK.PURE_CODE_PATTERN, "ABC\n") is not None
    assert re.fullmatch(FK.PURE_CODE_PATTERN, "ABC\n") is None
    assert FK._is_pure_code("ABC\n") is False


def test_l1_empty_path_returns_builtin_silently(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "fund_code_mapping.csv").write_text(
        "input_code,public_code,page_type,note\nQQQ111,QQQ222,yp010001,x\n", encoding="utf-8")
    m = SRC.load_fund_code_mapping(path="")
    assert m == SRC._DEFAULT_MAPPING
    assert capsys.readouterr().out == ""


# ═══════════════════════ 非 ASCII（Unicode 大小寫展開）═══════════════════════

@pytest.mark.parametrize("raw,expanded", [
    ("maß01", "MASS01"),      # ß → SS
    ("actı171", "ACTI171"),   # 無點 ı → I（展開後會命中內建表）
    ("ﬀ123", "FF123"),        # 合字 ﬀ → FF
    ("ſab12", "SAB12"),       # 長 s ſ → S
])
def test_non_ascii_is_error(no_csv, raw, expanded):
    assert raw.upper() == expanded and FK._is_pure_code(expanded)  # 不擋的話會被判成功
    r, _ = _one(raw)
    assert r["ok"] is False and r["full_key"] is None
    assert "ASCII" in r["error"]


def test_non_ascii_chinese(no_csv):
    r, _ = _one("安聯台灣科技")
    assert r["ok"] is False and "ASCII" in r["error"]


# ═══════════════════════ 正規化 ═══════════════════════

@pytest.mark.parametrize("raw", ["tlzf9", "  TLZF9  ", "\tTlZf9\n", "TLZF9"])
def test_case_and_whitespace(no_csv, raw):
    r, _ = _one(raw)
    assert r["ok"] is True
    assert r["full_key"] == "TLZF9"
    assert r["portal"] == ""
    assert r["input"] == raw
    assert r["error"] is None


# ═══════════════════════ 對照表 ═══════════════════════

def test_builtin_mapping_hit(no_csv):
    assert SRC._DEFAULT_MAPPING["ACTI171"]["public_code"] == "ACTI71"  # 挑的那一筆
    r, prov = _one("acti171")
    assert r["ok"] is True
    assert r["mapping_hit"] is True
    assert r["parsed_code"] == "ACTI171"
    assert r["full_key"] == "ACTI71"
    assert r["portal"] == ""
    assert prov["mapping_source"] == FK.MAPPING_SOURCE_BUILTIN
    assert prov["mapping_size"] == len(SRC._DEFAULT_MAPPING)


@pytest.mark.parametrize("raw,expected", [("zzz999", "ZZZ999"),
                                          ("acdd01-eqtal005", "ACDD01-EQTAL005")])
def test_mapping_miss_passes_through(no_csv, raw, expected):
    r, _ = _one(raw)
    assert r["ok"] is True
    assert r["mapping_hit"] is False
    assert r["full_key"] == expected


def test_injected_mapping(no_csv):
    m = {"ABC123": {"public_code": "XYZ789", "page_type": "yp010001", "note": ""}}
    r, prov = _one(" abc123 ", mapping=m)
    assert r["full_key"] == "XYZ789" and r["mapping_hit"] is True
    assert prov["mapping_source"] == FK.MAPPING_SOURCE_INJECTED
    assert prov["mapping_size"] == 1
    # 注入表裡沒有內建表的那一筆 → 原樣輸出
    r2, _ = _one("ACTI171", mapping=m)
    assert r2["full_key"] == "ACTI171" and r2["mapping_hit"] is False


def test_injected_mapping_bad_value_is_error(no_csv):
    for bad in ({"public_code": ""}, {"public_code": None}, {"public_code": " X "}, "ACTI71", {}):
        r, _ = _one("ABC123", mapping={"ABC123": bad})
        assert r["ok"] is False and r["full_key"] is None and "public_code" in r["error"]


@pytest.mark.parametrize("pub", ["acti71", "ACTI 71", "A" * 200, "NAN", "NONE", "AB", "A-"])
def test_injected_mapping_public_code_rechecked(no_csv, pub):
    r, _ = _one("ABC123", mapping={"ABC123": {"public_code": pub}})
    assert r["ok"] is False and r["full_key"] is None and "public_code" in r["error"]


@pytest.mark.parametrize("key,exc", [("abc123", ValueError), (" ABC123", ValueError),
                                     ("AB", ValueError), (123, TypeError)])
def test_injected_mapping_bad_key_raises(key, exc):
    with pytest.raises(exc):
        FK.resolve_full_keys(["ABC123"], mapping={key: {"public_code": "XYZ789"}})


def test_csv_blank_public_code_becomes_nan_and_fails(no_csv):
    (no_csv / "fund_code_mapping.csv").write_text(
        "input_code,public_code,page_type,note\nqqq111,,yp010001,留空\n", encoding="utf-8")
    assert SRC.load_fund_code_mapping()["QQQ111"]["public_code"] == "NAN"  # L1 的實際行為
    r, prov = _one("QQQ111")
    assert prov["mapping_source"] == FK.MAPPING_SOURCE_CSV
    assert r["ok"] is False and r["full_key"] is None and "NAN" in r["error"]


def test_injected_mapping_must_be_dict():
    with pytest.raises(TypeError):
        FK.resolve_full_keys(["ABC123"], mapping=[("ABC123", "X")])


def test_csv_mapping_provenance(no_csv, capsys):
    (no_csv / "fund_code_mapping.csv").write_text(
        "input_code,public_code,page_type,note\nqqq111,QQQ222,yp010001,測試\n", encoding="utf-8")
    r, prov = _one("QQQ111")
    assert r["full_key"] == "QQQ222"
    assert prov["mapping_source"] == FK.MAPPING_SOURCE_CSV
    assert prov["mapping_size"] == len(SRC._DEFAULT_MAPPING) + 1
    assert "[mapping]" in capsys.readouterr().out  # L1 的 print 未被攔下


def test_csv_read_failure_falls_back_to_builtin(no_csv, capsys):
    (no_csv / "fund_code_mapping.csv").mkdir()  # 存在但讀不了
    r, prov = _one("ACTI171")
    assert r["full_key"] == "ACTI71"  # 退回內建表
    # 本層分辨不出「csv 不存在」與「csv 讀取失敗」，兩者都標 builtin（檔頭寫明）
    assert prov["mapping_source"] == FK.MAPPING_SOURCE_BUILTIN
    assert "讀取失敗" in capsys.readouterr().out  # L1 的 print 未被攔下


def test_l1_exception_propagates(monkeypatch):
    def boom():
        raise RuntimeError("L1 壞了")
    monkeypatch.setattr(FK, "load_fund_code_mapping", boom)
    with pytest.raises(RuntimeError, match="L1 壞了"):
        FK.resolve_full_keys(["TLZF9"])


# ═══════════════════════ 錯誤路徑 ═══════════════════════

@pytest.mark.parametrize("raw", ["", "   ", "\n"])
def test_empty_string(no_csv, raw):
    r, _ = _one(raw)
    assert r["ok"] is False and r["full_key"] is None and r["portal"] is None
    assert "空" in r["error"]


@pytest.mark.parametrize("raw", [
    "AB C",            # 中間有空白
    "A" * 31,          # 超過 30 字元 → L1 兜底會截成 30
    "TLZF9!",          # 標點
    "AB",              # 主碼 2 字元（少於 3）
    "AB-CD",           # 主碼 2 字元＋後綴
])
def test_fallback_is_error(no_csv, raw):
    info = SRC.parse_moneydj_input(raw.strip().upper())
    assert info["is_url"] is False
    assert info["code"] == raw.strip().upper()[:30]  # 確認這些輸入真的走 L1 兜底那一支
    r, _ = _one(raw)
    assert r["ok"] is False and r["full_key"] is None
    assert "兜底" in r["error"]


def test_fallback_not_truncated(no_csv):
    r, _ = _one("A" * 31)
    assert r["full_key"] is None
    assert r["parsed_code"] == "A" * 30  # 記下 L1 給的值供診斷，但不當成 full_key


@pytest.mark.parametrize("raw", [123, None, 1.5, b"TLZF9", ["TLZF9"]])
def test_non_string(no_csv, raw):
    r, _ = _one(raw)
    assert r["ok"] is False and r["full_key"] is None
    assert "字串" in r["error"]


def test_fund_codes_must_be_sequence():
    with pytest.raises(TypeError):
        FK.resolve_full_keys("TLZF9")


# ═══════════════════════ 網址輸入 ═══════════════════════

def test_url_extracts_code(no_csv):
    url = "https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=tlzf9"
    assert SRC.parse_moneydj_input(url.upper())["code"] == "TLZF9"  # L1 實際行為
    r, _ = _one(url)
    assert r["ok"] is True and r["full_key"] == "TLZF9"


def test_url_code_goes_through_mapping(no_csv):
    r, _ = _one("https://www.moneydj.com/funddj/ya/yp010000.djhtm?a=acti171")
    assert r["full_key"] == "ACTI71" and r["mapping_hit"] is True


def test_url_without_code_is_error(no_csv):
    r, _ = _one("https://www.moneydj.com/funddj/ya/yp010001.djhtm")
    assert r["ok"] is False and "抽不出" in r["error"]


def test_url_overlong_code_is_error(no_csv):
    long = "B" * 40
    url = f"https://www.moneydj.com/funddj/ya/yp010001.djhtm?a={long}"
    assert SRC.parse_moneydj_input(url)["code"] == "B" * 30  # L1 會靜默截斷
    r, _ = _one(url)
    assert r["ok"] is False and r["full_key"] is None and "截" in r["error"]


@pytest.mark.parametrize("value", ["AB", "A-", "A--------", "ACTI71%20X", "ACTI71/X", "ACTI71?X", "ACTI71 X"])
def test_url_bad_a_value_is_error(no_csv, value):
    r, _ = _one(f"https://www.moneydj.com/funddj/ya/yp010001.djhtm?a={value}")
    assert r["ok"] is False and r["full_key"] is None


@pytest.mark.parametrize("url,expected", [
    ("https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=tlzf9#top", "TLZF9"),
    ("https://www.moneydj.com/funddj/ya/yp010001.djhtm?x=1&a=tlzf9", "TLZF9"),
    ("https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=TLZF9&a=TLZF9", "TLZF9"),
    ("https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=tlzf9&A=TLZF9", "TLZF9"),
])
def test_url_ok_variants(no_csv, url, expected):
    r, _ = _one(url)
    assert r["ok"] is True and r["full_key"] == expected


@pytest.mark.parametrize("url", [
    "https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=TLZF9&a=ACTI71",
    "https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=TLZF9&A=ACTI71",
    "https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=%41CTI71&a=ACTI71",
])
def test_url_conflicting_a_values_is_error(no_csv, url):
    r, _ = _one(url)
    assert r["ok"] is False and r["full_key"] is None


def test_url_code_followed_by_other_param_ok(no_csv):
    r, _ = _one("https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=tlzf9&b=1")
    assert r["ok"] is True and r["full_key"] == "TLZF9"


# ═══════════════════════ 決定性 ═══════════════════════

def test_deterministic_and_order_preserved(no_csv):
    codes = ["tlzf9", "ACTI171", "AB C", "", 5, "TLZF9"]
    a = FK.resolve_full_keys(codes)
    b = FK.resolve_full_keys(list(codes))
    assert a == b
    assert [r["input"] for r in a["results"]] == codes
    assert a["results"][0] == {**a["results"][5], "input": "tlzf9"}


# ═══════════════════════ 第三輪：查詢字串限定、空白格、mapping_hit ═══════════════════════

@pytest.mark.parametrize("url", [
    "https://x/#&a=FOO123",
    "https://x/#?a=FOO123",
    "https://x/p1&a=FOO123",
    "https://x/p%3FBAR456+&A=ACDD01-EQTAL005",
])
def test_url_a_outside_query_is_error(no_csv, url):
    assert SRC.parse_moneydj_input(url.upper())["code"] != ""  # L1 確實抽到了代碼
    r, _ = _one(url)
    assert r["ok"] is False and r["full_key"] is None
    assert "查詢字串" in r["error"]  # 走的是「查詢字串裡沒有 a=」那一支


def test_url_fragment_a_ignored(no_csv):
    r, _ = _one("https://x/?a=FOO#frag&a=FOO")
    assert r["ok"] is True and r["full_key"] == "FOO"


def test_url_fragment_a_with_other_value_ignored(no_csv):
    r, _ = _one("https://x/?a=FOO123#frag&a=BAR456")
    assert r["ok"] is True and r["full_key"] == "FOO123"


def test_url_query_without_a_param_is_error(no_csv):
    # L1 從片段裡抽到 FOO123，但查詢字串（?x=1）裡沒有 a=
    r, _ = _one("https://x/p?x=1#&a=FOO123")
    assert r["ok"] is False and "查詢字串" in r["error"]


def test_url_a_param_name_must_be_exact(no_csv):
    # `ba=` 不是 a=；L1 的 `[?&][aA]=` 也抽不到，走「抽不出代碼」
    r, _ = _one("https://x/?ba=FOO123")
    assert r["ok"] is False and r["full_key"] is None


def test_csv_whitespace_public_code_fails_at_final_check(no_csv):
    (no_csv / "fund_code_mapping.csv").write_text(
        "input_code,public_code,page_type,note\nqqq111,  ,yp010001,只有空白\n", encoding="utf-8")
    assert SRC.load_fund_code_mapping()["QQQ111"]["public_code"] == ""  # L1 strip 後是空字串
    r, _ = _one("QQQ111")
    assert r["ok"] is False and r["full_key"] is None
    assert "不符" in r["error"]  # 由最終關卡 `_is_pure_code` 擋下，不是 public_code 讀值那一關
    assert r["mapping_hit"] is True


def test_csv_inner_space_public_code_fails_at_final_check(no_csv):
    (no_csv / "fund_code_mapping.csv").write_text(
        "input_code,public_code,page_type,note\nqqq111,acti 71,yp010001,中間空白\n", encoding="utf-8")
    assert SRC.load_fund_code_mapping()["QQQ111"]["public_code"] == "ACTI 71"  # L1 只 strip，中間空白保留
    r, prov = _one("QQQ111")
    assert prov["mapping_source"] == FK.MAPPING_SOURCE_CSV
    assert r["ok"] is False and r["full_key"] is None
    assert "不符" in r["error"]  # 最終關卡 `_is_pure_code`
    assert r["mapping_hit"] is True


@pytest.mark.parametrize("url", [
    "https://x/?a=FOO123;b=2",        # `;` 不當參數分隔（擋 Z3）
    "https://u:p?w@x/?a=FOO123",      # 第一個 `?` 在帳密裡，查詢字串從那裡起算（擋 Z5）
    "https://x/?x=1?a=FOO123",        # 第二個 `?` 不是參數分隔
    "https://x/?a=FOO123&a",          # 沒等號的 a
    "https://x/?a&a=FOO123",          # 沒等號的 a
])
def test_url_query_edge_cases_are_error(no_csv, url):
    assert SRC.parse_moneydj_input(url.upper())["code"] == "FOO123"  # L1 都抽得到
    r, _ = _one(url)
    assert r["ok"] is False and r["full_key"] is None


def test_mapping_hit_on_failure_is_truthful(no_csv):
    m = {"ABC123": {"public_code": "acti71"}}
    r_hit, _ = _one("ABC123", mapping=m)
    assert r_hit["ok"] is False and r_hit["mapping_hit"] is True       # 查了、命中、值不合格
    r_nan, _ = _one("ABC123", mapping={"ABC123": {"public_code": "NAN"}})
    assert r_nan["ok"] is False and r_nan["mapping_hit"] is True
    r_pre, _ = _one("AB C", mapping=m)
    assert r_pre["ok"] is False and r_pre["mapping_hit"] is None       # 沒走到查表
    r_url, _ = _one("https://x/?a=AB", mapping=m)
    assert r_url["ok"] is False and r_url["mapping_hit"] is False      # 查了、沒命中、最終關卡擋
