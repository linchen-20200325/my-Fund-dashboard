# -*- coding: utf-8 -*-
"""持倉體檢（HLD）純邏輯測試。

測試先行：本檔先於 ui_v2/hld/logic.py 寫成並跑出紅燈。

引用範圍（客戶裁示）：只引 docs/v2/44_fund_ui_ssot.md（SSOT，已凍結）與
docs/v2/prototype/ui_prototype_hld.html（客戶已拍板的草稿）。
兩份對同一塊有不同說法以 44 為準（44 第零節自己訂明）。

本檔不 import streamlit，也不 import 任何舊 repo 模組。
"""

import math
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ui_v2.hld import fixtures, logic, theme  # noqa: E402


# ───────────────────────── 九塊與四層 ─────────────────────────


def test_本頁是九塊_HLD0到HLD8():
    """`44` 3.2 層次表：層 1 一塊／層 2 三塊／層 3 兩塊／層 4 三塊 ＝ 九塊。"""
    assert sorted(logic.BLOCK_TITLES) == [f"HLD-{i}" for i in range(9)]
    assert len(logic.BLOCK_TITLES) == 9


def test_各塊的層號逐塊對上SSOT層次表():
    assert logic.BLOCK_LAYERS["HLD-0"] == 1
    for code in ("HLD-1", "HLD-2", "HLD-3"):
        assert logic.BLOCK_LAYERS[code] == 2
    for code in ("HLD-4", "HLD-5"):
        assert logic.BLOCK_LAYERS[code] == 3
    for code in ("HLD-6", "HLD-7", "HLD-8"):
        assert logic.BLOCK_LAYERS[code] == 4


def test_塊名逐字引SSOT():
    assert logic.BLOCK_TITLES["HLD-0"] == "體檢結論燈"
    assert logic.BLOCK_TITLES["HLD-1"] == "偏離提示卡"
    assert logic.BLOCK_TITLES["HLD-2"] == "績效與風險卡"
    assert logic.BLOCK_TITLES["HLD-3"] == "配息與本金卡"
    assert logic.BLOCK_TITLES["HLD-4"] == "檢視區間與門檻輸入"
    assert logic.BLOCK_TITLES["HLD-5"] == "單檔展開"
    assert logic.BLOCK_TITLES["HLD-6"] == "淨值與配息序列"
    assert logic.BLOCK_TITLES["HLD-7"] == "計算軌跡"
    assert logic.BLOCK_TITLES["HLD-8"] == "最大回撤與本金類配息佔比"


def test_層一層二預設展開_層三層四預設收合():
    """`44` 第二節硬規則：初次載入展開的 ＝ 結論燈 ＋ 3 張核心卡。"""
    model = logic.build_page_model(fixtures.dataset_full())
    opened = [b["code"] for b in logic.all_blocks(model) if b["_default_open"]]
    assert opened == ["HLD-0", "HLD-1", "HLD-2", "HLD-3"]


# ───────────────────────── 四狀態（逐主值） ─────────────────────────


def test_四狀態的字面值就是SSOT卡片那四個():
    assert logic.STATE_OK == "ok"
    assert logic.STATE_MISSING == "資料未備"
    assert logic.STATE_BIZ == "業務例外"
    assert logic.STATE_ERROR == "系統錯誤"


def test_主值狀態_四態各一():
    assert logic.main_value_state() == logic.STATE_OK
    assert logic.main_value_state(missing=True) == logic.STATE_MISSING
    assert logic.main_value_state(na_reason="區間內無配息") == logic.STATE_BIZ
    assert logic.main_value_state(error="HTTP 503") == logic.STATE_ERROR


def test_主值狀態_系統錯誤蓋過其他三態():
    """失敗比缺資料更該說出來（§1 Fail Loud）。"""
    assert (
        logic.main_value_state(error="HTTP 503", missing=True, na_reason="X")
        == logic.STATE_ERROR
    )
    assert logic.main_value_state(missing=True, na_reason="X") == logic.STATE_MISSING


def test_顏色語意逐態對上SSOT卡片表():
    assert logic.tone_for_state(logic.STATE_OK) == "中性"
    assert logic.tone_for_state(logic.STATE_MISSING) == "灰"
    assert logic.tone_for_state(logic.STATE_BIZ) == "黃"
    assert logic.tone_for_state(logic.STATE_ERROR) == "紅"


# ───────────────────────── 逐塊四狀態 ─────────────────────────

_SCENARIO_BY_STATE = {
    logic.STATE_OK: "full",
    logic.STATE_MISSING: "srcmiss",
    logic.STATE_BIZ: "bizexc",
    logic.STATE_ERROR: "fetchfail",
}


def test_九塊在全部情境下都建得出來且狀態合法():
    """逐塊四狀態：九塊 × **全部情境**，每一塊都要給得出一個合法狀態值。

    ⚠️ **2026-09-24 擴寫（有意識的更正，不是漏刪；決策者：AI 總管；稽核抓到）**：
    ~~原本只跑六個情境（`full`/`srcmiss`/`bizexc`/`fetchfail`/`nothr`/`empty`）。~~
    **那正是 `KeyError: None` 溜出去的那道縫** —— 本組加了 `emptyfail` 與五個延伸情境，
    **卻沒有把這條合法性守衛一起擴**，於是新情境的塊狀態從來沒有被驗過。
    **舊表述在寫下當時涵蓋得完**（那時本頁就只有六個情境）；**被權衡掉的是它的前提**。

    ⛔ **同輪一併把 `_state` 的契約寫成可檢查的，而不是靠運氣**：
    `logic.py` 自己寫「`STATE_UNRANKED` **不是第五個狀態**」，但它確實會被寫進塊的 `_state`。
    `page.py` 剛好不讀塊的 `_state`（只讀 `_tone`），所以今天不會顯示成怪東西 ——
    **那是運氣，不是設計。** 這一條把它變成契約：
    `_state` 要嘛是四狀態之一，要嘛是 `STATE_UNRANKED`；**而且 `STATE_UNRANKED` 必須是掙來的**
    （那一塊真的同時有 `資料未備` 與 `業務例外` 的主值），不是漏接漏出來的 `None`；
    **無論哪一種，`_tone` 一律要是合法顏色**（那才是真正會被畫出去的東西）。
    """
    legal = {logic.STATE_OK, logic.STATE_MISSING, logic.STATE_BIZ, logic.STATE_ERROR}
    tones = {"中性", "灰", "黃", "紅"}
    unranked_seen = 0
    for name in _ALL_SCENARIOS:
        model = logic.build_page_model(**fixtures.scenario(name))
        assert [b["code"] for b in logic.all_blocks(model)] == [
            f"HLD-{i}" for i in range(9)
        ], name
        for block in logic.all_blocks(model):
            state = block["_state"]
            assert block["_tone"] in tones, (name, block["code"], block["_tone"])
            if state is logic.STATE_UNRANKED:
                # 掙來的：這一塊真的同時有那兩種主值，才准是 `STATE_UNRANKED`。
                value_states = {n["_state"] for n in logic.value_nodes(block)}
                if block["code"] == "HLD-0":
                    # 結論燈不自取數，它讀的是三塊的狀態值（`44` :488 來源欄）。
                    value_states = {
                        logic.find_block(model, c)["_state"]
                        for c in ("HLD-1", "HLD-2", "HLD-3")
                    }
                assert logic.STATE_UNRANKED in value_states or {
                    logic.STATE_MISSING, logic.STATE_BIZ
                } <= value_states, (name, block["code"], sorted(map(str, value_states)))
                unranked_seen += 1
            else:
                assert state in legal, (name, block["code"], state)
    # 反空掃留給下一條專門驗（本頁現行 12 情境不一定跑得出 `STATE_UNRANKED`）。
    assert unranked_seen >= 0


def test_A1回歸_同級主值不得讓整頁建不起來():
    """**2026-09-24 稽核必修 A1 的回歸測試。**

    `conclusion_light()` 裡那個 `worst_state(states)` 漏改，而 `states` 現在可以含
    `STATE_UNRANKED` ⇒ `build_page_model()` 直接 `KeyError: None`，**整頁畫不出來**。

    重現資料（純 fixtures 公開 API）：一檔區間內只有一筆淨值（→ `業務例外`）
    ＋ 一檔淨值來源整個抽掉（→ `資料未備`）＋ 門檻調到沒有任何一檔超出。
    **同一組資料在 `a7f8c1b` 上跑得起來**（HLD-0 為灰／`業務例外`）⇒ 這是第 6 件引進的。

    ⚠️ **拿掉修復就會紅**：把 `worst_state()` 裡的 `_band(s)` 改回 `_BAND[s]`，
    本條當場 `KeyError: None`。
    """
    dataset = fixtures._dataset(
        nav=[row for row in fixtures.navs() if row["fund_code"] != "CCCC"],
        window=fixtures.ONE_NAV_WINDOW,
        rules=fixtures._RULES_NOEXCEED,
    )
    model = logic.build_page_model(dataset)  # ⛔ 修復前這一行就炸了

    # 真的踩到那個同級情形（否則這一條會退化成「隨便一組資料建得起來」）。
    card = logic.find_block(model, "HLD-2")
    assert card["_state"] is logic.STATE_UNRANKED, card["_state"]
    assert {logic.STATE_MISSING, logic.STATE_BIZ} <= {
        n["_state"] for n in logic.value_nodes(card)
    }
    # 而且整頁九塊都畫得出顏色。
    for block in logic.all_blocks(model):
        assert block["_tone"] in {"中性", "灰", "黃", "紅"}, (block["code"], block["_tone"])


def test_全空情境_九塊一個數字也不出():
    model = logic.build_page_model(**fixtures.scenario("empty"))
    assert logic.numeric_nodes(model) == []


def test_取數失敗情境_配息卡進系統錯誤且印出訊息原文():
    model = logic.build_page_model(**fixtures.scenario("fetchfail"))
    card = logic.find_block(model, "HLD-3")
    assert card["_state"] == logic.STATE_ERROR
    joined = "".join(logic.collect_ui_strings(card))
    assert "⚠ 取數失敗" in joined
    assert fixtures.FETCH_FAIL_MESSAGE in joined


def test_業務例外情境_成立日晚於區間起點_不截短區間偷算():
    model = logic.build_page_model(**fixtures.scenario("bizexc"))
    card = logic.find_block(model, "HLD-2")
    group = logic.fund_group(card, "CCCC")
    assert [mv["_state"] for mv in group["main_values"]] == [
        logic.STATE_BIZ,
        logic.STATE_BIZ,
    ]
    for mv in group["main_values"]:
        assert mv["value_text"] == "⬜ 不適用：成立日晚於區間起點"
        assert mv["_has_number"] is False


# ───────────────────────── 逐主值：一缺一在 ─────────────────────────


def test_同一張卡上一個主值未備而另一個照出數():
    """`44` 5.1：四狀態掛在主值上，不掛在整張卡。"""
    model = logic.build_page_model(**fixtures.scenario("srcmiss"))
    card = logic.find_block(model, "HLD-3")
    group = logic.fund_group(card, "CCCC")
    states = [mv["_state"] for mv in group["main_values"]]
    assert states.count(logic.STATE_OK) == 1
    assert states.count(logic.STATE_MISSING) == 1
    ok_mv = [mv for mv in group["main_values"] if mv["_state"] == logic.STATE_OK][0]
    nd_mv = [mv for mv in group["main_values"] if mv["_state"] == logic.STATE_MISSING][0]
    assert ok_mv["_has_number"] is True
    assert nd_mv["value_text"] == "⬜ 資料未備"
    assert nd_mv["_has_number"] is False


def test_一缺一在時標題掛部分缺徽章():
    model = logic.build_page_model(**fixtures.scenario("srcmiss"))
    card = logic.find_block(model, "HLD-3")
    assert "部分缺" in [b["text"] for b in card["badges"]]


def test_兩個主值皆非ok時不掛部分缺():
    """`44` 5.1 改寫：兩個主值皆非 ok 時整塊進空狀態，全卡不出任何數字。"""
    model = logic.build_page_model(**fixtures.scenario("srcmiss"))
    card = logic.find_block(model, "HLD-2")
    group = logic.fund_group(card, "CCCC")
    assert all(mv["_state"] == logic.STATE_MISSING for mv in group["main_values"])
    assert all(mv["_has_number"] is False for mv in group["main_values"])


def test_每張核心卡最多兩個主值():
    """`44` 5.1 禁止欄：一張卡片最多承載兩個主值。"""
    for name in ("full", "srcmiss", "bizexc", "fetchfail", "nothr"):
        model = logic.build_page_model(**fixtures.scenario(name))
        for code in ("HLD-2", "HLD-3"):
            for group in logic.find_block(model, code).get("fund_groups", []):
                assert len(group["main_values"]) == 2, (name, code)


def test_最大回撤與本金類配息佔比不在核心卡上():
    """`H-02` 落地：第三個值移到層 4 的 HLD-8。"""
    model = logic.build_page_model(fixtures.dataset_full())
    for code in ("HLD-2", "HLD-3"):
        labels = [
            mv["label"]
            for group in logic.find_block(model, code).get("fund_groups", [])
            for mv in group["main_values"]
        ]
        assert "最大回撤" not in labels
        assert "本金類配息佔比" not in labels
    hld8 = logic.find_block(model, "HLD-8")
    assert hld8["column_labels"] == ["基金名", "幣別", "最大回撤", "本金類配息佔比"]


# ───────────────────────── HLD-1 列數 ＝ N ─────────────────────────


def test_偏離列依fund_code字面值排列_不排序成優先順序():
    model = logic.build_page_model(fixtures.dataset_full())
    rows = logic.find_block(model, "HLD-1")["_rows"]
    codes = [r["_fund_code"] for r in rows]
    assert codes == sorted(codes)


def test_偏離列的差額寫成帶正負號的數字():
    model = logic.build_page_model(fixtures.dataset_full())
    for row in logic.find_block(model, "HLD-1")["_rows"]:
        assert row["delta_text"][0] in "+-"


def test_缺淨值的檔不進本表不佔一列不計入列數():
    """客戶 `H-01` 裁示 ＋ `44` HLD-1 空狀態改寫。"""
    full = logic.build_page_model(**fixtures.scenario("full"))
    miss = logic.build_page_model(**fixtures.scenario("srcmiss"))
    full_rows = logic.find_block(full, "HLD-1")["_rows"]
    miss_rows = logic.find_block(miss, "HLD-1")["_rows"]
    assert "CCCC" not in [r["_fund_code"] for r in miss_rows]
    assert logic.find_block(miss, "HLD-1")["missing_nav_count"] == 1
    assert len(miss_rows) == len(full_rows)  # CCCC 在 full 也沒超出門檻


def test_缺淨值的檔在卡尾另寫一行_不另開區塊():
    miss = logic.build_page_model(**fixtures.scenario("srcmiss"))
    card = logic.find_block(miss, "HLD-1")
    assert any("另有 1 檔缺淨值，未列入" in line for line in card["tail_lines"])


def test_結論燈的N等於HLD1的列數():
    """`44` HLD-0 判準（2026-09-22 改寫）：N 與 HLD-1 列出的列數相等。"""
    for name in ("full", "srcmiss"):
        model = logic.build_page_model(**fixtures.scenario(name))
        light = logic.find_block(model, "HLD-0")
        rows = logic.find_block(model, "HLD-1")["_rows"]
        assert light["_deviation_count"] == len(rows), name
        assert f"有 {len(rows)} 檔超出你設定的門檻" in light["text"], name


def test_把門檻調到沒有一檔超出_燈轉灰且文案為無偏離項():
    model = logic.build_page_model(**fixtures.scenario("noexceed"))
    light = logic.find_block(model, "HLD-0")
    assert light["_tone"] == "灰"
    assert light["text"] == "無偏離項"
    assert logic.find_block(model, "HLD-1")["_rows"] == []


# ───────────────────────── 結論燈 ─────────────────────────


def test_燈的六種情境逐一():
    expect = {
        "full": ("黃", "有 2 檔超出你設定的門檻"),
        "srcmiss": ("黃", "有 2 檔超出你設定的門檻"),
        "noexceed": ("灰", "無偏離項"),
        "nothr": ("灰", "尚未設定門檻"),
        "empty": ("灰", "尚未建立任何持倉"),
    }
    for name, (tone, text) in expect.items():
        light = logic.find_block(
            logic.build_page_model(**fixtures.scenario(name)), "HLD-0"
        )
        assert light["_tone"] == tone, name
        assert text in light["text"], name


def test_任一塊為系統錯誤時燈為紅():
    light = logic.find_block(
        logic.build_page_model(**fixtures.scenario("fetchfail")), "HLD-0"
    )
    assert light["_tone"] == "紅"


def test_燈不自取數_只讀三塊的狀態值與HLD1的偏離筆數():
    """`44` HLD-0 來源欄逐字。"""
    model = logic.build_page_model(fixtures.dataset_full())
    light = logic.find_block(model, "HLD-0")
    assert light["_reads"] == ("HLD-1", "HLD-2", "HLD-3")
    assert light["main_values"] == []


def test_燈的三種各有自己的圖示與狀態字_不靠顏色單獨辨識():
    """客戶 2026-09-22 設計引導：狀態色一律配圖示＋文字。"""
    seen = {}
    for name in ("full", "noexceed", "fetchfail"):
        light = logic.find_block(
            logic.build_page_model(**fixtures.scenario(name)), "HLD-0"
        )
        seen[light["_tone"]] = (light["glyph"], light["state_word"])
    assert seen["灰"] == ("⬜", "狀態：中性")
    assert seen["黃"] == ("⚠", "狀態：要多看一眼")
    assert seen["紅"] == ("✖", "狀態：取數失敗")
    assert len({g for g, _ in seen.values()}) == 3
    assert len({w for _, w in seen.values()}) == 3


def test_持倉表為空時掛一枚導覽按鈕與那一行唯讀說明():
    model = logic.build_page_model(**fixtures.scenario("empty"))
    light = logic.find_block(model, "HLD-0")
    buttons = light["buttons"]
    assert [b["label"] for b in buttons] == ["前往 Sheets 維護持倉"]
    assert buttons[0]["_action_kind"] == "導覽"
    assert buttons[0]["_writes"] == set()
    assert "持倉資料在 Sheets 維護，本儀表板唯讀" in light["detail_lines"]


# ───────────────────────── 斷點 ─────────────────────────


def test_斷點四個邊界值():
    """`44` 2.1 客戶最終版：≤768 單欄／769-1279 兩欄／≥1280 三欄。"""
    assert logic.columns_for_width(768) == 1
    assert logic.columns_for_width(769) == 2
    assert logic.columns_for_width(1279) == 2
    assert logic.columns_for_width(1280) == 3


def test_斷點六個寬度的層二並排數():
    """`44` 2.1 節判準：1280／1279／769／768／375／374 → 三二二一一一。"""
    got = [logic.layer_columns(2, w) for w in (1280, 1279, 769, 768, 375, 374)]
    assert got == [3, 2, 2, 1, 1, 1]


def test_層一與層四一律單欄滿寬():
    for width in (374, 768, 769, 1279, 1280, 1920):
        assert logic.layer_columns(1, width) == 1
        assert logic.layer_columns(4, width) == 1


def test_層三最多兩塊並排_第三欄空著():
    """`44` 2.1：五頁的層 3 各只有兩塊。"""
    assert logic.layer_columns(3, 1280) == 2
    assert logic.layer_columns(3, 1279) == 2
    assert logic.layer_columns(3, 768) == 1


def test_窄於375不另立第四種排法():
    assert logic.columns_for_width(374) == logic.columns_for_width(375) == 1


# ───────────────────────── 套用與存檔 ─────────────────────────


def test_套用重算的是六塊():
    """`44` HLD-4 二次擴寫：HLD-1／2／3／5／7／8。"""
    assert logic.APPLY_RECALC_BLOCKS == (
        "HLD-1",
        "HLD-2",
        "HLD-3",
        "HLD-5",
        "HLD-7",
        "HLD-8",
    )
    assert logic.blocks_recalculated_by("套用") == logic.APPLY_RECALC_BLOCKS


def test_存檔不重算任何一塊():
    assert logic.blocks_recalculated_by("存檔") == ()


def test_存檔只寫user_setting_不寫四張表():
    assert logic.SAVE_WRITES == {"user_setting"}
    for table in ("holding", "policy", "nav", "dividend"):
        assert table not in logic.SAVE_WRITES


def test_沒有任何按鈕寫入四張唯讀表():
    """`44` 5.3 禁止欄 ＋ 元件判準。"""
    readonly = {"holding", "policy", "nav", "dividend"}
    for name in ("full", "srcmiss", "bizexc", "fetchfail", "nothr", "empty"):
        model = logic.build_page_model(**fixtures.scenario(name))
        for button in logic.collect_buttons(model):
            assert button["_action_kind"] in logic.BUTTON_KINDS, button["label"]
            assert not (button["_writes"] & readonly), button["label"]


def test_按鈕八類之外沒有第九類():
    assert logic.BUTTON_KINDS == (
        "取數",
        "套用",
        "展開",
        "匯出",
        "新增列",
        "清除",
        "導覽",
        "存檔",
    )


def test_套用只讀輸入不改輸入():
    assert logic.button_writes("套用") == set()


def test_區間兩欄皆空時存檔停用且寫出原因_停用不隱藏():
    model = logic.build_page_model(**fixtures.scenario("empty"))
    save = logic.find_button(model, "存檔")
    assert save["_enabled"] is False
    assert save["_visible"] is True
    assert save["disabled_reason"] == "區間兩個欄位皆未填"


def test_起日晚於迄日_不套用也不存檔且寫出那一句():
    model = logic.build_page_model(**fixtures.scenario("badrange"))
    block = logic.find_block(model, "HLD-4")
    assert "起日不晚於迄日" in block["detail_lines"]
    assert logic.find_button(model, "存檔")["_enabled"] is False
    assert block["_applied"] is False


def test_起日晚於迄日時六塊的主值不變():
    """`44` HLD-4 空狀態＋判準：六塊的主值與套用前逐字相同。"""
    before = logic.build_page_model(**fixtures.scenario("full"))
    after = logic.build_page_model(**fixtures.scenario("full_then_badrange"))
    for code in logic.APPLY_RECALC_BLOCKS:
        assert logic.block_value_strings(
            logic.find_block(before, code)
        ) == logic.block_value_strings(logic.find_block(after, code)), code


def test_換一段區間按套用_六塊跟著重算():
    a = logic.build_page_model(**fixtures.scenario("full"))
    b = logic.build_page_model(**fixtures.scenario("other_window"))
    changed = [
        code
        for code in logic.APPLY_RECALC_BLOCKS
        if logic.block_value_strings(logic.find_block(a, code))
        != logic.block_value_strings(logic.find_block(b, code))
    ]
    assert "HLD-8" in changed
    assert "HLD-2" in changed


def test_首次開啟四個欄位沒有任何預設值():
    """`44` HLD-4 判準第一句 ＋ G3†。"""
    model = logic.build_page_model(**fixtures.scenario("empty"))
    for field in logic.collect_inputs(model):
        assert field["_default"] is None, field["name"]


def test_全頁沒有任何輸入欄帶非空的預設值():
    """`44` 1.1 節判準後半句，六種情境都掃。"""
    for name in ("full", "srcmiss", "bizexc", "fetchfail", "nothr", "empty"):
        model = logic.build_page_model(**fixtures.scenario(name))
        for field in logic.collect_inputs(model):
            assert field["_default"] is None, (name, field["name"])


# ───────────────────────── HLD-7 計算軌跡 ─────────────────────────


def test_計算軌跡四欄():
    model = logic.build_page_model(fixtures.dataset_full())
    assert logic.find_block(model, "HLD-7")["column_labels"] == [
        "指標名",
        "取用的輸入筆數與首末日期",
        "算式的文字寫法",
        "輸出值",
    ]


def test_計算軌跡接住HLD8的兩個指標():
    """`44` HLD-7 擴寫：最大回撤與本金類配息佔比兩個指標各自佔一列。"""
    model = logic.build_page_model(fixtures.dataset_full())
    rows = logic.find_block(model, "HLD-7")["_rows"]
    names = {r["_indicator"] for r in rows}
    assert "最大回撤" in names
    assert "本金類配息佔比" in names
    owners = {r["_owner_code"] for r in rows if r["_indicator"] == "最大回撤"}
    assert owners == {"HLD-8"}


def test_計算軌跡的輸出值與所在那一塊上的字串逐字相同():
    """`44` HLD-7 判準第一句：本檔最承重的一條。"""
    for name in ("full", "srcmiss", "bizexc", "fetchfail", "nothr"):
        model = logic.build_page_model(**fixtures.scenario(name))
        for row in logic.find_block(model, "HLD-7")["_rows"]:
            shown = logic.value_shown_in_block(
                model, row["_owner_code"], row["_fund_code"], row["_indicator"]
            )
            assert row["output_text"] == shown, (name, row["_indicator"], row["_fund_code"])


def test_算式以文字寫出_不寫任何實作語言的語法():
    model = logic.build_page_model(fixtures.dataset_full())
    for row in logic.find_block(model, "HLD-7")["_rows"]:
        for token in ("(", ")", "[", "]", "def ", "lambda", "**", "/ ", "sum("):
            assert token not in row["formula_text"], row["formula_text"]


def test_區間縮到只含一筆淨值_兩個主值與最大回撤皆不適用且軌跡跟著同一句():
    """`44` HLD-7 判準第三句。"""
    model = logic.build_page_model(**fixtures.scenario("onenav"))
    card = logic.find_block(model, "HLD-2")
    for group in card["fund_groups"]:
        for mv in group["main_values"]:
            assert mv["value_text"] == "⬜ 不適用：區間內淨值筆數不足"
    hld8 = logic.find_block(model, "HLD-8")
    for row in hld8["_rows"]:
        assert row["drawdown"]["text"] == "⬜ 不適用：區間內淨值筆數不足"
    for row in logic.find_block(model, "HLD-7")["_rows"]:
        if row["_indicator"] in ("區間報酬率", "期間波動", "最大回撤"):
            assert row["output_text"] == "⬜ 不適用：區間內淨值筆數不足"
            assert row["inputs_text"] != ""


def test_四塊沒有一塊出數時計算軌跡進來源缺():
    model = logic.build_page_model(**fixtures.scenario("empty"))
    block = logic.find_block(model, "HLD-7")
    assert block["_state"] == logic.STATE_MISSING
    assert block["_rows"] == []


# ───────────────────────── HLD-8 ─────────────────────────


def test_HLD8兩個值逐值判狀態():
    """`44` HLD-8 判準：unknown → 該欄不適用而同一列的最大回撤照樣出數。"""
    model = logic.build_page_model(fixtures.dataset_full())
    row = logic.find_row(logic.find_block(model, "HLD-8"), "CCCC")
    assert row["principal"]["text"] == "⬜ 不適用：配息類別未知"
    assert row["drawdown"]["_has_number"] is True


def test_HLD8未知筆數寫在表下():
    model = logic.build_page_model(fixtures.dataset_full())
    block = logic.find_block(model, "HLD-8")
    assert any("配息類別未知" in line and "筆" in line for line in block["detail_lines"])


def test_HLD8缺淨值時最大回撤未備而本金類佔比照出數():
    model = logic.build_page_model(**fixtures.scenario("srcmiss"))
    row = logic.find_row(logic.find_block(model, "HLD-8"), "CCCC")
    assert row["drawdown"]["text"] == "⬜ 資料未備"
    assert row["principal"]["_has_number"] is True


def test_HLD8列依fund_code字面值排列():
    model = logic.build_page_model(fixtures.dataset_full())
    codes = [r["_fund_code"] for r in logic.find_block(model, "HLD-8")["_rows"]]
    assert codes == sorted(codes)


# ───────────────────────── HLD-5 / HLD-6 ─────────────────────────


def test_同時最多展開一檔_而且初次載入一檔也不展開():
    """⚠️ 本條原本斷言初次載入**剛好一檔展開**，那正是被 `44` 禁掉的行為 ——
    `44` :119／:128「初次載入展開的 ＝ 結論燈 ＋ 3 張核心卡」、
    §5.4 禁止欄「**展開區不自動展開**」。舊斷言把違憲釘成了規格。
    現行：初次載入 0 檔；點開一檔才 1 檔；**任何時候都不超過一檔**。
    """
    model = logic.build_page_model(fixtures.dataset_full())
    items = logic.find_block(model, "HLD-5")["_items"]
    assert sum(1 for item in items if item["_open"]) == 0

    picked = logic.build_page_model(fixtures.dataset_full(), open_fund="BBBB")
    opened = [i for i in logic.find_block(picked, "HLD-5")["_items"] if i["_open"]]
    assert len(opened) == 1 and opened[0]["_fund_code"] == "BBBB"


def test_DIRECT保單欄位顯示直接持有而不是空白():
    model = logic.build_page_model(fixtures.dataset_full())
    item = logic.find_row(logic.find_block(model, "HLD-5"), "AAAA")
    assert dict(item["_fields"])["保單"] == "直接持有"


def test_該檔在區間內無淨值時折線區來源缺而長條照畫():
    model = logic.build_page_model(**fixtures.scenario("srcmiss"))
    item = logic.find_row(logic.find_block(model, "HLD-5"), "CCCC")
    assert "⬜ 資料未備" in item["nav_plot_text"]
    assert item["div_plot_text"] != ""


def test_HLD6推估列掛推估徽章而相鄰列沒有():
    model = logic.build_page_model(fixtures.dataset_full())
    rows = logic.find_block(model, "HLD-6")["nav_rows"]
    flags = [r["_estimated_badge"] for r in rows]
    assert "推估" in flags
    assert "" in flags


def test_HLD6可空的只有入帳日一欄_空時顯示方框():
    model = logic.build_page_model(fixtures.dataset_full())
    rows = logic.find_block(model, "HLD-6")["div_rows"]
    assert any(r["pay_date"] == "⬜" for r in rows)
    for row in rows:
        for key, value in row.items():
            if key.startswith("_") or key == "pay_date":
                continue
            assert value != "⬜", key


def test_HLD6表不做任何補值_缺的日期不出現在表上():
    dataset = fixtures.dataset_full()
    nav_dates = {(r["fund_code"], r["nav_date"]) for r in dataset["nav"]}
    model = logic.build_page_model(dataset)
    shown = {
        (r["_fund_code"], r["nav_date"])
        for r in logic.find_block(model, "HLD-6")["nav_rows"]
    }
    assert shown == nav_dates


# ───────────────────────── 空狀態文案逐字 ─────────────────────────


def test_空狀態文案模板逐字():
    """`44` 5.5 那張表的四個模板。"""
    assert logic.empty_source_text(["holding"]) == "⬜ 資料未備：holding 尚無資料"
    assert logic.not_applicable_text("區間內無配息") == "⬜ 不適用：區間內無配息"
    assert logic.fetch_failed_text("HTTP 503") == "⚠ 取數失敗：HTTP 503"
    assert logic.partial_range_text("2026-03-01", "2026-04-01") == "缺 2026-03-01 至 2026-04-01"


def test_全頁用到的空狀態文案逐字落在SSOT寫下的那幾句之內():
    expected = {
        "⬜ 資料未備",
        "⬜ 不適用：尚未設定區間",
        "⬜ 不適用：尚未設定門檻",
        "⬜ 不適用：區間內淨值筆數不足",
        "⬜ 不適用：成立日晚於區間起點",
        "⬜ 不適用：區間內無配息",
        "⬜ 不適用：配息類別未知",
        "⚠ 取數失敗",
    }
    seen = set()
    for name in ("full", "srcmiss", "bizexc", "fetchfail", "nothr", "empty", "onenav"):
        model = logic.build_page_model(**fixtures.scenario(name))
        seen |= logic.empty_state_texts(model)
    assert seen <= expected, seen - expected
    assert seen >= expected - {"⬜ 不適用：區間內無配息"}


def test_空狀態不顯示0也不顯示上一期的值():
    """`44` 5.5 禁止欄。"""
    for name in ("empty", "nothr", "onenav"):
        model = logic.build_page_model(**fixtures.scenario(name))
        for node in logic.non_ok_value_nodes(model):
            assert node["_has_number"] is False
            assert node["text"].lstrip("+-")[:1] not in "0123456789"


def test_空狀態不整塊隱藏_塊的標題留著():
    model = logic.build_page_model(**fixtures.scenario("empty"))
    for block in logic.all_blocks(model):
        assert block["title"] == logic.BLOCK_TITLES[block["code"]]


# ───────────────────────── 徽章 ─────────────────────────


def test_狀態徽章的七個字面值():
    assert logic.STATUS_BADGE_LITERALS == (
        "資料未備",
        "不適用",
        "取數失敗",
        "推估",
        "修正過",
        "部分缺",
        "未定義",
    )


def test_全頁狀態徽章不落在那七個之外():
    """`44` 5.2 元件判準（2026-09-21 改寫後的版本）。"""
    for name in ("full", "srcmiss", "bizexc", "fetchfail", "nothr", "empty"):
        model = logic.build_page_model(**fixtures.scenario(name))
        texts = {
            b["text"] for b in logic.collect_badges(model) if b["_kind"] == "狀態"
        }
        assert texts <= set(logic.STATUS_BADGE_LITERALS), (name, texts)


def test_紅線徽章只出現在說明區_不出現在任何數值旁():
    for name in ("full", "empty"):
        model = logic.build_page_model(**fixtures.scenario(name))
        marks = [b for b in logic.collect_badges(model) if b["_kind"] == "紅線"]
        assert marks
        for badge in marks:
            assert badge["text"] in ("G1†", "G2†", "G3†")
            assert badge["_slot"] == "說明區"


def test_本頁的紅線落點是G2與G3():
    """`44` 1.3 表（2026-09-21 更正後）：持倉體檢 → G2† G3†。"""
    model = logic.build_page_model(fixtures.dataset_full())
    marks = {b["text"] for b in logic.collect_badges(model) if b["_kind"] == "紅線"}
    assert marks == {"G2†", "G3†"}


def test_來源徽章中性不著色():
    model = logic.build_page_model(fixtures.dataset_full())
    for badge in logic.collect_badges(model):
        if badge["_kind"] == "來源":
            assert badge["_tone"] == "中性"


# ───────────────────────── 紅線字表掃描 ─────────────────────────


def test_紅線字表_方向詞與箭頭一個也對不上():
    """`44` 1.2 節判準。掃的是渲染用的全部文案字串。"""
    for name in ("full", "srcmiss", "bizexc", "fetchfail", "nothr", "empty", "onenav"):
        model = logic.build_page_model(**fixtures.scenario(name))
        assert logic.scan_forbidden(logic.collect_ui_strings(model)) == {}, name


def test_禁令字表本身不是畫面文案():
    """負控：字表住在 logic 的常數裡，不住在模型裡；掃描掃的是模型。"""
    model = logic.build_page_model(fixtures.dataset_full())
    strings = logic.collect_ui_strings(model)
    for word in logic.FORBIDDEN_DIRECTION_WORDS:
        assert word not in strings


def test_按鈕標籤零禁詞():
    """`44` 1.1 節判準前半句。"""
    for name in ("full", "srcmiss", "bizexc", "fetchfail", "nothr", "empty"):
        model = logic.build_page_model(**fixtures.scenario(name))
        for button in logic.collect_buttons(model):
            for word in logic.FORBIDDEN_BUTTON_WORDS:
                assert word not in button["label"], (name, button["label"])


def test_持有起始日不寫成首次買進日():
    """`44` 4.1：`opened_on` 的畫面標籤一律用「持有起始日」。"""
    model = logic.build_page_model(fixtures.dataset_full())
    joined = "".join(logic.collect_ui_strings(model))
    assert "持有起始日" in joined
    assert "買進" not in joined


def test_本頁不輸出目標價與預期報酬():
    """`44` 1.2 禁輸出。"""
    model = logic.build_page_model(fixtures.dataset_full())
    joined = "".join(logic.collect_ui_strings(model))
    for word in ("目標價", "預期報酬", "最佳配置", "再平衡"):
        assert word not in joined


# ───────────────────────── 多幣別 ─────────────────────────


def test_每一個出數的值都帶自己的單一幣別():
    """客戶 2026-09-22 設計引導第三條。"""
    for name in ("full", "srcmiss", "bizexc", "nothr"):
        model = logic.build_page_model(**fixtures.scenario(name))
        for node in logic.numeric_nodes(model):
            assert isinstance(node["_ccy"], str), (name, node)
            assert node["_ccy"] in fixtures.CURRENCIES, (name, node["_ccy"])


def test_同卡不出現跨幣別的合計平均或比值():
    for name in ("full", "srcmiss", "bizexc", "nothr"):
        model = logic.build_page_model(**fixtures.scenario(name))
        assert logic.cross_currency_nodes(model) == [], name


def test_兩檔不同幣別放進同一張卡_卡上出現兩個幣別字面值():
    """`44` HLD-2 判準後半句。"""
    model = logic.build_page_model(fixtures.dataset_full())
    for code in ("HLD-2", "HLD-3"):
        card = logic.find_block(model, code)
        joined = "".join(logic.collect_ui_strings(card))
        assert "USD" in joined and "EUR" in joined
        for group in card["fund_groups"]:
            assert group["_ccy"] in group["head_text"]


def test_HLD8逐檔仍寫出幣別字面值():
    model = logic.build_page_model(fixtures.dataset_full())
    for row in logic.find_block(model, "HLD-8")["_rows"]:
        assert row["ccy_text"].startswith(row["_ccy"])


# ───────────────────────── 算式 ─────────────────────────


def test_區間報酬率就是首末兩筆的比再減一():
    navs = [10.0, 10.5, 10.2, 11.0]
    assert math.isclose(logic.return_pct(navs), 10.0, rel_tol=1e-9)


def test_最大回撤是區間內淨值除以之前最高再取最小():
    navs = [10.0, 12.0, 9.0, 11.0]
    assert math.isclose(logic.drawdown_pct(navs), -25.0, rel_tol=1e-9)


def test_期間波動用交易日252年化():
    navs = [10.0, 10.1, 10.0, 10.1, 10.0]
    assert logic.vol_pct(navs) > 0
    assert logic.TRADING_DAYS_PER_YEAR == 252


def test_淨值筆數少於兩筆算不出來():
    assert logic.return_pct([10.0]) is None
    assert logic.drawdown_pct([10.0]) is None
    assert logic.vol_pct([10.0]) is None


def test_浮點比較不用等號():
    """§4.3：本檔的算式測試一律用容差比較。"""
    source = pathlib.Path(logic.__file__).read_text(encoding="utf-8")
    assert "math.isclose" in source or "== 0.0" not in source


# ───────────────────────── 隔離 ─────────────────────────


def test_logic零streamlit與零舊repo_import():
    source = pathlib.Path(logic.__file__).read_text(encoding="utf-8")
    for banned in (
        "import streamlit",
        "from ui.",
        "from services.",
        "from repositories.",
        "from shared.",
        "from infra.",
        "import fund_fetcher",
    ):
        assert banned not in source


def test_fixtures零網路字表():
    for module in (logic, fixtures, theme):
        source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        for banned in (
            "requests",
            "httpx",
            "urllib",
            "yfinance",
            "gspread",
            "feedparser",
            "socket",
            "subprocess",
            "open_by_key",
        ):
            assert banned not in source, (module.__name__, banned)


# ───────────────────────── 資料表欄位 ─────────────────────────


def test_fixtures的欄位逐字照SSOT第四節那幾張表():
    dataset = fixtures.dataset_full()
    assert set(dataset["holding"][0]) == {
        "holding_id",
        "policy_id",
        "fund_code",
        "fund_name",
        "ccy",
        "units_shares",
        "cost_orig_ccy",
        "cost_twd",
        "opened_on",
        "bucket",
        "last_synced_at",
    }
    assert set(dataset["nav"][0]) == {
        "fund_code",
        "nav_date",
        "nav_orig_ccy",
        "ccy",
        "source_tier",
        "is_estimated",
        "fetched_at",
    }
    assert set(dataset["dividend"][0]) == {
        "fund_code",
        "ex_date",
        "pay_date",
        "div_per_unit_orig_ccy",
        "ccy",
        "div_kind",
        "fetched_at",
    }
    assert set(dataset["fund_profile"][0]) == {
        "fund_code",
        "fund_name",
        "ccy",
        "inception_on",
        "dividend_policy",
        "mgmt_fee_rate_pct",
        "fetched_at",
    }
    assert set(dataset["policy"][0]) == {
        "policy_id",
        "policy_name",
        "issuer",
        "ccy",
        "premium_paid_twd",
        "fee_rate_pct",
        "opened_on",
        "status",
    }


def test_逐檔帶ccy():
    dataset = fixtures.dataset_full()
    for table in ("holding", "nav", "dividend", "fund_profile"):
        for row in dataset[table]:
            assert row["ccy"] in fixtures.CURRENCIES, (table, row)


def test_nav為正且日期不重複():
    dataset = fixtures.dataset_full()
    keys = [(r["fund_code"], r["nav_date"]) for r in dataset["nav"]]
    assert len(keys) == len(set(keys))
    assert all(r["nav_orig_ccy"] > 0 for r in dataset["nav"])


def test_配息不為負且除息日不重複():
    dataset = fixtures.dataset_full()
    keys = [(r["fund_code"], r["ex_date"]) for r in dataset["dividend"]]
    assert len(keys) == len(set(keys))
    assert all(r["div_per_unit_orig_ccy"] >= 0 for r in dataset["dividend"])


def test_user_setting沒有任何內建值():
    """`44` 4.5 `user_setting`：本表不預先寫入任何一列有值的設定（G3†）。"""
    empty = fixtures.scenario("empty")["dataset"]
    assert all(r["setting_value"] in (None, "") for r in empty["user_setting"])
    assert all(r["updated_at"] in (None, "") for r in empty["user_setting"])


# ───────────────────────── WCAG ─────────────────────────


def test_對比公式對得上草稿published的數():
    assert math.isclose(theme.contrast_ratio("#8b949e", "#161b22"), 5.62, abs_tol=0.01)
    assert math.isclose(theme.contrast_ratio("#e3b341", "#241d07"), 8.61, abs_tol=0.01)
    assert math.isclose(theme.contrast_ratio("#ff4b4b", "#2b1114"), 5.33, abs_tol=0.01)
    assert math.isclose(theme.contrast_ratio("#7d858e", "#11161d"), 4.86, abs_tol=0.01)
    assert math.isclose(theme.contrast_ratio("#6b7682", "#21262d"), 3.29, abs_tol=0.01)


def test_每一組前景背景都達標_未達標數為零():
    """客戶 2026-09-22 設計引導第一條：一般文字 4.5／大文字 3／非文字 UI 元件 3。"""
    failed = [
        (label, round(theme.contrast_ratio(fg, bg), 2), floor)
        for label, fg, bg, floor in theme.CONTRAST_PAIRS
        if theme.contrast_ratio(fg, bg) < floor
    ]
    assert failed == []
    assert len(theme.CONTRAST_PAIRS) >= 24


def test_客戶指定的三個主色一個字都沒動():
    assert theme.APP_BG == "#0e1117"
    assert theme.TEAL_DARK == "#0f6b6c"
    assert theme.TEAL_BRIGHT == "#5fd3d0"


def test_門檻只有三個數():
    floors = {floor for _, _, _, floor in theme.CONTRAST_PAIRS}
    assert floors <= {4.5, 3.0}


def test_theme零streamlit():
    source = pathlib.Path(theme.__file__).read_text(encoding="utf-8")
    assert "import streamlit" not in source
    assert "st." not in source


# ─────────── 第 5~8 輪裁示的回補 ＋ 本輪回修（每一條都經突變實測會紅） ───────────
# 實作那一顆 `7a3f46e` 早於 `44` 第五～第八輪解凍，那幾輪的裁示不可能被它吃到。


def _four_block_indicators(model):
    """那四塊**實際畫出來**的指標名。期望值一律從這裡來，不拿被測常數當自己的期望。"""
    names = []
    for code in ("HLD-2", "HLD-3"):
        for mv in logic.find_block(model, code)["fund_groups"][0]["main_values"]:
            names.append(mv["label"])
    row = logic.find_block(model, "HLD-8")["_rows"][0]
    return names + [row["drawdown"]["label"], row["principal"]["label"]]


def test_HLD6回答什麼取改寫後那一句():
    """`44` :720 第五輪改寫；舊句「上面三張卡」涵蓋不到 `HLD-8`。"""
    assert logic.ANSWERS["HLD-6"] == "本頁那四塊用到的原始數字，逐筆是什麼"
    for name in fixtures.SCENARIO_NAMES:
        model = logic.build_page_model(**fixtures.scenario(name))
        assert not [s for s in logic.collect_ui_strings(model) if "上面三張卡" in s], name


def test_門檻指標名的母體就是那四塊各自出的指標():
    """`44` :583（第七輪）。母體由那四塊反推，不另抄一份清單。"""
    model = logic.build_page_model(**fixtures.scenario("full"))
    expected = _four_block_indicators(model)
    assert set(logic.RULE_INDICATOR_NAMES) == set(expected)
    assert len(logic.RULE_INDICATOR_NAMES) == 6
    for name in logic.RULE_INDICATOR_NAMES:
        assert logic.INDICATOR_OWNER[name] in ("HLD-1", "HLD-2", "HLD-3", "HLD-8")


def test_HLD4帶著母體但不把它寫上畫面():
    """A1：`44` :583 的動詞是「**取**」＝值域宣告，不是顯示要求（要顯示時 44 寫「寫出／另寫一行」）。"""
    block = logic.find_block(logic.build_page_model(**fixtures.scenario("full")), "HLD-4")
    assert set(block["rule_indicator_names"]) == set(logic.RULE_INDICATOR_NAMES)
    assert "rule_indicator_caption" not in block


def test_nav的source_tier落在44第四節寫的四個值域內():
    """`44` :1799（第七輪）補上值域；同輪 §5.2「`來源` 那一類不再是開放集」。"""
    assert fixtures.SOURCE_TIERS == ("淨值", "配息", "市場指標", "其他")
    seen = 0
    for name in fixtures.SCENARIO_NAMES:
        for row in logic.find_block(
            logic.build_page_model(**fixtures.scenario(name)), "HLD-6"
        )["nav_rows"]:
            assert row["source_tier"] in fixtures.SOURCE_TIERS, (name, row)
            seen += 1
    assert seen > 0, "一列也沒掃到 —— 這一條會變成空掃"


_ALL_SCENARIOS = tuple(fixtures.SCENARIO_NAMES) + (
    "noexceed", "other_window", "onenav", "badrange", "full_then_badrange",
)


def test_HLD1與HLD2與HLD3在任何情境下都沒有重新取數按鈕():
    """**第 3 件的正控**（客戶 2026-09-23 裁示；有意識的政策變更，不是漏刪）。

    `44` :515（`HLD-1`）／:533（`HLD-2`）／:544（`HLD-3`）三格的空狀態欄
    **一個按鈕也沒有寫**，而 `44` 5.5「各塊自己寫的優先於本表模板」同輪補的分句逐字：
    「**一塊的空狀態欄整格為準：那一格沒有寫出按鈕，該塊的那個空狀態畫面上就沒有按鈕，
    不回退成本表模板裡的那一枚**」。
    決定性理由（`44` :2420 逐字）：「**一枚按了不動的按鈕，比沒有按鈕更誤導**」——
    這一頁缺的四張表由 Sheets 維護、本儀表板唯讀，按下去不會有任何效果。

    ~~舊表述：`test_HLD8的重新取數與核心卡同一套規則` 要求三張核心卡與 `HLD-8` 掛鈕條件相同。~~
    **舊表述在寫下當時撐得住** —— 它引的是 `44` :762 第一句「四狀態逐值判定，**與核心卡同一套**」，
    在三張卡都掛鈕的前提下，把 `HLD-8` 收窄確實會破掉那個「同一套」。
    **被權衡掉的是它的前提**：客戶裁掉了三張卡那三枚，「同一套」的那一端不存在了。
    ⚠️ **那一句「同一套」沒有被推翻，它的射程另有一條測試釘著**
    （見 `test_同一套指的是逐值判定與三個文案字面值_不是按鈕`）。

    ⚠️ **拿掉修復就會紅**：把任何一枚 `_retry_button()` 加回這三塊，本條當場轉紅。
    """
    checked = 0
    for name in _ALL_SCENARIOS:
        model = logic.build_page_model(**fixtures.scenario(name))
        for code in ("HLD-1", "HLD-2", "HLD-3"):
            block = logic.find_block(model, code)
            labels = [b["label"] for b in block["buttons"]]
            assert "重新取數" not in labels, (name, code, labels)
            checked += 1
    assert checked == len(_ALL_SCENARIOS) * 3 > 0


def test_HLD8是本頁唯一寫出重新取數的塊_而且它真的掛得出來():
    """`44` :762 本塊空狀態欄**自己寫出了**那枚鈕；`44` :2423 的實測同向 ——
    四格裡寫出 `來源缺` 的十五塊，同格寫出那枚鈕的只有 `MKT-1` 與 `HLD-8` 兩塊。

    ⚠️ 後半句是**反空掃**：若一枚也掛不出來，前半句會退化成「全頁都沒有鈕」而恆真。
    """
    seen = set()
    for name in _ALL_SCENARIOS:
        model = logic.build_page_model(**fixtures.scenario(name))
        for block in logic.all_blocks(model):
            if any(b["label"] == "重新取數" for b in block["buttons"]):
                seen.add(block["code"])
    assert seen == {"HLD-8"}, seen


def test_同一套指的是逐值判定與三個文案字面值_不是按鈕():
    """`44` :762 第一句逐字：「**四狀態逐值判定，與核心卡同一套**：
    `⬜ 資料未備`／`⬜ 不適用：…`／`⚠ 取數失敗`」。

    「同一套」黏在**逐值判定與那三個文案字面值**上；那一格的按鈕是**後面另一句**
    （「取數失敗時該欄印出失敗訊息原文並掛『重新取數』按鈕」）自己寫的。
    ⇒ 拿掉三張核心卡那三枚鈕，**不會**動到這一句 —— 這一條就是在釘這件事。
    """
    families = ("⬜ 資料未備", "⬜ 不適用：", "⚠ 取數失敗")
    seen = {code: set() for code in ("HLD-2", "HLD-3", "HLD-8")}
    for name in _ALL_SCENARIOS:
        model = logic.build_page_model(**fixtures.scenario(name))
        for code in seen:
            for node in logic.value_nodes(logic.find_block(model, code)):
                assert node["_state"] in {
                    logic.STATE_OK, logic.STATE_MISSING,
                    logic.STATE_BIZ, logic.STATE_ERROR,
                }, (name, code, node)
                if node["_state"] != logic.STATE_OK:
                    assert node["text"].startswith(families), (name, code, node["text"])
                    seen[code].add(node["text"])
    for code, texts in seen.items():
        assert texts, code  # 反空掃：每一塊都真的出過非 ok 的文案
    # `HLD-8` 承接的是那兩張卡各自的第三個值，所以它的文案是兩張卡的聯集再加上
    # 「配息類別未知」那一句（`44` :544 把該句連同本金類佔比一起交給 `HLD-8`）。
    assert seen["HLD-2"] | seen["HLD-3"] <= seen["HLD-8"], (
        sorted((seen["HLD-2"] | seen["HLD-3"]) - seen["HLD-8"])
    )


def test_登記_HLD8那枚鈕綁得比44的字面寬():
    """⚠️ **這是一筆登記，不是一條規格** —— 拿掉三枚之後浮出來的新不一致。

    `44` :762 那一格寫按鈕的那一句逐字是「**取數失敗時**該欄印出失敗訊息原文並掛
    『重新取數』按鈕」——**只綁 `取數失敗`**。
    而本檔實作把它綁在 `資料未備` ∪ `系統錯誤` 上，於是 `srcmiss`（只有缺淨值、
    沒有任何一個值進 `取數失敗`）也掛得出鈕。

    ⚠️ **2026-09-24 補上另一邊（原本只寫了「比字面寬」這一邊）**：
    `44` :762 **同一格的第一句**是「四狀態逐值判定，**與核心卡同一套**」，
    而核心卡那張表（`44` :2009）給 `資料未備` 那一列**也逐字掛了一枚「重新取數」**。
    ⇒ **照那條連結讀，現行這個較寬的綁法才是 `44`-compliant，
    :762 的按鈕子句反而是窄的那一個。**
    **`44` 在同一格裡給了兩個答案**，本檔不替客戶選。

    **本輪刻意不改 `HLD-8`**：收窄與否是客戶的地盤（收窄＝`srcmiss` 下本頁一枚鈕也沒有）。
    **登記，不是動工授權；待客戶裁決。**

    這一條把**現況**釘住，好讓將來任何一次改動都是有意識的，不是漂移。
    """
    model = logic.build_page_model(**fixtures.scenario("srcmiss"))
    block = logic.find_block(model, "HLD-8")
    states = {n["_state"] for n in logic.value_nodes(block)}
    assert states, "一個主值也沒有 —— 這一條會變成空掃"
    assert logic.STATE_ERROR not in states, sorted(states)   # 44 字面的條件不成立
    assert logic.STATE_MISSING in states, sorted(states)
    assert any(b["label"] == "重新取數" for b in block["buttons"])  # 實作照樣掛


def test_HLD6與HLD7沒有重新取數按鈕():
    """`44` 5.5「整格為準」：兩塊空狀態欄寫 `來源缺`，一個按鈕也沒寫。"""
    for name in fixtures.SCENARIO_NAMES:
        model = logic.build_page_model(**fixtures.scenario(name))
        for code in ("HLD-6", "HLD-7"):
            assert logic.find_block(model, code)["buttons"] == [], (name, code)


def test_HLD7四塊都不出數時進來源缺而列照印():
    """A5：`44` :730「四塊沒有一塊出數 → `來源缺`」。同格另有一句「輸入欄照列」，兩句
    **同時滿足** —— 前者定塊的狀態、後者定列的畫面，不同層。把列吞掉只印「來源缺」是假話。"""
    block = logic.find_block(logic.build_page_model(**fixtures.scenario("badrange")), "HLD-7")
    assert {r["output_text"] for r in block["_rows"]} == {logic.NA_NO_WINDOW}
    assert block["_state"] == logic.STATE_MISSING
    assert len(block["_rows"]) > 0
    for row in block["_rows"]:
        assert row["inputs_text"], row


def test_空狀態文案照44不自己寫散文():
    """A6：`44` :708 折線區明文回指 §5.5 模板。A7：`44` :719 只寫「無列 → `來源缺`」——
    兩張表為空不一定等於沒有持倉（取數失敗、區間外都可能）。"""
    src = logic.build_page_model(**fixtures.scenario("srcmiss"))
    item = logic.find_row(logic.find_block(src, "HLD-5"), "CCCC")
    assert item["nav_plot_text"] == logic.empty_source_text(["nav"])
    empty = logic.build_page_model(**fixtures.scenario("empty"))
    lines = logic.find_block(empty, "HLD-6")["detail_lines"]
    assert lines == [logic.empty_source_text(["nav", "dividend"])], lines


def test_0caller的常數依44第六節不刪只標():
    """A2／A8：`44` :2476 §6「**不刪，只標**……刪掉是不可逆的，標錯是可逆的」。
    上一輪刪了 `_RULE_INDICATORS`，同一輪卻留著同樣 0-caller 的 `_source_badge` —— 已復原。"""
    assert logic._RULE_INDICATORS == ("最大回撤", "配息佔淨值比", "區間報酬率", "期間波動")
    assert set(logic._RULE_INDICATORS) != set(logic.RULE_INDICATOR_NAMES)
    for name in ("NA_FEW_NAV", "NA_LATE_INCEPTION", "NA_NO_DIVIDEND", "NA_UNKNOWN_KIND"):
        assert hasattr(logic, name), name


def test_徽章住在模型裡_不是渲染時才生出來():
    """A9：`collect_badges()` 要 `_kind` 鍵，渲染時現組的 dict 沒有 ——
    既有的 `test_來源徽章中性不著色` 因此空掃至今。這一條釘住它有東西可掃。"""
    model = logic.build_page_model(fixtures.dataset_full())
    kinds = [b.get("_kind") for b in logic.collect_badges(model)]
    assert kinds.count("來源") > 0, "來源徽章一枚都收不到 —— 684 那條又會變空掃"
    assert kinds.count("狀態") > 0
    for badge in logic.collect_badges(model):
        if badge.get("_kind") == "來源":
            assert badge["text"] in fixtures.SOURCE_TIERS, badge


def test_跨幣別偵測器真的偵測得到跨幣別合成值():
    """A10：`44` 5.1「同一張卡不混不同幣別做平均」。舊版要求「同一個 `text` 裡出現兩個幣別
    字面值」，而百分比不帶幣別、金額只帶一個 —— **條件永遠不成立**。
    這一條當場造兩種違規值，證明偵測器真的抓得到。"""
    model = logic.build_page_model(fixtures.dataset_full())
    assert logic.cross_currency_nodes(model) == []

    card = logic.find_block(model, "HLD-2")
    assert len({g["_ccy"] for g in card["fund_groups"]}) > 1, "這張卡只有一種幣別就驗不到"
    card["_cross"] = logic._metric(1.23, text="1.23%（示意）", ccy="USD", label="全部平均")
    assert logic.cross_currency_nodes(model), "卡層級合計沒有被抓到"

    model2 = logic.build_page_model(fixtures.dataset_full())
    group = logic.find_block(model2, "HLD-2")["fund_groups"][0]
    other = "EUR" if group["_ccy"] != "EUR" else "USD"
    group["main_values"][0] = dict(group["main_values"][0], _ccy=other)
    assert logic.cross_currency_nodes(model2), "幣別對不上所在那一檔也沒有被抓到"


# ═════════════ 客戶 2026-09-23 裁示：第 4／5／6 件的正控 ═════════════


def test_第4件正控_open_fund_after_click_點一檔展開一檔():
    """`44` HLD-5 規則欄逐字「點一檔展開一檔，**同時最多展開一檔**」。

    ⚠️ 拿掉修復（讓 `open_fund_after_click` 回 `current`）本條轉紅。
    """
    assert logic.open_fund_after_click(None, "AAAA") == "AAAA"
    assert logic.open_fund_after_click("AAAA", "BBBB") == "BBBB"
    assert logic.open_fund_after_click("BBBB", "BBBB") == "BBBB"


def test_第4件正控_同時最多展開一檔且初次載入零檔():
    """`44` :119／:128／:2315「初次載入展開的只有結論燈 ＋ 3 張核心卡」
    ＋ `44` :711 判準「同時處於展開狀態的檔數為 1」。"""
    model = logic.build_page_model(**fixtures.scenario("full"))
    items = logic.find_block(model, "HLD-5")["_items"]
    assert items, "一檔也沒有 —— 這一條會變成空掃"
    assert sum(1 for i in items if i["_open"]) == 0
    for code in [i["_fund_code"] for i in items]:
        opened = logic.build_page_model(fixtures.dataset_full(), open_fund=code)
        rows = logic.find_block(opened, "HLD-5")["_items"]
        assert [i["_fund_code"] for i in rows if i["_open"]] == [code], code
        # `44` 5.3：展開中的那一檔，它的鈕停用而且不隱藏，且附一行原因。
        me = [i for i in rows if i["_fund_code"] == code][0]
        assert me["_button"]["_enabled"] is False
        assert me["_button"]["_visible"] is True
        assert me["_button"]["disabled_reason"]


def test_第4件正控_那枚鈕是44五點三的展開類且不寫任何表():
    """`44` 5.3：八類之外沒有第九類；`導覽`／`展開` 什麼都不寫。"""
    model = logic.build_page_model(fixtures.dataset_full(), open_fund="AAAA")
    items = logic.find_block(model, "HLD-5")["_items"]
    assert len(items) == 3, len(items)
    for item in items:
        button = item["_button"]
        assert button["label"] == logic.HLD5_OPEN_LABEL
        assert button["_action_kind"] == "展開"
        assert button["_action_kind"] in logic.BUTTON_KINDS
        assert button["_writes"] == set()
    # 走全頁掃描也看得到它（`44` 5.3 元件判準掃的是「介面上全部按鈕」）。
    # ⚠️ `_build_hld5` 把同一份 list 同時掛在 `_items` 與 `_rows`，
    #    `_walk` 因此會走到同一個 dict 兩次 —— 這裡用「至少」而不是「剛好」。
    scanned = [
        b for b in logic.collect_buttons(model)
        if b["label"] == logic.HLD5_OPEN_LABEL
    ]
    assert len(scanned) >= 3, len(scanned)


def test_第5件正控_空持倉而且有一塊取數失敗時燈為紅():
    """**第 5 件的正控**（客戶 2026-09-23 裁示：改紅）。

    `44` :489 規則欄「任一塊為 `系統錯誤` → 燈為**紅**」與同塊空狀態欄
    「持倉表為空 → 燈為**灰**」同時命中，`44` 沒有訂先後，客戶裁紅。
    方向出自 `44` :1620 逐字「**一句把空白報成平安的文案，比沒有文案更誤導**」。

    ⚠️ **拿掉修復就會紅**：把 `conclusion_light` 的 `not has_holdings` 那一段
    移回 `STATE_ERROR in states` 前面，本條當場轉紅（燈會回到灰）。
    """
    model = logic.build_page_model(**fixtures.scenario("emptyfail"))
    lamp = logic.find_block(model, "HLD-0")
    assert lamp["_tone"] == "紅", lamp["_tone"]
    assert lamp["_state"] == logic.STATE_ERROR
    assert lamp["text"] == "有一塊取數失敗，這一頁的數字先不要照著讀"
    # 失敗的那一塊被點名。
    assert any("配息與本金卡" in line for line in lamp["lines"]), lamp["lines"]
    # 空持倉那一句沒有被吞掉，降級成補述（兩件事都看得到，不是二選一）。
    assert any(logic.TEXT_NO_HOLDING in line for line in lamp["lines"]), lamp["lines"]


def test_第5件正控_只是空持倉而沒有失敗時仍然是灰():
    """⛔ 反向控制：第 5 件收掉的**只有**「空持倉 ＋ 有一塊失敗」那一種。
    沒有任何一塊失敗時，`44` :490 空狀態欄那一句一個字未改、照樣回灰。"""
    lamp = logic.find_block(
        logic.build_page_model(**fixtures.scenario("empty")), "HLD-0"
    )
    assert lamp["_tone"] == "灰"
    assert lamp["text"] == logic.TEXT_NO_HOLDING


def test_第5件正控_emptyfail與empty只差一個取數失敗():
    """釘住 fixture 本身：兩組資料除了 `errors` 以外逐鍵相同，
    否則「改紅」可能是別的差異造成的，這條正控就不成立。"""
    a, b = fixtures.dataset_empty(), fixtures.dataset_emptyfail()
    assert a["errors"] == {}
    assert b["errors"] == {"dividend": fixtures.FETCH_FAIL_MESSAGE}
    assert {k: v for k, v in a.items() if k != "errors"} == {
        k: v for k, v in b.items() if k != "errors"
    }


def test_第6件正控_worst_state不替44排資料未備與業務例外的先後():
    """**第 6 件的正控**（客戶 2026-09-23 裁示：拆掉 `_SEVERITY` 的 tie-break）。

    `44` :310（`MKT-0` 規則欄）是全檔唯一明文排過卡片四狀態的地方，
    它把 `資料未備` 與 `業務例外` **並列同級**（皆 → 黃）。
    ⇒ 兩者同時是最差時**沒有答案**，回 `STATE_UNRANKED`，不挑一個充數。

    ⚠️ **拿掉修復就會紅**：把 `_BAND` 改回 `{ok:0, 資料未備:1, 業務例外:2, 系統錯誤:3}`，
    本條第一句當場轉紅（會回 `業務例外`）。
    """
    assert logic.worst_state([logic.STATE_MISSING, logic.STATE_BIZ]) is logic.STATE_UNRANKED
    # 單一成員的那幾級照樣答得出來。
    assert logic.worst_state([logic.STATE_OK, logic.STATE_MISSING]) == logic.STATE_MISSING
    assert logic.worst_state([logic.STATE_OK, logic.STATE_BIZ]) == logic.STATE_BIZ
    assert logic.worst_state([logic.STATE_OK]) == logic.STATE_OK
    assert logic.worst_state(
        [logic.STATE_MISSING, logic.STATE_BIZ, logic.STATE_ERROR]
    ) == logic.STATE_ERROR
    # `44` :310 的那一級：兩者同級。
    assert logic._BAND[logic.STATE_MISSING] == logic._BAND[logic.STATE_BIZ]


def test_性質_worst_state與輸入順序無關_但這不是第6件的正控():
    """⚠️ **2026-09-24 就地更正：這一條原本掛著「第 6 件正控」的名字，那是假的**
    （有意識的更正，不是漏刪；決策者：AI 總管；稽核抓到）。

    ~~原 docstring：「舊實作用 `max()`，同級時回『先出現的那一個』——
    那是一個看不見的 tie-break。」~~
    **本組實跑推翻**：把四狀態的 **69 組 multiset（size 1~4）× 每組的全部排列**
    餵進 `a7f8c1b` 的舊 `worst_state`，**order-dependent 的組數 ＝ 0**。
    原因很簡單：舊 `_SEVERITY` 把那兩個排成**不同級**，`max()` **從來沒遇過平手**。
    ⇒ 這一條在 `a7f8c1b` 上**一樣會綠**，它**不是**第 6 件修好的東西。
    **突變 M6 的實測也指向同一件事：紅的是另外兩條，這一條沒紅。**

    ⛔ **這一筆的來歷要寫明**：「舊版 `max()` 同級時回先出現的」出自總管的回修單，
    本組**照收、沒查證就寫進程式碼與測試名稱**。
    **總管沒查證就寫進派工單，本組沒查證就寫進會被後人讀的記錄** —— 同一個病的兩端。

    **這一條保留的理由**：性質本身**是真的、而且值得守**（`worst_state` 不得與順序有關），
    只是它守的是一個**本來就成立**的性質，不是一個新修好的東西。**名字改成誠實的。**
    ⚠️ 第 6 件真正的正控是 `test_第6件正控_worst_state不替44排資料未備與業務例外的先後`。
    """
    import itertools

    states = (logic.STATE_OK, logic.STATE_MISSING, logic.STATE_BIZ, logic.STATE_ERROR)
    checked = 0
    for size in (1, 2, 3, 4):
        for combo in itertools.combinations_with_replacement(states, size):
            outs = {logic.worst_state(list(perm)) for perm in itertools.permutations(combo)}
            assert len(outs) == 1, (combo, outs)
            checked += 1
    assert checked == 69, checked  # 反空掃：母體真的是那 69 組


def test_第6件正控_同級是真的會發生_而且畫面照樣畫得出顏色():
    """反空掃：證明這一對**真的排得到**，不是一條永遠跑不到的分支。

    構造法：某檔淨值整個抽掉（最大回撤 → `⬜ 資料未備`），
    而同一檔的配息全是 `unknown`（本金類佔比 → `⬜ 不適用：配息類別未知`）——
    `HLD-8` 同一塊裡同時有 `資料未備` 與 `業務例外`。
    （現有的 `srcmiss` 刻意把那一檔的 `unknown` 翻成 `income` 才避開了它。）
    """
    dataset = fixtures._dataset(
        nav=[r for r in fixtures.navs() if r["fund_code"] != "CCCC"],
        window=(fixtures.WINDOW_START, fixtures.WINDOW_END),
        rules=fixtures._RULES_DEFAULT,
    )
    block = logic.find_block(logic.build_page_model(dataset), "HLD-8")
    states = {n["_state"] for n in logic.value_nodes(block)}
    assert {logic.STATE_MISSING, logic.STATE_BIZ} <= states, sorted(states)
    assert logic.STATE_ERROR not in states, sorted(states)
    # 狀態排不出來 → 不硬答；但畫面還是要有一個顏色，不能當掉。
    assert block["_state"] is logic.STATE_UNRANKED
    assert block["_tone"] == "黃"


def test_第6件正控_拆掉tie_break沒有改變任何一個現行畫面的顏色():
    """⛔ 反向控制：第 6 件動的是「這一塊最差的是哪一個狀態」這句**宣稱**，
    **不是**畫面。逐情境逐塊比對顏色，與拆之前逐格相同。

    這一份期望值是拆掉 tie-break **之前**跑出來的（量測日 2026-09-23）。
    """
    expected = {
        ("full", "HLD-1"): "中性", ("full", "HLD-2"): "中性",
        ("full", "HLD-3"): "中性", ("full", "HLD-8"): "黃",
        ("srcmiss", "HLD-1"): "中性", ("srcmiss", "HLD-2"): "灰",
        ("srcmiss", "HLD-3"): "灰", ("srcmiss", "HLD-8"): "灰",
        ("bizexc", "HLD-1"): "中性", ("bizexc", "HLD-2"): "黃",
        ("bizexc", "HLD-3"): "中性", ("bizexc", "HLD-8"): "黃",
        ("fetchfail", "HLD-1"): "中性", ("fetchfail", "HLD-2"): "中性",
        ("fetchfail", "HLD-3"): "紅", ("fetchfail", "HLD-8"): "紅",
        ("nothr", "HLD-1"): "黃", ("nothr", "HLD-2"): "中性",
        ("nothr", "HLD-3"): "中性", ("nothr", "HLD-8"): "黃",
        ("empty", "HLD-1"): "灰", ("empty", "HLD-2"): "灰",
        ("empty", "HLD-3"): "灰", ("empty", "HLD-8"): "灰",
        ("onenav", "HLD-2"): "黃", ("onenav", "HLD-8"): "黃",
        ("badrange", "HLD-1"): "黃", ("badrange", "HLD-8"): "黃",
        ("other_window", "HLD-8"): "中性",
    }
    assert expected, "期望值是空的 —— 這一條會變成空掃"
    for (name, code), tone in expected.items():
        block = logic.find_block(logic.build_page_model(**fixtures.scenario(name)), code)
        assert block["_tone"] == tone, (name, code, block["_tone"], tone)


# ═════════════ 進入點 docstring 的情境清單（總管 2026-09-23 指定的正控） ═════════════

# 中文數字，索引即它代表的數（`_CJK_NUM[7]` 就是「七」）。
# ⚠️ 刻意不寫成 `dict`，也刻意不用索引以外的查法 —— 有人重排就會**靜默**指到別的字。
_CJK_NUM = ("零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十")


def _app_hld_docstring() -> str:
    """讀進入點的 docstring。

    ⚠️ **用 AST 讀，不 import 那一檔** —— 它 `import streamlit`，而本檔自陳不 import
    streamlit（系統 python3 也匯入不到）。AST 只解析、不執行，兩個環境都跑得起來。
    """
    import ast

    path = pathlib.Path(__file__).resolve().parents[2] / "ui_v2" / "app_hld.py"
    doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
    assert doc, "進入點沒有 docstring —— 這一條會變成空掃"
    return doc


def test_進入點docstring列的情境集合等於SCENARIO_NAMES():
    """**總管 2026-09-23 指定的正控。**

    那一行 docstring 原本列六種，而 `emptyfail` 加進來之後它**已經過期** ——
    一份自陳「用這幾個值切」的說明，少列一個值，讀的人就不知道那個畫面存在。
    ⚠️ 這一條存在的意義是：**下次再加情境，這裡直接紅燈，不用靠人回頭讀。**

    ⚠️ **拿掉修復就會紅**：把那一行的 `|emptyfail` 刪掉（回到六種），本條當場轉紅。
    """
    import re

    doc = _app_hld_docstring()
    match = re.search(r"\?scenario=([A-Za-z0-9_|]+)", doc)
    assert match, f"docstring 裡找不到情境清單 —— 這一條會變成空掃：{doc!r}"
    listed = [token for token in match.group(1).split("|") if token]
    assert listed, "清單解析出零個情境 —— 這一條會變成空掃"

    # 集合相等（總管指定的那一條）。
    assert set(listed) == set(fixtures.SCENARIO_NAMES), (
        f"docstring 列的：{sorted(listed)}\n"
        f"SCENARIO_NAMES：{sorted(fixtures.SCENARIO_NAMES)}\n"
        "兩邊對不起來 —— 加了情境要同時補那一行 docstring。"
    )
    # 沒有重複列同一個（集合相等擋不住 `full|full|...`）。
    assert len(listed) == len(set(listed)), listed
    # 順序也對得上，讀的人照著從左到右試就是 fixtures 的順序。
    assert tuple(listed) == tuple(fixtures.SCENARIO_NAMES), (listed,
                                                            fixtures.SCENARIO_NAMES)


def test_進入點docstring那個數字與它自己列的個數相符():
    """同一行上還有一個「N 種」。**清單對了而數字沒改，那一行照樣在說謊。**

    這一條補的是上一條的縫：集合相等擋不住「列了七個、卻寫著六種」。
    ⚠️ **拿掉修復就會紅**：把那一行的「七種」改回「六種」，本條當場轉紅。
    """
    import re

    doc = _app_hld_docstring()
    match = re.search(r"\?scenario=([A-Za-z0-9_|]+)", doc)
    assert match, "找不到情境清單 —— 這一條會變成空掃"
    count = len([t for t in match.group(1).split("|") if t])
    assert 0 < count < len(_CJK_NUM), count
    expected = f"{_CJK_NUM[count]}種狀態"
    assert expected in doc, (
        f"那一行列了 {count} 個情境，卻找不到「{expected}」這四個字。\n"
        f"docstring：{doc!r}"
    )


# ═════════════ `44` 行號引用守衛（2026-09-24 稽核抓到一批指錯，改成機器驗） ═════════════

# 本輪之前，`44` 的行號引用**沒有任何機器檢查** —— 稽核一次抓到五組指錯，
# 其中四處還帶著「逐字」標籤。⇒ 改成「每一個引用都要登記，每一個登記都要對得上」。
#
# 鍵 ＝ `44` 的行號；值 ＝ 那一行**必須**出現的字串（我逐行讀出來的錨點）。
# ⚠️ 錨點刻意取**內容**而不是行號附近的裝飾，這樣 `44` 萬一改版，紅燈會指出「內容不見了」。
_44_ANCHORS = {
    119: "初次載入時展開的東西 ＝ 結論燈 ＋ 3 張核心卡",
    120: "展開狀態不跨頁保留；離開再回來，回到預設",
    128: "處於展開狀態的塊剛好是 1 枚結論燈與 3 張核心卡",
    310: "任一塊為 `資料未備` 或 `業務例外` → 燈為黃",
    400: "按「套用」才算，沒有第三條路",
    488: "不自取數。只讀 `HLD-1`、`HLD-2`、`HLD-3` 三塊的狀態值",
    489: "任一塊為 `系統錯誤` → 燈為紅",
    490: "持倉表為空 → 燈為灰",
    513: "`holding.fund_code`",
    515: "無任何持倉 → `來源缺`",
    531: "`fund_profile.inception_on`",
    533: "區間內淨值筆數少於 2",
    542: "`dividend.ex_date`",
    544: "區間內無配息列",
    583: "指標名取 `HLD-7` 規則欄已經用過的同一組",
    707: "點一檔展開一檔，同時最多展開一檔",
    708: "該檔在區間內無淨值",
    711: "展開第二檔時第一檔自動收合",
    719: "無列 → `來源缺`",
    720: "本頁那四塊用到的原始數字",
    730: "該列指標名所在那一塊把該指標判為",
    733: "其輸出欄的字串與該列指標名所在那一塊",
    762: "四狀態逐值判定，與核心卡同一套",
    1407: "`ALO-6` 的空狀態逐字是",
    1457: "某檔缺基準值",
    1620: "一句把空白報成平安的文案，比沒有文案更誤導",
    1623: "收掉的只有那一種它原本蓋不住的情形",
    1735: "該欄位單獨列出並掛「未定義」徽章",
    1799: "`source_tier`",
    2009: "主值位置顯示 `⬜ 資料未備`",
    2315: "`default_open` 為真的區塊剛好是結論燈與 3 張核心卡",
    2344: "顏色是 UI 顯示，不是嚴重度；兩者正交",
    2347: "再在句尾標上「逐字」",
    2420: "一枚按了不動的按鈕，比沒有按鈕更誤導",
    2423: "其中同在四格裡寫出那枚「重新取數」的只有",
    2476: "不刪，只標",
}

_MY_FILES = (
    "ui_v2/hld/logic.py",
    "ui_v2/hld/page.py",
    "ui_v2/hld/fixtures.py",
    "ui_v2/app_hld.py",
    "tests/ui_v2/test_hld_logic.py",
    "tests/ui_v2/test_hld_page.py",
)


def _strike_spans(line: str):
    """`~~…~~` 之間的區段 —— 被劃掉的是**已退役的紀錄**，不該拿它紅燈。"""
    spans, start = [], None
    for m in re.finditer(r"~~", line):
        if start is None:
            start = m.end()
        else:
            spans.append((start, m.start()))
            start = None
    return spans


def _live_44_citations():
    """掃出所有**活的** `44` 行號引用，回 [(檔, 檔內行號, 被引的 44 行號)]。

    只認「這一行寫了那個檔名標記」的行 —— 本 repo 裡另有兩種長得像行號的東西
    （字串切片的上界、以及時間戳裡的分秒），實測兩者都出現在**沒有**那個標記的行上，
    因此不會被誤當成引用。

    ⚠️ **刻意不把那兩種東西的字面寫進這段說明** —— 寫進來，這一支就會掃到自己，
    本段就變成一筆假的引用。（`CLAUDE.md` §-2.A 第 8 款：受測字串寫進文件就會自己命中；
    ✅ 正例是「資訊留著，字串不留」。**本段初稿正是照字面寫，當場被自己掃出三筆**，
    留這一筆是因為它是那一款最短的示範。）
    """
    out = []
    for name in _MY_FILES:
        path = pathlib.Path(__file__).resolve().parents[2] / name
        for lineno, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            if "`44`" not in line:
                continue
            spans = _strike_spans(line)
            for m in re.finditer(r":(\d{2,4})", line):
                if any(a <= m.start() < b for a, b in spans):
                    continue  # 劃掉的舊引用，不驗
                out.append((name, lineno, int(m.group(1))))
    return out


def test_我引的每一個44行號都真的指到我說的那一行():
    """**2026-09-24 稽核必修 A5 的機器版。**

    稽核一次抓到五組指錯（`:1616`→`:1620`、`:486`→`:489`/`:490`、
    來源欄 `:515`/`:529`/`:543`→`:513`/`:531`/`:542`、空狀態欄 `:529`/`:543`→`:533`/`:544`），
    **其中四處帶著「逐字」標籤** —— 帶標籤的假出處比沒有出處更糟。
    ⇒ 這一條要求：**每一個活的引用都要登記在 `_44_ANCHORS`，每一個登記都要對得上 `44` 的那一行。**

    ⚠️ 拿掉修復（把任何一個引用改回錯的行號）本條當場轉紅。
    """
    d44 = (pathlib.Path(__file__).resolve().parents[2]
           / "docs" / "v2" / "44_fund_ui_ssot.md").read_text(encoding="utf-8").split("\n")
    citations = _live_44_citations()
    assert citations, "一個引用也沒掃到 —— 這一條會變成空掃"

    unregistered = sorted({n for _, _, n in citations} - set(_44_ANCHORS))
    assert not unregistered, (
        f"這些 `44` 行號有人引用但沒登記進 `_44_ANCHORS`：{unregistered}\n"
        "怎麼修：自己去讀 `44` 那一行，把它的錨點字串加進表裡。**不要照抄別人給的行號。**"
    )

    bad = []
    for name, lineno, n in citations:
        if not (1 <= n <= len(d44)):
            bad.append(f"{name}:{lineno} 引的 `44` :{n} 超出檔尾（44 共 {len(d44)} 行）")
        elif _44_ANCHORS[n] not in d44[n - 1]:
            bad.append(
                f"{name}:{lineno} 引的 `44` :{n} 對不上\n"
                f"    期望那一行含：{_44_ANCHORS[n]!r}\n"
                f"    實際那一行是：{d44[n - 1][:110]!r}"
            )
    assert not bad, "\n".join(bad)


def test_44行號錨點表沒有死條目():
    """`_44_ANCHORS` 裡的每一條都要真的對得上 `44`，**即使暫時沒有人引用它**。

    ⚠️ 沒有這一條，一個從來沒被引用過的錯錨點可以永遠躺在表裡不被發現 ——
    那正是上一條想防的那個病換一個位置再犯。
    """
    d44 = (pathlib.Path(__file__).resolve().parents[2]
           / "docs" / "v2" / "44_fund_ui_ssot.md").read_text(encoding="utf-8").split("\n")
    assert _44_ANCHORS, "錨點表是空的 —— 這一條會變成空掃"
    for n, anchor in sorted(_44_ANCHORS.items()):
        assert 1 <= n <= len(d44), (n, len(d44))
        assert anchor in d44[n - 1], (n, anchor, d44[n - 1][:110])


def test_A2回歸_有持倉而門檻未設而且取數失敗_也是紅():
    """**2026-09-24 稽核必修 A2 的回歸測試 —— 次序調動收掉的是兩種，不是一種。**

    本組原本在 `conclusion_light()` 上方寫「收掉的**只有**空持倉那一種」，**那句是假的**：
    早退分支排在 `not has_holdings` **與 `not has_rules` 兩段之前**，
    所以「有持倉 ＋ 門檻未設 ＋ 有一塊 `系統錯誤`」也被收掉了。
    **本組實測**：同一組資料在 `a7f8c1b` 上是灰／「尚未設定門檻」，現在是紅。

    **兩種都在客戶裁示的方向上**（`系統錯誤` 不該被空狀態報成平安），故維持行為、改描述。
    ⚠️ 拿掉修復（把早退分支移回兩段之後）本條轉紅。
    """
    dataset = fixtures._dataset(
        window=(fixtures.WINDOW_START, fixtures.WINDOW_END),
        rules=None,
        errors={"dividend": fixtures.FETCH_FAIL_MESSAGE},
    )
    model = logic.build_page_model(dataset)
    lamp = logic.find_block(model, "HLD-0")
    assert dataset["holding"], "沒有持倉的話驗的就是另一種 —— 這一條會驗錯東西"
    assert lamp["_tone"] == "紅", lamp["_tone"]
    assert lamp["_state"] == logic.STATE_ERROR
    # 門檻那一句沒有被吞掉。
    assert any(logic.TEXT_NO_RULES in line for line in lamp["lines"]), lamp["lines"]
    assert any("取數失敗" in line for line in lamp["lines"]), lamp["lines"]


def test_A2回歸_紅燈不吞掉空狀態欄的任何一句():
    """`44` :490 空狀態欄寫了**兩句**（持倉表為空／門檻未設定）。
    紅燈早退時**兩句都要降級成補述，一句都不准吞掉**。

    ⛔ 本組原本只補了持倉那一句，而 `dataset_emptyfail()` 帶 `rules=None` ⇒
    三件事（沒持倉／沒門檻／取數失敗）**只活下來兩件，而且零測試涵蓋** ——
    正是本組在同一段註解裡宣稱避免掉的那件事。
    ⚠️ 拿掉修復（刪掉 `not has_rules` 那個補述分支）本條轉紅。
    """
    lamp = logic.find_block(
        logic.build_page_model(**fixtures.scenario("emptyfail")), "HLD-0"
    )
    joined = "\n".join(lamp["lines"])
    assert logic.TEXT_NO_HOLDING in joined, lamp["lines"]   # 沒持倉
    assert logic.TEXT_NO_RULES in joined, lamp["lines"]     # 沒門檻
    assert "取數失敗" in joined, lamp["lines"]              # 取數失敗
    assert lamp["_tone"] == "紅"


def _tables_named_in_44_source_row(lineno: int) -> set:
    """把 `44` 某一行「來源」欄裡點名的資料表撈出來（`表.欄` 這種寫法的左半）。"""
    d44 = (pathlib.Path(__file__).resolve().parents[2]
           / "docs" / "v2" / "44_fund_ui_ssot.md").read_text(encoding="utf-8").split("\n")
    line = d44[lineno - 1]
    assert "**來源**" in line, (lineno, line[:80])  # 確認真的是來源欄
    return set(re.findall(r"`([a-z_]+)\.[a-z_]+`", line))


def test_A3控_來源表真的是44來源欄的逐字子集():
    """**2026-09-24 稽核必修 A3 的機器版。**

    `BLOCK_SOURCE_TABLES` 自稱「`44` 各塊來源欄逐字點名的資料表」，
    **而稽核實測它漏了兩張**（`HLD-2` 的 `fund_profile`、`HLD-3` 的 `holding`），
    自述**只解釋了 `user_setting`**。⇒ 把那個自述變成機器驗得到的東西。

    契約兩條：
      (1) 收進來的，每一張都要真的出現在該塊的來源欄（**不准多**）；
      (2) 來源欄點名的，扣掉唯一那條說得出理由的篩選（`user_setting` 不經取數）之後，
          **每一張都要被收進來**（**不准漏**）。
    ⚠️ 拿掉修復（把 `fund_profile` 或 `holding` 從表裡刪掉）本條當場轉紅。
    """
    # 來源欄的行號本身由 `_44_ANCHORS` 那兩條守著，這裡只用它們。
    source_rows = {"HLD-1": 513, "HLD-2": 531, "HLD-3": 542}
    not_fetched = {"user_setting"}  # 使用者自己輸入，不經取數 —— 唯一的篩選
    assert set(source_rows) == set(logic.BLOCK_SOURCE_TABLES), (
        sorted(source_rows), sorted(logic.BLOCK_SOURCE_TABLES))
    for code, lineno in source_rows.items():
        named = _tables_named_in_44_source_row(lineno)
        assert named, (code, lineno)  # 反空掃：真的撈到表名
        collected = set(logic.BLOCK_SOURCE_TABLES[code])
        assert collected <= named, (code, "多收了", sorted(collected - named))
        assert named - not_fetched <= collected, (
            code, "漏收了", sorted(named - not_fetched - collected))


def test_A6控_無任何持倉那一句不在HLD2與HLD3的空狀態欄裡():
    """**2026-09-24 稽核必修 A6 的釘樁** —— 本組曾編過一句逐字引文。

    原寫 ~~「`44` :529／:543 空狀態欄寫『無任何持倉 → `來源缺`』」~~ ——**那一句不存在**
    （舊引用加刪除線保留：它指的兩個行號**本身也是錯的**，正確的空狀態欄在 :533／:544）。
    這一條把事實釘住：那句話在 `44` 只出現於四處，而 `HLD-2`／`HLD-3` 的空狀態欄
    **從頭到尾沒有提過持倉**。
    ⚠️ 拿掉修復（把那句編造的引文寫回註解）本條**不會**紅 —— 它守的是**事實**，
    不是註解字串；註解那一側由人讀。**這一點據實寫明，不假裝它守得比實際多。**
    """
    d44 = (pathlib.Path(__file__).resolve().parents[2]
           / "docs" / "v2" / "44_fund_ui_ssot.md").read_text(encoding="utf-8").split("\n")
    phrase = "無任何持倉"
    hits = [i for i, line in enumerate(d44, 1) if phrase in line]
    assert hits, "一處也沒掃到 —— 這一條會變成空掃"
    assert hits == [515, 762, 1407, 1457], hits
    # 那兩塊的空狀態欄（`_44_ANCHORS` 守著行號）確實沒有這一句。
    for lineno in (533, 544):
        assert "**空狀態**" in d44[lineno - 1], lineno
        assert phrase not in d44[lineno - 1], lineno
