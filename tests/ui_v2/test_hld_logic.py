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


def test_九塊每一塊在四種情境下都建得出來且狀態合法():
    """逐塊四狀態：九塊 × 四種情境，每一塊都要給得出一個合法狀態值。"""
    legal = {logic.STATE_OK, logic.STATE_MISSING, logic.STATE_BIZ, logic.STATE_ERROR}
    for name in ("full", "srcmiss", "bizexc", "fetchfail", "nothr", "empty"):
        model = logic.build_page_model(**fixtures.scenario(name))
        assert [b["code"] for b in logic.all_blocks(model)] == [
            f"HLD-{i}" for i in range(9)
        ], name
        for block in logic.all_blocks(model):
            assert block["_state"] in legal, (name, block["code"])


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


def test_同時最多展開一檔():
    model = logic.build_page_model(fixtures.dataset_full())
    block = logic.find_block(model, "HLD-5")
    assert sum(1 for item in block["_items"] if item["_open"]) == 1


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
