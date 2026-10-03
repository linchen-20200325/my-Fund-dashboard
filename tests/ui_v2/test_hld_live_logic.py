# -*- coding: utf-8 -*-
"""持倉體檢正式模式呈現層（`ui_v2/hld/live.py`）的純函式測試。hld 接真資料 S3。

依據：客戶 2026-10-02 裁示（`docs/wireframes/draft_hld_live.html` §G 第 2 題 2-A、第 4 題 4-C）
與客戶 2026-10-02 裁示 A（「存檔」「重新取數」停用原因，逐字）。

本輪不接取數：正式模式的模型拿假資料的 dataset 跑。本檔不 import streamlit。
"""

import ast
import copy
import pathlib
import re
import sys
import threading
from datetime import date, datetime, timedelta, timezone

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ui_v2.hld import fixtures, live, logic  # noqa: E402

_LIVE_PY = pathlib.Path(__file__).resolve().parents[2] / "ui_v2" / "hld" / "live.py"


def _scrub(node):
    """把假資料**本身**帶的「（示意）」拿掉（基金名、類別、保單名、錯誤訊息）。

    正式模式不讀 fixtures，那些字不會出現（草稿 §E P16）；這裡拿掉它們，
    好讓「模型裡一個（示意）都沒有」這件事只量得到**程式自己接上去的**字尾。
    """
    if isinstance(node, str):
        return node.replace(logic.HINT, "")
    if isinstance(node, dict):
        return {k: _scrub(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_scrub(v) for v in node]
    if isinstance(node, tuple):
        return tuple(_scrub(v) for v in node)
    return node


_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _module_constant(rel, name):
    """用 AST 從舊樹原始檔讀出一個常數（本檔不 import 舊樹，也不另抄一份字面）。"""
    path = _REPO_ROOT / rel
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} 不在 {rel}")


# L2 `contract.DIRECT_POLICY_ID`（S4 第二輪 M2：正式模式一律要給）。
_DIRECT_ID = _module_constant("services/v2_tables/contract.py", "DIRECT_POLICY_ID")
# 假資料裡掛在 DIRECT 下的持倉，正式模式的測試改掛到這張既有保單（S4 第二輪 M2：
# L2 不為 DIRECT 產生 `holding` 列，正式模式拿到 DIRECT 持倉會 raise）。示範模式照用同一份，比對才對得上。
_REHOME_POLICY = "P-001"


def _scenario_args(name, *, scrub=True):
    args = copy.deepcopy(fixtures.scenario(name))
    for holding in args["dataset"].get("holding") or ():
        if holding["policy_id"] == _DIRECT_ID:
            holding["policy_id"] = _REHOME_POLICY
    return _scrub(args) if scrub else args


def _prov(dataset, *, fallback=(), stale=None):
    """L2 `build_nav_table` 的 `provenance` 形狀（`services/v2_tables/nav_dividend.py::rows_from_nav_series`）：
    淨值表裡每一檔一筆；`fallback` 裡的檔走預存那一支。"""
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


def _build(*args, **kw):
    """正式模式的 `build_live_model`，帶上 `direct_policy_id`；`nav_provenance` 沒給就補「全部即時取回」（S5）。"""
    if "nav_provenance" not in kw:
        kw["nav_provenance"] = _prov(args[0] if args else kw["dataset"])
    return live.build_live_model(*args, direct_policy_id=_DIRECT_ID, **kw)


def _first_holding(dataset):
    holdings = dataset.get("holding") or []
    return holdings[0]["holding_id"] if holdings else None


def _live(name, **kw):
    return _build(**_scenario_args(name), **kw)


def _demo(name, **kw):
    return logic.build_page_model(**_scenario_args(name), **kw)


_ALL = fixtures.ALL_SCENARIO_NAMES


# ───────────────────────── 1. 示意字樣（裁示 2-A） ─────────────────────────


@pytest.mark.parametrize("name", _ALL)
def test_正式模式_全頁模型沒有任何一個示意字樣(name):
    args = _scenario_args(name)
    model = _build(**args, open_fund=_first_holding(args["dataset"]))
    hits = [s for s in logic.collect_ui_strings(model) if "示意" in s]
    assert hits == []


@pytest.mark.parametrize("name", _ALL)
def test_示範模式_同一份去字資料_照舊帶示意字樣(name):
    """正控：上一條若只是因為資料裡沒有示意字樣才過，這一條會紅。
    空持倉的情境畫面上沒有任何一個數字，本來就沒有字尾可接 —— 那幾個只驗「沒有」。"""
    args = _scenario_args(name)
    if not args["dataset"].get("holding"):
        pytest.skip("空持倉：畫面上沒有數字，示範模式本來就沒有字尾")
    model = logic.build_page_model(**args, open_fund=_first_holding(args["dataset"]))
    assert any(logic.HINT in s for s in logic.collect_ui_strings(model))


def test_HLD1收合摘要_寫死的那一處示意字面_正式模式也拿掉():
    """草稿 §E P7：「N 列（示意）」原本寫死、沒有走 HINT，只把 HINT 改空會漏。"""
    live_hld1 = logic.find_block(_live("full"), "HLD-1")
    demo_hld1 = logic.find_block(_demo("full"), "HLD-1")
    n = len(demo_hld1["_rows"])
    assert n > 0
    assert demo_hld1["summary_text"] == f"{n} 列（示意）"
    assert live_hld1["summary_text"] == f"{n} 列"


def test_示範模式_demo_hint預設為真_與明傳True逐字相同():
    args = _scenario_args("full", scrub=False)
    assert logic.build_page_model(**args) == logic.build_page_model(**copy.deepcopy(args), demo_hint=True)


def test_正式模式組完之後_示範模式不被污染():
    """開關住在 ContextVar；`build_page_model` 結束一定要還原，否則下一個示範模式的呼叫會少字。"""
    _live("full")
    assert logic._hint() == logic.HINT
    # 不拿「組正式模式之前」那一份當基準：前面任何一條測試若已污染，前後兩份會一樣地少字而照樣相等。
    assert logic.find_block(_demo("full"), "HLD-1")["summary_text"].endswith(logic.HINT)


def test_組模型中途炸掉_開關照樣還原():
    bad = _scenario_args("full")
    bad["dataset"]["holding"].append(dict(bad["dataset"]["holding"][0]))  # holding_id 重複 → raise
    with pytest.raises(Exception):
        logic.build_page_model(**bad, demo_hint=False)
    assert logic._hint() == logic.HINT
    assert logic.find_block(_demo("full"), "HLD-1")["summary_text"].endswith(logic.HINT)


@pytest.mark.parametrize("name", _ALL)
def test_正式模式只差三件事_其餘逐字與示範模式相同(name):
    """示範模型 → 去示意字尾 → 改欄名 → 停用兩類按鈕 → 掛新鮮度標示（S5），必須恰好等於正式模型。
    正式模式若多改了任何一格（新增按鈕、改了別的字），這一條會紅。"""
    args = _scenario_args(name)
    open_fund = _first_holding(args["dataset"])
    today = date(2026, 10, 2)
    demo = logic.build_page_model(**copy.deepcopy(args), open_fund=open_fund)
    fresh = live.nav_freshness(args["dataset"], _prov(args["dataset"]), today=today)
    expected = live._apply_freshness(live.apply_live_notes(_scrub(demo), today=today), fresh)
    got = _build(**args, open_fund=open_fund, today=today)
    assert got == expected


# ───────────────────────── 2. 最後核對日（裁示 4-C） ─────────────────────────


def _hld5_fields(model):
    return [item["_fields"] for item in logic.find_block(model, "HLD-5")["_items"]]


def test_正式模式_HLD5欄名改為最後核對日只記日期_值只有日期():
    args = _scenario_args("full")
    holdings = {h["holding_id"]: h for h in args["dataset"]["holding"]}
    block = logic.find_block(_build(**args, today=TODAY), "HLD-5")
    assert block["_items"]
    for item in block["_items"]:
        labels = [label for label, _ in item["_fields"]]
        assert "最後核對日（只記日期）" in labels
        assert "最後對帳" not in labels
        value = dict(item["_fields"])["最後核對日（只記日期）"]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
        assert value == live.sync_date(holdings[item["_holding_id"]]["last_synced_at"], today=TODAY)


def test_正式模式_欄位順序不變_只換那一格的名字():
    demo = [[label for label, _ in f] for f in _hld5_fields(_demo("full"))]
    got = [[label for label, _ in f] for f in _hld5_fields(_live("full"))]
    assert got == [
        ["最後核對日（只記日期）" if label == "最後對帳" else label for label in row] for row in demo
    ]


def test_示範模式_HLD5欄名照舊是最後對帳():
    """草稿 §G 第 4 題只裁正式版；假資料版沒寫 ⇒ 不動。"""
    for fields in _hld5_fields(_demo("full")):
        labels = [label for label, _ in fields]
        assert "最後對帳" in labels
        assert "最後核對日（只記日期）" not in labels


TODAY = date(2026, 10, 2)


@pytest.mark.parametrize(
    "raw, want",
    [
        ("2026-09-19", "2026-09-19"),                      # 只有日期 → 照原樣
        ("2026-09-18T20:30:00Z", "2026-09-19"),            # 紅隊 J2：台灣是隔天
        ("2026-09-18T15:59:59Z", "2026-09-18"),            # 台灣 23:59:59
        ("2026-09-18T16:00:00Z", "2026-09-19"),            # 台灣 00:00:00
        ("2026-09-19T08:00:00+08:00", "2026-09-19"),
        ("2026-09-19 04:00:00+00:00", "2026-09-19"),       # 空白分隔也是 ISO
        ("2026-10-02T15:59:00Z", "2026-10-02"),            # 換算後恰好是今天 → 合格
        ("2026-10-02", "2026-10-02"),                      # 只有日期、恰好是今天 → 合格
    ],
)
def test_最後核對日_合格值換成台灣日期(raw, want):
    assert live.sync_date(raw, today=TODAY) == want


_BAD_SYNC = [
    "", "2026-02-30", "2026/09/19", " 2026-09-19", "2026-09-19 ", None, 20260919,
    "2026-09-19T12:00",          # 沒帶時區
    "2026-09-19xyz",             # 前 10 個字合格、後面接了別的
    "2026-09-19T",
    "2026-10-02T16:00:00Z",      # 換算後是台灣 10-03，晚於今天
    "2026-10-03",                # 只有日期、晚於今天（總管 S3 第二輪補充裁定）
    "2026-10-31",
    "20260919T010000Z", "2026-W38-6",
    "九月十五日中午十二點",
    # 紅隊 M1：換算到台灣時間會跑出公元 1～9999 年之外（`astimezone` 拋 OverflowError）
    "0001-01-01T00:00:00+14:00", "0001-01-01T07:00:00+08:00", "9999-12-31T23:00:00-08:00",
    # 非 ASCII 數字（規格組建議 1）
    "２０２６-09-19", "2026-09-1٩", "2026-09-19T１２:00:00Z",
]


@pytest.mark.parametrize("raw", _BAD_SYNC)
def test_最後核對日_不合格值回None(raw):
    assert live.sync_date(raw, today=TODAY) is None


def _with_sync(raw, index=1):
    args = _scenario_args("full")
    args["dataset"]["holding"][index]["last_synced_at"] = raw
    return args


def _sync_cell(model, holding_id):
    for item in logic.find_block(model, "HLD-5")["_items"]:
        if item["_holding_id"] == holding_id:
            return dict(item["_fields"])["最後核對日（只記日期）"]
    raise KeyError(holding_id)


@pytest.mark.parametrize("raw", _BAD_SYNC)
@pytest.mark.parametrize("opened", [False, True])
def test_最後核對日一格不合格_整頁不崩_那一格進系統錯誤(raw, opened):
    """紅隊 J1／總管裁定 1：不合格的那一格走值狀態（`系統錯誤`），其餘照常。沒展開的檔也一樣。"""
    args = _with_sync(raw)
    bad_id = args["dataset"]["holding"][1]["holding_id"]
    code = args["dataset"]["holding"][1]["fund_code"]
    open_fund = bad_id if opened else None
    model = _build(**args, open_fund=open_fund, today=TODAY)
    cell = _sync_cell(model, bad_id)
    assert cell["_value_node"] is True
    assert cell["_state"] == logic.STATE_ERROR
    assert cell["text"] == logic.ERR_TEXT
    assert cell["reason_text"] == live.bad_sync_message(raw)
    assert repr(raw) in cell["reason_text"]
    assert cell in logic.non_ok_value_nodes(model)
    hld5 = logic.find_block(model, "HLD-5")
    policy_id = args["dataset"]["holding"][1]["policy_id"]
    policy_name = {p["policy_id"]: p["policy_name"] for p in args["dataset"]["policy"]}[policy_id]
    want_line = logic.fund_fetch_failed_text(code, f"{policy_name}：{live.bad_sync_message(raw)}")
    assert want_line in hld5["detail_lines"]

    # 其他照常：拿同一檔換成合格值的那一份對照，除了 HLD-5 這一格與說明區那兩行，整頁逐字相同。
    good = _build(**_with_sync("2026-09-19"), open_fund=open_fund, today=TODAY)
    good_hld5 = logic.find_block(good, "HLD-5")
    assert [b for b in model["blocks"] if b["code"] != "HLD-5"] == [
        b for b in good["blocks"] if b["code"] != "HLD-5"
    ]
    # 塊態與摘要不動；色調比照 S2 裁定 7 變紅（S3 第三輪，紅隊 J3）。
    assert (hld5["_state"], hld5["summary_text"]) == (good_hld5["_state"], good_hld5["summary_text"])
    assert good_hld5["_tone"] == logic.tone_for_state(good_hld5["_state"])
    assert hld5["_tone"] == "紅"
    assert hld5["detail_lines"] == good_hld5["detail_lines"] + [want_line, logic.PRINT_AS_IS_LINE]
    for got, ok in zip(hld5["_items"], good_hld5["_items"]):
        if got["_holding_id"] == bad_id:
            got = dict(got, _fields=[f for f in got["_fields"] if f[0] != "最後核對日（只記日期）"])
            ok = dict(ok, _fields=[f for f in ok["_fields"] if f[0] != "最後核對日（只記日期）"])
        assert got == ok


def test_紅隊J2_帶時區的值_正式版顯示台灣日期():
    args = _with_sync("2026-09-18T20:30:00Z")
    bad_id = args["dataset"]["holding"][1]["holding_id"]
    assert _sync_cell(_build(**args, today=TODAY), bad_id) == "2026-09-19"


def test_只有日期_今天合格_明天不合格():
    """總管 S3 第二輪補充裁定：只有日期而晚於台灣的今天 → 不合格；今天當天照樣合格。"""
    assert live.sync_date("2026-10-02", today=TODAY) == "2026-10-02"
    assert live.sync_date("2026-10-01", today=TODAY) == "2026-10-01"
    assert live.sync_date("2026-10-03", today=TODAY) is None
    args = _with_sync("2026-10-03")
    hid = args["dataset"]["holding"][1]["holding_id"]
    cell = _sync_cell(_build(**copy.deepcopy(args), today=TODAY), hid)
    assert cell["_state"] == logic.STATE_ERROR
    assert _sync_cell(_build(**args, today=date(2026, 10, 3)), hid) == "2026-10-03"


def test_今天可以注入_同一個值換一天就變不合格():
    args = _with_sync("2026-09-20T01:00:00Z")
    hid = args["dataset"]["holding"][1]["holding_id"]
    assert _sync_cell(_build(**copy.deepcopy(args), today=date(2026, 9, 20)), hid) == "2026-09-20"
    cell = _sync_cell(_build(**args, today=date(2026, 9, 19)), hid)
    assert cell["_state"] == logic.STATE_ERROR


def test_不傳今天_取台灣的今天():
    tw_now = datetime.now(timezone(timedelta(hours=8)))
    tomorrow_tw = (tw_now + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    today_tw = tw_now.replace(hour=0, minute=0, second=1, microsecond=0)
    for raw, bad in ((tomorrow_tw.isoformat(), True), (today_tw.isoformat(), False)):
        args = _with_sync(raw)
        hid = args["dataset"]["holding"][1]["holding_id"]
        cell = _sync_cell(_build(**args), hid)
        assert isinstance(cell, dict) is bad, raw


def test_台灣的今天_用台灣日期_不用UTC日期():
    """UTC 2026-10-02 17:00 ＝ 台灣 10-03 01:00。用 UTC 日期會差一天（這一條不看執行當下的時鐘）。"""
    assert live.taiwan_today(datetime(2026, 10, 2, 17, 0, tzinfo=timezone.utc)) == date(2026, 10, 3)
    assert live.taiwan_today(datetime(2026, 10, 2, 15, 59, tzinfo=timezone.utc)) == date(2026, 10, 2)


def test_示範模式遇到不合格值_行為與base相同():
    """假資料版只動正式版：示範模式照舊取前 10 個字（`None` 照舊炸），一格不驗。"""
    args = _with_sync("2026/09/19xx")
    hid = args["dataset"]["holding"][1]["holding_id"]
    item = [i for i in logic.find_block(logic.build_page_model(**args), "HLD-5")["_items"] if i["_holding_id"] == hid][0]
    assert dict(item["_fields"])["最後對帳"] == "2026/09/19" + logic.HINT
    with pytest.raises(TypeError):
        logic.build_page_model(**_with_sync(None))


def test_紅隊M1_極端年份帶時區_不拋OverflowError():
    for raw in ("0001-01-01T00:00:00+14:00", "0001-01-01T07:00:00+08:00", "9999-12-31T23:00:00-08:00"):
        assert live.sync_date(raw, today=TODAY) is None
        args = _with_sync(raw)
        hid = args["dataset"]["holding"][1]["holding_id"]
        assert _sync_cell(_build(**args, today=TODAY), hid)["_state"] == logic.STATE_ERROR


def test_日期正則只認ASCII數字():
    for text in ("２０２６-09-19", "2026-09-1٩", "２０２６-０９-１９"):
        assert live._DATE_ONLY.fullmatch(text) is None
    for text in ("2026-09-19T１２:00", "２０２６-09-19T12:00", "2026-09-19 12:0٩"):
        assert live._DATETIME_HEAD.match(text) is None
    assert live._DATE_ONLY.fullmatch("2026-09-19")
    assert live._DATETIME_HEAD.match("2026-09-19T12:00")


def test_非ASCII數字_是正則擋下的_不是解析擋下的(monkeypatch):
    """把後面的解析換成「什麼都收」：若擋下非 ASCII 數字的是解析而不是正則，這一條就會放行。"""

    class _AnyDate(date):
        @classmethod
        def fromisoformat(cls, text):
            return date(2026, 9, 19)

    class _AnyDateTime(datetime):
        @classmethod
        def fromisoformat(cls, text):
            return datetime(2026, 9, 19, 4, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(live, "date", _AnyDate)
    monkeypatch.setattr(live, "datetime", _AnyDateTime)
    assert live.sync_date("2026-09-19", today=TODAY) == "2026-09-19"            # 正控：ASCII 照收
    assert live.sync_date("2026-09-19T04:00:00Z", today=TODAY) == "2026-09-19"  # 正控
    assert live.sync_date("２０２６-09-19", today=TODAY) is None
    assert live.sync_date("2026-09-19T１２:00:00Z", today=TODAY) is None


def test_台灣的今天_now沒帶時區就報錯():
    with pytest.raises(ValueError):
        live.taiwan_today(datetime(2026, 10, 2, 17, 0))


def _two_policy_args(raw, *, same_name):
    """AAAA 掛在兩張保單下（`44` 4.1 一列＝一組 policy_id＋fund_code），兩列的最後核對日都填 `raw`。"""
    args = _scenario_args("full")
    ds = args["dataset"]
    base = next(h for h in ds["holding"] if h["fund_code"] == "AAAA")
    first_policy = next(p for p in ds["policy"] if p["policy_id"] == base["policy_id"])
    second = dict(first_policy, policy_id="P-002",
                  policy_name=first_policy["policy_name"] if same_name else "另一張投資型保單")
    ds["policy"].append(second)
    ds["holding"].append(dict(base, holding_id="H-AAAA-2", policy_id="P-002"))
    base["last_synced_at"] = raw
    ds["holding"][-1]["last_synced_at"] = raw
    return args, first_policy["policy_name"], second["policy_name"]


def test_紅隊J2_同一代碼掛兩張保單_原因行各一行_寫明保單():
    raw = "2026/09/19"
    args, name1, name2 = _two_policy_args(raw, same_name=False)
    assert name1 != name2
    hld5 = logic.find_block(_build(**args, today=TODAY), "HLD-5")
    fail_lines = [line for line in hld5["detail_lines"] if line.startswith("⛔")]
    assert fail_lines == [
        logic.fund_fetch_failed_text("AAAA", f"{name1}：{live.bad_sync_message(raw)}"),
        logic.fund_fetch_failed_text("AAAA", f"{name2}：{live.bad_sync_message(raw)}"),
    ]
    assert hld5["detail_lines"].count(logic.PRINT_AS_IS_LINE) == 1


def test_紅隊J2_兩張保單名稱也相同_仍是兩行不合併():
    raw = "2026/09/19"
    args, name1, name2 = _two_policy_args(raw, same_name=True)
    assert name1 == name2
    hld5 = logic.find_block(_build(**args, today=TODAY), "HLD-5")
    assert len([line for line in hld5["detail_lines"] if line.startswith("⛔")]) == 2


# ───────────────────────── 舊欄名找不到（總管裁定 4） ─────────────────────────


def _raw_live_model():
    return logic.build_page_model(**_scenario_args("full"), demo_hint=False)


def test_找不到舊欄名_直接報錯():
    model = _raw_live_model()
    item = logic.find_block(model, "HLD-5")["_items"][0]
    item["_fields"] = [("最後同步" if label == "最後對帳" else label, v) for label, v in item["_fields"]]
    with pytest.raises(ValueError, match="最後對帳"):
        live.apply_live_notes(model, today=TODAY)


def test_舊欄名出現兩格_也報錯():
    model = _raw_live_model()
    item = logic.find_block(model, "HLD-5")["_items"][0]
    item["_fields"] = list(item["_fields"]) + [("最後對帳", "2026-09-19")]
    with pytest.raises(ValueError, match="最後對帳"):
        live.apply_live_notes(model, today=TODAY)


def test_已經套過一次的模型_再套一次報錯():
    """正式模型裡已經沒有舊欄名；再套一次若靜默通過，代表找不到時是略過而不是報錯。"""
    with pytest.raises(ValueError):
        live.apply_live_notes(_live("full"), today=TODAY)


def test_沒有展開項目時_不報錯():
    hld5 = logic.find_block(_build(**_scenario_args("empty"), today=TODAY), "HLD-5")
    assert hld5["_items"] == []


# ───────────────────────── 多執行緒（規格組建議 1） ─────────────────────────


def test_兩條執行緒同時組示範與正式_輸出逐字與單獨組的相同(monkeypatch):
    """開關若住在模組全域（而不是 ContextVar），兩條執行緒的設定會互相蓋掉。

    用事件把交錯釘死，不靠運氣。會出事的次序是「外層先設、內層後設、外層先結束」：
      1. 示範那一條先進組模型（開關已設成示範），到中段停下；
      2. 正式那一條進組模型（開關設成正式），到中段停下；
      3. 示範那一條繼續、組完 —— 開關若是全域，它後半段讀到的是正式那一條設的空字串，會少字；
      4. 正式那一條繼續、組完 —— 開關若是全域，示範那一條結束時把它還原成示範，正式這半段會多字。
    ⚠️ 反過來的次序（正式先設、示範後設、示範先結束）是巢狀的，全域變數也不會出錯 ——
       上一版這支測試就是那個次序，所以殺不掉「換成模組全域」那個突變。
    """
    args = _scenario_args("full")
    want_demo = logic.build_page_model(**copy.deepcopy(args))
    want_live = _build(**copy.deepcopy(args), today=TODAY)

    demo_paused = threading.Event()
    live_paused = threading.Event()
    demo_done = threading.Event()
    real = logic._build_hld5
    paused_once = set()

    def paused(*a, **kw):
        name = threading.current_thread().name
        if name not in paused_once:
            paused_once.add(name)
            if name == "demo":
                demo_paused.set()
                assert live_paused.wait(10)
            elif name == "live":
                live_paused.set()
                assert demo_done.wait(10)
        return real(*a, **kw)

    monkeypatch.setattr(logic, "_build_hld5", paused)
    out = {}
    errors = []

    def run_demo():
        try:
            out["demo"] = logic.build_page_model(**copy.deepcopy(args))
        except Exception as exc:  # pragma: no cover - 失敗時才走到
            errors.append(exc)
        finally:
            demo_done.set()

    def run_live():
        try:
            assert demo_paused.wait(10)
            out["live"] = _build(**copy.deepcopy(args), today=TODAY)
        except Exception as exc:  # pragma: no cover
            errors.append(exc)
        finally:
            live_paused.set()

    threads = [threading.Thread(target=run_demo, name="demo"), threading.Thread(target=run_live, name="live")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert errors == []
    assert paused_once == {"demo", "live"}
    assert out["demo"] == want_demo
    assert out["live"] == want_live


# ───────────────────────── 3. 按鈕（裁示 A） ─────────────────────────


def test_停用原因逐字照裁示A():
    assert live.SAVE_DISABLED_REASON == "存檔寫入端尚未接上，這一輪只讀不寫"
    assert live.REFETCH_DISABLED_REASON == "重新取數尚未接上"


def test_存檔停用原因_與alo頁逐字相同():
    from ui_v2.alo import live as alo_live

    assert live.SAVE_DISABLED_REASON == alo_live.SAVE_DISABLED_REASON


def test_停用原因沒有指示動作的句子():
    for reason in (live.SAVE_DISABLED_REASON, live.REFETCH_DISABLED_REASON):
        assert "請" not in reason


def _buttons_by_block(model):
    return {
        block["code"]: [b for b in logic.collect_buttons(block)] for block in logic.all_blocks(model)
    }


@pytest.mark.parametrize("name", _ALL)
def test_存檔一律停用_原因逐字(name):
    saves = [b for b in logic.collect_buttons(_live(name)) if b["_action_kind"] == "存檔"]
    assert len(saves) == 1
    assert saves[0]["label"] == "存檔"
    assert saves[0]["_enabled"] is False
    assert saves[0]["_visible"] is True
    assert saves[0]["disabled_reason"] == live.SAVE_DISABLED_REASON


@pytest.mark.parametrize("name", _ALL)
def test_重新取數一律停用_原因逐字(name):
    for button in logic.collect_buttons(_live(name)):
        if button["_action_kind"] == "取數":
            assert button["label"] == "重新取數"
            assert button["_enabled"] is False
            assert button["_visible"] is True
            assert button["disabled_reason"] == live.REFETCH_DISABLED_REASON


def test_重新取數有出現的情境_確實停用了():
    """正控：上一條在沒有任何一枚重新取數的情境下會空轉過關；這裡釘住至少一個情境真的有。"""
    found = [
        name for name in _ALL
        if any(b["_action_kind"] == "取數" for b in logic.collect_buttons(_live(name)))
    ]
    assert "srcmiss" in found and "fetchfail" in found


@pytest.mark.parametrize("name", _ALL)
def test_按鈕出現在哪幾塊_正式與示範一枚不差(name):
    demo = _buttons_by_block(_demo(name))
    got = _buttons_by_block(_live(name))
    assert {k: [b["label"] for b in v] for k, v in got.items()} == {
        k: [b["label"] for b in v] for k, v in demo.items()
    }


@pytest.mark.parametrize("name", _ALL)
def test_HLD1到3不掛重新取數_HLD8依值狀態掛(name):
    model = _live(name)
    for code in ("HLD-1", "HLD-2", "HLD-3"):
        assert not [
            b for b in logic.collect_buttons(logic.find_block(model, code)) if b["_action_kind"] == "取數"
        ]
    hld8 = logic.find_block(model, "HLD-8")
    states = [
        row[key]["_state"] for row in hld8.get("_rows", []) for key in ("drawdown", "principal")
    ]
    has_retry = any(b["_action_kind"] == "取數" for b in logic.collect_buttons(hld8))
    assert has_retry == any(s in (logic.STATE_MISSING, logic.STATE_ERROR) for s in states)


@pytest.mark.parametrize("name", _ALL)
def test_其他類按鈕的啟用狀態_一格不動(name):
    demo = logic.collect_buttons(_demo(name))
    got = logic.collect_buttons(_live(name))
    assert len(demo) == len(got)
    for d, g in zip(demo, got):
        assert d["_action_kind"] == g["_action_kind"]
        if g["_action_kind"] not in ("存檔", "取數"):
            assert (g["_enabled"], g["disabled_reason"]) == (d["_enabled"], d["disabled_reason"])


def test_apply_live_notes不改呼叫端那一份():
    model = logic.build_page_model(**_scenario_args("srcmiss"), demo_hint=False)
    snapshot = copy.deepcopy(model)
    live.apply_live_notes(model)
    assert model == snapshot


# ───────────────────────── 4. 全頁守衛 ─────────────────────────


_BANNED = ("一鍵", "最佳", "推薦", "最適", "買進", "賣出", "加碼", "減碼")


@pytest.mark.parametrize("name", _ALL)
def test_正式模式全頁_禁詞零命中(name):
    strings = logic.collect_ui_strings(_live(name))
    assert logic.scan_forbidden(strings) == {}
    assert [s for s in strings if any(w in s for w in _BANNED)] == []


@pytest.mark.parametrize("name", _ALL)
def test_正式模式全頁_狀態徽章只用那七個字(name):
    for badge in logic.collect_badges(_live(name)):
        if badge["_kind"] == "狀態":
            assert badge["text"] in logic.STATUS_BADGE_LITERALS


@pytest.mark.parametrize("name", _ALL)
def test_正式模式全頁_識別碼零命中(name):
    strings = logic.collect_ui_strings(_live(name))
    assert [s for s in strings if re.search(r"session_[0-9A-Za-z]{16,}|claude\.ai/code", s)] == []


def test_live模組不import_streamlit_也不import_fixtures():
    tree = ast.parse(_LIVE_PY.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names += [f"{node.module or ''}.{a.name}" for a in node.names]
    assert not [n for n in names if "streamlit" in n or "fixtures" in n]


# ───────────────────────── 5. DIRECT 持倉另列（S4，裁示 3-B (ii)；S4 第二輪 M1／M2／J1／J2） ─────────────────────────
# 出處：`docs/wireframes/draft_hld_live.html` §F 選項 3-B、§G 第 3／3a 題；第二輪為總管裁定。
# L2 `direct` 清單三種來源的字面，用 AST 從 L1 讀出來。

_L1 = "repositories/policy_supplement_repository.py"
_POLICY_TAB = _module_constant(_L1, "POLICY_TAB_SOURCE")
_TAB_PROFILE = _module_constant(_L1, "TAB_POLICY_PROFILE")
_TAB_SUPPLEMENT = _module_constant(_L1, "TAB_HOLDING_SUPPLEMENT")
_SOURCES = frozenset({_POLICY_TAB, _TAB_PROFILE, _TAB_SUPPLEMENT})
_WARN = "⚠ DIRECT 列暫不支援，該筆不計入體檢（{n} 筆）"


def _l2_direct():
    """形狀照 `services/v2_tables/alo_holdings.py::load_alo_tables` 三處 `direct.append(...)`。"""
    return [
        {"source": _TAB_PROFILE, "tab": _TAB_PROFILE, "row": 7, "policy_id": _DIRECT_ID},
        {"source": _TAB_SUPPLEMENT, "tab": _TAB_SUPPLEMENT, "row": 31, "policy_id": _DIRECT_ID},
        {"source": _POLICY_TAB, "tab": "DIRECT", "row": 3, "policy_id": _DIRECT_ID, "fund_code": "J1", "fund_name": "J"},
        {"source": _POLICY_TAB, "tab": "DIRECT", "row": 5, "policy_id": _DIRECT_ID, "fund_code": "K1", "fund_name": "K"},
    ]


def _direct_kw(direct=None):
    return {
        "direct": _l2_direct() if direct is None else direct,
        "policy_tab_source": _POLICY_TAB,
        "direct_sources": _SOURCES,
    }


def _live_direct(name, direct=None):
    return _build(**_scenario_args(name), today=TODAY, **_direct_kw(direct))


def _empty_args():
    """紅隊 M1 重現情境：`full` 的資料，持倉清空（＝全部持倉都是 DIRECT，L2 一列都不交）。"""
    args = _scenario_args("full")
    args["dataset"]["holding"] = []
    return args


def _three_policy_tab():
    return [{"source": _POLICY_TAB, "tab": "DIRECT", "row": r} for r in (3, 5, 9)]


def _all_text_hits(model, needle):
    return sum(s.count(needle) for s in logic.collect_ui_strings(model))


def test_DIRECT_字面逐字照裁示3B_ii():
    assert live.DIRECT_EXCLUDED_TEXT.format(n=2) == "⚠ DIRECT 列暫不支援，該筆不計入體檢（2 筆）"
    assert live.DIRECT_LOCATION_TEXT.format(tab="DIRECT", row=3) == "DIRECT 第 3 列"
    assert live.DIRECT_SUMMARY_SUFFIX.format(n=2) == " · DIRECT 2 筆未列入"
    assert live.DIRECT_SUMMARY_ONLY.format(n=2) == "DIRECT 2 筆未列入"


def test_DIRECT_N只數保單分頁那一種():
    block = logic.find_block(_live_direct("full"), "HLD-5")
    assert block["tail_notes"] == [
        {"text": _WARN.format(n=2), "_tone": "黃"},
        {"text": "DIRECT 第 3 列", "_tone": "灰"},
        {"text": "DIRECT 第 5 列", "_tone": "灰"},
    ]
    assert "tail_lines" not in block   # 規格組建議 1：不與 HLD-1 的 `tail_lines` 同名


def test_DIRECT_摘要只在原摘要尾端加一段():
    want = logic.find_block(_live("full", today=TODAY), "HLD-5")["summary_text"]
    got = logic.find_block(_live_direct("full"), "HLD-5")["summary_text"]
    assert got == want + " · DIRECT 2 筆未列入"


def test_DIRECT_不進任何計算_除HLD5兩處外整頁模型不變():
    base = _live("full", today=TODAY)
    got = _live_direct("full")
    b5, g5 = logic.find_block(base, "HLD-5"), dict(logic.find_block(got, "HLD-5"))
    g5.pop("tail_notes")
    g5["summary_text"] = b5["summary_text"]
    assert g5 == b5
    for code in ("HLD-0", "HLD-1", "HLD-2", "HLD-3", "HLD-4", "HLD-6", "HLD-7", "HLD-8"):
        assert logic.find_block(got, code) == logic.find_block(base, code), code
    assert {k: v for k, v in got.items() if k != "blocks"} == {k: v for k, v in base.items() if k != "blocks"}


def test_DIRECT_N為0_什麼都不加():
    base = _live("full", today=TODAY)
    only_other_sources = [d for d in _l2_direct() if d["source"] != _POLICY_TAB]
    assert _live_direct("full", direct=only_other_sources) == base
    assert _live_direct("full", direct=[]) == base
    assert "tail_notes" not in logic.find_block(base, "HLD-5")


# ── 紅隊 M1：持倉全空而 N＞0 ──


def test_紅隊M1_重現情境_尚未建立任何持倉出現0次():
    model = _build(**_empty_args(), today=TODAY, **_direct_kw(_three_policy_tab()))
    assert _all_text_hits(model, logic.TEXT_NO_HOLDING) == 0


def test_紅隊M1_各出口逐一換成客戶那一句():
    warn = _WARN.format(n=3)
    base = _build(**_empty_args(), today=TODAY)
    model = _build(**_empty_args(), today=TODAY, **_direct_kw(_three_policy_tab()))
    hld0 = logic.find_block(model, "HLD-0")
    assert hld0["text"] == warn and hld0["summary_text"] == warn
    for code in ("HLD-1", "HLD-2", "HLD-3"):
        block, before = logic.find_block(model, code), logic.find_block(base, code)
        assert before["summary_text"] == logic.TEXT_NO_HOLDING, code
        assert block["summary_text"] == warn, code
        assert block["detail_lines"] == [warn if x == logic.TEXT_NO_HOLDING else x for x in before["detail_lines"]], code
    hld8 = logic.find_block(model, "HLD-8")
    assert hld8["summary_text"] == f"{logic.ND_TEXT}：{warn}"
    assert warn in hld8["detail_lines"]


def test_紅隊M1_HLD5摘要只剩筆數_空持倉那一句拿掉_卡尾照舊():
    base5 = logic.find_block(_build(**_empty_args(), today=TODAY), "HLD-5")
    g5 = logic.find_block(_build(**_empty_args(), today=TODAY, **_direct_kw(_three_policy_tab())), "HLD-5")
    assert g5["summary_text"] == "DIRECT 3 筆未列入"
    assert "尚未建立任何持倉，沒有可以展開的檔。" in base5["detail_lines"]
    assert g5["detail_lines"] == [x for x in base5["detail_lines"] if x != "尚未建立任何持倉，沒有可以展開的檔。"]
    assert g5["tail_notes"] == [{"text": _WARN.format(n=3), "_tone": "黃"}] + [
        {"text": f"DIRECT 第 {r} 列", "_tone": "灰"} for r in (3, 5, 9)
    ]


def test_紅隊M1_各塊state與tone與按鈕都不動():
    base = _build(**_empty_args(), today=TODAY)
    model = _build(**_empty_args(), today=TODAY, **_direct_kw(_three_policy_tab()))
    for b, g in zip(logic.all_blocks(base), logic.all_blocks(model)):
        assert (g["code"], g["_state"], g["_tone"]) == (b["code"], b["_state"], b["_tone"])
        assert logic.collect_buttons(g) == logic.collect_buttons(b), g["code"]


def test_紅隊M1_紅燈時括號補述那一句也換掉():
    """`emptyfail`：持倉為空且有一塊取數失敗 → HLD-0 是紅燈，「尚未建立任何持倉」躲在括號補述裡。"""
    args = _scenario_args("emptyfail")
    assert not args["dataset"].get("holding")
    warn = _WARN.format(n=3)
    model = _build(**args, today=TODAY, **_direct_kw(_three_policy_tab()))
    assert _all_text_hits(model, logic.TEXT_NO_HOLDING) == 0
    assert f"（另：{warn}。{logic.TEXT_SHEETS_READONLY}）" in logic.find_block(model, "HLD-0")["lines"]


def test_紅隊M1_反向_持倉為空而N為0_與S3一模一樣():
    base = _build(**_empty_args(), today=TODAY)
    assert _build(**_empty_args(), today=TODAY, **_direct_kw([])) == base
    only_other = [d for d in _l2_direct() if d["source"] != _POLICY_TAB]
    assert _build(**_empty_args(), today=TODAY, **_direct_kw(only_other)) == base
    assert _all_text_hits(base, logic.TEXT_NO_HOLDING) > 0     # 正控：S3 畫面上確實有那一句


def test_紅隊M1_有持倉時不換字():
    model = _live_direct("full")
    assert logic.find_block(model, "HLD-0")["text"] != _WARN.format(n=2)
    assert _all_text_hits(model, _WARN.format(n=2)) == 1       # 只有 HLD-5 卡尾那一行


# ── 紅隊 M2：holding 裡有 DIRECT 列 ──


@pytest.mark.parametrize("pid", [_DIRECT_ID, f" {_DIRECT_ID} "])
def test_紅隊M2_holding有DIRECT列_raise(pid):
    args = _scenario_args("full")
    args["dataset"]["holding"][0]["policy_id"] = pid
    with pytest.raises(ValueError):
        _build(**args, today=TODAY)


def test_紅隊M2_沒給direct_policy_id_raise():
    with pytest.raises(ValueError):
        live.build_live_model(**_scenario_args("full"), today=TODAY)
    with pytest.raises(ValueError):
        live.build_live_model(**_scenario_args("full"), today=TODAY, direct_policy_id="  ")


def test_紅隊M2_大小寫不同不算DIRECT():
    args = _scenario_args("full")
    args["dataset"]["holding"][0]["policy_id"] = _DIRECT_ID.lower()
    _build(**args, today=TODAY)   # 與 L2 一致：大小寫敏感，`direct` 當一般保單編號


# ── 紅隊 J1／J2：清單不合格一律 raise ──


def test_DIRECT_有清單卻沒給來源值_raise():
    with pytest.raises(ValueError):
        _build(**_scenario_args("full"), today=TODAY, direct=_l2_direct())
    with pytest.raises(ValueError):
        _build(**_scenario_args("full"), today=TODAY, direct=_l2_direct(), policy_tab_source=_POLICY_TAB)


def test_紅隊J1_認不得的source_raise():
    direct = _l2_direct() + [{"source": "別的分頁", "tab": "X", "row": 2}]
    with pytest.raises(ValueError, match="source"):
        _live_direct("full", direct=direct)


def test_紅隊J1_缺source鍵_raise():
    direct = _l2_direct()
    del direct[0]["source"]
    with pytest.raises(ValueError, match="source"):
        _live_direct("full", direct=direct)


@pytest.mark.parametrize("bad", ["not a list", {"a": 1}, 42, {_POLICY_TAB}])
def test_紅隊J2_direct不是list或tuple_TypeError(bad):
    with pytest.raises(TypeError, match="list 或 tuple"):
        _live_direct("full", direct=bad)
    with pytest.raises(TypeError, match="list 或 tuple"):
        live.direct_holding_rows(bad, policy_tab_source=_POLICY_TAB, direct_sources=_SOURCES)


def test_紅隊J2_direct可以是tuple():
    assert _live_direct("full", direct=tuple(_l2_direct())) == _live_direct("full")


@pytest.mark.parametrize("bad", ["x", 3, None, ["source"]])
def test_紅隊J2_元素不是dict_TypeError(bad):
    with pytest.raises(TypeError):
        _live_direct("full", direct=_l2_direct() + [bad])


def test_紅隊J2_policy_tab_source空字串_ValueError():
    with pytest.raises(ValueError, match="policy_tab_source 是空字串"):
        _build(**_scenario_args("full"), today=TODAY, direct=_l2_direct(), policy_tab_source="",
               direct_sources=_SOURCES)


@pytest.mark.parametrize(
    "bad",
    [{"tab": ""}, {"tab": "   "}, {"row": None}, {"row": True}, {"row": "3"}, {"row": 0}, {"row": -1}, {"row": 2.0}],
)
def test_紅隊J2_分頁名空白或列號不是正整數_ValueError(bad):
    direct = _l2_direct()
    direct[2].update(bad)
    with pytest.raises(ValueError):
        _live_direct("full", direct=direct)


@pytest.mark.parametrize("index", [0, 2])
def test_紅隊J2_非保單分頁那幾筆也驗(index):
    direct = _l2_direct()
    direct[index]["row"] = 0
    with pytest.raises(ValueError):
        _live_direct("full", direct=direct)


@pytest.mark.parametrize("index", [0, 2])
def test_紅隊J2_同一筆重複出現_ValueError_不去重(index):
    direct = _l2_direct()
    direct.append(dict(direct[index]))
    with pytest.raises(ValueError, match="重複"):
        _live_direct("full", direct=direct)


def test_紅隊J2_只有列號相同而分頁不同_不算重複():
    direct = _l2_direct() + [{"source": _POLICY_TAB, "tab": "P-001", "row": 3}]
    assert logic.find_block(_live_direct("full", direct=direct), "HLD-5")["summary_text"].endswith(" · DIRECT 3 筆未列入")


def test_DIRECT_不改呼叫端手上的清單():
    direct = _l2_direct()
    snapshot = copy.deepcopy(direct)
    _live_direct("full", direct=direct)
    assert direct == snapshot


@pytest.mark.parametrize("name", _ALL)
def test_DIRECT_示範模式不帶卡尾(name):
    block = logic.find_block(_demo(name), "HLD-5")
    assert "tail_notes" not in block and "tail_lines" not in block


def test_DIRECT_live不另寫一份DIRECT判定():
    """DIRECT 的值、來源字面都由呼叫端傳；本檔不寫 `"DIRECT"`、`"保單分頁"` 這類字面。"""
    tree = ast.parse(_LIVE_PY.read_text(encoding="utf-8"))
    literals = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert not [s for s in literals if s in _SOURCES]
    assert not [s for s in literals if s.strip() == _DIRECT_ID]


@pytest.mark.parametrize("name", _ALL)
def test_DIRECT_全頁禁詞與識別碼零命中(name):
    for model in (_live_direct(name), _build(**_empty_args(), today=TODAY, **_direct_kw(_three_policy_tab()))):
        strings = logic.collect_ui_strings(model)
        assert logic.scan_forbidden(strings) == {}
        assert [s for s in strings if any(w in s for w in _BANNED)] == []
        assert [s for s in strings if re.search(r"session_[0-9A-Za-z]{16,}|claude\.ai/code", s)] == []


# ───────────────────────── S4 第三輪（總管裁定） ─────────────────────────
# 1. 換字依位置：組合測試守「出口表沒漏列」，注入測試守「上游原文不碰、不崩」。

_TABLE_ERRORS = (None, "holding", "policy", "nav", "dividend", "fund_profile", "user_setting")   # 7 種
_PENDINGS = (
    frozenset(),
    frozenset({"dividend"}),
    frozenset({"fund_profile"}),
    frozenset({"nav", "dividend", "fund_profile"}),
)
_UPSTREAM_PLAIN = "ConnectionError: upstream timeout"


def _empty_dataset(*, table=None, message=_UPSTREAM_PLAIN, pending=frozenset(), rules=True, window=True):
    ds = fixtures._dataset(
        holding=[],
        window=(fixtures.WINDOW_START, fixtures.WINDOW_END) if window else None,
        rules=fixtures._RULES_DEFAULT if rules else None,
        errors={table: message} if table else None,
    )
    if pending:
        ds["pending_tables"] = pending
    return ds


_COMBOS = [
    (t, p, r, w) for t in _TABLE_ERRORS for p in _PENDINGS for r in (True, False) for w in (True, False)
]


@pytest.mark.parametrize("table,pending,rules,window", _COMBOS)
def test_第三輪1_空持倉組合_N大於0_本檔產生的字串不殘留尚未建立任何持倉(table, pending, rules, window):
    """上游訊息刻意不含那幾個字 ⇒ 模型裡任何一處殘留，都是本頁自己產生而沒換到的出口。"""
    ds = _empty_dataset(table=table, pending=pending, rules=rules, window=window)
    base = _build(copy.deepcopy(ds), today=TODAY)
    assert _all_text_hits(base, logic.TEXT_NO_HOLDING) > 0          # 正控：S3 畫面上確實有
    model = _build(ds, today=TODAY, **_direct_kw(_three_policy_tab()))
    assert _all_text_hits(model, logic.TEXT_NO_HOLDING) == 0
    for b, g in zip(logic.all_blocks(base), logic.all_blocks(model)):
        assert (g["_state"], g["_tone"]) == (b["_state"], b["_tone"]), g["code"]


def test_第三輪1_組合涵蓋紅燈與灰燈兩種HLD0():
    """組合裡要真的走到 HLD-0 的兩條分支（紅燈的括號補述、灰燈的標題），組合測試才有意義。"""
    tones = {logic.find_block(_build(_empty_dataset(table=t), today=TODAY), "HLD-0")["_tone"] for t in _TABLE_ERRORS}
    assert {"紅", "灰"} <= tones


_UPSTREAM_WITH_PHRASE = (logic.TEXT_NO_HOLDING, f"上游說：{logic.TEXT_NO_HOLDING}")


def _string_paths(node, path=()):
    """（路徑, 字串）逐一列出；HLD-5 那一塊除外（它的說明行依裁示會拿掉一行，位置會位移）。"""
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        if node.get("code") == "HLD-5":
            return
        for k, v in node.items():
            yield from _string_paths(v, path + (k,))
    elif isinstance(node, (list, tuple)):
        for i, v in enumerate(node):
            yield from _string_paths(v, path + (i,))


def _at(node, path):
    for key in path:
        node = node[key]
    return node


@pytest.mark.parametrize("message", _UPSTREAM_WITH_PHRASE)
@pytest.mark.parametrize("table", [t for t in _TABLE_ERRORS if t])
def test_第三輪1_上游原文含那幾個字_不崩且照印(table, message):
    ds = _empty_dataset(table=table, message=message)
    base = _build(copy.deepcopy(ds), today=TODAY)
    model = _build(ds, today=TODAY, **_direct_kw(_three_policy_tab()))
    # 本頁自己產生、依裁示要換掉（或拿掉）的字串，不算上游原文。
    templates = set(live._empty_replacements("").keys()) | {live._HLD5_EMPTY_LINE}


    def is_exit(path, s):
        """出口表的位置上、而且是模板字串 ⇒ 本頁自己產生的；其餘含原文的一律算上游。"""
        if s not in templates or len(path) < 3 or path[0] != "blocks":
            return False
        return (base["blocks"][path[1]]["code"], path[2]) in live._EMPTY_EXITS

    upstream = [(path, s) for path, s in _string_paths(base) if message in s and not is_exit(path, s)]
    # 正控：上游原文真的印上畫面了。`policy`／`user_setting` 的表層級錯誤在空持倉時 S3 本來就不印，
    # 那兩種只驗「不崩」（上面兩次 `_build` 沒 raise 就是）。
    assert bool(upstream) == (table not in ("policy", "user_setting")), table
    for path, s in upstream:                         # 同一個位置、同一個字串，一個字都不換
        assert _at(model, path) == s, path
    if table == "holding":
        hld1 = logic.find_block(model, "HLD-1")
        assert hld1["_placeholder"]["reason_text"] == message     # 原文本體：一個字都不換


def test_第三輪1_上游原文整串等於那幾個字_原文本體不被換():
    """第二輪的「值相等就換」會把 `errors["holding"]` 的原文本體換成警告句（紅隊 J1 後半）。"""
    ds = _empty_dataset(table="holding", message=logic.TEXT_NO_HOLDING)
    model = _build(ds, today=TODAY, **_direct_kw(_three_policy_tab()))
    assert logic.find_block(model, "HLD-1")["_placeholder"]["reason_text"] == logic.TEXT_NO_HOLDING
    assert logic.fetch_failed_text(logic.TEXT_NO_HOLDING) in logic.collect_ui_strings(model)


def test_第三輪1_分頁名含那幾個字_照印():
    direct = [{"source": _POLICY_TAB, "tab": logic.TEXT_NO_HOLDING, "row": 3}]
    model = _build(**_empty_args(), today=TODAY, **_direct_kw(direct))
    notes = logic.find_block(model, "HLD-5")["tail_notes"]
    assert notes[1]["text"] == f"{logic.TEXT_NO_HOLDING} 第 3 列"


def test_第三輪1_出口表就是那些位置():
    assert live._EMPTY_EXITS == (
        ("HLD-0", "text"), ("HLD-0", "summary_text"), ("HLD-0", "lines"),
        ("HLD-1", "summary_text"), ("HLD-1", "detail_lines"),
        ("HLD-2", "summary_text"), ("HLD-2", "detail_lines"),
        ("HLD-3", "summary_text"), ("HLD-3", "detail_lines"),
        ("HLD-8", "summary_text"), ("HLD-8", "detail_lines"),
    )


# 2. 規格組 V8

def test_第三輪2_policy_tab_source不在direct_sources裡_raise():
    with pytest.raises(ValueError, match="不在 direct_sources 裡"):
        _build(**_scenario_args("full"), today=TODAY, direct=_l2_direct(), policy_tab_source=_POLICY_TAB,
               direct_sources=_SOURCES - {_POLICY_TAB})


# 3. 紅隊建議 2：分頁名前後空白、含換行 → ValueError，不 strip

@pytest.mark.parametrize("tab", [" DIRECT", "DIRECT ", "\tDIRECT", "DI\nRECT", "DIRECT\r", "DI\rRECT"])
def test_第三輪3_分頁名前後空白或含換行_ValueError(tab):
    direct = _l2_direct()
    direct[2]["tab"] = tab
    with pytest.raises(ValueError, match="第 2 筆的 tab"):
        _live_direct("full", direct=direct)


# 4. 紅隊建議 3：source 不可雜湊 → TypeError，寫明哪一筆、哪個欄位

@pytest.mark.parametrize("bad", [[_POLICY_TAB], {"a": 1}, {_POLICY_TAB}, 3])
def test_第三輪4_source型別不對_TypeError寫明位置(bad):
    direct = _l2_direct()
    direct[1]["source"] = bad
    with pytest.raises(TypeError, match="第 1 筆的 source"):
        _live_direct("full", direct=direct)


# ───────────────────────── S6a：畫面上交代開發過程的子句（正式模式只刪不加） ─────────────────────────
# 總管 S6a 第二輪裁定：只刪「交代開發過程」的子句，留下的字不改、不新增；標點只做最小調整。

# 刪減後的實際字面（逐字；改字要先回總管）。
_TRIMMED = {
    "HLD-2": "第三個值「最大回撤」移到層 4 的 HLD-8。",
    "HLD-3": "第三個值「本金類配息佔比」移到層 4 的 HLD-8。配息類別未知的列仍計入期間配息合計。",
    "HLD-8": "這兩個值原本各是績效與風險卡、配息與本金卡的第三個值。"
    "兩個值都是比率，逐檔仍寫出幣別字面值，本表沒有任何跨幣別的合計、平均或比值。",
    "HLD-0": "（另：尚未設定門檻。）",
    # S6a 第四輪（規格組必修 2／紅隊 J1）：不是開發過程字句，同一體例只刪不加。
    "HLD-4": "「套用」只讀這些欄位的當下值、重算 HLD-1、HLD-2、HLD-3、HLD-5、HLD-7、HLD-8 六塊，"
    "不寫任何資料表、不改欄位的內容。",
}
_ORIGINAL = {
    "HLD-2": logic.HLD2_MOVED_NOTE,
    "HLD-3": logic.HLD3_MOVED_NOTE,
    "HLD-8": logic.HLD8_DETAIL_NOTE,
    "HLD-0": logic.HLD0_NO_RULES_ASIDE,
    "HLD-4": logic.HLD4_APPLY_NOTE,
}
_FIELD = {"HLD-2": "detail_lines", "HLD-3": "detail_lines", "HLD-8": "detail_lines", "HLD-0": "lines"}
# 被刪掉的子句（逐字），一個都不能留在正式畫面上。
_DELETED = (
    "已依客戶 2026-09-22 裁定",
    "客戶 2026-09-22 裁定核心卡各留兩個主值，第三個值移到這一層",
    "兩句同時成立時哪一句出現，規格沒有寫",
    "兩枚按鈕並存，各做一件事。",
    logic.HLD4_SAVE_SCOPE_NOTE,
)


def _is_subsequence(short: str, long: str) -> bool:
    it = iter(long)
    return all(ch in it for ch in short)


def test_S6a_子序列判斷本身會分辨():
    """正控：下一條若只是因為判斷式恆真才過，這一條會紅。"""
    assert _is_subsequence("ac", "abc")
    assert not _is_subsequence("ca", "abc")
    assert not _is_subsequence("（另：尚未設定門檻；）", logic.HLD0_NO_RULES_ASIDE)


def test_S6a_刪減後的字串是原字串的子序列_只刪不加():
    table = {code: (original, trimmed) for code, _f, original, trimmed, *_ in live._DEV_TRIMS}
    assert set(table) == set(_TRIMMED)
    for code, (original, trimmed) in table.items():
        assert original == _ORIGINAL[code], code
        assert trimmed == _TRIMMED[code], code
        assert _is_subsequence(trimmed, original), code
        assert len(trimmed) < len(original), code


def test_S6a_原字串與抽常數之前相同():
    """抽成常數只是為了讓 live 能逐字比對；字面一字未改（示範畫面逐位元組不變）。"""
    assert logic.HLD2_MOVED_NOTE == "第三個值「最大回撤」已依客戶 2026-09-22 裁定移到層 4 的 HLD-8。"
    assert logic.HLD3_MOVED_NOTE == (
        "第三個值「本金類配息佔比」已依客戶 2026-09-22 裁定移到層 4 的 HLD-8。配息類別未知的列仍計入期間配息合計。"
    )
    assert logic.HLD8_DETAIL_NOTE == (
        "這兩個值原本各是績效與風險卡、配息與本金卡的第三個值；客戶 2026-09-22 裁定核心卡各留兩個主值，"
        "第三個值移到這一層。兩個值都是比率，逐檔仍寫出幣別字面值，本表沒有任何跨幣別的合計、平均或比值。"
    )
    assert logic.HLD0_NO_RULES_ASIDE == "（另：尚未設定門檻。兩句同時成立時哪一句出現，規格沒有寫）"


@pytest.mark.parametrize("name", _ALL)
def test_S6a_正式模式_四處換成刪減版_其餘行照舊(name):
    args = _scenario_args(name)
    demo = _demo(name)
    got = _build(**args, today=TODAY)
    for code, field in _FIELD.items():
        before = logic.find_block(demo, code)[field]
        after = logic.find_block(got, code)[field]
        if code in ("HLD-2", "HLD-3") or (code == "HLD-8" and args["dataset"].get("holding")):
            # 正控：示範模式照印原句（否則下面那條只是因為本來就沒有才過）。
            assert _ORIGINAL[code] in before, (name, code)
        # 示範模式的示意字尾是程式接上去的（正式模式本來就不接），比對前拿掉。
        expected = [
            _TRIMMED[code] if line == _ORIGINAL[code] else line.replace(logic.HINT, "") for line in before
        ]
        assert after == expected, (name, code)


def test_S6a_HLD0那一句只在空持倉且門檻未設時出現_正式版換成刪減版():
    assert logic.HLD0_NO_RULES_ASIDE in logic.find_block(_demo("empty"), "HLD-0")["lines"]
    lines = logic.find_block(_build(**_scenario_args("empty"), today=TODAY), "HLD-0")["lines"]
    assert lines == [_TRIMMED["HLD-0"]]


@pytest.mark.parametrize("name", _ALL)
def test_S6a_正式模式_全頁模型沒有任何被刪的子句(name):
    args = _scenario_args(name)
    model = _build(**args, today=TODAY, open_fund=_first_holding(args["dataset"]))
    blob = "\n".join(logic.collect_ui_strings(model))
    for piece in _DELETED:
        assert piece not in blob, (name, piece)


def test_S6a_HLD5佔位框照留():
    """總管裁定 d 保留：圖表確實還沒做，是真實資訊。"""
    args = _scenario_args("full")
    model = _build(**args, today=TODAY, open_fund=_first_holding(args["dataset"]))
    assert "〔配息長條〕照畫 · 本輪以佔位框代替，不畫真圖" in logic.collect_ui_strings(model)


@pytest.mark.parametrize("code", ["HLD-2", "HLD-3"])
def test_S6a_一定出現的那幾句_logic改了字面而live沒跟上_raise(code):
    model = _demo("full")
    block = logic.find_block(model, code)
    block["detail_lines"] = [line for line in block["detail_lines"] if line != _ORIGINAL[code]]
    with pytest.raises(ValueError, match=f"{code} 的 detail_lines 沒有"):
        live.apply_live_notes(model, today=TODAY)


@pytest.mark.parametrize("name, code, field, old, new", [
    ("empty", "HLD-0", "lines", "（另：", "（另外："),
    ("full", "HLD-8", "detail_lines", "；客戶", "，客戶"),
])
def test_S6a_條件出現的那幾句字面漂移_殘留檢查raise(name, code, field, old, new):
    model = _demo(name)
    block = logic.find_block(model, code)
    assert any(old in line for line in block[field]), "沒有可改的字 —— 這一條會變成空掃"
    block[field] = [line.replace(old, new) for line in block[field]]
    with pytest.raises(ValueError, match=f"{code} 的 {field} 還有開發過程字句"):
        live.apply_live_notes(model, today=TODAY)


# ───────────────────────── S6b-1（T1）：殘留檢查不得因資料內容而 raise ─────────────────────────
# 上游錯誤原文經 `logic.fetch_failed_text` 進 HLD-0／HLD-2／HLD-3／HLD-8 的說明區；原文碰巧含
# 殘留檢查那一小段（「2026-09-22」「規格沒有寫」…）時，舊寫法把資料當成開發字句而 raise。


@pytest.mark.parametrize("table", logic.FUND_ERROR_TABLES)
@pytest.mark.parametrize("marker", sorted({m for *_x, m in live._DEV_TRIMS}))
def test_S6b1_T1_錯誤訊息含殘留檢查字串_不raise_原文照印(table, marker):
    args = _scenario_args("full")
    code = args["dataset"]["holding"][0]["fund_code"]
    message = f"上游回應含「{marker}」字樣"
    args["dataset"]["fund_errors"] = {table: {code: message}}
    model = _build(**args, today=TODAY)
    line = logic.fund_fetch_failed_text(code, message)
    hits = [
        c for c in ("HLD-0", "HLD-2", "HLD-3", "HLD-8")
        if line in (logic.find_block(model, c).get("detail_lines", []) + logic.find_block(model, c).get("lines", []))
    ]
    assert hits, "錯誤行沒上任何一塊 —— 這一條會變成空掃"


def test_S6b1_T1_範本行含殘留字串照樣raise_即使旁邊有錯誤行():
    """保護作用保留：錯誤行被略過，不代表同一欄位的範本行也被略過。"""
    model = _demo("full")
    block = logic.find_block(model, "HLD-2")
    block["detail_lines"] = list(block["detail_lines"]) + [
        logic.fetch_failed_text("上游 2026-09-22"),
        "第三個值已依客戶 2026-09-22 裁定移走。",
    ]
    with pytest.raises(ValueError, match="HLD-2 的 detail_lines 還有開發過程字句"):
        live.apply_live_notes(model, today=TODAY)


def test_S6b1_T1_錯誤行前綴取自logic本身():
    assert live._ERROR_LINE_PREFIX == logic.fetch_failed_text("")
    assert live._is_upstream_error_line(logic.fund_fetch_failed_text("AAAA", "x"))
    assert not live._is_upstream_error_line(logic.HLD2_MOVED_NOTE)


# ───────────────────────── S6a-1：HLD-4 講兩枚按鈕的三句，正式版不印 ─────────────────────────
# 客戶 2026-10-03 裁示：「套用」尚未接線、「存檔」停用，三句在正式版都不成立 ⇒ 整句不印（只刪不加）；示範版照舊。

_HLD4_DROPPED = (logic.HLD4_APPLY_NOTE, logic.HLD4_SAVE_NOTE, logic.HLD4_SAVE_SCOPE_NOTE)


def test_S6a1_HLD4三句_原字面與抽常數之前相同():
    assert logic.HLD4_APPLY_NOTE == (
        "兩枚按鈕並存，各做一件事。「套用」只讀這些欄位的當下值、"
        "重算 HLD-1、HLD-2、HLD-3、HLD-5、HLD-7、HLD-8 六塊，不寫任何資料表、不改欄位的內容。"
    )
    assert logic.HLD4_SAVE_NOTE == (
        "「存檔」把當下值寫回使用者設定並更新最後修改時間，不重算任何一塊。"
        "要兩件事都發生就兩枚都按；兩枚的先後不影響結果。"
    )
    assert logic.HLD4_SAVE_SCOPE_NOTE == (
        "「存檔」只寫使用者設定，不寫持倉、保單、淨值、配息四張表任何一張，"
        "也不代你填任何值、不把空欄補成任何候選值。"
    )


# ───────────────────────── S6a 第三輪 ─────────────────────────


def test_S6a第三輪_HLD4存檔那一句_原字面與抽常數之前相同():
    assert logic.HLD4_SAVE_NOTE == (
        "「存檔」把當下值寫回使用者設定並更新最後修改時間，不重算任何一塊。"
        "要兩件事都發生就兩枚都按；兩枚的先後不影響結果。"
    )


@pytest.mark.parametrize("name", _ALL)
def test_S6a1_正式版HLD4三句不印_示範版照印_其餘照舊(name):
    """~~三句整句不印~~ → S6a-2（客戶 2026-10-03 範圍裁示第 1 項；有意識的更正，不是漏刪）：
    「套用」接好了，`HLD4_APPLY_NOTE` 只刪「兩枚按鈕並存，各做一件事。」，講「套用」的那一段恢復；
    講「存檔」的兩句照舊整句不印。"""
    demo = logic.find_block(_demo(name), "HLD-4")["notes"]
    got = logic.find_block(_build(**_scenario_args(name), today=TODAY), "HLD-4")["notes"]
    for line in _HLD4_DROPPED:
        assert line in demo, line          # 正控：示範版照印
    dropped = (logic.HLD4_SAVE_NOTE, logic.HLD4_SAVE_SCOPE_NOTE)
    assert got == [
        _TRIMMED["HLD-4"] if line == logic.HLD4_APPLY_NOTE else line for line in demo if line not in dropped
    ]
    assert got, "拿掉之後 HLD-4 說明區不得變空"


@pytest.mark.parametrize("name", _ALL)
def test_S6a1_正式版全頁模型沒有那三句的任何一段(name):
    args = _scenario_args(name)
    blob = "\n".join(logic.collect_ui_strings(_build(**args, today=TODAY, open_fund=_first_holding(args["dataset"]))))
    # S6a-2：「只讀這些欄位的當下值」那一段恢復（「套用」接好了），不再列在這裡。
    for piece in ("兩枚按鈕並存", "把當下值寫回使用者設定", "「存檔」只寫使用者設定"):
        assert piece not in blob, (name, piece)


@pytest.mark.parametrize("index", [0, 1, 2])
def test_S6a1_logic改了任一句字面而live沒跟上_raise(index):
    model = _demo("full")
    block = logic.find_block(model, "HLD-4")
    block["notes"] = [line for line in block["notes"] if line != _HLD4_DROPPED[index]]
    with pytest.raises(ValueError, match="HLD-4 的 notes 沒有"):
        live.apply_live_notes(model, today=TODAY)


@pytest.mark.parametrize("name", _ALL)
def test_S6a第三輪_正式版HLD4不印存檔那一句_示範版照印_其餘照舊(name):
    """第四輪起同一區另外兩處：「兩枚按鈕並存，各做一件事。」刪掉、講存檔只寫什麼的那一句整句不印。"""
    demo = logic.find_block(_demo(name), "HLD-4")["notes"]
    got = logic.find_block(_build(**_scenario_args(name), today=TODAY), "HLD-4")["notes"]
    for line in (logic.HLD4_SAVE_NOTE, logic.HLD4_SAVE_SCOPE_NOTE, logic.HLD4_APPLY_NOTE):
        assert line in demo
    dropped = (logic.HLD4_SAVE_NOTE, logic.HLD4_SAVE_SCOPE_NOTE)
    assert got == [
        _TRIMMED["HLD-4"] if line == logic.HLD4_APPLY_NOTE else line for line in demo if line not in dropped
    ]


def test_S6a第三輪_logic改了存檔那一句而live沒跟上_raise():
    model = _demo("full")
    block = logic.find_block(model, "HLD-4")
    block["notes"] = [line for line in block["notes"] if line != logic.HLD4_SAVE_NOTE]
    with pytest.raises(ValueError, match="HLD-4 的 notes 沒有"):
        live.apply_live_notes(model, today=TODAY)


@pytest.mark.parametrize("name", _ALL)
def test_S6a第三輪_沒按套用時_模型與加參數之前相同(name):
    args = _scenario_args(name)
    assert logic.build_page_model(**args) == logic.build_page_model(**args, applied_window=None)


def test_S6a第三輪_套用的區間取代存過的區間_正式版照轉():
    args = _scenario_args("full")
    window = ("2026-06-01", "2026-09-19")
    demo = logic.build_page_model(**args, applied_window=window)
    got = _build(**args, today=TODAY, applied_window=window)
    assert demo["_window"] == got["_window"] == window
    assert logic.build_page_model(**args)["_window"] != window
    # 六塊裡會隨區間動的那幾塊，正式版與示範版拿到同一組數（示意字尾除外）。
    for code in ("HLD-2", "HLD-3"):
        a = [mv["text"].replace(logic.HINT, "") for g in logic.find_block(demo, code)["fund_groups"] for mv in g["main_values"]]
        b = [mv["text"] for g in logic.find_block(got, code)["fund_groups"] for mv in g["main_values"]]
        assert a == b, code


# ───────────────────────── S6a 第四輪 ─────────────────────────


def test_S6a第四輪_HLD4另兩句_原字面與抽常數之前相同():
    assert logic.HLD4_APPLY_NOTE == (
        "兩枚按鈕並存，各做一件事。「套用」只讀這些欄位的當下值、"
        "重算 HLD-1、HLD-2、HLD-3、HLD-5、HLD-7、HLD-8 六塊，不寫任何資料表、不改欄位的內容。"
    )
    assert logic.HLD4_SAVE_SCOPE_NOTE == (
        "「存檔」只寫使用者設定，不寫持倉、保單、淨值、配息四張表任何一張，"
        "也不代你填任何值、不把空欄補成任何候選值。"
    )


def test_S6a第四輪_正式版HLD4存檔範圍那一句找不到_raise():
    model = _demo("full")
    block = logic.find_block(model, "HLD-4")
    block["notes"] = [line for line in block["notes"] if line != logic.HLD4_SAVE_SCOPE_NOTE]
    with pytest.raises(ValueError, match="HLD-4 的 notes 沒有"):
        live.apply_live_notes(model, today=TODAY)


# 紅隊 M4：區間只收嚴格的 YYYY-MM-DD


@pytest.mark.parametrize("start", ["20260601", "2026-6-1", "2026/06/01", " 2026-06-01", "2026-06-01 ",
                                   "２０２６-06-01", "2026-W23-1", "2026-06-01T00:00", "2026-02-30"])
def test_S6a第四輪_區間格式不是YYYY_MM_DD_不合法(start):
    assert logic.window_is_valid((start, "2026-09-19")) is False
    assert logic.window_is_valid(("2026-01-01", start)) is False
    assert logic.window_input_blocked(start, "2026-09-19") is True


def test_S6a第四輪_合法區間照舊():
    assert logic.window_is_valid(("2026-06-01", "2026-09-19")) is True
    assert logic.window_is_valid(("2026-09-19", "2026-09-19")) is True
    assert logic.window_is_valid(("2026-09-20", "2026-09-19")) is False


@pytest.mark.parametrize("start, end, blocked", [
    ("", "", False), (None, None, False),            # 兩格都空：照舊可以套用（＝尚未設定區間）
    ("2026-06-01", "", True), ("", "2026-09-19", True),   # 只填一格（紅隊建議 2）
    ("2026-06-01", None, True),
    ("2026-06-01", "2026-09-19", False),
])
def test_S6a第四輪_只填一格不可套用(start, end, blocked):
    assert logic.window_input_blocked(start, end) is blocked


# 紅隊 M3：門檻列接上「套用」，只用既有規則


def test_S6a第四輪_門檻列當下值_轉成門檻():
    rows = [("最大回撤", "低於", "-1"), ("", "", ""), ("配息佔淨值比", "高於", "+6.50")]
    assert logic.rules_from_inputs(rows) == [
        {"indicator": "最大回撤", "direction": "低於", "value": -1.0},
        {"indicator": "配息佔淨值比", "direction": "高於", "value": 6.5},
    ]
    assert logic.rules_from_inputs([("", "", ""), (None, None, None)]) == []


@pytest.mark.parametrize("row", [
    ("最大回撤", "低於", ""), ("最大回撤", "", "-1"), ("", "低於", "-1"),     # 只填一兩格
    ("最大回撤", "低於", "abc"), ("最大回撤", "低於", "1e3"), ("最大回撤", "低於", "inf"),
    ("最大回撤", "低於", "nan"), ("最大回撤", "低於", " -1"), ("最大回撤", "低於", "1_0"),
    ("最大回撤", "低於", "-1."), ("最大回撤", "低於", "１"),
])
def test_S6a第四輪_門檻列既有規則處理不了_回None(row):
    assert logic.rules_from_inputs([row]) is None
    assert logic.applied_from_inputs("2026-01-01", "2026-09-19", [row]) is None


def test_S6a第四輪_母體外的指標名照既有規則收_方向只收高於低於():
    """既有規則：母體外的指標名 → 未列入（`deviation_rows`），照收。
    ~~方向不是低於／高於 → 照收、不算超出（`_breaches`）~~ → S6a-2 第 3 項（N2，客戶 2026-10-03；
    有意識的更正，不是漏刪）：那就是「那一列被默默略過」，改成不可套用。"""
    rules = logic.rules_from_inputs([("不存在的指標", "低於", "1")])
    assert [r["indicator"] for r in rules] == ["不存在的指標"]
    assert logic.rules_from_inputs([("不存在的指標", "低於", "1"), ("最大回撤", "等於", "1")]) is None


def test_S6a第四輪_applied_from_inputs_區間空白存成None():
    assert logic.applied_from_inputs("", "", []) == {"window": (None, None), "rules": []}
    assert logic.applied_from_inputs("2026-06-01", "2026-09-19", [("最大回撤", "低於", "-1")]) == {
        "window": ("2026-06-01", "2026-09-19"),
        "rules": [{"indicator": "最大回撤", "direction": "低於", "value": -1.0}],
    }
    assert logic.applied_from_inputs("20260601", "2026-09-19", []) is None


def _hld4(**kw):
    return logic.find_block(logic.build_page_model(**_scenario_args("full"), **kw), "HLD-4")


def test_S6a第四輪_HLD4摘要讀已套用那一組_不讀欄位當下值():
    """紅隊 M1：只改欄位、還沒按「套用」，摘要不變（與下面各塊的數字對得上）。"""
    base = _hld4()
    typed = _hld4(fields={"window_start": "2026-06-01", "window_end": "2026-09-19"})
    assert typed["summary_text"] == base["summary_text"]
    assert "2026-01-01" in base["summary_text"]
    applied = _hld4(
        fields={"window_start": "2026-06-01", "window_end": "2026-09-19"},
        applied_window=("2026-06-01", "2026-09-19"),
    )
    assert "2026-06-01" in applied["summary_text"] and "2026-01-01" not in applied["summary_text"]
    one_rule = _hld4(applied_rules=[{"indicator": "最大回撤", "direction": "低於", "value": -1.0}])
    assert "門檻 1 列" in one_rule["summary_text"]


def _apply_button(block):
    return next(b for b in block["buttons"] if b["_action_kind"] == "套用")


@pytest.mark.parametrize("fields, enabled, reason", [
    ({"window_start": "20260601", "window_end": "2026-09-19"}, False, logic.TEXT_BAD_RANGE),
    ({"window_start": "2026-06-01", "window_end": ""}, False, logic.TEXT_BAD_RANGE),
    ({"window_start": "2026-06-01", "window_end": "2026-09-19"}, True, ""),
    ({"window_start": "", "window_end": ""}, True, ""),
    ({"window_start": "2026-06-01", "window_end": "2026-09-19", "rule_rows": [("最大回撤", "低於", "x")]},
     False, logic.TEXT_RULES_BAD),   # S6a-2 第 4 項：~~原因留空~~ → 客戶核准字面
    ({"window_start": "2026-06-01", "window_end": "2026-09-19", "rule_rows": [("最大回撤", "低於", "-1")]},
     True, ""),
])
def test_S6a第四輪_套用能不能按_與回呼同一支判定(fields, enabled, reason):
    button = _apply_button(_hld4(fields=fields))
    assert button["_enabled"] is enabled and button["disabled_reason"] == reason
    rows = fields.get("rule_rows", [])
    appliable = logic.applied_from_inputs(fields["window_start"], fields["window_end"], rows) is not None
    assert appliable is enabled


def test_S6a第四輪_套用的門檻取代存過的門檻_正式版照轉():
    rules = [{"indicator": "最大回撤", "direction": "低於", "value": -1.0}]
    args = _scenario_args("full")
    demo = logic.build_page_model(**args, applied_rules=rules)
    got = _build(**args, today=TODAY, applied_rules=rules)
    base = logic.build_page_model(**args)
    assert [r["_fund_code"] for r in logic.find_block(demo, "HLD-1")["_rows"]] != [
        r["_fund_code"] for r in logic.find_block(base, "HLD-1")["_rows"]
    ]
    assert [r["_fund_code"] for r in logic.find_block(demo, "HLD-1")["_rows"]] == [
        r["_fund_code"] for r in logic.find_block(got, "HLD-1")["_rows"]
    ]


def test_S6a第四輪_HLD4兩枚按鈕並存那一句_logic改了字面而live沒跟上_raise():
    model = _demo("full")
    block = logic.find_block(model, "HLD-4")
    block["notes"] = [line for line in block["notes"] if line != logic.HLD4_APPLY_NOTE]
    with pytest.raises(ValueError, match="HLD-4 的 notes 沒有"):
        live.apply_live_notes(model, today=TODAY)


# ───────────────────────── S6a-2（客戶 2026-10-03 範圍裁示第 2～5 項） ─────────────────────────

# 每一檔都同時超出兩條門檻：最大回撤一定 ≤ 0，配息佔淨值比一定 ≥ 0（假資料三檔都有淨值與配息）。
_TWO_BREACH_RULES = [
    {"indicator": "最大回撤", "direction": "低於", "value": 1.0},
    {"indicator": "配息佔淨值比", "direction": "高於", "value": -1.0},
]


def test_S6a2_第2項_N1_結論燈數不重複的檔_偏離表列數不變():
    """持倉 3 檔，每一檔都超出兩條門檻：偏離表 6 列（照舊），燈寫「有 3 檔超出」（不是 4、不是 6）。"""
    args = _scenario_args("full")
    held = {h["fund_code"] for h in args["dataset"]["holding"]}
    for model in (
        logic.build_page_model(**args, applied_rules=_TWO_BREACH_RULES),
        _build(**args, today=TODAY, applied_rules=_TWO_BREACH_RULES),
    ):
        rows = logic.find_block(model, "HLD-1")["_rows"]
        light = logic.find_block(model, "HLD-0")
        assert len(rows) == 2 * len(held) == 6, rows          # 偏離表列數不變：一檔一條門檻一列
        assert {r["_fund_code"] for r in rows} == held
        assert light["_deviation_count"] == len(held) == 3
        assert f"有 {len(held)} 檔超出你設定的門檻" in light["text"], light["text"]


def test_S6a2_第2項_N1_一檔一列時燈數仍與列數相等():
    """只驗假資料 `full` 這一組的現況（燈數與列數剛好相等），不是相等條件的保證（同 `ACCEPTANCE.md` 9.3）。"""
    # ~~正控：每一檔只超出一條時，燈數照舊等於列數（既有 `test_結論燈的N等於HLD1的列數` 的情境）。~~
    # → 2026-10-03 更正（有意識的更正，不是漏刪）：「每一檔只超出一條時照舊相等」已被紅隊反例推翻
    #   （同一檔掛兩張保單時，每一檔只超出一條，列數仍是 2、燈數 1；見 `ACCEPTANCE.md` 9.2）。
    model = logic.build_page_model(**_scenario_args("full"))
    rows = logic.find_block(model, "HLD-1")["_rows"]
    assert len({r["_fund_code"] for r in rows}) == len(rows)
    assert logic.find_block(model, "HLD-0")["_deviation_count"] == len(rows)


@pytest.mark.parametrize("direction", ["大於", "小於", "等於", "低於 ", " 高於", "<", "高于", "低於高於"])
def test_S6a2_第3項_N2_方向不是高於低於_不可套用(direction):
    row = ("最大回撤", direction, "-1")
    assert logic.rules_from_inputs([row]) is None
    hld4 = _hld4(fields={"window_start": "2026-01-01", "window_end": "2026-09-19", "rule_rows": [row]})
    button = _apply_button(hld4)
    assert button["_enabled"] is False and button["disabled_reason"] == logic.TEXT_RULES_BAD


@pytest.mark.parametrize("direction", logic.RULE_DIRECTIONS)
def test_S6a2_第3項_高於低於照收(direction):
    assert logic.rules_from_inputs([("最大回撤", direction, "-1")]) == [
        {"indicator": "最大回撤", "direction": direction, "value": -1.0}
    ]


def test_S6a2_第3項_方向母體與_breaches認得的一致():
    assert set(logic.RULE_DIRECTIONS) == {"低於", "高於"}
    assert logic._breaches({"direction": "低於", "value": 0.0}, -1.0) is True
    assert logic._breaches({"direction": "高於", "value": 0.0}, 1.0) is True


def test_S6a2_第4項_停用原因句是客戶核准的字面():
    assert logic.TEXT_RULES_BAD == "門檻列未填齊，或格式不符"


@pytest.mark.parametrize("value", ["9" * 400, "-" + "9" * 400, "1" + "0" * 310 + ".5"])
def test_S6a2_第4項_數值超長變成inf_不可套用(value):
    row = ("最大回撤", "低於", value)
    assert logic.rules_from_inputs([row]) is None
    button = _apply_button(_hld4(fields={"window_start": "2026-01-01", "window_end": "2026-09-19", "rule_rows": [row]}))
    assert button["_enabled"] is False and button["disabled_reason"] == logic.TEXT_RULES_BAD


def test_S6a2_第4項_區間與門檻都不可套用時_寫區間那一句():
    button = _apply_button(_hld4(fields={
        "window_start": "20260101", "window_end": "2026-09-19", "rule_rows": [("最大回撤", "大於", "-1")],
    }))
    assert button["_enabled"] is False and button["disabled_reason"] == logic.TEXT_BAD_RANGE


def test_S6a2_第5項_門檻格子照欄位當下值的列數畫_首次照已套用門檻():
    first = _hld4()
    assert len(first["threshold_rows"]) == 2 and len(first["row_buttons"]) == 2
    rows = [("最大回撤", "低於", "-1"), ("", "", ""), ("配息佔淨值比", "高於", "6")]
    grown = _hld4(fields={"window_start": "2026-01-01", "window_end": "2026-09-19", "rule_rows": rows})
    assert [[f["_value"] for f in row] for row in grown["threshold_rows"]] == [list(r) for r in rows]
    assert len(grown["row_buttons"]) == 3
    assert "門檻 2 列" in grown["summary_text"]      # 摘要照舊讀已套用的門檻


# ───────────────────────── S6a-2 追加（客戶 2026-10-03）：刪「N 與列數相等」子句 ─────────────────────────

# `srcmiss`：CCCC 缺淨值（卡尾會出那一句）；這組門檻下只有 AAAA 同時超出兩條（最大回撤 -11.20%、配息佔淨值比 4.10%）。
_ONE_FUND_TWO_RULES = [
    {"indicator": "最大回撤", "direction": "低於", "value": -10.0},
    {"indicator": "配息佔淨值比", "direction": "低於", "value": 5.0},
]


def test_S6a2追加_HLD1卡尾那一句_只刪後半子句_前半句一字不改():
    assert logic.HLD1_SKIPPED_NOTE == "未列入的檔不進上表、也不進偏離筆數。"
    for model in (logic.build_page_model(**_scenario_args("srcmiss")),
                  _build(**_scenario_args("srcmiss"), today=TODAY)):
        tail = logic.find_block(model, "HLD-1")["tail_lines"]
        assert logic.HLD1_SKIPPED_NOTE in tail
        blob = "\n".join(logic.collect_ui_strings(model))
        assert "列數相等" not in blob and "燈上的 N" not in blob


def test_S6a2追加_一檔超出兩條門檻_燈寫1檔_表2列_畫面沒有列數相等():
    args = _scenario_args("srcmiss")
    for model in (logic.build_page_model(**args, applied_rules=_ONE_FUND_TWO_RULES),
                  _build(**args, today=TODAY, applied_rules=_ONE_FUND_TWO_RULES)):
        rows = logic.find_block(model, "HLD-1")["_rows"]
        light = logic.find_block(model, "HLD-0")
        assert [r["_fund_code"] for r in rows] == ["AAAA", "AAAA"]
        assert light["_deviation_count"] == 1
        assert "有 1 檔超出你設定的門檻" in light["text"]
        assert logic.HLD1_SKIPPED_NOTE in logic.find_block(model, "HLD-1")["tail_lines"]
        assert "列數相等" not in "\n".join(logic.collect_ui_strings(model))
