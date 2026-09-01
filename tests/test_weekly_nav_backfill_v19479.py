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
             "n_ccy_refused": sum(1 for r in results if r.get("ccy_refused")),
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
    # ⚠️ 反向同樣要守:這句只有在**真的寫入了**的時候才准出現,見下方三則。


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


# ── 2026-09-01 稽核 🔴:「原幣別序列照常寫入」是**無條件斷言**,在兩個可達狀態下為假 ──
# `r["ccy_refused"]` 設在 `if s.empty` **之前**、也在 Gate 0 **之前** →
# 「拒絕發生」與「什麼都沒寫」可以同時成立。兩支都以實跑 probe 複驗過,不是推論。
# ⚠️ 資料行為是對的(空序列時拒絕美元候選仍然正確,§1 寧可沒有不可寫錯幣別);
#    這幾則守的是**敘述不得說謊** —— 訊息說謊比沒有訊息更危險。
_CCY_NOFETCH_ROW = {"code": "D", "fetched": 0, "date_min": None, "date_max": None,
                    "source": None, "blocked": False,
                    "error": "抓不到淨值(晨星/CnYES 查無 ISIN / MoneyDJ 掛 / 代碼不對)",
                    "ccy_refused": "幣別不一致:這檔基金應為 TWD,但候選序列宣告 USD"}
_CCY_BLOCKED_ROW = {"code": "E", "fetched": 2, "date_min": "2024-12-01",
                    "date_max": "2024-12-30", "source": "moneydj", "blocked": True,
                    "error": "與既有 nav_history 衝突:重疊 1 日、1 日對不上 —— 已擋下未寫入",
                    "ccy_refused": "幣別不一致:這檔基金應為 TWD,但候選序列宣告 USD"}


def test_currency_refusal_with_nothing_fetched_must_not_claim_a_write(monkeypatch, capsys):
    """拒絕換源 ＋ MoneyDJ 也抓不到 → **不存在**「原幣別序列」,不准說它被寫入。"""
    _patch_backfill(monkeypatch, _res([_CCY_NOFETCH_ROW]))
    W.main([])
    _err = capsys.readouterr().err
    assert "🟠 D" in _err and "拒絕換源" in _err
    assert "原幣別序列照常寫入" not in _err, (
        "同一次 run 同時印『⬜ 抓不到淨值』與『原幣別序列照常寫入』= 兩行自相矛盾")
    assert "今天等於沒補到" in _err


def test_currency_refusal_on_a_blocked_fund_must_not_claim_a_write(monkeypatch, capsys):
    """拒絕換源 ＋ 同一檔被 Gate 0 擋下 → 🔴 說「未寫入」、🟠 不准說「照常寫入」。

    ⚠️ 這兩件事**正相關**:幣別混亂的基金正是歷史值對不上 Gate 0 的那一檔。
    """
    _patch_backfill(monkeypatch, _res([_CCY_BLOCKED_ROW]))
    W.main([])
    _err = capsys.readouterr().err
    assert "🔴 E" in _err and "🟠 E" in _err
    assert "原幣別序列照常寫入" not in _err
    assert "另被 Gate 0 擋下" in _err


def test_summary_line_flags_how_many_wrote_nothing(monkeypatch, capsys):
    """完成行不得無條件宣稱「有寫入」,要把「其中幾檔完全沒寫入」講出來。"""
    _patch_backfill(monkeypatch, _res([_OK_ROW, _CCY_ROW, _CCY_NOFETCH_ROW]))
    W.main([])
    _err = capsys.readouterr().err
    assert "2 檔幣別不一致拒絕換源" in _err
    assert "其中 1 檔今天完全沒寫入" in _err
    assert "有寫入,寫的是原幣別那條)。" not in _err, "完成行仍是無條件斷言"


def test_step_summary_shows_per_fund_outcome_not_a_blanket_claim(monkeypatch, tmp_path):
    """Step Summary 逐檔要有「結局」欄;沒寫入的檔要另外拉一段警示。"""
    _f = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(_f))
    _patch_backfill(monkeypatch, _res([_CCY_ROW, _CCY_NOFETCH_ROW]))
    W.main([])
    _txt = _f.read_text(encoding="utf-8")
    assert "這一檔今天的結局" in _txt
    assert "原幣別序列照常寫入" in _txt and "今天等於沒補到" in _txt
    assert "**這些檔有寫入**" not in _txt, "表頭仍是無條件斷言"
    assert "不影響數字正確性" not in _txt, "那句在『完全沒寫入』的狀態下是假的"
    assert "完全沒有寫入任何淨值" in _txt


def test_step_summary_no_nothing_written_warning_when_all_wrote(monkeypatch, tmp_path):
    """反向:全部都有寫入 → 不要生出那段警示(§5 訊號不該被雜訊稀釋)。"""
    _f = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(_f))
    _patch_backfill(monkeypatch, _res([_CCY_ROW]))
    W.main([])
    _txt = _f.read_text(encoding="utf-8")
    assert "原幣別序列照常寫入" in _txt
    assert "完全沒有寫入任何淨值" not in _txt


def test_summary_line_reads_the_l2_aggregate_not_a_local_recount(monkeypatch, capsys):
    """稽核 minor:計數要讀 L2 的 `n_ccy_refused`(與 `_n_blocked` 對稱),不要自己再數一次。

    加一個聚合欄、用「這樣才看得見」當理由、然後沒有任何生產端讀者 —— 那個欄位就是裝飾品。
    """
    _res_obj = _res([_OK_ROW, _CCY_ROW])
    _res_obj["n_ccy_refused"] = 7          # 故意與 results 不同 → 只有真的讀它才會印 7
    _patch_backfill(monkeypatch, _res_obj)
    W.main([])
    assert "7 檔幣別不一致拒絕換源" in capsys.readouterr().err


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
