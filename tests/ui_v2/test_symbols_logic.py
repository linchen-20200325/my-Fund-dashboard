# -*- coding: utf-8 -*-
"""Phase 3 ◆／◇ 小批 `ui_v2/symbols.py` 的純函式測試（fast lane；不需要 streamlit）。

依據 `docs/v2/44_fund_ui_ssot.md` 第七節第三小節之七其三、其四與之八其三 (c-2)
（客戶裁示 `DEC-2026-10-17-03` 第 (3)(4) 題、`DEC-2026-10-17-07`；護欄 2：只改符號、顏色與文案，判定一字不改）：

1. ◆：持倉體檢偏離筆數大於零、資產配置超出容許帶 → 燈不著色（中性）、`◆`、「狀態：需要注意」，燈上文案字面照舊；
   偏離筆數、`_state`、`_max_bucket` 不動；灰燈與紅燈不動。
2. ◇：正式模型裡畫面字串的「⬜ 資料未備」全數換成「◇ 資料未備」，一處不多一處不少；`來源缺` 佔位圖示 `⬜` → `◇`；
   `⬜ 不適用`、`⬜ 無法判定`、`⬜ 未設定` 不動；`_` 開頭鍵上的字串不動。
3. 表格內單獨一個 `⬜` 的缺值格（其四第 2 條；總管 2026-10-17 裁定納入本批）：成因看 logic 的分支 ——
   logic 記在 `_missing_cells`／`_missing_fields` 的格（資料未備）改 `◇`，沒有記的（不適用、未設定、取數失敗、
   成因分不清）照舊 `⬜`；逐支驗「該記的有記、不該記的沒記」。
4. 不變式：除了上面明列的幾個鍵，套用前後模型深度相等（結構、數值、布林、`_` 鍵純量）。
5. 接線：五頁 `page.py` 各在正式模式分支、`plain.plain_model` 之後呼叫一次；示範模式不經過。

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
        assert (new["glyph"], new["state_word"], new["_tone"]) == ("◆", "狀態：需要注意", "中性"), key
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
        assert (new["glyph"], new["state_word"], new["_tone"]) == ("◆", "狀態：需要注意", "中性"), key
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


def test_狀態字前綴與同頁其他燈一致():
    from ui_v2 import health
    from ui_v2.alo import logic as A
    from ui_v2.hld import logic as H

    assert symbols.STATE_PREFIX == health.LIGHT_STATE_PREFIX
    for look in (H._LAMP_LOOK, A._LAMP_LOOK):
        assert all(word.startswith(symbols.STATE_PREFIX) for _glyph, word in look.values())
    assert symbols.STATE_WORD_ATTENTION.startswith(symbols.STATE_PREFIX)


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
            if path[-1] == "glyph" or a == "⬜":
                continue   # 圖示另驗（來源缺佔位那一條）；單獨一個 ⬜ 的缺值格另驗（第 3 節）
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
    assert {"⬜ 不適用", "⬜ 未設定"} <= seen, seen


def _reset_allowed(after, before):
    """把本批允許改的底線鍵（◆ 的 `_tone`、持倉體檢單檔展開的 `_fields`）還原成套用前的值，其餘照 after —— 給投影比對用。"""
    out = copy.deepcopy(after)
    for new, old in zip(out["blocks"], before["blocks"]):
        if "_tone" in old:
            new["_tone"] = old["_tone"]

    def restore(n, o):
        if isinstance(n, dict) and isinstance(o, dict):
            if "_fields" in o:
                n["_fields"] = copy.deepcopy(o["_fields"])
            for k in n:
                if k in o:
                    restore(n[k], o[k])
        elif isinstance(n, list) and isinstance(o, list):
            for a, b in zip(n, o):
                restore(a, b)

    restore(out, before)
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


# ───────────────────────── 3. 表格內單獨一個 ⬜ 的缺值格（依成因） ─────────────────────────


def _all_models():
    """示範＋正式模型（不經 plain；本節驗的是 logic 記的成因與 symbols 的換法，與換字無關）。"""
    return _PL._all_models()


def _cells(node, code=None, out=None):
    """[(塊代號, 節點)]：所有帶 `_missing_cells` 或 `_missing_fields` 的節點，以及所有含單獨 `⬜` 的節點。"""
    out = [] if out is None else out
    if isinstance(node, dict):
        code = node.get("code", code)
        out.append((code, node))
        for value in node.values():
            _cells(value, code, out)
    elif isinstance(node, (list, tuple)):
        for value in node:
            _cells(value, code, out)
    return out


def test_記為資料未備的格換成菱形_沒有記的單獨方塊照舊():
    converted = kept = 0
    for key, model in _all_models().items():
        after = _applied(model)
        for (code, old), (_, new) in zip(_cells(model), _cells(after)):
            marked = set(old.get("_missing_cells") or ())
            for k, v in old.items():
                if v != "⬜" or k == "glyph":
                    continue
                if k in marked:
                    assert new[k] == "◇", (key, code, k)
                    converted += 1
                else:
                    assert new[k] == "⬜", (key, code, k)
                    kept += 1
            labels = set(old.get("_missing_fields") or ())
            for f_old, f_new in zip(old.get("_fields") or (), new.get("_fields") or ()):
                if not (isinstance(f_old, tuple) and len(f_old) == 2):
                    continue   # 其他頁的 `_fields` 是值節點（dict），上面逐節點已驗
                label, v_old = f_old
                assert f_new[1] == ("◇" if (label in labels and v_old == "⬜") else v_old), (key, code, label)
    assert converted > 100 and kept > 50, (converted, kept)


def _marks(model):
    out = set()
    for code, node in _cells(model):
        for k in node.get("_missing_cells") or ():
            if node.get(k) == "⬜":
                out.add((code, k))
    return out


def test_不適用未設定與分不清的格_logic沒有記():
    """不適用（沒有目標、基準未選、合計不為正）、未設定、取數失敗、成因分不清的格，一格都不得被記成資料未備。"""
    never = {("ALO-2", "target_text"), ("ALO-7", "time_text"), ("HLD-6", "pay_date"),
             ("SET-3", "kind_text"), ("SET-3", "time_text")}
    for key, model in _all_models().items():
        assert not (_marks(model) & never), key
    from ui_v2.alo import fixtures as AF
    from ui_v2.alo import logic as A

    # 基準未選 ＝ 不適用：ALO-6 的基準值與兩個佔比格不記。
    rows = A.find_block(A.build_page_model(AF.scenario("nobasis")), "ALO-6")["_rows"]
    assert rows and all("_missing_cells" not in r for r in rows), rows
    # 沒有目標的類別（未分類）：目標、差額、內外三格不記。
    rows = A.find_block(A.build_page_model(AF.scenario("unbkt")), "ALO-2")["_rows"]
    no_target = [r for r in rows if not r["_has_target"]]
    assert no_target and all("_missing_cells" not in r for r in no_target), no_target


def test_資產配置_資料未備那幾支有記():
    from ui_v2.alo import fixtures as AF
    from ui_v2.alo import logic as A

    model = A.build_page_model(AF.scenario("nofx"))
    alo2 = A.find_block(model, "ALO-2")["_rows"]
    assert any(r.get("_missing_cells") == ("diff_text", "band_text") for r in alo2 if r["_has_target"])
    alo6 = A.find_block(model, "ALO-6")["_rows"]
    assert any(r.get("_missing_cells") == ("value_text", "in_bucket_text", "in_total_text") for r in alo6), alo6
    # 保單表查不到 → 保單格記。
    dataset = AF.scenario("full")
    dataset["policy"] = [p for p in dataset["policy"] if p["policy_id"] != "P001"]
    alo6 = A.find_block(A.build_page_model(dataset), "ALO-6")["_rows"]
    lost = [r for r in alo6 if r["policy_text"] == "⬜"]
    assert lost and all("policy_text" in r["_missing_cells"] for r in lost), lost
    # 每一類都缺基準值 ⇒ 沒有分母；沒有持倉的目標類別「目前比重」格記。
    dataset = AF.scenario("nofx")
    dataset["nav"] = [n for n in dataset["nav"] if n["ccy"] != "TWD"]
    for row in dataset["user_setting"]:
        if row["setting_key"] == "alo_target_weights":
            row["setting_value"] = list(row["setting_value"]) + [{"bucket": "債券（示意）", "weight_ratio": 0.0}]
        if row["setting_key"] == "alo_bucket_names":
            row["setting_value"] = list(row["setting_value"]) + ["債券（示意）"]
    alo2 = A.find_block(A.build_page_model(dataset), "ALO-2")["_rows"]
    empty = [r for r in alo2 if r["current_text"] == "⬜"]
    assert empty and all("current_text" in r["_missing_cells"] for r in empty), alo2


def test_市場總覽_無觀測的鍵與空格有記():
    from ui_v2.mkt import fixtures as MF
    from ui_v2.mkt import logic as M

    found7 = found6 = False
    for _name, dataset in MF.all_datasets().items():
        model = M.build_page_model(dataset)
        for row in M.find_block(model, "MKT-7")["_rows"] if hasattr(M, "find_block") else ():
            if row["obs_text"] == "⬜":
                assert row["_missing_cells"] == ("obs_text", "fetched_text", "tier_text", "delay_text")
                found7 = True
        if dataset.get("rows") and not found6:
            data = copy.deepcopy(dataset)
            data["rows"][0]["source_tier"] = None
            mkt6 = next(b for b in M.build_page_model(data)["blocks"] if b["code"] == "MKT-6")
            blank = [r for r in mkt6["_rows"] if r.get("source_tier") == "⬜"]
            if blank:
                assert all("source_tier" in r["_missing_cells"] for r in blank)
                found6 = True
    assert found7 and found6


def test_持倉體檢單檔展開_保單查不到記_類別留空不記():
    from ui_v2.hld import fixtures as HF
    from ui_v2.hld import logic as H

    args = copy.deepcopy(HF.scenario("full"))
    pid = next(h["policy_id"] for h in args["dataset"]["holding"] if h["policy_id"] != "DIRECT")
    args["dataset"]["policy"] = [p for p in args["dataset"]["policy"] if p["policy_id"] != pid]
    for h in args["dataset"]["holding"]:
        h["bucket"] = None
    model = H.build_page_model(**args)
    items = [n for _c, n in _cells(model) if "_fields" in n]
    lost = [n for n in items if dict(n["_fields"])["保單"] == "⬜"]
    assert lost and all(set(n["_missing_fields"]) == {"保單", "發行單位"} for n in lost), lost
    after = _applied(model)
    for n in [n for _c, n in _cells(after) if "_fields" in n]:
        fields = dict(n["_fields"])
        assert fields["類別"] == "⬜"   # 成因分不清（未分類或未填），照舊
        if n["_missing_fields"]:
            assert fields["保單"] == "◇" and fields["發行單位"] == "◇"


def test_設定與診斷_無紀錄的列有記_讀取失敗的列不記():
    from ui_v2.set import fixtures as SF
    from ui_v2.set import logic as S

    empty = failed = 0
    for name in SF.ALL_SCENARIO_NAMES:
        model = S.build_page_model(SF.scenario(name))
        for row in next(b for b in model["blocks"] if b["code"] == "SET-1")["_rows"]:
            if row["_empty"]:
                assert row["_missing_cells"] == ("at_text", "days_text", "compare_text")
                empty += 1
            elif row["_failed"]:
                assert "_missing_cells" not in row   # 成因是取數失敗，不是資料未備
                failed += 1
    assert empty and failed, (empty, failed)


def test_標的探索_缺格有記():
    from ui_v2.exp import logic as E

    node = E._missing_value("欄")
    assert node["text"] == "⬜" and node["_missing_cells"] == ("text",)
    symbols.mark_missing(node)
    assert node["text"] == "◇" and node["_state"] == E.STATE_MISSING


# ───────────────────────── 4. 接線 ─────────────────────────

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


def test_狀態徽章資料未備的圖示改菱形_文字與其他徽章不動():
    from ui_v2.set import logic as S

    nodes = [S.status_badge("資料未備"), S.status_badge("不適用"), S.status_badge("取數失敗")]
    before = copy.deepcopy(nodes)
    symbols.mark_missing({"badges": nodes})
    assert nodes[0] == {**before[0], "glyph": "◇"} and nodes[0]["text"] == "資料未備"
    assert nodes[1:] == before[1:]


def test_設定與診斷模型_資料未備徽章全數換成菱形():
    hits = 0
    for key, model in _all_models().items():
        if key[1] != "set":
            continue
        after = _applied(model)
        for _c, node in _cells(after):
            if node.get("_kind") == "狀態" and node.get("text") == "資料未備" and "glyph" in node:
                assert node["glyph"] == "◇", key
                hits += 1
    assert hits, "沒有帶圖示的資料未備徽章 —— 會變成空掃"


def test_市場總覽_取數失敗而沒有觀測的鍵_四格照舊方塊():
    from ui_v2.mkt import fixtures as MF
    from ui_v2.mkt import logic as M

    checked = 0
    base = next(d for d in MF.all_datasets().values() if d.get("rows"))
    built = copy.deepcopy(base)
    built["rows"] = [r for r in built["rows"] if r["indicator_key"] != "vol_index"]
    built["errors"] = {**(built.get("errors") or {}), "vol_index": "fetch_url returned None: ^VIX (kind=unreachable)"}
    for dataset in [*MF.all_datasets().values(), built]:
        errors = dataset.get("errors") or {}
        for row in M.find_block(M.build_page_model(dataset), "MKT-7")["_rows"]:
            if row["obs_text"] == "⬜" and row["indicator_key"] in errors:
                assert "_missing_cells" not in row, row
                after = {"blocks": [{"code": "MKT-7", "_rows": [copy.deepcopy(row)]}]}
                symbols.apply(after)
                cells = after["blocks"][0]["_rows"][0]
                assert [cells[k] for k in ("obs_text", "fetched_text", "tier_text", "delay_text")] == ["⬜"] * 4
                checked += 1
    assert checked, "fixtures 裡沒有取數失敗而沒有觀測的鍵 —— 會變成空掃"


def test_資產配置_直接持有不記保單格():
    from ui_v2.alo import fixtures as AF
    from ui_v2.alo import logic as A

    dataset = AF.scenario("full")
    dataset["policy"] = [p for p in dataset["policy"] if p["policy_id"] != "DIRECT"]
    rows = A.find_block(A.build_page_model(dataset), "ALO-6")["_rows"]
    direct = [r for r in rows if r["policy_text"] == "⬜"]
    assert direct and all("policy_text" not in (r.get("_missing_cells") or ()) for r in direct), direct
