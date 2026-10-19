# -*- coding: utf-8 -*-
"""BL-0250 實機驗收回修 批次 2（客戶 2026-10-19 裁示 G1，`docs/DECISIONS.md` `DEC-2026-10-19-04`；
44 第七節第三小節之十一，文字類 U1／U2／U3／U5／U6）的純邏輯守衛（fast lane；不需要 streamlit）。

- 正式模式一般畫面那一份模型（`ui_v2.plain.plain_model` 的輸出）：沒有紅線標記徽章、沒有任何一個字串帶三個標記；
  頁尾換成一句指路句；`EXP-7` 稽核等式那一行不在。
- 突變靈敏度：把拿掉徽章那一步關掉，同一個檢查當場找得到標記（不是空掃）。
- 示範模式那一份模型照舊帶徽章與舊頁尾（`plain_model` 不改輸入）。
- U5：`EXP-7` 那一行拿掉之後，等式改由這裡守：最後一列的符合檔數 ＝ `EXP-0` 的 N（＝`EXP-2` 列數扣掉無法判定）。
"""

from __future__ import annotations

import copy
import pathlib
import re
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2 import plain  # noqa: E402
from ui_v2.alo import fixtures as alo_fx, logic as alo_logic  # noqa: E402
from ui_v2.exp import fixtures as exp_fx, live as exp_live, logic as exp_logic  # noqa: E402
from ui_v2.hld import fixtures as hld_fx, logic as hld_logic  # noqa: E402
from ui_v2.mkt import fixtures as mkt_fx, logic as mkt_logic  # noqa: E402
from ui_v2.set import fixtures as set_fx, logic as set_logic  # noqa: E402

_MARK = re.compile(r"G[123]†")


def _demo_models():
    exp_params = dict(exp_fx.scenario_with("full", save_failed=False))
    exp_dataset = exp_params.pop("dataset")
    return {
        "mkt": mkt_logic.build_page_model(mkt_fx.dataset_all_ok()),
        "hld": hld_logic.build_page_model(hld_fx.dataset_full()),
        "exp": exp_logic.build_page_model(exp_dataset, save_failed=False, **exp_params),
        "alo": alo_logic.build_page_model(alo_fx.scenario_with("full", save_failed=False)),
        "set": set_logic.build_page_model(set_fx.scenario_with("ok", save_failed=False)),
    }


def _strings(node, private=False):
    """模型裡會上畫面的字串（`_` 開頭鍵底下的值是程式拿去比對的，不收）。"""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(value, private or (isinstance(key, str) and key.startswith("_")))
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _strings(item, private)
    elif isinstance(node, str) and not private:
        yield node


def _redline_badges(node):
    if isinstance(node, dict):
        if node.get("_kind") == "紅線":
            yield node
        for value in node.values():
            yield from _redline_badges(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _redline_badges(item)


def _violations(display):
    marks = [s for s in _strings(display) if _MARK.search(s) or "紅線說明區" in s or "本頁不負責什麼" in s]
    return marks + [b["text"] for b in _redline_badges(display)]


@pytest.mark.parametrize("page", list(plain.PAGE_NAMES))
def test_正式模式模型_沒有紅線標記與徽章_頁尾一句(page):
    model = _demo_models()[page]
    display, _raw, _status = plain.plain_model(model, page=page)
    assert _violations(display) == []
    assert display["footer_lines"] == [plain.PLAIN_FOOTERS[page]]
    assert display["footer_badges"] == []


@pytest.mark.parametrize("page", list(plain.PAGE_NAMES))
def test_示範模式模型照舊帶徽章_plain_model不改輸入(page):
    model = _demo_models()[page]
    before = copy.deepcopy(model)
    plain.plain_model(model, page=page)
    assert model == before
    assert list(_redline_badges(model)), page          # 示範模式那一份照舊有紅線徽章（正控）
    assert model["footer_badges"], page


def test_突變靈敏度_徽章那一步關掉守衛就紅(monkeypatch):
    """把「紅線徽章不上一般畫面」那一步關掉（徽章類別改成對不上的字），同一個檢查要找得到徽章 —— 守衛不是空掃。"""
    monkeypatch.setattr(plain, "REDLINE_BADGE_KIND", "（突變：不認得的類別）")
    found = []
    for page, model in _demo_models().items():
        display, _raw, _status = plain.plain_model(model, page=page)
        found += [b["text"] for b in _redline_badges(display)]
    # 徽章本體回來了（文字另被句中標記那一步洗成空字串 —— 那是第二道，下一條單獨驗）。
    assert len(found) >= 5


def test_突變靈敏度_句中標記那一步關掉守衛就紅(monkeypatch):
    monkeypatch.setattr(plain, "_strip_redline_marks", lambda text: text)
    display, _raw, _status = plain.plain_model(_demo_models()["exp"], page="exp")
    assert any(_MARK.search(s) for s in _strings(display))


def test_突變靈敏度_兩道都關掉_徽章帶標記回到畫面(monkeypatch):
    monkeypatch.setattr(plain, "REDLINE_BADGE_KIND", "（突變：不認得的類別）")
    monkeypatch.setattr(plain, "_strip_redline_marks", lambda text: text)
    display, _raw, _status = plain.plain_model(_demo_models()["hld"], page="hld")
    assert {b["text"] for b in _redline_badges(display)} >= {"G2†", "G3†"}
    assert _violations(display)


def test_頁尾五句_涵蓋各頁不負責的去處_不帶工程字樣與建議字眼():
    targets = {"mkt": ("持倉體檢", "標的探索", "資產配置"), "hld": ("標的探索", "市場總覽"),
               "exp": ("持倉體檢", "資產配置"), "alo": ("標的探索", "持倉體檢"), "set": ("市場總覽",)}
    for page, sentence in plain.PLAIN_FOOTERS.items():
        for name in targets[page]:
            assert f"請到{name}" in sentence, (page, name)
        assert sentence.startswith("這一頁只"), page
        for word in ("G1", "G2", "G3", "†", "44", "SSOT", "建議", "本頁不負責"):
            assert word not in sentence, (page, word)
    # 治理限制的字句照舊在頁尾裡（不是被刪掉）。
    assert "不排名、不標最佳" in plain.PLAIN_FOOTERS["exp"]
    assert "不產生再平衡動作" in plain.PLAIN_FOOTERS["alo"]
    assert "不提供調整方向" in plain.PLAIN_FOOTERS["hld"]
    assert "不下投資判斷" in plain.PLAIN_FOOTERS["set"]


def test_整句改寫表的每一個鍵都真的出現在該頁原始碼_沒有死條目():
    for page, edits in plain.REDLINE_TEXT_EDITS.items():
        source = "".join(p.read_text(encoding="utf-8") for p in (_ROOT / "ui_v2" / page).glob("*.py"))
        for old, new in edits.items():
            assert f'"{old}"' in source, (page, old)
            assert not _MARK.search(new), new


def test_HLD_兩句改一般用語_限制句意照留():
    display, _raw, _status = plain.plain_model(_demo_models()["hld"], page="hld")
    texts = list(_strings(display))
    assert "本卡只描述現況與你設定的門檻差多少，不提供任何處置方向。" in texts
    assert "檢視區間與門檻都由使用者自行輸入，系統不代填。" in texts


def test_EXP_紅線說明句改一般用語():
    display, _raw, _status = plain.plain_model(_demo_models()["exp"], page="exp")
    texts = list(_strings(display))
    assert "這裡只做客觀對照，不提供具體處置方向。" in texts
    assert "條件由使用者自行輸入，系統不代填，也沒有一鍵套用。" in texts
    assert "本卡不排名、不標最佳，也不預設排序欄位。" in texts
    assert not any(t.startswith("最後一列的") and "N 相等" in t for t in texts)   # U5


def test_ALO_說明行與欄名():
    display, _raw, _status = plain.plain_model(_demo_models()["alo"], page="alo")
    assert alo_logic.find_block(display, "ALO-1")["intro_line"] == "目標在這裡輸入；對照與試算在上方「關鍵數字」。"
    assert alo_logic.find_block(display, "ALO-7")["column_labels"][0] == "項目"
    demo = _demo_models()["alo"]
    assert alo_logic.find_block(demo, "ALO-1")["intro_line"] == alo_logic.TEXT_INTRO   # 示範模式照舊
    assert alo_logic.find_block(demo, "ALO-7")["column_labels"][0] == "鍵名"


# ───────────────────────── U5：EXP-7 稽核等式改由測試守 ─────────────────────────


def _pool(codes):
    return {"status": "ok", "backend": "service_account", "codes": list(codes), "dropped_blank": 0,
            "duplicates": 0, "message": None}


def _settings(rules):
    return {exp_live.KEY_RULES: tuple(rules), exp_live.KEY_COLUMNS: ("fund_name", "ccy"),
            exp_live.KEY_SORT: None, exp_live.KEY_WATCH: None}


# （規則, fund_profile 逐檔覆寫 {代碼: {欄: 值}}, 期望 N, 期望無法判定檔數）。
# 同日獨立稽核建議（總管裁定一併做）：加一組 N > 0 而且含無法判定的；「沒有符合」綁 N ＝ 0。
_CASES = (
    (({"field": "fund_code", "op": "不等於", "value": "C03"},), {}, 2, 0),
    (({"field": "ccy", "op": "等於", "value": "USD"},), {}, 0, 3),
    (({"field": "fund_code", "op": "不等於", "value": "C03"}, {"field": "ccy", "op": "等於", "value": "USD"}), {}, 0, 2),
    (({"field": "mgmt_fee_rate_pct", "op": "大於", "value": "1"},), {}, 0, 3),
    # N > 0 而且含無法判定：B02 符合、A01 明確不符、C03 幣別缺 → 無法判定。
    (({"field": "ccy", "op": "等於", "value": "USD"},), {"B02": {"ccy": "USD"}, "A01": {"ccy": "TWD"}}, 1, 1),
    (({"field": "ccy", "op": "等於", "value": "USD"},),
     {"B02": {"ccy": "USD"}, "A01": {"ccy": "USD"}, "C03": {"ccy": "EUR"}}, 2, 0),
)


@pytest.mark.parametrize("rules,profile,expect_n,expect_undet", _CASES, ids=[str(i) for i in range(len(_CASES))])
def test_EXP7最後一列符合檔數_等於EXP0的N(rules, profile, expect_n, expect_undet):
    pool = _pool(("B02", "A01", "C03"))
    settings = _settings(rules)
    dataset = exp_live.build_dataset(pool, settings)
    for row in dataset["fund_profile"]:
        row.update(profile.get(row["fund_code"], {}))
    inputs = {"dataset": dataset,
              "notes": {"pool": pool, "settings": settings, "settings_error": None,
                        exp_live.UNWIRED_FOR_TESTS: True}}
    model = exp_live.build_live_model(inputs, save_wired=True)
    exp2 = exp_logic.find_block(model, "EXP-2")
    exp7 = exp_logic.find_block(model, "EXP-7")
    undet = sum(1 for row in exp2["_rows"]
                if str(row["_cells"].get(exp_logic.JUDGE_COLUMN, {}).get("text", "")).startswith("⬜ 無法判定"))
    n = len(exp2["_rows"]) - undet
    assert (n, undet) == (expect_n, expect_undet), (rules, profile)
    assert exp7["_rows"], rules
    assert exp7["_rows"][-1]["_after"] == n
    text = exp_logic.find_block(model, "EXP-0")["text"]
    if n == 0:
        assert "沒有符合" in text, text
    else:
        assert f"有 {n} 檔" in text and "沒有符合" not in text, text
    assert (f"另有 {undet} 檔無法判定" in text) == (undet > 0), text
    # 正式模式畫面那一份不再寫這一行；等式本身由上面守。
    display, _raw, _status = plain.plain_model(model, page="exp")
    assert not any("N 相等" in s for s in _strings(exp_logic.find_block(display, "EXP-7")))
