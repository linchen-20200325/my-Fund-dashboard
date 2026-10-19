# -*- coding: utf-8 -*-
"""BL-0250 實機驗收回修 批次 1（客戶 2026-10-19 裁示，`docs/DECISIONS.md` `DEC-2026-10-19-04`）的純函式守衛（fast lane）。

只驗正式模式那幾支純函式；畫面上的整頁行為另見 `tests/ui_v2/test_bl0250_batch1_page.py`（slow lane）。
1. 市場總覽 `MKT-6`／`MKT-7`：時間轉台北時間、表頭註明時區、「是否修正」改「是／否」、表頭「指標鍵」改「指標」。
2. ~~標的探索三張卡的佔位徽章改寫一枚「◇ 資料未備」~~ → 獨立稽核 M1 後撤回（總管裁定；有意識的更正，不是漏刪）：
   來源層級缺值的符號 44 沒有唯一答案，待客戶 Decision Gate；本檔改為鎖住現況（佔位字照原樣搬到 ④）。
3. 資產配置資料狀態行：格內與列尾已畫出的 ◇ 也要報（`health.has_missing_marker`）。
4. 資產配置 `ALO-6`：佔比與合計改百分比。
5. G5：持倉體檢「⬜ 另有／其中 N 檔淨值超過 10 日未更新（資料未備）」句首改 ◇（只換符號）。
6. G3：成因全部是尚未設定的塊，本頁擬的「取數失敗」改寫成「尚未設定：<哪一項>」；有真的取數失敗時照舊。
"""

from __future__ import annotations

import copy
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2 import health, plain, sections, symbols  # noqa: E402
from ui_v2.alo import live as alo_live  # noqa: E402
from ui_v2.alo import logic as alo_logic  # noqa: E402
from ui_v2.hld import logic as hld_logic  # noqa: E402
from ui_v2.mkt import fixtures as mkt_fixtures  # noqa: E402
from ui_v2.mkt import live as mkt_live  # noqa: E402
from ui_v2.mkt import logic as mkt_logic  # noqa: E402


# ───────────────────────── 1. MKT-6／MKT-7 ─────────────────────────


def test_台北時間_同一瞬間轉UTC加8():
    assert mkt_live.local_time_text("2026-09-24T02:00:00Z") == "2026-09-24 10:00"
    assert mkt_live.local_time_text("2026-09-23T20:30:00+00:00") == "2026-09-24 04:30"   # 跨日
    assert mkt_live.local_time_text("2026-09-24T10:00:00+08:00") == "2026-09-24 10:00"


@pytest.mark.parametrize("cell", ["⬜", "◇", "⛔", None])
def test_台北時間_空格符號原樣交回(cell):
    assert mkt_live.local_time_text(cell) == cell


def test_台北時間_沒有時區照拋_不猜():
    with pytest.raises(ValueError):
        mkt_live.local_time_text("2026-09-24T02:00:00")


def _live_model(dataset):
    notes = {"pending": {}, "masked_keys": [], "cooldowns": [], "available_keys": None,
             "settings": {"window_days": None, "baseline_date": None, "pair_consistent": None,
                          "indicator_keys": ["vol_index", "credit_spread_pct"]},
             "settings_error": None}
    return mkt_live.build_live_model({"dataset": dataset, "notes": notes})


def test_MKT6_MKT7_正式模式_表頭時區與中文_值改是否():
    model = _live_model(mkt_fixtures.dataset_all_ok())
    mkt6, mkt7 = mkt_logic.find_block(model, "MKT-6"), mkt_logic.find_block(model, "MKT-7")
    assert mkt6["column_labels"][0] == "指標" and "指標鍵" not in mkt6["column_labels"]
    assert "取得時間（UTC+8）" in mkt6["column_labels"]
    assert mkt7["column_labels"] == ["指標", "最近觀測日", "最近取得時間（UTC+8）", "來源層級", "延遲日數"]
    assert mkt6["_rows"] and all(r["is_revised"] in ("是", "否") for r in mkt6["_rows"])
    assert all("T" not in r["fetched_at"] and not r["fetched_at"].endswith("Z") for r in mkt6["_rows"])
    assert all(not r["fetched_text"].endswith("Z") for r in mkt7["_rows"])
    assert f"時間以 {mkt_logic.STORAGE_TIMEZONE} 顯示" not in mkt7["detail_lines"]
    assert "指標鍵" not in mkt7["summary_text"]


def test_MKT6_MKT7_示範模式模型不變():
    """`logic` 本身（示範模式走的那一份）照舊：UTC 字面、布林原值、「指標鍵」。"""
    model = mkt_logic.build_page_model(mkt_fixtures.dataset_all_ok())
    mkt6, mkt7 = mkt_logic.find_block(model, "MKT-6"), mkt_logic.find_block(model, "MKT-7")
    assert mkt6["column_labels"][0] == "指標鍵"
    assert any(r["is_revised"] is False for r in mkt6["_rows"])
    assert f"時間以 {mkt_logic.STORAGE_TIMEZONE} 顯示" in mkt7["detail_lines"]


def test_延遲日數照舊以UTC日期相減_不因顯示時區改變():
    model = _live_model(mkt_fixtures.dataset_all_ok())
    demo = mkt_logic.build_page_model(mkt_fixtures.dataset_all_ok())
    live_delays = {r["indicator_key"]: r["delay_text"] for r in mkt_logic.find_block(model, "MKT-7")["_rows"]}
    demo_delays = {r["indicator_key"]: r["delay_text"] for r in mkt_logic.find_block(demo, "MKT-7")["_rows"]}
    assert live_delays and all(demo_delays[key] == text for key, text in live_delays.items())


# ───────────────────────── 2. 標的探索佔位徽章 ─────────────────────────


def test_佔位徽章_撤回後維持現況_佔位字照原樣搬到第四段():
    """BL-0250 批次 1 第 3 項已撤回（獨立稽核 M1）：EXP 核心卡來源層級缺值的符號待客戶 Decision Gate，
    佔位字外漏維持 `663ce984` 時的現況。客戶裁示後改本條。"""
    display = {"blocks": [{"code": "EXP-1", "title": "條件輸入卡", "_layer": 2, "badges": [
        {"_kind": "來源", "_tone": "中性", "_placeholder": True, "text": "〔來源層級〕"},
        {"_kind": "新鮮度", "_tone": "中性", "_placeholder": True, "text": "〔新鮮度〕"},
    ]}]}
    rows = health.move_card_provenance(display, ("EXP-1",))
    assert rows == [("條件輸入卡", "", ["〔來源層級〕", "〔新鮮度〕"])]
    assert display["blocks"][0]["badges"] == []


def test_佔位徽章_真值照舊搬():
    badge = {"_kind": "來源", "_tone": "中性", "text": "淨值"}
    display = {"blocks": [{"code": "HLD-2", "title": "績效與風險卡", "_layer": 2, "badges": [badge]}]}
    assert health.move_card_provenance(display, ("HLD-2",)) == [("績效與風險卡", "", ["淨值"])]


# ───────────────────────── 3. 資產配置資料狀態行的 ◇ ─────────────────────────


def _alo_display(scenario):
    from ui_v2.alo import fixtures as alo_fixtures

    model = alo_live.apply_live_notes(alo_logic.build_page_model(alo_fixtures.scenario(scenario)))
    display, _raw, _status = plain.plain_model(model, page="alo")
    symbols.apply(display)
    display, failures = health.dedupe_failures(display)
    return display, failures


def test_資產配置_格內的資料未備_資料狀態行要報():
    display, failures = _alo_display("partial")
    assert not health.has_missing(display)          # 舊判讀讀不到（這正是漏報的原因）
    assert health.has_missing_marker(display)
    line = health.status_line(display, failures, as_of="2026-09-23", missing=health.has_missing_marker(display))
    assert "◇ 資料未備" in line["text"]


def test_資產配置_沒有資料未備時不報():
    display, failures = _alo_display("full")
    assert not health.has_missing_marker(display)
    line = health.status_line(display, failures, as_of="2026-09-23", missing=False)
    assert "◇" not in line["text"]


def test_has_missing_marker_私有鍵底下的字不算():
    assert not health.has_missing_marker({"_export_text": "◇ 資料未備"})
    assert health.has_missing_marker({"rows": [{"cell": "◇", "_missing_cells": ("cell",)}]})
    assert not health.has_missing_marker({"rows": [{"cell": "⬜", "_missing_cells": ("cell",)}]})


# ───────────────────────── 4. ALO-6 百分比 ─────────────────────────


def test_ALO6_佔比與合計改百分比():
    from ui_v2.alo import fixtures as alo_fixtures

    model = alo_live.alo6_as_percent(alo_logic.build_page_model(alo_fixtures.scenario("full")))
    block = alo_logic.find_block(model, "ALO-6")
    assert "總體佔比合計 100.0%" in block["footer_lines"]
    subtotals = [line for line in block["footer_lines"] if line.startswith("類別內佔比合計")]
    assert subtotals and all(line.endswith(" 100.0%") for line in subtotals)
    assert all(r["in_total_text"].endswith("%") for r in block["_rows"] if r["_in_total"] is not None)


def test_ALO6_示範模式照舊比率():
    from ui_v2.alo import fixtures as alo_fixtures

    block = alo_logic.find_block(alo_logic.build_page_model(alo_fixtures.scenario("full")), "ALO-6")
    assert "總體佔比合計 1" in block["footer_lines"]


# ───────────────────────── 5. G5：純過期淨值 → ◇ ─────────────────────────


def test_G5_鏡像片段與持倉體檢兩句真身一致():
    for template in (hld_logic.HLD1_NOT_READY_TAIL, hld_logic.HLD7_NOT_READY_NOTE):
        assert template.startswith("⬜ ")
        assert symbols._is_nav_not_ready_line(template.format(n=3, days=10))


@pytest.mark.parametrize("template", [hld_logic.HLD1_NOT_READY_TAIL, hld_logic.HLD7_NOT_READY_NOTE])
def test_G5_句首改菱形_其餘字面不動(template):
    text = template.format(n=2, days=10)
    node = {"tail_lines": [text]}
    symbols.mark_missing(node)
    assert node["tail_lines"] == ["◇" + text[1:]]


def test_G5_取數失敗退回預存那一句不動():
    line = "⛔ 淨值 取數失敗：AAAA：改用 2026-09-18 的預存淨值"
    node = {"lines": [line, "⬜ 不適用：尚未設定區間"]}
    symbols.mark_missing(node)
    assert node["lines"] == [line, "⬜ 不適用：尚未設定區間"]


# ───────────────────────── 6. G3：尚未設定 ≠ 取數失敗 ─────────────────────────


def _g3_display(*, fetch_fail=False):
    unconfigured = f"⛔ 使用者設定 取數失敗：{plain._KNOWN_MESSAGES[0][2]}"   # 設定試算表尚未設定
    other = "⛔ 資料 取數失敗：相關數字暫時無法判定"
    return {"blocks": [
        {"code": "ALO-0", "title": "差距結論燈", "_layer": 1, "_state": "系統錯誤", "glyph": "⛔",
         "state_word": "狀態：取數失敗", "text": "有一塊取數失敗", "lines": ["目標輸入卡：取數失敗。"]},
        {"code": "ALO-1", "title": "目標輸入卡", "_layer": 3, "_state": "系統錯誤", "summary_text": "⛔ 取數失敗",
         "detail_lines": [unconfigured, "取數失敗，暫無資料"]},
        {"code": "ALO-6", "title": "歸屬明細", "_layer": 4, "_state": "系統錯誤", "summary_text": "取數失敗",
         "detail_lines": [other if fetch_fail else unconfigured]},
    ]}


def test_G3_全部是尚未設定_燈與摘要改寫成尚未設定加哪一項():
    display, summary = health.dedupe_failures(_g3_display())
    only = health.relabel_unconfigured(display, summary)
    assert only == {"ALO-1": ["設定試算表"], "ALO-6": ["設定試算表"]}
    light, alo1, alo6 = display["blocks"]
    assert light["state_word"] == "狀態：尚未設定"
    assert light["text"] == "有一塊尚未設定：設定試算表"
    assert light["lines"] == ["目標輸入卡：尚未設定：設定試算表。"]
    assert light["glyph"] == "⛔" and light["_state"] == "系統錯誤"   # 符號與判定照舊
    assert alo1["summary_text"] == "⛔ 尚未設定：設定試算表"
    assert alo6["summary_text"] == "尚未設定：設定試算表"
    assert "尚未設定：設定試算表，暫無資料" in alo1["detail_lines"]
    assert alo1[sections.UNCONFIGURED_KEY] == ["設定試算表"]


def test_G3_有真的取數失敗_那一塊與燈照舊取數失敗():
    display, summary = health.dedupe_failures(_g3_display(fetch_fail=True))
    only = health.relabel_unconfigured(display, summary)
    assert only == {"ALO-1": ["設定試算表"]}
    light, alo1, alo6 = display["blocks"]
    assert light["state_word"] == "狀態：取數失敗" and light["text"] == "有一塊取數失敗"
    assert alo6["summary_text"] == "取數失敗"
    assert alo1["summary_text"] == "⛔ 尚未設定：設定試算表"


def test_G3_燈逐卡點名_只換屬尚未設定的那一張():
    display = {"blocks": [
        {"code": "MKT-0", "title": "環境結論燈", "_layer": 1, "_state": "系統錯誤",
         "text": "風險情緒卡：取數失敗；資金與匯率卡：取數失敗"},
        {"code": "MKT-1", "title": "風險情緒卡", "_layer": 2, "_state": "系統錯誤",
         "detail_lines": ["⛔ 資料 取數失敗：相關數字暫時無法判定"]},
        {"code": "MKT-3", "title": "資金與匯率卡", "_layer": 2, "_state": "系統錯誤",
         "detail_lines": ["⛔ 市場指標 取數失敗：資料來源的金鑰尚未設定"]},
    ]}
    display, summary = health.dedupe_failures(display)
    health.relabel_unconfigured(display, summary)
    assert display["blocks"][0]["text"] == "風險情緒卡：取數失敗；資金與匯率卡：尚未設定：資料來源的金鑰"
    assert sections.mkt_attention({"blocks": [
        {"code": "MKT-0", "_tone": "紅"}, {"code": "MKT-1", "_state": "系統錯誤", "title": "風險情緒卡"},
        {"code": "MKT-2", "_state": "ok", "title": "景氣位置卡"}, display["blocks"][2]]})[0]["text"] == (
        "資料面：風險情緒卡 ⛔ 取數失敗；資金與匯率卡 ⛔ 尚未設定：資料來源的金鑰")


def test_G3_塊內去重那一處照舊只留狀態族_摘要寫尚未設定哪一項():
    """塊內失敗摘要一頁只出現一次（之七其二第 3 條）：塊內只留「⛔ 尚未設定」；展開區摘要那一行才寫哪一項。"""
    display, summary = health.dedupe_failures({"blocks": [
        {"code": "HLD-4", "title": "檢視區間與門檻輸入", "_layer": 3, "_state": "ok", "summary_text": "⛔ 取數失敗",
         "notes": ["x", "⛔ 使用者設定 取數失敗：設定試算表尚未設定"]}]})
    health.relabel_unconfigured(display, summary)
    assert display["blocks"][0]["notes"][1] == "⛔ 尚未設定"
    assert display["blocks"][0]["summary_text"] == "⛔ 尚未設定：設定試算表"


def test_G3_鏡像常數一致():
    assert sections.UNCONFIGURED_KEY == health.UNCONFIGURED_KEY
    assert sections.TEXT_NOT_CONFIGURED == health.TEXT_NOT_CONFIGURED


def test_G3_設定讀不到_成因是尚未設定時改同一種說法():
    model = copy.deepcopy({"blocks": [{"code": "MKT-4", "summary_text": mkt_logic.TEXT_SETTINGS_UNREADABLE,
                                       "buttons": [{"disabled_reason": mkt_logic.TEXT_SAVE_SETTINGS_UNREADABLE}],
                                       "detail_lines": [mkt_logic.TEXT_SHOW_ALL_UNREADABLE, "⬜ 不適用：比較條件讀不到"],
                                       "_raw": mkt_logic.TEXT_SETTINGS_UNREADABLE}]})
    mkt_live.relabel_unconfigured_settings(model, "尚未設定：設定試算表")
    block = model["blocks"][0]
    assert block["summary_text"] == "尚未設定：設定試算表"
    assert block["buttons"][0]["disabled_reason"] == "尚未設定：設定試算表，暫不存檔"
    # ~~"⬜ 不適用：尚未設定：設定試算表"~~ → BL-0250 批次 2（44 第七節第三小節之十一其六；有意識的更正，不是漏刪）：
    # 兩個冒號改把原因放進括號；⬜ 與「不適用」照舊。
    assert block["detail_lines"] == ["尚未設定：設定試算表，暫時列出全部指標", "⬜ 不適用（尚未設定：設定試算表）"]
    assert block["_raw"] == mkt_logic.TEXT_SETTINGS_UNREADABLE   # `_` 開頭的鍵不碰


def test_G3_plain判讀尚未設定那一族():
    assert plain.not_configured_state(plain.MSG_SETTINGS_NOT_CONFIGURED) == "設定試算表尚未設定"
    assert plain.not_configured_state("HTTPSConnectionPool: Max retries exceeded") is None
    assert plain.not_configured_state(None) is None
