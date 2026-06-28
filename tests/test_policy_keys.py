"""
test_policy_keys — T7 複合鍵工具單元測試
覆蓋 make_pk / pk_str / parse_pk / migrate_ledger_dict 的正常 + 邊界 + 跨保單同碼。
"""

from models.policy import (
    PK_SEP,
    fund_pk_str,
    make_pk,
    migrate_ledger_dict,
    parse_pk,
    pk_str,
)


# ──────────────────────────────────────────────────────────────────────
# 1. make_pk：基本生成 + None / 缺欄容錯 + 大小寫正規化
# ──────────────────────────────────────────────────────────────────────
def test_make_pk_full_fund():
    fund = {"code": "tlzf9", "policy_id": "P1", "name": "x"}
    assert make_pk(fund) == ("P1", "TLZF9")


def test_make_pk_no_policy_id_is_empty_string():
    fund = {"code": "TLZF9"}
    assert make_pk(fund) == ("", "TLZF9")


def test_make_pk_none_returns_empty():
    assert make_pk(None) == ("", "")
    assert make_pk({}) == ("", "")
    assert make_pk("not a dict") == ("", "")


# ──────────────────────────────────────────────────────────────────────
# 2. pk_str / parse_pk round-trip + 邊界
# ──────────────────────────────────────────────────────────────────────
def test_pk_str_roundtrip():
    pk = ("P1", "TLZF9")
    s = pk_str(pk)
    assert s == f"P1{PK_SEP}TLZF9"
    assert parse_pk(s) == pk


def test_parse_pk_old_format_falls_back_to_empty_policy():
    """舊鍵（純 code，無 ::） → 視為未綁保單。"""
    assert parse_pk("TLZF9") == ("", "TLZF9")


def test_pk_str_bad_input_returns_empty():
    assert pk_str(("only_one",)) == ""  # noqa
    assert pk_str(None) == ""  # noqa


# ──────────────────────────────────────────────────────────────────────
# 3. fund_pk_str 便利捷徑
# ──────────────────────────────────────────────────────────────────────
def test_fund_pk_str_shortcut():
    assert fund_pk_str({"code": "abc", "policy_id": "P2"}) == f"P2{PK_SEP}ABC"
    assert fund_pk_str({"code": "abc"}) == f"{PK_SEP}ABC"


# ──────────────────────────────────────────────────────────────────────
# 4. migrate_ledger_dict：舊單 code 鍵 → composite，跨保單同碼正確分流
# ──────────────────────────────────────────────────────────────────────
def test_migrate_legacy_keys_with_policy_lookup():
    old = {"TLZF9": "ledger_A", "ABCD": "ledger_B"}
    pf  = [
        {"code": "TLZF9", "policy_id": "P1"},
        {"code": "ABCD"},  # 無 policy_id → 未綁
    ]
    out = migrate_ledger_dict(old, pf)
    assert out == {f"P1{PK_SEP}TLZF9": "ledger_A", f"{PK_SEP}ABCD": "ledger_B"}


def test_migrate_preserves_already_composite_keys():
    old = {
        f"P1{PK_SEP}TLZF9": "ledger_X",
        "ABCD": "ledger_Y",          # 舊鍵需轉
    }
    pf  = [{"code": "ABCD", "policy_id": "P2"}]
    out = migrate_ledger_dict(old, pf)
    assert out[f"P1{PK_SEP}TLZF9"] == "ledger_X"
    assert out[f"P2{PK_SEP}ABCD"] == "ledger_Y"


def test_migrate_unknown_code_falls_back_to_unbound():
    """portfolio_funds 找不到時，舊鍵退回 ("", code)。"""
    old = {"GHOST": "ledger_g"}
    out = migrate_ledger_dict(old, [])
    assert out == {f"{PK_SEP}GHOST": "ledger_g"}


def test_migrate_prefers_fund_with_policy_id_over_unbound():
    """同 code 在 portfolio_funds 出現兩次（一綁一未綁）：取有 policy_id 的那筆。"""
    old = {"DUP": "ledger_d"}
    pf  = [
        {"code": "DUP"},                     # 未綁
        {"code": "DUP", "policy_id": "P9"},  # 已綁
    ]
    out = migrate_ledger_dict(old, pf)
    assert out == {f"P9{PK_SEP}DUP": "ledger_d"}


def test_migrate_empty_dict_returns_empty():
    assert migrate_ledger_dict({}, []) == {}
    assert migrate_ledger_dict(None, []) == {}
