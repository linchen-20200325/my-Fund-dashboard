# -*- coding: utf-8 -*-
"""單檔基金查詢呈現元件 隔離式 FAKE Preview：對 **production renderer／wording 的記憶體內突變測試**（不寫檔）。

做法：讀 production 原始碼 → 以字串替換出一個壞版本 → 在全新 module 命名空間內 exec → 對它跑與正式版相同的檢查組（`S.battery`）。
每個突變都必須（a）真的改到原始碼（目標字串恰好出現一次）、（b）不崩潰（崩潰型例外不算被殺）、（c）至少一個檢查失敗。
未突變的正式版必須零違規（基準線）。突變字串只存在於本測試檔的記憶體裡。
"""
from __future__ import annotations

import pathlib
import sys
import types

import pytest

import fund_lookup_cmp_support as S

import fund_lookup_renderer as R  # noqa: E402
import fund_lookup_wording as W  # noqa: E402

RENDERER_SRC = (S.POC / "fund_lookup_renderer.py").read_text(encoding="utf-8")
WORDING_SRC = (S.POC / "fund_lookup_wording.py").read_text(encoding="utf-8")


def _load(src: str, name: str, path: pathlib.Path) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__file__ = str(path)
    exec(compile(src, str(path), "exec"), mod.__dict__)    # noqa: S102 - 測試內的記憶體內突變，來源為本 repo 的原始碼字串
    return mod


def _mutate(src: str, old: str, new: str) -> str:
    assert src.count(old) == 1, f"突變目標必須恰好出現一次，實際 {src.count(old)} 次：{old[:60]!r}"
    return src.replace(old, new)


RENDERER_MUTATIONS = [
    ("no-escape", 'escape(str(value), quote=True)', 'str(value)'),
    ("no-dollar-escape", '.replace("$", "&#36;")', ''),
    ("no-backslash-escape", '.replace("\\\\", "&#92;")', ''),
    ("fake-tag-never", "    if fake:\n        parts.append(", "    if False:\n        parts.append("),
    ("fake-tag-inverted", "    if fake:\n        parts.append(", "    if not fake:\n        parts.append("),
    ("failed-shows-undetermined", 'W.status("fetch_failed")', 'W.status("undetermined")'),
    ("unmatched-shows-failed", 'W.status("undetermined")', 'W.status("fetch_failed")'),
    ("failed-not-alert", '[W.pending("failed_impact"), W.pending(f"failed_{reason}"), W.pending("not_identity")], "alert"',
     '[W.pending("failed_impact"), W.pending(f"failed_{reason}"), W.pending("not_identity")], "status"'),
    ("blocked-not-alert", 'return "blocked", W.pending("blocked_impact"), extra[1:], "alert"', 'return "blocked", W.pending("blocked_impact"), extra[1:], "status"'),
    ("missing-shown-as-zero", 'f\'<span class="fl-value-missing" data-kind="missing">{W.pending("field_missing")}</span>\'',
     'f\'<span class="fl-value-missing" data-kind="missing">0</span>\''),
    ("conflict-uses-missing-wording", '{W.pending("field_conflict")}</span>\', "conflict"', '{W.pending("field_missing")}</span>\', "conflict"'),
    ("missing-uses-conflict-status", '"missing"\n    if field.status is FieldStatus.CONFLICT', '"value"\n    if field.status is FieldStatus.CONFLICT'),
    ("always-draw-input-code", "    if echoed:", "    if True:"),
    ("dividend-swapped", 'DIVIDEND_KEYS = {"dist": "div_mode_distributing", "accum": "div_mode_accumulating"}',
     'DIVIDEND_KEYS = {"dist": "div_mode_accumulating", "accum": "div_mode_distributing"}'),
    ("rows-reordered", '("inception", "row_inception", f.inception_on, None), ("mgmt-fee", "row_mgmt_fee", f.mgmt_fee_rate_pct, None)',
     '("mgmt-fee", "row_mgmt_fee", f.mgmt_fee_rate_pct, None), ("inception", "row_inception", f.inception_on, None)'),
    ("extra-field-row", "    if rows:\n        parts.append", '    rows.append(_dl_row("ccy", "row_name", "USD", "value"))\n    if rows:\n        parts.append'),
    ("idle-extra-text", '{W.pending("not_queried")}</div></div>\')', '{W.pending("not_queried")} NAV</div></div>\')'),
    ("state-attr-constant", 'data-state="{name}"', 'data-state="result"'),
    ("reason-attr-dropped", 'reason_attr = f\' data-reason="{escape(view.reason_code)}"\' if view.reason_code else ""', 'reason_attr = ""'),
    ("region-role-dropped", 'data-state="{name}"{reason_attr} role="region" aria-labelledby="{ID_STATUS}">', 'data-state="{name}"{reason_attr}>'),
    ("isin-note-dropped", 'data-block="isin-note"', 'data-block="x-note"'),
    ("failed-says-not-exist", '[W.pending("failed_impact"), W.pending(f"failed_{reason}"), W.pending("not_identity")], "alert"',
     '[W.pending("failed_impact"), W.pending(f"failed_{reason}"), "基金" + "不存在"], "alert"'),
    ("non-result-draws-name", "    if view.state is LookupState.RESULT:\n        f = view.fields",
     '    rows.append(_dl_row("name", "row_name", "X", "value"))\n    if view.state is LookupState.RESULT:\n        f = view.fields'),
    ("provenance-line-added", 'parts.append(f\'<div class="uv3-note" data-note="single">{W.pending("single_note")}</div>\')',
     'parts.append(f\'<div class="uv3-note" data-note="single">{W.pending("single_note")}（Provider 來源）</div>\')'),
]


def test_baseline_the_unmutated_source_loaded_the_same_way_has_zero_violations():
    assert S.battery(_load(RENDERER_SRC, "fund_lookup_renderer_clean", S.POC / "fund_lookup_renderer.py")) == []


@pytest.mark.parametrize("name,old,new", RENDERER_MUTATIONS, ids=[m[0] for m in RENDERER_MUTATIONS])
def test_every_renderer_mutation_is_caught_by_at_least_one_check_and_does_not_merely_crash(name, old, new):
    mutant = _load(_mutate(RENDERER_SRC, old, new), f"fund_lookup_renderer_mut_{name.replace('-', '_')}", S.POC / "fund_lookup_renderer.py")
    found = S.battery(mutant)
    assert found, f"突變 {name} 沒有被任何檢查抓到"
    assert not any(v[0] == "CRASH" for v in found), f"突變 {name} 只是崩潰，不算被殺：{found[:1]}"


WORDING_MUTATIONS = [
    ("blocked-url-says-fund-missing", '_w("blocked_url_shape", "請輸入基金代碼，不要貼網址")', '_w("blocked_url_shape", "查無基金")'),
    ("not-identity-says-not-exist", '_w("not_identity", "這不是對基金身份的判斷")', '_w("not_identity", "這檔基金不存在")'),
    ("page-unmatched-claims-confirmed", '_w("unmatched_no_page", "找不到對應頁面")', '_w("unmatched_no_page", "已確認")'),
    ("result-state-mentions-nav", '_w("state_result", "查詢結果（模擬資料）")', '_w("state_result", "查詢結果（NAV 模擬資料）")'),
    ("missing-wording-empty-dash", '_w("field_missing", "此欄尚無可顯示的值")', '_w("field_missing", "-")'),
    ("dist-label-flipped", '_w("div_mode_distributing", "配息型")', '_w("div_mode_distributing", "累積型")'),
]


@pytest.mark.parametrize("name,old,new", WORDING_MUTATIONS, ids=[m[0] for m in WORDING_MUTATIONS])
def test_every_wording_mutation_is_caught_by_at_least_one_check_and_does_not_merely_crash(name, old, new, monkeypatch):
    wording = _load(_mutate(WORDING_SRC, old, new), "fund_lookup_wording", S.POC / "fund_lookup_wording.py")
    monkeypatch.setitem(sys.modules, "fund_lookup_wording", wording)
    mutant = _load(RENDERER_SRC, "fund_lookup_renderer_mut_w", S.POC / "fund_lookup_renderer.py")
    found = S.battery(mutant)        # battery 在呼叫時才 import 字樣表，所以它與 renderer 看到同一份（被突變的）字樣
    clean = W.FUND_LOOKUP_PENDING
    assert [k for k, w in wording.FUND_LOOKUP_PENDING.items() if clean[k].text != w.text], f"突變 {name} 沒有改到任何字樣"
    assert found, f"字樣突變 {name} 沒有被任何檢查抓到"
    assert not any(v[0] == "CRASH" for v in found), f"字樣突變 {name} 只是崩潰，不算被殺：{found[:1]}"


def test_the_checkers_themselves_turn_red_on_hand_made_bad_pages():
    assert S.forbidden_word_violations("<div>這檔基金不存在</div>")
    assert S.raw_script_violations("<script>x</script>") and S.raw_script_violations("<img src=x>") and S.raw_script_violations("<b onclick=1>")
    assert S.special_char_violations("a<b") and S.special_char_violations("a$b") and S.special_char_violations("a\\b")
    assert S.field_violations('<div data-row="name"></div><div data-row="input-code"></div>')                   # 順序錯
    assert S.field_violations('<div data-row="ccy"></div>')                                                       # 未核准欄位
