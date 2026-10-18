# -*- coding: utf-8 -*-
"""Phase 3 P0-②：四頁資料狀態行與同源錯誤去重 `ui_v2/health.py` 的純函式測試（fast lane；不需要 streamlit）。

依據 `docs/v2/44_fund_ui_ssot.md` 第七節第三小節之七其二第 3、4 條、其五（`DEC-2026-10-17-03`），
58 第 14 節護欄 2（只改呈現，不改判定）、護欄 3（導覽只換頁）。

1. **不變式**：四頁可在本機組出的正式模型（沿用 `test_plain_logic._all_models`），去重前後 `_` 開頭鍵的值、
   `code`、`name`、數值、布林、塊數、每一張「不是純字串」串列的長度**深度相等**（純字串串列只可能少掉
   一模一樣的 ⛔ 行 —— BL-0146）。
2. **同源只摘要一次**：去重後模型裡沒有任何一句失敗摘要；「此區塊暫時無法判定」的次數 ＝ 摘要交出的受影響塊數，
   而且那幾塊的狀態都是 `系統錯誤`；尚未設定那一族的狀態句（含寫入用的 `NOT_CONFIGURED_MESSAGE` 換成的那一句）
   在一般畫面模型裡 0 次，資料狀態行的「尚未設定：」恰 1 次。
3. **沒有異常時不寫「資料齊／正常」**，只寫資料截至日。
4. 逐條改寫、`latest_date`、`move_card_provenance`、`mark_last_valid`、`both_keys_save_failed`（BL-0177）。
5. **導覽無副作用的靜態半邊**：`ui_v2/health_view.py::render_settings_link` 函式本體只呼叫
   `st.page_link`／`st.caption`／`st.markdown`；`ui_v2/health.py` 不 import streamlit。
   執行期半邊（按下去之後 save／refetch 0 次）在 `tests/ui_v2/test_preview_page.py`。
"""

from __future__ import annotations

import ast
import copy
import pathlib
import re
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

import test_plain_logic as TPL  # noqa: E402  共用同一批正式模型（不另造一份）

from ui_v2 import health, plain  # noqa: E402

_LIVE_PAGES = ("mkt", "hld", "exp", "alo")


def _strings(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key != "reason_text":       # logic 內部的中間值，畫面不讀（`test_plain_logic.test_畫面層不讀reason_text`）
                yield from _strings(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _strings(item)
    elif isinstance(node, str):
        yield node


def _projection(node, private=False):
    """判定與結構的投影：一般字串只留位置；`_` 開頭鍵、`code`、`name`、選項清單與 `*_keys` 照原值；
    **純字串串列**（說明行）收成一個記號 —— 那裡唯一允許的變化是少掉一模一樣的 ⛔ 行。"""
    if isinstance(node, dict):
        out = {}
        is_input = "name" in node and "label" in node
        for key, value in node.items():
            keep = isinstance(key, str) and (key.startswith("_") or key in TPL._VERBATIM_KEYS
                                             or key.endswith("_keys") or (key == "value_text" and is_input))
            out[key] = _projection(value, keep)
        return out
    if isinstance(node, (list, tuple)):
        if node and not private and all(isinstance(i, str) for i in node):
            return "<字串串列>"
        return [type(node).__name__] + [_projection(item, private) for item in node]
    if isinstance(node, str):
        return node if private else "<s>"
    return node


def _live():
    for key, model in TPL._all_models().items():
        if key[0] == "live" and key[1] in _LIVE_PAGES:
            yield key, model


def _blocks(display):
    return {b["code"]: b for b in display.get("blocks") or ()}


_SUMMARY = re.compile(r"⛔ [^\s：]+ 取數失敗：|" + re.escape(plain.SETTINGS_UNREADABLE_PREFIX))


# ───────────────────────── 1. 不變式 ─────────────────────────


def test_不變式_判定與結構深度相等():
    count = {}
    for key, model in _live():
        display, _raw, _status = plain.plain_model(model, page=key[1])
        before = copy.deepcopy(display)
        after, _summary = health.dedupe_failures(display)
        assert _projection(after) == _projection(before), key
        assert len(after["blocks"]) == len(before["blocks"]), key
        count[key[1]] = count.get(key[1], 0) + 1
    for page in _LIVE_PAGES:
        assert count.get(page, 0) >= 4, count


def test_純字串串列只可能少掉一模一樣的停止符號行():
    for key, model in _live():
        display, _raw, _status = plain.plain_model(model, page=key[1])
        before = copy.deepcopy(display)
        health.dedupe_failures(display)
        _same_lists(before, display, key)


def _same_lists(a, b, key):
    if isinstance(a, dict):
        for k in a:
            _same_lists(a[k], b[k], key)
    elif isinstance(a, list) and a and all(isinstance(i, str) for i in a):
        assert len(b) <= len(a), key
        plain_a = [line for line in a if health.SYMBOL_ERROR not in line]
        plain_b = [line for line in b if health.SYMBOL_ERROR not in line]
        assert plain_a == plain_b, key                                   # 不帶 ⛔ 的行一行不動
        stops = [line for line in b if health.SYMBOL_ERROR in line]
        assert len(stops) == len(set(stops)), key                        # ⛔ 行沒有一模一樣的兩行
    elif isinstance(a, (list, tuple)):
        assert len(a) == len(b), key
        for x, y in zip(a, b):
            _same_lists(x, y, key)


# ───────────────────────── 2. 同源只摘要一次 ─────────────────────────


def test_去重後沒有任何失敗摘要_受影響塊數等於此區塊暫時無法判定的次數():
    affected_total = 0
    for key, model in _live():
        display, _raw, _status = plain.plain_model(model, page=key[1])
        after, summary = health.dedupe_failures(display)
        texts = list(_strings(after))
        # 客戶 2026-10-18 裁示 BL-0375（`DEC-2026-10-18-02`）：退回預存又過期的那一句帶著裁示要留的日期，照留（不是漏收）；
        # 本條只把那一句的完整形狀排除，其他失敗摘要照舊一句都不得留下。
        leftover = [t for t in texts if _SUMMARY.search(t) and not health._RETREAT_SUMMARY.fullmatch(t)]
        assert leftover == [], (key, leftover)
        sentence = sum(t.count(health.TEXT_BLOCK_UNDECIDABLE) for t in texts)
        assert sentence == len(summary["affected_blocks"]), (key, sentence, summary)
        assert len(set(summary["affected_blocks"])) == len(summary["affected_blocks"]), key   # 一塊只寫一次
        blocks = _blocks(after)
        for code in summary["affected_blocks"]:
            assert health._block_is_error(blocks[code]), (key, code)      # 只寫在 `系統錯誤` 的塊
        affected_total += sentence
    assert affected_total >= 10, affected_total                           # 空掃防呆


def test_受影響的塊每一塊恰一次():
    for key, model in _live():
        display, _raw, _status = plain.plain_model(model, page=key[1])
        after, summary = health.dedupe_failures(display)
        for code, block in _blocks(after).items():
            n = sum(t.count(health.TEXT_BLOCK_UNDECIDABLE) for t in _strings(block))
            assert n == (1 if code in summary["affected_blocks"] else 0), (key, code, n)


def test_尚未設定那一族的狀態句在一般畫面模型裡0次_狀態行的類別句恰1次():
    seen = 0
    for key, model in _live():
        display, _raw, _status = plain.plain_model(model, page=key[1])
        had = [s for s in health.NOT_CONFIGURED_STATES if any(s in t for t in _strings(display))]
        after, summary = health.dedupe_failures(display)
        for state in health.NOT_CONFIGURED_STATES:
            assert not any(state in t for t in _strings(after)), (key, state)
        line = health.status_line(after, summary, as_of="2026-10-01")
        if had:
            seen += 1
            assert line["text"].count(f"{health.TEXT_NOT_CONFIGURED}：") == 1, (key, line["text"])
            for state in had:
                assert health.not_configured_name(state) in line["text"], (key, state)
        # 寫入用的那一句原文（`NOT_CONFIGURED_MESSAGE`）本來就不在一般畫面（P0-①），去重之後也不會回來
        assert not any(plain.MSG_SETTINGS_NOT_CONFIGURED in t for t in _strings(after)), key
    assert seen >= 4, seen


def test_取數失敗的類別句在狀態行恰1次():
    seen = 0
    for key, model in _live():
        display, _raw, _status = plain.plain_model(model, page=key[1])
        after, summary = health.dedupe_failures(display)
        line = health.status_line(after, summary, as_of=None)
        if summary["fetch_failed"]:
            seen += 1
            assert line["text"].count(f"{health.SYMBOL_ERROR} {health.TEXT_FETCH_FAILED}：") == 1, key
    assert seen >= 4, seen


# ───────────────────────── 3. 資料狀態行 ─────────────────────────


def test_沒有異常時只寫資料截至日_不寫資料齊或正常():
    empty = {"blocks": [{"code": "MKT-1", "title": "風險情緒卡", "_layer": 2, "_state": "ok"}]}
    line = health.status_line(empty, {"fetch_failed": [], "not_configured": [], "affected_blocks": []},
                              as_of="2026-09-21")
    assert line["items"] == []
    assert line["text"] == "資料截至 2026-09-21"
    for word in ("資料齊", "正常", health.STATUS_LABEL):
        assert word not in line["text"]
    unknown = health.status_line(empty, {"fetch_failed": [], "not_configured": [], "affected_blocks": []},
                                 as_of=None)
    assert unknown["text"] == f"資料截至 {health.AS_OF_UNKNOWN}"


def test_四頁正式模型的狀態行都不寫資料齊或正常():
    for key, model in _live():
        display, _raw, _status = plain.plain_model(model, page=key[1])
        after, summary = health.dedupe_failures(display)
        for stale in (False, True):
            text = health.status_line(after, summary, as_of="2026-10-01", stale=stale)["text"]
            assert "資料齊" not in text and "正常" not in text, (key, text)
            assert text.endswith("資料截至 2026-10-01"), (key, text)


def test_四種同類只列一次_順序固定_附資料截至日():
    model = {"blocks": [
        {"code": "MKT-1", "title": "風險情緒卡", "_layer": 2, "_state": "系統錯誤",
         "main_values": [{"_state": "資料未備"}, {"_state": "資料未備"}]},
        {"code": "MKT-2", "title": "景氣位置卡", "_layer": 2, "_state": "資料未備"},
    ]}
    summary = {"fetch_failed": ["市場指標", "使用者設定"], "not_configured": ["設定試算表"], "affected_blocks": []}
    line = health.status_line(model, summary, as_of="2026-09-21", stale=True)
    assert [symbol for symbol, _t, _tone in line["items"]] == ["◷", "◇", "⛔", ""]
    assert line["text"] == ("資料狀態：◷ 不是最新：部分只顯示最後有效資料　◇ 資料未備　⛔ 取數失敗：市場指標、使用者設定"
                            "　尚未設定：設定試算表　·　資料截至 2026-09-21")
    assert [tone for _s, _t, tone in line["items"]] == ["中性", "灰", "紅", "中性"]


def test_資料未備的判定沿用模型既有狀態():
    assert health.has_missing({"a": [{"_state": "資料未備"}]})
    assert health.has_missing({"a": {"_empty_kind": "來源缺"}})
    assert health.has_missing({"a": {"_empty_kind": "部分缺"}})
    assert not health.has_missing({"a": {"_state": "業務例外", "_empty_kind": "算不出來"}})
    assert not health.has_missing({"a": {"_state": "ok", "text": "資料未備"}})      # 字面不算，只看狀態
    assert health.has_error_state({"a": {"_empty_kind": "系統錯誤"}})
    assert not health.has_error_state({"a": {"text": "⛔ 取數失敗"}})


def test_只有系統錯誤狀態而沒有摘要時_狀態行照樣寫取數失敗():
    model = {"blocks": [{"code": "HLD-3", "title": "配息與本金卡", "_layer": 2, "_state": "系統錯誤"}]}
    line = health.status_line(model, {"fetch_failed": [], "not_configured": [], "affected_blocks": []}, as_of=None)
    assert line["items"] == [("⛔", "取數失敗", "紅")]


def test_latest_date():
    rows = [{"d": "2026-09-01"}, {"d": "2026-09-21T02:00:00Z"}, {"d": "壞值"}, {"d": None}, {}, "x"]
    assert health.latest_date(rows, "d") == "2026-09-21"
    assert health.latest_date([], "d") is None
    assert health.latest_date(None, "d") is None


# ───────────────────────── 4. 逐條改寫 ─────────────────────────


def _one(text, *, state="系統錯誤", layer=2, field="value_text", code="MKT-1"):
    block = {"code": code, "title": plain.BLOCK_NAMES[code], "_layer": layer, "_state": state,
             "main_values": [{"label": "x", field: text}]}
    after, summary = health.dedupe_failures({"blocks": [block]})
    return after["blocks"][0]["main_values"][0][field], summary


@pytest.mark.parametrize("text, state, expected", [
    ("⛔ 市場指標 取數失敗：相關數字暫時無法判定", "系統錯誤", "⛔ 此區塊暫時無法判定"),
    ("⛔ 市場指標 取數失敗：相關數字暫時無法判定", "資料未備", "⛔ 取數失敗"),
    ("⛔ 市場指標 取數失敗：資料來源的金鑰尚未設定", "ok", "⛔ 尚未設定"),
    ("⛔ 使用者設定 取數失敗：設定試算表尚未設定", "ok", "⛔ 尚未設定"),
    ("⛔ 設定讀不到：設定試算表尚未設定", "ok", "⛔ 尚未設定"),
    ("⛔ 設定讀不到：已存的設定暫時讀不到", "ok", "⛔ 設定讀不到"),
    ("⛔ 資料 取數失敗：AAAA 的相關數字暫時無法判定", "系統錯誤", "⛔ AAAA 取數失敗"),
    ("條件輸入卡　⛔ 使用者設定 取數失敗：設定試算表尚未設定", "系統錯誤", "條件輸入卡　⛔ 尚未設定"),
    ("⬜ 資料未備", "系統錯誤", "⬜ 資料未備"),
    ("⛔ 取數失敗", "系統錯誤", "⛔ 取數失敗"),
])
def test_逐條改寫(text, state, expected):
    got, _summary = _one(text, state=state)
    assert got == expected


def test_摘要分類_尚未設定與取數失敗分開():
    _got, summary = _one("⛔ 市場指標 取數失敗：資料來源的金鑰尚未設定", state="ok")
    assert summary["not_configured"] == ["資料來源的金鑰"] and summary["fetch_failed"] == []
    _got, summary = _one("⛔ 市場指標 取數失敗：相關數字暫時無法判定", state="ok")
    assert summary["fetch_failed"] == ["市場指標"] and summary["not_configured"] == []
    _got, summary = _one("⛔ 設定讀不到：已存的設定暫時讀不到", state="ok")
    assert summary["fetch_failed"] == ["使用者設定"]


def test_核心卡不畫的摘要欄不放那一句_也不進狀態行():
    got, summary = _one("⛔ 資料 取數失敗：相關數字暫時無法判定", field="summary_text", layer=2)
    assert got == "⛔ 取數失敗" and summary["affected_blocks"] == [] and summary["fetch_failed"] == []
    got, summary = _one("⛔ 資料 取數失敗：相關數字暫時無法判定", field="summary_text", layer=3, code="HLD-5")
    assert got == "⛔ 此區塊暫時無法判定" and summary["affected_blocks"] == ["HLD-5"]


def test_表格列裡的失敗只留狀態族():
    block = {"code": "EXP-2", "title": "候選清單卡", "_layer": 2, "_state": "系統錯誤",
             "_rows": [{"_cells": {"nav": {"text": "⛔ 資料 取數失敗：相關數字暫時無法判定"}}}]}
    after, summary = health.dedupe_failures({"blocks": [block]})
    assert after["blocks"][0]["_rows"][0]["_cells"]["nav"]["text"] == "⛔ 取數失敗"
    assert summary["affected_blocks"] == []


def test_一模一樣的停止符號行只留第一行_其他行不動_BL0146():
    block = {"code": "HLD-1", "title": "偏離提示卡", "_layer": 2, "_state": "ok",
             "detail_lines": ["⛔ 使用者設定 取數失敗：設定試算表尚未設定", "說明", "說明",
                              "⛔ 使用者設定 取數失敗：設定試算表尚未設定", "⛔ AAAA 取數失敗"]}
    after, _summary = health.dedupe_failures({"blocks": [block]})
    assert after["blocks"][0]["detail_lines"] == ["⛔ 尚未設定", "說明", "說明", "⛔ AAAA 取數失敗"]


def test_受保護的鍵與底線鍵與輸入欄當下值不換字():
    text = "⛔ 市場指標 取數失敗：相關數字暫時無法判定"
    block = {"code": "MKT-4", "title": "觀察窗與比較基準輸入", "_layer": 3, "_reason": text, "options": [text],
             "inputs": [{"name": "f", "label": "欄", "value_text": text}]}
    after, _summary = health.dedupe_failures({"blocks": [block]})
    out = after["blocks"][0]
    assert out["_reason"] == text and out["options"] == [text] and out["inputs"][0]["value_text"] == text


# ───────────────────────── 4b. 徽章換位置、◷、BL-0177 ─────────────────────────


def test_核心卡的來源與新鮮度徽章拿下來_一個不少_其他徽章不動():
    block = {"code": "MKT-1", "title": "風險情緒卡", "_layer": 2,
             "badges": [{"_kind": "狀態", "text": "部分缺"}, {"_kind": "來源", "text": "〔來源層級〕"}],
             "main_values": [{"label": "波動度指數", "badges": [
                 {"_kind": "來源", "text": "T2"}, {"_kind": "新鮮度", "text": "延遲 3 日"},
                 {"_kind": "狀態", "text": "取數失敗"}]}],
             "fund_groups": [{"head_text": "基金 A", "freshness_badge": {"_kind": "新鮮度", "text": "延遲 10 日"}}]}
    other = {"code": "MKT-7", "title": "新鮮度與來源清單", "_layer": 4,
             "badges": [{"_kind": "來源", "text": "T1"}]}
    display = {"blocks": [block, other]}
    rows = health.move_card_provenance(display, ("MKT-1",))
    assert rows == [("風險情緒卡", "", ["〔來源層級〕"]), ("風險情緒卡", "波動度指數", ["T2", "延遲 3 日"]),
                    ("風險情緒卡", "基金 A", ["延遲 10 日"])]
    assert block["badges"] == [{"_kind": "狀態", "text": "部分缺"}]
    assert block["main_values"][0]["badges"] == [{"_kind": "狀態", "text": "取數失敗"}]
    assert block["fund_groups"][0]["freshness_badge"] is None
    assert other["badges"] == [{"_kind": "來源", "text": "T1"}]       # 不在 codes 裡的塊不動


def test_只顯示最後有效資料的副標加時鐘記號_灰色那一種不加():
    prefix = "淨值取自預存序列，不是本次取得；最近一筆 "
    fresh = {"text": prefix + "2026-09-18", "_tone": "中性"}
    old = {"text": prefix + "2026-09-01，已超過 10 日", "_tone": "灰"}
    display = {"blocks": [{"code": "HLD-2", "title": "績效與風險卡", "fund_groups": [
        {"freshness_note": fresh}, {"freshness_note": old}]},
        {"code": "HLD-6", "title": "淨值與配息序列", "nav_groups": [{"freshness_note": {"text": prefix, "_tone": "中性"}}]}]}
    assert health.mark_last_valid(display, ("HLD-2",), prefix) is True
    assert fresh["text"] == "◷ " + prefix + "2026-09-18"
    assert old["text"].startswith(prefix)
    assert display["blocks"][1]["nav_groups"][0]["freshness_note"]["text"] == prefix   # ④ 的不動
    assert health.mark_last_valid(display, ("HLD-2",), prefix) is True               # 再跑一次不重複加
    assert fresh["text"].count("◷") == 1
    assert health.mark_last_valid({"blocks": []}, ("HLD-2",), prefix) is False


def test_持倉體檢的預存序列副標開頭逐字等於真身():
    from ui_v2.hld import live as HL
    from ui_v2.hld import page as HP

    assert HP._LAST_VALID_PREFIX == HL.CACHE_NOTE_FRESH.split("{", 1)[0]
    assert HL.CACHE_NOTE_OLD.startswith(HP._LAST_VALID_PREFIX)        # 灰色那一種同開頭 ⇒ 必須靠色調分


def test_兩鍵都沒存進去_卡片層改儲存失敗_兩鍵原文都進原始訊息_BL0177():
    display = {"blocks": [{"code": "ALO-1", "title": "目標輸入卡",
                           "error_lines": ["存檔寫入失敗：這一次沒有存進去", "別的行"]}]}
    errors = {"alo_target_weights": "HTTP 503 甲", "alo_tolerance_pp": "HTTP 503 乙", "alo_basis": "丙"}
    entries = health.both_keys_save_failed(display, "ALO-1", ("alo_target_weights", "alo_tolerance_pp"),
                                           errors, "ALO-1 目標輸入卡")
    assert display["blocks"][0]["error_lines"] == ["儲存失敗", "別的行"]
    assert entries == [{"where": "ALO-1 目標輸入卡", "text": "存檔寫入失敗：alo_target_weights：HTTP 503 甲"},
                       {"where": "ALO-1 目標輸入卡", "text": "存檔寫入失敗：alo_tolerance_pp：HTTP 503 乙"}]


@pytest.mark.parametrize("errors", [{}, None, {"alo_target_weights": "x"}, {"alo_tolerance_pp": "y"},
                                    {"alo_target_weights": "", "alo_tolerance_pp": "y"}])
def test_不是兩鍵都失敗_一個字都不動(errors):
    display = {"blocks": [{"code": "ALO-1", "title": "目標輸入卡", "error_lines": ["存檔寫入失敗：這一次沒有存進去"]}]}
    before = copy.deepcopy(display)
    assert health.both_keys_save_failed(display, "ALO-1", ("alo_target_weights", "alo_tolerance_pp"), errors, "w") == []
    assert display == before


def test_資產配置存檔失敗字首逐字等於真身():
    from ui_v2.alo import logic as A

    assert health._ALO_SAVE_FAILED_PREFIX == A.TEXT_SAVE_FAILED + "："


def test_尚未設定那一族逐字等於plain的已知訊息():
    assert health.NOT_CONFIGURED_STATES == tuple(state for _m, _c, state in plain._KNOWN_MESSAGES)
    assert all(state.endswith(health.TEXT_NOT_CONFIGURED) for state in health.NOT_CONFIGURED_STATES)
    assert plain.MSG_SETTINGS_NOT_CONFIGURED in [m for m, _c, _s in plain._KNOWN_MESSAGES]
    assert health.not_configured_name("設定試算表尚未設定") == "設定試算表"


# ───────────────────────── 5. 導覽無副作用（靜態半邊） ─────────────────────────

_ALLOWED_NAV_CALLS = {"st.page_link", "st.caption", "st.markdown"}


def _function(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)


def _calls(node):
    return [ast.unparse(c.func) for c in ast.walk(node) if isinstance(c, ast.Call)]


def test_導覽函式本體只呼叫page_link_caption_markdown():
    fn = _function(_ROOT / "ui_v2" / "health_view.py", "render_settings_link")
    calls = _calls(fn)
    assert calls and set(calls) <= _ALLOWED_NAV_CALLS, calls
    assert "st.page_link" in calls
    # 函式本體不碰 session、不碰任何讀寫函式名
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
    for bad in ("session_state", "load_live", "save_live", "refetch_live", "save_setting", "refetch",
                "rerun", "switch_page", "button", "cache_data", "clear"):
        assert bad not in names, bad


def test_狀態行與徽章表的畫法也不碰讀寫():
    for name in ("render_status_line", "render_provenance"):
        fn = _function(_ROOT / "ui_v2" / "health_view.py", name)
        st_calls = {c for c in _calls(fn) if c.startswith("st.")}
        assert st_calls <= {"st.markdown", "st.expander"}, (name, st_calls)
        body = ast.get_source_segment((_ROOT / "ui_v2" / "health_view.py").read_text(encoding="utf-8"), fn)
        for word in ("session_state", "save", "refetch", "load_live", "button", "rerun", "switch_page"):
            assert word not in body, (name, word)


@pytest.mark.parametrize("code, ok", [
    ("def render_settings_link(p=None):\n    st.page_link(p, label='x')\n", True),
    ("def render_settings_link(p=None):\n    st.button('x')\n", False),
    ("def render_settings_link(p=None):\n    st.page_link(p)\n    save_live('k', 1, 'int')\n", False),
])
def test_正控_守衛看得出多出來的呼叫(code, ok):
    fn = ast.parse(code).body[0]
    assert (set(_calls(fn)) <= _ALLOWED_NAV_CALLS) is ok


def test_health模組不import_streamlit():
    tree = ast.parse((_ROOT / "ui_v2" / "health.py").read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert "streamlit" not in roots, roots


# ───────────────────────── 6. 稽核必修：「ok 但延遲」在 ② 卡上留 ◷（2026-10-17 回修） ─────────────────────────


def _card(badge_tone, group_tone=None):
    block = {"code": "MKT-1", "title": "風險情緒卡", "_layer": 2, "_state": "ok",
             "main_values": [{"label": "波動度指數", "_state": "ok", "badges": [
                 {"_kind": "來源", "_tone": "中性", "text": "T2"},
                 {"_kind": "新鮮度", "_tone": badge_tone, "text": "延遲 12 日"}]}]}
    if group_tone:
        block["fund_groups"] = [{"head_text": "基金 A",
                                 "freshness_badge": {"_kind": "新鮮度", "_tone": group_tone, "text": "延遲 15 日"}}]
    return {"blocks": [block]}


_EMPTY_SUMMARY = {"fetch_failed": [], "not_configured": [], "affected_blocks": [], "explained_blocks": []}


def test_畫成黃的新鮮度徽章_卡上留時鐘加原字面_同色調_第四段照列原字面_狀態行報時鐘():
    display = _card("黃", group_tone="黃")
    rows = health.move_card_provenance(display, ("MKT-1",))
    value = display["blocks"][0]["main_values"][0]
    assert value["badges"] == [{"_kind": "新鮮度", "_tone": "黃", "text": "◷ 延遲 12 日"}]
    assert display["blocks"][0]["fund_groups"][0]["freshness_badge"] == {
        "_kind": "新鮮度", "_tone": "黃", "text": "◷ 延遲 15 日"}
    assert ("風險情緒卡", "波動度指數", ["T2", "延遲 12 日"]) in rows            # ④ 照列原字面（換位置，不刪除）
    assert ("風險情緒卡", "基金 A", ["延遲 15 日"]) in rows
    assert health.has_stale_marker(display, ("MKT-1",)) is True
    line = health.status_line(display, _EMPTY_SUMMARY, as_of="2026-10-01",
                              stale=health.has_stale_marker(display, ("MKT-1",)))
    assert line["items"][0][0] == health.SYMBOL_STALE


@pytest.mark.parametrize("tone", ["中性", "灰"])
def test_中性與灰色的延遲_卡上與狀態行都沒有時鐘(tone):
    display = _card(tone, group_tone=tone)
    health.move_card_provenance(display, ("MKT-1",))
    assert display["blocks"][0]["main_values"][0]["badges"] == []
    assert display["blocks"][0]["fund_groups"][0]["freshness_badge"] is None
    assert health.has_stale_marker(display, ("MKT-1",)) is False
    line = health.status_line(display, _EMPTY_SUMMARY, as_of="2026-10-01", stale=False)
    assert health.SYMBOL_STALE not in line["text"]
    assert not any(health.SYMBOL_STALE in t for t in _strings(display))


def test_時鐘只看既有色調_不看日數():
    """「延遲 99 日」但色調中性 → 不加；「延遲 1 日」色調黃 → 加。日數門檻與色調映射住在各頁 logic／live，本模組不新算。"""
    neutral = {"blocks": [{"code": "MKT-1", "main_values": [{"badges": [
        {"_kind": "新鮮度", "_tone": "中性", "text": "延遲 99 日"}]}]}]}
    yellow = {"blocks": [{"code": "MKT-1", "main_values": [{"badges": [
        {"_kind": "新鮮度", "_tone": "黃", "text": "延遲 1 日"}]}]}]}
    health.move_card_provenance(neutral, ("MKT-1",))
    health.move_card_provenance(yellow, ("MKT-1",))
    assert neutral["blocks"][0]["main_values"][0]["badges"] == []
    assert yellow["blocks"][0]["main_values"][0]["badges"][0]["text"] == "◷ 延遲 1 日"


def test_現行三頁正式模型沒有一枚畫成黃的新鮮度徽章_時鐘路徑目前不觸發():
    """依據（程式碼位置）：`ui_v2/mkt/logic.py::_freshness_badge` 的回傳色調寫死「中性」；
    `ui_v2/hld/live.py::nav_freshness` 的 `badge` 只有「灰」（超過門檻＝資料未備）與「中性」兩支；
    `ui_v2/exp/logic.py::placeholder_badge` 寫死「中性」（佔位）。本條掃本機可組出的全部正式模型實測同一件事 ——
    哪天某頁開始交出黃色新鮮度徽章，本條先紅，提醒回頭看卡上的 ◷（`move_card_provenance` 已會處理）。"""
    yellow, checked = [], 0

    def walk(node, key):
        nonlocal checked
        if isinstance(node, dict):
            if node.get("_kind") == "新鮮度":
                checked += 1
                if node.get("_tone") == "黃":
                    yellow.append((key, node))
            for value in node.values():
                walk(value, key)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value, key)

    for key, model in _live():
        if key[1] in ("mkt", "hld", "exp"):
            walk(model, key)
    assert yellow == []
    assert checked >= 50, checked


def test_三頁真身的新鮮度色調寫法_AST():
    """上一條的靜態半邊：三處產生新鮮度徽章的程式碼，色調常值只有「中性」／`NOT_READY_TONE`（灰）。"""
    sources = {
        "ui_v2/mkt/logic.py": "_freshness_badge",
        "ui_v2/hld/live.py": "nav_freshness",
        "ui_v2/exp/logic.py": "placeholder_badge",
    }
    for rel, name in sources.items():
        fn = _function(_ROOT / rel, name)
        tones = set()
        for node in ast.walk(fn):
            if isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values):
                    if isinstance(k, ast.Constant) and k.value == "_tone":
                        tones.add(ast.unparse(v))
        assert tones and tones <= {"'中性'", "NOT_READY_TONE"}, (rel, tones)
    from ui_v2.hld import live as HL

    assert HL.NOT_READY_TONE == "灰"


# ───────────────────────── 7. 稽核可選 3：⛔ 與尚未設定各自獨立 ─────────────────────────


def test_有尚未設定也不省掉取數失敗_沒有交代的系統錯誤塊照樣報停止符號():
    display = {"blocks": [
        {"code": "HLD-1", "title": "偏離提示卡", "_layer": 2, "_state": "系統錯誤",
         "detail_lines": ["⛔ 保單與持倉 取數失敗：保單試算表尚未設定"]},
        {"code": "HLD-3", "title": "配息與本金卡", "_layer": 2, "_state": "系統錯誤",
         "detail_lines": ["⛔ 取數失敗"]},                    # 這一塊的錯誤沒有任何一句摘要交代
    ]}
    after, summary = health.dedupe_failures(display)
    assert summary["not_configured"] == ["保單試算表"] and summary["fetch_failed"] == []
    line = health.status_line(after, summary, as_of=None)
    assert [s for s, _t, _tone in line["items"]] == ["⛔", ""], line
    assert "⛔ 取數失敗" in line["text"] and "尚未設定：保單試算表" in line["text"]


def test_每一塊的錯誤都被尚未設定交代到_就不另報停止符號():
    display = {"blocks": [
        {"code": "HLD-0", "title": "體檢結論燈", "_layer": 1, "_state": "系統錯誤", "text": "有一塊取數失敗"},
        {"code": "HLD-1", "title": "偏離提示卡", "_layer": 2, "_state": "系統錯誤",
         "detail_lines": ["⛔ 保單與持倉 取數失敗：保單試算表尚未設定"]},
    ]}
    after, summary = health.dedupe_failures(display)
    assert summary["explained_blocks"] == ["HLD-1"]
    line = health.status_line(after, summary, as_of=None)
    assert [s for s, _t, _tone in line["items"]] == [""], line             # 結論燈不自己取數，不算沒交代


# ───────────────────────── 8. Phase 3 P1-④：結論燈同一則訊息不印兩次 ─────────────────────────
# 依據：⛔ 那幾句 —— 58 U-31「同一則原文重複印多次本身是錯，可視為修正錯誤」；44 第七節第三小節之七其二第 3 條；
# 59 線框第 1.1 節。⬜ 那幾句只依 58 U-31 一般原則做呈現去重，不屬於 44 其二第 3 條（那條只管同源系統錯誤）。
# 只動燈的 `text`；圖示、狀態字、色調、狀態一個都不碰（護欄 2）。變動範圍（不只資產配置）見 `health.trim_light_echo`。


def _lamp(glyph, word, text, **extra):
    return {"code": "ALO-0", "title": "差距結論燈", "_layer": 1, "_tone": "灰", "glyph": glyph,
            "state_word": word, "text": text, **extra}


@pytest.mark.parametrize(("glyph", "word", "text", "expected"), [
    ("⛔", "狀態：取數失敗", "⛔ 尚未設定", "尚未設定"),          # 句首圖示與燈相同 → 拿掉
    ("⛔", "狀態：取數失敗", "⛔ 取數失敗", ""),                  # 拿掉之後與狀態字相同 → 整句不畫
    ("⛔", "取數失敗", "⛔ 取數失敗", ""),                        # 標的探索：狀態字不帶「狀態：」
    ("⬜", "狀態：中性", "⬜ 資料未備", "資料未備"),
])
def test_結論燈句首重複的圖示拿掉_與狀態字相同就整句不畫(glyph, word, text, expected):
    block = _lamp(glyph, word, text, _state="系統錯誤")
    keep = {k: v for k, v in block.items() if k != "text"}
    assert health.trim_light_echo(block) is True
    assert block["text"] == expected
    assert {k: v for k, v in block.items() if k != "text"} == keep          # 只動 text


@pytest.mark.parametrize(("glyph", "text"), [
    ("⛔", "有一塊取數失敗，這一頁的數字先不要照著讀"),   # 句首沒有圖示
    ("⬜", "◇ 資料未備"),                                # 圖示不同
    ("⛔", "⛔取數失敗"),                                 # 圖示後面沒有空白：不是「圖示＋一句」的形狀
    ("", "⛔ 取數失敗"),                                  # 燈沒有圖示
])
def test_結論燈句首不是同一個圖示就一個字都不動(glyph, text):
    block = _lamp(glyph, "狀態：取數失敗", text)
    before = dict(block)
    assert health.trim_light_echo(block) is False
    assert block == before


def test_市場總覽的燈沒有圖示鍵_不動():
    block = {"code": "MKT-0", "title": "環境結論燈", "_layer": 1, "text": "⛔ 取數失敗"}
    assert health.trim_light_echo(block) is False and block["text"] == "⛔ 取數失敗"


def test_去重之後四頁正式模型的結論燈都不以自己的圖示開頭_而且不是空掃():
    changed = []
    for key, model in _live():
        display, _raw, _status = plain.plain_model(model, page=key[1])
        before = {b["code"]: b.get("text") for b in display["blocks"] if b.get("_layer") == 1}
        after, _summary = health.dedupe_failures(display)
        for block in after["blocks"]:
            if block.get("_layer") != 1 or not block.get("glyph"):
                continue
            assert not block["text"].startswith(f"{block['glyph']} "), (key, block["text"])
            if block["text"] != before[block["code"]]:
                changed.append(key)
    assert any(key[1] == "alo" for key in changed), changed                 # 資產配置那一句真的被改到


def test_核心卡與展開區的字不經過結論燈那一步():
    display = {"blocks": [
        _lamp("⛔", "狀態：取數失敗", "⛔ 尚未設定"),
        {"code": "ALO-2", "title": "目標對照卡", "_layer": 2, "glyph": "⛔", "state_word": "狀態：取數失敗",
         "text": "⛔ 尚未設定"},
    ]}
    after, _summary = health.dedupe_failures(display)
    assert after["blocks"][0]["text"] == "尚未設定"
    assert after["blocks"][1]["text"] == "⛔ 尚未設定"                        # 只有層 1 的燈
