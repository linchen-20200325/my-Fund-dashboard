# -*- coding: utf-8 -*-
"""正式模式 Answer-first 四段重排的純函式（Phase 3 P1-④；`ui_v2/sections.py`）。

依據 `docs/v2/44_fund_ui_ssot.md` 第七節第三小節之八其一（`DEC-2026-10-17-07` 第 (a-1)～(a-4) 題）。
不需要 streamlit（fast lane）。畫面層的段落順序見 `tests/ui_v2/test_sections_page.py`。
"""

from __future__ import annotations

import copy

import pytest

from ui_v2 import sections
from ui_v2.alo import fixtures as alo_fixtures
from ui_v2.alo import logic as alo_logic
from ui_v2.exp import fixtures as exp_fixtures
from ui_v2.exp import logic as exp_logic
from ui_v2.hld import fixtures as hld_fixtures
from ui_v2.hld import logic as hld_logic
from ui_v2.mkt import fixtures as mkt_fixtures
from ui_v2.mkt import logic as mkt_logic


def _codes(model, layer, logic):
    return logic.codes_in_layer(model, layer)


# ───────────────────────── 鏡像常數對真身 ─────────────────────────


def test_鏡像常數逐字等於各頁logic():
    for logic in (mkt_logic, hld_logic, exp_logic):
        assert (logic.STATE_OK, logic.STATE_MISSING, logic.STATE_BIZ, logic.STATE_ERROR) == (
            sections.STATE_OK, sections.STATE_MISSING, sections.STATE_BIZ, sections.STATE_ERROR)
    assert sections.HLD_TEXT_NO_HOLDING == hld_logic.TEXT_NO_HOLDING
    assert sections.HLD_TEXT_NO_RULES == hld_logic.TEXT_NO_RULES
    assert sections.ALO_TEXT_OUT == alo_logic.TEXT_OUT
    assert sections._MKT_UNRANKED_ORDER == mkt_logic._UNRANKED_PAIR
    assert mkt_logic.STATE_UNRANKED is None   # 本檔以 None 認哨符狀態


# ───────────────────────── 層次歸屬 ─────────────────────────


def test_標的探索_EXP2到層3_EXP3到層4_預設收合_EXP1留在層2():
    model = exp_logic.build_page_model(**exp_fixtures.scenario("full"))
    assert _codes(model, 2, exp_logic) == ["EXP-1", "EXP-2", "EXP-3"]   # 示範模式（logic）照舊
    moved = sections.relayer(model, "exp")
    assert moved == ["EXP-2", "EXP-3"]
    assert _codes(model, 2, exp_logic) == ["EXP-1"]
    assert _codes(model, 3, exp_logic) == ["EXP-2", "EXP-4", "EXP-5"]
    assert _codes(model, 4, exp_logic) == ["EXP-3", "EXP-6", "EXP-7"]
    opened = [b["code"] for b in model["blocks"] if b["_default_open"]]
    assert opened == ["EXP-0", "EXP-1"]   # 結論燈 ＋ 該頁層 2 的核心卡


def test_資產配置_ALO1到層3_ALO3留在層2():
    model = alo_logic.build_page_model(alo_fixtures.scenario("full"))
    sections.relayer(model, "alo")
    assert _codes(model, 2, alo_logic) == ["ALO-2", "ALO-3"]
    assert _codes(model, 3, alo_logic) == ["ALO-1", "ALO-4", "ALO-5"]
    assert [b["code"] for b in model["blocks"] if b["_default_open"]] == ["ALO-0", "ALO-2", "ALO-3"]


def test_市場總覽與持倉體檢不改層():
    mkt = mkt_logic.build_page_model(mkt_fixtures.dataset_all_ok())
    before = [(b["code"], b["_layer"], b["_default_open"]) for b in mkt["blocks"]]
    assert sections.relayer(mkt, "mkt") == []
    assert [(b["code"], b["_layer"], b["_default_open"]) for b in mkt["blocks"]] == before
    hld = hld_logic.build_page_model(**hld_fixtures.scenario("full"))
    assert sections.relayer(hld, "hld") == []
    assert hld_logic.find_block(hld, "HLD-1")["_layer"] == 2          # 結構上照舊屬層 2（畫在 ③）
    assert hld_logic.find_block(hld, "HLD-1")["_default_open"] is True


def test_移層對象不見了_當場炸():
    model = alo_logic.build_page_model(alo_fixtures.scenario("full"))
    model["blocks"] = [b for b in model["blocks"] if b["code"] != "ALO-1"]
    with pytest.raises(KeyError):
        sections.relayer(model, "alo")


def test_relayer不碰判定():
    model = exp_logic.build_page_model(**exp_fixtures.scenario("full"))
    keep = [(b["code"], b.get("_state"), b.get("_tone"), b.get("summary_text")) for b in model["blocks"]]
    sections.relayer(model, "exp")
    assert [(b["code"], b.get("_state"), b.get("_tone"), b.get("summary_text")) for b in model["blocks"]] == keep


# ───────────────────────── ③需要注意 ─────────────────────────


def _mkt_with_states(states):
    model = mkt_logic.build_page_model(mkt_fixtures.dataset_all_ok())
    for code, state in zip(sections.MKT_CARD_CODES, states):
        mkt_logic.find_block(model, code)["_state"] = state
    return model


def test_市場總覽_三張卡皆ok_不列():
    assert sections.attention_items(_mkt_with_states(["ok"] * 3), "mkt") == []


def test_市場總覽_不是ok的卡合成一行資料面():
    items = sections.attention_items(_mkt_with_states(["ok", "資料未備", "系統錯誤"]), "mkt")
    assert len(items) == 1
    assert items[0]["text"] == "資料面：景氣位置卡 ◇ 資料未備；資金與匯率卡 ⛔ 取數失敗"
    biz = sections.attention_items(_mkt_with_states(["業務例外", "ok", "ok"]), "mkt")
    assert biz[0]["text"] == "資料面：風險情緒卡 ⬜ 不適用"


def test_市場總覽_哨符狀態兩個都寫():
    model = _mkt_with_states(["ok", "ok", "ok"])
    card = mkt_logic.find_block(model, "MKT-1")
    card["_state"] = None
    card["main_values"][0]["_state"] = "業務例外"
    card["main_values"][1]["_state"] = "資料未備"
    assert sections.attention_items(model, "mkt")[0]["text"] == "資料面：風險情緒卡 ◇ 資料未備／⬜ 不適用"


def test_市場總覽_真資料情境_局部缺():
    model = mkt_logic.build_page_model(mkt_fixtures.dataset_mkt1_one_key_missing())
    items = sections.attention_items(model, "mkt")
    assert items and items[0]["text"].startswith(sections.MKT_DATA_PREFIX)
    assert "風險情緒卡" in items[0]["text"]


def test_市場總覽_三張卡全ok的真資料_不寫沒有例外():
    model = mkt_logic.build_page_model(mkt_fixtures.dataset_all_ok())
    assert sections.attention_items(model, "mkt") == []


def _formal(logic, build):
    """在正式模式（不接示意字尾）的情境下跑 `build()`；各頁 logic 的模式開關只有 `_HINT_SUFFIX` 這一個。"""
    token = logic._HINT_SUFFIX.set("")
    try:
        return build()
    finally:
        logic._HINT_SUFFIX.reset(token)


def test_市場總覽_需要注意顏色讀MKT0的燈色_取數失敗時為紅():
    model = mkt_logic.build_page_model(mkt_fixtures.dataset_mkt1_fetch_failed())
    light = mkt_logic.find_block(model, "MKT-0")
    assert light["_tone"] == "紅"
    items = sections.attention_items(model, "mkt")
    assert items and "⛔ 取數失敗" in items[0]["text"]
    assert items[0]["_tone"] == "紅"
    light["_tone"] = "黃"   # 只跟著燈走，不另判
    assert sections.attention_items(model, "mkt")[0]["_tone"] == "黃"


def test_標的探索_讀EXP0的無法判定檔數():
    demo = exp_logic.build_page_model(**exp_fixtures.scenario("full"))
    assert "_undet_count" not in exp_logic.find_block(demo, "EXP-0")   # 示範模式不放這個鍵（模型逐位元組不變）
    with pytest.raises(KeyError):
        sections.attention_items(demo, "exp")                           # 直讀：缺鍵就炸，不以 0 代替
    model = exp_logic.build_page_model(**exp_fixtures.scenario("full"), demo_hint=False)
    assert exp_logic.find_block(model, "EXP-0")["_undet_count"] == 0
    assert sections.attention_items(model, "exp") == []
    exp_logic.find_block(model, "EXP-0")["_undet_count"] = 2
    items = sections.attention_items(model, "exp")
    assert [(i["symbol"], i["text"]) for i in items] == [("⬜", "2 檔無法判定：照列在結果清單中，不算符合、不排除")]


def test_EXP0_無法判定檔數_正式模式放寫進燈的那個數_示範模式不放():
    rules = [{"field": "ccy", "op": "等於", "value": "USD"}]
    args = dict(count=1, has_rules=True, rules=rules, read_states=["ok", "ok"])
    shown = _formal(exp_logic, lambda: exp_logic._build_exp0({}, undet_count=3, **args))
    assert shown["_undet_count"] == 3 and "另有 3 檔無法判定" in shown["text"]
    assert _formal(exp_logic, lambda: exp_logic._build_exp0({}, undet_count=0, **args))["_undet_count"] == 0
    no_rules = _formal(exp_logic, lambda: exp_logic._build_exp0({}, **dict(args, has_rules=False), undet_count=3))
    assert no_rules["_undet_count"] == 0 and "另有" not in no_rules["text"]
    assert "_undet_count" not in exp_logic._build_exp0({}, undet_count=3, **args)   # 示範模式


def test_標的探索_真的有無法判定檔的正式模型_需要注意列出同一個數():
    """自己構造一個有缺值欄位的選股池：條件作用在 `mgmt_fee_rate_pct`，其中一檔該欄為空 → 無法判定。"""
    params = dict(exp_fixtures.scenario("full"))
    dataset = copy.deepcopy(params.pop("dataset"))
    profiles = dataset["fund_profile"]
    profiles[0]["mgmt_fee_rate_pct"] = None
    rules = [{"field": "mgmt_fee_rate_pct", "op": "大於", "value": "-1"}]
    model = exp_logic.build_page_model(dataset, **dict(params, draft_rules=rules), demo_hint=False, tristate=True)
    count = exp_logic.find_block(model, "EXP-0")["_undet_count"]
    assert count >= 1
    assert sections.attention_items(model, "exp")[0]["text"].startswith(f"{count} 檔無法判定")


def test_資產配置_帶外類別逐列_帶內不列():
    model = alo_logic.build_page_model(alo_fixtures.scenario("full"))
    outside = [r["bucket_text"] for r in alo_logic.find_block(model, "ALO-2")["_rows"] if r["band_text"] == "外"]
    assert outside, "full 情境應有帶外類別（fixtures 標「超出容許帶」）"
    items = sections.attention_items(model, "alo")
    assert [i["text"] for i in items] == [f"{b} 超出容許帶" for b in outside]
    assert all(i["symbol"] == "◆" for i in items)
    for row in alo_logic.find_block(model, "ALO-2")["_rows"]:
        row["band_text"] = "內"
    assert sections.attention_items(model, "alo") == []


def test_持倉體檢_需要注意由HLD1整塊撐起_不另列項目():
    model = hld_logic.build_page_model(**hld_fixtures.scenario("full"))
    assert sections.attention_items(model, "hld") == []
    with pytest.raises(ValueError):
        sections.attention_items(model, "set")


def test_持倉體檢_偏離列加菱形_只改畫面字串():
    model = hld_logic.build_page_model(**hld_fixtures.scenario("full"))
    rows = hld_logic.find_block(model, "HLD-1")["_rows"]
    assert rows
    private = [{k: v for k, v in r.items() if k.startswith("_")} for r in copy.deepcopy(rows)]
    names = [r["fund_name"] for r in rows]
    assert sections.mark_hld1_rows(model) == len(rows)
    assert [r["fund_name"] for r in rows] == [f"◆ {n}" for n in names]
    assert [{k: v for k, v in r.items() if k.startswith("_")} for r in rows] == private
    assert sections.mark_hld1_rows(model) == 0   # 再套一次不疊


# ───────────────────────── 持倉體檢 ① 三個計數 ─────────────────────────


def _hld_formal(name, mutate=None, **extra):
    args = copy.deepcopy(hld_fixtures.scenario(name))
    if mutate:
        mutate(args["dataset"])
    return hld_logic.build_page_model(**args, demo_hint=False, **extra)


def _counts(model):
    """(n, m, j)，三個都是不重複基金代碼數（總管 2026-10-18 裁定同一個單位）。"""
    light = hld_logic.find_block(model, "HLD-0")
    codes = {group["_fund_code"] for group in hld_logic.find_block(model, "HLD-2")["fund_groups"]}
    return (len(codes), light["_deviation_count"], hld_logic.find_block(model, "HLD-1")["_unevaluated_count"])


def _second_policy(code):
    """同一檔基金再放進第二張保單（另一筆持倉，`policy_id` 不同 ⇒ 不會被同鍵加總併掉）。"""
    def mutate(dataset):
        row = dict(next(h for h in dataset["holding"] if h["fund_code"] == code))
        row["holding_id"] += "-2"
        row["policy_id"] = f"{row['policy_id']}-2"
        dataset["holding"].append(row)
    return mutate


def test_持倉體檢_同一檔分在兩張保單_n只算1_n減m減j等於已評估且未超門檻的檔數():
    model = _hld_formal("full", _second_policy("CCCC"))
    groups = hld_logic.find_block(model, "HLD-2")["fund_groups"]
    assert len(groups) == 4                                   # 四筆持倉（CCCC 兩張保單）
    deviated = {row["_fund_code"] for row in hld_logic.find_block(model, "HLD-1")["_rows"]}
    assert deviated == {"AAAA", "BBBB"}
    assert sections.hld_counts(model) == "持有 3 檔　◆ 需要注意 2 檔　⬜ 無法判定 0 檔"
    n, m, j = _counts(model)
    # 已評估且未超門檻：只有 CCCC（兩張保單各一筆，仍是一檔）。
    assert n - m - j == len({g["_fund_code"] for g in groups} - deviated) == 1


def _drop_nav(code):
    def mutate(dataset):
        dataset["nav"] = [row for row in dataset["nav"] if row["fund_code"] != code]
    return mutate


def _fund_nav_error(code):
    def mutate(dataset):
        dataset["fund_errors"] = {"nav": {code: "fetch_url returned None"}}
    return mutate


# (情境, 變動, 額外參數, 期望 (n, m, j))。j ＝ 沒有進入偏離評估的不重複檔數，不論成因（44 之八其一 (a-2) 第 1 條 2026-10-18 更正）。
_J_CASES = {
    "全齊": ("full", None, {}, (3, 2, 0)),
    "缺淨值": ("srcmiss", None, {}, (3, 2, 1)),
    "門檻指標不適用": ("bizexc", None, {}, (3, 0, 1)),
    "只有一筆淨值": ("onenav", None, {}, (3, 0, 3)),
    "同檔兩種狀態": ("tiedstate", None, {}, (3, 0, 3)),
    "淨值超過10日": ("full", _drop_nav("AAAA"), {"nav_not_ready_codes": frozenset({"AAAA"}), "nav_not_ready_days": 10},
                     (3, 1, 1)),
    "單檔取數失敗": ("full", _fund_nav_error("AAAA"), {}, (3, 1, 1)),
}


@pytest.mark.parametrize("case", sorted(_J_CASES))
def test_持倉體檢_j是沒有進入偏離評估的檔數_不論成因(case):
    name, mutate, extra, expected = _J_CASES[case]
    model = _hld_formal(name, mutate, **extra)
    n, m, j = _counts(model)
    assert (n, m, j) == expected
    assert n >= m + j                                        # 不變量：m 與 j 互斥，都是持倉的子集
    line = sections.hld_counts(model)
    assert line == f"持有 {n} 檔　◆ 需要注意 {m} 檔　⬜ 無法判定 {j} 檔"
    assert "○" not in line and "正常" not in line


def test_持倉體檢_j的舊定義只算缺淨值_會把不適用與取數失敗的檔藏起來():
    """回歸：舊定義 j ＝ `missing_nav_count`。「只有一筆淨值」這一組三檔都沒有評估，舊定義寫 0。"""
    model = _hld_formal("onenav")
    assert hld_logic.find_block(model, "HLD-1")["missing_nav_count"] == 0
    assert _counts(model)[2] == 3


@pytest.mark.parametrize("name", hld_fixtures.ALL_SCENARIO_NAMES)
def test_持倉體檢_不變量_全情境_n不小於m加j(name):
    n, m, j = _counts(_hld_formal(name))
    assert n >= m + j, (name, n, m, j)


def test_持倉體檢_未評估檔數只在正式模式放():
    demo = hld_logic.build_page_model(**hld_fixtures.scenario("full"))
    assert "_unevaluated_count" not in hld_logic.find_block(demo, "HLD-1")
    with pytest.raises(KeyError):
        sections.hld_counts(demo)


def test_持倉體檢_計數不成立時當場炸():
    model = _hld_formal("full")
    hld_logic.find_block(model, "HLD-1")["_unevaluated_count"] = 2   # 2 ＋ 2 > 3
    with pytest.raises(ValueError):
        sections.hld_counts(model)


@pytest.mark.parametrize("name", ["empty", "nothr", "fetchfail"])
def test_持倉體檢_空持倉_門檻未設_紅燈_不列計數(name):
    model = _hld_formal(name)
    light = hld_logic.find_block(model, "HLD-0")
    assert light["_tone"] == "紅" or light["text"] in (hld_logic.TEXT_NO_HOLDING, hld_logic.TEXT_NO_RULES), (
        name, light["_tone"], light["text"])
    assert sections.hld_counts(model) is None


# ───────────────────────── ALO-1 摘要 ─────────────────────────


def test_ALO1摘要只拼卡上已有的字():
    model = alo_logic.build_page_model(alo_fixtures.scenario("full"))
    block = alo_logic.find_block(model, "ALO-1")
    summary = sections.alo1_summary(block)
    assert summary.startswith(f"{len(block['_rows'])} 個類別")
    assert block["tolerance_lines"][0] in summary
    # 失敗佔位：只留狀態族（「此區塊暫時無法判定」一塊只寫一次，已在卡上；之七其二第 3 條）。
    block["placeholder"] = {"text": "⛔ 此區塊暫時無法判定", "_empty_kind": "系統錯誤"}
    assert sections.alo1_summary(block) == "⛔ 取數失敗"
    block["placeholder"] = {"text": "◇ 資料未備", "_empty_kind": "來源缺"}
    assert sections.alo1_summary(block) == "◇ 資料未備"


def test_ALO1摘要_目標比重缺值時寫出資料未備():
    model = alo_logic.build_page_model(alo_fixtures.scenario("full"))
    block = alo_logic.find_block(model, "ALO-1")
    assert "◇ 資料未備" not in sections.alo1_summary(block)
    block["_rows"][0]["_weight"] = None
    assert "◇ 資料未備" in sections.alo1_summary(block).split("；")


def test_開始試算入口_空狀態或取數失敗時帶出狀態族():
    model = alo_logic.build_page_model(alo_fixtures.scenario("full"))
    block = alo_logic.find_block(model, "ALO-3")
    assert sections.alo3_entry_title(block) == "開始試算"
    block["placeholder"] = {"text": "⛔ 此區塊暫時無法判定", "_empty_kind": "系統錯誤"}
    assert sections.alo3_entry_title(block) == "開始試算　—　⛔ 取數失敗"
    block["placeholder"] = {"text": "◇ 資料未備", "_empty_kind": "來源缺"}
    assert sections.alo3_entry_title(block) == "開始試算　—　◇ 資料未備"


@pytest.mark.parametrize("name", ["holdfail", "settingfail", "nobasis", "nofx"])
def test_開始試算入口_真情境的佔位都帶得出狀態族(name):
    model = alo_logic.build_page_model(alo_fixtures.scenario(name))
    block = alo_logic.find_block(model, "ALO-3")
    title = sections.alo3_entry_title(block)
    if block["placeholder"]:
        assert title.startswith("開始試算　—　") and len(title) > len("開始試算　—　")
    else:
        assert title == "開始試算"


def test_市場總覽的狀態字照MKT0燈點名卡片的同一組():
    for state, words in sections._MKT_STATE_WORDS.items():
        assert words.endswith(mkt_logic._STATE_IN_LIGHT_TEXT[state]), (state, words)
