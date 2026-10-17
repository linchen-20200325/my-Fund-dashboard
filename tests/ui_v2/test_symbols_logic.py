# -*- coding: utf-8 -*-
"""Phase 3 ◆／◇ 小批 `ui_v2/symbols.py` 的純函式測試（fast lane；不需要 streamlit）。

依據 `docs/v2/44_fund_ui_ssot.md` 第七節第三小節之七其三、其四與之八其三 (c-2)
（客戶裁示 `DEC-2026-10-17-03` 第 (3)(4) 題、`DEC-2026-10-17-07`；護欄 2：只改符號、顏色與文案，判定一字不改）：

1. ◆：持倉體檢偏離筆數大於零、資產配置超出容許帶 → 燈不著色（中性）、`◆`、「需要注意」，燈上文案字面照舊；
   偏離筆數、`_state`、`_max_bucket` 不動；灰燈與紅燈不動。
2. ◇：正式模型裡畫面字串的「⬜ 資料未備」全數換成「◇ 資料未備」，一處不多一處不少；`來源缺` 佔位圖示 `⬜` → `◇`；
   `⬜ 不適用`、`⬜ 無法判定`、`⬜ 未設定` 與表格裡單獨一個 `⬜` 不動；`_` 開頭鍵上的字串不動。
3. 不變式：除了上面明列的幾個鍵，套用前後模型深度相等（結構、數值、布林、`_` 鍵純量）。
4. 接線：五頁 `page.py` 各在正式模式分支、`plain.plain_model` 之後呼叫一次；示範模式不經過。

突變驗證（本批實跑）：把 `symbols.apply` 改成直接回傳、或把五頁任一處呼叫拿掉，本檔對應的測試轉紅。
"""

from __future__ import annotations

import copy
import pathlib
import re
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

from ui_v2 import plain, symbols  # noqa: E402

import test_plain_logic as _PL  # noqa: E402  （借用它已組好的正式模型：五頁 fixtures × 情境）

_MODELS = None


def _formal_models():
    """{(頁, 情境): plain_model 之後的一般畫面模型}（尚未套用 symbols）。"""
    global _MODELS
    if _MODELS is None:
        _MODELS = {key: plain.plain_model(model, page=key[0])[0] for key, model in _PL._live_models().items()}
    return _MODELS


def _applied(display):
    out = copy.deepcopy(display)
    symbols.apply(out)
    return out


def _block(display, code):
    return next(b for b in display["blocks"] if b.get("code") == code)


def _strings(node, private=False, path=()):
    """畫面字串（掛在非 `_` 鍵上的字串、以及非 `_` 鍵底下串列裡的字串）→ [(路徑, 字串)]。"""
    out = []
    if isinstance(node, dict):
        for key, value in node.items():
            is_private = isinstance(key, str) and key.startswith("_")
            if isinstance(value, str):
                if not is_private:
                    out.append((path + (key,), value))
            else:
                out += _strings(value, is_private, path + (key,))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            if isinstance(item, str):
                if not private:
                    out.append((path + (index,), item))
            else:
                out += _strings(item, private, path + (index,))
    elif isinstance(node, tuple):
        for index, item in enumerate(node):
            if not isinstance(item, str):
                out += _strings(item, private, path + (index,))
    return out


# ───────────────────────── 1. ◆ 需要注意 ─────────────────────────


def _attention_cases():
    return [(key, d) for key, d in _formal_models().items()
            if key[0] in ("hld", "alo") and _block(d, {"hld": "HLD-0", "alo": "ALO-0"}[key[0]]).get("_tone") == "黃"]


def test_偏離與超出容許帶的情境存在_否則下面會是空掃():
    pages = {key[0] for key, _ in _attention_cases()}
    assert pages == {"hld", "alo"}, pages


def test_持倉體檢偏離_燈不著色_以菱形需要注意呈現_文案與判定照舊():
    cases = [(k, d) for k, d in _attention_cases() if k[0] == "hld"]
    assert cases
    for key, before in cases:
        after = _applied(before)
        old, new = _block(before, "HLD-0"), _block(after, "HLD-0")
        assert old["_deviation_count"] > 0, key
        assert (new["glyph"], new["state_word"], new["_tone"]) == ("◆", "需要注意", "中性"), key
        assert new["text"] == old["text"] and re.match(r"有 \d+ 檔超出你設定的門檻", new["text"]), key
        for k in ("_state", "_deviation_count", "_reads", "lines", "buttons", "main_values"):
            assert new[k] == old[k], (key, k)
        # 畫面上已經沒有黃燈，說明句不得再寫「黃燈」。
        assert not any("黃燈" in line for line in new["detail_lines"]), key
        assert symbols.HLD0_NOTE_TO in new["detail_lines"], key


def test_資產配置超出容許帶_燈不著色_以菱形需要注意呈現_文案與判定照舊():
    cases = [(k, d) for k, d in _attention_cases() if k[0] == "alo"]
    assert cases
    for key, before in cases:
        after = _applied(before)
        old, new = _block(before, "ALO-0"), _block(after, "ALO-0")
        assert (new["glyph"], new["state_word"], new["_tone"]) == ("◆", "需要注意", "中性"), key
        assert new["text"] == old["text"] and re.search(r" 與目標差 \d+\.\d 個百分點$", new["text"]), key
        assert new["_max_bucket"] == old["_max_bucket"] is not None, key
        assert new["detail_lines"] == old["detail_lines"], key


def test_灰燈與紅燈不動_其他頁的黃燈不動():
    for key, before in _formal_models().items():
        after = _applied(before)
        for old, new in zip(before["blocks"], after["blocks"]):
            if old.get("code") in symbols.ATTENTION_CODES and old.get("_tone") == "黃":
                continue
            for k in ("glyph", "state_word", "_tone"):
                assert new.get(k) == old.get(k), (key, old.get("code"), k)


def test_只認黃燈_同一份模型套兩次結果不變():
    for key, before in _attention_cases():
        once = _applied(before)
        assert _applied(once) == once, key


# ───────────────────────── 2. ◇ 資料未備 ─────────────────────────


def test_畫面上的方塊資料未備全數換成菱形_一處不多一處不少():
    total = 0
    for key, before in _formal_models().items():
        after = _applied(before)
        ref = copy.deepcopy(before)
        symbols.mark_attention(ref)   # ◆ 那幾鍵另驗；這裡只比 ◇
        old, new = _strings(ref), _strings(after)
        assert [p for p, _ in old] == [p for p, _ in new], key
        for (path, a), (_, b) in zip(old, new):
            if path[-1] == "glyph":
                continue   # 圖示另驗（來源缺佔位那一條）
            assert b == a.replace("⬜ 資料未備", "◇ 資料未備"), (key, path, a, b)
            total += a.count("⬜ 資料未備")
        assert not any("⬜ 資料未備" in s for _, s in new), key
    assert total > 100, total   # 不是空掃（2026-10-17 實測數百處）


def test_方塊只留給不適用與無法判定_那幾句不動():
    seen = set()
    for key, before in _formal_models().items():
        after = _applied(before)
        for (path, a), (_, b) in zip(_strings(before), _strings(after)):
            if path[-1] == "glyph":
                continue
            for head in ("⬜ 不適用", "⬜ 無法判定", "⬜ 未設定"):
                if head in a:
                    seen.add(head)
                    assert head in b and a.count(head) == b.count(head), (key, a, b)
            if a == "⬜":
                assert b == "⬜", key   # 表格缺值格依成因對照那一條不在本批（44 之七其四第 2 條）
    assert {"⬜ 不適用", "⬜ 未設定"} <= seen, seen


def _reset_allowed(after, before):
    """把本批允許改的鍵（◆ 的 `_tone`）還原成套用前的值，其餘照 after —— 給投影比對用。"""
    out = copy.deepcopy(after)
    for new, old in zip(out["blocks"], before["blocks"]):
        if "_tone" in old:
            new["_tone"] = old["_tone"]
    return out


def test_不變式_除了明列的鍵_套用前後深度相等_底線鍵上的字串不動():
    allowed_block_keys = {"glyph", "state_word", "_tone", "detail_lines"}
    for key, before in _formal_models().items():
        after = _applied(before)
        assert _PL._projection(_reset_allowed(after, before), key[0]) == _PL._projection(before, key[0]), key
        for old, new in zip(before["blocks"], after["blocks"]):
            changed = {k for k in old if old[k] != new.get(k)}
            if old.get("code") in symbols.ATTENTION_CODES and old.get("_tone") == "黃":
                assert changed <= allowed_block_keys | {"text"}, (key, changed)
                assert new["text"] == old["text"]


def test_來源缺的佔位圖示改菱形_其他空狀態的圖示不動():
    node = {"blocks": [
        {"code": "SET-6", "placeholder": {"text": "尚無取數紀錄", "_empty_kind": "來源缺", "glyph": "⬜", "_tone": "灰"}},
        {"code": "SET-2", "placeholder": {"text": "⬜ 不適用：x", "_empty_kind": "算不出來", "glyph": "⬜", "_tone": "灰"}},
        {"code": "SET-0", "glyph": "⬜", "state_word": "狀態：中性", "_tone": "灰", "text": "尚無取數紀錄"},
    ]}
    symbols.apply(node)
    assert node["blocks"][0]["placeholder"]["glyph"] == "◇"
    assert node["blocks"][1]["placeholder"]["glyph"] == "⬜"
    assert node["blocks"][2]["glyph"] == "⬜"


def test_資產配置來源缺的佔位_在正式模型裡也改了():
    hits = 0
    for key, before in _formal_models().items():
        if key[0] != "alo":
            continue
        after = _applied(before)
        for old, new in zip(before["blocks"], after["blocks"]):
            ph_old, ph_new = old.get("placeholder"), new.get("placeholder")
            if isinstance(ph_old, dict) and ph_old.get("_empty_kind") == "來源缺" and ph_old.get("glyph") == "⬜":
                assert ph_new["glyph"] == "◇", key
                hits += 1
    assert hits, "沒有任何一個情境帶 ⬜ 圖示的來源缺佔位 —— 會變成空掃"


# ───────────────────────── 3. 接線 ─────────────────────────

_PAGES = ("mkt", "hld", "exp", "alo", "set")


@pytest.mark.parametrize("page", _PAGES)
def test_五頁正式模式分支在plain之後呼叫一次_示範模式不經過(page):
    src = (_ROOT / "ui_v2" / page / "page.py").read_text(encoding="utf-8")
    lines = src.split("\n")
    calls = [i for i, line in enumerate(lines) if "symbols.apply(model)" in line and not line.lstrip().startswith("#")]
    assert len(calls) == 1, (page, calls)
    plains = [i for i, line in enumerate(lines) if "plain.plain_model(model" in line]
    assert len(plains) == 1, (page, plains)
    # 緊接在 plain_model 之後（中間只隔註解或 record_raw），同一個縮排 —— 也就是同一個正式模式分支。
    between = [l.strip() for l in lines[plains[0] + 1:calls[0]]]
    assert all(l.startswith("#") for l in between), (page, between)
    def indent(text):
        return len(text) - len(text.lstrip())

    assert indent(lines[calls[0]]) == indent(lines[plains[0]]), page


def test_symbols不import任何模組():
    src = (_ROOT / "ui_v2" / "symbols.py").read_text(encoding="utf-8")
    imports = [l for l in src.split("\n") if re.match(r"\s*(import|from)\s", l)]
    assert imports == ["from __future__ import annotations"], imports
