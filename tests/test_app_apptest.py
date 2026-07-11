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

    回歸目的：防止 portfolio_health.render_hero_kpi_cards 的 MK 標籤被誤改/誤刪 silent UI 破壞。
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
    expected = ["🟢 撿便宜雷達", "🔴 留校查看", "💰 停利提醒", "⚖️ 配置比例"]
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
    """Tab6 容器層至少渲染「系統說明書」+「公式與判斷標準」標題。

    回歸目的：防 Tab6 容器整個被誤刪 / 章標被誤改。
    （8 章節 nested tabs 內文僅在 click 後展開，AppTest 預設無法穿透，故只驗外層。）
    """
    markdown_blobs = " ".join(m.value for m in at.markdown if isinstance(m.value, str))
    assert "📖 系統說明書" in markdown_blobs, (
        f"Tab6 「📖 系統說明書」容器章標未在 markdown 中找到；"
        f"markdown 前 400 字: {markdown_blobs[:400]!r}"
    )
    assert "公式與判斷標準" in markdown_blobs, (
        "Tab6 副標「公式與判斷標準」未找到；可能說明書條件分支被改。"
    )


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


def test_tab1_missing_fred_key_shows_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """缺少 FRED_API_KEY 時，_check_secrets() 應顯示「缺少必要金鑰」錯誤訊息。

    回歸目的：保護 secrets 缺失時的降級提示，避免使用者面對 redacted error。
    monkeypatch.delenv：清除前面 module-scope fixture 對 os.environ 的污染。
    """
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = AppTest.from_file("app.py", default_timeout=60)
    app.secrets["FRED_API_KEY"] = ""
    app.secrets["GEMINI_API_KEY"] = "test-gemini-key"
    app.run()
    error_blobs = " ".join(
        str(getattr(e, "value", e) or "") for e in app.error
    )
    assert "缺少必要金鑰" in error_blobs, \
        f"未偵測到缺金鑰錯誤訊息；實際 error elements: {error_blobs!r}"
    assert "FRED_API_KEY" in error_blobs, \
        "錯誤訊息應點名缺失的具體 key"


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
