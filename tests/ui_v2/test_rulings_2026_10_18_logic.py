# -*- coding: utf-8 -*-
"""客戶 2026-10-18 裁示（`docs/DECISIONS.md` `DEC-2026-10-18-01`；44 第七節第三小節之九）的純函式守衛。

- BL-0371：沒有異常時省略整體正常宣告（`MKT-0` 三塊皆 ok、`SET-0` 兩個計數皆為零；示範與正式模式皆同）。
- BL-0373：取數失敗＝⛔、資料未備＝◇、不適用＝⬜（`MKT-7` 取數失敗的鍵、`SET-1` 只有失敗紀錄的那一類）。
- S1／S4／C1 的燈判定見 `tests/ui_v2/test_set_reshape_logic.py`、`tests/ui_v2/test_set_live_logic.py`；C2 見本檔與
  `tests/ui_v2/test_rulings_2026_10_18_page.py`。**C3 未裁，本檔不碰**（`test_未設定_導覽照舊顯示_它指向的重新取數停用` 照舊）。
BL-0373 只改正式模式；示範模式模型除 BL-0371 那兩句外逐位元組不變（本檔最後一條）。不需要 streamlit（fast lane）。
"""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from ui_v2 import sections
from ui_v2.mkt import fixtures as mkt_fixtures
from ui_v2.mkt import logic as mkt_logic
from ui_v2.set import fixtures as set_fixtures
from ui_v2.set import logic as set_logic


def _mkt(ds):
    return mkt_logic.build_page_model(ds)


# ───────────────────────── 鏡像常數對真身 ─────────────────────────


def test_鏡像常數逐字等於真身():
    assert mkt_logic._status_badge("取數失敗") == sections.MKT_BADGE_FETCH_FAILED
    assert mkt_logic._status_badge("資料未備")["text"] == sections.MKT_BADGE_MISSING_TEXT
    row = mkt_logic.find_block(_mkt(mkt_fixtures.dataset_all_ok()), "MKT-7")["_rows"][0]
    assert set(sections.MKT7_CELLS) <= set(row)
    assert mkt_logic.empty_source_text(["market_indicator"]) == sections.MKT6_EMPTY_LINE


# ───────────────────────── BL-0371：MKT-0（示範與正式模式皆同，logic 本身不寫） ─────────────────────────


@pytest.mark.parametrize("sign", [1, -1])
def test_BL0371_MKT0三塊皆ok_燈上不寫文案_燈色照舊灰(sign):
    light = mkt_logic.find_block(_mkt(mkt_fixtures.dataset_all_ok(sign)), "MKT-0")
    assert light["text"] == "" and light["_tone"] == "灰" and light["buttons"] == []


@pytest.mark.parametrize("name", sorted(n for n in vars(mkt_fixtures) if n.startswith("dataset_")))
def test_BL0371_MKT0全固定資料集_燈不寫資料齊(name):
    light = mkt_logic.find_block(_mkt(getattr(mkt_fixtures, name)()), "MKT-0")
    assert "資料齊" not in light["text"] and "正常" not in light["text"], (name, light["text"])


# ───────────────────────── BL-0373：MKT-7 ─────────────────────────


def _failed_keys(ds):
    return list((ds.get("errors") or {}).keys())


def _fetch_failed_no_rows():
    """`vol_index` 取數失敗、而且一筆觀測也沒有（正式模式取數失敗時資料層不交任何列）；`MKT-2` 兩鍵照舊缺來源（沒有失敗紀錄）。"""
    ds = mkt_fixtures.dataset_mkt1_fetch_failed()
    return dict(ds, rows=[r for r in ds["rows"] if r["indicator_key"] != "vol_index"])


def test_BL0373_MKT7取數失敗的鍵_改掛取數失敗_四格禁止號_不掛資料未備():
    ds = _fetch_failed_no_rows()
    failed = _failed_keys(ds)
    assert failed
    model = _mkt(ds)
    rows_before = {r["indicator_key"]: copy.deepcopy(r) for r in mkt_logic.find_block(model, "MKT-7")["_rows"]}
    changed = sections.mark_mkt7_fetch_failed(model, failed)
    rows = {r["indicator_key"]: r for r in mkt_logic.find_block(model, "MKT-7")["_rows"]}
    hit = [k for k in failed if k in rows and not mkt_logic.rows_for_key(ds, k)]
    assert hit and changed == 2 * len(hit)   # MKT-7 一列 ＋ MKT-5 一項
    for key in hit:
        row = rows[key]
        assert [b["text"] for b in row["badges"]] == ["取數失敗"]
        assert all(row[c] == "⛔" for c in sections.MKT7_CELLS)
        assert "_missing_cells" not in row
    for key, row in rows.items():
        if key not in hit:
            assert row == rows_before[key], key
    # 沒有失敗紀錄、只是缺來源的鍵（MKT-2 兩鍵）照舊資料未備
    missing = [r for r in rows.values() if r.get("_missing_cells")]
    assert missing and all([b["text"] for b in r["badges"]] == ["資料未備"] for r in missing)


def test_BL0373_MKT7取數失敗但沿用既有列的鍵_照舊不動():
    ds = mkt_fixtures.dataset_mkt1_fetch_failed()
    assert mkt_logic.rows_for_key(ds, "vol_index")
    model = _mkt(ds)
    before = copy.deepcopy(model)
    assert sections.mark_mkt7_fetch_failed(model, _failed_keys(ds)) == 0
    assert model == before


def test_BL0373_MKT7真正資料未備的鍵_照舊資料未備():
    """沒有失敗紀錄、只是沒有觀測的鍵：照舊 `資料未備`（正式模式之後由 `symbols` 畫 ◇）。"""
    ds = mkt_fixtures.dataset_mkt1_one_key_missing()
    model = _mkt(ds)
    before = copy.deepcopy(model)
    assert sections.mark_mkt7_fetch_failed(model, _failed_keys(ds)) == 0
    assert model == before
    missing = [r for r in mkt_logic.find_block(model, "MKT-7")["_rows"] if r.get("_missing_cells")]
    assert missing and all(b["text"] == "資料未備" for r in missing for b in r["badges"])


def test_BL0373_MKT7冪等():
    ds = _fetch_failed_no_rows()
    model = _mkt(ds)
    sections.mark_mkt7_fetch_failed(model, _failed_keys(ds))
    once = copy.deepcopy(model)
    assert sections.mark_mkt7_fetch_failed(model, _failed_keys(ds)) == 0
    assert model == once


def test_BL0373_MKT6每一個鍵都是取數失敗而表上沒有觀測_表尾寫取數失敗():
    ds = dict(mkt_fixtures.dataset_mkt1_fetch_failed(), rows=[])
    ds["errors"] = {k: "HTTPSConnectionPool(host='example.invalid'): Max retries exceeded" for k in mkt_logic.all_keys(ds)}
    model = _mkt(ds)
    assert sections.MKT6_EMPTY_LINE in mkt_logic.find_block(model, "MKT-6")["detail_lines"]
    sections.mark_mkt7_fetch_failed(model, ds["errors"].keys())
    assert sections.mark_mkt6_fetch_failed(model) == 1
    lines = mkt_logic.find_block(model, "MKT-6")["detail_lines"]
    assert sections.LINE_FETCH_FAILED in lines and sections.MKT6_EMPTY_LINE not in lines


def test_BL0373_MKT6成因混合_資料未備那一句照留_另加一行取數失敗列出失敗鍵():
    ds = dict(mkt_fixtures.dataset_mkt1_fetch_failed(), rows=[])   # 只有 vol_index 失敗，其餘鍵沒有失敗紀錄
    model = _mkt(ds)
    sections.mark_mkt7_fetch_failed(model, ds["errors"].keys())
    assert sections.mark_mkt6_fetch_failed(model) == 1
    lines = mkt_logic.find_block(model, "MKT-6")["detail_lines"]
    i = lines.index(sections.MKT6_EMPTY_LINE)
    assert lines[i + 1] == f"{sections.LINE_FETCH_FAILED}：vol_index"
    assert sum(line.startswith(sections.LINE_FETCH_FAILED) for line in lines) == 1


def test_BL0373_MKT6沒有任何取數失敗_不動():
    ds = dict(mkt_fixtures.dataset_all_ok(), rows=[], errors={})
    model = _mkt(ds)
    before = copy.deepcopy(model)
    sections.mark_mkt7_fetch_failed(model, ())
    assert sections.mark_mkt6_fetch_failed(model) == 0 and model == before


def test_BL0373_MKT5取數失敗的鍵改掛取數失敗_資料未備的鍵照舊():
    ds = _fetch_failed_no_rows()
    model = _mkt(ds)
    sections.mark_mkt7_fetch_failed(model, _failed_keys(ds))
    items = {i["name"]: i for i in mkt_logic.find_block(model, "MKT-5")["_items"]}
    assert [b["text"] for b in items["vol_index"]["badges"]] == ["取數失敗"]
    missing = [n for n, i in items.items() if n not in _failed_keys(ds) and i["badges"]]
    assert missing and all([b["text"] for b in items[n]["badges"]] == ["資料未備"] for n in missing)


# ───────────────────────── BL-0373：持倉體檢（`strict_fetch_failure` 只有正式模式會開） ─────────────────────────

from ui_v2.hld import fixtures as hld_fixtures  # noqa: E402
from ui_v2.hld import logic as hld_logic  # noqa: E402


def _hld(name, *, strict, mutate=None):
    args = copy.deepcopy(hld_fixtures.scenario(name))
    if mutate:
        mutate(args["dataset"])
    return hld_logic.build_page_model(**args, demo_hint=False, strict_fetch_failure=strict)


def _no_series(ds):
    ds["nav"], ds["dividend"] = [], []
    ds["errors"] = {"nav": "ConnectionError: 淨值讀取逾時（測試用原文）",
                    "dividend": "ConnectionError: 淨值讀取逾時（測試用原文）"}


def test_BL0373_HLD6成因混合_資料未備那一句照留_另寫取數失敗原文():
    """44 之九其二第 5 條統一規則：淨值整張失敗、配息沒有失敗紀錄 ⇒ 成因混合。"""
    def mixed(ds):
        ds["nav"], ds["dividend"] = [], []
        ds["errors"] = {"nav": "ConnectionError: 淨值讀取逾時（測試用原文）"}
    block = hld_logic.find_block(_hld("full", strict=True, mutate=mixed), "HLD-6")
    msg = hld_logic.fetch_failed_text("ConnectionError: 淨值讀取逾時（測試用原文）")
    assert block["_state"] == hld_logic.STATE_MISSING
    assert hld_logic.empty_source_text(["nav", "dividend"]) in block["detail_lines"] and msg in block["detail_lines"]
    demo = hld_logic.find_block(_hld("full", strict=False, mutate=mixed), "HLD-6")
    assert msg not in demo["detail_lines"]


def test_BL0373_HLD7成因混合_資料未備那一句照留_另寫取數失敗原文():
    """配息取數失敗、區間未設（淨值類的值是不適用）⇒ 四塊沒有一塊出數，成因混合。"""
    def no_window(ds):
        ds["user_setting"] = [r for r in ds.get("user_setting", []) if not r["setting_key"].startswith("hld_window")]
    block = hld_logic.find_block(_hld("fetchfail", strict=True, mutate=no_window), "HLD-7")
    assert block["_state"] == hld_logic.STATE_MISSING
    assert hld_logic.empty_source_text(["HLD-1", "HLD-2", "HLD-3", "HLD-8"]) in block["detail_lines"]
    assert any(line.startswith("⛔ 取數失敗：") for line in block["detail_lines"])
    demo = hld_logic.find_block(_hld("fetchfail", strict=False, mutate=no_window), "HLD-7")
    assert not any(line.startswith("⛔ 取數失敗：") for line in demo["detail_lines"])


def test_BL0373_HLD6兩張表都沒有列而成因全是取數失敗_正式模式取數失敗_示範照舊():
    strict = hld_logic.find_block(_hld("full", strict=True, mutate=_no_series), "HLD-6")
    demo = hld_logic.find_block(_hld("full", strict=False, mutate=_no_series), "HLD-6")
    msg = hld_logic.fetch_failed_text("ConnectionError: 淨值讀取逾時（測試用原文）")
    assert (strict["_state"], strict["summary_text"]) == (hld_logic.STATE_ERROR, msg)
    assert msg in strict["detail_lines"] and not any("資料未備" in line for line in strict["detail_lines"])
    assert demo["_state"] == hld_logic.STATE_MISSING


def test_BL0373_HLD6兩張表都沒有列而沒有任何失敗_照舊資料未備():
    def empty(ds):
        ds["nav"], ds["dividend"] = [], []
    assert hld_logic.find_block(_hld("full", strict=True, mutate=empty), "HLD-6")["_state"] == hld_logic.STATE_MISSING


def test_BL0373_HLD7四塊沒有一塊出數而成因全是取數失敗_正式模式取數失敗_示範照舊():
    strict = hld_logic.find_block(_hld("twofail", strict=True), "HLD-7")
    demo = hld_logic.find_block(_hld("twofail", strict=False), "HLD-7")
    assert strict["_state"] == hld_logic.STATE_ERROR and strict["summary_text"].startswith("⛔ 取數失敗：")
    assert strict["_rows"] == demo["_rows"]   # 輸入欄照列，列一格不動
    assert demo["_state"] == hld_logic.STATE_MISSING


def test_BL0373_HLD2持倉表讀不到_正式模式取數失敗_示範照舊():
    def holding_fail(ds):
        ds["holding"] = []
        ds["errors"] = {"holding": "ConnectionError: 持倉讀取逾時（測試用原文）"}
    strict = hld_logic.find_block(_hld("full", strict=True, mutate=holding_fail), "HLD-2")
    demo = hld_logic.find_block(_hld("full", strict=False, mutate=holding_fail), "HLD-2")
    assert strict["_state"] == hld_logic.STATE_ERROR and demo["_state"] == hld_logic.STATE_MISSING


def test_BL0373_HLD5淨值取數失敗那一檔_折線區寫取數失敗_示範照舊():
    def nav_fail(ds):
        ds["nav"] = []
        ds["errors"] = {"nav": "ConnectionError: 淨值讀取逾時（測試用原文）"}
    msg = hld_logic.fetch_failed_text("ConnectionError: 淨值讀取逾時（測試用原文）")
    strict = hld_logic.find_block(_hld("full", strict=True, mutate=nav_fail), "HLD-5")["_items"]
    demo = hld_logic.find_block(_hld("full", strict=False, mutate=nav_fail), "HLD-5")["_items"]
    assert strict and all(item["nav_plot_text"] == msg for item in strict)
    assert all("資料未備" in item["nav_plot_text"] for item in demo)


def test_BL0373_HLD5保單表讀不到_保單與發行單位兩格是取數失敗_不記資料未備():
    def policy_fail(ds):
        ds["policy"] = []
        ds["errors"] = {"policy": "ConnectionError: 保單讀取逾時（測試用原文）"}
    strict = hld_logic.find_block(_hld("full", strict=True, mutate=policy_fail), "HLD-5")["_items"]
    demo = hld_logic.find_block(_hld("full", strict=False, mutate=policy_fail), "HLD-5")["_items"]
    undirect = [i for i in strict if dict(i["_fields"])["發行單位"] != "—"]
    assert undirect
    for item in undirect:
        assert dict(item["_fields"])["保單"] == "⛔" and dict(item["_fields"])["發行單位"] == "⛔"
        assert item["_missing_fields"] == ()
    assert any(i["_missing_fields"] for i in demo)


def test_BL0373_HLD5保單表讀得到只是沒這一列_照舊資料未備():
    def no_policy_row(ds):
        ds["policy"] = []
    items = hld_logic.find_block(_hld("full", strict=True, mutate=no_policy_row), "HLD-5")["_items"]
    assert any(i["_missing_fields"] for i in items)


def test_BL0373_持倉體檢示範模式全部情境_開關關著時與動手前逐位元組相同():
    """示範模式不開 `strict_fetch_failure`；同一組情境開與不開，只有上面三塊可能不同（其餘塊逐字相同）。"""
    for name in hld_fixtures.ALL_SCENARIO_NAMES:
        on, off = _hld(name, strict=True), _hld(name, strict=False)
        for a, b in zip(on["blocks"], off["blocks"]):
            if a["code"] not in ("HLD-2", "HLD-5", "HLD-6", "HLD-7"):
                assert a == b, (name, a["code"])


# ───────────────────────── BL-0373：SET-1（`kind_time_from_log` 只有正式模式會給） ─────────────────────────


def _set_ds(logs):
    ds = set_fixtures.scenario("ok")
    ds = dict(ds, kind_time_from_log={"nav": "淨值"}, nav=[], fetch_log=logs)
    return ds


def _log(started, outcome, rows=None, message=None, tier="淨值", log_id=None):
    return {"log_id": log_id or started, "source_tier": tier, "started_at": started, "finished_at": started,
            "outcome": outcome, "row_count": rows, "message": message}


def _nav_row(ds):
    return {r["_kind_label"]: r for r in set_logic.find_block(set_logic.build_page_model(ds), "SET-1")["_rows"]}["淨值"]


def test_BL0373_SET1只有失敗紀錄_取數失敗_不是資料未備_缺值不補0():
    ds = _set_ds([_log("2026-09-25T02:00:00Z", "failed", message="HTTP 503 upstream")])
    row = _nav_row(ds)
    assert row["_failed"] is True and row["at_text"] == "⛔ 取數失敗：HTTP 503 upstream"
    assert [b["text"] for b in row["badges"]] == ["取數失敗"]
    assert row["days_text"] == "⬜" and row["compare_text"] == "⬜" and row["_days"] is None
    assert "_missing_cells" not in row and "0" not in (row["days_text"], row["compare_text"])
    set1 = set_logic.find_block(set_logic.build_page_model(ds), "SET-1")
    assert set1["_tone"] == "紅" and set1["_overdue"] == 0


def test_BL0373_SET1失敗紀錄沒有訊息_只寫取數失敗():
    row = _nav_row(_set_ds([_log("2026-09-25T02:00:00Z", "failed", message=None)]))
    assert row["_failed"] is True and row["at_text"] == "⛔ 取數失敗"


@pytest.mark.parametrize("logs", [
    [],                                                                            # 沒有紀錄
    [_log("2026-09-25T02:00:00Z", "ok", rows=0)],                                  # 只有取數回空
    [_log("2026-09-25T02:00:00Z", "failed", message="x"), _log("2026-09-25T05:00:00Z", "ok", rows=0)],  # 失敗後回空
    [_log("2026-09-25T02:00:00Z", "failed", message="x", tier="市場指標")],          # 失敗在別的層級
])
def test_BL0373_SET1沒有紀錄或最近一次是回空_照舊資料未備(logs):
    if not logs:
        # 該層級一筆紀錄也沒有（另放一筆別層 ok，免得整張 fetch_log 空）
        logs = [_log("2026-09-25T02:00:00Z", "ok", rows=3, tier="市場指標")]
    row = _nav_row(_set_ds(logs))
    assert row["_failed"] is False and row["at_text"] == "⬜"
    assert [b["text"] for b in row["badges"]] == ["資料未備"]
    assert row["_missing_cells"] == ("at_text", "days_text", "compare_text")


def test_BL0373_SET1有過取回列的成功_時間照舊取成功那一次():
    ds = _set_ds([_log("2026-09-25T02:00:00Z", "ok", rows=12), _log("2026-09-25T05:00:00Z", "failed", message="x")])
    row = _nav_row(ds)
    assert row["_failed"] is False and not row["at_text"].startswith("⛔") and row["badges"] == []


def test_BL0373_latest_failed_record_層級不在四個之內就炸():
    with pytest.raises(ValueError):
        set_logic.latest_failed_record([], "不存在的層級")


# ───────────────────────── 示範模式：模型逐位元組不變 ─────────────────────────


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


def test_示範模式SET與MKT模型_只差BL0371那兩句_其餘逐位元組不變():
    """本批只改正式模式。示範模式模型（設定與診斷 17 情境 × 存檔失敗開關、市場總覽各固定資料集）取 md5，
    基準值於 2d98692a（本批動手前）量得；`kind_time_from_log` 只有正式模式會給，示範模式走不到 BL-0373 那一支。"""
    out = []
    for name in set_fixtures.ALL_SCENARIO_NAMES:
        for sf in (False, True):
            out.append(["set", name, sf, set_logic.build_page_model(set_fixtures.scenario_with(name, save_failed=sf))])
    for name in sorted(n for n in vars(mkt_fixtures) if n.startswith("dataset_")):
        out.append(["mkt", name, _mkt(getattr(mkt_fixtures, name)())])
    # 模型裡有 `set`（順序隨雜湊種子變），序列化前排序，md5 才可重現。
    default = lambda o: sorted(o, key=repr) if isinstance(o, (set, frozenset)) else repr(o)  # noqa: E731
    # 客戶 2026-10-18 裁示 BL-0371（`DEC-2026-10-18-01`）不限正式模式：示範模式 `MKT-0` 三塊皆 ok、`SET-0` 兩個計數皆為零時
    # 燈上不寫文案。證明「示範模型只差這兩句」：把那兩句還原成舊字面，md5 必須回到動手前（2d98692a）的基準值。
    restored = copy.deepcopy(out)
    changed = 0
    for entry in restored:
        model = entry[-1]
        if entry[0] == "set":
            light = set_logic.find_block(model, "SET-0")
            if light["_state"] == "齊":
                assert light["text"] == ""
                light["text"] = "資料齊、來源皆可達"
                changed += 1
        else:
            light = mkt_logic.find_block(model, "MKT-0")
            if all(mkt_logic.find_block(model, c)["_state"] == "ok" for c in ("MKT-1", "MKT-2", "MKT-3")):
                assert light["text"] == ""
                light["text"] = "三張卡的資料齊"
                changed += 1
    assert changed > 0
    # 2026-10-27 BL-0478：頁名「設定與診斷」→「⚙️ 設定」、「市場總覽」→「🌍 市場與趨勢」（每個模型頂層 `title` 一格）；還原後回到同一個基準值。
    assert _restore_old_page_title([e for e in restored if e[0] == "set"], "⚙️ 設定", "設定與診斷") == 34
    mkt_entries = [e for e in restored if e[0] == "mkt"]
    assert mkt_entries and _restore_old_page_title(mkt_entries, "🌍 市場與趨勢", "市場總覽") == len(mkt_entries)   # 每個模型恰一格
    digest = hashlib.md5(json.dumps(_without_batch3b_marks(restored), ensure_ascii=False, sort_keys=True,
                                    default=default).encode()).hexdigest()
    assert digest == "e44fc6ade09b98d81979ff1ace6174c2", digest
