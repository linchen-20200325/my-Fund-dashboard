"""tests/test_watchlist_push.py — 追蹤清單 → MoneyDJ 淨值 → LINE 推播(v19.438)。

守:
- extract_items_from_csv:表頭欄鎖定 / 無表頭掃 token / 去重 / BOM / 全形逗號 / 排除純數字
- _fund_line / build_message:有 series 出淨值+近5日;抓不到誠實「資料不足」(§1),不捏造
- _chunks:超長切多則(LINE 單則上限)
- send:切塊逐塊 push(注入 push_fn)
- main:fail-loud(無 URL / 解析 0 項 → 非零 exit,不送空)
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "watchlist_push.py"


def _load():
    spec = importlib.util.spec_from_file_location("_wp_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _load()


def _fd(code, navs, dates):
    return {"full_key": code, "fund_name": f"{code}基金",
            "series": pd.Series(navs, index=pd.to_datetime(dates), dtype=float)}


# ── CSV 解析 ─────────────────────────────────────────────────
def test_extract_header_column_only():
    """有「代號」表頭 → 只讀該欄,不吃旁邊數量欄。"""
    csv = "代號,數量\nACCP138,1000\nTLZF9,500\n"
    assert M.extract_items_from_csv(csv) == ["ACCP138", "TLZF9"]


def test_extract_dedup_and_upper_and_bom():
    csv = "﻿代號\naccp138\nACCP138\ntlzf9\n"
    assert M.extract_items_from_csv(csv) == ["ACCP138", "TLZF9"]


def test_extract_no_header_scans_tokens_excludes_pure_numbers():
    """無表頭 → 掃 token;純數字(數量/金額)被排除,含字母 / 00 開頭保留。"""
    csv = "ACCP138 500000\n00980A、6239X\n"
    got = M.extract_items_from_csv(csv)
    assert "ACCP138" in got and "00980A" in got and "6239X" in got
    assert "500000" not in got                       # 純數字不當代號


def test_extract_empty():
    assert M.extract_items_from_csv("") == []


# ── 單檔行 / 訊息 ────────────────────────────────────────────
def test_fund_line_with_series_shows_nav_and_change():
    fd = _fd("TLZF9", [10.0, 10.2, 10.1, 10.3, 10.4, 11.0],
             ["2026-07-15", "2026-07-16", "2026-07-17",
              "2026-07-18", "2026-07-21", "2026-07-22"])
    line = M._fund_line("TLZF9", fd)
    assert "11.0000" in line and "2026-07-22" in line
    assert "近5日 +10.0%" in line                     # 11.0/10.0 - 1 = +10%


def test_fund_line_missing_data_is_honest():
    assert "資料不足" in M._fund_line("X", {})
    assert "資料不足" in M._fund_line("X", {"series": pd.Series(dtype=float)})


def test_fund_line_nonpositive_and_nan_last_are_honest():
    """§1:nav<=0 / 末點 NaN → 資料不足,不把壞值當淨值送。"""
    idx = pd.to_datetime(["2026-07-21", "2026-07-22"])
    assert "資料不足" in M._fund_line("X", {"series": pd.Series([10.0, 0.0], index=idx)})
    assert "資料不足" in M._fund_line(
        "X", {"series": pd.Series([10.0, float("nan")], index=idx)})


def test_fund_line_non_datetime_index_is_honest():
    """§1:非日期索引(RangeIndex)→ 假日期不配真 nav,標資料不足。"""
    assert "資料不足" in M._fund_line("X", {"series": pd.Series([10.0, 11.0])})


def test_extract_exact_header_wins_over_substring_column():
    """回歸:『備考code』不得把代號欄搶走 → 應讀精確命中的『代號』欄。"""
    csv = "備考code,代號\nSKIP,ACCP138\nSKIP,TLZF9\n"
    assert M.extract_items_from_csv(csv) == ["ACCP138", "TLZF9"]


def test_build_message_counts_missing_and_never_fakes():
    def _fetch(code):
        if code == "OK":
            return _fd("OK", [9.0, 9.9], ["2026-07-21", "2026-07-22"])
        raise RuntimeError("US IP blocked")           # 模擬抓不到
    msg = M.build_message(["OK", "BAD"], fetch_fn=_fetch, as_of="2026-08-12")
    assert "追蹤清單淨值（2026-08-12）" in msg
    assert "共 2 檔" in msg
    assert "9.9000" in msg                            # OK 檔有真淨值
    assert "資料不足" in msg and "1 檔抓不到" in msg   # BAD 誠實標,不捏造


# ── 切塊 / 送出 ─────────────────────────────────────────────
def test_chunks_splits_long_message():
    long = "\n".join([f"line-{i}" for i in range(2000)])   # 遠超 4900 字
    parts = M._chunks(long, n=4900)
    assert len(parts) >= 2
    assert all(len(p) <= 4900 for p in parts)


def test_send_pushes_each_chunk_via_injected_push():
    calls = []

    def _push(text, *, dry_run=False):
        calls.append((text, dry_run))
        return {"sent": True}
    res = M.send("a\nb\nc", dry_run=False, push_fn=_push)
    assert res["chunks"] == 1 and res["sent"] == 1
    assert calls and calls[0][1] is False


def test_send_dry_run_flag_passed_through():
    res = M.send("hi", dry_run=True, push_fn=lambda t, *, dry_run: {"sent": False})
    assert res["dry_run"] is True and res["sent"] == 0


# ── main fail-loud ──────────────────────────────────────────
def test_main_no_url_returns_1(monkeypatch):
    monkeypatch.delenv("WATCH_CSV_URL", raising=False)
    assert M.main([]) == 1                             # 無 URL → 非零,不送


def test_main_zero_items_returns_1(monkeypatch):
    monkeypatch.setenv("WATCH_CSV_URL", "http://example/csv")
    monkeypatch.setattr(M, "fetch_csv", lambda url, **k: "代號\n\n")   # 空清單
    assert M.main([]) == 1                             # 解析 0 項 → 不送空


def test_main_dry_run_happy_path(monkeypatch, capsys):
    monkeypatch.setenv("WATCH_CSV_URL", "http://example/csv")
    monkeypatch.setattr(M, "fetch_csv", lambda url, **k: "代號\nTLZF9\n")
    monkeypatch.setattr(M, "_default_fetch",
                        lambda code: _fd(code, [10.0, 11.0],
                                         ["2026-07-21", "2026-07-22"]))
    rc = M.main(["--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0 and "追蹤 1 檔" in out and "11.0000" in out


def test_main_push_failure_returns_1(monkeypatch):
    """§1:LINE 送出丟例外(如 LinePushError)→ main 非零(cron 紅燈)。"""
    monkeypatch.setenv("WATCH_CSV_URL", "http://example/csv")
    monkeypatch.setattr(M, "fetch_csv", lambda url, **k: "代號\nTLZF9\n")
    monkeypatch.setattr(M, "_default_fetch",
                        lambda c: _fd(c, [10.0, 11.0], ["2026-07-21", "2026-07-22"]))
    def _boom(msg):
        raise RuntimeError("LINE push HTTP 500")
    monkeypatch.setattr(M, "send", _boom)
    assert M.main([]) == 1


def test_main_missing_creds_not_all_sent_returns_1(monkeypatch):
    """缺 LINE 憑證 → push_text 回 sent=False → send sent<chunks → main 非零。"""
    monkeypatch.setenv("WATCH_CSV_URL", "http://example/csv")
    monkeypatch.setattr(M, "fetch_csv", lambda url, **k: "代號\nTLZF9\n")
    monkeypatch.setattr(M, "_default_fetch",
                        lambda c: _fd(c, [10.0, 11.0], ["2026-07-21", "2026-07-22"]))
    monkeypatch.setattr(M, "send", lambda msg: {"sent": 0, "chunks": 1, "dry_run": False})
    assert M.main([]) == 1


def test_main_all_missing_returns_2(monkeypatch):
    """全部抓不到 MoneyDJ 淨值 → 送了誠實通知,但 exit 2 讓 cron surface 系統性失敗。"""
    monkeypatch.setenv("WATCH_CSV_URL", "http://example/csv")
    monkeypatch.setattr(M, "fetch_csv", lambda url, **k: "代號\nTLZF9\nACCP138\n")
    monkeypatch.setattr(M, "_default_fetch", lambda c: {})   # 全抓不到
    monkeypatch.setattr(M, "send", lambda msg: {"sent": 1, "chunks": 1, "dry_run": False})
    assert M.main([]) == 2


def test_main_csv_failure_does_not_leak_url(monkeypatch, capsys):
    """§ log 不洩漏:CSV 抓取失敗時,含機密的 URL 不得出現在 stdout(只印例外型別)。"""
    _secret_url = "https://docs.google.com/spreadsheets/d/e/SECRET123/pub?output=csv"
    monkeypatch.setenv("WATCH_CSV_URL", _secret_url)

    def _boom(url, **k):
        raise RuntimeError(f"ConnectionError to {url}")     # 例外訊息內嵌 URL
    monkeypatch.setattr(M, "fetch_csv", _boom)
    rc = M.main([])
    out = capsys.readouterr().out
    assert rc == 1
    assert "SECRET123" not in out and _secret_url not in out
