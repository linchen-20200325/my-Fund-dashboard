"""v19.479:每週 NAV 自動補齊 cron(scripts/weekly_nav_backfill.py)。

驗證:代號蒐集(持倉 ∪ 選股池,去重 upper、單邊失敗不擋)+ main 退出碼(§1 Fail Loud)。
不打真網路 / 不碰真 Sheet —— 全 monkeypatch。
"""


import scripts.weekly_nav_backfill as W


class _E:
    def __init__(self, code):
        self.code = code


def _patch_pool(monkeypatch, codes):
    import repositories.pool_repository as PR
    monkeypatch.setattr(PR, "list_pool", lambda: [_E(c) for c in codes])


def _patch_holdings(monkeypatch, fn):
    import scripts.weekly_switch_notify as SW
    monkeypatch.setattr(SW, "_read_holdings", fn)


# ── _gather_codes ───────────────────────────────────────────────────────
def test_gather_union_dedup_upper(monkeypatch):
    _patch_holdings(monkeypatch, lambda c, s: ["ACDD01", "jfzn3"])
    _patch_pool(monkeypatch, ["jfzn3", "TLZF9", " albt8 "])   # jfzn3 與持倉重複
    out = W._gather_codes(object(), "SID")
    assert out == ["ACDD01", "JFZN3", "TLZF9", "ALBT8"]       # 去重 + upper + 保序(持倉先)


def test_gather_holdings_failure_keeps_pool(monkeypatch):
    def _boom(c, s):
        raise RuntimeError("policy sheet 讀取失敗")
    _patch_holdings(monkeypatch, _boom)
    _patch_pool(monkeypatch, ["TLZF9"])
    assert W._gather_codes(object(), "SID") == ["TLZF9"]      # 持倉炸 → 仍回選股池


def test_gather_pool_failure_keeps_holdings(monkeypatch):
    _patch_holdings(monkeypatch, lambda c, s: ["ACDD01"])
    import repositories.pool_repository as PR
    monkeypatch.setattr(PR, "list_pool", lambda: (_ for _ in ()).throw(RuntimeError("pool 讀取失敗")))
    assert W._gather_codes(object(), "SID") == ["ACDD01"]     # 選股池炸 → 仍回持倉


def test_gather_no_client_skips_holdings(monkeypatch):
    _patch_holdings(monkeypatch, lambda c, s: ["SHOULD_NOT"])  # client None → 不呼叫持倉
    _patch_pool(monkeypatch, ["TLZF9"])
    assert W._gather_codes(None, None) == ["TLZF9"]


# ── main 退出碼(§1)─────────────────────────────────────────────────────
def test_main_no_client_exits_2(monkeypatch):
    monkeypatch.setattr(W, "_load_client_and_holdings_sheet", lambda: (None, None))
    assert W.main([]) == 2


def test_main_no_codes_exits_2(monkeypatch):
    monkeypatch.setattr(W, "_load_client_and_holdings_sheet", lambda: (object(), "SID"))
    monkeypatch.setattr(W, "_gather_codes", lambda c, s: [])
    assert W.main([]) == 2


def test_main_dry_run_lists_without_fetch(monkeypatch):
    monkeypatch.setattr(W, "_load_client_and_holdings_sheet", lambda: (object(), "SID"))
    monkeypatch.setattr(W, "_gather_codes", lambda c, s: ["TLZF9", "JFZN3"])
    # dry-run 不該 import/呼叫 backfill_to_gs;若呼叫則測試以 import error 或 assert 失敗
    import services.nav_history_store as NS
    monkeypatch.setattr(NS, "backfill_to_gs",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("dry-run 不該抓")))
    assert W.main(["--dry-run"]) == 0


def test_main_gs_disabled_exits_2(monkeypatch):
    monkeypatch.setattr(W, "_load_client_and_holdings_sheet", lambda: (object(), "SID"))
    monkeypatch.setattr(W, "_gather_codes", lambda c, s: ["TLZF9"])
    import services.nav_history_gs as GS
    monkeypatch.setattr(GS, "is_enabled", lambda: False)
    assert W.main([]) == 2                                    # 雲端未啟用 → exit 2


def test_main_success_returns_0(monkeypatch):
    monkeypatch.setattr(W, "_load_client_and_holdings_sheet", lambda: (object(), "SID"))
    monkeypatch.setattr(W, "_gather_codes", lambda c, s: ["TLZF9"])
    import services.nav_history_gs as GS
    import services.nav_history_store as NS
    monkeypatch.setattr(GS, "is_enabled", lambda: True)
    monkeypatch.setattr(NS, "backfill_to_gs", lambda codes, **_k: {
        "results": [{"code": "TLZF9", "fetched": 1300, "date_min": "2021-01-01",
                     "date_max": "2026-08-18", "source": "yahoo(ISIN)", "error": None}],
        "gs_enabled": True, "gs_written": 5, "gs_error": None, "n_ok": 1, "n_fail": 0,
    })
    assert W.main([]) == 0


def test_main_all_fail_exits_1(monkeypatch):
    monkeypatch.setattr(W, "_load_client_and_holdings_sheet", lambda: (object(), "SID"))
    monkeypatch.setattr(W, "_gather_codes", lambda c, s: ["TLZF9"])
    import services.nav_history_gs as GS
    import services.nav_history_store as NS
    monkeypatch.setattr(GS, "is_enabled", lambda: True)
    monkeypatch.setattr(NS, "backfill_to_gs", lambda codes, **_k: {
        "results": [{"code": "TLZF9", "fetched": 0, "date_min": None, "date_max": None,
                     "source": None, "error": "抓不到"}],
        "gs_enabled": True, "gs_written": 0, "gs_error": None, "n_ok": 0, "n_fail": 1,
    })
    assert W.main([]) == 1


# ══════════════════════════════════════════════════════════════════════════
# 2026-08-28 稽核必修 4／5:被 Gate 0 擋下時,這條排程過去是**安靜的**
#   舊版只在 `gs_error` 或 `n_ok == 0` 時 return 1 —— 一檔被擋、其他正常 →
#   n_ok > 0 → exit 0 → **綠燈、零通知**,那檔基金從此每天被擋、每天沒人知道。
#   fail-closed 於是退化成 **silent data loss**。
# ══════════════════════════════════════════════════════════════════════════
def _patch_backfill(monkeypatch, res):
    monkeypatch.setattr(W, "_load_client_and_holdings_sheet", lambda: (object(), "SID"))
    monkeypatch.setattr(W, "_gather_codes", lambda c, s: ["A", "B"])
    import services.nav_history_gs as GS
    import services.nav_history_store as NS
    monkeypatch.setattr(GS, "is_enabled", lambda: True)
    monkeypatch.setattr(NS, "backfill_to_gs", lambda codes, **_k: res)


def _res(results, **kw):
    _base = {"results": results, "gs_enabled": True, "gs_written": 3, "gs_error": None,
             "n_ok": sum(1 for r in results if r["error"] is None and r["fetched"]),
             "n_fail": sum(1 for r in results if r["error"]),
             "n_blocked": sum(1 for r in results if r.get("blocked")),
             "gate_mode": "enforce"}
    _base.update(kw)
    return _base


_OK_ROW = {"code": "A", "fetched": 1300, "date_min": "2021-01-01",
           "date_max": "2026-08-27", "source": "yahoo(ISIN)", "error": None,
           "blocked": False}
_BLOCKED_ROW = {"code": "B", "fetched": 20, "date_min": "2026-08-01",
                "date_max": "2026-08-27", "source": "yahoo(ISIN)", "blocked": True,
                "error": "與既有 nav_history 衝突:重疊 5 日、5 日對不上 —— 已擋下未寫入"}


def test_main_returns_1_when_a_fund_is_blocked_even_though_others_succeeded(monkeypatch):
    """一檔被擋、其他正常 → **仍須 exit 1**。

    這是一個**持續性**故障:不處理就每天重演,而 exit code 是這條排程上唯一會主動
    通知人的管道（沒有人會去點開綠色 run 的 summary）。舊行為在這裡回 0。
    """
    _patch_backfill(monkeypatch, _res([_OK_ROW, _BLOCKED_ROW]))
    assert W.main([]) == 1


def test_main_still_returns_0_when_nothing_is_blocked(monkeypatch):
    """不可矯枉過正:單純「某檔今天抓不到」仍是 exit 0（增量場景非致命,原行為）。"""
    _nofetch = {"code": "B", "fetched": 0, "date_min": None, "date_max": None,
                "source": None, "error": "MoneyDJ 掛了", "blocked": False}
    _patch_backfill(monkeypatch, _res([_OK_ROW, _nofetch]))
    assert W.main([]) == 0


def test_main_does_not_call_a_blocked_fund_unfetchable(monkeypatch, capsys):
    """訊息不得說謊:被擋的檔**抓得好好的**（fetched=20）,不是「抓不到」。"""
    _patch_backfill(monkeypatch, _res([_OK_ROW, _BLOCKED_ROW]))
    W.main([])
    _err = capsys.readouterr().err
    assert "1 檔抓不到" not in _err, "把『被擋下』併進『抓不到』= 訊息說謊"
    assert "0 檔抓不到" in _err and "1 檔被 Gate 0 擋下" in _err
    assert "🔴 B" in _err, "被擋的檔要用 🔴（偵測到的真失敗）,不是 ⬜（還沒載入）"
    assert "NAV_GATE0_MODE=observe" in _err, "沒有告訴人怎麼止血 = 只會天天紅"


def test_step_summary_lists_the_blocked_funds(monkeypatch, tmp_path):
    """exit code 負責叫人來看,`$GITHUB_STEP_SUMMARY` 負責讓他一眼看懂（§5 可觀測）。"""
    _f = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(_f))
    _patch_backfill(monkeypatch, _res([_OK_ROW, _BLOCKED_ROW]))
    W.main([])
    _txt = _f.read_text(encoding="utf-8")
    assert "被 Gate 0 擋下" in _txt and "`B`" in _txt
    assert "抓不到:**0** 檔" in _txt, "summary 也不可以把被擋講成抓不到"
    assert "NAV_GATE0_MODE=observe" in _txt


# ══════════════════════════════════════════════════════════════════════════
# 2026-09-01:幣別不一致 → 拒絕換源,**必須被 cron 看見**
#
# 為什麼要有這一段(稽核 🔴 必修):`backfill_to_gs` 把理由記進 `results[].ccy_refused`
# 之後**沒有任何消費者** —— cron 入口對 `blocked` 有專屬 log ＋ Step Summary,
# 對幣別拒絕一行都沒有。那等於「揭露了但沒人看得見」,正是 §1／§5 要防的無聲降級。
# ⚠️ 同時要守住**反向**:它不得影響 exit code(那些檔有寫入,天天紅會淹掉真失敗)。
# ══════════════════════════════════════════════════════════════════════════
_CCY_ROW = {"code": "C", "fetched": 30, "date_min": "2026-08-01",
            "date_max": "2026-08-27", "source": "moneydj", "error": None,
            "blocked": False,
            "ccy_refused": "幣別不一致:這檔基金應為 TWD,但候選序列(yahoo(ISIN))宣告 USD"}


def test_main_logs_the_currency_refusal_per_fund(monkeypatch, capsys):
    """逐檔要看得到是**哪一檔、對不上什麼**,不是只有一個總數。"""
    _patch_backfill(monkeypatch, _res([_OK_ROW, _CCY_ROW]))
    W.main([])
    _err = capsys.readouterr().err
    assert "🟠 C" in _err, "🟠 而不是 🔴:它沒有造成任何資料遺失"
    assert "拒絕換源" in _err and "TWD" in _err and "USD" in _err
    assert "原幣別序列照常寫入" in _err, (
        "把『拒絕換源』講成『沒寫入』= 訊息說謊,會把人導去做不必要的補救")


def test_main_summary_line_counts_currency_refusals(monkeypatch, capsys):
    """完成行要有聚合計數 —— 沒有聚合,就得去掃幾百行 log 才知道發生過。"""
    _patch_backfill(monkeypatch, _res([_OK_ROW, _CCY_ROW]))
    W.main([])
    _err = capsys.readouterr().err
    assert "1 檔幣別不一致拒絕換源" in _err
    assert "1 檔抓不到" not in _err, "拒絕換源的檔抓得好好的,不可併進『抓不到』"


def test_main_currency_refusal_alone_does_not_fail_the_run(monkeypatch):
    """**反向守衛**:拒絕換源不進 exit code(那些檔有寫入,天天紅會淹掉真失敗)。"""
    _patch_backfill(monkeypatch, _res([_OK_ROW, _CCY_ROW]))
    assert W.main([]) == 0


def test_step_summary_lists_the_currency_refusals(monkeypatch, tmp_path):
    """Step Summary 要與 `blocked` 同規格:一個 bullet 計數 + 一張指名到檔的表。"""
    _f = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(_f))
    _patch_backfill(monkeypatch, _res([_OK_ROW, _CCY_ROW]))
    W.main([])
    _txt = _f.read_text(encoding="utf-8")
    assert "拒絕換源" in _txt and "`C`" in _txt
    assert "**1** 檔" in _txt
    assert "有寫入" in _txt, "summary 也不可以把『拒絕換源』渲染成失敗"
    assert "被 Gate 0 擋下（**抓到了但沒寫入**）:**0** 檔" in _txt, (
        "兩者語意完全不同,渲染上必須分得開")


def test_step_summary_has_no_currency_table_when_none(monkeypatch, tmp_path):
    """沒發生就不要生出一張空表(§5:訊號不該被雜訊稀釋)。"""
    _f = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(_f))
    _patch_backfill(monkeypatch, _res([_OK_ROW]))
    W.main([])
    _txt = _f.read_text(encoding="utf-8")
    assert "幣別不一致 → 拒絕換源" in _txt and "**0** 檔" in _txt   # bullet 照列
    assert "已拒絕換源（**這些檔有寫入**" not in _txt              # 但沒有表格


def test_step_summary_is_a_noop_without_the_env(monkeypatch):
    """本機 / NAS 沒有這個 env → 不寫、也不炸。"""
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    _patch_backfill(monkeypatch, _res([_OK_ROW]))
    assert W.main([]) == 0


def test_step_summary_failure_does_not_break_the_run(monkeypatch):
    """寫 summary 壞掉不該讓一次成功的補淨值變成失敗（§1 記 log 不靜默,但不致命）。"""
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", "/nonexistent-dir/x/summary.md")
    _patch_backfill(monkeypatch, _res([_OK_ROW]))
    assert W.main([]) == 0
