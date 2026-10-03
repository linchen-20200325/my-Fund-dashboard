# -*- coding: utf-8 -*-
"""持倉體檢正式模式：舊淨值的新鮮度標示（hld 接真資料 S5，裁示 1-A＋1-C）。純函式測試，不 import streamlit。

出處：`docs/wireframes/draft_hld_live.html` §D（「N 的算法」那一列、選項 1-A、1-C、1-A＋1-C）
與 §G 第 1、1a 題（客戶 2026-10-02 裁示：1-A＋1-C，黃燈門檻 10 天）。
假資料每一檔最後一筆 `nav_date` 都是 2026-09-18（`ui_v2/hld/fixtures.py::navs`）。
"""

import ast
import copy
import pathlib
import sys
from datetime import date, datetime, timedelta, timezone

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2.hld import fixtures, live, logic  # noqa: E402

_LIVE_PY = _ROOT / "ui_v2" / "hld" / "live.py"
_LAST = date(2026, 9, 18)
TODAY = date(2026, 10, 2)
_ALL = fixtures.ALL_SCENARIO_NAMES
# 派工單的八個禁詞，以跳脫碼寫（本檔字面不出現它們；同草稿 §H 那一條掃描指令的寫法）。
_BANNED = ("一鍵", "最佳", "推薦", "最適",
           "買進", "賣出", "加碼", "減碼")


def _module_constant(rel, name):
    for node in ast.parse((_ROOT / rel).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} 不在 {rel}")


_DIRECT_ID = _module_constant("services/v2_tables/contract.py", "DIRECT_POLICY_ID")
_POLICY_TAB = _module_constant("repositories/policy_supplement_repository.py", "POLICY_TAB_SOURCE")
_SOURCES = {
    _POLICY_TAB,
    _module_constant("repositories/policy_supplement_repository.py", "TAB_POLICY_PROFILE"),
    _module_constant("repositories/policy_supplement_repository.py", "TAB_HOLDING_SUPPLEMENT"),
}


def _args(name="full"):
    args = copy.deepcopy(fixtures.scenario(name))
    for holding in args["dataset"].get("holding") or ():
        if holding["policy_id"] == _DIRECT_ID:   # 正式模式拿到 DIRECT 持倉會 raise（S4）
            holding["policy_id"] = "P-001"
    return args


def _prov(dataset, *, fallback=(), stale=None):
    """L2 `services/v2_tables/nav_dividend.py::rows_from_nav_series` 的 `provenance` 形狀，淨值表裡每檔一筆。"""
    out = {}
    for row in dataset.get("nav") or ():
        code = row["fund_code"]
        is_fb = code in fallback
        out[code] = {
            "source": "GitHubActions:cache/nav/x" if is_fb else "MoneyDJ:x",
            "fetched_at": "2026-09-19T02:00:00+00:00",
            "ccy_source": "holding",
            "cache_fallback": is_fb,
            "stale": stale if is_fb else None,
        }
    return out


def _model(name="full", *, today, fallback=(), stale=None, mutate=None, **kw):
    args = _args(name)
    if mutate:
        mutate(args["dataset"])
    holdings = args["dataset"].get("holding") or []
    return live.build_live_model(
        **args,
        open_fund=holdings[0]["holding_id"] if holdings else None,
        today=today,
        direct_policy_id=_DIRECT_ID,
        nav_provenance=_prov(args["dataset"], fallback=fallback, stale=stale),
        **kw,
    )


def _group(model, block, code):
    return next(g for g in logic.find_block(model, block)["fund_groups"] if g["_fund_code"] == code)


_OLD = {"text": "⚠ 淨值取自預存序列，不是本次取得；最近一筆 2026-09-18，已超過 10 日", "_tone": "黃"}
_FRESH = {"text": "淨值取自預存序列，不是本次取得；最近一筆 2026-09-18", "_tone": "中性"}


# ───────────────────────── 常數與字面 ─────────────────────────


def test_門檻常數是10_不沿用MJ_FRESH_DAYS_YELLOW_註解寫明客戶原話():
    assert live.NAV_FRESH_DAYS_YELLOW == 10
    assert _module_constant("shared/signal_thresholds.py", "MJ_FRESH_DAYS_YELLOW") == 7
    assert "門檻 10 天，非 44 規定，是本輪依長假實況訂的" in _LIVE_PY.read_text(encoding="utf-8")


def test_字面逐字照草稿():
    assert live.FRESHNESS_TODAY_TEXT == "當日"
    assert live.FRESHNESS_DELAY_TEXT.format(n=3) == "延遲 3 日"
    assert live.CACHE_NOTE_OLD.format(day="2026-09-09", limit=10) == (
        "⚠ 淨值取自預存序列，不是本次取得；最近一筆 2026-09-09，已超過 10 日"
    )
    assert live.CACHE_NOTE_FRESH.format(day="2026-09-09") == "淨值取自預存序列，不是本次取得；最近一筆 2026-09-09"
    assert live.CACHE_TAIL_TEXT.format(n=1) == "本卡所列的檔中，1 檔的淨值取自預存序列，逐檔見 HLD-6"
    draft = (_ROOT / "docs/wireframes/draft_hld_live.html").read_text(encoding="utf-8")
    for text in (
        "<code>即時</code>／<code>當日</code>／<code>延遲 N 日</code>",
        "⚠ 淨值取自預存序列，不是本次取得；最近一筆 YYYY-MM-DD，已超過 10 日",
        "<code>淨值取自預存序列，不是本次取得；最近一筆 YYYY-MM-DD</code>",
        "本卡所列的檔中，N 檔的淨值取自預存序列，逐檔見 HLD-6",
        "「· 預存序列」",
        "門檻 10 天，非 44 規定，是本輪依長假實況訂的",
    ):
        assert text in draft


# ───────────────────────── N 的算法與邊界 ─────────────────────────


@pytest.mark.parametrize(
    "days, text, tone",
    [(0, "當日", "中性"), (1, "延遲 1 日", "中性"), (10, "延遲 10 日", "中性"), (11, "延遲 11 日", "黃")],
)
def test_邊界_0天_1天_10天_11天(days, text, tone):
    model = _model(today=_LAST + timedelta(days=days))
    want = {"_kind": "新鮮度", "_tone": tone, "text": text}
    for block in ("HLD-2", "HLD-3"):
        assert [g["freshness_badge"] for g in logic.find_block(model, block)["fund_groups"]] == [want] * 3
    assert [r["freshness_badge"] for r in logic.find_block(model, "HLD-8")["_rows"]] == [want] * 3
    assert [g["freshness_badge"] for g in logic.find_block(model, "HLD-6")["nav_groups"]] == [want] * 3


def test_未來日期_raise():
    with pytest.raises(ValueError, match="晚於今天"):
        _model(today=_LAST - timedelta(days=1))


@pytest.mark.parametrize("utc, days, tone", [
    (datetime(2026, 9, 28, 15, 59, 59, tzinfo=timezone.utc), 10, "中性"),   # 台灣 9/28 23:59:59
    (datetime(2026, 9, 28, 16, 0, 0, tzinfo=timezone.utc), 11, "黃"),       # 台灣 9/29 00:00:00
])
def test_跨台灣午夜_N用台灣日期(utc, days, tone):
    model = _model(today=live.taiwan_today(utc))
    badge = _group(model, "HLD-2", "AAAA")["freshness_badge"]
    assert (badge["text"], badge["_tone"]) == (f"延遲 {days} 日", tone)


def test_長假情境_最後一筆停在長假前_第10天不轉黃_第11天才轉黃():
    """客戶理由：7 天的門檻遇到春節等長假，每一檔基金都會被誤標黃燈。"""
    shift = _LAST - date(2026, 2, 11)

    def holiday(ds):
        for row in ds["nav"]:
            row["nav_date"] = (date.fromisoformat(row["nav_date"]) - shift).isoformat()

    for today, tone in ((date(2026, 2, 21), "中性"), (date(2026, 2, 22), "黃")):
        model = _model(today=today, mutate=holiday)
        for block in ("HLD-2", "HLD-3"):
            assert {g["freshness_badge"]["_tone"] for g in logic.find_block(model, block)["fund_groups"]} == {tone}


@pytest.mark.parametrize("stale, days, want", [(True, 2, _FRESH), (False, 20, _OLD), (None, 20, _OLD)])
def test_不讀stale_新舊只看N(stale, days, want):
    note = _group(_model(today=_LAST + timedelta(days=days), fallback={"AAAA"}, stale=stale), "HLD-2", "AAAA")
    if want is _FRESH:
        assert note["freshness_note"] == _FRESH
    else:
        assert note["freshness_note"]["_tone"] == "黃" and note["freshness_note"]["text"].startswith("⚠")


# ───────────────────────── 1-C 副標、卡尾、輸入欄 ─────────────────────────


@pytest.mark.parametrize("days, want", [(11, _OLD), (10, _FRESH)])
def test_預存那一檔副標_其他檔沒有(days, want):
    model = _model(today=_LAST + timedelta(days=days), fallback={"AAAA"})
    for block in ("HLD-2", "HLD-3"):
        notes = {g["_fund_code"]: g["freshness_note"] for g in logic.find_block(model, block)["fund_groups"]}
        assert notes == {"AAAA": want, "BBBB": None, "CCCC": None}
    assert {r["_fund_code"]: r["freshness_note"] for r in logic.find_block(model, "HLD-8")["_rows"]} == {
        "AAAA": want, "BBBB": None, "CCCC": None}
    hld5 = logic.find_block(model, "HLD-5")["_items"]
    assert {i["_fund_code"]: i["freshness_note"] for i in hld5} == {"AAAA": want, "BBBB": None, "CCCC": None}
    hld6 = logic.find_block(model, "HLD-6")["nav_groups"]
    assert {g["fund_code"]: g["freshness_note"] for g in hld6} == {"AAAA": want, "BBBB": None, "CCCC": None}


def test_HLD5不掛徽章_只掛副標():
    model = _model(today=TODAY, fallback={"AAAA"})
    assert all("freshness_badge" not in i for i in logic.find_block(model, "HLD-5")["_items"])


def test_同一檔徽章與副標同一個N_顏色一致():
    for days in (10, 11):
        group = _group(_model(today=_LAST + timedelta(days=days), fallback={"AAAA"}), "HLD-2", "AAAA")
        assert group["freshness_badge"]["_tone"] == group["freshness_note"]["_tone"]


def test_HLD7_預存那一檔各列輸入欄尾端加預存序列_其他檔不加():
    rows = logic.find_block(_model(today=TODAY, fallback={"AAAA"}), "HLD-7")["_rows"]
    base = logic.find_block(_model(today=TODAY), "HLD-7")["_rows"]
    assert len(rows) == len(base) and [r["_fund_code"] for r in rows].count("AAAA") > 0
    for row, b in zip(rows, base):
        want = b["inputs_text"] + " · 預存序列" if row["_fund_code"] == "AAAA" else b["inputs_text"]
        assert row["inputs_text"] == want


def test_HLD1卡尾第3句_只數本卡列上的檔_顏色跟著N():
    hld1 = logic.find_block(_model(today=TODAY), "HLD-1")
    listed = sorted({r["_fund_code"] for r in hld1["_rows"]})
    unlisted = sorted({"AAAA", "BBBB", "CCCC"} - set(listed))
    assert listed and unlisted and "freshness_tail" not in hld1   # 前提：有檔在卡上、有檔不在
    assert "freshness_tail" not in logic.find_block(_model(today=TODAY, fallback=set(unlisted)), "HLD-1")
    for days, tone in ((10, "中性"), (11, "黃")):
        hld1 = logic.find_block(_model(today=_LAST + timedelta(days=days), fallback={"AAAA", "BBBB", "CCCC"}), "HLD-1")
        assert hld1["freshness_tail"] == {
            "text": f"本卡所列的檔中，{len(listed)} 檔的淨值取自預存序列，逐檔見 HLD-6", "_tone": tone}
        assert hld1["tail_lines"] == logic.find_block(_model(today=TODAY), "HLD-1")["tail_lines"]


def test_HLD0燈與各塊狀態色調一格不動():
    # 基準是「沒掛新鮮度」的正式模型（S3 的 `apply_live_notes` 為止），不是另一份同樣掛過的模型 ——
    # 後者兩邊一起被改到時會照樣相等（突變 M34 就是這樣漏掉的）。
    args = _args()
    today = _LAST + timedelta(days=40)
    base = live.apply_live_notes(logic.build_page_model(**copy.deepcopy(args), demo_hint=False), today=today)
    model = _model(today=today, fallback={"AAAA", "BBBB", "CCCC"})
    assert logic.find_block(model, "HLD-0") == logic.find_block(base, "HLD-0")
    for code in ("HLD-1", "HLD-2", "HLD-3", "HLD-5", "HLD-6", "HLD-7", "HLD-8"):
        a, b = logic.find_block(model, code), logic.find_block(base, code)
        assert (a["_state"], a["_tone"], a["summary_text"], a["buttons"]) == (
            b["_state"], b["_tone"], b["summary_text"], b["buttons"])


def test_HLD6分組_列內容與順序不變():
    hld6 = logic.find_block(_model(today=TODAY), "HLD-6")
    assert [row for g in hld6["nav_groups"] for row in g["rows"]] == hld6["nav_rows"]
    assert [g["fund_code"] for g in hld6["nav_groups"]] == ["AAAA", "BBBB", "CCCC"]


# ───────────────────────── 輸入形狀不對一律 raise ─────────────────────────


def test_沒給nav_provenance_raise():
    with pytest.raises(ValueError, match="沒有給 nav_provenance"):
        live.build_live_model(**_args(), today=TODAY, direct_policy_id=_DIRECT_ID)


@pytest.mark.parametrize("bad, exc", [
    ([], TypeError),
    ({"AAAA": "x"}, TypeError),
    ({"AAAA": {"cache_fallback": False}}, ValueError),             # 缺 stale
    ({"AAAA": {"stale": None}}, ValueError),                        # 缺 cache_fallback
    ({"AAAA": {"cache_fallback": 1, "stale": None}}, TypeError),    # 不是 bool
    ({"AAAA": {"cache_fallback": True, "stale": "yes"}}, TypeError),
    ({"AAAA": {"cache_fallback": False, "stale": True}}, ValueError),   # 與 L2 不符
    ({1: {"cache_fallback": False, "stale": None}}, TypeError),
])
def test_provenance形狀不對_raise(bad, exc):
    args = _args()
    prov = _prov(args["dataset"])
    if isinstance(bad, dict):
        prov.update(bad)
    else:
        prov = bad
    with pytest.raises(exc):
        live.build_live_model(**args, today=TODAY, direct_policy_id=_DIRECT_ID, nav_provenance=prov)


def test_有淨值列的檔在provenance裡缺一筆_raise():
    args = _args()
    prov = _prov(args["dataset"])
    del prov["BBBB"]
    with pytest.raises(ValueError, match="BBBB"):
        live.build_live_model(**args, today=TODAY, direct_policy_id=_DIRECT_ID, nav_provenance=prov)


@pytest.mark.parametrize("bad", ["2026/09/18", "2026-9-18", "2026-02-30", "２０２６-09-18",
                                 datetime(2026, 9, 18), 20260918, None])
def test_nav_date形狀不對_raise(bad):
    args = _args()
    args["dataset"]["nav"][0]["nav_date"] = bad
    with pytest.raises((TypeError, ValueError), match="nav_date"):
        live.nav_freshness(args["dataset"], _prov(args["dataset"]), today=TODAY)


def test_nav_date收date物件_L2的寫法():
    args = _args()
    for row in args["dataset"]["nav"]:
        row["nav_date"] = date.fromisoformat(row["nav_date"])
    got = live.nav_freshness(args["dataset"], _prov(args["dataset"]), today=TODAY)
    assert {c: v["days"] for c, v in got.items()} == {c: (TODAY - _LAST).days for c in ("AAAA", "BBBB", "CCCC")}


@pytest.mark.parametrize("bad", [datetime(2026, 10, 2, tzinfo=timezone.utc), "2026-10-02"])
def test_today不是date_raise(bad):
    args = _args()
    with pytest.raises(TypeError, match="today 應為 date"):
        live.nav_freshness(args["dataset"], _prov(args["dataset"]), today=bad)


# ───────────────────────── 與 S2／S3／S4 同時出現 ─────────────────────────


def test_與S2逐檔淨值取數失敗並存_失敗那一檔不掛徽章不掛副標():
    def fail(ds):
        ds["fund_errors"] = {"nav": {"BBBB": "ConnectionError: 逾時"}}

    model = _model(today=TODAY, fallback={"AAAA", "BBBB"}, mutate=fail)
    b = _group(model, "HLD-2", "BBBB")
    assert b["freshness_badge"] is None and b["freshness_note"] is None
    assert all(mv["_state"] == logic.STATE_ERROR for mv in b["main_values"])
    assert _group(model, "HLD-2", "AAAA")["freshness_badge"] is not None
    assert not [r for r in logic.find_block(model, "HLD-7")["_rows"]
                if r["_fund_code"] == "BBBB" and r["inputs_text"].endswith("預存序列")]
    # S2 的逐檔失敗行照舊在 HLD-2 說明區
    assert any("BBBB" in line and "逾時" in line for line in logic.find_block(model, "HLD-2")["detail_lines"])


def test_表層級淨值取數失敗_一枚都不掛():
    model = _model("twofail", today=TODAY, fallback={"AAAA"})
    assert [b for b in logic.collect_badges(model) if b["_kind"] == "新鮮度"] == []
    assert "freshness_tail" not in logic.find_block(model, "HLD-1")
    assert all(g["freshness_note"] is None for g in logic.find_block(model, "HLD-6")["nav_groups"])


def test_與S3核對日並存_HLD5展開欄位一格不動():
    with_fb = _model(today=TODAY, fallback={"AAAA", "BBBB", "CCCC"})
    without = _model(today=TODAY)
    a = [i["_fields"] for i in logic.find_block(with_fb, "HLD-5")["_items"]]
    b = [i["_fields"] for i in logic.find_block(without, "HLD-5")["_items"]]
    assert a == b and any(label == live.SYNC_LABEL for fields in a for label, _ in fields)


def test_與S4的DIRECT並存_互不覆蓋():
    direct = [{"source": _POLICY_TAB, "tab": "DIRECT", "row": 3}]
    model = _model(today=TODAY, fallback={"AAAA"}, direct=direct, policy_tab_source=_POLICY_TAB,
                   direct_sources=_SOURCES)
    hld5 = logic.find_block(model, "HLD-5")
    assert hld5["tail_notes"][0]["text"] == "⚠ DIRECT 列暫不支援，該筆不計入體檢（1 筆）"
    assert {i["_fund_code"]: i["freshness_note"] for i in hld5["_items"]}["AAAA"] is not None


def test_空持倉_沒有任何新鮮度標示():
    model = _model("empty", today=TODAY)
    assert [b for b in logic.collect_badges(model) if b["_kind"] == "新鮮度"] == []
    assert "freshness_tail" not in logic.find_block(model, "HLD-1")


@pytest.mark.parametrize("name", _ALL)
def test_全情境_禁詞識別碼與狀態徽章守衛照過(name):
    import re

    model = _model(name, today=_LAST + timedelta(days=30), fallback={"AAAA", "BBBB", "CCCC"})
    strings = logic.collect_ui_strings(model)
    assert logic.scan_forbidden(strings) == {}
    assert [s for s in strings if any(w in s for w in _BANNED)] == []
    assert [s for s in strings if re.search(r"session_[0-9A-Za-z]{16,}|claude\.ai/code", s)] == []
    for badge in logic.collect_badges(model):
        if badge["_kind"] == "狀態":
            assert badge["text"] in logic.STATUS_BADGE_LITERALS
