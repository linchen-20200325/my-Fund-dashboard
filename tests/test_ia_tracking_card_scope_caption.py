"""📈 績效追蹤卡的「範圍說明」caption —— 執行期守衛（2026-09-02）。

**為什麼需要這一支**：換股顧問自 ② 搬到 ④ 之後，本卡與 ④ 既有的
「📊 組合績效」(`ui/helpers/portfolio_perf.render_portfolio_performance`) **同頁並存**，
而兩張卡有三個**逐字相同**的標籤（年化報酬 / 年化波動 σ / 最大回撤）。

實測（2026-09-02）：兩者的數學收口到**同一個 SSOT** —— `portfolio_returns()` →
`metrics_from_return_series()`；`performance_metrics()` 只是把 `cagr_pct` 改名成
`ann_return_pct` 出口。所以：

- 共同交易日 ≥ `PORTFOLIO_TREND_MIN_DAYS` → 三個同名指標**數字完全相同**（純冗餘）；
- 不足 → **本卡**抑制年化顯示「—」，而**下方那張沒有這道閘門、仍給數字**
  → 同一頁同一個標籤，一張「—」一張有數字，**會被讀成「其中一張壞了」**。
  而「不足 60 天」正是**新載入組合的常態**。

本檔守的就是那一行把範圍講清楚的 caption。

⚠️ **這是執行期守衛，不是字串 grep**：測試真的把 `render_portfolio_tracking()`
放進 Streamlit runtime（`AppTest.from_function`）跑起來，斷言**實際渲染出來的**
caption 內容。把 caption 包進永遠不成立的 `if` 裡（死分支）**同樣會轉紅**，
因為它斷言的是「畫面上有沒有這行字」，不是「原始碼裡有沒有這個字串」。

**守不到的**（誠實揭露）：
1. 文案寫得好不好讀 —— 只驗關鍵語意詞在不在，不驗可讀性。
2. caption 在畫面上的**視覺位置**（AppTest 給的是扁平元素清單，不解析版面）。
3. 真瀏覽器的呈現（沒有瀏覽器）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


# ── 測試用資料 ───────────────────────────────────────────────────────────

def _funds(n_days: int) -> list:
    """n_days 個營業日的 TWD 計價假 NAV（兩檔，帶投入金額）。"""
    rng = np.random.default_rng(20260902)
    idx = pd.bdate_range("2025-01-01", periods=n_days)
    out = []
    for i, code in enumerate(("AAA", "BBB")):
        r = rng.normal(0.0003, 0.008 + 0.001 * i, n_days)
        out.append({
            "code": code,
            "currency": "TWD",
            "invest_twd": 100000.0 * (i + 1),
            "series": pd.Series(100.0 * np.cumprod(1.0 + r), index=idx),
        })
    return out


def _script_short():          # < PORTFOLIO_TREND_MIN_DAYS → 年化被抑制
    from ui.helpers.fund_grp_health.switch_advisor_section import render_portfolio_tracking
    import tests.test_ia_tracking_card_scope_caption as _t
    render_portfolio_tracking(_t._funds(40))


def _script_long():           # ≥ PORTFOLIO_TREND_MIN_DAYS → 年化照給
    from ui.helpers.fund_grp_health.switch_advisor_section import render_portfolio_tracking
    import tests.test_ia_tracking_card_scope_caption as _t
    render_portfolio_tracking(_t._funds(220))


@pytest.fixture()
def hermetic(monkeypatch):
    """切斷本卡的兩條外部 I/O（匯率、永久快照），讓測試不碰網路也不寫 Google Sheets。"""
    import services.hot_money_service as _hm
    monkeypatch.setattr(_hm, "fetch_usdtwd_frame", lambda *a, **k: (None, "test"), raising=False)
    import repositories.portfolio_perf_repository as _pr
    monkeypatch.setattr(_pr, "load_snapshots", lambda *a, **k: [], raising=False)
    monkeypatch.setattr(_pr, "append_snapshot", lambda *a, **k: None, raising=False)


def _run(script):
    at = AppTest.from_function(script, default_timeout=60)
    at.session_state["_perf_snapshot_done"] = True     # 不寫快照（本檔不測那條路）
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    return at


def _captions(at) -> str:
    return "\n".join(c.value for c in at.caption)


# ── 1. 兩張卡的關係一定要講出來（兩種天數都要有） ───────────────────────

@pytest.mark.parametrize("script", [_script_short, _script_long],
                         ids=["short_series", "long_series"])
def test_the_card_always_says_how_it_relates_to_the_other_perf_card(hermetic, script):
    """不論天數長短，都要告訴使用者「下方那張是同一套算式的另一個出口」。

    突變：把 `st.caption(_scope)` 整行刪掉 → 兩個 id 同時轉紅。
    """
    _caps = _captions(_run(script))
    assert "組合績效" in _caps, f"沒有指出同頁那張姊妹卡：{_caps!r}"
    assert "同一套算式" in _caps, f"沒有說明兩張卡同源（會被讀成兩個獨立答案）：{_caps!r}"
    assert "同名同義" in _caps, f"沒有點明三個重疊標籤是同名同義：{_caps!r}"


# ── 2. 短序列：「—」要被解釋成設計，不是故障 ─────────────────────────────

def test_short_series_actually_shows_a_dash_in_the_two_annualised_metrics(hermetic):
    """先確認前提為真：< 門檻時那兩欄真的是「—」（否則第 3 條在測空氣）。"""
    at = _run(_script_short)
    _by_label = {m.label: m.value for m in at.metric}
    assert _by_label.get("年化報酬") == "—", _by_label
    assert _by_label.get("年化波動 σ") == "—", _by_label
    # 這兩欄不受年化閘門影響，必須仍是實數 —— caption 也是這樣寫的。
    assert _by_label.get("期間累積報酬") not in (None, "—"), _by_label
    assert _by_label.get("最大回撤") not in (None, "—"), _by_label


def test_short_series_caption_explains_the_dash_is_by_design_not_a_fault(hermetic):
    """突變：刪掉 `if _t["annualized_suppressed"]:` 那段 → 本條轉紅。"""
    _caps = _captions(_run(_script_short))
    assert "—" in _caps, f"沒有提到「—」這個符號本身：{_caps!r}"
    assert "不是其中一張壞掉" in _caps, f"沒有明說這不是故障：{_caps!r}"
    assert "沒有這道門檻" in _caps, f"沒有解釋為何另一張仍有數字：{_caps!r}"
    # 不受閘門影響的兩欄要一併講清楚，否則使用者會以為整張卡都失效
    assert "期間累積報酬" in _caps and "最大回撤" in _caps, _caps


def test_long_series_does_not_claim_a_dash_that_is_not_there(hermetic):
    """天數足夠時不得出現「顯示『—』」那段 —— 那會是說謊（§1）。

    突變：把 `if _t["annualized_suppressed"]:` 改成無條件 → 本條轉紅。
    """
    at = _run(_script_long)
    _by_label = {m.label: m.value for m in at.metric}
    assert _by_label.get("年化報酬") != "—", _by_label      # 前提
    assert "不是其中一張壞掉" not in _captions(at), _captions(at)


# ── 3. 門檻數字必須來自 SSOT，不得手寫 ───────────────────────────────────

def test_the_threshold_number_comes_from_the_ssot_not_a_hand_typed_60(hermetic, monkeypatch):
    """把 SSOT 常數改掉 → caption 的數字必須跟著改。

    這是本檔唯一擋得住「有人手寫 60」的斷言：字串比對擋不住，因為手寫的 60
    和 SSOT 的 60 長得一模一樣。
    突變：把 caption 裡的 `{PORTFOLIO_TREND_MIN_DAYS}` 改成字面 `60` → 本條轉紅。

    ⚠️ 只改 `shared.signal_thresholds` 的值不會改變 `services.portfolio_tracking`
    的閘門行為（那邊是 module-level import），所以本條驗的是**caption 讀哪裡**，
    不是閘門本身 —— 閘門行為由上面第 2 組守。
    """
    import shared.signal_thresholds as _th
    monkeypatch.setattr(_th, "PORTFOLIO_TREND_MIN_DAYS", 77, raising=True)
    _caps = _captions(_run(_script_short))
    assert "77" in _caps, f"門檻沒有跟著 SSOT 走（疑似寫死）：{_caps!r}"


# ── 4. 顏色：灰色說明，不得升級成藍框/橘框 ───────────────────────────────

def test_the_scope_note_is_grey_not_info_or_warning(hermetic):
    """三態顏色分離：這是說明，不是警示、也不是故障。

    突變：把 `st.caption(_scope)` 改成 `st.info(...)` 或 `st.warning(...)` → 本條轉紅。
    """
    at = _run(_script_short)
    _caps = _captions(at)
    assert "同一套算式" in _caps                      # 它必須在 caption 通道裡
    _info = "\n".join(getattr(i, "value", "") for i in at.info)
    _warn = "\n".join(getattr(w, "value", "") for w in at.warning)
    assert "同一套算式" not in _info, f"範圍說明被畫成藍色 info：{_info!r}"
    assert "同一套算式" not in _warn, f"範圍說明被畫成橘色 warning：{_warn!r}"
