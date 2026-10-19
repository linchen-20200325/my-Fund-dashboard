# -*- coding: utf-8 -*-
"""BL-0250 實機驗收回修 批次 3 第一段（3-A）（客戶 2026-10-19 批次 3 裁示，`docs/DECISIONS.md` `DEC-2026-10-19-05`；
44 第七節第三小節之十二）的邏輯守衛（fast lane）。

每一項至少一條正面（正式模式改了）＋一條反面（不該改的地方沒改：示範模式、混有真的取數失敗、其他缺資料情境）。
畫面層的守衛（五頁正式模式情境逐字）在 `tests/ui_v2/test_bl0250_batch3a_page.py`。
突變（把修復拿掉 → 本檔對應的測試轉紅）見本批回報。
"""

from __future__ import annotations

import copy
import pathlib
import sys
from datetime import timedelta, timezone

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
for _p in (_HERE, _HERE.parent, _HERE.parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ui_v2 import health, plain, sections  # noqa: E402
from ui_v2.mkt import fixtures as mkt_fixtures  # noqa: E402
from ui_v2.mkt import logic as mkt_logic  # noqa: E402
from ui_v2.set import fixtures as set_fixtures  # noqa: E402
from ui_v2.set import live as set_live  # noqa: E402
from ui_v2.set import logic as set_logic  # noqa: E402

TPE = timezone(timedelta(hours=8))


# ═══════════════════════ 待裁示 (2)＋批次 1 四處遺留：plain 認得 EXP-2 那一句尚未設定 ═══════════════════════


def test_EXP2摘要那一句_與exp正式模式的真身逐字相同_去掉取數失敗字首():
    exp_live = pytest.importorskip("ui_v2.exp.live")
    prefix = "⛔ 取數失敗："
    assert exp_live.TEXT_POOL_NOT_CLOUD.startswith(prefix)
    assert plain.MSG_POOL_NOT_CLOUD_SUMMARY == exp_live.TEXT_POOL_NOT_CLOUD[len(prefix):]


def test_EXP2摘要那一句_認成尚未設定_真的取數失敗照舊認不出():
    assert plain.not_configured_state(plain.MSG_POOL_NOT_CLOUD_SUMMARY) == "選股池的雲端來源尚未設定"
    assert plain.not_configured_state("選股池讀取失敗（連線逾時），候選清單不列任何一檔") is None


def test_缺服務帳戶的狀態句_寫Google服務帳戶():
    assert plain.not_configured_state(plain.MSG_NO_SERVICE_ACCOUNT) == "Google 服務帳戶尚未設定"
    assert all("讀取用的服務帳戶" not in state for _m, _c, state in plain._KNOWN_MESSAGES)


# ═══════════════════════ 第 2 點：尚未設定的值旁不掛「取數失敗」徽章（health） ═══════════════════════


def _badge_block(value_text, *, extra=None):
    node = {"label": "信用利差", "value_text": value_text,
            "badges": [{"_kind": "狀態", "_tone": "紅", "text": "取數失敗"}, {"_kind": "來源", "text": "T1"}]}
    if extra:
        node.update(extra)
    return {"code": "MKT-2", "title": plain.BLOCK_NAMES["MKT-2"], "_layer": 2, "_state": "ok", "main_values": [node]}


def _run(display):
    after, summary = health.dedupe_failures(display)
    health.relabel_unconfigured(after, summary)      # 就地改寫（回傳的是尚未設定的塊對照，不是畫面）
    return after


def test_值的成因全屬尚未設定_拿掉取數失敗那一枚_其他徽章不動():
    out = _run({"blocks": [_badge_block("⛔ 市場指標 取數失敗：資料來源的金鑰尚未設定")]})
    node = out["blocks"][0]["main_values"][0]
    assert node["value_text"] == "⛔ 尚未設定"
    assert node["badges"] == [{"_kind": "來源", "text": "T1"}]


def test_值的成因是真的取數失敗_取數失敗徽章照掛():
    out = _run({"blocks": [_badge_block("⛔ 市場指標 取數失敗：相關數字暫時無法判定")]})
    texts = [b["text"] for b in out["blocks"][0]["main_values"][0]["badges"]]
    assert "取數失敗" in texts


def test_值那一格以外的欄位_成因不算進那一枚徽章():
    """同一節點另一欄（例：停用原因）寫尚未設定、值那一格是真的取數失敗 → 照掛（不得把真的取數失敗那一枚拿掉）。"""
    block = _badge_block("⛔ 市場指標 取數失敗：相關數字暫時無法判定",
                         extra={"disabled_reason": "⛔ 使用者設定 取數失敗：設定試算表尚未設定"})
    out = _run({"blocks": [block]})
    assert "取數失敗" in [b["text"] for b in out["blocks"][0]["main_values"][0]["badges"]]


def test_去重那一步不拿徽章_只在relabel拿_結構不變式照舊():
    display = {"blocks": [_badge_block("⛔ 市場指標 取數失敗：資料來源的金鑰尚未設定")]}
    after, summary = health.dedupe_failures(display)
    assert len(after["blocks"][0]["main_values"][0]["badges"]) == 2      # 去重只記、不改結構
    assert summary["unconfigured_value_nodes"] == [after["blocks"][0]["main_values"][0]]


def test_尚未設定的系統錯誤佔位主值_取數失敗改尚未設定_同節點徽章拿掉_他節點不動():
    hold = {"_state": "系統錯誤", "text": health.LINE_FETCH_FAILED,
            "badges": [{"_kind": "狀態", "text": "取數失敗"}]}
    other = {"label": "另一項", "value_text": "1.0", "badges": [{"_kind": "狀態", "text": "取數失敗"}]}
    block = {"code": "HLD-1", "title": plain.BLOCK_NAMES["HLD-1"], "_layer": 2, "_state": "系統錯誤",
             "_placeholder": hold, "main_values": [other]}
    health._relabel_error_placeholders(block, ["保單試算表"])
    # ~~`health.LINE_NOT_CONFIGURED`（只寫狀態族）~~ → 同批總管裁定（適用 `DEC-2026-10-19-05` 第 2 點；有意識的更正，不是漏刪）：補上哪一項。
    assert hold["text"] == "⛔ 尚未設定：保單試算表" and hold["badges"] == []
    assert other["badges"] == [{"_kind": "狀態", "text": "取數失敗"}]
    with pytest.raises(ValueError):
        health._relabel_error_placeholders({"_state": "系統錯誤", "text": health.LINE_FETCH_FAILED}, [])


# ═══════════════════════ 第 2 點（set|stale 那一種）：一筆取數紀錄全屬尚未設定 ═══════════════════════

_FRED = plain.MSG_FRED_MISSING


def _rec(outcome="failed", message=None, tier="市場指標", **kw):
    return {"log_id": kw.get("log_id", "L1"), "source_tier": tier, "started_at": kw.get("started_at", "2026-10-19T01:00:00Z"),
            "outcome": outcome, "message": message}


@pytest.mark.parametrize("message, expected", [
    (f"credit_spread_pct: {_FRED}\nterm_spread_pct: {_FRED}", ["資料來源的金鑰"]),
    (f"{_FRED}", ["資料來源的金鑰"]),
    (f"credit_spread_pct: {_FRED}\n\npolicy_rate_pct: {_FRED}\n", ["資料來源的金鑰"]),
])
def test_紀錄每一則訊息都屬尚未設定_回對象(message, expected):
    assert set_live.record_unconfigured_names(_rec(message=message)) == expected


@pytest.mark.parametrize("record", [
    _rec(message=f"credit_spread_pct: {_FRED}\nvix: fetch_url returned None: ^VIX (kind=unreachable)"),  # 混有真的失敗
    _rec(message="vix: fetch_url returned None: ^VIX (kind=unreachable)"),
    _rec(message=""),
    _rec(message=None),
    _rec(outcome="ok", message=f"credit_spread_pct: {_FRED}"),
])
def test_紀錄混有別的訊息或沒有訊息或不是失敗_回None(record):
    assert set_live.record_unconfigured_names(record) is None


def test_結果欄中文_ok寫取數完成_failed寫取數失敗_全屬尚未設定寫尚未設定():
    assert set_live._result_text(_rec("ok", None)) == ("取數完成", set_live.RESULT_OK)
    assert set_live._result_text(_rec(message="vix: x")) == ("⛔ 取數失敗", set_live.RESULT_FAILED)
    assert set_live._result_text(_rec(message=_FRED)) == ("⛔ 尚未設定：資料來源的金鑰", set_live.RESULT_UNCONFIGURED)
    with pytest.raises(ValueError):
        set_live._result_text(_rec("partial", None))


def _set2(results):
    rows = [{"_tier": t, "tier_text": t, "result_text": r, "badges": [{"_kind": "狀態", "text": "取數失敗"}]}
            for t, r in results]
    return {"_rows": rows, "_failed_tiers": [t for t, r in results if r == "failed"]}


def test_SET2結果欄改中文_全屬尚未設定那一列不掛取數失敗徽章():
    logs = [_rec(message=_FRED, tier="市場指標", log_id="a"),
            _rec(message="x: boom", tier="淨值", log_id="b"),
            _rec("ok", None, tier="配息", log_id="c")]
    set2 = _set2([("市場指標", "failed"), ("淨值", "failed"), ("配息", "ok")])
    set_live._plain_results(set2, {"fetch_log": logs})
    got = {r["_tier"]: (r["result_text"], r["_result"], r["badges"]) for r in set2["_rows"]}
    assert got["市場指標"] == ("⛔ 尚未設定：資料來源的金鑰", "unconfigured", [])
    assert got["淨值"] == ("⛔ 取數失敗", "failed", [])                  # 結果欄已帶 ⛔：徽章不重複
    assert got["配息"][0:2] == ("取數完成", "ok")
    assert sections.set2_summary({"placeholder": None, "_rows": set2["_rows"]}) == (
        "⛔ 最近一次取數失敗：淨值；⛔ 尚未設定：資料來源的金鑰（市場指標）；最近一次取數完成：配息")


def test_SET0燈_失敗層級全屬尚未設定_狀態字改尚未設定_燈色與判定不動():
    logs = [_rec(message=_FRED)]
    set2 = _set2([("市場指標", "failed")])
    set_live._plain_results(set2, {"fetch_log": logs})
    set0 = {"_state": "來源失敗", "text": "失敗的來源層級：市場指標", "state_word": "狀態：來源失敗", "_tone": "紅"}
    set_live._relabel_unconfigured_lamp(set0, set2)
    assert set0 == {"_state": "來源失敗", "text": "尚未設定：資料來源的金鑰（市場指標）",
                    "state_word": "狀態：尚未設定", "_tone": "紅"}


def test_SET0燈_混有真的失敗層級_狀態字照舊_只改尚未設定那一層():
    logs = [_rec(message=_FRED, tier="市場指標", log_id="a"), _rec(message="x: boom", tier="淨值", log_id="b")]
    set2 = _set2([("市場指標", "failed"), ("淨值", "failed")])
    set_live._plain_results(set2, {"fetch_log": logs})
    set0 = {"_state": "來源失敗", "text": "失敗的來源層級：市場指標、淨值", "state_word": "狀態：來源失敗"}
    set_live._relabel_unconfigured_lamp(set0, set2)
    assert set0["state_word"] == "狀態：來源失敗"
    assert set0["text"] == "失敗的來源層級：淨值；尚未設定：資料來源的金鑰（市場指標）"


def test_SET0燈_沒有尚未設定的層級_一個字都不動():
    logs = [_rec(message="x: boom")]
    set2 = _set2([("市場指標", "failed")])
    set_live._plain_results(set2, {"fetch_log": logs})
    set0 = {"_state": "來源失敗", "text": "失敗的來源層級：市場指標", "state_word": "狀態：來源失敗"}
    before = dict(set0)
    set_live._relabel_unconfigured_lamp(set0, set2)
    assert set0 == before
    ok = {"_state": "ok", "text": "t"}
    set_live._relabel_unconfigured_lamp(ok, set2)
    assert ok == {"_state": "ok", "text": "t"}


# ═══════════════════════ SET-4／SET-6 讀取失敗的收合標題 ═══════════════════════


@pytest.mark.parametrize("code, table, expected", [
    ("not_configured", "user_setting", "⛔ 尚未設定：試算表 ID"),
    ("no_service_account", "fetch_log", "⛔ 尚未設定：Google 服務帳戶"),
    ("api", "user_setting", "⛔ 取數失敗"),
    ("api", "fetch_log", "⛔ 取數失敗"),
    ("cooling", "fetch_log", "⛔ 取數失敗"),
])
def test_讀取失敗的收合標題_依成因寫_不寫表名(code, table, expected):
    got = set_live._read_failure_title({"text": "卡上那一句"}, {}, {"table_errors": {table: {"code": code}}}, table)
    assert got == expected and table not in got


def test_設定試算表冷卻中_參數編輯標題寫卡上那一句暫停句_不是取數失敗():
    got = set_live._read_failure_title({"text": "⚠ 暫停中"}, {}, {"table_errors": {"user_setting": {"code": "cooling"}}},
                                       "user_setting")
    assert got == "⚠ 暫停中"


# ═══════════════════════ 第 3 點：缺 Google 服務帳戶 ═══════════════════════


def test_缺服務帳戶_兩種停用原因_其他閘門照舊():
    assert set_live.gate_reason({"state": "no_service_account"}) == "尚未設定 Google 服務帳戶，暫停寫入"
    assert set_live.gate_reason({"state": "not_configured"}) == set_live.TEXT_NO_SHEET_ID
    notes = {"gate": {"state": "no_service_account"}, "source_cooldowns": [], "wired_tiers": set_logic.TIERS}
    assert set_live.refetch_button("市場指標", notes)["disabled_reason"] == "尚未設定 Google 服務帳戶，暫停取數"
    notes = {"gate": {"state": "not_configured"}, "source_cooldowns": [], "wired_tiers": set_logic.TIERS}
    assert set_live.refetch_button("市場指標", notes)["disabled_reason"] == set_live.TEXT_NO_SHEET_ID


def test_缺服務帳戶_一般畫面那一句換字_訊息原文的塊與底線鍵不換():
    model = {"blocks": [{"code": "SET-3", "head_lines": [{"text": set_live._SA_RAW_LINE}], "_raw": set_live._SA_RAW_LINE}]}
    out = set_live._plain_set_words(model)
    assert out["blocks"][0]["head_lines"][0]["text"] == "⛔ 尚未設定：Google 服務帳戶"
    assert out["blocks"][0]["_raw"] == set_live._SA_RAW_LINE


# ═══════════════════════ U7：SET-3／SET-6／SET-7（走正式組裝，env 替身同 test_set_live_logic） ═══════════════════════

from test_set_live_logic import R, _b, _page, env  # noqa: E402,F401  （fixture 由 pytest 依名稱取用）


def _demo():
    return set_logic.build_page_model(set_fixtures.scenario("ok"))


def test_U7a_SET3表頭與列上用中文_示範模式照舊英文(env):
    _data, model = _page()
    set3 = _b(model, "SET-3")
    assert set3["column_labels"] == ["設定項目", "目前值", "資料型態", "最後修改時間（UTC+8）"]
    for row in set3["_rows"]:
        assert row["key_text"] == plain.key_name(row["_key"])
        assert row["kind_text"] in ("清單", "條件", "日期", "數字", "⬜")
    demo = set_logic.find_block(_demo(), "SET-3")
    assert demo.get("column_labels") != set3["column_labels"]
    assert any(r["kind_text"] in set_live.KIND_NAMES for r in demo["_rows"])        # 示範模式照舊英文 value_kind


def test_U7c_SET6不列紀錄編號欄_結果中文_原值在進階診斷(env):
    source = pytest.importorskip("ui_v2.set.source")
    source.refetch("市場指標")
    _data, model = _page()
    set6 = _b(model, "SET-6")
    assert set6["column_labels"] == set_live.SET6_COLUMN_LABELS and "紀錄編號" not in set6["column_labels"]
    assert set6["_rows"] and all(len(r["cells"]) == len(set6["column_labels"]) for r in set6["_rows"])
    assert all(r["cells"][3] in ("取數完成", "⛔ 取數失敗") or r["cells"][3].startswith("⛔ 尚未設定：")
               for r in set6["_rows"])
    assert set6["_raw_log"] and all(raw[2] in ("ok", "failed") for raw in set6["_raw_log"])
    assert "由新到舊排列。" in set6["detail_lines"]
    joined = "\n".join(str(c) for r in set6["_rows"] for c in r["cells"])
    assert not any(raw[0] in joined for raw in set6["_raw_log"])                    # 紀錄編號不上一般表格


def test_U7d_SET7留在原位_改標題_預設收合_內容不改(env):
    _data, model = _page()
    codes = [b["code"] for b in model["blocks"]]
    set7 = _b(model, "SET-7")
    assert set7["title"] == "欄位對照（進階）" and set7["_default_open"] is False
    assert set7["summary_text"].startswith("每一欄資料用在哪一塊")
    demo = _demo()
    assert codes.index("SET-7") == [b["code"] for b in demo["blocks"]].index("SET-7")
    demo7 = set_logic.find_block(demo, "SET-7")
    assert demo7["title"] != "欄位對照（進階）"                                       # 示範模式照舊
    assert set7["_rows"] == demo7["_rows"] or len(set7["_rows"]) == len(demo7["_rows"])


def test_U7b_SET2結果不寫英文原值_訊息原文照印(env):
    source = pytest.importorskip("ui_v2.set.source")
    source.refetch("市場指標")
    _data, model = _page()
    for row in _b(model, "SET-2")["_rows"]:
        assert row["result_text"] not in ("ok", "failed")


# ═══════════════════════ 待裁示 (4)：MKT-7 延遲日數以台北日期算 ═══════════════════════


def test_延遲日數_tz為None_照舊取世界協調時間日期():
    assert mkt_logic.delay_days("2026-09-18", "2026-09-18T20:30:00Z") == 0
    assert mkt_logic.delay_days("2026-09-18", "2026-09-18T20:30:00Z", tz=None) == 0


def test_延遲日數_台北時區_跨過台北午夜算下一天():
    assert mkt_logic.delay_days("2026-09-18", "2026-09-18T20:30:00Z", tz=TPE) == 1
    assert mkt_logic.delay_days("2026-09-18", "2026-09-18T01:00:00Z", tz=TPE) == 0      # 沒跨過：兩種算法相同
    assert mkt_logic.delay_days("2026-09-18", "2026-09-18T20:30:00+00:00", tz=TPE) == 1
    with pytest.raises(ValueError):
        mkt_logic.delay_days("2026-09-18", "2026-09-18T20:30:00", tz=TPE)               # 沒有時區不猜


def test_MKT7與核心卡徽章_同一個天數_obs與fetched兩欄一字不改():
    dataset = copy.deepcopy(mkt_fixtures.dataset_all_ok())
    for row in dataset["rows"]:
        row["fetched_at"] = row["obs_date"] + "T20:30:00Z"
    demo = mkt_logic._build_mkt7(dataset)
    got = mkt_logic._build_mkt7(dataset, delay_tz=TPE)
    assert {r["delay_text"] for r in demo["_rows"] if "_missing_cells" not in r} <= {"0 日"}
    assert {r["delay_text"] for r in got["_rows"] if "_missing_cells" not in r} == {"1 日"}
    assert [(r["obs_text"], r["fetched_text"]) for r in got["_rows"]] == [
        (r["obs_text"], r["fetched_text"]) for r in demo["_rows"]]
    rows = [r for r in dataset["rows"] if r["indicator_key"] == dataset["rows"][0]["indicator_key"]]
    assert mkt_logic._freshness_badge(rows, TPE)["text"] == "延遲 1 日"
    assert mkt_logic._freshness_badge(rows)["text"] != "延遲 1 日"


# ═══════════════════════ U4：HLD-4 正式模式不畫永遠停用的「套用」 ═══════════════════════


def test_只有停用中的套用不畫_其他按鈕照畫():
    hld_live = pytest.importorskip("ui_v2.hld.live")
    assert hld_live.hidden_in_live({"_action_kind": "套用", "_enabled": False})
    assert not hld_live.hidden_in_live({"_action_kind": "套用", "_enabled": True})
    assert not hld_live.hidden_in_live({"_action_kind": "存檔", "_enabled": False})
    assert not hld_live.hidden_in_live({"_action_kind": "新增列", "_enabled": True})


# ═══════════════════════ 待裁示 (1)：EXP 三張核心卡的來源／新鮮度 → ⬜ 不適用 ═══════════════════════


def _exp_model():
    exp_logic = pytest.importorskip("ui_v2.exp.logic")
    ph = [exp_logic.placeholder_badge("來源", "〔來源層級〕"), exp_logic.placeholder_badge("新鮮度", "〔新鮮度〕")]
    other = {"_kind": "狀態", "_tone": "黃", "text": "部分缺"}
    blocks = [{"code": c, "badges": copy.deepcopy(ph) + [dict(other)]} for c in ("EXP-1", "EXP-2", "EXP-3")]
    blocks.append({"code": "EXP-4", "badges": copy.deepcopy(ph)})
    blocks.append({"code": "EXP-5", "badges": [{"_kind": "來源", "_tone": "中性", "text": "T1"}]})
    return {"blocks": blocks}, other


def test_三張核心卡的佔位徽章換成一枚不適用_其他徽章不動():
    exp_live = pytest.importorskip("ui_v2.exp.live")
    model, other = _exp_model()
    assert exp_live.card_provenance_not_applicable(model) == 3
    for block in model["blocks"][:3]:
        assert block["badges"] == [other, {"_kind": "來源", "_tone": "中性", "_not_applicable": True,
                                            "text": "⬜ 不適用（這張卡由多檔基金組成，沒有單一的來源與新鮮度）"}]


def test_不適用只限三張核心卡的佔位_其他塊與真的來源徽章不換():
    exp_live = pytest.importorskip("ui_v2.exp.live")
    model, _other = _exp_model()
    before = copy.deepcopy(model["blocks"][3:])
    exp_live.card_provenance_not_applicable(model)
    assert model["blocks"][3:] == before
    assert "⬜ 不適用" not in str(model["blocks"][3:])
    again = copy.deepcopy(model)
    assert exp_live.card_provenance_not_applicable(again) == 0 and again == model     # 沒有佔位就不動


# ═══════════════════════ 同批總管裁定（決策者：AI 總管，適用客戶 DEC-2026-10-19-05 第 2／3 點；44 之十二其九） ═══════════════════════


def _mkt_model():
    def row(key):
        return {"indicator_key": key, "obs_text": "⬜", "fetched_text": "⬜", "tier_text": "⬜", "delay_text": "⬜",
                "badges": [{"_kind": "狀態", "text": "資料未備"}]}
    missing = dict(row("tw_fx"), _missing_cells=("obs_text",))
    rows = [row("credit_spread_pct"), row("policy_rate_pct"), row("vol_index"), missing]
    items = [{"name": k, "badges": [{"_kind": "狀態", "text": "資料未備"}]}
             for k in ("credit_spread_pct", "policy_rate_pct", "vol_index", "tw_fx")]
    return {"blocks": [{"code": "MKT-5", "_items": items}, {"code": "MKT-6", "_rows": [], "detail_lines": []},
                       {"code": "MKT-7", "_rows": rows}]}


_UNCONF = {"credit_spread_pct": "資料來源的金鑰", "policy_rate_pct": "資料來源的金鑰"}


def test_裁定1_MKT7_缺金鑰的鍵寫尚未設定_不掛取數失敗_真的失敗照掛():
    model = _mkt_model()
    sections.mark_mkt7_fetch_failed(model, ["credit_spread_pct", "policy_rate_pct", "vol_index"], _UNCONF)
    rows = {r["indicator_key"]: r for r in model["blocks"][2]["_rows"]}
    for key in _UNCONF:
        r = rows[key]
        assert (r["obs_text"], r["fetched_text"], r["tier_text"], r["delay_text"]) == (
            "⛔ 尚未設定：資料來源的金鑰", "⛔", "⛔", "⛔")
        assert r["badges"] == [] and r["_unconfigured"] == "資料來源的金鑰" and not r.get("_fetch_failed")
    assert [b["text"] for b in rows["vol_index"]["badges"]] == ["取數失敗"] and rows["vol_index"]["_fetch_failed"]
    assert [b["text"] for b in rows["tw_fx"]["badges"]] == ["資料未備"]                  # 真正的資料未備照舊
    items = {i["name"]: i for i in model["blocks"][0]["_items"]}
    assert items["credit_spread_pct"]["badges"] == [] and items["credit_spread_pct"]["_unconfigured"] == "資料來源的金鑰"
    assert [b["text"] for b in items["vol_index"]["badges"]] == ["取數失敗"]


def test_裁定1_沒有傳尚未設定對照_行為與改動前相同():
    a, b = _mkt_model(), _mkt_model()
    sections.mark_mkt7_fetch_failed(a, ["credit_spread_pct", "vol_index"])
    sections.mark_mkt7_fetch_failed(b, ["credit_spread_pct", "vol_index"], {})
    assert a == b
    assert [x["text"] for x in a["blocks"][2]["_rows"][0]["badges"]] == ["取數失敗"]


@pytest.mark.parametrize("failed, unconf, missing, expected", [
    ([], ["高收益信用利差", "政策利率"], False, ["⛔ 尚未設定：資料來源的金鑰"]),
    (["波動度指數"], ["高收益信用利差"], False, ["⛔ 取數失敗：波動度指數", "⛔ 尚未設定：資料來源的金鑰（高收益信用利差）"]),
    ([], ["高收益信用利差"], True, ["◇ 資料未備：市場指標尚無資料", "⛔ 尚未設定：資料來源的金鑰（高收益信用利差）"]),
    (["波動度指數"], [], True, ["◇ 資料未備：市場指標尚無資料", "⛔ 取數失敗：波動度指數"]),   # 改動前的混合寫法照舊
    (["波動度指數"], [], False, ["⛔ 取數失敗"]),                                              # 改動前的全部失敗寫法照舊
])
def test_裁定1_MKT6表尾_依成因分行(failed, unconf, missing, expected):
    rows = [{"indicator_key": k, "_fetch_failed": True} for k in failed]
    rows += [{"indicator_key": k, "_unconfigured": "資料來源的金鑰"} for k in unconf]
    rows += [{"indicator_key": "新臺幣對美元匯率"}] if missing else []
    model = {"blocks": [{"code": "MKT-6", "_rows": [], "detail_lines": ["◇ 資料未備：市場指標尚無資料", "說明"]},
                        {"code": "MKT-7", "_rows": rows}]}
    assert sections.mark_mkt6_fetch_failed(model) == 1
    assert model["blocks"][0]["detail_lines"] == expected + ["說明"]


def test_裁定1_尚未設定字樣與health同字():
    assert sections.MKT_NOT_CONFIGURED == health.TEXT_NOT_CONFIGURED


def test_裁定2_燈的成因全是缺服務帳戶_狀態字與文案改尚未設定_燈色判定不動(env):
    env.cfg.pop("google_service_account")
    _data, model = _page()
    set0 = _b(model, "SET-0")
    assert (set0["state_word"], set0["text"]) == ("狀態：尚未設定", "尚未設定：Google 服務帳戶")
    assert (set0["_tone"], set0["_state"], set0["glyph"]) == ("紅", "讀取失敗", "⛔")


def test_裁定2_燈的成因是真的讀取失敗_照寫取數失敗(env, monkeypatch):
    source = pytest.importorskip("ui_v2.set.source")

    def broken(values):
        raise R.SettingsSheetError("ConnectionError: refused", code="api")
    monkeypatch.setattr(source.settings_store, "load_fetch_log", broken)
    _data, model = _page()
    set0 = _b(model, "SET-0")
    assert set0["state_word"] == "狀態：取數失敗" and set0["text"] == "⛔ 取數失敗：ConnectionError: refused"


def test_裁定3_SET2與SET6缺服務帳戶那一格寫統一句_原文進進階診斷(env):
    env.cfg.pop("google_service_account")
    _data, model = _page()
    for code in ("SET-2", "SET-6"):
        assert _b(model, code)["placeholder"]["text"] == "⛔ 尚未設定：Google 服務帳戶"
        shown = [_b(model, code)["placeholder"]["text"]] + list(_b(model, code).get("tail_lines") or ())
        assert not any("google_service_account" in t for t in shown)       # 底線鍵 `_read_failure` 照舊帶原文（判定用，不上畫面）
    raw = model[set_live.ADVANCED_RAW_KEY]
    assert [r[0] for r in raw] == [_b(model, "SET-2")["title"], _b(model, "SET-6")["title"]]
    assert all(r[1] == "⛔ 取數失敗：" + plain.MSG_NO_SERVICE_ACCOUNT for r in raw)


def test_裁定3_缺試算表ID那一格照舊_不進進階診斷(env):
    env.cfg.pop("SETTINGS_SHEET_ID")
    _data, model = _page()
    assert _b(model, "SET-2")["placeholder"]["text"] == "⛔ 未設定試算表 ID，暫停寫入"
    assert model[set_live.ADVANCED_RAW_KEY] == []
