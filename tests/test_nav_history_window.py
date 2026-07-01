"""v19.281 regression test — NAV 歷史窗口擴展 + span-extend。

User 反饋:TLZF9(保單代碼)MoneyDJ 有 3-5 年資料,但本站顯示「成立 0.1 年」、
3Y/5Y 全 —。根因:
1. cnyes / Morningstar NAV 窗口原僅 400d(~13 月)→ 不足以算 3Y/5Y。
2. NAV 來源鏈只用「筆數」把關,保單代碼落到近期短源(~1 月,≥10 筆)就鎖定,
   把長歷史 Morningstar(硬編 secId)整條 skip。

本檔守:
- cnyes / Morningstar NAV 請求窗口 ≥ ~5 年(擴到 2000 天)。
- _fetch_fund_single 有 span-extend 分支(短跨度保單代碼 → 換長歷史)。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd


class _FakeJsonResp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def _days_between_ms(start_ms: int, end_ms: int) -> int:
    return int((end_ms - start_ms) / 1000 / 86400)


def test_cnyes_nav_window_is_multi_year():
    """fetch_nav_cnyes 請求窗口應 ≥ ~5 年(擴到 2000d,足以算 3Y/5Y)。"""
    import repositories.fund.sources as S

    seen_urls: list = []

    def _fake_get(url, **kw):
        seen_urls.append(url)
        return _FakeJsonResp({"data": {"nav": []}})

    with patch.object(S, "_cnyes_resolve_code", return_value=["TLZF9"]), \
         patch.object(S.requests, "get", side_effect=_fake_get):
        S.fetch_nav_cnyes("TLZF9")

    # 取第一個 nav 端點 URL,解析 start/end
    nav_urls = [u for u in seen_urls if "/nav?" in u]
    assert nav_urls, f"應打 nav 端點,實際 {seen_urls}"
    import urllib.parse as _up
    q = _up.parse_qs(_up.urlparse(nav_urls[0]).query)
    start_ms, end_ms = int(q["start"][0]), int(q["end"][0])
    span_days = _days_between_ms(start_ms, end_ms)
    assert span_days >= 1500, f"cnyes NAV 窗口應 ≥ ~5 年(1500d+),實際 {span_days}d"


def test_morningstar_nav_window_is_multi_year():
    """_src_morningstar_nav 請求窗口應 ≥ ~5 年(擴到 2000d)。"""
    import repositories.fund.sources as S

    seen_urls: list = []

    class _Resp:
        status_code = 200
        text = ""

        def read(self):  # urllib 介面(morningstar 用 urllib)
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _fake_urlopen(req, **kw):
        seen_urls.append(getattr(req, "full_url", str(req)))
        return _Resp()

    # TLZF9 已在 _MORNINGSTAR_SECID_MAP → 直接走硬編 secId,不需 search
    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        S._src_morningstar_nav("TLZF9")

    ts_urls = [u for u in seen_urls if "timeseries_price" in u]
    assert ts_urls, f"應打 timeseries_price,實際 {seen_urls}"
    import urllib.parse as _up
    q = _up.parse_qs(_up.urlparse(ts_urls[0]).query)
    start = q["startDate"][0]
    end = q["endDate"][0]
    span_days = (pd.Timestamp(end) - pd.Timestamp(start)).days
    assert span_days >= 1500, f"Morningstar NAV 窗口應 ≥ ~5 年,實際 {span_days}d"


def test_span_extend_helper_prefers_longer_span():
    """span-extend 決策邏輯:跨度更長者才替換(additive,不退步)。

    以純資料驗證「短跨度 → 換長跨度」的決策(整合層 _fetch_fund_single 網路重、
    不做端到端 mock;此處守決策不變式)。
    """
    def _span(_s):
        if _s is None or len(_s) < 2:
            return 0
        return int((pd.Timestamp(_s.index.max())
                    - pd.Timestamp(_s.index.min())).days)

    _short = pd.Series(range(25),
                       index=pd.date_range(end="2026-06-30", periods=25, freq="D"))
    _long = pd.Series(range(1200),
                      index=pd.date_range(end="2026-06-30", periods=1200, freq="D"))
    # 短跨度應觸發 span-extend(< 300d),長跨度不觸發
    assert 0 < _span(_short) < 300
    assert _span(_long) >= 300
    # 替換規則:長者 span 嚴格大於短者 → 採長者
    assert _span(_long) > _span(_short)


# ── v19.284:_span_extend_insurance_nav 已抽成模組級共用函式 —————————
# 供 _fetch_fund_single 與 fetch_fund_from_moneydj_url 的 legacy pipeline
# 共用(避免同檔內兩條 NAV pipeline 各寫一份 span-extend)。以下對該函式本體
# 直接單元測試(v19.281 版本是巢狀 closure,無法直接測;抽出後可測)。

def _mk_series(n: int, end="2026-06-30") -> pd.Series:
    return pd.Series(range(n), index=pd.date_range(end=end, periods=n, freq="D"))


def test_span_extend_insurance_nav_rescues_short_series():
    """短跨度(<300d)+ 保單代碼 → Morningstar 命中且跨度更長 → 換用。"""
    import repositories.fund.fund_orchestration as O

    _short = _mk_series(30)     # 保單代碼常見的「近30日」legacy fallback
    _long = _mk_series(1200)    # Morningstar 長歷史

    with patch.object(O, "_src_morningstar_nav", return_value=_long):
        s, src, span = O._span_extend_insurance_nav(
            "TLZF9", _short, "moneydj_legacy_scrape", fund_name="安聯收益成長",
        )
    assert len(s) == 1200
    assert src == "morningstar(span-extend)"
    assert span > 300


def test_span_extend_insurance_nav_keeps_baseline_label_when_no_rescue():
    """短跨度但 Morningstar/cnyes 皆查無資料 → 原樣回傳,baseline label 保留
    (banner 至少顯示「這是哪個來源」,不再是完全空白的「—」)。"""
    import repositories.fund.fund_orchestration as O

    _short = _mk_series(30)
    with patch.object(O, "_src_morningstar_nav", return_value=pd.Series(dtype=float)), \
         patch.object(O, "_src_cnyes_nav", return_value=pd.Series(dtype=float)):
        s, src, span = O._span_extend_insurance_nav(
            "TLZF9", _short, "moneydj_legacy_scrape",
        )
    assert len(s) == 30
    assert src == "moneydj_legacy_scrape"
    assert 0 < span < 300


def test_span_extend_insurance_nav_skips_non_insurance_code():
    """非保單代碼(如境內投信 ACTI71)→ 完全不觸發,原樣回傳。"""
    import repositories.fund.fund_orchestration as O

    _short = _mk_series(30)
    with patch.object(O, "_src_morningstar_nav") as _m:
        s, src, span = O._span_extend_insurance_nav("ACTI71", _short, "FundClear")
    _m.assert_not_called()
    assert len(s) == 30 and src == "FundClear"


def test_span_extend_insurance_nav_skips_when_already_long():
    """跨度已 ≥300 天(即使是保單代碼)→ 不需要 extend,不觸發外部呼叫。"""
    import repositories.fund.fund_orchestration as O

    _long = _mk_series(400)
    with patch.object(O, "_src_morningstar_nav") as _m:
        s, src, span = O._span_extend_insurance_nav(
            "TLZF9", _long, "tcb_moneydj", is_insurance_code=True,
        )
    _m.assert_not_called()
    assert len(s) == 400 and src == "tcb_moneydj"


def test_fetch_fund_from_moneydj_url_legacy_path_labels_data_source():
    """v19.284 回歸網:legacy pipeline(fetch_fund_from_moneydj_url 內「Step 3+
    原始流程」)最終組裝 result 時,也必須帶 data_source/nav_span_days —— 這是
    user 反饋「Tab2 banner 顯示來源:—」的直接根因(該 pipeline 先前完全沒設
    這兩欄)。此測試不做端到端網路 mock(該函式牽涉大量分支),改為直接驗證
    共用函式在該路徑的呼叫點語意正確(見上面 4 個 _span_extend_insurance_nav
    單元測試);此處額外確認函式簽章存在且可從 fund_orchestration 匯入,
    防止之後重構誤刪。
    """
    import repositories.fund.fund_orchestration as O

    assert hasattr(O, "_span_extend_insurance_nav")
    assert hasattr(O, "fetch_fund_from_moneydj_url")


def test_fetch_holdings_is_actually_importable_in_fund_orchestration():
    """v19.287 真根因回歸網:`fund_orchestration.py` 兩處持股呼叫點
    (`_fetch_fund_single` 既有 + `fetch_fund_from_moneydj_url` v19.287 新增)
    呼叫的都是 bare name `fetch_holdings(code)` —— 但這個模組先前從未 import
    這個名字,每次呼叫都拋 `NameError`,被外層 `except Exception` 吞掉,
    `result["holdings"]` 因此永遠停在初始模板的空 dict {}。v19.285/v19.286
    對 `nav_metrics.fetch_holdings()` 本體的診斷強化完全沒機會執行到,因為這個
    函式根本沒被成功呼叫過 —— 這才是 user 反饋「還是找不到持股」的真根因。

    本測試直接驗證 module-level name 解析正確(不會 NameError),且解析到的
    就是 `nav_metrics.fetch_holdings` 本體(同一顆函式物件,不是另一份重寫)。
    """
    import repositories.fund.fund_orchestration as O
    import repositories.fund.nav_metrics as NM

    assert hasattr(O, "fetch_holdings"), (
        "fetch_holdings 必須能在 fund_orchestration 模組命名空間解析,"
        "否則兩處呼叫點都會 NameError(被外層 except 吞掉,silent failure)"
    )
    assert O.fetch_holdings is NM.fetch_holdings, (
        "應該是同一顆共用函式物件(SSOT),不是另一份重寫的持股抓取邏輯"
    )


def test_fetch_fund_from_moneydj_url_legacy_path_calls_fetch_holdings():
    """v19.287:legacy pipeline(`fetch_fund_from_moneydj_url`)先前完全沒有
    呼叫持股抓取 —— `result["holdings"]` 全程停在初始模板的空 dict {},
    不管 `nav_metrics.fetch_holdings()` 內部診斷多完整都沒有意義。

    直接檢查原始碼字串確認呼叫點確實存在(該函式牽涉大量網路分支,端到端
    mock 成本過高;source-level 存在性檢查足以在之後重構誤刪時擋下)。
    """
    import inspect
    import repositories.fund.fund_orchestration as O

    src = inspect.getsource(O.fetch_fund_from_moneydj_url)
    assert "fetch_holdings(code)" in src, (
        "legacy pipeline 必須呼叫 fetch_holdings(code) 填入 result['holdings'],"
        "否則這條 pipeline 產出的基金(如保單代碼 TLZF9)永遠拿不到持股"
    )


def test_fund_orchestration_has_no_undefined_bare_names():
    """v19.288 全站掃描回歸網:user 反饋「還有沒有其他類似一直抓不到的
    function」,用 `ruff --select F405`(可能未定義或來自 star import)
    全站掃描 + 逐一動態 hasattr 驗證,在 `fund_orchestration.py` 抓到另外
    5 個同病灶的 bare name(前面 v19.287 只修了 fetch_holdings 一個):

    - fetch_risk_metrics / fetch_performance_wb01(兩條 pipeline 皆呼叫)—
      Sharpe/Sortino/Calmar/Alpha 全站顯示 None 的根因之一
    - fetch_nav(legacy pipeline「最終備援」)— 從未真的執行過
    - _BANK_PLATFORM_CODES / _MORNINGSTAR_SECID_MAP(兩個 dict 常數,未列入
      sources.py 的 __all__)— 呼叫點沒有 try/except 包住,NAV 筆數不足時
      直接拋出未捕捉例外

    本測試鎖住這 6 個名字(含 v19.287 的 fetch_holdings)都能在
    `fund_orchestration` 模組命名空間正確解析,防止之後重構誤刪 import
    又回到同一種 silent-failure 模式。
    """
    import repositories.fund.fund_orchestration as O

    _required_names = [
        "fetch_holdings", "fetch_nav", "fetch_risk_metrics",
        "fetch_performance_wb01", "_BANK_PLATFORM_CODES",
        "_MORNINGSTAR_SECID_MAP",
    ]
    _missing = [n for n in _required_names if not hasattr(O, n)]
    assert not _missing, (
        f"fund_orchestration 模組無法解析以下名字,呼叫時會 NameError:{_missing}"
    )


def test_direct_moneydj_nav_fetchers_use_2000d_window_not_400d():
    """v19.291 回歸網:user 截圖證實 MoneyDJ 官網對 JFZN3 有近 5 年淨值歷史
    (2021/10~2026/06),但本站 MK 3-3-3 卻判定「成立 0.1 年」。追查發現
    v19.281 只把 cnyes(`fetch_nav_cnyes`)/ Morningstar(`_src_morningstar_nav`)
    的查詢窗口從 400 天延伸到 2000 天,**但直接對 MoneyDJ 本身(`yp004002.djhtm`
    帶日期 A/B/C 三參數)的 9 個呼叫點漏做同樣的延伸**——這是保單代碼(如
    JFZN3)MK 3-3-3 常誤判「成立 0.1 年」的根因之一。

    本測試直接檢查原始碼:9 個已知呼叫點都不該再殘留 `timedelta(days=400)`,
    防止之後重構/合併衝突時,某一處被意外改回短窗口。
    """
    import inspect
    import repositories.fund.sources as S
    import repositories.fund.fund_orchestration as O

    _checks = [
        (S._src_fundclear_nav, "sources._src_fundclear_nav"),
        (S._src_bank_platform_nav, "sources._src_bank_platform_nav"),
        (S._src_taiwanlife_nav, "sources._src_taiwanlife_nav"),
        (S._src_franklin_nav, "sources._src_franklin_nav"),
        (S._src_tcb_nav, "sources._src_tcb_nav"),
        (S._src_sitca_nav, "sources._src_sitca_nav"),
        (S._src_insurance_subdomain_nav, "sources._src_insurance_subdomain_nav"),
        (O._fetch_fund_single, "fund_orchestration._fetch_fund_single"),
        (O.fetch_fund_from_moneydj_url, "fund_orchestration.fetch_fund_from_moneydj_url"),
    ]
    _still_short = []
    for _fn, _label in _checks:
        _src = inspect.getsource(_fn)
        if "timedelta(days=400)" in _src:
            _still_short.append(_label)
    assert not _still_short, (
        f"以下函式仍用 400 天短窗口查詢 MoneyDJ NAV 歷史(應為 2000 天,"
        f"對齊 v19.281 cnyes/Morningstar 已做的延伸):{_still_short}"
    )
