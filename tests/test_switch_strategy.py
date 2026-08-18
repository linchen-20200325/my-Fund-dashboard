"""換標決策引擎(v19.423)。驗:策略分、紅/黃/綠/灰燈、同類替換 argmax、大盤 regime、處置文字。

⚠️ 本檔曾把**錯誤語意釘成規格**:`switch_score(8.0, 1.0, None, None) == 100` 只驗了
「衡量」那一半,結果線上出現「缺 MaxDD + 缺 vs大盤 → 100 分 → 🟢 可定期定額加碼」——
缺資料的檔拿到比資料齊全但風險很差的檔**更強的買進訊號**。分數本身沒錯(語意是
「有證據的 65 分裡拿滿 65」),錯的是它被直接拿去跨綠燈門檻。修正後每一條缺值案例
都必須同時釘住 **score(衡量)+ signal(行動)+ coverage 旗標(揭露)** 三者。
"""
from services.switch_strategy import (
    GRAY,
    GREEN,
    RED,
    YELLOW,
    execution_advice,
    market_regime_alert,
    replacement_candidate,
    switch_coverage_label,
    switch_score,
    switch_signal,
)
from shared.switch_thresholds import SWITCH_GREEN_SCORE


# ── 策略分 ──────────────────────────────────────────────
def test_score_max():
    assert switch_score(8.0, 1.0, -10.0, 5.0) == 100          # 35+30+20+15


def test_score_mid():
    assert switch_score(3.0, 0.5, -20.0, -2.0) == 55          # 25+20+10+0


def test_score_floor():
    assert switch_score(-15.0, -0.5, -30.0, None) == 0        # 0+0+0+0


def test_score_missing_core_is_none():
    assert switch_score(None, 1.0, -10.0, 5.0) is None        # 缺 1Y含息
    assert switch_score(8.0, None, -10.0, 5.0) is None        # 缺 Sharpe


def test_score_optional_missing_ok():
    """MaxDD / vs大盤 缺 → 退出分母(缺值≠壞值,§1),核心齊 → 依可用權重放回 0-100。

    分數維持 100 是**刻意**的:語意是「有證據的 65 分裡你拿滿 65」。但 100 分**不得**
    自己走到綠燈 —— 那一半由 `test_partial_coverage_never_reaches_green` 釘。
    """
    _cov = {}
    assert switch_score(8.0, 1.0, None, None, coverage_out=_cov) == 100   # 65/65 → 100
    # 舊版此測只有上面那行 → 把「缺兩維也是滿分且可綠燈」釘成規格。以下三條補完契約:
    assert _cov["rescaled"] is True and _cov["available"] == 65
    assert _cov["earned"] == 65 < SWITCH_GREEN_SCORE          # 悲觀下界:缺的全算 0 → 65
    assert "65/100" in switch_coverage_label(_cov, 100)


def test_score_missing_not_scored_like_bad():
    """缺值必須明顯優於壞值,否則 §1「缺值偽裝成壞值」。"""
    _missing = switch_score(8.0, 1.0, None, 5.0)              # 缺 MaxDD
    _bad = switch_score(8.0, 1.0, -40.0, 5.0)                 # MaxDD 真的很差
    assert _missing is not None and _bad is not None
    assert _missing > _bad


# ── 覆蓋率閘門:缺資料不得換到更強的買進訊號(§1)────────────
def _sig_with_cov(tr, sh, dd, vm, eat):
    """走 production 同一條路:score(帶側車)→ signal(吃側車)。"""
    _cov = {}
    _sc = switch_score(tr, sh, dd, vm, coverage_out=_cov)
    return _sc, switch_signal(tr, sh, eat, _sc, coverage=_cov), _cov


def test_partial_coverage_never_reaches_green():
    """**修正前必紅**(修正前回 GREEN)—— 線上正在誤導使用者的那一條。

    B 檔:1Y含息 8% + Sharpe 1.0 齊全,但 MaxDD 與 vs大盤 **抓不到**
    (MaxDD 為 None 的成因 = NAV < MIN_OBS_MAX_DRAWDOWN 125 筆,新發行 / 保單子網域被封鎖
    只抓到短序列 → 風險最不明的一批)。
    重正規化後 65/65 → 100 分 → 舊碼 `score >= 70 and 健康` → 🟢
    「續抱,可作核心資產或定期定額**加碼**」。
    """
    _sc, _sig, _cov = _sig_with_cov(8.0, 1.0, None, None, "🟢🟢 健康")
    assert _sc == 100                                  # 衡量:有證據的部分拿滿(不變)
    assert _sig == YELLOW                              # 行動:證據不全 → 不給加碼訊號
    assert "不給綠燈" in switch_coverage_label(_cov, _sc)


def test_missing_data_is_not_more_bullish_than_bad_data():
    """QA 的 A/B 對照表:缺資料的燈號**不得**比「資料齊、風險很差」更積極。

    A 檔:1Y含息 8 / Sharpe 1.0 / MaxDD −40% / vs大盤 −2% → 65 分 → 🟡
    B 檔:同樣的含息與 Sharpe,但 MaxDD / vs大盤 **缺** → 100 分
    修正前 B 是 🟢 加碼、A 是 🟡 觀望 —— 缺資料反而拿到更強的買進建議(§1 違憲)。
    """
    _sc_a, _sig_a, _ = _sig_with_cov(8.0, 1.0, -40.0, -2.0, "🟢🟢 健康")   # 資料齊、風險差
    _sc_b, _sig_b, _ = _sig_with_cov(8.0, 1.0, None, None, "🟢🟢 健康")    # 風險資料抓不到
    assert _sc_a == 65 and _sc_b == 100                # 分數仍可區分(缺值≠壞值,§1 前一輪)
    assert _sig_a == YELLOW and _sig_b == YELLOW       # 但行動建議 B 不得比 A 積極
    # 執行建議層面:B 拿到的文字必須與 A 相同,且不得是綠燈那句「續抱,可…定期定額加碼」
    assert execution_advice(_sig_b) == execution_advice(_sig_a)
    assert "續抱" not in execution_advice(_sig_b)


def test_partial_coverage_still_green_when_lower_bound_clears():
    """閘門是**悲觀下界**不是「一律封殺」:缺的維度全拿 0 仍 ≥ 綠燈門檻 → 綠燈照給。

    35(含息)+ 30(Sharpe)+ 20(MaxDD)= 85 ≥ 70,只缺 vs大盤 的 15 分 ——
    那 15 分再怎麼樣都翻不掉結論,硬降黃就變成「缺值偽裝成壞值」的另一種形式。
    """
    _sc, _sig, _cov = _sig_with_cov(8.0, 1.0, -10.0, None, "🟢🟢 健康")
    assert _cov["earned"] == 85 >= SWITCH_GREEN_SCORE
    assert _sc == 100 and _sig == GREEN
    _lbl = switch_coverage_label(_cov, _sc)                  # 綠燈照給,但覆蓋率仍要揭露
    assert "85/100" in _lbl and "vs 大盤%" in _lbl and "不給綠燈" not in _lbl


def test_full_coverage_green_unchanged():
    """護欄(修正前也綠):四維齊全 → 覆蓋閘門完全不介入,既有燈號零變化。"""
    _sc, _sig, _cov = _sig_with_cov(8.0, 1.0, -10.0, 5.0, "🟢🟢 健康")
    assert _sc == 100 and _sig == GREEN
    assert _cov["rescaled"] is False
    assert switch_coverage_label(_cov, _sc).endswith("100/100")


def test_signal_without_coverage_keeps_legacy_behaviour():
    """未帶側車(舊呼叫端 / 單元測試)→ 沿用舊行為,不無聲改變既有 caller。"""
    assert switch_signal(8.0, 1.0, "🟢🟢 健康", 100) == GREEN


def test_coverage_label_for_unscored():
    assert switch_coverage_label({}, None) == "⬜ 未評分"
    assert switch_coverage_label(None, 80) == "⬜ 未評分"
    _cov = {}
    switch_score(None, None, None, None, coverage_out=_cov)   # 核心缺 → 未評分
    assert switch_coverage_label(_cov, None) == "⬜ 未評分"


def test_red_not_softened_by_coverage_gate():
    """閘門只擋綠燈:明確壞資料(含息<0 且 Sharpe<0)即使覆蓋不全也照樣紅燈(§1)。"""
    _sc, _sig, _ = _sig_with_cov(-5.0, -0.3, None, None, "🟡 警示")
    assert _sig == RED


# ── 燈號 ────────────────────────────────────────────────
def test_signal_red_both_negative():
    assert switch_signal(-5.0, -0.3, "🟡 警示", 20) == RED


def test_signal_red_severe_eat():
    assert switch_signal(3.0, 0.6, "🔴 嚴重的吃本金", 60) == RED


def test_signal_red_severe_even_without_score():
    # 稽核 Finding 1:嚴重吃本金 = 明確賣出,即使 Sharpe/含息/分 皆缺 也是紅燈(不被灰燈蓋)
    assert switch_signal(None, None, "🔴 嚴重的吃本金(報酬為負)", None) == RED


def test_signal_green():
    assert switch_signal(8.0, 1.0, "🟢🟢 健康", 85) == GREEN


def test_signal_gray_insufficient():
    assert switch_signal(8.0, 1.0, "健康", None) == GRAY
    assert switch_signal(None, 1.0, "健康", 80) == GRAY


def test_signal_yellow_default():
    # 非紅(tr>0)、非綠(分<70)、非灰 → 黃
    assert switch_signal(3.0, 0.5, "🟡 警示", 55) == YELLOW


def test_signal_high_score_but_not_healthy_is_yellow():
    # 分高但吃本金非健康 → 不綠 → 黃
    assert switch_signal(8.0, 1.0, "🟡 警示", 85) == YELLOW


def test_compute_switch_columns_reads_real_column_names():
    """稽核 Finding 6:鎖 cross-source 欄名契約 —— 欄名改掉 → 訊號靜默降級,此測試會抓到。"""
    from ui.helpers.fund_grp_health.unified import compute_switch_columns
    _row = {"1Y 含息 %": -5.0, "Sharpe 1Y": -0.3, "Max DD %": -20.0,
            "vs 大盤%": -2.0, "吃本金燈號 (1Y · )": "🔴 嚴重的吃本金", "距 HWM %": "-25%"}
    assert compute_switch_columns(_row)["策略燈號"] == RED
    _good = {"1Y 含息 %": 8.0, "Sharpe 1Y": 1.0, "Max DD %": -10.0, "vs 大盤%": 5.0,
             "吃本金燈號 (1Y · )": "🟢 健康"}
    _r = compute_switch_columns(_good)
    assert _r["換標策略分"] == 100 and _r["策略燈號"] == GREEN
    assert _r["策略分覆蓋"].endswith("100/100")   # 全覆蓋也要出旗標(欄恆在,非只在異常時冒出)


def test_compute_switch_columns_wires_coverage_into_signal():
    """**修正前必紅** —— `coverage_out` 全站 0 consumer 的那條「空頭承諾」。

    修正前 `unified.py` 呼叫 `switch_score(_tr, _sh, _dd, _vm)` 沒帶側車、
    `switch_signal(...)` 也拿不到覆蓋率 → 這一列在大表上就是「100 分 + 🟢 加碼」。
    """
    from ui.helpers.fund_grp_health.unified import compute_switch_columns
    _partial = {"1Y 含息 %": 8.0, "Sharpe 1Y": 1.0, "Max DD %": None,
                "vs 大盤%": None, "吃本金燈號 (1Y · )": "🟢🟢 健康"}
    _r = compute_switch_columns(_partial)
    assert _r["換標策略分"] == 100
    assert _r["策略燈號"] == YELLOW, "部分覆蓋不得走到綠燈(§1)"
    _lbl = _r["策略分覆蓋"]
    assert "65/100" in _lbl and "Max DD %" in _lbl and "vs 大盤%" in _lbl
    assert "不給綠燈" in _lbl, "旗標必須說明燈號被強制降級,否則 user 只看到 100 分"


def test_compute_switch_columns_handles_nan_from_dataframe():
    """邊界:大表走 `pd.to_numeric(errors='coerce')`,缺值是 **NaN 不是 None**。

    NaN 若沒被當成缺值 → 分母不會收斂、旗標也不會亮(靜默降級)。
    """
    import numpy as np

    from ui.helpers.fund_grp_health.unified import compute_switch_columns
    _row = {"1Y 含息 %": 8.0, "Sharpe 1Y": 1.0, "Max DD %": np.nan,
            "vs 大盤%": np.nan, "吃本金燈號 (1Y · )": "🟢🟢 健康"}
    _r = compute_switch_columns(_row)
    assert _r["策略燈號"] == YELLOW and "65/100" in _r["策略分覆蓋"]


def test_sharpe_provenance_column_tells_the_truth():
    """**修正前必紅**(欄根本不存在):大表 Sharpe 欄的來源必須逐檔照實顯示。

    大表 help 原本硬寫「非MoneyDJ公布值」,但 `m["sharpe"]` 優先序是
    官方一年 > 官方六個月 > 本地自算 —— 境外基金常態就是官方值。

    2026-08-10:顯示值改白話(原本印外站頁面代號 + 英文期間縮寫)。斷言改吃 SSOT
    常數而非抄字面值 —— 抄字面值等於在測試裡再寫一份文案,改文案時兩邊都要記得改。
    **未放寬**:六個月那條原本守「帶 6M + ⚠️」,現在守「帶警告記號、講得出六個月、
    且明講不是一年」,比原條更嚴。
    """
    from ui.helpers.fund_grp_health.unified import (
        SHARPE_SRC_OFFICIAL_1Y,
        SHARPE_SRC_OFFICIAL_6M,
        SHARPE_SRC_SELF_CALC,
        SHARPE_SRC_UNKNOWN,
        sharpe_provenance_by_code,
    )

    def _f(code, meta):
        return {"code": code, "metrics": {"risk_metric_meta": {"sharpe": meta}}}

    _out = sharpe_provenance_by_code([
        _f("A", {"source": "wb07_1y", "period_days": None}),
        _f("B", {"source": "wb07_6m", "period_days": None}),
        _f("C", {"source": "self_calc", "period_days": 250}),
        _f("D", {"source": None, "period_days": None}),
        {"code": "E"},                       # 舊 cache / 抓取失敗:無 metrics
    ])
    assert _out["A"]["Sharpe 來源"] == SHARPE_SRC_OFFICIAL_1Y
    _b = _out["B"]["Sharpe 來源"]
    assert _b == SHARPE_SRC_OFFICIAL_6M
    assert "⚠️" in _b, "六個月來源必須帶警告記號"
    assert "6 個月" in _b and "非 1 年" in _b, (
        f"期間警告不可弄丟 —— 本欄存在的理由就是「這一檔量的不是一年」:{_b!r}")
    assert _out["C"]["Sharpe 來源"] == f"{SHARPE_SRC_SELF_CALC}　250 天"
    assert _out["D"]["Sharpe 來源"] == SHARPE_SRC_UNKNOWN
    assert _out["E"]["Sharpe 來源"] == SHARPE_SRC_UNKNOWN
    assert sharpe_provenance_by_code([{"name": "無 code"}]) == {}   # 邊界:無 code 不炸


def test_sharpe_provenance_official_and_self_calc_stay_distinguishable():
    """§2.2:這一欄唯一的用途就是讓人分得出「官方公布值」與「本站自算」。

    **修正前會不會紅**:不會(舊值也分得出來)。這是把「改文案時不准把兩者搞混」
    寫成回歸鎖 —— 上一版沒有任何測試守這件事,文案一改就可能悄悄失守。
    """
    from ui.helpers.fund_grp_health.unified import (
        SHARPE_SRC_OFFICIAL_1Y,
        SHARPE_SRC_OFFICIAL_6M,
        SHARPE_SRC_SELF_CALC,
        SHARPE_SRC_UNKNOWN,
    )
    _official = (SHARPE_SRC_OFFICIAL_1Y, SHARPE_SRC_OFFICIAL_6M)
    for _lbl in _official:
        assert "官方" in _lbl, f"官方來源沒說自己是官方:{_lbl!r}"
        assert "自算" not in _lbl, f"官方來源不得出現「自算」字樣:{_lbl!r}"
    assert "自算" in SHARPE_SRC_SELF_CALC and "官方" not in SHARPE_SRC_SELF_CALC
    assert SHARPE_SRC_UNKNOWN not in _official
    assert len({SHARPE_SRC_OFFICIAL_1Y, SHARPE_SRC_OFFICIAL_6M,
                SHARPE_SRC_SELF_CALC, SHARPE_SRC_UNKNOWN}) == 4, "四種狀態不得撞值"


# ── 替換引擎(同類別 argmax)────────────────────────────
def _cand(code, cat, sharpe, tr, sortino, exp=0.8, eat="🟢 健康"):
    return {"code": code, "基金類別": cat, "Sharpe 1Y": sharpe, "1Y 含息 %": tr,
            "Sortino": sortino, "費用率 %": exp, "吃本金燈號 (1Y · )": eat, "策略燈號": GREEN}


def test_replacement_picks_best_same_category():
    pool = [_cand("B", "股票型", 1.0, 8.0, 0.5),
            _cand("C", "股票型", 1.5, 10.0, 1.0),   # 最佳
            _cand("D", "債券型", 2.0, 20.0, 2.0)]   # 不同類 → 排除
    best = replacement_candidate("股票型", pool)
    assert best is not None and best["code"] == "C"


def test_replacement_excludes_unhealthy():
    pool = [_cand("B", "股票型", 0.3, 8.0, 0.5),          # Sharpe<0.5 排除
            _cand("C", "股票型", 1.0, -2.0, 0.5),         # 總報酬<0 排除
            _cand("D", "股票型", 1.0, 8.0, 0.5, exp=1.8)]  # 費用率≥1.5 排除
    assert replacement_candidate("股票型", pool) is None


def test_replacement_none_when_no_same_category():
    pool = [_cand("B", "債券型", 1.5, 10.0, 1.0)]
    assert replacement_candidate("股票型", pool) is None


# ── 大盤 regime filter ──────────────────────────────────
def test_regime_systemic_when_over_80pct_negative():
    rows = [{"Sharpe 1Y": v} for v in [-0.5, -0.3, -1.0, -0.2, 0.1]]   # 4/5 = 80%
    r = market_regime_alert(rows)
    assert r["systemic_risk"] is True and r["neg_pct"] == 80.0


def test_regime_not_systemic_when_healthy():
    rows = [{"Sharpe 1Y": v} for v in [0.8, 1.0, -0.3, 0.5]]           # 1/4 = 25%
    assert market_regime_alert(rows)["systemic_risk"] is False


def test_regime_no_valid_sharpe():
    assert market_regime_alert([{"Sharpe 1Y": None}])["systemic_risk"] is False


def test_regime_by_category():
    rows = [{"基金類別": "股票型", "Sharpe 1Y": -0.5},
            {"基金類別": "股票型", "Sharpe 1Y": -0.3},
            {"基金類別": "債券型", "Sharpe 1Y": 1.0}]
    assert market_regime_alert(rows, category="股票型")["systemic_risk"] is True


# ── 處置文字 ────────────────────────────────────────────
def test_execution_advice_covers_all_lights():
    assert "平轉" in execution_advice(RED)
    assert "暫停" in execution_advice(YELLOW)
    assert "續抱" in execution_advice(GREEN)
    assert "資料不足" in execution_advice(GRAY)
