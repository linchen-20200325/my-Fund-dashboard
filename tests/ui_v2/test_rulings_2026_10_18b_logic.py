# -*- coding: utf-8 -*-
"""客戶 2026-10-18 第二筆裁示（`docs/DECISIONS.md` `DEC-2026-10-18-02`；44 第七節第三小節之十）的純函式守衛。

- BL-0375：淨值超過 10 日、而且資料層已確認是即時取數失敗後退回的預存序列 → ⛔ 取數失敗，並寫出畫面實際用的
  那一期日期（`改用 <日期> 的預存淨值`）；不畫 ◇／⬜ 資料未備、不寫成本次取得、不補 0、10 日門檻不改。
  持倉體檢（`ui_v2/hld/live.py`）與標的探索（`ui_v2/exp/live.py`）各驗退回／非退回兩種，另驗累積表那一支不算退回、
  恰 10 日照用、拿掉修正會轉紅（以 monkeypatch 把判定換回舊行為，期望值必須跟著變）。
- 示範模式：持倉體檢與標的探索全情境的示範模型 md5 與動手前（`7114da08`）相同。
- BL-0374 C3 的畫面守衛（導覽不觸發取數、重新讀取）在 `tests/ui_v2/test_rulings_2026_10_18_page.py`（需要 streamlit）。
不需要 streamlit（fast lane）。
"""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from datetime import date, timedelta

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parents[1]))
sys.path.insert(0, str(_HERE))

import _exp_wired_fixture as EF  # noqa: E402
import test_hld_live_freshness as HF  # noqa: E402
from services.v2_tables import nav_dividend  # noqa: E402
from ui_v2.exp import fixtures as exp_fixtures  # noqa: E402
from ui_v2.exp import live as exp_live  # noqa: E402
from ui_v2.exp import logic as exp_logic  # noqa: E402
from ui_v2.hld import fixtures as hld_fixtures  # noqa: E402
from ui_v2.hld import live as hld_live  # noqa: E402
from ui_v2.hld import logic as hld_logic  # noqa: E402

_OLD_DAY = HF._LAST + timedelta(days=11)          # 11 天：超過門檻
_RETREAT_LINE = "⛔ 取數失敗：AAAA：改用 2026-09-18 的預存淨值"


# ───────────────────────── 鏡像常數與字面 ─────────────────────────


def test_鏡像常數等於L2真身_兩頁字面逐字相同():
    assert hld_live.LATEST_FROM_NAV_HISTORY == nav_dividend.LATEST_FROM_NAV_HISTORY
    assert exp_live.NAV_LATEST_FROM_HISTORY == nav_dividend.LATEST_FROM_NAV_HISTORY
    assert exp_live.NAV_RETREAT_FAILED_TEXT == hld_live.NAV_RETREAT_FAILED_TEXT == "改用 {day} 的預存淨值"
    # 44 第五節第五小節的模板「⛔ 取數失敗：<訊息>」；兩頁都走各自既有的那一支，不另造。
    assert hld_logic.fetch_failed_text("x") == exp_logic.fetch_failed_text("x") == "⛔ 取數失敗：x"


def test_10日門檻沒有改():
    assert hld_live.NAV_FRESH_DAYS_YELLOW == exp_live.NAV_OLD_DAYS == hld_live.thresholds.NAV_NOT_READY_DAYS == 10


# ───────────────────────── 持倉體檢 ─────────────────────────


def _hld(today=_OLD_DAY, fallback=("AAAA",), prov_patch=None, **kw):
    args = HF._args()
    prov = HF._prov(args["dataset"], fallback=set(fallback))
    for code, extra in (prov_patch or {}).items():
        prov[code].update(extra)
    holdings = args["dataset"]["holding"]
    return hld_live.build_live_model(**args, open_fund=holdings[0]["holding_id"], today=today,
                                     direct_policy_id=HF._DIRECT_ID, nav_provenance=prov, **kw)


def _hld_strings_for(model, code):
    out = []
    for block in ("HLD-2", "HLD-3"):
        group = HF._group(model, block, code)
        out += [mv["text"] for mv in group["main_values"]]
    return out


def test_HLD_退回預存又過期_畫禁止號並寫出舊資料日期_不寫資料未備():
    model = _hld()
    values = HF._values(model, "AAAA")
    for name in HF._NAV_INPUT:
        node = values[name]
        assert (node["_state"], node["text"]) == (hld_logic.STATE_ERROR, "⛔ 取數失敗"), name
        assert node["_raw"] is None and node["_has_number"] is False, name          # 不補 0、不算數
    for name in HF._DIV_ONLY:                                                        # 不以淨值為輸入的照算
        assert values[name]["_state"] == hld_logic.STATE_OK, name
    group = HF._group(model, "HLD-2", "AAAA")
    assert group["freshness_badge"] is None and group["freshness_note"] is None    # 不掛「⬜ 資料未備」徽章
    assert _RETREAT_LINE in hld_logic.find_block(model, "HLD-2")["detail_lines"]   # 日期寫在取數失敗那一句裡
    assert _RETREAT_LINE in hld_logic.find_block(model, "HLD-1")["tail_lines"]
    plot = {i["_fund_code"]: i["nav_plot_text"] for i in hld_logic.find_block(model, "HLD-5")["_items"]}
    assert plot["AAAA"] == "⛔ 取數失敗：改用 2026-09-18 的預存淨值"
    assert "AAAA" not in {r["_fund_code"] for r in hld_logic.find_block(model, "HLD-6")["nav_rows"]}
    strings = hld_logic.collect_ui_strings(model)
    assert not [s for s in strings if "AAAA" in s and "資料未備" in s]
    assert not [s for s in strings if "本次取得" in s and "不是本次取得" not in s]  # 舊資料不寫成本次取得
    # 不是預存的另兩檔照舊資料未備（同一個 10 日門檻）。
    for code in ("BBBB", "CCCC"):
        assert HF._group(model, "HLD-2", code)["freshness_badge"] == HF._ND_BADGE
        assert all(v == "⬜ 資料未備" for v in _hld_strings_for(model, code)[:2])
    assert "⬜ 另有 2 檔淨值超過 10 日未更新（資料未備），未列入" in hld_logic.find_block(model, "HLD-1")["tail_lines"]


def test_HLD_非退回_不是預存序列的過期淨值_照舊資料未備():
    model = _hld(fallback=())
    for code in ("AAAA", "BBBB", "CCCC"):
        assert HF._group(model, "HLD-2", code)["freshness_badge"] == HF._ND_BADGE
        for name in HF._NAV_INPUT:
            assert HF._values(model, code)[name]["text"] == "⬜ 資料未備", (code, name)
    assert not [s for s in hld_logic.collect_ui_strings(model) if "預存淨值" in s]


def test_HLD_累積表那一支不算退回_照舊資料未備():
    model = _hld(prov_patch={"AAAA": {"latest_from": nav_dividend.LATEST_FROM_NAV_HISTORY}})
    group = HF._group(model, "HLD-2", "AAAA")
    assert group["freshness_badge"] == HF._ND_BADGE and group["freshness_note"] == HF._OLD
    assert HF._values(model, "AAAA")["區間報酬率"]["text"] == "⬜ 資料未備"


def test_HLD_預存但恰10日_門檻照舊_照用照算():
    fresh = _hld(today=HF.FRESH)
    group = HF._group(fresh, "HLD-2", "AAAA")
    assert group["freshness_note"] == HF._FRESH
    assert all(HF._values(fresh, "AAAA")[n]["_state"] == hld_logic.STATE_OK for n in HF._NAV_INPUT)


def test_HLD_持倉以外的代碼不算退回_mark不改輸入_衝突就raise():
    args = HF._args()
    ds = args["dataset"]
    fresh = hld_live.nav_freshness(ds, HF._prov(ds, fallback={"AAAA"}), today=_OLD_DAY)
    assert hld_live.retreat_failed_codes(ds, fresh, HF._prov(ds, fallback={"AAAA"})) == {"AAAA": HF._LAST}
    no_hold = dict(ds, holding=[h for h in ds["holding"] if h["fund_code"] != "AAAA"])
    assert hld_live.retreat_failed_codes(no_hold, fresh, HF._prov(ds, fallback={"AAAA"})) == {}
    snapshot = copy.deepcopy(ds)
    out = hld_live.mark_retreat_failed(ds, {"AAAA": HF._LAST})
    assert ds == snapshot and out["fund_errors"] == {"nav": {"AAAA": "改用 2026-09-18 的預存淨值"}}
    assert hld_live.mark_retreat_failed(ds, {}) is ds
    clash = dict(ds, fund_errors={"nav": {"AAAA": "逾時"}})
    with pytest.raises(ValueError, match="退回預存序列"):
        hld_live.mark_retreat_failed(clash, {"AAAA": HF._LAST})


def test_HLD_拿掉修正會轉紅(monkeypatch):
    """把判定換回舊行為（不認任何退回），本檔守衛要看到的 ⛔ 與日期就會消失、回到資料未備 —— 證明守衛不是恆真。"""
    monkeypatch.setattr(hld_live, "retreat_failed_codes", lambda *a, **k: {})
    model = _hld()
    assert HF._values(model, "AAAA")["區間報酬率"]["text"] == "⬜ 資料未備"
    assert _RETREAT_LINE not in hld_logic.find_block(model, "HLD-2")["detail_lines"]


# ───────────────────────── 標的探索 ─────────────────────────


def _exp_nav_out(**prov_patch):
    out = EF.nav_out()
    out["nav"]["provenance"]["C03"].update(prov_patch)
    return out


def _exp_cell(nav_out, column):
    wired = EF.assemble(nav=nav_out)
    return wired, wired["cells"]["C03"][column]


_EXP_RETREAT = "⛔ 取數失敗：改用 2026-10-03 的預存淨值"
_EXP_ND = "⬜ 資料未備：最近一筆淨值 2026-10-03，已超過 10 日"


def test_EXP_退回預存又過期_三格禁止號並寫出舊資料日期_不交給計算():
    wired, _ = _exp_cell(_exp_nav_out(cache_fallback=True, source="GitHubActions:cache/nav/C03.json"), "nav_date")
    for column in exp_live.NAV_COLUMNS:
        cell = wired["cells"]["C03"][column]
        assert cell["text"] == _EXP_RETREAT and cell["state"] == exp_logic.STATE_ERROR, column
        assert exp_live.TIP_NAV_RETREAT in cell["source_tip"], column
        assert "資料未備" not in cell["text"]
    assert all(r["fund_code"] != "C03" for r in wired["nav"])     # 不參與排序與任何計算
    assert "C03" not in wired["div_ratio_pct"]                     # 配息比不算、不補 0


def test_EXP_非退回_照舊資料未備():
    wired, cell = _exp_cell(_exp_nav_out(), "nav_date")
    assert cell["text"] == _EXP_ND and cell["state"] == exp_logic.STATE_MISSING


def test_EXP_累積表那一支不算退回():
    nav_out = _exp_nav_out(cache_fallback=True, latest_from=nav_dividend.LATEST_FROM_NAV_HISTORY)
    _, cell = _exp_cell(nav_out, "nav_date")
    assert cell["text"] == _EXP_ND


def test_EXP_預存但恰10日_照用():
    out = EF.nav_out()
    out["nav"]["provenance"]["B02"].update(cache_fallback=True)
    wired = EF.assemble(nav=out)
    assert wired["cells"]["B02"]["nav_date"]["state"] == exp_logic.STATE_OK
    assert any(r["fund_code"] == "B02" for r in wired["nav"])


@pytest.mark.parametrize("prov, want", [
    ({"cache_fallback": True}, True),
    ({"cache_fallback": True, "latest_from": "cache_nav"}, True),
    ({"cache_fallback": True, "latest_from": "nav_history"}, False),
    ({"cache_fallback": False}, False),
    ({"cache_fallback": 1}, False),
    ({}, False),
    (None, False),
])
def test_EXP_退回判定只讀既有兩個鍵(prov, want):
    assert exp_live.nav_retreat_failed(prov) is want


def test_EXP_拿掉修正會轉紅(monkeypatch):
    monkeypatch.setattr(exp_live, "nav_retreat_failed", lambda prov: False)
    _, cell = _exp_cell(_exp_nav_out(cache_fallback=True), "nav_date")
    assert cell["text"] == _EXP_ND


# ───────────────────────── 示範模式逐位元組不變 ─────────────────────────


def _without_batch3b_marks(node):
    """BL-0250 批次 3-B：產生處新增的資料類標記（`ui_v2/page_health.py::MARK_KEYS`，畫面不讀）不算進 md5；
    基準值一個都沒改（拿掉標記之後逐位元組仍與動手前相同）。"""
    from ui_v2.page_health import MARK_KEYS
    if isinstance(node, dict):
        return {k: _without_batch3b_marks(v) for k, v in node.items() if k not in MARK_KEYS}
    if isinstance(node, list):
        return [_without_batch3b_marks(v) for v in node]
    if isinstance(node, tuple):
        return tuple(_without_batch3b_marks(v) for v in node)
    return node


def _restore_old_page_title(node, new: str, old: str) -> int:
    """2026-10-27 BL-0478（`DEC-2026-10-27-02`，決策者：客戶）：頁名換成正式頁名後，模型頂層 `title` 是唯一改的一格。
    把等於新頁名的 `title` 原地還原成舊頁名，回傳還原了幾格；呼叫端斷言 > 0，再拿舊基準值比 —— 證明模型只差頁名這一格。"""
    count = 0
    if isinstance(node, dict):
        if node.get("title") == new:
            node["title"] = old
            count += 1
        for value in node.values():
            count += _restore_old_page_title(value, new, old)
    elif isinstance(node, (list, tuple)):
        for value in node:
            count += _restore_old_page_title(value, new, old)
    return count


def test_示範模式_持倉體檢與標的探索全情境模型_md5與動手前相同():
    """示範模式不經過 `live.py`。基準值於 `7114da08`（本批動手前）以同一支序列化量得。"""
    default = lambda o: sorted(o, key=repr) if isinstance(o, (set, frozenset)) else repr(o)  # noqa: E731
    out = []
    for name in hld_fixtures.ALL_SCENARIO_NAMES:
        out.append(["hld", name, hld_logic.build_page_model(**hld_fixtures.scenario(name))])
    for name in exp_fixtures.ALL_SCENARIO_NAMES:
        for save_failed in exp_fixtures.SAVE_FAIL_CHOICES:
            params = dict(exp_fixtures.scenario_with(name, save_failed=save_failed))
            ds = params.pop("dataset")
            out.append(["exp", name, save_failed, exp_logic.build_page_model(ds, save_failed=save_failed, **params)])
    # 2026-10-27 BL-0478：頁名「持倉體檢」→「💼 我的持股」、「標的探索」→「🔍 找基金」（每個模型頂層 `title` 一格）；還原後回到同一個基準值。
    assert _restore_old_page_title([e for e in out if e[0] == "hld"], "💼 我的持股", "持倉體檢") == len(hld_fixtures.ALL_SCENARIO_NAMES)
    assert _restore_old_page_title([e for e in out if e[0] == "exp"], "🔍 找基金", "標的探索") > 0
    digest = hashlib.md5(json.dumps(_without_batch3b_marks(out), ensure_ascii=False, sort_keys=True,
                                    default=default).encode()).hexdigest()
    assert digest == "4f2cbd85a00bdcff4e4aa1ee5b9508a0", digest


# ───────────────────────── 一般畫面去工程化：日期句照留 ─────────────────────────


def test_去工程化_退回日期句照留在一般畫面_其他原文照舊換成狀態描述():
    from ui_v2 import plain

    assert plain.NAV_RETREAT_FAILED_TEXT == hld_live.NAV_RETREAT_FAILED_TEXT == exp_live.NAV_RETREAT_FAILED_TEXT
    assert plain.plain_text("⛔ 取數失敗：AAAA：改用 2026-09-18 的預存淨值", page="hld") == (
        "⛔ 淨值 取數失敗：AAAA：改用 2026-09-18 的預存淨值")
    assert plain.plain_text("⛔ 取數失敗：改用 2026-10-03 的預存淨值", page="exp") == (
        "⛔ 淨值 取數失敗：改用 2026-10-03 的預存淨值")
    # 上游原文照舊換成狀態描述（不因本條放寬）；日期格式不對、或句子多了字，也不算這一句。
    for raw in ("⛔ 取數失敗：AAAA：ConnectionError 逾時", "⛔ 取數失敗：改用 2026/09/18 的預存淨值",
                "⛔ 取數失敗：改用 2026-09-18 的預存淨值，另有原文 timeout"):
        assert plain.plain_text(raw, page="hld").endswith(plain.STATE_FETCH_DEFAULT), raw


def test_失敗去重_退回日期句照留_資料狀態行記淨值():
    from ui_v2 import health

    for text in ("⛔ 淨值 取數失敗：AAAA：改用 2026-09-18 的預存淨值", "⛔ 淨值 取數失敗：改用 2026-10-03 的預存淨值"):
        display = {"blocks": [{"code": "HLD-2", "title": "績效與風險卡", "_state": "系統錯誤", "detail_lines": [text, text]}]}
        after, summary = health.dedupe_failures(display)
        assert after["blocks"][0]["detail_lines"] == [text]          # 照留日期；同一串裡一模一樣的 ⛔ 行只留一行
        assert summary["fetch_failed"] == ["淨值"] and summary["affected_blocks"] == []


def test_失敗去重_同一字串裡日期句與其他失敗摘要並存_其他摘要照舊改寫並記進資料狀態行():
    """2026-10-18 獨立稽核回修：日期句不得讓同一字串裡的其他失敗摘要逃過去重。"""
    from ui_v2 import health

    keep = "⛔ 淨值 取數失敗：AAAA：改用 2026-09-18 的預存淨值"
    other = f"⛔ 配息 取數失敗：BBBB 的{health.plain.STATE_FETCH_DEFAULT}"
    for text, want in ((f"{keep}；{other}", f"{keep}；⛔ BBBB 取數失敗"),
                       (f"{other}；{keep}", f"⛔ BBBB 取數失敗；{keep}")):
        display = {"blocks": [{"code": "HLD-2", "title": "績效與風險卡", "_state": "系統錯誤", "detail_lines": [text]}]}
        after, summary = health.dedupe_failures(display)
        assert after["blocks"][0]["detail_lines"] == [want]
        assert sorted(summary["fetch_failed"]) == sorted(["淨值", "配息"])
