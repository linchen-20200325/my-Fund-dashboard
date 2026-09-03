"""Layer 3-C：健康度 4D → 5D + 評分覆蓋揭露（2026-08-14）。

背景 —— **為什麼是 5D 不是原訂的 6D**
=====================================
`scripts/audit_6d_coverage.py` 實測後改案（user 2026-08-14 拍板）：
- 費用率：官方揭露率 0，有值的都是「拿經理費當費用率」→ 不足以分 A/B。不納入。
- 基金規模：2 檔就撞出 2 種字串格式（「266.04 億(美元)」vs「58,185.32 百萬歐元」），
  單位差 100 倍 + 幣別差一層，解析錯**不報錯**只會安靜地錯約 90 倍（§4.1）。不納入。
- 匯率風險：資料既有、已在用、TWD 的 N/A 語意清楚 → 唯一納入的。

每一條都必須**改回舊行為就紅**（PROCESS §4）。
"""
from __future__ import annotations

import pytest


# ══════════════════════════════════════════════════════════════════════
# 第 5 維：匯率風險
# ══════════════════════════════════════════════════════════════════════
def test_twd_fund_is_not_applicable_not_zero():
    """**§1 核心** —— 台幣基金「沒有匯率風險」是事實，不是缺資料、更不是 0 分。

    給 0 分等於懲罰一個優點；當成缺資料則會讓台幣基金的覆蓋率永遠低一截。
    """
    from services.health.grade import score_fx_risk

    for _twd in ("TWD", "twd", "台幣", "新台幣"):
        _s, _st = score_fx_risk(_twd, 3.0)
        assert _s is None and _st == "n/a", f"{_twd} 應為不適用，實得 {_s}/{_st}"


def test_foreign_fund_without_fx_data_is_missing_not_na():
    """外幣基金拿不到匯率 = **真的缺資料**，與 TWD 的 N/A 必須分得開。"""
    from services.health.grade import score_fx_risk

    _s, _st = score_fx_risk("USD", None)
    assert _s is None and _st == "missing"


def test_zero_cv_is_invalid_not_lowest_risk():
    """**同型於 v19.422 的 σ=0 修正** —— CV ≤ 0 是無效輸入，不是「零風險」。

    真實 CV = std/mean 恆 > 0（std ≥ 0、mean > 0）。若把 0 當成「最穩」給 90 分，
    抓不到序列的基金會被評成最健康 —— 專案在 NAV σ 上已經踩過這個坑一次。
    """
    from services.health.grade import score_fx_risk

    for _bad in (0.0, -1.0):
        _s, _st = score_fx_risk("USD", _bad)
        assert _s is None and _st == "missing", f"CV={_bad} 不該給分，實得 {_s}"


@pytest.mark.parametrize("cv,expect_order", [(1.0, 5), (4.0, 4), (6.0, 3),
                                             (10.0, 2), (20.0, 1)])
def test_fx_risk_is_monotonic_in_volatility(cv, expect_order):
    """波動越大分數越低（單調），且 5 個級距都取得到。"""
    from services.health.grade import score_fx_risk

    _s, _st = score_fx_risk("ZAR", cv)
    assert _st == "scored"
    assert _s is not None
    # 用「名次」驗單調：把五個切點跑一遍，分數必須嚴格遞減
    _all = [score_fx_risk("ZAR", c)[0] for c in (1.0, 4.0, 6.0, 10.0, 20.0)]
    assert _all == sorted(_all, reverse=True), f"分數非單調遞減：{_all}"
    assert len(set(_all)) == 5, "五個級距應給出五個不同分數"


def test_fx_risk_thresholds_come_from_ssot():
    """門檻不得寫死在函式裡（§3.3）。"""
    import ast
    import inspect
    import textwrap

    from services.health import grade as G

    _tree = ast.parse(textwrap.dedent(inspect.getsource(G.score_fx_risk)))
    _imported = {
        _a.name for _n in ast.walk(_tree) if isinstance(_n, ast.ImportFrom)
        for _a in _n.names
        if (_n.module or "").startswith("shared.signal_thresholds")
    }
    assert {"FX_RISK_CV_LOW_PCT", "FX_RISK_CV_MILD_PCT",
            "FX_RISK_CV_MID_PCT", "FX_RISK_CV_HIGH_PCT"} <= _imported


def test_cv_conversion_guards_division_by_zero():
    """CV = std/mean，mean ≤ 0 必須回 None 不可炸（§4.4）。"""
    from services.health.report import fx_cv_pct_from_regime

    assert fx_cv_pct_from_regime(None) is None
    assert fx_cv_pct_from_regime({}) is None
    assert fx_cv_pct_from_regime({"std": 1.0, "mean": 0}) is None
    assert fx_cv_pct_from_regime({"std": 1.0, "mean": -5}) is None
    assert fx_cv_pct_from_regime({"std": 0.96, "mean": 32.0}) == pytest.approx(3.0)


def test_cv_makes_currencies_comparable():
    """**§4.1 量綱** —— 用絕對 std 比大小會錯得離譜，CV 才可跨幣別比。

    USDTWD ≈ 32、JPYTWD ≈ 0.21：同樣波動 3%，絕對 std 差約 150 倍。
    """
    from services.health.report import fx_cv_pct_from_regime

    _usd = fx_cv_pct_from_regime({"std": 0.96, "mean": 32.0})     # 3%
    _jpy = fx_cv_pct_from_regime({"std": 0.0063, "mean": 0.21})   # 3%
    assert _usd == pytest.approx(_jpy, rel=1e-6), (
        "同樣 3% 波動的兩個幣別，CV 必須相等 —— 否則跨幣別比大小是量綱錯誤")


# ══════════════════════════════════════════════════════════════════════
# 加維度不得改變既有 caller 的行為
# ══════════════════════════════════════════════════════════════════════
def test_not_passing_fx_keeps_old_score():
    """**回歸護欄** —— 不傳匯率參數時，分數必須與加維前完全相同。

    第 5 維若在缺資料時仍進分母，全站每一個等第都會被稀釋 ——
    那是「改一個維度、動到所有結論」的災難。
    """
    from services.health.grade import compute_4d_health

    _kw = dict(tr1y_pct=12.0, adr_pct=6.0, sharpe=1.1, sigma_pct=12.0, ma_dir="up")
    _a = compute_4d_health(**_kw)
    _b = compute_4d_health(**_kw, fund_ccy="USD", fx_cv_pct=None)
    assert _a["score"] == _b["score"]
    assert _a["grade"] == _b["grade"]
    # 4 維算得出來 → 分母 5（USD 適用）、分子 4
    assert _b["coverage"]["n_scored"] == 4
    assert _b["coverage"]["n_applicable"] == 5


def test_twd_fund_denominator_excludes_fx():
    """台幣基金的分母是 4 不是 5 —— 不適用的維度不進分母。"""
    from services.health.grade import compute_4d_health

    _r = compute_4d_health(tr1y_pct=12.0, adr_pct=6.0, sharpe=1.1,
                           sigma_pct=12.0, ma_dir="up", fund_ccy="TWD")
    assert _r["fx_risk_status"] == "n/a"
    assert _r["coverage"]["n_applicable"] == 4
    assert _r["coverage"]["n_scored"] == 4
    assert _r["coverage"]["ratio"] == 1.0
    assert "fx_risk" not in _r["coverage"]["missing"], (
        "N/A 不是「缺」—— 列進 missing 會讓使用者以為資料不全")


def test_fx_dimension_actually_affects_score():
    """0-consumer 條款:第 5 維必須真的影響總分,否則等於白加。"""
    from services.health.grade import compute_4d_health

    _kw = dict(tr1y_pct=12.0, adr_pct=6.0, sharpe=1.1, sigma_pct=12.0, ma_dir="up")
    _low = compute_4d_health(**_kw, fund_ccy="USD", fx_cv_pct=1.0)    # 穩 → 90
    _high = compute_4d_health(**_kw, fund_ccy="ZAR", fx_cv_pct=20.0)  # 劇烈 → 15
    assert _low["score"] > _high["score"], "匯率維沒有影響總分"
    assert _low["factors"]["fx_risk"] == 90
    assert _high["factors"]["fx_risk"] == 15


# ══════════════════════════════════════════════════════════════════════
# 評分覆蓋揭露
# ══════════════════════════════════════════════════════════════════════
def test_coverage_is_reported():
    """**改回舊行為必紅** —— 沒有 coverage 就沒辦法分辨 2/5 的 A 與 5/5 的 A。"""
    from services.health.grade import compute_4d_health

    _r = compute_4d_health(tr1y_pct=12.0, adr_pct=6.0)   # 只有配息 + 走勢
    _c = _r["coverage"]
    assert set(_c) == {"n_scored", "n_applicable", "n_total", "missing", "ratio"}
    assert _c["n_total"] == 5
    assert "sharpe" in _c["missing"] and "volatility" in _c["missing"]


def test_coverage_label_distinguishes_na_from_missing():
    """➖(台幣不適用) 與 ⚠️(缺資料) 必須長得不一樣（§1 兩種狀態要分得開）。"""
    from services.health.grade import compute_4d_health
    from services.health.report import _grade_coverage_label

    _twd = compute_4d_health(tr1y_pct=12.0, adr_pct=6.0, sharpe=1.1,
                             sigma_pct=12.0, ma_dir="up", fund_ccy="TWD")
    _lbl_twd = _grade_coverage_label(_twd)
    assert _lbl_twd.startswith("➖") and "無匯率風險" in _lbl_twd

    _partial = compute_4d_health(tr1y_pct=12.0, adr_pct=6.0, fund_ccy="USD")
    _lbl_p = _grade_coverage_label(_partial)
    assert _lbl_p.startswith("⚠️")
    assert "缺" in _lbl_p and "風險報酬" in _lbl_p, (
        f"缺哪幾維必須寫出來（用中文，不是內部 key）：{_lbl_p!r}")

    _full = compute_4d_health(tr1y_pct=12.0, adr_pct=6.0, sharpe=1.1,
                              sigma_pct=12.0, ma_dir="up",
                              fund_ccy="USD", fx_cv_pct=3.0)
    assert _grade_coverage_label(_full).startswith("✅")


def test_coverage_label_handles_garbage():
    """算不出來時回 ⬜，不可炸也不可謊稱滿分。"""
    from services.health.report import _grade_coverage_label

    for _bad in (None, {}, {"coverage": None}, {"coverage": {}}):
        assert _grade_coverage_label(_bad) == "⬜ —"


def test_coverage_column_is_wired_everywhere():
    """0-consumer 條款:新欄必須進 row、進欄序、進 column_config help。"""
    from services.health.report import HEALTH_COLUMNS, build_health_analysis_row
    from ui.helpers.fund_grp_health.columns import health_column_config
    from ui.helpers.fund_grp_health.unified import (
        BATCH_UNIFIED_COLUMNS,
        _UNIFIED_FRONT,
    )

    assert "評分覆蓋" in HEALTH_COLUMNS
    _front = [c for c, _ in _UNIFIED_FRONT]
    assert "評分覆蓋" in _front
    assert "評分覆蓋" in BATCH_UNIFIED_COLUMNS
    assert "評分覆蓋" in build_health_analysis_row({}, "T")
    _spec = health_column_config()["評分覆蓋"]
    _help = str(getattr(_spec, "help", "") or _spec)
    assert "面向" in _help and "台幣" in _help


def test_coverage_sits_before_the_grade():
    """欄序:覆蓋率是那個字母的可信度前提,必須先被看到。"""
    from ui.helpers.fund_grp_health.unified import _UNIFIED_FRONT

    _front = [c for c, _ in _UNIFIED_FRONT]
    for _later in ("4D Grade", "4D Score"):
        assert _front.index("評分覆蓋") < _front.index(_later)


# ══════════════════════════════════════════════════════════════════════
# 跨畫面一致性 —— 本批最容易出錯的地方
# ══════════════════════════════════════════════════════════════════════
def test_fx_cache_lives_in_l2_so_every_caller_can_reach_it():
    """**§8.2 + §2.1** —— 快取必須在 L2。

    第 5 維會**改變分數本身**。~~`services/fund_batch.py` 是 L2，構不到 L3 helper~~
    （2026-08-28:該檔已整檔刪除；快取留在 L2 的理由**仍然成立** —— 其餘 L2 caller
    同樣構不到 L3 helper，這條約束不因單一 caller 消失而改變）；
    若只有部分 caller 拿得到匯率資料，同一檔基金會在不同頁得到不同等第。
    """
    import ast
    from pathlib import Path

    # ⚠️ 2026-08-28:原本這裡還有兩行 ——
    #     `from ui.helpers.fund_grp_health.fx_regime import fx_regime_by_ccy as _l3`
    #     `assert _l3 is S.fx_regime_by_ccy, "L3 應為薄轉呼,不得自己再存一份快取"`
    # 已刪除(**測試對象消失,不是為了讓 CI 綠**):那個 L3 re-export shim
    # production 0 caller,本輪整檔刪除,沒有「薄轉呼」可以驗了。
    # **下面的 AST 守衛刻意保留** —— 它驗的是 production 檔的 import 方向,
    # 那個對象還在,而且正是「有人把快取搬回 L3」時唯一會紅燈的地方。

    # production 必須從 **L2** 讀。若哪天有人改回 import L3,
    # 測試的 monkeypatch 就會 patch 不到 → 安靜地打真網路(PROCESS §4 假綠)。
    _root = Path(__file__).resolve().parent.parent
    for _rel in ("ui/helpers/fund_grp_health/unified.py",
                 "ui/helpers/fund_grp_health/switch_advisor_section.py",
                 "scripts/weekly_switch_notify.py"):
        _tree = ast.parse((_root / _rel).read_text(encoding="utf-8"))
        _from_l3 = [
            _n for _n in ast.walk(_tree) if isinstance(_n, ast.ImportFrom)
            and (_n.module or "").endswith("fund_grp_health.fx_regime")
        ]
        assert not _from_l3, (
            f"{_rel} 仍從 L3 import 匯率快取 —— 請改 services.fx_regime_service"
            "(否則測試 patch 不到,會安靜地打真網路)")


@pytest.mark.parametrize("relpath", [
    "ui/helpers/fund_grp_health/unified.py",     # 批次大表
    "ui/tab_fund_grp_health.py",                 # 組合健診大表
    "ui/helpers/fund_grp_health/rotation.py",    # 輪動配對
    "ui/tab2_single_fund.py",                    # 個基深掘
    # ⚠️ 2026-08-28 Phase 1.4:原本這裡還有一行 `"services/fund_batch.py"`(批次 L2 legacy)。
    #   已刪除(**測試對象消失,不是為了讓 CI 綠**):該檔 production 0 caller,本輪整檔刪除,
    #   沒有原始碼可以 read_text 了。⚠️ 這個 parametrize 是**用檔案路徑讀原始碼**,
    #   不是 import —— 字面 import 掃描看不到它,往後刪檔前請一併 grep parametrize 清單。
    #   **其餘 5 個 caller 一列未動**,「每個算等第的地方都要傳同一份匯率」這條守衛照舊生效。
    "scripts/weekly_switch_notify.py",           # NAS 週報
])
def test_every_grade_caller_passes_fx(relpath):
    """**改回舊行為必紅** —— 每個算等第的地方都要傳同一份匯率資料。

    漏掉任何一個，那一頁的等第就會是 4 維平均、別頁是 5 維平均，
    同一檔基金出現兩個結論(正是這一輪一直在修的「跨畫面矛盾」)。
    """
    from pathlib import Path

    _root = Path(__file__).resolve().parent.parent
    _src = (_root / relpath).read_text(encoding="utf-8")
    _code = [ln for ln in _src.splitlines() if not ln.lstrip().startswith("#")]
    _blk = "\n".join(_code)
    assert "build_health_analysis_row" in _blk, (
        f"{relpath} 已不再呼叫 build_health_analysis_row —— 測試清單需更新")
    assert "fx_cv_by_ccy" in _blk, (
        f"{relpath} 呼叫 build_health_analysis_row 但沒傳 fx_cv_by_ccy —— "
        "這一頁的等第會與其他頁不同源(§2.1)")
