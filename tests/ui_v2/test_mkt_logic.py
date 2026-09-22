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
