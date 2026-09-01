"""Streamlit AppTest headless e2e — runtime 層驗證。

不需要瀏覽器；用官方 streamlit.testing.v1.AppTest 模擬 session 渲染後抽出元素。
延長 default_timeout 因 app.py 初始化會跑 macro_engine 的指標載入流程。

第一個場景：Tab3 空組合進入時，必須顯示歡迎引導卡（關鍵字 "👋 歡迎"）。
回歸目的：防止「歡迎卡被誤刪/條件分支誤改」此類 silent UI 破壞。
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow  # 預設於 pre-commit 跳過，需 `pytest -m slow` 顯式執行

streamlit_testing = pytest.importorskip(
    "streamlit.testing.v1", reason="streamlit < 1.28 不支援 AppTest"
)
AppTest = streamlit_testing.AppTest


def _force_network_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """v19.340:讓本測試行程內所有外連秒收 ECONNREFUSED,測試回歸本旨(驗 UI 渲染)。

    背景:v19.340 修活 `fetch_fund_multi_source`(v19.248 起 NameError 秒死被吞)後,
    注入 mock 基金的 AppTest 在 tab3 健檢 ThreadPool 會對 mock 代碼**真打**多來源
    網路抓取 → CI 60s timeout。此前測試「跑得快」是騎在壞掉的 production 路徑上。
    對齊 stock repo v19.81 同類前例:proxy 指向 127.0.0.1:9(discard port,必
    ECONNREFUSED),requests/urllib 皆 trust_env → 全外連立即失敗走既有降級路徑。
    """
    for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.setenv(_pv, "http://127.0.0.1:9")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)


@pytest.fixture(scope="module", autouse=True)
def _no_hot_money_auto_refresh():
    """v19.342:tab1「>30 天自動補抓外資/USDTWD」在 AppTest 全程停用。

    該 data-only 補抓邏輯由 test_review_fixes_v19_342 單元測試覆蓋;AppTest
    每建一個 instance 都會觸發一次(session 全新 → is_stale=True),對
    FinMind/Yahoo 真打網路 — CI 引入不確定性、本地沙箱 proxy retry 累秒
    (同 v19.340 hermetic 原則:AppTest 只驗 UI 渲染,不外連)。
    module attr 直接替換(tab1 於 render 時 from-import,逐次讀 module attr)。
    """
    import ui.hot_money as _hm
    _orig = _hm.refresh_hot_money_data
    _hm.refresh_hot_money_data = lambda *a, **k: (False, "skipped in AppTest")
    yield
    _hm.refresh_hot_money_data = _orig


@pytest.fixture(scope="module")
def at() -> AppTest:
    """初始化一個共享 AppTest（單檔多測試共用以省 import 時間）。"""
    app = AppTest.from_file("app.py", default_timeout=60)
    app.secrets["FRED_API_KEY"] = "test-fred-key"
    app.secrets["GEMINI_API_KEY"] = "test-gemini-key"
    app.run()
    return app


def test_app_runs_without_exception(at: AppTest) -> None:
    """app.py 啟動到底，不可丟出未捕獲例外。"""
    assert not at.exception, f"app.py runtime exception: {[str(e) for e in at.exception]}"


def test_tab3_empty_portfolio_shows_welcome_card(at: AppTest) -> None:
    """portfolio_funds 初始為空 → 應渲染「👋 三步驟」引導條（v18.46 緊湊版）。"""
    markdown_blobs = " ".join(m.value for m in at.markdown if isinstance(m.value, str))
    assert ("👋 三步驟" in markdown_blobs) or ("👋 歡迎" in markdown_blobs), \
        "歡迎卡關鍵字「👋 三步驟 / 👋 歡迎」未出現；可能歡迎卡被誤刪或條件分支誤改"


def test_session_state_portfolio_funds_initialized(at: AppTest) -> None:
    """portfolio_funds 預設為空 list（Tab3 進入點期望條件）。"""
    pf = at.session_state["portfolio_funds"]
    assert pf == [], f"預期 portfolio_funds 初始為 []，實際: {pf!r}"


def _mock_loaded_fund(code: str = "0050", name: str = "元大台灣50",
                      base: float = 100.0, n_days: int = 400) -> dict:
    """構造一檔 loaded=True 的 mock 基金，給 Tab3 KPI / Tab5 重疊度測試共用。"""
    import numpy as np
    import pandas as pd
    rng = pd.date_range(end=pd.Timestamp.today().normalize(), periods=n_days, freq="B")
    np.random.seed(hash(code) & 0xFFFFFFFF)
    rets = np.random.normal(0.0005, 0.012, n_days)
    nav = base * (1 + rets).cumprod()
    series = pd.Series(nav, index=rng, name=code)
    last = float(series.iloc[-1])
    return {
        "code": code,
        "name": name,
        "series": series,
        "loaded": True,
        "load_error": None,
        "is_core": True,
        "policy_id": "P001",
        # v19.340:tab3 健檢 worker(process_one_fund)有 v19.180 設計的 fd 短路 —
        # portfolio_funds 帶 moneydj_raw 就跳過 auto_fetch_moneydj 真抓。原 mock
        # 缺此欄,v19.340 修活主聚合入口後健檢 ThreadPool 對 mock 代碼真打
        # 13-16 源網路 → AppTest 60s timeout(此前靠 NameError 秒死誤打誤撞地快)。
        # currency=TWD 同時走 tab2 v18.278 鏡像短路,不打 FX API → 全程零網路。
        "moneydj_raw": {
            "fund_code": code,
            "fund_name": name,
            "currency": "TWD",
            "series": series,
            "dividends": [],
            "nav_latest": last,
            "nav_date": str(series.index[-1])[:10],
        },
        "metrics": {
            "nav": last,
            "ret_1y": 8.5,
            "annual_div_rate": 4.2,
            "sharpe": 1.1,
            "std_1y": 12.0,
            "ret_1m": 1.5,
            "ret_3m": 3.8,
            "buy1": last * 0.95,
            "buy2": last * 0.90,
            "buy3": last * 0.85,
            "sell1": last * 1.05,
            "sell2": last * 1.10,
            "sell3": last * 1.15,
            "bb_upper": last * 1.05,
            "bb_lower": last * 0.95,
            "ma60": float(series.tail(60).mean()),
            "ret_3y": 25.0,
            "pos_label": "正常",
            "pos_color": "#888",
        },
    }


def test_tab3_with_mock_fund_renders_kpi_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    """注入一檔 loaded=True 的 mock 基金到 portfolio_funds → KPI 卡 label 應渲染。

    回歸目的：防止 portfolio_health.render_hero_kpi_cards 的 標籤被誤改/誤刪 silent UI 破壞。
    （v18.163 起頂部統一 hero KPI 取代舊長標籤 4 卡；舊版實作已於 v18.238 連同
     fund_json AI 工具組一併下架）
    """
    monkeypatch.setenv("FRED_API_KEY", "test-fred-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    _force_network_refused(monkeypatch)  # v19.340:防 tab3 健檢真打網路 timeout

    app = AppTest.from_file("app.py", default_timeout=60)
    app.secrets["FRED_API_KEY"] = "test-fred-key"
    app.secrets["GEMINI_API_KEY"] = "test-gemini-key"
    app.session_state["portfolio_funds"] = [_mock_loaded_fund()]
    app.run()

    assert not app.exception, \
        f"app.py runtime exception: {[str(e) for e in app.exception]}"

    metric_labels = [m.label for m in app.metric]
    # 「⚖️ 配置比例」→「⚖️ 核心/衛星檔數」：該卡是**檔數**口徑，改名以免與
    # 「① 配置總覽」的金額口徑「核心資產比例」混為一談（2026-08 稽核必修 4）。
    expected = ["🟢 撿便宜雷達", "🔴 留校查看", "💰 停利提醒", "⚖️ 核心/衛星檔數"]
    missing = [kw for kw in expected if kw not in metric_labels]
    assert not missing, \
        f"KPI 卡 label 缺失：{missing}；實際 metrics labels: {metric_labels!r}"


def test_tab5_overlap_button_click_renders_method_caption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """注入 2 檔同 policy_id 的 mock 基金 → 點「🔗 計算基金重疊度」→ 結果區應出現「計算方式」。

    回歸目的：防 T5 按鈕觸發 → calc_holdings_overlap/calc_correlation_matrix
    降級鏈 → st.session_state[corr_result_*] 寫入 → caption 渲染整條流程被破壞。
    """
    monkeypatch.setenv("FRED_API_KEY", "test-fred-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    _force_network_refused(monkeypatch)  # v19.340:防 tab3/tab5 健檢真打網路 timeout

    app = AppTest.from_file("app.py", default_timeout=60)
    app.secrets["FRED_API_KEY"] = "test-fred-key"
    app.secrets["GEMINI_API_KEY"] = "test-gemini-key"
    app.session_state["portfolio_funds"] = [
        _mock_loaded_fund(code="0050", name="元大台灣50"),
        _mock_loaded_fund(code="0056", name="元大高股息"),
    ]
    app.run()

    assert not app.exception, \
        f"app.py runtime exception: {[str(e) for e in app.exception]}"

    btn_key = "btn_corr_P001"
    found = [b for b in app.button if b.key == btn_key]
    assert found, \
        f"找不到 T5 重疊度按鈕 key={btn_key}；現有 buttons: {[b.key for b in app.button]!r}"

    found[0].click().run()
    assert not app.exception, \
        f"按鈕點擊後 runtime exception: {[str(e) for e in app.exception]}"

    info_blobs = " ".join(
        str(getattr(e, "value", e) or "") for e in app.info
    )
    err_blobs = " ".join(
        str(getattr(e, "value", e) or "") for e in app.error
    )
    combined = info_blobs + " " + err_blobs
    assert "計算方式" in combined, \
        f"未渲染「計算方式：」caption；infos+errors: {combined[:300]!r}"


def test_tab1_macro_not_loaded_shows_load_button_hint(at: AppTest) -> None:
    """Tab1 在 macro_done=False（初始狀態）→ 應渲染「載入總經資料」入口按鈕 / 提示。

    回歸目的：防止 sidebar 載入按鈕被誤刪、入口流程被破壞。
    （取代 v17.0 已廢棄的 view_mode L1/L2/L3 toggle 場景 — view_mode 固定為單軌完整版。）
    """
    button_labels = [b.label for b in at.button]
    info_blobs = " ".join(
        str(getattr(e, "value", e) or "") for e in at.info
    )
    has_load_button = any(("載入總經資料" in lbl) or ("更新總經資料" in lbl)
                          for lbl in button_labels if lbl)
    has_hint = ("尚未載入總經資料" in info_blobs) or ("點擊「載入總經資料」" in info_blobs)
    assert has_load_button or has_hint, \
        f"Tab1 載入入口未找到；buttons: {button_labels!r} infos: {info_blobs[:200]!r}"


# ════════════════════════════════════════════════════════════
# v18.104 進階場景（AppTest Phase A 6/7/8）：Tab2 搜尋 / Tab6 教學 / T7 帳本
# ════════════════════════════════════════════════════════════
def test_tab2_search_input_and_button_rendered(at: AppTest) -> None:
    """Tab2 應該渲染 MoneyDJ URL/代碼輸入欄 + 「🚀 分析」按鈕。

    回歸目的：防 v18.x 多次重構（auto_fetch / 境內外切換 / placeholder 改寫）
    造成搜尋入口 silent 消失 — 使用者進 Tab2 卻找不到任何輸入框/按鈕。
    """
    text_keys = [t.key for t in at.text_input]
    assert "mj_url_input" in text_keys, \
        f"Tab2 MoneyDJ URL/代碼輸入欄 (key=mj_url_input) 未找到；text_input keys: {text_keys!r}"

    btn_keys = [b.key for b in at.button]
    assert "btn_mj_load" in btn_keys, \
        f"Tab2 「🚀 分析」按鈕 (key=btn_mj_load) 未找到；button keys: {btn_keys!r}"


def test_tab6_manual_renders_key_sections(at: AppTest) -> None:
    """說明書容器層必須有標題 + 內文（防整塊被誤刪 / 章標被誤改）。

    ⚠️ **2026-09-01 就地更正：本行三個宣稱死了兩個半。有意識的更正，不是漏刪**
    （日期 **2026-09-01** · 決策者：**AI 總管** · 依據：**實測**，指令見下）::

        ~~（10 章節 nested tabs 內文僅在 click 後展開，AppTest 預設無法穿透，故只驗外層。）~~

    **舊表述在它寫下的當天是對的**：那時 `ui/tab6_manual.py` 確實用 `st.tabs`
    開了 10 個子分頁，內文只在點到該分頁時才渲染，「只驗外層」是誠實的自我設限。
    **被權衡掉的是它的時態，不是它的判斷** —— 它描述的那個載體**就是本 PR 拆掉的**
    （commit `10a8433`「說明書 10 個子分頁改單頁錨點目錄」）。
    **實測（2026-09-01，本行從實跑處照抄）**：
    `git grep -c -F ".tabs(" ffad4ca -- ui/tab6_manual.py` → **無輸出（0）**；
    同一指令對 `origin/main` → **1**。現況是**單頁 + 錨點目錄**，10 章一次全部渲染。

    ⚠️ **三個宣稱逐一對照 —— 不要因為「數字沒錯」就以為整句還活著**：
    ① 「**10 章節**」→ **仍然成立**（`ui.tab6_manual._CHAPTERS` 實測 10 章），
       本行唯一沒壞的字；
    ② 「**nested tabs** ／ 內文僅在 click 後展開 ／ AppTest 預設無法穿透」→ **全假**。
       沒有 tabs 就沒有 click，也就沒有「穿不穿得透」這個問題；
    ③ 「**故只驗外層**」→ **本函式自己就是反證**：下方 `markdown_blobs` 取
       `at.markdown + at.subheader + at.caption` 的聯集，它撈到的
       `⓪ 📊 資料來源完整地圖` 正是**內層**的章節標題。

    ⚠️ **這一處為什麼漏掉七輪，比這三句話本身更值得記**：**同一個函式的函式體裡**
    （下方 `markdown_blobs` 上面那段更正註解），由**同一次 commit** 寫下「說明書
    『10 子分頁 → 單頁錨點目錄』之後，章節標題…由 `st.markdown` 改成 `st.subheader`」
    —— 作者在同一個函式裡**描述了這個事實變更**，卻沒有回頭看自己這段 docstring。
    更關鍵的是**篩子選錯**：前六輪的自掃用「**這句是不是本 PR 寫的**」當納入判準，
    而本行由 `079c457`（早已在 main 上）寫入、由本 PR 打壞 ——
    **用「誰寫的」當篩子，正好會把它篩掉**。
    **正確判準是「是不是我這次的改動讓它不成立的」**（§-1.5.1c 判定 3）：
    「誰寫的」只是充分條件，「誰打壞的」才是必要條件。

    ⚠️ **本段刻意不寫「下方 N 行」這種行距數字** —— 它會被下一次編輯（包括本段
    自己這次插入）弄假，正是本 PR 反覆在修的同一種病；改用**不會漂移的錨點**
    （函式名／符號名）指位。

    ⚠️ **2026-08-31 由 WP-F 收斂：七 → 五。有意識的政策變更，不是漏改。**
    （日期 2026-08-31；決策者：**客戶 2026-08-31 拍板的五分頁動線線框**
    `docs/wireframes/fund-wireframe-final.html` §03）

    **舊斷言**（原地保留、加刪除線，不刪）::

        ~~assert "📖 系統說明書" in markdown_blobs~~
        ~~assert "公式與判斷標準" in markdown_blobs~~

    **舊斷言的理由仍然成立**：說明書整塊被誤刪、或章標被誤改，使用者會直接少掉
    一整頁而沒人發現 —— 這條就是那塊的存在性鎖。

    **被權衡掉的是「它去 `at.markdown` 找那一行 `##`」**：七→五之後說明書是
    「⑤ ⚙️ 設定與診斷」的分區，`ui/tab6_manual.py` 依 `MANUAL_HEADER` 旗標
    **讓掉自己那一行** `## 📖 系統說明書 — 公式與判斷標準完整說明`，改由 ⑤ 畫
    `st.subheader("📖 說明書")`。舊斷言找的那兩個字串**就長在同一行被讓掉的 `##` 上**。

    ⚠️ **這是「標題換位置」，不是「內容變少」—— 實測佐證（2026-08-31）**：
    同一次 AppTest run 裡，說明書內文（`資料來源完整地圖` / `六因` / `評等`）
    與它自己的 caption（`公式聖經`）**全部仍在**。本條把那三件事都驗進來，
    **覆蓋面是變大的**：舊寫法只驗一行 `##`，新寫法驗「⑤ 的分區標題」＋
    「說明書自己的 caption」＋「說明書內文」三段。

    ⚠️ 分區標題**從 SSOT 取**（`_SECTION_LABELS['manual']`），不在測試裡再抄一份。
    """
    from ui.helpers.story_nav import _SECTION_LABELS

    _want_head = _SECTION_LABELS["manual"]          # 「📖 說明書」
    _subs = [s.value for s in at.subheader if isinstance(s.value, str)]
    assert any(_want_head in s for s in _subs), (
        f"⑤ 沒有畫說明書分區標題「{_want_head}」；實際 subheader: {_subs!r}")

    _caps = " ".join(c.value for c in at.caption if isinstance(c.value, str))
    assert "公式聖經" in _caps, (
        "說明書自己的 caption（📖 故事附錄・公式聖經）不見了 —— "
        "本體可能整個沒被呼叫，不只是標題讓位。")

    # ⚠️ **2026-08-31 就地更正：草堆改對，針一字不動。有意識的更正，不是漏刪**
    # （決策者：AI 總管）。
    # ~~markdown_blobs = " ".join(m.value for m in at.markdown ...)~~
    # **舊寫法的理由仍然成立**：要驗的是「說明書內文還在」，把所有文字串起來
    # 找關鍵字是對的做法。**被權衡掉的是它只撈 `at.markdown` 這一種元素** ——
    # 說明書「10 子分頁 → 單頁錨點目錄」之後，章節標題（含本條找的
    # `⓪ 📊 資料來源完整地圖`）由 `st.markdown("### …")` 改成
    # `st.subheader(..., anchor=…)`：**元素換了型別，字沒有消失**。
    # 舊寫法會因為一次純渲染型別的搬遷而誤紅。
    # ⛔ **刻意不換掉、也不放寬 needle** —— `資料來源完整地圖` 這根針就是這條
    #    守衛的全部價值（章標被誤改／整塊被誤刪時它要紅）。換弱或刪掉才是放寬。
    # **三判準複驗（2026-08-31 實測）**：① 本寫法在 base `cc37709` 上也綠
    #    （那時標題還在 `at.markdown` 裡，聯集當然也撈得到）；② 突變「把
    #    `📊 資料來源完整地圖` 這個標題改名」→ 本條轉紅；③ 意圖保留（三根針全在）。
    markdown_blobs = " ".join(
        v for v in ([m.value for m in at.markdown]
                    + [h.value for h in at.subheader]
                    + [c.value for c in at.caption])
        if isinstance(v, str))
    assert "資料來源完整地圖" in markdown_blobs, (
        f"說明書內文（Section ⓪ 資料來源完整地圖）未找到；"
        f"markdown+subheader+caption 前 400 字: {markdown_blobs[:400]!r}")


def test_t7_ledgers_session_state_default_empty(at: AppTest) -> None:
    """T7 帳本 session_state["t7_ledgers"] 初始應為空 dict（lazy 初始化）。

    回歸目的：防 v18.x 多帳本管理重構造成 session_state 初始化 race condition —
    若初始未設為 dict 型，後續所有讀取（多處 .get("t7_ledgers", {}) 預期 dict）
    可能在某些路徑下撞 AttributeError。
    AppTest session_state 不支援 .get()；改用 in 判存在 + 索引取值。
    """
    if "t7_ledgers" in at.session_state:
        t7 = at.session_state["t7_ledgers"]
        assert isinstance(t7, dict), \
            f"t7_ledgers 應為 dict，實際 {type(t7).__name__} = {t7!r}"
    # 若未初始化 → lazy init 也算合法（app.py:6073-6074 會在 T7 進入點補上）


def test_t7_ledgers_with_seeded_ledger_survives_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """預先 seed 一筆 ledger → app.run() 後應仍保留（不被誤覆蓋）。

    回歸目的：T7 多帳本切換 / Sheet 同步流程不應在 startup 把使用者既有 ledger 清掉。
    """
    monkeypatch.setenv("FRED_API_KEY", "test-fred-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    app = AppTest.from_file("app.py", default_timeout=60)
    app.secrets["FRED_API_KEY"] = "test-fred-key"
    app.secrets["GEMINI_API_KEY"] = "test-gemini-key"
    seed = {"P001": [{"date": "2026-01-01", "code": "0050", "name": "元大台灣50",
                      "action": "BUY", "qty": 100.0, "price": 150.0,
                      "amount": 15000.0, "note": "seed"}]}
    app.session_state["t7_ledgers"] = seed
    app.run()

    assert not app.exception, \
        f"app.py runtime exception: {[str(e) for e in app.exception]}"
    assert "t7_ledgers" in app.session_state, \
        "app.run() 後 t7_ledgers key 不應消失"
    survived = app.session_state["t7_ledgers"]
    assert isinstance(survived, dict), \
        f"app.run() 後 t7_ledgers 不是 dict: {type(survived).__name__}"
    assert "P001" in survived, \
        f"seed 過的 P001 ledger 不應在 startup 被清掉；現存 keys: {list(survived.keys())!r}"


# ════════════════════════════════════════════════════════════
# v18.141 防退化：seed macro_done=True → 進入 calculate_composite_score 路徑
# 抓 PR #186-191 連環 NameError 等同類 cross-module reference 退化
# ════════════════════════════════════════════════════════════
def test_tab1_macro_done_seeded_renders_composite_without_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """seed `macro_done=True` + 最小 indicators / phase_info → app.run() 無例外。

    回歸目的：Tab1 主分支（macro_done=True）內呼叫 ui.helpers.macro_helpers 的
    `calculate_composite_score / composite_verdict / category_score /
    category_history` 與 ui.components.macro_card_edu 的 `MACRO_EDU`。
    這條路徑在預設 empty session（macro_done=False）下不會進入，故
    `test_app_runs_without_exception` 抓不到 — PR #186-191 連環 NameError 全
    都是在這分支內。本測試補上「macro_done=True 路徑可入無例外」防退化網。
    """
    monkeypatch.setenv("FRED_API_KEY", "test-fred-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    # v19.228 #6 F2 修補:test 用假 FRED key,渲染時 fred_get_next_release_date /
    # fetch_yf_close 等 fetcher 真實 hit NAS proxy 403 → retry 鏈每 series ~30s
    # → 240s 不夠。Mock 上游 fetcher 短路返回,讓 render path 純走 cache miss 0s。
    # 同時 patch shim attribute(類 B1 模式,caller 走 shim function-level lazy import)。
    import pandas as _pd
    from repositories.macro import fred as _fred_mod
    from repositories.macro import yf as _yf_mod
    from repositories import macro_repository as _shim
    _empty_df = lambda *a, **kw: _pd.DataFrame()
    _empty_s = lambda t, *a, **kw: _pd.Series(dtype=float, name=t)
    _none = lambda *a, **kw: None
    _empty_dict = lambda tickers: {t: None for t in tickers}
    for _mod in (_fred_mod, _yf_mod, _shim):
        monkeypatch.setattr(_mod, "fred_get_next_release_date", _none, raising=False)
        monkeypatch.setattr(_mod, "fetch_fred", _empty_df, raising=False)
        monkeypatch.setattr(_mod, "fetch_yf_close", _empty_s, raising=False)
        monkeypatch.setattr(_mod, "fetch_yf_latest", _empty_dict, raising=False)

    # macro_done=True 分支內含 23 指標卡 + 4 大類別 history + Sankey + KPI grid，
    # mock 後純 render path 應 < 60s,維持 240s 寬鬆預算
    app = AppTest.from_file("app.py", default_timeout=240)
    app.secrets["FRED_API_KEY"] = "test-fred-key"
    app.secrets["GEMINI_API_KEY"] = "test-gemini-key"

    # 4 大類別 23 指標最小可入 schema：每個指標只要 score / weight 兩 key
    # 缺值會被 calculate_composite_score 視為 0（fillna 等價），不影響測試
    _ind: dict = {}
    for _k in [
        "SAHM", "SLOOS", "PMI", "LEI", "YIELD_10Y2Y", "YIELD_10Y3M", "PPI",
        "COPPER", "ADL", "JOBLESS", "CONT_CLAIMS", "CONSUMER_CONF",
        "PERMIT_HOUSING", "CPI", "INFL_EXP_5Y", "FED_RATE", "UNEMPLOYMENT",
        "M2", "M2_WEEKLY", "FED_BS", "DXY", "HY_SPREAD", "VIX",
    ]:
        _ind[_k] = {"score": 0.5, "weight": 1.0, "value": 50.0, "date": "2026-05-15"}
    app.session_state["indicators"] = _ind
    app.session_state["phase_info"] = {
        "score": 6.5,
        "phase": "復甦",
        "phase_color": "#90EE90",
        "alloc": {"股票": 50, "債券": 30, "現金": 20},
        "advice": "test advice",
        "rec_prob": 0.15,
    }
    app.session_state["macro_done"] = True

    app.run()
    assert not app.exception, (
        f"Tab1 macro_done=True 路徑進入時 runtime exception: "
        f"{[str(e) for e in app.exception]}\n"
        f"  → 多半是 helper 漏 import（calculate_composite_score / MACRO_EDU 等）"
    )


def test_tab1_missing_fred_key_is_reported_as_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """缺少 FRED_API_KEY → 必須**點名這把 key**，而且用**灰色說明**、不是紅字。

    回歸目的（原意保留）：保護 secrets 缺失時的降級提示，避免使用者面對 redacted error。

    ⚠️ 2026-08-28 客戶拍板（線框 fund-empty-state-wireframe.html §03）：
    「未載入／未設定一律改灰色說明」—— 金鑰沒填是「你還沒設定」，不是「系統壞了」。
    原本每次開 App 最上方都是一條紅字，把真紅燈的份量稀釋掉。
    **有意識的政策變更，不是把測試改鬆**：斷言從一條變兩條，而且兩條方向相反 ——
      1. 有沒有講 → 灰色說明必須點名這把 key（**不釘文案**，只釘 key 名稱）；
      2. 用什麼顏色 → error / warning 兩種警示 widget 都**不得**出現這把 key。
    舊版只驗第 1 點的一個變形，且把文案「缺少必要金鑰」逐字釘死；
    現在文案可以改、顏色不能錯。

    monkeypatch.delenv：清除前面 module-scope fixture 對 os.environ 的污染。
    """
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = AppTest.from_file("app.py", default_timeout=60)
    app.secrets["FRED_API_KEY"] = ""
    app.secrets["GEMINI_API_KEY"] = "test-gemini-key"
    app.run()

    def _texts(elements) -> list[str]:
        return [str(getattr(e, "value", e) or "") for e in elements]

    # 「還沒設定」的語彙家族（SSOT 在 tests/test_render_state_color_separation.py，
    # 那支是全站規則；這裡只取用來認出「這一則講的是沒設定」）。
    not_configured = ("未設定", "未設置", "需設置", "尚未設定", "缺少必要金鑰")

    grey = _texts(app.caption)
    assert any("FRED_API_KEY" in t for t in grey), (
        "缺金鑰時必須用灰色說明點名缺的是哪一把；"
        f"實際 caption elements: {grey!r}"
    )

    # ⚠️ 逐則檢查，不能把全站 error/warning 串成一坨再搜 —— Tab5 的診斷區有一則
    # 合理的警示會提到 `FRED_API_KEY`（「連既有的 FRED_API_KEY 都讀不到 → 整份
    # secrets 沒生效」），那講的是**另一件事**（secrets 整份壞掉），不是「你還沒設定」。
    # 串起來搜會把它誤判成違規。判準是**同一則**裡同時出現「這把 key」和「還沒設定」。
    offenders = [t for t in _texts(app.error) + _texts(app.warning)
                 if "FRED_API_KEY" in t and any(p in t for p in not_configured)]
    assert not offenders, (
        "「還沒設定」不可畫成紅字／橘字 —— 那會稀釋真紅燈的份量（線框 §03）；"
        f"違規元素: {offenders!r}"
    )


# ════════════════════════════════════════════════════════════
# v18.142 防退化：Tab3 OAuth chain 互動 — _oauth_configured=True 分支可入無例外
# 對應 v18.140 OAuth 收口，補完 sys.modules['__main__'] hack 防退化網
# ════════════════════════════════════════════════════════════
def test_tab3_oauth_configured_branch_renders_without_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """monkeypatch `oauth_state._oauth_configured=True` → Tab3 OAuth-aware 分支
    可入無例外，未登入時應顯示「尚未登入 Google」info 提示。

    回歸目的：v18.140 把 5 個 OAuth helper（_oauth_configured / _resolve_oauth_cfg /
    _get_oauth_client / _gsa_secret / _sheet_id_secret）從 sys.modules['__main__']
    hack 改正規 import。預設 empty secrets 下 _oauth_configured=False，所以
    既有 test 抓不到 OAuth-aware 分支內 NameError（過去 PR #186 漏 import
    就是這條路徑）。本測試補上「_oauth_configured=True 分支可入無例外」防退化網。

    實作邊界：
    - oauth_state._oauth_configured 是 module-level 計算（讀 st.secrets 時 cache）
    - Tab3 的 `from ui.helpers.oauth_state import ...` 在 render fn 內，每次
      render 才綁定 → monkeypatch 模組屬性能被新一輪 render 讀到
    - 不 seed gsheet_tokens → _get_oauth_client() 安全回 None、不打網路
    """
    import ui.helpers.oauth_state as _oauth_mod
    # v18.148: tab3 / app.py 渲染前會呼叫 refresh_oauth_state() 重算 snapshot；
    # 若只 monkeypatch _oauth_configured / _oauth_cfg，refresh 會把它們清回 False。
    # 改 monkeypatch _resolve_oauth_cfg → refresh 自然把 module-level snapshot 設成 truthy。
    _mock_cfg = {
        "client_id": "mock-client-id",
        "client_secret": "mock-client-secret",
        "redirect_uri": "http://localhost:8501/",
    }
    monkeypatch.setattr(_oauth_mod, "_resolve_oauth_cfg", lambda: _mock_cfg)
    monkeypatch.setattr(_oauth_mod, "_oauth_configured", True)
    monkeypatch.setattr(_oauth_mod, "_oauth_cfg", _mock_cfg)
    monkeypatch.setenv("FRED_API_KEY", "test-fred-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    app = AppTest.from_file("app.py", default_timeout=120)
    app.secrets["FRED_API_KEY"] = "test-fred-key"
    app.secrets["GEMINI_API_KEY"] = "test-gemini-key"
    app.run()

    assert not app.exception, (
        f"Tab3 OAuth-aware 分支進入時 runtime exception: "
        f"{[str(e) for e in app.exception]}\n"
        f"  → 多半是 OAuth helper 漏 import 或 sys.modules hack 退化"
    )

    # 驗證確實進入 _oauth_configured=True 分支（未登入提示）
    info_blobs = " ".join(
        str(getattr(e, "value", e) or "") for e in app.info
    )
    assert "尚未登入 Google" in info_blobs or "🔐 用 Google 登入" in info_blobs, (
        f"未偵測到 _oauth_configured=True 未登入分支提示；"
        f"infos 前 400 字: {info_blobs[:400]!r}"
    )


# ════════════════════════════════════════════════════════════
# v18.148 防退化：refresh_oauth_state() — wizard 套用設定 no-op bug 修補單元
# ════════════════════════════════════════════════════════════
def test_refresh_oauth_state_updates_module_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v18.148: refresh_oauth_state() 重算 module-level _oauth_cfg / _oauth_configured。

    回歸目的：原本 `_oauth_cfg` 與 `_oauth_configured` 在 module import 時
    snapshot 一次；使用者透過 in-app wizard 寫 session_state 後 `st.rerun()`，
    snapshot 永遠 stale → 「💾 套用設定」按了沒反應、登入按鈕永遠不亮。
    本函式由 tab3 render 開頭 / app.py sidebar 渲染前呼叫以強制 re-resolve。
    """
    # v19.227 F1 修補:P2-7 shim `ui/helpers/oauth_state.py` 不穿透 sub-module
    # internal binding(類 B1 patch shim 不穿透 macro_repository 模式),
    # test 改直接走 sub-module `ui.helpers.io.oauth_state`。
    import ui.helpers.io.oauth_state as _osm

    # 1) 模擬 wizard 已寫入 session_state：refresh 後 _oauth_configured 應 True
    _truthy = {
        "client_id": "wizard-cid",
        "client_secret": "wizard-csec",
        "redirect_uri": "https://app.example.com/",
    }
    monkeypatch.setattr(_osm, "_resolve_oauth_cfg", lambda: _truthy)
    assert _osm.refresh_oauth_state() is True
    assert _osm._oauth_configured is True
    assert _osm._oauth_cfg == _truthy

    # 2) 模擬 secrets/session_state 都清空：refresh 應把 snapshot 回 False
    monkeypatch.setattr(_osm, "_resolve_oauth_cfg", lambda: None)
    assert _osm.refresh_oauth_state() is False
    assert _osm._oauth_configured is False
    assert _osm._oauth_cfg is None


# ════════════════════════════════════════════════════════════
# v18.143 防退化：Tab2 mk_fund_signal + _zh_holding 條件分支
# 對應 v18.139 Tab2 sys.modules hack 清理，補完三 tab 防退化網
# ════════════════════════════════════════════════════════════
def test_tab2_loaded_fund_with_macro_renders_mk_signal_without_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """seed `fund_data` (status=ok + series + metrics) + `macro_done=True` →
    Tab2 進 success render 分支，呼叫 mk_fund_signal / _quartile_check /
    _zh_holding，assert 無例外 + 「總經自動配比建議」配比卡渲染。

    回歸目的：Tab2 success render 分支（line 335+）只在「成功載入基金 +
    macro_done」雙條件下才進入；既有 test_tab2_search_input_and_button_rendered
    只驗輸入欄位、不進這分支。本測試補上「fd success render + mk_fund_signal +
    auto_alloc」防退化網（v18.139 sys.modules cleanup 對應）。
    """
    import pandas as pd

    monkeypatch.setenv("FRED_API_KEY", "test-fred-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    app = AppTest.from_file("app.py", default_timeout=180)
    app.secrets["FRED_API_KEY"] = "test-fred-key"
    app.secrets["GEMINI_API_KEY"] = "test-gemini-key"

    # 構造 NAV 序列（400 日）
    _idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=400, freq="B")
    _nav = pd.Series(
        [100.0 * (1 + 0.0003 * i) for i in range(400)],
        index=_idx, name="TEST001"
    )

    # 1. macro_done=True + indicators (mk_fund_signal 會讀 PMI / VIX 算 auto_alloc)
    app.session_state["macro_done"] = True
    app.session_state["indicators"] = {
        "PMI": {"score": 1.0, "weight": 1.0, "value": 52.0, "date": "2026-05-15"},
        "VIX": {"score": 1.0, "weight": 1.0, "value": 18.0, "date": "2026-05-15"},
        "UNEMPLOYMENT": {"score": 0.0, "weight": 1.0, "value": 3.8, "date": "2026-05-15"},
        "CPI": {"score": 0.0, "weight": 1.0, "value": 2.5, "prev": 2.6,
                "date": "2026-05-15"},
    }
    app.session_state["phase_info"] = {
        "score": 6.5,
        "phase": "復甦",
        "phase_color": "#90EE90",
        "alloc": {"股票": 50, "債券": 30, "現金": 20},
        "advice": "test",
        "rec_prob": 0.10,
    }

    # 2. fund_data 進 Tab2 success render 分支需要 status + series + metrics
    app.session_state["fund_data"] = {
        "status": "ok",
        "full_key": "TEST001",
        "fund_name": "Test Fund 收益基金",   # name 含「收益」→ is_core=True
        "series": _nav,
        "dividends": [],
        "metrics": {
            "nav_latest": 112.0,
            "ret_1y": 8.5,
            "ret_3y": 25.0,
            "annual_div_rate": 4.2,
            "sharpe": 1.1,
            "std_1y": 12.0,
            "bb_upper": 115.0,
            "bb_lower": 105.0,
            "ma60": 110.0,
        },
        "moneydj_raw": {},
        "page_type": "yp010000",
        "error": "",
        "warning": "",
    }

    app.run()
    assert not app.exception, (
        f"Tab2 success render 分支進入時 runtime exception: "
        f"{[str(e) for e in app.exception]}\n"
        f"  → 多半是 mk_fund_signal / _zh_holding helper 漏 import 退化"
    )

    # 驗證確實進到 mk_fund_signal 分支：「總經自動配比建議」配比卡會渲染
    markdown_blobs = " ".join(
        m.value for m in app.markdown if isinstance(m.value, str)
    )
    assert "總經自動配比建議" in markdown_blobs, (
        f"未偵測到 mk_fund_signal auto_alloc 配比卡渲染；"
        f"markdown 前 500 字: {markdown_blobs[:500]!r}"
    )


def test_tab2_nav_source_banner_shows_data_source_and_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v19.283 — Tab2「① 基本資料」banner 應顯示 NAV 來源 + 跨度。

    背景：user 反饋 TLZF9 顯示「成立 0.1 年」卻查不到「資料存放位置」；
    根因是 `_fetch_fund_single`（repositories/fund/fund_orchestration.py）
    已算好 `data_source` / `nav_span_days` 存進 result，但 UI 從未顯示，
    print() log 又進不了 user 視野。本測試守：`moneydj_raw` 帶這兩個既有
    欄位時，Tab2 banner 必須把它們攤出來（純讀取顯示，不重算，對齊 SSOT）。
    """
    import pandas as pd

    monkeypatch.setenv("FRED_API_KEY", "test-fred-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    app = AppTest.from_file("app.py", default_timeout=180)
    app.secrets["FRED_API_KEY"] = "test-fred-key"
    app.secrets["GEMINI_API_KEY"] = "test-gemini-key"

    _idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=400, freq="B")
    _nav = pd.Series(
        [100.0 * (1 + 0.0003 * i) for i in range(400)],
        index=_idx, name="TLZF9",
    )

    app.session_state["macro_done"] = False
    app.session_state["fund_data"] = {
        "status": "ok",
        "full_key": "TLZF9",
        "fund_name": "安聯收益成長基金",
        "series": _nav,
        "dividends": [],
        "metrics": {"nav_latest": 112.0, "sharpe": 1.1, "std_1y": 12.0},
        # v19.281 span-extend 命中後,_fetch_fund_single 會把這兩欄寫進 result
        # (= moneydj_raw)。此處模擬「已命中長歷史」情境。
        "moneydj_raw": {
            "data_source": "morningstar(span-extend)",
            "nav_span_days": 1825,
        },
        "page_type": "yp010001",
        "error": "",
        "warning": "",
    }

    app.run()
    assert not app.exception, (
        f"runtime exception: {[str(e) for e in app.exception]}"
    )
    markdown_blobs = " ".join(
        m.value for m in app.markdown if isinstance(m.value, str)
    )
    success_blobs = " ".join(
        str(getattr(m, "value", "")) for m in app.success
    )
    blob = markdown_blobs + " " + success_blobs
    assert "morningstar(span-extend)" in blob, (
        f"banner 應顯示 data_source；"
        f"success/markdown 前 500 字: {blob[:500]!r}"
    )
    assert "跨度 1825" in blob, (
        f"banner 應顯示 nav_span_days；"
        f"success/markdown 前 500 字: {blob[:500]!r}"
    )
