"""repositories/fund/fund_orchestration.py — v19.200 P1-5 主編排 + search。

從 fund_repository 主檔抽出(原 line 2452-3554):
- _fetch_fund_single / _finish_metrics
- fetch_fund_from_moneydj_url
- search_fundclear / search_moneydj_by_name / _parse_nav_html

(fetch_fund_multi_source 留在 sources.py,邏輯上是 source dispatcher。)
"""
from __future__ import annotations

import re
import requests
import pandas as pd
from bs4 import BeautifulSoup

from infra.cache import (  # noqa: F401
    _ttl_cache, register_cache, _CACHE_DIR, _FUND_SNAPSHOT, _cache_path,
    _cache_load_nav, _cache_save_nav, _cache_load_div, _cache_save_div,
    _cache_load_meta, _cache_save_meta,
)
from shared.fred_series import FRED_CHF_USD, FRED_CNH_USD, FRED_EUR_USD, FRED_JPY_USD
from shared.ttls import TTL_5MIN, TTL_15MIN, TTL_30MIN
from shared.signal_thresholds import NAV_SHORT_WINDOW_MAX_DAYS
from fund_fetcher import (  # noqa: F401
    safe_float, fetch_url_with_retry, is_valid_moneydj_page,
    HDR, HDR_JSON, PORTAL_CFG, TCB_BASE, _INSURANCE_SUBDOMAIN_HINTS,
    normalize_result_state, merge_non_empty, classify_fetch_status,
    _is_empty_value,
)
from infra.proxy import _proxies, _ssl_verify  # noqa: F401
# v19.240 R8 EX-L1ORCH-1 退役:calc_metrics + reconcile + perf 注入業務邏輯已上提
# 至 services.fund_service.finalize_fund_metrics + 2 enriched wrapper。本層
# 只回 raw result(metrics 由 L2 wrapper 補)。

from repositories.fund.sources import *  # noqa: F401, F403 — 所有 _src_* re-export
# v19.287/v19.288 真根因:ruff --select F405 全站掃描 + 逐一動態驗證(import
# 模組後 hasattr 檢查)發現本模組共 4 個 bare name 呼叫從未真的被 import,每次
# 呼叫都拋 NameError:
# - fetch_holdings(v19.287 已修):`result["holdings"]` 永遠停在空 dict {}
# - fetch_risk_metrics / fetch_performance_wb01(兩條 pipeline 皆呼叫):
#   `result["risk_metrics"]` / `result["perf"]` wb01 覆蓋從未真的執行過 ——
#   Sharpe/Sortino/Calmar/Alpha 全站顯示 None 的根因之一
# - fetch_nav(legacy pipeline「最終備援：完整 TCB 多路徑爬取」):從未真的執行過
# 以上 4 者呼叫點外層皆有 `except Exception: print(...)`,例外被完整吞掉,
# 診斷強化(v19.285/v19.286)完全沒機會執行到。此 import 補上後才會真的呼叫到
# nav_metrics 本體。
from repositories.fund.nav_metrics import (
    fetch_holdings, fetch_nav, fetch_performance_wb01, fetch_risk_metrics,
)


def _nav_span_days(_s) -> int:
    """NAV Series 首末日跨度(天)。空/單筆回 0。純函式,不吃 IO。"""
    try:
        if _s is None or len(_s) < 2:
            return 0
        return int((pd.Timestamp(_s.index.max())
                    - pd.Timestamp(_s.index.min())).days)
    except Exception:
        return 0


def _span_extend_insurance_nav(
    code: str, nav_s: pd.Series, nav_source: str,
    fund_name: str = "", is_insurance_code: "bool | None" = None,
) -> "tuple[pd.Series, str, int]":
    """v19.281/v19.284 SSOT:短跨度保單代碼 NAV → 試 Morningstar / cnyes 長歷史。

    背景:本檔內有**兩條獨立 NAV pipeline**——`_fetch_fund_single`(多來源
    waterfall)與 `fetch_fund_from_moneydj_url` 內的 legacy 直接爬蟲(當前者
    `_s_ok`/`_m_ok` 判斷失敗時的 fallback,見該函式「Step 3+ 原始流程」)。
    兩者都只用「筆數 ≥10/20」把關,無跨度檢查,保單代碼(如 TLZF9)常被短源
    (近30日、~1 月)搶先鎖定,長歷史 Morningstar 永遠沒機會補救。

    抽成本共用函式,**兩條 pipeline 都呼叫同一份**(而非各寫一份 span-extend),
    對齊 SSOT。additive:只在「短跨度 + 保單代碼」時嘗試,只換「跨度更長」者,
    不影響其餘 case。

    回傳 (nav_s, nav_source, span_days) — 未觸發時原樣回傳(nav_source 不變)。
    """
    _code = (code or "").upper().strip()
    if is_insurance_code is None:
        is_insurance_code = (not _is_domestic_code(_code) and
                             any(_code.startswith(p) for p in _INSURANCE_SUBDOMAIN_HINTS))

    _cur_span = _nav_span_days(nav_s)
    if is_insurance_code and 0 < _cur_span < 300:
        _long_candidates = (
            ("morningstar",
             lambda: _src_morningstar_nav(_code, fund_name=fund_name or "")),
            ("cnyes", lambda: _src_cnyes_nav(_code)),
        )
        for _long_src, _long_fn in _long_candidates:
            try:
                _cand = _long_fn()
            except Exception as _le:
                print(f"[orchestrator] span-extend {_long_src} 失敗: {_le}")
                _cand = pd.Series(dtype=float)
            if (_cand is not None and len(_cand) >= 10
                    and _nav_span_days(_cand) > _cur_span):
                print(f"[orchestrator] 📏 {_code} span-extend "
                      f"{nav_source}({_cur_span}d/{len(nav_s)}筆) → "
                      f"{_long_src}({_nav_span_days(_cand)}d/{len(_cand)}筆)")
                nav_s = _cand
                nav_source = f"{_long_src}(span-extend)"
                _cur_span = _nav_span_days(_cand)
    return nav_s, nav_source, _cur_span


def _effective_nav_len(s: "pd.Series | None") -> int:
    """NAV 序列的**有效**筆數:唯一日期 × 非 NaN × > 0。

    2026-08-11:`_adopt_if_better` 若只比 `len()`,「40 筆但只有 20 個唯一日期」
    或「50 筆全 NaN」的髒序列會**贏過** 30 筆乾淨序列,而下游 metrics 全吃 NaN
    —— 那是 §1 意義上更糟的失敗(看起來成功、通過所有既有不變量斷言)。
    本函式把 §3.1「date unique」+ §3.2「NAV > 0」+ §4.2 三條不變量收進比較基準。
    """
    if s is None:
        return 0
    try:
        _v = pd.Series(s).dropna()
        _v = _v[_v > 0]
        return int(_v.index.nunique()) if len(_v) else 0
    except Exception as _e:  # noqa: BLE001 — §1 不靜默:記 log 後當 0 筆處理
        print(f"[orchestrator] _effective_nav_len 失敗"
              f"({type(_e).__name__}: {_e}) → 視為 0 筆")
        return 0


def _is_short_window_nav(s: "pd.Series | None") -> bool:
    """這條序列是不是「近30日」短窗表(而非真正的長歷史)？

    2026-08-11 user 拍板後新增。線上實證:`_src_tcb_nav`(waterfall 順位 2c)
    在長歷史抓不到時,會把 MoneyDJ 主頁的「近30日淨值表」**掛在自己名下**回傳
    (`sources.py` 第三段),而 waterfall 的 gate 只數筆數(≥10)不看跨度 ——
    於是 30 筆短窗直接鎖定,後面 2c2/2d/2e… 一次都沒被試過。

    判定順序:
    1. **provenance 優先**(§2.2):`attrs["source"]` 含 `nav_30day` → 確定是短窗表。
    2. **跨度兜底**:`attrs` 在 concat/copy 中可能掉,故再看跨度 <
       `NAV_SHORT_WINDOW_MAX_DAYS`(90 天)。副作用是「真的很新的基金」也會被判短窗
       —— 那是**可接受且正確**的:它同樣值得讓其他來源再試一次,而重試只走非
       MoneyDJ 來源,不增加對 MoneyDJ 的請求。
    """
    if s is None or len(s) == 0:
        return False
    try:
        _src = str((getattr(s, "attrs", None) or {}).get("source", ""))
    except Exception:  # noqa: BLE001 — attrs 型別異常不該讓抓取整條掛掉
        _src = ""
    if "nav_30day" in _src:
        return True
    return _nav_span_days(s) < NAV_SHORT_WINDOW_MAX_DAYS


def _adopt_if_better(
    nav_s: pd.Series, nav_source: str,
    cand: "pd.Series | None", cand_name: str,
) -> "tuple[pd.Series, str]":
    """waterfall 收單一來源結果:**只在有效筆數更多時**才取代,且來源標籤同步換。

    2026-08-11 修的是 `_fetch_fund_single` waterfall 2a/2b/2c/2e 四處原本寫成
    `nav_s = _src_xxx(code)` 的**無條件覆蓋**,兩個獨立缺陷:

    1. **資料遺失(§1)**:前一順位已抓到、但未達本順位門檻的序列(例如安聯官網
       回 15 筆、門檻 20),會被下一個「回空」的來源直接抹成空 Series。
    2. **血緣錯標(§2.2)**:`nav_source` 只在通過門檻時才更新,所以
       `nav_s` 與 `nav_source` 可能**不同源** —— 例如 step 0 標了
       `allianzgi_tw`,序列卻已被 2a 換成 FundClear 的 8 筆。

    改成「更好才換、換就連標籤一起換」。與舊行為的差集**只有**「候選筆數 ≤
    手上筆數」這一種情形,而那正是舊碼會丟資料的情形 —— 故對筆數而言是
    單調不減的嚴格改善,不會讓任何原本會贏的來源改輸。

    ⚠️ 刻意**只比筆數不比跨度**:跨度優先(30 筆日資料 vs 25 筆月資料誰該贏)
    屬於 waterfall gate 的語意變更,須 user 拍板,不在本次修補範圍(§-1)。
    既有的跨度救援仍走 `_span_extend_insurance_nav`。

    ⚠️ **本函式刻意不直接用來取代 waterfall 的指派**。第一版曾把
    `nav_s = _src_xxx(...)` 直接改成走本函式,稽核抓到那是 net-negative:
    waterfall 的 gate(`if len(nav_s) < 10/20`)吃的就是 `nav_s`,一旦 `nav_s`
    變成「歷來最佳」,拿到 10~19 筆就會把 2c2/2d/2e/2f/2g… **整層下游關掉**,
    其中 2d 是 www yp004002 的 2000 天窗(可拿數百筆)。保住 15 筆卻放棄 500 筆,
    對「3Y 年化需 756 點」是反效果。
    現行做法:`nav_s` 與 gate 行為**完全維持原樣**,另開一條 `_best_s` 側車
    記錄歷來最長者,waterfall 跑完再回頭救援 —— 對 gate 零影響,對資料零遺失。
    """
    if cand is None or _effective_nav_len(cand) <= _effective_nav_len(nav_s):
        return nav_s, nav_source
    return cand, cand_name


def _fetch_fund_single(code: str, force_refresh: bool = False,
                       page_type: str = "") -> dict:
    """單一代碼的多來源抓取（由 fetch_fund_multi_source 呼叫）"""
    _code = code.upper().strip()
    _page_type = page_type or (
        "yp010000" if _is_domestic_code(_code) else "yp010001"
    )
    # [Auto-Fixed v18.203] _is_insurance_code 原本到函式後段（L2581）才賦值，但前面
    # 「nav<10 短資料」的 Morningstar/TDCC fallback 分支（L2484+）已引用它 → 短資料時
    # UnboundLocalError（正中「查無資料 / 新基金 / 抓取失敗」edge case）。提前計算一次。
    _is_insurance_code = (not _is_domestic_code(_code) and
                          any(_code.startswith(p) for p in _INSURANCE_SUBDOMAIN_HINTS))
    result = dict(
        fund_name="", full_key=_code, fund_code=_code,
        category="", risk_level="", dividend_freq="", currency="USD",
        fund_scale="", fund_region="", fund_type="",
        moneydj_div_yield=None,
        investment_target="", fund_rating="", umbrella_fund="",
        mgmt_fee="", is_esg="",
        nav_latest=None, nav_date="",
        year_high_nav=None, year_low_nav=None,
        series=None, dividends=[], perf={}, metrics={},
        risk_metrics={}, holdings={}, error=None,
        data_source="",     # 記錄實際使用的來源
    )

    # ── Step 2: 並行嘗試多來源（NAV）────────────────────────────────
    nav_s = pd.Series(dtype=float)
    nav_source = ""

    # 0. 安聯投信官網（ACTI/ACCP/ACDD 境內基金 + 保險平台安聯代碼）
    # v6.23 fix: 加入 len(nav_s) < 10 防護，避免覆蓋 GitHub Actions 快取資料
    # TLZF9/ANZ89 = 安聯收益成長，透過台灣人壽/兆豐等保險平台，走 tcbbankfund 取完整歷史
    _ALLIANZ_INSURANCE_CODES = frozenset({"TLZF9", "ANZ89"})
    if len(nav_s) < 10 and (
        (_is_domestic_code(_code) and any(_code.startswith(p) for p in ("ACTI","ACCP","ACDD","ACTT")))
        or _code in _ALLIANZ_INSURANCE_CODES
    ):
        _allianz_s = _src_allianzgi_nav(_code)
        if len(_allianz_s) >= 5:
            nav_s = _allianz_s
            # 2026-08-11 §1「填補須帶旗標」:`_src_allianzgi_nav` 在「JSON API 與
            # yp004002 兩段都 <90 筆」時會回 partial 並在 attrs 標 `...:partial`,
            # 但這裡原本硬編 `"allianzgi_tw"` 把那個旗標丟掉 —— 使用者在 Tab2
            # banner 與批次「資料來源」欄看到的,5 筆 partial 與完整 2000 天歷史
            # 長得一模一樣。改成把 partial 狀態帶出來(白話,不用內部代號)。
            _az_prov = str(_allianz_s.attrs.get("source") or "")
            nav_source = ("allianzgi_tw（僅部分歷史）"
                          if _az_prov.endswith(":partial") else "allianzgi_tw")

    # ── 2026-08-11 側車:歷來最長序列 ────────────────────────────────
    # 2a/2b/2c/2e/2f 五處寫的是 `nav_s = _src_xxx(_code)` **無條件覆蓋** ——
    # 前一順位已抓到、但未達本順位門檻的序列(例如安聯官網回 15 筆、2a 門檻 20)
    # 會被下一個「回空」的來源直接抹成空 Series(§1 資料遺失)。
    # 但那些指派同時也是 gate 的輸入,直接改成「較長者勝」會關掉整層下游來源
    # (見 `_adopt_if_better` docstring)。故 **gate 與 nav_s 一律維持原樣**,
    # 另存 `_best_s` 側車,waterfall 跑完再回頭救援。
    _best_s = pd.Series(dtype=float)
    _best_src = ""
    _best_s, _best_src = _adopt_if_better(_best_s, _best_src, nav_s, nav_source)

    # 2a. FundClear（境外最穩）
    if len(nav_s) < 20:
        nav_s = _src_fundclear_nav(_code)
        if len(nav_s) >= 20:
            nav_source = "FundClear"
        _best_s, _best_src = _adopt_if_better(_best_s, _best_src, nav_s, "FundClear")

    # 2b. 鉅亨網
    if len(nav_s) < 20:
        nav_s = _src_cnyes_nav(_code)
        if len(nav_s) >= 20:
            nav_source = "cnyes"
        _best_s, _best_src = _adopt_if_better(_best_s, _best_src, nav_s, "cnyes")

    # 2c. TCB MoneyDJ（子網域）
    if len(nav_s) < 20:
        nav_s = _src_tcb_nav(_code)
        if len(nav_s) >= 10:
            nav_source = "tcb_moneydj"
        _best_s, _best_src = _adopt_if_better(_best_s, _best_src, nav_s, "tcb_moneydj")

    # ── 2c'. 「近30日」偽裝拆除（2026-08-11 user 拍板）─────────────────────
    # `_src_tcb_nav` 抓不到長歷史時會把近30日表掛在自己名下回傳，而 gate 只數筆數
    # 不看跨度 → 30 筆直接鎖定，下游全部跳過。線上實證(ACCP138)：
    #   `[fetch] ✅ 主路線成功（src:tcb_moneydj nav=30筆）`、跨度 42 天，
    #   而 3Y 年化需 756 點 / Sharpe 250 / MaxDD 125 / σ 252 → 全數留白。
    #
    # 處置：短窗**不算數** → 收進側車、清空 nav_s 讓 gate 重新打開，
    # 但**只放行非 MoneyDJ 來源**（user 拍板：不增加對 MoneyDJ 的請求數；
    # MoneyDJ robots.txt 明文禁止 LLM/AI 用途）。故下方 2c2 / 2d / 2f
    # 三個 MoneyDJ 來源在本模式下一律跳過 —— 它們拿到的會是同一份短窗表。
    # 若非 MoneyDJ 來源也全敗，函式尾端的側車救援會把這 30 筆原樣放回去，
    # 資料零遺失、對 MoneyDJ 零額外請求。
    _retry_non_moneydj_only = False
    if _is_short_window_nav(nav_s):
        import sys as _sys_sw
        print(f"[orchestrator] 🔍 {_code} 2c 拿到的是近30日短窗"
              f"（{len(nav_s)}筆/{_nav_span_days(nav_s)}天）→ 不算數，"
              f"改試非 MoneyDJ 長歷史來源", file=_sys_sw.stderr)
        _retry_non_moneydj_only = True
        nav_s, nav_source = pd.Series(dtype=float), ""

    # 2c2. v6.8: 保險公司專屬 MoneyDJ 子網域（TL=台灣人壽, FL=富蘭克林 等）
    # ⚠️ MoneyDJ 網域 → 短窗重試模式下跳過（見 2c' 註解）
    if len(nav_s) < 10 and not _retry_non_moneydj_only:
        _ins_s = _src_insurance_subdomain_nav(_code)
        if len(_ins_s) >= 10:
            nav_s = _ins_s
            nav_source = "insurance_subdomain"
            result.setdefault("source_trace", []).append(
                {"source": "insurance_subdomain", "success": True, "nav_count": len(_ins_s)})

    # 2d. www.moneydj.com（主站，最後才試，IP 限制多）
    # ⚠️ MoneyDJ 網域 → 短窗重試模式下跳過（見 2c' 註解）
    if len(nav_s) < 10 and not _retry_non_moneydj_only:
        try:
            import datetime as _dt2
            import re as _re4
            base_www = "https://www.moneydj.com/funddj"
            today2 = _dt2.date.today()
            # v19.291:400d(~13 月)→ 2000d(~5.5 年),對齊 v19.281 cnyes/Morningstar 已做的窗口延伸
            # ——本函式先前漏做,是保單代碼(如 JFZN3) 3-3-3「成立 0.1 年」誤判的根因之一
            st2 = today2 - _dt2.timedelta(days=2000)
            # v13.8: page_type 互換 — 首選失敗自動換頁型重試
            _pages2 = get_page_types_to_try(
                "yp010000" if _is_domestic_code(_code) else "yp010001"
            )
            params_www = {
                "A": _code,
                "B": st2.strftime("%Y%m%d"),
                "C": today2.strftime("%Y%m%d"),
            }
            rw = None
            for _pg2 in _pages2:
                hdr2 = {**HDR,
                        "Referer": f"https://www.moneydj.com/funddj/ya/{_pg2}.djhtm?a={_code}"}
                rw = fetch_url_with_retry(
                    f"{base_www}/yf/yp004002.djhtm",
                    headers=hdr2, params=params_www, timeout=25, retries=2
                )
                if rw and is_valid_moneydj_page(rw.text):
                    print(f"[www_fallback] ✅ {_code} page={_pg2}")
                    break
                print(f"[www_fallback] {_code} page={_pg2} → 無效，換頁型")
                rw = None
            if rw and is_valid_moneydj_page(rw.text):
                soup_w = BeautifulSoup(rw.text, "lxml")
                _www_rows = {}
                for tbl in soup_w.find_all("table"):
                    for row in tbl.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) >= 2:
                            dt_t = cells[0].get_text(strip=True)
                            nv_t = cells[1].get_text(strip=True).replace(",", "")
                            if _re4.match(r"\d{4}/\d{2}/\d{2}", dt_t):
                                v = safe_float(nv_t)
                                if v: _www_rows[pd.Timestamp(dt_t)] = v
                if len(_www_rows) >= 10:
                    nav_s = pd.Series(_www_rows).sort_index()
                    nav_source = "moneydj_www"
                    print(f"[src_www] ✅ {_code} {len(nav_s)} 筆")
        except Exception as _we:
            print(f"[src_www] {_code}: {_we}")

    # 2e. SITCA（境內基金備援）
    if len(nav_s) < 10:
        nav_s = _src_sitca_nav(_code)
        if len(nav_s) >= 10:
            nav_source = "sitca"
        _best_s, _best_src = _adopt_if_better(_best_s, _best_src, nav_s, "sitca")

    # 2f. 近30日 nav 頁直接解析（最終 fallback，yf/yp004002 全被封鎖時使用）
    # 近30日雖然只有約25~30筆，足以計算 Sharpe/標準差
    # ⚠️ MoneyDJ 網域 → 短窗重試模式下跳過：那份資料 2c 已經拿到並存進側車了，
    #    再打一次是**完全重複**的請求（見 2c' 註解）。
    if len(nav_s) < 10 and not _retry_non_moneydj_only:
        nav_s = _src_nav_30day(_code, _page_type)
        if len(nav_s) >= 10:
            nav_source = "moneydj_nav30"
            print(f"[orchestrator] 📅 {_code} 使用近30日淨值（{len(nav_s)}筆）")
        _best_s, _best_src = _adopt_if_better(_best_s, _best_src, nav_s, "moneydj_nav30")

    # 2f2. v6.18: 銀行/保險平台直連（有明確代碼映射的基金優先）
    # 使用真實 URL（華南銀行/遠東銀行/台灣人壽），非 moneydj.com domain 較不被封鎖
    if len(nav_s) < 10 and _code in _BANK_PLATFORM_CODES:
        _bp_s = _src_bank_platform_nav(_code)
        if len(_bp_s) >= 5:
            nav_s = _bp_s
            nav_source = "bank_platform"
            result.setdefault("source_trace", []).append(
                {"source": "bank_platform", "success": True, "nav_count": len(_bp_s)})
            print(f"[orchestrator] 🏦 {_code} 銀行平台直連 {len(_bp_s)} 筆")
        else:
            result.setdefault("source_trace", []).append(
                {"source": "bank_platform", "success": False, "error": "所有平台均無回應"})

    # 2g. v6.19: Morningstar 國際資料源（改進版：使用硬編碼 secId + 正確 currencyId）
    # TLZF9 = 0P0001J5YG (Allianz Income and Growth AMg7 USD)，已確認存在於 Morningstar
    if len(nav_s) < 10 and _is_insurance_code:
        _ms_name = result.get("fund_name") or ""
        _ms_s = _src_morningstar_nav(_code, fund_name=_ms_name)
        if len(_ms_s) >= 10:
            nav_s = _ms_s
            nav_source = "morningstar"
            result.setdefault("source_trace", []).append(
                {"source": "morningstar", "success": True, "nav_count": len(_ms_s)})
            print(f"[orchestrator] 🌐 {_code} Morningstar 命中 {len(_ms_s)} 筆")
        else:
            result.setdefault("source_trace", []).append(
                {"source": "morningstar", "success": False,
                 "error": "查無資料"})

    # 2g2. v6.19: Yahoo Finance 備援（Morningstar secId.F 格式，美國 IP 可存取）
    # Yahoo Finance 對共同基金使用 {morningstar_secId}.F 作為代碼
    if len(nav_s) < 10 and _is_insurance_code and _code in _MORNINGSTAR_SECID_MAP:
        _yf_s = _src_yahoo_finance_nav(_code)
        if len(_yf_s) >= 10:
            nav_s = _yf_s
            nav_source = "yahoo_finance"
            result.setdefault("source_trace", []).append(
                {"source": "yahoo_finance", "success": True, "nav_count": len(_yf_s)})
            print(f"[orchestrator] 📈 {_code} Yahoo Finance 命中 {len(_yf_s)} 筆")
        else:
            result.setdefault("source_trace", []).append(
                {"source": "yahoo_finance", "success": False,
                 "error": "查無資料或代碼未在映射表"})

    # 2g3. v6.22: Alpha Vantage API（需 ALPHAVANTAGE_API_KEY，美國 IP 可存取）
    # 設定方式：Streamlit Cloud → Settings → Secrets → ALPHAVANTAGE_API_KEY = "你的KEY"
    # 免費 key：25 req/day，https://www.alphavantage.co/support/#api-key
    if len(nav_s) < 10 and _is_insurance_code:
        _av_s = _src_alphavantage_nav(_code)
        if len(_av_s) >= 10:
            nav_s = _av_s
            nav_source = "alphavantage"
            result.setdefault("source_trace", []).append(
                {"source": "alphavantage", "success": True, "nav_count": len(_av_s)})
            print(f"[orchestrator] 📊 {_code} Alpha Vantage 命中 {len(_av_s)} 筆")
        else:
            result.setdefault("source_trace", []).append(
                {"source": "alphavantage", "success": False,
                 "error": "無資料或未設定 API Key"})

    # 2h. v6.21: 基金公司官網直連（Morningstar 也沒有時，試各公司 TW 官網）
    # 注意：FLFM1 是 BNP Paribas（法巴），不是 Franklin（富蘭克林）！
    # FL 前綴判斷需排除 FLFM（BNP Paribas 在台灣的代碼前綴）
    _FRANKLIN_PREFIX = ("FLZ", "FLA", "FLB", "FLC", "FLD", "FLE")   # 富蘭克林實際前綴
    _BNP_FL_CODES = {"FLFM1", "FLFM2"}                               # 法巴用 FL 前綴的代碼
    if len(nav_s) < 10 and _is_insurance_code:
        _intl_s = pd.Series(dtype=float)
        if _code.startswith("FL") and _code not in _BNP_FL_CODES:
            _intl_s = _src_franklin_nav(_code)
            _intl_src = "franklin_tw"
        elif _code.startswith("JF"):
            _intl_s = _src_jpmorgan_nav(_code)
            _intl_src = "jpmorgan_tw"
        else:
            _intl_src = ""
        if len(_intl_s) >= 10:
            nav_s = _intl_s
            nav_source = _intl_src
            result.setdefault("source_trace", []).append(
                {"source": _intl_src, "success": True, "nav_count": len(_intl_s)})
            print(f"[orchestrator] 🏢 {_code} 基金公司直連 {len(_intl_s)} 筆")

    # 2i. v6.17: 台灣人壽官網直連（TL 前綴，TLZF9 等）
    if len(nav_s) < 10 and _is_insurance_code and _code.startswith("TL"):
        _tl_s = _src_taiwanlife_nav(_code)
        if len(_tl_s) >= 10:
            nav_s = _tl_s
            nav_source = "taiwanlife_direct"
            result.setdefault("source_trace", []).append(
                {"source": "taiwanlife_direct", "success": True, "nav_count": len(_tl_s)})
            print(f"[orchestrator] 🏛 {_code} 台灣人壽官網直連 {len(_tl_s)} 筆")
        else:
            result.setdefault("source_trace", []).append(
                {"source": "taiwanlife_direct", "success": False,
                 "error": "官網端點查無資料或 URL 需更新"})

    # ── 2026-08-11 側車救援:把 waterfall 中途被無條件覆蓋抹掉的最長序列拿回來 ──
    # 只在「最後留下的 nav_s 比歷來最佳短」時觸發,對其餘 case 零影響。
    # 放在 span-extend **之前**,讓跨度救援拿到的是救回來後的較長序列。
    if _effective_nav_len(_best_s) > _effective_nav_len(nav_s):
        import sys as _sys_rescue
        print(f"[orchestrator] ♻️ {_code} waterfall 收尾救援 "
              f"{nav_source or '—'}({len(nav_s)}筆) → {_best_src}({len(_best_s)}筆)",
              file=_sys_rescue.stderr)
        result.setdefault("source_trace", []).append(
            {"source": f"{_best_src}(best-of-waterfall)", "success": True,
             "nav_count": len(_best_s), "replaced": nav_source or "",
             "replaced_count": len(nav_s)})
        nav_s, nav_source = _best_s, _best_src

    # v19.281/v19.284 span-extend(共用 _span_extend_insurance_nav,見檔頭 SSOT 說明)
    nav_s, nav_source, _span_days = _span_extend_insurance_nav(
        _code, nav_s, nav_source,
        fund_name=result.get("fund_name") or "", is_insurance_code=_is_insurance_code,
    )

    if len(nav_s) >= 10:
        result["series"]      = nav_s
        result["data_source"] = nav_source
        result["nav_span_days"] = _span_days
        result.setdefault("source_trace", []).append(
            {"source": nav_source, "success": True, "nav_count": len(nav_s),
             "span_days": _span_days})
    else:
        result.setdefault("source_trace", []).append(
            {"source": "nav_all", "success": False,
             "error": f"所有來源均不足10筆（最多:{len(nav_s)}）"})

    # ── Step 3: 基本資料（Meta）─────────────────────────────────────
    meta = {}

    # v6.14: 保險公司代碼（TL/FL/CT 等）優先嘗試 TDCC OpenAPI
    # 原因：此類代碼的 MoneyDJ 保險子網域在 Streamlit Cloud 上全部被封鎖 IP，
    #       但 TDCC 是政府 API，無 IP 限制，可取得基金名稱與最新淨值。
    # v18.203：_is_insurance_code 已於函式開頭計算（避免短資料 fallback 引用未賦值）
    if _is_insurance_code:
        _tdcc_early = _src_tdcc_meta(_code)
        if _tdcc_early.get("fund_name") or _tdcc_early.get("nav_latest"):
            meta = merge_non_empty(meta, _tdcc_early)
            result.setdefault("source_trace", []).append(
                {"source": "tdcc_meta_early", "success": True})
            print(f"[orchestrator] 🏛 {_code} TDCC early 命中: "
                  f"{_tdcc_early.get('fund_name','')[:25]} "
                  f"nav={_tdcc_early.get('nav_latest')}")

    # 境內基金優先安聯投信官網
    if not meta.get("fund_name") and _is_domestic_code(_code):
        meta = _src_allianzgi_meta(_code)
        if meta.get("fund_name"):
            result["source_trace"].append({"source": "allianzgi_meta", "success": True})
    # 優先 TCB MoneyDJ（含年高/年低）
    if not meta.get("fund_name"):
        meta = _src_tcb_meta(_code)
        if meta.get("fund_name"):
            result["source_trace"].append({"source": "tcb_meta", "success": True})
    # 再試 FundClear
    if not meta.get("fund_name"):
        meta = merge_non_empty(meta, _src_fundclear_meta(_code))
        if meta.get("fund_name"):
            result["source_trace"].append({"source": "fundclear_meta", "success": True})
    # 最後 SITCA（境內基金）
    if not meta.get("fund_name"):
        meta = merge_non_empty(meta, _src_sitca_meta(_code))
        if meta.get("fund_name"):
            result["source_trace"].append({"source": "sitca_meta", "success": True})
    # 最終備援：TDCC OpenAPI（境外基金官方登記，MoneyDJ 被封鎖時仍可存取）
    if not meta.get("fund_name") and not _is_domestic_code(_code):
        _tdcc_m = _src_tdcc_meta(_code)
        if _tdcc_m.get("fund_name") or _tdcc_m.get("nav_latest"):
            meta = merge_non_empty(meta, _tdcc_m)
            result["source_trace"].append({"source": "tdcc_meta", "success": True})
            print(f"[orchestrator] 🏛 {_code} TDCC metadata 命中: {_tdcc_m.get('fund_name','')[:25]}")

    if meta:
        # v13.5: 用 merge_non_empty，不讓空值覆蓋前面成功的資料
        result = merge_non_empty(result, meta)

    # ── Step 4: 配息資料 ───────────────────────────────────────────
    divs = result.get("dividends") or []
    if not divs:
        divs = _src_tcb_div(_code)
    if not divs:
        divs = _src_fundclear_div(_code)
    if not divs:
        divs = _src_cnyes_div(_code)
    if divs:
        result["dividends"] = divs
        latest_yield = divs[0].get("yield_pct", 0)
        if latest_yield > 0:
            result["moneydj_div_yield"] = round(latest_yield, 2)

    # ── Step 5: 風險指標（wb07）+ 績效（wb01）────────────────────────
    # v19.310 Bug A:原本 wb01 績效巢狀在 `if risk_data:` 內 → wb07 風險一失敗,
    # 3Y/5Y 績效就跟著不抓(即使 wb01 本來抓得到)。兩個是獨立頁,分開抓、互不綁架。
    try:
        risk_data = fetch_risk_metrics(_code)
        if risk_data:
            result["risk_metrics"] = risk_data
    except Exception as _re5:
        print(f"[orchestrator] risk_metrics: {_re5}")
    try:
        perf_wb01 = fetch_performance_wb01(_code)
        if perf_wb01:
            result["perf"].update(perf_wb01)
            result["perf_source"] = "wb01"
    except Exception as _rep5:
        print(f"[orchestrator] perf_wb01: {_rep5}")

    # ── Step 6: 計算 指標 ────────────────────────────────────────
    _finish_metrics(result)

    # ── v6.14: 保險代碼專屬提示 ─────────────────────────────────────
    # 當代碼被識別為保險公司專屬，且歷史序列為空時，給予明確引導。
    # normalize_result_state 已處理 partial/failed 狀態，此處只覆寫訊息文字。
    if _is_insurance_code:
        _has_series = result.get("series") is not None and len(result.get("series", [])) >= 10
        if not _has_series:
            if result.get("fund_name") or result.get("nav_latest"):
                # 有部分資料（名稱/淨值）→ 黃色 warning，清除紅色 error
                result["error"] = None
                result["warning"] = (
                    f"⚠️ 保險平台專屬代碼（{_code}）在 Streamlit Cloud 上無法下載歷史淨值。"
                    "MoneyDJ 保險子網域封鎖雲端 IP，Morningstar 亦無此代碼的歷史序列。"
                    " 上方已顯示 TDCC 最新淨值。如需走勢分析，請使用「手動淨值輸入」功能。"
                )
            else:
                # 完全無資料 → 紅色 error 但說明原因
                result["error"] = (
                    f"❌ 保險平台專屬代碼（{_code}）：MoneyDJ 保險子網域封鎖雲端 IP，"
                    "TDCC 及 Morningstar 亦查無此代碼。"
                    "請確認代碼是否正確，或改用「手動淨值輸入」功能。"
                )

    return result


def _finish_metrics(result: dict):
    """v19.240 R8 EX-L1ORCH-1 退役後純化:本層只做 L1 狀態收尾(初始化
    source_trace + normalize_result_state)。metrics + perf 注入 + reconcile
    業務邏輯由 L2 services.fund_service.finalize_fund_metrics 處理(`_fetch_fund_single`
    走 L2 wrapper(services.fund_service.fetch_fund_*_enriched) 才會 enrich)。
    """
    s    = result.get("series")
    code = result.get("fund_code", "?")

    if "source_trace" not in result:
        result["source_trace"] = []

    if s is None:
        result["source_trace"].append(
            {"source": "nav_series", "success": False, "error": "無淨值序列"})
    elif len(s) < 10:
        result["source_trace"].append(
            {"source": "nav_series", "success": False,
             "error": f"只有 {len(s)} 筆(需≥10)"})

    result = normalize_result_state(result)
    print(f"[orchestrator] {code} → status={result.get('status')} "
          f"error={str(result.get('error',''))[:40]} "
          f"warning={str(result.get('warning',''))[:40]}")


def fetch_fund_from_moneydj_url(url: str) -> dict:
    """
    輸入任何 MoneyDJ 基金頁面網址（或純代碼如 tlzf9），
    自動抓取：基本資料、近一年淨值歷史、績效、配息。

    回傳格式（與 fetch_fund_by_key 相容）：
    {
      "fund_name": str, "full_key": str, "fund_code": str,
      "category": str, "risk_level": str, "dividend_freq": str,
      "currency": str, "fund_scale": str,
      "nav_latest": float, "nav_date": str,
      "series": pd.Series,        # 日期→淨值，可直接給 calc_metrics
      "dividends": list,           # [{date, amount, yield_pct}]
      "perf": dict,                # {1M, 3M, 6M, 1Y, 3Y, 5Y, sharpe, beta, std}
      "metrics": dict,             # calc_metrics 結果
      "error": str or None,
    }
    """
    import re as _re
    import datetime as _dt_mj   # v19.61 E1：抓取時戳

    # ── 1. 解析代碼 ──────────────────────────────────────
    # v19.61 E1：_moneydj_fetched_at 記錄抓取當下 wallclock（YYYY-MM-DD HH:MM:SS），
    # 給 Tab5 組合健檢「資料新鮮度」banner 顯示「抓取於 / NAV 日期 / 延遲 Nd」用。
    # 純新增欄位，零影響既有 caller（讀不到的就跳過）。
    result = dict(fund_name="", full_key="", fund_code="", category="",
                  risk_level="", dividend_freq="", currency="USD",
                  fund_scale="", fund_region="", fund_type="",
                  moneydj_div_yield=None,
                  investment_target="", fund_rating="", umbrella_fund="",
                  mgmt_fee="", is_esg="",
                  nav_latest=None, nav_date="",
                  year_high_nav=None, year_low_nav=None,
                  series=None, dividends=[], perf={}, metrics={},
                  risk_metrics={}, holdings={}, error=None,
                  # C2 v19.208 F-PROV-1:加 source orchestrator-level(§2.2)
                  source="MoneyDJ:fund_url_orchestrator",
                  _moneydj_fetched_at=_dt_mj.datetime.now().strftime(
                      "%Y-%m-%d %H:%M:%S"))

    # ── v18.22: 先 canonicalize 非標準變體 URL（mobile / 平台子網域）──
    #           m.moneydj.com / chubb.moneydj.com /w/wr/ 等都轉成
    #           www.moneydj.com/funddj/ya/yp01000X.djhtm?a={base_code}
    _canonical_url = canonicalize_moneydj_url(url)
    if _canonical_url != url:
        print(f"[fetch] canonicalize: {url[:60]} → {_canonical_url[:60]}")

    # ── v13.4: parse_moneydj_input — 保留 page_type，不再丟失境內路由資訊 ──
    _input_info = parse_moneydj_input(_canonical_url)
    code = _input_info.get("code", "")

    # 若輸入只是純代碼（非 URL），嘗試 regex 補救
    if not code:
        import re as _re
        m = _re.search(r"[?&][aA]=([A-Z0-9]{3,25}(?:-[A-Z0-9]{3,20})?)", url, _re.I)
        if m:
            code = m.group(1).upper()
        elif _re.match(r"^[A-Z0-9]{3,25}(-[A-Z0-9]{3,20})?$", url.strip(), _re.I):
            code = url.strip().upper()
    if not code:
        result["error"] = "無法解析代碼，請輸入 MoneyDJ 網址或代碼（如 tlzf9）"
        return result

    _page_type = _input_info.get("page_type", "")   # 保留原始頁型（URL 輸入最準）

    # 查 mapping table：補全 public_code 與 page_type
    _mapping = load_fund_code_mapping()
    if code in _mapping:
        _m = _mapping[code]
        code       = _m.get("public_code", code)
        _page_type = _m.get("page_type", _page_type)
        print(f"[fetch] mapping 命中：{_input_info['code']} → {code} (page:{_page_type})")

    # 若 page_type 仍空白（純代碼輸入），自動推斷
    if not _page_type:
        _page_type = "yp010000" if _is_domestic_code(code) else "yp010001"
        print(f"[fetch] page_type 自動推斷：{code} → {_page_type}")

    result["full_key"]  = code
    result["fund_code"] = code

    # ── Step 1: 直接抓使用者提供的原始 URL（最高優先）───────────────
    if _input_info.get("is_url") and _input_info.get("full_url"):
        _direct = _src_direct_moneydj_url(_input_info["full_url"])
        if _direct.get("fund_name") or _direct.get("nav_latest"):
            # ── 2026-08-11 兩項修正 ────────────────────────────────────
            # (1) §2.2 血緣：Step 1 只抓 **meta**（名稱 / 最新淨值 / 幣別 / 費用率），
            #     **完全不抓 NAV 序列** —— 它沒有資格為 `data_source` 背書。
            #     原本這個迴圈連 `data_source="direct_url"` 一起寫進 result，兩個連鎖後果：
            #       (a) 下方 legacy 收尾的
            #           `result.get("data_source") or "moneydj_legacy_scrape"`
            #           永遠取到 `"direct_url"` → `or` 那半邊是**死碼**，legacy 爬到的
            #           序列被標成 Step 1 的來源；
            #       (b) 畫面 banner 顯示「來源:direct_url ‧ 跨度 42 天」，而那 30 筆
            #           其實來自 legacy 的近30日爬蟲 —— **診斷儀器本身在說謊**，
            #           「多來源 waterfall 到底有沒有贏」在線上完全看不出來。
            #     故明確排除 `data_source`，改為在 source_trace 誠實登記「只給 meta」。
            # (2) 判空改走 `_is_empty_value`：原本的 `_v not in (None, "", {}, [])`
            #     與 merge_non_empty 是同型缺陷，遇 pd.Series 會拋
            #     `ValueError: truth value of a Series is ambiguous`，而**這一段沒有
            #     try 保護**（Step 2 那份有）。目前 `_src_direct_moneydj_url` 全回純量
            #     所以炸不到，但屬於等人來踩的地雷 —— 只要有人往它的 out 加一個
            #     series/DataFrame 欄位，整條 fetch 會炸在半合併狀態。
            for _k, _v in _direct.items():
                if _k == "data_source":
                    continue
                if not _is_empty_value(_v):
                    result[_k] = _v
            result.setdefault("source_trace", []).append(
                {"source": "direct_url", "success": True, "meta_only": True,
                 "note": "只提供 meta，未提供 NAV 序列"})
            print(f"[fetch] direct_url meta: {result.get('fund_name','')[:20]} NAV={result.get('nav_latest')}")

    # ── Step 2: 多來源 Orchestrator（帶 page_type）──────────────────
    try:
        _ms_result = fetch_fund_multi_source(
            code, force_refresh=False, page_type=_page_type
        )
        # 合併策略：series/metrics/perf 優先用 multi_source，meta 保留 direct_url 結果
        # v13.5: merge_non_empty，保留 direct_url meta，補入 multi_source 的 series/metrics
        if _ms_result:
            _protect = ("fund_name","currency","risk_level","nav_latest","nav_date",
                        "year_high_nav","year_low_nav")
            _saved_meta = {k: result[k] for k in _protect if result.get(k)}
            result = merge_non_empty(result, _ms_result)
            for _k, _v in _saved_meta.items():
                if _v:
                    result[_k] = _v
            result = normalize_result_state(result)

        _s_ok = result.get("series") is not None and len(result.get("series", [])) >= 10
        _m_ok = result.get("fund_name") and result.get("nav_latest")
        if _s_ok:
            # stderr:這一行是「多來源 waterfall 有沒有贏」的唯一線上訊號（見上方 stderr 註解）
            import sys as _sys_ok
            # 此處 `_s_ok` 已保證 series 非 None，但仍用同一種寫法保持一致
            # （避免下一個人複製貼上時退回 `or []` 的寫法）。
            _ser_ok = result.get("series")
            print(f"[fetch] ✅ 主路線成功（src:{result.get('data_source','')} "
                  f"nav={len(_ser_ok) if _ser_ok is not None else 0}筆 "
                  f"status:{result.get('status','')} page:{_page_type}）",
                  file=_sys_ok.stderr)
            return result
        # v18.121 issue 4: series 缺失但 fund_name+nav 有 → 不再提早 return（之前 bug）
        # 自動切 alternative page_type 重試一次（境內↔境外 mapping 錯誤的 case）
        # 例：ACTI71 mapping table 標境內 yp010000 但實際境外，切 yp010001 重試可拿到 series
        elif _m_ok:
            _alt_pt = "yp010001" if _page_type == "yp010000" else "yp010000"
            print(f"[fetch] ⚠️ {code} 主路線 ({_page_type}) series=0 但 meta 有；"
                  f"切 {_alt_pt} fallback 重試...")
            try:
                _alt_result = fetch_fund_multi_source(
                    code, force_refresh=False, page_type=_alt_pt
                )
                if _alt_result:
                    _alt_s = _alt_result.get("series")
                    _alt_s_ok = (_alt_s is not None and hasattr(_alt_s, "__len__")
                                 and len(_alt_s) >= 10)
                    if _alt_s_ok:
                        # alt page_type 拿到 series → 合併到既有 meta（保留主路線拿到的 name/nav）
                        _meta_protect = ("fund_name", "currency", "risk_level",
                                         "nav_latest", "nav_date",
                                         "year_high_nav", "year_low_nav")
                        _saved_meta = {k: result[k] for k in _meta_protect if result.get(k)}
                        result = merge_non_empty(result, _alt_result)
                        for _k, _v in _saved_meta.items():
                            if _v:
                                result[_k] = _v
                        result = normalize_result_state(result)
                        print(f"[fetch] ✅ alt page_type ({_alt_pt}) fallback 成功，"
                              f"series={len(_alt_s)}（meta 保留主路線結果）")
                        return result
                    else:
                        print(f"[fetch] alt page_type ({_alt_pt}) 仍 series=0，"
                              f"繼續原始流程")
            except Exception as _alt_e:
                print(f"[fetch] alt page_type fallback 異常: {_alt_e}")
            # 兩個 page_type 都拿不到 series → 繼續走 Step 3+ 原始 _src_* 流程
            print(f"[fetch] ⚠️ 兩個 page_type 都不足，繼續原始流程")
        else:
            # stderr:與上面那行成對 —— 「主路線輸了」也必須線上看得見
            import sys as _sys_ng
            # ⚠️ 同上：不可寫 `len(x.get("series") or [])`，`or` 對 Series 會炸。
            _ser_ng = result.get("series")
            print(f"[fetch] ⚠️ 主路線不足，改走 legacy 爬蟲"
                  f"（page:{_page_type} "
                  f"nav={len(_ser_ng) if _ser_ng is not None else 0}筆 "
                  f"name={'有' if result.get('fund_name') else '無'}）",
                  file=_sys_ng.stderr)
    except Exception as _ms_e:  # noqa: BLE001 — 有備援流程，但不得靜默（§1）
        # 2026-08-11:原本只印 `{_ms_e}`。這一顆 except 是**整條多來源 waterfall
        # 的唯一出口**,一旦裡面任何地方拋例外,結果整包被丟棄、流程默默改走
        # legacy 爬蟲(近30日,~30 筆)。而只印訊息不印型別/traceback 的後果是:
        # 線上看到「每檔剛好 30 點」時,**無法分辨**是
        #   (a) waterfall 跑完但每個來源都 <10 筆,還是
        #   (b) waterfall 中途炸掉。
        # 這兩者的修法完全不同,卻長得一模一樣。補上型別 + traceback。
        # ⚠️ 2026-08-11 第三輪:**必須寫 stderr**。Streamlit Cloud 的 log 面板
        # 只顯示 stderr —— 本 repo 絕大多數診斷 print 走 stdout,線上**完全看不到**。
        # 實測佐證:同一次抓取中,只有 `nav_metrics.py` 那幾行 `file=sys.stderr` 的
        # `[holdings:...]` 出現在 log,`[fetch]` / `[orchestrator]` / `[src_*]` 一行都沒有。
        # 這正是「§1 Fail Loud 寫了一堆、線上卻永遠是靜默失敗」的真正原因。
        import sys as _sys_ms
        import traceback as _tb_ms
        print(f"[fetch] ⚠️ 多來源異常({type(_ms_e).__name__}): {_ms_e}，繼續原始流程",
              file=_sys_ms.stderr)
        print(_tb_ms.format_exc(), file=_sys_ms.stderr)
        result.setdefault("source_trace", []).append(
            {"source": "multi_source", "success": False,
             "error": f"{type(_ms_e).__name__}: {_ms_e}"})

    # ── 判斷境內/境外基金（影響爬蟲路徑）──────────────────
    # 境內基金（投信，如聯博/安聯投信/富達投信）：
    #   www.moneydj.com/funddj/ya/yp010000.djhtm?a=ACTI71
    # 境外基金（ISIN/境外代碼）：
    #   www.moneydj.com/funddj/ya/YP081000.djhtm?a=TLZF9
    # tcbbankfund 子網域對境內/境外都相容，且 Colab IP 封鎖較少

    _portal_auto = ""
    _code_upper = code.upper()

    # BASE 一律優先走 tcbbankfund（對 Colab IP 最友善）
    BASE = "https://tcbbankfund.moneydj.com/funddj"
    print(f"[fetch] code={code}  BASE={BASE}")

    # ── 2. 基本資料 yp011001（tcbbankfund 優先，www fallback）──
    try:
        # v14.4: 境內用 yp011000，境外用 yp011001（從實際 HTML 確認）
        _info_page_type = "yp011000" if _is_domestic_code(code, _page_type) else "yp011001"
        _info_pages_try = [_info_page_type]
        # 互換備用：yp011000 失敗試 yp011001，反之亦然
        _info_pages_try.append("yp011001" if _info_page_type == "yp011000" else "yp011000")

        _info_urls = []
        for _ip in _info_pages_try:
            _info_urls.extend([
                f"https://tcbbankfund.moneydj.com/funddj/yp/{_ip}.djhtm?a={code}",
                f"https://www.moneydj.com/funddj/yp/{_ip}.djhtm?a={code}",
            ])
        r = None
        for _iu in _info_urls:
            # v14.4: fetch_url_with_retry (Big5 統一解碼)
            r = fetch_url_with_retry(_iu, timeout=20, retries=1)
            if r is not None and len(r.text) > 500:
                break
        if r is not None and len(r.text) > 500:
            soup = BeautifulSoup(r.text, "lxml")
            for tbl in soup.find_all("table"):
                txt = tbl.get_text()
                if "基金名稱" not in txt: continue
                # 建立 key→value map（支援多欄 row: col0=key1, col1=val1, col2=key2, col3=val2）
                rows_map = {}
                for row in tbl.find_all("tr"):
                    cells = row.find_all("td")
                    # 單欄對 (key, value)
                    if len(cells) == 2:
                        k = cells[0].get_text(strip=True)
                        v = cells[1].get_text(strip=True)
                        rows_map[k] = v
                    # 雙欄對 (key1, val1, key2, val2)
                    elif len(cells) >= 4:
                        for i in range(0, len(cells)-1, 2):
                            k = cells[i].get_text(strip=True)
                            v = cells[i+1].get_text(strip=True)
                            if k: rows_map[k] = v
                result["fund_name"]       = rows_map.get("基金名稱", "")
                result["currency"]        = rows_map.get("計價幣別", "USD").replace(" ","")
                result["risk_level"]      = rows_map.get("風險報酬等級", "").replace(" ","")
                result["dividend_freq"]   = rows_map.get("配息頻率", "").replace(" ","")
                result["fund_scale"]      = rows_map.get("基金規模", "")
                result["category"]        = rows_map.get("投資標的", rows_map.get("基金類型", "")).replace(" ","")
                result["fund_region"]     = rows_map.get("投資區域", "").replace(" ","")
                result["fund_type"]       = rows_map.get("基金類型", "").replace(" ","")
                result["investment_target"]= rows_map.get("投資標的", "").replace(" ","")
                result["fund_rating"]     = rows_map.get("基金評等", "")
                result["umbrella_fund"]   = rows_map.get("傘型架構", "").replace(" ","")
                result["mgmt_fee"]        = rows_map.get("最高經理費(%)", "")
                # v19.368 7/8:同表補抽保管費 → TER 估計第 2 主成分(零新增 HTTP)
                result["custody_fee"]     = (rows_map.get("最高保管費(%)") or
                                             rows_map.get("保管費(%)") or
                                             rows_map.get("保管費", ""))
                # v19.370 真實 TER:同表若揭露「總費用率」→ 收真值(消費端優先於估計)
                result["total_expense_ratio"] = (rows_map.get("總費用率(%)") or
                                                 rows_map.get("總費用率") or
                                                 rows_map.get("總開支比率(%)") or
                                                 rows_map.get("經常性費用(%)") or "")
                result["is_esg"]          = rows_map.get("是否為ESG", "")
                # v19.308：MoneyDJ 現成「成立日期」→ 供成立年計算免依賴本地長歷史
                #（Cloud IP 被擋、NAV 只抓到近 1 月時，成立年仍能正確）。抓不到則不設，
                # 成立年自動 fallback 回 NAV 序列（見 fund_screening.fund_inception_years）。
                _inc_raw = (rows_map.get("成立日期") or rows_map.get("設立日期") or
                            rows_map.get("成立日") or rows_map.get("基金成立日") or "")
                if _inc_raw:
                    _inc_m = _re.search(r"\d{4}[/-]\d{1,2}[/-]\d{1,2}", _inc_raw)
                    if _inc_m:
                        result["inception_date"] = _inc_m.group().replace("/", "-")
                # latest NAV + 年度高低點 from this page
                for row in tbl.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) >= 4:
                        # 行格式: 淨值日期 | 淨值 | 最高淨值(年) | 最低淨值(年)
                        dt = cells[0].get_text(strip=True)
                        if _re.match(r"\d{4}/\d{2}/\d{2}", dt):
                            try:
                                result["nav_date"]    = dt
                                result["nav_latest"]   = safe_float(cells[1].get_text(strip=True))
                                result["year_high_nav"] = safe_float(cells[2].get_text(strip=True))
                                result["year_low_nav"]  = safe_float(cells[3].get_text(strip=True))
                                print(f"[fetch_basic] 年高={result['year_high_nav']} 年低={result['year_low_nav']}")
                            except (ValueError, TypeError, IndexError) as _e:
                                # W5-1 §1 Fail Loud: bare except → narrow + log
                                print(f"[fetch_basic] ⚠️ 年高低解析失敗 dt={dt}: {_e}")
                    elif len(cells) >= 2:
                        dt = cells[0].get_text(strip=True)
                        if _re.match(r"\d{4}/\d{2}/\d{2}", dt):
                            try:
                                result["nav_date"]   = dt
                                result["nav_latest"] = float(cells[1].get_text(strip=True).replace(",",""))
                            except (ValueError, TypeError) as _e:
                                # W5-1 §1 Fail Loud: bare except → narrow + log
                                print(f"[fetch_basic] ⚠️ nav_latest 解析失敗 dt={dt}: {_e}")
                break
    except Exception as e:
        print(f"[fetch_basic] {e}")

    # ── 3. 淨值歷史（近30日）→ 再查詢歷史區間 ──
    # v13.8: page_type 互換 — 首選失敗自動換 yp010000 ↔ yp010001
    try:
        _primary_nav_page = _page_type if _page_type else (
            "yp010000" if _is_domestic_code(code) else "yp010001"
        )
        _nav_page_candidates = get_page_types_to_try(_primary_nav_page)
        _nav_bases = [
            BASE,
            TCB_BASE + "/funddj",
            "https://www.moneydj.com/funddj",
            "https://tcbbankfund.moneydj.com/funddj",
        ]
        _nav_r = None
        # 外層：依次嘗試各 base；若回傳無效，換頁型再試一遍
        for _nav_pg in _nav_page_candidates:
            if _nav_r is not None:
                break
            for _nb_url in _nav_bases:
                try:
                    _nav_r = fetch_url_with_retry(
                        f"{_nb_url}/ya/{_nav_pg}.djhtm?a={code}",
                        timeout=25, retries=1
                    )
                    if _nav_r is not None:
                        print(f"[nav30] ✅ {code} page={_nav_pg} base={_nb_url[:30]}")
                        break
                except Exception as _ne:
                    print(f"[nav fallback] {_nb_url}: {_ne}")
                    continue
        r = _nav_r
        # v13.6: fetch_url_with_retry 不回 status_code，直接判斷 r is not None
        if r is not None:
            soup = BeautifulSoup(r.text, "lxml")
            nav_rows = {}
            _nav30_parse_fail = 0  # W5-1 §1 Fail Loud: 計數解析失敗(逐 row 細 log 會 noise)
            for tbl in soup.find_all("table"):
                for row in tbl.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        date_txt = cells[0].get_text(strip=True)
                        nav_txt  = cells[1].get_text(strip=True).replace(",","")
                        if _re.match(r"\d{2}/\d{2}", date_txt) and _re.match(r"[\d.]+$", nav_txt):
                            try:
                                nav_rows[date_txt] = float(nav_txt)
                            except (ValueError, TypeError):
                                # 已通過 regex 預檢仍解析失敗(如 "1.2.3"),累計後彙總 log
                                _nav30_parse_fail += 1
            if _nav30_parse_fail > 0:
                print(f"[nav30] ⚠️ {code} nav 解析失敗 {_nav30_parse_fail} 筆(已過 regex 預檢)")
            # 轉換日期（MoneyDJ 近期只顯示 MM/DD，需補年份）
            import datetime as _dt
            # 2026-08-11:原為 `_dt.date.today()`(Streamlit Cloud 是 UTC)+ inline
            # 重寫一份年份推斷。兩個問題:
            #   (1) §4.5 時區:UTC 比 TW 慢最多 8 小時,「TW 已跨日、UTC 未跨日」的
            #       窗內,當日條目會被推回**去年同日**(≈365 天錯置)→ nav_span_days
            #       與所有年化指標一起壞,而且序列看起來完全正常(單調、正值)。
            #   (2) §3.3 SSOT:`_infer_year_for_mmdd`(sources.py)是 v19.333 F5 為了
            #       同一個 bug 抽出的純函式,legacy 這份卻自己 inline 重寫一遍。
            # v19.333 F5 當時只修了安聯路徑,`_src_nav_30day` 於 2026-08-11 補修,
            # **legacy 這份是第三份、也是最後一份** —— 而 user 的持倉現在全部走 legacy。
            today = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).date()
            parsed = {}
            for mmdd, v in nav_rows.items():
                try:
                    mo, da = int(mmdd.split("/")[0]), int(mmdd.split("/")[1])
                    yr = _infer_year_for_mmdd(mo, da, today)
                    parsed[_dt.date(yr, mo, da)] = v
                except Exception as e:
                    # v19.184 F-MED:加 stderr log(§3.3 反捏造)
                    import sys as _sys
                    print(f'[fund_repository] nav_rows mmdd parse fail "{mmdd}": '
                          f'{type(e).__name__}: {e}', file=_sys.stderr)

            # 再查詢整年歷史（使用查詢 endpoint）
            end_dt   = today
            # v19.291:400d(~13 月)→ 2000d(~5.5 年),對齊 v19.281 cnyes/Morningstar 已做的窗口延伸
            # ——本函式先前漏做,是保單代碼(如 JFZN3) 3-3-3「成立 0.1 年」誤判的根因之一
            start_dt = today - _dt.timedelta(days=2000)
            # v13.8: page_type 互換 — 首選失敗自動換頁型重試
            _hist_pages = get_page_types_to_try(
                "yp010000" if _is_domestic_code(code) else "yp010001"
            )
            _hist_params = {
                "A": code, "B": start_dt.strftime("%Y%m%d"), "C": end_dt.strftime("%Y%m%d")
            }
            _hist_urls = [
                f"{BASE}/yf/yp004002.djhtm",
                f"{TCB_BASE}/funddj/yf/yp004002.djhtm",
                f"https://www.moneydj.com/funddj/yf/yp004002.djhtm",
                f"https://tcbbankfund.moneydj.com/funddj/yf/yp004002.djhtm",
            ]
            r2 = None
            for _hpage in _hist_pages:
                if r2 is not None:
                    break
                hdr_ext = {**HDR,
                           "Referer": f"https://www.moneydj.com/funddj/ya/{_hpage}.djhtm?a={code}"}
                for _hu in _hist_urls:
                    try:
                        _r2_try = fetch_url_with_retry(
                            _hu, headers=hdr_ext,
                            params=_hist_params, timeout=25, retries=2
                        )
                        if _r2_try is not None:
                            r2 = _r2_try
                            print(f"[hist] ✅ {code} page={_hpage}")
                            break
                    except Exception as _he:
                        print(f"[hist fallback] {_hu}: {_he}")
                        continue
            if r2 is not None:
                soup2 = BeautifulSoup(r2.text, "lxml")
                hist_rows = {}
                for tbl in soup2.find_all("table"):
                    for row in tbl.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) >= 2:
                            dt_txt  = cells[0].get_text(strip=True)
                            nav_txt = cells[1].get_text(strip=True).replace(",","")
                            if _re.match(r"\d{4}/\d{2}/\d{2}", dt_txt) and _re.match(r"[\d.]+$", nav_txt):
                                try:
                                    import pandas as _pd
                                    hist_rows[_pd.to_datetime(dt_txt)] = float(nav_txt)
                                except (ValueError, TypeError, AttributeError, IndexError, KeyError): pass  # smoke-allow-pass — parse best-effort,row invalid skip
                if len(hist_rows) >= 20:
                    import pandas as _pd
                    result["series"] = _pd.Series(hist_rows).sort_index()
                    print(f"[fetch_nav_hist] ✅ {len(result['series'])} 筆")

            # v14.4: 若歷史查詢失敗，用近30日資料（parsed 已是 date key）
            if result["series"] is None and len(parsed) >= 5:
                import pandas as _pd
                try:
                    _s30 = _pd.Series({_pd.Timestamp(k): v for k,v in parsed.items()}).sort_index()
                    result["series"] = _s30
                    # stderr:legacy 落到「近30日」是 user 8 檔全部 30 點的直接成因,
                    # 這一行必須線上看得見(見上方 stderr 註解)
                    import sys as _sys_n30
                    print(f"[fetch_nav_30] ⚠️ {code} legacy 落到近30日 "
                          f"{len(result['series'])} 筆 —— 長歷史來源全部失敗",
                          file=_sys_n30.stderr)
                except Exception as _ps_e:
                    print(f"[fetch_nav_30] 轉換失敗: {_ps_e}")
                    # 最後備援：呼叫 _src_nav_30day
                    _s30b = _src_nav_30day(code, _page_type)
                    if len(_s30b) >= 5:
                        result["series"] = _s30b
                        print(f"[fetch_nav_30b] ✅ {len(_s30b)} 筆")
    except Exception as e:
        print(f"[fetch_nav] {e}")

    # ── 4. 績效評比 wb07 (標準差/Sharpe/Alpha/Beta/R²/Tracking Error) ──
    try:
        risk_data = fetch_risk_metrics(code)
        result["risk_metrics"] = risk_data
        # 從 peer_compare 取年報酬率 → perf["1Y"]（備援）
        peer = risk_data.get("peer_compare", {})
        for row_name, row_vals in peer.items():
            if "基金" in row_name or (code.upper() in row_name.upper()):
                try:
                    yr_txt = str(list(row_vals.values())[0]).replace("%","")
                    result["perf"]["1Y"] = float(yr_txt)
                except (ValueError, TypeError, AttributeError, IndexError, KeyError): pass  # smoke-allow-pass — parse best-effort,row invalid skip
                break
    except Exception as e:
        print(f"[fetch_risk] {e}")

    # ── 4c. 含息總報酬率 wb01（優先使用，MoneyDJ 說明：已考慮配息）─────
    try:
        perf_wb01 = fetch_performance_wb01(code)
        if perf_wb01:
            # wb01 資料覆蓋 peer_compare 估算值（更精確）
            for k, v in perf_wb01.items():
                result["perf"][k] = v
            result["perf_source"] = "wb01"
    except Exception as e:
        print(f"[fetch_perf_wb01] {e}")

    # ── 4b. 持股（產業配置 + 前10大持股）─────────────────
    try:
        holdings_data = fetch_holdings(code)
        result["holdings"] = holdings_data
    except Exception as e:
        print(f"[fetch_holdings] {e}")

    # ── 5. 配息 wb05 ──────────────────────────────────────
    try:
        # v14.4: 境內用 funddividend，境外用 wb05（與 _src_tcb_div 邏輯一致）
        _is_dom_div = _is_domestic_code(code, _page_type)
        _div_page = "funddividend" if _is_dom_div else "wb05"
        _div_fallback = "wb05" if _is_dom_div else "funddividend"
        _wb05_r = None
        for _div_pg in [_div_page, _div_fallback]:
            for _db in [BASE, TCB_BASE + "/funddj",
                        "https://www.moneydj.com/funddj",
                        "https://tcbbankfund.moneydj.com/funddj"]:
                # v14.4: fetch_url_with_retry (Big5)
                _try_r = fetch_url_with_retry(f"{_db}/yp/{_div_pg}.djhtm?a={code}",
                                              timeout=20, retries=1)
                if _try_r is not None:
                    _wb05_r = _try_r
                    print(f"[div] ✅ {code} 配息頁={_div_pg}")
                    break
            if _wb05_r is not None:
                break
        r = _wb05_r
        if r is not None:
            soup = BeautifulSoup(r.text, "lxml")
            for tbl in soup.find_all("table"):
                txt = tbl.get_text()
                if "配息基準日" not in txt and "除息日" not in txt: continue
                rows = tbl.find_all("tr")[1:]
                for row in rows[:36]:  # 最多3年
                    cols = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cols) < 5: continue
                    try:
                        # v14.4: col[3]=TEXT"配息", col[4]=配息金額, col[5]=年化率, col[6]=幣別
                        if len(cols) < 5: continue
                        if "/" not in cols[0]: continue   # 跳過非日期行
                        _amt = safe_float(cols[4])
                        if _amt is None or _amt <= 0 or _amt > 1000: continue
                        _yld = safe_float(cols[5]) or 0.0 if len(cols) > 5 else 0.0
                        _cur = (cols[6].strip() if len(cols) > 6 and cols[6].strip()
                                else result.get("currency", "USD"))
                        result["dividends"].append({
                            "date":      cols[0],
                            "ex_date":   cols[1],
                            "pay_date":  cols[2],
                            "amount":    _amt,
                            "yield_pct": _yld,
                            "currency":  _cur,
                        })
                    except (ValueError, TypeError, AttributeError, IndexError, KeyError): pass  # smoke-allow-pass — parse best-effort,row invalid skip
                # v10: 取最新一筆 年化配息率% 作為 MoneyDJ 官方值
                if result["dividends"]:
                    latest_yield = result["dividends"][0].get("yield_pct", 0)
                    if latest_yield > 0:
                        result["moneydj_div_yield"] = round(latest_yield, 2)
                        print(f"[wb05] MoneyDJ 年化配息率: {latest_yield:.2f}%")
                break
    except Exception as e:
        print(f"[fetch_div] {e}")

    # ── 6. 計算 指標（優先使用 wb07 標準差）────────────
    # ── 最終備援：使用 fetch_nav() 完整 TCB 多路徑爬取 ─────────────
    if result["series"] is None or len(result["series"]) < 10:
        try:
            _fallback_s = fetch_nav(code, portal="")
            if len(_fallback_s) >= 10:
                result["series"] = _fallback_s
                result["error"] = None
                print(f"[fetch_nav_fallback] \u2705 {len(_fallback_s)} \u7b46")
        except Exception as _fnf_e:
            print(f"[fetch_nav_fallback] {_fnf_e}")

    # v19.284:本函式的「Step 3+ 原始流程」是與 _fetch_fund_single 平行的第二條
    # NAV pipeline(前面 Step 2 多來源 orchestrator 若 _s_ok/_m_ok 判斷失敗才會
    # 走到這裡)。user 反饋 TLZF9 banner 顯示「來源:—」且無跨度 —— 根因正是這條
    # legacy pipeline 從未設 data_source/nav_span_days,也從未套用 span-extend。
    # 呼叫與 _fetch_fund_single 相同的共用函式(SSOT,不重寫第二份 span-extend),
    # 命中即用長歷史覆蓋;未命中也至少標出 data_source,banner 不再顯示「—」。
    if result.get("series") is not None and len(result["series"]) >= 10:
        _ext_s, _ext_src, _ext_span = _span_extend_insurance_nav(
            code, result["series"], result.get("data_source") or "moneydj_legacy_scrape",
            fund_name=result.get("fund_name") or "",
        )
        result["series"]        = _ext_s
        result["data_source"]   = _ext_src
        result["nav_span_days"] = _ext_span

    # v19.287:本函式(legacy pipeline)從未呼叫 fetch_holdings —— 唯一有持股呼叫的
    # 是 _fetch_fund_single(pipeline 1),但那邊呼叫的 bare name 從未被 import,
    # 兩條 pipeline 加總下來持股實際上從未真的被抓過。這裡補上與 pipeline 1
    # 同款呼叫(SSOT,呼叫同一顆共用函式,不重寫解析邏輯)。
    try:
        result["holdings"] = fetch_holdings(code)
    except Exception as e:
        print(f"[fetch_holdings] {e}")

    # v19.240 R8 EX-L1ORCH-1 退役:metrics + perf 注入 + reconcile 上提 L2
    # services.fund_service.finalize_fund_metrics(走 fetch_fund_from_moneydj_url_enriched
    # wrapper)。本層只 packaging raw series + dividends。
    if result["series"] is not None and len(result["series"]) < 10:
        result["error"] = f"只取到 {len(result['series'])} 筆淨值（建議≥10）"
    elif result["series"] is None:
        # v10.7.1 改善：淨值歷史失敗時，嘗試從 perf/risk 數據重建部分指標
        # 並給出明確的操作指引
        _has_perf = bool(result.get("perf"))
        _has_risk = bool(result.get("risk_metrics"))
        if _has_perf or _has_risk:
            result["error"] = (
                "⚠️ 淨值歷史抓取失敗（MoneyDJ 可能封鎖伺服器 IP）\n"
                "但已取得部分績效/風險數據，可繼續查看。\n"
                "💡 建議：直接貼 MoneyDJ 完整網址以取得最佳結果"
            )
        else:
            # ── 記憶體快照 fallback（網路斷線時顯示上次成功資料）──
            _snap_key = (code or result.get("full_key", "")).upper()
            if _snap_key and _snap_key in _FUND_SNAPSHOT:
                _snap = _FUND_SNAPSHOT[_snap_key]
                result.update({k: v for k, v in _snap.items() if v})
                result["error"]   = None
                result["warning"] = "⚠️ 網路暫時無法連線，顯示上次快照資料（數值可能稍舊）"
                print(f"[snapshot] ✅ {_snap_key} 使用記憶體快照")
            else:
                result["error"] = (
                    "❌ 無法取得基金資料（所有來源均失敗）\n"
                    "💡 解決方案：\n"
                    "① 直接貼 MoneyDJ 完整網址（比代碼更準確）：\n"
                    "   境內基金：www.moneydj.com/funddj/ya/yp010000.djhtm?a={code}\n"
                    "   境外基金：www.moneydj.com/funddj/ya/yp010001.djhtm?a={code}\n"
                    "② 於下方手動填入淨值、配息數據"
                ).format(code=result.get("full_key","???"))

    # ── 成功取得資料時更新記憶體快照 ──────────────────────────────────
    _snap_key = (code or result.get("full_key", "")).upper()
    if _snap_key and result.get("series") is not None and result.get("error") is None:
        # 快照不含 series（節省記憶體），保留 metrics/perf/fund_name 等輕量欄位
        # ⚠️ 2026-08-11 稽核登記(**刻意不改**):`v not in (None, [], {})` 是與
        # merge_non_empty 同型的判空,遇 pd.Series 會拋 ValueError。目前靠上一行
        # 「顯式排除 `series` 這個 key」擋住 —— 是**靠記得排除**而不是型別安全,
        # 只要 result 多出第二個 Series/DataFrame 欄位(例如未來加 benchmark 序列),
        # 這行就會在「成功取得資料」的收尾階段炸,最容易被誤判成抓取失敗。
        # 不改的理由(§-1):本行語意是「排除 None/[]/{} 但**保留空字串**」,
        # 與 `_is_empty_value`(空字串也算空)不同源。直接換會靜默改變快照欄位集合,
        # 屬於「修 bug 順手改到不相干行為」。等真的加第二個陣列欄位再一起處理。
        _FUND_SNAPSHOT[_snap_key] = {
            k: v for k, v in result.items()
            if k not in ("series",) and v not in (None, [], {})
        }
        print(f"[snapshot] 💾 {_snap_key} 快照已更新")

    return result




# ════════════════════════════════════════════════════════════
# v11.0 B-9b-6：search_fundclear / search_moneydj_by_name / _parse_nav_html / fetch_nav / fetch_div
# ════════════════════════════════════════════════════════════

def search_fundclear(keyword: str) -> list:
    """用 fundclear REST API 搜尋境外基金（Colab 可存取）"""
    results = []
    seen = set()
    kw = keyword.strip()
    try:
        body = {
            "fundName": kw, "fundCode": "",
            "fundAsset": "all", "fundAssetSub": "all",
            "fundInv": "all", "invArea": "all", "invAreaSub": "all",
            "agentCode": "all", "orgCode": "all",
            "pageNum": 1, "pageSize": 20,
        }
        r = requests.post(
            "https://www.fundclear.com.tw/api/offshore/fund-info/fund-search/query",
            json=body, headers=HDR_JSON, timeout=20, proxies=_proxies(), verify=_ssl_verify()
        )
        print(f"[fundclear] status={r.status_code}")
        if r.status_code == 200:
            d = r.json()
            # 嘗試各種回傳結構
            raw = d.get("data") or {}
            fund_list = (raw.get("list") or raw.get("fundList") or
                         (raw if isinstance(raw, list) else []))
            for item in fund_list:
                code = str(item.get("fundCode") or item.get("code") or "")
                name = str(item.get("fundName") or item.get("name") or "")
                # v19.336 review M7:原裸 float() 在單筆 nav 為非數字("N/A"等)時
                # ValueError 中斷整個迴圈 → 壞筆之後的搜尋結果全部丟失(外層
                # except 包整批)。改 safe_float 逐筆容錯,單筆壞 nav 只影響該筆。
                nav = safe_float(item.get("nav") or item.get("latestNav")) or 0.0
                if not code or not name or code in seen: continue
                seen.add(code)
                portal = "allianz" if ("安聯" in name or "AGIF" in code) else ""
                results.append({"full_key": code, "name": name,
                                 "portal": portal, "nav": nav, "source": "fundclear"})
            print(f"[fundclear] {len(results)} 筆")
    except Exception as e:
        print(f"[fundclear] ERR: {e}")
    return results


def search_moneydj_by_name(keyword: str) -> list:
    """搜尋基金：① fundclear API → ② MoneyDJ 選單 → ③ fundsearch"""
    kw = keyword.strip()
    kw_up = kw.upper()
    results = []
    seen = set()

    # ① fundclear
    for r in search_fundclear(kw):
        if r["full_key"] not in seen:
            seen.add(r["full_key"]); results.append(r)

    # ② MoneyDJ fund-page.html 選單
    for portal_name, url in [
        ("allianz", "https://tcbbankfund.moneydj.com/fund-page.html"),  # Fix: correct subdomain
        ("chubb",   "https://chubb.moneydj.com/fund-page.html?sUrl=$W$HTML$SELECT]DJHTM"),
    ]:
        try:
            r = requests.get(url, headers=HDR, timeout=20, proxies=_proxies(), verify=_ssl_verify())
            if r.status_code != 200: continue
            # v13.3: 同時支援 TLZF9 / ACTI98（無 dash）和 ABC-XYZ123（有 dash）
            for val, text in re.findall(
                r'value="([A-Z0-9a-z]{4,25}(?:-[A-Z0-9a-z]{3,20})?)"[^>]*>([^<]+)<',
                r.text, re.IGNORECASE
            ):
                if kw_up in text.upper():
                    fk = val.upper()
                    if fk in seen: continue
                    seen.add(fk)
                    name = re.sub(r"^[A-Z0-9]{3,20}\s*[-\u2013]\s*", "",
                                  text.strip(), flags=re.IGNORECASE).strip()
                    results.append({"full_key": fk, "name": name or text.strip(),
                                    "portal": portal_name, "nav": 0.0, "source": "moneydj_menu"})
        except Exception as e:
            print(f"[fund_page {portal_name}] ERR: {e}")

    # ③ fundsearch 備援
    if not results:
        try:
            url = f"https://www.moneydj.com/funddjx/fundsearch.xdjhtm?keyword={requests.utils.quote(kw)}"
            r = requests.get(url, headers=HDR, timeout=15, proxies=_proxies(), verify=_ssl_verify())
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "lxml")
                for tbl in soup.find_all("table"):
                    for row in tbl.find_all("tr")[1:]:
                        fk = ""; name = ""
                        for a in row.find_all("a", href=True):
                            mx = re.search(r"[aA]=([A-Z0-9a-z]{3,25})", a["href"])
                            if mx: fk = mx.group(1); name = a.get_text(strip=True); break
                        if fk and len(name) >= 3 and fk not in seen:
                            seen.add(fk)
                            results.append({"full_key": fk, "name": name,
                                            "portal": "", "nav": 0.0, "source": "mj_search"})
        except Exception as e:
            print(f"[fundsearch] ERR: {e}")

    print(f"[search_total] {kw!r} → {len(results)} 筆")
    return results[:15]
