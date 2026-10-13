# -*- coding: utf-8 -*-
"""持倉體檢正式模式：舊淨值的新鮮度標示（hld 接真資料 S5，裁示 1-A＋1-C）。純函式測試，不 import streamlit。

📌 客戶 2026-10-13 裁示（狀態更新，不是漏刪）：~~超過 10 天 → 黃燈、淨值照用~~ → 淨值日距觀測日**大於** 10 天
→ 該檔淨值「資料未備」：不交給 `logic`、相依淨值的值一律「⬜ 資料未備」、徽章中性灰，且**不得**觸發任何投資黃／紅燈或結論。
本檔下方「11 天」那一邊的期望值因此全部改寫；「10 天以內」那一邊一字未改。

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
TODAY = date(2026, 10, 2)            # 距最後一筆 14 天 ⇒ 2026-10-13 起三檔全部資料未備
FRESH = _LAST + timedelta(days=10)   # 恰 10 天 ⇒ 照用（判定方向是「大於」）
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


# ~~`_OLD = {"text": "⚠ 淨值取自預存序列…已超過 10 日", "_tone": "黃", ...}`~~ → 2026-10-13 客戶裁示：灰、不帶 ⚠。
_OLD = {"text": "淨值取自預存序列，不是本次取得；最近一筆 2026-09-18，已超過 10 日", "_tone": "灰",
        "_nowrap": ["2026-09-18"]}
# 2026-10-13 新增：超過門檻、不是預存序列的那幾檔。
_OLD_LIVE = {"text": "最近一筆淨值 2026-09-18，已超過 10 日", "_tone": "灰", "_nowrap": ["2026-09-18"]}
_ND_BADGE = {"_kind": "新鮮度", "_tone": "灰", "text": "⬜ 資料未備"}
_FRESH = {"text": "淨值取自預存序列，不是本次取得；最近一筆 2026-09-18", "_tone": "中性", "_nowrap": ["2026-09-18"]}


# ───────────────────────── 常數與字面 ─────────────────────────


def test_門檻常數是10_不沿用MJ_FRESH_DAYS_YELLOW_註解寫明客戶原話():
    assert live.NAV_FRESH_DAYS_YELLOW == 10
    # 2026-10-13 客戶裁示：值來自 B 線共用定義 `ui_v2/thresholds.py::NAV_NOT_READY_DAYS`，本檔不再寫死
    # （兩頁引用同一名稱與「不得是字面值」的 AST 守衛見 tests/ui_v2/test_alo_live_logic.py）。
    assert live.thresholds.__name__ == "ui_v2.thresholds"
    assert live.NAV_FRESH_DAYS_YELLOW == live.thresholds.NAV_NOT_READY_DAYS
    assert _module_constant("shared/signal_thresholds.py", "MJ_FRESH_DAYS_YELLOW") == 7
    assert "門檻 10 天，非 44 規定，是本輪依長假實況訂的" in _LIVE_PY.read_text(encoding="utf-8")


def test_字面逐字照草稿():
    assert live.FRESHNESS_TODAY_TEXT == "當日"
    assert live.FRESHNESS_DELAY_TEXT.format(n=3) == "延遲 3 日"
    # 2026-10-13 客戶裁示：草稿的「⚠ 」拿掉（資料未備不是投資黃燈），其餘字一字未改。草稿是裁示紀錄，不改。
    assert "⚠ " + live.CACHE_NOTE_OLD.format(day="2026-09-09", limit=10) == (
        "⚠ 淨值取自預存序列，不是本次取得；最近一筆 2026-09-09，已超過 10 日"
    )
    assert "⚠" not in live.CACHE_NOTE_OLD and "⚠" not in live.NAV_NOTE_NOT_READY
    assert live.NOT_READY_BADGE_TEXT == logic.ND_TEXT == "⬜ 資料未備"
    assert live.NOT_READY_TONE == logic.tone_for_state(logic.STATE_MISSING) == "灰"
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


# ~~`(11, "延遲 11 日", "黃")`~~ → 2026-10-13 客戶裁示：11 天 ＝「⬜ 資料未備」、灰；HLD-6 不再列那幾檔的淨值列。
@pytest.mark.parametrize(
    "days, text, tone",
    [(0, "當日", "中性"), (1, "延遲 1 日", "中性"), (10, "延遲 10 日", "中性"), (11, "⬜ 資料未備", "灰")],
)
def test_邊界_0天_1天_10天_11天(days, text, tone):
    model = _model(today=_LAST + timedelta(days=days))
    want = {"_kind": "新鮮度", "_tone": tone, "text": text}
    for block in ("HLD-2", "HLD-3"):
        assert [g["freshness_badge"] for g in logic.find_block(model, block)["fund_groups"]] == [want] * 3
    assert [r["freshness_badge"] for r in logic.find_block(model, "HLD-8")["_rows"]] == [want] * 3
    hld6 = logic.find_block(model, "HLD-6")["nav_groups"]
    assert [g["freshness_badge"] for g in hld6] == ([want] * 3 if days <= 10 else [])


def test_未來日期_raise():
    with pytest.raises(ValueError, match="晚於今天"):
        _model(today=_LAST - timedelta(days=1))


@pytest.mark.parametrize("utc, days, tone", [
    (datetime(2026, 9, 28, 15, 59, 59, tzinfo=timezone.utc), 10, "中性"),   # 台灣 9/28 23:59:59
    (datetime(2026, 9, 28, 16, 0, 0, tzinfo=timezone.utc), 11, "灰"),       # 台灣 9/29 00:00:00（2026-10-13：~~黃~~ → 灰）
])
def test_跨台灣午夜_N用台灣日期(utc, days, tone):
    model = _model(today=live.taiwan_today(utc))
    badge = _group(model, "HLD-2", "AAAA")["freshness_badge"]
    text = f"延遲 {days} 日" if days <= 10 else "⬜ 資料未備"
    assert (badge["text"], badge["_tone"]) == (text, tone)


def test_長假情境_最後一筆停在長假前_第10天照用_第11天才資料未備():
    """客戶理由：7 天的門檻遇到春節等長假，每一檔基金都會被誤標黃燈。"""
    shift = _LAST - date(2026, 2, 11)

    def holiday(ds):
        for row in ds["nav"]:
            row["nav_date"] = (date.fromisoformat(row["nav_date"]) - shift).isoformat()

    for today, tone in ((date(2026, 2, 21), "中性"), (date(2026, 2, 22), "灰")):   # 2026-10-13：~~黃~~ → 灰
        model = _model(today=today, mutate=holiday)
        for block in ("HLD-2", "HLD-3"):
            assert {g["freshness_badge"]["_tone"] for g in logic.find_block(model, block)["fund_groups"]} == {tone}


@pytest.mark.parametrize("stale, days, want", [(True, 2, _FRESH), (False, 20, _OLD), (None, 20, _OLD)])
def test_不讀stale_新舊只看N(stale, days, want):
    note = _group(_model(today=_LAST + timedelta(days=days), fallback={"AAAA"}, stale=stale), "HLD-2", "AAAA")
    if want is _FRESH:
        assert note["freshness_note"] == _FRESH
    else:   # 2026-10-13：~~黃、以 ⚠ 開頭~~ → 灰、不帶 ⚠
        assert note["freshness_note"] == _OLD


# ───────────────────────── 1-C 副標、卡尾、輸入欄 ─────────────────────────


# 2026-10-13 客戶裁示：11 天時三檔都資料未備 ⇒ 不是預存的 BBBB／CCCC 也掛一行灰色副標（`_OLD_LIVE`），
# HLD-6 不再列淨值列（分組為空）。10 天那一邊一字未改。
@pytest.mark.parametrize("days, want, other", [(11, _OLD, _OLD_LIVE), (10, _FRESH, None)])
def test_預存那一檔副標_其他檔沒有(days, want, other):
    model = _model(today=_LAST + timedelta(days=days), fallback={"AAAA"})
    for block in ("HLD-2", "HLD-3"):
        notes = {g["_fund_code"]: g["freshness_note"] for g in logic.find_block(model, block)["fund_groups"]}
        assert notes == {"AAAA": want, "BBBB": other, "CCCC": other}
    assert {r["_fund_code"]: r["freshness_note"] for r in logic.find_block(model, "HLD-8")["_rows"]} == {
        "AAAA": want, "BBBB": other, "CCCC": other}
    hld5 = logic.find_block(model, "HLD-5")["_items"]
    assert {i["_fund_code"]: i["freshness_note"] for i in hld5} == {"AAAA": want, "BBBB": other, "CCCC": other}
    hld6 = logic.find_block(model, "HLD-6")["nav_groups"]
    if days <= 10:
        assert {g["fund_code"]: g["freshness_note"] for g in hld6} == {"AAAA": want, "BBBB": None, "CCCC": None}
    else:
        assert hld6 == []


def test_HLD5不掛徽章_只掛副標():
    model = _model(today=TODAY, fallback={"AAAA"})
    assert all("freshness_badge" not in i for i in logic.find_block(model, "HLD-5")["_items"])


def test_同一檔徽章與副標同一個N_顏色一致():
    for days in (10, 11):
        group = _group(_model(today=_LAST + timedelta(days=days), fallback={"AAAA"}), "HLD-2", "AAAA")
        assert group["freshness_badge"]["_tone"] == group["freshness_note"]["_tone"]


# S5 第二輪（紅隊必修 M1，總管裁定）：尾巴只掛在以淨值為輸入的三列；配息類三列、門檻差額列不掛。
# 期望值逐列寫死，不從 `logic.NAV_INPUT_INDICATORS` 推（被測的就是那一份）。
_HLD7_SUFFIX_WANT = {
    "區間報酬率": True,
    "期間波動": True,
    "最大回撤": True,
    "期間配息合計": False,
    "配息佔淨值比": False,
    "本金類配息佔比": False,
    "最大回撤 與門檻的差額": False,   # HLD-1 帶過來的那一列（`full` 情境 AAAA 超出最大回撤門檻）
}


def test_HLD7_淨值為輸入的三列掛尾巴_配息三列與門檻差額列不掛():
    # 2026-10-13：~~`today=TODAY`~~（10-02 起三檔全部資料未備，尾巴一列都不掛）→ 恰 10 天（照用）
    rows = logic.find_block(_model(today=FRESH, fallback={"AAAA"}), "HLD-7")["_rows"]
    base = logic.find_block(_model(today=FRESH), "HLD-7")["_rows"]
    assert len(rows) == len(base)
    got = {}
    for row, b in zip(rows, base):
        assert (row["_fund_code"], row["_indicator"]) == (b["_fund_code"], b["_indicator"])
        if row["_fund_code"] != "AAAA":
            assert row["inputs_text"] == b["inputs_text"]          # 不是預存的檔，一列都不掛
            continue
        assert not b["inputs_text"].endswith("預存序列")
        if row["inputs_text"] == b["inputs_text"] + " · 預存序列":
            got[row["_indicator"]] = True
        else:
            assert row["inputs_text"] == b["inputs_text"]
            got[row["_indicator"]] = False
    assert got == _HLD7_SUFFIX_WANT


def test_HLD7_判定淨值列的名單就是logic輸入欄讀淨值列的那一份():
    """依據是 `logic._inputs_text`：名單內的指標，輸入欄讀 `nav_rows`；名單外讀 `div_rows`。"""
    assert logic.NAV_INPUT_INDICATORS == ("區間報酬率", "期間波動", "最大回撤")
    metric = {"nav_rows": [{"nav_date": "N1"}, {"nav_date": "N2"}], "div_rows": [{"ex_date": "D1"}]}
    for indicator in logic.INDICATOR_OWNER:
        text = logic._inputs_text(metric, indicator)
        assert ("N1" in text) == (indicator in logic.NAV_INPUT_INDICATORS)
        assert ("D1" in text) == (indicator not in logic.NAV_INPUT_INDICATORS)


def test_HLD1卡尾第3句_只數本卡列上的檔_資料未備的檔不算():
    # 2026-10-13 客戶裁示：~~`(11, "黃")`~~ → 11 天時三檔都資料未備、沒有用到淨值 ⇒ 不算「取自預存序列」，卡尾不出現；
    # 卡尾不再有黃色。名稱 ~~`…_顏色跟著N`~~ 隨之更正。
    hld1 = logic.find_block(_model(today=FRESH), "HLD-1")
    listed = sorted({r["_fund_code"] for r in hld1["_rows"]})
    unlisted = sorted({"AAAA", "BBBB", "CCCC"} - set(listed))
    assert listed and unlisted and "freshness_tail" not in hld1   # 前提：有檔在卡上、有檔不在
    assert "freshness_tail" not in logic.find_block(_model(today=FRESH, fallback=set(unlisted)), "HLD-1")
    hld1 = logic.find_block(_model(today=FRESH, fallback={"AAAA", "BBBB", "CCCC"}), "HLD-1")
    assert hld1["freshness_tail"] == {
        "text": f"本卡所列的檔中，{len(listed)} 檔的淨值取自預存序列，逐檔見 HLD-6", "_tone": "中性"}
    assert hld1["tail_lines"] == logic.find_block(_model(today=FRESH), "HLD-1")["tail_lines"]
    stale = logic.find_block(_model(today=_LAST + timedelta(days=11), fallback={"AAAA", "BBBB", "CCCC"}), "HLD-1")
    assert "freshness_tail" not in stale


@pytest.mark.parametrize("days", [10, 40])
def test_HLD0燈與各塊狀態色調一格不動(days):
    # 基準是「沒掛新鮮度」的正式模型（S3 的 `apply_live_notes` 為止），不是另一份同樣掛過的模型 ——
    # 後者兩邊一起被改到時會照樣相等（突變 M34 就是這樣漏掉的）。
    # 📌 2026-10-13 客戶裁示：超過 10 天時基準改為「淨值列整個拿掉」的 dataset（＝缺淨值的既有路徑），
    #    期望值自己拿掉、不呼叫被測的 `withhold_not_ready_nav`；10 天那一邊基準照舊（原本只測 40 天）。
    args = _args()
    today = _LAST + timedelta(days=days)
    base_args = copy.deepcopy(args)
    if days > 10:
        base_args["dataset"]["nav"] = []
    base = live.apply_live_notes(logic.build_page_model(**base_args, demo_hint=False), today=today)
    model = _model(today=today, fallback={"AAAA", "BBBB", "CCCC"})
    assert logic.find_block(model, "HLD-0") == logic.find_block(base, "HLD-0")
    for code in ("HLD-1", "HLD-2", "HLD-3", "HLD-5", "HLD-6", "HLD-7", "HLD-8"):
        a, b = logic.find_block(model, code), logic.find_block(base, code)
        assert (a["_state"], a["_tone"], a["summary_text"], a["buttons"]) == (
            b["_state"], b["_tone"], b["summary_text"], b["buttons"])


def test_HLD6分組_列內容與順序不變():
    hld6 = logic.find_block(_model(today=FRESH), "HLD-6")   # 2026-10-13：~~TODAY~~（10-02 起三檔都不列淨值列）
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


# ═══════════════ 客戶 2026-10-13 裁示：淨值日距觀測日大於 10 天 → 資料未備（不是投資風險訊號） ═══════════════
# 期望值一律逐格寫死或自己組（不呼叫被測的 `withhold_not_ready_nav`／`not_ready_codes`）。

_NAV_INPUT = ("區間報酬率", "期間波動", "配息佔淨值比", "最大回撤")   # 以淨值為輸入（含配息佔淨值比的分母）
_DIV_ONLY = ("期間配息合計", "本金類配息佔比")                      # 不以淨值為輸入
_RISK_WORDS = ("減碼", "撤出", "賣出", "買進", "加碼", "惡化", "轉弱", "風險升高", "該調整")


def _values(model, code):
    """一檔在各塊上的六個值節點：HLD-2／HLD-3 的主值、HLD-8 的最大回撤與本金類配息佔比。"""
    out = {}
    for block in ("HLD-2", "HLD-3"):
        for mv in _group(model, block, code)["main_values"]:
            out[mv["label"]] = mv
    row = next(r for r in logic.find_block(model, "HLD-8")["_rows"] if r["_fund_code"] == code)
    out["最大回撤"], out["本金類配息佔比"] = row["drawdown"], row["principal"]
    return out


def _age_one(code, days_back):
    """只讓 `code` 那一檔的淨值整段往前移 `days_back` 天（其他檔不動）。"""
    def mutate(ds):
        for row in ds["nav"]:
            if row["fund_code"] == code:
                row["nav_date"] = (date.fromisoformat(row["nav_date"]) - timedelta(days=days_back)).isoformat()
    return mutate


def test_資料未備_11天_以淨值為輸入的四個值都是資料未備_不是0也不是空白():
    stale = _model(today=_LAST + timedelta(days=11))
    fresh = _model(today=FRESH)
    for code in ("AAAA", "BBBB", "CCCC"):
        got, base = _values(stale, code), _values(fresh, code)
        for name in _NAV_INPUT:
            assert base[name]["_state"] == logic.STATE_OK, (code, name)   # 正控：10 天時照算
            node = got[name]
            assert (node["_state"], node["text"], node["_tone"]) == (logic.STATE_MISSING, "⬜ 資料未備", "灰"), (code, name)
            assert node["_raw"] is None and node["_has_number"] is False, (code, name)
        for name in _DIV_ONLY:   # 不以淨值為輸入的照算，與 10 天時逐格相同
            assert got[name] == base[name], (code, name)


def test_恰10天_照用_以淨值為輸入的值都有數():
    model = _model(today=FRESH)
    for code in ("AAAA", "BBBB", "CCCC"):
        got = _values(model, code)
        assert all(got[n]["_state"] == logic.STATE_OK and got[n]["_raw"] is not None for n in _NAV_INPUT), code
    assert len(logic.find_block(model, "HLD-6")["nav_rows"]) == len(_args()["dataset"]["nav"])


def test_部分過期_只有那一檔資料未備_其他檔逐格與全新鮮時相同():
    fresh = _model(today=FRESH)
    model = _model(today=FRESH, mutate=_age_one("AAAA", 20))
    for name in _NAV_INPUT:
        assert _values(model, "AAAA")[name]["text"] == "⬜ 資料未備"
    assert _group(model, "HLD-2", "AAAA")["freshness_badge"] == _ND_BADGE
    for code in ("BBBB", "CCCC"):
        assert _values(model, code) == _values(fresh, code)
        assert _group(model, "HLD-2", code)["freshness_badge"] == _group(fresh, "HLD-2", code)["freshness_badge"]
    hld6 = logic.find_block(model, "HLD-6")
    assert {r["_fund_code"] for r in hld6["nav_rows"]} == {"BBBB", "CCCC"}   # 過期那一檔的淨值列一列都不列
    hld1 = logic.find_block(model, "HLD-1")
    # 門檻是「最大回撤」與「配息佔淨值比」，兩者都以淨值為輸入 ⇒ 過期那一檔不進偏離表、只進「缺淨值」卡尾。
    assert "AAAA" not in {r["_fund_code"] for r in hld1["_rows"]}
    # 總管 2026-10-13 裁決：過期的檔寫「淨值超過 10 日未更新」，不寫「缺淨值」（實況是有資料、只是過期）。
    assert "⬜ 另有 1 檔淨值超過 10 日未更新（資料未備），未列入" in hld1["tail_lines"]
    assert not [line for line in hld1["tail_lines"] if "缺淨值" in line]
    # 本頁沒有跨檔合計（核心卡自陳「沒有任何跨幣別的合計、平均或比值」）—— 其他檔的列照舊，不因一檔資料未備而少列或改數。
    assert [r for r in logic.find_block(fresh, "HLD-1")["_rows"] if r["_fund_code"] != "AAAA"] == hld1["_rows"]


def test_全部過期_結論燈是灰色資料未備_不是黃也不是紅_沒有任何行動結論():
    fresh = _model(today=FRESH)
    assert logic.find_block(fresh, "HLD-0")["_tone"] == "黃"   # 正控：同一份持倉在 10 天時確實會亮投資黃燈
    model = _model(today=TODAY, fallback={"BBBB"})
    hld0 = logic.find_block(model, "HLD-0")
    assert (hld0["_tone"], hld0["_state"], hld0["text"]) == ("灰", logic.STATE_MISSING, "⬜ 資料未備")
    assert hld0["glyph"] == "⬜" and "超出" not in hld0["text"]
    hld1 = logic.find_block(model, "HLD-1")
    assert hld1["_rows"] == [] and hld1["_tone"] == "灰" and hld1["summary_text"] == "⬜ 資料未備"
    assert logic.find_block(model, "HLD-6")["nav_rows"] == []
    # 任何地方都沒有黃色的新鮮度徽章／副標，也沒有 ⚠。
    for block in ("HLD-2", "HLD-3"):
        for g in logic.find_block(model, block)["fund_groups"]:
            assert g["freshness_badge"] == _ND_BADGE and g["freshness_note"]["_tone"] == "灰"
    strings = logic.collect_ui_strings(model)
    assert not [s for s in strings if "⚠" in s]
    assert not [s for s in strings if any(w in s for w in _RISK_WORDS)]
    # 比 10 天時多出來的字，一句都不是風險語彙（資料缺失不得被讀成市場或基金惡化）。
    added = set(strings) - set(logic.collect_ui_strings(fresh))
    assert added and not [s for s in added if any(w in s for w in _RISK_WORDS + ("黃燈", "紅燈", "超出"))]


def test_部分過期_零偏離時_結論燈不因資料未備轉黃或轉紅():
    base = _model("noexceed", today=FRESH)
    assert logic.find_block(base, "HLD-0")["_tone"] == "灰"   # 正控：沒有偏離時是灰
    model = _model("noexceed", today=FRESH, mutate=_age_one("AAAA", 20))
    hld0 = logic.find_block(model, "HLD-0")
    assert hld0["_tone"] == "灰" and hld0["_state"] != logic.STATE_ERROR
    # 塊的色調：資料未備只會讓它變灰或維持原樣，不會因此變黃或變紅。
    # （`noexceed` 的 HLD-8 在 10 天時本來就是黃 —— 那是 `44` 5.1 的「業務例外」塊色，與資料未備無關，維持原樣。）
    for code in ("HLD-1", "HLD-2", "HLD-3", "HLD-8"):
        tone, before = logic.find_block(model, code)["_tone"], logic.find_block(base, code)["_tone"]
        assert tone in (before, "灰") and tone != "紅", (code, before, tone)


def test_資料未備的檔_HLD7輸入欄不掛預存序列尾巴():
    model = _model(today=TODAY, fallback={"AAAA", "BBBB", "CCCC"})
    rows = logic.find_block(model, "HLD-7")["_rows"]
    assert rows and not [r for r in rows if r["inputs_text"].endswith("預存序列")]
    for r in rows:
        if r["_indicator"] in logic.NAV_INPUT_INDICATORS:
            assert r["inputs_text"] == "0 筆" and r["output_text"] == "⬜ 資料未備", r


def test_withhold不改輸入_也不碰配息列():
    args = _args()
    ds = args["dataset"]
    snapshot = copy.deepcopy(ds)
    out = live.withhold_not_ready_nav(ds, {"AAAA"})
    assert ds == snapshot
    assert out["dividend"] == ds["dividend"] and {r["fund_code"] for r in out["nav"]} == {"BBBB", "CCCC"}
    assert live.withhold_not_ready_nav(ds, set()) is ds


def test_門檻只來自共用常數_別名與判定():
    """`NAV_FRESH_DAYS_YELLOW` 是 `ui_v2/thresholds.py::NAV_NOT_READY_DAYS` 的別名；判定讀它，不讀別處寫死的 10。"""
    assert live.NAV_FRESH_DAYS_YELLOW is live.thresholds.NAV_NOT_READY_DAYS
    ds = _args()["dataset"]
    assert live.not_ready_codes(ds, today=_LAST + timedelta(days=11)) == {"AAAA", "BBBB", "CCCC"}
    assert live.not_ready_codes(ds, today=_LAST + timedelta(days=10)) == frozenset()


def test_門檻只來自共用常數_換掉常數判定跟著變(monkeypatch):
    monkeypatch.setattr(live, "NAV_FRESH_DAYS_YELLOW", 20)
    ds = _args()["dataset"]
    assert live.not_ready_codes(ds, today=_LAST + timedelta(days=11)) == frozenset()
    badge = _group(_model(today=_LAST + timedelta(days=11)), "HLD-2", "AAAA")["freshness_badge"]
    assert badge == {"_kind": "新鮮度", "_tone": "中性", "text": "延遲 11 日"}


# ═══════════════ 總管 2026-10-13 裁決：「淨值過期而資料未備」與「淨值缺」字面可區分（兩頁一致） ═══════════════

_ALO_LOGIC = _ROOT / "ui_v2" / "alo" / "logic.py"


def _drop_nav(code):
    def mutate(ds):
        ds["nav"] = [r for r in ds["nav"] if r["fund_code"] != code]
    return mutate


def _both(*mutates):
    def mutate(ds):
        for m in mutates:
            m(ds)
    return mutate


def test_過期與缺淨值_HLD1卡尾各寫各的_說明行只印一次():
    """AAAA 淨值過期（有列、超過 10 日）、BBBB 真的缺淨值（一列都沒有）、CCCC 正常。"""
    model = _model(today=FRESH, mutate=_both(_age_one("AAAA", 20), _drop_nav("BBBB")))
    hld1 = logic.find_block(model, "HLD-1")
    assert "⬜ 另有 1 檔淨值超過 10 日未更新（資料未備），未列入" in hld1["tail_lines"]
    assert "⬜ 另有 1 檔缺淨值，未列入" in hld1["tail_lines"]
    assert hld1["tail_lines"].count(logic.HLD1_SKIPPED_NOTE) == 1
    assert hld1["missing_nav_count"] == 1   # 只數真正缺淨值的那一檔


def test_過期與缺淨值_HLD5淨值圖位置各寫各的():
    model = _model(today=FRESH, mutate=_both(_age_one("AAAA", 20), _drop_nav("BBBB")))
    texts = {i["_fund_code"]: i["nav_plot_text"] for i in logic.find_block(model, "HLD-5")["_items"]}
    assert texts["AAAA"] == "⬜ 資料未備：最近淨值已超過 10 日"
    assert texts["BBBB"] == "⬜ 資料未備：nav 尚無資料"          # 真正缺淨值：原字面一字未動
    assert texts["CCCC"] == "〔淨值折線〕與〔配息長條〕共用同一條時間軸"


def test_只有缺淨值時_字面與裁決前逐字相同():
    model = _model(today=FRESH, mutate=_drop_nav("BBBB"))
    hld1 = logic.find_block(model, "HLD-1")
    assert "⬜ 另有 1 檔缺淨值，未列入" in hld1["tail_lines"]
    assert not [line for line in hld1["tail_lines"] if "未更新" in line]
    texts = {i["_fund_code"]: i["nav_plot_text"] for i in logic.find_block(model, "HLD-5")["_items"]}
    assert texts["BBBB"] == logic.empty_source_text(["nav"])


def test_過期字面的天數取共用常數_不寫死(monkeypatch):
    monkeypatch.setattr(live, "NAV_FRESH_DAYS_YELLOW", 5)
    model = _model(today=_LAST + timedelta(days=6))
    hld1 = logic.find_block(model, "HLD-1")
    assert "⬜ 另有 3 檔淨值超過 5 日未更新（資料未備），未列入" in hld1["tail_lines"]
    texts = {i["_fund_code"]: i["nav_plot_text"] for i in logic.find_block(model, "HLD-5")["_items"]}
    assert set(texts.values()) == {"⬜ 資料未備：最近淨值已超過 5 日"}
    # 稽核 D（H6d）：非預存那幾檔的灰色副標（`NAV_NOTE_NOT_READY`）也跟著常數變
    for code in ("AAAA", "BBBB", "CCCC"):
        assert _group(model, "HLD-2", code)["freshness_note"]["text"] == "最近一筆淨值 2026-09-18，已超過 5 日"


def test_logic_有過期代碼卻沒給天數_raise():
    args = _args()
    with pytest.raises(ValueError, match="nav_not_ready_days"):
        logic.build_page_model(**args, nav_not_ready_codes={"AAAA"})
    with pytest.raises(TypeError, match="nav_not_ready_codes"):
        logic.build_page_model(**_args(), nav_not_ready_codes="AAAA", nav_not_ready_days=10)


def test_示範模式_不給過期代碼_一格不變():
    args = _args()
    assert logic.build_page_model(**copy.deepcopy(args)) == logic.build_page_model(
        **copy.deepcopy(args), nav_not_ready_codes=frozenset(), nav_not_ready_days=None)


def test_過期字面_兩頁逐字相同():
    """hld 與 alo 不互相 import；同一句以 AST 從 alo 原始檔讀出比對。"""
    import ast as _ast

    for node in _ast.parse(_ALO_LOGIC.read_text(encoding="utf-8")).body:
        if isinstance(node, _ast.Assign) and any(getattr(t, "id", None) == "NAV_NOT_READY_TEXT" for t in node.targets):
            assert _ast.literal_eval(node.value) == logic.NAV_NOT_READY_TEXT
            break
    else:
        raise AssertionError("ui_v2/alo/logic.py 沒有 NAV_NOT_READY_TEXT")
    assert logic.nav_not_ready_text(10) == "⬜ 資料未備：最近淨值已超過 10 日"
    assert logic.nav_not_ready_text(10) != logic.empty_source_text(["nav"])


# ═══════════════ 總管 2026-10-13 裁決（稽核 C2）：HLD-6／HLD-7 也要看得出是「淨值過期被拿掉」 ═══════════════

_C2_LINE = "⬜ 另有 1 檔淨值超過 10 日未更新（資料未備），未列入"


def test_C2_部分過期_HLD6與HLD7各加一行中性說明_真缺淨值的檔不算():
    model = _model(today=FRESH, mutate=_both(_age_one("AAAA", 20), _drop_nav("BBBB")))
    for code in ("HLD-6", "HLD-7"):
        block = logic.find_block(model, code)
        assert block["detail_lines"].count(_C2_LINE) == 1, code
        assert block["_tone"] != "黃" and block["_tone"] != "紅", code
    # HLD-7 那一檔以淨值為輸入的列仍是「0 筆」，說明行交代原因
    rows = [r for r in logic.find_block(model, "HLD-7")["_rows"]
            if r["_fund_code"] == "AAAA" and r["_indicator"] in logic.NAV_INPUT_INDICATORS]
    assert rows and all(r["inputs_text"] == "0 筆" for r in rows)


def test_C2_全部過期_HLD6與HLD7寫出3檔():
    model = _model(today=TODAY)
    line = "⬜ 另有 3 檔淨值超過 10 日未更新（資料未備），未列入"
    assert logic.find_block(model, "HLD-6")["summary_text"].startswith("淨值 0 列")
    for code in ("HLD-6", "HLD-7"):
        assert line in logic.find_block(model, code)["detail_lines"], code


def test_C2_只有真缺淨值或全部新鮮_HLD6與HLD7不加這一行():
    for model in (_model(today=FRESH), _model(today=FRESH, mutate=_drop_nav("BBBB"))):
        for code in ("HLD-6", "HLD-7"):
            assert not [line for line in logic.find_block(model, code)["detail_lines"] if "未更新" in line], code


def test_C2_天數取共用常數(monkeypatch):
    monkeypatch.setattr(live, "NAV_FRESH_DAYS_YELLOW", 5)
    model = _model(today=_LAST + timedelta(days=6))
    for code in ("HLD-6", "HLD-7"):
        assert "⬜ 另有 3 檔淨值超過 5 日未更新（資料未備），未列入" in logic.find_block(model, code)["detail_lines"]


# 稽核 D（H8b）：門檻是「不吃淨值」的期間配息合計時，過期的檔照樣進 HLD-1（配息照算），
# 但它沒有用到淨值 ⇒ 不得被算進「淨值取自預存序列」的卡尾計數。
_DIV_RULE = [{"indicator": "期間配息合計", "direction": "高於", "value": 0.0}]


def test_H8b_不吃淨值的門檻_過期檔在偏離表上_卻不算進預存序列計數():
    model = _model(today=FRESH, fallback={"AAAA", "BBBB", "CCCC"}, mutate=_age_one("AAAA", 20),
                   applied_rules=_DIV_RULE)
    hld1 = logic.find_block(model, "HLD-1")
    listed = {r["_fund_code"] for r in hld1["_rows"]}
    assert "AAAA" in listed and len(listed) >= 2   # 前提：過期那一檔照樣因配息門檻列上卡
    assert hld1["freshness_tail"] == {
        "text": f"本卡所列的檔中，{len(listed) - 1} 檔的淨值取自預存序列，逐檔見 HLD-6", "_tone": "中性"}
    # 正控：同一組門檻、AAAA 不過期時，三檔都算
    fresh = logic.find_block(_model(today=FRESH, fallback={"AAAA", "BBBB", "CCCC"}, applied_rules=_DIV_RULE), "HLD-1")
    assert fresh["freshness_tail"]["text"].startswith(f"本卡所列的檔中，{len(listed)} 檔")
