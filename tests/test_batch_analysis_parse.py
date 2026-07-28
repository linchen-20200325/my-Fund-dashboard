"""tests/test_batch_analysis_parse.py — 批次分頁代號解析器測試。

_parse_codes 是批次 UI 唯一非平凡邏輯,§6 對其最易錯輸入上鎖:
表頭列 / 多欄 CSV / 大小寫 / 重複 / 空白與雜訊 token / 全空輸入。
"""
from __future__ import annotations

from ui.tab_batch_analysis import _is_fail, _parse_codes, _rows_compatible


def test_rows_compatible_new_vs_old_schema():
    """v19.413:舊 flat-schema 存檔(有 status 無 狀態)須判為不相容 → 讀回時忽略。"""
    assert _rows_compatible({"A": {"狀態": "✅ 成功", "code": "A"}})       # 新 schema
    assert not _rows_compatible({"A": {"status": "ok", "code": "A"}})       # 舊 flat
    assert not _rows_compatible({})                                          # 空
    assert not _rows_compatible({"A": {"狀態": "✅"}, "B": {"status": "ok"}})  # 混 → 不相容


def test_is_fail():
    assert _is_fail({"狀態": "❌ 抓取失敗"}) and _is_fail({"狀態": "⚠️ 無效代號"})
    assert not _is_fail({"狀態": "✅ 成功"}) and not _is_fail({})


def test_empty_and_none():
    assert _parse_codes("") == []
    assert _parse_codes(None) == []
    assert _parse_codes("   \n\n  ") == []


def test_dedup_upper_and_order():
    codes = _parse_codes("accp138\nB07\nACCP138\nb07")
    assert codes == ["ACCP138", "B07"]        # 去重 + 大寫 + 保留首見順序


def test_multi_column_csv_takes_first_field():
    raw = "代號,名稱,幣別\nACCP138,美元高收益,USD\n0050,元大台灣50,TWD"
    assert _parse_codes(raw) == ["ACCP138", "0050"]   # 只取第一欄 + 過濾表頭


def test_header_tokens_filtered():
    assert _parse_codes("CODE\nSYMBOL\n基金代號\nACCP138") == ["ACCP138"]


def test_junk_and_out_of_range_dropped():
    # 純標點 / 過短 / 過長 → 丟;合法碼 → 留
    raw = "!!!\nab\n" + "X" * 25 + "\nACCP138\n0050"
    assert _parse_codes(raw) == ["ACCP138", "0050"]


def test_commas_semicolons_tabs_and_newlines():
    assert _parse_codes("ACCP138\tfoo") == ["ACCP138"]
    assert _parse_codes("ACCP138;bar") == ["ACCP138"]
    # 多行混逗號
    assert _parse_codes("A123, name\nB456; other") == ["A123", "B456"]
