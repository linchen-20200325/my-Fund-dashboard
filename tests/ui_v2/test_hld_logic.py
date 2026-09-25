# -*- coding: utf-8 -*-
"""持倉體檢（HLD）純邏輯測試。

測試先行：本檔先於 ui_v2/hld/logic.py 寫成並跑出紅燈。

引用範圍（客戶裁示）：只引 docs/v2/44_fund_ui_ssot.md（SSOT，已凍結）與
docs/v2/prototype/ui_prototype_hld.html（客戶已拍板的草稿）。
兩份對同一塊有不同說法以 44 為準（44 第零節自己訂明）。

本檔不 import streamlit，也不 import 任何舊 repo 模組。
"""

import json
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
    # ⛔ **2026-09-24 稽核必修 F：這裡原本是一句恆真的斷言。**
    # ~~舊寫法：`assert unranked_seen >= 0`，註解寫「反空掃留給下一條專門驗」。~~
    # **實測**：十五個情境產生的哨符塊數是 **0** ⇒ 上面那段「掙來的哨符」契約
    # **從出生到現在一次都沒有被執行過**，而收尾這一句**任何情況下都成立**。
    # ⇒ **一段沒跑過的 assert ＋ 一句恆真的收尾 ＝ 這半邊守衛是空的。**
    # ⚠️ **而同一輪 `mkt` 的孿生版寫的就是 `> 0`，而且真的踩得到** ——
    #    一份對、一份空轉；本輪補上 `tiedstate` 情境，兩邊口徑一致。
    assert unranked_seen > 0, (
        "沒有任何情境產生哨符 —— 上面那段「掙來的哨符」契約等於沒有被執行過")


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
    assert "⛔ 取數失敗" in joined
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
    assert seen["紅"] == ("⛔", "狀態：取數失敗")  # 2026-09-24 客戶裁示：取數失敗 ⛔（原 ✖）
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
    assert logic.fetch_failed_text("HTTP 503") == "⛔ 取數失敗：HTTP 503"
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
        "⛔ 取數失敗",
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
    # 2026-09-24 第 2 件新增三組。⚠️ **加在這裡是必要的，不是順手** ——
    # 上一輪 `KeyError: None` 就是因為「新增了情境、卻沒把全頁守衛一起擴」。
    "holdfail", "profilefail", "holdfail_nothr",
    # 2026-09-24 稽核必修 F 再加一組：**唯一會產生哨符的情境**。
    "tiedstate",
    # 2026-09-24 稽核必修 G 再加一組：**唯一會同時有兩張表失敗的情境**。
    "twofail",
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
    `⬜ 資料未備`／`⬜ 不適用：…`／`⛔ 取數失敗`」（圖示 2026-09-24 客戶裁示由 ⚠ 改 ⛔）。

    「同一套」黏在**逐值判定與那三個文案字面值**上；那一格的按鈕是**後面另一句**
    （「取數失敗時該欄印出失敗訊息原文並掛『重新取數』按鈕」）自己寫的。
    ⇒ 拿掉三張核心卡那三枚鈕，**不會**動到這一句 —— 這一條就是在釘這件事。
    """
    families = ("⬜ 資料未備", "⬜ 不適用：", "⛔ 取數失敗")
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


# ═══════════ 第 2 件｜失敗訊息補路（客戶 2026-09-24 裁示） ═══════════


def test_哪些來源表在有持倉時本來就浮得出來():
    """**先釘前提，再談補路。**

    `_SURFACED_PER_VALUE` 這張清單如果是憑印象列的，第 2 件整件事就建立在猜測上。
    這一條用**行為**把它定義出來：逐表注入一個取數失敗，看它**在沒有新路的情況下**
    會不會經由逐值判定浮出來（＝有值進 `系統錯誤`）。

    ⚠️ 所以這一條**不**呼叫新路，它驗的是「舊路覆蓋到哪裡」；
       日後 `fund_metrics()` 改讀別的 `errors` 鍵，這一條會紅，
       `_SURFACED_PER_VALUE` 不會靜默過期。
    """
    tables = sorted({t for ts in logic.BLOCK_SOURCE_TABLES.values() for t in ts})
    assert tables, "一張表也沒掃到 —— 這一條會變成空掃"
    surfaced = set()
    for table in tables:
        dataset = fixtures._dataset(
            window=(fixtures.WINDOW_START, fixtures.WINDOW_END),
            rules=fixtures._RULES_DEFAULT,
            errors={table: fixtures.FETCH_FAIL_MESSAGE},
        )
        assert dataset["holding"], "這一條的前提是有持倉"
        model = logic.build_page_model(dataset)
        hit = any(
            node["_state"] == logic.STATE_ERROR
            for block in logic.all_blocks(model)
            for node in logic.value_nodes(block)
        )
        if hit:
            surfaced.add(table)
    assert surfaced == set(logic._SURFACED_PER_VALUE), (
        sorted(surfaced), sorted(logic._SURFACED_PER_VALUE))
    # 反向：真的有沒被覆蓋到的，否則第 2 件無事可補。
    assert set(tables) - surfaced == {"holding", "fund_profile"}, sorted(set(tables) - surfaced)


def test_第2件正控_有持倉時holding取數失敗也浮得出來():
    """**第 2 件的正控。** `holding` 是 `HLD-1` 與 `HLD-3` 來源欄點名的表。

    ⚠️ **拿掉修復**（把 `_build_hld1`／`_build_core_card` 尾端那兩段
       `if has_holdings and unsurfaced:` 刪掉，或把 `build_page_model` 裡的
       `unsurfaced=` 拿掉）**本條當場轉紅**。
    """
    model = logic.build_page_model(fixtures.dataset_holdfail())
    for code in ("HLD-1", "HLD-3"):
        block = logic.find_block(model, code)
        assert block["_state"] == logic.STATE_ERROR, (code, block["_state"])
        assert block["_tone"] == "紅", (code, block["_tone"])
        assert any(fixtures.FETCH_FAIL_MESSAGE in line for line in block["detail_lines"]), code
        assert "訊息原文照印，不改寫成安撫語句。" in block["detail_lines"], code
    # `HLD-2` 的來源欄**沒有** `holding` ⇒ 它不該被連坐。
    assert logic.find_block(model, "HLD-2")["_state"] != logic.STATE_ERROR
    # 燈跟著紅 —— `44` :489 本來就這樣寫，本件只是讓它進得了 `系統錯誤`。
    assert logic.find_block(model, "HLD-0")["_tone"] == "紅"


def test_第2件正控_有持倉時fund_profile取數失敗也浮得出來():
    """`fund_profile` 只有 `HLD-2` 的來源欄點名 ⇒ 只有它該紅。"""
    model = logic.build_page_model(fixtures.dataset_profilefail())
    block = logic.find_block(model, "HLD-2")
    assert block["_state"] == logic.STATE_ERROR, block["_state"]
    assert block["_tone"] == "紅"
    assert any(fixtures.FETCH_FAIL_MESSAGE in line for line in block["detail_lines"])
    for code in ("HLD-1", "HLD-3"):
        assert logic.find_block(model, code)["_state"] != logic.STATE_ERROR, code
    assert logic.find_block(model, "HLD-0")["_tone"] == "紅"


def test_第2件正控_有持倉而門檻未設那一半也要補到():
    """**最容易漏的那一半。** 「有持倉」不只是最後那個 `else`，
    `elif not rules`（門檻未設）同樣是有持倉。

    ⚠️ 拿掉修復（把那段 `if has_holdings and unsurfaced:` 從 if/elif/else **之後**
       搬進 `else` **之內**）本條當場轉紅，而上面那兩條**不會** ——
       這就是為什麼要單獨有這一條。
    """
    model = logic.build_page_model(fixtures.dataset_holdfail_nothr())
    block = logic.find_block(model, "HLD-1")
    assert block["_state"] == logic.STATE_ERROR, block["_state"]
    assert any(fixtures.FETCH_FAIL_MESSAGE in line for line in block["detail_lines"])
    # 對照組：同樣門檻未設、但沒有取數失敗 → 照舊是 `業務例外`（本件未動）。
    plain = logic.find_block(logic.build_page_model(**fixtures.scenario("nothr")), "HLD-1")
    assert plain["_state"] == logic.STATE_BIZ, plain["_state"]


def test_第2件_算得出來的東西一個也沒有被失敗訊息蓋掉():
    """射程：本件只動塊層的 `_state` 與說明區，**不清空已經算出來的內容**。

    空持倉那一支會清空是因為它本來就沒東西可顯示；這裡有。
    ⛔ 用一個失敗訊息蓋掉還算得出來的事實，是另一種說謊。
    """
    failed = logic.build_page_model(fixtures.dataset_holdfail())
    clean = logic.build_page_model(**fixtures.scenario("full"))
    # 偏離列與逐值主值，逐格與沒有失敗時相同。
    assert logic.find_block(failed, "HLD-1")["_rows"] == logic.find_block(clean, "HLD-1")["_rows"]
    assert logic.find_block(failed, "HLD-1")["_rows"], "一列也沒有 —— 這一條會變成空掃"
    for code in ("HLD-2", "HLD-3"):
        a = [(n["label"], n["_state"], n["text"]) for n in logic.value_nodes(logic.find_block(failed, code))]
        b = [(n["label"], n["_state"], n["text"]) for n in logic.value_nodes(logic.find_block(clean, code))]
        assert a == b, code
        assert a, code


def test_第2件_同一個失敗不會被印兩次():
    """`_SURFACED_PER_VALUE` 那兩張表已經逐值印過訊息原文了，新路必須跳過它們，
    否則同一句會在同一塊出現兩次。"""
    model = logic.build_page_model(**fixtures.scenario("fetchfail"))  # dividend 失敗
    block = logic.find_block(model, "HLD-3")
    hits = [line for line in block["detail_lines"] if fixtures.FETCH_FAIL_MESSAGE in line]
    assert len(hits) == 1, hits
    # 而且新路對這張表根本不回東西。
    assert logic.unsurfaced_source_error(
        fixtures.scenario("fetchfail")["dataset"], "HLD-3") is None


def test_第2件_空持倉那兩支一格未動():
    """射程：`not has_holdings` 的行為**一格未動**，它們照舊走 `source_error()`。

    ⚠️ **本條的初稿寫錯過一次，就地記下來**：原本斷言 `emptyfail` 會讓 `HLD-1` 進
    `系統錯誤` —— **那是猜的**。`emptyfail` 的失敗表是 `dividend`，
    而 `dividend` **不在** `HLD-1` 的來源欄裡（`44` :513 只點名 `holding` 與 `nav`），
    所以 `HLD-1` 本來就是 `資料未備`、紅的是 `HLD-3`。
    ⇒ 改成照 `fd5e41b` 逐格 dump 出來的事實寫。**這一條自己就是「不要憑印象寫斷言」的示範。**
    """
    # 空持倉 ＋ `dividend` 取數失敗 → 紅的是 `HLD-3`（它的來源欄有 `dividend`），
    # `HLD-1` 照舊 `資料未備`。兩格都與 `fd5e41b` 相同。
    model = logic.build_page_model(**fixtures.scenario("emptyfail"))
    assert logic.find_block(model, "HLD-3")["_state"] == logic.STATE_ERROR
    assert logic.find_block(model, "HLD-1")["_state"] == logic.STATE_MISSING
    # 空持倉 ＋ 沒有失敗 → 照舊灰／`資料未備`。
    model = logic.build_page_model(**fixtures.scenario("empty"))
    assert logic.find_block(model, "HLD-1")["_state"] == logic.STATE_MISSING
    assert logic.find_block(model, "HLD-1")["_tone"] == "灰"
    # 空持倉 ＋ `holding` 取數失敗 → 照舊走 `source_error()` 那一支（2026-09-23 裁的那一種），
    # **與本件新路無關**：新路的硬前提是 `has_holdings`。
    ds = fixtures._dataset(
        holding=[],
        window=(fixtures.WINDOW_START, fixtures.WINDOW_END),
        rules=fixtures._RULES_DEFAULT,
        errors={"holding": fixtures.FETCH_FAIL_MESSAGE},
    )
    assert not ds["holding"]
    assert logic.find_block(logic.build_page_model(ds), "HLD-1")["_state"] == logic.STATE_ERROR
    # 新路對空持倉不回東西不是因為它沒被呼叫，而是因為 `has_holdings` 擋著 ——
    # 這一行把那個分工釘住（`unsurfaced_source_error()` 本身照樣回訊息）。
    assert logic.unsurfaced_source_error(ds, "HLD-1") == fixtures.FETCH_FAIL_MESSAGE
    # ⭐ **而且訊息只准印一次。**
    # ⚠️ **這一段是突變測試逼出來的，據實寫下經過**：本條的初版只驗 `_state`，
    #    於是「把新路的 `has_holdings` 前提拿掉」這個突變**全綠通過** ——
    #    因為空持倉那一支的 `state` 本來就已經是 `系統錯誤`，狀態看不出差別，
    #    **差別在說明區裡同一句話被印了兩次**。
    #    ⇒ 一條只驗狀態的正控，擋不住一個只弄髒文案的射程外溢。
    lines = logic.find_block(logic.build_page_model(ds), "HLD-1")["detail_lines"]
    hits = [line for line in lines if fixtures.FETCH_FAIL_MESSAGE in line]
    assert len(hits) == 1, hits
    assert lines.count("訊息原文照印，不改寫成安撫語句。") == 1, lines


def _cell_digest(block) -> str:
    """一塊模型的全格摘要。

    ⚠️ **正規化必須與產生期望值時逐字相同**，否則這條守衛會假紅：
    dict 鍵排序、set 轉排序後的 list、非 JSON 型別轉 `repr`。
    """
    import hashlib

    def scrub(obj):
        if isinstance(obj, dict):
            return {k: scrub(v) for k, v in sorted(obj.items())}
        if isinstance(obj, (list, tuple)):
            return [scrub(v) for v in obj]
        if isinstance(obj, set):
            return sorted(scrub(v) for v in obj)
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        return repr(obj)

    blob = json.dumps(scrub(block), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def test_第2件反向控制_十二情境乘九塊一百零八格逐格未變():
    """⛔ **反向控制，整張網。**

    第 2 件是**行為擴張**，所以「現行情境一格都不准動」必須用網驗，不是抽驗。
    這一份期望值是 `fd5e41b`（動手前）逐格 dump 出來的 —— **不是**從現行程式現撈的；
    從現行程式撈等於拿被測物當期望值，這一條就會變成恆真。

    ⚠️ 十二情境 × 九塊 ＝ **一百零八格**，每一格比三樣：`_tone`、`_state`、
       以及**整塊模型的摘要**。

    ⛔ **2026-09-24 就地更正：本條 docstring 原本對「摘要那一欄為什麼存在」的說法是錯的，
       而且錯了兩層（有意識的更正，不是漏刪；決策者：AI 總管；稽核抓到）。**
    ~~原寫：那兩個射程外溢的突變（拿掉 `has_holdings` 前提、清空 `_SURFACED_PER_VALUE`）
      沒被這張網攔下來，是因為它們不改狀態、只把同一句失敗訊息多印一次。~~
    **兩層都不成立，實測如下（本組獨立重跑，不是轉述）**：
      · **第一層（機制錯）**：真正的原因不是「改了文案但沒改狀態」，而是
        **這十二個情境根本走不到那段新程式碼** ——
        逐情境呼叫 `unsurfaced_source_error()`，**十二個情境回非 `None` 的是 0 個**。
        ⇒ **這張網對那條新路結構上是盲的，加不加摘要都一樣。**
      · **第二層（歸因錯）**：那兩個突變**升級成摘要之後也不是這張網抓到的**。
        單獨跑本條：兩個突變**都 passed**。真正抓到它們的是
        `test_第2件_空持倉那兩支一格未動`（2d）與
        `test_哪些來源表在有持倉時本來就浮得出來` ＋
        `test_第2件_同一個失敗不會被印兩次`（2e）。

    ✅ **摘要那一欄仍然留著，但理由換成一個真的**：它擋得住
       **十二個情境之內**「不改狀態、只改文案」的改動 ——
       實測把 `_build_hld1` 的一句說明文案改一個詞（不動任何狀態顏色），
       **只比 `_tone`／`_state` 的版本是綠的，加了摘要之後轉紅**。
    ⚠️ **這張網管不到那三個新情境**（它們在 `fd5e41b` 上不存在，沒有「之前」可比）——
       那個結構性盲點由下面那一條 `test_第2件_三個新情境的整頁模型逐格釘住()` 補上。
    ⚠️ 摘要對不上時看不出**哪裡**不同 —— 那是這個做法的代價，就地寫明：
       重跑一次逐格 dump 再 diff，不要直接改期望值。**期望值改了，這條就廢了。**
    """
    expected = {
        # ⚠️ 2026-09-24 第二十一輪：客戶裁示取數失敗圖示 ⚠→⛔，受影響格的摘要已換新值（有意識的更正，不是漏刪；hld 燈的紅圖示同輪 ✖→⛔）。
        #    換之前先證明：把現行模型字串裡的 ⛔ 換回原圖示（燈的圖示格換回 ✖、其餘換回 ⚠）再算摘要，本表舊值逐格全數重現（量測日 2026-09-24）；
        #    故差異只有那個圖示。沒被取數失敗碰到的格一格未動。
        ("full", "HLD-0"): ('黃', 'ok', "e241f44eef9e"),
        ("full", "HLD-1"): ('中性', 'ok', "057d10d7e5b3"),
        ("full", "HLD-2"): ('中性', 'ok', "6347d81de348"),
        ("full", "HLD-3"): ('中性', 'ok', "1d1e3f822996"),
        ("full", "HLD-4"): ('中性', 'ok', "dffae81c35eb"),
        ("full", "HLD-5"): ('中性', 'ok', "77305900bc65"),
        ("full", "HLD-6"): ('中性', 'ok', "cc137930f370"),
        ("full", "HLD-7"): ('中性', 'ok', "0594b2871949"),
        ("full", "HLD-8"): ('黃', '業務例外', "552b13b86b81"),
        ("srcmiss", "HLD-0"): ('黃', 'ok', "e241f44eef9e"),
        ("srcmiss", "HLD-1"): ('中性', 'ok', "36dc9ac49a78"),
        ("srcmiss", "HLD-2"): ('灰', '資料未備', "9e18e3388c92"),
        ("srcmiss", "HLD-3"): ('灰', '資料未備', "038877e4c54c"),
        ("srcmiss", "HLD-4"): ('中性', 'ok', "dffae81c35eb"),
        ("srcmiss", "HLD-5"): ('中性', 'ok', "39affe04cec8"),
        ("srcmiss", "HLD-6"): ('中性', 'ok', "0fa8eb2d70c6"),
        ("srcmiss", "HLD-7"): ('中性', 'ok', "697f3caf3268"),
        ("srcmiss", "HLD-8"): ('灰', '資料未備', "11c8446e411f"),
        ("bizexc", "HLD-0"): ('灰', '業務例外', "361d526cc96d"),
        ("bizexc", "HLD-1"): ('中性', 'ok', "54989f40bf94"),
        ("bizexc", "HLD-2"): ('黃', '業務例外', "10f06cc9db29"),
        ("bizexc", "HLD-3"): ('中性', 'ok', "1d1e3f822996"),
        ("bizexc", "HLD-4"): ('中性', 'ok', "e887c1dadaf2"),
        ("bizexc", "HLD-5"): ('中性', 'ok', "77305900bc65"),
        ("bizexc", "HLD-6"): ('中性', 'ok', "cc137930f370"),
        ("bizexc", "HLD-7"): ('中性', 'ok', "4cf045f13082"),
        ("bizexc", "HLD-8"): ('黃', '業務例外', "cecebdfffedc"),
        ("fetchfail", "HLD-0"): ('紅', '系統錯誤', "1cf22225b317"),
        ("fetchfail", "HLD-1"): ('中性', 'ok', "fe2c96ceefd7"),
        ("fetchfail", "HLD-2"): ('中性', 'ok', "6347d81de348"),
        ("fetchfail", "HLD-3"): ('紅', '系統錯誤', "49dd1baf455f"),
        ("fetchfail", "HLD-4"): ('中性', 'ok', "dffae81c35eb"),
        ("fetchfail", "HLD-5"): ('中性', 'ok', "77305900bc65"),
        ("fetchfail", "HLD-6"): ('中性', 'ok', "cc137930f370"),
        ("fetchfail", "HLD-7"): ('中性', 'ok', "1f8c41588f98"),
        ("fetchfail", "HLD-8"): ('紅', '系統錯誤', "5f6082f726fb"),
        ("nothr", "HLD-0"): ('灰', '業務例外', "c9353d4830c6"),
        ("nothr", "HLD-1"): ('黃', '業務例外', "e1d2c2c2da54"),
        ("nothr", "HLD-2"): ('中性', 'ok', "6347d81de348"),
        ("nothr", "HLD-3"): ('中性', 'ok', "1d1e3f822996"),
        ("nothr", "HLD-4"): ('中性', 'ok', "3de52cd071ec"),
        ("nothr", "HLD-5"): ('中性', 'ok', "77305900bc65"),
        ("nothr", "HLD-6"): ('中性', 'ok', "cc137930f370"),
        ("nothr", "HLD-7"): ('中性', 'ok', "8c667c291d77"),
        ("nothr", "HLD-8"): ('黃', '業務例外', "552b13b86b81"),
        ("empty", "HLD-0"): ('灰', '資料未備', "4562c6ab4995"),
        ("empty", "HLD-1"): ('灰', '資料未備', "47cf6be0fa49"),
        ("empty", "HLD-2"): ('灰', '資料未備', "19fe8879556e"),
        ("empty", "HLD-3"): ('灰', '資料未備', "a17b38e825ef"),
        ("empty", "HLD-4"): ('中性', 'ok', "2a92af344d78"),
        ("empty", "HLD-5"): ('灰', '資料未備', "0a56191f5002"),
        ("empty", "HLD-6"): ('灰', '資料未備', "291f8e96ab83"),
        ("empty", "HLD-7"): ('灰', '資料未備', "700622874cba"),
        ("empty", "HLD-8"): ('灰', '資料未備', "642bfc46dc5d"),
        ("emptyfail", "HLD-0"): ('紅', '系統錯誤', "42ebce44a36e"),
        ("emptyfail", "HLD-1"): ('灰', '資料未備', "47cf6be0fa49"),
        ("emptyfail", "HLD-2"): ('灰', '資料未備', "19fe8879556e"),
        ("emptyfail", "HLD-3"): ('紅', '系統錯誤', "6e75fe7f9b61"),
        ("emptyfail", "HLD-4"): ('中性', 'ok', "2a92af344d78"),
        ("emptyfail", "HLD-5"): ('灰', '資料未備', "0a56191f5002"),
        ("emptyfail", "HLD-6"): ('灰', '資料未備', "291f8e96ab83"),
        ("emptyfail", "HLD-7"): ('灰', '資料未備', "700622874cba"),
        ("emptyfail", "HLD-8"): ('灰', '資料未備', "642bfc46dc5d"),
        ("noexceed", "HLD-0"): ('灰', 'ok', "5aa16b6c8ace"),
        ("noexceed", "HLD-1"): ('中性', 'ok', "d6e09a8fff14"),
        ("noexceed", "HLD-2"): ('中性', 'ok', "6347d81de348"),
        ("noexceed", "HLD-3"): ('中性', 'ok', "1d1e3f822996"),
        ("noexceed", "HLD-4"): ('中性', 'ok', "e887c1dadaf2"),
        ("noexceed", "HLD-5"): ('中性', 'ok', "77305900bc65"),
        ("noexceed", "HLD-6"): ('中性', 'ok', "cc137930f370"),
        ("noexceed", "HLD-7"): ('中性', 'ok', "8c667c291d77"),
        ("noexceed", "HLD-8"): ('黃', '業務例外', "552b13b86b81"),
        ("other_window", "HLD-0"): ('灰', 'ok', "5aa16b6c8ace"),
        ("other_window", "HLD-1"): ('中性', 'ok', "d6e09a8fff14"),
        ("other_window", "HLD-2"): ('中性', 'ok', "5ea8fe7a7d69"),
        ("other_window", "HLD-3"): ('中性', 'ok', "d5547893ebe0"),
        ("other_window", "HLD-4"): ('中性', 'ok', "4af1779c6576"),
        ("other_window", "HLD-5"): ('中性', 'ok', "77305900bc65"),
        ("other_window", "HLD-6"): ('中性', 'ok', "cc137930f370"),
        ("other_window", "HLD-7"): ('中性', 'ok', "ad6c5cd4bc32"),
        ("other_window", "HLD-8"): ('中性', 'ok', "2a28e2a9534f"),
        ("onenav", "HLD-0"): ('灰', '業務例外', "361d526cc96d"),
        ("onenav", "HLD-1"): ('中性', 'ok', "51f6d37571ec"),
        ("onenav", "HLD-2"): ('黃', '業務例外', "eac4b10c9634"),
        ("onenav", "HLD-3"): ('黃', '業務例外', "a0b4b23b64c4"),
        ("onenav", "HLD-4"): ('中性', 'ok', "ff7c473013a3"),
        ("onenav", "HLD-5"): ('中性', 'ok', "77305900bc65"),
        ("onenav", "HLD-6"): ('中性', 'ok', "cc137930f370"),
        ("onenav", "HLD-7"): ('灰', '資料未備', "5ac721b1d7cb"),
        ("onenav", "HLD-8"): ('黃', '業務例外', "6131e0d46dd5"),
        ("badrange", "HLD-0"): ('灰', '業務例外', "c9353d4830c6"),
        ("badrange", "HLD-1"): ('黃', '業務例外', "e1d2c2c2da54"),
        ("badrange", "HLD-2"): ('黃', '業務例外', "4d9d1c56d7e3"),
        ("badrange", "HLD-3"): ('黃', '業務例外', "56270fe59261"),
        ("badrange", "HLD-4"): ('中性', 'ok', "14676aae6af8"),
        ("badrange", "HLD-5"): ('中性', 'ok', "56f4d7c00fa8"),
        ("badrange", "HLD-6"): ('中性', 'ok', "cc137930f370"),
        ("badrange", "HLD-7"): ('灰', '資料未備', "15a039bc1d56"),
        ("badrange", "HLD-8"): ('黃', '業務例外', "2d3de88d51b7"),
        ("full_then_badrange", "HLD-0"): ('黃', 'ok', "e241f44eef9e"),
        ("full_then_badrange", "HLD-1"): ('中性', 'ok', "057d10d7e5b3"),
        ("full_then_badrange", "HLD-2"): ('中性', 'ok', "6347d81de348"),
        ("full_then_badrange", "HLD-3"): ('中性', 'ok', "1d1e3f822996"),
        ("full_then_badrange", "HLD-4"): ('中性', 'ok', "044134dd12f9"),
        ("full_then_badrange", "HLD-5"): ('中性', 'ok', "77305900bc65"),
        ("full_then_badrange", "HLD-6"): ('中性', 'ok', "cc137930f370"),
        ("full_then_badrange", "HLD-7"): ('中性', 'ok', "0594b2871949"),
        ("full_then_badrange", "HLD-8"): ('黃', '業務例外', "552b13b86b81"),
    }
    assert len(expected) == 108, len(expected)
    old12 = set(fixtures.SCENARIO_NAMES) | {
        "noexceed", "other_window", "onenav", "badrange", "full_then_badrange"}
    # 涵蓋度也要驗：動手前就存在的情境，一個都不准從期望值裡漏掉。
    assert {name for name, _ in expected} == old12, sorted({n for n, _ in expected} ^ old12)
    # 2026-09-24 新增的三個情境刻意不在期望值裡（它們在 `fd5e41b` 上不存在，
    # 沒有「之前」可比）；它們的行為由上面那幾條正控釘。
    assert not (old12 & {"holdfail", "profilefail", "holdfail_nothr"})
    for (name, code), (tone, state, digest) in expected.items():
        block = logic.find_block(logic.build_page_model(**fixtures.scenario(name)), code)
        assert block["_tone"] == tone, (name, code, "tone", block["_tone"], tone)
        assert block["_state"] == state, (name, code, "state", block["_state"], state)
        assert _cell_digest(block) == digest, (
            name, code, "整格內容變了（狀態與顏色沒變，改的是這一塊裡的其他東西）")


# ═══════════ 第 3 件｜`46` 第 1 節的新入口（客戶 2026-09-24 裁示） ═══════════

_DOC46 = "docs/v2/46_fund_live_dead.md"


def _doc46_lines():
    return (pathlib.Path(__file__).resolve().parents[2]
            / _DOC46).read_text(encoding="utf-8").split("\n")


def _unstruck(line: str) -> str:
    """把 `~~…~~` 之間的字挖掉 —— 劃掉的是**已退役的條文**，不是現行規則。

    ⚠️ 與本檔 `44` 行號守衛的 `_strike_spans()` 同一套讀法，刻意不另發明一種。
    """
    out, keep, i = [], True, 0
    while i < len(line):
        if line.startswith("~~", i):
            keep = not keep
            i += 2
            continue
        if keep:
            out.append(line[i])
        i += 1
    return "".join(out)


def _doc46_registry_rows():
    """登記表的表頭與資料列（`| 檔案::符號 |` 那一張，不是第 5 節的量測表）。"""
    lines = _doc46_lines()
    head = next(i for i, ln in enumerate(lines) if ln.startswith("| 檔案::符號"))
    rows = []
    for ln in lines[head + 2:]:
        if not ln.startswith("|"):
            break
        rows.append(ln)
    return lines[head], rows


def test_第3件正控_46登記表的每一列都記了兩個日期():
    """**第 3 件的正控。**

    客戶 2026-09-24 改的第 1 節帶著**條件**：補登可以，但那一列必須把
    「確認日」與「登記日」分開記。**條件寫在散文裡、表格卻少一欄的話，
    那條新條文當場變成一條寫不了的規則** —— 而那正是它要修的那種互斥
    （`46` 第 5.5 節其三：兩條各自都對，合起來做不到）。

    ⇒ 這一條把散文與表格綁在一起，**不讓它們各自漂移**。
    ⚠️ 拿掉修復（把表頭那一欄拿掉、或把任何一列的「登記日」那一格清空）本條當場轉紅。
    """
    import re

    header, rows = _doc46_registry_rows()
    cells = [c.strip() for c in header.strip().strip("|").split("|")]
    assert len(cells) == 5, cells
    assert cells[-2:] == ["確認日", "登記日"], cells
    assert rows, "一列也沒掃到 —— 這一條會變成空掃"
    date = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for row in rows:
        got = [c.strip() for c in row.strip().strip("|").split("|")]
        assert len(got) == 5, (row[:60], len(got))
        assert date.match(got[-2]), ("確認日", row[:60], got[-2])
        assert date.match(got[-1]), ("登記日", row[:60], got[-1])


def test_第3件正控_46第1節的舊禁令劃掉保留而新入口是活的():
    """**體例的正控**：舊條文**加刪除線保留**，不是真刪；新條文是活的。

    ⚠️ 為什麼這一條值得單獨有：本輪同時做了兩件相反方向的事 ——
    **廢掉一條禁令**、**立一條帶條件的新規**。
    兩種失敗模式都會讓 `46` 說謊，而且方向相反：
      · 把舊禁令**真的刪掉** → 後人看不出這裡曾經有過一條禁令，也看不出它為什麼被換掉；
      · 舊禁令**忘了劃掉** → 同一節裡一句說「不准補登」、一句說「補登可以」，兩句都像現行。
    這一條把兩邊都釘住。
    ⚠️ 拿掉修復（刪掉舊句、或把它的刪除線拿掉）本條當場轉紅。
    """
    lines = _doc46_lines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("## 1. 登記時機"))
    end = next(i for i, ln in enumerate(lines) if ln.startswith("## 2. "))
    section = lines[start:end]
    assert section, "第 1 節是空的 —— 這一條會變成空掃"

    ban = "不在登記時機之外補登"
    # (a) 舊禁令還在檔裡（保留，不是真刪）。
    assert any(ban in ln for ln in section), "舊禁令不見了 —— 本檔體例是劃掉保留，不是真刪"
    # (b) 而且它是被劃掉的（挖掉刪除線區段之後就找不到了）。
    assert not any(ban in _unstruck(ln) for ln in section), \
        "舊禁令還是活的 —— 同一節裡同時有『不准補登』與『補登可以』兩句"
    # (c) 新入口是活的，而且帶著那個條件。
    live = "\n".join(_unstruck(ln) for ln in section)
    assert "登記日" in live, "新入口沒有提到『登記日』—— 那個條件掉了"
    assert "確認日" in live
    # (d) 體例三件套：政策變更的標註、日期、決策者。
    assert "有意識的政策變更，不是漏刪" in live
    assert "2026-09-24" in live
    assert "客戶" in live


def test_第3件_46沒有留下指向已被改掉的規則的標籤():
    """第 5.5 節其二那個標籤原本寫「明知違反第 1 節第一句……待客戶裁」。

    第 1 節改掉之後，那個標籤指向的規則已經不存在了 ⇒ 標籤必須跟著退役。
    ⚠️ 本條只驗**那個標籤不再是現行標籤**，不驗它被換成了什麼 ——
    換成什麼是人讀的事，**不假裝這一條守得比實際多**。
    ⚠️ **這一條的初版寫錯過一次，就地記下來**：它原本掃「整份檔案的活文字裡
    有沒有那句標籤」，結果**被自己的解說文推翻** —— 那則 2026-09-24 的更正註
    為了說明「這一句為什麼退役」，**必須逐字引它一次**，而那一次引用是活的。
    ⇒ 那是 `CLAUDE.md` §-2.A 第 8 款的形狀：**把要掃的字串寫進文件，它就會自己命中。**
    **現在改成只看有權威性的那一行**（`**現行標籤**：` 開頭的那一行），
    引用與解說不在射程內。**資訊留著，判定收窄到該收的地方。**
    """
    labels = [
        _unstruck(ln) for ln in _doc46_lines()
        if _unstruck(ln).lstrip("- ").startswith("**現行標籤**：")
    ]
    assert labels, "一行『現行標籤』也沒掃到 —— 這一條會變成空掃"
    for label in labels:
        assert "明知違反第 1 節第一句" not in label, ("過期的標籤還是現行標籤", label)
        assert "待客戶裁" not in label, ("已裁的東西還掛著待裁", label)
    # 反空掃：那句話確實還留在檔裡（劃掉保留），不是被整段刪掉。
    raw = "\n".join(_doc46_lines())
    assert "明知違反第 1 節第一句" in raw, "整句被刪掉了 —— 本檔體例是劃掉保留"


def test_第2件_三個新情境的整頁模型逐格釘住():
    """⭐ **補上那張反向控制網的結構性盲點（2026-09-24 稽核指出）。**

    上面那張 108 格的網對第 2 件的新路**結構上是盲的**（十二個情境沒有一個走得到它）。
    在它之外，新路只有四條正控在守，而正控只驗**它們各自斷言的那幾格**；
    新路產出的其餘欄位（說明區其他行、摘要、徽章、按鈕…）**沒有任何東西看著**。

    ⚠️ **這一條刻意不叫「反向控制」** —— 它**不是**拿改動前的值比對
    （那三個情境在 `fd5e41b` 上不存在，沒有「之前」）。
    它是**前向釘樁**：把現行行為整頁逐格釘住，往後任何一次無意的改動都會紅。
    **期望值的正確性由上面那四條正控背書，不由這一條自己背書** —— 據實寫明，不含糊。

    ⚠️ 摘要對不上時看不出**哪裡**不同 —— 代價就地寫明：
       重跑一次逐格 dump 再 diff，**不要直接改期望值**。期望值改了，這條就廢了。
    """
    expected = {
        # ⚠️ 2026-09-24 第二十一輪：客戶裁示取數失敗圖示 ⚠→⛔，受影響格的摘要已換新值（有意識的更正，不是漏刪；hld 燈的紅圖示同輪 ✖→⛔）。
        #    換之前先證明：把現行模型字串裡的 ⛔ 換回原圖示（燈的圖示格換回 ✖、其餘換回 ⚠）再算摘要，本表舊值逐格全數重現（量測日 2026-09-24）；
        #    故差異只有那個圖示。沒被取數失敗碰到的格一格未動。
        ("holdfail", "HLD-0"): ('紅', '系統錯誤', "da6f97c35600"),
        ("holdfail", "HLD-1"): ('紅', '系統錯誤', "6781b2bdacd5"),
        ("holdfail", "HLD-2"): ('中性', 'ok', "6347d81de348"),
        ("holdfail", "HLD-3"): ('紅', '系統錯誤', "1edc467d1985"),
        ("holdfail", "HLD-4"): ('中性', 'ok', "dffae81c35eb"),
        ("holdfail", "HLD-5"): ('中性', 'ok', "77305900bc65"),
        ("holdfail", "HLD-6"): ('中性', 'ok', "cc137930f370"),
        ("holdfail", "HLD-7"): ('中性', 'ok', "0594b2871949"),
        ("holdfail", "HLD-8"): ('黃', '業務例外', "552b13b86b81"),
        ("profilefail", "HLD-0"): ('紅', '系統錯誤', "84b033948b7f"),
        ("profilefail", "HLD-1"): ('中性', 'ok', "057d10d7e5b3"),
        ("profilefail", "HLD-2"): ('紅', '系統錯誤', "020d64867585"),
        ("profilefail", "HLD-3"): ('中性', 'ok', "1d1e3f822996"),
        ("profilefail", "HLD-4"): ('中性', 'ok', "dffae81c35eb"),
        ("profilefail", "HLD-5"): ('中性', 'ok', "77305900bc65"),
        ("profilefail", "HLD-6"): ('中性', 'ok', "cc137930f370"),
        ("profilefail", "HLD-7"): ('中性', 'ok', "0594b2871949"),
        ("profilefail", "HLD-8"): ('黃', '業務例外', "552b13b86b81"),
        ("holdfail_nothr", "HLD-0"): ('紅', '系統錯誤', "e2716e8e35a7"),
        ("holdfail_nothr", "HLD-1"): ('紅', '系統錯誤', "59e8c7ce9c35"),
        ("holdfail_nothr", "HLD-2"): ('中性', 'ok', "6347d81de348"),
        ("holdfail_nothr", "HLD-3"): ('紅', '系統錯誤', "1edc467d1985"),
        ("holdfail_nothr", "HLD-4"): ('中性', 'ok', "3de52cd071ec"),
        ("holdfail_nothr", "HLD-5"): ('中性', 'ok', "77305900bc65"),
        ("holdfail_nothr", "HLD-6"): ('中性', 'ok', "cc137930f370"),
        ("holdfail_nothr", "HLD-7"): ('中性', 'ok', "8c667c291d77"),
        ("holdfail_nothr", "HLD-8"): ('黃', '業務例外', "552b13b86b81"),
    }
    assert len(expected) == 27, len(expected)
    assert {name for name, _ in expected} == {"holdfail", "profilefail", "holdfail_nothr"}
    for (name, code), (tone, state, digest) in expected.items():
        block = logic.find_block(logic.build_page_model(**fixtures.scenario(name)), code)
        assert block["_tone"] == tone, (name, code, "tone", block["_tone"], tone)
        assert block["_state"] == state, (name, code, "state", block["_state"], state)
        assert _cell_digest(block) == digest, (
            name, code, "整格內容變了（狀態與顏色沒變，改的是這一塊裡的其他東西）")


# ═══════ 稽核必修 G：兩條自訂約束原本零測試背書（射程外溢突變存活） ═══════


def test_G1正控_失敗訊息不得蓋掉算得出來的說明():
    """⭐ **本檔自己那段註解寫死的條文，原本沒有任何測試背書。**

    `_build_hld1()` 那段的註解逐字寫著：「**算出來的東西一律留著**……
    把它清掉等於用一個失敗訊息蓋掉還算得出來的事實，**那是另一種說謊**」。
    **實測（稽核）**：把 `detail_lines = detail_lines + [...]` 改成 `= [...]`，
    **262 條全綠存活** —— 那句條文當時只是一段散文。

    ⚠️ 既有的 `test_第2件_算得出來的東西一個也沒有被失敗訊息蓋掉` 擋不住它：
    那一條比的是 `_rows` 與主值，**沒有比說明區**，而被蓋掉的正是說明區。
    ⚠️ 拿掉修復（把那個 `+` 拿掉）本條當場轉紅。
    """
    failed = logic.find_block(logic.build_page_model(**fixtures.scenario("holdfail")), "HLD-1")
    clean = logic.find_block(logic.build_page_model(**fixtures.scenario("full")), "HLD-1")
    assert clean["detail_lines"], "對照組說明區是空的 —— 這一條會變成空掃"
    # 沒有失敗時就有的每一行，失敗之後**一行都不准少、順序不准變**。
    assert failed["detail_lines"][: len(clean["detail_lines"])] == clean["detail_lines"], (
        clean["detail_lines"], failed["detail_lines"])
    # 而且失敗訊息是**加在後面**，不是取而代之。
    assert len(failed["detail_lines"]) > len(clean["detail_lines"])
    assert any(fixtures.FETCH_FAIL_MESSAGE in line for line in failed["detail_lines"])


def test_G2正控_同一句失敗訊息在同一塊只印一次():
    """⭐ **`_build_core_card()` 的 `if line not in error_lines` 原本從沒被走過。**

    **實測（稽核）**：拿掉那句去重，**262 條全綠存活** ——
    因為在 `twofail` 之前，**十六個情境沒有任何一個同時有兩張表失敗**。
    ⇒ 與稽核必修 B 是同一種結構性盲點：**程式碼裡有一條路，而測試資料走不到它。**

    ⚠️ 拿掉修復（刪掉那句 `if line not in error_lines`）本條當場轉紅。
    """
    ds = fixtures.scenario("twofail")["dataset"]
    # 先釘前提：這一組真的有兩張表同時失敗，而且訊息一模一樣。
    errs = {k: v for k, v in ds["errors"].items() if v}
    assert len(errs) == 2, errs
    assert len(set(errs.values())) == 1, errs
    # 而且那兩張表真的都在 `HLD-3` 的來源欄裡（否則這一條驗不到去重）。
    assert set(errs) <= set(logic.BLOCK_SOURCE_TABLES["HLD-3"]), (
        sorted(errs), logic.BLOCK_SOURCE_TABLES["HLD-3"])

    block = logic.find_block(logic.build_page_model(**fixtures.scenario("twofail")), "HLD-3")
    lines = block["detail_lines"]
    hits = [line for line in lines if fixtures.FETCH_FAIL_MESSAGE in line]
    assert len(hits) == 1, hits
    assert lines.count("訊息原文照印，不改寫成安撫語句。") == 1, lines


def test_第3件_既有六列是補登_兩個日期不同():
    """⭐ **稽核必修 D 的正控。**

    `46` 第 2 節自己寫死：「**兩者相同 ⇒ 這一列是在登記時機當下寫的；
    兩者不同 ⇒ 這一列是補登的**」。
    而那六列**確實是補登的**（查 git：三層確認釘 `a7f8c1b`＝2026-09-23，
    六列寫進本表是在 `fd5e41b`＝2026-09-24）。

    ⛔ **本條擋的是本輪自己犯過的那個錯**：初版把兩欄都填成 2026-09-23，
    於是**一份為了讓補登合法而改寫的條文，第一個例子把補登記成了非補登** ——
    而它當時之所以看起來合理，是因為引了本表自己的一則註記當佐證（**循環引用**）。
    ⚠️ 拿掉修復（把登記日改回與確認日同值）本條當場轉紅。

    ⚠️ **本條不驗「2026-09-24 是不是正確的那一天」** —— 那取決於 git，
    而本檔不跑 git。**不假裝這一條守得比實際多。** 它驗的是
    「這六列被標成補登」這個**表內事實**與第 2 節的定義一致。
    """
    _, rows = _doc46_registry_rows()
    assert len(rows) == 6, len(rows)
    for row in rows:
        got = [c.strip() for c in row.strip().strip("|").split("|")]
        confirmed, registered = got[-2], got[-1]
        assert confirmed != registered, (
            "這一列的兩個日期同值 ⇒ 依 `46` 第 2 節就是『在登記時機當下寫的』，"
            "但這六列是補登的", row[:70])
        assert confirmed < registered, ("確認日不該晚於登記日", row[:70])
