# -*- coding: utf-8 -*-
"""ui_v2/alo/live.py 的純函式測試（fast lane；不需要 streamlit、不碰舊樹、不打網路）。

依據 docs/v2/49_data_integration_plan.md §3.4 第 6 項（正式入口不帶示意字樣）、
2026-09-28 客戶核准的 docs/wireframes/draft_alo_live.html，以及 `CLAUDE.md` §1（Fail Loud）。
"""

from __future__ import annotations

import json
import math
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2.alo import fixtures, live, logic  # noqa: E402

_CORE, _SAT, _CASH = fixtures.CORE, fixtures.SATELLITE, fixtures.CASH


def _weights(pairs):
    return json.dumps([{"bucket": b, "weight_ratio": w} for b, w in pairs], ensure_ascii=False)


def _rows(**values):
    """做出 L2 `load_user_settings()["rows"]` 的形狀（`setting_value` 是試算表上的原字串）。"""
    return {key: {"setting_key": key, "setting_value": text, "value_kind": "list",
                  "updated_at": "2026-09-20T06:00:00Z"}
            for key, text in values.items()}


def _by_key(rows):
    return {r["setting_key"]: r for r in rows}


# ═══════════════════════ 設定值解析：好的那一邊 ═══════════════════════


def test_五個鍵一定都在_沒設定的那一列值為None():
    rows, problem = live.parse_user_settings({})
    assert problem is None
    assert [r["setting_key"] for r in rows] == list(live.SETTING_KEYS)
    assert all(r["setting_value"] is None and r["updated_at"] is None for r in rows)
    # `logic._setting_row` 讀不到鍵會 KeyError —— 五列都在才不會炸。
    dataset = dict(fixtures.scenario("full"), user_setting=rows)
    assert logic.build_page_model(dataset)["title"] == logic.PAGE_TITLE


def test_五個鍵都解析得出來_而且吃得進build_page_model():
    rows, problem = live.parse_user_settings(_rows(
        alo_target_weights=_weights([(_CORE, 0.6), (_SAT, 0.3), (_CASH, None)]),
        alo_tolerance_pp="4",
        alo_basis=logic.BASIS_COST,
        alo_bucket_names=json.dumps([_CORE, _SAT, _CASH], ensure_ascii=False),
        alo_scenario_input=json.dumps([{"bucket": _SAT, "amount_twd": 100000}], ensure_ascii=False),
    ))
    assert problem is None
    got = _by_key(rows)
    assert got["alo_target_weights"]["setting_value"] == [
        {"bucket": _CORE, "weight_ratio": 0.6},
        {"bucket": _SAT, "weight_ratio": 0.3},
        {"bucket": _CASH, "weight_ratio": None},
    ]
    assert got["alo_tolerance_pp"]["setting_value"] == 4.0
    assert got["alo_basis"]["setting_value"] == logic.BASIS_COST
    assert got["alo_bucket_names"]["setting_value"] == [_CORE, _SAT, _CASH]
    assert got["alo_scenario_input"]["setting_value"] == [{"bucket": _SAT, "amount_twd": 100000}]
    model = logic.build_page_model(dict(fixtures.scenario("full"), user_setting=rows))
    assert logic.find_block(model, "ALO-2")["_rows"], "解析出來的目標沒有進 ALO-2"


def test_解析出來的形狀與fixtures那一份逐欄相同():
    """示範模式的 `user_setting` 列長什麼樣，正式模式就要長什麼樣（同一個 `logic` 吃）。"""
    rows, _ = live.parse_user_settings({})
    demo = fixtures.user_settings(targets=fixtures.TARGETS, tolerance=fixtures.TOLERANCE,
                                  basis=fixtures.BASIS_COST, bucket_names=fixtures.BUCKET_NAMES,
                                  scenario_rows=fixtures.SCENARIO_ROWS)
    assert [r["setting_key"] for r in rows] == [r["setting_key"] for r in demo]
    assert all(set(r) == set(demo[0]) for r in rows)


def test_浮點金額剛好是整數時照收_同一個數不是換算():
    rows, problem = live.parse_user_settings(_rows(
        alo_scenario_input=json.dumps([{"bucket": _SAT, "amount_twd": 100000.0}], ensure_ascii=False)))
    assert problem is None
    assert _by_key(rows)["alo_scenario_input"]["setting_value"] == [{"bucket": _SAT, "amount_twd": 100000}]


# ═══════════════════════ 設定值解析：壞的那一邊（一律 fail loud，不當成「尚未設定」）═══════════════════════


@pytest.mark.parametrize("key, text, why", [
    ("alo_target_weights", "不是 JSON", "不是 JSON"),
    ("alo_target_weights", '{"bucket": "x"}', "不是陣列"),
    ("alo_target_weights", '[{"bucket": "x"}]', "少一個欄位"),
    ("alo_target_weights", '[{"bucket": "x", "weight_ratio": 0.5, "zz": 1}]', "多一個欄位"),
    ("alo_target_weights", '[{"bucket": "", "weight_ratio": 0.5}]', "bucket 空字串"),
    ("alo_target_weights", '[{"bucket": "x", "weight_ratio": 60}]', "百分比寫成整數 → 100 倍誤差"),
    ("alo_target_weights", '[{"bucket": "x", "weight_ratio": -0.1}]', "負數"),
    ("alo_target_weights", '[{"bucket": "x", "weight_ratio": NaN}]', "NaN"),
    ("alo_target_weights", '[{"bucket": "x", "weight_ratio": Infinity}]', "Infinity"),
    ("alo_target_weights", '[{"bucket": "x", "weight_ratio": true}]', "布林不是數"),
    ("alo_target_weights", ' [] ', "前後有空白"),
    ("alo_tolerance_pp", "四", "不是數"),
    ("alo_tolerance_pp", "nan", "NaN"),
    ("alo_tolerance_pp", "1e999", "溢位成 inf"),
    ("alo_tolerance_pp", " 4 ", "前後有空白"),
    ("alo_basis", "cost", "舊存值"),
    ("alo_basis", "成本 ", "帶空白"),
    ("alo_basis", "市值成本", "兩個接起來"),
    ("alo_bucket_names", '["a", 1]', "元素不是字串"),
    ("alo_bucket_names", '["a", "  "]', "元素只有空白"),
    ("alo_scenario_input", '[{"bucket": "x", "amount_twd": 1.5}]', "金額不是整數"),
    ("alo_scenario_input", '[{"bucket": "x", "amount_twd": "100"}]', "金額是字串"),
])
def test_壞值一律回訊息_而且該鍵不會被說成尚未設定(key, text, why):
    rows, problem = live.parse_user_settings(_rows(**{key: text}))
    assert problem is not None, (key, text, why)
    assert key in problem, (key, why)
    # 值一律不交出去 —— 由 `source.py` 把整張 `user_setting` 清空、改走取數失敗那條路。
    assert _by_key(rows)[key]["setting_value"] is None


def test_極深巢狀不崩_當成壞值():
    rows, problem = live.parse_user_settings(_rows(alo_bucket_names="[" * 100000 + "]" * 100000))
    assert problem is not None and _by_key(rows)["alo_bucket_names"]["setting_value"] is None


def test_L1說這一列解析不了_就不是尚未設定():
    """L1 `load_user_settings` docstring 逐字：`broken_keys` 的鍵「畫面應顯示錯誤狀態，不是 ⬜ 未設定」。"""
    rows, problem = live.parse_user_settings({}, broken_keys=["alo_tolerance_pp"])
    assert problem is not None and "alo_tolerance_pp" in problem
    assert _by_key(rows)["alo_tolerance_pp"]["setting_value"] is None


def test_不是本頁的鍵不影響():
    rows, problem = live.parse_user_settings(_rows(set_max_age_days="21"), broken_keys=["set_max_age_days"])
    assert problem is None and len(rows) == len(live.SETTING_KEYS)


def test_多個問題一起回報_不是只回第一個():
    _rows_out, problem = live.parse_user_settings(_rows(alo_tolerance_pp="四", alo_basis="cost"))
    assert "alo_tolerance_pp" in problem and "alo_basis" in problem


# ═══════════════════════ 兩張表一起失敗（示範模式分得開、正式模式分不開）═══════════════════════


def test_holding與policy一起標失敗():
    out = live.tables_failed_together("上游 503")
    assert out == {"holding": "上游 503", "policy": "上游 503"}
    assert set(out) <= set(logic.FETCHABLE_TABLES)     # build_page_model 認得這兩個鍵
    model = logic.build_page_model(dict(fixtures.scenario("full"), errors=out, holding=[], policy=[]))
    assert model["title"] == logic.PAGE_TITLE


# ═══════════════════════ 正式模式的模型調整 ═══════════════════════


def _live_model(name="full"):
    # 正式路徑（page 拿到 save_live 時）明確傳已接上的鍵；預設值是空（fail-closed）。
    return live.apply_live_notes(logic.build_page_model(fixtures.scenario(name)),
                                 wired_keys=live.SAVE_WIRED_KEYS)


def _all_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _all_strings(value)
    elif isinstance(node, (list, tuple, set)):
        for value in node:
            yield from _all_strings(value)


@pytest.mark.parametrize("name", fixtures.ALL_SCENARIO_NAMES)
def test_示意字樣在正式模式的模型裡一個都不剩(name):
    model = _live_model(name)
    assert model["hint_note"] == ""
    strings = list(_all_strings(model))
    assert logic.HINT_NOTE not in strings
    assert not any(logic.PAGE_HINT_NOTE in s for s in strings)


def test_正控_示範模式的模型本來就有示意字樣():
    model = logic.build_page_model(fixtures.scenario("full"))
    assert model["hint_note"] == logic.PAGE_HINT_NOTE
    assert sum(logic.HINT_NOTE in b["detail_lines"] for b in model["blocks"]) >= 6


def test_不改呼叫端手上的那一份():
    model = logic.build_page_model(fixtures.scenario("full"))
    before = logic.find_block(model, "ALO-1")["detail_lines"][:]
    live.apply_live_notes(model)
    assert logic.find_block(model, "ALO-1")["detail_lines"] == before
    assert model["hint_note"] == logic.PAGE_HINT_NOTE


def _buttons(model):
    out = []
    for block in model["blocks"]:
        out.extend(block.get("buttons", ()) or ())
    return out


def test_只有尚未接上寫入的存檔停用並寫出原因_其餘不動():
    """2026-10-09 更正（舊名 `test_會寫user_setting的按鈕停用並寫出原因_其餘不動`）：
    舊版斷言「凡是 `_writes` 非空的按鈕一律停用」—— 那正是客戶 2026-10-09 裁示要改掉的行為
    （ALO-1／ALO-4 的存檔接上寫入）。現行：只有要寫的鍵不全在 `SAVE_WIRED_KEYS` 的那一枚停用，
    實質就是 ALO-3（`alo_scenario_input`，存檔仍未授權）。匯出、導覽、新增列三類的比對一字未改。"""
    demo = logic.build_page_model(fixtures.scenario("full"))
    model = _live_model("full")
    disabled = [b for b in _buttons(model) if not b["_enabled"]]
    assert [b["_keys"] for b in disabled] == [("alo_scenario_input",)], disabled
    assert disabled[0]["disabled_reason"] == live.SAVE_DISABLED_REASON
    for code in ("ALO-1", "ALO-4"):
        save = [b for b in logic.find_block(model, code)["buttons"] if b["_writes"]]
        assert len(save) == 1 and save[0]["_enabled"] is True, code
        assert save[0]["disabled_reason"] == "", code
    # 匯出、導覽、新增列三類一字未動（連標籤與停用原因都與示範模式相同）。
    same = [(b["label"], b["_enabled"], b["disabled_reason"])
            for b in _buttons(model) if not b["_writes"]]
    assert same == [(b["label"], b["_enabled"], b["disabled_reason"])
                    for b in _buttons(demo) if not b["_writes"]]


def test_沒有寫入函式時_三枚存檔照舊全部停用():
    """`page.render` 沒拿到 `save_live` 時傳 `wired_keys=()`：那時按了不會存，一律停用（與接寫入之前相同）。"""
    for kwargs in ({"wired_keys": ()}, {}):          # 2026-10-09 稽核回修：預設值就是空（fail-closed）
        model = live.apply_live_notes(logic.build_page_model(fixtures.scenario("full")), **kwargs)
        saves = [b for b in _buttons(model) if b["_writes"]]
        assert len(saves) == 3, kwargs
        assert all(not b["_enabled"] and b["disabled_reason"] == live.SAVE_DISABLED_REASON
                   for b in saves), kwargs


def test_停用判斷看按鈕的鍵_不看塊代碼():
    """fail-closed：一枚會寫的按鈕只要有一個鍵沒接上（或根本沒帶鍵）就停用。"""
    model = logic.build_page_model(fixtures.scenario("full"))
    alo1_save = logic.find_block(model, "ALO-1")["buttons"][0]
    alo1_save["_keys"] = ("alo_target_weights", "alo_scenario_input")
    alo4_save = [b for b in logic.find_block(model, "ALO-4")["buttons"] if b["_writes"]][0]
    alo4_save["_keys"] = ()
    out = live.apply_live_notes(model, wired_keys=live.SAVE_WIRED_KEYS)
    for code in ("ALO-1", "ALO-4"):
        save = [b for b in logic.find_block(out, code)["buttons"] if b["_writes"]][0]
        assert save["_enabled"] is False and save["disabled_reason"] == live.SAVE_DISABLED_REASON, code


def test_停用原因逐字等於客戶核准的那一句():
    """客戶 2026-09-28 逐字核准（草稿 `docs/wireframes/draft_alo_save_disabled.html`，PR #861）。
    ⛔ 不准加字、不准補後半句 —— 客戶砍掉「按了不會存下任何東西」，理由是本頁根本沒有存這個動作。"""
    assert live.SAVE_DISABLED_REASON == "存檔寫入端尚未接上，這一輪只讀不寫"


def test_停用原因刻意不沿用mkt那一句_因為那一句在本頁是假的():
    """`ui_v2/mkt/page.py` 有 2 個 `on_click`（真的寫 `st.session_state`）⇒ mkt 那句字面正確；
    同一句在本頁的 ALO-3 是假的 —— 它的鍵 `alo_scenario_input` 在本頁沒有任何寫入路徑。
    2026-10-09 更正：舊版另斷言 `ui_v2/alo/page.py` 的 `on_click` 為 0、`source.py` 沒有 save 函式；
    ALO-1／ALO-4 接上寫入後兩者都不再成立（那正是本次裁示要改的行為）。本句現在只停用在 ALO-3 上，
    所以改釘「ALO-3 的鍵不在已接上的集合裡」—— 那才是這一句仍然為真的前提。"""
    mkt_live = pytest.importorskip("ui_v2.mkt.live")
    assert live.SAVE_DISABLED_REASON != mkt_live.SAVE_DISABLED_REASON
    for implies_saved in ("存了", "留不到", "下次開頁"):
        assert implies_saved not in live.SAVE_DISABLED_REASON, implies_saved
    assert "alo_scenario_input" not in live.SAVE_WIRED_KEYS
    assert set(live.SAVE_WIRED_KEYS) == {"alo_target_weights", "alo_tolerance_pp",
                                         "alo_basis", "alo_bucket_names"}


def test_正式模式的模型零禁詞_零方向詞零箭頭():
    for name in fixtures.ALL_SCENARIO_NAMES:
        text = "\n".join(_all_strings(_live_model(name)))
        for word in logic.FORBIDDEN_DIRECTION_WORDS + logic.FORBIDDEN_ADVICE_WORDS:
            assert word not in text, (name, word)
        for arrow in logic.FORBIDDEN_ARROWS:
            assert arrow not in text, (name, arrow)
        for word in logic.FORBIDDEN_BUTTON_WORDS:
            assert word not in [b["label"] for b in _buttons(_live_model(name))], (name, word)


def test_live的import就是那幾個_純函式模組():
    """⚠️ 刻意用 AST 不用字面掃描：本檔的 docstring 自己就寫著「不 import streamlit」，
    字面掃描會掃到那一句話而誤報（`CLAUDE.md` §-1.5.1c 判定 2：字表選錯，掃再多次都沒用）。
    整個 `ui_v2/` 的 import 隔離另有 fail-closed 守衛 tests/ui_v2/test_ui_v2_live_import_guard.py。"""
    import ast

    tree = ast.parse((_ROOT / "ui_v2" / "alo" / "live.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = ("." * node.level) + (node.module or "")
            names.add(prefix)
            names.update(prefix + ("." if node.module else "") + a.name for a in node.names)
    # 2026-10-13 第二輪 N-b：加 `datetime.date`（解析淨值日；標準庫、純函式，不讀時鐘 —— today 由呼叫端注入）。
    # 2026-10-13 客戶裁示（10 天單一共用定義）：加 `from .. import thresholds`（`ui_v2/thresholds.py`，純常數、
    # 不 import 任何東西；不是姊妹頁、不是舊樹 —— 舊樹 `shared` 被 import 守衛第 (5) 條擋，所以門檻住在 ui_v2 底下）。
    assert names == {"__future__", "__future__.annotations", "copy", "datetime", "datetime.date", "json", "math", "re",
                     ".", ".logic", "..", "..thresholds"}, names


# ═══════════════════════ ALO-GAP-分母全缺：總管 2026-09-28 盯住的那條界線 ═══════════════════════
#
# 「只在『每一檔都沒有基準值、而且缺的理由只有一種』時改畫 ⬜，其餘照舊 raise」——
# 下面四條把界線的兩邊都釘住：放行的那一種要放行，不放行的兩種要照舊炸。
# → 2026-10-13 更正（有意識的更正，不是漏刪；總管 2026-10-13 派工）：「理由不只一種」那一種改為逐類別寫理由、
#   不再炸（見 ALO-GAP-分母全缺）；「有值卻加起來不為正」那一種照舊炸。


def _mv(dataset):
    for row in dataset["user_setting"]:
        if row["setting_key"] == "alo_basis":
            row["setting_value"] = logic.BASIS_MV
    return dataset


def test_分母全缺_理由只有一種_改畫來源缺而不是炸掉():
    """接真資料時真正會走到的那一種：~~`nav` 在 L2 是 PENDING_TABLES~~ 本頁不取淨值
    （2026-10-09：L2 已把 nav 移出 PENDING_TABLES，但 alo 取淨值未獲授權；狀態更新，不是漏刪）⇒ 每一檔都沒有基準值。"""
    dataset = _mv(fixtures.scenario("full"))
    dataset["nav"] = []
    block = logic.find_block(logic.build_page_model(dataset), "ALO-2")
    assert block["placeholder"]["text"] == logic.empty_source_text(["nav"])
    assert block["placeholder"]["_empty_kind"] == "來源缺"
    assert block["_rows"] == []


def test_分母全缺_理由不只一種_逐類別各寫自己的理由_不再炸():
    """~~一類缺 `nav`、一類缺匯率 —— `44` 沒有這種情形的畫法，不准自己編一句。（舊名 `…_照舊raise`）~~
    → 2026-10-13 更正（有意識的更正，不是漏刪；依據：總管 2026-10-13 派工「非美元不崩頁、缺淨值或缺匯率照實呈現
    資料未備」；見 `logic.GAPS["ALO-GAP-分母全缺"]`）：接上真淨值後，美元與非美元匯率都還在閘門後面，
    這一種在真資料裡會出現。改為照 `44` ALO-2 空狀態逐類別寫各自的缺值字面（**沒有新句子**），
    沒有持倉的目標類別只印 ⬜。舊斷言寫下時為真（當時真資料走不到）；被推翻的是它的前提。"""
    dataset = _mv(fixtures.scenario("full"))
    dataset["market_indicator"] = []                                     # 美元那幾類缺匯率
    dataset["nav"] = [r for r in dataset["nav"] if r["fund_code"] not in ("BBBB", "DDDD")]
    values = logic._category_values(dataset, logic.BASIS_MV,
                                    logic.setting_value(dataset, "alo_bucket_names"))
    reasons = {v["reason"] for v in values.values()}
    assert len(reasons) == 2 and None not in reasons, "前提沒成立：這個資料集沒有兩種理由"
    block = logic.find_block(logic.build_page_model(dataset), "ALO-2")
    assert block["placeholder"] is None
    texts = {r["current_text"] for r in block["_rows"]}
    assert reasons <= texts                                              # 每一種理由都照字面上了畫面
    assert texts <= reasons | {"⬜"}                                     # 除此之外只有 ⬜，沒有新編的字
    assert all(r["_current_pct"] is None and r["_diff"] is None for r in block["_rows"])
    assert not any(r["current_text"].endswith("%") for r in block["_rows"])  # 不把「沒有分母」寫成 0%
    assert any(line.startswith("合計未涵蓋 ") for line in block["tail_lines"])


def test_有值卻加起來不為正_照舊raise():
    dataset = fixtures.scenario("full")                                   # 成本基準
    for holding in dataset["holding"]:
        holding["cost_twd"] = 0
    with pytest.raises(ValueError, match="分母為零或負"):
        logic.build_page_model(dataset)


def test_負控_市值基準但有台幣淨值時分母為正_根本不走那個分支():
    """這一條記的是一次探針失誤：`full` 只拿掉 `market_indicator` 並不會讓分母為 0 ——
    現金那一類的 DDDD 是台幣、淨值還在，分母 ＝ 50050。**拿它當「界線沒鬆」的證據是錯的。**"""
    dataset = _mv(fixtures.scenario("full"))
    dataset["market_indicator"] = []
    values = logic._category_values(dataset, logic.BASIS_MV,
                                    logic.setting_value(dataset, "alo_bucket_names"))
    assert sum(v["value"] for v in values.values() if v["value"] is not None) > 0
    assert logic.find_block(logic.build_page_model(dataset), "ALO-2")["_rows"]     # 照常出列


# ═══════════════════════ 市值基準：美元／新臺幣／歐元（2026-10-13 客戶裁示：資產配置必須是真資料）═══════════════════════
#
# ALO-GAP-非美元幣別：非美元幣別依 49 §6.1 Q9 換鍵（`fx_twd_per_<ISO 小寫>`），取 obs_date 規則同美元；
# 缺匯率照 44 ALO-2 空狀態的既有字面「⬜ 資料未備：缺換算匯率 <鍵>」，不炸。


def _to_eur(dataset, code="CCCC"):
    """把一檔美元基金改成歐元計價（持倉列與淨值列一起改；淨值列的幣別來自持倉列，同 L2）。"""
    for row in dataset["holding"]:
        if row["fund_code"] == code:
            row["ccy"] = "EUR"
    for row in dataset["nav"]:
        if row["fund_code"] == code:
            row["ccy"] = "EUR"
    return dataset


def _fx_row(key, obs_date, value):
    return {"indicator_key": key, "obs_date": obs_date, "release_date": obs_date, "value_num": value,
            "value_unit": "新臺幣／EUR", "source_tier": "市場指標", "is_revised": False,
            "fetched_at": "2026-09-23T01:30:00Z"}


def _holding(dataset, code):
    return next(h for h in logic.aggregated_holdings(dataset) if h["fund_code"] == code)


def test_市值基準_新臺幣與美元_照淨值乘單位數_美元再乘不晚於淨值日的最近一筆匯率():
    dataset = _mv(fixtures.scenario("full"))
    # 新臺幣：BBBB 10000 單位 × 最近一筆淨值 21.5，不乘匯率
    assert logic.basis_value(dataset, _holding(dataset, "BBBB"), logic.BASIS_MV) == (10000 * 21.5, None)
    # 美元：AAAA 1000 × 15.2（09-23）× 32.0（obs 09-22；09-24 那筆晚於淨值日，不取）
    value, reason = logic.basis_value(dataset, _holding(dataset, "AAAA"), logic.BASIS_MV)
    assert reason is None and math.isclose(value, 1000 * 15.2 * 32.0)


def test_市值基準_歐元有匯率_換鍵換算_只取不晚於淨值日的最近一筆():
    dataset = _to_eur(_mv(fixtures.scenario("full")))
    dataset["market_indicator"] += [_fx_row("fx_twd_per_eur", "2026-09-19", 34.0),
                                    _fx_row("fx_twd_per_eur", "2026-09-23", 35.0),
                                    _fx_row("fx_twd_per_eur", "2026-09-24", 99.0)]   # 晚於淨值日，不取
    value, reason = logic.basis_value(dataset, _holding(dataset, "CCCC"), logic.BASIS_MV)
    assert reason is None and math.isclose(value, 3000 * 3.1 * 35.0)
    block = logic.find_block(logic.build_page_model(dataset), "ALO-2")
    assert block["placeholder"] is None and all(r["_current_pct"] is not None for r in block["_rows"])


def test_市值基準_歐元不拿美元的匯率():
    """表上只有 fx_twd_per_usd：歐元那一檔不得拿美元匯率硬算（44 ALO-2 判準「不以 1 當匯率硬算」的同一件事）。"""
    dataset = _to_eur(_mv(fixtures.scenario("full")))
    value, reason = logic.basis_value(dataset, _holding(dataset, "CCCC"), logic.BASIS_MV)
    assert value is None
    assert reason == "⬜ 資料未備：缺換算匯率 fx_twd_per_eur"


def test_市值基準_歐元缺匯率_不崩頁_該類別照字面寫資料未備_其餘照算():
    dataset = _to_eur(_mv(fixtures.scenario("full")))
    model = logic.build_page_model(dataset)                       # 舊行為：ValueError（ALO-GAP-非美元幣別）
    alo2 = logic.find_block(model, "ALO-2")
    by_bucket = {r["_bucket"]: r for r in alo2["_rows"]}
    satellite = by_bucket[fixtures.SATELLITE]
    assert satellite["current_text"] == "⬜ 資料未備：缺換算匯率 fx_twd_per_eur"
    assert satellite["_current_pct"] is None and satellite["diff_text"] == "⬜"
    assert by_bucket[fixtures.CORE]["_current_pct"] is not None          # 其餘類別照算
    assert "合計未涵蓋 " + fixtures.SATELLITE in alo2["tail_lines"]
    assert alo2["_tone"] == "灰"
    alo4 = logic.find_block(model, "ALO-4")
    assert logic.TEXT_FX_MISSING_ALO4 in alo4["detail_lines"]
    assert "fx_twd_per_eur" in alo4["summary_text"] and alo4["_tone"] == "灰"
    alo6 = logic.find_block(model, "ALO-6")
    row = next(r for r in alo6["_rows"] if r["_fund_code"] == "CCCC")
    assert row["_value"] is None and row["value_text"] == "⬜"


def test_市值基準_美元與歐元都缺匯率_兩個鍵都列出_美元字面不變():
    dataset = _to_eur(_mv(fixtures.scenario("full")))
    dataset["market_indicator"] = []
    model = logic.build_page_model(dataset)
    texts = {r["current_text"] for r in logic.find_block(model, "ALO-2")["_rows"]}
    assert logic.TEXT_FX_MISSING_ALO2 in texts                            # 44 原字面一字未改
    assert "⬜ 資料未備：缺換算匯率 fx_twd_per_eur" in texts
    summary = logic.find_block(model, "ALO-4")["summary_text"]
    assert "缺 fx_twd_per_usd、fx_twd_per_eur" in summary


def test_缺匯率字面_美元版就是44原字面():
    assert logic.fx_missing_text(logic.FX_KEY) == logic.TEXT_FX_MISSING_ALO2
    assert logic.fx_missing_text("fx_twd_per_eur").startswith(logic.TEXT_FX_MISSING_ALO4 + " ")


@pytest.mark.parametrize("bad", ["TWD", "eur", "EU", None])
def test_匯率鍵_契約外的幣別當場炸(bad):
    with pytest.raises(ValueError):
        logic.fx_key_for(bad)


def test_成本基準不看淨值也不看匯率_歐元照算():
    dataset = _to_eur(fixtures.scenario("full"))                   # 成本基準
    dataset["nav"], dataset["market_indicator"] = [], []
    block = logic.find_block(logic.build_page_model(dataset), "ALO-2")
    assert block["placeholder"] is None and all(r["_current_pct"] is not None for r in block["_rows"])


# ═══════════════════════ 存檔組值（ALO-1／ALO-4，客戶 2026-10-09 裁示）═══════════════════════
#
# 畫面上的當下字串 → 要寫的試算表字串；寫之前先丟回 `_PARSERS` 解析，解析不過不寫、訊息用解析器原文。
# ⛔ 不 strip、不補 0、不把非數字當 null（`CLAUDE.md` §1）。

_ALO1_KEYS = ("alo_target_weights", "alo_tolerance_pp")
_ALO4_KEYS = ("alo_basis", "alo_bucket_names")


def _alo1_values(rows, tolerance):
    out = {"alo_tolerance_pp": tolerance}
    for index, (bucket, weight) in enumerate(rows):
        out[f"alo_target_{index}_bucket"] = bucket
        out[f"alo_target_{index}_weight"] = weight
    return out


def _entries(keys, values, **kw):
    return {e["key"]: e for e in live.save_entries(keys, values, **kw)}


def test_組值_ALO1正常_順序同畫面列序_原字照寫():
    out = _entries(_ALO1_KEYS, _alo1_values([(_CORE, "0.60"), (_SAT, "0.4")], "4"))
    assert out["alo_target_weights"] == {
        "key": "alo_target_weights", "value_kind": "list", "error": None,
        "value": '[{"bucket": "%s", "weight_ratio": 0.60}, {"bucket": "%s", "weight_ratio": 0.4}]' % (_CORE, _SAT),
    }
    assert out["alo_tolerance_pp"] == {"key": "alo_tolerance_pp", "value": "4", "value_kind": "float",
                                       "error": None}
    # 寫出去的字串讀回來就是原值（與讀取端同一支解析器）。
    assert live._PARSERS["alo_target_weights"](out["alo_target_weights"]["value"], "k") == [
        {"bucket": _CORE, "weight_ratio": 0.6}, {"bucket": _SAT, "weight_ratio": 0.4}]


def test_組值_比重留空寫成null():
    out = _entries(_ALO1_KEYS, _alo1_values([(_CORE, "0.6"), (_SAT, "")], "4"))
    assert out["alo_target_weights"]["error"] is None
    assert json.loads(out["alo_target_weights"]["value"])[1] == {"bucket": _SAT, "weight_ratio": None}


@pytest.mark.parametrize("weight", ["六成", "nan", ".6", "0,6", "1e999"])
def test_組值_比重不是有限的數_不寫_訊息是解析器原文(weight):
    out = _entries(_ALO1_KEYS, _alo1_values([(_CORE, weight)], "4"))
    entry = out["alo_target_weights"]
    with pytest.raises(live.BadSettingValue) as caught:
        live._PARSERS["alo_target_weights"](entry["value"], "alo_target_weights")
    assert entry["error"] == str(caught.value)
    assert "weight_ratio 不是有限的數" in entry["error"]
    assert out["alo_tolerance_pp"]["error"] is None             # 另一鍵不受牽連


def test_組值_比重寫成60而不是0點6_不寫():
    entry = _entries(_ALO1_KEYS, _alo1_values([(_CORE, "60")], "4"))["alo_target_weights"]
    assert entry["error"] == "alo_target_weights 第 1 個元素的 weight_ratio 不在 0 到 1（60.0）"


@pytest.mark.parametrize("weight", [" 0.6", "0.6 ", "\t0.6"])
def test_組值_比重前後有空白_不strip_不寫(weight):
    entry = _entries(_ALO1_KEYS, _alo1_values([(_CORE, weight)], "4"))["alo_target_weights"]
    assert entry["error"] is not None and "不是有限的數" in entry["error"]
    assert json.dumps(weight) in entry["value"]                 # 原字照嵌，沒有被修掉


def test_組值_容許帶空字串寫None_前後空白不寫():
    assert _entries(_ALO1_KEYS, _alo1_values([], ""))["alo_tolerance_pp"]["value"] is None
    entry = _entries(_ALO1_KEYS, _alo1_values([], " 4"))["alo_tolerance_pp"]
    assert entry["value"] == " 4"
    assert entry["error"] == "alo_tolerance_pp 的值不是前後無空白的字串"
    entry = _entries(_ALO1_KEYS, _alo1_values([], "四"))["alo_tolerance_pp"]
    assert entry["error"] == "alo_tolerance_pp 的值不是數（alo_tolerance_pp）"


def test_組值_一列也沒有_寫None清除():
    entry = _entries(_ALO1_KEYS, _alo1_values([], "4"))["alo_target_weights"]
    assert entry["value"] is None and entry["error"] is None


def test_組值_ALO4_比重基準與類別名稱():
    values = {"alo_basis": logic.BASIS_MV, "alo_bucket_name_0": _CORE, "alo_bucket_name_1": _SAT}
    out = _entries(_ALO4_KEYS, values)
    assert out["alo_basis"] == {"key": "alo_basis", "value": logic.BASIS_MV, "value_kind": "list",
                                "error": None}
    assert out["alo_bucket_names"]["value"] == json.dumps([_CORE, _SAT], ensure_ascii=False)
    assert json.loads(out["alo_bucket_names"]["value"]) == [_CORE, _SAT]
    assert out["alo_bucket_names"]["value_kind"] == "list" and out["alo_bucket_names"]["error"] is None


def test_組值_ALO4_基準未選寫None_類別名稱空白不寫():
    out = _entries(_ALO4_KEYS, {"alo_basis": None, "alo_bucket_name_0": ""})
    assert out["alo_basis"]["value"] is None and out["alo_basis"]["error"] is None
    assert out["alo_bucket_names"]["error"] == "alo_bucket_names 第 1 個元素不是非空字串"


def test_組值_設定讀失敗時一律不寫_兩鍵都記為存檔失敗_訊息是讀取失敗原文():
    """2026-10-09 稽核回修（舊版斷言回空清單 ⇒ 按了沒反應，§1 讓流程看起來成功）：
    讀不到真值時畫面上沒有可編的已存值，寫了就是拿空白蓋掉讀不到的真值 ⇒ 不寫；
    兩鍵都帶讀取失敗原文 ⇒ `run_saves` 記兩鍵皆失敗 ⇒ logic 走卡片層既有「存檔寫入失敗：…」。"""
    dataset = fixtures.scenario("settingfail")
    message = logic.settings_failure(dataset)
    assert message
    calls = []
    for keys in (_ALO1_KEYS, _ALO4_KEYS):
        entries = live.save_entries(keys, {}, settings_error=message)
        assert [(e["key"], e["value"], e["error"]) for e in entries] == [(k, None, message) for k in keys]
        results = live.run_saves(entries, lambda *a: calls.append(a))
        assert results == {k: message for k in keys}
    assert calls == []                                          # 寫入函式 0 次呼叫
    dataset["save_errors"] = {k: message for k in _ALO1_KEYS + _ALO4_KEYS}
    model = logic.build_page_model(dataset)
    for code in ("ALO-1", "ALO-4"):
        card = logic.find_block(model, code)
        assert card["error_lines"] == [logic.TEXT_SAVE_FAILED + "：" + message], code
        assert card["key_error_lines"] == {}, code


def test_組值_沒接上的鍵當場炸():
    with pytest.raises(ValueError, match="尚未接上"):
        live.save_entries(("alo_scenario_input",), {})


# ═══════════════════════ 逐鍵寫入與記帳 ═══════════════════════


def test_寫入_一鍵成功一鍵失敗_不rollback_訊息原文():
    calls = []

    def save(key, value, kind):
        calls.append((key, value, kind))
        if key == "alo_tolerance_pp":
            return {"status": "failed", "key": key, "message": "HTTP 503（已遮蔽）"}
        return {"status": "saved", "key": key, "row": {}}

    entries = live.save_entries(_ALO1_KEYS, _alo1_values([(_CORE, "1")], "4"))
    results = live.run_saves(entries, save)
    assert results == {"alo_target_weights": None, "alo_tolerance_pp": "HTTP 503（已遮蔽）"}
    assert [c[0] for c in calls] == list(_ALO1_KEYS)
    assert calls[1] == ("alo_tolerance_pp", "4", "float")


def test_寫入_解析不過的鍵不呼叫寫入_另一鍵照寫():
    calls = []

    def save(key, value, kind):
        calls.append(key)
        return {"status": "saved", "key": key}

    entries = live.save_entries(_ALO1_KEYS, _alo1_values([(_CORE, "abc")], "4"))
    results = live.run_saves(entries, save)
    assert calls == ["alo_tolerance_pp"]
    assert "不是有限的數" in results["alo_target_weights"] and results["alo_tolerance_pp"] is None


@pytest.mark.parametrize("status", ["kind_mismatch", "kind_missing", "failed"])
def test_寫入_非saved一律記為失敗(status):
    results = live.run_saves(
        [{"key": "alo_basis", "value": logic.BASIS_COST, "value_kind": "list", "error": None}],
        lambda *a: {"status": status, "key": "alo_basis", "message": f"（{status} 原文）"},
    )
    assert results == {"alo_basis": f"（{status} 原文）"}


def test_寫入_寫入以外的例外照樣往上拋():
    def save(*args):
        raise RuntimeError("boom")

    entries = live.save_entries(_ALO4_KEYS, {"alo_basis": logic.BASIS_COST})
    with pytest.raises(RuntimeError, match="boom"):
        live.run_saves(entries, save)


def test_記帳_成功移除_失敗寫入_不改呼叫端那一份():
    before = {"alo_basis": "舊的失敗", "alo_tolerance_pp": "舊的"}
    after = live.merge_save_results(before, {"alo_basis": None, "alo_bucket_names": "新的失敗"})
    assert after == {"alo_tolerance_pp": "舊的", "alo_bucket_names": "新的失敗"}
    assert before == {"alo_basis": "舊的失敗", "alo_tolerance_pp": "舊的"}
    assert live.merge_save_results(None, {}) == {}


def test_併進save_errors_不改呼叫端那一份():
    dataset = fixtures.scenario("full")
    out = live.dataset_with_save_errors(dataset, {"alo_basis": "x"})
    assert out["save_errors"] == {"alo_basis": "x"} and dataset["save_errors"] == {}
    assert live.dataset_with_save_errors(dataset, None)["save_errors"] == {}



# ═══════════════════════ 沒動過的欄位寫回原值（2026-10-09 稽核回修）═══════════════════════
#
# 輸入欄初值是 `format_number` 的顯示字串（最多四位小數）；沒動過就按存檔，必須寫回已存的原值，
# 不得把 0.333333 寫成 0.3333、0.00001 寫成 0、"2.55555" 寫成 "2.5556"。

_RAW_WEIGHTS = '[{"bucket": "%s", "weight_ratio": 0.333333}, {"bucket": "%s", "weight_ratio": 0.00001}]' % (
    _CORE, _SAT)


def _precise():
    """已存值帶四位以上小數的 ALO-1：回 (塊的輸入欄節點, 畫面當下值＝顯示字串, 原字串表)。"""
    raw = {"alo_target_weights": _RAW_WEIGHTS, "alo_tolerance_pp": "2.55555"}
    rows, problem = live.parse_user_settings(_rows(**raw))
    assert problem is None
    dataset = dict(fixtures.scenario("full"), user_setting=rows)
    card = logic.find_block(logic.build_page_model(dataset), "ALO-1")
    values = {field["name"]: field["value_text"] for field in card["inputs"]}
    # 前提：顯示字串確實被四捨五入過 —— 不成立的話下面幾條就是空測。
    assert values["alo_target_0_weight"] == "0.3333" and values["alo_target_1_weight"] == "0"
    assert values["alo_tolerance_pp"] == "2.5556"
    return card["inputs"], values, raw


def test_沒動過的欄位按存檔_寫出值與原值相同():
    fields, values, raw = _precise()
    out = _entries(_ALO1_KEYS, values, fields=fields, raw=raw)
    assert out["alo_tolerance_pp"]["value"] == "2.55555" and out["alo_tolerance_pp"]["error"] is None
    assert out["alo_target_weights"]["error"] is None
    assert live._PARSERS["alo_target_weights"](out["alo_target_weights"]["value"], "k") == \
        live._PARSERS["alo_target_weights"](_RAW_WEIGHTS, "k")
    assert json.loads(out["alo_target_weights"]["value"]) == json.loads(_RAW_WEIGHTS)


def test_改動其中一列_只有那一列換成新輸入():
    fields, values, raw = _precise()
    values["alo_target_1_weight"] = "0.2"
    out = _entries(_ALO1_KEYS, values, fields=fields, raw=raw)
    assert json.loads(out["alo_target_weights"]["value"]) == [
        {"bucket": _CORE, "weight_ratio": 0.333333}, {"bucket": _SAT, "weight_ratio": 0.2}]
    assert out["alo_tolerance_pp"]["value"] == "2.55555"
    values["alo_tolerance_pp"] = "3"
    assert _entries(_ALO1_KEYS, values, fields=fields, raw=raw)["alo_tolerance_pp"]["value"] == "3"


def test_沒動過的留空列與未設定容許帶_照舊寫null與None():
    rows, _ = live.parse_user_settings(_rows(alo_target_weights=_weights([(_CORE, None)])))
    dataset = dict(fixtures.scenario("full"), user_setting=rows)
    card = logic.find_block(logic.build_page_model(dataset), "ALO-1")
    values = {field["name"]: field["value_text"] for field in card["inputs"]}
    out = _entries(_ALO1_KEYS, values, fields=card["inputs"],
                   raw={"alo_target_weights": _weights([(_CORE, None)]), "alo_tolerance_pp": None})
    assert json.loads(out["alo_target_weights"]["value"]) == [{"bucket": _CORE, "weight_ratio": None}]
    assert out["alo_tolerance_pp"]["value"] is None


def test_沒動過但原字串表漏了那一鍵_當場炸不猜():
    fields, values, _raw = _precise()
    with pytest.raises(KeyError):
        live.save_entries(_ALO1_KEYS, values, fields=fields, raw={})


# ═══════════════════════ 淨值表判讀 `live.assemble_nav`（2026-10-13；規則同 hld `assemble_live_load`）═══════════════════════

_EMPTY = "來源回傳空值，原因未提供"
_FOUR = frozenset({"ccy_missing", "ccy_conflict", "fetched_at_missing", "fetched_at_in_future"})


def _nav_table(**over):
    table = {"rows": [], "errors": {}, "withheld": {}, "skipped": {}, "fetched": {}, "skipped_rows": {},
             "provenance": {}}
    table.update(over)
    return table


def _keys(codes, fail=()):
    return [{"input": c, "ok": c not in fail} for c in codes]


_TODAY = __import__("datetime").date(2026, 9, 25)


def _assemble(table, codes=("AAAA", "BBBB"), fail=(), mask=lambda m: m.replace("SECRET", "＊"),
              today=_TODAY, max_age_days=live.NAV_MAX_AGE_DAYS):
    return live.assemble_nav(holding_codes=list(codes), key_results=_keys(codes, fail), nav_table=table,
                             empty_without_reason=_EMPTY, nav_unavailable_withheld=_FOUR, mask=mask,
                             today=today, max_age_days=max_age_days)


def test_assemble_nav_失敗原文逐檔遮蔽串成一句_來源回空與扣下不算失敗():
    nav_row = {"fund_code": "AAAA", "nav_date": "2026-09-23", "nav_orig_ccy": 10.0, "ccy": "TWD",
               "source_tier": "淨值", "is_estimated": False, "fetched_at": "2026-09-23T01:30:00+00:00"}
    out = _assemble(_nav_table(rows=[nav_row], errors={"BBBB": "逾時 SECRET", "CCCC": _EMPTY},
                               withheld={"DDDD": "ccy_conflict"},
                               fetched={"AAAA": 1, "BBBB": 0, "CCCC": 0}),
                    codes=("AAAA", "BBBB", "CCCC", "DDDD"))
    assert out["nav"] == [nav_row]
    assert out["error"] == "BBBB：逾時 ＊"
    assert out["notes"]["withheld"] == {"DDDD": "ccy_conflict"}


def test_assemble_nav_扣下代碼不在約定清單_當場炸():
    with pytest.raises(ValueError, match="input_conflict"):
        _assemble(_nav_table(withheld={"AAAA": "input_conflict"}, fetched={"BBBB": 0}))


def test_assemble_nav_一致性_代碼對不上就炸():
    with pytest.raises(ValueError, match="持倉裡沒有"):
        _assemble(_nav_table(fetched={"AAAA": 0, "BBBB": 0, "ZZZZ": 0}))
    with pytest.raises(ValueError, match="沒有交給淨值表"):
        _assemble(_nav_table(fetched={"AAAA": 0}))
    with pytest.raises(ValueError, match="不得出現在淨值表"):
        _assemble(_nav_table(fetched={"AAAA": 0, "BBBB": 0}), fail=("BBBB",))


def test_wants_market_value_只認已存基準為市值():
    assert live.wants_market_value([{"setting_key": "alo_basis", "setting_value": logic.BASIS_MV}]) is True
    assert live.wants_market_value([{"setting_key": "alo_basis", "setting_value": logic.BASIS_COST}]) is False
    assert live.wants_market_value([{"setting_key": "alo_basis", "setting_value": None}]) is False
    assert live.wants_market_value([]) is False                       # 設定讀不到：各塊本來就畫失敗框


def test_fx_ccys_needed_只列新臺幣與美元以外_依序不重複():
    rows = [{"ccy": c} for c in ("USD", "EUR", "TWD", "JPY", "EUR")]
    assert live.fx_ccys_needed(rows) == ["EUR", "JPY"]


def test_merge_fx_table_失敗接在試算表錯誤之後_pending不是失敗():
    fx = {"rows": [{"indicator_key": "fx_twd_per_eur"}], "errors": {"fx_twd_per_jpy": "逾時 SECRET"},
          "pending": {"fx_twd_per_aud": "fx_obs_date_rule"}, "skipped": {}, "fetched": {}}
    rows, error, pending = live.merge_fx_table([{"indicator_key": "fx_twd_per_usd"}], "讀不到表", fx,
                                               lambda m: m.replace("SECRET", "＊"))
    assert [r["indicator_key"] for r in rows] == ["fx_twd_per_usd", "fx_twd_per_eur"]
    assert error == "讀不到表；fx_twd_per_jpy：逾時 ＊"
    assert pending == {"fx_twd_per_aud": "fx_obs_date_rule"}
    _rows, error, _p = live.merge_fx_table([], None, dict(fx, errors={}), str)
    assert error is None


# ═══════════════════════ 2026-10-13 稽核 B1：沒有分母時 ALO-3 不得說「合計不為正」；有目標、沒持倉的類別 ═══════════════════════

_BOND = "債券（示意）"


def _with_empty_target(dataset):
    """加一個有目標、沒有任何持倉的類別（目標比重照舊合計 1，債券給 0.1、現金讓出 0.1）。"""
    for row in dataset["user_setting"]:
        if row["setting_key"] == "alo_target_weights":
            row["setting_value"] = [dict(t) for t in row["setting_value"]]
            for t in row["setting_value"]:
                if t["weight_ratio"] == 0.1:
                    t["weight_ratio"] = 0.0
            row["setting_value"].append({"bucket": _BOND, "weight_ratio": 0.1})
        if row["setting_key"] == "alo_bucket_names":
            row["setting_value"] = list(row["setting_value"]) + [_BOND]
    return dataset


def _all_missing_two_reasons(dataset):
    dataset["market_indicator"] = []                                     # 美元那幾類缺匯率
    dataset["nav"] = [r for r in dataset["nav"] if r["fund_code"] not in ("BBBB", "DDDD")]
    return dataset


def test_B1_沒有分母_ALO3照來源缺畫列序最先的理由_不說合計不為正():
    dataset = _all_missing_two_reasons(_mv(fixtures.scenario("full")))
    assert logic.setting_value(dataset, "alo_scenario_input"), "前提：有試算輸入，否則量不到 total 那一支"
    model = logic.build_page_model(dataset)
    alo2 = logic.find_block(model, "ALO-2")
    assert alo2["_no_denominator"] is True
    alo3 = logic.find_block(model, "ALO-3")
    first = next(r["current_text"] for r in alo2["_rows"] if r["_value"] is None)
    assert alo3["placeholder"]["text"] == first and alo3["placeholder"]["_empty_kind"] == "來源缺"
    assert first.startswith("⬜ 資料未備：")                              # 44 既有字面，不是新句子
    strings = logic.collect_ui_strings(alo3)
    assert logic.TEXT_NA_ZERO_TOTAL not in strings                         # 「沒有合計」不是「合計不為正」
    assert alo3["_rows"] == []


def test_B1_單一理由與正常情形_ALO2沒有分母旗標():
    single = _mv(fixtures.scenario("full"))
    single["nav"] = []
    assert logic.find_block(logic.build_page_model(single), "ALO-2")["_no_denominator"] is False
    assert logic.find_block(logic.build_page_model(fixtures.scenario("full")), "ALO-2")["_no_denominator"] is False


def test_有目標沒持倉的類別_正常情形_目前比重0且照算差額_試算比重0():
    dataset = _with_empty_target(fixtures.scenario("full"))               # 成本基準、有分母
    model = logic.build_page_model(dataset)
    row = next(r for r in logic.find_block(model, "ALO-2")["_rows"] if r["_bucket"] == _BOND)
    assert row["_count"] == 0 and row["_current_pct"] == 0.0 and row["current_text"] == "0.0%"
    assert math.isclose(row["_diff"], -10.0)
    result = next(r for r in logic.find_block(model, "ALO-3")["_rows"] if r["_bucket"] == _BOND)
    assert result["_share_pct"] == 0.0


def test_有目標沒持倉的類別_沒有分母_只印方塊_不寫0百分比_ALO3不算():
    dataset = _all_missing_two_reasons(_with_empty_target(_mv(fixtures.scenario("full"))))
    model = logic.build_page_model(dataset)
    alo2 = logic.find_block(model, "ALO-2")
    row = next(r for r in alo2["_rows"] if r["_bucket"] == _BOND)
    assert row["current_text"] == "⬜" and row["_current_pct"] is None and row["diff_text"] == "⬜"
    assert _BOND not in next(line for line in alo2["tail_lines"] if line.startswith("合計未涵蓋 "))
    assert logic.find_block(model, "ALO-3")["placeholder"]["_empty_kind"] == "來源缺"


def test_2026_10_13補登的GAPS都在():
    for gap_id in ("ALO-GAP-單檔淨值失敗升整表", "ALO-GAP-匯率單位待裁", "ALO-GAP-全缺兩種畫法",
                   "ALO-GAP-全缺合計未涵蓋", "ALO-GAP-多理由並列", "ALO-GAP-ALO4缺匯率字面",
                   "ALO-GAP-基準標籤只寫美元", "ALO-GAP-過期淨值不納入"):
        assert gap_id in logic.GAPS, gap_id


# ═══════════════════════ 2026-10-13 稽核 N1／N2：過期或預存淨值不納入；notes 的 live_error 經遮蔽 ═══════════════════════


def _nav_row(code, *, estimated=False):
    return {"fund_code": code, "nav_date": "2026-09-23", "nav_orig_ccy": 10.0, "ccy": "TWD",
            "source_tier": "淨值", "is_estimated": estimated, "fetched_at": "2026-09-23T01:30:00+00:00"}


def _prov(**over):
    out = {"source": "MoneyDJ:x", "fetched_at": "2026-09-23T01:30:00+00:00", "ccy_source": "holding_user_input",
           "cache_fallback": False, "stale": None, "live_error": None}
    out.update(over)
    return out


@pytest.mark.parametrize("prov, estimated", [
    (dict(cache_fallback=True, stale=False), False),   # 預存舊序列（即時全敗）
    (dict(cache_fallback=True, stale=True), False),    # 預存且過期
    (dict(stale=True), False),                          # 只標過期
    ({}, True),                                         # 推估值
])
def test_N1_過期或預存或推估淨值_不交進dataset_記在notes(prov, estimated):
    table = _nav_table(rows=[_nav_row("AAAA", estimated=estimated), _nav_row("BBBB")],
                       fetched={"AAAA": 1, "BBBB": 1},
                       provenance={"AAAA": _prov(**prov), "BBBB": _prov()})
    out = _assemble(table)
    assert [r["fund_code"] for r in out["nav"]] == ["BBBB"]
    assert out["notes"]["not_fresh"] == ["AAAA"]
    assert out["error"] is None                                            # 不是取數失敗，是資料未備


def test_N1_被拿掉的那一檔在市值基準下畫資料未備():
    dataset = _mv(fixtures.scenario("full"))
    table = _nav_table(rows=[dict(r, fund_code=r["fund_code"]) for r in dataset["nav"]],
                       fetched={c: 2 for c in ("AAAA", "BBBB", "CCCC", "DDDD")},
                       provenance={"BBBB": _prov(cache_fallback=True)})
    out = _assemble(table, codes=("AAAA", "BBBB", "CCCC", "DDDD"))
    dataset["nav"] = out["nav"]
    holding = next(h for h in logic.aggregated_holdings(dataset) if h["fund_code"] == "BBBB")
    assert logic.basis_value(dataset, holding, logic.BASIS_MV) == (None, logic.empty_source_text(["nav"]))


def test_N2_notes裡的live_error經遮蔽():
    table = _nav_table(rows=[_nav_row("AAAA")], fetched={"AAAA": 1, "BBBB": 0},
                       errors={"BBBB": "逾時 SECRET"},
                       provenance={"AAAA": _prov(live_error="上一次 SECRET 失敗")})
    out = _assemble(table)
    assert out["notes"]["provenance"]["AAAA"]["live_error"] == "上一次 ＊ 失敗"
    assert table["provenance"]["AAAA"]["live_error"] == "上一次 SECRET 失敗"   # 不改輸入


# ═══════════════════════ 2026-10-13 第二輪：N-b 淨值日期、N-c 遮蔽、is_estimated 缺欄／None ═══════════════════════


def test_第二輪4_is_estimated為None_不納入():
    table = _nav_table(rows=[_nav_row("AAAA", estimated=None), _nav_row("BBBB")],
                       fetched={"AAAA": 1, "BBBB": 1}, provenance={"AAAA": _prov(), "BBBB": _prov()})
    out = _assemble(table)
    assert [r["fund_code"] for r in out["nav"]] == ["BBBB"] and out["notes"]["not_fresh"] == ["AAAA"]


def test_第二輪4_is_estimated缺欄_不納入():
    row = _nav_row("AAAA")
    del row["is_estimated"]
    table = _nav_table(rows=[row, _nav_row("BBBB")], fetched={"AAAA": 1, "BBBB": 1},
                       provenance={"AAAA": _prov(), "BBBB": _prov()})
    out = _assemble(table)
    assert [r["fund_code"] for r in out["nav"]] == ["BBBB"] and out["notes"]["not_fresh"] == ["AAAA"]


def _dated_row(code, day):
    return dict(_nav_row(code), nav_date=day)


# 名稱更正（2026-10-13，斷言未改）：~~test_第二輪Nb_淨值日超過門檻天數_不納入_剛好等於門檻照收~~ —— 內容是第三輪的 10 天。
def test_第三輪_淨值日超過10天_不納入_剛好10天照收():
    """~~今天 2026-09-25、門檻 7 天：09-18（7 天）照收、09-17（8 天）不納入（🔴 > 7d）。~~
    → 第三輪（門檻改為客戶裁示的 10 天；有意識的更正，不是漏刪）：今天 2026-09-25，
    09-15（10 天）照收、09-14（11 天）不納入 —— 與 hld 黃燈同向（`days > 10`）。"""
    table = _nav_table(rows=[_dated_row("AAAA", "2026-09-14"), _dated_row("BBBB", "2026-09-15")],
                       fetched={"AAAA": 1, "BBBB": 1}, provenance={"AAAA": _prov(), "BBBB": _prov()})
    out = _assemble(table)
    assert [r["fund_code"] for r in out["nav"]] == ["BBBB"]
    assert out["notes"]["too_old"] == ["AAAA"] and out["notes"]["not_fresh"] == ["AAAA"]
    assert out["error"] is None                                            # 不是取數失敗，是資料未備


def test_第二輪Nb_看的是該檔最新一筆淨值日_不是fetched_at():
    """即時取回（fetched_at 是今天）卻是四個月前的淨值 → 照樣不納入；同一檔有一筆夠新 → 整檔照收。"""
    old = dict(_dated_row("AAAA", "2026-05-20"), fetched_at="2026-09-25T01:00:00+00:00")
    table = _nav_table(rows=[old, _dated_row("BBBB", "2026-05-20"), _dated_row("BBBB", "2026-09-24")],
                       fetched={"AAAA": 1, "BBBB": 2}, provenance={"AAAA": _prov(), "BBBB": _prov()})
    out = _assemble(table)
    assert out["notes"]["too_old"] == ["AAAA"]
    assert {r["fund_code"] for r in out["nav"]} == {"BBBB"}


def test_第二輪Nb_門檻由呼叫端注入_today型別不對就炸():
    table = _nav_table(rows=[_dated_row("AAAA", "2026-09-20")], fetched={"AAAA": 1, "BBBB": 0},
                       provenance={"AAAA": _prov()})
    assert _assemble(table, max_age_days=4)["notes"]["too_old"] == ["AAAA"]
    assert _assemble(table, max_age_days=5)["notes"]["too_old"] == []
    with pytest.raises(TypeError):
        _assemble(table, today="2026-09-25")
    with pytest.raises(TypeError):
        _assemble(table, max_age_days=7.0)


def test_第二輪Nc_chain_failures與累積表read_error經遮蔽_不改輸入():
    prov = _prov(chain_failures="頁型 yp010001：SECRET 逾時",
                 nav_history={"source": "nav_history", "points": 0, "read_error": "讀表 SECRET 403"})
    table = _nav_table(rows=[_nav_row("AAAA")], fetched={"AAAA": 1, "BBBB": 0}, provenance={"AAAA": prov})
    out = _assemble(table)
    got = out["notes"]["provenance"]["AAAA"]
    assert got["chain_failures"] == "頁型 yp010001：＊ 逾時"
    assert got["nav_history"]["read_error"] == "讀表 ＊ 403"
    assert "SECRET" not in repr(out["notes"])
    assert prov["chain_failures"] == "頁型 yp010001：SECRET 逾時"
    assert prov["nav_history"]["read_error"] == "讀表 SECRET 403"          # 深拷貝，不改輸入


def test_第二輪6_兩筆只登記不改行為的GAP在():
    assert "ALO-GAP-部分缺的內外判讀" in logic.GAPS and "ALO-GAP-同類別多理由" in logic.GAPS
    assert "不是 False（含缺欄或 None）" in logic.GAPS["ALO-GAP-過期淨值不納入"]


# ═══════════════════════ 2026-10-13 第三輪：門檻改用客戶裁示的 10 天，與 hld 鎖在一起 ═══════════════════════


# ~~test_第三輪_alo淨值日上限與hld黃燈門檻是同一個值_不得脫鉤（只鎖兩個寫死的 10 相等）~~
# → 2026-10-13 客戶裁示（有意識的更正，不是漏刪）：10 天要有**單一**共用定義，兩個寫死的 10 靠測試鎖相等仍是兩個數字。
#   改為鎖「兩頁引用的是同一個共用常數」＋「門檻那一行不是整數字面值」。

_THRESHOLD_ALIASES = {
    "ui_v2/hld/live.py": "NAV_FRESH_DAYS_YELLOW",
    "ui_v2/alo/live.py": "NAV_MAX_AGE_DAYS",
}


def _assignments_to(rel, name):
    """回傳檔內所有對 `name` 賦值的右側 AST（Assign、AnnAssign、AugAssign 都算）。"""
    import ast

    tree = ast.parse((_ROOT / rel).read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        else:
            continue
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            out.append(node.value)
    return out


def test_10天門檻_兩頁引用同一個共用常數_值為10():
    """出處：`ui_v2/thresholds.py::NAV_NOT_READY_DAYS`（客戶 2026-10-02 裁示「門檻 10 天，非 44 規定，是本輪依長假實況訂的」；
    客戶 2026-10-13 裁示：10 天要有單一、明確的共用定義）。"""
    import ast

    from ui_v2 import thresholds
    from ui_v2.hld import live as hld_live

    assert thresholds.NAV_NOT_READY_DAYS == 10 and type(thresholds.NAV_NOT_READY_DAYS) is int
    # 執行期：兩頁拿到的是同一個模組物件、同一個值
    assert live.thresholds is thresholds and hld_live.thresholds is thresholds
    assert live.NAV_MAX_AGE_DAYS == thresholds.NAV_NOT_READY_DAYS
    assert hld_live.NAV_FRESH_DAYS_YELLOW == thresholds.NAV_NOT_READY_DAYS
    # 原始碼：別名的右側就是 `thresholds.NAV_NOT_READY_DAYS` 這個名稱（小整數在 CPython 是同一個物件，
    # 光比 `is` 抓不到「各寫一個 10」，所以另以 AST 鎖名稱）
    for rel, alias in _THRESHOLD_ALIASES.items():
        values = _assignments_to(rel, alias)
        assert len(values) == 1, (rel, alias, len(values))
        assert ast.unparse(values[0]) == "thresholds.NAV_NOT_READY_DAYS", (rel, ast.unparse(values[0]))
    # 共用常數本身：全 ui_v2 只有 `ui_v2/thresholds.py` 這一處給它值，而且是字面值 10
    owners = {}
    for path in sorted((_ROOT / "ui_v2").rglob("*.py")):
        rel = path.relative_to(_ROOT).as_posix()
        got = _assignments_to(rel, "NAV_NOT_READY_DAYS")
        if got:
            owners[rel] = [ast.unparse(v) for v in got]
    assert owners == {"ui_v2/thresholds.py": ["10"]}, owners


@pytest.mark.parametrize("rel, alias", sorted(_THRESHOLD_ALIASES.items()))
def test_10天門檻_兩頁門檻那一行不得是整數字面值(rel, alias):
    """AST 守衛：門檻賦值的右側不得是 `ast.Constant`（例：`NAV_MAX_AGE_DAYS = 10`）—— 那就是又各寫一個數字。"""
    import ast

    values = _assignments_to(rel, alias)
    assert values, (rel, alias)                                            # 空掃防呆：真的找到那一行
    bad = [ast.unparse(v) for v in values if _has_number_literal(v)]
    assert bad == [], (rel, alias, bad)


def _has_number_literal(value) -> bool:
    """右側（含巢狀，例 `int(10)`、`x + 0`）出現數字字面值 → 真。"""
    import ast

    return any(isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)
               for n in ast.walk(value))


@pytest.mark.parametrize("code, caught", [
    ("NAV_MAX_AGE_DAYS = 10", True),
    ("NAV_MAX_AGE_DAYS: int = 10", True),
    ("NAV_MAX_AGE_DAYS = int(10)", True),
    ("NAV_MAX_AGE_DAYS = thresholds.NAV_NOT_READY_DAYS + 0", True),
    ("NAV_MAX_AGE_DAYS = thresholds.NAV_NOT_READY_DAYS", False),          # 負控：現行寫法不誤報
])
def test_10天門檻_字面值守衛的正控與負控(code, caught):
    """守衛本身會咬：把數字寫回本頁的各種寫法都要被判出來；現行寫法不得誤報。"""
    import ast

    tree = ast.parse(code)
    values = [n.value for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.AnnAssign))]
    assert len(values) == 1, code
    assert _has_number_literal(values[0]) is caught, code


def test_第三輪_判定方向與hld黃燈相同_剛好等於門檻不排除():
    """hld：`days > NAV_FRESH_DAYS_YELLOW` 才黃；本頁：`> NAV_MAX_AGE_DAYS` 才排除。"""
    import datetime as _dt
    limit = live.NAV_MAX_AGE_DAYS
    edge = (_TODAY - _dt.timedelta(days=limit)).isoformat()
    over = (_TODAY - _dt.timedelta(days=limit + 1)).isoformat()
    table = _nav_table(rows=[_dated_row("AAAA", over), _dated_row("BBBB", edge)],
                       fetched={"AAAA": 1, "BBBB": 1}, provenance={"AAAA": _prov(), "BBBB": _prov()})
    assert _assemble(table)["notes"]["too_old"] == ["AAAA"]
