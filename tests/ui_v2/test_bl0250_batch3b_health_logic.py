# -*- coding: utf-8 -*-
"""BL-0250 批次 3-B：各頁資料狀態的原因項目、件數（線框 1.1）、主要原因（線框 1.2 新設計 A）、總表排序與明細列（線框 6.3；
總管 2026-10-19 裁定 (a)(b)(c)）—— `ui_v2/page_health.py` 純函式守衛（fast lane）。

本批純函式已落地、尚未接線（四頁交出原因項目那一步停下回報，見 44 第七節第三小節之十三其五）；本檔只用手寫的項目驗算法。
"""

from __future__ import annotations

import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
for _p in (_HERE, _HERE.parent, _HERE.parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ui_v2 import page_health as PH  # noqa: E402

A = PH.affected
I = PH.make_item


def _key_unconf():   # 資料來源的金鑰：兩張核心卡的主值讀不到
    return I(PH.KIND_UNCONFIGURED, "資料來源的金鑰", [
        A("風險情緒卡", "高收益信用利差", core=True, unreadable=True, data_class="市場指標"),
        A("資金與匯率卡", "政策利率", core=True, unreadable=True, data_class="市場指標"),
    ], lamp=True, order=1)


def _sheet_unconf():  # 設定試算表：只讓比較值不適用
    return I(PH.KIND_UNCONFIGURED, "設定試算表", [
        A("風險情緒卡", "比較值", core=True, unreadable=False), A("觀察窗與比較基準輸入", "")], order=2)


def _fetch(key="資料", cards=("風險情緒卡",), order=3, **kw):
    return I(PH.KIND_FETCH, key, [A(c, "波動度指數", core=True, unreadable=True) for c in cards], order=order, **kw)


def _missing(key="市場指標", cards=("景氣位置卡",), order=4):
    return I(PH.KIND_MISSING, key, [A(c, "領先指標", core=True, unreadable=True) for c in cards], order=order)


def _stale(card="績效與風險卡"):
    return I(PH.KIND_STALE, "任意", [A(card, "AAAA", core=True)], order=5)


# ═══════════════════════ 件數（線框 1.1） ═══════════════════════


def test_線框12情境_件數_尚未設定2_取數失敗1_資料未備1():
    items = [_key_unconf(), _sheet_unconf(), _fetch(), _missing()]
    assert PH.counts(items) == {"尚未設定": 2, "取數失敗": 1, "資料未備": 1}
    assert PH.count_text(PH.counts(items)) == "尚未設定 2 項　⛔ 取數失敗 1 項　◇ 資料未備 1 項"


def test_同一個原因影響多張卡只算一項_受影響清單取聯集():
    a = _missing(cards=("景氣位置卡",))
    b = _missing(cards=("資金與匯率卡", "景氣位置卡"))
    merged = PH.merge_items([a, b])
    assert len(merged) == 1 and PH.counts([a, b]) == {"資料未備": 1}
    assert [e["card"] for e in merged[0]["affected"]] == ["景氣位置卡", "資金與匯率卡"]


def test_不同資料類各算一項():
    assert PH.counts([_missing("淨值"), _missing("配息"), _missing("淨值")]) == {"資料未備": 2}


def test_尚未設定與取數失敗分開數_同一個鍵也不合併():
    items = [I(PH.KIND_UNCONFIGURED, "設定試算表", [A("卡", core=True, unreadable=True)]),
             I(PH.KIND_FETCH, "設定試算表", [A("卡", core=True, unreadable=True)])]
    assert PH.counts(items) == {"尚未設定": 1, "取數失敗": 1}


def test_不是最新整頁只算一項():
    a = I(PH.KIND_STALE, "淨值", [A("績效與風險卡", "AAAA", core=True)])
    b = I(PH.KIND_STALE, "市場指標", [A("配息與本金卡", "BBBB", core=True)])
    assert PH.counts([a, b]) == {"不是最新": 1} and a["key"] == b["key"] == PH.STALE_KEY


def test_尚未設定不加符號_其餘帶各自符號_沒有任何一項回None():
    assert PH.count_text({"尚未設定": 1, "不是最新": 1}) == "尚未設定 1 項　◷ 不是最新 1 項"
    assert PH.count_text({}) is None


def test_項目沒有鍵或種類不認得_當場炸_不猜():
    with pytest.raises(ValueError):
        I(PH.KIND_MISSING, "", [])
    with pytest.raises(ValueError):
        I("系統錯誤", "淨值", [])
    with pytest.raises(ValueError):
        I(PH.KIND_MISSING, "淨值", [], retreat={"day": "2026-09-18", "codes": ["AAAA"]})


# ═══════════════════════ 主要原因（新設計 A 的六個順位與「都沒有」） ═══════════════════════


def test_順位1_整頁載不出來_其他項目不看():
    assert PH.main_reason([_key_unconf()], page_failure="淨值") == "⛔ 本頁暫時無法判定：淨值取數失敗"


def test_順位2_尚未設定而且有主值讀不到_排在取數失敗前():
    items = [_fetch(cards=("風險情緒卡", "景氣位置卡", "資金與匯率卡")), _key_unconf(), _sheet_unconf(), _missing()]
    assert PH.main_reason(items) == "⛔ 主要原因：資料來源的金鑰尚未設定（2 張卡有值讀不到）"
    assert PH.other_counts(items) == {"尚未設定": 1, "取數失敗": 1, "資料未備": 1}   # 線框 1.2：另有 3 項


def test_順位3_取數失敗():
    items = [_fetch(), _missing(), _sheet_unconf()]
    assert PH.main_reason(items) == "⛔ 主要原因：資料取數失敗（1 張卡有值讀不到）"
    assert PH.other_counts(items) == {"尚未設定": 1, "資料未備": 1}


def test_順位3_改用預存淨值_日期與代碼寫在那一句():
    item = I(PH.KIND_FETCH, "淨值", [A("績效與風險卡", "AAAA", core=True, unreadable=True)],
             retreat={"day": "2026-09-18", "codes": ["AAAA"]})
    items = [item, _missing("淨值", cards=("績效與風險卡",))]
    assert PH.main_reason(items) == "⛔ 主要原因：淨值取數失敗，改用 2026-09-18 的預存淨值（AAAA）"
    assert PH.other_counts(items) == {"資料未備": 1}


def test_順位4_資料未備():
    assert PH.main_reason([_missing(), _stale()]) == "◇ 主要原因：市場指標資料未備（1 張卡有值讀不到）"


def test_順位5_不是最新():
    assert PH.main_reason([_stale(), _sheet_unconf()]) == "◷ 主要原因：部分只顯示最後有效資料"
    assert PH.other_counts([_stale(), _sheet_unconf()]) == {"尚未設定": 1}


def test_順位6_只有只影響比較值的尚未設定_不加符號_另有為空():
    assert PH.main_reason([_sheet_unconf()]) == "尚未設定：設定試算表（只影響比較值）"
    assert PH.other_counts([_sheet_unconf()]) == {}


def test_順位6_有其他問題時不當主要原因():
    assert PH.main_reason([_sheet_unconf(), _missing()]).startswith("◇ 主要原因：")


def test_都沒有_不寫主要原因():
    assert PH.main_reason([]) is None and PH.other_counts([]) == {}


def test_沒有核心卡讀不到時_不寫幾張卡():
    item = I(PH.KIND_MISSING, "淨值", [A("單檔展開", "AAAA")])
    assert PH.main_reason([item]) == "◇ 主要原因：淨值資料未備"


def test_同順位比_a_核心卡多的贏_b_影響燈的贏_c_順序小的贏():
    few = _missing("配息", cards=("配息與本金卡",), order=1)
    many = _missing("淨值", cards=("績效與風險卡", "配息與本金卡"), order=2)
    assert PH.pick_main([few, many])["key"] == "淨值"                                  # (a)
    x = I(PH.KIND_FETCH, "淨值", [A("卡一", core=True, unreadable=True)], order=1)
    y = I(PH.KIND_FETCH, "配息", [A("卡二", core=True, unreadable=True)], lamp=True, order=2)
    assert PH.pick_main([x, y])["key"] == "配息"                                       # (b)
    z = I(PH.KIND_FETCH, "持倉", [A("卡三", core=True, unreadable=True)], order=0)
    assert PH.pick_main([x, z])["key"] == "持倉"                                       # (c)


# ═══════════════════════ 總表第一層：排序、沒開過的頁、記錄時間 ═══════════════════════

_NOW = datetime(2026, 10, 19, 23, 5, tzinfo=timezone.utc)   # 台北 10-20 07:05


def _store(**pages):
    state: dict = {}
    for slug, (items, as_of, failure) in pages.items():
        PH.record(state, slug, items, as_of=as_of, now=_NOW, page_failure=failure)
    return state[PH.STATE_KEY]


def test_排序_尚未設定或取數失敗_只有資料未備_只有不是最新_沒有異常_沒開過():
    store = _store(alo=([], "2026-09-23", None), hld=([_stale()], "2026-09-18", None),
                   exp=([_missing("淨值")], "2026-10-13", None))
    assert [r["slug"] for r in PH.summary_rows(store)] == ["exp", "hld", "alo", "mkt"]
    store = _store(alo=([_sheet_unconf()], "2026-09-23", None), mkt=([_missing()], "—", None))
    assert [r["slug"] for r in PH.summary_rows(store)] == ["alo", "mkt", "hld", "exp"]


def test_同級依固定頁序():
    store = _store(alo=([_fetch()], None, None), mkt=([_key_unconf()], None, None))
    assert [r["slug"] for r in PH.summary_rows(store)][:2] == ["mkt", "alo"]


def test_沒開過的頁_寫本次尚未開過這一頁_不給符號_不寫正常():
    rows = PH.summary_rows({})
    assert [r["main"] for r in rows] == [PH.TEXT_NOT_OPENED] * 4
    assert all(r["status"] == "—" and r["at"] == "—" for r in rows)
    assert not any(s in r["status"] + r["main"] for r in rows for s in ("⛔", "◇", "◷", "⬜", "正常"))


def test_沒有異常的頁_狀態寫資料截至_主要原因一槓_不寫正常():
    (row,) = [r for r in PH.summary_rows(_store(alo=([], "2026-09-23", None))) if r["slug"] == "alo"]
    assert row["status"] == "資料截至 2026-09-23" and row["main"] == "—" and "正常" not in str(row)


def test_總表件數與頁首另有對得上_總表含主要原因那一項():
    items = [_key_unconf(), _sheet_unconf(), _fetch(), _missing()]
    (row,) = [r for r in PH.summary_rows(_store(mkt=(items, None, None))) if r["slug"] == "mkt"]
    assert row["status"] == "尚未設定 2 項　⛔ 取數失敗 1 項　◇ 資料未備 1 項"
    assert row["main"] == "⛔ 主要原因：資料來源的金鑰尚未設定（2 張卡有值讀不到）"
    total = sum(PH.counts(items).values())
    assert sum(PH.other_counts(items).values()) == total - 1


def test_記錄時間_台北時分_整格覆寫():
    state: dict = {}
    PH.record(state, "hld", [_stale()], as_of="2026-09-18", now=_NOW)
    PH.record(state, "hld", [], as_of="2026-09-18", now=_NOW + timedelta(minutes=10))
    entry = state[PH.STATE_KEY]["hld"]
    assert entry["items"] == [] and PH.recorded_time_text(entry["at"]) == "07:15"
    with pytest.raises(ValueError):
        PH.record(state, "hld", [], as_of=None, now=datetime(2026, 10, 19, 23, 5))   # 沒有時區：不猜
    with pytest.raises(ValueError):
        PH.record(state, "set", [], as_of=None, now=_NOW)


def test_整頁載不出來_總表算一項取數失敗_主要原因順位1():
    (row,) = [r for r in PH.summary_rows(_store(hld=([], None, "淨值"))) if r["slug"] == "hld"]
    assert row["status"] == "⛔ 取數失敗 1 項" and row["main"] == "⛔ 本頁暫時無法判定：淨值取數失敗"


# ═══════════════════════ 明細表（總管裁定 (b)） ═══════════════════════


def test_明細一列一項乘一個受影響項目_沒有異常的也列狀態一槓():
    items = PH.merge_items([_key_unconf(), _fetch()])
    entry = {"items": items}
    normal = [A("景氣位置卡", "領先指標", data_class="市場指標", obs="2026-08-31", fetched="2026-09-21 09:00",
                delay=21, tier="T1"),
              A("風險情緒卡", "高收益信用利差", data_class="市場指標")]   # 已在異常列裡的不重列
    rows = PH.detail_rows(entry, normal)
    assert rows == [
        ("市場指標", "風險情緒卡　高收益信用利差", "⛔ 尚未設定：資料來源的金鑰", "—", "—", "—", "—"),
        ("市場指標", "資金與匯率卡　政策利率", "⛔ 尚未設定：資料來源的金鑰", "—", "—", "—", "—"),
        ("—", "風險情緒卡　波動度指數", "⛔ 取數失敗", "—", "—", "—", "—"),
        ("市場指標", "景氣位置卡　領先指標", "—", "2026-08-31", "2026-09-21 09:00", "21", "T1"),
    ]
    assert len(PH.DETAIL_LABELS) == len(rows[0])
    assert not any("正常" in cell for row in rows for cell in row)
    assert PH.detail_rows(None) == []
