# -*- coding: utf-8 -*-
"""市場總覽（MKT）純邏輯測試。

測試先行：本檔先於 ui_v2/mkt/logic.py 寫成並跑出紅燈。

引用範圍（客戶裁示）：只引 docs/v2/44_fund_ui_ssot.md（SSOT）與
docs/v2/47_fund_wireframe_mkt.md（線框）。兩份對同一塊有不同說法以 44 為準。

⚠️ 斷點數值一律用 44 第二節第一小節的現行宣告
（≤768 單欄／769-1279 兩欄／≥1280 三欄）。47 的三個斷點小節標題仍寫
1024／640，那兩個值已由客戶廢棄（44 §2.1 逐字：「1024 / 640 廢棄，未量過裝置」）。

本檔不 import streamlit，也不 import 任何舊 repo 模組。
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ui_v2.mkt import fixtures, logic  # noqa: E402


# ───────────────────────── 四狀態（逐主值） ─────────────────────────


def test_四狀態的字面值就是SSOT卡片那四個():
    assert logic.STATE_OK == "ok"
    assert logic.STATE_MISSING == "資料未備"
    assert logic.STATE_BIZ == "業務例外"
    assert logic.STATE_ERROR == "系統錯誤"


def test_主值狀態_ok():
    obs = fixtures.observation("vol_index", value_num=18.4, value_unit="index")
    assert logic.main_value_state([obs], expected_unit="index") == logic.STATE_OK


def test_主值狀態_資料未備_是沒有任何一筆():
    assert logic.main_value_state([], expected_unit="index") == logic.STATE_MISSING
    assert logic.main_value_state(None, expected_unit="index") == logic.STATE_MISSING


def test_主值狀態_業務例外_是單位不符():
    obs = fixtures.observation("fx_twd_per_usd", value_num=31.5, value_unit="TWD")
    assert (
        logic.main_value_state([obs], expected_unit="新臺幣／美元")
        == logic.STATE_BIZ
    )


def test_主值狀態_系統錯誤_蓋過其他三態():
    obs = fixtures.observation("vol_index", value_num=18.4, value_unit="index")
    assert (
        logic.main_value_state([obs], expected_unit="index", error="HTTP 503")
        == logic.STATE_ERROR
    )
    # 連一筆都沒有、又有錯誤訊息時，仍是系統錯誤（失敗比缺資料更該說出來）
    assert logic.main_value_state([], expected_unit="index", error="HTTP 503") == (
        logic.STATE_ERROR
    )


def test_逐主值判定_一個缺一個在_卡片不整塊空掉且掛部分缺徽章():
    """SSOT 5.1 元件判準逐字：其中一個主值設為 `資料未備`、另一個留在 `ok`，
    出現數字的主值位置剛好一處、未備的那個位置出現 `⬜ 資料未備`、標題出現「部分缺」徽章。"""
    model = logic.build_page_model(fixtures.dataset_mkt1_one_key_missing())
    card = logic.find_block(model, "MKT-1")

    states = [mv["_state"] for mv in card["main_values"]]
    assert sorted(states) == sorted([logic.STATE_OK, logic.STATE_MISSING])

    with_number = [mv for mv in card["main_values"] if mv["_has_number"]]
    assert len(with_number) == 1

    missing = [mv for mv in card["main_values"] if mv["_state"] == logic.STATE_MISSING]
    assert missing[0]["value_text"] == "⬜ 資料未備"

    badge_texts = [b["text"] for b in card["badges"]]
    assert "部分缺" in badge_texts


def test_逐主值判定_兩個主值都未備_整塊不出任何數字():
    model = logic.build_page_model(fixtures.dataset_mkt1_both_keys_missing())
    card = logic.find_block(model, "MKT-1")
    assert not any(mv["_has_number"] for mv in card["main_values"])


# ───────────────────────── 斷點 → 欄數 ─────────────────────────


def test_斷點四個邊界值():
    """44 §2.1 客戶最終版：≤768 單欄／769-1279 兩欄／≥1280 三欄。"""
    assert logic.columns_for_width(768) == 1
    assert logic.columns_for_width(769) == 2
    assert logic.columns_for_width(1279) == 2
    assert logic.columns_for_width(1280) == 3


def test_斷點_節判準那六個寬度():
    """44 §2.1 節判準逐字：1280、1279、769、768、375、374 → 三、二、二、一、一、一。"""
    widths = [1280, 1279, 769, 768, 375, 374]
    assert [logic.columns_for_width(w) for w in widths] == [3, 2, 2, 1, 1, 1]


def test_斷點_1024與640對不到任何一段的分界():
    """44 §2.1 節判準逐字：把 1024 與 640 兩個字面值拿去對排法宣告，對不到任何一段。
    驗法：那兩個值的左右鄰居欄數相同 ＝ 它們不是分界。"""
    for abolished in (1024, 640):
        assert logic.columns_for_width(abolished - 1) == logic.columns_for_width(
            abolished
        )


def test_各層的欄數():
    """44 §2.1：層 1 與層 4 恆單欄滿寬；層 3 五頁各只有兩塊。"""
    for width in (374, 768, 769, 1279, 1280, 1920):
        assert logic.layer_columns(1, width) == 1
        assert logic.layer_columns(4, width) == 1
    assert logic.layer_columns(2, 1280) == 3
    assert logic.layer_columns(2, 769) == 2
    assert logic.layer_columns(2, 768) == 1
    # 層 3 只有兩塊：≥1280 時兩塊並排同一列（第三欄空著）
    assert logic.layer_columns(3, 1280) == 2
    assert logic.layer_columns(3, 769) == 2
    assert logic.layer_columns(3, 768) == 1


# ───────────────────────── 空狀態文案（逐字） ─────────────────────────


def test_來源缺文案模板_逐字():
    """SSOT 5.5：`⬜ 資料未備：<來源鍵> 尚無資料`。"""
    assert (
        logic.empty_source_text(["vol_index", "credit_spread_pct"])
        == "⬜ 資料未備：vol_index 與 credit_spread_pct 尚無資料"
    )
    assert logic.empty_source_text(["leading_index"]) == "⬜ 資料未備：leading_index 尚無資料"


def test_不適用文案模板_逐字():
    assert logic.not_applicable_text("單位不符") == "⬜ 不適用：單位不符"
    assert (
        logic.not_applicable_text("觀察窗起點早於序列第一筆")
        == "⬜ 不適用：觀察窗起點早於序列第一筆"
    )
    assert logic.not_applicable_text("可用筆數不足 6") == "⬜ 不適用：可用筆數不足 6"
    assert logic.not_applicable_text("尚未設定觀察窗") == "⬜ 不適用：尚未設定觀察窗"
    assert (
        logic.not_applicable_text("取得時間早於觀測日")
        == "⬜ 不適用：取得時間早於觀測日"
    )


def test_取數失敗文案模板_逐字_且訊息原文不改寫不截斷():
    raw = "HTTPSConnectionPool(host='example.invalid', port=443): Max retries exceeded"
    assert logic.fetch_failed_text(raw) == "⚠ 取數失敗：" + raw


def test_部分缺的起迄那一行_逐字():
    assert logic.partial_range_text("2026-01-01", "2026-03-31") == "缺 2026-01-01 至 2026-03-31"


def test_未設定觀察窗時三張核心卡的副標逐字():
    model = logic.build_page_model(fixtures.dataset_all_ok(), window_days=None, baseline_date=None)
    for code in ("MKT-1", "MKT-2", "MKT-3"):
        card = logic.find_block(model, code)
        assert "⬜ 不適用：尚未設定觀察窗" in card["detail_lines"]


# ───────────────────────── 結論燈 ─────────────────────────


def test_結論燈_三塊皆齊_灰燈且文案不含任何一張卡的名字():
    model = logic.build_page_model(fixtures.dataset_all_ok())
    light = logic.find_block(model, "MKT-0")
    assert light["_tone"] == "灰"
    assert light["text"] == "三張卡的資料齊"
    for name in ("風險情緒卡", "景氣位置卡", "資金與匯率卡"):
        assert name not in light["text"]
    assert light["buttons"] == []


def test_結論燈_抽掉MKT2的來源_由灰轉黃且點名MKT2():
    """44 MKT-0 判準逐字：把 `MKT-2` 的來源抽掉，結論燈由灰轉黃且文案點名 `MKT-2`。"""
    model = logic.build_page_model(fixtures.dataset_mkt2_both_keys_missing())
    light = logic.find_block(model, "MKT-0")
    assert light["_tone"] == "黃"
    assert light["text"] == "景氣位置卡：資料未備"


def test_結論燈_業務例外也是黃():
    model = logic.build_page_model(fixtures.dataset_mkt3_unit_mismatch())
    light = logic.find_block(model, "MKT-0")
    assert light["_tone"] == "黃"
    assert light["text"] == "資金與匯率卡：不適用"


def test_結論燈_系統錯誤是紅且蓋過黃():
    model = logic.build_page_model(fixtures.dataset_mkt1_fetch_failed())
    light = logic.find_block(model, "MKT-0")
    assert light["_tone"] == "紅"
    assert light["text"] == "風險情緒卡：取數失敗"


def test_結論燈_三塊皆無資料_灰燈加重新取數按鈕():
    """44 MKT-0 空狀態逐字：三塊皆無資料 → 燈為灰，文案「本頁三張卡皆未取到資料」，
    並掛一枚「重新取數」按鈕。"""
    model = logic.build_page_model(fixtures.dataset_all_empty())
    light = logic.find_block(model, "MKT-0")
    assert light["_tone"] == "灰"
    assert light["text"] == "本頁三張卡皆未取到資料"
    assert [b["label"] for b in light["buttons"]] == ["重新取數"]


def test_結論燈本身不出任何數字():
    for ds in fixtures.all_datasets().values():
        light = logic.find_block(logic.build_page_model(ds), "MKT-0")
        assert light.get("main_values", []) == []


def test_副標不適用不改變卡片狀態值_燈維持灰():
    """47 D-21 的讀法：副標進不適用時主值仍 ok，故結論燈維持灰。"""
    model = logic.build_page_model(fixtures.dataset_all_ok(), window_days=None, baseline_date=None)
    assert logic.find_block(model, "MKT-0")["_tone"] == "灰"


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


def test_全頁狀態徽章都落在七個之內():
    """SSOT 5.2 元件判準逐字：kind 為 `狀態` 的徽章 text 沒有一項落在七個字面值之外。"""
    for name, ds in fixtures.all_datasets().items():
        model = logic.build_page_model(ds)
        for badge in logic.collect_badges(model):
            if badge["_kind"] == "狀態":
                assert badge["text"] in logic.STATUS_BADGE_LITERALS, (name, badge)


def test_紅線徽章只有三個標記且不掛在數值旁():
    model = logic.build_page_model(fixtures.dataset_all_ok())
    redline = [b for b in logic.collect_badges(model) if b["_kind"] == "紅線"]
    assert redline, "本頁 G3† 落點在 MKT-4 與 MKT-5 的說明區"
    for badge in redline:
        assert badge["text"] in ("G1†", "G2†", "G3†")
        assert badge["_slot"] == "說明區"


def test_來源徽章中性不著色():
    model = logic.build_page_model(fixtures.dataset_all_ok())
    for badge in logic.collect_badges(model):
        if badge["_kind"] == "來源":
            assert badge["_tone"] == "中性"


def test_新鮮度_延遲日數是取得日減觀測日_日曆日():
    assert logic.delay_days("2026-09-19", "2026-09-22T03:00:00Z") == 3
    assert logic.delay_days("2026-09-22", "2026-09-22T23:00:00Z") == 0
    assert logic.delay_days("2026-09-22", "2026-09-21T23:00:00Z") == -1


def test_新鮮度徽章_延遲N日_有定義時才出字():
    assert logic.freshness_badge_text(3) == "延遲 3 日"
    assert logic.freshness_badge_text(1) == "延遲 1 日"
    # 即時／當日的門檻 SSOT 未定義（47 Q-05）→ 不自行發明門檻
    assert logic.freshness_badge_text(0) is None
    assert logic.freshness_badge_text(-1) is None


# ───────────────────────── 按鈕與輸入欄（紅線 G1† / G3†） ─────────────────────────


def test_所有按鈕標籤不含四個禁詞():
    """44 §1.1 節判準逐字：沒有一列的標籤含「一鍵」「最佳」「推薦」「最適」。"""
    for name, ds in fixtures.all_datasets().items():
        for button in logic.collect_buttons(logic.build_page_model(ds)):
            for word in ("一鍵", "最佳", "推薦", "最適"):
                assert word not in button["label"], (name, button)


def test_所有按鈕的action_kind落在八類之內且不寫四張表():
    eight = ("取數", "套用", "展開", "匯出", "新增列", "清除", "導覽", "存檔")
    for ds in fixtures.all_datasets().values():
        for button in logic.collect_buttons(logic.build_page_model(ds)):
            assert button["_action_kind"] in eight
            assert button["_writes"] & {"holding", "policy", "nav", "dividend"} == set()


def test_存檔只寫user_setting():
    model = logic.build_page_model(fixtures.dataset_all_ok())
    saves = [b for b in logic.collect_buttons(model) if b["_action_kind"] == "存檔"]
    assert saves, "MKT-4 依 44 本輪擴寫掛兩枚按鈕，套用與存檔並存"
    for button in saves:
        assert button["_writes"] == {"user_setting"}


def test_套用只讀輸入不寫任何表():
    model = logic.build_page_model(fixtures.dataset_all_ok())
    applies = [b for b in logic.collect_buttons(model) if b["_action_kind"] == "套用"]
    assert applies
    for button in applies:
        assert button["_writes"] == set()


def test_存檔在兩欄皆未填時停用且附停用原因():
    """44 MKT-4 空狀態逐字：此時「存檔」停用，停用原因為「兩個欄位皆未填」。"""
    model = logic.build_page_model(fixtures.dataset_all_ok(), window_days=None, baseline_date=None)
    save = [b for b in logic.collect_buttons(model) if b["_action_kind"] == "存檔"][0]
    assert save["_enabled"] is False
    assert save["disabled_reason"] == "兩個欄位皆未填"


def test_按鈕停用時不隱藏():
    model = logic.build_page_model(fixtures.dataset_all_ok(), window_days=None, baseline_date=None)
    disabled = [b for b in logic.collect_buttons(model) if not b["_enabled"]]
    assert disabled
    for button in disabled:
        assert button["_visible"] is True
        assert button["disabled_reason"]


def test_沒有任何輸入欄帶非空預設值():
    """44 §1.1 節判準逐字：沒有一列帶有非空的預設值。"""
    for ds in fixtures.all_datasets().values():
        inputs = logic.collect_inputs(logic.build_page_model(ds))
        assert inputs
        for field in inputs:
            assert field["_default"] is None, field


def test_負數或零_不套用也不存檔且主值不變():
    """44 MKT-4 空狀態逐字：輸入為負數或零 → 「日數為正整數」，不套用也不存檔。"""
    ok = logic.build_page_model(fixtures.dataset_all_ok(), window_days=30, baseline_date="2026-06-30")
    bad = logic.build_page_model(fixtures.dataset_all_ok(), window_days=-5, baseline_date="2026-06-30")
    block = logic.find_block(bad, "MKT-4")
    assert "日數為正整數" in block["detail_lines"]
    assert block["_applied"] is False
    assert block["_saved"] is False
    baseline = logic.build_page_model(fixtures.dataset_all_ok(), window_days=None, baseline_date=None)
    for code in ("MKT-1", "MKT-2", "MKT-3"):
        bad_values = [mv["value_text"] for mv in logic.find_block(bad, code)["main_values"]]
        base_values = [mv["value_text"] for mv in logic.find_block(baseline, code)["main_values"]]
        ok_values = [mv["value_text"] for mv in logic.find_block(ok, code)["main_values"]]
        assert bad_values == base_values == ok_values  # 主值不隨觀察窗改變


def test_MKT5是唯讀勾選_沒有存檔按鈕():
    """44 MKT-5 的來源欄只宣告讀，沒有宣告寫入對象（對照 MKT-4 本輪補的寫入對象宣告）。
    47 Q-08 亦登記本頁勾選無寫回路徑。照現況做成唯讀，不自行補一枚存檔鈕。"""
    model = logic.build_page_model(fixtures.dataset_all_ok())
    block = logic.find_block(model, "MKT-5")
    assert block["buttons"] == []
    assert block["_readonly"] is True


def test_MKT5勾選上限六_第七項停用且附原因():
    model = logic.build_page_model(fixtures.dataset_all_ok(), selected_keys=fixtures.SIX_KEYS)
    block = logic.find_block(model, "MKT-5")
    over = [item for item in block["_items"] if not item["_enabled"]]
    assert over, "六個已勾滿時，其餘項目停用"
    for item in over:
        assert item["disabled_reason"]


def test_MKT5一個也沒勾_三張核心卡顯示尚未選定任何指標():
    model = logic.build_page_model(fixtures.dataset_all_ok(), selected_keys=[])
    for code in ("MKT-1", "MKT-2", "MKT-3"):
        card = logic.find_block(model, code)
        joined = " ".join(card["detail_lines"] + [mv["value_text"] for mv in card["main_values"]])
        assert "尚未選定任何指標" in joined
        assert "0" not in [mv["value_text"] for mv in card["main_values"]]


# ───────────────────────── 逐塊規則 ─────────────────────────


def test_MKT2_不足六筆_副標不適用而主值照出():
    model = logic.build_page_model(fixtures.dataset_mkt2_only_five_rows())
    card = logic.find_block(model, "MKT-2")
    assert "⬜ 不適用：可用筆數不足 6" in card["detail_lines"]
    assert any(mv["_has_number"] for mv in card["main_values"])


def test_MKT2_公布日晚於基準日的筆數被排除且副標寫出筆數():
    model = logic.build_page_model(
        fixtures.dataset_mkt2_one_row_after_baseline(), baseline_date="2026-06-30", window_days=30
    )
    card = logic.find_block(model, "MKT-2")
    assert any("排除" in line for line in card["detail_lines"])


def test_MKT2方向文案只有同向與分歧兩句():
    for ds_name in ("dataset_all_ok", "dataset_mkt2_diverging"):
        model = logic.build_page_model(getattr(fixtures, ds_name)(), window_days=30, baseline_date="2026-09-30")
        card = logic.find_block(model, "MKT-2")
        hits = [line for line in card["detail_lines"] if line in ("兩者同向", "兩者分歧")]
        assert len(hits) == 1, ds_name


def test_MKT3_單位不符_該數不適用且副標印出來源給的單位字面值():
    model = logic.build_page_model(fixtures.dataset_mkt3_unit_mismatch())
    card = logic.find_block(model, "MKT-3")
    bad = [mv for mv in card["main_values"] if mv["_state"] == logic.STATE_BIZ]
    assert len(bad) == 1
    assert bad[0]["value_text"] == "⬜ 不適用：單位不符"
    assert any("TWD" in line for line in card["detail_lines"])
    # 另一個主值照畫
    assert any(mv["_has_number"] for mv in card["main_values"])


def test_MKT3匯率不顯示倒數且卡上明寫方向():
    model = logic.build_page_model(fixtures.dataset_all_ok())
    card = logic.find_block(model, "MKT-3")
    fx = [mv for mv in card["main_values"] if mv["_source_key"] == "fx_twd_per_usd"][0]
    assert fx["unit_text"] == "新臺幣／美元"
    assert "1 美元" in " ".join(card["detail_lines"] + [fx.get("direction_text", "")])


def test_MKT6欄序固定且不依數值排序():
    model = logic.build_page_model(fixtures.dataset_all_ok())
    block = logic.find_block(model, "MKT-6")
    assert block["_columns"] == (
        "indicator_key",
        "obs_date",
        "release_date",
        "value_num",
        "value_unit",
        "source_tier",
        "fetched_at",
        "is_revised",
    )
    rows_in = fixtures.dataset_all_ok()["rows"]
    assert [r["indicator_key"] for r in block["_rows"]] == [r["indicator_key"] for r in rows_in]


def test_MKT6修正過的列掛修正過徽章():
    model = logic.build_page_model(fixtures.dataset_revised_row())
    block = logic.find_block(model, "MKT-6")
    flagged = [r for r in block["_rows"] if r.get("_row_badge") == "修正過"]
    assert len(flagged) == 1


def test_MKT6單位直接印字面值不做換算():
    model = logic.build_page_model(fixtures.dataset_unknown_unit_literal())
    block = logic.find_block(model, "MKT-6")
    assert any(r["value_unit"] == "basis_point" for r in block["_rows"])


def test_MKT6無任何列_尚無任何觀測():
    model = logic.build_page_model(fixtures.dataset_all_empty())
    block = logic.find_block(model, "MKT-6")
    assert "尚無任何觀測" in " ".join(block["detail_lines"] + [block["summary_text"]])


def test_MKT7取得時間早於觀測日_延遲欄不適用而不是負數():
    model = logic.build_page_model(fixtures.dataset_fetched_before_obs())
    block = logic.find_block(model, "MKT-7")
    cells = [row["delay_text"] for row in block["_rows"]]
    assert "⬜ 不適用：取得時間早於觀測日" in cells
    for cell in cells:
        assert not cell.lstrip().startswith("-")


def test_MKT7表頭註明時區字面值():
    model = logic.build_page_model(fixtures.dataset_all_ok())
    block = logic.find_block(model, "MKT-7")
    assert any("UTC" in line for line in block["detail_lines"])


# ───────────────────────── 層次與預設展開 ─────────────────────────


def test_四層的塊代號分派():
    model = logic.build_page_model(fixtures.dataset_all_ok())
    assert logic.codes_in_layer(model, 1) == ["MKT-0"]
    assert logic.codes_in_layer(model, 2) == ["MKT-1", "MKT-2", "MKT-3"]
    assert logic.codes_in_layer(model, 3) == ["MKT-4", "MKT-5"]
    assert logic.codes_in_layer(model, 4) == ["MKT-6", "MKT-7"]


def test_預設展開的剛好是結論燈與三張核心卡():
    """SSOT 5.4 元件判準逐字：初次載入任一頁，default_open 為真的區塊剛好是結論燈與 3 張核心卡。"""
    model = logic.build_page_model(fixtures.dataset_all_ok())
    opened = [b["code"] for b in logic.all_blocks(model) if b["_default_open"]]
    assert opened == ["MKT-0", "MKT-1", "MKT-2", "MKT-3"]


def test_資料缺時層三層四仍維持收合():
    """SSOT 5.4 禁止逐字：展開區不自動展開 —— 沒有任何資料狀態會讓收合區自己打開。"""
    for ds in fixtures.all_datasets().values():
        model = logic.build_page_model(ds)
        for block in logic.all_blocks(model):
            if block["_layer"] in (3, 4):
                assert block["_default_open"] is False


def test_收合摘要在資料缺時寫出缺什麼():
    model = logic.build_page_model(fixtures.dataset_all_empty())
    for code in ("MKT-6", "MKT-7"):
        assert logic.find_block(model, code)["summary_text"]


def test_空狀態不整塊隱藏_塊標題留著():
    model = logic.build_page_model(fixtures.dataset_all_empty())
    for code in ("MKT-0", "MKT-1", "MKT-2", "MKT-3", "MKT-4", "MKT-5", "MKT-6", "MKT-7"):
        assert logic.find_block(model, code)["title"]


# ───────────────────────── 紅線字表掃描 ─────────────────────────


def test_禁方向詞字表_全頁零命中():
    """44 §1.2 節判準逐字：把介面全頁文字抓成一份字串，上列方向詞一個也對不上。"""
    for name, ds in fixtures.all_datasets().items():
        for window in (None, 30):
            model = logic.build_page_model(ds, window_days=window, baseline_date="2026-06-30")
            hits = logic.scan_forbidden(logic.collect_ui_strings(model))
            assert hits == {}, (name, window, hits)


def test_禁箭頭_全頁零命中():
    for ds in fixtures.all_datasets().values():
        text = "".join(logic.collect_ui_strings(logic.build_page_model(ds)))
        for arrow in ("↑", "↓", "▲", "▼"):
            assert arrow not in text


def test_期間變化以正負號與數字寫出_不配箭頭():
    assert logic.format_signed(-2.3, 1) == "-2.3"
    assert logic.format_signed(2.3, 1) == "+2.3"
    assert logic.format_signed(0.0, 2) == "+0.00"
    for arrow in ("↑", "↓", "▲", "▼"):
        assert arrow not in logic.format_signed(-2.3, 1)


def test_禁排名冠詞_不出現在任何畫面文案():
    for ds in fixtures.all_datasets().values():
        text = "".join(logic.collect_ui_strings(logic.build_page_model(ds)))
        for word in ("精選", "推薦", "最佳", "首選", "優選", "最適"):
            assert word not in text


def test_禁輸出_不出現買賣指示目標價最佳配置預期報酬():
    for ds in fixtures.all_datasets().values():
        text = "".join(logic.collect_ui_strings(logic.build_page_model(ds)))
        for word in ("目標價", "最佳配置", "預期報酬", "買賣指示"):
            assert word not in text


def test_顏色只映射資料狀態與新鮮度_主值正負號相反時顏色相同():
    """44 §1.2 節判準逐字：把同一塊在「資料齊」下的主值換成一個正負號相反的數，
    兩張圖的主值區顏色相同。"""
    positive = logic.build_page_model(fixtures.dataset_all_ok(sign=+1))
    negative = logic.build_page_model(fixtures.dataset_all_ok(sign=-1))
    for code in ("MKT-1", "MKT-2", "MKT-3"):
        a = [mv["_tone"] for mv in logic.find_block(positive, code)["main_values"]]
        b = [mv["_tone"] for mv in logic.find_block(negative, code)["main_values"]]
        assert a == b


def test_四狀態各自的顏色照SSOT第五節卡片那張表():
    assert logic.tone_for_state(logic.STATE_OK) == "中性"
    assert logic.tone_for_state(logic.STATE_MISSING) == "灰"
    assert logic.tone_for_state(logic.STATE_BIZ) == "黃"
    assert logic.tone_for_state(logic.STATE_ERROR) == "紅"


def test_空狀態不顯示零也不顯示上一期的值():
    model = logic.build_page_model(fixtures.dataset_mkt1_one_key_missing())
    card = logic.find_block(model, "MKT-1")
    for mv in card["main_values"]:
        if mv["_state"] != logic.STATE_OK:
            assert mv["_has_number"] is False
            assert mv["value_text"] in ("⬜ 資料未備", "⬜ 不適用", "⚠ 取數失敗") or mv[
                "value_text"
            ].startswith(("⬜ ", "⚠ "))


def test_空狀態不把沒有資料寫成沒有風險():
    for ds in fixtures.all_datasets().values():
        text = "".join(logic.collect_ui_strings(logic.build_page_model(ds)))
        for word in ("沒有風險", "表現平穩", "市場平靜", "市場危險"):
            assert word not in text


# ───────────────────────── 邊界說明區（本頁不負責什麼） ─────────────────────────


def test_頁尾三行指路逐字():
    model = logic.build_page_model(fixtures.dataset_all_ok())
    assert model["footer_lines"][:3] == [
        "這個問題在持倉體檢",
        "這個問題在標的探索",
        "這個問題在資產配置",
    ]


def test_本頁沒有任何一塊碰到基金代碼或持倉():
    for ds in fixtures.all_datasets().values():
        text = "".join(logic.collect_ui_strings(logic.build_page_model(ds)))
        for word in ("基金代碼", "持倉明細", "我的持股"):
            assert word not in text


# ───────────────────────── 零外部相依 ─────────────────────────


def test_logic與fixtures都沒有import_streamlit或舊repo模組():
    import ui_v2.mkt.fixtures as f
    import ui_v2.mkt.logic as g
    import ui_v2.mkt.theme as t

    for module in (f, g, t):
        source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        for banned in ("import streamlit", "import pandas", "import numpy"):
            assert banned not in source, (module.__name__, banned)


# ───────── 兩枚按鈕各做一件事（`44` MKT-4 本輪擴寫；由實跑 app 抓出的迴歸） ─────────


def test_填了值但還沒按套用時_存檔仍可按():
    """回歸：存檔原本被綁在「已套用」那一組值上，於是「填了值、還沒按套用」時誤停用 ——
    那等於把 44 剛拆開的兩枚按鈕又綁回一枚。"""
    model = logic.build_page_model(
        fixtures.dataset_all_ok(),
        window_days=None,
        baseline_date=None,
        field_window_days=30,
        field_baseline_date="2026-09-20",
    )
    save = [b for b in logic.collect_buttons(model) if b["_action_kind"] == "存檔"][0]
    assert save["_enabled"] is True
    assert save["disabled_reason"] == ""


def test_只按存檔不按套用_三張核心卡不重算():
    """`44` MKT-4 逐字：「存檔」把值寫回 user_setting，不重算三張核心卡。"""
    unapplied = logic.build_page_model(
        fixtures.dataset_all_ok(),
        window_days=None,
        baseline_date=None,
        field_window_days=30,
        field_baseline_date="2026-09-20",
    )
    applied = logic.build_page_model(
        fixtures.dataset_all_ok(), window_days=30, baseline_date="2026-09-20"
    )
    for code in ("MKT-1", "MKT-2", "MKT-3"):
        card = logic.find_block(unapplied, code)
        assert "⬜ 不適用：尚未設定觀察窗" in card["detail_lines"]
        assert "⬜ 不適用：尚未設定觀察窗" not in logic.find_block(applied, code)["detail_lines"]


def test_欄位值不合格時存檔停用且原因就是那一句說明():
    model = logic.build_page_model(
        fixtures.dataset_all_ok(),
        window_days=None,
        baseline_date=None,
        field_window_days=0,
        field_baseline_date="2026-09-20",
    )
    save = [b for b in logic.collect_buttons(model) if b["_action_kind"] == "存檔"][0]
    assert save["_enabled"] is False
    assert save["disabled_reason"] == "日數為正整數"
    assert "日數為正整數" in logic.find_block(model, "MKT-4")["detail_lines"]


# ═══════════ 第 1 件｜拆掉自創的嚴重度先後（客戶 2026-09-24 裁示） ═══════════


def test_44只排過一次序而且把中間兩個並列同級():
    """先把**前提**釘住：本件整件事建立在「`44` 只排過一次、而且那一次並列」上。

    沒有這一條，下面每一條都只是在驗「我寫的程式照我寫的規格跑」。
    這一條驗的是規格本身 —— 直接讀 `44` :310 那一行。
    """
    line = (pathlib.Path(__file__).resolve().parents[2]
            / "docs" / "v2" / "44_fund_ui_ssot.md").read_text(encoding="utf-8").split("\n")[309]
    assert "三塊狀態取最差者" in line
    # 那兩個被寫在**同一條**規則裡、指向**同一個**結果（黃）。
    assert "任一塊為 `資料未備` 或 `業務例外` → 燈為黃" in line
    # 而 `系統錯誤` 另有自己的一條，結果不同（紅）⇒ 級數是三級，不是四級。
    assert "任一塊為 `系統錯誤` → 燈為紅" in line
    # 反向：`44` 全檔沒有第二處把這兩個排出先後。
    d44 = (pathlib.Path(__file__).resolve().parents[2]
           / "docs" / "v2" / "44_fund_ui_ssot.md").read_text(encoding="utf-8").split("\n")
    both = [i + 1 for i, ln in enumerate(d44) if "資料未備" in ln and "業務例外" in ln]
    assert both, "一行也沒掃到 —— 這一條會變成空掃"
    assert 310 in both, both


def test_三級而不是四級_而且哨符不是第五個狀態():
    assert logic._BAND == {
        logic.STATE_OK: 0,
        logic.STATE_MISSING: 1,
        logic.STATE_BIZ: 1,
        logic.STATE_ERROR: 2,
    }
    # 哨符**刻意不在** `_BAND` 裡 —— 收進去就等於承認它是第五個狀態。
    assert logic.STATE_UNRANKED not in logic._BAND
    # 但它答得出「哪一級」（`44` 把那兩個放同一級，所以級是確定的）。
    assert logic._band(logic.STATE_UNRANKED) == logic._band(logic.STATE_MISSING)
    assert logic._band(logic.STATE_UNRANKED) == logic._band(logic.STATE_BIZ)
    # 它也不得混進四狀態的封閉列舉。
    assert logic.STATE_UNRANKED not in {
        logic.STATE_OK, logic.STATE_MISSING, logic.STATE_BIZ, logic.STATE_ERROR
    }


def test_同級時不替44排先後_回哨符而不是挑一個():
    """**第 1 件的正控。** 兩者同時是最差 → 不回答。

    ⚠️ 拿掉修復（把 `worst_state()` 改回 `max(states, key=_SEVERITY.__getitem__)`，
    或把 `_BAND` 的 `STATE_BIZ` 改回 2）本條當場轉紅。
    """
    assert logic.worst_state([logic.STATE_MISSING, logic.STATE_BIZ]) is logic.STATE_UNRANKED
    assert logic.worst_state([logic.STATE_BIZ, logic.STATE_MISSING]) is logic.STATE_UNRANKED
    # 只有一個成員在最高級 → 照回那一個（既有行為，一格未動）。
    assert logic.worst_state([logic.STATE_OK, logic.STATE_MISSING]) == logic.STATE_MISSING
    assert logic.worst_state([logic.STATE_OK, logic.STATE_BIZ]) == logic.STATE_BIZ
    assert logic.worst_state(
        [logic.STATE_MISSING, logic.STATE_BIZ, logic.STATE_ERROR]
    ) == logic.STATE_ERROR
    assert logic.worst_state([logic.STATE_OK, logic.STATE_OK]) == logic.STATE_OK
    # 空集：既有行為，`44` 未訂。本輪未動。
    assert logic.worst_state([]) == logic.STATE_MISSING


def test_worst_state與輸入順序無關_窮舉全部排列():
    """反向控制：拆掉 tie-break 之後**不准**留下另一個看不見的先後。

    四狀態的全部非空 multiset（大小 1~4）× 每個 multiset 的全部排列，
    同一個 multiset 的每一種排列必須回同一個值。
    """
    import itertools

    four = (logic.STATE_OK, logic.STATE_MISSING, logic.STATE_BIZ, logic.STATE_ERROR)
    checked = 0
    for size in range(1, 5):
        for combo in itertools.combinations_with_replacement(four, size):
            answers = {logic.worst_state(list(p)) for p in itertools.permutations(combo)}
            assert len(answers) == 1, (combo, answers)
            checked += 1
    assert checked > 0, "一組也沒掃到 —— 這一條會變成空掃"
    # 反空掃：這批裡真的有回哨符的（否則本條退化成「四狀態都不會平手」）。
    assert logic.worst_state([logic.STATE_MISSING, logic.STATE_BIZ]) is logic.STATE_UNRANKED


def test_哨符可以再餵回worst_state_而不是KeyError():
    """結論燈讀的三塊狀態就可能含哨符 —— 那一層必須吃得下它。"""
    assert logic.worst_state([logic.STATE_UNRANKED]) is logic.STATE_UNRANKED
    assert logic.worst_state(
        [logic.STATE_UNRANKED, logic.STATE_ERROR]
    ) == logic.STATE_ERROR
    assert logic.worst_state([logic.STATE_UNRANKED, logic.STATE_OK]) is logic.STATE_UNRANKED


def test_block_tone只做呈現_不宣稱誰比較嚴重():
    """`44` 沒有給卡層級一個顏色，邊框得有一個 —— 這一支就是那個實作必需品。"""
    assert logic.block_tone([logic.STATE_OK, logic.STATE_OK]) == "中性"
    assert logic.block_tone([logic.STATE_OK, logic.STATE_MISSING]) == "灰"
    assert logic.block_tone([logic.STATE_MISSING, logic.STATE_BIZ]) == "黃"
    assert logic.block_tone([logic.STATE_BIZ, logic.STATE_ERROR]) == "紅"
    # 顏色與輸入順序無關。
    assert logic.block_tone([logic.STATE_BIZ, logic.STATE_MISSING]) == logic.block_tone(
        [logic.STATE_MISSING, logic.STATE_BIZ]
    )
    # 排得出來就照 `44` 5.1 那張表；排不出來才退到主值顏色。
    assert logic.tone_for_block(logic.STATE_BIZ, [logic.STATE_BIZ]) == "黃"
    assert logic.tone_for_block(
        logic.STATE_UNRANKED, [logic.STATE_MISSING, logic.STATE_BIZ]
    ) == "黃"


def test_回歸_同級主值不得讓整頁建不起來():
    """**第 1 件的當掉點回歸測試。**

    `hld` 上一輪就是漏了結論燈那一個呼叫端，害它在特定資料下 `KeyError`。
    本檔有**兩個**呼叫端（`_build_card` 與 `conclusion_light`），兩個都吃得到哨符。

    ⚠️ 拿掉任一半修復都會紅：
      · `_build_card` 的 `tone_for_block(...)` 改回 `tone_for_state(block_state)`
        → `KeyError: None`；
      · `conclusion_light` 改回 `next(card ... == worst)` ＋ `_STATE_IN_LIGHT_TEXT[worst]`
        → `KeyError: None`（卡內同級）或 `StopIteration`（三塊之間同級）。
    """
    for name in ("mkt3_tied_in_one_card", "two_cards_tied"):
        model = logic.build_page_model(fixtures.all_datasets()[name])  # ⛔ 修復前這一行就炸了
        for block in logic.all_blocks(model):
            if "_tone" in block:  # 層 3／層 4 那四塊本來就沒有邊框顏色，見下一條的說明
                assert block["_tone"] in {"中性", "灰", "黃", "紅"}, (name, block["code"])

    # 真的踩到那兩種同級（否則本條退化成「隨便一組資料建得起來」）。
    card = logic.find_block(
        logic.build_page_model(fixtures.dataset_mkt3_tied_in_one_card()), "MKT-3"
    )
    assert card["_state"] is logic.STATE_UNRANKED, card["_state"]
    assert {logic.STATE_MISSING, logic.STATE_BIZ} == {
        mv["_state"] for mv in card["main_values"]
    }

    cards = [
        logic.find_block(
            logic.build_page_model(fixtures.dataset_two_cards_tied()), code
        )
        for code in ("MKT-1", "MKT-2", "MKT-3")
    ]
    assert {c["_state"] for c in cards} == {
        logic.STATE_MISSING, logic.STATE_BIZ, logic.STATE_OK
    }
    assert logic.worst_state([c["_state"] for c in cards]) is logic.STATE_UNRANKED


def test_八塊在全部情境下都建得出來且狀態合法():
    """逐塊狀態合法性守衛：**八塊 × 全部情境**。

    ⚠️ **這一條是照 `hld` 上一輪的教訓寫的**：那一邊的同名守衛只跑了六個情境，
    而新加的情境沒被納入 —— `KeyError: None` 就是從那道縫溜出去的。
    ⇒ 本條一律跑 `fixtures.all_datasets()` 的**全部**，新增情境自動納入，不必記得改這裡。

    契約：塊的 `_state` 要嘛是四狀態之一、要嘛是 `STATE_UNRANKED`；
    而且 `STATE_UNRANKED` 必須是**掙來的**（那一塊真的同時有那兩種主值），
    不是漏接漏出來的 `None`；**有 `_tone` 的塊，`_tone` 一律要是合法顏色**
    （那才是真正會被畫出去的東西）。

    ⚠️ **本頁的形狀與 `hld` 不同，這裡照實寫，不硬套**（總管指示：不適用就寫出理由）：
      · `hld` 九塊**每一塊都有** `_tone` 與 `_state`，所以那一邊可以無條件驗九塊。
      · 本頁只有 `MKT-1`／`MKT-2`／`MKT-3` 三張卡有 `_state`；
        `MKT-0` 有 `_tone` 但**沒有** `_state`（燈色由 `44` :310 三條規則直接給）；
        層 3／層 4 的 `MKT-4`~`MKT-7` **兩個都沒有**（它們不是卡，沒有邊框顏色）。
      ⛔ **本輪不替那四塊發明一個 `_tone`** —— `44` 沒有給它們顏色，補一個就是造規格。
    ⚠️ **所以這一條額外釘住「哪些塊該有哪些鍵」**：只寫 `if "_tone" in block` 而不釘形狀，
       日後有人把 `_tone` 從某塊拿掉，這條守衛會**靜默**縮小射程還是綠的 ——
       那就是 `hld` 上一輪那道縫換一個位置再開一次。
    """
    legal = {logic.STATE_OK, logic.STATE_MISSING, logic.STATE_BIZ, logic.STATE_ERROR}
    tones = {"中性", "灰", "黃", "紅"}
    has_tone = {"MKT-0", "MKT-1", "MKT-2", "MKT-3"}
    has_state = {"MKT-1", "MKT-2", "MKT-3"}
    checked = 0
    unranked_seen = 0
    for name, ds in fixtures.all_datasets().items():
        model = logic.build_page_model(ds)
        blocks = logic.all_blocks(model)
        assert [b["code"] for b in blocks] == [f"MKT-{i}" for i in range(8)], name
        # 形狀本身就是契約的一部分（理由見 docstring 末段）。
        assert {b["code"] for b in blocks if "_tone" in b} == has_tone, name
        assert {b["code"] for b in blocks if "_state" in b} == has_state, name
        for block in blocks:
            checked += 1
            if "_tone" in block:
                assert block["_tone"] in tones, (name, block["code"], block["_tone"])
            if "_state" not in block:
                continue
            state = block["_state"]
            if state is logic.STATE_UNRANKED:
                value_states = {mv["_state"] for mv in block.get("main_values", [])}
                assert {logic.STATE_MISSING, logic.STATE_BIZ} <= value_states, (
                    name, block["code"], sorted(map(str, value_states)))
                unranked_seen += 1
            else:
                assert state in legal, (name, block["code"], state)
    assert checked == len(fixtures.all_datasets()) * 8 > 0
    # 反空掃：全部情境裡**真的**有踩到同級的，否則上面那一支 if 從來沒被執行過。
    assert unranked_seen > 0, "沒有任何情境踩到同級 —— 這條守衛等於沒驗到哨符那一半"


def test_結論燈_卡內同級_兩個字面值都寫出來而不是挑一個():
    """`44` :310 逐字要的是「文案列出是哪一張卡」。

    這張卡同時有 `資料未備` 與 `業務例外` 的主值 —— **兩件事都真的發生了**，
    所以兩個都寫。⛔ 這不是「兩個都最嚴重」，也不得被讀成一個先後。
    """
    model = logic.build_page_model(fixtures.dataset_mkt3_tied_in_one_card())
    light = logic.find_block(model, "MKT-0")
    assert light["_tone"] == "黃"  # `44` :310：任一塊為那兩者之一 → 黃
    assert light["text"] == "資金與匯率卡：資料未備／不適用"
    # 書寫順序照 `44` :310 那一行自己並列兩者的寫法，不是嚴重度。
    assert logic._UNRANKED_PAIR == (logic.STATE_MISSING, logic.STATE_BIZ)


def test_結論燈_三塊之間同級_兩張卡都點名而不是吞掉一張():
    """舊寫法 `next(card ... == worst)` 只會回第一張 —— 那是按**清單位置**排的
    第二個看不見的先後。本輪把它換成「最高那一級的卡全部列出」。"""
    model = logic.build_page_model(fixtures.dataset_two_cards_tied())
    light = logic.find_block(model, "MKT-0")
    assert light["_tone"] == "黃"
    assert light["text"] == "風險情緒卡：資料未備；資金與匯率卡：不適用"
    # 反向：沒進最高那一級的卡**不得**被點名。
    assert "景氣位置卡" not in light["text"]


def test_結論燈的文案只用44五點二那七個徽章字面值():
    """哨符**不得**流進任何畫面文字（它不是第五個狀態）。"""
    for name, ds in fixtures.all_datasets().items():
        light = logic.find_block(logic.build_page_model(ds), "MKT-0")
        text = light["text"]
        assert "None" not in text, (name, text)
        assert str(logic.STATE_UNRANKED) not in text, (name, text)
        # 冒號後面的每一個字面值都要落在那七個之內。
        for chunk in text.split("；"):
            if "：" not in chunk:
                continue
            for word in chunk.split("：", 1)[1].split("／"):
                assert word in logic.STATUS_BADGE_LITERALS, (name, word, text)


def test_第1件反向控制_拆掉tie_break沒有改變任何一個現行情境的顏色與文案():
    """⛔ **反向控制**：第 1 件動的是「這一塊最差的是哪一個狀態」這句**宣稱**，
    **不是**畫面。

    這一份期望值是拆掉 tie-break **之前**、在 `fd5e41b` 上跑出來的
    （量測日 2026-09-24；十四個情境 × 四塊 ＝ 五十六格，
    另加結論燈文案十四格）。**新增的兩個同級情境刻意不在這份期望值裡。**

    ⛔ **2026-09-24 就地更正：本行原本給的理由是假的**（有意識的更正，不是漏刪；
       決策者：AI 總管；稽核抓到）。
    ~~原寫：它們在 `fd5e41b` 上根本建不起來，沒有「之前」可比。~~
    **實測推翻**：把這兩組資料在 `fd5e41b` 的 `ui_v2/` 上手工重建再餵進去，
    **兩組都建得起來**，而且有明確輸出（`MKT-3` 的 `_state` 是 `業務例外`、
    燈是「資金與匯率卡：不適用」）。
    **建不起來的是「`fd5e41b` ＋ 只改 `worst_state`」那個中間態，不是 `fd5e41b` 本身。**
    ⚠️ **同一輪 `hld` 那一份用字是對的**（「在 `fd5e41b` 上**不存在**」—— 那三個
       scenario 在 base 樹確實沒有）。**一份寫對、一份從「不存在」升級成了「建不起來」：
       同一把尺沒有往內用。**
    ✅ **成立的理由（而且比原來那個強）**：`fd5e41b` 上「之前」的那個答案
       （`業務例外`／「資金與匯率卡：不適用」）**正好就是本輪要拆掉的那個自創先後** ——
       它把 `業務例外` 排在 `資料未備` 之上，還默默吞掉了那張卡同時是 `資料未備` 的事實。
       **把它鎖進期望值，等於把 bug 鎖進反向控制。**
    """
    expected_tone = {
        ("all_ok", "MKT-0"): "灰", ("all_ok", "MKT-1"): "中性",
        ("all_ok", "MKT-2"): "中性", ("all_ok", "MKT-3"): "中性",
        ("all_ok_negative", "MKT-0"): "灰", ("all_ok_negative", "MKT-1"): "中性",
        ("all_ok_negative", "MKT-2"): "中性", ("all_ok_negative", "MKT-3"): "中性",
        ("mkt1_one_key_missing", "MKT-0"): "黃", ("mkt1_one_key_missing", "MKT-1"): "灰",
        ("mkt1_one_key_missing", "MKT-2"): "中性", ("mkt1_one_key_missing", "MKT-3"): "中性",
        ("mkt1_both_keys_missing", "MKT-0"): "黃", ("mkt1_both_keys_missing", "MKT-1"): "灰",
        ("mkt1_both_keys_missing", "MKT-2"): "中性", ("mkt1_both_keys_missing", "MKT-3"): "中性",
        ("mkt1_fetch_failed", "MKT-0"): "紅", ("mkt1_fetch_failed", "MKT-1"): "紅",
        ("mkt1_fetch_failed", "MKT-2"): "灰", ("mkt1_fetch_failed", "MKT-3"): "中性",
        ("mkt2_both_keys_missing", "MKT-0"): "黃", ("mkt2_both_keys_missing", "MKT-1"): "中性",
        ("mkt2_both_keys_missing", "MKT-2"): "灰", ("mkt2_both_keys_missing", "MKT-3"): "中性",
        ("mkt2_only_five_rows", "MKT-0"): "灰", ("mkt2_only_five_rows", "MKT-1"): "中性",
        ("mkt2_only_five_rows", "MKT-2"): "中性", ("mkt2_only_five_rows", "MKT-3"): "中性",
        ("mkt2_one_row_after_baseline", "MKT-0"): "灰",
        ("mkt2_one_row_after_baseline", "MKT-1"): "中性",
        ("mkt2_one_row_after_baseline", "MKT-2"): "中性",
        ("mkt2_one_row_after_baseline", "MKT-3"): "中性",
        ("mkt2_diverging", "MKT-0"): "灰", ("mkt2_diverging", "MKT-1"): "中性",
        ("mkt2_diverging", "MKT-2"): "中性", ("mkt2_diverging", "MKT-3"): "中性",
        ("mkt3_unit_mismatch", "MKT-0"): "黃", ("mkt3_unit_mismatch", "MKT-1"): "中性",
        ("mkt3_unit_mismatch", "MKT-2"): "中性", ("mkt3_unit_mismatch", "MKT-3"): "黃",
        ("all_empty", "MKT-0"): "灰", ("all_empty", "MKT-1"): "灰",
        ("all_empty", "MKT-2"): "灰", ("all_empty", "MKT-3"): "灰",
        ("revised_row", "MKT-0"): "灰", ("revised_row", "MKT-1"): "中性",
        ("revised_row", "MKT-2"): "中性", ("revised_row", "MKT-3"): "中性",
        ("unknown_unit_literal", "MKT-0"): "灰", ("unknown_unit_literal", "MKT-1"): "中性",
        ("unknown_unit_literal", "MKT-2"): "中性", ("unknown_unit_literal", "MKT-3"): "中性",
        ("fetched_before_obs", "MKT-0"): "灰", ("fetched_before_obs", "MKT-1"): "中性",
        ("fetched_before_obs", "MKT-2"): "中性", ("fetched_before_obs", "MKT-3"): "中性",
    }
    expected_text = {
        "all_ok": "三張卡的資料齊",
        "all_ok_negative": "三張卡的資料齊",
        "mkt1_one_key_missing": "風險情緒卡：資料未備",
        "mkt1_both_keys_missing": "風險情緒卡：資料未備",
        "mkt1_fetch_failed": "風險情緒卡：取數失敗",
        "mkt2_both_keys_missing": "景氣位置卡：資料未備",
        "mkt2_only_five_rows": "三張卡的資料齊",
        "mkt2_one_row_after_baseline": "三張卡的資料齊",
        "mkt2_diverging": "三張卡的資料齊",
        "mkt3_unit_mismatch": "資金與匯率卡：不適用",
        "all_empty": "本頁三張卡皆未取到資料",
        "revised_row": "三張卡的資料齊",
        "unknown_unit_literal": "三張卡的資料齊",
        "fetched_before_obs": "三張卡的資料齊",
    }
    assert expected_tone and expected_text, "期望值是空的 —— 這一條會變成空掃"
    # 反向控制的**涵蓋度**也要驗：拆之前存在的情境，一個都不准從期望值裡漏掉。
    before = set(fixtures.all_datasets()) - {"mkt3_tied_in_one_card", "two_cards_tied"}
    assert set(expected_text) == before, (sorted(set(expected_text) ^ before))

    datasets = fixtures.all_datasets()
    for (name, code), tone in expected_tone.items():
        block = logic.find_block(logic.build_page_model(datasets[name]), code)
        assert block["_tone"] == tone, (name, code, block["_tone"], tone)
    for name, text in expected_text.items():
        light = logic.find_block(logic.build_page_model(datasets[name]), "MKT-0")
        assert light["text"] == text, (name, light["text"], text)


# ═════════════ `44` 行號引用守衛（比照 `hld` 上一輪，本檔本輪首次建立） ═════════════

# 本輪之前，`ui_v2/mkt/**` 一個 `44` 行號引用也沒有；本輪新增了幾個，
# **同一輪就把守衛一起建起來**，不留「先引用、之後再說」的縫。
#
# 鍵 ＝ `44` 的行號；值 ＝ 那一行**必須**出現的字串（我逐行讀出來的錨點）。
# ⚠️ 錨點刻意取**內容**而不是行號附近的裝飾，這樣 `44` 萬一改版，紅燈會指出「內容不見了」。
# ⛔ **不要照抄別人給的行號**，包括 `hld` 那一份 —— 兩邊各自讀、各自登記。
_44_ANCHORS = {
    310: "三塊狀態取最差者",
    1735: "該欄位單獨列出並掛「未定義」徽章",
    2344: "顏色是 UI 顯示，不是嚴重度；兩者正交",
    2347: "再在句尾標上「逐字」",
    # 為了上面 `_NOT_A_44_QUOTE` 那一筆理由而引 —— 自己讀過該行才登記的：
    # `44` :733 的**現行**判準（舊的已劃掉），關鍵在「**該列指標名所在那一塊**」，
    # 而 `hld` 那兩句改寫寫的是「所在那一塊」／「該值所在那一塊」，**字不一樣**。
    733: "其輸出欄的字串與該列指標名所在那一塊上顯示的字串逐字相同",
}

_MY_FILES = (
    "ui_v2/mkt/logic.py",
    "ui_v2/mkt/page.py",
    "ui_v2/mkt/fixtures.py",
    "ui_v2/mkt/theme.py",
    "ui_v2/app_mkt.py",
    "tests/ui_v2/test_mkt_logic.py",
    "tests/ui_v2/test_mkt_page.py",
)


def _strike_spans(line: str):
    """`~~…~~` 之間的區段 —— 被劃掉的是**已退役的紀錄**，不該拿它紅燈。"""
    import re

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

    只認「這一行寫了那個檔名標記」的行 —— 本頁另有幾種長得像行號的東西
    （時間戳裡的分秒、以及版本字串），實測都出現在**沒有**那個標記的行上。

    ⚠️ **刻意不把那幾種東西的字面寫進這段說明** —— 寫進來，這一支就會掃到自己，
    本段就變成一筆假的引用。（`CLAUDE.md` §-2.A 第 8 款：受測字串寫進文件就會自己命中；
    ✅ 正例是「資訊留著，字串不留」。）
    """
    import re

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
    """每一個活的引用都要登記在 `_44_ANCHORS`，每一個登記都要對得上 `44` 的那一行。

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
    """`_44_ANCHORS` 裡的每一條都要真的對得上 `44`，**即使暫時沒有人引用它**。"""
    d44 = (pathlib.Path(__file__).resolve().parents[2]
           / "docs" / "v2" / "44_fund_ui_ssot.md").read_text(encoding="utf-8").split("\n")
    assert _44_ANCHORS, "錨點表是空的 —— 這一條會變成空掃"
    for n, anchor in sorted(_44_ANCHORS.items()):
        assert 1 <= n <= len(d44), (n, len(d44))
        assert anchor in d44[n - 1], (n, anchor, d44[n - 1][:110])


# ⚠️ **本表目前是空的，而且那是好事** —— 現行四個檔裡，**每一句由「逐字」引進來的
#    引文都真的逐字對得上 `44`**（本輪把唯一一句對不上的補成全句 —— 在
#    `ui_v2/hld/logic.py` 的 `_BAND` 那段檔頭註解裡，**刻意寫符號不寫行號**：
#    行號會因為任何一次編輯而失效，而那正是本檔另一支守衛在修的病）。
#    留這個機制是為了**日後真的出現「逐字引別的東西」時有合法出口**
#    （例：某處寫「草稿逐字要求：『…』」—— 那是引草稿，不是引 `44`）。
# ⛔ 加進來的每一筆都必須寫出**它到底在引什麼** —— 一張沒有理由的豁免清單，
#    就是把「無法否證」從函式裡搬到字典裡。
_NOT_A_44_QUOTE: dict = {}

# 掃描母體。⚠️ **`hld` 一起掃**：那一檔有同型的引文，本輪如果只掃 `mkt`，
#    就是本輪被指出兩次的那個形狀（同一把尺只往外用、不往內用）。
_QUOTE_SCAN_FILES = (
    "ui_v2/mkt/logic.py",
    "ui_v2/mkt/fixtures.py",
    "ui_v2/hld/logic.py",
    "ui_v2/hld/fixtures.py",
)

# 下限：四個檔裡由「逐字」引進來、而且**真的對得上 `44`** 的引文筆數。
# **量測值 24**（`mkt/logic` 6 ＋ `hld/logic` 17 ＋ `hld/fixtures` 1；量測日 2026-09-24，
# 本輪工作樹）。
# ⚠️ **這個數字不是隨手挑的，是突變量出來的**：本輪先把它設成 15，
#    然後把觸發判定**收窄成只認同一行**（＝舊守衛那個洞）跑一次 —— **全綠溜過去**，
#    因為收窄後還剩 **16** 筆，仍然高於 15。**一個擋不住收窄的下限，等於沒有下限。**
#    ⇒ 改成 **20**：收窄後的 16 會跌破它而紅燈，同時還留 4 筆的退役餘裕
#    （貼著現值 24 會讓「正常退役一句引文」變成紅燈，逼人不敢退役 ——
#    理由同 `tests/test_doc_counters.py` 各下限的寫法）。
# ⚠️ 若哪天真的要退役第五句：**改這個數，並寫下新的量測與理由**，不要一路往下調。
_MIN_VERIFIED_QUOTES = 20

# 「逐字」與它引進來的那個 `「` 之間，允許夾哪些字。
# ⚠️ 必須含換行與 `#`：實測本 repo 就有「…… :1735 逐字是」換行後才寫引文的寫法，
#    而**那一句正是舊守衛漏掉的那一句**。只認同一行，這支守衛會再漏同一個洞。
_QUOTE_CONNECTORS = set(" \t\r\n#：:是寫著引的為，,。－—-*~`＝=")


def _flat44(text: str) -> str:
    """比對前的正規化。三件事，每一件都有實測理由：

    1. 拿掉 markdown 強調（`**`／`` ` ``／`~~`／`*`／`_`）—— 引文常帶本檔自己的粗體，
       那是本檔的強調，不是 `44` 的字；不拿掉每一條都會假紅。
    2. 拿掉全部空白 —— 引文會換行並加註解前綴。
    3. **`『』` 一律折成 `「」`** —— `44` 裡寫 `「重新取數」`，而本 repo 把它**巢狀**
       引在外層 `「…」` 之內時必須改寫成 `『重新取數』`，那是**排版必需**、不是竄改。
       ⚠️ 這一條是本輪實測補的：沒有它，`hld/logic.py` 那一句會假紅，
       而**一支會亂叫的守衛會被當成雜訊忽略掉** —— 那等於沒有守衛。
    """
    import re

    text = re.sub(r"\n\s*#\s*", "", text)
    text = text.replace("\u300e", "\u300c").replace("\u300f", "\u300d")
    return re.sub(r"\s+", "", re.sub(r"\*\*|~~|`|\*|_", "", text))


def _unstruck_text(text: str) -> str:
    """把 `~~…~~` 之間的字挖掉（退役的紀錄不該紅燈）。"""
    out, keep, i = [], True, 0
    while i < len(text):
        if text.startswith("~~", i):
            keep = not keep
            i += 2
            continue
        if keep:
            out.append(text[i])
        i += 1
    return "".join(out)


def _quotes_introduced_by_verbatim(text: str):
    """回 [(字元位置, 引文)]：**由「逐字」兩個字引進來的**那些 `「…」`。

    ⚠️ **為什麼是這個觸發條件，而不是「這一行有逐字就掃全行／整塊」**（兩種都試過、
    都實測過，經過寫在這裡免得下一個人再走一遍）：
      · **逐行**：引文與「逐字」可以**不在同一行**（本 repo 就有），會漏；
        而且把引文改壞時可能**連觸發詞一起改掉**，於是那一句從此不被檢查 ——
        **會被它要抓的那個編輯關掉的守衛，等於沒有守衛。**
      · **整個註解區塊**：實測會把區塊裡每一個普通強調引號都掃進來
        （`hld` 一次掃出 25 筆雜訊），豁免表會膨脹成三十幾筆「這只是強調」，
        **雜訊會殺死守衛**。
      · **由「逐字」引進來**：實測四個檔 24 筆、雜訊 0 筆，而且觸發詞在引文**之外**，
        改壞引文不會把觸發關掉。

    ⛔ **射程要誠實**：本支只管「**宣告自己是逐字的**」那些引文。
    一句把改寫放進引號、**旁邊沒有寫「逐字」**的句子，本支**掃不到**
    （`hld` 自己登記過兩筆那種，見該檔 :123 起那則登記）—— 那是另一個問題，本支不宣稱守得到。
    """
    import re

    out = []
    for m in re.finditer("逐字", text):
        j = m.end()
        while j < len(text) and j - m.end() <= 12 and text[j] in _QUOTE_CONNECTORS:
            j += 1
        if j >= len(text) or text[j] != "\u300c":
            continue
        depth, k = 0, j
        while k < len(text):
            if text[k] == "\u300c":
                depth += 1
            elif text[k] == "\u300d":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        if k < len(text):
            out.append((m.start(), text[j + 1:k]))
    return out


def _all_verbatim_quotes():
    out = []
    for rel in _QUOTE_SCAN_FILES:
        path = pathlib.Path(__file__).resolve().parents[2] / rel
        text = _unstruck_text(path.read_text(encoding="utf-8"))
        for pos, quote in _quotes_introduced_by_verbatim(text):
            out.append((rel, text[:pos].count("\n") + 1, quote))
    return out


def test_標了逐字的引文_每一句都回比過44():
    """⛔ **2026-09-24 重寫：上一版無法否證，稽核用突變證明它是空的。**

    ~~舊寫法：`used = [q for q in quoted if q in src]`，再逐一比對 `44`。~~
    **那個 `if q in src` 就是洞** —— 引文一旦被改壞，它就不再 `in src`、
    **從受檢清單裡掉出去、從此不被檢查**；反空掃 `assert used` 因為還剩四條而照樣通過。
    ⇒ 它只驗得到「**我列出來的句子有沒有跑掉**」，驗不到「**檔案裡標了逐字的句子是不是逐字**」，
    而後者才是它 docstring 自陳在守的東西。
    **實測**：把本輪自陳「抓到自己」的那個假引文原樣種回 `ui_v2/mkt/logic.py`，
    舊守衛 **255 passed 全綠**（稽核與本組各跑一次，結果相同）。

    **現在的契約**：從**檔案**抽出每一句**由「逐字」引進來**的 `「…」`，逐句回比 `44`；
    要嘛對得上，要嘛登記進 `_NOT_A_44_QUOTE` 並寫出它在引什麼。
    ⇒ **引文被改壞時它仍然被抽出來、仍然對不上 ⇒ 紅。**

    ⚠️ **本輪用突變實跑確認它現在真的會咬**（不是推論）。逐項照實記，含**沒擋住的那一個**：
      · 把那個假引文原樣種回 `mkt`（＝舊守衛全綠的那一個）→ **紅** ✅
      · 改壞 `mkt` 另一句逐字引文 → **紅** ✅
      · 改壞 `hld` 一句逐字引文 → **紅** ✅（證明 `hld` 真的在射程內，不是只掃自己那一邊）
      · 把觸發判定收窄成「只認同一行」→ 一開始**綠**（下限設太低），
        把下限由 15 改成 20 之後 → **紅** ✅

    ⛔ **一條擋不住的逃生路徑，據實寫明，不假裝守得到**：
    **把某一句的「逐字」兩個字順手刪掉**，那一句就脫離本支的射程（實測：仍然全綠）。
    這**在定義上是對的** —— 不寫「逐字」的句子沒有宣稱自己逐字，本支管的就是那個宣稱；
    但它確實是一條路：**想造假的人只要先撤掉宣稱就能繞過**。
    本支**不宣稱**擋得住那一種，留給讀 diff 的人。
    """
    d44 = (pathlib.Path(__file__).resolve().parents[2]
           / "docs" / "v2" / "44_fund_ui_ssot.md").read_text(encoding="utf-8")
    flat44 = _flat44(d44)
    found = _all_verbatim_quotes()
    assert found, "一句引文也沒抽到 —— 這一條會變成空掃"

    bad, verified = [], 0
    for rel, lineno, quote in found:
        if quote in _NOT_A_44_QUOTE:
            continue
        if _flat44(quote) in flat44:
            verified += 1
        else:
            bad.append(
                f"{rel}:{lineno} 標了「逐字」，但這一句在 `44` 裡找不到：\n"
                f"    {quote!r}\n"
                "    怎麼修：回 `44` 讀那一行照抄；真的不是在引 `44`（例如引草稿、"
                "引本檔舊表述）就登記進 `_NOT_A_44_QUOTE` 並寫出它在引什麼。"
            )
    assert not bad, "\n".join(bad)
    assert verified >= _MIN_VERIFIED_QUOTES, (
        f"只驗到 {verified} 句逐字引文，低於下限 {_MIN_VERIFIED_QUOTES} —— "
        "要嘛引文被整批刪了，要嘛抽取判定被收窄了（＝這一條正在變成空掃）")


def test_逐字豁免表沒有死條目而且每一筆都有理由():
    """`_NOT_A_44_QUOTE` 目前是空的；這一條是為了**它不是空的那一天**。

    ⚠️ 沒有這一條，一筆已經不存在的豁免可以永遠躺在表裡；
    下一個人把一句真的假引文改成與它同字，就會被那筆死條目默默放行。
    """
    live = {q for _, _, q in _all_verbatim_quotes()}
    assert live, "一句也沒抽到 —— 這一條會變成空掃"
    dead = sorted(set(_NOT_A_44_QUOTE) - live)
    assert not dead, f"這些豁免登記在檔案裡已經找不到了，請刪掉：{dead}"
    for quote, why in _NOT_A_44_QUOTE.items():
        assert len(why) >= 10, (quote, why)


def _cell_digest(block) -> str:
    """一塊模型的全格摘要（正規化方式與產生期望值時逐字相同）。"""
    import hashlib
    import json

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


def test_第1件反向控制_十四情境乘八塊一百一十二格逐格未變():
    """⛔ **反向控制，整張網**（上面那一條只比顏色與燈的文案，這一條比整格）。

    期望值取自 `fd5e41b`（動手前）逐格 dump，**不是**從現行程式現撈的。

    ⚠️ **這一條在 2026-09-24 被本組自己誤刪過一次，就地記下來，因為它比條文本身值錢**：
    修那支逐字守衛時用了「從某個函式名的位置起，整段換掉」的寫法
    （`s[:start] + new`），而**那個位置後面還接著這一條**，於是它連同 `_cell_digest`
    一起被無聲截掉。**測試總數當時剛好沒變**（守衛由一條拆成兩條 ＋1、這一條 −1，淨 0），
    所以**綠燈、數字也正常，看不出少了東西**。
    ⇒ **教訓**：用位置截檔改測試，會刪掉你沒在看的那一段；
    而「總數沒變」**不是**沒刪東西的證據。**要比的是名字的集合，不是數量。**
    （本條是照稽核指示去覆核另一件事時，發現行號對不上才挖出來的。）

    ⚠️ 2026-09-24 新增的兩個同級情境不在期望值裡，理由與上一條相同
    （「之前」的答案正好是本輪要拆掉的那個自創先後，鎖它等於把 bug 鎖進期望值）。
    ⚠️ 摘要對不上時看不出**哪裡**不同 —— 代價就地寫明：
       重跑一次逐格 dump 再 diff，**不要直接改期望值**。期望值改了，這條就廢了。
    """
    expected = {
        ("all_ok", "MKT-0"): "cd15f0ceb6da",
        ("all_ok", "MKT-1"): "e156a51bed11",
        ("all_ok", "MKT-2"): "bd304edd8d7a",
        ("all_ok", "MKT-3"): "ddef408d6b7c",
        ("all_ok", "MKT-4"): "f707120cac99",
        ("all_ok", "MKT-5"): "6f94365bce3d",
        ("all_ok", "MKT-6"): "c24cf97e69cd",
        ("all_ok", "MKT-7"): "bac3497a5a08",
        ("all_ok_negative", "MKT-0"): "cd15f0ceb6da",
        ("all_ok_negative", "MKT-1"): "ed7b2bcbe848",
        ("all_ok_negative", "MKT-2"): "345183416afc",
        ("all_ok_negative", "MKT-3"): "c6708ead229f",
        ("all_ok_negative", "MKT-4"): "f707120cac99",
        ("all_ok_negative", "MKT-5"): "6f94365bce3d",
        ("all_ok_negative", "MKT-6"): "31bff38dba2a",
        ("all_ok_negative", "MKT-7"): "bac3497a5a08",
        ("mkt1_one_key_missing", "MKT-0"): "ef60bfbaad0d",
        ("mkt1_one_key_missing", "MKT-1"): "1a5ce27c4183",
        ("mkt1_one_key_missing", "MKT-2"): "bd304edd8d7a",
        ("mkt1_one_key_missing", "MKT-3"): "ddef408d6b7c",
        ("mkt1_one_key_missing", "MKT-4"): "f707120cac99",
        ("mkt1_one_key_missing", "MKT-5"): "70af65a5c678",
        ("mkt1_one_key_missing", "MKT-6"): "dc25df106aba",
        ("mkt1_one_key_missing", "MKT-7"): "53af7974b63c",
        ("mkt1_both_keys_missing", "MKT-0"): "ef60bfbaad0d",
        ("mkt1_both_keys_missing", "MKT-1"): "655862709f27",
        ("mkt1_both_keys_missing", "MKT-2"): "bd304edd8d7a",
        ("mkt1_both_keys_missing", "MKT-3"): "ddef408d6b7c",
        ("mkt1_both_keys_missing", "MKT-4"): "f707120cac99",
        ("mkt1_both_keys_missing", "MKT-5"): "fff54b3d1a1d",
        ("mkt1_both_keys_missing", "MKT-6"): "aeb8c9401970",
        ("mkt1_both_keys_missing", "MKT-7"): "9e2a93c22cb1",
        ("mkt1_fetch_failed", "MKT-0"): "344b2d64a392",
        ("mkt1_fetch_failed", "MKT-1"): "c10f7e76aa01",
        ("mkt1_fetch_failed", "MKT-2"): "ad095103c630",
        ("mkt1_fetch_failed", "MKT-3"): "ddef408d6b7c",
        ("mkt1_fetch_failed", "MKT-4"): "f707120cac99",
        ("mkt1_fetch_failed", "MKT-5"): "214ed57f3396",
        ("mkt1_fetch_failed", "MKT-6"): "2ddc98a10e56",
        ("mkt1_fetch_failed", "MKT-7"): "70796f04a9ba",
        ("mkt2_both_keys_missing", "MKT-0"): "adb56d32cd27",
        ("mkt2_both_keys_missing", "MKT-1"): "e156a51bed11",
        ("mkt2_both_keys_missing", "MKT-2"): "ad095103c630",
        ("mkt2_both_keys_missing", "MKT-3"): "ddef408d6b7c",
        ("mkt2_both_keys_missing", "MKT-4"): "f707120cac99",
        ("mkt2_both_keys_missing", "MKT-5"): "214ed57f3396",
        ("mkt2_both_keys_missing", "MKT-6"): "2ddc98a10e56",
        ("mkt2_both_keys_missing", "MKT-7"): "70796f04a9ba",
        ("mkt2_only_five_rows", "MKT-0"): "cd15f0ceb6da",
        ("mkt2_only_five_rows", "MKT-1"): "e156a51bed11",
        ("mkt2_only_five_rows", "MKT-2"): "5802aba4e9e8",
        ("mkt2_only_five_rows", "MKT-3"): "ddef408d6b7c",
        ("mkt2_only_five_rows", "MKT-4"): "f707120cac99",
        ("mkt2_only_five_rows", "MKT-5"): "6f94365bce3d",
        ("mkt2_only_five_rows", "MKT-6"): "104bbfaf98cc",
        ("mkt2_only_five_rows", "MKT-7"): "f3ce815e6cda",
        ("mkt2_one_row_after_baseline", "MKT-0"): "cd15f0ceb6da",
        ("mkt2_one_row_after_baseline", "MKT-1"): "e156a51bed11",
        ("mkt2_one_row_after_baseline", "MKT-2"): "d697126c2cfb",
        ("mkt2_one_row_after_baseline", "MKT-3"): "ddef408d6b7c",
        ("mkt2_one_row_after_baseline", "MKT-4"): "f707120cac99",
        ("mkt2_one_row_after_baseline", "MKT-5"): "6f94365bce3d",
        ("mkt2_one_row_after_baseline", "MKT-6"): "12a9373cbc2d",
        ("mkt2_one_row_after_baseline", "MKT-7"): "80513c138371",
        ("mkt2_diverging", "MKT-0"): "cd15f0ceb6da",
        ("mkt2_diverging", "MKT-1"): "e156a51bed11",
        ("mkt2_diverging", "MKT-2"): "581dd6da4127",
        ("mkt2_diverging", "MKT-3"): "ddef408d6b7c",
        ("mkt2_diverging", "MKT-4"): "f707120cac99",
        ("mkt2_diverging", "MKT-5"): "6f94365bce3d",
        ("mkt2_diverging", "MKT-6"): "0d3dfaff86a1",
        ("mkt2_diverging", "MKT-7"): "bac3497a5a08",
        ("mkt3_unit_mismatch", "MKT-0"): "c53092c5a96c",
        ("mkt3_unit_mismatch", "MKT-1"): "e156a51bed11",
        ("mkt3_unit_mismatch", "MKT-2"): "bd304edd8d7a",
        ("mkt3_unit_mismatch", "MKT-3"): "74a194e6bc2c",
        ("mkt3_unit_mismatch", "MKT-4"): "f707120cac99",
        ("mkt3_unit_mismatch", "MKT-5"): "6f94365bce3d",
        ("mkt3_unit_mismatch", "MKT-6"): "05b1c5bf2b53",
        ("mkt3_unit_mismatch", "MKT-7"): "bac3497a5a08",
        ("all_empty", "MKT-0"): "e80f5173aa64",
        ("all_empty", "MKT-1"): "655862709f27",
        ("all_empty", "MKT-2"): "ad095103c630",
        ("all_empty", "MKT-3"): "a9db1ba8af95",
        ("all_empty", "MKT-4"): "f707120cac99",
        ("all_empty", "MKT-5"): "744fadcede78",
        ("all_empty", "MKT-6"): "70d28a6ea733",
        ("all_empty", "MKT-7"): "29ac69345567",
        ("revised_row", "MKT-0"): "cd15f0ceb6da",
        ("revised_row", "MKT-1"): "e156a51bed11",
        ("revised_row", "MKT-2"): "bd304edd8d7a",
        ("revised_row", "MKT-3"): "71a5a27d7dd7",
        ("revised_row", "MKT-4"): "f707120cac99",
        ("revised_row", "MKT-5"): "6f94365bce3d",
        ("revised_row", "MKT-6"): "c8010960bf01",
        ("revised_row", "MKT-7"): "bac3497a5a08",
        ("unknown_unit_literal", "MKT-0"): "cd15f0ceb6da",
        ("unknown_unit_literal", "MKT-1"): "e156a51bed11",
        ("unknown_unit_literal", "MKT-2"): "bd304edd8d7a",
        ("unknown_unit_literal", "MKT-3"): "ddef408d6b7c",
        ("unknown_unit_literal", "MKT-4"): "f707120cac99",
        ("unknown_unit_literal", "MKT-5"): "6f94365bce3d",
        ("unknown_unit_literal", "MKT-6"): "48a65b18ad96",
        ("unknown_unit_literal", "MKT-7"): "bac3497a5a08",
        ("fetched_before_obs", "MKT-0"): "cd15f0ceb6da",
        ("fetched_before_obs", "MKT-1"): "e156a51bed11",
        ("fetched_before_obs", "MKT-2"): "bd304edd8d7a",
        ("fetched_before_obs", "MKT-3"): "8e0d5339c884",
        ("fetched_before_obs", "MKT-4"): "f707120cac99",
        ("fetched_before_obs", "MKT-5"): "6f94365bce3d",
        ("fetched_before_obs", "MKT-6"): "d2c6b21df1e2",
        ("fetched_before_obs", "MKT-7"): "8b80c471541b",
    }
    assert len(expected) == 112, len(expected)
    before = set(fixtures.all_datasets()) - {"mkt3_tied_in_one_card", "two_cards_tied"}
    assert {name for name, _ in expected} == before, sorted({n for n, _ in expected} ^ before)
    datasets = fixtures.all_datasets()
    for (name, code), digest in expected.items():
        block = logic.find_block(logic.build_page_model(datasets[name]), code)
        assert _cell_digest(block) == digest, (name, code, "整格內容變了")


def test_結論燈_窮舉六十四種組合_永遠點名最高那一級的全部卡():
    """⭐ **把第 1 件在結論燈上的射程變成機器驗得到的性質**（2026-09-24 稽核必修 H）。

    上面那些正控只釘了幾個具體情境；這一條窮舉**四狀態 × 三張卡 ＝ 64 種組合**，
    驗一條不變量：**被點名的卡，恰好就是落在最高那一級的那些卡** ——
    一張不多（沒進最高級的不准被點名）、一張不少（進了最高級的不准被吞掉）。

    ⚠️ **為什麼需要它**：與 `fd5e41b` 逐一對跑，本塊文案有變的是 **30 種**，
    其中 **12 種**來自真的同級、**18 種**來自「同一個狀態、好幾張卡」
    （舊碼默默吞掉其餘卡名）。⇒ **本輪在這一塊修掉的是兩件事**，
    而具體情境的正控只踩得到其中幾點。
    """
    import itertools

    four = (logic.STATE_OK, logic.STATE_MISSING, logic.STATE_BIZ, logic.STATE_ERROR)
    titles = {"MKT-1": "風險情緒卡", "MKT-2": "景氣位置卡", "MKT-3": "資金與匯率卡"}
    checked = named_more_than_one = 0
    for combo in itertools.product(four, repeat=3):
        cards = [
            {"title": titles[code], "_state": state, "_all_missing": False,
             "main_values": [{"_state": state}]}
            for code, state in zip(("MKT-1", "MKT-2", "MKT-3"), combo)
        ]
        light = logic.conclusion_light(cards)
        checked += 1
        if all(s == logic.STATE_OK for s in combo):
            assert light["text"] == "三張卡的資料齊", combo
            continue
        top = max(logic._band(s) for s in combo)
        expect = {titles[c] for c, s in zip(("MKT-1", "MKT-2", "MKT-3"), combo)
                  if logic._band(s) == top}
        got = {chunk.split("：", 1)[0] for chunk in light["text"].split("；")}
        assert got == expect, (combo, sorted(got), sorted(expect))
        # 燈色一律由「最高那一級」決定（`44` :310 的三條規則）。
        assert light["_tone"] == ("紅" if top == logic._BAND[logic.STATE_ERROR] else "黃"), combo
        if len(expect) > 1:
            named_more_than_one += 1
    assert checked == 64, checked
    # 反空掃：真的有「點名超過一張卡」的組合，否則這一條退化成「永遠只點一張」。
    assert named_more_than_one > 0, "沒有任何組合點名超過一張卡 —— 這一條沒驗到重點"
