"""回歸網 — v19.322:基金組合健診代號去重 SSOT(`_dedup_upper`)。

user 2026-07-05「配息事件（多檔合併）有重複」根因:同基金被多張保單持有 →
`portfolio_funds` 同 code 多筆 → 帶入健診後逐檔各算一次 → 持有 meta / 配息事件 /
比較圖三表全部重複列。修法:單一 SSOT helper `_dedup_upper` order-preserving 去重,
接在代號清單唯一化的兩個入口(組合帶入 + 手動處理 chokepoint)。
"""
from __future__ import annotations

from ui.tab_fund_grp_health import _dedup_rows_by_code, _dedup_upper


def test_dedup_removes_duplicates_order_preserving():
    """同 code 多筆 → 只留第一次出現,順序不變(這就是 user 看到的重複列根因)。"""
    assert _dedup_upper(["TLZF9", "JFZN3", "TLZF9", "ACDD01", "JFZN3"]) == \
        ["TLZF9", "JFZN3", "ACDD01"]


def test_dedup_uppercases_and_strips():
    """大小寫 / 前後空白正規化後才比對(避免 'tlzf9 ' 與 'TLZF9' 被當兩檔)。"""
    assert _dedup_upper([" tlzf9 ", "TLZF9", "Jfzn3"]) == ["TLZF9", "JFZN3"]


def test_dedup_drops_empty_and_whitespace():
    """空字串 / 純空白列丟棄(§1 不把空碼當一檔去抓)。"""
    assert _dedup_upper(["", "  ", "TLZF9", "\t"]) == ["TLZF9"]


def test_dedup_accepts_generator_and_dict_codes():
    """接受 generator(組合帶入用 f.get('code') for f in ...)。"""
    pf = [{"code": "TLZF9"}, {"code": "tlzf9"}, {"code": "JFZN3"}, {"code": ""}]
    assert _dedup_upper(f.get("code", "") for f in pf) == ["TLZF9", "JFZN3"]


def test_dedup_empty_input():
    assert _dedup_upper([]) == []


def test_dedup_rows_by_code_keeps_first_order_preserving():
    """顯示層 chokepoint:同 code 多筆只留第一筆(這是 user 螢幕上重複列的直接修點)。"""
    rows = [
        {"code": "TLZF9", "ok": True, "v": 1},
        {"code": "JFZN3", "ok": True, "v": 2},
        {"code": "tlzf9", "ok": True, "v": 99},  # 同檔(大小寫)→ 應被去掉,保留 v=1
        {"code": "ACDD01", "ok": True, "v": 3},
    ]
    out = _dedup_rows_by_code(rows)
    assert [r["code"] for r in out] == ["TLZF9", "JFZN3", "ACDD01"]
    assert out[0]["v"] == 1  # 留第一筆、非後來的 v=99


def test_dedup_rows_keeps_empty_code_rows():
    """空 code 的 row 視為各自唯一 → 不丟、不去重(避免誤刪合法列)。"""
    rows = [{"code": "", "v": 1}, {"code": "", "v": 2}, {"code": "TLZF9", "v": 3}]
    out = _dedup_rows_by_code(rows)
    assert len(out) == 3
