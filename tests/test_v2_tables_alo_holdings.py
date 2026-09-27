# -*- coding: utf-8 -*-
"""services/v2_tables/alo_holdings.py（L2）與 contract 的 `holding`／`policy` 鏡像測試（fast lane）。

每個測試名前綴標出它守的裁示：T6、R1、U6、U7、U9、U10、U11、U4、C1/D3、C4、T2、契約。
`build_alo_tables` 是純函式，直接餵 L1 形狀的假輸入；`load_alo_tables` 另以假 gspread 走一次整條路。
"""

from __future__ import annotations

import pathlib
import re

import pytest

from _fake_settings_sheet import FakeClient, FakeSpreadsheet, FakeWorksheet
from infra import gspread_retry as GR
from infra import source_backoff as SB
from repositories import policy_supplement_repository as R
from services.v2_tables import alo_holdings as A
from services.v2_tables import contract

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_D44 = _ROOT / "docs" / "v2" / "44_fund_ui_ssot.md"

S, P = R.TAB_HOLDING_SUPPLEMENT, R.TAB_POLICY_PROFILE
WARN = "DIRECT 列暫不支援，該筆不計入配置"


# ─────────────── 假輸入 ───────────────

def prow(pid="PX-TEST-001", code="ZZ9999", name="測試基金甲", ccy="USD", invest=300000,
         units=1000.0, avg_nav=10.0, **extra):
    """保單分頁一列（`ALL_COLS_V2` 欄名，值照既有讀取函式的樣子）。"""
    row = {"policy_id": pid, "fund_code": code, "fund_name": name, "currency": ccy, "tier": "core",
           "invest_twd": invest, "div_cash_pct": 100.0, "units": units, "avg_nav": avg_nav,
           "avg_fx": 30.0}
    row.update(extra)
    return row


def srec(row, pid="PX-TEST-001", code="ZZ9999", opened="2001-01-01", checked="2001-02-03",
         bucket="測試類別甲"):
    return {"_row": row, "_raw": (pid, code, opened, checked, bucket or ""), "policy_id": pid,
            "fund_code": code, "opened_on": opened, "last_checked_on": checked, "bucket": bucket}


def precd(row, pid="PX-TEST-001", name="測試保單甲", issuer="測試人壽", ccy="USD", premium=123456,
          opened="2001-01-01", status="active"):
    return {"_row": row, "_raw": (pid, name, issuer, ccy, str(premium), opened, status),
            "policy_id": pid, "policy_name": name, "issuer": issuer, "ccy": ccy,
            "premium_paid_twd": premium, "opened_on": opened, "status": status}


def tabs(supp=(), prof=(), supp_bad=(), prof_bad=(), supp_missing=False, prof_missing=False):
    return {S: {"records": list(supp), "bad_rows": list(supp_bad), "blank_rows": 0,
                "tab_missing": supp_missing},
            P: {"records": list(prof), "bad_rows": list(prof_bad), "blank_rows": 0,
                "tab_missing": prof_missing}}


def build(rows, t):
    return A.build_alo_tables(rows, t)


# ═══════════════════════ 基本正例 ═══════════════════════

def test_正例_一列持倉與一列保單照44寫出():
    out = build([prow()], tabs([srec(2)], [precd(2)]))
    (h,) = out["holding"]
    assert h == {"holding_id": "PX-TEST-001|ZZ9999|1", "policy_id": "PX-TEST-001",
                 "fund_code": "ZZ9999", "fund_name": "測試基金甲", "ccy": "USD",
                 "units_shares": 1000.0, "cost_orig_ccy": 10000.0, "cost_twd": 300000,
                 "opened_on": "2001-01-01", "bucket": "測試類別甲",
                 "last_synced_at": "2001-02-03T04:00:00Z"}
    assert contract.holding_row_problems(h) == []
    (p,) = out["policy"]
    assert contract.policy_row_problems(p) == []
    assert out["warnings"] == [] and out["skipped_holdings"] == []


# ═══════════════════════ R1：最後核對日 → 當日 12:00 台灣時間 ═══════════════════════

@pytest.mark.parametrize("day,expected", [
    ("2001-02-03", "2001-02-03T04:00:00Z"),
    ("2001-01-31", "2001-01-31T04:00:00Z"),   # 月底
    ("2001-12-31", "2001-12-31T04:00:00Z"),   # 年底
    ("2001-04-30", "2001-04-30T04:00:00Z"),   # 30 日的月底
    ("2024-02-29", "2024-02-29T04:00:00Z"),   # 閏年
    ("2000-02-29", "2000-02-29T04:00:00Z"),   # 世紀閏年
    ("2001-03-01", "2001-03-01T04:00:00Z"),   # 月初：日期不前移
])
def test_R1_正例_換算邊界_日期不前移不後移(day, expected):
    assert A.last_synced_at_from_check_date(day) == expected


@pytest.mark.parametrize("bad", [
    "2001-02-29", "1900-02-29", "2001-02-30", "2001-04-31", "2001/02/03", "2001-2-3", "20010203",
    "2001-02-03 10:00", "2001-02-03T04:00:00Z", "2001-02-03T10:20:30", "2001-02-03T10:20:30+08:00",
    "２００１-０２-０３", "", None, 36925,
])
def test_R1_反例_格式錯閏年錯帶時間一律拒收不猜(bad):
    with pytest.raises(ValueError):
        A.last_synced_at_from_check_date(bad)


def test_R1_正例_不以讀取時間冒充_同一份輸入重跑結果相同():
    t = tabs([srec(2, checked="2001-01-31")], [precd(2)])
    first = build([prow()], t)["holding"][0]["last_synced_at"]
    second = build([prow()], t)["holding"][0]["last_synced_at"]
    assert first == second == "2001-01-31T04:00:00Z"


def test_R1_正例_last_synced_at通過契約的世界協調時間檢查():
    row = build([prow()], tabs([srec(2)], [precd(2)]))["holding"][0]
    assert row["last_synced_at"].endswith("Z")
    assert contract.holding_row_problems(row) == []


# ═══════════════════════ U6：沒有時區的時間拒收（R1 下只保留紀錄）═══════════════════════

def test_U6_反例_沒有時區的時間拒收():
    with pytest.raises(ValueError):
        A.last_synced_at_from_check_date("2001-02-03T12:00:00")


def test_U6_R1下有時區的時間同樣拒收_U6沒有套用對象():
    for text in ("2001-02-03T04:00:00Z", "2001-02-03T12:00:00+08:00"):
        with pytest.raises(ValueError):
            A.last_synced_at_from_check_date(text)


def test_U6_正例_契約的時間欄只收世界協調時間():
    row = build([prow()], tabs([srec(2)], [precd(2)]))["holding"][0]
    assert contract.holding_row_problems(dict(row, last_synced_at="2001-02-03T12:00:00")) != []
    assert contract.holding_row_problems(row) == []


# ═══════════════════════ U10：淨投資金額空白＝沒填 ═══════════════════════

@pytest.mark.parametrize("invest", [0, None, ""])
def test_U10_反例_淨投資金額空白不寫入也不補0(invest):
    out = build([prow(invest=invest)], tabs([srec(2)], [precd(2)]))
    assert out["holding"] == []
    (s,) = out["skipped_holdings"]
    assert "淨投資金額空白（沒填）" in s["reasons"]


def test_U10_正例_有填就寫入_且照原值不改():
    out = build([prow(invest=1)], tabs([srec(2)], [precd(2)]))
    assert out["holding"][0]["cost_twd"] == 1


def test_U10_反例_非整數本金不寫入():
    out = build([prow(invest=12.5)], tabs([srec(2)], [precd(2)]))
    assert out["holding"] == [] and "不是正整數" in out["skipped_holdings"][0]["reasons"][0]


@pytest.mark.parametrize("field", ["units", "avg_nav"])
@pytest.mark.parametrize("value", [0.0, None, ""])
def test_Q4a_反例_單位數或平均成本為0或空白不寫入(field, value):
    out = build([prow(**{field: value})], tabs([srec(2)], [precd(2)]))
    assert out["holding"] == [] and out["skipped_holdings"]


# ═══════════════════════ U11：前導 0 ═══════════════════════

def test_U11_正例_兩邊都是文字且逐字相同才比對得上():
    out = build([prow(code="0050")], tabs([srec(2, code="0050")], [precd(2)]))
    assert out["holding"][0]["fund_code"] == "0050"


def test_U11_反例_保單分頁代號被轉成數字_不猜原本字串_不寫入並寫明原因():
    out = build([prow(code=50)], tabs([srec(2, code="0050")], [precd(2)]))
    assert out["holding"] == []
    assert "前導 0" in out["skipped_holdings"][0]["reasons"][0]
    assert out["orphan_supplement"] == [{"row": 2, "key": ("PX-TEST-001", "0050")}]


def test_U11_反例_即使數字轉回字串相同也不比對():
    out = build([prow(code=50)], tabs([srec(2, code="50")], [precd(2)]))
    assert out["holding"] == []


def test_U11_反例_不補前導0():
    out = build([prow(code="50")], tabs([srec(2, code="0050")], [precd(2)]))
    assert out["holding"] == [] and out["missing_supplement"] == [
        {"policy_id": "PX-TEST-001", "fund_code": "50"}]


def test_U11_反例_保單編號被轉成數字同樣不比對():
    out = build([prow(pid=12345)], tabs([srec(2, pid="12345")], [precd(2, pid="12345")]))
    assert out["holding"] == [] and out["policy"] == []


def test_鍵只去前後空白_不改大小寫():
    out = build([prow(code=" zz9999 ")], tabs([srec(2, code="ZZ9999")], [precd(2)]))
    assert out["holding"] == []
    out = build([prow(code=" ZZ9999 ")], tabs([srec(2, code="ZZ9999")], [precd(2)]))
    assert out["holding"][0]["fund_code"] == "ZZ9999"


# ═══════════════════════ U7：重複、孤兒、缺列 ═══════════════════════

def test_U7_反例_持倉補充同鍵兩列_整組不採用_即使內容相同():
    out = build([prow()], tabs([srec(2), srec(3)], [precd(2)]))
    assert out["holding"] == []
    assert out["duplicate_supplement"] == [{"key": ("PX-TEST-001", "ZZ9999"), "rows": [2, 3]}]
    assert out["skipped_holdings"][0]["reasons"] == ["_持倉補充 同一組鍵有兩列以上，整組不採用"]
    assert out["missing_supplement"] == []       # 重複不是缺列


def test_U7_反例_缺持倉補充_該持倉不寫入並列出():
    out = build([prow()], tabs([], [precd(2)]))
    assert out["holding"] == []
    assert out["missing_supplement"] == [{"policy_id": "PX-TEST-001", "fund_code": "ZZ9999"}]


def test_U7_正例_孤兒列略過並列出列號():
    out = build([prow()], tabs([srec(2), srec(3, code="ZZ7777")], [precd(2), precd(4, pid="PX-TEST-404")]))
    assert len(out["holding"]) == 1
    assert out["orphan_supplement"] == [{"row": 3, "key": ("PX-TEST-001", "ZZ7777")}]
    assert out["orphan_profile"] == [{"row": 4, "key": "PX-TEST-404"}]


def test_U7_反例_保單資料同保單編號兩列_整組不採用_持倉不受影響():
    out = build([prow()], tabs([srec(2)], [precd(2), precd(3)]))
    assert out["policy"] == []
    assert out["duplicate_profile"] == [{"key": "PX-TEST-001", "rows": [2, 3]}]
    assert len(out["holding"]) == 1
    assert out["missing_profile"] == []     # 重複不另計缺列


def test_U7_反例_缺保單資料_該保單列不寫入並列出():
    out = build([prow()], tabs([srec(2)], []))
    assert out["policy"] == [] and out["missing_profile"] == ["PX-TEST-001"]
    assert len(out["holding"]) == 1


# ═══════════════════════ T2：holding_id 組法寫死、可重現 ═══════════════════════

def test_T2_正例_同鍵多列各自一列_ID依讀取順序編號且可重現():
    rows = [prow(invest=100), prow(code="ZZ8888"), prow(invest=200)]
    t = tabs([srec(2), srec(3, code="ZZ8888")], [precd(2)])
    ids = [h["holding_id"] for h in build(rows, t)["holding"]]
    assert ids == ["PX-TEST-001|ZZ9999|1", "PX-TEST-001|ZZ8888|1", "PX-TEST-001|ZZ9999|2"]
    assert ids == [h["holding_id"] for h in build(rows, t)["holding"]]
    assert len(set(ids)) == 3


# ═══════════════════════ U9：DIRECT ═══════════════════════

def test_U9_保單分頁的DIRECT持倉_照讀_不計入持倉_逐字警示():
    rows = [prow(pid="DIRECT", code="ZZ5555", name="測試基金丙"), prow()]
    out = build(rows, tabs([srec(2), srec(3, pid="DIRECT", code="ZZ5555")], [precd(2)]))
    assert [h["policy_id"] for h in out["holding"]] == ["PX-TEST-001"]
    assert any(d["policy_id"] == "DIRECT" and d.get("fund_code") == "ZZ5555"
               and d["source"] == "保單分頁" for d in out["direct"])
    assert [w["message"] for w in out["warnings"]] == [WARN, WARN]
    assert out["orphan_supplement"] == []      # DIRECT 那一列補充不算孤兒
    (supp_entry,) = [d for d in out["direct"] if d["source"] == S]
    # 總管 2026-09-27 更正：DIRECT 持倉的 `_持倉補充` 三欄照常讀（U9 的三欄指 policy 欄）
    assert supp_entry["opened_on"] == "2001-01-01"
    assert supp_entry["last_synced_at"] == "2001-02-03T04:00:00Z"
    assert supp_entry["bucket"] == "測試類別甲"


def test_U9_DIRECT的持倉補充列格式不符_照規格列入bad_rows不豁免():
    bad = {"row": 3, "reason": "最後核對日：只收 YYYY-MM-DD 日期（'2001/02/03'）",
           "cells": ["DIRECT", "ZZ5555", "2001-01-01", "2001/02/03", ""]}
    out = build([prow()], tabs([srec(2)], [precd(2)], supp_bad=[bad]))
    assert out["bad_rows"][S] == [bad]
    assert out["warnings"] == []


def test_U9_保單資料DIRECT列三欄有填也不產生值_同時產生警示():
    prof = [precd(2), precd(3, pid="DIRECT", issuer="測試人壽乙", ccy="TWD", opened="2002-02-02")]
    out = build([prow()], tabs([srec(2)], prof))
    (d,) = [d for d in out["direct"] if d["source"] == P]
    assert not ({"issuer", "ccy", "opened_on"} & set(d))
    assert "測試人壽乙" not in repr(out) and "2002-02-02" not in repr(out)
    assert all(p["policy_id"] != "DIRECT" for p in out["policy"])
    assert [w["message"] for w in out["warnings"]] == [WARN]


def test_U9_保單資料的DIRECT列_照讀但不寫三欄_不產生policy列():
    prof = [precd(2), precd(3, pid="DIRECT", name="測試保單乙")]
    out = build([prow()], tabs([srec(2)], prof))
    assert [p["policy_id"] for p in out["policy"]] == ["PX-TEST-001"]
    (d,) = [d for d in out["direct"] if d["source"] == P]
    for col in A.DIRECT_UNWRITTEN_COLUMNS:
        assert col not in d
    assert d["policy_name"] == "測試保單乙"
    assert out["warnings"] == [{"code": "direct_unsupported", "message": WARN, "source": P,
                                "row": 3, "policy_id": "DIRECT"}]


def test_U9_保單資料的DIRECT列三欄空白_不算格式不符_照樣警示():
    bad = {"row": 3, "reason": "發行單位：不可空", "cells": ["DIRECT", "測試保單乙", "", "", "0", "", "active"]}
    out = build([prow()], tabs([srec(2)], [precd(2)], prof_bad=[bad]))
    assert out["bad_rows"][P] == []
    assert out["warnings"][0]["message"] == WARN and out["warnings"][0]["row"] == 3


def test_U9_反例_非DIRECT列不產生警示_且不出現直接持有字樣():
    out = build([prow()], tabs([srec(2)], [precd(2)]))
    assert out["warnings"] == [] and out["direct"] == []
    assert "直接持有" not in repr(out)


def test_U9_警示字樣逐字():
    assert A.DIRECT_WARNING == WARN
    assert A.DIRECT_UNWRITTEN_COLUMNS == ("issuer", "ccy", "opened_on")


# ═══════════════════════ U4、C1/D3 ═══════════════════════

def test_U4_fee_rate_pct恆為空不以0代替():
    (p,) = build([prow()], tabs([srec(2)], [precd(2)]))["policy"]
    assert p["fee_rate_pct"] is None


def test_C1_D3_類別照讀_空白為空值_不取保單分頁的級別():
    out = build([prow(tier="satellite")], tabs([srec(2, bucket=None)], [precd(2)]))
    assert out["holding"][0]["bucket"] is None
    out = build([prow(tier="satellite")], tabs([srec(2, bucket="測試類別乙")], [precd(2)]))
    assert out["holding"][0]["bucket"] == "測試類別乙"


def test_C4_L2沒有任何寫入函式():
    public = [n for n in dir(A) if not n.startswith("_")]
    for word in ("write", "save", "append", "update", "delete", "put"):
        assert not [n for n in public if word in n.lower()], word


# ═══════════════════════ 契約鏡像（真相源是 `44`）═══════════════════════

def _strip_struck(text: str) -> str:
    return re.sub(r"~~.*?~~", "", text)


def _table_from_44(name: str):
    text = _D44.read_text(encoding="utf-8")
    sec4 = text[text.index("## 4. 資料庫結構"): text.index("## 5. 元件清單")]
    head = re.search(rf"(?m)^#{{3,4}} (?:[0-9.]+ )?表 `{name}`", sec4)
    assert head, f"44 第四節找不到 {name} 表"
    rest = sec4[head.end():]
    nxt = re.search(r"(?m)^#{3,4} ", rest)
    body = rest[: nxt.start()] if nxt else rest
    fields, meanings = [], {}
    for line in body.split("\n"):
        m = re.match(r"^\| `([a-z_]+)` \| ([^|]+) \| ([^|]+) \| ([^|]+) \| (.*) \|\s*$", line)
        if m:
            col, typ, _unit, nullable, meaning = (g.strip() for g in m.groups())
            fields.append((col, typ, nullable == "是"))
            meanings[col] = _strip_struck(meaning)
    return tuple(fields), meanings


def test_契約_holding與44逐欄相同():
    fields, _ = _table_from_44("holding")
    assert len(fields) == 11, fields
    assert contract.HOLDING_FIELDS == fields


def test_契約_policy與44逐欄相同_status值域相同():
    fields, meanings = _table_from_44("policy")
    assert len(fields) == 8, fields
    assert contract.POLICY_FIELDS == fields
    assert tuple(re.findall(r"`([a-z_]+)`", meanings["status"])) == contract.POLICY_STATUS_VALUES
    assert "`DIRECT`" in meanings["policy_id"]


def test_契約_L1的status值域與讀出欄名對得上contract():
    assert R.STATUS_VALUES == contract.POLICY_STATUS_VALUES
    holding_cols = {n for n, _t, _nl in contract.HOLDING_FIELDS}
    policy_cols = {n for n, _t, _nl in contract.POLICY_FIELDS}
    for _h, name, _k, _nl in R.HOLDING_SUPPLEMENT_SPEC:
        assert name in holding_cols | {"last_checked_on"}, name
    for _h, name, _k, _nl in R.POLICY_PROFILE_SPEC:
        assert name in policy_cols, name


def test_契約_holding_row_problems_正反例():
    good = build([prow()], tabs([srec(2)], [precd(2)]))["holding"][0]
    assert contract.holding_row_problems(good) == []
    assert contract.holding_row_problems(dict(good, units_shares=0.0))
    assert contract.holding_row_problems(dict(good, cost_twd=0))
    assert contract.holding_row_problems(dict(good, ccy="usd"))
    assert contract.holding_row_problems(dict(good, bucket=""))
    assert contract.holding_row_problems(dict(good, opened_on="2001/01/01"))
    assert contract.holding_row_problems({k: v for k, v in good.items() if k != "last_synced_at"})


def test_契約_policy_row_problems_正反例():
    good = build([prow()], tabs([srec(2)], [precd(2)]))["policy"][0]
    assert contract.policy_row_problems(good) == []
    assert contract.policy_row_problems(dict(good, status="Active"))
    assert contract.policy_row_problems(dict(good, premium_paid_twd=-1))
    assert contract.policy_row_problems(dict(good, ccy="US"))
    assert contract.policy_row_problems(dict(good, issuer=None))
    assert contract.policy_row_problems(dict(good, fee_rate_pct=1.2)) == []


# ═══════════════════════ 整條路：L3 → L2 → L1（假 gspread）═══════════════════════

HS_HEAD = [h for h, *_ in R.HOLDING_SUPPLEMENT_SPEC]
PP_HEAD = [h for h, *_ in R.POLICY_PROFILE_SPEC]


@pytest.fixture
def live(monkeypatch):
    import pandas as pd
    book = FakeSpreadsheet()
    secrets = {"POLICY_SHEET_ID": "policy-book-under-test",
               "google_service_account": {"client_email": "sa@example.iam.gserviceaccount.com"}}
    monkeypatch.setattr(R, "get_secret", lambda key, default=None: secrets.get(key, default))
    monkeypatch.setattr(R, "_make_client", lambda creds: FakeClient(book))
    monkeypatch.setattr(GR.time, "sleep", lambda _s: None)
    rows = [prow(), prow(pid="DIRECT", code="ZZ5555")]
    monkeypatch.setattr(R, "_policy_loader", lambda client, sid: (pd.DataFrame(rows), [], []))
    R.clear_cache()
    SB.reset_all()
    yield book, secrets
    R.clear_cache()
    SB.reset_all()


def test_整條路_正例_讀兩張補充分頁與保單分頁_只讀不寫(live):
    book, _s = live
    book.tabs[S] = FakeWorksheet(book, S, [HS_HEAD, ["PX-TEST-001", "ZZ9999", "2001-01-01", "2001-02-03", ""]])
    book.tabs[P] = FakeWorksheet(book, P, [PP_HEAD, ["PX-TEST-001", "測試保單甲", "測試人壽", "USD",
                                                     "123456", "2001-01-01", "active"]])
    out = A.load_alo_tables([])
    assert [h["holding_id"] for h in out["holding"]] == ["PX-TEST-001|ZZ9999|1"]
    assert out["holding"][0]["last_synced_at"] == "2001-02-03T04:00:00Z"
    assert [p["policy_id"] for p in out["policy"]] == ["PX-TEST-001"]
    assert [w["message"] for w in out["warnings"]] == [WARN]
    assert book.writes() == []


def test_整條路_反例_標頭不符往上拋_不回空表冒充成功(live):
    book, _s = live
    book.tabs[S] = FakeWorksheet(book, S, [["保單編號", "基金代號"]])
    with pytest.raises(A.PolicySupplementError) as err:
        A.load_alo_tables([])
    assert err.value.code == "header_mismatch"


def test_整條路_反例_未設ID往上拋(live):
    _book, secrets = live
    secrets.pop("POLICY_SHEET_ID")
    with pytest.raises(A.PolicySupplementError) as err:
        A.load_alo_tables([])
    assert err.value.code == "not_configured"


def test_masker拒收字串():
    with pytest.raises(TypeError):
        A.masker("abc")
