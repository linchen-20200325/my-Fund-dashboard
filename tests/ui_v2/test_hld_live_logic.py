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


def _build(*args, **kw):
    """正式模式的 `build_live_model`，帶上 `direct_policy_id`。"""
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
    """示範模型 → 去示意字尾 → 改欄名 → 停用兩類按鈕，必須恰好等於正式模型。
    正式模式若多改了任何一格（新增按鈕、改了別的字），這一條會紅。"""
    args = _scenario_args(name)
    open_fund = _first_holding(args["dataset"])
    demo = logic.build_page_model(**copy.deepcopy(args), open_fund=open_fund)
    expected = live.apply_live_notes(_scrub(demo))
    got = _build(**args, open_fund=open_fund)
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
