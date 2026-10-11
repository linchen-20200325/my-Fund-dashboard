# -*- coding: utf-8 -*-
"""批次存檔讀回時中和名稱推定時代的買賣句（客戶 2026-10-11 裁示的後續）。

問題：舊版 `mk_fund_signal` 依基金名稱猜核心／衛星並輸出買賣句，批次大表把它存進
`data_cache/batch/batch_<run_id>.json` 的「操作訊號」格。名稱推定停用後，舊存檔讀回時欄名沒變，
買賣句會原樣顯示（還與重跑的新列「—」並排），名稱推定結果因此從磁碟復活；舊欄「資產屬性」則靜默丟失。

修法（`repositories/batch_checkpoint.py::load`）：讀回時就地把已知的 8 句買賣句改「—」、移除舊「資產屬性」鍵；
錯誤標記（「⚠️ …」）與其他欄位原封不動；不改寫磁碟檔；不替舊列補「基金屬性」。

突變：拿掉 `load()` 內的 `_neutralize_name_inferred_signals(...)` 呼叫 → 本檔多條轉紅（輸出貼於回報）。
全部導向 tmp_path，不碰真 data_cache/。
"""
from __future__ import annotations

import json

import pytest

from repositories import batch_checkpoint as bc

_OLD_SENTENCES = ("🟢 買進加碼", "🟢 積極買進", "⚪ 持有核心", "🟡 持有設停利",
                  "🟡 持有減碼", "🔴 賣出獲利", "🟢 逢低買進", "⏸️ 觀望等待")
_ERR_MARKS = ("⚠️ 計算失敗(ValueError)", "⚠️ 訊號模組載入失敗(ImportError)")


@pytest.fixture(autouse=True)
def _tmp_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(bc, "_DIR", tmp_path / "batch")
    return tmp_path / "batch"


def _old_row(code, signal, attr="核心資產 🛡️"):
    return {"code": code, "基金名": f"基金{code}", "狀態": "✅ 成功", "資產屬性": attr,
            "操作訊號": signal, "現價": "12.34", "Sharpe": 1.1, "備註": ""}


def _write_old_checkpoint(run_id: str) -> tuple:
    codes, rows = [], {}
    for i, s in enumerate(_OLD_SENTENCES + _ERR_MARKS + ("—",)):
        c = f"C{i:02d}"
        codes.append(c)
        rows[c] = _old_row(c, s, attr=("衛星資產 ⚡" if i % 2 else "混合型 ⚖️"))
    bc.save(run_id, codes, rows)
    return codes, rows


def test_load_neutralizes_old_sentences_keeps_errors_and_other_fields():
    codes, original = _write_old_checkpoint("RUNOLD")
    data = bc.load("RUNOLD")
    assert data is not None and set(data["rows"]) == set(codes)
    for c in codes:
        got, was = data["rows"][c], original[c]
        if was["操作訊號"] in _OLD_SENTENCES:
            assert got["操作訊號"] == "—", (c, got)
        else:
            assert got["操作訊號"] == was["操作訊號"], f"錯誤標記／「—」不得被改：{c}"
        assert "資產屬性" not in got, "舊鍵必須移除"
        assert "基金屬性" not in got, "缺值不補：不得替舊列補「基金屬性」"
        for k in ("code", "基金名", "狀態", "現價", "Sharpe", "備註"):
            assert got[k] == was[k], (c, k)


def test_load_does_not_rewrite_the_file_on_disk():
    _write_old_checkpoint("RUNDISK")
    p = bc._path("RUNDISK")
    before = p.read_bytes()
    bc.load("RUNDISK")
    assert p.read_bytes() == before
    raw = json.loads(before.decode("utf-8"))
    assert any(r["操作訊號"] in _OLD_SENTENCES for r in raw["rows"].values()), "磁碟檔應仍是舊內容"


def test_variation_selector_difference_does_not_let_a_sentence_through():
    """「⏸️」(帶 U+FE0F) 與「⏸」(不帶) 都要中和。"""
    bc.save("RUNVS", ["A", "B"], {"A": _old_row("A", "⏸️ 觀望等待"), "B": _old_row("B", "⏸ 觀望等待")})
    rows = bc.load("RUNVS")["rows"]
    assert rows["A"]["操作訊號"] == "—" and rows["B"]["操作訊號"] == "—"


def test_new_format_rows_are_untouched():
    new = {"code": "N1", "狀態": "✅ 成功", "基金屬性": "—", "操作訊號": "—"}
    bc.save("RUNNEW", ["N1"], {"N1": dict(new)})
    assert bc.load("RUNNEW")["rows"]["N1"] == new


def test_list_recent_returns_meta_only_so_no_row_content_to_neutralize():
    """`list_recent`（「📂 讀回」清單）只回 meta，不含列內容；列內容唯一讀回路徑是 `load`。"""
    _write_old_checkpoint("RUNLIST")
    metas = bc.list_recent()
    assert metas and set(metas[0]) == {"run_id", "n_done", "n_codes", "updated_at", "mtime"}


def test_end_to_end_old_checkpoint_never_shows_old_sentences_in_table_or_csv():
    """讀回後的列餵給畫面用的 `_build_df`（舊批次分頁）與 `_batch_table_rows`／`_batch_csv`（③ 合併頁）：
    輸出不含任何舊買賣句，「資產屬性」欄不存在。"""
    from ui.tab_batch_analysis import _build_df
    from ui.views.page_03_research import _batch_csv, _batch_table_rows

    codes, _ = _write_old_checkpoint("RUNE2E")
    rows = bc.load("RUNE2E")["rows"]

    df = _build_df(codes, rows)
    assert "資產屬性" not in df.columns and "基金屬性" in df.columns
    _cells = set(df["操作訊號"].astype(str))
    assert not (_cells & set(_OLD_SENTENCES)), _cells
    assert set(_ERR_MARKS) <= _cells, "錯誤標記應保留"

    table = _batch_table_rows(codes, rows)
    assert not ({r["操作訊號"] for r in table} & set(_OLD_SENTENCES))
    assert all(r["基金屬性"] is None for r in table), "缺值不補"
    csv_text = _batch_csv(table).decode("utf-8-sig")
    for s in _OLD_SENTENCES:
        assert s not in csv_text, f"CSV 仍含舊買賣句 {s!r}"
    for s in ("核心資產", "衛星資產", "混合型"):
        assert s not in csv_text
