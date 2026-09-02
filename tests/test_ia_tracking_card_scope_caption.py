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
4. ⭐ **這行字說的是不是真的 —— 本檔只驗「關鍵詞在不在」，不驗「內容為真」。**
   **本 PR 的 `下方` 錯誤就是從這個洞掉下去的**：第一版 caption 兩次寫
   「**下方**「📊 組合績效」」，而那張卡實際渲染在**本頁最上面**
   （`_sec_add` 顯示位置 1/8，本卡 `_sec_switch` 是 5/8）。
   當時 7 條全綠 —— 因為每一條都只問「有沒有提到組合績效」，沒有一條問「方位對不對」。
   2026-09-02 稽核另外實證兩個同型的**沉默突變**：
   - **A6**：在 caption 尾端加回那句**已被撤回的假宣稱**
     「但兩者演算法不同,數字對不上是正常的。」→ 當時 **7 passed，零紅**。
   - **A7**：把「期間累積報酬與最大回撤**不受影響**」改成「**也一樣顯示「—」**」
     （與本檔另一條測試自己斷言的事實**直接矛盾**）→ 當時 **7 passed，零紅**。
   本輪已針對**這三個具體的假話**補上斷言（方位詞、A6、A7，見下方三條），
   ⚠️ **但那是三個點狀補丁，不是通用的「內容真偽」檢查** ——
   任何**新的**假陳述仍可能全綠通過。讀本檔請據此打折信任。
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


def _script_sister_card():    # ④ 既有的那張姊妹卡（用來驗 SSOT 名字對不對得上）
    from ui.helpers.portfolio_perf import render_portfolio_performance
    import tests.test_ia_tracking_card_scope_caption as _t
    render_portfolio_performance(_t._funds(220))


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


# ── 5. 姊妹卡的名字必須走 SSOT，不得手抄（漂移鎖） ───────────────────────

def _sister_card_heading_name() -> str:
    """姊妹卡**實際渲染出來**的標題，取「(」之前的名字部分。

    `### 📊 組合績效(固定權重・日再平衡假設・TWD 計價)` → `📊 組合績效`
    """
    at = AppTest.from_function(_script_sister_card, default_timeout=60)
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    _heads = [m.value for m in at.markdown if m.value.lstrip().startswith("#")]
    assert _heads, f"姊妹卡沒有渲染出任何標題：{[m.value for m in at.markdown]!r}"
    _h = _heads[0].lstrip("# ").strip()
    for _sep in ("(", "（"):
        _h = _h.split(_sep)[0]
    return _h.strip()


def test_the_ssot_label_still_matches_the_sister_cards_real_heading(hermetic):
    """SSOT 的 `pf_perf` 必須**精確等於**姊妹卡實際標題的名字部分。

    **為什麼要有這條**：2026-09-02 稽核突變 A8 —— 把「📊 組合績效」改名，
    當時 **40 passed、零紅**：caption 立刻變成死指路而沒有任何測試察覺。
    本 repo 的「指路指到不存在的東西」已經發作過三次。

    ⚠️ **必須是精確比對，不能用 `in`**：本條第一版就是寫 `label in heading`，
    結果 A8 改成「組合績效**表**」時**照樣綠燈**（原字串是新字串的子字串）。
    這個洞是本輪自己踩出來、自己補的。

    突變：把 `render_portfolio_performance` 的標題改名（不動 SSOT）→ 本條轉紅。
    """
    from ui.helpers.story_nav import section_label
    assert _sister_card_heading_name() == section_label("pf_perf"), (
        f"SSOT 的 '{section_label('pf_perf')}' 對不上姊妹卡實際標題的名字部分 "
        f"'{_sister_card_heading_name()}' —— 有人改名卻沒同步 SSOT，caption 已成死指路")


def test_the_caption_reads_the_label_from_the_ssot_not_a_hand_copy(hermetic, monkeypatch):
    """把 SSOT 的值換掉 → caption 顯示的名字必須跟著換。

    這是唯一擋得住「有人手抄『📊 組合績效』四個字」的斷言：手抄值與 SSOT 值
    **逐字相同**，所以純比對字串永遠分不出來（本條第一版就是這樣被 B1 突變騙過去的）。

    突變：把 caption 裡的 `section_label("pf_perf")` 換成手抄字面值 → 本條轉紅。
    """
    import ui.helpers.story_nav as _nav
    _sentinel = "🧪 姊妹卡哨兵名"
    monkeypatch.setitem(_nav._SECTION_LABELS, "pf_perf", _sentinel)
    _caps = _captions(_run(_script_long))
    assert _sentinel in _caps, f"caption 沒跟著 SSOT 走（疑似手抄字面值）：{_caps!r}"


# ── 6. 不准寫方位詞（本 PR 真的在這裡跌過一次） ──────────────────────────

_POSITIONAL = ("下方", "上方", "下面", "上面", "往下捲", "往上捲", "底下")


@pytest.mark.parametrize("script", [_script_short, _script_long],
                         ids=["short_series", "long_series"])
def test_the_caption_uses_no_positional_words(hermetic, script):
    """方位是 **slot 順序的函數**，寫進文案等於保證下一次重排就說謊。

    **實證**：本 caption 第一版寫了兩次「下方」，而姊妹卡其實在**上面**。
    ④ 的完整版面線框正在客戶端審批、很可能重排 —— 方位詞一律不准寫。

    突變：把任何一處改回「下方「📊 組合績效」」 → 本條轉紅。
    """
    _caps = _captions(_run(script))
    _hit = [w for w in _POSITIONAL if w in _caps]
    assert not _hit, f"caption 出現方位詞 {_hit} —— 版面一重排就會指錯：{_caps!r}"


# ── 7. 兩句已知假話不得復活（點狀補丁，非通用真偽檢查） ────────────────────

def test_caption_does_not_resurrect_the_retracted_algorithm_claim(hermetic):
    """堵稽核突變 A6：那句「兩者演算法不同」**已被實測推翻**，不得回到畫面上。

    兩張卡的數學收口到同一個 SSOT；≥ 門檻時三個同名指標數字完全相同。
    突變：在 caption 尾端加回「但兩者演算法不同,數字對不上是正常的。」→ 本條轉紅。
    """
    for _s in (_script_short, _script_long):
        _caps = _captions(_run(_s))
        assert "演算法不同" not in _caps, f"已撤回的假宣稱又出現在畫面上：{_caps!r}"


def test_caption_claim_about_unaffected_metrics_matches_the_real_values(hermetic):
    """堵稽核突變 A7：caption 說哪兩欄「不受影響」，就必須真的沒被打成「—」。

    這一條是**行為交叉比對**，不是純字串：先讀實際渲染出來的四個 metric 值，
    算出真正被打成「—」的集合，再要求 caption 的說法與它一致。
    突變：把「不受影響、仍是實數」改成「也一樣顯示「—」」→ 本條轉紅。
    """
    at = _run(_script_short)
    _by_label = {m.label: m.value for m in at.metric}
    _dashed = {k for k, v in _by_label.items() if v == "—"}
    _solid = {k for k, v in _by_label.items() if v != "—"}
    # 前提：短序列下只有兩個年化欄位被抑制
    assert _dashed == {"年化報酬", "年化波動 σ"}, _by_label
    assert _solid == {"期間累積報酬", "最大回撤"}, _by_label

    _caps = _captions(at)
    assert "不受影響" in _caps, (
        f"caption 沒有說那兩欄不受影響 —— 但它們實際上是實數 {_solid}：{_caps!r}")
    for _lbl in _solid:
        assert _lbl in _caps, f"caption 沒點名不受影響的「{_lbl}」：{_caps!r}"
